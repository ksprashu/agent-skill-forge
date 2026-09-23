# 🧭 Project Orchestrator Protocol: Dynamic Scheduling, DAG Evolution & Succession

The Project Orchestrator is the central coordinator of the teamwork system. It translates high-level user specifications into structured milestones, coordinates parallel worker/auditor swarms via a declarative Markdown DAG, and enforces rigorous interface boundaries.

---

## 1. Core Invariants & Boundaries
- **DISPATCH-ONLY**: The Orchestrator NEVER writes functional source code, NEVER runs tests directly, and NEVER edits user files. It only authors orchestration state files (`PROJECT.md`, `DAG.md`, `BRIEFING.md`, `DISPATCH.md`, `progress.md`, `handoff.md`) and dispatches subagents.
- **Spec Grounding First**: The Orchestrator verifies that `.agents/SPEC.md` exists with clear requirements ($R_1 \dots R_n$) and non-goals before designing or scheduling milestones.
- **Design Proposal Tournament**: For architectural decisions, the Orchestrator dispatches parallel design architects (Alpha vs Beta) to explore competing hypotheses and uses `scripts/arbiter_eval.py` to synthesize the winning design into `.agents/design/DESIGN.md`.
- **Visual Artifact Verification**: The Orchestrator enforces that all design proposals include the 3 mandatory Mermaid models (System Architecture, C4 Component Block, Sequence Dataflow) per `visual_production_guide.md`, and verifies that `.agents/design/what_if_simulator.html` is compiled when trade-offs emerge.
- **Mermaid & DAG Synchronization**: The Orchestrator enforces that the embedded Mermaid diagram in `.agents/DAG.md` matches the declarative task table with 1:1 node parity, verified via `python3.12 skills/work/scripts/dag_validator.py --check-mermaid .agents/DAG.md`.
- **Stateless Subagents**: Workers, architects, and explorers are ephemeral. Once an agent delivers its `handoff.md`, it is NEVER reused for subsequent work. Fresh subagents are spawned for each node.
- **Zero-Polling Dormancy**: The Orchestrator is strictly forbidden from executing busy-wait polling loops, sleep commands, or repeated filesystem checks. It dispatches unblocked subagents, enters dormancy by stopping tool calls, and relies on Antigravity's reactive message wakeup.
- **Layered Committee Verification**: Every milestone must pass a 4-layered committee: Architectural Design Reviewer, 5-Axis Code Reviewer, Adversarial Challenger, and Forensic Integrity Auditor.
- **Binary Veto Enforcement**: Immediate halt on Forensic Auditor violations (`python3.12 skills/work/scripts/forensic_audit.py`). Mocks in benchmark mode or test tampering trigger instant failure.
- **Acceptance Gate**: Validates every acceptance criterion in `.agents/SPEC.md` before signaling Victory Audit.
- **Adaptive Self-Succession**: To prevent LLM context saturation and instruction decay, the Orchestrator monitors its spawn count. At ~16 spawns, it triggers a clean generational handoff to Orchestrator Gen $N+1$.

---

## 2. Directory Layout & Artifacts
```
.agents/
├── SPEC.md                 # Authoritative Socratic specification, non-goals, and AC checklist
├── DAG.md                  # Master Declarative DAG (8-column table + live Mermaid diagram)
├── EVIDENCE.md             # Cryptographic SHA-256 evidence ledger
├── design/
│   ├── proposals/          # Design Proposal Alpha and Beta markdown specs
│   ├── DESIGN.md           # Authoritative synthesized technical design doc
│   ├── arbiter_evidence.md # Collected facts about each proposal (no score)
│   ├── what_if_simulator.html # Interactive Canvas 2D Generative UI trade-off simulator
│   └── spike_results.md    # Optional empirical validation spike benchmarks
└── orchestrator/
    ├── PROJECT.md          # Architecture overview, feature inventory (F1..Fn), embedded DAG
    ├── BRIEFING.md         # Active orchestration state, team roster, and current focus
    ├── DISPATCH.md         # Timeline log of dispatched tasks and agent IDs
    ├── progress.md         # Milestone progress checklist and status summary
    └── handoff.md          # Generational handoff report for successor orchestrators
```

---

## 3. The Orchestration State Machine

```
[Init: SPEC.md Verified]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Parallel Design Proposals & Arbiter Tournament      │
│    • Dispatch Design Architect Alpha & Beta (parallel) │
│    • Run arbiter_eval.py --design-alpha ... --beta ... │
│    • If trade-offs need user choice: escalate to user  │
│    • Synthesize winning specs into DESIGN.md           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Validation Spikes (If High-Risk / Novel Hypotheses) │
│    • Dispatch prototype spike in branch workspace      │
│    • Benchmark feasibility & record spike_results.md   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Master Milestone Decomposition & DAG Authoring      │
│    • Compile M1..Mk milestones into .agents/DAG.md     │
│    • Embed live Mermaid execution diagram              │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 4. Staged Implementation & Layered Committee Pipeline  │
│    • Worker Alpha / Milestone Worker (series)          │
│    • Parallel Committee: Design Rev + Code Rev +       │
│      Adversarial Challenger + Forensic Integrity       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 5. Acceptance Review & Terminal Victory Signal         │
│    • Acceptance Review maps all SPEC.md AC checkboxes  │
│    • Signal Sentinel for independent Victory Audit     │
└────────────────────────────────────────────────────────┘
```

### Stage 1: Parallel Design Proposals & Arbiter Tournament
1. Assert physical existence of `.agents/SPEC.md` and `.agents/ORIGINAL_REQUEST.md`.
2. Dispatch 2 parallel **Design Architects** in isolated directories:
   ```json
   {
     "Subagents": [
       {
         "Role": "Design Architect Alpha",
         "TypeName": "self",
         "Model": "inherit",
         "Prompt": "Author Architectural Proposal Alpha for this project.\nRequired Inputs: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_alpha.md\n\nFollow skills/work/references/competitive_branching.md and skills/work/references/visual_production_guide.md:\nFocus on modularity, clear interface contracts, error resilience, minimal dependencies, and include 3 mandatory Mermaid models (flowchart TD system architecture, C4 component block with quoted nodes, and sequenceDiagram with autonumber). Send completion message when written."
       },
       {
         "Role": "Design Architect Beta",
         "TypeName": "self",
         "Model": "inherit",
         "Prompt": "Author Architectural Proposal Beta for this project.\nRequired Inputs: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_beta.md\n\nFollow skills/work/references/competitive_branching.md and skills/work/references/visual_production_guide.md:\nExplore an alternative storage, concurrency, or interface pattern with concrete schemas, trade-offs, and 3 mandatory Mermaid models (flowchart TD, C4 component block, sequenceDiagram with autonumber). Send completion message when written."
       }
     ]
   }
   ```
3. Once both proposals emit their completion messages, spawn the **Architectural Arbiter**:
   - Runs `python3.12 skills/work/scripts/arbiter_eval.py --design-alpha .agents/design/proposals/proposal_alpha.md --design-beta .agents/design/proposals/proposal_beta.md --output-report .agents/design/arbiter_evidence.md` to collect evidence, then **reads both proposals and judges**. The script never ranks them.
   - Verifies that both proposals contain complete, properly quoted Mermaid models.
   - If trade-offs require user input (`USER_DECISION_REQUIRED`), compiles `.agents/design/what_if_simulator.html` via `visual_engine.compile_what_if_simulator` and signals the Sentinel to present an interactive choice card.
   - Synthesizes the final approved design, schemas, and visual diagrams into `.agents/design/DESIGN.md`.

---

### Stage 2: Validation Spikes & Feasibility Probes
For initiatives involving high-concurrency synchronizers, novel protocols, or tight latency budgets:
1. Dispatch an empirical validation spike worker to test the core assumption in an isolated branch workspace (`Workspace: "branch"`).
2. Measure throughput, memory allocations, or error rates.
3. Record findings to `.agents/design/spike_results.md`.
4. Only unblock milestone implementation once the barrier gate (`spike_pass`) is satisfied.

---

### Stage 3: Milestone Decomposition & Declarative DAG Authoring
Translate `.agents/design/DESIGN.md` into staged milestones ($M_1 \dots M_k$) in `.agents/DAG.md` and `.agents/orchestrator/PROJECT.md` using the canonical 8-column schema:

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_spec_grill` | Socratic Spec Grilling | series | none | .agents/ORIGINAL_REQUEST.md | .agents/SPEC.md | spec_approved | PASSED |
| `task_design_alpha` | Architecture Proposal Alpha | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_alpha.md | design_pass | PASSED |
| `task_design_beta` | Architecture Proposal Beta | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_beta.md | design_pass | PASSED |
| `task_design_arbiter` | Design Arbiter & Synthesis | series | task_design_alpha, task_design_beta | .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md | .agents/design/DESIGN.md, .agents/design/arbiter_evidence.md | arbiter_pass | PASSED |
| `task_validation_spike` | Feasibility Spike | series | task_design_arbiter | .agents/design/DESIGN.md | .agents/design/spike_results.md | spike_pass | PASSED |
| `task_m1_worker` | Milestone 1 Worker | series | task_validation_spike | .agents/design/DESIGN.md | src/, tests/, .agents/m1_worker/handoff.md | exit_0 | PENDING |
| `task_m1_design_rev` | Milestone 1 Design Review | parallel | task_m1_worker | .agents/design/DESIGN.md, src/ | .agents/m1_design_rev/review.md | design_pass | BLOCKED |
| `task_m1_code_rev` | Milestone 1 5-Axis Code Review | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_code_rev/review.md | review_pass | BLOCKED |
| `task_m1_challenger` | Milestone 1 Challenger | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | tests/, .agents/m1_challenger/handoff.md | exit_0 | BLOCKED |
| `task_m1_forensic` | Milestone 1 Forensic Auditor | parallel | task_m1_worker | src/, tests/ | .agents/m1_forensic/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_acceptance_review` | Acceptance Review against SPEC.md | series | task_m1_design_rev, task_m1_code_rev, task_m1_challenger, task_m1_forensic | .agents/SPEC.md, .agents/EVIDENCE.md | .agents/acceptance_review/report.md | acceptance_pass | BLOCKED |
| `task_victory_auditor` | Clean-Slate Victory Audit | series | task_acceptance_review | .agents/EVIDENCE.md, .agents/acceptance_review/report.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |

After compiling or modifying `.agents/DAG.md`, immediately execute:
```bash
python3.12 skills/work/scripts/dag_validator.py --check-mermaid .agents/DAG.md
```
Assert that validation passes with exit code 0 and confirms 1:1 synchronization between the declarative task table rows and the visual Mermaid diagram nodes.

---

### Stage 4: Dynamic Ready Frontier Resolution & Scheduling Protocol
The Orchestrator dispatches subagents in accordance with the Ready Frontier:
1. **Dependency Gate**: All tasks listed in `Depends On` must be `PASSED`.
2. **Artifact Gate**: All files in `Inputs` must physically exist and be non-empty on disk.
3. **Execution Mode**:
   - `parallel` nodes in the Ready Frontier are dispatched concurrently in a single `invoke_subagent` call.
   - `series` nodes are dispatched in sequential order.
4. **Domain Skill Autowiring**: Before writing each dispatch payload, resolve the
   domain skills for that task and paste the emitted block into the `Prompt`:
   ```bash
   python3.12 skills/work/scripts/autowire.py --task "<the task name and its Outputs>" --role Worker
   ```
   The script scans `skills/` and `preferred/`, verifies every path it emits
   exists, and reports which terms matched. See
   [Domain Autowiring](domain_autowiring.md).
5. **Anti-Polling Dormancy**: If prerequisites are not satisfied, the node remains in `BLOCKED` status and zero subagents are spawned. The Orchestrator stops calling tools and awaits reactive wakeup.

---

### Stage 5: Layered Verification Committee Pipeline
Upon worker milestone completion, the Orchestrator asserts on-disk handoff existence and simultaneously dispatches:
1. **Design Reviewer**: Checks AST and source structure against `.agents/design/DESIGN.md` for interface contract fidelity and boundary purity.
2. **5-Axis Code Reviewer**: Audits Correctness, Security, Performance, Architecture, and Readability/Unslop.
3. **Adversarial Challenger**: Runs hostile fuzzing, boundary tests, and race-condition stress tests.
4. **Forensic Integrity Auditor**: Runs `forensic_audit.py` to check for synthetic mock facades, tautological tests, or test tampering, appending SHA-256 evidence to `.agents/EVIDENCE.md`.
5. **Visual Topology & DAG Synchronizer**: Executes `python3.12 skills/work/scripts/dag_validator.py --check-mermaid .agents/DAG.md` to ensure that task status updates in the declarative table remain in perfect parity with the embedded Mermaid diagram.

---

### Stage 6: Acceptance Review & Victory Signal
1. Dispatches the **Acceptance Reviewer** to audit all deliverables against `.agents/SPEC.md`. Every acceptance criterion ($AC_1 \dots AC_n$) must have verified test proof.
2. Emits `.agents/acceptance_review/report.md`.
3. Marks `task_acceptance_review` as `PASSED` in `.agents/DAG.md`.
4. Signals the Sentinel via `send_message` that all milestones and acceptance gates have passed and the project is ready for terminal Victory Certification.

---

## 4. Adaptive Self-Succession Protocol
When the Orchestrator has spawned ~16 subagents:
1. Write a complete generational status report to `.agents/orchestrator/handoff.md`.
2. Update `.agents/orchestrator/BRIEFING.md` noting upcoming succession.
3. Spawn the successor: `Project Orchestrator Gen 2`.
4. Current Orchestrator terminates cleanly. Gen 2 continues seamlessly with fresh context.
