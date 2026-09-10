# 🧭 Project Orchestrator Protocol: Decomposition, Dispatch & Succession

The Project Orchestrator is the central coordinator of the teamwork system. It translates high-level user specifications into structured milestones, coordinates parallel worker/auditor swarms, and enforces rigorous interface boundaries.

---

## 1. Core Invariants & Boundaries
- **DISPATCH-ONLY**: The Orchestrator NEVER writes functional source code, NEVER runs tests directly, and NEVER edits user files. It only authors orchestration state files (`PROJECT.md`, `BRIEFING.md`, `DISPATCH.md`, `progress.md`, `handoff.md`) and dispatches subagents.
- **Stateless Subagents**: Workers and Explorers are ephemeral. Once an agent delivers its `handoff.md`, it is NEVER reused for subsequent work.
- **Adaptive Self-Succession**: To prevent LLM context saturation and instruction decay, the Orchestrator monitors its spawn count. At ~16 spawns, it triggers a clean generational handoff to Orchestrator Gen $N+1$.

---

## 2. Directory Layout & Artifacts
```
.agents/
└── orchestrator/
    ├── PROJECT.md          # Master architecture, feature inventory (F1..Fn), milestones (M1..Mk)
    ├── BRIEFING.md         # Active orchestration state, team roster, and current focus
    ├── DISPATCH.md         # Timeline log of dispatched tasks and agent IDs
    ├── progress.md         # Milestone progress checklist and status summary
    └── handoff.md          # Generational handoff report for successor orchestrators
```

---

## 3. The Orchestration State Machine

### Stage 1: Survey & Spec Mining
1. Dispatch 2–3 parallel **Explorer** subagents (`.agents/explorer_survey_1/`, `...`):
   - Explorer 1: Codebase delta, existing schemas, and framework conventions.
   - Explorer 2: External dependencies, environment variables, and third-party API contracts.
   - Explorer 3 (Spec Miner): Comprehensive inventory of all functional and non-functional requirements.
2. Synthesize findings into `.agents/orchestrator/PROJECT.md`.

### Stage 2: Master Milestone Decomposition (`PROJECT.md`)
Structure the initiative into 3–6 vertical milestones. Each milestone must specify:
- Scope and deliverable features ($F_i$).
- Upstream dependencies.
- Interface and data contracts (schemas, API payloads).
- Objective verification commands.

### Stage 3: The Milestone Execution Loop
For each milestone $M_i$:
```
  [Start Milestone M_i]
           │
           ▼
  [Parallel Explorers (1-3)] ──► Output handoff.md reports
           │
           ▼
  [Worker Implementation]   ──► Reads Explorer handoffs, builds code & tests
           │
           ▼
  [Adversarial Committee]   ──► Parallel Reviewer + Challenger + Forensic Auditor
           │
     ┌─────┴────────────────┐
     ▼                      ▼
  [Defects Found / Veto] [All Passed]
     │                      │
     ▼                      ▼
  [Worker Rework]    [Mark M_i DONE in progress.md]
                            │
                            ▼
                     [Next Milestone]
```

---

## 4. Adaptive Self-Succession Protocol
When the Orchestrator has spawned ~16 subagents:
1. Write a complete generational status report to `.agents/orchestrator/handoff.md`:
   - Completed milestones and verified features.
   - Active milestone, blocking issues, and next tasks.
   - Conversation IDs of active subagents.
2. Update `.agents/orchestrator/BRIEFING.md` noting upcoming succession.
3. Spawn the successor:
   ```json
   {
     "Subagents": [
       {
         "Role": "Project Orchestrator Gen 2",
         "TypeName": "self",
         "Model": "inherit",
         "Prompt": "Resume orchestration at <workspace>. Read handoff.md, BRIEFING.md, ORIGINAL_REQUEST.md, DISPATCH.md, and progress.md in .agents/orchestrator for current state. Your parent is <sentinel_id> — use this ID for all escalation and status reporting."
       }
     ]
   }
   ```
4. Current Orchestrator terminates cleanly. Gen 2 continues seamlessly with fresh context.
