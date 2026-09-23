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
> When `/work` (or `/teamwork`, `/team`, `/swarm`) is triggered:
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
   - **Mandatory Visual Deliverables**: Each proposal MUST include 3 complete visual diagrams adhering to [Visual Production Guide](references/visual_production_guide.md):
     1. High-Level System Architecture Diagram (`flowchart TD`)
     2. C4 Level 2/3 Component Block Diagram (`graph TD` / `flowchart LR` with quoted node labels)
     3. Lifecycle Sequence & Dataflow Diagram (`sequenceDiagram` with `autonumber`).
2. **Evidence Collection, then Judgement**:
   - `scripts/arbiter_eval.py` reads both proposals and writes `.agents/design/arbiter_evidence.md`: counts of substantive schema and code blocks, trivial and placeholder blocks, measured claims (a number with a unit), named alternatives and trade-offs, unresolved `TBD`/`TODO` markers, hedge phrases, and distinct backticked identifiers.
   - **It does not score and does not pick a winner.** It used to award 100 points across four axes, and on a two-sided fixture pair it preferred the hollow proposal to the substantive one, because length and heading count are easy to fake and depth is not. Counting is a script's job; choosing an architecture is not.
   - The Arbiter agent reads the evidence *and both proposals*, answers the questions the report poses, and records the decision with its reasoning in `.agents/design/DESIGN.md`.

---

### Phase 3: Architectural Manager Evaluation & User Decision Gate
1. **Interactive "What-If" Trade-Off Simulator Compilation**:
   - When proposals reveal fundamental architectural trade-offs (e.g. In-Memory Speed vs SQLite Persistence, REST vs GraphQL, Client vs Server State), the Arbiter compiles `.agents/design/what_if_simulator.html` via `visual_engine.compile_what_if_simulator`.
   - The simulator provides an offline, zero-CDN HTML5 Canvas 2D radar visualizer with high-DPI scaling and interactive sensitivity sliders.
2. **User Choice Escalation via Sentinel**:
   - Arbiter flags `USER_DECISION_REQUIRED` and generates markdown choice cards.
   - The Sentinel inspects `.agents/design/what_if_simulator.html` and presents an interactive choice modal to the user via `ask_question`.
3. **Authoritative Synthesis**:
   - Synthesize the winning architecture, resolved trade-offs, approved visual diagrams, and concrete schemas into `.agents/design/DESIGN.md`.

---

### Phase 4: Prototyping Spikes & Hypothesis Validation Tournaments
1. **Empirical Feasibility Probes**:
   - For high-risk assumptions, latency budgets, or novel libraries, dispatch a prototype worker in an isolated branch (`Workspace: "branch"`).
   - Run micro-benchmarks or proof-of-concept tests.
   - Record results in `.agents/design/spike_results.md` satisfying the barrier gate (`spike_pass`).

---

### Phase 5: Declarative Task DAG Decomposition
- Compile the approved `DESIGN.md` into vertical implementation milestones ($M_1 \dots M_k$) in `.agents/DAG.md`.
- Synthesize authoritative system architecture, C4 component, and sequence diagrams directly into `DESIGN.md` § 1.1, § 1.2, § 1.3.
- Embed live visual Mermaid execution topology into `.agents/DAG.md`.
- Validate graph acyclicity, contract validity, and visual parity:
  ```bash
  python3.12 skills/work/scripts/dag_validator.py --check-mermaid .agents/DAG.md
  ```

---

### Phase 6: Staged Implementation & Testing
- Dispatches implementation workers sequentially per milestone.
- Workers author production code, write automated unit/integration tests, and verify physical exit code 0.
- Reports delivery in `.agents/m{i}_worker/handoff.md`.

---

### Phase 7: Multi-Perspective Layered Verification & Acceptance Gate
Upon milestone completion, the Orchestrator dispatches the Verification Committee concurrently:
1. **Architectural Design Reviewer**: Audits git diff against `.agents/design/DESIGN.md` to prevent architectural drift or interface leaks (`design_pass`).
2. **5-Axis Code Reviewer**: Audits Correctness, Security, Performance, Architecture, and Readability/Unslop (`review_pass`).
3. **Adversarial Challenger**: Executes hostile edge tests, concurrency stress, and race-condition probes (`exit_0`).
4. **Forensic Integrity Auditor**: Runs `forensic_audit.py` to enforce zero synthetic mock facades and log SHA-256 evidence to `.agents/EVIDENCE.md` (`zero_mock`).
5. **Visual Topology & DAG Synchronizer**: Executes `dag_validator.py --check-mermaid` to ensure 1:1 parity between task table rows and Mermaid diagram nodes.
6. **Acceptance Reviewer**: Systematically audits all acceptance criteria in `.agents/SPEC.md`, producing `.agents/acceptance_review/report.md` (`acceptance_pass`).
7. **Victory Auditor**: Independent clean-slate cold run producing final sign-off (`victory_cert`).

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
- **Node Status States (`Status`)**:
  - `PENDING`, `RUNNING`, `PASSED`, `BLOCKED`, `FAILED`.

### 2. Barrier Gates (`Gate`)

Every gate name in the Gate column resolves to a predicate in
`skills/work/scripts/gate_executor.py`. `dag_validator.py --set-status X=PASSED`
calls that predicate and **refuses to write PASSED when it returns false**, with
exit code 3. Run `python3.12 skills/work/scripts/gate_executor.py list` for the
live registry. A gate name the executor does not recognise fails closed — a typo
in the Gate column is not permission.

**Mechanical gates** — the executor settles these itself:

| Gate | What has to be true |
|---|---|
| `exit_0` (also `test_pass`, `all_passed`) | A verification command was recorded for this task, it exited 0, and the code has not changed since. |
| `zero_mock` | `forensic_audit.py --strict` exits 0 against the tree. |
| `file_exists` | Every declared Output exists and is more than a placeholder. |
| `victory_cert` | Every task PASSED **and** the strict audit is clean **and** a verification run against the current tree exited 0. |
| `none` | Nothing. Recorded as passing for nothing. |
| a literal command | The Gate cell may be a test command (`pytest tests/test_auth.py`). It is run as argv — never through a shell — and exit 0 is the gate. |

**Attested gates** — `spec_approved`, `design_pass`, `arbiter_pass`,
`spike_pass`, `review_pass`, `review_5axis_pass`, `acceptance_pass`,
`committee_join`. These are judgements, and no script can make them. A reviewer
records one with:

```bash
python3.12 skills/work/scripts/gate_executor.py attest \
  --task task_m1_code_rev --gate review_5axis_pass --verdict PASS \
  --reviewer-role code-reviewer --worker-role implementer \
  --evidence .agents/m1_code_rev/review.md \
  --summary "What was reviewed and what was found."
```

The executor then refuses that attestation if it is self-signed (reviewer role
equals worker role), cites nothing, cites a file that does not exist or is
placeholder text, carries a summary under 40 characters, or was written against
a different revision than the one on disk. It cannot check whether the reviewer
was *right* — and says so, in every report, under "Not checked by this gate".

**Recording evidence.** Workers record their verification runs rather than
asserting them:

```bash
python3.12 skills/work/scripts/gate_executor.py record \
  --task task_m1_worker --cmd "python3.12 -m pytest tests -q"
```

That call exits non-zero when the suite is red, and stamps the run with a digest
of the source tree. A green run stops counting the moment the code changes.

**Overrides.** `--force-status --reason '<why>'` writes PASSED over a failing
gate and appends the override, the gate, and the reason to a `## Gate Overrides`
section of the DAG document. There is no silent bypass.

---

## 📐 Canonical DAG Templates

`scaffold_work.py --topology` accepts six values. Pick by how much verification
the work needs, not by how impressive the name sounds:

| Topology | Shape | Use when |
|---|---|---|
| `lifecycle` | Spec grill → two design proposals → arbiter → spike → milestone worker → four parallel reviewers → acceptance → victory | New system or a change whose design is not settled. The only topology that grills the spec first. |
| `full` | Survey → (worker → committee) × N → victory | The design is settled and one committee verdict per milestone is enough. |
| `proof` | Survey → spike → (worker → code review ∥ challenger ∥ forensic → join) × N → victory | A single committee verdict is too coarse to trust: each verifier gets its own gate and can fail independently. |
| `massive` | `full` at 8 milestones | Work that does not decompose into three milestones. Override with `--milestones`. |
| `focused` | Worker → review ∥ challenger ∥ forensic → victory | One bug, one fix, full verification. |
| `review` | Lead review → fact check ∥ inconsistency analysis → unslop synthesis | The deliverable is a document, not code. |

Every gate named in every template resolves to a predicate in
`gate_executor.py`; `test_gate_executor.py` scaffolds all six and fails if any
gate does not.

### Template 1: Full Lifecycle Engineering Swarm (`--topology lifecycle`)
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_spec_grill` | Socratic Spec Grilling | series | none | .agents/ORIGINAL_REQUEST.md | .agents/SPEC.md | spec_approved | PENDING |
| `task_design_alpha` | Architecture Proposal Alpha | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_alpha.md | design_pass | BLOCKED |
| `task_design_beta` | Architecture Proposal Beta | parallel | task_spec_grill | .agents/SPEC.md | .agents/design/proposals/proposal_beta.md | design_pass | BLOCKED |
| `task_design_arbiter` | Design Arbiter & User Decision Gate | series | task_design_alpha, task_design_beta | .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md | .agents/design/DESIGN.md, .agents/design/arbiter_evidence.md | arbiter_pass | BLOCKED |
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

### Template 3: Multi-Milestone Swarm (`--topology full`, `--topology massive`)
Identical shape; `massive` only starts at 8 milestones instead of 3. Shown at
two milestones:
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_m0_survey` | Initial Code & Spec Survey | parallel | none | .agents/ORIGINAL_REQUEST.md | .agents/survey/handoff.md | survey_pass | PENDING |
| `task_m1_worker` | Milestone 1 Worker | series | task_m0_survey | .agents/survey/handoff.md | src/, tests/, .agents/m1_worker/handoff.md | exit_0 | BLOCKED |
| `task_m1_committee` | Milestone 1 Committee | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_committee/review.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_m2_worker` | Milestone 2 Worker | series | task_m1_committee | .agents/m1_committee/review.md | src/, tests/, .agents/m2_worker/handoff.md | exit_0 | BLOCKED |
| `task_m2_committee` | Milestone 2 Committee | parallel | task_m2_worker | src/, tests/, .agents/m2_worker/handoff.md | .agents/m2_committee/review.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_victory_auditor` | Clean-Slate Certification | series | task_m2_committee | .agents/EVIDENCE.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |
```

### Template 4: Proof Swarm (`--topology proof`)
`full` plus an upfront validation spike, with the committee split into three
verifiers that gate independently. A code review that passes no longer carries a
failing forensic audit across the line with it. Shown at one milestone:
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_m0_survey` | Initial Code & Spec Survey | parallel | none | .agents/ORIGINAL_REQUEST.md | .agents/survey/handoff.md | survey_pass | PENDING |
| `task_validation_spike` | Validation Spike | series | task_m0_survey | .agents/survey/handoff.md | .agents/design/spike_results.md | spike_pass | BLOCKED |
| `task_m1_worker` | Milestone 1 Worker | series | task_validation_spike | .agents/design/spike_results.md | src/, tests/, .agents/m1_worker/handoff.md | exit_0 | BLOCKED |
| `task_m1_code_rev` | Milestone 1 5-Axis Code Review | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_code_rev/review.md | review_pass | BLOCKED |
| `task_m1_challenger` | Milestone 1 Adversarial Challenger | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_challenger/handoff.md | exit_0 | BLOCKED |
| `task_m1_forensic` | Milestone 1 Forensic Integrity Auditor | parallel | task_m1_worker | src/, tests/, .agents/m1_worker/handoff.md | .agents/m1_forensic/handoff.md, .agents/EVIDENCE.md | zero_mock | BLOCKED |
| `task_m1_join` | Milestone 1 Verification Join | series | task_m1_code_rev, task_m1_challenger, task_m1_forensic | .agents/m1_code_rev/review.md, .agents/m1_challenger/handoff.md, .agents/m1_forensic/handoff.md | .agents/m1_join/verdict.md | committee_join | BLOCKED |
| `task_victory_auditor` | Clean-Slate Certification | series | task_m1_join | .agents/EVIDENCE.md | .agents/victory_auditor/handoff.md | victory_cert | BLOCKED |
```

### Template 5: Document Review Deck (`--topology review`)
```markdown
| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_lead_reviewer` | Lead Document Review | series | none | .agents/ORIGINAL_REQUEST.md | .agents/review_deck/lead_review.md | review_pass | PENDING |
| `task_fact_checker` | Comparative Fact-Checking | parallel | task_lead_reviewer | .agents/review_deck/lead_review.md | .agents/review_deck/fact_check.md | fact_check_pass | BLOCKED |
| `task_inconsistency_inquisitor` | Inconsistency Analysis | parallel | task_lead_reviewer | .agents/review_deck/lead_review.md | .agents/review_deck/inconsistencies.md | analysis_pass | BLOCKED |
| `task_unslop_auditor` | Standards & Unslop Synthesis | series | task_fact_checker, task_inconsistency_inquisitor | .agents/review_deck/fact_check.md, .agents/review_deck/inconsistencies.md | .agents/review_deck/review_deck.md | unslop_clean | BLOCKED |
```

---

## 🎨 Visual Production Standards & Generative UI Architecture

Detailed copyable templates, sanitization algorithms, and Generative UI source patterns are documented in the [Visual Production Guide](references/visual_production_guide.md).

### 1. Mandatory Visual Deliverables across the 7-Phase Lifecycle
Every `/work` swarm enforces visual rigor across proposals, user decisions, architecture consolidation, and verification:

| Phase | Swarm Stage | Mandatory Visual Deliverable | Target Artifact | Enforcing Gate |
|---|---|---|---|---|
| **Phase 2** | Parallel Design Proposals | 3 Complete Diagrams: System Architecture (`flowchart TD`), C4 Level 2/3 Component Block (`graph TD`), and Lifecycle Sequence (`sequenceDiagram` with `autonumber`) | `.agents/design/proposals/proposal_alpha.md`, `proposal_beta.md` | `arbiter_eval.py` / `design_pass` |
| **Phase 3** | Decision Gate | Interactive "What-If" Trade-Off Simulator (Canvas 2D, Retina, Sensitivity Sliders) & Markdown Choice Cards | `.agents/design/what_if_simulator.html` | Sentinel `ask_question` modal |
| **Phase 5** | Design & DAG Synthesis | Synthesized Architecture Diagrams in `DESIGN.md` § 1.1–1.3 and Live Mermaid Topology in `DAG.md` | `.agents/design/DESIGN.md`, `.agents/DAG.md` | `dag_validator.py --check-mermaid` |
| **Phase 7** | Layered Verification | 1:1 Parity Validation between Declarative Task Table and Mermaid Diagram Nodes | `.agents/DAG.md` | `dag_validator.py --check-mermaid` |

### 2. Mermaid Diagram Invariants
- **Node Quoting**: All node labels containing spaces, brackets `[]`, parentheses `()`, slashes, or hyphens MUST be wrapped in explicit double quotes: `node_id["Label (Context)"]`.
- **Entity Escaping**: Escape internal quotes as `#quot;`, pipes as `&#124;`, arrows as `--&gt;`, and newlines as `<br/>`.
- **Sequence Autonumber**: All `sequenceDiagram` blocks MUST include the `autonumber` directive.

### 3. Antigravity Generative UI Simulator Invariants
- **Zero External CDNs**: Artifacts must be 100% self-contained; no external script tags (`unpkg`, `cdnjs`, `jsdelivr`, or external chart libraries like Chart.js or D3) are permitted inside the sandboxed iframe.
- **Canvas 2D Retina Scaling**: Render radar charts natively via HTML5 Canvas 2D, scaling buffer dimensions by `window.devicePixelRatio` and calling `ctx.scale(dpr, dpr)`.
- **Headless Fallback**: Include a pre-rendered static HTML comparison table in `<noscript>` so CI test runners and non-JS clients can evaluate trade-offs.
- **Choice-Card Export**: Provide one-click clipboard export formatting user slider selections into Markdown suitable for the Sentinel's `ask_question` tool.

---

## 🚀 Swarm Dispatch Payloads

**Before writing any payload, resolve the domain skills for that task** and
paste the emitted block into the `Prompt`:

```bash
python3.12 skills/work/scripts/autowire.py --task "<task name and its Outputs>" --role Worker
```

It scans `skills/` and `preferred/`, emits only paths that exist, and names the
terms that matched. A subagent that is not told which local skills apply will
work from its own priors instead. See
[Domain Autowiring](references/domain_autowiring.md).

Every subagent runs `"Model": "inherit"`. A reviewer cheaper than the agent it
reviews is theatre.

### 1. Design Architect Subagents (Parallel Proposals)
```json
{
  "Subagents": [
    {
      "Role": "Design Architect Alpha",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are Design Architect Alpha.\nAuthoritative specification: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_alpha.md\n\nFollow skills/work/references/competitive_branching.md and skills/work/references/visual_production_guide.md:\nAuthor a modular, robust architectural proposal with explicit schemas, interfaces, error handling, trade-offs, and 3 mandatory Mermaid diagrams (flowchart TD system architecture, C4 component block with quoted nodes, and sequenceDiagram with autonumber). Send completion message when written."
    },
    {
      "Role": "Design Architect Beta",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are Design Architect Beta.\nAuthoritative specification: .agents/SPEC.md\nWorking directory: .agents/design/proposals/\nOutput: .agents/design/proposals/proposal_beta.md\n\nFollow skills/work/references/competitive_branching.md and skills/work/references/visual_production_guide.md:\nAuthor an alternative architectural proposal exploring distinct storage, concurrency, or interface paradigms with clear trade-offs and 3 mandatory Mermaid diagrams (flowchart TD, C4 component block, sequenceDiagram with autonumber). Send completion message when written."
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
      "Prompt": "You are the Architectural Arbiter.\nRequired Inputs: .agents/design/proposals/proposal_alpha.md, .agents/design/proposals/proposal_beta.md\nGrounding: read the relevant subtrees of .gemini/knowledge/ before judging (see skills/catalog/SKILL.md).\n\nFollow skills/work/references/competitive_branching.md:\n1. Run: python3.12 skills/work/scripts/arbiter_eval.py --design-alpha .agents/design/proposals/proposal_alpha.md --design-beta .agents/design/proposals/proposal_beta.md --output-report .agents/design/arbiter_evidence.md\n2. That report is EVIDENCE, not a verdict. It counts substantive blocks, measured claims, named alternatives, hedges and unresolved markers; it deliberately emits no score and no winner. Read both proposals yourself and decide.\n3. Answer every question under 'Questions the Arbiter must answer' in the report, in writing.\n4. If trade-offs require a user decision, signal Sentinel with options.\n5. Synthesize the winning architecture into .agents/design/DESIGN.md, stating what you rejected and why.\n6. Attest the gate: python3.12 skills/work/scripts/gate_executor.py attest --task task_design_arbiter --gate arbiter_pass --verdict PASS --reviewer-role architectural-arbiter --worker-role design-architect --evidence .agents/design/DESIGN.md --evidence .agents/design/arbiter_evidence.md --summary '<what you compared and why you chose it>'\n7. Send completion message referencing DESIGN.md."
    }
  ]
}
```

### 3. Layered Verification Committee (Parallel Batch)

The committee is the only thing standing between faked work and a green DAG, so
it runs on the orchestrator's own model. It used to be dispatched on `flash` —
the cheapest model in the fleet reviewing the most expensive model's output,
which inverts the point of review.

```json
{
  "Subagents": [
    {
      "Role": "Architectural Design Reviewer",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "Audit git diff against .agents/design/DESIGN.md for interface drift and boundary violations. Ground yourself in .gemini/knowledge/architecture/ first. Follow skills/review/SKILL.md. Output .agents/m1_design_rev/review.md, then attest:\npython3.12 skills/work/scripts/gate_executor.py attest --task task_m1_design_rev --gate review_pass --verdict PASS --reviewer-role design-reviewer --worker-role implementer --evidence .agents/m1_design_rev/review.md --summary '<what drifted, what did not>'"
    },
    {
      "Role": "5-Axis Code Reviewer",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "Audit the diff across Correctness, Security, Performance, Architecture, and Readability/Unslop. The five axes and their rubrics live in skills/review/SKILL.md and skills/unslop/SKILL.md — read them; do not reinvent them here. Output .agents/m1_code_rev/review.md, then attest:\npython3.12 skills/work/scripts/gate_executor.py attest --task task_m1_code_rev --gate review_5axis_pass --verdict PASS --reviewer-role code-reviewer --worker-role implementer --evidence .agents/m1_code_rev/review.md --summary '<findings per axis>'"
    },
    {
      "Role": "Adversarial Challenger",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "Author hostile edge-case and boundary tests against the implementation. Follow skills/test/SKILL.md. Record the run as evidence rather than asserting it in prose:\npython3.12 skills/work/scripts/gate_executor.py record --task task_m1_challenger --cmd '<your test command>'\nThat call exits non-zero if the suite is red. Output .agents/m1_challenger/handoff.md."
    },
    {
      "Role": "Forensic Integrity Auditor",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "Run: python3.12 skills/work/scripts/forensic_audit.py --target-dir . --strict\nThe auditor scans production source as well as tests: hardcoded returns, ignored parameters, dead computation, stubs, mocks, tautological assertions. Add --mutate --test-cmd '<test command>' to check that the tests would notice if the code broke. Exit 1 means VETO; the milestone does not advance. Write findings to .agents/m1_forensic/report.md."
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
      "Prompt": "You are the Acceptance Reviewer.\nRequired Inputs: .agents/SPEC.md, .agents/evidence/\n\nSystematically audit every requirement R1..Rn and acceptance criterion AC1..ACk in .agents/SPEC.md against physical test suites and diffs. For each one, cite the test that covers it or record that none does.\nOutput report to .agents/acceptance_review/report.md, then attest:\npython3.12 skills/work/scripts/gate_executor.py attest --task task_acceptance_review --gate acceptance_pass --verdict PASS --reviewer-role acceptance-reviewer --worker-role implementer --evidence .agents/acceptance_review/report.md --summary '<which requirements are covered and which are not>'\nSend completion message."
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
      "Prompt": "You are the independent Victory Auditor.\nRequired Inputs: .agents/evidence/, clean git workspace, .agents/acceptance_review/report.md.\n\nExecute the verification commands cold, from a clean checkout. Then run the terminal gate, which re-derives the claim rather than trusting the ledger:\npython3.12 skills/work/scripts/gate_executor.py check --gate victory_cert --task task_victory_auditor --cmd '<full test command>'\nIt exits 0 only when every task is PASSED, a strict forensic audit is clean, and a verification run against the current tree exited 0. Exit 1 is VICTORY REJECTED; write the reason it gave into .agents/victory_auditor/handoff.md. Do not write VICTORY CONFIRMED unless that command exited 0."
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
