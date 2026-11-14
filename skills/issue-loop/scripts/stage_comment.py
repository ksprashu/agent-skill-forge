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

"""Post an idempotent structured stage comment (triage, plan, pr) on a GitHub issue.

  stage_comment.py --issue N --stage {triage,plan,pr} (--body TEXT | --body-file FILE)
                   [--repo owner/name] [--from-file FILE] [--trusted-login LOGIN]
                   [--update] [--dry-run]

Prepends `<!-- issue-loop:stage=<stage> v1 -->`, matches existing stage comments
only when authored by the authenticated viewer (or `--trusted-login`) with the
marker leading the body, refuses duplicate trusted comments unless `--update`
is passed, and blocks any unredacted secret or AI attribution.

Exit codes:
  0   comment posted/updated, or --dry-run preview printed
  1   refused: duplicate trusted stage marker without --update, secret leak,
      or AI attribution
  2   gh unavailable, API failure, or unreadable file
  64  usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_common as IC  # noqa: E402


def compose_comment_body(stage: str, raw_body: str) -> str:
    """Ensure the stage marker leads the comment and reject conflicting markers."""
    body = raw_body.strip()
    if not body:
        raise IC.UsageError("comment body cannot be empty")
    found_stages = IC.parse_stage_markers(body)
    wrong = [s for s in found_stages if s != stage]
    if wrong:
        raise IC.UsageError(f"body carries conflicting stage marker(s): {wrong} (expected {stage!r})")
    marker = IC.STAGE_MARKER_TEMPLATE.format(stage=stage)
    if IC.parse_leading_stage_marker(body) == stage:
        return body
    if found_stages:
        raise IC.UsageError("stage marker must appear on the first non-empty line of the comment")
    return f"{marker}\n{body}"


def _extract_comments(payload: Any) -> tuple[list[dict[str, Any]], str]:
    """Extract comment dicts (flattening --paginate --slurp pages) and optional viewer login."""
    if isinstance(payload, list):
        flat: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, list):
                flat.extend(c for c in item if isinstance(c, dict))
            elif isinstance(item, dict):
                flat.append(item)
        return flat, ""
    if isinstance(payload, dict):
        viewer = ""
        data_node = payload.get("data")
        if isinstance(data_node, dict):
            viewer = ((data_node.get("viewer") or {}).get("login") or "").strip()
        if "comments" in payload:
            conn = payload["comments"]
            if isinstance(conn, list):
                return [c for c in conn if isinstance(c, dict)], viewer
            if isinstance(conn, dict):
                return [c for c in (conn.get("nodes") or []) if isinstance(c, dict)], viewer
        issue = ((payload.get("data") or {}).get("repository") or {}).get("issue")
        if isinstance(issue, dict):
            comments, _ = _extract_comments(issue)
            return comments, viewer
    raise IC.GhError("comments payload must be a JSON array or issue GraphQL response")


def fetch_issue_comments(repo: str, issue: int) -> list[dict[str, Any]]:
    out = IC.run_gh(["api", "--paginate", "--slurp", f"repos/{repo}/issues/{issue}/comments?per_page=100"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise IC.GhError(f"gh api returned non-JSON comments: {exc}") from exc
    comments, _ = _extract_comments(data)
    return comments


def _comment_author(comment: dict[str, Any]) -> str:
    author = comment.get("user") or comment.get("author") or {}
    return (author.get("login") or "").strip()


def find_existing_stage_comment(
    comments: list[dict[str, Any]],
    stage: str,
    trusted_logins: set[str],
) -> dict[str, Any] | None:
    """Return the latest comment whose body leads with the stage marker from a trusted author."""
    if not trusted_logins:
        return None
    matches = [
        c for c in comments
        if _comment_author(c) in trusted_logins
        and IC.parse_leading_stage_marker(c.get("body") or "") == stage
    ]
    return matches[-1] if matches else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--issue", required=True, type=int, help="target GitHub issue number")
    parser.add_argument("--stage", required=True, choices=IC.STAGES, help="pipeline stage marker")
    body_group = parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="markdown comment body")
    body_group.add_argument("--body-file", help="read markdown comment body from file ('-' for stdin)")
    parser.add_argument("--repo", help="owner/name (default: resolved from current gh repo)")
    parser.add_argument("--from-file", help="read existing issue comments JSON instead of calling gh")
    parser.add_argument("--trusted-login", action="append", default=[], help="login trusted to own stage comments (repeatable)")
    parser.add_argument("--update", action="store_true", help="update existing stage comment in place")
    parser.add_argument("--dry-run", action="store_true", help="preview payload without calling gh write API")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if args.issue < 1:
        print("stage_comment: --issue must be a positive integer", file=sys.stderr)
        return 64
    if args.repo and not IC.REPO_PATTERN.match(args.repo):
        print("stage_comment: --repo must look like owner/name", file=sys.stderr)
        return 64

    try:
        if args.body_file:
            raw_body = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
        else:
            raw_body = args.body or ""
    except OSError as exc:
        print(f"stage_comment: cannot read {args.body_file}: {exc}", file=sys.stderr)
        return 2

    try:
        composed = compose_comment_body(args.stage, raw_body)
    except IC.UsageError as exc:
        print(f"stage_comment: {exc}", file=sys.stderr)
        return 64

    secret_hits = IC.find_secret_leaks(composed)
    if secret_hits:
        print(f"stage_comment: refused: unredacted secret in comment body ({secret_hits[0]})", file=sys.stderr)
        return 1

    attr_hits = IC.check_ai_attribution(composed)
    if attr_hits:
        print(f"stage_comment: refused: forbidden AI attribution in comment body ({attr_hits[0]})", file=sys.stderr)
        return 1

    trusted_logins = {login.strip() for login in args.trusted_login if login.strip()}
    try:
        if args.from_file:
            raw_comments = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
            comments, file_viewer = _extract_comments(raw_comments)
            if file_viewer:
                trusted_logins.add(file_viewer)
            repo = args.repo or "offline/local"
        else:
            repo = args.repo or IC.resolve_repo()
            trusted_logins.add(IC.resolve_viewer_login())
            comments = fetch_issue_comments(repo, args.issue)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"stage_comment: cannot read {args.from_file}: {exc}", file=sys.stderr)
        return 2
    except IC.GhError as exc:
        print(f"stage_comment: {exc}", file=sys.stderr)
        return 2

    existing = find_existing_stage_comment(comments, args.stage, trusted_logins)
    marker = IC.STAGE_MARKER_TEMPLATE.format(stage=args.stage)

    if existing and not args.update:
        cid = existing.get("id") or existing.get("databaseId")
        print(
            f"stage_comment: refused: stage {args.stage!r} comment already exists on issue #{args.issue} "
            f"(id={cid}); pass --update to replace it",
            file=sys.stderr,
        )
        return 1

    if existing and args.update:
        cid = existing.get("databaseId") if existing.get("databaseId") is not None else existing.get("id")
        if cid is None:
            print("stage_comment: existing stage comment has no numeric id for PATCH", file=sys.stderr)
            return 2
        if args.dry_run:
            print(json.dumps({
                "action": "update",
                "repo": repo,
                "issue": args.issue,
                "stage": args.stage,
                "marker": marker,
                "comment_id": cid,
                "trusted_logins": sorted(trusted_logins),
                "body": composed,
            }, indent=2))
            return 0
        try:
            out = IC.run_gh([
                "api", "-X", "PATCH", f"repos/{repo}/issues/comments/{cid}",
                "-f", f"body={composed}",
            ])
            resp = json.loads(out)
        except (IC.GhError, json.JSONDecodeError) as exc:
            print(f"stage_comment: failed to update comment {cid}: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"action": "update", "id": resp.get("id", cid), "url": resp.get("html_url")}))
        return 0

    if args.dry_run:
        print(json.dumps({
            "action": "create",
            "repo": repo,
            "issue": args.issue,
            "stage": args.stage,
            "marker": marker,
            "comment_id": None,
            "trusted_logins": sorted(trusted_logins),
            "body": composed,
        }, indent=2))
        return 0

    try:
        out = IC.run_gh([
            "api", "-X", "POST", f"repos/{repo}/issues/{args.issue}/comments",
            "-f", f"body={composed}",
        ])
        resp = json.loads(out)
    except (IC.GhError, json.JSONDecodeError) as exc:
        print(f"stage_comment: failed to create comment on issue #{args.issue}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"action": "create", "id": resp.get("id"), "url": resp.get("html_url")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
