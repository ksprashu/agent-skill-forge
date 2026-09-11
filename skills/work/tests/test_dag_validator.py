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
Unit tests for skills/work/scripts/dag_validator.py.
Covers:
- Linear, diamond, and multi-branch DAGs
- Cycle detection (direct, indirect, self-loop) via 3-color DFS
- Topological sort via Kahn's algorithm
- Missing dependency detection and duplicate task IDs
- Artifact path validation and physical existence checks
- Ready frontier computation and dormancy rules
- State consistency checks
- Mermaid diagram generation with CSS status classes
- In-place file update and status modification
- CLI execution, JSON output, stdin streaming, and exit codes
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dag_validator import (
    DAGValidator,
    ExecutionMode,
    TaskNode,
    TaskStatus,
    ValidationIssue,
    ValidationReport,
)


class TestDAGValidator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = str(SCRIPTS_DIR / "dag_validator.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_valid_linear_dag(self):
        md = """
# Pipeline
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | none | - | out_a.txt | exit_0 | PASSED |
| B | Step B | series | A | out_a.txt | out_b.txt | exit_0 | PASSED |
| C | Step C | series | B | out_b.txt | out_c.txt | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.topological_order, ["A", "B", "C"])
        self.assertEqual(report.ready_frontier, ["C"])
        self.assertEqual(len(report.cycle), 0)

    def test_valid_diamond_dag(self):
        md = """
# Diamond Graph
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Root | series | none | - | - | exit_0 | PASSED |
| B | Branch Left | parallel | A | - | - | exit_0 | PASSED |
| C | Branch Right | parallel | A | - | - | exit_0 | PASSED |
| D | Join | series | B, C | - | - | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.topological_order[0], "A")
        self.assertEqual(report.topological_order[-1], "D")
        self.assertIn("B", report.topological_order[1:3])
        self.assertIn("C", report.topological_order[1:3])
        self.assertEqual(report.ready_frontier, ["D"])

    def test_cycle_detection_direct(self):
        md = """
# Direct Cycle
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | B | - | - | none | PENDING |
| B | Task B | series | A | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        cycle_codes = [iss.code for iss in report.issues if iss.code == "CYCLE_DETECTED"]
        self.assertTrue(len(cycle_codes) > 0)
        self.assertTrue(len(report.cycle) >= 3)
        self.assertEqual(report.cycle[0], report.cycle[-1])

    def test_cycle_detection_indirect(self):
        md = """
# 3-Node Cycle
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | C | - | - | none | PENDING |
| B | Task B | series | A | - | - | none | PENDING |
| C | Task C | series | B | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        cycle_issues = [iss for iss in report.issues if iss.code == "CYCLE_DETECTED"]
        self.assertTrue(len(cycle_issues) > 0)
        self.assertEqual(report.cycle[0], report.cycle[-1])
        self.assertIn("A", report.cycle)
        self.assertIn("B", report.cycle)
        self.assertIn("C", report.cycle)

    def test_cycle_detection_self_loop(self):
        md = """
# Self Loop
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Self Dependent | series | A | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        self.assertEqual(report.cycle, ["A", "A"])

    def test_missing_dependency(self):
        md = """
# Missing Dep
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | - | - | none | PENDING |
| B | Task B | series | non_existent_task | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        missing_issues = [iss for iss in report.issues if iss.code == "MISSING_DEPENDENCY"]
        self.assertEqual(len(missing_issues), 1)
        self.assertIn("non_existent_task", missing_issues[0].message)

    def test_duplicate_task_id(self):
        md = """
# Duplicate ID
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| worker | First Worker | series | none | - | - | none | PENDING |
| worker | Second Worker | series | none | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        dup_issues = [iss for iss in report.issues if iss.code == "DUPLICATE_TASK_ID"]
        self.assertEqual(len(dup_issues), 1)
        self.assertIn("worker", dup_issues[0].message)

    def test_invalid_execution_mode(self):
        md = """
# Bad Mode
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Bad Mode Task | invalid_mode_xyz | none | - | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        mode_issues = [iss for iss in report.issues if iss.code == "INVALID_MODE"]
        self.assertEqual(len(mode_issues), 1)

    def test_invalid_status(self):
        md = """
# Bad Status
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Bad Status Task | series | none | - | - | none | UNKNOWN_STATUS_123 |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        st_issues = [iss for iss in report.issues if iss.code == "INVALID_STATUS"]
        self.assertEqual(len(st_issues), 1)

    def test_artifact_path_validation_illegal_chars(self):
        md = """
# Illegal Path
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | src/<invalid>*path.py | - | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        path_issues = [iss for iss in report.issues if iss.code == "ILLEGAL_PATH_CHARS"]
        self.assertEqual(len(path_issues), 1)

    def test_artifact_path_validation_absolute_roots(self):
        md = """
# Absolute Paths
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | /etc/passwd | C:\\secrets.txt | none | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        abs_issues = [iss for iss in report.issues if iss.code == "ABSOLUTE_PATH_DISALLOWED"]
        self.assertEqual(len(abs_issues), 2)

    def test_check_artifacts_physical_existing(self):
        # Create physical files
        f_in = Path(self.test_dir) / "in.txt"
        f_out = Path(self.test_dir) / "out.txt"
        f_in.write_text("sample input", encoding="utf-8")
        f_out.write_text("sample output", encoding="utf-8")

        md = """
# Physical Files Present
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | in.txt | out.txt | exit_0 | PASSED |
"""
        validator = DAGValidator(check_artifacts=True, base_dir=self.test_dir)
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Unexpected errors: {report.errors}")

    def test_check_artifacts_physical_missing(self):
        md = """
# Physical Files Missing
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | missing_input.txt | missing_output.txt | exit_0 | PASSED |
"""
        validator = DAGValidator(check_artifacts=True, base_dir=self.test_dir)
        report = validator.validate(md)
        self.assertFalse(report.valid)
        codes = [iss.code for iss in report.issues]
        self.assertIn("MISSING_INPUT_ARTIFACT", codes)
        self.assertIn("MISSING_OUTPUT_ARTIFACT", codes)

    def test_ready_frontier_resolution(self):
        md = """
# Frontier Test
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | parallel | none | - | - | exit_0 | PASSED |
| B | Task B | parallel | none | - | - | exit_0 | PASSED |
| C | Task C | parallel | A, B | - | - | exit_0 | PENDING |
| D | Task D | series | C | - | - | exit_0 | PENDING |
| E | Task E | parallel | none | - | - | exit_0 | RUNNING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid)
        # C is ready because A and B are PASSED.
        # D is NOT ready because C is PENDING.
        # E is already RUNNING.
        self.assertEqual(report.ready_frontier, ["C"])

    def test_ready_frontier_dormancy_when_dep_failed(self):
        md = """
# Dormancy Test
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | - | - | exit_0 | FAILED |
| B | Task B | series | A | - | - | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        # B should NOT be in ready frontier because A failed
        self.assertEqual(report.ready_frontier, [])

    def test_state_inconsistency(self):
        md = """
# Inconsistent States
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | exit_0 | FAILED |
| B | Downstream | series | A | - | - | exit_0 | PASSED |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        incon_issues = [iss for iss in report.issues if iss.code == "STATE_INCONSISTENCY"]
        self.assertEqual(len(incon_issues), 1)

    def test_async_background_handling(self):
        md = """
# Background Watchdog
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| watchdog | Liveness Watchdog | async_background | none | - | - | none | RUNNING |
| worker | Main Task | series | none | - | - | exit_0 | PASSED |
| arbiter | Arbiter | series | worker | - | - | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid)
        self.assertIn("watchdog", report.topological_order)
        self.assertEqual(report.ready_frontier, ["arbiter"])

    def test_mermaid_generation(self):
        md = """
# Mermaid Check
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Alpha | series | none | - | - | none | PASSED |
| B | Beta | series | A | - | - | none | RUNNING |
| C | Gamma | series | B | - | - | none | PENDING |
| D | Delta | series | B | - | - | none | BLOCKED |
| E | Epsilon | series | B | - | - | none | FAILED |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid)
        mermaid = report.mermaid

        self.assertIn("```mermaid", mermaid)
        self.assertIn("graph TD", mermaid)
        self.assertIn("A[\"A<br/>[series] <b>PASSED</b>\"]:::status-passed", mermaid)
        self.assertIn("B[\"B<br/>[series] <b>RUNNING</b>\"]:::status-running", mermaid)
        self.assertIn("C[\"C<br/>[series] <b>PENDING</b>\"]:::status-pending", mermaid)
        self.assertIn("D[\"D<br/>[series] <b>BLOCKED</b>\"]:::status-blocked", mermaid)
        self.assertIn("E[\"E<br/>[series] <b>FAILED</b>\"]:::status-failed", mermaid)
        self.assertIn("A --> B", mermaid)
        self.assertIn("B --> C", mermaid)
        self.assertIn("classDef status-passed fill:#14532d", mermaid)
        self.assertIn("classDef status-running fill:#1e3a8a", mermaid)
        self.assertIn("classDef status-pending fill:#2d3748", mermaid)
        self.assertIn("classDef status-blocked fill:#78350f", mermaid)
        self.assertIn("classDef status-failed fill:#7f1d1d", mermaid)

    def test_in_place_file_update(self):
        initial_md = """# Swarm Project

## Task Graph
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| worker_alpha | Worker | series | none | - | - | none | RUNNING |
| victory | Victory | series | worker_alpha | - | - | none | PENDING |
"""
        test_file = Path(self.test_dir) / "DAG.md"
        test_file.write_text(initial_md, encoding="utf-8")

        validator = DAGValidator()
        updated_text = validator.update_markdown_content(
            initial_md,
            status_updates={"worker_alpha": "PASSED"}
        )
        test_file.write_text(updated_text, encoding="utf-8")

        # Verify file content
        content = test_file.read_text(encoding="utf-8")
        self.assertIn("PASSED", content)
        self.assertIn("```mermaid", content)
        self.assertIn("worker_alpha --> victory", content)

        # Re-validate updated file
        report = validator.validate(content)
        self.assertTrue(report.valid)
        self.assertEqual(report.nodes["worker_alpha"].status, TaskStatus.PASSED)
        self.assertEqual(report.ready_frontier, ["victory"])

    def test_structured_task_blocks_format_b(self):
        md = """# Structured Task Block Specification

### Task: task_1
- **Title**: Initialize Project
- **Mode**: series
- **Depends On**: none
- **Inputs**: none
- **Outputs**: init.log
- **Gate**: exit_0
- **Status**: PASSED

### Task: task_2
- **Title**: Execute Pipeline
- **Mode**: parallel
- **Depends On**: task_1
- **Inputs**: init.log
- **Outputs**: results.json
- **Gate**: exit_0
- **Status**: PENDING
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.topological_order, ["task_1", "task_2"])
        self.assertEqual(report.ready_frontier, ["task_2"])
        self.assertEqual(report.nodes["task_2"].mode, ExecutionMode.PARALLEL)

    def test_cli_json_output(self):
        f = Path(self.test_dir) / "test_cli.md"
        f.write_text("""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Alpha | series | none | - | - | none | PASSED |
| B | Beta | series | A | - | - | none | PENDING |
""", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, self.script_path, str(f), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data["valid"])
        self.assertEqual(data["topological_order"], ["A", "B"])
        self.assertEqual(data["ready_frontier"], ["B"])

    def test_cli_stdin_input(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| S1 | Step 1 | series | none | - | - | none | PASSED |
"""
        proc = subprocess.run(
            [sys.executable, self.script_path, "--stdin", "--json"],
            input=md,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertTrue(data["valid"])
        self.assertEqual(data["tasks"][0]["id"], "S1")

    def test_cli_cycle_exit_code(self):
        f = Path(self.test_dir) / "cycle.md"
        f.write_text("""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | B | - | - | none | PENDING |
| B | Step B | series | A | - | - | none | PENDING |
""", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, self.script_path, str(f)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Cycle Detected", proc.stdout)

    def test_cli_invalid_file_exit_code(self):
        non_existent = str(Path(self.test_dir) / "not_found.md")
        proc = subprocess.run(
            [sys.executable, self.script_path, non_existent],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 2)

    def test_cli_update_file(self):
        f = Path(self.test_dir) / "update_test.md"
        f.write_text("""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | - | - | none | PENDING |
""", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, self.script_path, str(f), "--set-status", "A=PASSED", "--update-file"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        updated_content = f.read_text(encoding="utf-8")
        self.assertIn("PASSED", updated_content)
        self.assertIn("```mermaid", updated_content)

    def test_multi_token_backticks_split(self):
        md = """
# Multi-token Code Spans
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Multi Dep | series | `T1`, `T2` | `in1.txt`, `in2.txt` | `out.txt` | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T3"].depends_on, ["T1", "T2"])
        self.assertEqual(report.nodes["T3"].inputs, ["in1.txt", "in2.txt"])
        self.assertEqual(report.ready_frontier, ["T3"])

    def test_escaped_pipe_in_table_cell(self):
        md = r"""
# Escaped Pipe Table
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Pipeline Step \| grep foo | series | none | - | - | grep \| wc -l | PASSED |
| B | Next Step | series | A | - | - | exit_0 | PENDING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertIn("A", report.nodes)
        self.assertIn("B", report.nodes)
        self.assertEqual(report.nodes["A"].mode, ExecutionMode.SERIES)
        self.assertEqual(report.nodes["A"].status, TaskStatus.PASSED)
        self.assertEqual(report.ready_frontier, ["B"])

    def test_git_virtual_artifacts(self):
        md = """
# Git Artifacts
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | none | git:diff, git:branch | git:commit, git:patch | exit_0 | PASSED |
"""
        validator = DAGValidator(check_artifacts=True, base_dir=self.test_dir)
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")

    def test_state_consistency_downstream_passed_upstream_pending(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | none | PENDING |
| B | Downstream | series | A | - | - | none | PASSED |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        issues = [iss for iss in report.issues if iss.code == "STATE_INCONSISTENCY"]
        self.assertEqual(len(issues), 1)

    def test_state_consistency_downstream_running_upstream_failed(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | none | FAILED |
| B | Downstream | series | A | - | - | none | RUNNING |
"""
        validator = DAGValidator()
        report = validator.validate(md)
        self.assertFalse(report.valid)
        issues = [iss for iss in report.issues if iss.code == "STATE_INCONSISTENCY"]
        self.assertEqual(len(issues), 1)

    def test_cli_set_status_in_memory_without_update_file(self):
        f = Path(self.test_dir) / "status_in_mem.md"
        initial_content = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | none | - | - | none | PENDING |
"""
        f.write_text(initial_content, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, self.script_path, str(f), "--set-status", "A=PASSED", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["tasks"][0]["status"], "PASSED")
        # File on disk should remain unchanged because --update-file was NOT specified
        disk_content = f.read_text(encoding="utf-8")
        self.assertEqual(disk_content, initial_content)

    def test_scaffold_work_focused_dag(self):
        scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        temp_d = Path(self.test_dir) / "focused_proj"
        temp_d.mkdir()
        proc = subprocess.run(
            [sys.executable, scaffold_script, "--project-dir", str(temp_d), "--topology", "focused"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        dag_file = temp_d / ".agents" / "DAG.md"
        self.assertTrue(dag_file.exists())
        validator = DAGValidator()
        report = validator.validate(dag_file.read_text(encoding="utf-8"))
        self.assertTrue(report.valid, f"Scaffolded focused DAG invalid: {report.errors}")
        self.assertEqual(report.ready_frontier, ["task_worker_fix"])

    def test_scaffold_work_full_dag(self):
        scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        temp_d = Path(self.test_dir) / "full_proj"
        temp_d.mkdir()
        proc = subprocess.run(
            [sys.executable, scaffold_script, "--project-dir", str(temp_d), "--topology", "full", "--milestones", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        dag_file = temp_d / ".agents" / "DAG.md"
        self.assertTrue(dag_file.exists())
        validator = DAGValidator()
        report = validator.validate(dag_file.read_text(encoding="utf-8"))
        self.assertTrue(report.valid, f"Scaffolded full DAG invalid: {report.errors}")
        self.assertEqual(report.ready_frontier, ["task_m0_survey"])


if __name__ == "__main__":
    unittest.main()

