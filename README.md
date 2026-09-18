# 🔨 Agent Skill Forge

A curated, unified monorepo of high-performance skills for **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

Built for engineering rigor, token context economy, and zero AI slop.

---

## 🚀 Quickstart & Selective Installation

`agent-skill-forge` allows you to install **everything**, **only specific clusters** (e.g. Content & Creative without Planning/Spec), or **individual skills**.

### 1. Interactive Wizard (Recommended)
Run the interactive installer in your terminal to pick exact clusters and target scope:

**macOS / Linux:**
```bash
bash scripts/install.sh
```

**Windows (PowerShell):**
```powershell
pwsh scripts/install.ps1
```

### 2. Fast Scripted Section Installation
Install only the specific clusters you need across all AI developer tools (`~/.gemini`, `~/.agents`, `~/.claude`, etc.):

```bash
# Install ONLY Content, Creative & Authoring skills (codelab, voice, copy-write, image-gen)
# Prunes unselected skills like plan, spec, test, etc.
bash scripts/install.sh --content --prune

# Install specific clusters (e.g., Content C3 + Full-Stack D1)
bash scripts/install.sh --clusters c3,d1

# Install only Quality & Verification skills (test, verify, review, unslop)
bash scripts/install.sh --clusters c2 --prune

# Install all Core skills (C1, C2, C3, C4)
bash scripts/install.sh --core

# Install all Preferred Domain skills (D1, D2, D3, D4)
bash scripts/install.sh --domain

# Install the COMPLETE Forge (All 30 Core + Domain skills)
bash scripts/install.sh --all

# Bootstrap specific clusters into a local project workspace only (.gemini/skills)
bash scripts/install.sh --project . --clusters c3,d1
```

### 3. Verify Active Skills & Clusters
```bash
# List all active symlinks across all AI tools
python3 scripts/sync_skills.py

# Print the complete cluster taxonomy with descriptions
python3 scripts/sync_skills.py --list-clusters
```

---

## 🌟 Core Skills Taxonomy (4 Clusters)

The 18 Core Action Skills cover the complete end-to-end engineering lifecycle and are organized into 4 functional clusters:

### 📐 Cluster C1: Planning, Specification & Swarm Execution (`plan-spec`)
*Grounds requirements, gathers intent, conducts Socratic alignment, plans dependency DAGs, and executes autonomous swarms.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`spec`](./skills/spec)** | `/spec` | Autonomous | **Grounded Specifications**: Writes specifications with official documentation citations, interface contracts, and explicit non-goals before coding. Prevents API hallucinations and scope creep. |
| **[`plan`](./skills/plan)** | `/plan` | Autonomous | **Task Slicing & Dependency DAGs**: Slices complex features or refactors into small, vertically testable tasks with verifiable checkpoints. Ensures incremental progress and rollback points. |
| **[`work`](./skills/work)** | `/work` | User Slash | **Autonomous Multi-Agent Swarm Engine**: Coordinates parallel swarms with Sentinel oversight, dispatch-only orchestration, competitive branching tournaments, and adversarial verification. |
| **[`grill`](./skills/grill)** | `/grill`, `/grill-me` | User Slash | **Socratic Requirements Interview**: 1-question Socratic interview with attached technical hypotheses to clarify requirements and tradeoffs until 95% confident. Eliminates hidden assumptions. |
| **[`prompt`](./skills/prompt)** | `/prompt` | User Slash | **Meta-Task & Intent Engineering**: Decomposes complex tasks, vague ideas, or multi-step goals into intent directives, model tier selection, and DAG task graphs (`task_graph.json`). |

### 🧪 Cluster C2: Quality & Verification (`test-review`)
*Enforces TDD, static verifiers, blinded judge rubrics, architectural reviews, and slop elimination.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`test`](./skills/test)** | `/test` | Autonomous | **TDD & Prove-It Reproduction**: Enforces writing failing tests first to prove bug reproduction before modifying production code. Guarantees bug fixes are permanent. |
| **[`verify`](./skills/verify)** | `/verify`, `/ega` | Autonomous | **Deterministic & Judged Verification**: Expectation-Grounded Alignment (EGA) running deterministic static check scripts alongside blinded multi-persona dynamic judge rubrics. |
| **[`review`](./skills/review)** | `/review` | Autonomous | **5-Axis Code & Architecture Review**: Audits changes across correctness, security, performance, architecture, and readability with line-by-line remediation diffs. |
| **[`unslop`](./skills/unslop)** | `/unslop`, `/simplify` | Auto / Slash | **Universal Anti-Bloat Engine**: Strips AI boilerplate, defensive wrapper clutter, sterile prose, and dead single-use abstractions from code, prose, and UI. |

### 🎨 Cluster C3: Content, Creative & Authoring (`content-creative`)
*Designs step-by-step developer tutorials, extracts human writing cadence, drafts articles, and synthesizes diagrams.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`codelab`](./skills/codelab)** | `/codelab` | User Slash | **Google Codelab Creator**: 7-phase workflow scaffolding engaging, interactive developer tutorials and workshops formatted for `claat` with automated quality guards. |
| **[`voice`](./skills/voice)** | `/voice` | User Slash | **Persona & Cadence Profiler**: Scans developer conversation logs, scrubs PII, and extracts authentic human writing style markers and typing cadence for personalization. |
| **[`copy-write`](./skills/copy-write)** | `/copy-write` | User Slash | **Technical Prose Companion**: Drafts articles, documentation, keynotes, and announcements using a 3-tier Profile-Overlay system (`.local.md` > `personas/` > `.template.md`). |
| **[`image-gen`](./skills/image-gen)** | `/image-gen` | User Slash | **Multimodal Diagram & Asset Generator**: Generates high-fidelity technical diagrams, infographics, and UI graphics using Gemini Flash Image with style consistency. |

### 📚 Cluster C4: Knowledge & Governance (`docs-governance`)
*Preserves durable codebase memory, compiles interactive portals, enforces OSS licensing, and keeps AGENTS.md lean.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`docs`](./skills/docs)** | `/docs`, `/compile-docs` | User Slash | **SDLC Docs & Stitch Compiler**: Scaffolds standard SDLC documentation suites and compiles markdown into interactive 4-theme standalone HTML presentation portals. |
| **[`catalog`](./skills/catalog)** | `/catalog` | Autonomous | **Open Knowledge Format (OKF)**: Scaffolds and indexes progressive disclosure knowledge bundles (`.gemini/knowledge/`) for durable codebase memory. |
| **[`google-oss`](./skills/google-oss)** | `/google-oss` | User Slash | **Open Source Compliance**: Audits repositories for Apache-2.0 license headers, scrubs internal corporate paths, and validates OSS structure. |
| **[`continuous-alignment`](./skills/continuous-alignment)** | `/align`, `/evolve` | Auto / Slash | **Continuous Alignment Engine**: Distills transcript learnings into a strict 200-line `AGENTS.md` budget, records living ADRs, and compiles roadmap visualizers. |
| **[`sync`](./skills/sync)** | `/sync` | User Slash | **Symlink Manager & JIT Bootstrapper**: Manages symlinks across global agent runtimes and bootstraps domain skills into project workspaces. |
>>>>>>> 5fc5217 (feat(installer): add skill clusters and selective installation support)

---

## 🛠️ Preferred Domain Skills Taxonomy (4 Clusters)

The 12 Preferred Domain Skills are stored in [`preferred/`](./preferred/) for project-scoped bootstrapping or selective global installation:

### 🌐 Cluster D1: Full-Stack & Quality (`fullstack`)
*   **[`frontend-ui-engineering`](./preferred/frontend-ui-engineering)**: Modern CSS (`:has()`, container queries, View Transitions), accessible components, and slop-free design systems.
*   **[`performance-optimization`](./preferred/performance-optimization)**: Core Web Vitals (CWV) budgets (LCP $\le 2.5$s, INP $\le 200$ms), memory leak diagnosis, and layout thrashing fixes.
*   **[`browser-testing-with-devtools`](./preferred/browser-testing-with-devtools)**: Headless Chrome DevTools automation, runtime console trapping, and live DOM inspection via MCP.
*   **[`api-and-interface-design`](./preferred/api-and-interface-design)**: Hyrum's law guardrails, discriminated unions, idempotent REST/GraphQL contracts, and backward compatibility.

### 🛡️ Cluster D2: Security, Diagnostics & Reliability (`security`)
*   **[`security-and-hardening`](./preferred/security-and-hardening)**: Trust boundary mapping, STRIDE threat modeling, OWASP Top 10 mitigations, and secret sanitization.
*   **[`debugging-and-error-recovery`](./preferred/debugging-and-error-recovery)**: Systematic 6-step root cause analysis, stack trace deconstruction, and Stop-the-Line discipline.
*   **[`observability-and-instrumentation`](./preferred/observability-and-instrumentation)**: Structured JSON logging, OpenTelemetry distributed tracing, RED/USE metrics, and alert rules.

### 🚀 Cluster D3: DevOps & Workflows (`devops`)
*   **[`ci-cd-and-automation`](./preferred/ci-cd-and-automation)**: Multi-platform GitHub Actions workflows, matrix testing, deterministic caching, and automated release gates.
*   **[`git-workflow-and-versioning`](./preferred/git-workflow-and-versioning)**: Trunk-based Git workflows, short-lived feature branches, conventional commits, and atomic PRs.
*   **[`deprecation-and-migration`](./preferred/deprecation-and-migration)**: Expand/Contract database migrations, automated codemods, and zero-downtime schema evolution.

### 🧠 Cluster D4: AI & Evaluation (`ai`)
*   **[`context-engineering`](./preferred/context-engineering)**: Token context window budgeting, prompt packing, 5-tier context hierarchy, and progressive memory eviction.
*   **[`benchmark-harness`](./preferred/benchmark-harness)**: Standardized evaluation suite scoring codebases across 12 standardized engineering use cases with Dual Gemini LLM Judges.

👉 See the **[Preferred Skills Guide](./preferred/PREFERRED_SKILLS.md)** for `npx skills` commands and individual installation details.

---

## 👤 Attributions & Lineage Matrix (Page at a Glance)

We gratefully acknowledge the creators, open-source contributors, and engineering pioneers whose work inspired and shaped the skills in `agent-skill-forge`:

| Skill / Domain | Original Creators & Inspirations | Upstream Repositories / Standards | Adaptation & Role in `agent-skill-forge` |
| :--- | :--- | :--- | :--- |
| **`unslop`** | **Matt Pocock** & **poteto / Cursor pstack** | [`mattpocock/skills/deslop`](https://github.com/mattpocock/skills) & [`cursor/plugins/pstack`](https://github.com/cursor/plugins/tree/main/pstack) | Fused universal anti-bloat engine spanning code, prose, analysis, and visual UI. |
| **`grill`** | **Matt Pocock** & **Addy Osmani** | [`mattpocock/skills/grill-me-with-docs`](https://github.com/mattpocock/skills) & [`addyosmani/agent-skills/interview-me`](https://github.com/addyosmani/agent-skills) | Fused 1-question Socratic alignment protocol with confidence stop gating. |
| **`spec`** | **Addy Osmani** | [`addyosmani/agent-skills/source-driven-development`](https://github.com/addyosmani/agent-skills) | Source-grounded specification engine with official API doc citations. |
| **`plan`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/planning`](https://github.com/addyosmani/agent-skills) | Vertical task slicing and dependency DAG checkpointing. |
| **`test`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/test`](https://github.com/addyosmani/agent-skills) | Test-Driven Development and Prove-It bug reproduction loop. |
| **`review`** | **Addy Osmani** | [`addyosmani/agent-skills/skills/review`](https://github.com/addyosmani/agent-skills) | 5-axis code and architectural review framework. |
| **`work`** | **Google DeepMind Antigravity Team** | Google Antigravity Teamwork System (`/teamwork-preview`) | Fully open, decoupled multi-agent swarm with Sentinel, Dispatch-Only Orchestrator, Explorers, Competitive Workers, Adversarial Quartet, and Victory Auditor. |
| **`prompt`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/prompt`](https://github.com/ksprashu/agent-skill-forge) | Intent engineering, 6-persona framework, and DAG task graph compiler. |
| **`verify`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/verify`](https://github.com/ksprashu/agent-skill-forge) | Expectation-Grounded Alignment (EGA) with static checks + blinded judge rubrics. |
| **`continuous-alignment`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/continuous-alignment`](https://github.com/ksprashu/agent-skill-forge) | Autonomous alignment, 200-line AGENTS.md budget engine, and living ADR compiler. |
| **`docs`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/docs`](https://github.com/ksprashu/agent-skill-forge) | Full SDLC documentation scaffolding + Stitch 4-theme interactive HTML compiler. |
| **`catalog`** | **Prashanth Subrahmanyam** | [Google Open Knowledge Format (OKF)](https://github.com/ksprashu/agent-skill-forge) | Codebase memory and progressive disclosure index tree specification. |
| **`sync`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/sync`](https://github.com/ksprashu/agent-skill-forge) | Multi-runtime symlink synchronizer and JIT workspace bootstrapper. |
| **`google-oss`** | **Google Open Source Programs Office (OSPO)** | [Google Open Source Docs](https://opensource.google/documentation) | Apache-2.0 compliance, header automation, and repository sanitization. |
| **`codelab`** | **Google Developer Relations** | [Google Codelabs](https://codelabs.developers.google.com/) | Interactive step-by-step developer tutorial authoring and quality validation. |
| **`voice`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/voice`](https://github.com/ksprashu/agent-skill-forge) | PII-sanitized linguistic style and typing cadence extraction. |
| **`copy-write`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/copy-write`](https://github.com/ksprashu/agent-skill-forge) | Technical prose companion with 3-tier Profile-Overlay voice personalization. |
| **`image-gen`** | **Google DeepMind** | [Gemini API Documentation](https://ai.google.dev/) | Multimodal image and diagram generation using Gemini Flash Image. |
| **Preferred Skills (12)** | **Addy Osmani**, **Matt Pocock**, **Cursor**, **Anthropic** | [`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills), [`mattpocock/skills`](https://github.com/mattpocock/skills), [`anthropics/skills`](https://github.com/anthropics/skills) | Curated domain skills for frontend, performance, security, CI/CD, and debugging. |

---

## 🛡️ Profile-Overlay Personalization

`agent-skill-forge` uses a **3-tier Profile-Overlay Architecture** so you can personalize tone and voice without leaking private information:

1. **Priority 1: Local Machine Profile (`references/*.local.md`)** — Gitignored private personal style rules.
2. **Priority 2: User Home Profile (`~/.gemini/personas/default/*.md`)** — System-wide user profile.
3. **Priority 3: Open Source Template (`references/*.template.md`)** — Public, clean baseline for team sharing.

---

## 📁 Monorepo Structure

```
agent-skill-forge/
├── skills/                     # 18 Core Universal Global Action Verbs
├── preferred/                  # 12 Curated Domain-Specific Skills (JIT)
│   ├── catalog.json            # Machine-readable registry
│   └── PREFERRED_SKILLS.md     # Quick bootstrap guide
├── scripts/                    # Installer & Verification Scripts
│   ├── install.sh              # 1-liner installer
│   ├── sync_skills.py          # Symlink manager & JIT bootstrapper
│   └── validate_skills.py      # Frontmatter linter & PII scanner
├── docs/                       # Full Documentation Suite & Stitch Portals
│   └── skill_authoring_guide.md# Official Skill Authoring Guide
├── .gemini/knowledge/          # Google OKF Knowledge Bundle
└── README.md                   # Monorepo Entrypoint & Attribution Matrix
```

---

## 📜 License & Compliance

Distributed under the **Apache-2.0 License**. All skill definitions are free of hardcoded PII and ready for enterprise collaboration.
