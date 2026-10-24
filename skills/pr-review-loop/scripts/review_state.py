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

"""Collect the pr-guardian review state of a pull request as JSON evidence.

  review_state.py --pr 42 [--repo owner/name]     fetch live via `gh api graphql`
  review_state.py --from-file response.json       read a saved GraphQL response

This is a collector (ENGINEERING_STANDARD S9). It counts and quotes; it does not
decide whether a finding is right, whether pushback is good, or whether to
escalate. `escalation_signals` lists facts (counts, timestamps), never advice.

Markers it reads (see references/commands.md):
  first line of a thread's first comment   <!-- pr-guardian:finding id=R-001 severity=P1 -->
  in a pr-guardian reply                   <!-- pr-guardian:status id=R-001 status=reopened -->
  in the nits summary PR comment           <!-- pr-guardian:nits -->
Engineer commands it reads: `/ai-review wontfix: <reason>` (thread reply) and
`/ai-review escalate: <why>` (PR comment).

Exit codes:
  0   no open threads (P0-P3, unparsed-marker, or human) and the verdict check
      concluded SUCCESS
  1   open work remains, or the verdict is missing, pending, or not SUCCESS
  2   gh unavailable, the API call failed, or the response is not usable
  64  usage error

Surface (V3): review threads, their comments, PR comments, pr-guardian review
submissions, labels, and the head commit's check rollup. Not checked (V5):
whether a fix is correct, and anything beyond the first page of each
connection; truncation is reported in `not_checked`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Mirrors skills/review/scripts/findings.py. This skill must run standalone
# after `npx skills add`, so it cannot import that file; a test asserts the
# copies agree whenever both are present.
ID_PATTERN = r"^[A-Z][A-Z0-9]*-[0-9]{3,}$"
SEVERITIES = ("P0", "P1", "P2", "P3", "nit")
BLOCKING_SEVERITIES = ("P0", "P1", "P2", "P3")
STATUSES = ("new", "still_open", "reopened", "fixed", "accepted_pushback")

DEFAULT_CHECK = "pr-guardian/verdict"
DEFAULT_BOT_LOGINS = ("github-actions", "pr-guardian")
NEEDS_HUMAN_LABEL = "needs-human"
OVERRIDE_LABEL = "human-override"

REOPEN_SIGNAL_THRESHOLD = 2
REJECTED_PUSHBACK_THRESHOLD = 2
ROUNDS_SIGNAL_THRESHOLD = 3

MARKER_ANY = re.compile(r"<!--\s*pr-guardian:", re.IGNORECASE)
MARKER = re.compile(r"<!--\s*pr-guardian:([a-z_-]+)((?:\s+[^\s=]+=[^\s]+)*)\s*-->")
WONTFIX = re.compile(r"(?im)^\s*/ai-review\s+wontfix:[ \t]*(.*)$")
ESCALATE = re.compile(r"(?im)^\s*/ai-review\s+escalate:[ \t]*(.*)$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number url state headRefName baseRefName
      labels(first: 50) { nodes { name } }
      reviewThreads(first: 100) {
        pageInfo { hasNextPage }
        nodes {
          id isResolved isOutdated path line
          comments(first: 50) {
            pageInfo { hasNextPage }
            nodes { author { login } body createdAt url }
          }
        }
      }
      reviews(first: 100) {
        pageInfo { hasNextPage }
        nodes { author { login } state submittedAt body }
      }
      comments(last: 100) {
        nodes { author { login } body createdAt url }
      }
      commits(last: 1) {
        nodes { commit { oid statusCheckRollup { contexts(first: 100) { nodes {
          __typename
          ... on CheckRun { name status conclusion
                            checkSuite { workflowRun { workflow { name } } } }
          ... on StatusContext { context state }
        } } } } }
      }
    }
  }
}
"""


class GhError(Exception):
    """gh is missing, failed, or returned something unusable."""


def run_gh(args: list[str]) -> str:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                              shell=False, check=False)
    except FileNotFoundError as exc:
        raise GhError("gh CLI not found on PATH") from exc
    if proc.returncode != 0:
        raise GhError(f"gh {args[0]} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def resolve_repo() -> str:
    out = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
    if not REPO_PATTERN.match(out):
        raise GhError(f"could not resolve the current repository (got {out!r})")
    return out


def fetch(repo: str, number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    out = run_gh(["api", "graphql", "-f", f"query={QUERY}", "-f", f"owner={owner}",
                  "-f", f"name={name}", "-F", f"number={number}"])
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned non-JSON output: {exc}") from exc


# --- parsing ----------------------------------------------------------------

def _fields(raw: str) -> dict[str, str]:
    return dict(pair.split("=", 1) for pair in raw.split())


def parse_finding_marker(body: str) -> tuple[str, dict[str, str] | None, str]:
    """Classify a thread's first comment.

    Returns (kind, fields, reason): kind is "none" (no pr-guardian marker at
    all), "finding" (valid; fields has id and severity), or "unparsed"
    (something marker-like that does not meet the contract; reason says why).
    """
    if not MARKER_ANY.search(body or ""):
        return "none", None, ""
    first = (body or "").lstrip().splitlines()[0] if (body or "").strip() else ""
    m = MARKER.match(first.strip())
    if not m:
        return "unparsed", None, "first line is not a well-formed pr-guardian marker"
    if m.group(1) != "finding":
        return "unparsed", None, f"marker kind {m.group(1)!r} is not 'finding'"
    fields = _fields(m.group(2))
    fid, sev = fields.get("id", ""), fields.get("severity", "")
    if not re.match(ID_PATTERN, fid):
        return "unparsed", None, f"id {fid!r} does not match {ID_PATTERN}"
    if sev not in SEVERITIES:
        return "unparsed", None, f"severity {sev!r} not one of {list(SEVERITIES)}"
    return "finding", {"id": fid, "severity": sev}, ""


def parse_status_markers(body: str) -> list[dict[str, str]]:
    out = []
    for m in MARKER.finditer(body or ""):
        if m.group(1) == "status":
            fields = _fields(m.group(2))
            if fields.get("status") in STATUSES:
                out.append(fields)
    return out


def _login(node: dict[str, Any]) -> str:
    author = node.get("author") or {}
    return author.get("login") or "ghost"


def _nodes(conn: Any) -> list[dict[str, Any]]:
    if not isinstance(conn, dict):
        return []
    return [n for n in conn.get("nodes") or [] if isinstance(n, dict)]


def _truncated(conn: Any) -> bool:
    return bool(isinstance(conn, dict) and (conn.get("pageInfo") or {}).get("hasNextPage"))


def _verdict(pr: dict[str, Any], check_name: str) -> dict[str, Any]:
    commits = _nodes(pr.get("commits"))
    commit = commits[-1].get("commit", {}) if commits else {}
    rollup = commit.get("statusCheckRollup") or {}
    found: dict[str, Any] = {"check": check_name, "found": False, "status": None,
                             "conclusion": None, "head_sha": commit.get("oid")}
    for ctx in _nodes(rollup.get("contexts")):
        if ctx.get("__typename") == "StatusContext":
            if ctx.get("context") == check_name:
                state = ctx.get("state")
                found.update(found=True, status="COMPLETED" if state != "PENDING" else "PENDING",
                             conclusion=state if state != "PENDING" else None)
            continue
        workflow = (((ctx.get("checkSuite") or {}).get("workflowRun") or {})
                    .get("workflow") or {}).get("name")
        names = {ctx.get("name")}
        if workflow:
            names.add(f"{workflow} / {ctx.get('name')}")
        if check_name in names:
            found.update(found=True, status=ctx.get("status"),
                         conclusion=ctx.get("conclusion"))
    return found


def build_state(response: Any, check_name: str = DEFAULT_CHECK,
                bot_logins: tuple[str, ...] = DEFAULT_BOT_LOGINS) -> dict[str, Any]:
    """Turn a GraphQL response into the evidence document. Raises GhError."""
    if not isinstance(response, dict):
        raise GhError("response is not a JSON object")
    if response.get("errors"):
        msgs = [e.get("message", "?") for e in response["errors"] if isinstance(e, dict)]
        raise GhError(f"GraphQL errors: {msgs}")
    pr = (((response.get("data") or {}).get("repository") or {}).get("pullRequest"))
    if not isinstance(pr, dict):
        raise GhError("response has no data.repository.pullRequest")

    threads_raw = _nodes(pr.get("reviewThreads"))
    bots = set(bot_logins)
    for t in threads_raw:
        comments = _nodes(t.get("comments"))
        if comments and parse_finding_marker(comments[0].get("body", ""))[0] == "finding":
            bots.add(_login(comments[0]))

    reviews = [r for r in _nodes(pr.get("reviews")) if _login(r) in bots]
    review_times = sorted(r.get("submittedAt") or "" for r in reviews)
    not_checked: list[str] = []
    if _truncated(pr.get("reviewThreads")):
        not_checked.append("review threads beyond the first 100")
    if _truncated(pr.get("reviews")):
        not_checked.append("reviews beyond the first 100 (round count is a floor)")

    open_, resolved, unparsed, other_open, pending = [], [], [], [], []
    signals: list[dict[str, Any]] = []
    reopen_by_id: dict[str, int] = {}
    threads_by_id: dict[str, list[str]] = {}

    for t in threads_raw:
        comments = _nodes(t.get("comments"))
        if _truncated(t.get("comments")):
            not_checked.append(f"comments beyond the first 50 in thread {t.get('id')}")
        first = comments[0] if comments else {}
        kind, fields, reason = parse_finding_marker(first.get("body", ""))
        base = {"thread_id": t.get("id"), "path": t.get("path"), "line": t.get("line"),
                "is_outdated": bool(t.get("isOutdated")), "url": first.get("url")}
        resolved_flag = bool(t.get("isResolved"))

        if kind == "none":
            if not resolved_flag:
                other_open.append({**base, "author": _login(first) if first else None})
            continue
        if kind == "unparsed":
            unparsed.append({**base, "is_resolved": resolved_flag, "reason": reason,
                             "first_line": (first.get("body") or "").strip().splitlines()[0][:200]})
            continue

        fid = fields["id"]
        threads_by_id.setdefault(fid, []).append(t.get("id"))
        statuses: list[str] = []
        wontfix: list[dict[str, Any]] = []
        for c in comments[1:]:
            is_bot = _login(c) in bots
            if is_bot:
                for s in parse_status_markers(c.get("body", "")):
                    statuses.append(s["status"])
            else:
                for m in WONTFIX.finditer(c.get("body", "")):
                    bot_after = [b for b in comments if _login(b) in bots
                                 and (b.get("createdAt") or "") > (c.get("createdAt") or "")]
                    accepted = any(s["status"] == "accepted_pushback"
                                   for b in bot_after for s in parse_status_markers(b.get("body", "")))
                    wontfix.append({"reason": m.group(1).strip(), "at": c.get("createdAt"),
                                    "by": _login(c), "bot_replies_after": len(bot_after),
                                    "accepted_marker_after": accepted})
        reopen_events = statuses.count("reopened")
        reopen_by_id[fid] = reopen_by_id.get(fid, 0) + reopen_events
        created = first.get("createdAt") or ""
        rounds_open = sum(1 for r in review_times if r >= created) if created else 0
        last = comments[-1] if comments else {}
        entry = {**base, "finding_id": fid, "severity": fields["severity"],
                 "reopen_events": reopen_events, "last_status": statuses[-1] if statuses else None,
                 "rounds_since_raised": rounds_open, "wontfix_replies": len(wontfix),
                 "last_comment_by": "pr-guardian" if _login(last) in bots else "engineer",
                 "first_comment_excerpt": "\n".join((first.get("body") or "").splitlines()[1:])[:400]}

        if resolved_flag:
            resolved.append(entry)
            continue
        open_.append(entry)

        if wontfix and wontfix[-1]["bot_replies_after"] == 0:
            pending.append({"thread_id": t.get("id"), "finding_id": fid,
                            "reason": wontfix[-1]["reason"], "replied_at": wontfix[-1]["at"]})
        answered = [w for w in wontfix if w["bot_replies_after"] and not w["accepted_marker_after"]]
        if answered:
            w = answered[-1]
            signals.append({"kind": "pushback_answered_thread_still_open", "finding_id": fid,
                            "thread_id": t.get("id"),
                            "fact": f"wontfix posted {w['at']}; pr-guardian replied "
                                    f"{w['bot_replies_after']} time(s) after; no accepted_pushback "
                                    f"status; thread unresolved"})
        if len(answered) >= REJECTED_PUSHBACK_THRESHOLD:
            signals.append({"kind": "pushback_rejected_repeatedly", "finding_id": fid,
                            "thread_id": t.get("id"),
                            "fact": f"{len(answered)} wontfix replies each answered without "
                                    f"accepted_pushback"})
        if rounds_open >= ROUNDS_SIGNAL_THRESHOLD:
            signals.append({"kind": "open_across_rounds", "finding_id": fid,
                            "thread_id": t.get("id"),
                            "fact": f"unresolved through {rounds_open} pr-guardian review rounds"})

    for fid, count in sorted(reopen_by_id.items()):
        if count >= REOPEN_SIGNAL_THRESHOLD:
            signals.append({"kind": "finding_reopened_repeatedly", "finding_id": fid,
                            "thread_id": None, "fact": f"{fid} reopened {count} times"})
    for fid, ids in sorted(threads_by_id.items()):
        if len(ids) > 1:
            signals.append({"kind": "finding_id_in_multiple_threads", "finding_id": fid,
                            "thread_id": None, "fact": f"{fid} appears in {len(ids)} threads"})

    pr_comments = _nodes(pr.get("comments"))
    nits = None
    for c in pr_comments:
        if _login(c) in bots and re.search(r"<!--\s*pr-guardian:nits\b", c.get("body") or ""):
            nits = {"url": c.get("url"), "created_at": c.get("createdAt"),
                    "body": (c.get("body") or "")[:4000]}
    escalations = [{"by": _login(c), "at": c.get("createdAt"), "why": m.group(1).strip()}
                   for c in pr_comments if _login(c) not in bots
                   for m in ESCALATE.finditer(c.get("body") or "")]

    labels = sorted(n.get("name") for n in _nodes(pr.get("labels")) if n.get("name"))
    blocking = [e for e in open_ if e["severity"] in BLOCKING_SEVERITIES]
    verdict = _verdict(pr, check_name)
    return {
        "pr": {"number": pr.get("number"), "url": pr.get("url"), "state": pr.get("state"),
               "head": pr.get("headRefName"), "base": pr.get("baseRefName")},
        "verdict": verdict,
        "labels": labels,
        "rounds": len(reviews),
        "open_blocking": len(blocking),
        "by_severity": {s: sum(1 for e in blocking if e["severity"] == s)
                        for s in BLOCKING_SEVERITIES},
        "threads": {
            "open": open_,
            "reopened": [e for e in open_ if e["reopen_events"] > 0],
            "resolved": resolved,
            "unparsed": unparsed,
            "other_open": other_open,
        },
        "pending_wontfix": pending,
        "nits_comment": nits,
        "escalation": {"requested": escalations,
                       "needs_human_label": NEEDS_HUMAN_LABEL in labels,
                       "human_override_label": OVERRIDE_LABEL in labels},
        "escalation_signals": signals,
        "not_checked": not_checked,
    }


def exit_code(state: dict[str, Any]) -> int:
    threads = state["threads"]
    open_work = (state["open_blocking"]
                 or any(not u["is_resolved"] for u in threads["unparsed"])
                 or threads["other_open"])
    verdict = state["verdict"]
    passed = verdict["found"] and verdict["conclusion"] == "SUCCESS"
    return 0 if passed and not open_work else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, help="pull request number")
    parser.add_argument("--repo", help="owner/name (default: the current gh repo)")
    parser.add_argument("--from-file", help="read a saved GraphQL response instead of calling gh")
    parser.add_argument("--check-name", default=DEFAULT_CHECK,
                        help=f"verdict check name (default: {DEFAULT_CHECK!r})")
    parser.add_argument("--bot-login", action="append", default=[],
                        help="extra login to treat as pr-guardian (repeatable)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if not args.from_file and args.pr is None:
        print("review_state: give --pr N or --from-file FILE", file=sys.stderr)
        return 64
    if args.pr is not None and args.pr < 1:
        print("review_state: --pr must be a positive integer", file=sys.stderr)
        return 64
    if args.repo and not REPO_PATTERN.match(args.repo):
        print("review_state: --repo must look like owner/name", file=sys.stderr)
        return 64

    try:
        if args.from_file:
            try:
                response = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise GhError(f"cannot read {args.from_file}: {exc}") from exc
        else:
            response = fetch(args.repo or resolve_repo(), args.pr)
        state = build_state(response, args.check_name,
                            tuple(DEFAULT_BOT_LOGINS) + tuple(args.bot_login))
    except GhError as exc:
        print(f"review_state: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(state, indent=2))
    return exit_code(state)


if __name__ == "__main__":
    sys.exit(main())
