---
name: spec
description: Write grounded specifications with official API doc citations and non-goals before coding.
---

# Spec: Specification & Source Grounding

Write structured, source-cited specifications before writing implementation code.

---

## 🎯 Goal
Align requirements, technical constraints, non-goals, and official API documentation in a clean `SPEC.md`.

---

## 📋 Step-by-Step Workflow

1. **Clarify Objective & Personas**: Identify target users, core capabilities, and success criteria.
2. **Ground Against Official Docs**: Look up external library/framework documentation for official API contracts.
3. **Define Boundaries & Non-Goals**: Explicitly list what the system will NOT do in this iteration.
4. **Author `SPEC.md`**: Produce the specification document and save to the project root or `.gemini/specs/`.
5. **Get Human Approval**: Stop and wait for user confirmation before executing implementation code.

---

## 💡 Concrete Example

### Fixture: `SPEC.md`
```markdown
# Specification: Webhook Ingestion Engine

## 1. Objective
Ingest Stripe webhook events, verify signatures using official SDK APIs, and record idempotently to PostgreSQL.

## 2. Official Source Grounding
* Stripe Webhook Verification: [Stripe Docs](https://docs.stripe.com/webhooks/signatures) -> `stripe.webhooks.constructEvent(payload, header, secret)`.

## 3. Explicit Non-Goals
* No email notification sending inside the webhook handler (handled downstream via Cloud Tasks).
* No support for unverified webhook test payloads in production mode.

## 4. Acceptance Criteria
* [ ] Rejects requests with invalid or missing `stripe-signature` header (HTTP 400).
* [ ] Ignores duplicate event IDs if already recorded in `processed_events` table (HTTP 200).
* [ ] 100% test coverage for replay attacks and tampered payloads.
```

---

## 🚫 Hard Constraints

*   **NEVER** write implementation code before the user approves `SPEC.md`.
*   **NEVER** invent or guess external third-party library signatures—always ground against official docs.
*   **NEVER** omit the Non-Goals section.
