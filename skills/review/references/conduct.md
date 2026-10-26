# The Reviewer's Code of Conduct & Cognitive Bandwidth Guide

> **Purpose:** Professional conduct standards, communication principles, and cognitive budgeting guidelines for automated and human code reviewers.
> **Philosophy:** High-signal code review is an empirical, architectural, and empathetic collaboration. Reviewers protect system invariants while fostering trust and engineering excellence.
> **Standard:** Read on-demand per Progressive Disclosure rules. Governs all interactions and review outputs across Mode A and Mode B pipelines.

---

## 1. The 3-Tier Hierarchy of Review Concerns (The 80 / 20 / 0 Rule)

To prevent reviewer cognitive fatigue and maximize impact, mental effort must be allocated strictly according to the **3-Tier Hierarchy**:

```
┌────────────────────────────────────────────────────────────────────────┐
│               THE 3-TIER EFFORT HIERARCHY (80 / 20 / 0)                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   ▲  TIER 3: Deep Systems & Invariants                [ 80% OF TIME ]  │
│   │  • Correctness, boundary conditions, edge cases                    │
│   │  • Security boundaries, authorization, multi-tenant IDOR           │
│   │  • Race conditions, locking, async lifecycles, resource cleanup    │
│   │  • Data integrity, schema migrations, idempotency                  │
│   │                                                                    │
│   │  TIER 2: Architecture & Ergonomics                [ 20% OF TIME ]  │
│   │  • API contract design, backward compatibility                     │
│   │  • Modularity, separation of concerns, abstraction leaks           │
│   │  • Test suite effectiveness, flakiness eradication                 │
│   │  • Observability, structured logging, latency metrics              │
│   │                                                                    │
│   │  TIER 1: Formatting, Syntax & Types               [  0% OF TIME ]  │
│   │  • Automated linting, code style, formatting, import ordering      │
│   │  • Handled completely by linters, formatters, and compilers (CI)   │
│   ▼  • NEVER waste reviewer cognitive bandwidth on automated checks    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Tier 1: Formatting, Syntax & Types (0% Reviewer Energy)
- **The Rule:** Zero human or reviewer agent bandwidth should ever be spent on formatting, indentation, import sorting, or syntax nitpicking.
- **Enforcement:** Automated tools (`prettier`, `black`, `ruff`, `eslint`, `tsc`, `rustfmt`, `gofmt`) must enforce style in CI prior to review.
- **Handling Gaps:** If a stylistic issue slips through because a linter rule does not exist, **do NOT nitpick it in the PR review**. The correct remediation is submitting a separate PR to update the project linter configuration. Human review comments must never substitute for missing compiler or linter rules.

### 1.2 Tier 2: Architecture & Ergonomics (20% Reviewer Energy)
- Focus on architectural durability, interface clarity, and long-term maintainability.
- Evaluate whether abstractions leak implementation details, whether API changes preserve backward compatibility, whether tests are behavioral, and whether system observability (metrics, logs) is sufficient for production debugging.

### 1.3 Tier 3: Deep Systems & Invariants (80% Reviewer Energy)
- Reviewers dedicate 80% of their critical attention to problems automated tools cannot catch:
  - Complex concurrency race conditions (TOCTOU).
  - Multi-tenant data leakage (IDOR / BOLA).
  - Business invariant violations under partial failure.
  - Zero-downtime database migration hazards.
  - Cascading timeout and retry storms.

---

## 2. The 7 Golden Rules of Code Review

Synthesized from Staff QE principles and high-performing engineering practices, all reviews must obey these 7 Golden Rules:

### Rule 1: Evidence Over Assertion
- **Principle:** Never claim code is defective, slow, or insecure based on intuition alone.
- **Execution:** Back every claim with concrete evidence: a reproducible test case, an execution trace, an exact asymptotic analysis ($O(N^2)$ query loop), or a static analysis diagnostic.
- **Contrast:**
  - *Bad:* *"This might cause performance issues."*
  - *Good:* *"In lines 42–46, `fetch_user()` executes inside the loop over `organizations`, causing an $O(N)$ query cascade. Here is an eager-loading query that reduces this to a single batch fetch."*

### Rule 2: Actionable Over Philosophical
- **Principle:** Avoid abstract lectures or open-ended complaints. Provide drop-in solutions.
- **Execution:** Every identified defect must specify exact file and line coordinates, an explanation of the failure mode, and a drop-in `# Before` vs. `# After` code block that the author can immediately apply.
- **Contrast:**
  - *Bad:* *"The error handling in this module is poorly structured."*
  - *Good:* *"[`src/api/auth.py:L78`](file:///src/api/auth.py#L78): Unhandled `TokenExpiredError` causes an unmasked 500 Internal Server Error. Replace with this try/catch block returning a typed 401 Unauthorized."*

### Rule 3: No Blocker Downgrading
- **Principle:** Never compromise system integrity or customer trust for schedule convenience.
- **Execution:** P0 Critical and P1 High defects are absolute blockers to merge. Never downgrade a known security vulnerability, concurrency race condition, or data corruption risk to "fix in a follow-up PR". Technical debt accepted under pressure rarely gets remediated before production impact.

### Rule 4: Audit the Tests First
- **Principle:** A green test suite that asserts nothing is worse than no tests—it creates false confidence.
- **Execution:** Inspect newly introduced and modified test files *before* reviewing implementation logic. Verify that tests assert observable behavioral outcomes rather than internal mock calls (`expect(fn).toHaveBeenCalled()`). Check whether tests actually fail when business logic invariants are inverted.

### Rule 5: Critique the Code, Never the Author
- **Principle:** Depersonalize feedback to maintain psychological safety and collaboration.
- **Execution:** Frame observations around the code, data flow, specifications, and system invariants. Avoid personal pronouns ("you", "your").
- **Contrast:**
  - *Bad:* *"You forgot to sanitize the user input here."*
  - *Good:* *"This query concatenates raw string inputs without parameterization, exposing a SQL injection surface."*
  - *Bad:* *"Why did you write such an over-complicated function?"*
  - *Good:* *"This logic can be simplified using the standard library's `itertools.groupby`, reducing 30 lines to 4."*

### Rule 6: Demarcate Objective Defects from Subjective Tastes
- **Principle:** Never hold a pull request hostage over personal aesthetic preferences.
- **Execution:** Clearly badge suggestions that are not strictly required for correctness, security, or performance as `[P3: Low - Suggestion/Nit]` or `[Question]`. Explicitly inform the author that P3 items and questions do not block merging.

### Rule 7: Reinforce Exemplary Engineering
- **Principle:** Code review is a teaching tool and culture builder, not merely a bug trap.
- **Execution:** Actively acknowledge well-crafted solutions, thorough test suites, elegant abstractions, and clear documentation in review summaries. Positive reinforcement drives engineering excellence across the entire organization.
- **Example:** *"Commendable concurrency test suite—testing simultaneous race conditions with barrier latches prevents critical production regressions."*

---

## 3. Communication, Psychological Safety & Feedback Delivery

### 3.1 Socratic Inquiry vs. Prescriptive Directives
When encountering ambiguous architectural decisions:
- Use Socratic questions prefixed with `[Question]` to understand author intent before declaring an approach defective.
- Example: *"What was the rationale for choosing polling over WebSocket notifications here? Is it to minimize persistent connection overhead on the edge gateway?"*

### 3.2 Resolving Deadlocks & Escalation
1. **Focus on Requirements:** Anchor discussions to documented requirements, SLAs, and the Engineering Standard.
2. **Bring Empirical Proof:** When disagreement persists on a potential bug or race condition, write an adversarial challenger test script proving the failure mode under realistic inputs.
3. **Timeboxed Escalation:** If consensus cannot be reached within 2 review rounds, escalate to the Tech Lead or Staff Engineer for binding architectural arbitration.

### 3.3 Re-Review Turnaround SLA
- **The Golden Rule of Velocity:** Reviewers must prioritize re-reviewing updated diffs above opening new reviews.
- When an author addresses feedback and pushes commits, the reviewer should re-verify the targeted diff within **4 business hours** (for PR diffs) or **24 hours** (for large repository audits) to prevent context switching and branch rot.
