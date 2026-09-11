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
Tier 5 Adversarial Coverage Hardening Test Suite
Part of the Google Antigravity Work Swarm Engine (skills/work).

Author: Final Challenger 1 (Tier 5 Adversarial Coverage Hardening)
Roles: critic, specialist

Stress-tests:
1. Multi-token backticks & delimiter robustness
2. Escaped pipes & markdown table integrity across in-place mutations
3. Git virtual artifact prefix matching (`git:*`) and disk verification
4. State consistency matrices across all status combinations
5. Dynamic DAG mutations and scaling (up to 500 nodes)
6. Security invariants: Directory traversal, absolute roots, illegal characters
7. Work swarm scaffolding edge cases across topologies
"""

import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and getattr(sys.stderr, "encoding", "").lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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


class TestAdversarialHardening(unittest.TestCase):
    """Tier 5 Adversarial Test Matrix."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = str(SCRIPTS_DIR / "dag_validator.py")
        self.validator = DAGValidator()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. Multi-Token Backticks & Delimiter Edge Cases
    # --------------------------------------------------------------------------
    def test_multi_token_backticks_standard(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Dependent | series | `T1`, `T2` | `in1.txt`, `in2.txt` | `out.txt` | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T3"].depends_on, ["T1", "T2"])
        self.assertEqual(report.nodes["T3"].inputs, ["in1.txt", "in2.txt"])
        self.assertEqual(report.ready_frontier, ["T3"])

    def test_multi_token_backticks_bracketed(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Dependent | series | [`T1`, `T2`] | [`in1.txt`, `in2.txt`] | [`out.txt`] | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T3"].depends_on, ["T1", "T2"])
        self.assertEqual(report.nodes["T3"].inputs, ["in1.txt", "in2.txt"])
        self.assertEqual(report.ready_frontier, ["T3"])

    def test_multi_token_backticks_semicolon_delimited(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Dependent | series | `T1`; `T2` | `in1.txt`; `in2.txt` | out.txt | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T3"].depends_on, ["T1", "T2"])
        self.assertEqual(report.nodes["T3"].inputs, ["in1.txt", "in2.txt"])

    def test_multi_token_backticks_mixed_styles(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Third | series | none | - | - | exit_0 | PASSED |
| T4 | Dependent | series | `T1`, T2, `T3` | in1.txt, `in2.txt` | out.txt | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T4"].depends_on, ["T1", "T2", "T3"])
        self.assertEqual(report.nodes["T4"].inputs, ["in1.txt", "in2.txt"])

    def test_multi_token_backticks_empty_delimiters(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | First | series | none | - | - | exit_0 | PASSED |
| T2 | Second | series | none | - | - | exit_0 | PASSED |
| T3 | Dependent | series | `T1`, , `T2` | - | - | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["T3"].depends_on, ["T1", "T2"])

    # --------------------------------------------------------------------------
    # 2. Escaped Pipes & Cell Splitting Robustness
    # --------------------------------------------------------------------------
    def test_escaped_pipe_in_gate_multiple(self):
        md = r"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | none | - | - | cat foo \| grep bar \| wc -l | PASSED |
| B | Step B | series | A | - | - | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertIn("A", report.nodes)
        self.assertIn("B", report.nodes)
        self.assertEqual(report.nodes["A"].status, TaskStatus.PASSED)
        self.assertEqual(report.ready_frontier, ["B"])

    def test_escaped_pipe_in_title(self):
        md = r"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A \| Worker | series | none | - | - | exit_0 | PASSED |
| B | Step B | series | A | - | - | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertIn("Step A", report.nodes["A"].title)

    def test_escaped_pipe_preserved_after_inplace_update(self):
        md = r"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Step A | series | none | - | - | cat foo \| grep bar | RUNNING |
| B | Step B | series | A | - | - | exit_0 | PENDING |
"""
        updated = self.validator.update_markdown_content(md, {"A": "PASSED"})
        report = self.validator.validate(updated)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.nodes["A"].status, TaskStatus.PASSED)
        self.assertEqual(report.ready_frontier, ["B"])
        self.assertIn(r"cat foo \| grep bar", updated)

    # --------------------------------------------------------------------------
    # 3. Git Virtual Artifacts
    # --------------------------------------------------------------------------
    def test_git_virtual_artifacts_comprehensive(self):
        validator = DAGValidator(check_artifacts=True, base_dir=self.test_dir)
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Diff Check | series | none | git:diff, git:branch, git:commit | git:patch, git:workspace | exit_0 | PASSED |
| T2 | Branch Check | series | T1 | git:origin/main, git:HEAD~1 | git:refs/tags/v1.0 | exit_0 | PASSED |
| T3 | Tree Check | series | T2 | git:tree/abc123 | stdout, stderr | exit_0 | PASSED |
"""
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")

    def test_mixed_git_and_real_artifacts(self):
        f_real_in = Path(self.test_dir) / "real_in.txt"
        f_real_out = Path(self.test_dir) / "real_out.txt"
        f_real_in.write_text("input data", encoding="utf-8")
        f_real_out.write_text("output data", encoding="utf-8")

        validator = DAGValidator(check_artifacts=True, base_dir=self.test_dir)
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Step | series | none | git:diff, real_in.txt | git:commit, real_out.txt | exit_0 | PASSED |
"""
        report = validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")

    # --------------------------------------------------------------------------
    # 4. Hardened State Consistency
    # --------------------------------------------------------------------------
    def test_state_consistency_all_invalid_combinations(self):
        invalid_combos = [
            (TaskStatus.PENDING, TaskStatus.PASSED),
            (TaskStatus.FAILED, TaskStatus.PASSED),
            (TaskStatus.BLOCKED, TaskStatus.PASSED),
            (TaskStatus.RUNNING, TaskStatus.PASSED),
            (TaskStatus.PENDING, TaskStatus.RUNNING),
            (TaskStatus.FAILED, TaskStatus.RUNNING),
            (TaskStatus.BLOCKED, TaskStatus.RUNNING),
        ]
        for dep_st, task_st in invalid_combos:
            with self.subTest(dep=dep_st.value, task=task_st.value):
                md = f"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | exit_0 | {dep_st.value} |
| B | Downstream | series | A | - | - | exit_0 | {task_st.value} |
"""
                report = self.validator.validate(md)
                self.assertFalse(report.valid, f"Expected invalid for {dep_st.value} -> {task_st.value}")
                issues = [iss for iss in report.issues if iss.code == "STATE_INCONSISTENCY"]
                self.assertTrue(len(issues) >= 1)

    def test_state_consistency_all_valid_combinations(self):
        valid_combos = [
            (TaskStatus.PASSED, TaskStatus.PASSED),
            (TaskStatus.PASSED, TaskStatus.RUNNING),
            (TaskStatus.PASSED, TaskStatus.PENDING),
            (TaskStatus.PENDING, TaskStatus.PENDING),
            (TaskStatus.PENDING, TaskStatus.BLOCKED),
            (TaskStatus.FAILED, TaskStatus.BLOCKED),
            (TaskStatus.FAILED, TaskStatus.FAILED),
        ]
        for dep_st, task_st in valid_combos:
            with self.subTest(dep=dep_st.value, task=task_st.value):
                md = f"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | exit_0 | {dep_st.value} |
| B | Downstream | series | A | - | - | exit_0 | {task_st.value} |
"""
                report = self.validator.validate(md)
                self.assertTrue(report.valid, f"Expected valid for {dep_st.value} -> {task_st.value}, got errors: {report.errors}")

    def test_state_consistency_downstream_running_upstream_running(self):
        """
        Adversarial Finding: A downstream task should NOT be RUNNING if its upstream
        dependency is still RUNNING. Upstream outputs are not yet produced.
        """
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Upstream | series | none | - | - | exit_0 | RUNNING |
| B | Downstream | series | A | - | - | exit_0 | RUNNING |
"""
        report = self.validator.validate(md)
        # Should be rejected with STATE_INCONSISTENCY
        self.assertFalse(report.valid, "Downstream task should not be RUNNING when dependency is RUNNING")
        self.assertTrue(any(iss.code == "STATE_INCONSISTENCY" for iss in report.issues))

    # --------------------------------------------------------------------------
    # 5. Dynamic DAG Mutations & Large Graph Scaling
    # --------------------------------------------------------------------------
    def test_repeated_inplace_status_updates(self):
        content = """# Continuous Lifecycle Swarm
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Step 1 | series | none | - | - | exit_0 | PENDING |
| T2 | Step 2 | series | T1 | - | - | exit_0 | PENDING |
| T3 | Step 3 | series | T2 | - | - | exit_0 | PENDING |
"""
        transitions = [
            {"T1": "RUNNING"},
            {"T1": "PASSED"},
            {"T2": "RUNNING"},
            {"T2": "PASSED"},
            {"T3": "RUNNING"},
            {"T3": "PASSED"},
        ]
        for step in transitions:
            content = self.validator.update_markdown_content(content, step)
            report = self.validator.validate(content)
            self.assertTrue(report.valid, f"Failed at transition {step}: {report.errors}")

        final_report = self.validator.validate(content)
        self.assertEqual(final_report.nodes["T3"].status, TaskStatus.PASSED)
        self.assertIn("T1 --> T2", content)
        self.assertIn("T2 --> T3", content)

    def test_large_graph_scaling_100_nodes(self):
        rows = ["| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |",
                "|---|---|---|---|---|---|---|---|"]
        for i in range(1, 101):
            dep = f"N{i-1:03d}" if i > 1 else "none"
            rows.append(f"| N{i:03d} | Node {i} | series | {dep} | - | - | exit_0 | PENDING |")
        md = "\n".join(rows)

        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(len(report.topological_order), 100)
        self.assertEqual(report.ready_frontier, ["N001"])

    def test_large_graph_scaling_500_nodes(self):
        t0 = time.perf_counter()
        rows = ["| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |",
                "|---|---|---|---|---|---|---|---|"]
        for i in range(1, 501):
            dep = f"N{i-1:03d}" if i > 1 else "none"
            rows.append(f"| N{i:03d} | Node {i} | series | {dep} | - | - | exit_0 | PENDING |")
        md = "\n".join(rows)

        report = self.validator.validate(md)
        elapsed = time.perf_counter() - t0
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(len(report.topological_order), 500)
        self.assertLess(elapsed, 1.5, f"500-node graph took {elapsed:.3f}s (should be < 1.5s)")

    # --------------------------------------------------------------------------
    # 6. Malformed Formats & Robustness
    # --------------------------------------------------------------------------
    def test_malformed_table_truncated_row(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Short Row | series |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid)
        self.assertIn("T1", report.nodes)

    def test_malformed_table_missing_separator(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
| T1 | No Separator | series | none | - | - | exit_0 | PASSED |
"""
        report = self.validator.validate(md)
        self.assertFalse(report.valid)
        self.assertIn("NO_TASKS_FOUND", [iss.code for iss in report.issues])

    def test_unicode_and_emojis(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| 任务_1 | 🚀 Rocket Deployment | series | none | - | - | exit_0 | PASSED |
| 任务_2 | 🛡️ Security Audit | series | 任务_1 | - | - | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.assertEqual(report.topological_order, ["任务_1", "任务_2"])
        self.assertEqual(report.ready_frontier, ["任务_2"])

    def test_case_insensitive_status_aliases(self):
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Task A | series | none | - | - | exit_0 | done |
| B | Task B | series | A | - | - | exit_0 | in_progress |
| C | Task C | series | B | - | - | exit_0 | error |
"""
        report = self.validator.validate(md)
        self.assertIn("A", report.nodes)
        self.assertEqual(report.nodes["A"].status, TaskStatus.PASSED)
        self.assertEqual(report.nodes["B"].status, TaskStatus.RUNNING)
        self.assertEqual(report.nodes["C"].status, TaskStatus.FAILED)

    # --------------------------------------------------------------------------
    # 7. Security Invariants
    # --------------------------------------------------------------------------
    def test_reject_absolute_paths(self):
        disallowed = [
            "/etc/passwd",
            "/var/log/syslog",
            r"\Windows\System32\cmd.exe",
            r"C:\secret.txt",
            "D:/data/key.pem",
            "~/.ssh/id_rsa",
        ]
        for p in disallowed:
            with self.subTest(path=p):
                md = f"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T | Task | series | none | {p} | - | exit_0 | PENDING |
"""
                report = self.validator.validate(md)
                self.assertFalse(report.valid)
                abs_issues = [iss for iss in report.issues if iss.code == "ABSOLUTE_PATH_DISALLOWED"]
                self.assertTrue(len(abs_issues) >= 1)

    def test_reject_illegal_path_chars(self):
        illegal = [
            "src/<evil>.py",
            "src/>evil.py",
            'src/"evil".py',
            "src/evil?.py",
            "src/evil*.py",
        ]
        for p in illegal:
            with self.subTest(path=p):
                md = f"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T | Task | series | none | {p} | - | exit_0 | PENDING |
"""
                report = self.validator.validate(md)
                self.assertFalse(report.valid)
                ill_issues = [iss for iss in report.issues if iss.code == "ILLEGAL_PATH_CHARS"]
                self.assertTrue(len(ill_issues) >= 1)

    def test_directory_traversal_attempts(self):
        """
        Adversarial Finding: Directory traversal paths (e.g. `../secret.txt`) escape the
        workspace root, violating the Workspace-Relative constraint (Section 4.3).
        """
        traversal_paths = [
            "../secret.txt",
            "../../etc/shadow",
            "subfolder/../../../passwords.txt",
            r"..\..\Windows\win.ini",
        ]
        for p in traversal_paths:
            with self.subTest(path=p):
                md = f"""
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T | Task | series | none | {p} | - | exit_0 | PENDING |
"""
                report = self.validator.validate(md)
                # Should reject directory traversal
                self.assertFalse(report.valid, f"Path traversal '{p}' should be rejected")
                self.assertTrue(any(iss.code == "DIRECTORY_TRAVERSAL_DISALLOWED" for iss in report.issues))

    def test_drive_relative_paths(self):
        """
        Adversarial Finding: Windows drive-relative path `C:secret.txt` escapes regex
        `^[a-zA-Z]:[\\\\/]` because it lacks a slash after colon.
        """
        md = """
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T | Task | series | none | C:secret.txt | - | exit_0 | PENDING |
"""
        report = self.validator.validate(md)
        self.assertFalse(report.valid, "Drive-relative path 'C:secret.txt' should be disallowed")
        self.assertTrue(any(iss.code == "ABSOLUTE_PATH_DISALLOWED" for iss in report.issues))

    # --------------------------------------------------------------------------
    # 8. Scaffolding Edge Cases
    # --------------------------------------------------------------------------
    def test_scaffold_focused_topology(self):
        scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        temp_d = Path(self.test_dir) / "scaffold_focused"
        temp_d.mkdir()
        proc = subprocess.run(
            [sys.executable, scaffold_script, "--project-dir", str(temp_d), "--topology", "focused"],
            capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        dag_file = temp_d / ".agents" / "DAG.md"
        self.assertTrue(dag_file.exists())
        report = self.validator.validate(dag_file.read_text(encoding="utf-8"))
        self.assertTrue(report.valid)
        self.assertEqual(report.ready_frontier, ["task_worker_fix"])

    def test_scaffold_full_topology_multi_milestone(self):
        scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        temp_d = Path(self.test_dir) / "scaffold_full"
        temp_d.mkdir()
        proc = subprocess.run(
            [sys.executable, scaffold_script, "--project-dir", str(temp_d), "--topology", "full", "--milestones", "4"],
            capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        dag_file = temp_d / ".agents" / "DAG.md"
        self.assertTrue(dag_file.exists())
        report = self.validator.validate(dag_file.read_text(encoding="utf-8"))
        self.assertTrue(report.valid)
        self.assertEqual(len(report.nodes), 10)  # m0_survey + 4*(worker + committee) + victory

    def test_scaffold_review_topology_consistency(self):
        """
        Adversarial Finding: `scaffold_work.py` with `--topology review` writes a
        dedicated document review DAG without requiring an Orchestrator.
        """
        scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        temp_d = Path(self.test_dir) / "scaffold_review"
        temp_d.mkdir()
        proc = subprocess.run(
            [sys.executable, scaffold_script, "--project-dir", str(temp_d), "--topology", "review"],
            capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0)
        dag_file = temp_d / ".agents" / "DAG.md"
        dag_content = dag_file.read_text(encoding="utf-8")
        # Review topology DAG should not be a multi-milestone worker/committee DAG
        self.assertNotIn("task_m0_survey", dag_content, "Review topology should have a review DAG, not milestone swarm")
        report = self.validator.validate(dag_content)
        self.assertTrue(report.valid, f"Scaffolded review DAG should be valid, got: {report.errors}")
        self.assertEqual(report.ready_frontier, ["task_lead_reviewer"])


if __name__ == "__main__":
    unittest.main()
