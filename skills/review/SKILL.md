---
name: review
description: Review code, architecture, plans, and diffs across correctness, security, performance, and readability. Trigger via /review.
---

# Review: 5-Axis Code & Architecture Review

Conduct structured code reviews of git diffs across five engineering axes.

---

## 🎯 Goal
Identify defects, security flaws, performance regressions, and architectural inconsistencies before merging.

---

## 📋 Step-by-Step Workflow

1. **Inspect Diff**: Review staged changes (`git diff --staged`) or recent commits.
2. **Audit 5 Axes**:
   - **Correctness**: Logic bugs, off-by-one errors, missing error handling.
   - **Security**: SQL injection, XSS, unvalidated inputs, exposed secrets.
   - **Performance**: N+1 queries, memory leaks, unindexed database filters.
   - **Architecture**: Boundary violations, circular dependencies, coupling.
   - **Readability**: Obscure naming, redundant abstractions, code slop.
3. **Categorize Findings**: Group as **Critical** (blocking), **Important** (should fix), or **Suggestion** (optional).
4. **Provide Exact File:Line References**: Include actionable drop-in code fixes.

---

## 💡 Concrete Example

### Fixture: Review Report
```markdown
# Code Review Findings

### 🔴 Critical (Blocking)
*   [`src/api/auth.ts:L42`](file:///src/api/auth.ts#L42): SQL Injection risk in raw query concatenation.
    *   *Fix*: Use parameterized queries with `$1` bindings instead of string template interpolation.

### 🟡 Important (Should Fix)
*   [`src/db/queries.ts:L105`](file:///src/db/queries.ts#L105): Unbounded `SELECT * FROM logs` query without `LIMIT` or pagination.
    *   *Fix*: Add `LIMIT 100` and cursor-based pagination.

### 🟢 Suggestion (Optional)
*   [`src/utils/format.ts:L12`](file:///src/utils/format.ts#L12): Inline single-use helper `formatDateString`.
```

---

## 🚫 Hard Constraints

*   **NEVER** approve changes with unresolved Critical findings.
*   **NEVER** give vague approval ("looks good") without auditing all five axes.
*   **NEVER** omit file paths and line numbers from recommendations.
