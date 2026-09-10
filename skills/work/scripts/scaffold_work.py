#!/usr/bin/env python3
"""
Scaffold Work Swarm Project Layout
Initializes .agents/ directory structure for autonomous multi-agent execution.
"""

import os
import sys
import io
import argparse
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def scaffold_work(target_dir: str, project_name: str, milestones: int):
    agents_dir = os.path.join(target_dir, ".agents")
    sentinel_dir = os.path.join(agents_dir, "sentinel")
    orchestrator_dir = os.path.join(agents_dir, "orchestrator")

    os.makedirs(sentinel_dir, exist_ok=True)
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
Integrity mode: development

## Requirements

### R1. Core Architecture & Foundation
[Define primary deliverable]

### R2. Functional Workflows & Logic
[Define core functionality]

## Acceptance Criteria
- [ ] 100% automated test pass rate
- [ ] Clean build with zero warnings or errors
- [ ] Independent Victory Audit certified
""")
        print(f"Created: {orig_req_path}")

    # 2. Sentinel BRIEFING.md & DISPATCH.md
    sentinel_briefing = os.path.join(sentinel_dir, "BRIEFING.md")
    if not os.path.exists(sentinel_briefing):
        with open(sentinel_briefing, "w", encoding="utf-8") as f:
            f.write(f"""# Sentinel BRIEFING — {now_iso}

## Mission
Executive oversight, liveness monitoring, and mandatory Victory Audit coordination for {project_name}.

## 🔒 My Identity
- Archetype: sentinel
- Working directory: {os.path.abspath(sentinel_dir)}
- Active Orchestrator: [Pending spawn]
- Victory Auditor: [Pending completion]

## 🔒 Key Constraints
- Relay & oversight only; NO technical or architectural decisions.
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
Sentinel initialized. Awaiting Orchestrator spawn and heartbeat scheduling.
""")
        print(f"Created: {sentinel_dispatch}")

    # 3. Orchestrator PROJECT.md, BRIEFING.md, DISPATCH.md, progress.md
    orchestrator_project = os.path.join(orchestrator_dir, "PROJECT.md")
    if not os.path.exists(orchestrator_project):
        milestone_rows = "\n".join([
            f"| M{i} | Milestone {i}: [Title] | [Scope] | {'none' if i == 1 else f'M{i-1}'} | PENDING |"
            for i in range(1, milestones + 1)
        ])
        with open(orchestrator_project, "w", encoding="utf-8") as f:
            f.write(f"""# Project: {project_name}

## Architecture Overview
[High-level architecture, tech stack, and module boundaries]

## Feature Inventory
| ID | Feature Name | Description | Milestone | Ref Requirements |
|----|--------------|-------------|-----------|------------------|
| F1 | Foundation & Core Models | Data structures and foundational interfaces | M1 | R1 |
| F2 | Core Execution Engine | Main business logic and workflows | M2 | R1, R2 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
{milestone_rows}

---

## Interface Contracts & Verification Strategy
- Test Suite: Automated test execution command
- Verification Suite: Deterministic static/end-to-end check script
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
- Binary veto on Forensic Auditor integrity violations.
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

    print(f"\n✅ Successfully initialized Work Swarm workspace at {agents_dir}")

def main():
    parser = argparse.ArgumentParser(description="Scaffold Work Swarm Project Layout")
    parser.add_argument("--project-dir", default=".", help="Root project workspace directory")
    parser.add_argument("--name", default="Project", help="Project name")
    parser.add_argument("--milestones", type=int, default=4, help="Number of initial milestones")
    args = parser.parse_args()

    scaffold_work(args.project_dir, args.name, args.milestones)

if __name__ == "__main__":
    main()
