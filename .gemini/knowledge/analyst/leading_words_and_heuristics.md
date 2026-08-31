---
type: "Linguistic Heuristic"
title: "Leading Words & Cognitive Linguistics in Skill Design"
description: "Theoretical framework for utilizing pretrained model priors, leading words, information hierarchy ladders, and diagnosing agent failure modes."
resource: "file:///Users/ksprashanth/code/github/mattpocock-skills/skills/productivity/writing-great-skills/SKILL.md"
tags: ["analyst", "linguistics", "leading-words", "information-hierarchy", "failure-modes", "matt-pocock"]
---

# 🧠 Leading Words & Cognitive Linguistics in Skill Design

Theoretical principles and linguistic mechanics for authoring deterministic, high-efficiency AI agent skills.

---

## 1. Leading Words Theory (Recruiting Model Priors)

A **Leading Word** is a compact, highly dense concept already living in the LLM's pretraining weights that anchors a large behavioral domain in the fewest possible tokens.

```
Verbose Triad: "fast, deterministic, low-overhead loop"   ──►   Leading Word: "tight loop"
Ambiguous Gate: "a test loop you genuinely believe in"    ──►   Leading Word: "red state"
Exploratory Prototyping: "build a small vertical slice"   ──►   Leading Word: "tracer bullets"
Unmapped Subsystem: "navigating unfamiliar codebases"     ──►   Leading Word: "fog of war"
```

### Benefits:
1. **Context Compression**: Replaces verbose multi-sentence descriptions with a single high-signal token.
2. **Behavioral Anchor**: In the skill body, it establishes consistent procedural execution across runs.
3. **Invocation Anchor**: In the frontmatter `description`, it reliably triggers the skill when matching words appear in user prompts.

---

## 2. The 3-Tier Information Hierarchy Ladder

Skills mix **steps** (ordered procedural actions) and **references** (definitions, rules, rubrics). The authoring decision is determining where content sits on the hierarchy ladder:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. In-Skill Steps (SKILL.md)                                           │
│    Primary imperative sequence ending on checkable completion criteria │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Disclose
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. In-Skill Reference (SKILL.md)                                       │
│    Flat definitions, core rules, and anti-rationalization tables       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Externalize
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. External Reference (references/*.md, scripts/)                      │
│    Deep rubrics, templates, and schemas reached via context pointers   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 6 Canonical Agent Failure Modes

When diagnosing why an agent skips steps or produces sloppy output, map the behavior to these failure modes:

| Failure Mode | Symptom / Behavior | Root Cause | Architectural Remedy |
| :--- | :--- | :--- | :--- |
| **Premature Completion** | Agent declares task complete before running tests or checking edge cases. | Agent attention slips to "being done" rather than doing the work. | Sharpen completion criteria into binary checkable states; hide post-completion steps. |
| **Duplication** | Same instructions repeated across multiple skill files or sections. | Redundant prose inflating token cost and causing synchronization drift. | Extract single source of truth into `references/` and link via context pointers. |
| **Sediment** | Outdated or dead rules accumulating over time. | Fear of deleting rules ("adding feels safe, deleting feels risky"). | Aggressive no-op pruning: test each sentence in isolation; delete if default behavior. |
| **Sprawl** | Overly lengthy `SKILL.md` exceeding 500 lines. | Pushing reference material into the top-level execution file. | Push reference docs into `references/` or scripts into `scripts/`. |
| **No-Ops** | Rules stating what the model already does by default ("write clean code"). | Paying context load to state obvious defaults. | Replace weak platitudes with assertive leading words (`relentless`, `hermetic`). |
| **Negation** | Steering by prohibition ("Do NOT do X"). | Mentioning banned concept makes it more cognitively salient to the LLM. | Prompt the positive target behavior; pair unavoidable prohibitions with concrete alternatives. |
