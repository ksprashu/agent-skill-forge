---
type: "Design Decision"
title: "Agent Skill Forge Architecture & Design Rationale"
description: "Architectural rationale for 2-tier scoping, token context conservation, 1-word action verbs, and the Laziness Protocol."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/docs/architecture.md"
tags: ["analyst", "decisions", "architecture", "token-economy", "design-rationale"]
---

# 📊 Architectural Decisions & Design Rationale

Core design decisions and technical tradeoffs governing the architecture of **Agent Skill Forge**.

---

## 1. Two-Tier Skill Scoping: Global Lifecycle vs. Project-Scoped JIT

### Context & Problem
Modern agentic coding environments (Antigravity, Claude Code, Gemini CLI, Cursor) inject the frontmatter descriptions of all active skills directly into system context windows on every conversation turn. Installing dozens of specialized domain skills globally causes:
- Severe prompt token bloat (~2,000–5,000 tokens wasted per turn).
- Increased prompt processing latency.
- Semantic trigger collisions (e.g., a backend agent triggering frontend CSS instructions).

### Decision
Split skills into two distinct tiers:
1. **Tier 1 (Global Lifecycle)**: Exactly **16 universal action verbs** that apply to every codebase regardless of language or framework (`prompt`, `grill`, `spec`, `plan`, `test`, `verify`, `review`, `unslop`, `docs`, `catalog`, `sync`, `google-oss`, `codelab`, `voice`, `copy-write`, `image-gen`).
2. **Tier 2 (Project-Scoped JIT)**: Deep domain skills stored in [`preferred/`](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/PREFERRED_SKILLS.md) and bootstrapped into `<project>/.gemini/skills/` only when working on matching codebases.

### Consequences
- **Positive**: Global system prompts remain lean (<1,200 tokens). Zero unwanted trigger activations across unrelated tech stacks.
- **Tradeoff**: Specialized skills require a 1-second JIT bootstrap command (`sync_skills.py --project . --skills <name>`) when entering a new project.

---

## 2. 1-Word Primary Action Verbs with Backward-Compatible Aliases

### Context & Problem
Legacy skill names (e.g., `skills-extract-human-voice`, `expectation-harness`, `copy-write-bara`) were verbose, clunky to type in slash commands, and inconsistent in naming syntax.

### Decision
Standardize on concise, intuitive 1-word verbs for all core skills while preserving full backward-compatibility via symbolic link aliases in the installer (`sync_skills.py`).

| Primary Verb | Preserved Alias | Rationale |
| :--- | :--- | :--- |
| `prompt` | `prompt-writer` | Direct imperative verb matching developer intent. |
| `grill` | `grill-me` | Concise slash command for Socratic interview alignment. |
| `plan` | `planning` | Aligns with standard SDLC verb forms. |
| `verify` | `expectation-harness` | Standardizes verification under the universal verb. |
| `docs` | `documentation`, `compile-docs` | Unified documentation scaffolding and HTML compilation. |
| `catalog` | `knowledge-catalog` | Direct verb for OKF progressive disclosure indexing. |
| `sync` | `skill-sync` | Universal symlink synchronizer verb. |
| `google-oss` | `make-google-oss` | Standardized hyphenated slug for open-source compliance. |
| `codelab` | `codelab-creator` | Direct entity name for tutorial authoring. |
| `voice` | `extract-human-voice` | Concise verb for cadence and style profiling. |
| `copy-write` | `copy-write-bara` | Clear verb for technical drafting. |
| `image-gen` | `image-gen-expert` | Streamlined command for asset generation. |

---

## 3. The Laziness Protocol ("Subtract Before You Add")

### Context & Problem
LLMs inherently suffer from additive bias—generating defensive helper functions, redundant type wrappers, single-use utility files, and speculative abstractions that clutter codebases.

### Decision
Codify the **Laziness Protocol** as a mandatory principle in `unslop` and `review`:
1. **Inline Single-Use Functions**: Never extract a function unless it is called from 3 or more distinct locations.
2. **Delete Speculative Wrappers**: Remove "just-in-case" configuration managers, ghost interfaces, and empty factory classes.
3. **Refactor by Subtraction**: Always evaluate whether a feature can be implemented by deleting dead code or leveraging existing standard library primitives.

---

## 4. 3-Tier Profile-Overlay Architecture

### Context & Problem
Personalized writing tools need access to user voice profiles, sample emails, and personal style samples. Storing these directly in repository files risks accidental PII leakage to public remotes.

### Decision
Implement a 3-tier fallback resolution engine:
1. **Tier 1 (Local Override)**: Check for gitignored `references/*.local.md` in the workspace.
2. **Tier 2 (User Profile)**: Check `~/.gemini/personas/default/*.md` in the user home directory.
3. **Tier 3 (Generic Fallback)**: Fall back to sanitized open-source templates (`references/*.template.md`).
