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

"""Detect and resolve squash-merge stack conflicts and stale PR bases.

  restack.py --pr 12 [--repo owner/name] [--dry-run | --apply]
  restack.py --cascade --merged-pr 10 [--repo owner/name] [--dry-run | --apply]
  restack.py --pr 12 --from-file pr_context.json --no-fetch --repo-dir .

When a lower PR in a stack is squash-merged, GitHub creates a new commit on
`<base>` whose tree matches the lower PR's head tree (`headRefOid^{tree}`), but
whose commit history is unrelated. Running a plain `git merge origin/<base>`
replays changes that are already in `HEAD` and triggers avoidable conflicts.

This script inspects ancestry and git tree OIDs before acting:
  - Only when a merged PR's `headRefOid` is an ancestor of `HEAD` AND its tree
    matches `origin/<base>^{tree}` does `--apply` run `merge -s ours`.
  - When a merged PR's squash commit (`mergeCommit.oid`) is an ancestor of
    `origin/<base>` with matching tree, it syncs that squash commit `-s ours`
    first, then merges `origin/<base>` cleanly (atomic rollback on conflict).
  - Otherwise it runs a normal `git merge --no-edit` (or `git rebase`), aborts
    cleanly on conflict, and reports `conflicting_files` as JSON.

Exit codes:
  0   clean, already up to date, dry-run plan ready, or apply succeeded
  1   conflict (aborted cleanly), dirty working tree, branch mismatch, cycle,
      or unsafe PR ref
  2   git/gh missing, API/command failure, or unreadable/invalid JSON
  64  usage error (bad flags, invalid --repo/--remote, invalid strategy combo)

Surface (V3): PR metadata (`headRefName`, `baseRefName`, `mergeable`,
`headRefOid`, `isCrossRepository`), recent merged PRs against `<base>`, local
git ancestry/tree OIDs, and `git diff --numstat` before/after stats.
Not checked (V5): semantic correctness of auto-merged hunks, remote CI checks,
or fork PRs (skipped by `--cascade` when `isCrossRepository != false`).
"""

from __future__ import annotations

import argparse
import heapq
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REMOTE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
OID_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

STRATEGIES = ("merge", "rebase")
DEFAULT_REMOTE = "origin"
DEFAULT_MERGED_LIMIT = 10
DEFAULT_OPEN_LIMIT = 100

_SECRET_PATTERNS = (
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,})\b"),
     "[REDACTED_TOKEN]"),
    (re.compile(r"(https?://)([^:/@\s]+):([^@\s]+)@"),
     r"\1\2:[REDACTED]@"),
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
     r"\1[REDACTED]"),
)


class RestackError(Exception):
    """Operational failure (git/gh missing, command failed, bad JSON)."""


class RefusalError(Exception):
    """Fail-closed safety refusal (conflict, unsafe ref, dirty tree, cycle)."""


def redact_secrets(text: str) -> str:
    """Redact credentials at capture time (ENGINEERING_STANDARD S8)."""
    out = text
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def validate_ref(ref: Any, label: str = "ref") -> str:
    """Reject empty, control-char, or `-`-prefixed git refs (CWE-88)."""
    if not isinstance(ref, str) or not ref:
        raise RefusalError(f"unsafe {label}: empty ref")
    if ref.startswith("-"):
        raise RefusalError(f"unsafe {label} {ref!r}: ref cannot start with '-'")
    if any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in ref):
        raise RefusalError(f"unsafe {label} {ref!r}: whitespace or control char")
    if not SAFE_REF_RE.match(ref):
        raise RefusalError(f"unsafe {label} {ref!r}: disallowed characters")
    if ".." in ref or "//" in ref or "/." in ref or "@{" in ref:
        raise RefusalError(f"unsafe {label} {ref!r}: invalid git ref sequence")
    if ref.endswith("/") or ref.endswith(".") or ref.endswith(".lock"):
        raise RefusalError(f"unsafe {label} {ref!r}: invalid ref ending")
    return ref


def validate_oid(oid: Any) -> str | None:
    if isinstance(oid, str) and OID_PATTERN.match(oid.strip()):
        return oid.strip()
    return None


def _run_cmd(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    proc.stdout = redact_secrets(proc.stdout or "")
    proc.stderr = redact_secrets(proc.stderr or "")
    return proc


def run_git(repo_dir: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = _run_cmd(["git", *args], cwd=repo_dir)
    except FileNotFoundError as exc:
        raise RestackError("git CLI not found on PATH") from exc
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RestackError(f"git {args[0]} failed: {detail}")
    return proc


def run_gh(args: list[str], cwd: Path | None = None) -> str:
    try:
        proc = _run_cmd(["gh", *args], cwd=cwd)
    except FileNotFoundError as exc:
        raise RestackError("gh CLI not found on PATH") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RestackError(f"gh {args[0]} failed: {detail}")
    return proc.stdout


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = redact_secrets(path.read_text(encoding="utf-8"))
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RestackError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RestackError(f"{path} must contain a JSON object")
    return data


def resolve_repo(repo_dir: Path | None = None) -> str:
    out = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                 cwd=repo_dir).strip()
    if not REPO_PATTERN.match(out):
        raise RestackError(f"could not resolve the current repository (got {out!r})")
    return out


def fetch_pr_metadata(repo: str, pr_number: int) -> dict[str, Any]:
    fields = "number,url,state,headRefName,baseRefName,mergeable,mergeStateStatus,headRefOid,baseRefOid,isCrossRepository"
    out = run_gh(["pr", "view", str(pr_number), "--repo", repo, "--json", fields])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RestackError(f"gh pr view returned non-JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RestackError("gh pr view returned non-object JSON")
    return data


def fetch_merged_prs(repo: str, base_branch: str, limit: int = DEFAULT_MERGED_LIMIT) -> list[dict[str, Any]]:
    validate_ref(base_branch, "base branch")
    out = run_gh([
        "pr", "list", "--repo", repo, "--state", "merged",
        "--base", base_branch, "--limit", str(limit),
        "--json", "number,headRefName,baseRefName,headRefOid,mergeCommit",
    ])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RestackError(f"gh pr list (merged) returned non-JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RestackError("gh pr list (merged) returned non-list JSON")
    return [item for item in data if isinstance(item, dict)]


def fetch_merged_by_head(repo: str, head_branch: str) -> list[dict[str, Any]]:
    validate_ref(head_branch, "head branch")
    out = run_gh([
        "pr", "list", "--repo", repo, "--state", "merged",
        "--head", head_branch, "--limit", "5",
        "--json", "number,headRefName,baseRefName,headRefOid,mergeCommit",
    ])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RestackError(f"gh pr list (merged --head) returned non-JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RestackError("gh pr list (merged --head) returned non-list JSON")
    return [item for item in data if isinstance(item, dict)]


def fetch_pr_for_cascade(repo: str, merged_pr: int) -> dict[str, Any]:
    out = run_gh([
        "pr", "view", str(merged_pr), "--repo", repo,
        "--json", "number,state,headRefName,baseRefName,headRefOid,mergeCommit,mergedAt",
    ])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RestackError(f"gh pr view returned non-JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RestackError("gh pr view returned non-object JSON")
    return data


def fetch_open_prs(repo: str, limit: int = DEFAULT_OPEN_LIMIT) -> list[dict[str, Any]]:
    out = run_gh([
        "pr", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
        "--json", "number,url,headRefName,baseRefName,mergeable,mergeStateStatus,headRefOid,isCrossRepository",
    ])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RestackError(f"gh pr list (open) returned non-JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RestackError("gh pr list (open) returned non-list JSON")
    return [item for item in data if isinstance(item, dict)]


# --- git inspection & diff stats --------------------------------------------

def git_oid(repo_dir: Path, rev: str) -> str | None:
    proc = run_git(repo_dir, ["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], check=False)
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def git_tree_oid(repo_dir: Path, rev: str) -> str | None:
    proc = run_git(repo_dir, ["rev-parse", "--verify", "--quiet", f"{rev}^{{tree}}"], check=False)
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def git_is_ancestor(repo_dir: Path, ancestor: str, descendant: str) -> bool:
    proc = run_git(repo_dir, ["merge-base", "--is-ancestor", ancestor, descendant], check=False)
    return proc.returncode == 0


def git_current_branch(repo_dir: Path) -> str:
    return run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def git_is_dirty(repo_dir: Path) -> bool:
    return bool(run_git(repo_dir, ["status", "--porcelain"]).stdout.strip())


def git_conflict_files(repo_dir: Path) -> list[str]:
    proc = run_git(repo_dir, ["diff", "--name-only", "--diff-filter=U"], check=False)
    return sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())


def git_diff_stats(repo_dir: Path, rev_spec: str) -> dict[str, Any]:
    proc = run_git(repo_dir, ["diff", "--numstat", rev_spec])
    files: list[dict[str, Any]] = []
    ins_total = 0
    del_total = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        raw_ins, raw_del, path = parts
        ins = int(raw_ins) if raw_ins.isdigit() else 0
        dels = int(raw_del) if raw_del.isdigit() else 0
        ins_total += ins
        del_total += dels
        files.append({"path": path, "insertions": ins, "deletions": dels})
    return {
        "files_changed": len(files),
        "insertions": ins_total,
        "deletions": del_total,
        "files": files,
    }


def _squash_message(base_name: str, merged_number: Any) -> str:
    num = merged_number if isinstance(merged_number, int) else "?"
    return f"chore: sync {base_name} after #{num} squash merge"


def _merge_cmd(target: str, strategy: str, message: str | None = None,
               ours: bool = False, onto_base: str | None = None) -> list[str]:
    if strategy == "rebase":
        if onto_base is not None:
            return ["git", "-c", "commit.gpgsign=false", "rebase", "--onto", target, onto_base]
        return ["git", "-c", "commit.gpgsign=false", "rebase", target]
    if ours:
        return ["git", "-c", "commit.gpgsign=false", "merge", "-s", "ours",
                "--no-edit", "-m", message or "chore: sync squash merge", target]
    return ["git", "-c", "commit.gpgsign=false", "merge", "--no-edit", target]


# --- planning & execution ---------------------------------------------------

def plan_restack(
    repo_dir: Path,
    head_rev: str,
    target_rev: str,
    base_name: str,
    merged_prs: list[dict[str, Any]],
    strategy: str = "merge",
    parent_pre_oid: str | None = None,
) -> dict[str, Any]:
    """Compute a deterministic restack plan without modifying the repo."""
    head_oid = git_oid(repo_dir, head_rev)
    if not head_oid:
        raise RestackError(f"local head ref {head_rev!r} does not exist")
    target_oid = git_oid(repo_dir, target_rev)
    if not target_oid:
        raise RestackError(f"target ref {target_rev!r} does not exist")

    if git_is_ancestor(repo_dir, target_oid, head_oid):
        return {
            "mode": "already_up_to_date",
            "strategy": strategy,
            "head_oid": head_oid,
            "target_ref": target_rev,
            "target_oid": target_oid,
            "exact_tree_match": False,
            "chain_tree_match": False,
            "matched_merged_pr": None,
            "sync_commit": None,
            "commands_planned": [],
        }

    if strategy == "rebase" and parent_pre_oid and git_is_ancestor(repo_dir, parent_pre_oid, head_oid):
        return {
            "mode": "cascade_parent_onto",
            "strategy": strategy,
            "head_oid": head_oid,
            "target_ref": target_rev,
            "target_oid": target_oid,
            "exact_tree_match": False,
            "chain_tree_match": False,
            "matched_merged_pr": None,
            "sync_commit": None,
            "parent_pre_oid": parent_pre_oid,
            "commands_planned": [_merge_cmd(target_rev, "rebase", onto_base=parent_pre_oid)],
        }

    target_tree = git_tree_oid(repo_dir, target_oid)
    direct_match: dict[str, Any] | None = None
    chain_candidates: list[tuple[str, dict[str, Any], str]] = []

    for mpr in merged_prs:
        m_oid = validate_oid(mpr.get("headRefOid"))
        if not m_oid:
            continue
        m_tree = git_tree_oid(repo_dir, m_oid)
        if not m_tree or not git_is_ancestor(repo_dir, m_oid, head_oid):
            continue
        if m_tree == target_tree:
            direct_match = {
                "number": mpr.get("number"),
                "head_ref": mpr.get("headRefName"),
                "head_oid": m_oid,
            }
            break
        mc_oid = validate_oid((mpr.get("mergeCommit") or {}).get("oid"))
        if mc_oid:
            mc_tree = git_tree_oid(repo_dir, mc_oid)
            if (mc_tree and mc_tree == m_tree
                    and git_is_ancestor(repo_dir, mc_oid, target_oid)
                    and not git_is_ancestor(repo_dir, mc_oid, head_oid)):
                chain_candidates.append((mc_oid, mpr, m_oid))

    if direct_match is not None:
        msg = _squash_message(base_name, direct_match["number"])
        if strategy == "rebase":
            cmds = [_merge_cmd(target_rev, "rebase", onto_base=direct_match["head_oid"])]
        else:
            cmds = [_merge_cmd(target_rev, "merge", message=msg, ours=True)]
        return {
            "mode": "exact_tree_squash_ours",
            "strategy": strategy,
            "head_oid": head_oid,
            "target_ref": target_rev,
            "target_oid": target_oid,
            "exact_tree_match": True,
            "chain_tree_match": False,
            "matched_merged_pr": direct_match,
            "sync_commit": target_oid,
            "commands_planned": cmds,
        }

    if chain_candidates:
        # Pick the squash commit furthest downstream on target_rev.
        best_mc, best_mpr, best_m_oid = chain_candidates[0]
        for mc_oid, mpr, m_oid in chain_candidates[1:]:
            if mc_oid != best_mc and git_is_ancestor(repo_dir, best_mc, mc_oid):
                best_mc, best_mpr, best_m_oid = mc_oid, mpr, m_oid
        msg = _squash_message(base_name, best_mpr.get("number"))
        if strategy == "rebase":
            cmds = [_merge_cmd(target_rev, "rebase", onto_base=best_m_oid)]
        else:
            cmds = [
                _merge_cmd(best_mc, "merge", message=msg, ours=True),
                _merge_cmd(target_rev, "merge"),
            ]
        return {
            "mode": "chain_squash_ours_then_sync",
            "strategy": strategy,
            "head_oid": head_oid,
            "target_ref": target_rev,
            "target_oid": target_oid,
            "exact_tree_match": False,
            "chain_tree_match": True,
            "matched_merged_pr": {
                "number": best_mpr.get("number"),
                "head_ref": best_mpr.get("headRefName"),
                "head_oid": best_m_oid,
            },
            "sync_commit": best_mc,
            "commands_planned": cmds,
        }

    return {
        "mode": "standard_sync",
        "strategy": strategy,
        "head_oid": head_oid,
        "target_ref": target_rev,
        "target_oid": target_oid,
        "exact_tree_match": False,
        "chain_tree_match": False,
        "matched_merged_pr": None,
        "sync_commit": None,
        "commands_planned": [_merge_cmd(target_rev, strategy)],
    }


def _abort_in_progress(repo_dir: Path, strategy: str, pre_head: str) -> None:
    abort_cmd = ["rebase", "--abort"] if strategy == "rebase" else ["merge", "--abort"]
    run_git(repo_dir, abort_cmd, check=False)
    cur = git_oid(repo_dir, "HEAD")
    if cur and cur != pre_head:
        run_git(repo_dir, ["reset", "--hard", pre_head], check=False)


def _check_remote_ancestry(
    repo_dir: Path,
    head_branch: str,
    head_oid: str,
    remote: str,
    pr_head_oid: Any,
) -> str | None:
    """Return expected remote OID if safe, or raise RefusalError if local head is stale."""
    remote_ref = f"{remote}/{head_branch}"
    remote_oid = git_oid(repo_dir, remote_ref)
    if remote_oid and not git_is_ancestor(repo_dir, remote_oid, head_oid):
        raise RefusalError(
            f"remote ref {remote_ref!r} ({remote_oid}) is not an ancestor of local "
            f"{head_branch!r} ({head_oid}); remote has newer commits"
        )
    expected_pr_oid = validate_oid(pr_head_oid)
    if expected_pr_oid and (
        not git_oid(repo_dir, expected_pr_oid)
        or not git_is_ancestor(repo_dir, expected_pr_oid, head_oid)
    ):
        raise RefusalError(
            f"PR headRefOid {expected_pr_oid} is not an ancestor of local "
            f"{head_branch!r} ({head_oid}); fetch or pull before --apply"
        )
    return remote_oid or expected_pr_oid


def _execute_plan(
    repo_dir: Path,
    plan: dict[str, Any],
    head_branch: str,
    target_rev: str,
    remote: str,
    push: bool,
    pr_head_oid: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Run planned git operations in repo_dir, aborting atomically on conflict or mismatch."""
    if git_is_dirty(repo_dir):
        raise RefusalError("working tree has uncommitted changes; commit or stash before --apply")
    cur_branch = git_current_branch(repo_dir)
    if cur_branch != head_branch:
        raise RefusalError(
            f"checked out branch is {cur_branch!r}, expected PR head {head_branch!r}"
        )

    pre_head = git_oid(repo_dir, "HEAD") or ""
    pre_tree = git_tree_oid(repo_dir, "HEAD")
    expected_remote_oid = _check_remote_ancestry(
        repo_dir, head_branch, pre_head, remote, pr_head_oid
    )

    diff_vs_base_before = git_diff_stats(repo_dir, f"{target_rev}..HEAD")
    pr_net_diff_before = git_diff_stats(repo_dir, f"{target_rev}...HEAD")

    if plan["mode"] == "already_up_to_date":
        return 0, {
            **plan,
            "applied": False,
            "status": "already_up_to_date",
            "pushed": False,
            "conflicting_files": [],
            "diff_vs_base_before": diff_vs_base_before,
            "pr_net_diff_before": pr_net_diff_before,
            "diff_vs_base_after": diff_vs_base_before,
            "pr_net_diff_after": pr_net_diff_before,
            "tree_unchanged": True,
        }

    strategy = plan["strategy"]
    for cmd in plan["commands_planned"]:
        proc = run_git(repo_dir, cmd[1:], check=False)
        if proc.returncode != 0:
            conflicts = git_conflict_files(repo_dir)
            _abort_in_progress(repo_dir, strategy, pre_head)
            detail = proc.stderr.strip() or proc.stdout.strip()
            return 1, {
                **plan,
                "applied": False,
                "status": "conflict" if conflicts else "git_failed",
                "pushed": False,
                "conflicting_files": conflicts,
                "error": detail,
                "diff_vs_base_before": diff_vs_base_before,
                "pr_net_diff_before": pr_net_diff_before,
            }

    post_head = git_oid(repo_dir, "HEAD")
    post_tree = git_tree_oid(repo_dir, "HEAD")
    target_oid = plan.get("target_oid") or git_oid(repo_dir, target_rev)
    if not post_head or not target_oid or not git_is_ancestor(repo_dir, target_oid, post_head):
        _abort_in_progress(repo_dir, strategy, pre_head)
        return 1, {
            **plan,
            "applied": False,
            "status": "ancestry_mismatch",
            "pushed": False,
            "conflicting_files": [],
            "error": (
                f"post-restack HEAD does not descend from target {target_rev!r} "
                f"({target_oid}); rolled back"
            ),
            "diff_vs_base_before": diff_vs_base_before,
            "pr_net_diff_before": pr_net_diff_before,
        }

    tree_unchanged = bool(pre_tree and post_tree and pre_tree == post_tree)
    if plan["mode"] == "exact_tree_squash_ours" and not tree_unchanged:
        _abort_in_progress(repo_dir, strategy, pre_head)
        return 1, {
            **plan,
            "applied": False,
            "status": "tree_mismatch",
            "pushed": False,
            "conflicting_files": [],
            "tree_unchanged": False,
            "error": (
                "exact_tree_squash_ours altered the branch tree (for example, rebase "
                "flattened a merge commit); rolled back"
            ),
            "diff_vs_base_before": diff_vs_base_before,
            "pr_net_diff_before": pr_net_diff_before,
        }

    diff_vs_base_after = git_diff_stats(repo_dir, f"{target_rev}..HEAD")
    pr_net_diff_after = git_diff_stats(repo_dir, f"{target_rev}...HEAD")

    pushed = False
    if push:
        push_args = ["push"]
        if strategy == "rebase":
            lease_oid = expected_remote_oid or ""
            push_args.append(f"--force-with-lease=refs/heads/{head_branch}:{lease_oid}")
        push_args.extend([remote, head_branch])
        push_proc = run_git(repo_dir, push_args, check=False)
        if push_proc.returncode != 0:
            _abort_in_progress(repo_dir, strategy, pre_head)
            detail = push_proc.stderr.strip() or push_proc.stdout.strip()
            return 1, {
                **plan,
                "applied": False,
                "status": "push_rejected",
                "pushed": False,
                "conflicting_files": [],
                "error": detail,
                "diff_vs_base_before": diff_vs_base_before,
                "pr_net_diff_before": pr_net_diff_before,
            }
        pushed = True

    return 0, {
        **plan,
        "applied": True,
        "status": "restacked",
        "post_head_oid": post_head,
        "pushed": pushed,
        "conflicting_files": [],
        "diff_vs_base_before": diff_vs_base_before,
        "pr_net_diff_before": pr_net_diff_before,
        "diff_vs_base_after": diff_vs_base_after,
        "pr_net_diff_after": pr_net_diff_after,
        "tree_unchanged": tree_unchanged,
    }


def run_single_pr(
    repo_dir: Path,
    pr_meta: dict[str, Any],
    merged_prs: list[dict[str, Any]],
    remote: str,
    strategy: str,
    apply: bool,
    push: bool,
    repo_slug: str | None = None,
) -> tuple[int, dict[str, Any]]:
    head_branch = validate_ref(pr_meta.get("headRefName"), "headRefName")
    base_branch = validate_ref(pr_meta.get("baseRefName"), "baseRefName")
    target_rev = f"{remote}/{base_branch}"

    retarget_base: str | None = None
    if not git_oid(repo_dir, target_rev):
        # Check whether the PR's base branch itself already merged into another base.
        for mpr in merged_prs:
            if mpr.get("headRefName") == base_branch and mpr.get("baseRefName"):
                retarget_base = validate_ref(mpr["baseRefName"], "retarget base")
                break
        if retarget_base and git_oid(repo_dir, f"{remote}/{retarget_base}"):
            target_rev = f"{remote}/{retarget_base}"
            base_branch = retarget_base

    cur_branch = git_current_branch(repo_dir)
    if cur_branch == head_branch:
        inspect_rev = "HEAD"
    elif git_oid(repo_dir, head_branch):
        inspect_rev = head_branch
    elif git_oid(repo_dir, f"{remote}/{head_branch}"):
        inspect_rev = f"{remote}/{head_branch}"
    else:
        raise RestackError(f"cannot find local ref for PR head {head_branch!r}")

    plan = plan_restack(repo_dir, inspect_rev, target_rev, base_branch, merged_prs, strategy)
    if not apply:
        diff_vs_base_before = git_diff_stats(repo_dir, f"{target_rev}..{inspect_rev}")
        pr_net_diff_before = git_diff_stats(repo_dir, f"{target_rev}...{inspect_rev}")
        return 0, {
            **plan,
            "pr": {
                "number": pr_meta.get("number"),
                "head": head_branch,
                "base": pr_meta.get("baseRefName"),
                "mergeable": pr_meta.get("mergeable"),
                "merge_state": pr_meta.get("mergeStateStatus"),
                "retarget_base_needed": retarget_base,
            },
            "dry_run": True,
            "applied": False,
            "status": "already_up_to_date" if plan["mode"] == "already_up_to_date" else "planned",
            "diff_vs_base_before": diff_vs_base_before,
            "pr_net_diff_before": pr_net_diff_before,
        }

    code, result = _execute_plan(
        repo_dir, plan, head_branch, target_rev, remote, push,
        pr_head_oid=pr_meta.get("headRefOid"),
    )
    if code == 0 and retarget_base and repo_slug:
        run_gh(["pr", "edit", str(pr_meta["number"]), "--repo", repo_slug, "--base", retarget_base])
    result["pr"] = {
        "number": pr_meta.get("number"),
        "head": head_branch,
        "base": base_branch,
        "mergeable": pr_meta.get("mergeable"),
        "merge_state": pr_meta.get("mergeStateStatus"),
        "retarget_base_needed": retarget_base,
    }
    result["dry_run"] = False
    return code, result


# --- cascade topological planning & execution -------------------------------

def build_cascade_plan(
    merged_pr: dict[str, Any],
    open_prs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select affected same-repo PRs and sort them topologically (upstream first)."""
    merged_head = validate_ref(merged_pr.get("headRefName"), "merged headRefName")
    merged_base = validate_ref(merged_pr.get("baseRefName"), "merged baseRefName")

    if merged_pr.get("state") not in (None, "MERGED") and not (merged_pr.get("mergeCommit") or {}).get("oid"):
        raise RefusalError(f"PR #{merged_pr.get('number')} is not merged (state={merged_pr.get('state')!r})")

    skipped_forks: list[dict[str, Any]] = []
    same_repo: list[dict[str, Any]] = []
    for pr in open_prs:
        if pr.get("isCrossRepository") is not False:
            skipped_forks.append({
                "number": pr.get("number"),
                "head": pr.get("headRefName"),
                "reason": "cross-repository/fork PR skipped",
            })
            continue
        validate_ref(pr.get("headRefName"), f"PR #{pr.get('number')} headRefName")
        validate_ref(pr.get("baseRefName"), f"PR #{pr.get('number')} baseRefName")
        same_repo.append(pr)

    affected_by_num: dict[int, dict[str, Any]] = {}
    affected_heads: set[str] = {merged_head}

    for pr in same_repo:
        num = pr.get("number")
        if not isinstance(num, int):
            continue
        base = pr["baseRefName"]
        if (base == merged_head
                or pr.get("mergeable") == "CONFLICTING"
                or pr.get("mergeStateStatus") == "DIRTY"
                or (base == merged_base and pr.get("mergeStateStatus") == "BEHIND")):
            affected_by_num[num] = pr
            affected_heads.add(pr["headRefName"])

    changed = True
    while changed:
        changed = False
        for pr in same_repo:
            num = pr.get("number")
            if not isinstance(num, int) or num in affected_by_num:
                continue
            if pr["baseRefName"] in affected_heads:
                affected_by_num[num] = pr
                affected_heads.add(pr["headRefName"])
                changed = True

    affected = list(affected_by_num.values())
    by_head: dict[str, list[int]] = {}
    for pr in affected:
        by_head.setdefault(pr["headRefName"], []).append(pr["number"])

    indegree: dict[int, int] = {pr["number"]: 0 for pr in affected}
    children: dict[int, list[int]] = {pr["number"]: [] for pr in affected}
    for pr in affected:
        for parent_num in by_head.get(pr["baseRefName"], []):
            if parent_num == pr["number"]:
                raise RefusalError(f"PR #{pr['number']} has self-referential baseRefName {pr['baseRefName']!r}")
            indegree[pr["number"]] += 1
            children[parent_num].append(pr["number"])

    heap = [num for num, deg in indegree.items() if deg == 0]
    heapq.heapify(heap)
    ordered_nums: list[int] = []
    while heap:
        num = heapq.heappop(heap)
        ordered_nums.append(num)
        for child in sorted(children[num]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(heap, child)

    if len(ordered_nums) != len(affected):
        cycle_nums = sorted(num for num, deg in indegree.items() if deg > 0)
        raise RefusalError(f"dependency cycle detected among open PRs: {cycle_nums}")

    plan: list[dict[str, Any]] = []
    for num in ordered_nums:
        pr = affected_by_num[num]
        cur_base = pr["baseRefName"]
        needs_retarget = cur_base == merged_head
        target_base = merged_base if needs_retarget else cur_base
        plan.append({
            "number": num,
            "url": pr.get("url"),
            "head": pr["headRefName"],
            "current_base": cur_base,
            "target_base": target_base,
            "needs_retarget": needs_retarget,
            "mergeable": pr.get("mergeable"),
            "merge_state": pr.get("mergeStateStatus"),
            "head_oid": pr.get("headRefOid"),
        })
    return plan, skipped_forks


def _sync_cascade_local_branch(
    repo_dir: Path,
    head_branch: str,
    remote: str,
    pr_head_oid: Any,
) -> str | None:
    """Checkout head_branch, creating or fast-forwarding from remote when behind."""
    local_oid = git_oid(repo_dir, head_branch)
    remote_ref = f"{remote}/{head_branch}"
    remote_oid = git_oid(repo_dir, remote_ref)
    expected_pr_oid = validate_oid(pr_head_oid)

    if local_oid is None:
        if remote_oid:
            run_git(repo_dir, ["checkout", "-b", head_branch, remote_ref])
            local_oid = remote_oid
        elif expected_pr_oid and git_oid(repo_dir, expected_pr_oid):
            run_git(repo_dir, ["checkout", "-b", head_branch, expected_pr_oid])
            local_oid = expected_pr_oid
        else:
            return f"local and remote refs missing for {head_branch!r}"
    else:
        run_git(repo_dir, ["checkout", head_branch])
        if remote_oid and remote_oid != local_oid:
            if git_is_ancestor(repo_dir, local_oid, remote_oid):
                run_git(repo_dir, ["merge", "--ff-only", remote_ref])
                local_oid = remote_oid
            elif not git_is_ancestor(repo_dir, remote_oid, local_oid):
                return (
                    f"local {head_branch!r} ({local_oid}) diverged from {remote_ref!r} "
                    f"({remote_oid}); resolve divergence before cascade"
                )

    if expected_pr_oid and (
        not git_oid(repo_dir, expected_pr_oid)
        or not git_is_ancestor(repo_dir, expected_pr_oid, local_oid)
    ):
        return (
            f"PR headRefOid {expected_pr_oid} is not an ancestor of {head_branch!r} "
            f"({local_oid}); fetch or pull before cascade"
        )
    return None


def run_cascade(
    repo_dir: Path,
    merged_pr: dict[str, Any],
    open_prs: list[dict[str, Any]],
    merged_prs: list[dict[str, Any]],
    remote: str,
    strategy: str,
    apply: bool,
    push: bool,
    repo_slug: str | None = None,
) -> tuple[int, dict[str, Any]]:
    plan, skipped_forks = build_cascade_plan(merged_pr, open_prs)
    merged_summary = {
        "number": merged_pr.get("number"),
        "head": merged_pr.get("headRefName"),
        "base": merged_pr.get("baseRefName"),
        "head_oid": merged_pr.get("headRefOid"),
    }
    merged_pool = [merged_pr, *[m for m in merged_prs if m.get("number") != merged_pr.get("number")]]

    if not apply:
        for item in plan:
            target_rev = f"{remote}/{item['target_base']}"
            head_rev = item["head"] if git_oid(repo_dir, item["head"]) else f"{remote}/{item['head']}"
            if git_oid(repo_dir, head_rev) and git_oid(repo_dir, target_rev):
                item["restack"] = plan_restack(
                    repo_dir, head_rev, target_rev, item["target_base"], merged_pool, strategy
                )
            else:
                item["restack"] = {"mode": "pending_upstream_or_fetch", "strategy": strategy}
        return 0, {
            "mode": "cascade",
            "merged_pr": merged_summary,
            "dry_run": True,
            "applied": False,
            "plan": plan,
            "skipped_forks": skipped_forks,
        }

    if git_is_dirty(repo_dir):
        raise RefusalError("working tree has uncommitted changes; commit or stash before --apply")

    orig_branch = git_current_branch(repo_dir)
    if orig_branch == "HEAD":
        orig_branch = git_oid(repo_dir, "HEAD") or "HEAD"

    restacked_heads: set[str] = set()
    pre_oid_by_head: dict[str, str] = {}
    blocked_heads: set[str] = set()
    results: list[dict[str, Any]] = []
    overall_exit = 0

    try:
        for item in plan:
            if item["target_base"] in blocked_heads:
                blocked_heads.add(item["head"])
                results.append({**item, "status": "blocked_by_upstream_conflict", "applied": False})
                overall_exit = 1
                continue

            sync_err = _sync_cascade_local_branch(
                repo_dir, item["head"], remote, item.get("head_oid")
            )
            if sync_err is not None:
                blocked_heads.add(item["head"])
                results.append({**item, "status": "stale_local_branch", "applied": False, "error": sync_err})
                overall_exit = 1
                continue

            pre_head_oid = git_oid(repo_dir, "HEAD") or ""
            target_rev = (item["target_base"] if item["target_base"] in restacked_heads
                          else f"{remote}/{item['target_base']}")
            parent_pre_oid = (
                pre_oid_by_head.get(item["target_base"])
                if item["target_base"] in restacked_heads else None
            )
            step_plan = plan_restack(
                repo_dir, "HEAD", target_rev, item["target_base"], merged_pool,
                strategy, parent_pre_oid=parent_pre_oid,
            )
            code, step_res = _execute_plan(
                repo_dir, step_plan, item["head"], target_rev, remote, push,
                pr_head_oid=item.get("head_oid"),
            )
            if code == 0 and item["needs_retarget"] and repo_slug:
                run_gh(["pr", "edit", str(item["number"]), "--repo", repo_slug,
                        "--base", item["target_base"]])
            results.append({**item, **step_res})
            if code != 0:
                blocked_heads.add(item["head"])
                overall_exit = 1
            else:
                restacked_heads.add(item["head"])
                if pre_head_oid:
                    pre_oid_by_head[item["head"]] = pre_head_oid
    finally:
        run_git(repo_dir, ["checkout", orig_branch], check=False)

    return overall_exit, {
        "mode": "cascade",
        "merged_pr": merged_summary,
        "dry_run": False,
        "applied": overall_exit == 0,
        "results": results,
        "skipped_forks": skipped_forks,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace | int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--pr", type=int, help="pull request number to inspect/restack")
    mode_group.add_argument("--cascade", action="store_true",
                            help="discover and restack open non-fork PRs after a squash merge")
    parser.add_argument("--merged-pr", type=int,
                        help="merged PR number (required with --cascade)")
    parser.add_argument("--repo", help="owner/name (default: the current gh repo)")
    parser.add_argument("--repo-dir", default=".", help="local git repository directory (default: .)")
    parser.add_argument("--remote", default=DEFAULT_REMOTE,
                        help=f"git remote name (default: {DEFAULT_REMOTE!r})")
    parser.add_argument("--from-file",
                        help="read saved PR/stack JSON instead of calling gh (for offline runs/tests)")
    parser.add_argument("--strategy", choices=STRATEGIES, default="merge",
                        help="restack strategy when exact-tree squash is not used (default: merge)")
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip `git fetch <remote> --prune` (for offline tests)")
    parser.add_argument("--push", action="store_true",
                        help="push updated branch after --apply")
    parser.add_argument("--force-with-lease", action="store_true",
                        help="allow `git push --force-with-lease` when --push and --strategy rebase")
    act = parser.add_mutually_exclusive_group()
    act.add_argument("--dry-run", action="store_true",
                     help="inspect and print plan without modifying git state (default)")
    act.add_argument("--apply", action="store_true",
                     help="execute the planned git merge/rebase locally")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if args.pr is not None and args.pr < 1:
        print("restack: --pr must be a positive integer", file=sys.stderr)
        return 64
    if args.cascade and (args.merged_pr is None or args.merged_pr < 1):
        print("restack: --cascade requires positive --merged-pr N", file=sys.stderr)
        return 64
    if not args.cascade and args.merged_pr is not None:
        print("restack: --merged-pr is only valid with --cascade", file=sys.stderr)
        return 64
    if args.repo and not REPO_PATTERN.match(args.repo):
        print("restack: --repo must look like owner/name", file=sys.stderr)
        return 64
    if not REMOTE_PATTERN.match(args.remote):
        print(f"restack: invalid --remote {args.remote!r}", file=sys.stderr)
        return 64
    if args.force_with_lease and args.strategy != "rebase":
        print("restack: --force-with-lease is only valid with --strategy rebase", file=sys.stderr)
        return 64
    if args.push and args.strategy == "rebase" and not args.force_with_lease:
        print("restack: --push with --strategy rebase requires explicit --force-with-lease",
              file=sys.stderr)
        return 64
    if args.push and not args.apply:
        print("restack: --push requires --apply", file=sys.stderr)
        return 64
    return args


def main(argv: list[str] | None = None) -> int:
    parsed = _parse_args(argv)
    if isinstance(parsed, int):
        return parsed
    args = parsed

    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.is_dir():
        print(f"restack: --repo-dir {args.repo_dir!r} is not a directory", file=sys.stderr)
        return 2

    try:
        if not args.no_fetch:
            run_git(repo_dir, ["fetch", args.remote, "--prune"])

        if args.from_file:
            fixture_data = load_json_file(Path(args.from_file))
            repo_slug = args.repo
        else:
            repo_slug = args.repo or resolve_repo(repo_dir)
            fixture_data = None

        if args.cascade:
            if fixture_data is not None:
                merged_pr = fixture_data.get("merged_pr")
                open_prs = fixture_data.get("open_prs")
                merged_prs = fixture_data.get("merged_prs") or []
                if not isinstance(merged_pr, dict) or not isinstance(open_prs, list):
                    raise RestackError("--from-file for --cascade must contain 'merged_pr' and 'open_prs'")
            else:
                merged_pr = fetch_pr_for_cascade(repo_slug, args.merged_pr)
                open_prs = fetch_open_prs(repo_slug)
                m_base = validate_ref(merged_pr.get("baseRefName"), "merged baseRefName")
                merged_prs = fetch_merged_prs(repo_slug, m_base)
            code, output = run_cascade(
                repo_dir, merged_pr, open_prs, merged_prs, args.remote,
                args.strategy, args.apply, args.push, repo_slug=repo_slug if fixture_data is None else None,
            )
        else:
            if fixture_data is not None:
                pr_meta = fixture_data.get("pr")
                merged_prs = fixture_data.get("merged_prs") or []
                if not isinstance(pr_meta, dict) or not isinstance(merged_prs, list):
                    raise RestackError("--from-file for --pr must contain 'pr' and 'merged_prs'")
            else:
                pr_meta = fetch_pr_metadata(repo_slug, args.pr)
                base_branch = validate_ref(pr_meta.get("baseRefName"), "baseRefName")
                merged_prs = fetch_merged_prs(repo_slug, base_branch)
                if not git_oid(repo_dir, f"{args.remote}/{base_branch}"):
                    by_head = fetch_merged_by_head(repo_slug, base_branch)
                    for mpr in by_head:
                        if mpr.get("headRefName") == base_branch and mpr.get("baseRefName"):
                            new_base = validate_ref(mpr["baseRefName"], "retarget base")
                            merged_prs = by_head + fetch_merged_prs(repo_slug, new_base)
                            break
            code, output = run_single_pr(
                repo_dir, pr_meta, merged_prs, args.remote,
                args.strategy, args.apply, args.push, repo_slug=repo_slug if fixture_data is None else None,
            )
    except RestackError as exc:
        print(f"restack: {exc}", file=sys.stderr)
        return 2
    except RefusalError as exc:
        print(f"restack: refused: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output, indent=2))
    if code != 0:
        print(f"restack: failed with status={output.get('status', 'error')!r}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
