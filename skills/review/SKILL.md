---
name: review
description: Conduct structured code reviews and repository audits across 8 engineering dimensions with empirical challenger testing and mechanical schema validation. Trigger via /review, /review --diff, or /review --repo.
---

# Review Orchestrator: High-Signal Code & Architecture Quality Engineering

Conduct empirical, architectural, and adversarial code reviews and repository audits across 8 engineering dimensions.

---

## 1. Dual-Mode Dispatch Router

Route requests based on invocation trigger and scope:

- **Mode A: Pull Request / Local Diff Review** (Default: `/review` or `/review --diff`):
  Focused review on staged diffs (`git diff --staged`) or active feature PRs. Trace execution dataflow (`Route -> Service -> DB -> Egress`). Emit badged inline feedback with drop-in Before/After remediations.
  > **Instruction:** Read `references/workflows.md#2-mode-a-pull-request--local-diff-review-pipeline` for the full 6-Phase PR review lifecycle.

- **Mode B: Macro Repository QE Audit** (`/review --repo` or `/review --audit`):
  Comprehensive top-to-bottom health audit of the entire codebase or release candidate. Map topology, run the repo's own linters and type checkers, conduct 4-tier layered audit, and generate the formal Executive Audit Report (Scorecard + Heatmap).
  > **Instruction:** Read `references/workflows.md#3-mode-b-macro-repository-quality-engineering-audit-pipeline` for the 5-Pass audit methodology.

---

## 2. The 8-Axis QE Inspection Matrix

Cross-examine modifications and repository architecture across all 8 dimensions:

1. **Scope & Architecture**: Diff discipline (<500 lines logic), layering direction, interface segregation, backward compatibility.
2. **Correctness & Logic**: Boundary conditions, off-by-one errors, nullability/optionals, state transitions, numerical/time rigor.
3. **Security & Auth**: Injection flaw eradication, multi-tenant IDOR isolation, authn/authz gates, secret leakage, OWASP Top 10.
4. **Reliability & Concurrency**: TOCTOU race conditions, ACID transaction boundaries, deadlocks, resource leaks, graceful drainage.
5. **Performance & Scale**: N+1 query eradication, unindexed table scans, memory allocation bloat, connection pool exhaustion.
6. **Data Integrity & Migrations**: Reversible schema migrations, zero-downtime expand/contract, column constraints, idempotency.
7. **Test Suite Rigor**: Behavioral tests over implementation coupling, edge case coverage, flake prevention, mutation survival.
8. **Observability & Anti-Slop**: Structured logging context, latency metrics, actionable error messages, removal of AI boilerplate.

> **Instruction:** Read `references/checklist.md` for the complete 32-point inspection checklist and verification criteria.

---

## 3. Cognitive Effort Tiering (The 80 / 20 / 0 Rule)

Allocate reviewer cognitive bandwidth strictly according to system impact:

- **Tier 3: Deep Systems & Invariants (80% of Attention)**
  Race conditions, boundary violations, multi-tenant IDOR, data integrity, partial failure states, and migration hazards.
- **Tier 2: Architecture & Ergonomics (20% of Attention)**
  Public contract design, modularity, abstraction leaks, test effectiveness, and production observability.
- **Tier 1: Formatting, Syntax & Linters (0% of Attention)**
  Automated checks handled strictly by compilers, linters, and formatters (`tsc`, `eslint`, `ruff`). Never waste review commentary on automated style.

> **Instruction:** Read `references/conduct.md` for professional reviewer conduct, tone, and communication principles.

---

## 4. Empirical Challenger Mode (Adversarial Probing)

Never speculate or debate theoretical bugs. Act as an active adversary:
- Write and run concrete reproducer test scripts or fixtures targeting suspected race conditions, cross-tenant leaks, or edge failures.
- If a vulnerability or regression is suspected, prove it empirically before logging:
  - **Multi-Tenant Isolation**: Craft tests asserting Tenant A cannot access Tenant B resources.
  - **Concurrency Collision**: Simulate concurrent requests against check-then-act operations.
  - **Boundary Fuzzing**: Probe inputs with empty, negative, max-int, or malformed payloads.

---

## 5. Level 3 Mechanical Enforcement

Two deterministic S9 scripts ground the review. What each one does, and does not do:

1. **Fact Collection**: `review_collector.py` writes diff stats (files, lines, the >500-line flag), manifests, repository topology, and which linters, type checkers, test runners and CI systems are *configured* (by their config files) to `evidence.json`. It does not run those tools and does not read CI status:
   ```bash
   python3.12 skills/review/scripts/review_collector.py --diff --out evidence.json   # Mode A (PR review)
   python3.12 skills/review/scripts/review_collector.py --repo --out evidence.json   # Mode B (Repo audit)
   ```
   Then run the configured tools yourself (for example `ruff check`, `tsc --noEmit`) and read CI with `gh pr checks <n>`. Report anything you could not run as not inspected, never as passed.
2. **Defect Schema Validation**: `defect_validator.py` checks every defect against the Atomic Defect Schema (P3, Suggestion and Question entries need only a badge and location), and fails a report whose stated verdict contradicts its defects (APPROVED with an open P0/P1, CERTIFIED with an open P0-P2):
   ```bash
   python3.12 skills/review/scripts/defect_validator.py --file <report.md>
   ```

---

## 6. Output Standards & Defect Schema

Every defect finding must adhere to the Atomic Defect Schema (`[DEFECT-###]` or severity badge, markdown link to exact file and line range, blast radius, empirical reproducer, and Before/After diff).

> **Instruction:** Read `references/schemas.md` for the atomic defect template, PR review comment layout, and Executive Audit Dashboard format.

---

## 7. Hard Constraints

- **NEVER** approve changes with unresolved P0 (Critical) or P1 (High) findings.
- **NEVER** review unverified PRs if CI or automated static baselines are failing (check them yourself: the collector only detects which tools are configured).
- **NEVER** read diffs in alphabetical order; trace execution dataflow (`Route -> Service -> DB -> Egress`).
- **NEVER** omit exact file paths and line numbers from recommendations.
- **NEVER** downgrade P0/P1 blockers to meet delivery schedules.
- **NEVER** substitute review comments for missing linter or compiler rules.
