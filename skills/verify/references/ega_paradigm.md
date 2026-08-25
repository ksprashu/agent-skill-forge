# Expectation-Grounded Alignment (EGA) Paradigm

**Expectation-Grounded Alignment (EGA)**, also known as **Expectation-Aligned Work (EAW)**, is a general-purpose agentic execution paradigm. It extends Test-Driven Development (TDD) and Behavior-Driven Development (BDD) beyond traditional software engineering into **all domain problem statements**—including research, technical writing, architecture, data analysis, policy design, and complex multi-agent coding.

---

## 1. Core Philosophy: Synthesis Before Execution

Traditional agent execution suffers from **Subjective Completion Syndrome**: an LLM is given a goal, performs work, and self-evaluates whether the work is complete. Because the model judges its own work using the same context that produced it, it frequently exhibits confirmation bias, hallucination, or false confidence.

EGA flips this workflow completely:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      TRADITIONAL AGENT WORKFLOW                           │
│  User Goal ────► Agent Execution ────► Self-Assessment ("Looks good!")    │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│              EXPECTATION-GROUNDED ALIGNMENT (EGA) WORKFLOW                │
│                                                                           │
│  1. Goal Ingestion                                                        │
│       │                                                                   │
│       ▼                                                                   │
│  2. Expectation Synthesis ───► Generates Static Verifiers & Dynamic Rubrics│
│       │                                                                   │
│       ▼                                                                   │
│  3. Worker Execution ────────► Generates Implementation Artifacts          │
│       │                                                                   │
│       ▼                                                                   │
│  4. Dual-Verification Gate ──► [Static Checks PASS?] AND [Blind Judge PASS?]│
│       │                               │                                   │
│       │ No                            │ Yes                               │
│       ▼                               ▼                                   │
│  5. Feedback Delta Loop           6. Grounded Alignment Sign-off          │
│     (Re-attempt until PASS)                                               │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Four Pillars of EGA

### Pillar 1: Expectation Synthesis (Pre-Execution Contract)
Before any code, text, or analysis is generated, the Orchestrator synthesizes two explicit contract artifacts:
1. **Deterministic Static Verifiers**: Programmatic Python/Node scripts, JSON Schemas, AST structure checkers, link resolvers, unit tests, and linters.
2. **Blinded Dynamic Rubrics**: Structured evaluation specs (`rubric.json` / `judge_prompt.md`) defining qualitative standards, tone, completeness, and counter-evidence checks.

### Pillar 2: Execution Isolation
The **Worker Agent** is given the task directive and the expectation rubric. It is free to decide *how* to implement the solution, but it is strictly isolated from modifying the verification harness scripts.

### Pillar 3: Dual-Verification Gate (Static + Blinded Dynamic)
Verification occurs across two independent dimensions:
* **Static Layer**: Executes non-flaky, deterministic code scripts locally on disk. Fast, zero-cost, and objective.
* **Dynamic Layer (Blinded LLM-as-a-Judge)**: Launches a **fresh subagent session with zero past conversation history or execution context pollution**. The Judge receives *only* the raw output artifact and the Expectation Rubric, evaluating the deliverable as an unbiased third-party auditor.

### Pillar 4: Iterative Feedback Delta Loops
If either verification layer fails, raw diagnostic logs (failed assertions, schema breaches, or judge defect lists) are formatted into a concise **Feedback Delta Report** and fed back to the Worker Agent. The loop repeats until `STATUS: PASS` or the retry circuit breaker is triggered (`MAX_ITERATIONS=3`).

---

## 3. Comparative Summary: TDD vs. BDD vs. EGA

| Feature | Test-Driven Development (TDD) | Behavior-Driven Development (BDD) | Expectation-Grounded Alignment (EGA) |
| :--- | :--- | :--- | :--- |
| **Primary Domain** | Software unit logic | User stories & feature specs | **All domains** (coding, research, strategy, docs, architecture) |
| **Contract Format** | Unit tests (`pytest`, `Jest`) | Gherkin feature files (`behave`) | **Dual Harness**: Static scripts + Dynamic Blinded Judge Rubrics |
| **Evaluator** | Test Runner CLI | BDD Runner CLI | **Dual Gate**: Local Script Execution + Fresh-Context LLM Judge |
| **Context Isolation** | N/A (Code level) | N/A (Feature level) | **Strict Context Partitioning** (Judge has zero worker memory) |
| **Feedback Mechanism** | Stack trace | Feature step failure | Structured **Delta Report** fed into iterative refinement loop |
