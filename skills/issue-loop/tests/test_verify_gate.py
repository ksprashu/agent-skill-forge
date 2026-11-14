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

"""Tests for verify_gate.py: V1/V2 fixtures, swarm cross-family, git SHA binding, T6 contract sync."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures"
GOOD_DIR = FIXTURES / "known_good"
BAD_DIR = FIXTURES / "known_bad"
SCRIPT = SKILL / "scripts" / "verify_gate.py"
COMMON = SKILL / "scripts" / "issue_common.py"
REVIEW_FINDINGS = SKILL.parent / "review" / "scripts" / "findings.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        timeout=60,
    )


class TestKnownGoodAndKnownBad(unittest.TestCase):
    """V1 & V2: rejects every known_bad bundle and accepts every known_good bundle."""

    def test_all_known_good_bundles_pass(self):
        good_swarm = run_cli("--bundle", str(GOOD_DIR / "verify_bundle_swarm.json"), "--swarm")
        self.assertEqual(good_swarm.returncode, 0, good_swarm.stdout + good_swarm.stderr)
        swarm_out = json.loads(good_swarm.stdout)
        self.assertEqual(swarm_out["verdict"], "PASS")
        self.assertEqual(swarm_out["head_sha"], "abc1234def5678")
        self.assertEqual(swarm_out["branch"], "fix/issue-101-auth-token")
        self.assertEqual(swarm_out["cross_family"]["author_family"], "gemini")
        self.assertEqual(swarm_out["cross_family"]["review_family"], "claude")

        good_solo = run_cli("--bundle", str(GOOD_DIR / "verify_bundle_standalone.json"))
        self.assertEqual(good_solo.returncode, 0, good_solo.stdout + good_solo.stderr)
        solo_out = json.loads(good_solo.stdout)
        self.assertEqual(solo_out["verdict"], "PASS")
        self.assertEqual(solo_out["head_sha"], "deadbeef123456")

    def test_all_known_bad_bundles_rejected(self):
        expected = {
            "verify_bundle_same_family_swarm.json": "cross-family",
            "verify_bundle_open_review_p1.json": "blocking",
            "verify_bundle_scope_violation.json": "billing.py",
            "verify_bundle_stale_sha.json": "head_sha",
            "verify_bundle_missing_scanner_not_inspected.json": "not_inspected",
            "verify_bundle_omitted_scanner.json": "gitleaks",
            "verify_bundle_wrong_security_producer.json": "producer",
            "verify_bundle_main_branch.json": "protected branch",
        }
        for name, needle in expected.items():
            with self.subTest(fixture=name):
                proc = run_cli("--bundle", str(BAD_DIR / name))
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                out = json.loads(proc.stdout)
                self.assertEqual(out["verdict"], "FAIL")
                self.assertIn(needle.lower(), "\n".join(out["failures"]).lower())


class TestSwarmAndGitRepoGates(unittest.TestCase):
    """T4 negatives, fallback disclosure, findings contract validation, live git HEAD check."""

    def test_swarm_flag_rejects_standalone_bundle_without_cross_family(self):
        proc = run_cli("--bundle", str(GOOD_DIR / "verify_bundle_standalone.json"), "--swarm")
        self.assertEqual(proc.returncode, 1)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "FAIL")

    def test_intra_family_fallback_requires_explicit_disclosure_reason(self):
        bundle = json.loads((BAD_DIR / "verify_bundle_same_family_swarm.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            bpath = Path(tmp) / "bundle.json"
            bpath.write_text(json.dumps(bundle), encoding="utf-8")
            refused = run_cli("--bundle", str(bpath), "--swarm", "--allow-intra-family-fallback")
            self.assertEqual(refused.returncode, 1)

            bundle["intra_family_fallback_reason"] = "Gemini quota exhausted across workspace; deterministic scanners and full unittest suite ran."
            bpath.write_text(json.dumps(bundle), encoding="utf-8")
            allowed = run_cli("--bundle", str(bpath), "--swarm", "--allow-intra-family-fallback")
            self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_repo_root_checks_live_git_head_match_and_drift(self):
        bundle = json.loads((GOOD_DIR / "verify_bundle_standalone.json").read_text(encoding="utf-8"))
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
            (repo / "src" / "auth").mkdir(parents=True)
            (repo / "tests").mkdir(parents=True)
            (repo / "src" / "auth" / "tokens.py").write_text("def verify(t): return bool(t)\n", encoding="utf-8")
            (repo / "tests" / "test_tokens.py").write_text("assert True\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "fix/issue-101-standalone"], cwd=repo, check=True, capture_output=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

            bundle["head_sha"] = head
            bundle["tests"]["head_sha"] = head
            bundle["review"]["head_sha"] = head
            bundle["security"]["head_sha"] = head
            bpath = Path(tmp) / "bundle.json"
            bpath.write_text(json.dumps(bundle), encoding="utf-8")

            ok = run_cli("--bundle", str(bpath), "--repo-root", str(repo))
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

            # Advance HEAD -> stale evidence must now fail!
            (repo / "src" / "auth" / "tokens.py").write_text("def verify(t): return False\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "edit after gate"], cwd=repo, check=True, capture_output=True)
            stale = run_cli("--bundle", str(bpath), "--repo-root", str(repo))
            self.assertEqual(stale.returncode, 1)
            self.assertIn("HEAD", "\n".join(json.loads(stale.stdout)["failures"]))

    def test_malformed_review_findings_document_is_rejected(self):
        bundle = copy.deepcopy(json.loads((GOOD_DIR / "verify_bundle_standalone.json").read_text(encoding="utf-8")))
        bundle["review"]["findings_doc"]["findings"] = [{"id": "bad", "severity": "P0"}]
        with tempfile.TemporaryDirectory() as tmp:
            bpath = Path(tmp) / "bad_findings.json"
            bpath.write_text(json.dumps(bundle), encoding="utf-8")
            proc = run_cli("--bundle", str(bpath))
            self.assertEqual(proc.returncode, 1)
            out = json.loads(proc.stdout)
            self.assertEqual(out["verdict"], "FAIL")

    def test_constants_match_shared_review_findings_contract(self):
        """T6: shared review findings contract stays in sync with skills/review."""
        if not REVIEW_FINDINGS.exists():
            self.skipTest("skills/review/scripts/findings.py not present (standalone install)")
        common = _load(COMMON, "issue_loop_common_contract")
        findings = _load(REVIEW_FINDINGS, "review_findings_contract")
        self.assertEqual(common.FINDINGS_ID_PATTERN, findings.ID_PATTERN)
        self.assertEqual(common.FINDINGS_SEVERITIES, findings.SEVERITIES)
        self.assertEqual(common.FINDINGS_BLOCKING_SEVERITIES, findings.BLOCKING_SEVERITIES)
        self.assertEqual(common.FINDINGS_AXES, findings.AXES)
        self.assertEqual(common.FINDINGS_STATUSES, findings.STATUSES)
        self.assertEqual(common.FINDINGS_CLOSED_STATUSES, findings.CLOSED_STATUSES)
        self.assertEqual(common.FINDINGS_SECURITY_VERDICTS, findings.SECURITY_VERDICTS)
        self.assertEqual(common.FINDINGS_SECURITY_RULE_PATTERN, findings.SECURITY_RULE_PATTERN)


if __name__ == "__main__":
    unittest.main()
