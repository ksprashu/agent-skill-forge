#!/usr/bin/env python3
# Copyright 2026 Agent Skill Forge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deterministic L3 pre-merge gate and squash-merge executor.

  merge_pr.py --pr 42 [--repo owner/name] [--auto] [--dry-run | --execute]
  merge_pr.py --from-file response.json [--auto] [--dry-run]

Runs `review_state.py` logic first (refusing on any open thread, unresolved
human/nit/unparsed thread, missing/failing verdict, truncation, or conflict),
then enforces:
  - PR `state == "OPEN"`
  - `mergeable == "MERGEABLE"` and `mergeStateStatus` in `CLEAN` / `HAS_HOOKS`
  - zero open blocking threads and `pr-guardian/verdict == SUCCESS`
  - every check in `statusCheckRollup` completed with passing conclusion
  - `needs-human` label not active without `human-override`

Only when all gates pass and `--execute` is given does it invoke:
  `gh pr merge <N> --repo <owner/name> [--auto] --squash --delete-branch`

Exit codes:
  0   all gates clean (dry-run ready, or merge executed cleanly)
  1   refused by pre-merge gate (open threads, conflicts, BLOCKED, failing/pending checks)
  2   gh missing, API/command failed, or response unreadable/invalid
  64  usage error

Surface (V3): everything checked by `review_state.py` plus `mergeable`,
`mergeStateStatus`, and every check run / status context in the head commit's
`statusCheckRollup`. Not checked (V5): external branch-protection rules not
surfaced in `mergeStateStatus`, or checks beyond the first 100 contexts.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_state as RS  # noqa: E402  (sibling module; skill folder is self-contained)

CLEAN_MERGE_STATES = frozenset({"CLEAN", "HAS_HOOKS"})
PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})

_SECRET_RE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,})\b"
)


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED_TOKEN]", text)


def extract_checks(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every check run and status context from the head commit rollup."""
    pr = (((response.get("data") or {}).get("repository") or {}).get("pullRequest")) or {}
    commits = RS._nodes(pr.get("commits"))
    commit = commits[-1].get("commit", {}) if commits else {}
    rollup = commit.get("statusCheckRollup") or {}
    out: list[dict[str, Any]] = []
    for ctx in RS._nodes(rollup.get("contexts")):
        if ctx.get("__typename") == "StatusContext":
            state = ctx.get("state")
            out.append({
                "kind": "StatusContext",
                "name": ctx.get("context") or "<status>",
                "status": "COMPLETED" if state != "PENDING" else "PENDING",
                "conclusion": state if state != "PENDING" else None,
            })
            continue
        workflow = (((ctx.get("checkSuite") or {}).get("workflowRun") or {})
                    .get("workflow") or {}).get("name")
        name = ctx.get("name") or "<check>"
        full_name = f"{workflow} / {name}" if workflow else name
        out.append({
            "kind": "CheckRun",
            "name": full_name,
            "status": ctx.get("status"),
            "conclusion": ctx.get("conclusion"),
        })
    return out


def evaluate_merge_readiness(
    response: Any,
    check_name: str = RS.DEFAULT_CHECK,
    bot_logins: tuple[str, ...] = RS.DEFAULT_BOT_LOGINS,
    pr_number: int | None = None,
    repo: str | None = None,
    auto: bool = False,
    delete_branch: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """Evaluate all deterministic L3 merge gates against a GraphQL response."""
    state = RS.build_state(response, check_name=check_name, bot_logins=bot_logins,
                           allow_unknown_mergeable=False)
    reasons: list[str] = []

    pr_info = state["pr"]
    if pr_info.get("state") != "OPEN":
        reasons.append(f"PR state is {pr_info.get('state')!r}, expected 'OPEN'")

    threads = state["threads"]
    if threads["open"]:
        reasons.append(f"{len(threads['open'])} open pr-guardian thread(s)")
    unresolved_unparsed = [u for u in threads["unparsed"] if not u.get("is_resolved")]
    if unresolved_unparsed:
        reasons.append(f"{len(unresolved_unparsed)} unresolved unparsed-marker thread(s)")
    if threads["other_open"]:
        reasons.append(f"{len(threads['other_open'])} unresolved non-bot thread(s)")
    if state["not_checked"]:
        reasons.append(f"unchecked surfaces remain: {'; '.join(state['not_checked'])}")

    verdict = state["verdict"]
    if not (verdict.get("found") and verdict.get("status") == "COMPLETED"
            and verdict.get("conclusion") == "SUCCESS"):
        reasons.append(
            f"verdict {verdict.get('check')!r} is not SUCCESS "
            f"(found={verdict.get('found')}, status={verdict.get('status')}, "
            f"conclusion={verdict.get('conclusion')})"
        )

    merge = state["merge"]
    if merge.get("mergeable") != "MERGEABLE":
        reasons.append(f"mergeable is {merge.get('mergeable')!r}, expected 'MERGEABLE'")
    if merge.get("merge_state") not in CLEAN_MERGE_STATES:
        reasons.append(
            f"mergeStateStatus is {merge.get('merge_state')!r}, expected CLEAN or HAS_HOOKS"
        )

    checks = extract_checks(response)
    for chk in checks:
        if chk["status"] != "COMPLETED":
            reasons.append(f"check {chk['name']!r} has status {chk['status']!r}, not COMPLETED")
        elif chk["conclusion"] not in PASSING_CONCLUSIONS:
            reasons.append(f"check {chk['name']!r} concluded {chk['conclusion']!r}")

    esc = state["escalation"]
    if esc.get("needs_human_label") and not esc.get("human_override_label"):
        reasons.append("needs-human label is set without human-override")

    if RS.exit_code(state) != 0 and not reasons:
        reasons.append("review_state gate exited non-zero")

    ready = len(reasons) == 0
    num = pr_number if pr_number is not None else pr_info.get("number")
    cmd: list[str] | None = None
    if ready and num is not None:
        cmd = ["gh", "pr", "merge", str(num)]
        if repo:
            cmd.extend(["--repo", repo])
        if auto:
            cmd.append("--auto")
        cmd.append("--squash")
        if delete_branch:
            cmd.append("--delete-branch")

    return ready, {
        "ready": ready,
        "pr": pr_info,
        "merge": merge,
        "verdict": verdict,
        "checks": checks,
        "open_blocking": state["open_blocking"],
        "refusal_reasons": reasons,
        "command": cmd,
    }


def _execute_merge(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", shell=False, check=False)
    except FileNotFoundError as exc:
        raise RS.GhError("gh CLI not found on PATH") from exc
    stdout = _redact(proc.stdout or "")
    stderr = _redact(proc.stderr or "")
    if proc.returncode != 0:
        raise RS.GhError(f"gh pr merge failed: {stderr.strip() or stdout.strip()}")
    return stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, help="pull request number")
    parser.add_argument("--repo", help="owner/name (default: the current gh repo)")
    parser.add_argument("--from-file", help="read a saved GraphQL response instead of calling gh")
    parser.add_argument("--check-name", default=RS.DEFAULT_CHECK,
                        help=f"verdict check name (default: {RS.DEFAULT_CHECK!r})")
    parser.add_argument("--bot-login", action="append", default=[],
                        help="extra login to treat as pr-guardian (repeatable)")
    parser.add_argument("--auto", action="store_true",
                        help="pass --auto to `gh pr merge`")
    parser.add_argument("--no-delete-branch", action="store_true",
                        help="omit --delete-branch from `gh pr merge`")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="evaluate gates and print planned merge command (default)")
    mode.add_argument("--execute", action="store_true",
                      help="run `gh pr merge` if all gates pass (requires live --pr)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if not args.from_file and args.pr is None:
        print("merge_pr: give --pr N or --from-file FILE", file=sys.stderr)
        return 64
    if args.pr is not None and args.pr < 1:
        print("merge_pr: --pr must be a positive integer", file=sys.stderr)
        return 64
    if args.repo and not RS.REPO_PATTERN.match(args.repo):
        print("merge_pr: --repo must look like owner/name", file=sys.stderr)
        return 64
    if args.execute and (args.from_file or args.pr is None):
        print("merge_pr: --execute requires live --pr N without --from-file", file=sys.stderr)
        return 64

    try:
        repo: str | None = args.repo
        if args.from_file:
            try:
                raw = _redact(Path(args.from_file).read_text(encoding="utf-8"))
                response = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                raise RS.GhError(f"cannot read {args.from_file}: {exc}") from exc
        else:
            repo = args.repo or RS.resolve_repo()
            response = RS.fetch(repo, args.pr)

        ready, report = evaluate_merge_readiness(
            response,
            check_name=args.check_name,
            bot_logins=tuple(RS.DEFAULT_BOT_LOGINS) + tuple(args.bot_login),
            pr_number=args.pr,
            repo=repo,
            auto=args.auto,
            delete_branch=not args.no_delete_branch,
        )
        report["dry_run"] = not args.execute
        report["executed"] = False

        if not ready:
            print(json.dumps(report, indent=2))
            print(f"merge_pr: refused: {'; '.join(report['refusal_reasons'])}", file=sys.stderr)
            return 1

        if args.execute and report["command"]:
            report["gh_output"] = _execute_merge(report["command"])
            report["executed"] = True

    except RS.GhError as exc:
        print(f"merge_pr: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
