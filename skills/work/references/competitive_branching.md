# 🏆 Competitive Branching & Arbiter Synthesis

In high-stakes software engineering (e.g. designing core algorithms, high-concurrency database synchronizers, parser architectures, or complex refactors), choosing the wrong implementation strategy upfront leads to expensive rewrites.

The **Competitive Branching Pattern** allows the Orchestrator to dispatch multiple competing workers in parallel, each exploring a distinct implementation hypothesis, before an Arbiter selects or synthesizes the optimal solution.

---

## 1. When to Use Competitive Branching
- **Algorithmic Alternatives**: Approach A (e.g. iterative scan) vs Approach B (e.g. interval tree index).
- **Architecture Spikes**: REST vs GraphQL endpoints; Server Actions vs API routes.
- **Performance Optimization**: Comparing memory overhead vs CPU throughput under load.
- **Complex Refactors**: Evaluating two different decoupling patterns without risking the main branch.

---

## 2. The Tournament Protocol

```
                        [Start Milestone Task]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌─────────────────────────┐                       ┌─────────────────────────┐
│     WORKER ALPHA        │                       │       WORKER BETA       │
│ • Branch / Dir A        │                       │ • Branch / Dir B        │
│ • Approach A            │                       │ • Approach B            │
│ • Unit tests & design   │                       │ • Unit tests & design   │
└────────┬────────────────┘                       └────────┬────────────────┘
         │                                                 │
         └────────────────────────┬────────────────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │   THE ARBITER SUBAGENT  │
                     │ • Executes shared tests │
                     │ • Benchmarks latency    │
                     │ • Evaluates unslop/code │
                     │ • Selects winner/merges │
                     └────────────┬────────────┘
                                  │
                                  ▼
                     [Adversarial Committee Gate]
```

### Step 1: Dispatch Competing Workers in Isolated Workspaces
The Orchestrator dispatches two workers simultaneously using `invoke_subagent`:
```json
{
  "Subagents": [
    {
      "Role": "Worker Alpha — Approach A (In-Memory Index)",
      "TypeName": "self",
      "Model": "flash",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 2 using in-memory Trie indexing. Working directory: .agents/worker_alpha/. Write implementation and tests."
    },
    {
      "Role": "Worker Beta — Approach B (SQLite Virtual Table)",
      "TypeName": "self",
      "Model": "flash",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 2 using SQLite FTS5 virtual tables. Working directory: .agents/worker_beta/. Write implementation and tests."
    }
  ]
}
```

### Step 2: The Arbiter Evaluation Matrix
Once both workers emit their `handoff.md` reports, the Orchestrator spawns the **Arbiter** subagent (`Role: "Architectural Arbiter"`):
1. **Functional Correctness**: Does the implementation pass 100% of requirement acceptance criteria?
2. **Empirical Benchmarks**: Runs `preferred/benchmark-harness` to measure p95 latency and heap allocations under load.
3. **Simplicity & Unslop**: Strips defensive wrappers, boilerplate, and unnecessary single-use abstractions (`skills/unslop`).
4. **Maintenance Burden**: Evaluates readability, external dependency count, and architectural clarity.

### Step 3: Synthesis & Mainline Integration
- If one approach clearly dominates, the Arbiter copies or merges that branch's changes to the main workspace.
- If both approaches have unique strengths (e.g. Alpha has better API ergonomics, Beta has better query performance), the Arbiter synthesizes the best components into the final implementation.
- The resulting code is then handed over to the **Adversarial Committee** (Reviewer, Challenger, Forensic Auditor) for final milestone gating.
