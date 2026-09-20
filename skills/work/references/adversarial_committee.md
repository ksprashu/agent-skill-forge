# ⚔️ The Multi-Perspective Verification Committee

Self-certification by implementing agents is the leading cause of software regressions, architectural drift, and superficial implementations in multi-agent workflows. The Verification Committee enforces layered, multi-perspective verification with zero shared author bias.

---

## 1. Committee Roles & Responsibilities

| Role | Phase | Core Mission | Method | Veto Power? |
|------|-------|-------------|--------|-------------|
| **Design Reviewer** | Per Milestone | Architectural & Schema Adherence | Compares implementation AST and interfaces against `.agents/design/DESIGN.md`. | **BLOCKING** on Drift |
| **5-Axis Code Reviewer** | Per Milestone | Code Quality, Security & Slop Audit | Inspects git diffs against Correctness, Security, Performance, Architecture, and Readability. | **BLOCKING** on Critical |
| **Adversarial Challenger** | Per Milestone | Hostile Failure Hunting & Edge Stress | Authors runnable hostile tests for race conditions, boundary overflows, and payload corruption. | **EMPIRICAL BLOCKING** |
| **Forensic Integrity Auditor** | Per Milestone | Anti-Mock & Cheat Detection | Deterministic AST checks for mock facades, tautologies, test tampering, and SHA-256 ledgering. | **BINARY VETO** |
| **Acceptance Reviewer** | Post-Milestone | Requirements & AC Verification | Systematically audits implementation against every checkbox in `.agents/SPEC.md`. | **BLOCKING** on Incomplete |
| **Victory Auditor** | Terminal Gate | End-to-End Clean-Slate Certification | Executes full test suites, verification scripts, and production builds in a clean cold environment. | **TERMINAL GATE** |

---

## 2. Detailed Protocols

### A. Architectural Design Reviewer Protocol (`.agents/m{i}_design_rev/`)
The Design Reviewer guards against architectural drift and contract mutations:
1. Compares repository diff against `.agents/design/DESIGN.md`:
   - Are exported types and function signatures identical to approved interfaces?
   - Do database models or schemas deviate from agreed-upon migrations?
   - Are module boundaries respected without circular dependencies or layer-skipping?
2. Emits `.agents/m{i}_design_rev/review.md`. Any unauthorized interface change blocks milestone completion (`design_pass`).

---

### B. 5-Axis Code Reviewer Protocol (`.agents/m{i}_code_rev/`)
Audits changes across five core engineering axes using `skills/review` and `skills/unslop`:
1. **Correctness**: Logic edge cases, nullability, missing error handling, off-by-one errors.
2. **Security**: Injection vulnerabilities, credential leaks, unvalidated inputs, missing auth gates.
3. **Performance**: N+1 database queries, unbounded memory allocations, missing indices.
4. **Architecture**: Boundary violations, circular imports, interface contract deviations.
5. **Readability & Unslop**: Strips redundant abstractions, AI boilerplate, and fluff.
- Emits `.agents/m{i}_code_rev/review.md`. Requires `review_pass`.

---

### C. Adversarial Challenger Protocol (`.agents/m{i}_challenger/`)
Operates under an adversarial mindset: *"How can I prove this code is broken?"*
- Does NOT merely review code statically.
- Authors concrete, runnable adversarial tests in `test/` or `tests/`:
  - **Cross-Tenant / Boundary Isolation**: Can unauthorized actors mutate foreign records?
  - **Concurrency & Race Conditions**: Idempotency under rapid burst requests.
  - **Rate Limiting & Evasion**: Brute-force resilience.
  - **Malformed Payloads**: Graceful validation errors on corrupted input structures.
- Executes tests directly:
  - If tests fail, reports concrete failure stack traces.
  - The Worker MUST fix the code until the Challenger's tests pass with exit code 0.

---

### D. Forensic Integrity Auditor Protocol (`.agents/m{i}_forensic/`)
Protects the project from self-delusion and test cheating via `scripts/forensic_audit.py`:
- **Automated Tooling**:
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
- **Binary Veto**: If any cheating, mock facade, or tampering is detected, issues an immediate binary veto (`zero_mock`).

---

### E. Acceptance Reviewer Protocol (`.agents/acceptance_review/`)
Invoked after all implementation milestones have completed:
1. Loads `.agents/SPEC.md` and audits the entire repository against each requirement:
   - For every Requirement ($R_1 \dots R_n$), identifies verified test files and implementation paths.
   - For every Acceptance Criterion ($AC_1 \dots AC_n$), confirms empirical evidence.
2. Formats findings into `.agents/acceptance_review/report.md` with explicit pass/fail checkboxes.
3. Emits `acceptance_pass` only when 100% of criteria are proven with evidence.

---

### F. Victory Auditor Protocol (`.agents/victory_auditor/`)
Invoked exclusively by the Sentinel as the terminal barrier gate:
1. Runs in complete isolation with zero shared context from previous workers.
2. Executes clean verification commands and records proof hashes:
   ```bash
   python3.12 skills/work/scripts/forensic_audit.py --integrity-mode benchmark --exec-and-record "npm test"
   npm run verify    # or python scripts/verify.py
   npm run lint      # or tsc --noEmit / flake8
   npm run build     # or production packaging
   ```
3. Asserts:
   - 100% test pass rate with physical exit code 0.
   - Zero AST mock bypasses or tautological assertions.
   - Clean build artifacts and zero lint/type errors.
   - Zero unencrypted secrets in git history.
4. Emits formal verdict in `handoff.md`: `VICTORY CONFIRMED` or `VICTORY REJECTED` (`victory_cert`).
