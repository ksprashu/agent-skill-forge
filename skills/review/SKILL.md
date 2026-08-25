---
name: review
description: Conducts a five-axis code review across correctness, readability, architecture, security, and performance. Auto-invokes before PR merge or via `/review`.
---

# Review

## Overview

Conduct a comprehensive, multi-dimensional code review of staged changes or recent commits across correctness, readability, architecture, security, and performance.

## When to Use

- Use before merging any pull request or committing changes.
- Use after completing a major task or implementation phase.
- Do NOT use in place of writing actual unit or integration tests.

## Core Process

Review the current changes (staged or recent commits) across all five axes:

1. **Correctness** — Does it match the spec? Edge cases handled? Tests adequate?
2. **Readability** — Clear names? Straightforward logic? Well-organized?
3. **Architecture** — Follows existing patterns? Clean boundaries? Right abstraction level?
4. **Security** — Input validated? Secrets safe? Auth checked? (Use `security-and-hardening` skill)
5. **Performance** — No N+1 queries? No unbounded ops? (Use `performance-optimization` skill)

Categorize findings as Critical, Important, or Suggestion.
Output a structured review with specific file:line references and fix recommendations.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The tests passed, so the code must be correct and doesn't need review." | Tests verify expected scenarios, but code review checks for security vulnerabilities, architectural consistency, and performance bottlenecks. |
| "I wrote this code, so I don't need to review it myself." | Self-review with a structured five-axis framework often catches mistakes or simplification opportunities that were missed during coding. |

## Red Flags

- Skipping security or performance considerations because "it's an internal tool."
- Giving vague feedback (e.g., "looks good") without analyzing the five axes.
- Failing to reference specific files and line numbers for recommended fixes.

## Verification

After completing the review, confirm:
- [ ] Staged or recent changes have been evaluated across all five axes.
- [ ] Findings are categorized clearly (Critical, Important, Suggestion).
- [ ] Specific file and line references are provided for all actionable items.
- [ ] A structured review report is presented to the user.
