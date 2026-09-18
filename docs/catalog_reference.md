---
title: "Skills Catalog Reference & Attribution Matrix"
theme: "technical"
description: "Comprehensive dictionary, clusters, triggers, and attribution lineage for all skills in Agent Skill Forge."
---

# 📚 Skills Catalog Reference & Attribution Matrix

Comprehensive dictionary, cluster categorization, execution triggers, and upstream attribution lineage for all 29 skills in **Agent Skill Forge**.

---

## 🌟 1. Core Universal Action Verbs (17 Skills across 4 Clusters)

The Core Skills can be installed individually or in functional clusters using `bash scripts/install.sh --clusters <ids>` (e.g. `--clusters c3` or `--content`).

### 📐 Cluster C1: Planning, Specification & Swarm Execution (`plan-spec`)
*Grounds requirements, gathers intent, conducts Socratic alignment, plans dependency DAGs, and executes autonomous swarms.*

| Cluster | Slug | Invocations & Triggers | Execution Mode | Scope & Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | **`prompt`** | `/prompt`, `/prompt-writer` | User Slash | Decomposes complex tasks, vague ideas, or multi-step goals into intent directives and DAG task graphs (`task_graph.json`). |
| **C1** | **`grill`** | `/grill`, `/grill-me`, `/interview` | User Slash | 1-question Socratic interview with attached hypotheses to clarify requirements, architecture, or design tradeoffs until 95% confident. |
| **C1** | **`spec`** | `/spec`, auto on new features | Autonomous | Writes structured, doc-cited specifications with explicit non-goals before executing code. |
| **C1** | **`plan`** | `/plan`, `/planning` | Autonomous | Slices complex features, refactors, or projects into small, vertically sliced tasks with verifiable checkpoints. |
| **C1** | **`work`** | `/work` | User Slash | Coordinates autonomous parallel swarms with Sentinel oversight, dispatch-only orchestration, competitive branching tournaments, and adversarial verification. |

### 🧪 Cluster C2: Quality & Verification (`test-review`)
*Enforces TDD, static verifiers, blinded judge rubrics, architectural reviews, and slop elimination.*

| Cluster | Slug | Invocations & Triggers | Execution Mode | Scope & Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **C2** | **`test`** | `/test`, auto during coding | Autonomous | Enforces writing failing tests first to prove bug reproduction and verify new feature behavior (TDD & Prove-It). |
| **C2** | **`verify`** | `/verify`, `/ega`, `/expectation-harness` | Autonomous | Dual-layer verification running deterministic static check scripts and blinded multi-persona dynamic judge rubrics. |
| **C2** | **`review`** | `/review`, pre-merge | Autonomous | Audits diffs across correctness, security, performance, architecture, and readability with exact line fixes. |
| **C2** | **`unslop`** | `/unslop`, `/deslop`, `/simplify` | Auto / Slash | Strips AI boilerplate, defensive wrapper clutter, sterile prose, and unnecessary complexity from code, text, analyses, and UI. |

### 🎨 Cluster C3: Content, Creative & Authoring (`content-creative`)
*Designs step-by-step developer tutorials, extracts human writing cadence, drafts articles, and synthesizes diagrams.*

| Cluster | Slug | Invocations & Triggers | Execution Mode | Scope & Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **C3** | **`codelab`** | `/codelab`, `/codelab-creator` | User Slash | Scaffolds and validates interactive step-by-step developer tutorials, workshops, and guides formatted for `claat`. |
| **C3** | **`voice`** | `/voice`, `/extract-voice` | User Slash | Scans developer tool conversation logs, scrubs PII, and extracts authentic human writing style markers. |
| **C3** | **`copy-write`**| `/copy-write`, `/copy-write-bara`| User Slash | Drafts technical articles, documentation, keynotes, and copy using 3-tier Profile-Overlay personalization. |
| **C3** | **`image-gen`** | `/image-gen`, `/image-gen-expert` | User Slash | Generates high-fidelity technical diagrams, infographics, and UI assets using Gemini Flash Image. |

### 📚 Cluster C4: Knowledge & Governance (`docs-governance`)
*Preserves durable codebase memory, compiles interactive portals, enforces OSS licensing, and keeps AGENTS.md lean.*

| Cluster | Slug | Invocations & Triggers | Execution Mode | Scope & Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **C4** | **`docs`** | `/docs`, `/compile-docs` | User Slash | Scaffolds standard SDLC doc suites and compiles markdown into interactive 4-theme HTML presentation portals. |
| **C4** | **`catalog`** | `/catalog`, `/knowledge-catalog` | Autonomous | Scaffolds and indexes progressive disclosure knowledge bundles (`.gemini/knowledge/`) for long-term project memory. |
| **C4** | **`google-oss`**| `/google-oss`, `/make-google-oss`| User Slash | Audits repositories for Apache-2.0 license headers, scrubs internal corporate paths, and validates OSS structure. |
| **C4** | **`continuous-alignment`** | `/align`, `/evolve` | Auto / Slash | Autonomous continuous alignment engine: distills session transcripts into strict 200-line AGENTS.md budget, records living ADRs, and compiles roadmap visualizers. |
| **C4** | **`sync`** | `/sync`, `/skill-sync` | User Slash | Manages symlinks across global agent runtimes and bootstraps domain skills into project workspaces. |

---

## 🛠️ 2. Preferred Domain-Specific Skills (12 Skills across 4 Clusters)

The 12 Preferred Domain Skills are located in `preferred/` and can be installed via NPX or linked globally via `scripts/sync_skills.py --clusters d1,d2...` or `--domain`.

### 🌐 Cluster D1: Full-Stack & Quality (`fullstack`)

| Cluster | Slug | Category | NPX Install Command | Capabilities & Frameworks |
| :--- | :--- | :--- | :--- | :--- |
| **D1** | **`frontend-ui-engineering`** | Frontend & Design | `npx skills add addyosmani/agent-skills --skill frontend-ui-engineering` | Modern CSS (`:has()`, container queries, View Transitions), accessible components, slop-free design. |
| **D1** | **`performance-optimization`** | Performance & CWV | `npx skills add addyosmani/agent-skills --skill performance-optimization` | Core Web Vitals (CWV), LCP/INP budgets, memory leak diagnosis, and backend query optimization. |
| **D1** | **`browser-testing-with-devtools`**| Testing & QA | `npx skills add addyosmani/agent-skills --skill browser-testing-with-devtools` | Headless Chrome DevTools testing, console trapping, visual regression checks, and network assertions. |
| **D1** | **`api-and-interface-design`** | Architecture & APIs | `npx skills add addyosmani/agent-skills --skill api-and-interface-design` | Hyrum's law, discriminated unions, idempotent REST/GraphQL contracts, and backward compatibility. |

### 🛡️ Cluster D2: Security, Diagnostics & Reliability (`security`)

| Cluster | Slug | Category | NPX Install Command | Capabilities & Frameworks |
| :--- | :--- | :--- | :--- | :--- |
| **D2** | **`security-and-hardening`** | Security & Sentry | `npx skills add addyosmani/agent-skills --skill security-and-hardening` | Threat modeling, OWASP Top 10 mitigations, input sanitization, and secret protection. |
| **D2** | **`debugging-and-error-recovery`**| Diagnostics | `npx skills add addyosmani/agent-skills --skill debugging-and-error-recovery` | Systematic root cause analysis, stack trace deconstruction, and defensive error isolation. |
| **D2** | **`observability-and-instrumentation`**| Ops & Telemetry | `npx skills add addyosmani/agent-skills --skill observability-and-instrumentation` | Structured JSON logs, OpenTelemetry distributed tracing, Prometheus metrics, and alert rules. |

### 🚀 Cluster D3: DevOps & Workflows (`devops`)

| Cluster | Slug | Category | NPX Install Command | Capabilities & Frameworks |
| :--- | :--- | :--- | :--- | :--- |
| **D3** | **`ci-cd-and-automation`** | DevOps & Pipelines | `npx skills add addyosmani/agent-skills --skill ci-cd-and-automation` | GitHub Actions workflows, matrix testing, deterministic caching, and automated release gates. |
| **D3** | **`git-workflow-and-versioning`** | Git & Release | `npx skills add addyosmani/agent-skills --skill git-workflow-and-versioning` | Conventional commits, atomic PRs, interactive rebase workflows, and semantic versioning tags. |
| **D3** | **`deprecation-and-migration`** | Database & Migration | `npx skills add addyosmani/agent-skills --skill deprecation-and-migration` | Expand/Contract database migrations, automated codemods, and zero-downtime upgrades. |

### 🧠 Cluster D4: AI & Evaluation (`ai`)

| Cluster | Slug | Category | NPX Install Command | Capabilities & Frameworks |
| :--- | :--- | :--- | :--- | :--- |
| **D4** | **`context-engineering`** | AI Engineering | `npx skills add addyosmani/agent-skills --skill context-engineering` | Token context window budgeting, prompt packing, and progressive disclosure tree navigation. |
| **D4** | **`benchmark-harness`** | Evals & Benchmarking | `npx skills add agent-skill-forge --skill benchmark-harness` | Automated latency, memory allocation, and throughput regression testing with statistical variance checks. |

---

## 👤 3. Attributions & Lineage Matrix

| Skill / Domain | Original Creators & Inspirations | Upstream Repositories / Standards | Adaptation & Role in `agent-skill-forge` |
| :--- | :--- | :--- | :--- |
| **`unslop`** | **Matt Pocock** & **poteto / Cursor pstack** | [`mattpocock/skills/deslop`](https://github.com/mattpocock/skills) & [`cursor/plugins/pstack`](https://github.com/cursor/plugins/tree/main/pstack) | Fused universal anti-bloat engine spanning code, prose, analysis, and visual UI. |
| **`grill`** | **Matt Pocock** & **Addy Osmani** | [`mattpocock/skills/grill-me-with-docs`](https://github.com/mattpocock/skills) & [`addyosmani/agent-skills/interview-me`](https://github.com/addyosmani/agent-skills) | Fused 1-question Socratic alignment protocol with confidence stop gating. |
| **`spec`** | **Addy Osmani** | [`addyosmani/agent-skills/source-driven-development`](https://github.com/addyosmani/agent-skills) | Source-grounded specification engine with official API doc citations. |
| **`plan`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/planning`](https://github.com/addyosmani/agent-skills) | Vertical task slicing and dependency DAG checkpointing. |
| **`test`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/test`](https://github.com/addyosmani/agent-skills) | Test-Driven Development and Prove-It bug reproduction loop. |
| **`review`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/review`](https://github.com/addyosmani/agent-skills) | 5-axis code and architectural review framework. |
| **`prompt`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/prompt`](https://github.com/ksprashu/agent-skill-forge) | Intent engineering, 6-persona framework, and DAG task graph compiler. |
| **`verify`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/verify`](https://github.com/ksprashu/agent-skill-forge) | Expectation-Grounded Alignment (EGA) with static checks + blinded judge rubrics. |
| **`docs`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/docs`](https://github.com/ksprashu/agent-skill-forge) | Full SDLC documentation scaffolding + Stitch 4-theme interactive HTML compiler. |
| **`catalog`** | **Prashanth Subrahmanyam** | [Google Open Knowledge Format (OKF)](https://github.com/ksprashu/agent-skill-forge) | Codebase memory and progressive disclosure index tree specification. |
| **`sync`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/sync`](https://github.com/ksprashu/agent-skill-forge) | Multi-runtime symlink synchronizer and JIT workspace bootstrapper. |
| **`google-oss`** | **Google Open Source Programs Office (OSPO)** | [Google Open Source Docs](https://opensource.google/documentation) | Apache-2.0 compliance, header automation, and repository sanitization. |
| **`codelab`** | **Google Developer Relations** | [Google Codelabs](https://codelabs.developers.google.com/) | Interactive step-by-step developer tutorial authoring and quality validation. |
| **`voice`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/voice`](https://github.com/ksprashu/agent-skill-forge) | PII-sanitized linguistic style and typing cadence extraction. |
| **`copy-write`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/copy-write`](https://github.com/ksprashu/agent-skill-forge) | Technical prose companion with 3-tier Profile-Overlay voice personalization. |
| **`image-gen`** | **Google DeepMind** | [Gemini API Documentation](https://ai.google.dev/) | Multimodal image and diagram generation using Gemini Flash Image. |
| **`continuous-alignment`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/continuous-alignment`](https://github.com/ksprashu/agent-skill-forge) | Transcript-distilled memory distillation, strict 200-line AGENTS.md budget guard, living ADRs, and roadmap visualizer. |
| **`work`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/work`](https://github.com/ksprashu/agent-skill-forge) | Autonomous multi-agent swarm engine with Sentinel protocol, tournament arbiter, and DAG runner. |
| **Preferred Skills (12)** | **Addy Osmani**, **Matt Pocock**, **Cursor**, **Anthropic** | [`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills), [`mattpocock/skills`](https://github.com/mattpocock/skills), [`anthropics/skills`](https://github.com/anthropics/skills) | Curated domain skills for frontend, performance, security, CI/CD, and debugging. |
