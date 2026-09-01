# 🔨 Agent Skill Forge

A curated, unified monorepo of high-performance skills for **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

Built for engineering rigor, token context economy, and zero AI slop.

---

## 🚀 Quickstart

### 1. Install & Synchronize Global Skills (1-Liner)
Run the installer to link the 16 core universal action verbs into all your AI tools:

**macOS / Linux:**
```bash
bash scripts/install.sh
```

**Windows (PowerShell):**
```powershell
pwsh scripts/install.ps1
```

### 2. Verify Your Active Symlinks
```bash
python3 scripts/sync_skills.py
```

### 3. Bootstrap Project-Specific Skills on Demand
Need specialized domain skills for a specific project? Bootstrap them directly into your workspace or install via `npx skills`:
```bash
# Option A: Fast local symlink bootstrapper
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization

# Option B: Standard npx skills / skills.sh installer
npx skills add ksprashu/agent-skill-forge --skill frontend-ui-engineering
```

---

## 🌟 The 16 Core Universal Action Verbs

These 16 skills cover the complete end-to-end engineering lifecycle across code, prose, architectural analysis, tutorials, and visual design:

| Skill | Triggers & Invocations | Execution Mode | What It Does & When to Use |
| :--- | :--- | :--- | :--- |
| **`prompt`** | `/prompt` | User Slash | **Meta-Task & Intent Engineering**: Decomposes complex tasks, vague ideas, or multi-step goals into clear intent directives and dependency DAGs (`task_graph.json`). |
| **`grill`** | `/grill`, `/grill-me`, `/interview` | User Slash | **Socratic Grilling**: 1-question Socratic interview with attached hypotheses to clarify requirements, architecture, or design tradeoffs until 95% confident. |
| **`spec`** | `/spec`, auto on new features | Autonomous | **Specification & Source Grounding**: Writes structured, doc-cited specifications with explicit non-goals before writing code. |
| **`plan`** | `/plan`, auto after spec | Autonomous | **Task Slicing & Dependency DAGs**: Slices complex features, refactors, or projects into small, vertically sliced tasks with verifiable checkpoints. |
| **`test`** | `/test`, auto during coding | Autonomous | **Test-Driven Development & Prove-It**: Enforces writing failing tests first to prove bug reproduction and verify new feature behavior. |
| **`verify`** | `/verify`, `/ega`, `/harness` | Autonomous | **Expectation-Grounded Alignment (EGA)**: Dual-layer verification running deterministic static check scripts and blinded multi-persona dynamic judge rubrics. |
| **`review`** | `/review`, pre-merge | Autonomous | **5-Axis Code & Architecture Review**: Audits changes across correctness, security, performance, architecture, and readability with exact line fixes. |
| **`unslop`** | `/unslop`, `/deslop`, `/simplify` | Auto / Slash | **Universal Anti-Bloat Engine**: Strips AI boilerplate, defensive wrapper clutter, sterile prose, and unnecessary complexity from code, text, analyses, and UI. |
| **`docs`** | `/docs`, `/compile-docs` | User Slash | **SDLC Documentation & Stitch Compiler**: Scaffolds standard SDLC doc suites and compiles markdown into interactive 4-theme HTML portals. |
| **`catalog`** | `/catalog`, auto on concepts | Autonomous | **Open Knowledge Format (OKF)**: Scaffolds and indexes progressive disclosure knowledge bundles (`.gemini/knowledge/`) for long-term project memory. |
| **`sync`** | `/sync`, `/skill-sync` | User Slash | **Symlink & JIT Bootstrapper**: Manages symlinks across global agent runtimes and bootstraps domain skills into project workspaces. |
| **`google-oss`**| `/google-oss`, `/make-google-oss`| User Slash | **Open Source Compliance**: Audits repositories for Apache-2.0 license headers, scrubs internal corporate paths, and validates OSS structure. |
| **`codelab`** | `/codelab`, `/codelab-creator` | User Slash | **Google Codelab Authoring**: Scaffolds and validates interactive step-by-step developer tutorials and workshops. |
| **`voice`** | `/voice`, `/extract-voice` | User Slash | **Persona & Cadence Profiler**: Scans developer tool conversation logs, scrubs PII, and extracts authentic human writing style markers. |
| **`copy-write`**| `/copy-write`, `/copy-write-bara`| User Slash | **Technical Writing Companion**: Drafts technical articles, documentation, keynotes, and copy using 3-tier Profile-Overlay personalization. |
| **`image-gen`** | `/image-gen` | User Slash | **Multimodal Asset Generator**: Generates high-fidelity technical diagrams, infographics, and UI assets using Gemini Flash Image. |

---

## 🛠️ Curated Preferred Skills (Project-Scoped JIT)

Specialized engineering skills are stored in [`preferred/`](./preferred/) and can be bootstrapped into any workspace in seconds:

| Domain Skill | Trigger & Scope | Key Capabilities & Frameworks |
| :--- | :--- | :--- |
| **`frontend-ui-engineering`** | Frontend & UI tasks | Modern CSS (`:has()`, container queries, View Transitions), accessible components, clean design systems without generic AI aesthetic. |
| **`performance-optimization`**| Perf audits & optimization | Core Web Vitals (CWV), LCP/INP budgets, memory leak diagnosis, and backend query optimization. |
| **`api-and-interface-design`** | API & schema modeling | Hyrum's law, discriminated unions, idempotent REST/GraphQL contracts, and backward compatibility. |
| **`security-and-hardening`** | Security audits & fixes | Threat modeling, OWASP Top 10 mitigations, input sanitization, and secret protection. |
| **`deprecation-and-migration`**| Refactors & migrations | Expand/Contract database migrations, automated codemods, and zero-downtime upgrades. |
| **`browser-testing-with-devtools`**| Web testing & automation | Headless Chrome DevTools testing, console trapping, visual regression checks, and network assertions. |
| **`observability-and-instrumentation`**| Logging & telemetry | Structured JSON logs, OpenTelemetry distributed tracing, Prometheus metrics, and alert rules. |
| **`ci-cd-and-automation`** | Pipelines & workflows | GitHub Actions workflows, matrix testing, deterministic caching, and automated release gates. |
| **`debugging-and-error-recovery`**| Error investigation | Systematic root cause analysis, stack trace deconstruction, and defensive error isolation. |
| **`git-workflow-and-versioning`** | Git & release management | Conventional commits, atomic PRs, interactive rebase workflows, and semantic versioning tags. |
| **`context-engineering`** | Context optimization | Token context window budgeting, prompt packing, and progressive disclosure tree navigation. |
| **`benchmark-harness`** | Benchmarking & evals | Automated latency, memory allocation, and throughput regression testing with statistical variance checks. |

👉 Check out the full **[Preferred Skills Catalog](./preferred/PREFERRED_SKILLS.md)** for `npx skills` commands and detailed documentation.

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
├── skills/                     # 16 Core Universal Global Action Verbs
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
