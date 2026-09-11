# 🧭 Project Orchestrator Protocol: Dynamic Scheduling, DAG Evolution & Succession

The Project Orchestrator is the central coordinator of the teamwork system. It translates high-level user specifications into structured milestones, coordinates parallel worker/auditor swarms via a declarative Markdown DAG, and enforces rigorous interface boundaries.

---

## 1. Core Invariants & Boundaries
- **DISPATCH-ONLY**: The Orchestrator NEVER writes functional source code, NEVER runs tests directly, and NEVER edits user files. It only authors orchestration state files (`PROJECT.md`, `DAG.md`, `BRIEFING.md`, `DISPATCH.md`, `progress.md`, `handoff.md`) and dispatches subagents.
- **Stateless Subagents**: Workers and Explorers are ephemeral. Once an agent delivers its `handoff.md`, it is NEVER reused for subsequent work. Fresh subagents are spawned for each node.
- **Zero-Polling Dormancy**: The Orchestrator is strictly forbidden from executing busy-wait polling loops, sleep commands, or repeated filesystem checks. It dispatches unblocked subagents, enters dormancy by stopping tool calls, and relies on Antigravity's reactive message wakeup.
- **Binary Veto Enforcement**: Immediate halt on Forensic Auditor violations (`python3.12 skills/work/scripts/forensic_audit.py`). Mocks in benchmark mode or test tampering trigger instant failure.
- **Adaptive Self-Succession**: To prevent LLM context saturation and instruction decay, the Orchestrator monitors its spawn count. At ~16 spawns, it triggers a clean generational handoff to Orchestrator Gen $N+1$.

---

## 2. Directory Layout & Artifacts
```
.agents/
├── DAG.md                  # Master Declarative DAG (8-column table + live Mermaid diagram)
├── EVIDENCE.md             # Cryptographic SHA-256 evidence ledger
└── orchestrator/
    ├── PROJECT.md          # Architecture overview, feature inventory (F1..Fn), embedded DAG
    ├── BRIEFING.md         # Active orchestration state, team roster, and current focus
    ├── DISPATCH.md         # Timeline log of dispatched tasks and agent IDs
    ├── progress.md         # Milestone progress checklist and status summary
    └── handoff.md          # Generational handoff report for successor orchestrators
```

---

## 3. The Orchestration State Machine

### Stage 1: Survey & Spec Mining
1. Verify physical presence of `.agents/ORIGINAL_REQUEST.md`.
2. Dispatch 2–3 parallel **Explorer** subagents (`.agents/explorer_survey_1/`, `...`):
   - Explorer 1: Codebase delta, existing schemas, and framework conventions.
   - Explorer 2: External dependencies, environment variables, and third-party API contracts.
   - Explorer 3 (Spec Miner): Comprehensive inventory of all functional and non-functional requirements.
   ```json
   {
     "Subagents": [
       {
         "Role": "Explorer 1 — Codebase & Delta Survey",
         "TypeName": "self",
         "Model": "flash",
         "Prompt": "You are Explorer 1.\nWorking directory: .agents/explorer_survey_1/\nRequired Inputs: .agents/ORIGINAL_REQUEST.md\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Verify physical presence of .agents/ORIGINAL_REQUEST.md. If missing, fail fast with error to parent.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-waits.\n3. Handoff Delivery: Survey repo structure and delta. Write report to .agents/explorer_survey_1/handoff.md. Send completion message to parent referencing handoff path."
       }
     ]
   }
   ```
3. Synthesize findings into `.agents/orchestrator/PROJECT.md` and scaffold initial task nodes in `.agents/DAG.md`.

---

### Stage 2: Master Milestone Decomposition & Declarative DAG Authoring
Structure the initiative into staged vertical milestones ($M_1 \dots M_k$) in `.agents/DAG.md` and `.agents/orchestrator/PROJECT.md` using the standardized 8-column format:

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_m0_survey` | Initial Code & Spec Survey | parallel | none | .agents/ORIGINAL_REQUEST.md | .agents/survey/handoff.md | survey_pass | PASSED |
| `task_m1_worker` | Milestone 1 Core Store | series | task_m0_survey | .agents/survey/handoff.md | src/, tests/, .agents/m1_worker/handoff.md | exit_0 | PENDING |
| `task_m1_rev` | Milestone 1 Code Review | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_rev/review.md | review_pass | BLOCKED |
| `task_m1_chal` | Milestone 1 Adversarial Tests | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | tests/, .agents/m1_chal/handoff.md | exit_0 | BLOCKED |
| `task_m1_aud` | Milestone 1 Forensic Audit | parallel | task_m1_worker | src/, tests/ | .agents/m1_aud/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_final_vic` | Terminal Victory Certification | series | task_m1_rev, task_m1_chal, task_m1_aud | .agents/EVIDENCE.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |

Sync the live Mermaid execution topology:
```bash
python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --update-file
```

---

### Stage 3: Dynamic Model-Driven Orchestration & Scheduling Protocol

Instead of coarse sequential loops, the Orchestrator executes dynamic, fine-grained scheduling governed by the **Ready Frontier Resolution Algorithm**:

```
[Wakeup Trigger: Message Received / Init]
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 1. Parse Declarative DAG Table                         │
│    Extract tasks, modes, depends_on, inputs, status    │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 2. Evaluate Blocked & Pending Nodes                    │
│    For each node where status == PENDING or BLOCKED:   │
│    • Are ALL dependencies in depends_on marked PASSED? │
│    • Do ALL required files in Inputs physically exist? │
└──────────────────┬─────────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
  [All Satisfied]         [Any Unsatisfied]
       │                       │
       ▼                       ▼
 [Mark PENDING / READY]   [Mark BLOCKED (Keep DORMANT)]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ 3. Resolve the Ready Frontier Batch                    │
│    • Gather all READY nodes                            │
│    • Group parallel siblings for concurrent dispatch   │
│    • Schedule series tasks in topological sequence     │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 4. Dispatch Ready Batch via invoke_subagent            │
│    • Injects anti-polling directives                   │
│    • Injects verified input artifact paths             │
│    • Updates status to RUNNING in DAG.md & Mermaid     │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 5. Enter Reactive Dormancy (STOP CALLING TOOLS)        │
│    • Zero busy-waiting, zero polling loops             │
│    • Await subagent completion message via Antigravity │
└────────────────────────────────────────────────────────┘
```

#### 1. Ready Frontier Resolution Rules
1. **Dependency Gate**: A task node cannot enter the Ready Frontier unless every task listed in its `Depends On` column has achieved `PASSED` status.
2. **Artifact Gate**: The Orchestrator verifies via `os.path.exists` that every physical file listed in `Inputs` exists and is non-empty before dispatching.
3. **Execution Mode Grouping**:
   - `parallel` nodes in the Ready Frontier are dispatched concurrently in a single `invoke_subagent` call.
   - `series` nodes are dispatched individually in topological order.
   - `async_background` nodes (e.g. telemetry, liveness monitors) are launched without gating downstream task evaluation.

#### 2. Zero-Polling Dormancy for Blocked Nodes
- **Strict Anti-Polling Invariant**: The Orchestrator is **STRICTLY PROHIBITED** from dispatching dependent subagents (e.g. Reviewers, Challengers, Forensic Auditors) before their upstream dependencies have passed and prerequisite input artifacts physically exist on disk.
- If prerequisites are not met, the node remains in `BLOCKED` status and **zero subagents are spawned**.
- Once a ready batch is dispatched, the Orchestrator **ceases tool calls immediately**.

#### 3. Dynamic DAG Evolution Protocol
When implementation reality diverges from the initial plan, the Orchestrator dynamically mutates the DAG:
1. **Remediation Node Injection**:
   - If an Adversarial Committee member issues a rejection or veto:
     - Mark the failing node `FAILED` in `.agents/DAG.md`.
     - Dynamically insert a remediation node: `task_m{i}_remediation` (Mode: `series`, Inputs: failure logs and diff, Outputs: remediation patch).
     - Rewire downstream nodes to depend on `task_m{i}_remediation` instead of the failing node.
     - Update `.agents/DAG.md` and regenerate the Mermaid diagram using `python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --update-file`.
2. **Competitive Tournament Branching**:
   - For high-risk modules, fork the milestone into parallel sibling nodes: `task_m{i}_worker_alpha` and `task_m{i}_worker_beta` (`Workspace: "branch"`).
   - Converge both workers into a synthesis node: `task_m{i}_arbiter` which runs `python3.12 skills/work/scripts/arbiter_eval.py`.
   - Downstream committee nodes depend on `task_m{i}_arbiter`.
3. **Mutation Boundary Guardrail**:
   - Dynamic remediation loops per milestone are strictly capped at `MAX_MUTATIONS = 4`. If 4 remediation attempts fail, the Orchestrator escalates to the Sentinel and pauses execution.

#### 4. Reactive Wakeup Integration
Antigravity automatically resumes Orchestrator execution when:
- A child subagent finishes and calls `send_message(Recipient="<parent_id>", Message="...")`.
- The recurring heartbeat cron triggers.
Upon waking up:
1. The Orchestrator reads the child's `handoff.md`.
2. Validates the Barrier Gate preconditions (e.g. exit code 0, clean audit).
3. Updates the task status to `PASSED` in `.agents/DAG.md`.
4. Re-runs the Ready Frontier Resolution algorithm and dispatches the next batch.

---

## 4. Adaptive Self-Succession Protocol
When the Orchestrator has spawned ~16 subagents:
1. Write a complete generational status report to `.agents/orchestrator/handoff.md`:
   - Completed milestones, verified features, and current DAG state.
   - Active milestone, blocking issues, and next tasks in the Ready Frontier.
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
         "Prompt": "Resume orchestration at <workspace>.\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nMaster DAG: .agents/DAG.md\nScope document: .agents/orchestrator/PROJECT.md\nWorking directory: .agents/orchestrator/\nParent Sentinel ID: <sentinel_id>\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Verify physical presence of .agents/orchestrator/handoff.md, BRIEFING.md, and DAG.md before proceeding. If missing, fail fast with error to parent.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-wait polling loops. Execution is event-driven.\n3. Handoff Delivery: Maintain .agents/DAG.md and .agents/orchestrator/PROJECT.md. Use send_message for all parent communication.\n\nFollow skills/work/references/orchestrator_protocol.md:\n- DISPATCH-ONLY: NEVER edit code, NEVER run tests directly.\n- Resolve Ready Frontier: dispatch unblocked tasks whose dependencies are PASSED and inputs physically exist.\n- Zero-polling dormancy for blocked nodes: NEVER dispatch dependent subagents before their prerequisite artifacts exist.\n- Dynamic DAG Evolution: insert remediation nodes upon adversarial failure.\n- At ~16 spawns, self-succeed to Gen 3 Orchestrator.\n- Upon completion of all milestones, signal Sentinel for Victory Audit."
       }
     ]
   }
   ```
4. Current Orchestrator terminates cleanly. Gen 2 continues seamlessly with fresh context.
