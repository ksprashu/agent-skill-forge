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

"""Tests for the stdlib-only checker.

A checker that never fires is indistinguishable from no checker, so most of
these feed it code that should fail and assert that it does.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = str(REPO_ROOT / "scripts" / "check_stdlib_only.py")

sys.path.insert(0, str(REPO_ROOT / "scripts"))

# The checker refuses to import below 3.10 because sys.stdlib_module_names does
# not exist there. Skip the module rather than let a SystemExit during import
# abort discovery for every other test file in this directory. Nothing the
# installer runs has this floor; see the note in check_stdlib_only.py.
if sys.version_info < (3, 10):
    raise unittest.SkipTest(
        f"check_stdlib_only.py needs Python 3.10+; running "
        f"{sys.version_info.major}.{sys.version_info.minor}")

import check_stdlib_only as checker  # noqa: E402


def write(root: Path, relpath: str, source: str) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


class ScanCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def scan(self, roots=("scripts",)):
        return checker.scan(self.root, roots)


class TestViolationsAreCaught(ScanCase):
    def test_a_third_party_import_is_reported(self):
        write(self.root, "scripts/a.py", "import requests\n")
        problems = self.scan()
        self.assertEqual(len(problems), 1)
        self.assertIn("requests", problems[0])

    def test_a_from_import_is_reported(self):
        write(self.root, "scripts/a.py", "from requests import get\n")
        self.assertTrue(any("requests" in p for p in self.scan()))

    def test_a_dotted_import_reports_the_top_package(self):
        write(self.root, "scripts/a.py", "import google.genai\n")
        self.assertTrue(any("'google'" in p for p in self.scan()))

    def test_the_line_number_is_reported(self):
        write(self.root, "scripts/a.py", "import os\nimport sys\nimport numpy\n")
        self.assertIn("a.py:3", self.scan()[0])

    def test_every_violation_is_reported_not_just_the_first(self):
        write(self.root, "scripts/a.py", "import numpy\nimport pandas\n")
        self.assertEqual(len(self.scan()), 2)

    def test_violations_in_nested_directories_are_found(self):
        write(self.root, "scripts/deep/nested/a.py", "import yaml\n")
        self.assertTrue(any("yaml" in p for p in self.scan()))

    def test_a_syntax_error_is_a_violation_not_a_silent_skip(self):
        write(self.root, "scripts/a.py", "def broken(:\n")
        self.assertTrue(any("syntax error" in p for p in self.scan()))

    def test_a_missing_enforced_root_is_a_violation(self):
        problems = checker.scan(self.root, ("scripts", "does-not-exist"))
        self.assertTrue(any("does not exist" in p for p in problems))

    def test_pytest_is_flagged_in_engine_code_with_a_reason(self):
        write(self.root, "scripts/a.py", "import pytest\n")
        problems = self.scan()
        self.assertTrue(any("test-only dependency" in p for p in problems))


class TestCleanCodePasses(ScanCase):
    def test_stdlib_imports_are_accepted(self):
        write(self.root, "scripts/a.py", "import os\nimport json\nfrom pathlib import Path\n")
        self.assertEqual(self.scan(), [])

    def test_a_sibling_module_is_not_a_dependency(self):
        write(self.root, "scripts/helper.py", "X = 1\n")
        write(self.root, "scripts/a.py", "import helper\n")
        self.assertEqual(self.scan(), [])

    def test_a_sibling_package_directory_is_not_a_dependency(self):
        write(self.root, "scripts/engine/__init__.py", "")
        write(self.root, "scripts/a.py", "from engine import thing\n")
        self.assertEqual(self.scan(), [])

    def test_relative_imports_are_not_dependencies(self):
        write(self.root, "scripts/pkg/__init__.py", "")
        write(self.root, "scripts/pkg/a.py", "from . import sibling\n")
        self.assertEqual(self.scan(), [])

    def test_pycache_is_skipped(self):
        write(self.root, "scripts/__pycache__/a.py", "import requests\n")
        self.assertEqual(self.scan(), [])

    def test_fixtures_are_skipped(self):
        write(self.root, "scripts/fixtures/a.py", "import requests\n")
        self.assertEqual(self.scan(), [])


class TestRepositoryIsClean(unittest.TestCase):
    def test_the_enforced_roots_are_clean_today(self):
        problems = checker.scan(REPO_ROOT)
        self.assertEqual(problems, [], f"non-stdlib imports found: {problems}")

    def test_the_cli_exits_zero_on_this_repository(self):
        proc = subprocess.run(
            [sys.executable, CHECKER, "--repo-root", str(REPO_ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_cli_exits_one_where_dependencies_are_declared(self):
        # skills/image-gen genuinely needs Pillow; it is outside the enforced
        # roots. Pointing the checker at it proves the checker still fires.
        proc = subprocess.run(
            [sys.executable, CHECKER, "--repo-root", str(REPO_ROOT),
             "--root", "skills/image-gen/scripts"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("PIL", proc.stderr)

    def test_the_work_engine_is_inside_the_enforced_roots(self):
        self.assertIn("skills/work/scripts", checker.ENFORCED_ROOTS)

    def test_a_bad_repo_root_is_an_invocation_error(self):
        proc = subprocess.run(
            [sys.executable, CHECKER, "--repo-root", "/nonexistent/xyz"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
