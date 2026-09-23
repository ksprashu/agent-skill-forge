# Calibration: four cards, about two minutes

The cold-start path, and the way to close gaps left by thin logs.

Each card shows **the same answer twice**, in two formats. Because the
substance is identical, the choice isolates format from content — which is
what an open question like "how do you like things explained?" cannot do.
People are reliably bad at describing their own reading preferences and
reliably good at picking between two concrete samples.

---

## How to run it

1. Show one card at a time. Both variants in full — do not summarise them.
2. Ask: **"Which of these two would you rather receive? A, B, or somewhere in
   between?"**
3. Record the answer as `source: "declared"` with a note of what they picked.
4. Stop when the remaining dimensions are covered. Four cards is the whole
   set; fewer is fine if logs already grounded some axes.

Everything a card does not settle stays `unknown`. Do not extrapolate from
card 1 to a dimension only card 3 tests.

> Running example throughout: *should a background job queue live in Postgres
> or in SQS?* Same recommendation, same facts, every time.

---

## Card 1 — structure vs prose

*Settles `visual_scaffolding` and `text_density`.*

**A.**

> **Recommendation: stay on Postgres.**
>
> | | Postgres queue | SQS |
> |---|---|---|
> | Ops surface | Already running it | One more service |
> | Throughput ceiling | ~2k jobs/sec | Effectively none |
> | Transactional with your writes | Yes | No |
> | Cost at your volume | £0 | ~£40/mo |
>
> - **You are at 40 jobs/sec.** The ceiling is 50× away.
> - **Transactional enqueue is the real win** — no publish-after-rollback bugs.
> - **Revisit at ~1k jobs/sec**, or if queue tables start bloating.

**B.**

> Stay on Postgres. You are running about 40 jobs a second and a
> `SELECT ... FOR UPDATE SKIP LOCKED` queue comfortably handles roughly 2,000,
> so the ceiling is fifty times away and not the thing to optimise for today.
>
> The argument that actually matters is transactional: because the enqueue
> happens in the same transaction as the write that caused it, the entire
> class of publish-after-rollback bugs disappears. SQS cannot offer that at
> any price, and the £40 a month it would cost is not the deciding factor
> either way.
>
> Revisit the decision if sustained throughput approaches a thousand jobs a
> second, or if the queue table starts to bloat.

- **A** → `visual_scaffolding: high`, `text_density: high`
- **B** → `visual_scaffolding: low`, `text_density: low`
- *"B, but break it up"* → `visual_scaffolding: low`, `text_density: high`
- *"A, but I read the prose"* → both `medium`

---

## Card 2 — framing vs payload

*Settles `orientation_need` and `decision_directness`.*

**A.**

> **Context.** You are choosing where background jobs queue.
> **Problem.** Postgres is simple but has a throughput ceiling; SQS scales but
> adds a service and breaks transactional enqueue.
>
> Two options are viable:
>
> 1. **Postgres.** Free, transactional, ceiling ~2k jobs/sec.
> 2. **SQS.** Unbounded, ~£40/mo, enqueue can no longer be transactional.
>
> At 40 jobs/sec both work. Postgres is the lower-risk default; SQS is
> defensible if you expect an order-of-magnitude jump this year.

**B.**

> Stay on Postgres.
>
> `SKIP LOCKED` handles ~2k jobs/sec and you are at 40. The deciding factor is
> that enqueue stays in the same transaction as the write, which removes
> publish-after-rollback entirely. Move to SQS when you pass ~1k/sec.

- **A** → `orientation_need: high`, `decision_directness: low`
- **B** → `orientation_need: low`, `decision_directness: high`
- *"A's framing, B's decisiveness"* → both `high`
- *"B, but I want the alternative"* → `orientation_need: low`,
  `decision_directness: medium`

---

## Card 3 — analogy vs mechanism

*Settles `metaphor_affinity`.*

Same underlying explanation of `SKIP LOCKED`:

**A.**

> Think of the queue table as a pile of paper forms and each worker as a clerk
> walking up to it. Normally if one clerk is holding a form, the next clerk
> stands there waiting for it. `SKIP LOCKED` is the rule that says "if someone
> is already holding that one, walk past it and take the next" — so the queue
> never forms a bottleneck at the top of the pile.

**B.**

> `SELECT ... FOR UPDATE SKIP LOCKED` takes a row-level lock and omits rows
> already locked by another transaction, instead of blocking on them. Workers
> therefore never serialise on the head of the queue; each one claims the
> first unlocked row in index order and commits independently.

- **A** → `metaphor_affinity: high`
- **B** → `metaphor_affinity: low`
- *"B, and A if it's genuinely new to me"* → `medium`

---

## Card 4 — headline vs full model

*Settles `evidence_depth`.*

**A.**

> SQS would cost about £40/month at your volume. Postgres is free. Not the
> deciding factor — stay on Postgres for the transactional enqueue.

**B.**

> Full cost of moving to SQS at 40 jobs/sec (~104M messages/month):
>
> | Line | Monthly |
> |---|---|
> | Requests (104M, after free tier) | ~£37 |
> | NAT gateway data processing | ~£4 |
> | CloudWatch metrics + alarms | ~£3 |
> | **Recurring total** | **~£44** |
> | Migration (engineer-days) | ~£3,200 one-off |
>
> Three things that bill do not show:
>
> - **Dead-letter handling** becomes your code, not a `WHERE` clause.
> - **Local development** needs LocalStack or a live queue per developer.
> - **Transactional enqueue is gone**, so publish-after-rollback becomes a bug
>   class you now have to defend against in review.

- **A** → `evidence_depth: low`
- **B** → `evidence_depth: high`
- *"B's table, skip the caveats"* → `medium`

---

## Afterwards

Ask one open question — it catches what fixed cards cannot:

> **"What is the single most annoying thing an AI assistant does when it
> answers you?"**

The answer is usually a specific, quotable prohibition. Record it in
`forbidden` with `source: "declared"` and their words in the evidence note.
In practice this one question produces the most-used rule in the profile.
