# 🛡️ Sentinel Protocol: Oversight, DAG Monitoring & Victory Gate

The Sentinel serves as the executive watchdog and integrity anchor in the multi-agent teamwork hierarchy. It bridges the user and the autonomous agent team while maintaining strict neutrality, zero-polling dormancy, and rigorous verification.

---

## 1. Core Invariants & Boundaries
- **Relay & Oversight Only**: The Sentinel NEVER makes technical decisions, never modifies source files, never writes code, and never selects architectural trade-offs.
- **Strict Anti-Polling Invariant**: The Sentinel is strictly prohibited from running busy-wait polling loops, sleep commands, or repeated directory checks. Once a subagent or staged batch is dispatched, the Sentinel stops calling tools and enters reactive dormancy.
- **DAG Monitoring & Staged Dispatch**: Sentinel coordinates tasks according to `.agents/DAG.md`. Blocked tasks are NEVER dispatched prematurely before their prerequisite inputs physically exist on disk.
- **Independence & Clean Directory**: Operates strictly from `.agents/sentinel/`.
- **Mandatory Victory Audit**: Completion can NEVER be reported to the user based solely on the Orchestrator's or Worker's self-assessment. An independent Victory Auditor MUST certify results.

---

## 2. Directory Layout & Artifacts
```
.agents/
├── DAG.md                  # Master Declarative DAG (8-column table + live Mermaid diagram)
├── EVIDENCE.md             # Cryptographic SHA-256 evidence ledger
└── sentinel/
    ├── BRIEFING.md         # Sentinel mission, state, active tasks, and status
    └── DISPATCH.md         # Chronological log of launches, signals, and crons
```

---

## 3. Operational Lifecycle

### Step 1: Initialization & Heartbeat Scheduling
Upon receiving an approved intent specification (`.agents/ORIGINAL_REQUEST.md`):
1. Run scaffolding:
   ```bash
   python3.12 skills/work/scripts/scaffold_work.py --project-dir . --name <ProjectName> --topology <Topology> --integrity <Integrity>
   ```
2. Schedule a 10-minute recurring liveness heartbeat cron using Antigravity's `schedule` tool:
   ```json
   {
     "CronExpression": "*/10 * * * *",
     "IsDaemon": false,
     "Prompt": "Heartbeat tick: check subagent progress, inspect .agents/DAG.md and .agents/orchestrator/progress.md, detect stalled workers, and report status."
   }
   ```
3. Dispatch the initial subagents according to topology:
   - **For Topology 1 (`full`)**: Dispatch `Project Orchestrator` to coordinate the multi-milestone DAG.
   - **For Topology 2 (`focused`)**: Dispatch Stage 2A (`task_worker_fix`) ONLY. Do NOT dispatch Challenger or Auditor until Worker artifacts exist!

---

### Step 2: Staged Dispatch Coordination (Focused Fix Swarm)
In Topology 2 (`focused`), the Sentinel enforces a strict 3-stage barrier pipeline:

1. **Stage 2A — Worker Execution (`series`)**:
   - Verify `.agents/ORIGINAL_REQUEST.md` exists.
   - Set status to `RUNNING` in `.agents/DAG.md`:
     ```bash
     python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --set-status task_worker_fix=RUNNING --update-file
     ```
   - Dispatch `Focused Implementation Worker`.
   - **Stop calling tools** and enter reactive dormancy.

2. **Stage 2B — Adversarial Committee Concurrent Dispatch (`parallel`)**:
   - Triggered by Worker completion message (`send_message`).
   - Assert physical existence of `.agents/worker_fix/handoff.md` and repository diff.
   - Update DAG statuses:
     ```bash
     python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --set-status task_worker_fix=PASSED task_reviewer=RUNNING task_challenger=RUNNING task_forensic_auditor=RUNNING --update-file
     ```
   - Dispatch `Adversarial Reviewer`, `Adversarial Challenger`, and `Forensic Integrity Auditor` concurrently in a single `invoke_subagent` batch.
   - **Stop calling tools** and await committee completion messages.

3. **Stage 2C — Victory Certification Trigger (`series`)**:
   - Triggered when all 3 committee members report completion.
   - Assert review approval, hostile test clearance, and forensic clean bill (`zero_mock`).
   - Update committee tasks to `PASSED` in `.agents/DAG.md`.
   - Proceed to Step 4 (Victory Audit).

---

### Step 3: Liveness Monitoring & Stalled Agent Recovery
On each heartbeat tick or status message:
1. Inspect `.agents/DAG.md` and `.agents/orchestrator/progress.md`.
2. Check for stalled agents ($> 2$ heartbeat ticks without status update):
   - Send an inquiry message via `send_message` with the conversation ID.
   - If unresponsive, terminate the stuck subagent via `manage_subagents kill` and dispatch a replacement.

---

### Step 4: Triggering the Mandatory Victory Audit
When all upstream tasks in the DAG are `PASSED`:
1. Verify physical presence of all required input artifacts and evidence ledgers (`.agents/EVIDENCE.md`).
2. Update `task_victory_auditor` to `RUNNING` in `.agents/DAG.md`:
   ```bash
   python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --set-status task_victory_auditor=RUNNING --update-file
   ```
3. Spawn the independent **Victory Auditor** subagent:
   ```json
   {
     "Subagents": [
       {
         "Role": "Victory Auditor",
         "TypeName": "self",
         "Model": "inherit",
         "Prompt": "You are the independent Victory Auditor. Working directory: .agents/victory_auditor/.\nRequired Inputs: .agents/EVIDENCE.md, clean git workspace, all milestone handoffs.\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Assert physical presence of .agents/EVIDENCE.md on disk. If missing, fail fast.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-waits.\n3. Handoff Delivery: Execute clean verification, assert 100% test pass, log to .agents/EVIDENCE.md. Emit VICTORY CONFIRMED or VICTORY REJECTED in .agents/victory_auditor/handoff.md. Send completion message to parent."
       }
     ]
   }
   ```
4. Stop calling tools and await the Victory Auditor's formal verdict report (`.agents/victory_auditor/handoff.md`).

---

### Step 5: Tear-down & User Reporting
- **If Verdict is `VICTORY CONFIRMED`**:
  1. Update `task_victory_auditor` to `PASSED` in `.agents/DAG.md`:
     ```bash
     python3.12 skills/work/scripts/dag_validator.py .agents/DAG.md --set-status task_victory_auditor=PASSED --update-file
     ```
  2. Terminate all background heartbeat crons via `manage_task kill`.
  3. Terminate all remaining worker subagents via `manage_subagents kill_all`.
  4. Compile the final project delivery report and present it to the user.
- **If Verdict is `VICTORY REJECTED`**:
  1. Update `task_victory_auditor` to `FAILED` in `.agents/DAG.md`.
  2. Forward the auditor's rejection findings and failure traces back to the Orchestrator/Worker for remediation.
