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
2. **Audit 5 Engineering Axes**:
   - **Correctness**: Logic bugs, off-by-one errors, missing error handling, nullability crashes.
   - **Security**: SQL injection, XSS, unvalidated inputs, exposed secrets, missing auth gates.
   - **Performance**: N+1 queries, memory leaks, unindexed database filters, runaway loops.
   - **Architecture**: Boundary violations, circular dependencies, coupling, interface mismatches.
   - **Readability & Slop**: Obscure naming, redundant single-use abstractions, AI boilerplate.
3. **Execute Empirical Challenger Mode (Adversarial Stress Testing)**:
   - In addition to static review, write and execute concrete adversarial tests targeting edge cases:
     - **Cross-Tenant / Boundary Isolation**: Assert that unauthorized actors or foreign tenants cannot access or mutate private resources.
     - **Concurrency & Race Conditions**: Assert idempotency and integrity under burst traffic.
     - **Rate Limiting & Evasion**: Assert that brute-force attacks are rejected (e.g. HTTP 429).
     - **Malformed Payloads**: Assert graceful validation errors on corrupt input structures.
4. **Categorize Findings**: Group as **Critical** (blocking), **Important** (should fix), or **Suggestion** (optional).
5. **Provide Exact File:Line References & Test Repros**: Include drop-in fixes and runnable failure reproduction scripts.

---

## 💡 Concrete Examples

### 1. Fixture: Static Review Report
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

### 2. Fixture: Adversarial Challenger Test Suite (`test/challenger.test.ts`)
```typescript
import { describe, it, expect } from 'vitest';
import { executeCheckIn } from '../src/services/checkin';

describe('Challenger: Cross-Tenant Isolation Challenge', () => {
  it('strictly rejects check-in if worker tenant does not match checkpoint tenant', async () => {
    const foreignWorkerSession = { tenantId: 'tenant_beta', workerId: 'w_02' };
    const targetCheckpoint = { tenantId: 'tenant_alpha', checkpointId: 'cp_01' };

    await expect(executeCheckIn(foreignWorkerSession, targetCheckpoint))
      .rejects.toThrow('Cross-tenant check-in prohibited: HTTP 403');
  });
});
```

---

## 🚫 Hard Constraints

*   **NEVER** approve changes with unresolved Critical findings.
*   **NEVER** give vague approval ("looks good") without auditing all five axes.
*   **NEVER** claim code works without running empirical tests when operating as Challenger.
*   **NEVER** omit file paths and line numbers from recommendations.
