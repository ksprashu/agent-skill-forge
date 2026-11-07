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

"""Tests for reply.py: dry-run output and refusals. Nothing here calls GitHub."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reply.py"


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, shell=False, env=env)


def dry(*args: str) -> dict:
    proc = run("--thread-id", "PRRT_kwDOabc123", "--dry-run", *args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestDryRun(unittest.TestCase):

    def test_wontfix_body(self):
        out = dry("--wontfix", "  false positive: input is an enum, see keys.py:3  ")
        self.assertIn("addPullRequestReviewThreadReply", out["query"])
        self.assertEqual(out["variables"], {
            "threadId": "PRRT_kwDOabc123",
            "body": "/ai-review wontfix: false positive: input is an enum, see keys.py:3"})

    def test_fixed_body(self):
        out = dry("--fixed", "A1B2C3D", "--note", "Added tenant id to the cache key.")
        self.assertEqual(out["variables"]["body"],
                         "Fixed in a1b2c3d. Added tenant id to the cache key.")

    def test_free_body(self):
        self.assertEqual(dry("--body", "Question: which line?")["variables"]["body"],
                         "Question: which line?")

    def test_different_inputs_different_mutations(self):
        self.assertNotEqual(dry("--fixed", "abcdef1"), dry("--wontfix", "reason"))

    def test_dry_run_does_not_need_gh(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run("--thread-id", "PRRT_x123", "--fixed", "abcdef1", "--dry-run",
                       env={**os.environ, "PATH": empty})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_mutation_never_resolves(self):
        self.assertNotIn("resolveReviewThread", dry("--fixed", "abcdef1")["query"])


class TestRefusals(unittest.TestCase):

    def assert_refused(self, *args: str, needle: str = ""):
        proc = run(*args)
        self.assertEqual(proc.returncode, 64, (args, proc.stderr))
        self.assertEqual(proc.stdout, "")
        if needle:
            self.assertIn(needle, proc.stderr)

    def test_empty_wontfix_reason(self):
        self.assert_refused("--thread-id", "PRRT_x123", "--wontfix", "", "--dry-run",
                            needle="reason")
        self.assert_refused("--thread-id", "PRRT_x123", "--wontfix", "   ", "--dry-run",
                            needle="reason")

    def test_empty_wontfix_refused_before_gh(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run("--thread-id", "PRRT_x123", "--wontfix", " ",
                       env={**os.environ, "PATH": empty})
        self.assertEqual(proc.returncode, 64)

    def test_bad_sha(self):
        self.assert_refused("--thread-id", "PRRT_x123", "--fixed", "HEAD", "--dry-run",
                            needle="SHA")

    def test_empty_body(self):
        self.assert_refused("--thread-id", "PRRT_x123", "--body", " ", "--dry-run")

    def test_bad_thread_id(self):
        self.assert_refused("--thread-id", "x; rm -rf /", "--fixed", "abcdef1", "--dry-run")

    def test_missing_or_conflicting_modes(self):
        self.assert_refused("--thread-id", "PRRT_x123", "--dry-run")
        self.assert_refused("--thread-id", "PRRT_x123", "--fixed", "abcdef1",
                            "--wontfix", "r", "--dry-run")
        self.assert_refused("--fixed", "abcdef1", "--dry-run")

    def test_gh_missing_exits_2(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run("--thread-id", "PRRT_x123", "--fixed", "abcdef1",
                       env={**os.environ, "PATH": empty})
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
