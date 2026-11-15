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

"""Real-git and contract tests for restack.py (T1-T6, S4, S8, CWE-88)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures"
SCRIPT = SKILL / "scripts" / "restack.py"


def _load_restack():
    spec = importlib.util.spec_from_file_location("pr_review_loop_restack", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RSK = _load_restack()


def _git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "author@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Committer"
    env["GIT_COMMITTER_EMAIL"] = "committer@example.com"
    if extra:
        env.update(extra)
    return env


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        shell=False,
        env=env or _git_env(),
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr or proc.stdout}"
    return proc.stdout.strip()


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        env=env or _git_env(),
    )


def _init_bare_and_clone(root: Path) -> tuple[Path, Path]:
    bare = root / "origin.git"
    _git(root, "init", "--bare", "-b", "main", str(bare))
    work = root / "work"
    _git(root, "clone", str(bare), str(work))
    _git(work, "checkout", "-b", "main")
    _commit_file(work, "shared.py", "line1\nline2\nline3\n", "chore: init")
    _git(work, "push", "-u", "origin", "main")
    return bare, work


def _squash_branch_to_main(work: Path, branch_head_oid: str, msg: str) -> str:
    """Create a GitHub-style squash commit on origin/main with branch_head_oid's tree."""
    _git(work, "checkout", "main")
    _git(work, "merge", "--squash", branch_head_oid)
    _git(work, "-c", "commit.gpgsign=false", "commit", "-m", msg)
    squash_oid = _git(work, "rev-parse", "HEAD")
    _git(work, "push", "origin", "main")
    return squash_oid


class TestSquashMergeAndDivergence(unittest.TestCase):
    """Real temp git repos for exact-tree -s ours, chain sync, and conflict abort."""

    def test_exact_tree_squash_merge_syncs_with_ours_and_preserves_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            # PR #10 (feat/step-1) edits shared.py.
            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")

            # PR #11 (feat/step-2) stacks on feat/step-1 and modifies the SAME line + adds file.
            _git(work, "checkout", "-b", "feat/step-2")
            _commit_file(work, "shared.py", "line1-step1-step2\nline2\nline3\n", "feat: step 2")
            h2 = _commit_file(work, "step2.py", "x = 2\n", "feat: step 2 module")
            _git(work, "push", "-u", "origin", "feat/step-2")

            # Squash-merge #10 onto origin/main -> S1^{tree} == H1^{tree}.
            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")

            # Return to feat/step-2; naive merge would conflict on shared.py line 1!
            _git(work, "checkout", "feat/step-2")
            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 11,
                    "headRefName": "feat/step-2",
                    "baseRefName": "main",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "headRefOid": h2,
                    "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10,
                    "headRefName": "feat/step-1",
                    "baseRefName": "main",
                    "headRefOid": h1,
                    "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")

            dry = _run_script("--pr", "11", "--from-file", str(ctx),
                              "--repo-dir", str(work), "--no-fetch", "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            dry_doc = json.loads(dry.stdout)
            self.assertEqual(dry_doc["mode"], "exact_tree_squash_ours")
            self.assertTrue(dry_doc["exact_tree_match"])
            self.assertFalse(dry_doc["applied"])
            self.assertEqual(
                dry_doc["commands_planned"],
                [["git", "-c", "commit.gpgsign=false", "merge", "-s", "ours",
                  "--no-edit", "-m", "chore: sync main after #10 squash merge", "origin/main"]],
            )
            self.assertEqual(_git(work, "rev-parse", "HEAD"), h2)

            applied = _run_script("--pr", "11", "--from-file", str(ctx),
                                  "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            app_doc = json.loads(applied.stdout)
            self.assertTrue(app_doc["applied"])
            self.assertTrue(app_doc["tree_unchanged"])
            expected_diff = {
                "files_changed": 2,
                "insertions": 2,
                "deletions": 1,
                "files": [
                    {"path": "shared.py", "insertions": 1, "deletions": 1},
                    {"path": "step2.py", "insertions": 1, "deletions": 0},
                ],
            }
            self.assertEqual(app_doc["diff_vs_base_before"], expected_diff)
            self.assertEqual(app_doc["pr_net_diff_after"], expected_diff)
            self.assertEqual(_git(work, "log", "-1", "--format=%s"),
                             "chore: sync main after #10 squash merge")
            self.assertEqual((work / "shared.py").read_text(encoding="utf-8"),
                             "line1-step1-step2\nline2\nline3\n")
            self.assertEqual((work / "step2.py").read_text(encoding="utf-8"), "x = 2\n")
            # Now origin/main is an ancestor of HEAD; re-running reports already_up_to_date.
            again = _run_script("--pr", "11", "--from-file", str(ctx),
                                "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(again.returncode, 0)
            self.assertEqual(json.loads(again.stdout)["mode"], "already_up_to_date")

    def test_diverged_main_never_guesses_ours_and_aborts_cleanly_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")

            _git(work, "checkout", "-b", "feat/step-2")
            h2 = _commit_file(work, "shared.py", "line1-step2-conflict\nline2\nline3\n", "feat: step 2")

            # Squash #10 AND add another conflicting commit on main -> trees DO NOT match!
            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _commit_file(work, "shared.py", "line1-hotfix-on-main\nline2\nline3\n", "fix: hotfix")
            _git(work, "push", "origin", "main")

            _git(work, "checkout", "feat/step-2")
            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 11,
                    "headRefName": "feat/step-2",
                    "baseRefName": "main",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "headRefOid": h2,
                    "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10,
                    "headRefName": "feat/step-1",
                    "baseRefName": "main",
                    "headRefOid": h1,
                    "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")

            proc = _run_script("--pr", "11", "--from-file", str(ctx),
                               "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(proc.returncode, 1)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["status"], "conflict")
            self.assertFalse(doc["applied"])
            self.assertFalse(doc["exact_tree_match"])
            self.assertEqual(doc["conflicting_files"], ["shared.py"])
            # Clean abort + atomic rollback back to h2.
            self.assertEqual(_git(work, "rev-parse", "HEAD"), h2)
            self.assertEqual(_git(work, "status", "--porcelain"), "")
            self.assertFalse((work / ".git" / "MERGE_HEAD").exists())

    def test_chain_squash_then_unrelated_commit_merges_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")

            _git(work, "checkout", "-b", "feat/step-2")
            h2 = _commit_file(work, "shared.py", "line1-step1-step2\nline2\nline3\n", "feat: step 2")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            # Unrelated commit on main after S1.
            _commit_file(work, "other.txt", "from main\n", "chore: unrelated")
            _git(work, "push", "origin", "main")

            _git(work, "checkout", "feat/step-2")
            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 11,
                    "headRefName": "feat/step-2",
                    "baseRefName": "main",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "headRefOid": h2,
                    "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10,
                    "headRefName": "feat/step-1",
                    "baseRefName": "main",
                    "headRefOid": h1,
                    "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")

            proc = _run_script("--pr", "11", "--from-file", str(ctx),
                               "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["mode"], "chain_squash_ours_then_sync")
            self.assertTrue(doc["chain_tree_match"])
            self.assertEqual((work / "other.txt").read_text(encoding="utf-8"), "from main\n")
            self.assertEqual((work / "shared.py").read_text(encoding="utf-8"),
                             "line1-step1-step2\nline2\nline3\n")

    def test_standard_non_conflicting_merge_when_no_squash_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/standalone")
            h = _commit_file(work, "feature.txt", "feat\n", "feat: standalone")

            _git(work, "checkout", "main")
            _commit_file(work, "main_only.txt", "main\n", "chore: main update")
            _git(work, "push", "origin", "main")

            _git(work, "checkout", "feat/standalone")
            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 30,
                    "headRefName": "feat/standalone",
                    "baseRefName": "main",
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "BEHIND",
                    "headRefOid": h,
                    "isCrossRepository": False,
                },
                "merged_prs": [],
            }), encoding="utf-8")

            proc = _run_script("--pr", "30", "--from-file", str(ctx),
                               "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["mode"], "standard_sync")
            self.assertEqual((work / "main_only.txt").read_text(encoding="utf-8"), "main\n")
            self.assertEqual((work / "feature.txt").read_text(encoding="utf-8"), "feat\n")

    def test_rebase_strategy_with_force_with_lease_push_and_conflict_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")
            _git(work, "checkout", "-b", "feat/step-2")
            h2 = _commit_file(work, "step2.py", "x = 2\n", "feat: step 2")
            _git(work, "push", "-u", "origin", "feat/step-2")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _git(work, "checkout", "feat/step-2")

            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 11,
                    "headRefName": "feat/step-2",
                    "baseRefName": "main",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "headRefOid": h2,
                    "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10,
                    "headRefName": "feat/step-1",
                    "baseRefName": "main",
                    "headRefOid": h1,
                    "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")

            # Rebase + push WITHOUT --force-with-lease must be refused (64).
            refused = _run_script("--pr", "11", "--from-file", str(ctx), "--repo-dir", str(work),
                                  "--no-fetch", "--strategy", "rebase", "--apply", "--push")
            self.assertEqual(refused.returncode, 64)

            # Rebase + push WITH --force-with-lease succeeds and updates bare origin.
            ok = _run_script("--pr", "11", "--from-file", str(ctx), "--repo-dir", str(work),
                             "--no-fetch", "--strategy", "rebase", "--apply", "--push",
                             "--force-with-lease")
            self.assertEqual(ok.returncode, 0, ok.stderr)
            doc = json.loads(ok.stdout)
            self.assertTrue(doc["pushed"])
            self.assertTrue(doc["tree_unchanged"])
            remote_head = _git(bare, "rev-parse", "refs/heads/feat/step-2")
            self.assertEqual(remote_head, doc["post_head_oid"])

            # Now test rebase conflict abort on another branch.
            _git(work, "checkout", "-b", "feat/rebase-conflict", "main")
            _commit_file(work, "shared.py", "rebase-branch-line\n", "feat: conflict")
            pre = _git(work, "rev-parse", "HEAD")
            _git(work, "checkout", "main")
            _commit_file(work, "shared.py", "main-conflict-line\n", "chore: conflict")
            _git(work, "push", "origin", "main")
            _git(work, "checkout", "feat/rebase-conflict")

            ctx2 = root / "ctx2.json"
            ctx2.write_text(json.dumps({
                "pr": {"number": 99, "headRefName": "feat/rebase-conflict", "baseRefName": "main",
                       "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                       "headRefOid": pre, "isCrossRepository": False},
                "merged_prs": [],
            }), encoding="utf-8")
            bad = _run_script("--pr", "99", "--from-file", str(ctx2), "--repo-dir", str(work),
                              "--no-fetch", "--strategy", "rebase", "--apply")
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(json.loads(bad.stdout)["conflicting_files"], ["shared.py"])
            self.assertEqual(_git(work, "rev-parse", "HEAD"), pre)
            self.assertFalse((work / ".git" / "rebase-merge").exists())

    def test_stale_local_branch_refuses_to_clobber_remote_c2_and_pins_lease(self):
        """REV-001: stale local branch or remote race never overwrites remote c2."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")
            _git(work, "checkout", "-b", "feat/step-2")
            c1 = _commit_file(work, "step2.py", "x = 1\n", "feat: c1")
            _git(work, "push", "-u", "origin", "feat/step-2")

            # Peer pushes c2 to origin/feat/step-2 while work remains at stale c1.
            peer = root / "peer"
            _git(root, "clone", str(bare), str(peer))
            _git(peer, "checkout", "feat/step-2")
            c2 = _commit_file(peer, "peer.py", "y = 2\n", "feat: c2 from peer")
            _git(peer, "push", "origin", "feat/step-2")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _git(work, "checkout", "feat/step-2")

            # Case A: live fetch brings in c2; restack refuses to overwrite remote c2.
            gh_bin = root / "gh"
            gh_bin.write_text(
                f"#!{sys.executable}\n"
                "import json, sys\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['repo', 'view']:\n"
                "    print('acme/widgets')\n"
                "elif args[:3] == ['pr', 'view', '11']:\n"
                f"    print(json.dumps({{'number': 11, 'state': 'OPEN', 'headRefName': 'feat/step-2', 'baseRefName': 'main', 'mergeable': 'CONFLICTING', 'mergeStateStatus': 'DIRTY', 'headRefOid': {c2!r}, 'isCrossRepository': False}}))\n"
                "elif args[:2] == ['pr', 'list']:\n"
                f"    print(json.dumps([{{'number': 10, 'headRefName': 'feat/step-1', 'baseRefName': 'main', 'headRefOid': {h1!r}, 'mergeCommit': {{'oid': {s1!r}}}}}]))\n"
                "else:\n"
                "    sys.exit(1)\n",
                encoding="utf-8",
            )
            gh_bin.chmod(0o755)
            env = _git_env({"PATH": f"{root}{os.pathsep}{os.environ.get('PATH', '')}"})

            stale_proc = _run_script(
                "--pr", "11", "--repo-dir", str(work), "--strategy", "rebase",
                "--apply", "--push", "--force-with-lease", env=env,
            )
            self.assertEqual(stale_proc.returncode, 1)
            self.assertIn("not an ancestor", stale_proc.stderr)
            self.assertEqual(_git(bare, "rev-parse", "refs/heads/feat/step-2"), c2)
            self.assertEqual(_git(work, "rev-parse", "HEAD"), c1)

            # Case B: CWE-362 race where local tracking ref was still c1 (--no-fetch)
            # and pr_meta still reported c1, while bare remote already has c2.
            _git(work, "update-ref", "refs/remotes/origin/feat/step-2", c1)
            race_ctx = root / "race_ctx.json"
            race_ctx.write_text(json.dumps({
                "pr": {
                    "number": 11, "headRefName": "feat/step-2", "baseRefName": "main",
                    "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                    "headRefOid": c1, "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10, "headRefName": "feat/step-1", "baseRefName": "main",
                    "headRefOid": h1, "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")
            race_proc = _run_script(
                "--pr", "11", "--from-file", str(race_ctx), "--repo-dir", str(work),
                "--no-fetch", "--strategy", "rebase", "--apply", "--push", "--force-with-lease",
            )
            self.assertEqual(race_proc.returncode, 1)
            race_doc = json.loads(race_proc.stdout)
            self.assertEqual(race_doc["status"], "push_rejected")
            self.assertFalse(race_doc["pushed"])
            self.assertEqual(_git(bare, "rev-parse", "refs/heads/feat/step-2"), c2)
            self.assertEqual(_git(work, "rev-parse", "HEAD"), c1)

    def test_exact_tree_squash_ours_rejects_flattened_merge_commit_and_rolls_back(self):
        """REV-002: rebase flattening a merge commit fails tree_mismatch before push."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")

            _git(work, "checkout", "-b", "feat/step-2")
            _commit_file(work, "step2.py", "x = 2\n", "feat: step 2")
            _git(work, "checkout", "-b", "feat/side", h1)
            side = _commit_file(work, "side.py", "s = 1\n", "feat: side")
            _git(work, "checkout", "feat/step-2")
            _git(work, "merge", "--no-ff", "--no-commit", side)
            (work / "merge_only.py").write_text("m = 1\n", encoding="utf-8")
            _git(work, "add", "merge_only.py")
            _git(work, "-c", "commit.gpgsign=false", "commit", "-m", "merge side with merge_only.py")
            h2 = _git(work, "rev-parse", "HEAD")
            _git(work, "push", "-u", "origin", "feat/step-2")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _git(work, "checkout", "feat/step-2")

            ctx = root / "merge_commit_ctx.json"
            ctx.write_text(json.dumps({
                "pr": {
                    "number": 11, "headRefName": "feat/step-2", "baseRefName": "main",
                    "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                    "headRefOid": h2, "isCrossRepository": False,
                },
                "merged_prs": [{
                    "number": 10, "headRefName": "feat/step-1", "baseRefName": "main",
                    "headRefOid": h1, "mergeCommit": {"oid": s1},
                }],
            }), encoding="utf-8")

            proc = _run_script(
                "--pr", "11", "--from-file", str(ctx), "--repo-dir", str(work),
                "--no-fetch", "--strategy", "rebase", "--apply", "--push", "--force-with-lease",
            )
            self.assertEqual(proc.returncode, 1)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["status"], "tree_mismatch")
            self.assertFalse(doc["applied"])
            self.assertFalse(doc["pushed"])
            self.assertFalse(doc["tree_unchanged"])
            self.assertEqual(_git(work, "rev-parse", "HEAD"), h2)
            self.assertTrue((work / "merge_only.py").is_file())
            self.assertEqual(_git(bare, "rev-parse", "refs/heads/feat/step-2"), h2)


class TestCascadeAndLiveGh(unittest.TestCase):
    """Topological cascade ordering, fork isolation, CWE-88, S8, and temp gh CLI."""

    def test_cascade_dry_run_topological_order_and_fork_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)
            proc = _run_script(
                "--cascade", "--merged-pr", "10",
                "--from-file", str(FIXTURES / "known_good" / "cascade_stack.json"),
                "--repo-dir", str(work), "--no-fetch", "--dry-run",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual([p["number"] for p in doc["plan"]], [11, 12])
            self.assertTrue(doc["plan"][0]["needs_retarget"])
            self.assertEqual(doc["plan"][0]["target_base"], "main")
            self.assertFalse(doc["plan"][1]["needs_retarget"])
            self.assertEqual(doc["plan"][1]["target_base"], "feat/step-2")
            self.assertEqual([f["number"] for f in doc["skipped_forks"]], [13])

    def test_cascade_apply_multi_pr_stack_and_upstream_conflict_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")

            _git(work, "checkout", "-b", "feat/step-2")
            h2 = _commit_file(work, "shared.py", "line1-step1-step2\nline2\nline3\n", "feat: step 2")

            _git(work, "checkout", "-b", "feat/step-3")
            h3 = _commit_file(work, "step3.py", "z = 3\n", "feat: step 3")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")

            cascade_ctx = root / "cascade.json"
            cascade_ctx.write_text(json.dumps({
                "merged_pr": {
                    "number": 10, "state": "MERGED", "headRefName": "feat/step-1",
                    "baseRefName": "main", "headRefOid": h1, "mergeCommit": {"oid": s1},
                },
                "open_prs": [
                    {"number": 12, "headRefName": "feat/step-3", "baseRefName": "feat/step-2",
                     "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
                     "headRefOid": h3, "isCrossRepository": False},
                    {"number": 11, "headRefName": "feat/step-2", "baseRefName": "feat/step-1",
                     "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                     "headRefOid": h2, "isCrossRepository": False},
                ],
            }), encoding="utf-8")

            proc = _run_script("--cascade", "--merged-pr", "10", "--from-file", str(cascade_ctx),
                               "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertTrue(doc["applied"])
            self.assertEqual([r["number"] for r in doc["results"]], [11, 12])
            self.assertEqual(_git(work, "rev-parse", "--abbrev-ref", "HEAD"), "main")
            # Now force an upstream conflict on feat/step-2 vs main and verify #12 gets blocked.
            _git(work, "checkout", "main")
            _commit_file(work, "shared.py", "main-breaks-step2\n", "chore: conflict")
            _git(work, "push", "origin", "main")
            bad = _run_script("--cascade", "--merged-pr", "10", "--from-file", str(cascade_ctx),
                              "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(bad.returncode, 1)
            bad_doc = json.loads(bad.stdout)
            self.assertEqual(bad_doc["results"][0]["status"], "conflict")
            self.assertEqual(bad_doc["results"][1]["status"], "blocked_by_upstream_conflict")

    def test_cascade_rebase_multi_commit_parent_tracks_parent_pre_oid_and_fast_forwards(self):
        """REV-003 + REV-001: cascade rebase tracks parent_pre_oid and ff-syncs behind local head."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "v1\nline2\nline3\n", "feat: step 1")

            # #11 has TWO commits modifying the same line of shared.py.
            _git(work, "checkout", "-b", "feat/step-2")
            _commit_file(work, "shared.py", "v2a\nline2\nline3\n", "feat: step 2a")
            _commit_file(work, "shared.py", "v2b\nline2\nline3\n", "feat: step 2b")
            _git(work, "push", "-u", "origin", "feat/step-2")

            # Peer pushes one more commit on feat/step-2 so work's local feat/step-2 is behind!
            peer = root / "peer"
            _git(root, "clone", str(bare), str(peer))
            _git(peer, "checkout", "feat/step-2")
            h2 = _commit_file(peer, "step2_peer.py", "p = 1\n", "feat: step 2c peer")
            _git(peer, "push", "origin", "feat/step-2")

            # #12 branches from h2 (via peer) and adds step3.py.
            _git(peer, "checkout", "-b", "feat/step-3")
            h3 = _commit_file(peer, "step3.py", "z = 3\n", "feat: step 3")
            _git(peer, "push", "-u", "origin", "feat/step-3")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _git(work, "fetch", "origin", "--prune")

            cascade_ctx = root / "cascade_rebase.json"
            cascade_ctx.write_text(json.dumps({
                "merged_pr": {
                    "number": 10, "state": "MERGED", "headRefName": "feat/step-1",
                    "baseRefName": "main", "headRefOid": h1, "mergeCommit": {"oid": s1},
                },
                "open_prs": [
                    {"number": 12, "headRefName": "feat/step-3", "baseRefName": "feat/step-2",
                     "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
                     "headRefOid": h3, "isCrossRepository": False},
                    {"number": 11, "headRefName": "feat/step-2", "baseRefName": "feat/step-1",
                     "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                     "headRefOid": h2, "isCrossRepository": False},
                ],
            }), encoding="utf-8")

            proc = _run_script(
                "--cascade", "--merged-pr", "10", "--from-file", str(cascade_ctx),
                "--repo-dir", str(work), "--no-fetch", "--strategy", "rebase", "--apply",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            doc = json.loads(proc.stdout)
            self.assertTrue(doc["applied"])
            self.assertEqual([r["number"] for r in doc["results"]], [11, 12])
            self.assertEqual(doc["results"][0]["mode"], "exact_tree_squash_ours")
            self.assertEqual(doc["results"][1]["mode"], "cascade_parent_onto")
            self.assertEqual(doc["results"][1]["parent_pre_oid"], h2)

            # Confirm step2_peer.py (from c2 ff), shared.py v2b, and step3.py all survived!
            _git(work, "checkout", "feat/step-3")
            self.assertTrue((work / "step2_peer.py").is_file())
            self.assertTrue((work / "step3.py").is_file())
            self.assertEqual((work / "shared.py").read_text(encoding="utf-8"), "v2b\nline2\nline3\n")
            _git(work, "merge-base", "--is-ancestor", s1, "HEAD")

            # Also verify diverged local branch is refused cleanly in cascade.
            _git(work, "checkout", "feat/step-2")
            _commit_file(work, "local_only.py", "l = 1\n", "feat: local diverge")
            div = _run_script(
                "--cascade", "--merged-pr", "10", "--from-file", str(cascade_ctx),
                "--repo-dir", str(work), "--no-fetch", "--strategy", "rebase", "--apply",
            )
            self.assertEqual(div.returncode, 1)
            div_doc = json.loads(div.stdout)
            self.assertEqual(div_doc["results"][0]["status"], "stale_local_branch")
            self.assertEqual(div_doc["results"][1]["status"], "blocked_by_upstream_conflict")

    def test_known_bad_cycle_and_unsafe_ref_and_s8_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)

            cycle = _run_script("--cascade", "--merged-pr", "20",
                                "--from-file", str(FIXTURES / "known_bad" / "cascade_cycle.json"),
                                "--repo-dir", str(work), "--no-fetch", "--dry-run")
            self.assertEqual(cycle.returncode, 1)
            self.assertIn("cycle", cycle.stderr)

            self_loop = root / "self_loop.json"
            self_loop.write_text(json.dumps({
                "merged_pr": {"number": 20, "state": "MERGED",
                              "headRefName": "feat/step-1", "baseRefName": "main"},
                "open_prs": [{"number": 24, "headRefName": "feat/loop", "baseRefName": "feat/loop",
                              "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                              "isCrossRepository": False}],
            }), encoding="utf-8")
            loop_proc = _run_script("--cascade", "--merged-pr", "20",
                                    "--from-file", str(self_loop),
                                    "--repo-dir", str(work), "--no-fetch", "--dry-run")
            self.assertEqual(loop_proc.returncode, 1)
            self.assertIn("self-referential", loop_proc.stderr)

            unsafe = _run_script("--pr", "23",
                                 "--from-file", str(FIXTURES / "known_bad" / "cascade_unsafe_ref.json"),
                                 "--repo-dir", str(work), "--no-fetch", "--dry-run")
            self.assertEqual(unsafe.returncode, 1)
            self.assertIn("start with '-'", unsafe.stderr)

            # S8 secret redaction on ingest.
            secret_file = root / "secret.json"
            secret_file.write_text(json.dumps({
                "pr": {
                    "number": 1,
                    "headRefName": "feat/ok",
                    "baseRefName": "main",
                    "url": "https://x-access-token:ghp_1234567890abcdef@github.com/a/b",
                },
                "merged_prs": [],
            }), encoding="utf-8")
            loaded = RSK.load_json_file(secret_file)
            self.assertNotIn("ghp_1234567890abcdef", json.dumps(loaded))
            self.assertIn("[REDACTED", json.dumps(loaded))
            self.assertEqual(
                RSK.redact_secrets("Bearer abcdef1234567890"),
                "Bearer [REDACTED]",
            )

    def test_live_gh_mode_with_fetch_and_stale_base_retarget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare, work = _init_bare_and_clone(root)

            _git(work, "checkout", "-b", "feat/step-1")
            h1 = _commit_file(work, "shared.py", "line1-step1\nline2\nline3\n", "feat: step 1")
            _git(work, "checkout", "-b", "feat/step-2")
            h2 = _commit_file(work, "step2.py", "x = 2\n", "feat: step 2")
            _git(work, "push", "-u", "origin", "feat/step-2")

            s1 = _squash_branch_to_main(work, h1, "feat: step 1 (#10)")
            _git(work, "checkout", "feat/step-2")

            state_log = root / "gh_calls.log"
            gh_bin = root / "gh"
            gh_bin.write_text(
                f"#!{sys.executable}\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                f"with Path({str(state_log)!r}).open('a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(args) + '\\n')\n"
                "if args[:2] == ['repo', 'view']:\n"
                "    print('acme/widgets')\n"
                "elif args[:3] == ['pr', 'view', '11']:\n"
                f"    print(json.dumps({{'number': 11, 'state': 'OPEN', 'headRefName': 'feat/step-2', 'baseRefName': 'feat/step-1', 'mergeable': 'CONFLICTING', 'mergeStateStatus': 'DIRTY', 'headRefOid': {h2!r}, 'isCrossRepository': False}}))\n"
                "elif args[:3] == ['pr', 'view', '10']:\n"
                f"    print(json.dumps({{'number': 10, 'state': 'MERGED', 'headRefName': 'feat/step-1', 'baseRefName': 'main', 'headRefOid': {h1!r}, 'mergeCommit': {{'oid': {s1!r}}}}}))\n"
                "elif args[:2] == ['pr', 'list'] and 'merged' in args and '--base' in args:\n"
                "    base = args[args.index('--base') + 1]\n"
                "    if base == 'main':\n"
                f"        print(json.dumps([{{'number': 10, 'headRefName': 'feat/step-1', 'baseRefName': 'main', 'headRefOid': {h1!r}, 'mergeCommit': {{'oid': {s1!r}}}}}]))\n"
                "    else:\n"
                "        print('[]')\n"
                "elif args[:2] == ['pr', 'list'] and 'merged' in args and '--head' in args:\n"
                f"    print(json.dumps([{{'number': 10, 'headRefName': 'feat/step-1', 'baseRefName': 'main', 'headRefOid': {h1!r}, 'mergeCommit': {{'oid': {s1!r}}}}}]))\n"
                "elif args[:2] == ['pr', 'list'] and 'open' in args:\n"
                f"    print(json.dumps([{{'number': 11, 'headRefName': 'feat/step-2', 'baseRefName': 'feat/step-1', 'mergeable': 'CONFLICTING', 'mergeStateStatus': 'DIRTY', 'headRefOid': {h2!r}, 'isCrossRepository': False}}]))\n"
                "elif args[:2] == ['pr', 'edit']:\n"
                "    print('ok')\n"
                "else:\n"
                "    sys.exit(1)\n",
                encoding="utf-8",
            )
            gh_bin.chmod(0o755)
            env = _git_env({"PATH": f"{root}{os.pathsep}{os.environ.get('PATH', '')}"})

            # Live single-PR restack with fetch + deleted base retargeting + gh pr edit.
            proc = _run_script("--pr", "11", "--repo-dir", str(work), "--apply", env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["pr"]["retarget_base_needed"], "main")
            self.assertEqual(doc["mode"], "exact_tree_squash_ours")

            # Live cascade dry-run via gh.
            cas = _run_script("--cascade", "--merged-pr", "10", "--repo-dir", str(work),
                              "--dry-run", env=env)
            self.assertEqual(cas.returncode, 0, cas.stderr)
            calls = state_log.read_text(encoding="utf-8")
            self.assertIn("pr edit 11 --repo acme/widgets --base main", calls)
            self.assertIn("pr list --repo acme/widgets --state open", calls)
            # Touch bare to verify real remote repo existed.
            self.assertTrue((bare / "HEAD").is_file())


class TestRefusalsAndUsage(unittest.TestCase):
    """T4 negatives: dirty worktree, branch mismatch, usage errors, missing CLIs."""

    def test_dirty_worktree_and_branch_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, work = _init_bare_and_clone(root)
            h = _git(work, "rev-parse", "HEAD")
            ctx = root / "ctx.json"
            ctx.write_text(json.dumps({
                "pr": {"number": 5, "headRefName": "feat/other", "baseRefName": "main",
                       "headRefOid": h, "isCrossRepository": False},
                "merged_prs": [],
            }), encoding="utf-8")

            # Branch mismatch (we are on main, PR expects feat/other).
            _git(work, "branch", "feat/other")
            mismatch = _run_script("--pr", "5", "--from-file", str(ctx),
                                   "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(mismatch.returncode, 1)
            self.assertIn("expected PR head", mismatch.stderr)

            # Dirty worktree.
            _git(work, "checkout", "feat/other")
            (work / "dirty.txt").write_text("uncommitted", encoding="utf-8")
            dirty = _run_script("--pr", "5", "--from-file", str(ctx),
                                "--repo-dir", str(work), "--no-fetch", "--apply")
            self.assertEqual(dirty.returncode, 1)
            self.assertIn("uncommitted changes", dirty.stderr)

    def test_usage_errors_exit_64_and_missing_cli_exits_2(self):
        bad_cases = [
            [],
            ["--pr", "0"],
            ["--cascade"],
            ["--pr", "1", "--merged-pr", "2"],
            ["--pr", "1", "--cascade", "--merged-pr", "2"],
            ["--pr", "1", "--repo", "bad"],
            ["--pr", "1", "--remote", "-evil"],
            ["--pr", "1", "--force-with-lease"],
            ["--pr", "1", "--apply", "--push", "--strategy", "rebase"],
            ["--pr", "1", "--push"],
            ["--pr", "1", "--dry-run", "--apply"],
        ]
        for args in bad_cases:
            self.assertEqual(_run_script(*args).returncode, 64, args)

        with tempfile.TemporaryDirectory() as empty:
            env = {**os.environ, "PATH": empty}
            self.assertEqual(_run_script("--pr", "1", "--no-fetch", env=env).returncode, 2)
            self.assertEqual(_run_script("--pr", "1", env=env).returncode, 2)

        self.assertEqual(_run_script("--pr", "1", "--repo-dir", "/no/such/repo").returncode, 2)
        self.assertEqual(_run_script("--help").returncode, 0)


if __name__ == "__main__":
    unittest.main()
