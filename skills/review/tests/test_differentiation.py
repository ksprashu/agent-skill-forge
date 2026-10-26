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
Differentiation Test Suite (Pattern T1) for Review Collector.

In strict compliance with docs/ENGINEERING_STANDARD.md:
- Pattern T1 (Differentiation): Feed two opposite inputs. Assert every output artifact differs.
  Proves that review_collector outputs are genuinely derived from input topology and diff state,
  never emitting hardcoded, static, or input-independent data.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
import review_collector as RC  # noqa: E402

COLLECTOR_SCRIPT = SCRIPTS_DIR / "review_collector.py"


def _setup_git_repo(path: Path) -> None:
    """Initialize a clean git repository for testing diff collection."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Review Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "review-test@example.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


class TestReviewCollectorDifferentiation(unittest.TestCase):
    """Pattern T1: Differentiation tests across repository topology and git diffs."""

    def test_repo_topology_differentiation_t1(self) -> None:
        """
        Pattern T1: Feed two distinct repository setups (Python backend vs TypeScript frontend).
        Assert that every topology, manifest, and tool metric in the output differs.
        """
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            path_py = Path(tmp_a)
            path_ts = Path(tmp_b)

            # --- Target A: Python backend service ---
            (path_py / "pyproject.toml").write_text(
                "[project]\nname = 'py-service'\n[tool.ruff]\nline-length = 88\n[tool.pytest.ini_options]\nminversion = '7.0'\n",
                encoding="utf-8",
            )
            (path_py / "ruff.toml").write_text("select = ['E', 'F']\n", encoding="utf-8")
            (path_py / "pytest.ini").write_text("[pytest]\ntestpaths = ['tests']\n", encoding="utf-8")
            (path_py / "src").mkdir()
            (path_py / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (path_py / "src" / "utils.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
            (path_py / "tests").mkdir()
            (path_py / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

            # --- Target B: TypeScript fullstack frontend ---
            (path_ts / "package.json").write_text(
                json.dumps({"name": "ts-frontend", "scripts": {"test": "vitest"}}),
                encoding="utf-8",
            )
            (path_ts / "tsconfig.json").write_text("{\n  \"compilerOptions\": {\"strict\": true}\n}\n", encoding="utf-8")
            (path_ts / "eslint.config.js").write_text("export default [];\n", encoding="utf-8")
            (path_ts / "vitest.config.ts").write_text("export default {};\n", encoding="utf-8")
            gh_wf = path_ts / ".github" / "workflows"
            gh_wf.mkdir(parents=True)
            (gh_wf / "ci.yml").write_text("name: CI\non: push\njobs: {}\n", encoding="utf-8")
            (path_ts / "src").mkdir()
            for fname in ["index.ts", "server.ts", "client.ts", "models.ts", "auth.ts", "theme.css"]:
                (path_ts / "src" / fname).write_text(f"// {fname}\n", encoding="utf-8")
            (path_ts / "tests").mkdir()
            for fname in ["server.test.ts", "client.test.ts", "auth.test.ts"]:
                (path_ts / "tests" / fname).write_text(f"// test {fname}\n", encoding="utf-8")

            # Collect evidence programmatically
            collector_py = RC.ReviewCollector(target_path=path_py)
            evidence_py = collector_py.collect_all(include_diff=False, include_repo=True)

            collector_ts = RC.ReviewCollector(target_path=path_ts)
            evidence_ts = collector_ts.collect_all(include_diff=False, include_repo=True)

            # T1 Assertions: Every dimension must differ and reflect its specific source
            # 1. Total file count
            files_py = evidence_py["repo"]["topology"]["total_files"]
            files_ts = evidence_ts["repo"]["topology"]["total_files"]
            self.assertNotEqual(files_py, files_ts, "Total file counts must differ between topologies")
            self.assertEqual(files_py, 6)
            self.assertEqual(files_ts, 14)

            # 2. Manifests
            manifests_py = [m["name"] for m in evidence_py["manifests"]]
            manifests_ts = [m["name"] for m in evidence_ts["manifests"]]
            self.assertNotEqual(manifests_py, manifests_ts, "Manifest lists must differ")
            self.assertIn("pyproject.toml", manifests_py)
            self.assertIn("package.json", manifests_ts)

            # 3. Static tools
            tools_py = {t["name"] for t in evidence_py["tools"]}
            tools_ts = {t["name"] for t in evidence_ts["tools"]}
            self.assertNotEqual(tools_py, tools_ts, "Detected static tools must differ")
            self.assertIn("ruff", tools_py)
            self.assertIn("eslint", tools_ts)
            self.assertIn("typescript", tools_ts)

            # 4. Detected linters
            self.assertNotEqual(
                evidence_py["detected_linters"],
                evidence_ts["detected_linters"],
                "Detected linters must differ",
            )
            self.assertIn("ruff", evidence_py["detected_linters"])
            self.assertIn("eslint", evidence_ts["detected_linters"])

            # 5. Detected test runners
            self.assertNotEqual(
                evidence_py["detected_test_runners"],
                evidence_ts["detected_test_runners"],
                "Detected test runners must differ",
            )
            self.assertIn("pytest", evidence_py["detected_test_runners"])
            self.assertIn("vitest", evidence_ts["detected_test_runners"])

            # 6. File extensions
            exts_py = evidence_py["repo"]["topology"]["extensions"]
            exts_ts = evidence_ts["repo"]["topology"]["extensions"]
            self.assertNotEqual(exts_py, exts_ts, "File extensions breakdown must differ")
            self.assertIn(".py", exts_py)
            self.assertNotIn(".py", exts_ts)
            self.assertIn(".ts", exts_ts)
            self.assertNotIn(".ts", exts_py)

    def test_git_diff_differentiation_t1(self) -> None:
        """
        Pattern T1: Feed two distinct git diffs (1-line change vs 600-line change).
        Assert that diff metrics, modified files, and large-diff boolean flags differ.
        """
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            path_small = Path(tmp_a)
            path_large = Path(tmp_b)

            # Setup Git repos
            _setup_git_repo(path_small)
            _setup_git_repo(path_large)

            # Repo Small: initial commit with 1 file
            (path_small / "small.txt").write_text("line1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(path_small), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(path_small), capture_output=True, check=True)

            # Repo Large: initial commit with 5 files
            for i in range(5):
                (path_large / f"large_{i}.txt").write_text(f"initial {i}\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(path_large), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(path_large), capture_output=True, check=True)

            # Now modify repos:
            # Small repo: add 2 lines to 1 file
            (path_small / "small.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")

            # Large repo: add 110 lines to each of 5 files (total 550 lines changed, exceeding 500 threshold)
            for i in range(5):
                content = f"initial {i}\n" + "".join(f"data line {n}\n" for n in range(110))
                (path_large / f"large_{i}.txt").write_text(content, encoding="utf-8")

            # Collect diff facts
            col_small = RC.ReviewCollector(target_path=path_small)
            diff_small = col_small.collect_diff()

            col_large = RC.ReviewCollector(target_path=path_large)
            diff_large = col_large.collect_diff()

            # T1 Assertions:
            # 1. Modified files count differs
            self.assertNotEqual(
                diff_small["files_changed_count"],
                diff_large["files_changed_count"],
                "Files changed count must differ",
            )
            self.assertEqual(diff_small["files_changed_count"], 1)
            self.assertEqual(diff_large["files_changed_count"], 5)

            # 2. Total lines changed differs
            self.assertNotEqual(
                diff_small["total_lines_changed"],
                diff_large["total_lines_changed"],
                "Total lines changed must differ",
            )
            self.assertEqual(diff_small["total_lines_changed"], 2)
            self.assertEqual(diff_large["total_lines_changed"], 550)

            # 3. 500-lines threshold flag differs
            self.assertNotEqual(
                diff_small["diff_exceeds_500_lines"],
                diff_large["diff_exceeds_500_lines"],
                "diff_exceeds_500_lines flag must differ",
            )
            self.assertFalse(diff_small["diff_exceeds_500_lines"])
            self.assertTrue(diff_large["diff_exceeds_500_lines"])

            # 4. is_large_diff convenience alias differs
            self.assertNotEqual(
                diff_small["is_large_diff"],
                diff_large["is_large_diff"],
                "is_large_diff alias must differ",
            )
            self.assertFalse(diff_small["is_large_diff"])
            self.assertTrue(diff_large["is_large_diff"])

            # 5. Modified file lists differ
            self.assertNotEqual(
                diff_small["modified_files"],
                diff_large["modified_files"],
                "Modified files lists must differ",
            )
            self.assertEqual(diff_small["modified_files"], ["small.txt"])
            self.assertEqual(len(diff_large["modified_files"]), 5)

    def test_cli_json_differentiation_t1(self) -> None:
        """
        Pattern T1: Execute review_collector.py CLI on two different project dirs.
        Assert that stdout JSON differs in tool detection, manifests, and topology.
        """
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            path_a = Path(tmp_a)
            path_b = Path(tmp_b)

            # Project A: Rust cargo project
            (path_a / "Cargo.toml").write_text("[package]\nname = 'rust-crate'\nversion = '0.1.0'\n", encoding="utf-8")
            (path_a / "rustfmt.toml").write_text("max_width = 100\n", encoding="utf-8")
            (path_a / "src").mkdir()
            (path_a / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")

            # Project B: Go project
            (path_b / "go.mod").write_text("module example.com/gomod\n\ngo 1.22\n", encoding="utf-8")
            (path_b / ".golangci.yml").write_text("linters:\n  enable:\n    - errcheck\n", encoding="utf-8")
            (path_b / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

            res_a = subprocess.run(
                [sys.executable, str(COLLECTOR_SCRIPT), "--repo", "--path", str(path_a), "--json"],
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
            self.assertEqual(res_a.returncode, 0)
            parsed_a = json.loads(res_a.stdout)

            res_b = subprocess.run(
                [sys.executable, str(COLLECTOR_SCRIPT), "--repo", "--path", str(path_b), "--json"],
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
            self.assertEqual(res_b.returncode, 0)
            parsed_b = json.loads(res_b.stdout)

            # T1 Assertions on CLI JSON output
            self.assertNotEqual(parsed_a["manifests"], parsed_b["manifests"])
            self.assertIn("Cargo.toml", [m["name"] for m in parsed_a["manifests"]])
            self.assertIn("go.mod", [m["name"] for m in parsed_b["manifests"]])

            self.assertNotEqual(parsed_a["tools"], parsed_b["tools"])
            self.assertIn("rustfmt", [t["name"] for t in parsed_a["tools"]])
            self.assertIn("golangci-lint", [t["name"] for t in parsed_b["tools"]])

            self.assertNotEqual(
                parsed_a["repo"]["topology"]["extensions"],
                parsed_b["repo"]["topology"]["extensions"],
            )


if __name__ == "__main__":
    unittest.main()
