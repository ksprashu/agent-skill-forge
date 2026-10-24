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

"""Post a reply in a pull request review thread via `gh api graphql`.

  reply.py --thread-id PRRT_x --fixed <sha> [--note "what changed"]
  reply.py --thread-id PRRT_x --wontfix "<concrete technical reason>"
  reply.py --thread-id PRRT_x --body "free text"
  add --dry-run to print the mutation and variables instead of sending

It only replies. It never resolves a thread: resolution is the reviewer's call
once the next round confirms the fix or accepts the pushback.

Exit codes:
  0   reply posted (or, with --dry-run, mutation printed)
  2   gh unavailable or the API call failed
  64  usage error: missing/conflicting flags, empty wontfix reason, empty
      body, malformed thread id or SHA
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

MUTATION = """
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
    comment { id url }
  }
}
"""

THREAD_ID = re.compile(r"^[A-Za-z0-9_=-]{4,}$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")


class UsageError(Exception):
    pass


def compose_body(fixed: str | None, wontfix: str | None, body: str | None,
                 note: str | None) -> str:
    """Build the reply text, refusing anything the reviewer could not act on."""
    if wontfix is not None:
        reason = wontfix.strip()
        if not reason:
            raise UsageError("--wontfix needs a concrete technical reason; an empty one is refused")
        return f"/ai-review wontfix: {reason}"
    if fixed is not None:
        sha = fixed.strip().lower()
        if not SHA.match(sha):
            raise UsageError(f"--fixed expects a commit SHA (7-40 hex chars), got {fixed!r}")
        text = f"Fixed in {sha}."
        if note and note.strip():
            text += f" {note.strip()}"
        return text
    text = (body or "").strip()
    if not text:
        raise UsageError("--body is empty")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--thread-id", required=True, help="review thread node id (PRRT_...)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixed", metavar="SHA", help="reply 'Fixed in <sha>.'")
    group.add_argument("--wontfix", metavar="REASON", help="reply '/ai-review wontfix: <reason>'")
    group.add_argument("--body", help="free-text reply")
    parser.add_argument("--note", help="extra sentence appended to a --fixed reply")
    parser.add_argument("--dry-run", action="store_true", help="print the mutation, send nothing")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    try:
        if not THREAD_ID.match(args.thread_id):
            raise UsageError(f"--thread-id {args.thread_id!r} is not a GraphQL node id")
        text = compose_body(args.fixed, args.wontfix, args.body, args.note)
    except UsageError as exc:
        print(f"reply: {exc}", file=sys.stderr)
        return 64

    if args.dry_run:
        print(json.dumps({"query": MUTATION.strip(),
                          "variables": {"threadId": args.thread_id, "body": text}}, indent=2))
        return 0

    cmd = ["gh", "api", "graphql", "-f", f"query={MUTATION}",
           "-f", f"threadId={args.thread_id}", "-f", f"body={text}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=False, check=False)
    except FileNotFoundError:
        print("reply: gh CLI not found on PATH", file=sys.stderr)
        return 2
    if proc.returncode != 0:
        print(f"reply: gh api graphql failed: {proc.stderr.strip() or proc.stdout.strip()}",
              file=sys.stderr)
        return 2
    try:
        comment = json.loads(proc.stdout)["data"]["addPullRequestReviewThreadReply"]["comment"]
    except (json.JSONDecodeError, KeyError, TypeError):
        print(f"reply: unexpected response: {proc.stdout.strip()[:500]}", file=sys.stderr)
        return 2
    print(json.dumps(comment))
    return 0


if __name__ == "__main__":
    sys.exit(main())
