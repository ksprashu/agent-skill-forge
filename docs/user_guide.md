---
title: "Agent Skill Forge User Guide"
description: "Comprehensive operational framework, execution flow, and JIT preferred domain skills guide for AI agents."
theme: "technical"
---

# 📖 Agent Skill Forge User Guide

A comprehensive, zero-slop operational framework for orchestrating **Agent Skill Forge** across **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

---

## 🏛️ 1. Architecture: Modular Clusters & Selective Installation

To maximize agent efficiency, eliminate AI slop, and prevent context bloat, **Agent Skill Forge** organizes all 30 skills into **8 functional clusters** across two categories:

### 📦 Core Clusters (18 Action Skills)
Available globally or installable in focused sections:
*   **Cluster C1: Planning & Specification (`plan-spec`)**: `spec`, `plan`, `grill`, `prompt`
*   **Cluster C2: Quality & Verification (`test-review`)**: `test`, `verify`, `review`, `unslop`
*   **Cluster C3: Content, Creative & Authoring (`content-creative`)**: `codelab`, `human-voice`, `copy-write`, `image-gen`
*   **Cluster C4: Knowledge & Governance (`docs-governance`)**: `docs`, `catalog`, `google-oss`, `continuous-alignment`, `sync`

### 🛠️ Domain Clusters (12 Preferred Skills)
Bootstrapped JIT into project workspaces (`.gemini/skills/`) or installed globally:
*   **Cluster D1: Full-Stack & Quality (`fullstack`)**: `frontend-ui-engineering`, `performance-optimization`, `browser-testing-with-devtools`, `api-and-interface-design`
*   **Cluster D2: Security, Diagnostics & Reliability (`security`)**: `security-and-hardening`, `debugging-and-error-recovery`, `observability-and-instrumentation`
*   **Cluster D3: DevOps & Workflows (`devops`)**: `ci-cd-and-automation`, `git-workflow-and-versioning`, `deprecation-and-migration`
*   **Cluster D4: AI & Evaluation (`ai`)**: `context-engineering`, `benchmark-harness`

```
                                  ┌──────────────────────────────────────────────────────────┐
                                  │            AGENT SKILL FORGE TAXONOMY (30 SKILLS)        │
                                  └────────────────────────────┬─────────────────────────────┘
                                                               │
                              ┌────────────────────────────────┴────────────────────────────────┐
                              ▼                                                                 ▼
               ┌──────────────────────────────┐                                  ┌──────────────────────────────┐
               │    CORE CLUSTERS (C1 - C4)   │                                  │   DOMAIN CLUSTERS (D1 - D4)  │
               ├──────────────────────────────┤                                  ├──────────────────────────────┤
               │ C1: Plan & Spec              │                                  │ D1: Full-Stack & Quality     │
               │     /spec, /plan, /grill,    │                                  │     frontend-ui, perf-opt,   │
               │     /prompt                  │                                  │     browser-test, api-design │
               │                              │                                  │                              │
               │ C2: Quality & Verification   │                                  │ D2: Security & Reliability   │
               │     /test, /verify, /review, │                                  │     security, debugging,     │
               │     /unslop                  │                                  │     observability            │
               │                              │                                  │                              │
               │ C3: Content & Creative       │                                  │ D3: DevOps & Workflows       │
               │     /codelab, /human-voice,  │                                  │     ci-cd, git-workflow,     │
               │     /copy-write, /image-gen  │                                  │     deprecation-migration    │
               │                              │                                  │                              │
               │ C4: Knowledge & Governance   │                                  │ D4: AI & Evaluation          │
               │     /docs, /catalog, /sync,  │                                  │     context-engineering,     │
               │     /google-oss, /align      │                                  │     benchmark-harness        │
               └──────────────────────────────┘                                  └──────────────────────────────┘
```

---

## ⚡ 2. How to Install Skills in Sections

Agent Skill Forge includes an interactive terminal installer and powerful scriptable flags:

### A. Interactive Wizard
Run the installer in an interactive terminal to choose exactly which clusters to install:
```bash
bash scripts/install.sh
```

### B. Installing Specific Clusters (e.g. Content & Creative Only)
If you only want specific skills (such as Codelabs, Human-Voice, Copywriting, Image-Gen) and want to exclude planning/spec skills:
```bash
# Install Cluster C3 only and prune unselected skills (like plan, spec, test):
bash scripts/install.sh --content --prune

# Or explicitly by cluster code:
bash scripts/install.sh --clusters c3 --prune
```

### C. Mixing Core and Domain Clusters
```bash
# Install Content & Creative (C3) + Full-Stack (D1):
bash scripts/install.sh --clusters c3,d1

# Install Quality & Verification (C2) + Security (D2):
bash scripts/install.sh --clusters c2,d2
```

### D. Presets & Complete Installation
```bash
# Install all Core skills:
bash scripts/install.sh --core

# Install all Preferred Domain skills:
bash scripts/install.sh --domain

# Install everything:
bash scripts/install.sh --all
```

---

## 🌟 3. Detailed Core Skills Directory by Cluster

### 📐 Cluster C1: Planning & Specification (`plan-spec`)
*   **`/spec`** (`skills/spec`): Writes source-grounded specifications with official API doc citations, interface data contracts, and explicit non-goals before generating code.
*   **`/plan`** (`skills/plan`): Slices specifications into vertically testable task units with dependency DAG checkpoints.
*   **`/grill`** (`skills/grill`): Conducts an iterative, 1-question-at-a-time Socratic interview with attached technical hypotheses, continuing until all ambiguities are resolved.
*   **`/prompt`** (`skills/prompt`): Deconstructs vague requests, complex architectural goals, or multi-step tasks into clear intent directives and machine-readable dependency graphs (`task_graph.json`).

### 🧪 Cluster C2: Quality & Verification (`test-review`)
*   **`/test`** (`skills/test`): Enforces Test-Driven Development (TDD) and Prove-It reproduction loops. Requires writing failing unit/integration tests before writing implementation logic.
*   **`/verify`** (`skills/verify`): Expectation-Grounded Alignment (EGA). Executes deterministic static check scripts alongside blinded multi-persona dynamic LLM judge rubrics.
*   **`/review`** (`skills/review`): Conducts 5-axis code reviews (Correctness, Security, Performance, Architecture, Readability) with line-by-line remediation diffs.
*   **`/unslop`** (`skills/unslop`): Universal anti-bloat engine. Strips AI boilerplate, defensive wrapper clutter, sterile filler words, and dead abstractions across code, prose, analyses, and UI.

### 🎨 Cluster C3: Content, Creative & Authoring (`content-creative`)
*   **`/codelab`** (`skills/codelab`): Scaffolds and validates interactive step-by-step developer tutorials and hands-on workshops formatted for `claat`.
*   **`/human-voice`** (`skills/human-voice`): Scans developer tool logs, scrubs PII, and extracts authentic human writing style markers and typing cadence for personalization.
*   **`/copy-write`** (`skills/copy-write`): Technical drafting companion for articles, keynotes, and announcements using a 3-tier Profile-Overlay system (`.local.md` > `personas/` > `.template.md`).
*   **`/image-gen`** (`skills/image-gen`): Generates high-fidelity technical architecture diagrams, infographics, and UI graphics using Gemini Flash Image.

### 📚 Cluster C4: Knowledge & Governance (`docs-governance`)
*   **`/docs`** (`skills/docs`): Generates full SDLC documentation suites and compiles markdown into interactive, 4-theme standalone HTML presentation portals.
*   **`/catalog`** (`skills/catalog`): Scaffolds and indexes Google Open Knowledge Format (OKF) progressive disclosure knowledge bundles (`.gemini/knowledge/`) for durable codebase memory.
*   **`/google-oss`** (`skills/google-oss`): Audits codebases for Google Open Source compliance, inserts Apache-2.0 license headers, and sanitizes internal corporate paths.
*   **`/align`** (`skills/continuous-alignment`): Distills conversation session transcripts into a strict 200-line `AGENTS.md` budget, records living Architecture Decision Records (ADRs), and compiles roadmap visualizers.
*   **`/sync`** (`skills/sync`): Manages symlinks across global agent directories and bootstraps domain skills into project workspaces on demand.

---

## 🔄 3. The Universal Engineering Flow & Order of Execution

For any substantive engineering, refactoring, or feature development task, invoke skills in this strict sequence:

```
[1. /prompt]  ────────► Decompose intent, select model tier & generate DAG
      │
[2. /grill]   ────────► Clarify open questions 1-by-1 until 95% confident
      │
[3. /spec]    ────────► Ground in official docs, define data contracts & non-goals
      │
[4. /plan]    ────────► Slice into vertical tasks with verification checkpoints
      │
[5. /sync]    ────────► Bootstrap required JIT domain skills into workspace
      │
┌─────▼────────────────────────────────────────────────────────┐
│                   THE TDD EXECUTION LOOP                     │
│                                                              │
│  [6. /test]   ──► Write failing "Prove-It" test first        │
│        │                                                     │
│  [Implement]  ──► Write minimal implementation               │
│        │                                                     │
│  [7. /unslop] ──► Strip AI wrapper clutter & sterile bloat   │
└─────┬────────────────────────────────────────────────────────┘
      │
[8. /verify]  ────────► Run static verifier scripts & blinded judge rubrics
      │
[9. /review]  ────────► 5-Axis audit (Correctness, Security, Perf, Arch, Style)
      │
[10. /docs]   ────────► Scaffold SDLC docs & compile standalone HTML portal
      │
[11. /align]  ────────► Distill session learnings into AGENTS.md & living ADRs
```

---

## 📋 4. Step-by-Step Flow Rationale: Why This Order Matters

| Sequence | Skill / Gate | Why It Must Run at This Exact Stage |
| :--- | :--- | :--- |
| **Step 1** | **`/prompt`** | **Prevents wrong-direction execution.** Formulates intent directives, establishes Manager-worker roles, and determines whether lightweight or heavyweight execution is required. |
| **Step 2** | **`/grill`** | **Eliminates all implicit assumptions.** Asks as many questions as necessary—iteratively and strictly *one question at a time* with attached hypotheses—until all architectural, data, UX, and security ambiguities are 100% resolved and the spec is completely fleshed out. |
| **Step 3** | **`/spec`** | **Prevents hallucinated APIs.** Grounds interfaces in official documentation citations and sets explicit Non-Goals to avoid scope creep. |
| **Step 4** | **`/plan`** | **Enforces incremental verifiability.** Slices work into small, vertically testable tasks so every component has an isolated pass/fail checkpoint. |
| **Step 5** | **`/sync` (JIT)** | **Loads domain rules on demand.** Injects specialized domain conventions (e.g. modern CSS rules, threat modeling, distributed tracing) without polluting global memory. |
| **Step 6** | **`/test`** | **Guarantees correctness by construction.** For bugs, writing the failing test first proves reproduction. For new features, it defines expected behavior upfront. |
| **Step 7** | **`/unslop`** | **Strips AI tells before review.** Inlines redundant single-use helpers, removes defensive wrapper bloat, and eliminates sterile comments while the code diff is fresh. |
| **Step 8** | **`/verify`** | **Dual-layer deterministic proof.** Runs static deterministic check scripts (`verify_okf.py`) combined with multi-persona blinded LLM judge rubrics. |
| **Step 9** | **`/review`** | **Adversarial gate before commit.** Evaluates diffs across 5 axes (Correctness, Security, Performance, Architecture, Readability) with line-by-line remediation. |
| **Step 10**| **`/docs` & `/catalog`** | **Preserves codebase memory.** Documents architecture in the Google Open Knowledge Format (`.gemini/knowledge/`) and compiles 4-theme standalone HTML portals. |
| **Step 11**| **`/align`** | **Keeps agent memory hot & lean.** Summarizes transcript learnings into the 200-line `AGENTS.md` budget, records living ADRs, and updates project roadmaps. |

---

## 🎨 5. Specialized Sub-Workflows

### A. The Content, Prose & Codelab Pipeline
Used when authoring documentation, tutorials, technical blogs, or developer keynotes:
1. **`/human-voice`**: Extracts typing cadence and linguistic markers from past transcripts (stripping PII).
2. **`/copy-write`** or **`/codelab`**: Generates drafts using the 3-tier Profile-Overlay system (`.local.md` > `~/.gemini/personas/` > `.template.md`).
3. **`/image-gen`**: Generates high-fidelity visual diagrams and infographics via Gemini Flash Image.
4. **`/unslop`**: Eliminates AI filler words (*"delve"*, *"leverage"*, *"testament"*, *"in conclusion"*).
5. **`/docs`**: Compiles the markdown documentation into an interactive, self-contained single-page HTML portal.
6. **`/google-oss`**: Verifies Apache-2.0 headers and cleans internal company paths before publication.

### B. The Fast Tactical Bugfix Flow
Used for urgent hotfixes, regression debugging, or localized patches:
1. **`debugging-and-error-recovery`** (JIT): Deconstructs the stack trace and isolates the minimal reproduction script.
2. **`/test`**: Writes a failing "Prove-It" unit or integration test reproducing the exact failure.
3. **Apply Minimal Fix**: Implements the smallest patch that makes the test pass.
4. **`/unslop`**: Cleans up temporary debug wrappers, verbose logging, and trailing comments.
5. **`/review`**: Audits the diff for potential side effects and regressions.
6. **`git-workflow-and-versioning`** (JIT): Formulates an atomic conventional commit (`fix: <description>`).

---

## 📦 6. Curated Preferred Skills (On-Demand / JIT Catalog)

Specialized engineering skills should **never** be permanently installed in global scope. Instead, bootstrap them on demand into your workspace:

```bash
# Method 1: Local Monorepo Sync (Instant Symlinks)
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills <skill-1>,<skill-2>

# Method 2: Global npx skills Registry (Zero Config)
npx skills add ksprashu/agent-skill-forge --skill <skill-name>
```

---

### Complete Preferred Domain Skills Matrix

| Domain Skill | When to Invoke & Initialize | What It Enforces / Key Capabilities |
| :--- | :--- | :--- |
| **`frontend-ui-engineering`** | Web frontend, UI component, or stylesheet development. | Modern CSS (`:has()`, container queries, subgrid, View Transitions API), semantic HTML, accessible ARIA patterns, zero generic AI aesthetics. |
| **`performance-optimization`** | Slow response times, high LCP/INP, memory leaks, or heavy bundle sizes. | Core Web Vitals (CWV) budgets, layout thrashing elimination, query plan optimization, memory leak tracing. |
| **`api-and-interface-design`** | Designing REST, GraphQL, gRPC, or TypeScript interfaces. | Discriminated unions, Hyrum's Law mitigation, idempotency keys, backward-compatible evolutions. |
| **`security-and-hardening`** | Authentication, authorization, public endpoints, or input processing. | Threat modeling, OWASP Top 10 mitigations, input sanitization, secret scrubbing, boundary validation. |
| **`deprecation-and-migration`** | Refactoring legacy APIs, database migrations, or breaking upgrades. | Expand/Contract migration patterns, zero-downtime schema changes, automated codemods, dual-write bridges. |
| **`browser-testing-with-devtools`** | E2E web verification, DOM inspection, visual regressions. | Headless Chrome DevTools testing, console exception trapping, visual snapshot validation, network stubbing. |
| **`observability-and-instrumentation`** | Production services, microservices, background queues. | Structured JSON logs, OpenTelemetry distributed traces, Prometheus metrics (RED/USE methods), alert rules. |
| **`ci-cd-and-automation`** | Setting up repositories, CI presubmits, release pipelines. | Multi-platform GitHub Actions workflows, matrix testing, deterministic caching, semantic release tagging. |
| **`debugging-and-error-recovery`** | Production crashes, unhandled stack traces, complex regressions. | Systematic root cause analysis, stack trace isolation, minimal reproducible test cases, defensive boundaries. |
| **`git-workflow-and-versioning`** | Branch management, PR preparation, release tagging. | Conventional commits (`feat:`, `fix:`), atomic PR slicing, interactive rebase, SemVer release automation. |
| **`context-engineering`** | Complex multi-agent prompts, large token budgets, LLM reasoning pipelines. | Context window optimization, prompt compression, memory eviction, token economy budgeting. |
| **`benchmark-harness`** | Evaluating AI agent workflows, latency regressions, or benchmark runs. | Automated execution of 12 SWE benchmark use cases, artifact verification, Dual Gemini LLM-as-a-Judge scoring. |

---

## 🎯 7. Decision Matrix: Which Skill to Invoke When

| User Scenario / Trigger | Skill Invocations & Action |
| :--- | :--- |
| Vague request, complex multi-file task, or new architecture | Invoke `/prompt` |
| Unclear requirements, design trade-offs, or multiple choices | Invoke `/grill` |
| Defining new API interfaces, endpoints, or data models | Invoke `/spec` & `api-and-interface-design` |
| Creating a multi-step refactoring or implementation roadmap | Invoke `/plan` |
| Writing code or fixing a bug | Invoke `/test` (Prove-It TDD loop) |
| Cleaning verbose code, repetitive wrappers, or AI filler | Invoke `/unslop` |
| Auditing code quality, security, or regressions | Invoke `/verify` & `/review` |
| Scaffolding SDLC doc suite or compiling HTML presentations | Invoke `/docs` & `compile_docs.py` |
| Extracting developer voice or drafting technical prose | Invoke `/human-voice` & `/copy-write` |
| Creating step-by-step developer workshops or codelabs | Invoke `/codelab` |
| Verifying OSS license compliance and cleaning company paths | Invoke `/google-oss` |
| Maintaining project vision, rules budget, and living ADRs | Invoke `/align` (`continuous-alignment`) |
| Adding UI components, styles, or responsive layouts | Bootstrap JIT: `frontend-ui-engineering` |
| Optimizing database queries, bundle size, or CWV (LCP/INP) | Bootstrap JIT: `performance-optimization` |
| Building secure auth flows or remediating OWASP/CWE issues | Bootstrap JIT: `security-and-hardening` |
| Setting up GitHub Actions, test presubmits, or release CI | Bootstrap JIT: `ci-cd-and-automation` |

---

## 💡 8. The 5 Invariant Best Practices

1. **Never Skip the `/test` Prove-It Step**: For bug fixes, reproduction *is* the proof. Write the failing test before changing a single line of application logic.
2. **Run `/unslop` Before `/review`**: Always de-slop generated code and documentation before running reviews. It strips trivial helper wrappers and verbose comments that distract from architectural review.
3. **Keep `AGENTS.md` Under 200 Lines**: Use `/align` regularly. It condenses project learnings and evicts stale instructions to prevent instruction drift and context degradation.
4. **Use Profile-Overlays for Authentic Voice**: Store personal stylistic preferences in `references/*.local.md` (gitignored). The `copy-write` and `codelab` skills automatically layer this over baseline templates without exposing private data.
5. **Always Bootstrap Project-Scoped**: Never symlink domain skills (like `frontend-ui-engineering` or `security-and-hardening`) into global directories. Use `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills <name>` to keep workspace dependencies isolated and reproducible.

