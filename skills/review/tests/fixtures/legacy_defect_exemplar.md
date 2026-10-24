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
