---
type: "Interactive Engine"
title: "Socratic Grilling & Branch-Walking Interview Engine"
description: "Operational specification for the Socratic interrogation loop, design-tree branch walking, and proactive default recommendation heuristics."
resource: "file:///Users/ksprashanth/code/github/mattpocock-skills/skills/productivity/grilling/SKILL.md"
tags: ["builder", "grilling", "interview", "socratic", "interaction-design", "matt-pocock"]
---

# 🥩 Socratic Grilling & Branch-Walking Engine

Specification of the conversational requirements interrogation loop and decision-tree traversal algorithm.

---

## 1. The Grilling Philosophy

When a user presents a vague, high-level, or underspecified objective, the agent must **never guess or silently assume requirements**. Instead, it initiates a structured Socratic Grilling session to clarify constraints before any code is generated.

---

## 2. The 5 Core Invariants of Grilling

```
1. One Question at a Time       ──► Never overwhelm the user with walls of multi-part questions.
2. Read Codebase First          ──► Investigate local files to answer obvious questions autonomously.
3. Walk the Design Tree         ──► Resolve root architectural dependencies before leaf styling choices.
4. Provide Recommended Defaults ──► Always supply 2-3 concrete options with an explicit recommended fallback.
5. Confirm Shared Understanding ──► Summarize agreed specifications into an actionable artifact before coding.
```

---

## 3. Tool Selection: `ask_question` vs. Fluid Chat

| Interaction Scenario | Selected Modality | Reason & UX Benefit |
| :--- | :--- | :--- |
| **Technical Architecture Decisions** (Database choice, UI theme, Auth schema) | **`ask_question` Modal Tool** | Presents explicit selectable radio/checkbox options with single-click submission. |
| **Open-Ended Brainstorming** (Exploring user vision, brand voice, novel features) | **Fluid Chat Dialogue** | Fosters rich conversational exploration without restrictive multiple-choice bounds. |

---

## 4. Branch-Walking Algorithm

```
                 ┌─────────────────────────────┐
                 │  Root Architectural Branch  │
                 │  (Storage / Data Model)     │
                 └──────────────┬──────────────┘
                                │ Resolved
                                ▼
                 ┌─────────────────────────────┐
                 │ Intermediate Logic Branch   │
                 │ (API Interface & Auth)      │
                 └──────────────┬──────────────┘
                                │ Resolved
                                ▼
                 ┌─────────────────────────────┐
                 │   Leaf Presentation Branch  │
                 │   (UI Theme & Visual Polish)│
                 └─────────────────────────────┘
```

1. **Step 1 (Root Resolution)**: Inquire about the primary system boundary (e.g., SQLite vs PostgreSQL vs Memory).
2. **Step 2 (Interface Resolution)**: Inquire about communication protocol (REST vs GraphQL vs gRPC).
3. **Step 3 (Edge Cases)**: Inquire about error recovery, auth roles, and rate limits.
4. **Step 4 (Leaf Resolution)**: Inquire about visual aesthetics and UI component styling.
