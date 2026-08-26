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
4. **Enforce Doubt-Driven Disproof**: The dynamic judge actively searches for edge-case failures and broken assumptions.
5. **Remediate on Failure**: If any check fails, generate a concrete delta report and retry (max 3 retries).

---

## 💡 Concrete Example

### Fixture: Static Verifier Script (`verify_static.py`)
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

### Fixture: Blinded Dynamic Judge Rubric (`rubric.json`)
```json
{
  "criteria": [
    {
      "name": "Correctness",
      "weight": 0.5,
      "rule": "Handles null and negative integers without crashing."
    },
    {
      "name": "Security",
      "weight": 0.5,
      "rule": "Does not execute un-sanitized SQL or shell strings."
    }
  ],
  "pass_threshold": 0.9
}
```

---

## 🚫 Hard Constraints

*   **NEVER** sign off on deliverables without running the deterministic static verification script.
*   **NEVER** pass author rationale or conversational history to the blinded dynamic judge.
*   **NEVER** allow more than 3 remediation retry cycles without halting for human inspection.
