---
type: "Ecosystem Landscape"
title: "Agent Skills Ecosystem Landscape & Reference Repositories"
description: "Comprehensive landscape analysis of major AI agent skill ecosystems: Addy Osmani, Matt Pocock, Superpowers, Anthropic, Codex, and Cursor."
resource: "file:///Users/ksprashanth/code/github/agent-skills/docs/comparison.md"
tags: ["scout", "landscape", "ecosystem", "addy-osmani", "matt-pocock", "superpowers", "codex", "anthropic", "cursor"]
---

# 🌐 Agent Skills Ecosystem Landscape

Comprehensive landscape mapping of the primary AI agent skill repositories, frameworks, and distribution standards.

---

## 1. The Reference Ecosystems

| Ecosystem / Project | Primary Creator / Sponsor | Core Focus & Specialty | Primary Runtime |
| :--- | :--- | :--- | :--- |
| **`agent-skills`** | Addy Osmani | Complete SDLC lifecycle (Define $\rightarrow$ Ship), review personas, 3-tier eval framework | Multi-runtime (Claude Code, Gemini CLI, Codex, Cursor, Antigravity) |
| **`mattpocock-skills`** | Matt Pocock | Socratic grilling primitive, cognitive linguistics (leading words), issue-tracker orchestration | Claude Code first, `npx skills` |
| **`superpowers`** | Jesse Vincent (`obra`) | Autonomous multi-agent pipelines, 2-stage review gates, git-worktree isolation | Claude Code, Codex, Cursor, Antigravity |
| **`anthropics/skills`** | Anthropic | Standard `SKILL.md` format, YAML frontmatter specification, tool gating | Claude Code, Anthropic API |
| **`codex-plugin`** | OpenAI | `.codex-plugin/plugin.json` manifest, `@` skill invocation | OpenAI Codex CLI & Operator |
| **`cursor/pstack`** | Cursor / Poteto | Project `.cursor/skills/` and `.cursor/rules/*.mdc` integration | Cursor IDE Agent |

---

## 2. Structural Paradigms Across Frameworks

```
                       ┌──────────────────────────────────────────────┐
                       │   Global AI Agent Engineering Ecosystem      │
                       └──────────────────────┬───────────────────────┘
                                              │
         ┌────────────────────────────────────┼───────────────────────────────────┐
         ▼                                    ▼                                   ▼
┌──────────────────┐               ┌───────────────────────┐            ┌───────────────────┐
│ SDLC Lifecycle   │               │ Interrogation & TDD   │            │ Autonomous Engine │
│ (Addy Osmani)    │               │ (Matt Pocock)         │            │ (Superpowers)     │
│ 6-Phase Pipeline │               │ Grilling Loop         │            │ Worktree Pipeline │
│ 3-Tier Evals     │               │ Leading Words Theory  │            │ 2-Stage Review    │
│ Parallel Personas│               │ Information Hierarchy │            │ Skill TDD         │
└──────────────────┘               └───────────────────────┘            └───────────────────┘
```

---

## 3. Key Ingested Innovations in Agent Skill Forge

1. **From Addy Osmani (`agent-skills`)**:
   - 6-Phase SDLC Lifecycle: DEFINE $\rightarrow$ PLAN $\rightarrow$ BUILD $\rightarrow$ VERIFY $\rightarrow$ REVIEW $\rightarrow$ SHIP.
   - Parallel Review Fan-out (`/ship` running code review, security, performance, and QA simultaneously).
   - Anti-Rationalization Guardrails and Red Flags tables.
   - 3-Tier Evaluation Architecture (Syntax, Description Routing, Behavioral Graders).
2. **From Matt Pocock (`mattpocock-skills`)**:
   - Socratic Grilling Primitive (one question at a time, walking branches with recommended defaults).
   - Leading Words Theory (recruiting pre-trained model priors with single high-density tokens like *tight* and *red*).
   - Information Hierarchy Ladder (in-skill steps $\rightarrow$ in-skill reference $\rightarrow$ external reference).
   - Failure Mode Taxonomy (premature completion, sediment, sprawl, no-ops, negation).
3. **From Jesse Vincent (`superpowers`)**:
   - Independent subagent execution with two-stage review sign-offs.
   - Worktree directory isolation for zero branch collisions.
4. **From Anthropic, OpenAI Codex & Cursor**:
   - Universal plugin manifests (`plugin.json`, `.codex-plugin`, `marketplace.json`).
   - Clean separation between global rules (`.mdc`) and on-demand progressive skills.
