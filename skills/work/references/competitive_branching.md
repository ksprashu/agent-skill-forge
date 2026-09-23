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
                           │ Generates evidence.md   │
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
Every proposal MUST include three complete, copyable Mermaid visual models adhering to [Visual Production Guide](../references/visual_production_guide.md):
1. **High-Level System Architecture Diagram** (`flowchart TD`): Full topology spanning client ingress, application layers, event queues, and storage engines.
2. **C4 Level 2/3 Component Block Diagram** (`graph TD` or `flowchart LR`): Internal container boundaries, technology annotations, and strict node label quoting `id["Label (Context)"]`.
3. **Lifecycle Sequence & Dataflow Diagram** (`sequenceDiagram` with `autonumber`): Step-by-step request flow, concurrency blocks (`par`), and fallback branches (`alt`).

Proposals missing these visual models will fail the Architectural Arbiter evaluation gate.

### 2. Arbiter Evidence Collection, then Judgement
`arbiter_eval.py` collects facts about the two proposals and stops there:

```bash
python3.12 skills/work/scripts/arbiter_eval.py \
  --design-alpha .agents/design/proposals/proposal_alpha.md \
  --design-beta .agents/design/proposals/proposal_beta.md \
  --output-report .agents/design/arbiter_evidence.md
```

The report contains, per proposal: the heading outline; substantive, trivial,
placeholder and unterminated code blocks counted separately; measured claims
with concrete numbers, quoted with line numbers; named alternatives that were
considered and rejected; unresolved `TBD`/`TODO` markers; hedging phrases that
promise a decision without making one; slop words; and the count of distinct
backticked identifiers. Its verdict field is always `JUDGEMENT_REQUIRED`.

**It does not score and does not pick a winner.** It used to award 100 points
across four axes, and on a two-sided fixture pair it preferred the hollow
proposal to the substantive one — a document of empty headings scored 95 and a
rigorous one 40. Because the Design Architects can read the scorer, a scorer
that rewards headings teaches them to write headings. The Arbiter agent reads
both proposals and the evidence, and decides.

Judge on: does each requirement $R_1 \dots R_n$ in `SPEC.md` have a mechanism
named against it; are the interface contracts concrete enough to implement
against; are the failure modes ones this system can actually hit; does the
proposal name what it gave up. A placeholder block and an unresolved marker in
the evidence report are the cheap tells — start there, then read.

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
During critical milestones, dispatch competing implementation workers in
parallel. Both run `inherit`: a tournament decided between two cheap-model
implementations tells you which cheap implementation won, not which design is
right.
```json
{
  "Subagents": [
    {
      "Role": "Worker Alpha — Approach A",
      "TypeName": "self",
      "Model": "inherit",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 1 using Approach A in branch workspace. Required inputs: .agents/design/DESIGN.md. Output handoff to .agents/worker_alpha/handoff.md."
    },
    {
      "Role": "Worker Beta — Approach B",
      "TypeName": "self",
      "Model": "inherit",
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
  --output-report .agents/orchestrator/arbiter_evidence.md
```
The report contains measurements, not a ranking: each candidate's test exit
code, test count, assertion count, source and test line counts, and any
benchmark output. Where a fact settles the question mechanically — one suite
green and the other red — the report says so (`SELECT_ALPHA`, `SELECT_BETA`,
`BOTH_REJECTED`). Where it does not, the verdict is `JUDGEMENT_REQUIRED` and the
Arbiter decides.

- **One candidate green, one red**: merge the green one. The report already says which.
- **Both green**: read both implementations. Line counts and assertion counts do not tell you which design will survive the next change; that is the judgement you were spawned to make.
- Results advance to the **Adversarial Committee** for milestone gating.
