# 🔨 Agent Skill Forge

A curated, unified monorepo of high-performance skills for **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

Built for engineering rigor, token context economy, and zero AI slop.

---

## 🚀 Quickstart

### 1. Install & Synchronize Global Skills (1-Liner)
Run the installer to link the 15 core universal action verbs into all your AI tools:
```bash
bash scripts/install.sh
```

### 2. Verify Your Active Symlinks
```bash
python3 scripts/sync_skills.py
```

### 3. Bootstrap Project-Specific Skills on Demand
Need specialized domain skills for a specific project? Bootstrap them directly into your repo workspace without cluttering global memory:
```bash
# Inside your project directory:
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization
```

---

## 🌟 The 15 Core Global Action Verbs

These skills cover the entire software engineering lifecycle. They are linked globally across all your agent environments:

| Primary Verb | Slash Command | Mode | What It Does & When to Use |
| :--- | :--- | :--- | :--- |
| **`prompt`** | `/prompt` | User Slash | Meta-task intent engineering, Socratic grilling, and DAG task graph generation. |
| **`grill`** | `/grill` | User Slash | Disciplined 1-question Socratic interview with attached hypotheses and 95% confidence stop test. |
| **`spec`** | `/spec` | Autonomous | Gated specifications, non-goals, and official API documentation grounding. |
| **`plan`** | `/plan` | Autonomous | Vertical task slicing, dependency DAGs, and checkpointing. |
| **`test`** | `/test` | Autonomous | Test-Driven Development (TDD) and Prove-It bug reproduction loops. |
| **`verify`** | `/verify` | Autonomous | Expectation-Grounded Alignment (EGA) static AST/schema verifiers + 6-persona blinded judge rubrics. |
| **`review`** | `/review` | Autonomous | 5-axis code and architecture review (correctness, readability, architecture, security, performance). |
| **`unslop`** | `/unslop` | Autonomous | Anti-AI bloat, Laziness Protocol ("Subtract before you add"), and ghost abstraction elimination. |
| **`docs`** | `/docs` | User Slash | Full SDLC documentation suite + 4 Stitch themes interactive HTML presentation compilation. |
| **`catalog`** | `/catalog` | Autonomous | Google Open Knowledge Format (OKF) bundle scaffolding and progressive disclosure trees. |
| **`sync`** | `/sync` | User Slash | Canonical symlink manager and project-scoped skill bootstrapper. |
| **`google-oss`**| `/google-oss` | User Slash | Google Open Source compliance, license header checks, and repo sanitization. |
| **`codelab`** | `/codelab` | User Slash | Interactive Google Codelab tutorial scaffolding and markdown validation. |
| **`voice`** | `/voice` | User Slash | Linguistic style analysis, typing cadence extraction, and speech profiling. |
| **`copy-write`**| `/copy-write` | User Slash | Technical drafting companion with 3-tier Profile-Overlay personalization. |
| **`image-gen`** | `/image-gen` | User Slash | Multimodal diagram, infographic, and blog asset generator via Gemini Flash Image. |

---

## 🛠️ Curated Preferred Skills (Project-Scoped JIT)

Specialized engineering skills are stored in [`preferred/`](./preferred/) and can be installed into any workspace in seconds:

*   **`frontend-ui-engineering`**: Modern CSS layouts (`:has()`, container queries, View Transitions API).
*   **`performance-optimization`**: Core Web Vitals (CWV), LCP/INP budgets, and memory leak analysis.
*   **`api-and-interface-design`**: Hyrum's law, discriminated unions, and idempotent REST contracts.
*   **`security-and-hardening`**: Threat modeling, OWASP Top 10 fixes, and CWE sanitization.
*   **`deprecation-and-migration`**: Expand/Contract database schema migrations and zero-downtime updates.
*   **`browser-testing-with-devtools`**: Headless Chrome DevTools testing, console trapping, and network assertions.
*   **`observability-and-instrumentation`**: Structured JSON logs, OpenTelemetry distributed tracing, and metrics.
*   **`ci-cd-and-automation`**: GitHub Actions workflows, matrix testing, and automated release gates.
*   **`debugging-and-error-recovery`**: Stack trace deconstruction and defensive error isolation.
*   **`git-workflow-and-versioning`**: Conventional commits, atomic PRs, and linear Git history.
*   **`context-engineering`**: Token context optimization and LLM prompt packing.
*   **`benchmark-harness`**: Dual Gemini LLM-as-a-Judge scoring across 12 standardized engineering use cases.

👉 Check out the full **[Preferred Skills Catalog](./preferred/PREFERRED_SKILLS.md)** for `npx skills` commands and documentation links.

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
├── skills/                     # 15 Core Universal Global Action Verbs
├── preferred/                  # Curated Domain-Specific Skills (JIT)
│   ├── catalog.json            # Machine-readable registry
│   └── PREFERRED_SKILLS.md     # Quick bootstrap guide
├── scripts/                    # Installer & Verification Scripts
│   ├── install.sh              # 1-liner installer
│   ├── sync_skills.py          # Symlink manager & JIT bootstrapper
│   └── validate_skills.py      # Frontmatter linter & PII scanner
├── docs/                       # Full Documentation Suite
├── .gemini/knowledge/          # Google OKF Knowledge Bundle
└── README.md                   # Monorepo Entrypoint
```

---

## 📜 License & Compliance

Distributed under the **Apache-2.0 License**. All skill definitions are free of hardcoded PII and ready for enterprise collaboration.
