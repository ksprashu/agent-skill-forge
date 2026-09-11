# 🌐 Multi-Agent Team Topologies & Routing Engine

The Google Antigravity Work Swarm supports **five specialized team topologies**, directly mirroring and expanding the core routing patterns of Google Antigravity Teamwork (`/teamwork-preview`).

---

## 1. Topologies Overview

```
                                 [ Incoming Request ]
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
         ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
         │  1. FULL SWARM  │     │ 2. FOCUSED FIX  │     │  3. DOC REVIEW  │
         │ Multi-milestone │     │ Single bug/ref  │     │ Papers & specs  │
         └─────────────────┘     └─────────────────┘     └─────────────────┘
                  │                       │
                  ▼                       ▼
         ┌─────────────────┐     ┌─────────────────┐
         │ 4. FORMAL PROOF │     │5. MASSIVE SWARM │
         │ Math & lemmas   │     │ 10+ Speculative │
         └─────────────────┘     └─────────────────┘
```

---

## 2. Topology Specifications

### Topology 1: Full Multi-Milestone Swarm (`--topology full`)
- **Use Case**: Complex end-to-end features, platform migrations, full-stack applications.
- **Topology Hierarchy**:
  1. **Primary Thread Sentinel**: User liaison, scaffolding, scheduled heartbeat watchdog.
  2. **Dispatch-Only Orchestrator**: Generates `PROJECT.md`, decomposes milestones (M1..Mk), adaptive self-succession at 16 spawns.
  3. **Parallel Explorers (2–3 agents)**: Deep dive into existing codebase, API docs, and dependencies.
  4. **Competitive Workers (Worker Alpha vs Beta)**: Isolated branch workspaces (`Workspace: "branch"`).
  5. **Architectural Arbiter**: Evaluates tournament via `scripts/arbiter_eval.py`.
  6. **Adversarial Committee**: Reviewer (5-axis), Challenger (hostile tests), Forensic Auditor (anti-mock veto).
  7. **Victory Auditor**: Final clean-slate verification.

### Topology 2: Small Focused Fix Swarm (`--topology focused`)
- **Use Case**: Single self-contained bug, failing test case, screenshot styling fix, or contained refactor.
- **Rule**: Keeps the team small and focused. Avoids over-engineering or multi-milestone decomposition.
- **Topology Hierarchy**:
  1. **Primary Sentinel**: Sets up `.agents/ORIGINAL_REQUEST.md` and coordinates subagents.
  2. **Focused Implementation Worker**: Reads logs, reproduces failure, writes minimal patch and regression test.
  3. **Adversarial Challenger & Reviewer**: Audits git diff against 5 engineering axes and attempts to break the fix with boundary tests.
  4. **Forensic Integrity Auditor**: Runs `scripts/forensic_audit.py` to ensure zero mock facades or test weakening.

### Topology 3: Document Review Swarm (`--topology review`)
- **Use Case**: Research papers, architectural design documents (ADRs), API specifications, or RFCs.
- **Topology Hierarchy**:
  1. **Primary Sentinel**: Captures document location and evaluation objectives.
  2. **Lead Document Reviewer**: Synthesizes document structure, primary claims, and core architecture.
  3. **Comparative Fact-Checker**: Researches external citations, verifies claims against official documentation or source code.
  4. **Inconsistency Inquisitor**: Scans for internal contradictions, underspecified boundary conditions, and security risks.
  5. **Standards & Unslop Auditor**: Evaluates conciseness, strips academic/AI boilerplate, and produces the finalized `review_deck.md`.

### Topology 4: Formal Proof & Algorithmic Swarm (`--topology proof`)
- **Use Case**: Formal logic, mathematical theorems, cryptographic routines, or complex algorithm invariants.
- **Topology Hierarchy**:
  1. **Hypothesis Explorer**: Decomposes target conjecture into discrete lemmas.
  2. **Parallel Lemma Provers**: Concurrently construct proofs using formal verification or inductive reasoning.
  3. **Adversarial Counterexample Fuzzer**: Aggressively searches for edge-case counterexamples or arithmetic overflows.
  4. **Proof Verifier**: Validates completeness, logical continuity, and physical correctness.

### Topology 5: Massive Parallel Swarm (`--topology massive`)
- **Use Case**: Hard combinatorial problems, wide architectural spikes, deep optimization searches requiring 10+ concurrent exploration branches.
- **Topology Hierarchy**:
  1. **Swarm Commander**: Oversees task distribution across multiple branch workers.
  2. **Speculative Worker Fleet (Workers A..N)**: Dispatched in parallel isolated git worktrees (`Workspace: "branch"`).
  3. **Tournament Arbiter**: Runs automated scoring matrix across all candidates using `scripts/arbiter_eval.py`.
  4. **Adversarial Synthesis Committee**: Hardens and gates the final unified implementation.

---

## 3. Dynamic Routing Decision Matrix

| Trigger Signals | Recommended Topology | Flag |
|---|---|---|
| Single bug, stack trace, screenshot fix, quick refactor | **Small Focused Fix** | `--topology focused` |
| Multi-feature build, full-stack app, system redesign | **Full Multi-Milestone** | `--topology full` |
| Paper URL, markdown spec review, architecture review | **Document Review** | `--topology review` |
| Math proof, cryptographic invariant, formal logic | **Formal Proof** | `--topology proof` |
| Explicit user request: *"use a very large team / massive parallel"* | **Massive Parallel Swarm** | `--topology massive` |
