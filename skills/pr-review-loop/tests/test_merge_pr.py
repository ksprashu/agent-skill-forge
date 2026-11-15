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

"""Tests for merge_pr.py and skill doc/flag parity (T1, T4, T6, V1-V2, S6)."""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures"
SCRIPTS = SKILL / "scripts"
SCRIPT = SCRIPTS / "merge_pr.py"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        env=env,
    )


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestMergePrReadiness(unittest.TestCase):
    """V1/V2/T1/T4: clean PR passes; conflicts, BLOCKED, failing checks, open threads fail closed."""

    def test_known_good_mergeable_clean_passes_dry_run(self):
        proc = _run("--from-file", str(FIXTURES / "known_good" / "mergeable_clean.json"),
                    "--repo", "acme/widgets")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["ready"])
        self.assertTrue(doc["dry_run"])
        self.assertFalse(doc["executed"])
        self.assertEqual(doc["refusal_reasons"], [])
        self.assertEqual(doc["command"], [
            "gh", "pr", "merge", "12", "--repo", "acme/widgets", "--squash", "--delete-branch"
        ])

    def test_auto_and_no_delete_branch_shape_command(self):
        proc = _run("--from-file", str(FIXTURES / "known_good" / "mergeable_clean.json"),
                    "--repo", "acme/widgets", "--auto", "--no-delete-branch")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["command"], [
            "gh", "pr", "merge", "12", "--repo", "acme/widgets", "--auto", "--squash"
        ])

    def test_known_bad_fixtures_are_all_refused(self):
        cases = [
            ("conflicting_pr.json", "CONFLICTING"),
            ("blocked_pr.json", "BLOCKED"),
            ("dirty_state_mergeable_flag.json", "DIRTY"),
            ("unknown_mergeable.json", "UNKNOWN"),
            ("failing_ci_check.json", "FAILURE"),
        ]
        for fname, needle in cases:
            for extra in ([], ["--auto"]):
                proc = _run("--from-file", str(FIXTURES / "known_bad" / fname), *extra)
                self.assertEqual(proc.returncode, 1, (fname, extra, proc.stdout))
                doc = json.loads(proc.stdout)
                self.assertFalse(doc["ready"], fname)
                self.assertIsNone(doc["command"], fname)
                self.assertTrue(
                    any(needle in r for r in doc["refusal_reasons"]),
                    (fname, doc["refusal_reasons"]),
                )

    def test_open_threads_and_needs_human_and_closed_pr_are_refused(self):
        for fname in ("open_p1.json", "verified_open.json", "escalation.json", "malformed_marker.json"):
            proc = _run("--from-file", str(FIXTURES / f"{fname}"))
            self.assertEqual(proc.returncode, 1, fname)
            self.assertFalse(json.loads(proc.stdout)["ready"])

        base = _load_fixture(FIXTURES / "known_good" / "mergeable_clean.json")
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Pending non-verdict CI check blocks merge.
            pending = copy.deepcopy(base)
            pending["data"]["repository"]["pullRequest"]["commits"]["nodes"][0]["commit"][
                "statusCheckRollup"]["contexts"]["nodes"][0]["status"] = "IN_PROGRESS"
            p_file = Path(tmp) / "pending.json"
            p_file.write_text(json.dumps(pending), encoding="utf-8")
            p_proc = _run("--from-file", str(p_file))
            self.assertEqual(p_proc.returncode, 1)
            self.assertTrue(any("IN_PROGRESS" in r for r in json.loads(p_proc.stdout)["refusal_reasons"]))

            # 2. Closed/merged PR refuses.
            merged = copy.deepcopy(base)
            merged["data"]["repository"]["pullRequest"]["state"] = "MERGED"
            m_file = Path(tmp) / "merged.json"
            m_file.write_text(json.dumps(merged), encoding="utf-8")
            self.assertEqual(_run("--from-file", str(m_file)).returncode, 1)

            # 3. needs-human without human-override refuses even if everything else passed.
            nh = copy.deepcopy(base)
            nh["data"]["repository"]["pullRequest"]["labels"]["nodes"] = [{"name": "needs-human"}]
            n_file = Path(tmp) / "needs_human.json"
            n_file.write_text(json.dumps(nh), encoding="utf-8")
            n_proc = _run("--from-file", str(n_file))
            self.assertEqual(n_proc.returncode, 1)
            self.assertTrue(any("needs-human" in r for r in json.loads(n_proc.stdout)["refusal_reasons"]))

    def test_live_execute_with_temp_gh_cli_and_error_paths(self):
        payload = (FIXTURES / "known_good" / "mergeable_clean.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            resp_file = tmp_path / "resp.json"
            resp_file.write_text(payload, encoding="utf-8")
            calls = tmp_path / "calls.log"
            gh_bin = tmp_path / "gh"
            gh_bin.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                f"with Path({str(calls)!r}).open('a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(args) + '\\n')\n"
                "if args[:2] == ['repo', 'view']:\n"
                "    print('acme/widgets')\n"
                "elif args[:2] == ['api', 'graphql']:\n"
                f"    print(Path({str(resp_file)!r}).read_text(encoding='utf-8'))\n"
                "elif args[:2] == ['pr', 'merge']:\n"
                "    if '--fail-merge' in args:\n"
                "        sys.stderr.write('merge failed ghp_supersecret12345\\n')\n"
                "        sys.exit(1)\n"
                "    print('Merged PR #12')\n"
                "else:\n"
                "    sys.exit(1)\n",
                encoding="utf-8",
            )
            gh_bin.chmod(0o755)
            env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ.get('PATH', '')}"}

            ok = _run("--pr", "12", "--auto", "--execute", env=env)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            doc = json.loads(ok.stdout)
            self.assertTrue(doc["executed"])
            self.assertEqual(doc["gh_output"], "Merged PR #12")
            self.assertIn(
                "pr merge 12 --repo acme/widgets --auto --squash --delete-branch",
                calls.read_text(encoding="utf-8"),
            )

            # Verify failing `gh pr merge` exits 2 and redacts leaked tokens (S8).
            gh_fail = tmp_path / "gh"
            gh_fail.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['repo', 'view']:\n"
                "    print('acme/widgets')\n"
                "elif args[:2] == ['api', 'graphql']:\n"
                f"    print(Path({str(resp_file)!r}).read_text(encoding='utf-8'))\n"
                "elif args[:2] == ['pr', 'merge']:\n"
                "    sys.stderr.write('merge rejected ghp_secretToken999999\\n')\n"
                "    sys.exit(1)\n"
                "else:\n"
                "    sys.exit(1)\n",
                encoding="utf-8",
            )
            gh_fail.chmod(0o755)
            bad_exec = _run("--pr", "12", "--execute", env=env)
            self.assertEqual(bad_exec.returncode, 2)
            self.assertNotIn("ghp_secretToken999999", bad_exec.stderr)
            self.assertIn("[REDACTED_TOKEN]", bad_exec.stderr)

    def test_usage_and_gh_errors(self):
        for args in ([], ["--pr", "0"], ["--pr", "1", "--repo", "bad"],
                     ["--from-file", str(FIXTURES / "known_good" / "mergeable_clean.json"), "--execute"],
                     ["--dry-run", "--execute"]):
            self.assertEqual(_run(*args).returncode, 64, args)

        with tempfile.TemporaryDirectory() as empty:
            env = {**os.environ, "PATH": empty}
            self.assertEqual(_run("--pr", "12", "--repo", "acme/widgets", env=env).returncode, 2)
        self.assertEqual(_run("--from-file", "/no/such/file.json").returncode, 2)


class TestDocsAndContractFreshness(unittest.TestCase):
    """K2/K3/S6/T6: SKILL.md budget, portable paths, and --help flag parity."""

    def test_skill_md_budget_links_and_portable_paths(self):
        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        lines = skill_md.splitlines()
        self.assertLessEqual(len(lines), 200)
        self.assertIn("references/commands.md", skill_md)
        self.assertIn("references/escalation.md", skill_md)
        self.assertNotRegex(skill_md, r"(?<!<skill-dir>/)scripts/\w+\.py")

    def test_documented_flags_match_help_across_all_scripts(self):
        cmds_md = (SKILL / "references" / "commands.md").read_text(encoding="utf-8")
        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        combined = cmds_md + "\n" + skill_md

        scripts = {
            "review_state.py": SCRIPTS / "review_state.py",
            "reply.py": SCRIPTS / "reply.py",
            "resolve.py": SCRIPTS / "resolve.py",
            "restack.py": SCRIPTS / "restack.py",
            "merge_pr.py": SCRIPTS / "merge_pr.py",
        }
        help_by_script: dict[str, str] = {}
        for name, path in scripts.items():
            proc = subprocess.run(
                [sys.executable, str(path), "--help"],
                capture_output=True, text=True, shell=False,
            )
            self.assertEqual(proc.returncode, 0, name)
            help_by_script[name] = proc.stdout

        # Every script invocation line in docs only names flags present in that script's --help.
        for line in combined.splitlines():
            for name in scripts:
                if f"scripts/{name}" in line:
                    for flag in re.findall(r"--[a-z][a-z0-9-]*", line):
                        self.assertIn(flag, help_by_script[name],
                                      f"{name} missing documented flag {flag}")

        # Verify expected flags exist in new/updated scripts' --help.
        for flag in ("--allow-unknown-mergeable",):
            self.assertIn(flag, help_by_script["review_state.py"])
        for flag in ("--pr", "--cascade", "--merged-pr", "--repo", "--repo-dir", "--remote",
                     "--from-file", "--strategy", "--no-fetch", "--push", "--force-with-lease",
                     "--dry-run", "--apply"):
            self.assertIn(flag, help_by_script["restack.py"])
        for flag in ("--pr", "--repo", "--from-file", "--check-name", "--bot-login",
                     "--auto", "--no-delete-branch", "--dry-run", "--execute"):
            self.assertIn(flag, help_by_script["merge_pr.py"])


if __name__ == "__main__":
    unittest.main()
