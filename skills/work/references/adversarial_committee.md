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
- **Automated Tooling**:
  The Forensic Auditor executes deterministic AST and tampering checks:
  ```bash
  python3.12 skills/work/scripts/forensic_audit.py --integrity-mode benchmark --strict
  ```
- **Cheats Checked**:
  - Mocking away physical business logic or database layers (AST check for `mock`, `jest.fn`, etc.).
  - Tautological assertions (`assert True`, `expect(true).toBe(true)`).
  - Hardcoded return values designed specifically to pass unit tests.
  - Git diff tampering (deleted assertions or added skip markers).
  - Disabling linters or type checkers via file-wide ignore comments.
- **Cryptographic Evidence Ledger**:
  All physical verification executions are hashed via SHA-256 and appended to `.agents/EVIDENCE.md`:
  ```bash
  python3.12 skills/work/scripts/forensic_audit.py --exec-and-record "pytest -v"
  ```
- **Binary Veto**: If any cheating, mock facade, or tampering is detected, the auditor issues an immediate binary veto (`VERDICT: VETO`). The milestone CANNOT pass until fully remediated.

### D. The Victory Auditor Protocol (`.agents/victory_auditor/`)
Invoked exclusively by the Sentinel at the conclusion of all milestones:
- Runs in complete isolation with zero shared context from previous workers.
- Executes clean verification commands and records proof hashes:
  ```bash
  python3.12 skills/work/scripts/forensic_audit.py --integrity-mode benchmark --exec-and-record "npm test"
  npm run verify    # or python scripts/verify.py
  npm run lint      # or tsc --noEmit / flake8
  npm run build     # or production packaging
  ```
- Asserts:
  1. 100% test pass rate with physical exit code 0.
  2. Zero AST mock bypasses or tautological assertions.
  3. Clean build artifacts and zero lint/type errors.
  4. Zero unencrypted secrets in git history.
- Emits formal verdict in `handoff.md`: `VICTORY CONFIRMED` or `VICTORY REJECTED`.
