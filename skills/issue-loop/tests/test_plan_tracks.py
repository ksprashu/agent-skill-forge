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

"""Tests for plan_tracks.py: V1/V2 known_good/known_bad, disjoint tracks, evidence parity."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
GOOD_DIR = FIXTURES / "known_good"
BAD_DIR = FIXTURES / "known_bad"
SCRIPT = TESTS.parent / "scripts" / "plan_tracks.py"
STATE_SCRIPT = TESTS.parent / "scripts" / "issue_state.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        timeout=60,
    )


class TestKnownGoodAndKnownBad(unittest.TestCase):
    """V1 & V2: rejects every known_bad plan and accepts every known_good plan."""

    def test_all_known_good_plans_accepted(self):
        good_files = sorted(GOOD_DIR.glob("plan_*.json"))
        self.assertGreaterEqual(len(good_files), 2)
        for path in good_files:
            with self.subTest(fixture=path.name):
                proc = run_cli("--plan", str(path), "--check-disjoint")
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                out = json.loads(proc.stdout)
                self.assertTrue(out["valid"])
                self.assertEqual(out["collisions"], [])
                self.assertEqual(out["errors"], [])

    def test_all_known_bad_plans_rejected(self):
        expected_needles = {
            "plan_overlapping_tracks.json": "src/shared/utils.py",
            "plan_overlapping_dir_prefix.json": "src/auth",
            "plan_casefold_collision.json": "src/Auth.py",
            "plan_unmapped_fixable_issue.json": "101",
            "plan_partial_without_partial_mark.json": "partial_issues",
            "plan_path_traversal.json": "repo-relative",
        }
        for name, needle in expected_needles.items():
            with self.subTest(fixture=name):
                proc = run_cli("--plan", str(BAD_DIR / name), "--check-disjoint")
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                out = json.loads(proc.stdout)
                self.assertFalse(out["valid"])
                combined = "\n".join(out["errors"] + [json.dumps(out["collisions"])])
                self.assertIn(needle, combined)


class TestDerivedContractsAndEvidenceParity(unittest.TestCase):
    """T1, T3, T4: link modes, evidence coverage, triage sharding, usage errors."""

    def test_issue_link_modes_derived_from_classification_and_partial_issues(self):
        proc = run_cli("--plan", str(GOOD_DIR / "plan_disjoint_swarm.json"), "--check-disjoint")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["issue_link_modes"], {"101": "Fixes", "102": "Refs"})

    def test_from_evidence_detects_dropped_open_issue_and_computes_shards(self):
        state_proc = subprocess.run(
            [sys.executable, str(STATE_SCRIPT), "--from-file", str(FIXTURES / "gh_issues_open.json"), "--repo", "acme/widgets"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
        )
        self.assertEqual(state_proc.returncode, 0, state_proc.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            ev_path.write_text(state_proc.stdout, encoding="utf-8")

            # plan_standalone only accounts for #101, dropping #102 and #103 -> must reject!
            bad_proc = run_cli("--plan", str(GOOD_DIR / "plan_standalone.json"), "--from-evidence", str(ev_path))
            self.assertEqual(bad_proc.returncode, 1)
            bad_out = json.loads(bad_proc.stdout)
            self.assertTrue(any("102" in err for err in bad_out["errors"]))

            # plan_disjoint_swarm accounts for 101, 102, 103 (and 104) -> passes and computes shards!
            ok_proc = run_cli(
                "--plan", str(GOOD_DIR / "plan_disjoint_swarm.json"),
                "--from-evidence", str(ev_path),
                "--max-shard-size", "2",
            )
            self.assertEqual(ok_proc.returncode, 0, ok_proc.stdout + ok_proc.stderr)
            ok_out = json.loads(ok_proc.stdout)
            self.assertEqual(ok_out["triage_shards"], [[101, 102], [103]])

    def test_check_disjoint_flag_governs_standalone_multi_track_plans(self):
        plan = json.loads((BAD_DIR / "plan_overlapping_tracks.json").read_text(encoding="utf-8"))
        plan["mode"] = "standalone"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "standalone_overlap.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(run_cli("--plan", str(path)).returncode, 0)
            proc = run_cli("--plan", str(path), "--check-disjoint")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("src/shared/utils.py", json.dumps(json.loads(proc.stdout)["collisions"]))

    def test_bad_inputs_and_usage_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{bad", encoding="utf-8")
            self.assertEqual(run_cli("--plan", str(bad)).returncode, 2)
        self.assertEqual(run_cli("--plan", str(GOOD_DIR / "plan_standalone.json"), "--max-shard-size", "0").returncode, 64)


if __name__ == "__main__":
    unittest.main()
