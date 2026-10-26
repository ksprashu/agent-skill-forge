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

"""
Negative tests (Pattern T4) and parsing regressions for review_collector.py.

- Failure paths exit non-zero: nonexistent --path, --diff outside git, invalid --base.
- Renames are reported under their new path with an R status (git --numstat -z).
- pyproject.toml tool tables are read with tomllib: sub-tables count, comments do not.
- A hung git call is bounded by a timeout.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
import review_collector as RC  # noqa: E402

COLLECTOR_SCRIPT = SCRIPTS_DIR / "review_collector.py"


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(path), capture_output=True, check=True)


def _repo(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.name", "Review Test")
    _git(path, "config", "user.email", "review-test@example.com")


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(COLLECTOR_SCRIPT), *args],
                          capture_output=True, text=True, shell=False, check=False)


class TestCollectorFailurePaths(unittest.TestCase):
    """Pattern T4: every documented failure exits non-zero with a diagnostic."""

    def test_nonexistent_path_raises_and_cli_exits_1(self) -> None:
        missing = Path(tempfile.gettempdir()) / "review-collector-no-such-dir-1f3c"
        with self.assertRaises(FileNotFoundError):
            RC.ReviewCollector(target_path=missing)
        res = _cli("--repo", "--path", str(missing))
        self.assertEqual(res.returncode, 1)
        self.assertIn("does not exist", res.stderr)

    def test_diff_outside_git_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = _cli("--diff", "--path", tmp)
            self.assertEqual(res.returncode, 1)
            self.assertIn("not inside a git repository", res.stderr)
            with self.assertRaises(RuntimeError):
                RC.ReviewCollector(target_path=tmp).collect_diff()

    def test_invalid_base_ref_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            _repo(path)
            (path / "a.txt").write_text("a\n", encoding="utf-8")
            _git(path, "add", ".")
            _git(path, "commit", "-m", "init")
            res = _cli("--diff", "--path", tmp, "--base", "no-such-ref")
            self.assertEqual(res.returncode, 1)
            self.assertIn("git diff --numstat failed", res.stderr)

    def test_git_timeout_is_bounded(self) -> None:
        """R-012: a hung git call surfaces as 'not a repo', not an indefinite stall."""
        with tempfile.TemporaryDirectory() as tmp:
            collector = RC.ReviewCollector(target_path=tmp)
            hang = subprocess.TimeoutExpired(cmd=["git"], timeout=RC.GIT_TIMEOUT_S)
            with mock.patch.object(RC.subprocess, "run", side_effect=hang) as run:
                self.assertFalse(collector.is_git_repo())
            self.assertEqual(run.call_args.kwargs["timeout"], RC.GIT_TIMEOUT_S)


class TestCollectorParsing(unittest.TestCase):

    def test_rename_reported_under_new_path(self) -> None:
        """R-005: renames are not reported as 'old => new' with status M."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            _repo(path)
            (path / "pkg").mkdir()
            (path / "pkg" / "old.py").write_text("".join(f"x{n} = {n}\n" for n in range(20)),
                                                 encoding="utf-8")
            _git(path, "add", ".")
            _git(path, "commit", "-m", "init")
            _git(path, "mv", "pkg/old.py", "pkg/new.py")
            diff = RC.ReviewCollector(target_path=path).collect_diff(staged_only=True)
            self.assertEqual(diff["modified_files"], ["pkg/new.py"])
            self.assertTrue(diff["file_stats"][0]["status"].startswith("R"),
                            diff["file_stats"][0])

    def test_pyproject_sub_tables_detected_comments_ignored(self) -> None:
        """R-006: [tool.ruff.lint] / [[tool.mypy.overrides]] count; '# [tool.black]' does not."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "pyproject.toml").write_text(
                "[project]\nname = 'x'\n\n"
                "# [tool.black]\n"
                "[tool.ruff.lint]\nselect = ['E']\n\n"
                "[[tool.mypy.overrides]]\nmodule = 'a'\n\n"
                "[tool.pytest.ini_options]\naddopts = '-q'\n",
                encoding="utf-8",
            )
            names = {t["name"] for t in RC.ReviewCollector(target_path=path).collect_static_tools()}
            self.assertTrue({"ruff", "mypy", "pytest"} <= names, names)
            self.assertNotIn("black", names)

    def test_pyproject_fallback_without_tomllib(self) -> None:
        """R-006: the Python < 3.11 header fallback agrees with tomllib on the same file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pyproject.toml"
            path.write_text("# [tool.black]\n[tool.ruff.lint]\n[[tool.mypy.overrides]]\n", encoding="utf-8")
            with mock.patch.object(RC, "tomllib", None):
                self.assertEqual(set(RC._pyproject_tools(path)), {"ruff", "mypy"})

    def test_malformed_pyproject_is_ignored(self) -> None:
        """T4: an unparseable pyproject.toml detects nothing instead of crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "pyproject.toml").write_text("[tool.ruff\nbroken", encoding="utf-8")
            names = {t["name"] for t in RC.ReviewCollector(target_path=path).collect_static_tools()}
            self.assertNotIn("ruff", names)


if __name__ == "__main__":
    unittest.main()
