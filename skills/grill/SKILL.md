---
name: grill
description: Interactive Socratic interview engine for rapid requirements extraction and assumption stress-testing. Trigger via `/grill`, `/grill-me`, or `/interview` when requirements are underspecified or before committing to an architecture.
disable-model-invocation: true
---

# Socratic Grilling & Requirements Extraction Engine

Extract what the user actually needs rather than what they initially asked for. Closes the gap between conventional requests ("build me a dashboard") and true underlying intent through a disciplined, one-question-at-a-time interview.

---

## 🎯 When to Use

- When an ask is underspecified ("build feature X" without clear user personas, SLAs, or success metrics).
- When a user explicitly triggers: `/grill`, `/grill-me`, `/interview`, "stress-test my thinking", or "are we sure?".
- Before creating a complex specification, architecture doc, or multi-agent task DAG.
- When two design goals are in tension (simplicity vs flexibility, speed vs thoroughness) and the tradeoff priority is unstated.

---

## 🔄 The Socratic Grilling Protocol

### 1. Formulate a Hypothesis with Confidence Score
Before asking any question, state your current best hypothesis in **one sentence** along with an honest confidence score (0–100%):

```
HYPOTHESIS: You want an automated latency monitor to alert when Cloud Run p95 exceeds 500ms during keynotes.
CONFIDENCE: ~40% — unresolved: who receives the alert, and what action triggers on failure.
```

### 2. Ask Exactly ONE Question at a Time
Never present multi-question bulleted questionnaires. Ask a single focused question with your best guess and rationale attached:

```
Q: Should the alert trigger a webhook to a Slack channel, or write structured JSON logs directly to Cloud Logging for BigQuery GA4 analysis?
GUESS: Cloud Logging / BigQuery, because your existing analytics pipelines in `codelabs-completion-dash` ingest telemetry asynchronously.
```

### 3. Stop Condition (95% Confidence)
Cease interviewing as soon as confidence reaches $\ge 95\%$. Stop asking questions when:
- You know **who** uses it, **why** now, **what success looks like**, and the **binding constraints**.
- You can accurately predict the user's answers to the next 3 implementation questions.

### 4. Output: Requirements Brief (`CONTEXT.md`)
Conclude the interview by generating a concise, structured `CONTEXT.md` summarising:
1. **Core Problem Statement & Target Personas**
2. **Explicit Non-Goals & Boundaries**
3. **Key Tradeoffs & Selected Options**
4. **Acceptance Criteria & Verifiable SLAs**
