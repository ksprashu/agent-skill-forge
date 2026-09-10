# ⚔️ The Adversarial Committee: Reviewer, Challenger, Forensic Auditor & Victory Auditor

Self-certification by the implementing agent is the leading cause of software regressions and superficial implementations in multi-agent workflows. The Adversarial Committee enforces multi-layered verification with zero shared author bias.

---

## 1. Committee Roles & Responsibilities

| Role | Core Mission | Method | Veto Power? |
|------|-------------|--------|-------------|
| **Reviewer** | 5-Axis Code & Architectural Audit | Inspects git diffs, source files, and structure against quality standards. | Advisory / Blocking on Critical |
| **Challenger** | Empirical Failure Hunting & Edge Stress | Actively authors adversarial tests to break code, expose leaks, and trigger race conditions. | Empirical Blocking |
| **Forensic Auditor** | Anti-Mock & Cheat Detection | Inspects test fixtures, mocks, facades, and assertions for circumvention. | **BINARY VETO** |
| **Victory Auditor** | End-to-End Clean-Slate Certification | Executes full test suites, verification scripts, and builds from a cold environment. | **TERMINAL GATE** |

---

## 2. Detailed Protocols

### A. The Reviewer Protocol (`.agents/reviewer_m{i}_{j}/`)
Audits the worker's changes across five engineering axes:
1. **Correctness**: Logic edge cases, nullability, missing error handling.
2. **Security**: Injection vulnerabilities, credential leaks, unvalidated inputs, missing auth gates.
3. **Performance**: N+1 database queries, unbounded memory allocations, missing indices.
4. **Architecture**: Boundary violations, circular imports, interface contract deviations.
5. **Readability & Slop**: Unslops redundant abstractions, AI boilerplate, and fluff.
- Outputs `.agents/reviewer_m{i}_{j}/review.md` and `handoff.md`.

### B. The Challenger Protocol (`.agents/challenger_m{i}_{j}/`)
The Challenger operates under an adversarial mindset: *"How can I prove this code is broken?"*
- Does NOT merely review code statically.
- Writes concrete, runnable adversarial tests in `test/` or `tests/`:
  - **Cross-Tenant Isolation**: Can Tenant B read or write Tenant A's records?
  - **Concurrency & Race Conditions**: What happens under rapid duplicate requests?
  - **Rate Limiting & Evasion**: Can brute-force attacks bypass IP or token limits?
  - **Malformed Payloads**: Do unexpected JSON structures cause unhandled crashes?
- Executes tests directly:
  - If tests fail, the Challenger reports concrete failure stack traces.
  - The Worker MUST fix the code until the Challenger's tests pass.

### C. The Forensic Integrity Auditor Protocol (`.agents/auditor_m{i}_{j}/`)
The Forensic Auditor protects the project from self-delusion and test cheating.
- **Cheats Checked**:
  - Mocking away the actual business logic or database.
  - Hardcoded return values designed to pass specific unit test cases.
  - Deleting, skipping, or weakening existing test assertions.
  - Disabling linters or type checkers via file-wide ignore comments.
- **Binary Veto**: If any cheating or circumvention is detected, the auditor issues an immediate binary veto (`VERDICT: VETO`). The milestone CANNOT pass until fully remediated.

### D. The Victory Auditor Protocol (`.agents/victory_auditor/`)
Invoked exclusively by the Sentinel at the conclusion of all milestones:
- Runs in complete isolation with zero shared context from previous workers.
- Executes clean verification commands:
  ```bash
  npm test          # or pytest
  npm run verify    # or python scripts/verify.py
  npm run lint      # or tsc --noEmit / flake8
  npm run build     # or production packaging
  ```
- Asserts:
  1. 100% test pass rate.
  2. Zero lint/type errors.
  3. Clean build artifacts.
  4. Zero unencrypted secrets in git history.
- Emits formal verdict in `handoff.md`: `VICTORY CONFIRMED` or `VICTORY REJECTED`.
