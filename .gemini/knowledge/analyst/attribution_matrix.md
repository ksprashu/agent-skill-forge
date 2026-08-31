---
type: "Attribution Matrix"
title: "Agent Skill Forge Upstream Lineage & Attribution"
description: "Upstream creators, original inspirations, open-source repositories, and adaptation models for all 28 skills."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/docs/catalog_reference.md"
tags: ["analyst", "attribution", "lineage", "open-source", "creators"]
---

# 👤 Upstream Lineage & Attribution Matrix

Authoritative attribution and upstream provenance for all skills curated, fused, or authored within **Agent Skill Forge**.

---

## 🌟 Core Skills Provenance & Lineage

| Skill / Domain | Original Creators & Inspirations | Upstream Repositories / Standards | Adaptation in `agent-skill-forge` |
| :--- | :--- | :--- | :--- |
| **`unslop`** | **Matt Pocock** & **poteto / Cursor pstack** | [`mattpocock/skills/deslop`](https://github.com/mattpocock/skills) & [`cursor/plugins/pstack`](https://github.com/cursor/plugins/tree/main/pstack) | Fused universal anti-bloat engine spanning code, prose, analysis, and visual UI with the Laziness Protocol. |
| **`grill`** | **Matt Pocock** & **Addy Osmani** | [`mattpocock/skills/grill-me-with-docs`](https://github.com/mattpocock/skills) & [`addyosmani/agent-skills/interview-me`](https://github.com/addyosmani/agent-skills) | 1-question Socratic alignment protocol with confidence threshold gating into `CONTEXT.md`. |
| **`spec`** | **Addy Osmani** | [`addyosmani/agent-skills/source-driven-development`](https://github.com/addyosmani/agent-skills) | Source-grounded specification engine with official API doc citations and explicit non-goals. |
| **`plan`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/planning`](https://github.com/addyosmani/agent-skills) | Vertical task slicing and dependency DAG checkpointing. |
| **`test`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/test`](https://github.com/addyosmani/agent-skills) | Test-Driven Development and Prove-It bug reproduction loop. |
| **`review`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/review`](https://github.com/addyosmani/agent-skills) | 5-axis code and architectural review framework with line-specific fix blocks. |
| **`prompt`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/prompt`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/SKILL.md) | Intent engineering, 6-persona framework, and DAG task graph compiler. |
| **`verify`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/verify`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/verify/SKILL.md) | Expectation-Grounded Alignment (EGA) with static check scripts + 6-persona blinded judge rubrics. |
| **`docs`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/docs`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/docs/SKILL.md) | Full SDLC documentation scaffolding + Stitch 4-theme interactive HTML compiler. |
| **`catalog`** | **Prashanth Subrahmanyam** | [Google Open Knowledge Format (OKF)](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/catalog/SKILL.md) | Codebase memory and progressive disclosure index tree specification. |
| **`sync`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/sync`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/sync/SKILL.md) | Multi-runtime symlink synchronizer and JIT workspace bootstrapper. |
| **`google-oss`** | **Google Open Source Programs Office (OSPO)** | [Google Open Source Docs](https://opensource.google/documentation) | Apache-2.0 compliance, header automation, and repository sanitization. |
| **`codelab`** | **Google Developer Relations** | [Google Codelabs](https://codelabs.developers.google.com/) | Interactive step-by-step developer tutorial authoring and quality validation. |
| **`voice`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/voice`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/voice/SKILL.md) | PII-sanitized linguistic style and typing cadence extraction. |
| **`copy-write`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/copy-write`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/copy-write/SKILL.md) | Technical prose companion with 3-tier Profile-Overlay voice personalization. |
| **`image-gen`** | **Google DeepMind** | [Gemini API Documentation](https://ai.google.dev/) | Multimodal image and diagram generation using Gemini Flash Image. |

---

## 🛠️ Preferred Domain Skills Lineage

The 12 specialized domain skills in [`preferred/`](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/PREFERRED_SKILLS.md) are adapted from authoritative engineering standards:
* **Addy Osmani & Google Chrome Team**: Frontend UI engineering, performance optimization, browser testing with DevTools, and deprecation migrations.
* **Anthropic Agent Skills Standard**: Context engineering and API interface design standards.
* **Open Source Community**: CI/CD automation, distributed observability, and defensive debugging.
