---
type: "Comparative Analysis"
title: "Agent Skill Frameworks Comparative Matrix & Trade-Offs"
description: "In-depth comparative analysis of architecture, token economy, evaluation rigor, and orchestration models across major skill repositories."
resource: "file:///Users/ksprashanth/code/github/agent-skills/docs/comparison.md"
tags: ["analyst", "comparative-analysis", "benchmarks", "tradeoffs", "token-economy"]
---

# ⚖️ Agent Skill Frameworks Comparative Matrix

Comparative evaluation of architecture, token efficiency, evaluation rigor, and developer interaction paradigms across major open-source agent skill repositories.

---

## 1. Deep Feature Comparison

| Dimension | `agent-skills` (Addy Osmani) | `mattpocock-skills` (Matt Pocock) | `superpowers` (Jesse Vincent) | `agent-skill-forge` (This Repo) |
| :--- | :--- | :--- | :--- | :--- |
| **Core Organizing Philosophy** | Full SDLC lifecycle (Define $\rightarrow$ Ship) with review personas | Pragmatic daily workflow, interrogation & cognitive linguistics | Autonomous development pipeline with two-stage reviews | Universal action verbs + project-scoped domain skills + OKF knowledge |
| **Catalog Architecture** | Flat lifecycle directory (24 skills) | Grouped directories (engineering, productivity, deprecated) | Unified pipeline (~14 skills) | 2-Tier: 16 Core Verbs (Global) + 12 Preferred Skills (Project-Scoped) |
| **Human Interaction Model** | Human checkpoint at each phase | Socratic grilling (1 question at a time with recommended defaults) | Autonomous pipeline with minimal mid-run interruption | Dynamic dual-mode: Lightweight (Direct) vs Heavyweight (Socratic + OKF) |
| **Parallel Orchestration** | Parallel fan-out with merge (`/ship`) | Sequential issue-tracker flow | Parallel subagent worktrees | Parallel subagent DAG with isolated workspaces (`branch`/`share`) |
| **Evaluation Framework** | 3-Tier in-repo eval suite (Syntax, Routing, Behavioral) | None in-repo | TDD methodology for skills | 3-Tier verification: `validate_skills.py` + `verify_okf.py` + `compile_docs.py` |
| **Multi-Runtime Reach** | Claude Code, Codex, Cursor, Gemini CLI, Antigravity | Claude Code primary, `npx skills` | Claude Code, Codex, Cursor, Antigravity | 5 Runtime hubs (`.agents`, `.gemini`, `.gemini/config`, `.claude`, `.antigravity-cli`) |
| **Personalization Engine** | Persona system prompts (`agents/*.md`) | Setup wizards | Fixed persona instructions | 3-Tier Profile-Overlay engine (`*.local.md` $\rightarrow$ `~/.gemini/personas/` $\rightarrow$ `*.template.md`) |

---

## 2. Token Economics & Latency Trade-Offs

### 1. Context Load vs. Cognitive Load
- **Model-Invoked Skills**: Description loaded in every system turn. High context load, zero user cognitive load.
- **User-Invoked Skills (`disable-model-invocation: true`)**: Zero context load on the LLM system prompt. Requires human user to know and trigger the slash command.
- **Agent Skill Forge Hybrid**: 16 Core Verbs optimized with ultra-compact descriptions ($\le 50$ words). Domain skills kept strictly project-scoped.

### 2. Validation Depth vs. Upfront Reasoning
- **Heavy Upfront Reasoning (Superpowers model)**: 12+ minutes of upfront brainstorming and subagent planning before writing first line of code. Ideal for greenfield architecture.
- **Broad Disciplined Validation (Addy Osmani model)**: Rapid path to code (~8 min) followed by deep multi-axis verification (unit, BDD, performance, security, accessibility).
- **Forge Synthesis**: Fast lightweight mode for localized tasks; deep Socratic DAG generation for complex multi-module systems.
