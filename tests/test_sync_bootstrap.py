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

"""Tests for project-scoped skill bootstrapping in ``sync_skills.py``.

The bug these were written against: ``--project X --skills work`` printed
``[BOOTSTRAP] work -> X/.gemini/skills/work`` and created nothing, because
writes require ``--fix``. The skill documentation reproduced that output and
called it "successfully bootstrapped". A dry run that announces itself as a
completed install is worse than one that says nothing.

``--copy`` is covered here because it is the documented path on Windows, where
unprivileged symlink creation depends on Developer Mode being enabled.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC = str(REPO_ROOT / "scripts" / "sync_skills.py")

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_skills  # noqa: E402


def run_sync(args, cwd=REPO_ROOT):
    proc = subprocess.run(
        [sys.executable, SYNC, *args], cwd=str(cwd), capture_output=True, text=True
    )
    return proc.returncode, proc.stdout, proc.stderr


class BootstrapCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    @property
    def gemini_work(self) -> Path:
        return self.project / ".gemini" / "skills" / "work"

    @property
    def agents_work(self) -> Path:
        return self.project / ".agents" / "skills" / "work"


class TestDryRunWritesNothing(BootstrapCase):
    def test_no_skill_directory_is_created(self):
        code, out, err = run_sync(["--project", str(self.project), "--skills", "work"])
        self.assertEqual(code, 0, err)
        self.assertFalse(self.gemini_work.exists(), "dry run created the skill entry")
        self.assertFalse(self.agents_work.exists(), "dry run created the skill entry")

    def test_output_does_not_claim_the_install_happened(self):
        _, out, _ = run_sync(["--project", str(self.project), "--skills", "work"])
        self.assertIn("WOULD BOOTSTRAP", out)
        self.assertIn("--fix", out)

    def test_parent_directories_are_created_so_the_path_is_visible(self):
        run_sync(["--project", str(self.project), "--skills", "work"])
        self.assertTrue((self.project / ".gemini" / "skills").is_dir())


class TestFixCreatesTheEntry(BootstrapCase):
    def test_skill_file_is_reachable_after_fix(self):
        code, out, err = run_sync(
            ["--project", str(self.project), "--skills", "work", "--fix"]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue((self.gemini_work / "SKILL.md").is_file())
        self.assertTrue((self.agents_work / "SKILL.md").is_file())

    def test_the_entry_points_at_the_forge_copy(self):
        run_sync(["--project", str(self.project), "--skills", "work", "--fix"])
        self.assertTrue(
            os.path.samefile(self.gemini_work, REPO_ROOT / "skills" / "work")
        )

    def test_rerunning_fix_is_idempotent(self):
        run_sync(["--project", str(self.project), "--skills", "work", "--fix"])
        code, out, err = run_sync(
            ["--project", str(self.project), "--skills", "work", "--fix"]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("ALREADY PRESENT", out)
        self.assertTrue((self.gemini_work / "SKILL.md").is_file())


class TestCopyMode(BootstrapCase):
    """``--copy`` is the Windows-safe path; it must produce real files."""

    def test_copy_mode_produces_a_real_directory_not_a_link(self):
        code, out, err = run_sync(
            ["--project", str(self.project), "--skills", "work", "--fix", "--copy"]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue(self.gemini_work.is_dir())
        self.assertFalse(
            sync_skills.is_link(str(self.gemini_work)), "copy mode created a link"
        )
        self.assertTrue((self.gemini_work / "SKILL.md").is_file())

    def test_copied_skill_survives_deleting_the_link_target_semantics(self):
        run_sync(["--project", str(self.project), "--skills", "work", "--fix", "--copy"])
        # A copy is independent of the forge checkout: reading it must not
        # traverse back into skills/work.
        self.assertFalse(
            os.path.samefile(self.gemini_work, REPO_ROOT / "skills" / "work")
        )

    def test_copy_mode_brings_the_scripts_along(self):
        run_sync(["--project", str(self.project), "--skills", "work", "--fix", "--copy"])
        self.assertTrue((self.gemini_work / "scripts" / "gate_executor.py").is_file())


class TestUnknownAndReservedSkills(BootstrapCase):
    def test_unknown_skill_is_reported_and_creates_nothing(self):
        code, out, err = run_sync(
            ["--project", str(self.project), "--skills", "no-such-skill", "--fix"]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("NOT FOUND LOCALLY", out)
        self.assertFalse((self.project / ".gemini" / "skills" / "no-such-skill").exists())

    def test_reserved_name_is_refused(self):
        code, out, err = run_sync(
            ["--project", str(self.project), "--skills", "browser", "--fix"]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("RESERVED SKIPPED", out)
        self.assertFalse((self.project / ".gemini" / "skills" / "browser").exists())

    def test_a_missing_project_directory_is_an_error(self):
        missing = self.project / "nope" / "deeper"
        code, out, err = run_sync(["--project", str(missing), "--skills", "work", "--fix"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
