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

"""Tests for the machine-specific-path scan in scripts/validate_skills.py.

The 2026-09-18 review found 49 tracked files carrying ``/Users/<name>`` in a
repo whose README advertised "Zero-PII". The finding went unfixed for five
days because nothing failed. These tests are the thing that now fails.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_skills import (  # noqa: E402
    HOST_PATH_EXEMPT,
    HOST_PATH_INLINE_MARKER,
    scan_host_paths,
)


class TestHostPathScan(unittest.TestCase):

    def scan(self, filename, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return scan_host_paths(tmp)

    def test_macos_home_is_rejected(self):
        self.assertTrue(self.scan("a.md", "See /Users/someone/code/x.md\n"))  # host-path-ok

    def test_windows_home_is_rejected(self):
        self.assertTrue(self.scan("a.md", r"See C:\Users\kspra\code\x.md" + "\n"))  # host-path-ok

    def test_windows_forward_slash_home_is_rejected(self):
        self.assertTrue(self.scan("a.md", "See c:/Users/kspra/code/x.md\n"))  # host-path-ok

    def test_linux_home_is_rejected(self):
        self.assertTrue(self.scan("a.md", "See /home/builder/code/x.md\n"))  # host-path-ok

    def test_file_url_home_is_rejected(self):
        self.assertTrue(self.scan("a.md", "[x](file:///Users/someone/code/x.md)\n"))  # host-path-ok

    def test_relative_path_is_accepted(self):
        self.assertEqual([], self.scan("a.md", "See ../catalog/SKILL.md\n"))

    def test_tilde_path_is_accepted(self):
        self.assertEqual([], self.scan("a.md", "See ~/.gemini/skills/x\n"))

    def test_placeholder_user_segment_is_accepted(self):
        """``/Users/<USER_ID>`` is what the redactor emits; it is not a leak."""
        self.assertEqual([], self.scan("a.md", "Scrubbed to /Users/<USER_ID>/code\n"))

    def test_inline_marker_suppresses_a_deliberate_path(self):
        text = f"Bad example: /Users/someone/x.md <!-- {HOST_PATH_INLINE_MARKER} -->\n"  # host-path-ok
        self.assertEqual([], self.scan("a.md", text))

    def test_every_offending_line_is_reported_not_just_the_first(self):
        text = "a /Users/one/x\nb /Users/two/y\nc /Users/three/z\n"  # host-path-ok
        self.assertEqual(3, len(self.scan("a.md", text)))

    def test_the_report_names_the_file_and_line(self):
        errors = self.scan("deep/nested.md", "ok\nok\n/Users/someone/x\n")  # host-path-ok
        self.assertIn("deep/nested.md:3", errors[0])

    def test_binary_and_unscanned_extensions_are_skipped(self):
        self.assertEqual([], self.scan("logo.png", "/Users/someone/x"))  # host-path-ok

    def test_generated_directories_are_skipped(self):
        self.assertEqual([], self.scan("node_modules/pkg/a.md", "/Users/someone/x"))  # host-path-ok
        self.assertEqual([], self.scan(".agents/run.json", '"/Users/someone/x"'))  # host-path-ok


class TestExemptions(unittest.TestCase):

    def test_every_whole_file_exemption_still_exists(self):
        """A stale exemption silently widens the hole it was cut for."""
        for rel in HOST_PATH_EXEMPT:
            self.assertTrue((REPO_ROOT / rel).exists(),
                            f"{rel} is exempt from the host-path scan but no longer "
                            f"exists; remove it from HOST_PATH_EXEMPT.")

    def test_exemption_list_stays_small(self):
        self.assertLessEqual(
            len(HOST_PATH_EXEMPT), 8,
            "Whole-file exemptions are accumulating. Prefer the inline "
            f"`{HOST_PATH_INLINE_MARKER}` marker, which sits next to the line "
            "it excuses.")


class TestRepositoryIsClean(unittest.TestCase):

    def test_the_repository_has_no_machine_specific_paths(self):
        errors = scan_host_paths(str(REPO_ROOT))
        self.assertEqual([], errors, "\n".join(errors[:20]))

    def test_the_validator_exits_zero_on_this_repository(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate_skills.py")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
