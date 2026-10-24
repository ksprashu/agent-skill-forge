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
