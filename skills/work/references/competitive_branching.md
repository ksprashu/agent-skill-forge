# 🏆 Competitive Branching, Design Tournaments & Arbiter Synthesis

In high-stakes software engineering (e.g. designing core architectures, choosing database technologies, concurrency synchronizers, parser designs, or major refactors), choosing the wrong strategy upfront leads to catastrophic rewrites.

The **Competitive Branching Pattern** operates at two distinct tiers:
1. **Tier 1: Architectural Design Tournaments**: Competing design proposals written in parallel before code is written, evaluated by an Architectural Arbiter, with major trade-offs escalated to the user.
2. **Tier 2: Prototyping Spikes & Implementation Tournaments**: Competing code branches executed in parallel isolated workspaces, evaluated via empirical benchmarks and unit test suites.

---

## 🏛️ Tier 1: Architectural Design Tournaments

```
                     [SPEC.md Verified by Socratic Grilling]
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
     ┌───────────────────────┐                     ┌───────────────────────┐
     │ DESIGN ARCHITECT ALPHA│                     │ DESIGN ARCHITECT BETA │
     │ Proposal Alpha        │                     │ Proposal Beta         │
     │ e.g. In-Memory Cache  │                     │ e.g. SQLite Storage   │
     └───────────┬───────────┘                     └───────────┬───────────┘
                 │                                             │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                           ┌─────────────────────────┐
                           │  ARCHITECTURAL ARBITER  │
                           │ Runs arbiter_eval.py    │
                           │ Generates scorecard.md  │
                           └────────────┬────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
             [Trade-offs Unambiguous]        [Fundamental Trade-off]
                       │                                 │
                       ▼                                 ▼
               SYNTHESIZE DESIGN.md            SENTINEL ASKS USER
                       │                       (ask_question Choice Card)
                       │                                 │
                       └────────────────◄────────────────┘
                                        │
                                        ▼
                         [Approve Authoritative DESIGN.md]
```

### 1. Authoring Competing Proposals
Design architects write structured markdown proposals in `.agents/design/proposals/`:
- **Proposal Alpha (`proposal_alpha.md`)**: Explores primary hypothesis (e.g., in-memory trie, sync API, client-side caching).
- **Proposal Beta (`proposal_beta.md`)**: Explores alternative hypothesis (e.g., SQLite FTS5 virtual table, event-driven worker, server action pagination).

#### Mandatory Visual Production Deliverables
Every proposal MUST include three complete, copyable Mermaid visual models adhering to [Visual Production Guide](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/work/references/visual_production_guide.md):
1. **High-Level System Architecture Diagram** (`flowchart TD`): Full topology spanning client ingress, application layers, event queues, and storage engines.
2. **C4 Level 2/3 Component Block Diagram** (`graph TD` or `flowchart LR`): Internal container boundaries, technology annotations, and strict node label quoting `id["Label (Context)"]`.
3. **Lifecycle Sequence & Dataflow Diagram** (`sequenceDiagram` with `autonumber`): Step-by-step request flow, concurrency blocks (`par`), and fallback branches (`alt`).

Proposals missing these visual models will fail the Architectural Arbiter evaluation gate.

### 2. Automated Arbiter Scoring
The Architectural Arbiter evaluates proposals across 4 axes using `arbiter_eval.py`:
1. **Architecture & Spec Grounding (30 pts)**: Coverage of requirements $R_1 \dots R_n$ and non-goals from `SPEC.md`, including complete Mermaid architecture models.
2. **Interface & Data Contracts (25 pts)**: Schema definitions, TypeScript types, migration cleanliness.
3. **Failure Modes & Resilience (25 pts)**: Concurrency, error handling, retry limits, security boundary checks.
4. **Simplicity & Unslop (20 pts)**: Avoidance of unnecessary abstractions, minimal dependencies, zero AI fluff words.

Run command:
```bash
python3.12 skills/work/scripts/arbiter_eval.py \
  --design-alpha .agents/design/proposals/proposal_alpha.md \
  --design-beta .agents/design/proposals/proposal_beta.md \
  --output-scorecard .agents/design/arbiter_scorecard.md
```

### 3. User Choice Escalation Protocol & "What-If" Simulator
If the Arbiter identifies genuine trade-offs that affect operational ergonomics, durability, or external dependencies, it marks the recommendation as `USER_DECISION_REQUIRED` and compiles an interactive Generative UI simulator:
1. **Compile What-If Simulator**: Arbiter calls `visual_engine.compile_what_if_simulator` to generate `.agents/design/what_if_simulator.html` with Canvas 2D radar visualizers, interactive range sliders, and headless comparison tables.
2. **Present Choice Modal**: The Sentinel reviews the artifact and presents an interactive choice modal via `ask_question`:
   - Option 1 (Recommended): Proposal Alpha trade-off summary (latency vs persistence).
   - Option 2: Proposal Beta trade-off summary (persistence vs latency).
3. **Synthesize Approved Design**: Once the user selects an option, the Arbiter records the user decision in `.agents/design/DESIGN.md` § 4, integrating the approved architecture and visual models into `DESIGN.md`.

---

## 🔬 Tier 2: Prototyping Spikes & Implementation Tournaments

### 1. Validation Spikes (Pre-Build)
For high-risk assumptions (e.g. latency budgets, novel library compatibility), dispatch a prototype worker in a branched workspace (`Workspace: "branch"`):
- Tests core hypothesis with minimal code.
- Runs micro-benchmarks.
- Emits `.agents/design/spike_results.md`.

### 2. Implementation Code Tournaments (Milestone Build)
During critical milestones, dispatch competing implementation workers in parallel:
```json
{
  "Subagents": [
    {
      "Role": "Worker Alpha — Approach A",
      "TypeName": "self",
      "Model": "flash",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 1 using Approach A in branch workspace. Required inputs: .agents/design/DESIGN.md. Output handoff to .agents/worker_alpha/handoff.md."
    },
    {
      "Role": "Worker Beta — Approach B",
      "TypeName": "self",
      "Model": "flash",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 1 using Approach B in branch workspace. Required inputs: .agents/design/DESIGN.md. Output handoff to .agents/worker_beta/handoff.md."
    }
  ]
}
```

### 3. Implementation Evaluation & Synthesis
The Arbiter evaluates both codebases:
```bash
python3.12 skills/work/scripts/arbiter_eval.py \
  --alpha-dir .agents/worker_alpha/ \
  --beta-dir .agents/worker_beta/ \
  --alpha-test "pytest tests/alpha" \
  --beta-test "pytest tests/beta" \
  --output-scorecard .agents/orchestrator/arbiter_scorecard.md
```
- **Dominant Winner**: Arbiter merges winning branch to mainline.
- **Close Scores**: Arbiter synthesizes Alpha's interface ergonomics with Beta's backend performance.
- Results advance to the **Adversarial Committee** for milestone gating.
