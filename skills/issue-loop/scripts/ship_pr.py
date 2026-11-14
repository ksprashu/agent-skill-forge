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

"""Stage 5 PR creation guard: conventional title, SHA-bound gate report, Refs vs Fixes safety.

  ship_pr.py --title "fix(auth): ..." (--body TEXT | --body-file FILE)
             [--base main] [--head branch] [--head-sha SHA]
             [--fixes N ...] [--refs N ...] [--repo owner/name] [--repo-root DIR]
             (--gate-report FILE | --no-gate --no-gate-reason REASON) [--dry-run]

Prevents premature GitHub issue auto-closure by refusing closing keywords
(`Fixes #N`, `Closes #N`, `Resolves #N`, or `Fixes https://github.com/.../issues/N`)
in PR bodies and branch commit messages for issues declared under `--refs`,
rejects protected branches, AI attribution, and secrets, and binds the PR to a
matching SHA/branch `verify_gate.py` PASS report (unless overridden loudly).

Exit codes:
  0   PR created (or --dry-run payload emitted)
  1   policy/gate refusal (protected branch, bad title, partial closing keyword,
      AI attribution, secret leak, missing/stale/failing gate report)
  2   gh or git missing/failed, or unreadable file
  64  usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_common as IC  # noqa: E402

CLOSING_CLAUSE_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*:?((?:[^\n.;]|\.(?!\s|$))*)",
    re.IGNORECASE,
)
ISSUE_NUM_REF_RE = re.compile(
    r"(?:https?://github\.com/[^/\s]+/[^/\s]+/issues/|(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?#)([1-9][0-9]*)\b",
    re.IGNORECASE,
)


def _sha_matches(expected: str, actual: str) -> bool:
    if not IC.SHA_PATTERN.match(expected) or not IC.SHA_PATTERN.match(actual):
        return False
    a, b = expected.lower(), actual.lower()
    return a.startswith(b) or b.startswith(a)


def find_closing_issue_refs(body: str) -> set[int]:
    """Return every issue number targeted by a GitHub closing keyword in text."""
    closed: set[int] = set()
    for match in CLOSING_CLAUSE_RE.finditer(body or ""):
        clause = match.group(1)
        for num_match in ISSUE_NUM_REF_RE.finditer(clause):
            closed.add(int(num_match.group(1)))
    return closed


def compose_pr_body(raw_body: str, fixes: list[int], refs: list[int]) -> str:
    """Ensure every --fixes and --refs issue is linked accurately without duplicate lines."""
    body = raw_body.strip()
    closed_in_body = find_closing_issue_refs(body)
    missing_lines: list[str] = []

    for num in fixes:
        if num not in closed_in_body:
            missing_lines.append(f"- Fixes #{num}")
    for num in refs:
        if not re.search(rf"\bRefs\s*:?\s*#{num}\b", body, re.IGNORECASE):
            missing_lines.append(f"- Refs #{num}")

    if not missing_lines:
        return body
    return f"{body}\n\n### Linked Issues\n" + "\n".join(missing_lines)


def _git_output(repo_root: Path | None, args: list[str]) -> str:
    cwd = repo_root if repo_root is not None else Path.cwd()
    try:
        proc = IC.run_cmd(["git", *args], cwd=cwd)
    except FileNotFoundError as exc:
        raise IC.GhError("git CLI not found on PATH") from exc
    if proc.returncode != 0:
        raise IC.GhError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def resolve_git_branch(repo_root: Path | None) -> str:
    branch = _git_output(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch or branch == "HEAD":
        raise IC.GhError("detached HEAD; pass --head <branch>")
    return branch


def resolve_git_head_sha(repo_root: Path | None) -> str:
    sha = _git_output(repo_root, ["rev-parse", "HEAD"])
    if not IC.SHA_PATTERN.match(sha):
        raise IC.GhError(f"unexpected git HEAD SHA: {sha!r}")
    return sha


def read_branch_commit_messages(repo_root: Path | None, base: str) -> str:
    """Return concatenated commit messages on HEAD not in base/origin-base."""
    cwd = repo_root if repo_root is not None else Path.cwd()
    base_ref = None
    for candidate in (f"origin/{base}", base):
        try:
            probe = IC.run_cmd(["git", "rev-parse", "--verify", "--quiet", candidate], cwd=cwd)
        except FileNotFoundError as exc:
            raise IC.GhError("git CLI not found on PATH") from exc
        if probe.returncode == 0:
            base_ref = candidate
            break
    if base_ref is None:
        raise IC.GhError(f"cannot resolve base ref {base!r} or origin/{base}")
    return _git_output(repo_root, ["log", f"{base_ref}..HEAD", "--format=%B"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--title", required=True, help="conventional PR title")
    body_group = parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="PR description markdown")
    body_group.add_argument("--body-file", help="read PR description from file ('-' for stdin)")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--head", help="head feature branch (default: current git branch)")
    parser.add_argument("--head-sha", help="expected HEAD commit SHA for --gate-report binding")
    parser.add_argument("--repo", help="owner/name")
    parser.add_argument("--repo-root", help="git repository root for branch/SHA/commit inspection")
    parser.add_argument("--fixes", action="append", type=int, default=[], help="fully resolved issue number (repeatable)")
    parser.add_argument("--refs", action="append", type=int, default=[], help="partially addressed issue number (repeatable)")
    parser.add_argument("--gate-report", help="verify_gate.py JSON output requiring verdict=PASS and matching branch/SHA")
    parser.add_argument("--no-gate", action="store_true", help="explicitly bypass --gate-report (requires --no-gate-reason)")
    parser.add_argument("--no-gate-reason", help="written justification (>= 20 chars) when using --no-gate")
    parser.add_argument("--dry-run", action="store_true", help="print gh pr create payload without calling gh")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    fixes = list(dict.fromkeys(args.fixes))
    refs = list(dict.fromkeys(args.refs))
    if not fixes and not refs:
        print("ship_pr: pass at least one --fixes N or --refs N", file=sys.stderr)
        return 64
    if any(n < 1 for n in fixes + refs):
        print("ship_pr: issue numbers must be positive integers", file=sys.stderr)
        return 64
    overlap = sorted(set(fixes) & set(refs))
    if overlap:
        print(f"ship_pr: issue(s) {overlap} cannot appear in both --fixes and --refs", file=sys.stderr)
        return 64
    if args.repo and not IC.REPO_PATTERN.match(args.repo):
        print("ship_pr: --repo must look like owner/name", file=sys.stderr)
        return 64
    if not IC.SAFE_BRANCH_PATTERN.match(args.base) or ".." in args.base:
        print(f"ship_pr: --base {args.base!r} is not a safe branch name", file=sys.stderr)
        return 64
    if args.head_sha and not IC.SHA_PATTERN.match(args.head_sha.strip()):
        print(f"ship_pr: --head-sha must be 7..40 hex chars, got {args.head_sha!r}", file=sys.stderr)
        return 64
    if args.gate_report and args.no_gate:
        print("ship_pr: pass either --gate-report or --no-gate, not both", file=sys.stderr)
        return 64
    if not args.gate_report:
        if not args.no_gate:
            print("ship_pr: --gate-report FILE is required (or pass --no-gate --no-gate-reason '...')", file=sys.stderr)
            return 64
        reason = (args.no_gate_reason or "").strip()
        if len(reason) < 20:
            print("ship_pr: --no-gate requires --no-gate-reason of at least 20 characters", file=sys.stderr)
            return 64

    try:
        if args.body_file:
            raw_body = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
        else:
            raw_body = args.body or ""
    except OSError as exc:
        print(f"ship_pr: cannot read {args.body_file}: {exc}", file=sys.stderr)
        return 2

    if not raw_body.strip():
        print("ship_pr: PR body cannot be empty", file=sys.stderr)
        return 64

    repo_root: Path | None = None
    if args.repo_root:
        repo_root = Path(args.repo_root)
        if not repo_root.is_dir():
            print(f"ship_pr: --repo-root {args.repo_root} is not a directory", file=sys.stderr)
            return 2

    title = args.title.strip()
    if not IC.CONVENTIONAL_TITLE_RE.match(title):
        print(
            f"ship_pr: refused: title {title!r} must use conventional commit format "
            "(e.g. 'fix(scope): short summary')",
            file=sys.stderr,
        )
        return 1

    try:
        head = args.head.strip() if args.head else resolve_git_branch(repo_root)
        live_head_sha = (
            resolve_git_head_sha(repo_root)
            if (repo_root is not None or not args.dry_run)
            else None
        )
        commit_log = (
            read_branch_commit_messages(repo_root, args.base)
            if (repo_root is not None or not args.dry_run)
            else ""
        )
    except IC.GhError as exc:
        print(f"ship_pr: {exc}", file=sys.stderr)
        return 2

    if not IC.SAFE_BRANCH_PATTERN.match(head) or ".." in head:
        print(f"ship_pr: refused: unsafe head branch {head!r}", file=sys.stderr)
        return 1
    if head in IC.PROTECTED_BRANCHES or head == args.base:
        print(f"ship_pr: refused: cannot open PR from protected/base branch {head!r}", file=sys.stderr)
        return 1

    if live_head_sha and args.head_sha and not _sha_matches(live_head_sha, args.head_sha.strip()):
        print(f"ship_pr: refused: --head-sha {args.head_sha!r} does not match live HEAD {live_head_sha!r}", file=sys.stderr)
        return 1

    expected_sha = live_head_sha or (args.head_sha.strip() if args.head_sha else None)

    combined_text = f"{title}\n{raw_body}\n{commit_log}"
    attr_hits = IC.check_ai_attribution(combined_text)
    if attr_hits:
        print(f"ship_pr: refused: forbidden AI attribution ({attr_hits[0]})", file=sys.stderr)
        return 1

    secret_hits = IC.find_secret_leaks({"title": title, "body": raw_body, "commits": commit_log})
    if secret_hits:
        print(f"ship_pr: refused: secret pattern detected ({secret_hits[0]})", file=sys.stderr)
        return 1

    closed_refs = find_closing_issue_refs(f"{raw_body}\n{commit_log}")
    premature = sorted(set(refs) & closed_refs)
    if premature:
        nums = ", ".join(f"#{n}" for n in premature)
        print(
            f"ship_pr: refused: partial issue(s) {nums} declared under --refs must not use "
            "auto-closing keywords (Fixes/Closes/Resolves) in PR body or commit messages",
            file=sys.stderr,
        )
        return 1

    if args.gate_report:
        try:
            gate = json.loads(Path(args.gate_report).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ship_pr: cannot read gate report {args.gate_report}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(gate, dict) or gate.get("verdict") != "PASS":
            print("ship_pr: refused: --gate-report verdict is not PASS", file=sys.stderr)
            return 1
        gate_sha = gate.get("head_sha")
        if not isinstance(gate_sha, str) or not IC.SHA_PATTERN.match(gate_sha):
            print("ship_pr: refused: --gate-report missing valid head_sha binding", file=sys.stderr)
            return 1
        gate_branch = gate.get("branch")
        if not isinstance(gate_branch, str) or gate_branch != head:
            print(
                f"ship_pr: refused: --gate-report branch {gate_branch!r} does not match head branch {head!r}",
                file=sys.stderr,
            )
            return 1
        if expected_sha and not _sha_matches(expected_sha, gate_sha):
            print(
                f"ship_pr: refused: stale --gate-report head_sha {gate_sha!r} does not match {expected_sha!r}",
                file=sys.stderr,
            )
            return 1

    final_body = compose_pr_body(raw_body, fixes, refs)
    cmd = ["gh", "pr", "create", "--base", args.base, "--head", head, "--title", title, "--body", final_body]
    if args.repo:
        cmd.extend(["--repo", args.repo])

    if args.dry_run:
        print(json.dumps({
            "action": "create_pr",
            "command": cmd,
            "payload": {
                "repo": args.repo,
                "base": args.base,
                "head": head,
                "head_sha": expected_sha,
                "title": title,
                "body": final_body,
                "fixes": fixes,
                "refs": refs,
                "gate_bypass_reason": args.no_gate_reason.strip() if args.no_gate else None,
            },
        }, indent=2))
        return 0

    try:
        out = IC.run_gh(cmd[1:], timeout=60)
    except IC.GhError as exc:
        print(f"ship_pr: {exc}", file=sys.stderr)
        return 2

    url = out.strip().splitlines()[-1].strip() if out.strip() else ""
    print(json.dumps({
        "action": "create_pr",
        "url": url,
        "head": head,
        "base": args.base,
        "head_sha": expected_sha,
        "fixes": fixes,
        "refs": refs,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
