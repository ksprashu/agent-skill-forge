# 🛡️ Swarm Integrity Modes: Development, Demo & Benchmark

The Google Antigravity Work Swarm enforces three distinct **Integrity Modes**, directly aligned with Google Antigravity Teamwork (`/teamwork-preview`). The integrity mode determines the strictness of the **Forensic Integrity Auditor** and the acceptable engineering shortcuts for Worker subagents.

---

## 1. Mode Summary Matrix

| Dimension | `development` (Default) | `demo` | `benchmark` (Zero-Shortcut) |
|---|---|---|---|
| **Primary Goal** | Feature velocity & pragmatic delivery | Standalone capability showcase | Pure empirical proof & evaluation |
| **Open-Source Copying** | Permitted with clean attribution | Permitted for utilities only | **STRICTLY FORBIDDEN** |
| **Pre-built Libraries** | Any standard library/package | Permitted | Permitted only for base runtime |
| **Unit Test Mocks** | Permitted for external I/O & DB | Permitted only for remote APIs | **STRICTLY FORBIDDEN** (AST Veto) |
| **External Script Delegation** | Permitted | **FORBIDDEN** (must run self-contained) | **FORBIDDEN** |
| **Reading Test Answers** | Permitted | Discouraged | **STRICTLY FORBIDDEN** (Blind implementation) |
| **Forensic Audit Rigor** | Checks tampering & tautologies | Checks standalone self-containment | Full AST parse + SHA-256 proof ledger |

---

## 2. Detailed Protocols

### 🛠️ Mode 1: `development`
*   **Philosophy**: Maximize engineering throughput while maintaining high code quality.
*   **Permitted**:
    - Using industry-standard third-party dependencies (`requests`, `pydantic`, `axios`).
    - Standard unit test mock fixtures for external services (Stripe, AWS, email providers).
    - Incremental exploratory debugging.
*   **Forensic Auditor Checks**:
    - Flags **Tautological Assertions** (`assert True`, `expect(true).toBe(true)`).
    - Flags **Test Tampering** (deleted test assertions, added `@pytest.mark.skip`).
    - Standard mocks emit non-blocking `WARNING`.

---

### 🎪 Mode 2: `demo`
*   **Philosophy**: Showcase genuine, standalone system capabilities without fragile runtime crutches.
*   **Rules**:
    - The deliverable must execute cleanly in a self-contained local environment without requiring proprietary external tool harnesses or human manual intervention.
    - Core domain logic cannot be stubbed out with mock facades.
*   **Forensic Auditor Checks**:
    - Verifies that all demo scripts and entrypoints run to exit code 0.
    - Flags external script delegation or unconfigured network prerequisites.

---

### 🔬 Mode 3: `benchmark`
*   **Philosophy**: Total empirical purity and non-self-certifying verification.
*   **Strict Prohibitions**:
    1. **Zero Synthetic Mocks**: Any occurrence of `unittest.mock`, `MagicMock`, `jest.fn()`, `vi.fn()`, or `sinon` triggers an immediate **Binary Veto**.
    2. **Zero Test Contamination**: Implementing workers must NOT inspect test implementation source code prior to writing feature code.
    3. **Zero Hardcoded Stubs**: Functions returning static values specifically to satisfy test fixtures are treated as adversarial breaches.
*   **Forensic Auditor Mandatory Tooling**:
    - Must execute:
      ```bash
      python3.12 skills/work/scripts/forensic_audit.py --integrity-mode benchmark --strict
      ```
    - Must record SHA-256 process evidence into `.agents/EVIDENCE.md` for all verification passes.
    - Requires 100% exit code 0 and clean AST verification before milestone sign-off.
