---
name: grill
description: Ask 1 question at a time with your best guess to clarify requirements, designs, or decisions until 95% confident. Trigger via /grill.
disable-model-invocation: true
---

# Grill: 1-Question Socratic Alignment

Clarify ambiguous goals through a disciplined, 1-question-at-a-time Socratic interview with attached hypotheses.

---

## 🎯 Goal
Extract requirements, non-goals, and constraints from underspecified requests and generate a concise `CONTEXT.md` brief.

---

## 📋 Step-by-Step Workflow

1. **State Hypothesis & Confidence**: Begin each turn with your 1-sentence understanding and confidence score (0–100%).
2. **Ask Exactly ONE Question**: Ask 1 high-leverage question, attaching your recommended answer and rationale.
3. **Check Stop Condition**: When confidence reaches $\ge 95\%$ (or the user says stop), do NOT ask further questions.
4. **Write `CONTEXT.md`**: Produce a structured summary defining problem statement, non-goals, and verifiable acceptance criteria.

---

## 💡 Concrete Example

### Interaction Turn Example
```markdown
HYPOTHESIS: You want an automated latency monitor for your Cloud Run API that alerts when p95 exceeds 500ms.
CONFIDENCE: 60% — unresolved: destination of the alert payload.

QUESTION: Should the alert send a webhook to Slack, or write structured JSON logs directly to Google Cloud Logging?
MY GUESS: Google Cloud Logging, because your analytics pipelines already ingest BigQuery logs asynchronously.
```

### Final Output Fixture (`CONTEXT.md`)
```markdown
# Context Brief: API Latency Monitor

## 1. Problem Statement
Monitor Cloud Run API p95 latency during peak traffic and trigger alerts when p95 > 500ms for 2 consecutive minutes.

## 2. Non-Goals
* No SMS / PagerDuty integration in v1.
* No automatic auto-scaler overriding.

## 3. Selected Decisions
* Destination: Google Cloud Logging structured JSON sink.
* Threshold: p95 > 500ms measured over a 60s sliding window.

## 4. Acceptance Criteria
* [ ] Cloud Run latency metric exporter runs every 15s.
* [ ] Unit test verifies threshold triggering logic with synthetic metrics.
```

---

## 🚫 Hard Constraints

*   **NEVER** ask multiple questions in a single turn. Always ask exactly ONE.
*   **NEVER** ask open-ended questions without providing your best guess.
*   **NEVER** continue grilling once confidence reaches 95%.
