---
name: test
description: Enforces Test-Driven Development (TDD) and Prove-It bug reproduction before writing implementation code. Auto-invokes during coding phases or via `/test`.
---

# Test

## Overview

Execute test-driven development (TDD) by writing failing tests before implementing functional code. For bug fixes, reproduce the failure with a test first.

## When to Use

- Use when implementing new features or extending existing codebase functionality.
- Use when fixing bugs to ensure a regression test exists (Prove-It pattern).
- Do NOT skip testing unless writing purely static/documentation files.

## Core Process

For new features:

1. Write tests that describe the expected behavior (they should FAIL).
2. Implement the code to make them pass.
3. Refactor while keeping tests green.

For bug fixes (Prove-It pattern):

1. Write a test that reproduces the bug (must FAIL).
2. Confirm the test fails.
3. Implement the fix.
4. Confirm the test passes.
5. Run the full test suite for regressions.

For browser-related issues, also invoke `browser-testing-with-devtools` to verify with Chrome DevTools MCP.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Writing tests first is too slow; I will write them after the implementation." | Writing tests first defines clear boundaries and prevents implementing speculative, unneeded features. |
| "This bug is obvious, so I don't need a reproducing test before fixing it." | Without a reproducing test, you cannot prove your fix actually resolved the root cause or prevent future regressions. |

## Red Flags

- Writing functional code before a failing test has been created.
- Submitting code changes without verifying that the entire test suite passes.
- Mocking complex dependencies heavily instead of using simple stubs or integration tests.

## Verification

After completing the testing process, confirm:
- [ ] A failing test was successfully written first (to prove behavior or reproduce a bug).
- [ ] The implementation has been completed and makes all tests pass.
- [ ] The full test suite runs and completes with a 100% pass rate.
