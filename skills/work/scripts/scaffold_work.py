#!/usr/bin/env python3
"""
Scaffold Work Swarm Project Layout
Initializes .agents/ directory structure for autonomous multi-agent execution
across all 5 Teamwork topologies and 3 Integrity modes.
"""

import os
import sys
import io
import argparse
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def scaffold_work(target_dir: str, project_name: str, milestones: int, topology: str = "full", integrity: str = "development"):
    agents_dir = os.path.join(target_dir, ".agents")
    sentinel_dir = os.path.join(agents_dir, "sentinel")
    orchestrator_dir = os.path.join(agents_dir, "orchestrator")

    os.makedirs(sentinel_dir, exist_ok=True)
    if topology in ("full", "massive", "proof"):
        os.makedirs(orchestrator_dir, exist_ok=True)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. ORIGINAL_REQUEST.md
    orig_req_path = os.path.join(agents_dir, "ORIGINAL_REQUEST.md")
    if not os.path.exists(orig_req_path):
        with open(orig_req_path, "w", encoding="utf-8") as f:
            f.write(f"""# Original User Request — {project_name}

## Initial Request — {now_iso}

[Insert high-level project mission and requirements here]

Working directory: {os.path.abspath(target_dir)}
Topology: {topology}
Integrity mode: {integrity}

## Requirements

### R1. Core Architecture & Deliverable
[Define primary deliverable]

### R2. Functional Workflows & Constraints
[Define core functionality and constraints]

## Acceptance Criteria
- [ ] 100% automated test pass rate with physical exit code 0
- [ ] Forensic integrity verified (zero mock bypasses, zero assertion tampering)
- [ ] Cryptographic SHA-256 evidence logged to .agents/EVIDENCE.md
- [ ] Independent Victory Audit certified
""")
        print(f"Created: {orig_req_path}")

    # 2. EVIDENCE.md (Cryptographic Proof Ledger)
    evidence_path = os.path.join(agents_dir, "EVIDENCE.md")
    if not os.path.exists(evidence_path):
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(f"""# 🛡️ Multi-Agent Forensic Evidence Ledger — {project_name}

- Initialized: {now_iso}
- Topology: `{topology}`
- Integrity Mode: `{integrity}`

Immutable ledger of physical runtime executions, test outputs, and SHA-256 process hashes.

---
""")
        print(f"Created: {evidence_path}")

    # 3. Sentinel BRIEFING.md & DISPATCH.md
    sentinel_briefing = os.path.join(sentinel_dir, "BRIEFING.md")
    if not os.path.exists(sentinel_briefing):
        with open(sentinel_briefing, "w", encoding="utf-8") as f:
            f.write(f"""# Sentinel BRIEFING — {now_iso}

## Mission
Executive oversight, liveness monitoring, and mandatory Victory Audit coordination for {project_name}.

## 🔒 My Identity
- Archetype: sentinel
- Topology: {topology}
- Integrity mode: {integrity}
- Working directory: {os.path.abspath(sentinel_dir)}
- Active Lead / Orchestrator: [Pending spawn]
- Victory Auditor: [Pending completion]

## 🔒 Key Constraints
- Relay & oversight only; NO direct implementation in primary thread.
- Mandatory Victory Audit before reporting completion.
- Monitor progress and liveness via recurring heartbeat crons.
- Clean up subagents and crons upon confirmed victory.

## Project Status
- Phase: initialization
- Crons: [Pending schedule]
- Victory Audit: pending
""")
        print(f"Created: {sentinel_briefing}")

    sentinel_dispatch = os.path.join(sentinel_dir, "DISPATCH.md")
    if not os.path.exists(sentinel_dispatch):
        with open(sentinel_dispatch, "w", encoding="utf-8") as f:
            f.write(f"""# Sentinel DISPATCH Log

## {now_iso}
Sentinel initialized with topology '{topology}' and integrity '{integrity}'.
Awaiting subagent dispatch and heartbeat scheduling.
""")
        print(f"Created: {sentinel_dispatch}")

    # 4. Declarative DAG.md (8-column table with execution modes, artifact contracts & live Mermaid)
    dag_path = os.path.join(agents_dir, "DAG.md")
    if not os.path.exists(dag_path):
        if topology == "focused":
            dag_content = f"""# Declarative DAG: Focused Bugfix Swarm — {project_name}

Topology: focused
Integrity Mode: {integrity}
Last Scheduled: {now_iso}

---

## 📊 Live Mermaid Execution Topology

```mermaid
graph TD
  task_worker_fix["task_worker_fix<br/>[series] <b>PENDING</b>"]:::status-pending
  task_reviewer["task_reviewer<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
  task_challenger["task_challenger<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
  task_forensic_auditor["task_forensic_auditor<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
  task_victory_auditor["task_victory_auditor<br/>[series] <b>BLOCKED</b>"]:::status-blocked

  task_worker_fix --> task_reviewer
  task_worker_fix --> task_challenger
  task_worker_fix --> task_forensic_auditor
  task_reviewer --> task_victory_auditor
  task_challenger --> task_victory_auditor
  task_forensic_auditor --> task_victory_auditor

  classDef status-passed fill:#14532d,stroke:#16a34a,stroke-width:2px,color:#dcfce7;
  classDef status-running fill:#1e3a8a,stroke:#2563eb,stroke-width:2px,color:#dbeafe;
  classDef status-pending fill:#2d3748,stroke:#64748b,stroke-width:1px,color:#f1f5f9;
  classDef status-blocked fill:#78350f,stroke:#d97706,stroke-width:1px,stroke-dasharray: 5 5,color:#fef3c7;
  classDef status-failed fill:#7f1d1d,stroke:#dc2626,stroke-width:2px,color:#fee2e2;
```

---

## 📋 Declarative Task Graph Table

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Bugfix Implementation | series | none | .agents/ORIGINAL_REQUEST.md | src/, tests/, .agents/worker_fix/handoff.md | exit_0 | PENDING |
| `task_reviewer` | 5-Axis Code Review | parallel | task_worker_fix | src/, tests/, .agents/worker_fix/handoff.md | .agents/reviewer_fix/review.md | review_pass | BLOCKED |
| `task_challenger` | Adversarial Boundary Fuzzer | parallel | task_worker_fix | src/, tests/, .agents/worker_fix/handoff.md | tests/, .agents/challenger_fix/handoff.md | exit_0 | BLOCKED |
| `task_forensic_auditor` | AST Anti-Mock Integrity Check | parallel | task_worker_fix | src/, tests/ | .agents/auditor_fix/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_victory_auditor` | Clean-Slate Certification | series | task_reviewer, task_challenger, task_forensic_auditor | .agents/reviewer_fix/review.md, .agents/challenger_fix/handoff.md, .agents/auditor_fix/handoff.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |
"""
        elif topology == "review":
            table_rows = "\n".join([
                "| `task_lead_reviewer` | Lead Document Review | series | none | .agents/ORIGINAL_REQUEST.md | .agents/review_deck/lead_review.md | review_pass | PENDING |",
                "| `task_fact_checker` | Comparative Fact-Checking | parallel | task_lead_reviewer | .agents/review_deck/lead_review.md | .agents/review_deck/fact_check.md | fact_check_pass | BLOCKED |",
                "| `task_inconsistency_inquisitor` | Inconsistency Analysis | parallel | task_lead_reviewer | .agents/review_deck/lead_review.md | .agents/review_deck/inconsistencies.md | analysis_pass | BLOCKED |",
                "| `task_unslop_auditor` | Standards & Unslop Synthesis | series | task_fact_checker, task_inconsistency_inquisitor | .agents/review_deck/fact_check.md, .agents/review_deck/inconsistencies.md | .agents/review_deck/review_deck.md | unslop_clean | BLOCKED |",
            ])
            dag_content = f"""# Declarative DAG: Document Review Swarm — {project_name}

Topology: review
Integrity Mode: {integrity}
Last Scheduled: {now_iso}

---

## 📊 Live Mermaid Execution Topology

```mermaid
graph TD
  task_lead_reviewer["task_lead_reviewer<br/>[series] <b>PENDING</b>"]:::status-pending
  task_fact_checker["task_fact_checker<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
  task_inconsistency_inquisitor["task_inconsistency_inquisitor<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked
  task_unslop_auditor["task_unslop_auditor<br/>[series] <b>BLOCKED</b>"]:::status-blocked

  task_lead_reviewer --> task_fact_checker
  task_lead_reviewer --> task_inconsistency_inquisitor
  task_fact_checker --> task_unslop_auditor
  task_inconsistency_inquisitor --> task_unslop_auditor

  classDef status-passed fill:#14532d,stroke:#16a34a,stroke-width:2px,color:#dcfce7;
  classDef status-running fill:#1e3a8a,stroke:#2563eb,stroke-width:2px,color:#dbeafe;
  classDef status-pending fill:#2d3748,stroke:#64748b,stroke-width:1px,color:#f1f5f9;
  classDef status-blocked fill:#78350f,stroke:#d97706,stroke-width:1px,stroke-dasharray: 5 5,color:#fef3c7;
  classDef status-failed fill:#7f1d1d,stroke:#dc2626,stroke-width:2px,color:#fee2e2;
```

---

## 📋 Declarative Task Graph Table

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
{table_rows}
"""
        else:
            # Multi-milestone swarm DAG
            m_tasks = []
            m_nodes = ['  task_m0_survey["task_m0_survey<br/>[parallel] <b>PENDING</b>"]:::status-pending']
            m_edges = []
            prev_dep = "task_m0_survey"
            prev_out = ".agents/survey/handoff.md"

            for i in range(1, milestones + 1):
                w_id = f"task_m{i}_worker"
                c_id = f"task_m{i}_committee"
                m_nodes.append(f'  {w_id}["{w_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
                m_nodes.append(f'  {c_id}["{c_id}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked')
                m_edges.append(f"  {prev_dep} --> {w_id}")
                m_edges.append(f"  {w_id} --> {c_id}")
                m_tasks.append(f"| `{w_id}` | Milestone {i} Worker | series | {prev_dep} | {prev_out} | src/, tests/, .agents/m{i}_worker/handoff.md | exit_0 | BLOCKED |")
                m_tasks.append(f"| `{c_id}` | Milestone {i} Committee | parallel | {w_id} | src/, tests/, .agents/m{i}_worker/handoff.md | .agents/m{i}_committee/review.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |")
                prev_dep = c_id
                prev_out = f".agents/m{i}_committee/review.md"

            v_id = "task_victory_auditor"
            m_nodes.append(f'  {v_id}["{v_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
            m_edges.append(f"  {prev_dep} --> {v_id}")

            mermaid_lines = "\n".join(m_nodes + [""] + m_edges)
            table_rows = "\n".join([
                "| `task_m0_survey` | Initial Code & Spec Survey | parallel | none | .agents/ORIGINAL_REQUEST.md | .agents/survey/handoff.md | survey_pass | PENDING |"
            ] + m_tasks + [
                f"| `{v_id}` | Clean-Slate Certification | series | {prev_dep} | .agents/EVIDENCE.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |"
            ])

            dag_content = f"""# Declarative Master DAG: Multi-Milestone Swarm — {project_name}

Topology: {topology}
Integrity Mode: {integrity}
Last Scheduled: {now_iso}

---

## 📊 Live Mermaid Execution Topology

```mermaid
graph TD
{mermaid_lines}

  classDef status-passed fill:#14532d,stroke:#16a34a,stroke-width:2px,color:#dcfce7;
  classDef status-running fill:#1e3a8a,stroke:#2563eb,stroke-width:2px,color:#dbeafe;
  classDef status-pending fill:#2d3748,stroke:#64748b,stroke-width:1px,color:#f1f5f9;
  classDef status-blocked fill:#78350f,stroke:#d97706,stroke-width:1px,stroke-dasharray: 5 5,color:#fef3c7;
  classDef status-failed fill:#7f1d1d,stroke:#dc2626,stroke-width:2px,color:#fee2e2;
```

---

## 📋 Declarative Task Graph Table

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
{table_rows}
"""
        with open(dag_path, "w", encoding="utf-8") as f:
            f.write(dag_content)
        print(f"Created: {dag_path}")

    # 5. Topology-specific layout
    if topology == "focused":
        worker_dir = os.path.join(agents_dir, "worker_fix")
        reviewer_dir = os.path.join(agents_dir, "reviewer_fix")
        challenger_dir = os.path.join(agents_dir, "challenger_fix")
        auditor_dir = os.path.join(agents_dir, "auditor_fix")
        victory_dir = os.path.join(agents_dir, "victory_auditor")
        for d in (worker_dir, reviewer_dir, challenger_dir, auditor_dir, victory_dir):
            os.makedirs(d, exist_ok=True)
        print(f"Created focused fix directories: {worker_dir}, {reviewer_dir}, {challenger_dir}, {auditor_dir}, {victory_dir}")

    elif topology == "review":
        review_dir = os.path.join(agents_dir, "review_deck")
        os.makedirs(review_dir, exist_ok=True)
        print(f"Created document review directory: {review_dir}")

    elif topology in ("full", "massive", "proof"):
        # Orchestrator PROJECT.md, BRIEFING.md, DISPATCH.md, progress.md
        orchestrator_project = os.path.join(orchestrator_dir, "PROJECT.md")
        if not os.path.exists(orchestrator_project):
            with open(orchestrator_project, "w", encoding="utf-8") as f:
                f.write(f"""# Project: {project_name}

## Architecture Overview
[High-level architecture, tech stack, and module boundaries]
Topology: {topology} | Integrity: {integrity}

## Feature Inventory
| ID | Feature Name | Description | Milestone | Ref Requirements |
|----|--------------|-------------|-----------|------------------|
| F1 | Foundation & Core Models | Data structures and foundational interfaces | M1 | R1 |
| F2 | Core Execution Engine | Main business logic and workflows | M2 | R1, R2 |

---

## Declarative Task Graph & Execution DAG
Refer to master specification: `.agents/DAG.md`

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
{table_rows}

---

## Interface Contracts & Verification Strategy
- Test Suite: Automated test execution command
- Forensic Command: `python3.12 skills/work/scripts/forensic_audit.py --integrity-mode {integrity}`
- Tournament Tool: `python3.12 skills/work/scripts/arbiter_eval.py`
""")
            print(f"Created: {orchestrator_project}")

        orchestrator_briefing = os.path.join(orchestrator_dir, "BRIEFING.md")
        if not os.path.exists(orchestrator_briefing):
            with open(orchestrator_briefing, "w", encoding="utf-8") as f:
                f.write(f"""# Orchestrator BRIEFING — {now_iso}

## Mission
Orchestrate the end-to-end delivery of {project_name} across {milestones} staged milestones.

## 🔒 My Identity
- Archetype: orchestrator
- Roles: orchestrator, dispatcher, synthesizer, successor
- Working directory: {os.path.abspath(orchestrator_dir)}
- Generation: 1 (Spawn Count: 0)

## 🔒 Key Constraints
- DISPATCH-ONLY: NEVER edit code, NEVER run tests directly.
- Binary veto on Forensic Auditor integrity violations (`skills/work/scripts/forensic_audit.py`).
- Competitive Branching: Dispatch Worker Alpha vs Beta in `Workspace: "branch"`.
- Spawn fresh subagents per task; do not reuse finished agents.
- Self-succeed at 16 spawns, write handoff.md, spawn Gen 2.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
""")
            print(f"Created: {orchestrator_briefing}")

        orchestrator_dispatch = os.path.join(orchestrator_dir, "DISPATCH.md")
        if not os.path.exists(orchestrator_dispatch):
            with open(orchestrator_dispatch, "w", encoding="utf-8") as f:
                f.write(f"""# Orchestrator DISPATCH Log

## {now_iso}
Orchestrator initialized. Ready for Survey Phase dispatch.
""")
            print(f"Created: {orchestrator_dispatch}")

        orchestrator_progress = os.path.join(orchestrator_dir, "progress.md")
        if not os.path.exists(orchestrator_progress):
            progress_items = "\n".join([f"- [ ] Milestone {i}: [Title] (PENDING)" for i in range(1, milestones + 1)])
            with open(orchestrator_progress, "w", encoding="utf-8") as f:
                f.write(f"""## Current Status
Last visited: {now_iso}
Current milestone: M1 (Pending Survey)

## Milestone Checklist
{progress_items}
""")
            print(f"Created: {orchestrator_progress}")

    print(f"\n✅ Successfully initialized Work Swarm workspace at {agents_dir} (Topology: {topology}, Integrity: {integrity})")

def main():
    parser = argparse.ArgumentParser(description="Scaffold Work Swarm Project Layout")
    parser.add_argument("--project-dir", default=".", help="Root project workspace directory")
    parser.add_argument("--name", default="Project", help="Project name")
    parser.add_argument("--milestones", type=int, default=3, help="Number of initial milestones")
    parser.add_argument("--topology", choices=["full", "focused", "review", "proof", "massive"], default="full",
                        help="Swarm topology to initialize")
    parser.add_argument("--integrity", choices=["development", "demo", "benchmark"], default="development",
                        help="Integrity mode enforcement")
    args = parser.parse_args()

    scaffold_work(args.project_dir, args.name, args.milestones, args.topology, args.integrity)

if __name__ == "__main__":
    main()
