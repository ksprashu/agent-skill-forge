---
name: work
description: Autonomous, parallel multi-agent swarm execution engine with Sentinel oversight, Socratic spec grilling, parallel design proposals, arbiter tournaments, user decision gates, hypothesis validation spikes, declarative DAG execution, and layered verification. Trigger via /work.
disable-model-invocation: true
---

# Work: Autonomous Multi-Agent Swarm Engineering Engine

Decompose, parallelize, competitively design, empirically validate, and rigorously verify ambitious software initiatives through an autonomous multi-agent swarm.

---

## 🛑 MANDATORY: Primary Thread Invariant (You are the Sentinel)

> [!IMPORTANT]
> **PRIMARY THREAD DELEGATION INVARIANT**:
> When `/work` (or `/teamwork`, `/teamwork-preview`, `/team`, `/swarm`) is triggered:
> 1. **Your Identity**: In this primary conversation thread, you operate strictly as the **Work Sentinel & User Liaison**.
> 2. **Strict Prohibition on Direct Implementation**: You are **STRICTLY FORBIDDEN** from inspecting source files to fix bugs yourself, writing code, editing files, or running test runners directly on the primary thread.
> 3. **Bypassing Delegation is Prohibited**: If you write or edit project code yourself in this thread instead of delegating to subagents, you have violated the `/work` contract.
> 4. **Mandatory Two-Phase Workflow**:
>    - **Phase 1**: Socratic Spec Grilling, authoring `.agents/SPEC.md` and `.agents/ORIGINAL_REQUEST.md`, and scaffolding `.agents/`.
>    - **Phase 2**: **DELEGATE via `invoke_subagent`**. Both phases are required — crafting without delegation is incomplete!

---

## 🏗️ Multi-Agent Swarm Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│             PRIMARY THREAD (YOU — THE WORK SENTINEL)                   │
│ • Socratic Spec Grilling (1 question at a time until >= 95% confidence)│
│ • Never writes functional code; relay-only user liaison                │
│ • Scaffolds .agents/ layout & schedules liveness heartbeat cron        │
│ • Presents Architectural Choice Cards to user via ask_question         │
│ • DELEGATES execution via invoke_subagent                              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ invoke_subagent
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│             PROJECT ORCHESTRATOR (.agents/orchestrator/)               │
│ • DISPATCH-ONLY: NEVER writes code, NEVER runs tests directly          │
│ • Resolves Ready Frontier from .agents/DAG.md                          │
│ • Adaptive Self-Succession: at ~16 spawns, spawns Gen 2 Orchestrator   │
└──────┬───────────────────────────┼──────────────────────────────┬──────┘
       │                           │                              │
       ▼                           ▼                              ▼
┌───────────────┐        ┌───────────────────┐           ┌────────────────┐
│PARALLEL DESIGN│        │VALIDATION SPIKES &│           │ LAYERED REVIEW │
│  TOURNAMENT   │        │TOURNAMENT WORKERS │           │   COMMITTEE    │
│Architect A vs │ ─────► │Empirical branch   │ ────────► │• Design Review │
│Architect B    │        │spikes & benchmarks│           │• 5-Axis Code   │
│Arbiter scores │        │synthesized into   │           │• Challenger    │
│User chooses   │        │production mainline│           │• Forensic AST  │
└───────────────┘        └───────────────────┘           └───────┬────────┘
                                                                 │
                                     Acceptance Review ◄─────────┘
                                     (Audits all SPEC.md ACs)
                                                                 │
                                     Victory Auditor ◄───────────┘
                                     (Clean cold-run certification)
```

---

## 📋 The Sentinel's 7-Phase Execution Lifecycle

### Phase 1: Intent Elicitation & Socratic Spec Grilling
1. **Intake & Assess User Request**: Record verbatim prompt into `.agents/ORIGINAL_REQUEST.md`.
2. **Socratic Grilling Protocol**:
   - If requirements, constraints, or non-goals contain ambiguity, interview the user using Matt Pocock Socratic protocols (state hypothesis, state confidence, ask **exactly ONE** high-leverage question with recommended answer).
   - Continue grilling until confidence $\ge 95\%$ or until the user explicitly signals approval.
3. **Compile `.agents/SPEC.md`**:
   - Document Objective, Official Source Grounding, Explicit Non-Goals, Functional Requirements ($R_1 \dots R_n$), and Binary Acceptance Criteria checkboxes.
4. **Scaffold Layout**:
   ```bash
   python3.12 skills/work/scripts/scaffold_work.py --project-dir . --name <ProjectName> --topology lifecycle --integrity development
   ```
5. **Schedule Heartbeat Watchdog**:
   Schedule a 10-minute recurring liveness cron via `schedule`:
   ```json
   {
     "CronExpression": "*/10 * * * *",
     "IsDaemon": false,
     "Prompt": "Heartbeat tick: inspect subagent progress, examine .agents/DAG.md and .agents/orchestrator/progress.md, detect stalled workers, and report status."
   }
   ```

---

### Phase 2: Parallel Alternative Technical Design Proposals
1. **Dispatch Parallel Design Architects**:
   - The Orchestrator spawns `Design Architect Alpha` and `Design Architect Beta` concurrently to author distinct architectural approaches in `.agents/design/proposals/proposal_alpha.md` and `proposal_beta.md`.
2. **Design Rubric Scoring**:
   - The Architectural Arbiter evaluates both proposals across 4 axes using `scripts/arbiter_eval.py`:
     1. Architecture & Spec Grounding (30 pts)
     2. Interface & Data Contract Rigor (25 pts)
     3. Failure Modes & Resilience (25 pts)
     4. Simplicity & Unslop (20 pts)
   - Outputs `.agents/design/arbiter_scorecard.md`.

---

### Phase 3: Architectural Manager Evaluation & User Decision Gate
1. **User Choice Escalation**:
   - If the Arbiter discovers fundamental trade-offs (e.g. In-Memory Speed vs SQLite Persistence, REST vs GraphQL, Client vs Server State), it flags `USER_DECISION_REQUIRED`.
   - The Sentinel presents an interactive choice modal to the user via `ask_question`.
2. **Authoritative Synthesis**:
   - Synthesize the winning architecture, resolved trade-offs, and concrete schemas into `.agents/design/DESIGN.md`.

---

### Phase 4: Prototyping Spikes & Hypothesis Validation Tournaments
1. **Empirical Feasibility Probes**:
   - For high-risk assumptions, latency budgets, or novel libraries, dispatch a prototype worker in an isolated branch (`Workspace: "branch"`).
   - Run micro-benchmarks or proof-of-concept tests.
   - Record results in `.agents/design/spike_results.md` satisfying the barrier gate (`spike_pass`).

---

### Phase 5: Declarative Task DAG Decomposition
- Compile the approved `DESIGN.md` into vertical implementation milestones ($M_1 \dots M_k$) in `.agents/DAG.md`.
- Validate graph acyclicity and contract validity:
  ```bash
  python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md
  ```

---

### Phase 6: Staged Implementation & Testing
- Dispatches implementation workers sequentially per milestone.
- Workers author production code, write automated unit/integration tests, and verify physical exit code 0.
- Reports delivery in `.agents/m{i}_worker/handoff.md`.

---

### Phase 7: Multi-Perspective Layered Verification & Acceptance Gate
Upon milestone completion, the Orchestrator dispatches the 4-member Verification Committee concurrently:
1. **Architectural Design Reviewer**: Audits git diff against `.agents/design/DESIGN.md` to prevent architectural drift or interface leaks (`design_pass`).
2. **5-Axis Code Reviewer**: Audits Correctness, Security, Performance, Architecture, and Readability/Unslop (`review_pass`).
3. **Adversarial Challenger**: Executes hostile edge tests, concurrency stress, and race-condition probes (`exit_0`).
4. **Forensic Integrity Auditor**: Runs `forensic_audit.py` to enforce zero synthetic mock facades and log SHA-256 evidence to `.agents/EVIDENCE.md` (`zero_mock`).
5. **Acceptance Reviewer**: Systematically audits all acceptance criteria in `.agents/SPEC.md`, producing `.agents/acceptance_review/report.md` (`acceptance_pass`).
6. **Victory Auditor**: Independent clean-slate cold run producing final sign-off (`victory_cert`).

---

## 📊 Declarative Markdown DAG Task Specification Standard

All workflows in `/work` are governed by a standardized, human-readable, model-parseable Markdown DAG specification (`.agents/DAG.md` or embedded in `.agents/orchestrator/PROJECT.md`).

### 1. Specification Schema
The task graph is declared using an 8-column GFM Markdown table:
`| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |`

- **Execution Modes**:
  - `series`: Synchronously blocking sequential execution.
  - `parallel`: Concurrently executable alongside ready sibling nodes once dependencies pass.
  - `async_background`: Non-blocking watchdog, liveness monitor, or performance telemetry collector.
- **Topological Dependencies (`Depends On`)**:
  - Comma-separated list of prerequisite Task IDs or `none`.
- **Artifact & Data Flow Contracts (`Inputs` / `Outputs`)**:
  - **Inputs**: Physical files that MUST exist on disk before dispatch (anti-polling invariant).
  - **Outputs**: Physical deliverables guaranteed to exist upon task completion.
- **Barrier Gates (`Gate`)**:
  - Deterministic criteria: `spec_approved`, `design_pass`, `arbiter_pass`, `spike_pass`, `exit_0`, `review_pass`, `zero_mock`, `acceptance_pass`, `victory_cert`.
- **Node Status States (`Status`)**:
  - `PENDING`, `RUNNING`, `PASSED`, `BLOCKED`, `FAILED`.

---

## 📐 Canonical DAG Templates

### Template 1: Full Lifecycle Engineering Swarm (`--topology lifecycle`)
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_spec_grill` | Socratic Spec Grilling | series | none | .agents/ORIGINAL_REQUEST.md | .agents/SPEC.md | spec_approved | PENDING |
| `task_design_alpha` | Architecture Proposal Alpha | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_alpha.md | design_pass | BLOCKED |
| `task_design_beta` | Architecture Proposal Beta | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_beta.md | design_pass | BLOCKED |
| `task_design_arbiter` | Design Arbiter & User Decision Gate | series | task_design_alpha, task_design_beta | .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md | .agents/design/DESIGN.md, .agents/design/arbiter_scorecard.md | arbiter_pass | BLOCKED |
| `task_validation_spike` | Prototyping & Feasibility Spike | series | task_design_arbiter | .agents/design/DESIGN.md | .agents/design/spike_results.md | spike_pass | BLOCKED |
| `task_m1_worker` | Milestone 1 Worker | series | task_validation_spike | .agents/design/DESIGN.md | src/, tests/, .agents/m1_worker/handoff.md | exit_0 | BLOCKED |
| `task_m1_design_rev` | Milestone 1 Design Review | parallel | task_m1_worker | .agents/design/DESIGN.md, src/ | .agents/m1_design_rev/review.md | design_pass | BLOCKED |
| `task_m1_code_rev` | Milestone 1 5-Axis Code Review | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_code_rev/review.md | review_pass | BLOCKED |
| `task_m1_challenger` | Milestone 1 Adversarial Challenger | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | tests/, .agents/m1_challenger/handoff.md | exit_0 | BLOCKED |
| `task_m1_forensic` | Milestone 1 Forensic Integrity Auditor | parallel | task_m1_worker | src/, tests/ | .agents/m1_forensic/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_acceptance_review` | Acceptance Review against SPEC.md | series | task_m1_design_rev, task_m1_code_rev, task_m1_challenger, task_m1_forensic | .agents/SPEC.md, .agents/EVIDENCE.md | .agents/acceptance_review/report.md | acceptance_pass | BLOCKED |
| `task_victory_auditor` | Clean-Slate Victory Audit | series | task_acceptance_review | .agents/EVIDENCE.md, .agents/acceptance_review/report.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |
```

### Template 2: Focused Bugfix Swarm (`--topology focused`)
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Bugfix Implementation | series | none | .agents/ORIGINAL_REQUEST.md | src/, tests/, .agents/worker_fix/handoff.md | exit_0 | PENDING |
| `task_reviewer` | 5-Axis Code Review | parallel | task_worker_fix | src/, tests/, .agents/worker_fix/handoff.md | .agents/reviewer_fix/review.md | review_pass | BLOCKED |
| `task_challenger` | Adversarial Boundary Fuzzer | parallel | task_worker_fix | src/, tests/, .agents/worker_fix/handoff.md | tests/, .agents/challenger_fix/handoff.md | exit_0 | BLOCKED |
| `task_forensic_auditor` | AST Anti-Mock Integrity Check | parallel | task_worker_fix | src/, tests/ | .agents/auditor_fix/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_victory_auditor` | Clean-Slate Certification | series | task_reviewer, task_challenger, task_forensic_auditor | .agents/reviewer_fix/review.md, .agents/challenger_fix/handoff.md, .agents/auditor_fix/handoff.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |
```

---

## 🚀 Swarm Dispatch Payloads

### 1. Design Architect Subagents (Parallel Proposals)
```json
{
  "Subagents": [
    {
      "Role": "Design Architect Alpha",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are Design Architect Alpha.\nAuthoritative specification: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_alpha.md\n\nFollow skills/work/references/competitive_branching.md:\nAuthor a modular, robust architectural proposal with explicit schemas, interfaces, error handling, and trade-offs. Send completion message when written."
    },
    {
      "Role": "Design Architect Beta",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are Design Architect Beta.\nAuthoritative specification: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_beta.md\n\nFollow skills/work/references/competitive_branching.md:\nAuthor an alternative architectural proposal exploring distinct storage, concurrency, or interface paradigms with clear trade-offs. Send completion message when written."
    }
  ]
}
```

### 2. Architectural Arbiter & Synthesizer
```json
{
  "Subagents": [
    {
      "Role": "Architectural Arbiter",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Architectural Arbiter.\nRequired Inputs: .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md\n\nFollow skills/work/references/competitive_branching.md:\n1. Run: python3.12 skills/work/scripts/arbiter_eval.py --design-alpha .agents/design/proposals/proposal_alpha.md --design-beta .agents/design/proposals/proposal_beta.md --output-scorecard .agents/design/arbiter_scorecard.md\n2. If trade-offs require user decision, signal Sentinel with options.\n3. Synthesize winning architecture into .agents/design/DESIGN.md.\n4. Send completion message referencing DESIGN.md."
    }
  ]
}
```

### 3. Layered Verification Committee (Parallel Batch)
```json
{
  "Subagents": [
    {
      "Role": "Architectural Design Reviewer",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "Audit git diff against .agents/design/DESIGN.md for interface drift and boundary violations. Output .agents/m1_design_rev/review.md."
    },
    {
      "Role": "5-Axis Code Reviewer",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "Audit diff across Correctness, Security, Performance, Architecture, and Readability/Unslop. Output .agents/m1_code_rev/review.md."
    },
    {
      "Role": "Adversarial Challenger",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "Author hostile edge-case and boundary tests. Assert exit code 0. Output .agents/m1_challenger/handoff.md."
    },
    {
      "Role": "Forensic Integrity Auditor",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "Run: python3.12 skills/work/scripts/forensic_audit.py --integrity-mode development --strict\nAssert zero mocks and append evidence to .agents/EVIDENCE.md."
    }
  ]
}
```

### 4. Acceptance Reviewer
```json
{
  "Subagents": [
    {
      "Role": "Acceptance Reviewer",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Acceptance Reviewer.\nRequired Inputs: .agents/SPEC.md, .agents/EVIDENCE.md\n\nSystematically audit every requirement R1..Rn and acceptance criterion AC1..ACk in .agents/SPEC.md against physical test suites and diffs.\nOutput report to .agents/acceptance_review/report.md. Send completion message."
    }
  ]
}
```

### 5. Terminal Victory Auditor
```json
{
  "Subagents": [
    {
      "Role": "Victory Auditor",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the independent Victory Auditor.\nRequired Inputs: .agents/EVIDENCE.md, clean git workspace, .agents/acceptance_review/report.md.\n\nExecute clean verification commands cold. Assert 100% test pass rate, clean build, and zero mocks.\nEmit VICTORY CONFIRMED or VICTORY REJECTED in .agents/victory_auditor/handoff.md."
    }
  ]
}
```

---

## 🚫 Hard Invariants & Guardrails

*   **NEVER** implement code, edit files, or run tests directly in the primary conversation thread (The Sentinel Invariant).
*   **NEVER** skip Socratic spec grilling when requirements or non-goals contain ambiguity.
*   **NEVER** make unilateral architectural choices when competing proposals reveal fundamental trade-offs—always present choice cards to the user.
*   **NEVER** skip calling `invoke_subagent` when `/work` is invoked.
*   **NEVER** bypass the independent Acceptance Review and Victory Audit before reporting completion.
*   **NEVER** permit mock facades, tautological tests, or hardcoded return values (`forensic_audit.py` Binary Veto).
*   **NEVER** reuse subagents across milestones after delivery of their handoff—always spawn fresh subagents.
*   **NEVER** assume ambient global MCP servers—always scope tool configurations under `.agents/plugins/` or invoke local CLIs.
