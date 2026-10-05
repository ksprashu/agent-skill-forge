# Standardized Review Schemas & Reporting Templates

> **Purpose:** Canonical schemas, severity taxonomy, and reporting templates for all review deliverables.
> **Enforcement:** Enforced mechanically by `skills/review/scripts/defect_validator.py` (L3 Validator) per `docs/ENGINEERING_STANDARD.md`.
> **Standard:** Read on-demand per Progressive Disclosure rules. Every finding produced across Mode A and Mode B must adhere to the schemas defined herein.

---

## 1. Severity Classification & Operational SLA Matrix

Every defect logged in a code review or repository audit must be assigned an unambiguous severity tier.

| Severity Level | Standard Badge | Definition & System Impact | Operational SLA | PR Merge Rule |
| :---: | :--- | :--- | :---: | :---: |
| **P0** | 🔴 **`[P0: Critical - Blocker]`** | Exploitable security vulnerability (RCE, SQLi, Auth bypass, cross-tenant IDOR), silent data loss/corruption, or crash in critical user path. Zero workaround. | **Immediate** | **Hard Blocker** (Merge prohibited) |
| **P1** | 🟠 **`[P1: High - Blocker]`** | Broken core business invariant, concurrency race condition (TOCTOU), resource leak, unhandled payment state, or breaking public contract. Complex workaround. | **24–48 hours** | **Hard Blocker** (Merge prohibited) |
| **P2** | 🟡 **`[P2: Medium - Important]`** | Edge-case logic defect, unindexed database query (N+1), missing edge schema validation, or fragile error recovery. Simple workaround exists. | **Next sprint** | **Soft Blocker** (Requires Tech Lead sign-off) |
| **P3** | 🟢 **`[P3: Low - Suggestion/Nit]`** | Non-blocking code hygiene, dead code, single-use wrapper cleanup, or readability enhancement. | **Backlog** | **Non-blocking** (Merge allowed) |
| **REQ** | ❓ **`[Question / Discussion]`** | Socratic inquiry into architectural rationale, non-obvious trade-offs, or unclear requirements. Requests author clarification. | **Current review cycle** | **Non-blocking** (May escalate if answers reveal P0/P1) |

### Blocker Rules & Downgrade Prevention:
- **Zero Blocker Downgrading:** Under no circumstances may a P0 Critical or P1 High defect be downgraded to P2 or P3 to meet delivery deadlines or sprint commitments.
- **Escalation Path:** If an author disputes a P0/P1 classification, the disagreement must be escalated to the Staff QE / Tech Lead with empirical test reproduction traces.

---

## 2. Standardized Atomic Defect Schema

Every logged defect, whether embedded in a PR comment or an Executive Dashboard, must adhere to this standardized schema:

````markdown
### [DEFECT-<ID>] <Badge> <Concise, Imperative Defect Title>

- **Severity:** P0: Critical | P1: High | P2: Medium | P3: Low
- **Engineering Axis:** Scope & Architecture | Correctness & State | Security & Isolation | Reliability & Concurrency | Performance & Scale | Data Integrity | Test Rigor | Observability & Hygiene
- **Location:** [`<relative_path>:<line_range>`](file:///<absolute_path>#L<start>-L<end>)
- **Component / Subsystem:** `<Module or Package Name>`

#### 1. Vulnerability / Defect Description
<Precise, technical explanation of existing behavior, root cause, and failure mechanism.>

#### 2. Blast Radius & Production Impact
<Concrete real-world impact: affected tenants, data corruption risk, resource exhaustion, financial liability, or cascade failure.>

#### 3. Empirical Proof / Reproduction Fixture
```typescript
// Concrete reproduction test or script that fails against the current code
it('reproduces failure condition against vulnerable implementation', async () => {
  const result = await vulnerableFunction({ input: maliciousPayload });
  expect(result.corrupted).toBe(true);
});
```

#### 4. Drop-in Remediation
**Current Defective Code ([`<file_path>:<line_range>`](file:///<file_path>#L<start>-L<end>)):**
```python
# Before
<Defective implementation lines>
```

**Proposed Drop-in Fix:**
```python
# After
<Drop-in remediation correcting the defect>
```

#### 5. Verification Gate Command
`<Exact CLI test command that confirms the defect is resolved by the proposed fix>`
````

---

### Concrete Exemplar: Atomic Defect

````markdown
### [DEFECT-001] 🔴 [P0: Critical - Blocker] TOCTOU Race Condition in Concurrent Account Withdrawal

- **Severity:** P0: Critical
- **Engineering Axis:** Reliability & Concurrency
- **Location:** [`src/services/billing.py:L42-L51`](file:///src/services/billing.py#L42-L51)
- **Component / Subsystem:** `billing-service`

#### 1. Vulnerability / Defect Description
The withdrawal endpoint performs a separate "Check-Then-Act" sequence: it fetches the account balance via `find_one`, verifies in application memory that `balance >= amount`, and subsequently issues an `$inc` update. Under concurrent requests with the identical `account_id`, multiple worker threads read the initial balance simultaneously before any decrement executes, permitting negative balances and double-spending.

#### 2. Blast Radius & Production Impact
Direct financial loss and database corruption. An automated user or client retrying network requests can overdraft balances beyond established credit limits. Affects all payment withdrawal and ledger balance operations.

#### 3. Empirical Proof / Reproduction Fixture
```python
import asyncio
import pytest
from src.services.billing import withdraw

@pytest.mark.asyncio
async def test_concurrent_withdrawal_double_spend():
    account_id = "acc_test_100"
    # Starting balance is 100
    # Two simultaneous withdrawal requests of 100
    results = await asyncio.gather(
        withdraw(account_id, 100),
        withdraw(account_id, 100),
        return_exceptions=True
    )
    successful_withdrawals = [r for r in results if not isinstance(r, Exception)]
    # In buggy code, both succeed; in correct code, exactly 1 succeeds
    assert len(successful_withdrawals) == 1, f"Double spend occurred! Both requests succeeded: {results}"
```

#### 4. Drop-in Remediation
**Current Defective Code ([`src/services/billing.py:L42-L51`](file:///src/services/billing.py#L42-L51)):**
```python
# Before
account = await db.accounts.find_one({"id": account_id})
if not account:
    raise AccountNotFound(account_id)
if account["balance"] < amount:
    raise InsufficientFunds("Insufficient balance")

await db.accounts.update_one({"id": account_id}, {"$inc": {"balance": -amount}})
```

**Proposed Drop-in Fix:**
```python
# After
# Execute atomic conditional decrement guarded by balance threshold constraint
result = await db.accounts.update_one(
    {"id": account_id, "balance": {"$gte": amount}},
    {"$inc": {"balance": -amount}}
)
if result.matched_count == 0:
    # Distinguish account absence from insufficient funds
    account_exists = await db.accounts.find_one({"id": account_id}, {"_id": 1})
    if not account_exists:
        raise AccountNotFound(account_id)
    raise InsufficientFunds("Insufficient balance")
```

#### 5. Verification Gate Command
`pytest tests/test_billing.py -k "test_concurrent_withdrawal_double_spend"`
````

---

## 3. Pull Request Review Output Template (Mode A)

When executing Mode A (`/review --diff`), format the final review output using this structured template:

````markdown
# Pull Request Quality Engineering Review

**Branch / Diff:** `<branch_name>` against `main`  
**Lines of Logic Changed:** `<lines_count>`  
**Review Status:** [ CHANGES REQUESTED | APPROVED | APPROVED WITH SUGGESTIONS ]  
**Reviewer:** Quality Engineering Sentinel

---

## 1. Executive Summary & Macro Intent
<High-level narrative explaining the PR's purpose, architectural fit, and key risks. Acknowledge elegant engineering, well-designed test fixtures, or thorough documentation.>

---

## 2. Findings Summary
- 🔴 **P0 (Critical):** <count>
- 🟠 **P1 (High):** <count>
- 🟡 **P2 (Medium):** <count>
- 🟢 **P3 (Low / Suggestion):** <count>
- ❓ **Questions:** <count>

---

## 3. Blocking Findings (P0 / P1)
<!-- Itemized defects using the Atomic Defect Schema -->

### [DEFECT-001] 🔴 [P0: Critical - Blocker] Cross-Tenant IDOR in Invoice Retrieval
- **Severity:** P0: Critical
- **Engineering Axis:** Security & Isolation
- **Location:** [`src/controllers/invoices.py:L35-L42`](file:///src/controllers/invoices.py#L35-L42)
- **Component:** `invoice-controller`

#### 1. Vulnerability Description
Handler queries invoice by `id` without scoping by `current_user.organization_id`.

#### 2. Blast Radius
Any authenticated user can read arbitrary tenant invoices by guessing UUIDs.

#### 3. Empirical Proof
```python
response = client.get("/api/invoices/org2_inv_123", headers={"Authorization": "Bearer tenant_1_token"})
assert response.status_code == 404 # Buggy code returns 200 OK
```

#### 4. Drop-in Remediation
```python
# Before
invoice = await db.invoices.find_one({"id": invoice_id})

# After
invoice = await db.invoices.find_one({
    "id": invoice_id,
    "organization_id": current_user.organization_id
})
if not invoice:
    raise NotFoundException("Invoice not found")
```

#### 5. Verification Gate Command
`pytest tests/test_invoices.py -k "test_cross_tenant_isolation"`

---

## 4. Important & Non-Blocking Findings (P2 / P3)
<!-- P2 and P3 findings with file:line and Before/After blocks -->

---

## 5. Architectural Discussion & Questions
* **[`src/config/limits.py:L14`](file:///src/config/limits.py#L14)**: `MAX_RETRIES = 5`
  * Does this align with the upstream gateway timeout? 5 retries with 5s timeouts could hold worker threads for 25s during cascading downstream outages.

---

## 6. Next Steps for Author
1. Apply drop-in remediations for **P0** and **P1** blocking defects.
2. Run the specified verification gate commands locally.
3. Push fixes and request re-review.
````

---

## 4. Executive Audit Report Template (Mode B)

When concluding a macro repository audit (`/review --repo`), aggregate all findings into an Executive Dashboard document:

````markdown
# Repository Quality Engineering Audit Report

**Target Repository:** `<repo_name>`  
**Commit / SHA Audited:** `<commit-hash>`  
**Date of Audit:** `YYYY-MM-DD`  
**Lead Auditor:** Quality Engineering Sentinel  
**Certification Verdict:** [ REJECTED | CONDITIONALLY APPROVED | CERTIFIED ]

---

## 1. Executive Summary & Verdict Narrative
- **Overall Verdict:** `REJECTED` (due to open P0/P1 blockers)
- **Narrative:** Comprehensive audit across all 8 QE inspection axes. System demonstrates sound domain modeling, but exhibits systemic vulnerabilities in tenant isolation and concurrency controls under load.

---

## 2. Findings Scorecard

| Severity Level | Total Count | Hard Blocking | Status |
| :--- | :---: | :---: | :--- |
| 🔴 **P0: Critical** | 2 | 2 | Action Required |
| 🟠 **P1: High** | 3 | 3 | Action Required |
| 🟡 **P2: Medium** | 6 | 0 | Pending Sprint Scheduling |
| 🟢 **P3: Low / Hygiene** | 11 | 0 | Backlog |
| **Total Findings** | **22** | **5** | **Merge Blocked** |

---

## 3. Findings Heatmap by Module

| Module / Path | P0 | P1 | P2 | P3 | Primary Risk Axis |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `src/auth/` | 1 | 0 | 1 | 2 | Security & Boundary Isolation |
| `src/billing/` | 1 | 2 | 0 | 1 | Reliability & Concurrency (TOCTOU) |
| `src/db/` | 0 | 1 | 3 | 4 | Performance (N+1 queries, unindexed) |
| `src/workers/` | 0 | 0 | 2 | 4 | Observability & Error Recovery |

---

## 4. Itemized Findings Log
<!-- Full itemized log containing every finding in atomic schema -->

### [DEFECT-001] 🔴 [P0: Critical - Blocker] ...
...

### [DEFECT-002] 🟠 [P1: High - Blocker] ...
...

---

## 5. Next Actions & Sign-off Criteria
1. **Mandatory Blockers:** Remediate all 2 P0 defects and 3 P1 defects.
2. **Empirical Verification:** Execute all reproducer tests in `test/challenger/` and verify pass.
3. **Automated Baseline:** Re-run `review_collector.py --repo` to confirm zero static baseline errors.
4. **Re-Audit Sign-Off:** Schedule Phase 4 re-audit for final certification.
````
