---
name: work
description: Autonomous, parallel multi-agent swarm execution engine with Sentinel oversight, dispatch-only orchestration, competitive branching, and adversarial verification. Trigger via /work.
---

# Work: Autonomous Multi-Agent Swarm Engineering Engine

Decompose, parallelize, competitively implement, and rigorously verify ambitious software initiatives through an autonomous multi-agent swarm.

---

## 🎯 Goal
Deliver production-grade systems with zero human handholding through a multi-tier agent hierarchy: a relay-only **Sentinel**, a dispatch-only **Project Orchestrator**, parallel **Explorer swarms**, **Competitive Branching Worker Tournaments**, an **Adversarial Committee** (Reviewer, Challenger, Forensic Auditor), and an independent **Victory Auditor**.

---

## 🏗️ Multi-Agent Swarm Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER / PRIMARY THREAD                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Spawns & monitors
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   SENTINEL LAYER (.agents/sentinel/)                   │
│ • Relay-only watchdog; zero technical/architectural bias               │
│ • Heartbeat watchdog cron (schedule '*/10 * * * *')                    │
│ • Mandatory independent Victory Audit gate before reporting completion │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Dispatches
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│             PROJECT ORCHESTRATOR (.agents/orchestrator/)               │
│ • DISPATCH-ONLY invariant: NEVER writes code, NEVER runs tests directly│
│ • Generates PROJECT.md (Features F1..Fn, Milestones M1..Mk, contracts) │
│ • Adaptive Self-Succession: at ~16 spawns, spawns Gen 2 Orchestrator   │
└──────┬───────────────────────────┼──────────────────────────────┬──────┘
       │                           │                              │
       ▼                           ▼                              ▼
┌───────────────┐        ┌───────────────────┐           ┌────────────────┐
│   EXPLORER    │        │    COMPETITIVE    │           │  ADVERSARIAL   │
│     SWARM     │        │ WORKER TOURNAMENT │           │   COMMITTEE    │
│ (2-3 parallel)│ ─────► │ Worker A vs B     │ ────────► │ (Reviewer,     │
│ Surveys code, │        │ Isolated branches │           │  Challenger,   │
│ grounds docs  │        │ Arbiter picks best│           │  Forensic      │
└───────────────┘        └───────────────────┘           │  Auditor)      │
                                                         └───────┬────────┘
                                                                 │
                                     Binary Veto / Remediate ◄───┘
                                     All Passed ──────► Next Milestone
```

---

## 📋 Comprehensive 2-Phase Workflow

### Phase 1: Intent Elicitation & Confidence Stop Gate (Socratic Grill)
Before launching swarm execution, align on intent using Matt Pocock's 1-question Socratic protocol with confidence gating:
1. **Initial Assessment**: Read the user prompt, extract the core objective, and calculate initial confidence score ($0\% \dots 100\%$).
2. **1-Question Socratic Loop**: If confidence $< 95\%$, ask **exactly ONE** high-leverage question at a time via `ask_question` with 2–4 concrete hypotheses:
   - Identify scope boundaries, technology constraints, and deployment targets.
   - Ground against official documentation (Addy Osmani's Source-Driven principle).
   - Once confidence reaches $\ge 95\%$, **STOP grilling immediately** and advance to prompt assembly.
3. **Determine Integrity Mode**:
   - `development`: Standard engineering with full tooling and libraries.
   - `demo`: Polished proof-of-concept showcases with tight visual scope.
   - `benchmark`: Zero shortcuts; strict clean-slate implementation without pre-baked mocks.
4. **Draft Requirements ($R_1 \dots R_n$) & Acceptance Criteria**: Formulate falsifiable, checkable criteria.
5. **Assemble Verbatim Request**: Save the authoritative specification to `.agents/ORIGINAL_REQUEST.md`.

---

### Phase 2: Autonomous Swarm Execution Protocol

#### 1. Sentinel Initialization (`.agents/sentinel/`)
- Initialize `BRIEFING.md` and `DISPATCH.md`.
- Schedule a 10-minute recurring liveness heartbeat cron using `schedule`:
  - `CronExpression: "*/10 * * * *"`
  - `Prompt: "Heartbeat tick: check subagent progress, inspect .agents/orchestrator/progress.md, detect stalled workers, and report status."`
- Spawn the initial **Project Orchestrator** subagent (`Role: "Project Orchestrator"`, `TypeName: "self"`).

#### 2. Orchestrator Decomposition (`.agents/orchestrator/`)
- Read `.agents/ORIGINAL_REQUEST.md`.
- **Survey Phase**: Dispatch 2–3 parallel Explorer subagents:
  - Explorer 1 (Codebase Delta): Existing schemas, ORMs, and patterns.
  - Explorer 2 (Source Grounding): Ground against official docs for third-party libraries.
  - Explorer 3 (Spec Miner): Comprehensive inventory of requirements and non-goals.
- **Master Plan (`PROJECT.md`)**:
  - Feature Inventory: $F_1, F_2, \dots, F_n$ mapped to user requirements.
  - Staged Milestones: $M_1, M_2, \dots, M_k$ (typically 3–6 milestones) with interface contracts.
- **DISPATCH-ONLY Rule**: The orchestrator coordinates and dispatches tasks. It NEVER edits source files or executes build/test tools directly.

#### 3. Staged Milestone Execution Loop
For each milestone $M_i$:
1. **Parallel Explorer Swarm**:
   - Spawn 1–3 Explorers (`.agents/explorer_m{i}_{j}/`).
   - Autowire relevant domain skills from `skills/` or `preferred/` (e.g. `api-and-interface-design`, `observability-and-instrumentation`, `security-and-hardening`).
   - Explorers deliver `handoff.md` blueprints, schemas, and failure modes.
2. **Implementation: Standard or Competitive Branching Tournament**:
   - **Standard Mode**: Single Worker implementer builds code and automated unit/integration tests.
   - **Competitive Tournament Mode** (for complex algorithms, high-risk refactors, or latency-critical paths):
     - Spawn 2 competing Workers in parallel with isolated branches (`Workspace: "branch"` or `.agents/worker_alpha/` vs `.agents/worker_beta/`).
     - Worker Alpha implements Approach A; Worker Beta implements Approach B.
     - An **Arbiter Subagent** runs the shared test suite and benchmark harness across both, compares code elegance (unslop), performance, and robustness, and selects or synthesizes the winning code into the main branch.
3. **Adversarial Committee Gate (Multi-Vantage Verification)**:
   - Spawn in parallel:
     - **Reviewer**: 5-axis code audit (Correctness, Security, Performance, Architecture, Readability/Unslop).
     - **Challenger**: Actively authors empirical attack tests (cross-tenant leakage, race conditions, rate-limiting evasion, malformed inputs) to break the code.
     - **Forensic Integrity Auditor**: Checks for mock facades, cheated tests, hardcoded outputs, or bypassed requirements. Holds **BINARY VETO** power.
4. **Remediation or Gate Convergence**:
   - If findings or vetoes arise: Worker is re-dispatched with explicit failure traces for resolution.
   - When all checks pass: Milestone status in `PROJECT.md` is marked `DONE`.

#### 4. Adaptive Orchestrator Succession
- When orchestrator subagent spawn count reaches 16 (or token pressure increases):
  1. Write generational status report to `.agents/orchestrator/handoff.md`.
  2. Spawn successor Orchestrator Gen $N+1$ passing handoff paths.
  3. Orchestrator Gen $N$ terminates cleanly, preventing context window saturation.

#### 5. Independent Victory Audit
- Orchestrator signals completion to Sentinel.
- Sentinel spawns an independent **Victory Auditor** (`.agents/victory_auditor/`).
- Victory Auditor executes clean-slate verification:
  - Runs full automated test suite (`npm test`, `pytest`).
  - Runs deterministic verification runner (`npm run verify`, `python scripts/verify.py`).
  - Audits git diff and zero-secret hygiene.
- Emits structured verdict: `VICTORY CONFIRMED` or `VICTORY REJECTED`.
- Upon confirmed victory, Sentinel cancels crons, terminates subagents, and presents the completed solution.

---

## 💡 Concrete Example: Scaffolding a Work Project

Initialize the `.agents/` workspace structure programmatically:
```bash
python3.12 skills/work/scripts/scaffold_work.py --project-dir . --name my_feature --milestones 4
```

This scaffolds:
- `.agents/ORIGINAL_REQUEST.md`
- `.agents/sentinel/BRIEFING.md`
- `.agents/orchestrator/PROJECT.md`
- `.agents/orchestrator/BRIEFING.md`
- `.agents/orchestrator/DISPATCH.md`
- `.agents/orchestrator/progress.md`

---

## 🚫 Hard Invariants & Guardrails

*   **NEVER** bypass the independent Victory Audit before reporting completion.
*   **NEVER** allow the Orchestrator to write functional code or execute test runners directly (Dispatch-Only Invariant).
*   **NEVER** permit mock facades or hardcoded return values to satisfy verification (Forensic Auditor Binary Veto).
*   **NEVER** reuse subagents across milestones after delivery of their handoff—always spawn fresh, single-focus subagents.
*   **NEVER** assume ambient global MCP servers—always scope tool configurations under `.agents/plugins/` or invoke local CLIs.
