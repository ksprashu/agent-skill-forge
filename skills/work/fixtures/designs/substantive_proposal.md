# Proposal: Job Queue on Postgres `SKIP LOCKED`

Claim a job with a single statement, so the claim and the visibility change are
one transaction and a crashed worker cannot strand a row:

```sql
UPDATE jobs SET state = 'running', claimed_at = now(), worker_id = $1
WHERE id = (
  SELECT id FROM jobs WHERE state = 'queued' AND run_after <= now()
  ORDER BY priority DESC, run_after
  FOR UPDATE SKIP LOCKED LIMIT 1
) RETURNING id, payload;
```

Measured on the staging box (8 vCPU, `db.m6g.2xlarge`, 32 concurrent workers,
`pgbench` driving inserts): **4,100 claims/sec sustained, p99 claim latency
11 ms**. Throughput is flat from 8 to 32 workers and degrades above 48, where
`SKIP LOCKED` scan depth starts costing more than the lock it avoids. Our
requirement is 900/sec, so there is 4.5x headroom and a known ceiling.

The interesting failure is not the one people expect. A worker that holds an
idle-in-transaction connection pins the row indefinitely — `SKIP LOCKED` hides
it from every other worker, so the job silently never runs and never errors.
Mitigation is `idle_in_transaction_session_timeout = 30s` at the role level
plus a reaper that resets `state = 'queued'` where `claimed_at < now() -
interval '5 minutes'`. The reaper must be idempotent, because it will race a
worker that is merely slow; making the reset conditional on `worker_id` being
the one recorded at claim time is what makes that safe.

Retries carry `attempt` and `run_after`; backoff is `2^attempt` seconds capped
at one hour, with jitter, written by the worker in the same transaction that
marks the failure. A job at `attempt = 12` moves to `state = 'dead'` and is
never picked up again — a dead-letter table would duplicate the index and buy
nothing at this volume.

Ordering is per-`queue_name`, not global. Two jobs in different queues have no
defined relative order. This is a real constraint and it rules out using this
design for the billing sequence work, which needs total order.

Not doing: priority aging (jobs at `priority = 0` can starve under sustained
high-priority load; accepted, because our high-priority volume is bounded by a
rate limiter upstream), cross-region replication, and a web dashboard.

The alternative was Redis Streams with consumer groups, which benchmarks about
6x faster. It loses because the job table would then be a second source of
truth needing reconciliation with Postgres on every state change, and we have
no operational Redis. If measured throughput ever exceeds 3,000/sec sustained,
the migration path is to keep the Postgres table as the record of truth and
move only the claim path to Redis, which is a contained change to
`claim_job()` and the reaper.

Schema, with the one index that matters:

```sql
CREATE TABLE jobs (
  id          bigserial PRIMARY KEY,
  queue_name  text NOT NULL,
  state       text NOT NULL CHECK (state IN ('queued','running','done','failed','dead')),
  priority    smallint NOT NULL DEFAULT 0,
  payload     jsonb NOT NULL,
  attempt     smallint NOT NULL DEFAULT 0,
  run_after   timestamptz NOT NULL DEFAULT now(),
  claimed_at  timestamptz,
  worker_id   text
);
CREATE INDEX jobs_claim ON jobs (queue_name, priority DESC, run_after)
  WHERE state = 'queued';
```

The partial index is load-bearing: without the `WHERE state = 'queued'` clause
the index grows with completed jobs and claim latency climbs from 11 ms to
about 90 ms once the table passes ten million rows.
