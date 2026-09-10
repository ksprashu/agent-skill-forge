---
name: verify
description: Run deterministic static verifier scripts and blinded multi-persona rubrics to prove requirements. Trigger via /verify.
---

# Verify: Dual-Layer Expectation Verification

Enforce Expectation-Grounded Alignment (EGA) through deterministic static check scripts and blinded dynamic judge rubrics.

---

## 🎯 Goal
Prove that deliverables satisfy architectural contracts, word bounds, schemas, and functional behavior with zero author bias.

---

## 📋 Step-by-Step Workflow

1. **Synthesize Expectations First**: Before writing deliverables, define deterministic static check scripts (`verify_static.py`) and blinded rubrics (`rubric.json`).
2. **Execute Static Layer**: Run the Python/Node static verifier to check AST, schema validity, link integrity, and formatting bounds.
3. **Run Blinded Dynamic Judge**: Evaluate the raw deliverable without exposing the author's internal thinking or conversation history.
4. **Conduct Forensic Integrity Audit (Anti-Mock Gate)**:
   - Inspect test suites, fixtures, and source files to verify real implementation.
   - Assert zero dummy mock facades replacing core business logic.
   - Assert zero hardcoded outputs designed specifically to satisfy unit tests.
   - Assert zero deleted, weakened, or commented-out test assertions.
   - If circumvention is detected, issue an immediate **Binary Veto** halting progression.
5. **Enforce Doubt-Driven Disproof**: The judge actively searches for edge-case failures, broken assumptions, and unhandled errors.
6. **Execute Independent Victory Audit**:
   - Before final sign-off, run a clean-slate empirical test and build pass with zero shared context from implementing agents.
   - Emit formal verdict: `VICTORY CONFIRMED` or `VICTORY REJECTED`.
7. **Remediate on Failure**: If any check fails, generate a concrete delta report and retry (max 3 retries).

---

## 💡 Concrete Examples

### 1. Fixture: Static Verifier Script (`verify_static.py`)
```python
import os, sys, json

def verify():
    # 1. File exists
    assert os.path.exists("dist/bundle.json"), "Missing dist/bundle.json"
    
    # 2. Schema validity
    with open("dist/bundle.json") as f:
        data = json.load(f)
    assert "version" in data, "Missing version field in bundle.json"
    assert len(data.get("items", [])) > 0, "Items list cannot be empty"
    
    print("✅ Static verification PASSED")

if __name__ == "__main__":
    verify()
```

### 2. Fixture: Forensic Integrity Audit Checklist
```markdown
# Forensic Integrity Audit Check
- [ ] No hardcoded mock returns replacing business logic
- [ ] Real database / network integration verified (no fake in-memory facades)
- [ ] No weakened or deleted test assertions from baseline
- [ ] No `@ts-ignore` or file-wide linter disable comments hiding defects
- [ ] Verdict: PASS or BINARY VETO
```

---

## 🚫 Hard Constraints

*   **NEVER** sign off on deliverables without running the deterministic static verification script.
*   **NEVER** pass author rationale or conversational history to the blinded dynamic judge.
*   **NEVER** tolerate mock facades, cheated assertions, or hardcoded return values (Binary Veto).
*   **NEVER** report task completion without clean-slate Victory Audit confirmation.
*   **NEVER** allow more than 3 remediation retry cycles without halting for human inspection.
