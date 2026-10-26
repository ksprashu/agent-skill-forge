# [DEFECT-001] [P0: Critical] SQL Injection in auth.ts

- **Location**: [`src/api/auth.ts:L42`](file:///src/api/auth.ts#L42)

## Description
User input from the request query parameter is concatenated directly into the raw SQL query string without parameter binding or sanitization, allowing arbitrary SQL execution.

## Blast Radius
Critical severity. Remote unauthenticated attackers can execute arbitrary SQL commands, bypass authentication, extract password hashes and tokens, and mutate or drop database tables.

## Empirical Proof
Execute reproduction exploit request against the auth endpoint:
```bash
curl -X POST http://localhost:3000/api/auth -d "user=' OR 1=1--"
```

## Drop-in Remediation
```typescript
// Before:
const user = await db.query(`SELECT * FROM users WHERE name = '${input}'`);

// After:
const user = await db.query('SELECT * FROM users WHERE name = $1', [input]);
```

## Verification Gate
`npm run test:security`
