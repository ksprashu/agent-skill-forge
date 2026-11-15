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

"""Collect GitHub issues, comments, trusted stage markers, and open PR links as JSON evidence.

  issue_state.py [--repo owner/name] [--issue N] [--limit 50] [--include-closed]
                 [--trusted-login LOGIN] [--out FILE]
  issue_state.py --from-file response.json [--repo owner/name] [--issue N]
                 [--include-closed] [--trusted-login LOGIN] [--out FILE]

Collector (ENGINEERING_STANDARD S9): extracts mechanical facts, redacts secrets
and PII at capture (S8), frames untrusted issue/comment bodies, marks stage
comments as `trusted: true` only when authored by the viewer or `--trusted-login`
with the marker leading the body, and never decides triage classifications.

Exit codes:
  0   issue(s) collected cleanly with zero truncation
  1   no matching issues found, or results truncated (`not_checked` non-empty)
  2   gh unavailable, GraphQL/API error, or unreadable input file
  64  usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_common as IC  # noqa: E402

LIST_QUERY_TEMPLATE = """
query($owner: String!, $name: String!, $limit: Int!) {{
  viewer {{ login }}
  repository(owner: $owner, name: $name) {{
    issues(first: $limit, states: {states}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      pageInfo {{ hasNextPage }}
      nodes {{
        number url state title body createdAt updatedAt
        author {{ login }}
        labels(first: 30) {{ nodes {{ name }} }}
        comments(first: 50) {{
          pageInfo {{ hasNextPage }}
          nodes {{ id databaseId author {{ login }} body createdAt url }}
        }}
      }}
    }}
    pullRequests(first: 50, states: [OPEN], orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      pageInfo {{ hasNextPage }}
      nodes {{
        number url title body headRefName state
        closingIssuesReferences(first: 20) {{ nodes {{ number }} }}
      }}
    }}
  }}
}}
"""

ISSUE_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  viewer { login }
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      number url state title body createdAt updatedAt
      author { login }
      labels(first: 30) { nodes { name } }
      comments(first: 100) {
        pageInfo { hasNextPage }
        nodes { id databaseId author { login } body createdAt url }
      }
    }
    pullRequests(first: 50, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage }
      nodes {
        number url title body headRefName state
        closingIssuesReferences(first: 20) { nodes { number } }
      }
    }
  }
}
"""

PR_ISSUE_REF_RE = re.compile(r"(?<![A-Za-z0-9_-])#([1-9][0-9]*)\b")


def _nodes(conn: Any) -> list[dict[str, Any]]:
    if isinstance(conn, list):
        return [n for n in conn if isinstance(n, dict)]
    if isinstance(conn, dict):
        return [n for n in (conn.get("nodes") or []) if isinstance(n, dict)]
    return []


def _has_next_page(conn: Any) -> bool:
    return bool(isinstance(conn, dict) and (conn.get("pageInfo") or {}).get("hasNextPage"))


def _login(node: dict[str, Any]) -> str:
    author = node.get("author") or node.get("user") or {}
    return author.get("login") or "ghost"


def build_list_query(include_closed: bool) -> str:
    """Return the GraphQL list query filtering OPEN or [OPEN, CLOSED] issues."""
    states = "[OPEN, CLOSED]" if include_closed else "[OPEN]"
    return LIST_QUERY_TEMPLATE.format(states=states)


def fetch_graphql(repo: str, issue: int | None, limit: int, include_closed: bool = False) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    if issue is not None:
        raw = IC.run_gh([
            "api", "graphql", "-f", f"query={ISSUE_QUERY}",
            "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={issue}",
        ])
    else:
        query = build_list_query(include_closed)
        raw = IC.run_gh([
            "api", "graphql", "-f", f"query={query}",
            "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"limit={limit}",
        ])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IC.GhError(f"gh returned non-JSON output: {exc}") from exc


def _extract_open_prs(repo_node: dict[str, Any], not_checked: list[str]) -> list[dict[str, Any]]:
    prs_conn = repo_node.get("pullRequests")
    if _has_next_page(prs_conn):
        not_checked.append("open pullRequests beyond first page")
    prs_out: list[dict[str, Any]] = []
    for pr in _nodes(prs_conn):
        closing_nums = {
            n["number"]
            for n in _nodes(pr.get("closingIssuesReferences"))
            if isinstance(n.get("number"), int)
        }
        title = IC.redact_secrets(pr.get("title") or "")
        body = IC.redact_secrets(pr.get("body") or "")
        mentioned = {
            int(m.group(1))
            for m in PR_ISSUE_REF_RE.finditer(f"{title}\n{body}")
        }
        prs_out.append({
            "number": pr.get("number"),
            "url": pr.get("url"),
            "state": pr.get("state") or "OPEN",
            "title": title,
            "head": pr.get("headRefName"),
            "closing_issues": sorted(closing_nums),
            "mentioned_issues": sorted(mentioned - closing_nums),
        })
    return prs_out


def build_state(
    response: Any,
    repo: str,
    target_issue: int | None = None,
    include_closed: bool = False,
    trusted_logins: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build redacted, injection-framed Stage 1 evidence JSON from a GraphQL payload."""
    if not isinstance(response, dict):
        raise IC.GhError("response is not a JSON object")
    if response.get("errors"):
        msgs = [e.get("message", "?") for e in response["errors"] if isinstance(e, dict)]
        raise IC.GhError(f"GraphQL errors: {msgs}")

    data_node = response.get("data") or {}
    repo_node = data_node.get("repository")
    if not isinstance(repo_node, dict):
        raise IC.GhError("response has no data.repository")

    trusted_set = {x.strip() for x in trusted_logins if isinstance(x, str) and x.strip()}
    viewer_login = ((data_node.get("viewer") or {}).get("login") or "").strip()
    if viewer_login:
        trusted_set.add(viewer_login)

    not_checked: list[str] = []
    raw_issues: list[dict[str, Any]] = []

    if target_issue is not None:
        if "issue" in repo_node:
            single = repo_node.get("issue")
            if single is None:
                raise IC.GhError(f"issue #{target_issue} not found in {repo}")
            if isinstance(single, dict):
                raw_issues = [single]
        else:
            raw_issues = [n for n in _nodes(repo_node.get("issues")) if n.get("number") == target_issue]
            if not raw_issues:
                raise IC.GhError(f"issue #{target_issue} not found in payload")
    else:
        issues_conn = repo_node.get("issues")
        if _has_next_page(issues_conn):
            not_checked.append("issues beyond first page")
        raw_issues = _nodes(issues_conn)

    open_prs = _extract_open_prs(repo_node, not_checked)
    issues_out: list[dict[str, Any]] = []

    for node in raw_issues:
        num = node.get("number")
        state = (node.get("state") or "OPEN").upper()
        if not include_closed and state != "OPEN":
            continue

        title_env = IC.frame_untrusted(node.get("title") or "", f"issue#{num}:title")
        body_env = IC.frame_untrusted(node.get("body") or "", f"issue#{num}:body")

        comments_conn = node.get("comments")
        if _has_next_page(comments_conn):
            not_checked.append(f"comments beyond first page on issue #{num}")

        comments_out: list[dict[str, Any]] = []
        stage_markers: dict[str, list[dict[str, Any]]] = {stage: [] for stage in IC.STAGES}
        signals_count = len(title_env["suspicious_directives"]) + len(body_env["suspicious_directives"])

        for c in _nodes(comments_conn):
            raw_cbody = c.get("body") or ""
            author = _login(c)
            cid = c.get("databaseId") if c.get("databaseId") is not None else c.get("id")
            leading_stage = IC.parse_leading_stage_marker(raw_cbody)
            for stage in sorted(set(IC.parse_stage_markers(raw_cbody))):
                is_trusted = (author in trusted_set) and (leading_stage == stage)
                stage_markers[stage].append({
                    "comment_id": cid,
                    "author": author,
                    "trusted": is_trusted,
                    "leading_marker": leading_stage == stage,
                    "created_at": c.get("createdAt"),
                    "url": c.get("url"),
                })
            c_env = IC.frame_untrusted(raw_cbody, f"issue#{num}:comment:{cid}")
            signals_count += len(c_env["suspicious_directives"])
            comments_out.append({
                "id": cid,
                "author": author,
                "created_at": c.get("createdAt"),
                "url": c.get("url"),
                "body": c_env,
            })

        linked_prs: list[dict[str, Any]] = []
        for pr in open_prs:
            if num in pr["closing_issues"]:
                linked_prs.append({
                    "number": pr["number"],
                    "url": pr["url"],
                    "title": pr["title"],
                    "head": pr["head"],
                    "relation": "closing_ref",
                })
            elif num in pr["mentioned_issues"]:
                linked_prs.append({
                    "number": pr["number"],
                    "url": pr["url"],
                    "title": pr["title"],
                    "head": pr["head"],
                    "relation": "body_mention",
                })

        labels = sorted(lbl["name"] for lbl in _nodes(node.get("labels")) if lbl.get("name"))
        issues_out.append({
            "number": num,
            "url": node.get("url"),
            "state": state,
            "author": _login(node),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "labels": labels,
            "title": title_env,
            "body": body_env,
            "comments": comments_out,
            "stage_markers": stage_markers,
            "linked_open_prs": linked_prs,
            "injection_signals_count": signals_count,
        })

    if not_checked:
        status = "partial_truncated"
    elif issues_out:
        status = "work_available"
    else:
        status = "empty"

    return {
        "schema_version": IC.SCHEMA_VERSION,
        "repo": repo,
        "status": status,
        "trusted_logins": sorted(trusted_set),
        "issues": issues_out,
        "open_prs": open_prs,
        "summary": {
            "total_issues": len(issues_out),
            "open_issues": sum(1 for item in issues_out if item["state"] == "OPEN"),
            "with_open_pr": sum(1 for item in issues_out if item["linked_open_prs"]),
            "with_injection_signals": sum(1 for item in issues_out if item["injection_signals_count"] > 0),
            "already_triaged": sum(
                1 for item in issues_out
                if any(m["trusted"] for m in item["stage_markers"]["triage"])
            ),
        },
        "not_checked": not_checked,
    }


def exit_code(state: dict[str, Any]) -> int:
    if state["not_checked"]:
        return 1
    return 0 if state["issues"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="owner/name (default: resolved from current gh repo)")
    parser.add_argument("--issue", type=int, help="single issue number to collect")
    parser.add_argument("--limit", type=int, default=50, help="max issues to fetch (1..100)")
    parser.add_argument("--include-closed", action="store_true", help="include closed issues when collecting")
    parser.add_argument("--trusted-login", action="append", default=[], help="extra login trusted for stage markers (repeatable)")
    parser.add_argument("--from-file", help="read saved GraphQL JSON instead of calling gh ('-' for stdin)")
    parser.add_argument("--out", help="optional path to write the JSON evidence document")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if args.issue is not None and args.issue < 1:
        print("issue_state: --issue must be a positive integer", file=sys.stderr)
        return 64
    if args.limit < 1 or args.limit > 100:
        print("issue_state: --limit must be between 1 and 100", file=sys.stderr)
        return 64
    if args.repo and not IC.REPO_PATTERN.match(args.repo):
        print("issue_state: --repo must look like owner/name", file=sys.stderr)
        return 64

    try:
        if args.from_file:
            raw_text = sys.stdin.read() if args.from_file == "-" else Path(args.from_file).read_text(encoding="utf-8")
            try:
                response = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise IC.GhError(f"invalid JSON in {args.from_file}: {exc}") from exc
            repo = args.repo or "offline/local"
        else:
            repo = args.repo or IC.resolve_repo()
            response = fetch_graphql(repo, args.issue, args.limit, include_closed=args.include_closed)
        state = build_state(
            response,
            repo,
            target_issue=args.issue,
            include_closed=args.include_closed,
            trusted_logins=tuple(args.trusted_login),
        )
    except OSError as exc:
        print(f"issue_state: cannot read {args.from_file}: {exc}", file=sys.stderr)
        return 2
    except IC.GhError as exc:
        print(f"issue_state: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(state, indent=2)
    if args.out:
        try:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"issue_state: cannot write {args.out}: {exc}", file=sys.stderr)
            return 2

    print(payload)
    return exit_code(state)


if __name__ == "__main__":
    sys.exit(main())
