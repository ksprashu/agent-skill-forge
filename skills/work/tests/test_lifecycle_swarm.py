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
Unit tests for Full Lifecycle Work Swarm execution, scaffolding, and design arbiter.
Covers:
1. Scaffolding full lifecycle topology (SPEC.md, design proposals, DESIGN.md, lifecycle DAG)
2. DAG validation and Ready Frontier progression through the 7 lifecycle phases
3. Architectural Design Arbiter evaluation, scoring matrix, and trade-off detection
4. Multi-layered review committee gates (Design Review, Code Review, Challenger, Forensic)
5. Acceptance Review and Terminal Victory Certification
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dag_validator import DAGValidator, TaskStatus
from arbiter_eval import evaluate_design_file, score_design_proposals, print_scorecard
from scaffold_work import scaffold_work


class TestLifecycleSwarm(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.validator = DAGValidator(check_artifacts=False, base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scaffold_lifecycle_topology(self):
        proj_dir = os.path.join(self.test_dir, "lifecycle_proj")
        scaffold_work(
            target_dir=proj_dir,
            project_name="TestLifecycle",
            milestones=2,
            topology="lifecycle",
            integrity="development"
        )

        agents_dir = os.path.join(proj_dir, ".agents")
        spec_file = os.path.join(agents_dir, "SPEC.md")
        design_alpha = os.path.join(agents_dir, "design", "proposals", "proposal_alpha.md")
        design_beta = os.path.join(agents_dir, "design", "proposals", "proposal_beta.md")
        design_doc = os.path.join(agents_dir, "design", "DESIGN.md")
        dag_file = os.path.join(agents_dir, "DAG.md")

        self.assertTrue(os.path.exists(spec_file), "SPEC.md must be scaffolded")
        self.assertTrue(os.path.exists(design_alpha), "proposal_alpha.md must be scaffolded")
        self.assertTrue(os.path.exists(design_beta), "proposal_beta.md must be scaffolded")
        self.assertTrue(os.path.exists(design_doc), "DESIGN.md must be scaffolded")
        self.assertTrue(os.path.exists(dag_file), "DAG.md must be scaffolded")

        # Validate DAG
        content = Path(dag_file).read_text(encoding="utf-8")
        report = self.validator.validate(content)
        self.assertTrue(report.valid, f"Scaffolded lifecycle DAG invalid: {report.errors}")

        # Ready frontier MUST start with task_spec_grill
        self.assertEqual(report.ready_frontier, ["task_spec_grill"])

        # Check required lifecycle nodes exist
        self.assertIn("task_spec_grill", report.nodes)
        self.assertIn("task_design_alpha", report.nodes)
        self.assertIn("task_design_beta", report.nodes)
        self.assertIn("task_design_arbiter", report.nodes)
        self.assertIn("task_validation_spike", report.nodes)
        self.assertIn("task_m1_worker", report.nodes)
        self.assertIn("task_m1_design_rev", report.nodes)
        self.assertIn("task_m1_code_rev", report.nodes)
        self.assertIn("task_m1_challenger", report.nodes)
        self.assertIn("task_m1_forensic", report.nodes)
        self.assertIn("task_acceptance_review", report.nodes)
        self.assertIn("task_victory_auditor", report.nodes)

    def test_design_arbiter_evaluation(self):
        # Create test design proposals
        proposal_a = Path(self.test_dir) / "proposal_a.md"
        proposal_b = Path(self.test_dir) / "proposal_b.md"

        proposal_a.write_text("""# Architectural Design Proposal Alpha — In-Memory Store

## 1. Overview & System Topology
In-memory trie-indexed cache architecture for sub-millisecond retrieval.

## 2. Data Models & Schemas
```typescript
interface TrieNode {
  char: string;
  isWord: boolean;
  children: Map<string, TrieNode>;
}
```

## 3. Interface & API Contracts
```typescript
export function searchPrefix(prefix: string): string[];
```

## 4. Failure Modes & Edge Case Resilience
- Concurrency: Read-write mutex lock guards prefix mutations.
- Memory overflow: Strict LRU eviction kicks in at 512MB threshold.

## 5. Explicit Non-Goals & Simplicity
- Out of scope: Persistent disk storage and network clustering.
- Zero external runtime dependencies.

## 6. Trade-Off Analysis & Decision Points
- Trade-off: Maximum throughput at the cost of durability across restarts.
""", encoding="utf-8")

        proposal_b.write_text("""# Architectural Design Proposal Beta — SQLite Virtual Tables

## 1. Overview & System Topology
Relational SQLite FTS5 index architecture providing persistent storage.

## 2. Data Models & Schemas
```sql
CREATE VIRTUAL TABLE prefix_index USING fts5(token, payload);
```

## 3. Interface & API Contracts
```typescript
export function queryTokens(prefix: string): Promise<string[]>;
```

## 4. Failure Modes & Edge Case Resilience
- Concurrency: WAL mode with busy timeout handling.
- Corrupt DB: Automatic checkpoint recovery on cold startup.

## 5. Explicit Non-Goals & Simplicity
- Out of scope: Distributed multi-node clustering.

## 6. Trade-Off Analysis & Decision Points
- [Choice]: In-memory transient speed (Alpha) vs Persistent disk reliability (Beta).
""", encoding="utf-8")

        eval_a = evaluate_design_file("Proposal Alpha", str(proposal_a))
        eval_b = evaluate_design_file("Proposal Beta", str(proposal_b))

        self.assertTrue(eval_a["exists"])
        self.assertTrue(eval_b["exists"])
        self.assertTrue(eval_a["scores"]["total"] >= 70.0)
        self.assertTrue(eval_b["scores"]["total"] >= 70.0)

        score_res = score_design_proposals(eval_a, eval_b)
        self.assertEqual(score_res["type"], "design")
        # Since Proposal B has a [Choice] item, it should trigger user decision required or synthesis
        self.assertIn("recommendation", score_res)

        # Print scorecard and assert disk file creation
        scorecard_out = Path(self.test_dir) / "arbiter_scorecard.md"
        print_scorecard(score_res, str(scorecard_out))
        self.assertTrue(scorecard_out.exists())
        scorecard_text = scorecard_out.read_text(encoding="utf-8")
        self.assertIn("Architectural Design Arbiter Scorecard", scorecard_text)
        self.assertIn("Architecture & Spec Grounding", scorecard_text)
        self.assertIn("Interface & Data Contracts", scorecard_text)

    def test_lifecycle_dag_state_progression(self):
        # Scaffold lifecycle DAG
        proj_dir = os.path.join(self.test_dir, "prog_proj")
        scaffold_work(
            target_dir=proj_dir,
            project_name="ProgTest",
            milestones=1,
            topology="lifecycle"
        )
        dag_file = os.path.join(proj_dir, ".agents", "DAG.md")
        content = Path(dag_file).read_text(encoding="utf-8")

        # Step 1: Initial state -> task_spec_grill is ready
        r1 = self.validator.validate(content)
        self.assertEqual(r1.ready_frontier, ["task_spec_grill"])

        # Step 2: Mark spec_grill as PASSED and unblock parallel design proposals
        c2 = self.validator.update_markdown_content(content, status_updates={
            "task_spec_grill": "PASSED",
            "task_design_alpha": "PENDING",
            "task_design_beta": "PENDING"
        })
        r2 = self.validator.validate(c2)
        self.assertEqual(sorted(r2.ready_frontier), ["task_design_alpha", "task_design_beta"])

        # Step 3: Mark both design proposals as PASSED and unblock arbiter
        c3 = self.validator.update_markdown_content(c2, status_updates={
            "task_design_alpha": "PASSED",
            "task_design_beta": "PASSED",
            "task_design_arbiter": "PENDING"
        })
        r3 = self.validator.validate(c3)
        self.assertEqual(r3.ready_frontier, ["task_design_arbiter"])

        # Step 4: Mark arbiter PASSED and unblock validation spike
        c4 = self.validator.update_markdown_content(c3, status_updates={
            "task_design_arbiter": "PASSED",
            "task_validation_spike": "PENDING"
        })
        r4 = self.validator.validate(c4)
        self.assertEqual(r4.ready_frontier, ["task_validation_spike"])

        # Step 5: Mark spike PASSED and unblock milestone 1 worker
        c5 = self.validator.update_markdown_content(c4, status_updates={
            "task_validation_spike": "PASSED",
            "task_m1_worker": "PENDING"
        })
        r5 = self.validator.validate(c5)
        self.assertEqual(r5.ready_frontier, ["task_m1_worker"])

        # Step 6: Mark worker PASSED and unblock all 4 committee members
        c6 = self.validator.update_markdown_content(c5, status_updates={
            "task_m1_worker": "PASSED",
            "task_m1_design_rev": "PENDING",
            "task_m1_code_rev": "PENDING",
            "task_m1_challenger": "PENDING",
            "task_m1_forensic": "PENDING",
        })
        r6 = self.validator.validate(c6)
        expected_committee = sorted(["task_m1_design_rev", "task_m1_code_rev", "task_m1_challenger", "task_m1_forensic"])
        self.assertEqual(sorted(r6.ready_frontier), expected_committee)

        # Step 7: Mark committee PASSED and unblock acceptance review
        c7 = self.validator.update_markdown_content(c6, status_updates={
            "task_m1_design_rev": "PASSED",
            "task_m1_code_rev": "PASSED",
            "task_m1_challenger": "PASSED",
            "task_m1_forensic": "PASSED",
            "task_acceptance_review": "PENDING",
        })
        r7 = self.validator.validate(c7)
        self.assertEqual(r7.ready_frontier, ["task_acceptance_review"])

        # Step 8: Mark acceptance review PASSED and unblock victory auditor
        c8 = self.validator.update_markdown_content(c7, status_updates={
            "task_acceptance_review": "PASSED",
            "task_victory_auditor": "PENDING",
        })
        r8 = self.validator.validate(c8)
        self.assertEqual(r8.ready_frontier, ["task_victory_auditor"])


if __name__ == "__main__":
    unittest.main()
