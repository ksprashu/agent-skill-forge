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

"""End-to-end pipeline and documentation contract tests for issue-loop (T5, T6, K2, K3, S6)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPTS = SKILL / "scripts"
FIXTURES = TESTS / "fixtures"
GOOD_DIR = FIXTURES / "known_good"

CLI_SCRIPTS = (
    "issue_state.py",
    "stage_comment.py",
    "plan_tracks.py",
    "verify_gate.py",
    "ship_pr.py",
)


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        shell=False,
        timeout=60,
    )


class TestEndToEndOfflinePipeline(unittest.TestCase):
    """T5: full 5-stage offline pipeline from issue intake to PR creation and final comment."""

    def test_five_stage_dry_run_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            evidence_path = tmp_dir / "evidence.json"
            gate_path = tmp_dir / "gate.json"

            # Stage 1: Collect state
            s1 = _run(
                "issue_state.py",
                "--from-file", str(FIXTURES / "gh_issues_open.json"),
                "--repo", "acme/widgets",
                "--out", str(evidence_path),
            )
            self.assertEqual(s1.returncode, 0, s1.stderr)
            ev = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(ev["summary"]["open_issues"], 3)

            # Stage 1 comment (triage)
            c1 = _run(
                "stage_comment.py",
                "--issue", "101",
                "--stage", "triage",
                "--body", "Triaged as valid_bug at src/auth/tokens.py:42.",
                "--from-file", str(FIXTURES / "gh_comments_empty.json"),
                "--repo", "acme/widgets",
                "--dry-run",
            )
            self.assertEqual(c1.returncode, 0, c1.stderr)
            self.assertEqual(json.loads(c1.stdout)["action"], "create")

            # Stage 2: Validate file-disjoint plan against Stage 1 evidence
            s2 = _run(
                "plan_tracks.py",
                "--plan", str(GOOD_DIR / "plan_disjoint_swarm.json"),
                "--from-evidence", str(evidence_path),
                "--check-disjoint",
            )
            self.assertEqual(s2.returncode, 0, s2.stdout + s2.stderr)
            plan_out = json.loads(s2.stdout)
            self.assertEqual(plan_out["issue_link_modes"]["101"], "Fixes")
            self.assertEqual(plan_out["issue_link_modes"]["102"], "Refs")

            # Stage 2 comment (plan)
            c2 = _run(
                "stage_comment.py",
                "--issue", "101",
                "--stage", "plan",
                "--body", "Assigned to track-auth (src/auth/tokens.py, tests/test_tokens.py).",
                "--from-file", str(FIXTURES / "gh_comments_existing.json"),
                "--trusted-login", "maintainer",
                "--repo", "acme/widgets",
                "--dry-run",
            )
            self.assertEqual(c2.returncode, 0, c2.stderr)

            # Stage 4: Verification gate (swarm cross-family)
            s4 = _run(
                "verify_gate.py",
                "--bundle", str(GOOD_DIR / "verify_bundle_swarm.json"),
                "--swarm",
            )
            self.assertEqual(s4.returncode, 0, s4.stdout + s4.stderr)
            gate_path.write_text(s4.stdout, encoding="utf-8")

            # Stage 5: Create PR bound to PASS gate + final stage comment
            s5 = _run(
                "ship_pr.py",
                "--title", "fix(auth): handle empty token header",
                "--body", "Guards empty bearer token header in verify_token.",
                "--head", "fix/issue-101-auth-token",
                "--head-sha", "abc1234def5678",
                "--base", "main",
                "--fixes", "101",
                "--refs", "102",
                "--repo", "acme/widgets",
                "--gate-report", str(gate_path),
                "--dry-run",
            )
            self.assertEqual(s5.returncode, 0, s5.stderr)
            pr_out = json.loads(s5.stdout)
            self.assertIn("Fixes #101", pr_out["payload"]["body"])
            self.assertIn("Refs #102", pr_out["payload"]["body"])

            c5 = _run(
                "stage_comment.py",
                "--issue", "101",
                "--stage", "pr",
                "--body", "Opened PR #401 at commit abc1234def5678; gate PASS (12/12 tests).",
                "--from-file", str(FIXTURES / "gh_comments_existing.json"),
                "--trusted-login", "maintainer",
                "--repo", "acme/widgets",
                "--dry-run",
            )
            self.assertEqual(c5.returncode, 0, c5.stderr)
            self.assertIn("<!-- issue-loop:stage=pr v1 -->", json.loads(c5.stdout)["body"])


class TestDocsAndCliParity(unittest.TestCase):
    """K2, K3, S6: SKILL.md budget, explicit reference disclosure, and --help flag parity."""

    def test_skill_md_is_within_200_lines_and_references_all_reference_docs(self):
        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        lines = skill_md.splitlines()
        self.assertLessEqual(len(lines), 200, f"SKILL.md has {len(lines)} lines (> 200)")

        ref_dir = SKILL / "references"
        ref_files = sorted(p.name for p in ref_dir.glob("*.md"))
        self.assertTrue(ref_files, "Expected at least one reference doc")
        for ref_name in ref_files:
            self.assertIn(f"references/{ref_name}", skill_md, f"Dead-weight reference {ref_name} not cited in SKILL.md")

    def test_documented_flags_match_script_help_outputs(self):
        docs_text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]
        )
        help_by_script = {}
        for script in CLI_SCRIPTS:
            proc = _run(script, "--help")
            self.assertEqual(proc.returncode, 0, f"{script} --help failed: {proc.stderr}")
            help_by_script[script] = proc.stdout

        # Check every `scripts/<name>.py ...` invocation snippet in SKILL.md and references/
        pattern = re.compile(r"(?:<skill-dir>/)?scripts/(" + "|".join(re.escape(s) for s in CLI_SCRIPTS) + r")([^\n`]*)")
        matches = list(pattern.finditer(docs_text))
        self.assertGreaterEqual(len(matches), len(CLI_SCRIPTS))
        for m in matches:
            script_name, rest = m.group(1), m.group(2)
            flags = re.findall(r"--[a-z][a-z0-9-]*", rest)
            for flag in flags:
                self.assertIn(
                    flag,
                    help_by_script[script_name],
                    f"Flag {flag} documented for {script_name} missing from --help",
                )


if __name__ == "__main__":
    unittest.main()
