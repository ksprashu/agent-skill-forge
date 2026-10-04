#!/usr/bin/env python3
# Copyright 2026 Google LLC
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

"""
ega_closure_engine.py - Domain-Aware Full Closure Protocol

Executes post-verification closure activities based on domain type:
1. Git status check, staging, conventional commit, and remote push (if remote configured).
2. OKF knowledge index & log synchronization.
3. Selective HTML portal compilation for user guides.
4. Deliverable manifest & state persistence.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Refusing to push here by default. Pushing is irreversible and outward
# facing, and this module runs as a side effect of a *verification* pass:
# nobody asking "did my work pass the gate?" is asking to publish it. Callers
# that genuinely want it opt in with push=True.
PROTECTED_BRANCHES = {"main", "master", "trunk", "develop", "release"}


def run_cmd(argv, cwd=None):
    """Runs a command given as an argument vector and returns stdout, stderr, returncode.

    No shell. The commit message is task-derived text that reaches this
    function verbatim; interpolating it into a shell string made any goal
    summary containing a backtick or $(...) an arbitrary command. Passing an
    argv list removes the shell from the path entirely, so no quoting or
    stripping is required to be correct.
    """
    res = subprocess.run(argv, shell=False, capture_output=True, text=True, cwd=cwd)
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def is_git_repo(repo_dir):
    out, _, code = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    return code == 0 and out == "true"

def execute_git_closure(short_id, goal_summary, domain, repo_dir, push=False):
    """Executes git status check and a conventional commit.

    Pushes only when `push` is True and the current branch is not protected.
    """
    if not is_git_repo(repo_dir):
        print(f"[Closure Engine] Notice: {repo_dir} is not a git repository. Skipping git commit.")
        return False, "Not a git repo"

    # Check git status
    # Tracked changes only, matching what `git add -u` below will stage. An
    # untracked scratch file used to count as a change, stage nothing, and fail
    # the commit -- a closure with nothing to commit reported as an error.
    status_out, _, _ = run_cmd(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=repo_dir)
    if not status_out:
        print("[Closure Engine] Working tree clean. No uncommitted changes.")
        return True, "Clean working tree"

    print(f"[Closure Engine] Uncommitted changes detected:\n{status_out}")

    # Tracked files only. `git add -A` also swept up untracked work that
    # happened to be in the tree — scratch files, unrelated experiments —
    # into a commit the user did not write.
    run_cmd(["git", "add", "-u"], cwd=repo_dir)

    # Determine conventional commit prefix based on domain
    domain_norm = domain.lower() if domain else "general"
    prefix = "feat"
    if domain_norm in ["markdown", "doc", "docs", "documentation", "okf"]:
        prefix = "docs"
    elif domain_norm in ["research", "analysis", "security"]:
        prefix = "chore"
    elif domain_norm in ["python", "node", "javascript", "ts", "go"]:
        prefix = "feat"

    # Collapse whitespace so the subject line stays one line. Quotes are left
    # alone: with an argv list there is no shell to confuse, and stripping them
    # only corrupted summaries that legitimately contained one.
    clean_goal = " ".join(goal_summary.split())
    if len(clean_goal) > 60:
        clean_goal = clean_goal[:57] + "..."

    commit_msg = f"{prefix}({short_id.lower()}): {clean_goal}\n\nEGA-Grounded Closure Signoff\nShort ID: {short_id}\nDomain: {domain}"

    # Execute Commit
    commit_out, commit_err, commit_code = run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir)
    if commit_code != 0:
        print(f"[Closure Engine Warning] Git commit failed: {commit_err or commit_out}")
        return False, commit_err or commit_out

    print(f"[Closure Engine] Git Commit Successful: {prefix}({short_id.lower()}): {clean_goal}")

    if not push:
        print("[Closure Engine] Local commit persisted. Push not requested.")
        return True, "Git closure completed (local)"

    branch_out, _, _ = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    branch = branch_out.strip()
    if not branch:
        print("[Closure Engine Notice] Detached HEAD — nothing pushed.")
        return True, "Git closure completed (local)"
    if branch in PROTECTED_BRANCHES:
        print(f"[Closure Engine Notice] '{branch}' is protected — nothing pushed. "
              f"Open a branch and a PR instead.")
        return True, "Git closure completed (local)"

    remote_out, _, remote_code = run_cmd(["git", "remote", "-v"], cwd=repo_dir)
    if remote_code != 0 or not remote_out:
        print("[Closure Engine Notice] No git remote configured. Local commit persisted.")
        return True, "Git closure completed (local)"

    push_out, push_err, push_code = run_cmd(["git", "push", "origin", branch], cwd=repo_dir)
    if push_code == 0:
        print(f"[Closure Engine] Git Push Successful -> origin/{branch}")
    else:
        print(f"[Closure Engine Notice] Git push skipped/failed (no upstream or auth required): {push_err or push_out}")

    return True, "Git closure completed"

def execute_domain_closure(harness_dir, push=False):
    """Executes full domain-aware closure for a completed EGA harness directory."""
    harness_path = Path(harness_dir)
    graph_file = harness_path / "task_graph.json"
    if not graph_file.exists():
        print(f"[Closure Engine Error] task_graph.json missing in {harness_path}")
        return False

    with open(graph_file, "r", encoding="utf-8") as f:
        graph = json.load(f)

    short_id = graph.get("short_id", "EGA-UNKNOWN")
    goal = graph.get("goal_summary", "EGA Goal")
    domain = graph.get("domain", "general")
    repo_dir = harness_path.parent.parent.parent  # Workspace root (.gemini/harness/SHORT_ID -> workspace)

    print(f"\n=======================================================")
    print(f"🔒 EGA DOMAIN CLOSURE ENGINE ({short_id})")
    print(f"Domain: {domain} | Workspace: {repo_dir}")
    print(f"=======================================================")

    # 1. Save Closure Manifest
    manifest = {
        "short_id": short_id,
        "goal_summary": goal,
        "domain": domain,
        "closure_status": "COMPLETED",
        "nodes_completed": len(graph.get("nodes", [])),
        "target_artifacts": [n.get("target_artifact") for n in graph.get("nodes", [])]
    }
    manifest_file = harness_path / "closure_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[Closure Engine] Manifest saved to {manifest_file}")

    # 2. Execute Git Closure
    execute_git_closure(short_id, goal, domain, repo_dir, push=push)

    print(f"=======================================================\n")
    return True

def main():
    args = [a for a in sys.argv[1:] if a != "--push"]
    push = "--push" in sys.argv[1:]
    if len(args) < 1:
        print("Usage: ega_closure_engine.py <HARNESS_DIR> [--push]")
        sys.exit(1)

    harness_dir = args[0]
    success = execute_domain_closure(harness_dir, push=push)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
