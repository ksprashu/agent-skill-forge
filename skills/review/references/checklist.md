# Unified 8-Axis QE Inspection Checklist

> **Purpose:** Exhaustive, deterministic inspection checklist covering all 8 Quality Engineering (QE) dimensions.
> **Usage:** Used during Phase 2 (Micro Dataflow Deep Dive) in Mode A PR reviews and Pass 2 (Layered Architectural Audit) in Mode B repository audits.
> **Standard:** Read on-demand per Progressive Disclosure rules. Every finding generated against these checkpoints must be logged using the atomic defect schema in [`schemas.md`](schemas.md).

---

## Overview: The 8-Axis Inspection Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE UNIFIED 8-AXIS REVIEW MATRIX                     │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Scope & Architecture          │ 5. Performance & Resource Scale     │
│ 2. Correctness, Logic & State    │ 6. Data Integrity & Storage Evol.   │
│ 3. Security & Boundary Isolation │ 7. Test Suite Effectiveness & Rigor │
│ 4. Reliability & Concurrency     │ 8. Observability & Anti-Slop        │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## Axis 1: Scope, Architecture & Modularity

- [ ] **1.1 Diff Discipline & Single-Responsibility Gate (<500 Lines)**
  - **Rule:** A functional pull request must strictly address a single coherent intent and contain fewer than 500 lines of functional business logic (excluding auto-generated lockfiles, mocks, or snapshots).
  - **Inspection Criteria:**
    - Verify that unrelated refactorings, styling changes, dependency updates, and feature code are not bundled together.
    - Check for scope creep beyond the stated ticket, PR description, or issue acceptance criteria.
    - If logic exceeds 500 lines, recommend splitting into stacked PRs (e.g., PR 1: Schemas & Migrations, PR 2: Domain Services & Tests, PR 3: API & UI integration).

- [ ] **1.2 Clean Layering & Dependency Direction**
  - **Rule:** Architectural dependencies must follow a strict unidirectional hierarchy: `Ingress / Transport` $\rightarrow$ `Domain Services` $\rightarrow$ `Persistence / Infrastructure`.
  - **Inspection Criteria:**
    - Verify that transport layer constructs (HTTP headers, query strings, cookies, Express/FastAPI request objects) never leak into domain models or business services.
    - Assert that domain entities do not import database drivers, ORM decorators, or low-level file I/O utilities.
    - Check for circular dependencies across modules or packages; detect tangled imports using structural analysis.

- [ ] **1.3 Interface Segregation & Abstraction Leaks**
  - **Rule:** Interfaces must represent client-specific consumer needs, not implementation mechanics.
  - **Inspection Criteria:**
    - Verify that consumers depend only on the minimal interface methods they actually invoke.
    - Prevent database-specific or protocol-specific types (e.g., `MongoObjectId`, `gRPC metadata`) from escaping interface boundaries into core business workflows.
    - Guard against premature abstraction: reject 5-layer generic factory-builder patterns created for a single callsite. Reject redundant single-use wrappers.

- [ ] **1.4 Backward-Compatible Public Contracts & Dependency Hygiene**
  - **Rule:** Public API contracts, serialization wire schemas, and shared library signatures must preserve backward compatibility. Third-party dependencies must be justified.
  - **Inspection Criteria:**
    - Verify that public fields, endpoints, or exported symbols are not renamed or deleted without an explicit deprecation cycle.
    - Check new external dependencies: verify license permissiveness (MIT, Apache 2.0, BSD; reject copyleft GPL in proprietary code).
    - Prevent dependency bloat: reject multi-megabyte packages introduced to solve trivial tasks easily handled by standard library utilities.

---

## Axis 2: Correctness, Logic & State

- [ ] **2.1 Boundary & Off-by-One Arithmetic**
  - **Rule:** Index calculations, collection slices, loop bounds, and ranges must behave correctly under boundary conditions.
  - **Inspection Criteria:**
    - Audit `<` vs. `<=`, `>` vs. `>=` in range comparisons and termination conditions.
    - Inspect handling of empty collections (`len == 0`), single-element collections, and maximum capacity slices.
    - Audit pagination bounds (e.g., `offset < 0`, `limit > MAX_ALLOWED`, `page = 0` vs. `page = 1`).
    - Verify inclusive versus exclusive timestamp intervals (e.g., `[start, end)` vs. `[start, end]`).

- [ ] **2.2 Nullability, Optionals & Fall-Through Safety**
  - **Rule:** Missing values, optional types, and unexpected fall-throughs must be handled with exhaustive defensive guards.
  - **Inspection Criteria:**
    - Verify that optional or nullable properties (`Option<T>`, `Optional[T]`, `T | null | undefined`) are guarded prior to member access; forbid unhandled unwrap calls (`.unwrap()`, `!`, `as any`).
    - Ensure exhaustive pattern matching over enum values; forbid silent `default:` drops that ignore newly added enum variants.
    - Verify that default fallback values do not mask underlying infrastructure failures.

- [ ] **2.3 State Machine Transition Completeness & Mutability**
  - **Rule:** System entity state transitions must be explicit, valid, and atomic.
  - **Inspection Criteria:**
    - Verify that state transitions reject illegal hops (e.g., transitioning directly from `CANCELLED` to `FULFILLED`).
    - Audit shared mutable state: ensure collections, dictionaries, and memory references are not mutated concurrently across threads or async tasks.
    - Ensure mutations are idempotent; verify that retrying a transition from the same state produces identical results without side-effect duplication.

- [ ] **2.4 Numerical Precision & Time Domain Rigor**
  - **Rule:** Numerical calculations must preserve domain precision; time calculations must be timezone-aware and unambiguous.
  - **Inspection Criteria:**
    - Strictly forbid IEEE-754 floating-point arithmetic (`float`, `double`) for monetary currency, token accounting, or fixed-ratio math. Mandate integer cents, `Decimal`, or `BigNumber`.
    - Enforce UTC for date-time storage, wire transfer, and domain math. Reject naive local timestamps (`datetime.now()` without timezone).
    - Audit daylight saving time (DST) shifts, leap years, and leap seconds in duration arithmetic.

---

## Axis 3: Security, Auth & Boundary Isolation

- [ ] **3.1 Injection Flaw Eradication**
  - **Rule:** All queries, commands, and dynamic evaluations must use parameterized inputs and strict contextual escaping.
  - **Inspection Criteria:**
    - Audit all SQL, CQL, and GraphQL queries: ensure parameterized bindings (`$1`, `?`, `:param`) are used. Forbid raw string concatenation or f-strings in queries.
    - Audit shell execution: ensure argument lists (`execFile`, `subprocess.run(args, shell=False)`) are used instead of interpolating strings into shell environments (`shell=True`).
    - Check for template injection, regular expression denial-of-service (ReDoS), LDAP injection, and XML external entity (XXE) vulnerabilities.

- [ ] **3.2 Multi-Tenant IDOR & Authorization Bounding**
  - **Rule:** Every resource access must enforce explicit tenant scoping and authorization checks.
  - **Inspection Criteria:**
    - Inspect every database query by entity identifier (`/api/documents/:id`): mandate tenant boundary filter (`WHERE id = :id AND org_id = :org_id`).
    - Forbid relying solely on client-supplied identifiers without session-bound ownership validation (Insecure Direct Object Reference - IDOR / BOLA).
    - Verify role-based or attribute-based access control (RBAC / ABAC) middleware is bound to every newly created route.

- [ ] **3.3 Input Validation & Deserialization Hardening**
  - **Rule:** All external inputs must be validated against a strict schema at the system ingress boundary before domain execution.
  - **Inspection Criteria:**
    - Enforce strict ingress validation libraries (Zod, Pydantic, Joi, Protobuf) for payloads, path parameters, and query parameters.
    - Guard against mass-assignment: reject blind unpacking of request bodies into database ORM models (`User.create(**request.body)`). Mandate explicit field allowlists.
    - Forbid unsafe deserialization primitives (Python `pickle`, Java `ObjectInputStream`, PHP `unserialize`, YAML `yaml.load` without `SafeLoader`).

- [ ] **3.4 Secrets, Cryptography & Sensitive Data Scrubbing**
  - **Rule:** Secrets must never reside in source code; sensitive data must be masked across all telemetry and logs.
  - **Inspection Criteria:**
    - Scan diffs for hardcoded API keys, private certificates, JWT signing secrets, database credentials, and seed salts.
    - Verify that customer PII (Personally Identifiable Information), passwords, cardholder data, and authorization headers are scrubbed from log statements, error traces, and metrics.
    - Ensure cryptographic algorithms are modern and secure (e.g., Argon2id/bcrypt for password hashing; AES-256-GCM / ChaCha20-Poly1305 for symmetric encryption; forbid MD5, SHA-1, DES).

---

## Axis 4: Reliability, Concurrency & Resilience

- [ ] **4.1 TOCTOU Race Condition Prevention**
  - **Rule:** Multi-step check-then-act operations must execute inside atomic transactions or use appropriate concurrency control.
  - **Inspection Criteria:**
    - Audit "Check-Then-Act" sequences (e.g., check account balance > debit amount; check user exists > create user).
    - Require database row-level locking (`SELECT ... FOR UPDATE`), optimistic locking with version columns, or atomic database operations (`UPDATE ... WHERE balance >= :amount`).
    - Audit distributed operations: verify distributed locks (Redis Redlock, Postgres advisory locks) have bounded leases and fencing tokens.

- [ ] **4.2 Deterministic Resource Management & Cleanup**
  - **Rule:** Every allocated system resource must be deterministically released along all execution paths, including error and cancel paths.
  - **Inspection Criteria:**
    - Ensure file descriptors, database connections, HTTP response bodies, sockets, and memory buffers are freed using language constructs: `try...finally`, `defer`, `using`, or Python context managers (`with`).
    - Audit mutex locks: verify locks are always unlocked in a deferred/finally block to prevent deadlocks under panic/exceptions.
    - Verify temporary files created during processing are removed even if exceptions are thrown.

- [ ] **4.3 Mandatory Deadlines & Outbound I/O Timeouts**
  - **Rule:** Every outbound network call must specify an explicit, conservative connection and read timeout.
  - **Inspection Criteria:**
    - Audit HTTP clients, Redis clients, database connection pools, gRPC stubs, and message queues: verify timeouts are declared.
    - Forbid default infinite or unbounded timeouts that can lead to thread pool or connection pool exhaustion.
    - Ensure context cancellation propagates across asynchronous task hierarchies (e.g., Go `context.Context`, Python `asyncio.Task`).

- [ ] **4.4 Retry Storm Prevention & Graceful Process Termination**
  - **Rule:** Retries must incorporate backoff and jitter; background workers must shut down cleanly on process signals.
  - **Inspection Criteria:**
    - Audit retry logic: verify exponential backoff with randomized jitter and an enforced maximum retry attempt cap. Forbid tight retry loops that amplify outage pressure.
    - Verify that idempotent operations are retried, while non-idempotent operations are never retried without deduplication safeguards.
    - Audit `SIGTERM` / `SIGINT` signal handlers: ensure long-running services stop accepting new work, drain in-flight operations within a deadline, flush logs, and close connection pools cleanly.

---

## Axis 5: Performance & Resource Scale

- [ ] **5.1 N+1 Query & Loop I/O Eradication**
  - **Rule:** Never execute synchronous database queries or remote network calls inside iterative loops.
  - **Inspection Criteria:**
    - Identify queries, RPCs, or file reads inside `for` / `while` / `forEach` loops.
    - Require batch fetching using set membership (`WHERE id IN (...)`), joins, or ORM eager-loading patterns (`select_related`, `prefetch_related`, `include`).
    - Detect nested loop iteration over collections that can be rewritten with hash-map lookups ($O(N)$ vs. $O(N^2)$).

- [ ] **5.2 Unbounded Queries & Mandatory Pagination**
  - **Rule:** Every data retrieval endpoint must enforce strict upper limits and predictable pagination.
  - **Inspection Criteria:**
    - Reject queries executing `SELECT *` without an explicit `LIMIT` clause.
    - Enforce a conservative server-side default limit (e.g., `LIMIT 50`) and an absolute maximum ceiling (e.g., `MAX_LIMIT = 250`).
    - For high-volume tables, require cursor-based pagination (`WHERE id > :cursor ORDER BY id ASC LIMIT :limit`) over offset-based pagination (`OFFSET 100000`) to avoid disk scan penalties.
    - Verify that database indexes exist for columns used in `WHERE`, `JOIN`, and `ORDER BY` clauses.

- [ ] **5.3 Memory Streaming & Large Payload Buffering**
  - **Rule:** Large files, payloads, and datasets must be processed via streaming chunks rather than loaded entirely into heap memory.
  - **Inspection Criteria:**
    - Audit file uploads, downloads, CSV generation, and report exports: ensure streaming APIs (`pipe`, `ReadableStream`, generators) are used.
    - Check JSON parsing: prevent parsing multi-megabyte payloads in a single synchronous pass that blocks the event loop or causes Out-Of-Memory (OOM) crashes.
    - Verify buffer allocations are bounded and reused where appropriate.

- [ ] **5.4 Cache Invalidation & Stampede Protection**
  - **Rule:** Cached data must have explicit TTLs and safeguards against cache stampedes (dogpiling).
  - **Inspection Criteria:**
    - Verify that every cache write specifies a deterministic Time-To-Live (TTL).
    - Ensure cache key construction includes tenant isolation and schema versioning (`tenant:v1:entity:id`).
    - Audit cache invalidation on write paths: ensure mutation updates or deletes stale cache entries atomically.
    - Implement mutual exclusion (mutex/lock) or probabilistic early expiration (XFetch) on expensive cached computations to prevent simultaneous recalculation during cache miss storms.

---

## Axis 6: Data Integrity & Storage Evolution

- [ ] **6.1 Zero-Downtime Expand-and-Contract Migrations**
  - **Rule:** Database schema changes must be backward-compatible with older application versions running concurrently during rolling deployments.
  - **Inspection Criteria:**
    - Enforce the 2-phase **Expand / Contract** pattern for breaking changes (e.g., column renames, type conversions, table splits):
      - *Phase 1 (Expand):* Add new column as nullable; deploy application that writes to both columns and reads from old column.
      - *Phase 1.5 (Backfill):* Run asynchronous data backfill script to populate historical rows.
      - *Phase 2 (Contract):* Deploy application reading from new column; drop old column in a subsequent release.
    - Forbid dropping columns, renaming columns, or adding non-nullable columns without defaults in a single migration step.

- [ ] **6.2 Database-Level Integrity Constraints**
  - **Rule:** Invariants must be enforced by storage engines, not solely delegated to application memory.
  - **Inspection Criteria:**
    - Verify foreign key constraints exist for relational references to prevent orphaned records.
    - Require `UNIQUE` indexes for business-unique fields (e.g., email, organization slug, external idempotency key).
    - Enforce `NOT NULL` constraints on mandatory attributes and use database `CHECK` constraints for numeric ranges and enum states.

- [ ] **6.3 Operation Idempotency & Deduplication**
  - **Rule:** State-mutating operations (financial charges, external webhooks, queue messages) must be safe to execute multiple times.
  - **Inspection Criteria:**
    - Audit mutation endpoints: require client-supplied `Idempotency-Key` headers stored in an atomic persistence store with TTL.
    - Verify message consumers record processed message identifiers before or within the same transaction as state mutation.
    - Ensure webhook ingestion endpoints return HTTP 200 on duplicate deliveries without executing duplicate side effects.

- [ ] **6.4 Executable Down-Migrations & Rollback Verification**
  - **Rule:** Every schema migration must have an executable, tested down-migration that reverses the schema change without data corruption.
  - **Inspection Criteria:**
    - Verify migration tools (Flyway, Liquibase, Alembic, Prisma, Goose) provide a valid `down` / `revert` script.
    - Assert that down-migrations do not execute destructive operations (`DROP TABLE`) if a clean rollback is required during a failed deployment.
    - Validate that rollback instructions are documented and tested against staging-equivalent schema snapshots.

---

## Axis 7: Test Suite Effectiveness & Rigor

- [ ] **7.1 Behavioral Outcomes vs. Mock Abuse**
  - **Rule:** Tests must verify observable outcomes, state transitions, and contracts—not internal implementation minutiae.
  - **Inspection Criteria:**
    - Audit assertion quality: flag tests that only assert a mock was called (`expect(spy).toHaveBeenCalled()`) without asserting the resulting system state or response payload.
    - Reject excessive mocking where 90% of the test file mocks internal collaborator methods, leaving zero testing of actual logic.
    - Verify tests treat the system as a black box where possible, exercising public APIs and validating persistent state changes.

- [ ] **7.2 Negative Scenarios & Fault Path Coverage**
  - **Rule:** The test suite must actively exercise failure modes, error branches, and degraded system conditions.
  - **Inspection Criteria:**
    - Verify tests cover error responses: HTTP 400 (malformed schema), HTTP 401/403 (unauthorized/forbidden), HTTP 404 (not found), HTTP 429 (rate limited).
    - Check fault-injection tests: simulate third-party API timeouts, database connection drops, disk write failures, and corrupted payloads.
    - Ensure error handling logic actually triggers and behaves as expected under failure conditions.

- [ ] **7.3 Flakiness Eradication & Determinism**
  - **Rule:** Tests must execute deterministically across all environments, independent of clock time, execution order, or machine speed.
  - **Inspection Criteria:**
    - Strictly ban hardcoded sleep timers (`time.sleep(1)`, `setTimeout(..., 500)`). Require event polling, promise awaiting, or latch countdowns.
    - Forbid reliance on real system clocks for time-sensitive logic: mandate mock clocks or time-travel test runners.
    - Forbid order-dependent tests: assert that tests clean up database state after execution and do not depend on data seeded by preceding tests.

- [ ] **7.4 "Audit the Tests First" Protocol**
  - **Rule:** Review newly added or modified tests before inspecting the production implementation.
  - **Inspection Criteria:**
    - Verify test assertions actually fail when the business logic is commented out or inverted (mutant test check).
    - Ensure tests do not contain tautological assertions (`expect(true).toBe(true)` or `assert result is not None`).
    - Verify test coverage matches all new public code paths and branches added in the pull request.

---

## Axis 8: Observability, Operational Readiness & Anti-Slop

- [ ] **8.1 Structured Contextual Logging**
  - **Rule:** All operational logs must be structured JSON containing correlation identifiers.
  - **Inspection Criteria:**
    - Forbid unstructured console printing (`console.log`, `print()`, `fmt.Println`) in production code paths.
    - Verify logs include contextual fields: `trace_id`, `request_id`, `tenant_id`, `user_id`, and component tags.
    - Ensure error logs capture the root cause, message, and sanitized stack trace without truncating critical context.

- [ ] **8.2 Critical Metric Instrumentation & Telemetry**
  - **Rule:** Critical workflows must expose metrics for latency, throughput, error rates, and saturation.
  - **Inspection Criteria:**
    - Verify new endpoints or background workers increment error and success counters.
    - Check that latency is recorded using histograms (to observe p95/p99 percentiles) rather than simple averages.
    - Ensure gauge metrics track critical resource levels (e.g., active worker count, queue depth, connection pool utilization).

- [ ] **8.3 Dead Code & Dormant Artifact Eradication**
  - **Rule:** All unreferenced code, obsolete feature toggles, and commented-out snippets must be purged.
  - **Inspection Criteria:**
    - Check for unused imports, unreferenced private methods, unreachable `else` branches, and orphan types.
    - Strip commented-out code blocks: Git history preserves historical versions; dead code in the active branch creates cognitive noise.
    - Ensure obsolete feature flags and legacy migration shims are removed after rollout completion.

- [ ] **8.4 Anti-Slop & Abstraction Hygiene**
  - **Rule:** Code, comments, and designs must be clear, concise, and free from AI-generated boilerplate.
  - **Inspection Criteria:**
    - Strip meaningless single-use utility wrappers that simply forward a call to a standard library function.
    - Remove redundant comments that merely restate code syntax (`// sets x to 5`).
    - Eliminate AI boilerplate phrases, verbose apologetic comments, or empty documentation stubs.
    - Ensure naming is precise and domain-focused rather than vague (`processData()`, `handleItem()`, `managerHelper`).
