---
type: "Inventory"
title: "Agent Skill Forge Full Skills Taxonomy"
description: "Comprehensive directory of all 16 core universal action verbs and 12 preferred domain skills, including trigger modes, aliases, and paths."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/catalog.json"
tags: ["scout", "inventory", "skills", "core", "preferred", "taxonomy"]
---

# 📦 Full Skills Taxonomy & Inventory

Complete directory of the **16 Core Global Universal Action Verbs** and **12 Preferred Domain Skills** in Agent Skill Forge.

---

## 🌟 1. Core Global Universal Skills (16 Action Verbs)

These skills cover the universal end-to-end software development and technical authoring lifecycle.

| Skill Verb | Slash Triggers | Aliases | Execution Mode | Purpose & Capabilities | Path |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`prompt`** | `/prompt` | `prompt-writer` | User Slash | Meta-task intent engineering, Socratic interview, and dependency DAG compilation (`task_graph.json`). | [skills/prompt](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/SKILL.md) |
| **`grill`** | `/grill`, `/grill-me`, `/interview` | `grill-me` | User Slash | 1-question Socratic alignment interview with hypotheses, auto-stopping at 95% confidence into `CONTEXT.md`. | [skills/grill](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/grill/SKILL.md) |
| **`spec`** | `/spec` | — | Autonomous | Doc-grounded specification authoring with official API citations, non-goals, and data contracts. | [skills/spec](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/spec/SKILL.md) |
| **`plan`** | `/plan` | `planning` | Autonomous | Vertical task slicing, dependency DAG execution, and checkpoint validation. | [skills/plan](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/plan/SKILL.md) |
| **`test`** | `/test` | — | Autonomous | Test-Driven Development (TDD) and Prove-It bug reproduction loops before writing code. | [skills/test](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/test/SKILL.md) |
| **`verify`** | `/verify`, `/ega`, `/harness` | `expectation-harness` | Autonomous | Expectation-Grounded Alignment with deterministic static check scripts + 6-persona blinded judge rubrics. | [skills/verify](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/verify/SKILL.md) |
| **`review`** | `/review` | — | Autonomous | 5-axis code & architecture reviews across correctness, security, performance, architecture, and readability. | [skills/review](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/review/SKILL.md) |
| **`unslop`** | `/unslop`, `/deslop`, `/simplify` | — | Auto / Slash | Universal anti-bloat engine eliminating AI clichés, sterile prose, single-use wrappers, and over-engineering. | [skills/unslop](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/unslop/SKILL.md) |
| **`docs`** | `/docs`, `/compile-docs` | `documentation`, `compile-docs` | User Slash | Scaffolds standard SDLC documentation sheets and compiles markdown into 4-theme interactive HTML portals. | [skills/docs](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/docs/SKILL.md) |
| **`catalog`** | `/catalog` | `knowledge-catalog` | Autonomous | Scaffolds and indexes progressive disclosure Open Knowledge Format (OKF) bundles under `.gemini/knowledge/`. | [skills/catalog](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/catalog/SKILL.md) |
| **`sync`** | `/sync`, `/skill-sync` | `skill-sync` | User Slash | Universal symlink synchronizer across 5 agent hubs and on-demand JIT project bootstrapper. | [skills/sync](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/sync/SKILL.md) |
| **`google-oss`** | `/google-oss`, `/make-google-oss` | `make-google-oss` | User Slash | Audits repos for Apache-2.0 license compliance, scrubs internal paths, and automates SPDX headers. | [skills/google-oss](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/google-oss/SKILL.md) |
| **`codelab`** | `/codelab`, `/codelab-creator` | `codelab-creator` | User Slash | Scaffolds and validates interactive step-by-step developer tutorials following Google Codelabs format. | [skills/codelab](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/codelab/SKILL.md) |
| **`voice`** | `/voice`, `/extract-voice` | `extract-human-voice` | User Slash | Scans conversation logs, scrubs PII, and extracts authentic human writing style markers and cadence profiles. | [skills/voice](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/voice/SKILL.md) |
| **`copy-write`** | `/copy-write`, `/copy-write-bara` | `copy-write-bara` | User Slash | Technical drafting companion using 3-tier Profile-Overlay personalization for blog posts, keynotes, and copy. | [skills/copy-write](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/copy-write/SKILL.md) |
| **`image-gen`** | `/image-gen` | `image-gen-expert` | User Slash | Generates high-fidelity technical diagrams, infographics, and UI assets using Gemini Flash Image. | [skills/image-gen](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/image-gen/SKILL.md) |

---

## 🛠️ 2. Preferred Domain-Specific Skills (12)

These skills are project-scoped and bootstrapped on demand into specific workspaces.

| Domain Skill | Category | Primary Capabilities | NPX Remote Package | Local Path |
| :--- | :--- | :--- | :--- | :--- |
| **`frontend-ui-engineering`** | Frontend & UI | Modern CSS (`:has()`, container queries, subgrid, View Transitions API), accessible components. | `addyosmani/agent-skills` | [preferred/frontend-ui-engineering](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/frontend-ui-engineering/SKILL.md) |
| **`performance-optimization`** | Performance | Core Web Vitals (CWV), LCP/INP performance budgets, memory leak diagnosis, layout thrashing fixes. | `addyosmani/agent-skills` | [preferred/performance-optimization](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/performance-optimization/SKILL.md) |
| **`api-and-interface-design`** | APIs & Schema | Hyrum's law guardrails, discriminated unions, idempotent REST/GraphQL contracts, backward compatibility. | `addyosmani/agent-skills` | [preferred/api-and-interface-design](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/api-and-interface-design/SKILL.md) |
| **`security-and-hardening`** | Security | Threat modeling, OWASP Top 10 mitigations, CWE remediation, input sanitization, secret isolation. | `addyosmani/agent-skills` | [preferred/security-and-hardening](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/security-and-hardening/SKILL.md) |
| **`deprecation-and-migration`** | Databases | Expand/Contract database migrations, non-blocking table alterations, backward-compatible deprecations. | `addyosmani/agent-skills` | [preferred/deprecation-and-migration](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/deprecation-and-migration/SKILL.md) |
| **`browser-testing-with-devtools`** | QA & E2E | Headless Chrome DevTools testing, runtime console error trapping, network assertions, visual regression. | `addyosmani/agent-skills` | [preferred/browser-testing-with-devtools](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/browser-testing-with-devtools/SKILL.md) |
| **`observability-and-instrumentation`** | Ops & Metrics | Structured JSON logging, OpenTelemetry distributed tracing, RED/USE metrics emission, alert rules. | `addyosmani/agent-skills` | [preferred/observability-and-instrumentation](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/observability-and-instrumentation/SKILL.md) |
| **`ci-cd-and-automation`** | DevOps | GitHub Actions workflows, matrix testing, deterministic caching, automated release tagging, presubmits. | `addyosmani/agent-skills` | [preferred/ci-cd-and-automation](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/ci-cd-and-automation/SKILL.md) |
| **`debugging-and-error-recovery`** | Diagnostics | Systematic root cause analysis, stack trace deconstruction, minimal reproducible test cases. | `addyosmani/agent-skills` | [preferred/debugging-and-error-recovery](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/debugging-and-error-recovery/SKILL.md) |
| **`git-workflow-and-versioning`** | Version Control | Conventional commits, atomic PRs, interactive rebase workflows, semantic versioning tags. | `addyosmani/agent-skills` | [preferred/git-workflow-and-versioning](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/git-workflow-and-versioning/SKILL.md) |
| **`context-engineering`** | AI Context | Token window budgeting, compact system prompt packing, progressive disclosure navigation. | `addyosmani/agent-skills` | [preferred/context-engineering](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/context-engineering/SKILL.md) |
| **`benchmark-harness`** | Benchmarking | Automated physical verification and Dual Gemini LLM-as-a-Judge scoring across 12 standardized test cases. | `agent-skill-forge` | [preferred/benchmark-harness](file:///Users/ksprashanth/code/github/agent-skill-forge/preferred/benchmark-harness/SKILL.md) |
