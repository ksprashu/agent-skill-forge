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

"""Tests for ship_pr.py: partial Refs vs Fixes guard, commit check, SHA/branch gate binding."""

from __future__ import annotations

import json
import os
import random
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPT = TESTS.parent / "scripts" / "ship_pr.py"


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        env=env,
        timeout=60,
    )


def _dynamic_token(seed: int) -> str:
    rng = random.Random(seed)
    return "ghp_" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(32))


def _write_gate(tmp_dir: Path, verdict: str = "PASS", head_sha: str = "abc1234def5678", branch: str = "fix/101") -> Path:
    path = tmp_dir / f"gate_{verdict.lower()}_{branch.replace('/', '_')}.json"
    path.write_text(
        json.dumps({"verdict": verdict, "head_sha": head_sha, "branch": branch, "failures": [] if verdict == "PASS" else ["failed"]}),
        encoding="utf-8",
    )
    return path


class TestDryRunAndIssueLinkSafety(unittest.TestCase):
    """T1 & T4: valid PR creation, SHA/branch gate binding, and partial-issue protection."""

    def test_valid_fixes_and_refs_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = _write_gate(Path(tmp), branch="fix/issue-101-auth")
            proc = run_cli(
                "--title", "fix(auth): guard empty bearer token",
                "--body", "Handles empty header cleanly.",
                "--head", "fix/issue-101-auth",
                "--head-sha", "abc1234def5678",
                "--base", "main",
                "--fixes", "101",
                "--refs", "102",
                "--repo", "acme/widgets",
                "--gate-report", str(gate),
                "--dry-run",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["action"], "create_pr")
            body = out["payload"]["body"]
            self.assertIn("Fixes #101", body)
            self.assertIn("Refs #102", body)
            self.assertNotIn("Fixes #102", body)
            self.assertEqual(out["payload"]["fixes"], [101])
            self.assertEqual(out["payload"]["refs"], [102])

    def test_refuses_closing_keyword_and_issue_urls_for_partial_refs_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = _write_gate(Path(tmp), branch="fix/issue-102-cli")
            for bad_body in (
                "Fixes #102 partially.",
                "Closes #101, #102",
                "Fixes #101 and #102",
                "Resolves acme/widgets#102",
                "Fixes https://github.com/acme/widgets/issues/102",
                "Closes https://github.com/acme/widgets/issues/101, https://github.com/acme/widgets/issues/102",
            ):
                proc = run_cli(
                    "--title", "fix(cli): create export parent dir",
                    "--body", bad_body,
                    "--head", "fix/issue-102-cli",
                    "--fixes", "101",
                    "--refs", "102",
                    "--gate-report", str(gate),
                    "--dry-run",
                )
                self.assertEqual(proc.returncode, 1, (bad_body, proc.stdout))
                self.assertIn("#102", proc.stderr)

    def test_refuses_protected_branches_and_same_head_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = _write_gate(Path(tmp), branch="main")
            for head, base in (("main", "main"), ("master", "main"), ("release", "release")):
                proc = run_cli(
                    "--title", "fix(auth): guard empty token",
                    "--body", "Fixes #101",
                    "--head", head,
                    "--base", base,
                    "--fixes", "101",
                    "--gate-report", str(gate),
                    "--dry-run",
                )
                self.assertEqual(proc.returncode, 1, (head, base))

    def test_refuses_non_conventional_title_and_ai_attribution_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = _write_gate(Path(tmp), branch="fix/101")
            self.assertEqual(
                run_cli(
                    "--title", "Fix bug in auth",
                    "--body", "Fixes #101",
                    "--head", "fix/101",
                    "--fixes", "101",
                    "--gate-report", str(gate),
                    "--dry-run",
                ).returncode,
                1,
            )
            for bad_body in (
                "Fixes #101\n\nCo-Authored-By: Claude <noreply@example.com>",
                "Fixes #101\n\nGenerated with [Claude Code](https://claude.com/claude-code)",
            ):
                self.assertEqual(
                    run_cli(
                        "--title", "fix(auth): guard empty token",
                        "--body", bad_body,
                        "--head", "fix/101",
                        "--fixes", "101",
                        "--gate-report", str(gate),
                        "--dry-run",
                    ).returncode,
                    1,
                    bad_body,
                )
            tok = _dynamic_token(91)
            self.assertEqual(
                run_cli(
                    "--title", "fix(auth): guard empty token",
                    "--body", f"Fixes #101\nDebug token: {tok}",
                    "--head", "fix/101",
                    "--fixes", "101",
                    "--gate-report", str(gate),
                    "--dry-run",
                ).returncode,
                1,
            )

    def test_gate_report_binding_and_stale_or_unlinked_report_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fail_gate = _write_gate(tmp_dir, verdict="FAIL", branch="fix/101")
            pass_gate = _write_gate(tmp_dir, verdict="PASS", head_sha="abc1234def5678", branch="fix/101")
            no_sha_gate = tmp_dir / "no_sha.json"
            no_sha_gate.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")

            # Missing --gate-report and missing --no-gate fails usage
            self.assertEqual(
                run_cli("--title", "fix(auth): guard", "--body", "Fixes #101", "--head", "fix/101", "--fixes", "101", "--dry-run").returncode,
                64,
            )
            # --no-gate requires >=20 char reason
            self.assertEqual(
                run_cli("--title", "fix(auth): guard", "--body", "Fixes #101", "--head", "fix/101", "--fixes", "101", "--no-gate", "--no-gate-reason", "too short", "--dry-run").returncode,
                64,
            )
            self.assertEqual(
                run_cli("--title", "fix(auth): guard", "--body", "Fixes #101", "--head", "fix/101", "--fixes", "101", "--no-gate", "--no-gate-reason", "Emergency hotfix approved by owner on call.", "--dry-run").returncode,
                0,
            )

            # Fail verdict, missing SHA/branch, wrong SHA, and wrong branch all exit 1
            for bad_gate, sha, branch in (
                (fail_gate, "abc1234def5678", "fix/101"),
                (no_sha_gate, "abc1234def5678", "fix/101"),
                (pass_gate, "deadbeef999999", "fix/101"),
                (pass_gate, "abc1234def5678", "fix/other-branch"),
            ):
                proc = run_cli(
                    "--title", "fix(auth): guard empty token",
                    "--body", "Fixes #101",
                    "--head", branch,
                    "--head-sha", sha,
                    "--fixes", "101",
                    "--gate-report", str(bad_gate),
                    "--dry-run",
                )
                self.assertEqual(proc.returncode, 1, (bad_gate.name, sha, branch, proc.stdout))

            proc_ok = run_cli(
                "--title", "fix(auth): guard empty token",
                "--body", "Fixes #101",
                "--head", "fix/101",
                "--head-sha", "abc1234def5678",
                "--fixes", "101",
                "--gate-report", str(pass_gate),
                "--dry-run",
            )
            self.assertEqual(proc_ok.returncode, 0, proc_ok.stderr)

    def test_usage_errors_exit_64(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = _write_gate(Path(tmp), branch="fix/1")
            for args in (
                ["--title", "fix(a): ok", "--body", "hi", "--head", "fix/1", "--gate-report", str(gate)],
                ["--title", "fix(a): ok", "--body", "hi", "--head", "fix/1", "--fixes", "5", "--refs", "5", "--gate-report", str(gate)],
                ["--title", "fix(a): ok", "--body", "hi", "--head", "fix/1", "--fixes", "0", "--gate-report", str(gate)],
                ["--title", "fix(a): ok", "--body", "hi", "--head", "fix/1", "--fixes", "5", "--repo", "bad", "--gate-report", str(gate)],
                ["--title", "fix(a): ok", "--body", "hi", "--head", "fix/1", "--base", "-bad", "--fixes", "5", "--gate-report", str(gate)],
            ):
                self.assertEqual(run_cli(*args).returncode, 64, args)

    def test_live_repo_checks_commit_messages_stale_sha_and_fake_gh_pr_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            for cmd in (
                ["git", "init", "-b", "main"],
                ["git", "config", "user.email", "ci@example.com"],
                ["git", "config", "user.name", "CI"],
                ["git", "config", "commit.gpgsign", "false"],
            ):
                subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
            (repo / "a.txt").write_text("hi\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "fix/issue-101"], cwd=repo, check=True, capture_output=True)
            (repo / "a.txt").write_text("fixed\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "fix(auth): handle empty token"], cwd=repo, check=True, capture_output=True)
            head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

            gate = _write_gate(Path(tmp), head_sha=head_sha, branch="fix/issue-101")
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            git_bin = shutil.which("git")
            if not git_bin:
                self.skipTest("git not installed")
            (bin_dir / "git").symlink_to(git_bin)
            gh_path = bin_dir / "gh"
            gh_path.write_text(
                textwrap.dedent(
                    f"""\
                    #!{sys.executable}
                    import sys
                    if sys.argv[1:3] == ["pr", "create"]:
                        sys.stdout.write("https://github.com/acme/widgets/pull/401\\n")
                        sys.exit(0)
                    sys.exit(1)
                    """
                ),
                encoding="utf-8",
            )
            gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
            proc = run_cli(
                "--title", "fix(auth): guard empty token",
                "--body", "Fixes #101",
                "--repo-root", str(repo),
                "--repo", "acme/widgets",
                "--fixes", "101",
                "--gate-report", str(gate),
                env={**os.environ, "PATH": str(bin_dir)},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["url"], "https://github.com/acme/widgets/pull/401")
            self.assertEqual(out["head"], "fix/issue-101")

            # Add commit with Fixes #102 while declaring --refs 102 -> stale SHA & commit-msg guard fire
            (repo / "a.txt").write_text("more\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "fix(cli): partial\n\nFixes #102"], cwd=repo, check=True, capture_output=True)
            new_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
            fresh_gate = _write_gate(Path(tmp), head_sha=new_sha, branch="fix/issue-101")

            stale_proc = run_cli(
                "--title", "fix(auth): guard empty token",
                "--body", "Fixes #101\nRefs #102",
                "--repo-root", str(repo),
                "--fixes", "101",
                "--refs", "102",
                "--gate-report", str(gate),
                "--dry-run",
                env={**os.environ, "PATH": str(bin_dir)},
            )
            self.assertEqual(stale_proc.returncode, 1)

            commit_guard_proc = run_cli(
                "--title", "fix(auth): guard empty token",
                "--body", "Fixes #101\nRefs #102",
                "--repo-root", str(repo),
                "--fixes", "101",
                "--refs", "102",
                "--gate-report", str(fresh_gate),
                "--dry-run",
                env={**os.environ, "PATH": str(bin_dir)},
            )
            self.assertEqual(commit_guard_proc.returncode, 1)
            self.assertIn("#102", commit_guard_proc.stderr)


if __name__ == "__main__":
    unittest.main()
