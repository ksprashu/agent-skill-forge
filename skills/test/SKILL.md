---
name: test
description: Enforce Test-Driven Development and Prove-It bug reproduction before writing fixes.
---

# Test: Test-Driven Development & Prove-It

Write failing tests before writing implementation code. For bug fixes, reproduce the failure with a test first.

---

## 🎯 Goal
Guarantee high code reliability and prevent regressions by adhering to the Red-Green-Refactor loop.

---

## 📋 Step-by-Step Workflow

1. **Write Failing Test (Red)**: Write an automated test describing the expected behavior or reproducing the bug.
2. **Execute Test to Confirm Failure**: Run the test runner and verify it fails for the exact intended reason.
3. **Write Minimal Implementation (Green)**: Write only enough code to make the failing test pass.
4. **Verify Pass**: Re-run the test to confirm it turns green.
5. **Run Full Regression Suite**: Execute all project tests to ensure zero regressions across the codebase.

---

## 💡 Concrete Example

### Prove-It Bug Fix Example
**Step 1: Write Reproducing Test (`tests/test_calculator.py`)**
```python
def test_division_by_zero_returns_none_instead_of_crashing():
    # Bug: Currently throws unhandled ZeroDivisionError
    result = safe_divide(10, 0)
    assert result is None
```

**Step 2: Run test to confirm failure**
```bash
pytest tests/test_calculator.py
# FAILED: ZeroDivisionError: division by zero
```

**Step 3: Implement minimal fix (`src/calculator.py`)**
```python
def safe_divide(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return a / b
```

**Step 4: Verify test passes**
```bash
pytest tests/test_calculator.py
# 1 passed in 0.02s
```

---

## 🚫 Hard Constraints

*   **NEVER** write implementation code before running and seeing the test fail.
*   **NEVER** weaken or delete existing test assertions to make failing code pass.
*   **NEVER** skip running the full regression test suite before concluding a task.
