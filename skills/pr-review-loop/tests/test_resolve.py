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

"""Tests for resolve.py: it resolves only threads pr-guardian has verified.

Every case reads a canned GraphQL response and uses --dry-run, so nothing here
calls GitHub.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPT = TESTS.parent / "scripts" / "resolve.py"
FIXTURES = TESTS / "fixtures"


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, shell=False, env=env)


def resolve(fixture: str, thread_id: str, *extra: str) -> subprocess.CompletedProcess:
    return run("--from-file", str(FIXTURES / f"{fixture}.json"), "--thread-id", thread_id,
               "--dry-run", *extra)


class TestVerifiedThreads(unittest.TestCase):

    def test_fixed_thread_resolves(self):
        proc = resolve("verified_open", "PRRT_r1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIn("resolveReviewThread", out["query"])
        self.assertEqual(out["variables"], {"threadId": "PRRT_r1"})

    def test_accepted_pushback_thread_resolves(self):
        self.assertEqual(resolve("verified_open", "PRRT_r2").returncode, 0)

    def test_dry_run_does_not_need_gh(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run("--from-file", str(FIXTURES / "verified_open.json"),
                       "--thread-id", "PRRT_r1", "--dry-run", env={**os.environ, "PATH": empty})
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestRefusals(unittest.TestCase):
    """Never resolve before the reviewer verifies, and never resolve what is not addressed."""

    def assert_refused(self, fixture: str, thread_id: str, needle: str):
        proc = resolve(fixture, thread_id)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn(needle, proc.stderr)

    def test_unanswered_fix_is_refused(self):
        self.assert_refused("verified_open", "PRRT_r5", "status=none")

    def test_later_still_open_overrides_earlier_fixed(self):
        self.assert_refused("verified_open", "PRRT_r3", "status=still_open")

    def test_status_for_another_finding_does_not_count(self):
        self.assert_refused("verified_open", "PRRT_r4", "status=none")

    def test_open_finding_without_bot_status_is_refused(self):
        self.assert_refused("open_p1", "PRRT_o1", "wait for the reviewer")

    def test_already_resolved_is_refused(self):
        self.assert_refused("all_resolved", "PRRT_r1", "already resolved")

    def test_unknown_thread_is_refused(self):
        self.assert_refused("verified_open", "PRRT_nope", "not an open pr-guardian finding")


class TestUsage(unittest.TestCase):

    def test_missing_source_is_usage_error(self):
        self.assertEqual(run("--thread-id", "PRRT_r1").returncode, 64)

    def test_bad_repo_is_usage_error(self):
        self.assertEqual(run("--pr", "1", "--repo", "nope", "--thread-id", "PRRT_r1").returncode, 64)

    def test_unreadable_file_exits_2(self):
        self.assertEqual(run("--from-file", "/no/such/file.json", "--thread-id", "x").returncode, 2)


if __name__ == "__main__":
    unittest.main()
