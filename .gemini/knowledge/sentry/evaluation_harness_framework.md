---
type: "Evaluation Framework"
title: "3-Tier Agent Skill Evaluation Harness"
description: "Architectural design of the 3-tier testing framework for agent skills: structural linting, trigger/routing evaluation, and behavioral trace grading."
resource: "file:///Users/ksprashanth/code/github/agent-skills/evals/README.md"
tags: ["sentry", "evals", "testing", "benchmarks", "verification", "ci-cd"]
---

# 🧪 3-Tier Agent Skill Evaluation Framework

Comprehensive testing framework for verifying skill syntax, routing precision, and runtime agent execution fidelity.

---

## 1. The 3-Tier Evaluation Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Static Structural & Syntax Linter (Deterministic / Fast)       │
│ • YAML frontmatter schema validation (name, description, aliases)      │
│ • Markdown heading symmetry and unbalanced tag detection               │
│ • PII pattern scanning (zero developer usernames, private emails)      │
│ Runner: `python3 scripts/validate_skills.py` (Runs in CI <1s)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Pass
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 2: Description & Routing Collision Evaluator (Deterministic)      │
│ • Trigger keyword density audit against user utterance datasets        │
│ • Semantic routing collision check across sibling skills               │
│ • Model-invoked vs user-invoked token economy check (<1024 chars)      │
│ Runner: `python3 evals/run_routing_evals.py` (Runs in CI <5s)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Pass
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 3: Behavioral Execution Trace Graders (LLM Judge / High Thinking) │
│ • Evaluates real agent execution traces against expected rubrics       │
│ • Verifies adherence to TDD red-green cycles and Prove-It reproduction │
│ • Checks anti-rationalization compliance and red flag avoidance        │
│ Runner: `python3 evals/run_behavioral_evals.py`                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tier 1: Static Structural Checks

1. **Frontmatter Schema**: Verifies presence of `name` matching folder basename, valid `description`, and allowed boolean flags.
2. **Zero-PII Scanning**: Regex audit against developer usernames, private corporate URLs, and personal emails.
3. **OKF Conformance**: Validates concept files against `verify_okf.py`.

---

## 3. Tier 2: Routing Collision Testing

Prevents two skills from competing for the same user intent:
- **Corpus Testing**: Evaluates 100+ synthetic user queries (e.g., "Review my PR", "Check security in auth.ts", "Draft an API spec").
- **Accuracy Metric**: Requires $\ge 95\%$ deterministic routing accuracy to the intended skill.
- **Collision Metric**: Triggers build failure if two skills match the same prompt with overlapping confidence scores.

---

## 4. Tier 3: Behavioral Trace Rubrics

Grades agent conversation trajectories against per-skill golden rubrics:
- **Spec Verification**: Did the agent produce a formal spec before writing code?
- **TDD Verification**: Did the agent create a failing test before writing implementation logic?
- **Evidence Verification**: Did the agent log test execution output and build logs?
