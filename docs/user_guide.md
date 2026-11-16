---
title: "Agent Skill Forge User Guide"
description: "Comprehensive operational framework, execution flow, and JIT preferred domain skills guide for AI agents."
theme: "technical"
---

# 📖 Agent Skill Forge User Guide

A comprehensive, zero-slop operational framework for orchestrating **Agent Skill Forge** across **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

---

## 🏛️ 1. Architecture: Modular Clusters & Selective Installation

To maximize agent efficiency, eliminate AI slop, and prevent context bloat, **Agent Skill Forge** organizes its skills into functional clusters across two categories:

### 📦 Core Clusters (Action Skills)
Available globally or installable in focused sections:
*   **Cluster C1: Planning, Specification & Swarm Execution (`plan-spec`)**: `spec`, `plan`, `grill`, `prompt`, `work`, `h2o`
*   **Cluster C2: Quality & Verification (`test-review`)**: `test`, `verify`, `review`, `security-review`, `pr-review-loop`, `issue-loop`, `unslop`
*   **Cluster C3: Content, Creative & Authoring (`content-creative`)**: `codelab`, `human-voice`, `voice-register`, `cognitive-profiler`, `image-gen`, `video-gen`, `audio-gen`, `atelier`, `chronicle`
*   **Cluster C4: Knowledge & Governance (`docs-governance`)**: `docs`, `catalog`, `google-oss`, `continuous-alignment`, `handoff`, `horizon`

### 🛠️ Domain Clusters (Preferred Skills)
Bootstrapped JIT into project workspaces (`.gemini/skills/`) or installed globally. All but `agent-security-posture` come from `addyosmani/agent-skills`, pinned in `config/upstream.lock.json` and fetched into `.upstream/` at install time:
*   **Cluster D1: Full-Stack & Quality (`fullstack`)**: `frontend-ui-engineering`, `performance-optimization`, `browser-testing-with-devtools`, `api-and-interface-design`
*   **Cluster D2: Security, Diagnostics & Reliability (`security`)**: `agent-security-posture`, `debugging-and-error-recovery`, `observability-and-instrumentation`
*   **Cluster D3: DevOps & Workflows (`devops`)**: `ci-cd-and-automation`, `git-workflow-and-versioning`, `deprecation-and-migration`
*   **Cluster D4: AI & Context (`ai`)**: `context-engineering`

```
                                  ┌──────────────────────────────────────────────────────────┐
                                  │            AGENT SKILL FORGE TAXONOMY (39 SKILLS)        │
                                  └────────────────────────────┬─────────────────────────────┘
                                                               │
                              ┌────────────────────────────────┴────────────────────────────────┐
                              ▼                                                                 ▼
               ┌──────────────────────────────┐                                  ┌──────────────────────────────┐
               │    CORE CLUSTERS (C1 - C4)   │                                  │   DOMAIN CLUSTERS (D1 - D4)  │
               ├──────────────────────────────┤                                  ├──────────────────────────────┤
               │ C1: Plan, Spec & Swarm       │                                  │ D1: Full-Stack & Quality     │
               │     /spec, /plan, /grill,    │                                  │     frontend-ui, perf-opt,   │
               │     /prompt, /work, /h2o     │                                  │     browser-test, api-design │
               │                              │                                  │                              │
               │ C2: Quality & Verification   │                                  │ D2: Security & Reliability   │
               │     /test, /verify, /review, │                                  │     agent-security-posture,  │
               │     /security-review,        │                                  │     debugging, observability │
               │     /pr-review-loop,         │                                  │                              │
               │     /issue-loop, /unslop     │                                  │                              │
               │                              │                                  │                              │
               │ C3: Content & Creative       │                                  │ D3: DevOps & Workflows       │
               │     /codelab, /human-voice,  │                                  │     ci-cd, git-workflow,     │
               │     voice-register,          │                                  │     deprecation-migration    │
               │     /cognitive-profiler,     │                                  │                              │
               │     /image-gen, /video-gen,  │                                  │                              │
               │     /audio-gen, atelier,     │                                  │                              │
               │     /chronicle               │                                  │                              │
               │                              │                                  │                              │
               │ C4: Knowledge & Governance   │                                  │ D4: AI & Context             │
               │     /docs, /catalog,         │                                  │     context-engineering      │
               │     /google-oss, /align,     │                                  │                              │
               │     /handoff, /horizon       │                                  │                              │
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

### 📐 Cluster C1: Planning, Specification & Swarm Execution (`plan-spec`)
*   **`/spec`** (`skills/spec`): Writes source-grounded specifications with official API doc citations, interface data contracts, and explicit non-goals before generating code.
*   **`/plan`** (`skills/plan`): Slices specifications into vertically testable task units with dependency DAG checkpoints.
*   **`/grill`** (`skills/grill`): Conducts an iterative, 1-question-at-a-time Socratic interview with attached technical hypotheses, continuing until all ambiguities are resolved.
*   **`/prompt`** (`skills/prompt`): Deconstructs vague requests, complex architectural goals, or multi-step tasks into clear intent directives and machine-readable dependency graphs (`task_graph.json`).
*   **`/work`** (`skills/work`): Coordinates parallel multi-agent swarms with Sentinel oversight, dispatch-only orchestration, competitive branching tournaments, and adversarial verification. Its DAG gates are settled by a script rather than by the agent's own say-so, and a forensic auditor is calibrated against a known-fake corpus.
*   **`/h2o`** (`skills/h2o`): Runs a lean sequential swarm. The coordinator grills you to >= 90% confidence and freezes binary done criteria, then one Hydrogen planner and one Hydrogen implementer work against Opus adversarial gates (plan, functional, code, security). Each gate allows 3 NOT GOOD verdicts before asking you to stop or continue. Use `/work` instead for the heavyweight parallel DAG swarm with design tournaments.

### 🧪 Cluster C2: Quality & Verification (`test-review`)
*   **`/test`** (`skills/test`): Enforces Test-Driven Development (TDD) and Prove-It reproduction loops. Requires writing failing unit/integration tests before writing implementation logic.
*   **`/verify`** (`skills/verify`): Expectation-Grounded Alignment (EGA). Executes deterministic static check scripts alongside blinded multi-persona dynamic LLM judge rubrics.
*   **`/review`** (`skills/review`): Runs the repo's linters and type checkers, then reviews across eight axes (scope/architecture, correctness, security, reliability, performance, data integrity, tests, observability) plus style, and emits schema-validated findings (P0–P3, nit) and SARIF.
*   **`/security-review`** (`skills/security-review`): Runs semgrep, gitleaks, osv-scanner, trivy, actionlint, zizmor and native audits as leads, then confirms each against a six-element finding test grounded in OWASP Top 10 2025, ASVS 5.0 and CWE Top 25. Uses the same findings schema and P0–P3 scale as `review`.
*   **`/pr-review-loop`** (`skills/pr-review-loop`): Works the review threads on your PR until the `pr-guardian/verdict` gate is green: fixes and replies with the SHA, pushes back with `/ai-review wontfix:`, or escalates to a human, and resolves a thread only after pr-guardian verifies it.
*   **`/issue-loop`** (`skills/issue-loop`, aliases `/fix-issue`, `/fix-issues`): Drives open GitHub issues through five gated stages: redacted intake and triage, file-disjoint track planning, a TDD red-green fix on a feature branch, review plus a cross-family verification gate, and PR creation with final issue updates.
*   **`/unslop`** (`skills/unslop`): Universal anti-bloat engine. Strips AI smells, promotional bloat, and filler words from prose, docs, code comments, commit messages, analyses, and UI copy. It leaves code logic alone.

### 🎨 Cluster C3: Content, Creative & Authoring (`content-creative`)
*   **`/codelab`** (`skills/codelab`): Scaffolds and validates interactive step-by-step developer tutorials and hands-on workshops formatted for `claat`.
*   **`/human-voice`** (`skills/human-voice`): Scans developer tool logs, scrubs PII, and extracts authentic human writing style markers and typing cadence for personalization.
*   **`voice-register`** (`skills/voice-register`): Applies your voice profile in the right channel register (email, blog, strategy doc, notes) on top of `unslop`. Profile tiers: `.local.md` > `~/.gemini/personas/default/` > `.template.md`.
*   **`/cognitive-profiler`** (`skills/cognitive-profiler`, alias `/profile-me`): Harvests redacted evidence of how you react to AI output, judges it against a rubric, and compiles a cited communication profile into `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `.cursorrules`.
*   **`/image-gen`** (`skills/image-gen`): Generates high-fidelity technical architecture diagrams, infographics, and UI graphics using Gemini Flash Image.
*   **`/video-gen`** (`skills/video-gen`): Generates and chains arbitrary-length videos via `gemini-api` (`gemini-omni-1.2-flash`) and `ffmpeg`, with broadcast `-14 LUFS` audio, OCR-verified scene text, captions, and motion cards.
*   **`/audio-gen`** (`skills/audio-gen`, aliases `/music-gen`, `/sfx-gen`, `/tts-gen`): Generates and verifies music, TTS narration and dialogue, custom voices, foley, and stingers, then masters 2-pass `-14 LUFS` ducked mixes.
*   **`atelier`** (`skills/atelier`, auto on reports and briefs): Produces subject-grounded, scannable reports, briefs, digests, and documents with strong hierarchy, tables, and diagrams, avoiding generic AI aesthetics.
*   **`/chronicle`** (`skills/chronicle`): Turns a technical report, dossier, or architecture brief into a Gladwell/Grant nonfiction chapter or field book, with evidence badges and a Field Notebook checklist.

### 📚 Cluster C4: Knowledge & Governance (`docs-governance`)
*   **`/docs`** (`skills/docs`): Generates full SDLC documentation suites and compiles markdown into interactive, 4-theme standalone HTML presentation portals.
*   **`/catalog`** (`skills/catalog`): Scaffolds and indexes Google Open Knowledge Format (OKF) progressive disclosure knowledge bundles (`.gemini/knowledge/`) for durable codebase memory.
*   **`/google-oss`** (`skills/google-oss`): Audits codebases for Google Open Source compliance, inserts Apache-2.0 license headers, and sanitizes internal corporate paths.
*   **`/align`** (`skills/continuous-alignment`): Distills conversation session transcripts into a strict 200-line `AGENTS.md` budget, records living Architecture Decision Records (ADRs), and compiles roadmap visualizers.
*   **`/handoff`** (`skills/handoff`, alias `/handover`): Packages multi-repository session state, locked decisions, and SHA-256 file digests into `.handoff/HANDOFF.md`, and arms reversible Turn-0 auto-pickup beacons across Google Antigravity (`agy`), Claude Code, OpenAI Codex, and Cursor. See [`skills/handoff/README.md`](../skills/handoff/README.md).
*   **`/horizon`** (`skills/horizon`, aliases `/radar`, `/tech-horizon`): Persists 6-12 month technical forecasts into a central ledger (`~/.gemini/horizons/`), runs deterministic upstream and anchor probes, validates sweep verdicts, enforces SHA-256 pre-edit backups and PR URL provenance, and renders `INDEX.md`. See [`skills/horizon/README.md`](../skills/horizon/README.md).

---

## 🔄 4. The Universal Engineering Flow & Order of Execution

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
[5. JIT sync] ────────► `scripts/sync_skills.py --project . --skills <names> --fix`
      │
┌─────▼────────────────────────────────────────────────────────┐
│                   THE TDD EXECUTION LOOP                     │
│                                                              │
│  [6. /test]   ──► Write failing "Prove-It" test first        │
│        │                                                     │
│  [Implement]  ──► Write minimal implementation               │
│        │                                                     │
│  [7. /unslop] ──► Strip AI tells from comments & prose       │
└─────┬────────────────────────────────────────────────────────┘
      │
[8. /verify]  ────────► Run static verifier scripts & blinded judge rubrics
      │
[9. /review]  ────────► 8-axis audit + style (Scope/Arch, Correctness, Security, ...)
      │
[10. /docs]   ────────► Scaffold SDLC docs & compile standalone HTML portal
      │
[11. /align]  ────────► Distill session learnings into AGENTS.md & living ADRs
      │
[12. /handoff]────────► Package multi-repo baton & arm Turn-0 cross-tool beacons
```

---

## 📋 5. Step-by-Step Flow Rationale: Why This Order Matters

| Sequence | Skill / Gate | Why It Must Run at This Exact Stage |
| :--- | :--- | :--- |
| **Step 1** | **`/prompt`** | **Prevents wrong-direction execution.** Formulates intent directives, establishes Manager-worker roles, and determines whether lightweight or heavyweight execution is required. |
| **Step 2** | **`/grill`** | **Eliminates all implicit assumptions.** Asks as many questions as necessary—iteratively and strictly *one question at a time* with attached hypotheses—until all architectural, data, UX, and security ambiguities are 100% resolved and the spec is completely fleshed out. |
| **Step 3** | **`/spec`** | **Prevents hallucinated APIs.** Grounds interfaces in official documentation citations and sets explicit Non-Goals to avoid scope creep. |
| **Step 4** | **`/plan`** | **Enforces incremental verifiability.** Slices work into small, vertically testable tasks so every component has an isolated pass/fail checkpoint. |
| **Step 5** | **JIT bootstrap (`scripts/sync_skills.py --project`)** | **Loads domain rules on demand.** Injects specialized domain conventions (e.g. modern CSS rules, threat modeling, distributed tracing) without polluting global memory. |
| **Step 6** | **`/test`** | **Guarantees correctness by construction.** For bugs, writing the failing test first proves reproduction. For new features, it defines expected behavior upfront. |
| **Step 7** | **`/unslop`** | **Strips AI tells before review.** Cleans sterile comments, docstrings, and commit messages while the diff is fresh. It leaves code logic alone. |
| **Step 8** | **`/verify`** | **Dual-layer deterministic proof.** Runs static deterministic check scripts (`verify_okf.py`) combined with multi-persona blinded LLM judge rubrics. |
| **Step 9** | **`/review`** | **Adversarial gate before commit.** Runs the repo's linters and type checkers, then evaluates diffs across eight axes (scope/architecture, correctness, security, reliability, performance, data integrity, tests, observability) plus style, emitting schema-validated findings. |
| **Step 10**| **`/docs` & `/catalog`** | **Preserves codebase memory.** Documents architecture in the Google Open Knowledge Format (`.gemini/knowledge/`) and compiles 4-theme standalone HTML portals. |
| **Step 11**| **`/align`** | **Keeps agent memory hot & lean.** Summarizes transcript learnings into the 200-line `AGENTS.md` budget, records living ADRs, and updates project roadmaps. |
| **Step 12**| **`/handoff`** | **Enables zero-loss cross-harness continuity.** Captures multi-repo git/SHA-256 drift digests into `.handoff/`, validates secret-free workspace-confined state, and arms reversible Turn-0 auto-pickup beacons across harnesses. |

---

## 🎨 6. Specialized Sub-Workflows

### A. The Content, Prose & Codelab Pipeline
Used when authoring documentation, tutorials, technical blogs, or developer keynotes:
1. **`/human-voice`**: Extracts typing cadence and linguistic markers from past transcripts (stripping PII).
2. **`/codelab`** or a plain draft: Writes the content.
3. **`/unslop`**: Eliminates AI filler words (*"delve"*, *"leverage"*, *"testament"*, *"in conclusion"*).
4. **`voice-register`**: For text published under your name, applies your voice profile and the channel register after unslop's hygiene pass. Profile tiers: `.local.md` > `~/.gemini/personas/default/` > `.template.md`.
5. **`/image-gen`**: Generates high-fidelity visual diagrams and infographics via Gemini Flash Image.
6. **`/docs`**: Compiles the markdown documentation into an interactive, self-contained single-page HTML portal.
7. **`/google-oss`**: Verifies Apache-2.0 headers and cleans internal company paths before publication.

For a narrative edition of an existing report or brief, invoke `/chronicle` (a chapter arc, evidence badges, and a Field Notebook) on the draft.

### B. The Fast Tactical Bugfix Flow
Used for urgent hotfixes, regression debugging, or localized patches:
1. **`debugging-and-error-recovery`** (JIT): Deconstructs the stack trace and isolates the minimal reproduction script.
2. **`/test`**: Writes a failing "Prove-It" unit or integration test reproducing the exact failure.
3. **Apply Minimal Fix**: Implements the smallest patch that makes the test pass.
4. **`/unslop`**: Cleans sterile comments and the commit message.
5. **`/review`**: Audits the diff for potential side effects and regressions.
6. **`git-workflow-and-versioning`** (JIT): Formulates an atomic conventional commit (`fix: <description>`).

### C. Your Writing Voice on Every Machine
`unslop` keeps all prose neutral. `voice-register` adds your personal voice, but only to text that goes out under your name (emails, posts, docs, PR descriptions). The agent's replies to you stay neutral.

Your profile is private, so it doesn't live in this repo. Keep it in a private git repo of your own, cloned to `~/.gemini/personas`, and tell the skill where it is:

```bash
gh auth login                                   # once per machine
export AGENT_PERSONA_REPO=<you>/agent-persona   # in your shell profile
```

On a new machine, `voice-register` clones the repo the first time it needs your voice, and refreshes it at most once a day. The installer also pulls it when the variable is set. Run `python3 <voice-register-dir>/scripts/persona.py status` to see which profile resolves.

If you don't set the variable, nothing is fetched and you get neutral prose, with a note that no profile was found. That's what a public user sees until they create their own persona repo. See [`skills/voice-register/README.md`](../skills/voice-register/README.md) for creating the repo, every `persona.py` behavior, and the settings.

---

## 📦 7. Curated Preferred Skills (On-Demand / JIT Catalog)

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
| **`deprecation-and-migration`** | Refactoring legacy APIs, database migrations, or breaking upgrades. | Expand/Contract migration patterns, zero-downtime schema changes, automated codemods, dual-write bridges. |
| **`browser-testing-with-devtools`** | E2E web verification, DOM inspection, visual regressions. | Headless Chrome DevTools testing, console exception trapping, visual snapshot validation, network stubbing. |
| **`observability-and-instrumentation`** | Production services, microservices, background queues. | Structured JSON logs, OpenTelemetry distributed traces, Prometheus metrics (RED/USE methods), alert rules. |
| **`ci-cd-and-automation`** | Setting up repositories, CI presubmits, release pipelines. | Multi-platform GitHub Actions workflows, matrix testing, deterministic caching, semantic release tagging. |
| **`agent-security-posture`** | Code, dependency, agent tool or MCP config changes; security reviews, CVE checks, read-only infrastructure audits. Local to the forge, not upstream. | Agent authority rules for untrusted content, OSV/NVD dependency checks, secret handling, finding verdicts and severity, read-only infrastructure audits. |
| **`debugging-and-error-recovery`** | Production crashes, unhandled stack traces, complex regressions. | Systematic root cause analysis, stack trace isolation, minimal reproducible test cases, defensive boundaries. |
| **`git-workflow-and-versioning`** | Branch management, PR preparation, release tagging. | Conventional commits (`feat:`, `fix:`), atomic PR slicing, interactive rebase, SemVer release automation. |
| **`context-engineering`** | Complex multi-agent prompts, large token budgets, LLM reasoning pipelines. | Context window optimization, prompt compression, memory eviction, token economy budgeting. |

---

## 🎯 8. Decision Matrix: Which Skill to Invoke When

| User Scenario / Trigger | Skill Invocations & Action |
| :--- | :--- |
| Vague request, complex multi-file task, or new architecture | Invoke `/prompt` |
| Unclear requirements, design trade-offs, or multiple choices | Invoke `/grill` |
| Defining new API interfaces, endpoints, or data models | Invoke `/spec` & `api-and-interface-design` |
| Creating a multi-step refactoring or implementation roadmap | Invoke `/plan` |
| Running a gated plan-build-review loop with cross-family adversarial reviewers | Invoke `/h2o` (lean, sequential); use `/work` for a parallel DAG swarm |
| Writing code or fixing a bug | Invoke `/test` (Prove-It TDD loop) |
| Cleaning AI filler from prose, comments, or commit messages | Invoke `/unslop` |
| Auditing code quality, security, or regressions | Invoke `/verify` & `/review` |
| Scanner-backed security review of a diff, PR, or repository | Invoke `/security-review` |
| Working pr-guardian review threads on your PR until the verdict gate is green | Invoke `/pr-review-loop` |
| Fixing one or more open GitHub issues end to end, from triage to PR | Invoke `/issue-loop` (`/fix-issue`, `/fix-issues`) |
| Scaffolding SDLC doc suite or compiling HTML presentations | Invoke `/docs` & `compile_docs.py` |
| Extracting developer voice or drafting technical prose | Invoke `/human-voice`, then `voice-register` |
| Creating step-by-step developer workshops or codelabs | Invoke `/codelab` |
| Turning a technical report or brief into a nonfiction story or field book | Invoke `/chronicle` |
| Verifying OSS license compliance and cleaning company paths | Invoke `/google-oss` |
| Maintaining project vision, rules budget, and living ADRs | Invoke `/align` (`continuous-alignment`) |
| Switching AI coding tools or pausing a multi-session / multi-repo arc | Invoke `/handoff` (`skills/handoff`) |
| Tracking a 6-12 month technical forecast or sweeping an upstream watchlist | Invoke `/horizon` (`/radar`, `/tech-horizon`) |
| Adding UI components, styles, or responsive layouts | Bootstrap JIT: `frontend-ui-engineering` |
| Optimizing database queries, bundle size, or CWV (LCP/INP) | Bootstrap JIT: `performance-optimization` |
| Building secure auth flows or remediating OWASP/CWE issues | Invoke `/review`; bootstrap JIT: `agent-security-posture` |
| Setting up GitHub Actions, test presubmits, or release CI | Bootstrap JIT: `ci-cd-and-automation` |

---

## 💡 9. The 5 Invariant Best Practices

1. **Never Skip the `/test` Prove-It Step**: For bug fixes, reproduction *is* the proof. Write the failing test before changing a single line of application logic.
2. **Run `/unslop` Before `/review`**: Always de-slop generated comments and documentation before running reviews. Verbose comments distract from architectural review.
3. **Keep `AGENTS.md` Under 200 Lines**: Use `/align` regularly. It condenses project learnings and evicts stale instructions to prevent instruction drift and context degradation.
4. **Keep Your Voice Private**: Store your voice profile in `~/.gemini/personas/default/` or in `skills/voice-register/references/voice_and_tone.local.md` (gitignored). `voice-register` applies it to text sent under your name without exposing private data.
5. **Always Bootstrap Project-Scoped**: Never symlink domain skills (like `frontend-ui-engineering` or `agent-security-posture`) into global directories. Use `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills <name>` to keep workspace dependencies isolated and reproducible.

