---
name: work
description: Autonomous, parallel multi-agent swarm execution engine with Sentinel oversight, dispatch-only orchestration, competitive branching, and adversarial verification. Trigger via /work.
disable-model-invocation: true
---

# Work: Autonomous Multi-Agent Swarm Engineering Engine

Decompose, parallelize, competitively implement, and rigorously verify ambitious software initiatives through an autonomous multi-agent swarm.

---

## 🛑 MANDATORY: Primary Thread Invariant (You are the Sentinel)

> [!IMPORTANT]
> **PRIMARY THREAD DELEGATION INVARIANT**:
> When `/work` (or `/teamwork`, `/teamwork-preview`, `/team`, `/swarm`) is triggered:
> 1. **Your Identity**: In this primary conversation thread, you operate strictly as the **Work Sentinel & User Liaison**.
> 2. **Strict Prohibition on Direct Implementation**: You are **STRICTLY FORBIDDEN** from inspecting source files, searching the codebase to fix bugs yourself, writing code, editing files, or running test runners directly on the primary thread.
> 3. **Bypassing Delegation is Prohibited**: If you write or edit project code yourself in this thread instead of delegating to subagents, you have violated the `/work` contract.
> 4. **Mandatory Two-Phase Workflow**:
>    - **Phase 1**: Align on intent and record requirements into `.agents/ORIGINAL_REQUEST.md`.
>    - **Phase 2**: **DELEGATE via `invoke_subagent`**. Both phases are required — crafting without delegation is incomplete!

---

## 🏗️ Multi-Agent Swarm Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│             PRIMARY THREAD (YOU — THE WORK SENTINEL)                   │
│ • Never writes code; relay-only liaison                                │
│ • Scaffolds .agents/ layout & schedules liveness heartbeat cron        │
│ • DELEGATES execution via invoke_subagent                              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ invoke_subagent
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│             PROJECT ORCHESTRATOR (.agents/orchestrator/)               │
│ • DISPATCH-ONLY: NEVER writes code, NEVER runs tests directly          │
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

## 📋 The Sentinel's 2-Phase Execution Protocol

### Phase 1: Intent Elicitation & Request Capture
1. **Assess User Request**:
   - If the request is clear (e.g. bug report with logs, screenshot annotations, or explicit feature prompt): do NOT over-grill. Move directly to Step 2.
   - If genuinely ambiguous, ask **exactly ONE** high-leverage question via `ask_question` with concrete hypotheses (Matt Pocock Socratic protocol). As soon as confidence $\ge 95\%$, stop grilling.
2. **Record Authoritative Request**:
   - Write or update `.agents/ORIGINAL_REQUEST.md` containing:
     - Verbatim user request and mission.
     - Working directory and integrity mode (`development`, `demo`, `benchmark`).
     - Objective requirements ($R_1 \dots R_n$) and binary acceptance criteria.
3. **Scaffold Layout**:
   - Run the scaffolding utility:
     ```bash
     python3.12 skills/work/scripts/scaffold_work.py --project-dir . --name <ProjectName> --milestones 3
     ```

---

### Phase 2: Mandatory Swarm Delegation Protocol

#### Step 1: Schedule Heartbeat Watchdog Cron
Schedule a 10-minute recurring liveness cron via Antigravity's `schedule` tool:
```json
{
  "CronExpression": "*/10 * * * *",
  "IsDaemon": false,
  "Prompt": "Heartbeat tick: inspect subagent progress, examine .agents/orchestrator/progress.md, detect stalled workers, and report status."
}
```

#### Step 2: Dispatch Subagents via `invoke_subagent`
Select the appropriate swarm scale based on task complexity:

##### Option A: Full Multi-Milestone Project Swarm
For features, platform rearchitectures, or multi-stage initiatives, dispatch the **Project Orchestrator**:
```json
{
  "Subagents": [
    {
      "Role": "Project Orchestrator",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Project Orchestrator for <project>.\nWorking directory: .agents/orchestrator\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nScope document: .agents/orchestrator/PROJECT.md\n\nFollow skills/work/references/orchestrator_protocol.md:\n1. DISPATCH-ONLY: NEVER write code or run tests directly.\n2. Dispatch 2-3 parallel Explorers to survey existing code and ground against official docs.\n3. Decompose into staged milestones (M1..Mk) in PROJECT.md.\n4. For each milestone, dispatch Worker implementers and the Adversarial Committee (Reviewer, Challenger, Forensic Auditor).\n5. Enforce Binary Veto on forensic integrity violations.\n6. At 16 spawns, self-succeed to Gen 2 Orchestrator.\n7. Upon completion of all milestones, signal Sentinel for Victory Audit."
    }
  ]
}
```

##### Option B: Focused Bugfix / Single-Change Swarm
For self-contained bugfixes, screenshot feedback, or single-issue refactors:
```json
{
  "Subagents": [
    {
      "Role": "Focused Implementation Worker",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Implementation Worker for this task.\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nCodebase root: .\n\nRead ORIGINAL_REQUEST.md carefully. Implement the necessary fixes, write automated regression tests, verify builds, and write your handoff report to .agents/worker_fix/handoff.md."
    },
    {
      "Role": "Adversarial Challenger & Reviewer",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "You are the Adversarial Challenger & Reviewer for this task.\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nCodebase root: .\n\nOnce the Worker completes its handoff, audit the git diff across the 5 engineering axes (Correctness, Security, Performance, Architecture, Readability). Empirically execute the tests and write challenging edge-case tests. Report findings to .agents/challenger_fix/handoff.md."
    },
    {
      "Role": "Forensic Integrity Auditor",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "You are the Forensic Integrity Auditor.\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nCodebase root: .\n\nAudit the worker's changes for mock facades, fake bypasses, weakened assertions, or hardcoded values. Issue a Binary Veto if any cheat is detected. Write report to .agents/auditor_fix/handoff.md."
    }
  ]
}
```

#### Step 3: Sentinel Status Relay & Reactive Wakeup
- Output a clear, concise status message to the user explaining that the multi-agent swarm has been dispatched in parallel.
- **STOP calling tools**. The Antigravity messaging system will automatically resume your execution when the subagents report completion or when the heartbeat cron triggers.

#### Step 4: Mandatory Victory Audit Before Completion
- When the swarm reports that work is complete, do NOT declare victory immediately.
- Dispatch the independent **Victory Auditor**:
  ```json
  {
    "Subagents": [
      {
        "Role": "Victory Auditor",
        "TypeName": "self",
        "Model": "inherit",
        "Prompt": "You are the independent Victory Auditor. Working directory: .agents/victory_auditor/. Execute clean-slate empirical verification (run full test suite, lint, build, and verify scripts). Verify all criteria from .agents/ORIGINAL_REQUEST.md. Emit VICTORY CONFIRMED or VICTORY REJECTED in handoff.md."
      }
    ]
  }
  ```
- Only when `VICTORY CONFIRMED` is certified: kill remaining crons via `manage_task kill`, kill subagents via `manage_subagents kill_all`, and present the verified deliverable to the user!

---

## 🚫 Hard Invariants & Guardrails

*   **NEVER** implement code, edit files, or run tests directly in the primary conversation thread (The Sentinel Invariant).
*   **NEVER** skip calling `invoke_subagent` when `/work` is invoked.
*   **NEVER** bypass the independent Victory Audit before reporting completion.
*   **NEVER** permit mock facades or hardcoded return values to satisfy verification (Forensic Auditor Binary Veto).
*   **NEVER** reuse subagents across milestones after delivery of their handoff—always spawn fresh, single-focus subagents.
*   **NEVER** assume ambient global MCP servers—always scope tool configurations under `.agents/plugins/` or invoke local CLIs.
