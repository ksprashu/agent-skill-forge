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
      "Prompt": "Implement Milestone 2 using in-memory Trie indexing.\nWorking directory: .agents/worker_alpha/\nRequired Inputs: .agents/ORIGINAL_REQUEST.md, .agents/orchestrator/PROJECT.md\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Verify physical presence of .agents/ORIGINAL_REQUEST.md and PROJECT.md before proceeding. If missing, fail fast with error to parent.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-wait polling loops. Execution is event-driven.\n3. Handoff Delivery: Write implementation and tests in branch workspace. Verify builds pass with exit code 0. Report findings to .agents/worker_alpha/handoff.md. Send completion message to parent referencing handoff path."
    },
    {
      "Role": "Worker Beta — Approach B (SQLite Virtual Table)",
      "TypeName": "self",
      "Model": "flash",
      "Workspace": "branch",
      "Prompt": "Implement Milestone 2 using SQLite FTS5 virtual tables.\nWorking directory: .agents/worker_beta/\nRequired Inputs: .agents/ORIGINAL_REQUEST.md, .agents/orchestrator/PROJECT.md\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Verify physical presence of .agents/ORIGINAL_REQUEST.md and PROJECT.md before proceeding. If missing, fail fast with error to parent.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-wait polling loops. Execution is event-driven.\n3. Handoff Delivery: Write implementation and tests in branch workspace. Verify builds pass with exit code 0. Report findings to .agents/worker_beta/handoff.md. Send completion message to parent referencing handoff path."
    }
  ]
}
```

### Step 2: The Arbiter Evaluation Matrix
Once both workers emit their `handoff.md` reports and their artifacts physically exist on disk, the Orchestrator spawns the **Arbiter** subagent:
```json
{
  "Subagents": [
    {
      "Role": "Architectural Arbiter",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Architectural Arbiter.\nRequired Inputs: .agents/worker_alpha/handoff.md, .agents/worker_beta/handoff.md\n\n### 🛑 MANDATORY SUBAGENT OPERATIONAL INVARIANTS\n1. Pre-Flight Input Artifact Check: Assert physical presence of both worker handoff reports before beginning evaluation. If either is missing, fail fast with error to parent.\n2. Strict Prohibition on Polling Loops: Zero sleep commands or busy-waits. Execution is event-driven.\n3. Handoff Delivery: Run python3.12 skills/work/scripts/arbiter_eval.py. Measure correctness, latency, heap allocations, and simplicity. Synthesize the winning code into the main tree. Output scorecard to .agents/orchestrator/arbiter_scorecard.md. Send completion message to parent referencing scorecard path."
    }
  ]
}
```

1. **Functional Correctness**: Does the implementation pass 100% of requirement acceptance criteria?
2. **Empirical Benchmarks**: Runs `preferred/benchmark-harness` to measure p95 latency and heap allocations under load.
3. **Simplicity & Unslop**: Strips defensive wrappers, boilerplate, and unnecessary single-use abstractions (`skills/unslop`).
4. **Maintenance Burden**: Evaluates readability, external dependency count, and architectural clarity.

### Step 3: Synthesis & Mainline Integration
- If one approach clearly dominates, the Arbiter copies or merges that branch's changes to the main workspace.
- If both approaches have unique strengths (e.g. Alpha has better API ergonomics, Beta has better query performance), the Arbiter synthesizes the best components into the final implementation.
- The resulting code is then handed over to the **Adversarial Committee** (Reviewer, Challenger, Forensic Auditor) for final milestone gating.
