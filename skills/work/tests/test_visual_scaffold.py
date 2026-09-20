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
Comprehensive unit and integration tests for Visual Production Swarm Engine Scaffolding
and Mermaid synchronization validation.
Covers:
1. Running scaffold_work.py with --lifecycle:
   - Verifies creation of proposal_alpha.md, proposal_beta.md, DESIGN.md.
   - Verifies embedded Mermaid C4 component diagrams, sequence diagrams, and system architecture.
   - Verifies generation of .agents/design/what_if_simulator.html with Canvas 2D radar visualizer.
2. dag_validator.py --check-mermaid and validate_mermaid_sync():
   - Validates in-sync DAG topologies (lifecycle, focused, review).
   - Detects drift when task table contains tasks missing from Mermaid.
   - Detects drift when Mermaid contains nodes missing from task table.
   - Validates CLI exit codes (0 on in-sync, 1 on drift) and JSON output format.
"""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scaffold_work import scaffold_work
from dag_validator import (
    DAGValidator,
    MermaidSyncResult,
    extract_mermaid_node_ids,
    validate_mermaid_sync,
)


class TestVisualScaffoldLifecycle(unittest.TestCase):
    """Tests for scaffold_work.py visual artifact and diagram generation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.proj_dir = os.path.join(self.test_dir, "test_lifecycle_proj")
        self.scaffold_script = str(SCRIPTS_DIR / "scaffold_work.py")
        self.validator_script = str(SCRIPTS_DIR / "dag_validator.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scaffold_lifecycle_visual_artifacts_generation(self):
        """Verify that scaffold_work with lifecycle generates proposals, DESIGN.md, and what_if_simulator.html."""
        scaffold_work(
            target_dir=self.proj_dir,
            project_name="SwarmVisuals",
            milestones=2,
            topology="lifecycle",
            lifecycle=True,
        )

        agents_dir = Path(self.proj_dir) / ".agents"
        design_dir = agents_dir / "design"
        proposals_dir = design_dir / "proposals"

        alpha_file = proposals_dir / "proposal_alpha.md"
        beta_file = proposals_dir / "proposal_beta.md"
        design_file = design_dir / "DESIGN.md"
        simulator_file = design_dir / "what_if_simulator.html"
        dag_file = agents_dir / "DAG.md"

        self.assertTrue(alpha_file.exists(), "proposal_alpha.md must be scaffolded")
        self.assertTrue(beta_file.exists(), "proposal_beta.md must be scaffolded")
        self.assertTrue(design_file.exists(), "DESIGN.md must be scaffolded")
        self.assertTrue(simulator_file.exists(), "what_if_simulator.html must be generated in lifecycle mode")
        self.assertTrue(dag_file.exists(), "DAG.md must be scaffolded")

        # 1. Inspect proposal_alpha.md
        alpha_content = alpha_file.read_text(encoding="utf-8")
        self.assertIn("### 1.1 High-Level System Architecture", alpha_content)
        self.assertIn("flowchart TD", alpha_content)
        self.assertIn("### 1.2 C4 Level 2/3 Component Diagram", alpha_content)
        self.assertIn("graph TD", alpha_content)
        self.assertIn("subgraph AlphaBoundary", alpha_content)
        self.assertIn("### 1.3 Lifecycle Sequence & Dataflow Diagram", alpha_content)
        self.assertIn("sequenceDiagram", alpha_content)
        self.assertIn("autonumber", alpha_content)
        self.assertIn("## 2. Data Models & Schemas", alpha_content)
        self.assertIn("export interface AlphaTaskRequest", alpha_content)

        # 2. Inspect proposal_beta.md
        beta_content = beta_file.read_text(encoding="utf-8")
        self.assertIn("### 1.1 High-Level System Architecture", beta_content)
        self.assertIn("flowchart TD", beta_content)
        self.assertIn("### 1.2 C4 Level 2/3 Component Diagram", beta_content)
        self.assertIn("graph TD", beta_content)
        self.assertIn("subgraph BetaBoundary", beta_content)
        self.assertIn("### 1.3 Lifecycle Sequence & Dataflow Diagram", beta_content)
        self.assertIn("sequenceDiagram", beta_content)
        self.assertIn("## 2. Data Models & Schemas", beta_content)
        self.assertIn("export interface BetaTaskRequest", beta_content)

        # 3. Inspect DESIGN.md
        design_content = design_file.read_text(encoding="utf-8")
        self.assertIn("### 1.1 High-Level System Architecture", design_content)
        self.assertIn("flowchart TD", design_content)
        self.assertIn("### 1.2 C4 Level 3 Component Block Diagram", design_content)
        self.assertIn("graph TD", design_content)
        self.assertIn("subgraph SwarmBoundary", design_content)
        self.assertIn("### 1.3 Lifecycle Sequence & Dataflow Diagram", design_content)
        self.assertIn("sequenceDiagram", design_content)
        self.assertIn("## 2. Data Models & Interface Contracts", design_content)

        # 4. Inspect what_if_simulator.html
        sim_content = simulator_file.read_text(encoding="utf-8")
        self.assertTrue(sim_content.startswith("<!DOCTYPE html>"))
        self.assertIn("radar-canvas", sim_content)
        self.assertIn("devicePixelRatio", sim_content)
        self.assertIn("drawRadarChart", sim_content)
        self.assertIn("sliders-container", sim_content)
        self.assertIn("exportDecisionMarkdown", sim_content)
        self.assertIn("SwarmVisuals", sim_content)
        self.assertIn("https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js", sim_content)
        self.assertNotIn("unpkg.com", sim_content)
        self.assertNotIn("jsdelivr.net", sim_content)
        self.assertNotIn("cdnjs.cloudflare.com", sim_content)
        self.assertIn("<noscript>", sim_content)

    def test_scaffold_cli_lifecycle_flag(self):
        """Verify running scaffold_work.py via CLI with --lifecycle flag."""
        cli_proj = os.path.join(self.test_dir, "cli_lifecycle")
        cmd = [
            sys.executable,
            self.scaffold_script,
            "--project-dir", cli_proj,
            "--name", "CLISwarm",
            "--milestones", "2",
            "--lifecycle",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"scaffold_work CLI failed: {proc.stderr}")

        sim_path = Path(cli_proj) / ".agents" / "design" / "what_if_simulator.html"
        self.assertTrue(sim_path.exists())
        self.assertIn("CLISwarm", sim_path.read_text(encoding="utf-8"))

        alpha_path = Path(cli_proj) / ".agents" / "design" / "proposals" / "proposal_alpha.md"
        alpha_text = alpha_path.read_text(encoding="utf-8")
        self.assertIn("C4 Level 2/3 Component Diagram", alpha_text)
        self.assertIn("sequenceDiagram", alpha_text)


class TestDAGValidatorCheckMermaid(unittest.TestCase):
    """Tests for dag_validator.py --check-mermaid flag and validate_mermaid_sync function."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.validator_script = str(SCRIPTS_DIR / "dag_validator.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_mermaid_node_ids(self):
        """Test robust node ID extraction across various Mermaid syntax elements."""
        mermaid_code = """
        graph TD
          %% Comment line
          subgraph CoreBoundary ["Core Subsystem"]
            task_worker_fix["task_worker_fix<br/>[series] <b>PENDING</b>"]:::status-pending
            task_reviewer["task_reviewer<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
            task_join([task_join])
            task_decision{task_decision}
          end

          task_worker_fix --> task_reviewer
          task_reviewer -->|Gate Pass| task_join
          task_join -.-> task_decision
          task_decision ==> task_victory["task_victory"]:::status-blocked

          classDef status-pending fill:#2d3748,stroke:#64748b;
          classDef status-blocked fill:#78350f,stroke:#d97706;
          class task_victory status-blocked;
        """
        nodes = extract_mermaid_node_ids(mermaid_code)
        expected = {
            "task_worker_fix",
            "task_reviewer",
            "task_join",
            "task_decision",
            "task_victory",
        }
        self.assertEqual(nodes, expected)
        self.assertNotIn("graph", nodes)
        self.assertNotIn("CoreBoundary", nodes)
        self.assertNotIn("classDef", nodes)
        self.assertNotIn("class", nodes)

    def test_extract_mermaid_node_ids_with_and_syntax(self):
        """Test extraction when multiple nodes are linked with & syntax."""
        mermaid_code = """
        graph LR
          task_a & task_b --> task_c & task_d
        """
        nodes = extract_mermaid_node_ids(mermaid_code)
        self.assertEqual(nodes, {"task_a", "task_b", "task_c", "task_d"})

    def test_validate_mermaid_sync_insync(self):
        """Test validate_mermaid_sync on perfectly synchronized table and diagram."""
        content = """
# Declarative DAG
```mermaid
graph TD
  task_worker_fix["task_worker_fix"]:::status-pending
  task_reviewer["task_reviewer"]:::status-blocked
  task_victory_auditor["task_victory_auditor"]:::status-blocked

  task_worker_fix --> task_reviewer
  task_reviewer --> task_victory_auditor
```

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Fix Worker | series | none | - | - | exit_0 | PENDING |
| `task_reviewer` | Code Review | parallel | task_worker_fix | - | - | review_pass | BLOCKED |
| `task_victory_auditor` | Clean Certification | series | task_reviewer | - | - | victory_cert | BLOCKED |
"""
        result = validate_mermaid_sync(content)
        self.assertTrue(result.valid)
        self.assertTrue(bool(result))
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(result.mermaid_nodes, {"task_worker_fix", "task_reviewer", "task_victory_auditor"})
        self.assertEqual(result.table_nodes, {"task_worker_fix", "task_reviewer", "task_victory_auditor"})

        # Test tuple unpacking
        is_valid, errors = result
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_mermaid_sync_drift_missing_in_mermaid(self):
        """Detect drift when a task in the table is omitted from the Mermaid diagram."""
        content = """
# Declarative DAG
```mermaid
graph TD
  task_worker_fix["task_worker_fix"]:::status-pending
  task_victory_auditor["task_victory_auditor"]:::status-blocked

  task_worker_fix --> task_victory_auditor
```

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Fix Worker | series | none | - | - | exit_0 | PENDING |
| `task_reviewer` | Code Review | parallel | task_worker_fix | - | - | review_pass | BLOCKED |
| `task_victory_auditor` | Clean Certification | series | task_reviewer | - | - | victory_cert | BLOCKED |
"""
        result = validate_mermaid_sync(content)
        self.assertFalse(result.valid)
        self.assertFalse(bool(result))
        self.assertEqual(len(result.errors), 1)
        self.assertIn("task_reviewer", result.errors[0])
        self.assertIn("missing from Mermaid diagram", result.errors[0])

        is_valid, errors = result
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)

    def test_validate_mermaid_sync_drift_extra_in_mermaid(self):
        """Detect drift when a node exists in Mermaid but has no table entry."""
        content = """
# Declarative DAG
```mermaid
graph TD
  task_worker_fix["task_worker_fix"]:::status-pending
  task_ghost["task_ghost"]:::status-pending
  task_victory_auditor["task_victory_auditor"]:::status-blocked

  task_worker_fix --> task_ghost
  task_ghost --> task_victory_auditor
```

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Fix Worker | series | none | - | - | exit_0 | PENDING |
| `task_victory_auditor` | Clean Certification | series | task_worker_fix | - | - | victory_cert | BLOCKED |
"""
        result = validate_mermaid_sync(content)
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("task_ghost", result.errors[0])
        self.assertIn("not declared in task table", result.errors[0])

    def test_validate_mermaid_sync_missing_diagram(self):
        """Test error when markdown has tasks but no Mermaid block."""
        content = """
# Table Only
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_a` | Task A | series | none | - | - | exit_0 | PENDING |
"""
        result = validate_mermaid_sync(content)
        self.assertFalse(result.valid)
        self.assertTrue(any("No Mermaid diagram block found" in e for e in result.errors))

    def test_validate_mermaid_sync_no_tasks(self):
        """Test error when markdown has no valid tasks."""
        content = """
# No Tasks
```mermaid
graph TD
  A --> B
```
"""
        result = validate_mermaid_sync(content)
        self.assertFalse(result.valid)
        self.assertTrue(any("No valid DAG tasks found" in e for e in result.errors))

    def test_dag_validator_class_with_check_mermaid(self):
        """Test DAGValidator class instance with check_mermaid=True."""
        synced_content = """
# DAG
```mermaid
graph TD
  T1["T1"]
  T2["T2"]
  T1 --> T2
```
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Step 1 | series | none | - | - | exit_0 | PASSED |
| T2 | Step 2 | series | T1 | - | - | exit_0 | PENDING |
"""
        drifted_content = """
# DAG
```mermaid
graph TD
  T1["T1"]
```
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| T1 | Step 1 | series | none | - | - | exit_0 | PASSED |
| T2 | Step 2 | series | T1 | - | - | exit_0 | PENDING |
"""
        # When check_mermaid=True on synced DAG
        v_check = DAGValidator(check_mermaid=True)
        rep_synced = v_check.validate(synced_content)
        self.assertTrue(rep_synced.valid, f"Synced DAG should be valid: {rep_synced.errors}")

        # When check_mermaid=True on drifted DAG
        rep_drifted = v_check.validate(drifted_content)
        self.assertFalse(rep_drifted.valid, "Drifted DAG must be marked invalid")
        self.assertTrue(any("T2" in err and "missing from Mermaid diagram" in err for err in rep_drifted.errors))

        # When check_mermaid=False on drifted DAG
        v_no_check = DAGValidator(check_mermaid=False)
        rep_no_check = v_no_check.validate(drifted_content)
        self.assertTrue(rep_no_check.valid, "Without check_mermaid flag, table-only validation passes")

    def test_scaffolded_dags_all_pass_check_mermaid(self):
        """Verify that all topologies generated by scaffold_work pass --check-mermaid without drift."""
        topologies = ["lifecycle", "focused", "review", "full"]
        for topo in topologies:
            proj_dir = os.path.join(self.test_dir, f"proj_{topo}")
            scaffold_work(
                target_dir=proj_dir,
                project_name=f"Proj{topo.capitalize()}",
                milestones=2,
                topology=topo,
                lifecycle=(topo == "lifecycle"),
            )
            dag_file = Path(proj_dir) / ".agents" / "DAG.md"
            self.assertTrue(dag_file.exists(), f"DAG.md must exist for topology {topo}")

            dag_content = dag_file.read_text(encoding="utf-8")
            sync_res = validate_mermaid_sync(dag_content)
            self.assertTrue(
                sync_res.valid,
                f"Topology '{topo}' DAG has Mermaid synchronization drift: {sync_res.errors}",
            )

    def test_cli_check_mermaid_exit_codes_and_json(self):
        """Test CLI execution of dag_validator.py with --check-mermaid flag."""
        # 1. Create in-sync file
        synced_file = Path(self.test_dir) / "synced_dag.md"
        synced_file.write_text("""
# Synced DAG
```mermaid
graph TD
  A["A"]
  B["B"]
  A --> B
```
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Alpha | series | none | - | - | exit_0 | PASSED |
| B | Beta | series | A | - | - | exit_0 | PENDING |
""", encoding="utf-8")

        # CLI on in-sync file -> exit code 0
        cmd_sync = [sys.executable, self.validator_script, str(synced_file), "--check-mermaid"]
        p_sync = subprocess.run(cmd_sync, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p_sync.returncode, 0, f"Expected exit 0 for synced DAG, got {p_sync.returncode}: {p_sync.stderr}")

        # 2. Create drifted file (extra node in mermaid)
        drifted_file = Path(self.test_dir) / "drifted_dag.md"
        drifted_file.write_text("""
# Drifted DAG
```mermaid
graph TD
  A["A"]
  B["B"]
  C_GHOST["C_GHOST"]
  A --> B
```
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| A | Alpha | series | none | - | - | exit_0 | PASSED |
| B | Beta | series | A | - | - | exit_0 | PENDING |
""", encoding="utf-8")

        # CLI on drifted file -> exit code 1
        cmd_drift = [sys.executable, self.validator_script, str(drifted_file), "--check-mermaid"]
        p_drift = subprocess.run(cmd_drift, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p_drift.returncode, 1, f"Expected exit 1 for drifted DAG, got {p_drift.returncode}")
        self.assertIn("C_GHOST", p_drift.stdout)

        # 3. JSON output on drifted file
        cmd_json = [sys.executable, self.validator_script, str(drifted_file), "--check-mermaid", "--json"]
        p_json = subprocess.run(cmd_json, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p_json.returncode, 1)
        data = json.loads(p_json.stdout)
        self.assertFalse(data["valid"])
        self.assertTrue(any("C_GHOST" in err for err in data["errors"]))


if __name__ == "__main__":
    unittest.main()
