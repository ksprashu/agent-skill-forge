# 🌐 Multi-Agent Team Topologies & Routing Engine

The Google Antigravity Work Swarm supports specialized team topologies directly mirroring and expanding the core routing patterns of Google Antigravity Teamwork (`/teamwork-preview`), incorporating the complete software engineering lifecycle from Socratic spec grilling to design tournaments, spikes, implementation, and layered verification.

---

## 1. Topologies Overview

```
                                  [ Incoming Request ]
                                           │
         ┌─────────────────────────┬───────┴─────────┬─────────────────────────┐
         ▼                         ▼                 ▼                         ▼
┌──────────────────┐      ┌─────────────────┐ ┌───────────────┐      ┌──────────────────┐
│  1. LIFECYCLE    │      │  2. FOCUSED FIX │ │ 3. DOC REVIEW │      │  4. MASSIVE /    │
│ Spec -> Design ->│      │ Single bug/ref  │ │ Papers & specs│      │    PROOFS        │
│ Spike -> Build ->│      │ Swift patch     │ │ Fact-check    │      │ Combinatorial    │
│ Layered Review   │      └─────────────────┘ └───────────────┘      └──────────────────┘
└──────────────────┘
```

---

## 2. Topology Specifications

### Topology 1: Full Lifecycle Engineering Swarm (`--topology lifecycle`)
- **Use Case**: New features, large-scale refactors, platform migrations, full-stack applications, and any project requiring rigorous design exploration and customer alignment.
- **Topology Hierarchy**:
  1. **Primary Thread Sentinel & Socratic Interviewer**: Conducts 1-question Socratic interviews until $\ge 95\%$ confidence, authoring `.agents/SPEC.md`. Presents design choice cards to the user via `ask_question`. Schedules heartbeat watchdog.
  2. **Dispatch-Only Orchestrator**: Manages state, resolves the Ready Frontier, and triggers succession at ~16 spawns.
  3. **Parallel Design Architects (Architect Alpha vs Beta)**: Author competing architectural proposals in `.agents/design/proposals/`.
  4. **Architectural Arbiter**: Evaluates proposals via `scripts/arbiter_eval.py`, manages trade-offs, and synthesizes `.agents/design/DESIGN.md`.
  5. **Validation Spike Workers**: Prototyping branches (`Workspace: "branch"`) to benchmark feasibility before production commit.
  6. **Staged Implementation Workers (M1..Mk)**: TDD implementation satisfying barrier gates (`exit_0`).
  7. **Multi-Perspective Layered Committee**:
     - **Design Reviewer**: Asserts code adheres to `.agents/design/DESIGN.md`.
     - **5-Axis Code Reviewer**: Audits Correctness, Security, Performance, Architecture, and Readability/Unslop.
     - **Adversarial Challenger**: Hostile fuzzing, boundary tests, and race conditions.
     - **Forensic Integrity Auditor**: Anti-mock AST check and SHA-256 evidence logging via `forensic_audit.py`.
  8. **Acceptance Reviewer**: Systematically audits all acceptance criteria in `.agents/SPEC.md`.
  9. **Victory Auditor**: Independent cold-run verification.

### Topology 2: Small Focused Fix Swarm (`--topology focused`)
- **Use Case**: Single self-contained bug, failing test case, screenshot styling fix, or targeted refactor.
- **Rule**: Keeps the team small and focused. Avoids multi-milestone decomposition.
- **Topology Hierarchy**:
  1. **Primary Sentinel**: Captures bug reproduction, minimal spec brief, and coordinates subagents.
  2. **Focused Implementation Worker**: Reproduces failure, writes minimal patch and regression test.
  3. **Adversarial Challenger & 5-Axis Reviewer**: Audits diff and attempts to break the fix with boundary tests.
  4. **Forensic Integrity Auditor**: Runs `scripts/forensic_audit.py` to ensure zero mock facades or test weakening.
  5. **Victory Auditor**: Final verification pass.

### Topology 3: Multi-Milestone Swarm (`--topology full`)
- **Use Case**: Multi-stage initiatives with pre-existing or external specifications where design proposals are already fixed.
- **Topology Hierarchy**: Explorers -> Staged Milestone Workers -> Adversarial Committee -> Victory Auditor.

### Topology 4: Document Review Swarm (`--topology review`)
- **Use Case**: Research papers, architectural design documents (ADRs), API specifications, or RFCs.
- **Topology Hierarchy**:
  1. **Primary Sentinel**: Captures document location and evaluation objectives.
  2. **Lead Document Reviewer**: Synthesizes document structure, primary claims, and core architecture.
  3. **Comparative Fact-Checker**: Researches external citations, verifies claims against official documentation or source code.
  4. **Inconsistency Inquisitor**: Scans for internal contradictions, underspecified boundary conditions, and security risks.
  5. **Standards & Unslop Auditor**: Evaluates conciseness, strips academic/AI boilerplate, and produces the finalized `review_deck.md`.

### Topology 5: Formal Proof & Algorithmic Swarm (`--topology proof`)
- **Use Case**: Formal logic, mathematical theorems, cryptographic routines, or complex algorithm invariants.
- **Topology Hierarchy**: Hypothesis Explorer -> Parallel Lemma Provers -> Adversarial Counterexample Fuzzer -> Proof Verifier.

### Topology 6: Massive Parallel Swarm (`--topology massive`)
- **Use Case**: Hard combinatorial problems, wide architectural spikes, deep optimization searches requiring 10+ concurrent exploration branches.
- **Topology Hierarchy**: Swarm Commander -> Speculative Worker Fleet (Workers A..N in isolated worktrees) -> Tournament Arbiter -> Adversarial Synthesis Committee.

---

## 3. Dynamic Routing Decision Matrix

| Trigger Signals | Recommended Topology | Flag |
|---|---|---|
| New feature, architectural choices, user interview needed | **Full Lifecycle Swarm** | `--topology lifecycle` |
| Single bug, stack trace, screenshot fix, quick refactor | **Small Focused Fix** | `--topology focused` |
| Pre-specified multi-milestone initiative | **Multi-Milestone Swarm** | `--topology full` |
| Paper URL, markdown spec review, architecture review | **Document Review** | `--topology review` |
| Math proof, cryptographic invariant, formal logic | **Formal Proof** | `--topology proof` |
| Explicit user request: *"use a very large team / massive parallel"* | **Massive Parallel Swarm** | `--topology massive` |
