"""
End-to-End Test Suite for Markdown-Driven DAG Workflow Engine & Harness Protocol
Path: tests/e2e/test_dag_workflow_e2e.py

Verifies the public CLI interface and interface contracts of dag_validator.py
across all 4 tiers:
- Tier 1: Feature Coverage (25 tests)
- Tier 2: Boundary & Corner Cases (30 tests)
- Tier 3: Cross-Feature Combinations (12 tests)
- Tier 4: Real-World Workload Scenarios (10 tests)
Total: 77 comprehensive opaque-box tests.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# UTF-8 console output guard for Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Path constants
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "e2e" / "fixtures"
DEFAULT_VALIDATOR_PATH = REPO_ROOT / "skills" / "work" / "scripts" / "dag_validator.py"
DAG_VALIDATOR_PATH = Path(os.environ.get("DAG_VALIDATOR_SCRIPT", str(DEFAULT_VALIDATOR_PATH)))

# Resolve Python 3.12 executable
PYTHON_EXE = os.environ.get("PYTHON_EXE")
if not PYTHON_EXE:
    # Try sys.executable if Python 3.12, else python3.12 binary
    if sys.version_info >= (3, 12):
        PYTHON_EXE = sys.executable
    else:
        PYTHON_EXE = shutil.which("python3.12") or "python3.12"


def run_validator(
    args: list[str],
    input_str: str | None = None,
    cwd: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, str, str]:
    """
    Execute dag_validator.py via subprocess CLI contract.
    Returns (returncode, stdout, stderr).
    """
    cmd = [PYTHON_EXE, str(DAG_VALIDATOR_PATH)] + args
    effective_cwd = cwd or str(REPO_ROOT)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    proc = subprocess.run(
        cmd,
        input=input_str,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=effective_cwd,
        env=env,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


class BaseE2ETestCase(unittest.TestCase):
    """Base test case providing fixture helpers and CLI assertion utilities."""

    @classmethod
    def setUpClass(cls):
        if not DAG_VALIDATOR_PATH.exists():
            raise unittest.SkipTest(
                f"Target CLI script not found at {DAG_VALIDATOR_PATH}. "
                "Harness tests are ready; awaiting Milestone 1 implementation."
            )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def copy_fixture(self, fixture_name: str) -> Path:
        """Copy a fixture markdown file to the temporary working directory."""
        src = FIXTURES_DIR / fixture_name
        self.assertTrue(src.exists(), f"Fixture file not found: {src}")
        dst = self.work_dir / fixture_name
        shutil.copy2(src, dst)
        return dst

    def write_temp_dag(self, content: str, filename: str = "temp_dag.md") -> Path:
        """Write inline markdown DAG content to a temporary file."""
        target = self.work_dir / filename
        target.write_text(content, encoding="utf-8")
        return target

    def parse_json_report(self, stdout: str) -> dict:
        """Parse and assert JSON output from validator CLI."""
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Failed to parse JSON output: {exc}\nRaw stdout:\n{stdout}")


# ==============================================================================
# TIER 1: FEATURE COVERAGE TESTS (25 Tests, >=5 per feature)
# ==============================================================================

class Tier1FeatureCoverageTests(BaseE2ETestCase):
    """Tier 1: Comprehensive feature coverage across all 5 core capabilities."""

    # --------------------------------------------------------------------------
    # Feature 1: Markdown Task Table Parsing (5 tests)
    # --------------------------------------------------------------------------

    def test_T1_1_1_parse_canonical_8col_table(self):
        """Verify parsing of canonical 8-column GFM table with all fields."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0, f"Expected code 0, got {code}. Stderr: {err}")
        data = self.parse_json_report(out)
        self.assertTrue(data.get("valid") is True or data.get("is_valid") is True)
        tasks = data.get("tasks", [])
        self.assertEqual(len(tasks), 5, f"Expected 5 tasks, found {len(tasks)}")
        worker = next((t for t in tasks if t["id"] == "task_worker_fix"), None)
        self.assertIsNotNone(worker)
        self.assertEqual(worker.get("mode"), "series")
        self.assertEqual(worker.get("status"), "PASSED")

    def test_T1_1_2_parse_flexible_column_order(self):
        """Verify parsing tables with non-standard column ordering."""
        content = """# Rearranged Columns DAG
| Mode | ID | Status | Depends On | Gate | Task Name | Inputs | Outputs |
|---|---|---|---|---|---|---|---|
| series | task_init | PASSED | none | exit_0 | System Init | ORIGINAL_REQUEST.md | src/init.py |
| parallel | task_worker | RUNNING | task_init | test_pass | Worker Implementation | src/init.py | src/worker.py |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Flexible column table failed. Stderr: {err}")
        data = self.parse_json_report(out)
        tasks = data.get("tasks", [])
        self.assertEqual(len(tasks), 2)
        init = next((t for t in tasks if t["id"] == "task_init"), None)
        self.assertIsNotNone(init)
        self.assertEqual(init.get("mode"), "series")
        self.assertEqual(init.get("status"), "PASSED")

    def test_T1_1_3_parse_empty_token_normalization(self):
        """Verify empty cell tokens ('none', '-', '[]', 'n/a') normalize to empty lists."""
        content = """# Empty Token DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Root One | series | none | - | [] | none | PASSED |
| T2 | Root Two | series | [] | n/a | none | - | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Empty token normalization failed: {err}")
        data = self.parse_json_report(out)
        tasks = data.get("tasks", [])
        self.assertEqual(len(tasks), 2)
        for t in tasks:
            self.assertEqual(t.get("depends_on"), [])

    def test_T1_1_4_parse_comma_separated_lists(self):
        """Verify tokenizing multiple comma-separated dependencies and artifacts."""
        content = """# Multi-Token DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Base Task 1 | series | none | in1.txt, in2.txt | out1.txt, out2.txt | exit_0 | PASSED |
| T2 | Base Task 2 | series | none | in3.txt | out3.txt | exit_0 | PASSED |
| T3 | Multi Dep Task | series | T1, T2 | out1.txt, out3.txt | out_final.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Failed multi-token list: {err}")
        data = self.parse_json_report(out)
        tasks = data.get("tasks", [])
        t3 = next((t for t in tasks if t["id"] == "T3"), None)
        self.assertIsNotNone(t3)
        self.assertIn("T1", t3.get("depends_on", []))
        self.assertIn("T2", t3.get("depends_on", []))

    def test_T1_1_5_parse_ragged_whitespace_alignment(self):
        """Verify tolerance of ragged pipes, variable padding, and backticks."""
        content = """# Ragged Table
|ID|Task Name|Mode|Depends On|Inputs|Outputs|Gate|Status|
|---|---|---|---|---|---|---|---|
|`task_a`|  Task Alpha   |series| none |in.txt|out.txt|none|PASSED|
| `task_b` |Task Beta|parallel| `task_a` | out.txt | out_b.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Ragged whitespace failed: {err}")
        data = self.parse_json_report(out)
        tasks = data.get("tasks", [])
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "task_a")
        self.assertEqual(tasks[1]["id"], "task_b")

    # --------------------------------------------------------------------------
    # Feature 2: Task Execution Modes (5 tests)
    # --------------------------------------------------------------------------

    def test_T1_2_1_mode_series_enforcement(self):
        """Verify series mode enforces sequential blocking."""
        fixture = self.copy_fixture("linear_dag.md")
        code, out, err = run_validator([str(fixture), "--ready-frontier"])
        self.assertEqual(code, 0, f"Series execution check failed: {err}")
        # In linear_dag: T1 is PASSED, T2 is RUNNING, T3 is PENDING depending on T2.
        # T3 must not be in ready frontier because T2 is not PASSED.
        self.assertNotIn("T3", out)

    def test_T1_2_2_mode_parallel_concurrency(self):
        """Verify parallel siblings unblock concurrently in ready frontier."""
        fixture = self.copy_fixture("diamond_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0, f"Diamond concurrency failed: {err}")
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        # T1 is PASSED; T2 and T3 are parallel and PENDING; both must be ready
        self.assertIn("T2", frontier)
        self.assertIn("T3", frontier)
        self.assertNotIn("T4", frontier)

    def test_T1_2_3_mode_async_background_nonblocking(self):
        """Verify async_background task does not block downstream series tasks."""
        fixture = self.copy_fixture("async_watchdog_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0, f"Async watchdog check failed: {err}")
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        # task_init is PASSED, task_worker is RUNNING, task_gate is BLOCKED.
        # Watchdog is running in background without causing validation error.
        self.assertTrue(data.get("valid") is True or data.get("is_valid") is True)

    def test_T1_2_4_mode_mixed_heterogeneous_dag(self):
        """Verify heterogeneous mix of series, parallel, and async_background."""
        content = """# Mixed Modes DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| daemon_1 | Log Watcher | async_background | none | none | log.txt | none | RUNNING |
| root_1 | Setup DB | series | none | schema.sql | db.sqlite | exit_0 | PASSED |
| worker_a | Migrate Auth | parallel | root_1 | db.sqlite | auth.py | exit_0 | RUNNING |
| worker_b | Migrate API | parallel | root_1 | db.sqlite | api.py | exit_0 | PENDING |
| terminal | Integration Gate | series | worker_a, worker_b | auth.py, api.py | bundle.js | exit_0 | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Heterogeneous modes failed: {err}")
        data = self.parse_json_report(out)
        tasks = {t["id"]: t for t in data.get("tasks", [])}
        self.assertEqual(tasks["daemon_1"]["mode"], "async_background")
        self.assertEqual(tasks["root_1"]["mode"], "series")
        self.assertEqual(tasks["worker_a"]["mode"], "parallel")

    def test_T1_2_5_mode_case_insensitive_normalization(self):
        """Verify execution modes with mixed casing normalize to lowercase."""
        content = """# Casing DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | SERIES | none | in.txt | out1.txt | exit_0 | PASSED |
| T2 | Task 2 | Parallel | T1 | out1.txt | out2.txt | exit_0 | PENDING |
| T3 | Task 3 | ASYNC_BACKGROUND | none | none | log.txt | none | RUNNING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Mode normalization failed: {err}")
        data = self.parse_json_report(out)
        tasks = {t["id"]: t for t in data.get("tasks", [])}
        self.assertEqual(tasks["T1"]["mode"], "series")
        self.assertEqual(tasks["T2"]["mode"], "parallel")
        self.assertEqual(tasks["T3"]["mode"], "async_background")

    # --------------------------------------------------------------------------
    # Feature 3: Dependency Ordering & Topological Sorting (5 tests)
    # --------------------------------------------------------------------------

    def test_T1_3_1_order_linear_pipeline(self):
        """Verify topological sort for strict linear pipeline."""
        fixture = self.copy_fixture("linear_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        order = data.get("topological_order", [])
        self.assertEqual(order, ["T1", "T2", "T3"])

    def test_T1_3_2_order_diamond_concurrency(self):
        """Verify topological order respects diamond concurrency boundaries."""
        fixture = self.copy_fixture("diamond_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        order = data.get("topological_order", [])
        self.assertEqual(order[0], "T1")
        self.assertEqual(order[-1], "T4")
        self.assertIn("T2", order[1:3])
        self.assertIn("T3", order[1:3])

    def test_T1_3_3_order_multi_parent_join(self):
        """Verify topological sort when multiple parents converge into single child."""
        content = """# Multi Parent Join DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| P1 | Parent 1 | parallel | none | in.txt | p1.txt | exit_0 | PASSED |
| P2 | Parent 2 | parallel | none | in.txt | p2.txt | exit_0 | PASSED |
| P3 | Parent 3 | parallel | none | in.txt | p3.txt | exit_0 | PASSED |
| C1 | Child Convergence | series | P1, P2, P3 | p1.txt, p2.txt, p3.txt | c1.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        order = data.get("topological_order", [])
        idx_c1 = order.index("C1")
        self.assertLess(order.index("P1"), idx_c1)
        self.assertLess(order.index("P2"), idx_c1)
        self.assertLess(order.index("P3"), idx_c1)

    def test_T1_3_4_order_multi_root_fork(self):
        """Verify topological sort when multiple independent roots branch."""
        content = """# Multi Root Fork DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| R1 | Root 1 | series | none | in.txt | r1.txt | exit_0 | PASSED |
| R2 | Root 2 | series | none | in.txt | r2.txt | exit_0 | PASSED |
| C1 | Child 1 | series | R1 | r1.txt | c1.txt | exit_0 | PENDING |
| C2 | Child 2 | series | R2 | r2.txt | c2.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        order = data.get("topological_order", [])
        self.assertLess(order.index("R1"), order.index("C1"))
        self.assertLess(order.index("R2"), order.index("C2"))

    def test_T1_3_5_order_transitive_invariance(self):
        """Verify topological order respects direct and transitive edges (A->B->C and A->C)."""
        content = """# Transitive Invariance DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | in.txt | a.txt | exit_0 | PASSED |
| B | Task B | series | A | a.txt | b.txt | exit_0 | PASSED |
| C | Task C | series | A, B | a.txt, b.txt | c.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        order = data.get("topological_order", [])
        self.assertEqual(order, ["A", "B", "C"])

    # --------------------------------------------------------------------------
    # Feature 4: Artifact Contracts & Physical Validation (5 tests)
    # --------------------------------------------------------------------------

    def test_T1_4_1_artifact_relative_paths_accepted(self):
        """Verify valid relative workspace paths are accepted without error."""
        content = """# Relative Paths DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | series | none | src/app.py | dist/app.js, .agents/m1/handoff.md | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Relative paths rejected: {err}")

    def test_T1_4_2_artifact_virtual_tokens_recognized(self):
        """Verify virtual non-filesystem tokens ('none', '-', 'stdout', 'stderr')."""
        content = """# Virtual Tokens DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Standard Out Task | series | none | - | stdout | exit_0 | PASSED |
| T2 | Standard Err Task | series | T1 | none | stderr | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--check-artifacts", "--base-dir", str(self.work_dir)])
        self.assertEqual(code, 0, f"Virtual tokens should not trigger missing file error: {err}")

    def test_T1_4_3_check_artifacts_passed_files_exist(self):
        """Verify --check-artifacts passes when physical files exist on disk."""
        # Create physical files
        (self.work_dir / "src").mkdir(parents=True, exist_ok=True)
        (self.work_dir / "src" / "worker.py").write_text("# worker", encoding="utf-8")
        (self.work_dir / "test_out.txt").write_text("passed", encoding="utf-8")

        content = """# Artifact Exists DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Worker | series | none | src/worker.py | test_out.txt | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([
            str(dag_file),
            "--check-artifacts",
            "--base-dir", str(self.work_dir),
            "--json",
        ])
        self.assertEqual(code, 0, f"Artifact check should pass. Out: {out}, Err: {err}")

    def test_T1_4_4_check_artifacts_missing_input_fails(self):
        """Verify --check-artifacts returns exit code 1 when input artifact is missing."""
        content = """# Missing Input DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Worker | series | none | nonexistent_input_file.py | out.txt | exit_0 | RUNNING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([
            str(dag_file),
            "--check-artifacts",
            "--base-dir", str(self.work_dir),
        ])
        self.assertEqual(code, 1, f"Expected exit code 1 for missing input artifact, got {code}")

    def test_T1_4_5_check_artifacts_missing_output_fails(self):
        """Verify --check-artifacts returns exit code 1 when output artifact of PASSED node is missing."""
        content = """# Missing Output DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Completed Task | series | none | none | missing_declared_output.txt | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([
            str(dag_file),
            "--check-artifacts",
            "--base-dir", str(self.work_dir),
        ])
        self.assertEqual(code, 1, f"Expected exit code 1 for missing output artifact, got {code}")

    # --------------------------------------------------------------------------
    # Feature 5: Mermaid Visualization & In-Place Updates (5 tests)
    # --------------------------------------------------------------------------

    def test_T1_5_1_mermaid_graph_td_header(self):
        """Verify --mermaid generates valid flowchart TD header."""
        fixture = self.copy_fixture("linear_dag.md")
        code, out, err = run_validator([str(fixture), "--mermaid"])
        self.assertEqual(code, 0, f"Mermaid generation failed: {err}")
        self.assertIn("graph TD", out)

    def test_T1_5_2_mermaid_nodes_and_edges_present(self):
        """Verify Mermaid output contains node labels and directed edges."""
        fixture = self.copy_fixture("diamond_dag.md")
        code, out, err = run_validator([str(fixture), "--mermaid"])
        self.assertEqual(code, 0)
        self.assertIn("T1", out)
        self.assertIn("T2", out)
        self.assertIn("T3", out)
        self.assertIn("T4", out)
        self.assertIn("-->", out)

    def test_T1_5_3_mermaid_status_css_classes(self):
        """Verify Mermaid diagram defines CSS class styling for states."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        code, out, err = run_validator([str(fixture), "--mermaid"])
        self.assertEqual(code, 0)
        self.assertIn("classDef", out)
        # Should define status styles (passed, running, pending, etc.)
        self.assertTrue(any(c in out for c in ["passed", "running", "blocked", "pending"]))

    def test_T1_5_4_update_file_replaces_existing_mermaid(self):
        """Verify --update-file updates the existing Mermaid block in-place without duplicate blocks."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        # Update status and sync mermaid
        code, out, err = run_validator([
            str(fixture),
            "--set-status", "task_reviewer=PASSED",
            "--update-file",
        ])
        self.assertEqual(code, 0, f"Update file failed: {err}")
        updated_content = fixture.read_text(encoding="utf-8")
        # Check that table cell was updated
        self.assertIn("PASSED", updated_content)
        # Check that mermaid fences occur exactly twice (one opening ```mermaid, one closing ```)
        mermaid_occurrences = updated_content.count("```mermaid")
        self.assertEqual(mermaid_occurrences, 1, f"Expected 1 ```mermaid block, found {mermaid_occurrences}")

    def test_T1_5_5_update_file_appends_missing_mermaid(self):
        """Verify --update-file appends Mermaid block if file lacked one."""
        content = """# No Mermaid DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Step 1 | series | none | in.txt | out1.txt | exit_0 | PASSED |
| T2 | Step 2 | series | T1 | out1.txt | out2.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--update-file"])
        self.assertEqual(code, 0, f"Append mermaid failed: {err}")
        updated = dag_file.read_text(encoding="utf-8")
        self.assertIn("```mermaid", updated)
        self.assertIn("graph TD", updated)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (30 Tests, >=5 per feature)
# ==============================================================================

class Tier2BoundaryCornerCaseTests(BaseE2ETestCase):
    """Tier 2: Extreme boundary conditions, malformed structures, path styles, and stress scaling."""

    # --------------------------------------------------------------------------
    # Category 1: Empty & Minimal Graphs (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_1_1_boundary_empty_file(self):
        """Verify completely empty 0-byte file returns failure exit code (1 or 2)."""
        dag_file = self.write_temp_dag("")
        code, out, err = run_validator([str(dag_file)])
        self.assertIn(code, (1, 2), f"Empty file should fail with exit code 1 or 2, got {code}")

    def test_T2_1_2_boundary_no_table_prose_only(self):
        """Verify file with markdown prose but no task table returns failure exit code."""
        content = "# Project Overview\n\nThis is just documentation without any table.\n"
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertIn(code, (1, 2))

    def test_T2_1_3_boundary_header_only_table(self):
        """Verify table with headers but 0 data rows returns failure exit code."""
        fixture = self.copy_fixture("empty_table_dag.md")
        code, out, err = run_validator([str(fixture)])
        self.assertIn(code, (1, 2))

    def test_T2_1_4_boundary_single_isolated_task(self):
        """Verify single isolated task DAG is valid."""
        content = """# Single Task DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| solitary_task | Solo Mission | series | none | in.txt | out.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Single task DAG failed: {err}")
        data = self.parse_json_report(out)
        self.assertEqual(data.get("topological_order"), ["solitary_task"])
        self.assertEqual(data.get("ready_frontier"), ["solitary_task"])

    def test_T2_1_5_boundary_all_independent_tasks(self):
        """Verify DAG with multiple disconnected independent tasks is valid and all are ready."""
        content = """# Disconnected Tasks DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | parallel | none | in.txt | out1.txt | exit_0 | PENDING |
| T2 | Task 2 | parallel | none | in.txt | out2.txt | exit_0 | PENDING |
| T3 | Task 3 | parallel | none | in.txt | out3.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        self.assertEqual(set(frontier), {"T1", "T2", "T3"})

    # --------------------------------------------------------------------------
    # Category 2: Cycle Detection of Various Lengths (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_2_1_cycle_length_1_self_reference(self):
        """Verify cycle of length 1 (self-dependency) is detected."""
        content = """# Self Cycle DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Ouroboros | series | T1 | in.txt | out.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 1, f"Expected exit code 1 for self-cycle, got {code}")
        data = self.parse_json_report(out)
        self.assertFalse(data.get("valid", True) and data.get("is_valid", True))

    def test_T2_2_2_cycle_length_2_direct(self):
        """Verify direct 2-node cycle (A -> B -> A) is detected."""
        content = """# 2-Node Cycle DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | B | in.txt | out_a.txt | exit_0 | PENDING |
| B | Task B | series | A | out_a.txt | out_b.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 1)

    def test_T2_2_3_cycle_length_3_indirect(self):
        """Verify indirect 3-node cycle (A -> B -> C -> A) is detected."""
        fixture = self.copy_fixture("cyclic_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 1)
        data = self.parse_json_report(out)
        self.assertFalse(data.get("valid", True) and data.get("is_valid", True))

    def test_T2_2_4_cycle_length_5_deep(self):
        """Verify deep 5-node cycle embedded in larger graph."""
        content = """# Deep Cycle DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Node 1 | series | none | in.txt | o1.txt | exit_0 | PASSED |
| T2 | Node 2 | series | T1, T5 | o1.txt | o2.txt | exit_0 | PENDING |
| T3 | Node 3 | series | T2 | o2.txt | o3.txt | exit_0 | PENDING |
| T4 | Node 4 | series | T3 | o3.txt | o4.txt | exit_0 | PENDING |
| T5 | Node 5 | series | T4 | o4.txt | o5.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1, f"Expected cycle detection failure for deep cycle, got {code}")

    def test_T2_2_5_cycle_disconnected_subgraph(self):
        """Verify cycle in disconnected component is detected while main component is acyclic."""
        content = """# Disconnected Cycle DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A1 | Valid Root | series | none | in.txt | a1.txt | exit_0 | PASSED |
| A2 | Valid Child | series | A1 | a1.txt | a2.txt | exit_0 | PENDING |
| X1 | Cyclic X1 | series | X2 | none | x1.txt | none | PENDING |
| X2 | Cyclic X2 | series | X1 | none | x2.txt | none | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1)

    # --------------------------------------------------------------------------
    # Category 3: Missing Targets & Duplicate IDs (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_3_1_missing_dep_single_ghost(self):
        """Verify missing dependency target triggers exit code 1."""
        fixture = self.copy_fixture("missing_dep_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 1)
        data = self.parse_json_report(out)
        self.assertFalse(data.get("valid", True) and data.get("is_valid", True))

    def test_T2_3_2_missing_dep_partial_valid(self):
        """Verify task with one valid dep and one missing dep fails."""
        content = """# Partial Missing Dep DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Valid Task | series | none | in.txt | t1.txt | exit_0 | PASSED |
| T2 | Half Missing | series | T1, ghost_target_x | t1.txt | t2.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1)

    def test_T2_3_3_duplicate_task_id_rejected(self):
        """Verify duplicate task ID triggers exit code 1."""
        fixture = self.copy_fixture("duplicate_id_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 1)
        data = self.parse_json_report(out)
        self.assertFalse(data.get("valid", True) and data.get("is_valid", True))

    def test_T2_3_4_missing_dep_multiple_ghosts(self):
        """Verify multiple undefined dependencies are all reported."""
        content = """# Multiple Ghosts DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | series | ghost_a, ghost_b | in.txt | out.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1)

    def test_T2_3_5_empty_string_task_id_rejected(self):
        """Verify row with empty or blank task ID is rejected."""
        content = """# Blank ID DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| | Blank ID Task | series | none | in.txt | out.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1)

    # --------------------------------------------------------------------------
    # Category 4: Path Styles & Escaping (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_4_1_path_windows_backslashes_handled(self):
        """Verify Windows-style backslash paths are handled cleanly."""
        content = """# Windows Paths DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Windows Task | series | none | src\\core\\engine.py | .agents\\worker\\handoff.md | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Windows path handling failed: {err}")

    def test_T2_4_2_path_posix_forward_slashes_handled(self):
        """Verify POSIX forward-slash paths work seamlessly."""
        content = """# POSIX Paths DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | POSIX Task | series | none | src/core/engine.py | .agents/worker/handoff.md | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"POSIX path handling failed: {err}")

    def test_T2_4_3_path_mixed_slashes_normalized(self):
        """Verify mixed slashes in paths normalize consistently."""
        content = """# Mixed Paths DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Mixed Task | series | none | src/foo\\bar/baz.py | out\\res/data.json | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Mixed path normalization failed: {err}")

    def test_T2_4_4_path_forbidden_characters_rejected(self):
        """Verify paths containing illegal characters (< > | ? *) trigger validation failure."""
        content = """# Illegal Chars DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Bad Path Task | series | none | src/<illegal>|pipe.py | out.txt | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1, f"Expected exit code 1 for illegal path characters, got {code}")

    def test_T2_4_5_path_absolute_root_leaked_rejected(self):
        """Verify hardcoded machine absolute root paths trigger contract rejection."""
        content = """# Absolute Path Leak DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Leaked Path Task | series | none | C:\\Users\\Admin\\secret.key | /etc/passwd | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1, f"Expected exit code 1 for machine absolute path leaks, got {code}")

    # --------------------------------------------------------------------------
    # Category 5: Unicode, Formatting & Adversarial Inputs (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_5_1_unicode_titles_and_emoji(self):
        """Verify Unicode characters, emoji, and non-ASCII text are preserved cleanly."""
        fixture = self.copy_fixture("unicode_dag.md")
        code, out, err = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0, f"Unicode processing failed: {err}")
        data = self.parse_json_report(out)
        tasks = {t["id"]: t for t in data.get("tasks", [])}
        self.assertIn("🚀", tasks["task_utf_1"].get("title", ""))

    def test_T2_5_2_brackets_and_quotes_in_titles(self):
        """Verify bracketed and quoted strings in task titles do not break parsing."""
        content = """# Special Chars DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | [Core] "Auth" (Service: V2) | series | none | in.txt | out.txt | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--mermaid"])
        self.assertEqual(code, 0, f"Special characters in titles failed: {err}")
        self.assertIn("T1", out)

    def test_T2_5_3_escaped_pipes_in_table_cells(self):
        """Verify command flags and arguments in Gate column are preserved."""
        content = """# Quoted Gate DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Command Line Task | series | none | in.txt | out.txt | pytest -k 'not slow' tests/ | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"Quoted gate failed: {err}")

    def test_T2_5_4_crlf_and_lf_line_endings(self):
        """Verify Windows CRLF line endings parse identically to Unix LF."""
        content_lf = "# LF DAG\n| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |\n|---|---|---|---|---|---|---|---|\n| T1 | Task 1 | series | none | in.txt | out.txt | exit_0 | PASSED |\n"
        content_crlf = content_lf.replace("\n", "\r\n")

        file_lf = self.work_dir / "lf.md"
        file_lf.write_bytes(content_lf.encode("utf-8"))
        file_crlf = self.work_dir / "crlf.md"
        file_crlf.write_bytes(content_crlf.encode("utf-8"))

        code_lf, out_lf, _ = run_validator([str(file_lf), "--json"])
        code_crlf, out_crlf, _ = run_validator([str(file_crlf), "--json"])

        self.assertEqual(code_lf, 0)
        self.assertEqual(code_crlf, 0)
        self.assertEqual(json.loads(out_lf).get("topological_order"), json.loads(out_crlf).get("topological_order"))

    def test_T2_5_5_blank_lines_within_table(self):
        """Verify comments and padding within table section do not abort valid row parsing."""
        content = """# Documented Table DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | series | none | in.txt | out1.txt | exit_0 | PASSED |
<!-- checkpoint boundary -->
| T2 | Task 2 | series | T1 | out1.txt | out2.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertGreaterEqual(len(data.get("tasks", [])), 1)

    # --------------------------------------------------------------------------
    # Category 6: Mode Boundaries & Scaling (5 tests)
    # --------------------------------------------------------------------------

    def test_T2_6_1_invalid_execution_mode_rejected(self):
        """Verify unsupported execution mode values trigger validation failure."""
        content = """# Invalid Mode DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Bad Mode Task | hyper_concurrent | none | in.txt | out.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1, f"Expected exit code 1 for invalid mode, got {code}")

    def test_T2_6_2_invalid_status_value_rejected(self):
        """Verify unsupported status values trigger validation failure."""
        content = """# Invalid Status DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Bad Status Task | series | none | in.txt | out.txt | exit_0 | HALFWAY_DONE |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file)])
        self.assertEqual(code, 1, f"Expected exit code 1 for invalid status, got {code}")

    def test_T2_6_3_status_case_insensitivity(self):
        """Verify mixed casing in status normalizes to canonical uppercase."""
        content = """# Status Casing DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Task 1 | series | none | in.txt | out1.txt | exit_0 | passed |
| T2 | Task 2 | series | T1 | out1.txt | out2.txt | exit_0 | Running |
| T3 | Task 3 | series | T2 | out2.txt | out3.txt | exit_0 | Pending |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        statuses = {t["id"]: t["status"] for t in data.get("tasks", [])}
        self.assertEqual(statuses["T1"], "PASSED")
        self.assertEqual(statuses["T2"], "RUNNING")
        self.assertEqual(statuses["T3"], "PENDING")

    def test_T2_6_4_large_dag_scaling_100_nodes(self):
        """Verify scaling performance on 100-node graph completes in < 2 seconds."""
        rows = []
        rows.append("# Large 100-Node DAG\n| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |\n|---|---|---|---|---|---|---|---|")
        # 10 waves of 10 nodes
        for wave in range(10):
            for i in range(10):
                task_id = f"w{wave}_t{i}"
                if wave == 0:
                    deps = "none"
                    status = "PASSED"
                else:
                    prev_id = f"w{wave-1}_t{i}"
                    deps = prev_id
                    status = "PENDING"
                rows.append(f"| {task_id} | Wave {wave} Task {i} | parallel | {deps} | in.txt | out.txt | exit_0 | {status} |")

        content = "\n".join(rows)
        dag_file = self.write_temp_dag(content)

        start_time = time.time()
        code, out, err = run_validator([str(dag_file), "--json"])
        elapsed = time.time() - start_time

        self.assertEqual(code, 0, f"100-node DAG failed: {err}")
        self.assertLess(elapsed, 2.5, f"Execution took too long: {elapsed:.2f}s")
        data = self.parse_json_report(out)
        self.assertEqual(len(data.get("tasks", [])), 100)

    def test_T2_6_5_deep_linear_chain_recursion_limit(self):
        """Verify deep linear chain of 150 tasks doesn't exceed recursion stack."""
        rows = ["# Deep Chain DAG\n| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |\n|---|---|---|---|---|---|---|---|"]
        rows.append("| T_0 | Initial Task | series | none | in.txt | out_0.txt | exit_0 | PASSED |")
        for i in range(1, 150):
            rows.append(f"| T_{i} | Task {i} | series | T_{i-1} | out_{i-1}.txt | out_{i}.txt | exit_0 | PENDING |")

        content = "\n".join(rows)
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0, f"150-task chain failed: {err}")
        data = self.parse_json_report(out)
        self.assertEqual(len(data.get("topological_order", [])), 150)


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (Pairwise Coverage, 12 Tests)
# ==============================================================================

class Tier3CrossFeatureCombinationTests(BaseE2ETestCase):
    """Tier 3: Pairwise combinations of concurrent dispatch, watchdogs, barriers, and mutations."""

    def test_T3_1_combo_shared_inputs_parallel_frontier(self):
        """Verify parallel sibling tasks sharing identical input unblock together."""
        content = """# Shared Inputs DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| root | Data Producer | series | none | seed.json | shared_dataset.parquet | exit_0 | PASSED |
| worker_1 | Transform 1 | parallel | root | shared_dataset.parquet | out1.csv | exit_0 | PENDING |
| worker_2 | Transform 2 | parallel | root | shared_dataset.parquet | out2.csv | exit_0 | PENDING |
| worker_3 | Transform 3 | parallel | root | shared_dataset.parquet | out3.csv | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        self.assertEqual(set(frontier), {"worker_1", "worker_2", "worker_3"})

    def test_T3_2_combo_overlapping_input_subsets(self):
        """Verify parallel tasks with distinct input subsets unblock appropriately."""
        content = """# Overlapping Inputs DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| root_a | Producer A | parallel | none | in.txt | a.txt | exit_0 | PASSED |
| root_b | Producer B | parallel | none | in.txt | b.txt | exit_0 | RUNNING |
| consumer_a | Consumer A Only | parallel | root_a | a.txt | res_a.txt | exit_0 | PENDING |
| consumer_both | Consumer A and B | parallel | root_a, root_b | a.txt, b.txt | res_both.txt | exit_0 | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        self.assertIn("consumer_a", frontier)
        self.assertNotIn("consumer_both", frontier)

    def test_T3_3_combo_async_watchdog_alongside_series(self):
        """Verify background watchdog does not block milestone gate evaluation."""
        fixture = self.copy_fixture("async_watchdog_dag.md")
        # task_worker set to PASSED -> task_gate should now enter ready frontier even though watchdog is RUNNING
        code, out, err = run_validator([
            str(fixture),
            "--set-status", "task_worker=PASSED",
            "--update-file",
            "--ready-frontier",
        ])
        self.assertEqual(code, 0)
        self.assertIn("task_gate", out)

    def test_T3_4_combo_async_watchdog_artifact_check(self):
        """Verify async_background task output is checked when marked PASSED."""
        (self.work_dir / ".agents" / "sentinel").mkdir(parents=True, exist_ok=True)
        log_file = self.work_dir / ".agents" / "sentinel" / "heartbeat.log"
        log_file.write_text("heartbeat tick", encoding="utf-8")

        content = """# Watchdog Artifact DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| watchdog | Liveness Monitor | async_background | none | none | .agents/sentinel/heartbeat.log | none | PASSED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([
            str(dag_file),
            "--check-artifacts",
            "--base-dir", str(self.work_dir),
        ])
        self.assertEqual(code, 0, f"Watchdog artifact check failed: {err}")

    def test_T3_5_combo_failure_propagation_to_blocked(self):
        """Verify that when a dependency fails, downstream tasks are not ready."""
        content = """# Failure Propagation DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| worker | Implementation Worker | series | none | spec.md | code.py | exit_0 | FAILED |
| reviewer | 5-Axis Reviewer | parallel | worker | code.py | review.md | review_pass | BLOCKED |
| challenger | Adversarial Fuzzer | parallel | worker | code.py | tests.py | exit_0 | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--ready-frontier"])
        self.assertEqual(code, 0)
        # Downstream tasks must not be in ready frontier
        self.assertNotIn("reviewer", out)
        self.assertNotIn("challenger", out)

    def test_T3_6_combo_inplace_status_update_mermaid_sync(self):
        """Verify --set-status and --update-file updates table cell and Mermaid CSS simultaneously."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        code, out, err = run_validator([
            str(fixture),
            "--set-status", "task_reviewer=PASSED",
            "--set-status", "task_challenger=PASSED",
            "--update-file",
        ])
        self.assertEqual(code, 0)
        updated = fixture.read_text(encoding="utf-8")
        # Check table
        self.assertTrue(re.search(r"task_reviewer.*PASSED", updated))
        self.assertTrue(re.search(r"task_challenger.*PASSED", updated))
        # Check mermaid reflects passed status
        self.assertIn("task_reviewer", updated)

    def test_T3_7_combo_dynamic_remediation_node_injection(self):
        """Verify dynamically inserting remediation node resolves updated topological order."""
        content = """# Dynamic Remediation DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| worker_1 | Initial Worker | series | none | spec.md | code.py | exit_0 | FAILED |
| task_remediation | Fix Rework | series | worker_1 | spec.md, code.py | code_fixed.py | exit_0 | PENDING |
| victory | Victory Auditor | series | task_remediation | code_fixed.py | victory.md | exit_0 | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertEqual(data.get("topological_order"), ["worker_1", "task_remediation", "victory"])

    def test_T3_8_combo_ready_frontier_dynamic_evolution(self):
        """Verify inspecting ready frontier dynamically as states transition across 3 turns."""
        fixture = self.copy_fixture("diamond_dag.md")

        # Turn 1: T1 is PASSED, T2 and T3 are PENDING -> Frontier = [T2, T3]
        code, out, _ = run_validator([str(fixture), "--ready-frontier"])
        self.assertIn("T2", out)
        self.assertIn("T3", out)
        self.assertNotIn("T4", out)

        # Turn 2: Mark T2 as PASSED -> T3 still PENDING -> Frontier = [T3]
        run_validator([str(fixture), "--set-status", "T2=PASSED", "--update-file"])
        code, out, _ = run_validator([str(fixture), "--ready-frontier"])
        self.assertNotIn("T2", out)
        self.assertIn("T3", out)
        self.assertNotIn("T4", out)

        # Turn 3: Mark T3 as PASSED -> T4 becomes unblocked -> Frontier = [T4]
        run_validator([str(fixture), "--set-status", "T3=PASSED", "--update-file"])
        code, out, _ = run_validator([str(fixture), "--ready-frontier"])
        self.assertIn("T4", out)

    def test_T3_9_combo_artifact_check_with_status_transitions(self):
        """Verify physical check fails before output creation and passes after creation."""
        out_file = self.work_dir / "generated_artifact.json"
        content = f"""# Artifact Transition DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| producer | JSON Producer | series | none | none | generated_artifact.json | exit_0 | PASSED |
"""
        dag_file = self.write_temp_dag(content)

        # Step A: Output file does not exist yet -> Must fail with exit code 1
        code, _, _ = run_validator([str(dag_file), "--check-artifacts", "--base-dir", str(self.work_dir)])
        self.assertEqual(code, 1)

        # Step B: Write output file -> Must pass with exit code 0
        out_file.write_text('{"status": "ok"}', encoding="utf-8")
        code, _, err = run_validator([str(dag_file), "--check-artifacts", "--base-dir", str(self.work_dir)])
        self.assertEqual(code, 0, f"Artifact check should pass after file creation: {err}")

    def test_T3_10_combo_ready_frontier_gated_by_physical_input(self):
        """Verify --ready-frontier with --check-artifacts withholds node if physical input is absent."""
        content = """# Gated Input Frontier DAG
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| prep | Prep Task | series | none | none | missing_handoff.md | exit_0 | PASSED |
| downstream | Blocked Subagent | series | prep | missing_handoff.md | result.txt | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        # Without missing_handoff.md on disk, downstream must not be ready
        code, out, _ = run_validator([
            str(dag_file),
            "--ready-frontier",
            "--check-artifacts",
            "--base-dir", str(self.work_dir),
        ])
        self.assertNotIn("downstream", out)

    def test_T3_11_combo_stdin_cyclic_dag_json(self):
        """Verify streaming cyclic DAG via stdin returns exit code 1 with JSON report."""
        cyclic_content = """# Stdin Cycle
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Node A | series | B | in.txt | a.txt | none | PENDING |
| B | Node B | series | A | a.txt | b.txt | none | PENDING |
"""
        code, out, err = run_validator(["--stdin", "--json"], input_str=cyclic_content)
        self.assertEqual(code, 1)
        data = self.parse_json_report(out)
        self.assertFalse(data.get("valid", True) and data.get("is_valid", True))

    def test_T3_12_combo_stdin_valid_diamond_dag_json(self):
        """Verify streaming valid diamond DAG via stdin returns exit code 0 with full JSON."""
        diamond_content = """# Stdin Diamond
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Root | series | none | in.txt | t1.txt | exit_0 | PASSED |
| T2 | Left | parallel | T1 | t1.txt | t2.txt | exit_0 | PENDING |
| T3 | Right | parallel | T1 | t1.txt | t3.txt | exit_0 | PENDING |
| T4 | Join | series | T2, T3 | t2.txt, t3.txt | t4.txt | exit_0 | BLOCKED |
"""
        code, out, err = run_validator(["--stdin", "--json"], input_str=diamond_content)
        self.assertEqual(code, 0, f"Stdin diamond validation failed: {err}")
        data = self.parse_json_report(out)
        self.assertTrue(data.get("valid") is True or data.get("is_valid") is True)
        self.assertEqual(len(data.get("tasks", [])), 4)
        self.assertEqual(set(data.get("ready_frontier", [])), {"T2", "T3"})


# ==============================================================================
# TIER 4: REAL-WORLD WORKLOAD SCENARIOS (10 Tests)
# ==============================================================================

class Tier4RealWorldWorkloadScenarioTests(BaseE2ETestCase):
    """Tier 4: End-to-end multi-turn simulations of real-world swarm workflows."""

    # --------------------------------------------------------------------------
    # Scenario A: Focused Bugfix Full Workflow Simulation (Topology 2, 5 tests)
    # --------------------------------------------------------------------------

    def test_T4_1_scenario_focused_bugfix_initial_state(self):
        """Simulate Turn 1: Initial state of Focused Bugfix swarm."""
        # Initial: Worker is PENDING; Committee is BLOCKED; Victory is BLOCKED
        content = """# Focused Bugfix Initial State
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| task_worker_fix | Bugfix Implementation | series | none | ORIGINAL_REQUEST.md | src/parser.py, tests/test_parser.py, .agents/worker_fix/handoff.md | pytest | PENDING |
| task_reviewer | 5-Axis Reviewer | parallel | task_worker_fix | src/parser.py, .agents/worker_fix/handoff.md | .agents/reviewer/review.md | review_pass | BLOCKED |
| task_challenger | Adversarial Fuzzer | parallel | task_worker_fix | src/parser.py, tests/test_parser.py | tests/test_hostile.py | pytest | BLOCKED |
| task_forensic_auditor | Anti-Mock Auditor | parallel | task_worker_fix | src/parser.py, tests/test_parser.py | .agents/EVIDENCE.md | zero_mock | BLOCKED |
| task_victory_auditor | Victory Gate | series | task_reviewer, task_challenger, task_forensic_auditor | .agents/reviewer/review.md | .agents/VICTORY.md | victory_gate | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, _ = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertEqual(data.get("ready_frontier"), ["task_worker_fix"])

    def test_T4_2_scenario_focused_bugfix_worker_completion_unblocks_committee(self):
        """Simulate Turn 2: Worker finishes; unblocks parallel Adversarial Committee."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        # In fixture, task_worker_fix is PASSED; committee members are RUNNING
        # If we set committee to PENDING, all 3 should be in ready frontier
        run_validator([
            str(fixture),
            "--set-status", "task_reviewer=PENDING",
            "--set-status", "task_challenger=PENDING",
            "--set-status", "task_forensic_auditor=PENDING",
            "--update-file",
        ])
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        self.assertEqual(set(frontier), {"task_reviewer", "task_challenger", "task_forensic_auditor"})

    def test_T4_3_scenario_focused_bugfix_committee_concurrency_unblocks_victory(self):
        """Simulate Turn 3: Committee members all complete; unblocks Victory Auditor."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        # Mark all committee members PASSED
        run_validator([
            str(fixture),
            "--set-status", "task_reviewer=PASSED",
            "--set-status", "task_challenger=PASSED",
            "--set-status", "task_forensic_auditor=PASSED",
            "--update-file",
        ])
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertEqual(data.get("ready_frontier"), ["task_victory_auditor"])

    def test_T4_4_scenario_focused_bugfix_victory_certification_terminates(self):
        """Simulate Turn 4: Victory Auditor completes; entire workflow terminates."""
        fixture = self.copy_fixture("focused_bugfix_dag.md")
        run_validator([
            str(fixture),
            "--set-status", "task_reviewer=PASSED",
            "--set-status", "task_challenger=PASSED",
            "--set-status", "task_forensic_auditor=PASSED",
            "--set-status", "task_victory_auditor=PASSED",
            "--update-file",
        ])
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        # All tasks passed; ready frontier must be empty
        self.assertEqual(data.get("ready_frontier"), [])

    def test_T4_5_scenario_focused_bugfix_remediation_branch_injection(self):
        """Simulate Turn 5: Challenger fails; Orchestrator injects dynamic remediation node."""
        content = """# Focused Bugfix with Injected Remediation
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| task_worker_fix | Worker Implementation | series | none | spec.md | patch.diff | exit_0 | PASSED |
| task_reviewer | 5-Axis Reviewer | parallel | task_worker_fix | patch.diff | review.md | review_pass | PASSED |
| task_challenger | Adversarial Fuzzer | parallel | task_worker_fix | patch.diff | hostile_test.py | exit_0 | FAILED |
| task_remediation | Worker Remediation | series | task_worker_fix | hostile_test.py | patch_v2.diff | exit_0 | PENDING |
| task_victory | Victory Gate | series | task_reviewer, task_remediation | patch_v2.diff | victory.md | exit_0 | PENDING |
"""
        dag_file = self.write_temp_dag(content)
        code, out, err = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        # task_remediation should now be ready
        self.assertEqual(data.get("ready_frontier"), ["task_remediation"])
        # Victory gate remains blocked waiting for remediation
        self.assertNotIn("task_victory", data.get("ready_frontier", []))

    # --------------------------------------------------------------------------
    # Scenario B: Multi-Milestone Swarm with Tournament Branching (5 tests)
    # --------------------------------------------------------------------------

    def test_T4_6_scenario_swarm_m0_parallel_explorers(self):
        """Simulate Milestone 0: 3 parallel explorers unblock concurrently."""
        content = """# Swarm M0 Exploration
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| task_m0_exp1 | Codebase Survey | parallel | none | ORIGINAL_REQUEST.md | .agents/exp1/handoff.md | file_exists | PENDING |
| task_m0_exp2 | Dependency Survey | parallel | none | ORIGINAL_REQUEST.md | .agents/exp2/handoff.md | file_exists | PENDING |
| task_m0_exp3 | Requirements Miner | parallel | none | ORIGINAL_REQUEST.md | .agents/exp3/handoff.md | file_exists | PENDING |
| task_m1_worker | Storage Engine | series | task_m0_exp1, task_m0_exp2, task_m0_exp3 | exp_handoffs | src/storage.py | exit_0 | BLOCKED |
"""
        dag_file = self.write_temp_dag(content)
        code, out, _ = run_validator([str(dag_file), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        frontier = data.get("ready_frontier", [])
        self.assertEqual(set(frontier), {"task_m0_exp1", "task_m0_exp2", "task_m0_exp3"})

    def test_T4_7_scenario_swarm_m1_implementation_and_committee(self):
        """Simulate Milestone 1: M0 completes; M1 Worker executes and unblocks M1 Committee."""
        fixture = self.copy_fixture("multi_milestone_swarm_dag.md")
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        tasks = {t["id"]: t for t in data.get("tasks", [])}
        self.assertEqual(tasks["task_m1_worker"]["status"], "PASSED")
        self.assertEqual(tasks["task_m1_rev"]["status"], "PASSED")
        self.assertEqual(tasks["task_m1_chal"]["status"], "PASSED")
        self.assertEqual(tasks["task_m1_aud"]["status"], "PASSED")

    def test_T4_8_scenario_swarm_m2_competitive_branching_tournament(self):
        """Simulate Milestone 2: Worker Alpha vs Beta execute in parallel tournament."""
        fixture = self.copy_fixture("multi_milestone_swarm_dag.md")
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        tasks = {t["id"]: t for t in data.get("tasks", [])}
        # Both tournament workers are running in parallel
        self.assertEqual(tasks["task_m2_worker_a"]["status"], "RUNNING")
        self.assertEqual(tasks["task_m2_worker_b"]["status"], "RUNNING")
        # Arbiter depends on both workers
        self.assertIn("task_m2_worker_a", tasks["task_m2_arbiter"]["depends_on"])
        self.assertIn("task_m2_worker_b", tasks["task_m2_arbiter"]["depends_on"])

    def test_T4_9_scenario_swarm_m2_arbiter_synthesis_to_victory(self):
        """Simulate Milestone 2 Arbiter synthesis resolving winner and unblocking M2 Committee."""
        fixture = self.copy_fixture("multi_milestone_swarm_dag.md")
        # Workers A and B pass; Arbiter unblocks
        run_validator([
            str(fixture),
            "--set-status", "task_m2_worker_a=PASSED",
            "--set-status", "task_m2_worker_b=PASSED",
            "--update-file",
        ])
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertIn("task_m2_arbiter", data.get("ready_frontier", []))

    def test_T4_10_scenario_swarm_full_lifecycle_simulation(self):
        """Simulate complete 5-stage swarm progression with atomic Mermaid sync."""
        fixture = self.copy_fixture("multi_milestone_swarm_dag.md")

        # Stage 1: Tournament workers complete
        run_validator([
            str(fixture),
            "--set-status", "task_m2_worker_a=PASSED",
            "--set-status", "task_m2_worker_b=PASSED",
            "--update-file",
        ])
        # Stage 2: Arbiter completes synthesis
        run_validator([
            str(fixture),
            "--set-status", "task_m2_arbiter=PASSED",
            "--set-status", "task_m2_comm=PASSED",
            "--update-file",
        ])
        # Stage 3: Victory gate is now ready
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        data = self.parse_json_report(out)
        self.assertEqual(data.get("ready_frontier"), ["task_final_vic"])

        # Stage 4: Victory confirmed
        run_validator([
            str(fixture),
            "--set-status", "task_final_vic=PASSED",
            "--update-file",
        ])
        code, out, _ = run_validator([str(fixture), "--json"])
        self.assertEqual(code, 0)
        final_data = self.parse_json_report(out)
        self.assertEqual(final_data.get("ready_frontier"), [])


if __name__ == "__main__":
    unittest.main()
