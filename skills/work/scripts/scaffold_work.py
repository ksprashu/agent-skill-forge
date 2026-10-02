#!/usr/bin/env python3
"""
Scaffold Work Swarm Project Layout
Initializes .agents/ directory structure for autonomous multi-agent execution
across all Teamwork topologies and Integrity modes.
Supports full lifecycle workflows: Socratic spec grilling, parallel design proposals,
architectural manager evaluation, hypothesis validation spikes, and layered reviews.
"""

import os
import sys
import io
import argparse
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

try:
    from visual_engine.c4_generator import render_c4_component_diagram
    from visual_engine.sequence_generator import render_sequence_diagram
    from visual_engine.what_if_compiler import compile_what_if_simulator
    from visual_engine.manifest import get_baseline_manifest
except ImportError:
    try:
        from .visual_engine.c4_generator import render_c4_component_diagram
        from .visual_engine.sequence_generator import render_sequence_diagram
        from .visual_engine.what_if_compiler import compile_what_if_simulator
        from .visual_engine.manifest import get_baseline_manifest
    except ImportError:
        from visual_engine import (
            render_c4_component_diagram,
            render_sequence_diagram,
            compile_what_if_simulator,
            get_baseline_manifest,
        )

if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and getattr(sys.stderr, "encoding", "").lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

#: Milestone count used when the caller does not name one. ``massive`` exists
#: to decompose work that does not fit in three milestones; defaulting it to
#: three made it indistinguishable from ``full``.
DEFAULT_MILESTONES = {"massive": 8}
FALLBACK_MILESTONES = 3


def resolve_milestones(milestones, topology: str) -> int:
    """Milestone count for a topology, honouring an explicit ``--milestones``."""
    if milestones is not None:
        return milestones
    return DEFAULT_MILESTONES.get(topology, FALLBACK_MILESTONES)


def scaffold_work(target_dir: str, project_name: str, milestones=None, topology: str = "full",
                  integrity: str = "development", lifecycle: bool = False):
    milestones = resolve_milestones(milestones, topology)
    agents_dir = os.path.join(target_dir, ".agents")
    sentinel_dir = os.path.join(agents_dir, "sentinel")
    orchestrator_dir = os.path.join(agents_dir, "orchestrator")
    design_dir = os.path.join(agents_dir, "design")
    proposals_dir = os.path.join(design_dir, "proposals")

    os.makedirs(sentinel_dir, exist_ok=True)
    os.makedirs(proposals_dir, exist_ok=True)

    if topology in ("full", "massive", "proof", "lifecycle"):
        os.makedirs(orchestrator_dir, exist_ok=True)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    is_lifecycle = (topology == "lifecycle") or lifecycle

    # Generate baseline C4 and Sequence diagrams via visual_engine
    alpha_c4_spec = {
        "direction": "TD",
        "diagram_type": "graph",
        "boundaries": [
            {"id": "AlphaBoundary", "label": f"{project_name} Subsystem (Alpha In-Memory)"}
        ],
        "components": [
            {
                "id": "Gateway",
                "name": "API Gateway",
                "technology": "FastAPI / Router",
                "description": "Validates requests & routes in-memory",
                "boundary": "AlphaBoundary",
                "dependencies": ["Engine"],
            },
            {
                "id": "Engine",
                "name": "In-Memory Engine",
                "technology": "Python Core",
                "description": "High-throughput execution engine",
                "boundary": "AlphaBoundary",
                "dependencies": ["StateStore"],
            },
            {
                "id": "StateStore",
                "name": "State Store",
                "technology": "In-Memory RAM / Cache",
                "description": "Zero-IO transient state cache",
                "boundary": "AlphaBoundary",
                "dependencies": [],
            },
        ],
    }
    alpha_c4 = render_c4_component_diagram(alpha_c4_spec)

    alpha_seq_participants = [
        {"id": "Client", "label": "Client / Caller"},
        {"id": "Gateway", "label": "API Gateway"},
        {"id": "Engine", "label": "In-Memory Engine"},
        {"id": "StateStore", "label": "In-Memory Cache"},
    ]
    alpha_seq_steps = [
        {"source": "Client", "target": "Gateway", "message": "Submit Request"},
        {"source": "Gateway", "target": "Engine", "message": "Dispatch Task"},
        {"source": "Engine", "target": "StateStore", "message": "Read / Write Transient State"},
        {"source": "StateStore", "target": "Engine", "message": "State Updated (In-Memory)", "return": True},
        {"source": "Engine", "target": "Gateway", "message": "Execution Result", "return": True},
        {"source": "Gateway", "target": "Client", "message": "Response Ready (Fast)", "return": True},
    ]
    alpha_seq = render_sequence_diagram(alpha_seq_participants, alpha_seq_steps)

    beta_c4_spec = {
        "direction": "TD",
        "diagram_type": "graph",
        "boundaries": [
            {"id": "BetaBoundary", "label": f"{project_name} Subsystem (Beta Modular)"}
        ],
        "components": [
            {
                "id": "Router",
                "name": "Decoupled Router",
                "technology": "Service Router",
                "description": "Dispatches requests to decoupled modules",
                "boundary": "BetaBoundary",
                "dependencies": ["ModularCore"],
            },
            {
                "id": "ModularCore",
                "name": "Modular Core Subsystem",
                "technology": "Decoupled Sub-Package",
                "description": "Manifest-driven modular business logic",
                "boundary": "BetaBoundary",
                "dependencies": ["DiskStorage"],
            },
            {
                "id": "DiskStorage",
                "name": "Persistence Engine",
                "technology": "File System / JSON",
                "description": "Durable write-ahead storage",
                "boundary": "BetaBoundary",
                "dependencies": [],
            },
        ],
    }
    beta_c4 = render_c4_component_diagram(beta_c4_spec)

    beta_seq_participants = [
        {"id": "Client", "label": "Client / Caller"},
        {"id": "Router", "label": "Decoupled Router"},
        {"id": "ModularCore", "label": "Modular Core"},
        {"id": "DiskStorage", "label": "Persistence Engine"},
    ]
    beta_seq_steps = [
        {"source": "Client", "target": "Router", "message": "Submit Request"},
        {"source": "Router", "target": "ModularCore", "message": "Invoke Subsystem"},
        {"source": "ModularCore", "target": "DiskStorage", "message": "Persist State to Disk"},
        {"source": "DiskStorage", "target": "ModularCore", "message": "Disk Write Acknowledged (Sync)", "return": True},
        {"source": "ModularCore", "target": "Router", "message": "Execution Verified", "return": True},
        {"source": "Router", "target": "Client", "message": "Response Confirmed (Durable)", "return": True},
    ]
    beta_seq = render_sequence_diagram(beta_seq_participants, beta_seq_steps)

    design_c4_spec = {
        "direction": "TD",
        "diagram_type": "graph",
        "boundaries": [
            {"id": "SwarmBoundary", "label": f"{project_name} Subsystem Boundary"}
        ],
        "components": [
            {
                "id": "Dispatcher",
                "name": "Hybrid Dispatcher",
                "technology": "Python CLI / Orchestrator",
                "description": "Coordinates lifecycle execution & gates",
                "boundary": "SwarmBoundary",
                "dependencies": ["CoreEngine"],
            },
            {
                "id": "CoreEngine",
                "name": "Decoupled Engine Core",
                "technology": "Modular Python Sub-Package",
                "description": "Executes tasks with in-memory caching and disk sync",
                "boundary": "SwarmBoundary",
                "dependencies": ["Cache", "DiskStore"],
            },
            {
                "id": "Cache",
                "name": "State Cache",
                "technology": "In-Memory RAM",
                "description": "Fast transient state lookups",
                "boundary": "SwarmBoundary",
                "dependencies": [],
            },
            {
                "id": "DiskStore",
                "name": "Durable Store",
                "technology": "Atomic File Persistence",
                "description": "Crash-resilient persistent artifacts",
                "boundary": "SwarmBoundary",
                "dependencies": [],
            },
        ],
    }
    design_c4 = render_c4_component_diagram(design_c4_spec)

    design_seq_participants = [
        {"id": "Sentinel", "label": "Work Sentinel"},
        {"id": "Dispatcher", "label": "Hybrid Dispatcher"},
        {"id": "CoreEngine", "label": "Decoupled Engine Core"},
        {"id": "Storage", "label": "Hybrid Persistence"},
    ]
    design_seq_steps = [
        {"source": "Sentinel", "target": "Dispatcher", "message": "Initialize Swarm Workflow"},
        {"source": "Dispatcher", "target": "CoreEngine", "message": "Execute Staged Milestone"},
        {"source": "CoreEngine", "target": "Storage", "message": "Sync State & Persist Checkpoints"},
        {"source": "Storage", "target": "CoreEngine", "message": "State Persisted (Durable)", "return": True},
        {"source": "CoreEngine", "target": "Dispatcher", "message": "Milestone Verified (Exit 0)", "return": True},
        {"source": "Dispatcher", "target": "Sentinel", "message": "Ready for Gate Review", "return": True},
    ]
    design_seq = render_sequence_diagram(design_seq_participants, design_seq_steps)

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

    # 2. SPEC.md (Authoritative Socratic Specification & Non-Goals)
    spec_path = os.path.join(agents_dir, "SPEC.md")
    if not os.path.exists(spec_path):
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(f"""# Specification & Socratic Context Brief — {project_name}

- Initialized: {now_iso}
- Status: DRAFT / IN_REVIEW
- Topology: `{topology}` | Integrity Mode: `{integrity}`

---

## 1. Objective & Problem Statement
[Define exact problem, users, and core value proposition]

## 2. Socratic Grilling Log (Matt Pocock Alignment Protocol)
| Turn | Hypothesis | Clarifying Question | Confirmed Decision | User Confidence |
|------|------------|---------------------|--------------------|-----------------|
| 1 | [Initial Hypothesis] | [Clarifying Question with Best Guess] | [Confirmed Choice] | >= 95% |

## 3. Official Source Grounding & External Contracts
- Official SDK / Documentation Links:
  - [Service Docs](https://...) -> `Contract Signature`
- Project-Scoped Tooling: CLI tools or plugins under `.agents/plugins/` (zero ambient global MCP assumption).

## 4. Explicit Non-Goals & Scope Boundaries
- [Define explicit non-goal 1]
- [Define explicit non-goal 2]

## 5. Detailed Functional & Interface Requirements
- **R1. Core Interfaces**: [Define request/response schemas, API contracts, types]
- **R2. Resilience & Edge Cases**: [Concurrency, race conditions, retries, error handling]
- **R3. Performance Budget**: [Latency p95 targets, memory bounds]

## 6. Binary Acceptance Criteria Checklist
- [ ] AC1: All functional requirements verified with automated tests (exit code 0).
- [ ] AC2: Interface contracts match approved DESIGN.md without drift.
- [ ] AC3: Zero mock shortcuts or test tampering detected (`forensic_audit.py`).
- [ ] AC4: Cryptographic SHA-256 evidence logged to `.agents/EVIDENCE.md`.
- [ ] AC5: Independent Victory Audit certified clean cold run.
""")
        print(f"Created: {spec_path}")

    # 3. Design Proposals & DESIGN.md
    proposal_alpha_path = os.path.join(proposals_dir, "proposal_alpha.md")
    if not os.path.exists(proposal_alpha_path):
        with open(proposal_alpha_path, "w", encoding="utf-8") as f:
            f.write(f"""# Architectural Design Proposal Alpha — {project_name}

- Author: Design Architect Alpha
- Date: {now_iso}
- Status: PROPOSED

## 1. Overview & System Topology
Proposed in-memory high-throughput architecture prioritizing ultra-low latency and minimal cold-start overhead.

### 1.1 High-Level System Architecture

```mermaid
flowchart TD
  Client["Client / User"] --> Gateway["API Gateway (Alpha)"]
  Gateway --> Engine["In-Memory Core Engine"]
  Engine --> Cache[("In-Memory State Store")]
```

### 1.2 C4 Level 2/3 Component Diagram

{alpha_c4}

### 1.3 Lifecycle Sequence & Dataflow Diagram

{alpha_seq}

## 2. Data Models & Schemas
```typescript
// Define primary interfaces and data contracts
export interface AlphaTaskRequest {{
  taskId: string;
  payload: Record<string, unknown>;
  timestamp: string;
}}

export interface AlphaTaskResult {{
  taskId: string;
  status: "success" | "error";
  latencyMs: number;
}}
```

## 3. Interface & API Contracts
```typescript
// Define endpoint contracts or function signatures
export interface AlphaEngineService {{
  executeTask(req: AlphaTaskRequest): Promise<AlphaTaskResult>;
  getState(taskId: string): Promise<Record<string, unknown> | null>;
}}
```

## 4. Failure Modes & Edge Case Resilience
- Concurrency & Race Conditions: Atomic in-memory operations and lock-free concurrency.
- Error Handling & Retries: In-memory retry loop with exponential backoff before surfacing error.
- Security & Boundary Isolation: Isolated memory spaces per tenant task.

## 5. Explicit Non-Goals & Simplicity
- Out of Scope: Multi-node distributed clustering and heavy database persistence.
- Dependency Footprint: Zero external database dependencies; pure standard library and light runtime.

## 6. Trade-Off Analysis & Decision Points
- **Trade-off A vs B**: Ultra-low latency (Alpha) vs Durable disk persistence (Beta).
- **[Choice]**: Choose between in-memory transient speed and persistent disk storage across restarts.
""")
        print(f"Created: {proposal_alpha_path}")

    proposal_beta_path = os.path.join(proposals_dir, "proposal_beta.md")
    if not os.path.exists(proposal_beta_path):
        with open(proposal_beta_path, "w", encoding="utf-8") as f:
            f.write(f"""# Architectural Design Proposal Beta — {project_name}

- Author: Design Architect Beta
- Date: {now_iso}
- Status: PROPOSED

## 1. Overview & System Topology
Proposed modular, decoupled architecture prioritizing maximum durability, persistence, and auditability.

### 1.1 High-Level System Architecture

```mermaid
flowchart TD
  Client["Client / User"] --> Router["Decoupled Router (Beta)"]
  Router --> ModularCore["Modular Subsystem Core"]
  ModularCore --> DiskStorage[("Durable File / Disk Store")]
```

### 1.2 C4 Level 2/3 Component Diagram

{beta_c4}

### 1.3 Lifecycle Sequence & Dataflow Diagram

{beta_seq}

## 2. Data Models & Schemas
```typescript
// Define alternative interfaces and data contracts
export interface BetaTaskRequest {{
  requestId: string;
  manifestPath: string;
  options: {{
    persist: boolean;
    sync: boolean;
  }};
}}

export interface BetaTaskResult {{
  requestId: string;
  persistedArtifacts: string[];
  durabilityScore: number;
}}
```

## 3. Interface & API Contracts
```typescript
// Define endpoint contracts or function signatures
export interface BetaModularService {{
  processManifest(req: BetaTaskRequest): Promise<BetaTaskResult>;
  recoverSession(sessionId: string): Promise<boolean>;
}}
```

## 4. Failure Modes & Edge Case Resilience
- Concurrency & Race Conditions: File locking and atomic rename patterns for disk state.
- Error Handling & Retries: Crash-recovery journaling and automatic checkpoint replay.
- Security & Boundary Isolation: Strict sandbox path validation preventing directory traversal.

## 5. Explicit Non-Goals & Simplicity
- Out of Scope: Complex relational databases or distributed consensus clusters.
- Dependency Footprint: Self-contained file-based storage using robust standard libraries.

## 6. Trade-Off Analysis & Decision Points
- **Trade-off A vs B**: In-memory transient speed (Alpha) vs Persistent disk reliability (Beta).
- **[Choice]**: Prioritize durable persistence across crashes vs raw in-memory operation speed.
""")
        print(f"Created: {proposal_beta_path}")

    design_doc_path = os.path.join(design_dir, "DESIGN.md")
    if not os.path.exists(design_doc_path):
        with open(design_doc_path, "w", encoding="utf-8") as f:
            f.write(f"""# Authoritative Technical Design Document — {project_name}

- Approved Date: {now_iso}
- Arbiter / Manager: Architectural Arbiter
- Status: PENDING_SYNTHESIS

## 1. Approved Architecture & Selected Approach
Synthesized hybrid architecture combining decoupled modular engines with high-DPI visual rendering and dual caching/durability guarantees.

### 1.1 High-Level System Architecture

```mermaid
flowchart TD
  Client["Client / Orchestrator"] --> Dispatcher["Hybrid Dispatcher"]
  Dispatcher --> CoreEngine["Decoupled Engine Core"]
  CoreEngine --> Cache[("In-Memory State Cache")]
  CoreEngine --> Disk[("Durable Disk Persistence")]
```

### 1.2 C4 Level 3 Component Block Diagram

{design_c4}

### 1.3 Lifecycle Sequence & Dataflow Diagram

{design_seq}

## 2. Data Models & Interface Contracts
[Final data models, database schemas, and API contracts]

## 3. Failure Modes, Concurrency & Security
[Guaranteed edge case handling, locking strategies, and security gates]

## 4. Trade-Off Resolutions & User Decisions
[Record resolutions of user decision cards and arbiter evidence reports]

## 5. Validation Spike & Implementation Milestones
[Summary of validation spikes executed and target milestone breakdown]
""")
        print(f"Created: {design_doc_path}")

    # Baseline What-If Simulator in lifecycle mode
    if is_lifecycle:
        simulator_path = os.path.join(design_dir, "what_if_simulator.html")
        if not os.path.exists(simulator_path):
            manifest = get_baseline_manifest(project_name)
            sim_html = compile_what_if_simulator(manifest)
            with open(simulator_path, "w", encoding="utf-8") as f:
                f.write(sim_html)
            print(f"Created: {simulator_path}")

    # 4. EVIDENCE.md (Cryptographic Proof Ledger)
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

    # 5. Sentinel BRIEFING.md & DISPATCH.md
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
- Socratic Spec Grilling: Interview user until confidence >= 95%.
- User Decision Gates: Present trade-off choice cards to user when architects diverge.
- Mandatory Victory Audit before reporting completion.
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

    # 6. Declarative DAG.md
    dag_path = os.path.join(agents_dir, "DAG.md")
    if not os.path.exists(dag_path):
        is_lifecycle = (topology == "lifecycle") or lifecycle

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
        elif is_lifecycle:
            # Full Lifecycle DAG: Spec Grill -> Parallel Design Alpha/Beta -> Arbiter -> Validation Spike -> Milestones -> Multi-Review Committee -> Acceptance Review -> Victory
            m_tasks = []
            m_nodes = [
                '  task_spec_grill["task_spec_grill<br/>[series] <b>PENDING</b>"]:::status-pending',
                '  task_design_alpha["task_design_alpha<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                '  task_design_beta["task_design_beta<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                '  task_design_arbiter["task_design_arbiter<br/>[series] <b>BLOCKED</b>"]:::status-blocked',
                '  task_validation_spike["task_validation_spike<br/>[series] <b>BLOCKED</b>"]:::status-blocked',
            ]
            m_edges = [
                '  task_spec_grill --> task_design_alpha',
                '  task_spec_grill --> task_design_beta',
                '  task_design_alpha --> task_design_arbiter',
                '  task_design_beta --> task_design_arbiter',
                '  task_design_arbiter --> task_validation_spike',
            ]

            init_tasks = [
                "| `task_spec_grill` | Socratic Spec Grilling | series | none | .agents/ORIGINAL_REQUEST.md | .agents/SPEC.md | spec_approved | PENDING |",
                "| `task_design_alpha` | Architecture Proposal Alpha | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_alpha.md | design_pass | BLOCKED |",
                "| `task_design_beta` | Architecture Proposal Beta | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_beta.md | design_pass | BLOCKED |",
                "| `task_design_arbiter` | Design Arbiter & User Decision Gate | series | task_design_alpha, task_design_beta | .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md | .agents/design/DESIGN.md, .agents/design/arbiter_evidence.md | arbiter_pass | BLOCKED |",
                "| `task_validation_spike` | Prototyping & Feasibility Spike | series | task_design_arbiter | .agents/design/DESIGN.md | .agents/design/spike_results.md | spike_pass | BLOCKED |",
            ]

            prev_dep = "task_validation_spike"
            prev_out = ".agents/design/spike_results.md"

            for i in range(1, milestones + 1):
                w_id = f"task_m{i}_worker"
                d_rev = f"task_m{i}_design_rev"
                c_rev = f"task_m{i}_code_rev"
                chal = f"task_m{i}_challenger"
                forn = f"task_m{i}_forensic"

                m_nodes.extend([
                    f'  {w_id}["{w_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked',
                    f'  {d_rev}["{d_rev}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                    f'  {c_rev}["{c_rev}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                    f'  {chal}["{chal}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                    f'  {forn}["{forn}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked',
                ])
                m_edges.extend([
                    f"  {prev_dep} --> {w_id}",
                    f"  {w_id} --> {d_rev}",
                    f"  {w_id} --> {c_rev}",
                    f"  {w_id} --> {chal}",
                    f"  {w_id} --> {forn}",
                ])

                m_tasks.append(f"| `{w_id}` | Milestone {i} Worker | series | {prev_dep} | {prev_out} | src/, tests/, .agents/m{i}_worker/handoff.md | exit_0 | BLOCKED |")
                m_tasks.append(f"| `{d_rev}` | Milestone {i} Design Review | parallel | {w_id} | .agents/design/DESIGN.md, src/ | .agents/m{i}_design_rev/review.md | design_pass | BLOCKED |")
                m_tasks.append(f"| `{c_rev}` | Milestone {i} 5-Axis Code Review | parallel | {w_id} | src/, tests/, .agents/m{i}_worker/handoff.md | .agents/m{i}_code_rev/review.md | review_pass | BLOCKED |")
                m_tasks.append(f"| `{chal}` | Milestone {i} Adversarial Challenger | parallel | {w_id} | src/, tests/, .agents/m{i}_worker/handoff.md | tests/, .agents/m{i}_challenger/handoff.md | exit_0 | BLOCKED |")
                m_tasks.append(f"| `{forn}` | Milestone {i} Forensic Integrity Auditor | parallel | {w_id} | src/, tests/ | .agents/m{i}_forensic/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |")

                prev_dep = f"{d_rev}, {c_rev}, {chal}, {forn}"
                prev_out = f".agents/m{i}_code_rev/review.md"

            accept_id = "task_acceptance_review"
            m_nodes.append(f'  {accept_id}["{accept_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
            for part in prev_dep.split(", "):
                m_edges.append(f"  {part} --> {accept_id}")

            v_id = "task_victory_auditor"
            m_nodes.append(f'  {v_id}["{v_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
            m_edges.append(f"  {accept_id} --> {v_id}")

            mermaid_lines = "\n".join(m_nodes + [""] + m_edges)
            table_rows = "\n".join(init_tasks + m_tasks + [
                f"| `{accept_id}` | Acceptance Review against SPEC.md | series | {prev_dep} | .agents/SPEC.md, .agents/EVIDENCE.md | .agents/acceptance_review/report.md | acceptance_pass | BLOCKED |",
                f"| `{v_id}` | Clean-Slate Terminal Victory Certification | series | {accept_id} | .agents/EVIDENCE.md, .agents/acceptance_review/report.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |",
            ])

            dag_content = f"""# Declarative Master DAG: Full Lifecycle Swarm — {project_name}

Topology: lifecycle
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
        else:
            # Multi-milestone swarm DAG, shared by the full, massive and proof
            # topologies. They differ in exactly two ways, and nothing else:
            #   full    — one committee node per milestone.
            #   massive — same shape, more milestones by default.
            #   proof   — the committee is split into three separately gated
            #             verifiers, and a validation spike runs before any
            #             milestone starts. More nodes, more independent gates,
            #             for work where a single committee verdict is too
            #             coarse to trust.
            # Until 2026-09-23 all three emitted byte-identical DAGs, so two of
            # the six advertised topologies were names with nothing behind them.
            split_committee = (topology == "proof")

            m_tasks = []
            m_nodes = ['  task_m0_survey["task_m0_survey<br/>[parallel] <b>PENDING</b>"]:::status-pending']
            m_edges = []
            prev_dep = "task_m0_survey"
            prev_out = ".agents/survey/handoff.md"

            if split_committee:
                s_id = "task_validation_spike"
                m_nodes.append(f'  {s_id}["{s_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
                m_edges.append(f"  {prev_dep} --> {s_id}")
                m_tasks.append(f"| `{s_id}` | Validation Spike | series | {prev_dep} | {prev_out} | .agents/design/spike_results.md | spike_pass | BLOCKED |")
                prev_dep = s_id
                prev_out = ".agents/design/spike_results.md"

            for i in range(1, milestones + 1):
                w_id = f"task_m{i}_worker"
                m_nodes.append(f'  {w_id}["{w_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
                m_edges.append(f"  {prev_dep} --> {w_id}")
                m_tasks.append(f"| `{w_id}` | Milestone {i} Worker | series | {prev_dep} | {prev_out} | src/, tests/, .agents/m{i}_worker/handoff.md | exit_0 | BLOCKED |")

                if split_committee:
                    verifiers = [
                        (f"task_m{i}_code_rev", f"Milestone {i} 5-Axis Code Review",
                         f".agents/m{i}_code_rev/review.md", "review_pass"),
                        (f"task_m{i}_challenger", f"Milestone {i} Adversarial Challenger",
                         f".agents/m{i}_challenger/handoff.md", "exit_0"),
                        (f"task_m{i}_forensic", f"Milestone {i} Forensic Integrity Auditor",
                         f".agents/m{i}_forensic/handoff.md, .agents/EVIDENCE.md", "zero_mock"),
                    ]
                    for v_node, v_name, v_out, v_gate in verifiers:
                        m_nodes.append(f'  {v_node}["{v_node}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked')
                        m_edges.append(f"  {w_id} --> {v_node}")
                        m_tasks.append(f"| `{v_node}` | {v_name} | parallel | {w_id} | src/, tests/, .agents/m{i}_worker/handoff.md | {v_out} | {v_gate} | BLOCKED |")
                    j_id = f"task_m{i}_join"
                    joined = ", ".join(v[0] for v in verifiers)
                    m_nodes.append(f'  {j_id}["{j_id}<br/>[series] <b>BLOCKED</b>"]:::status-blocked')
                    for v_node, _, _, _ in verifiers:
                        m_edges.append(f"  {v_node} --> {j_id}")
                    m_tasks.append(f"| `{j_id}` | Milestone {i} Verification Join | series | {joined} | .agents/m{i}_code_rev/review.md, .agents/m{i}_challenger/handoff.md, .agents/m{i}_forensic/handoff.md | .agents/m{i}_join/verdict.md | committee_join | BLOCKED |")
                    prev_dep = j_id
                    prev_out = f".agents/m{i}_join/verdict.md"
                else:
                    c_id = f"task_m{i}_committee"
                    m_nodes.append(f'  {c_id}["{c_id}<br/>[parallel] <b>BLOCKED</b>"]:::status-blocked')
                    m_edges.append(f"  {w_id} --> {c_id}")
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

    # 7. Topology-specific layout
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

    elif topology in ("full", "massive", "proof", "lifecycle"):
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
- Socratic Spec & Parallel Design Proposals: coordinate proposals before full build.
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
    parser.add_argument("--milestones", type=int, default=None,
                        help="Number of initial milestones (default: 3, or 8 for --topology massive)")
    parser.add_argument("--topology", choices=["full", "focused", "review", "proof", "massive", "lifecycle"], default="full",
                        help="Swarm topology to initialize: lifecycle (spec grill through victory), "
                             "full (survey, milestone workers, one committee each), "
                             "proof (full plus a validation spike and three separately gated verifiers "
                             "per milestone), massive (full at 8 milestones), "
                             "focused (single bugfix plus committee), review (document review deck)")
    parser.add_argument("--integrity", choices=["development", "demo", "benchmark"], default="development",
                        help="Integrity mode enforcement")
    parser.add_argument("--lifecycle", action="store_true", help="Enable full lifecycle DAG (spec grill, parallel designs, spikes, acceptance review)")
    args = parser.parse_args()

    scaffold_work(args.project_dir, args.name, args.milestones, args.topology, args.integrity, args.lifecycle)

if __name__ == "__main__":
    main()
