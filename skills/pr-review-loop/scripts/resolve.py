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

"""Resolve a pr-guardian review thread the reviewer has already verified.

  resolve.py --pr 42 --thread-id PRRT_x [--repo owner/name]
  resolve.py --from-file response.json --thread-id PRRT_x    use a saved GraphQL response
  add --dry-run to print the mutation instead of sending it

pr-guardian replies "Verified fixed" or "Pushback accepted" with a
`pr-guardian:status ... status=fixed|accepted_pushback` marker, but it cannot
resolve threads (its token has no contents: write). The PR author resolves
them. This script re-reads the thread first and refuses unless the latest
pr-guardian reply in it carries one of those statuses, so a thread is never
resolved before the reviewer has checked the fix or accepted the pushback.

Exit codes:
  0   thread resolved (or, with --dry-run, mutation printed)
  1   refused: the thread is not open, not a pr-guardian finding, or its latest
      pr-guardian reply is not status=fixed or status=accepted_pushback
  2   gh unavailable or the API call failed
  64  usage error
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_state as RS  # noqa: E402  (sibling module; the skill folder is self-contained)

MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def refusal(state: dict, thread_id: str) -> str | None:
    """Why this thread may not be resolved yet, or None if it may."""
    threads = state["threads"]
    if any(e["thread_id"] == thread_id for e in threads["ready_to_resolve"]):
        return None
    for e in threads["open"]:
        if e["thread_id"] == thread_id:
            return (f"{e['finding_id']}: the latest pr-guardian reply is "
                    f"status={e['latest_bot_status'] or 'none'}, not fixed or accepted_pushback; "
                    "wait for the reviewer to verify")
    if any(e["thread_id"] == thread_id for e in threads["resolved"]):
        return "thread is already resolved"
    return "not an open pr-guardian finding thread on this PR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--thread-id", required=True, help="review thread node id (PRRT_...)")
    parser.add_argument("--pr", type=int, help="pull request number")
    parser.add_argument("--repo", help="owner/name (default: the current gh repo)")
    parser.add_argument("--from-file", help="read a saved GraphQL response instead of calling gh")
    parser.add_argument("--bot-login", action="append", default=[],
                        help="extra login to treat as pr-guardian (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="print the mutation, send nothing")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if not args.from_file and args.pr is None:
        print("resolve: give --pr N or --from-file FILE", file=sys.stderr)
        return 64
    if args.pr is not None and args.pr < 1:
        print("resolve: --pr must be a positive integer", file=sys.stderr)
        return 64
    if args.repo and not RS.REPO_PATTERN.match(args.repo):
        print("resolve: --repo must look like owner/name", file=sys.stderr)
        return 64

    try:
        if args.from_file:
            try:
                response = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RS.GhError(f"cannot read {args.from_file}: {exc}") from exc
        else:
            response = RS.fetch(args.repo or RS.resolve_repo(), args.pr)
        state = RS.build_state(response, RS.DEFAULT_CHECK,
                               tuple(RS.DEFAULT_BOT_LOGINS) + tuple(args.bot_login))
    except RS.GhError as exc:
        print(f"resolve: {exc}", file=sys.stderr)
        return 2

    why = refusal(state, args.thread_id)
    if why:
        print(f"resolve: refused: {why}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps({"query": MUTATION.strip(),
                          "variables": {"threadId": args.thread_id}}, indent=2))
        return 0

    cmd = ["gh", "api", "graphql", "-f", f"query={MUTATION}", "-f", f"threadId={args.thread_id}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=False, check=False)
    except FileNotFoundError:
        print("resolve: gh CLI not found on PATH", file=sys.stderr)
        return 2
    if proc.returncode != 0:
        print(f"resolve: gh api graphql failed: {proc.stderr.strip() or proc.stdout.strip()}",
              file=sys.stderr)
        return 2
    try:
        thread = json.loads(proc.stdout)["data"]["resolveReviewThread"]["thread"]
    except (json.JSONDecodeError, KeyError, TypeError):
        print(f"resolve: unexpected response: {proc.stdout.strip()[:500]}", file=sys.stderr)
        return 2
    print(json.dumps(thread))
    return 0


if __name__ == "__main__":
    sys.exit(main())
