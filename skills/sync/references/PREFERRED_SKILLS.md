# Curated Preferred Skills Catalog

This document serves as the **Single Source of Truth** for preferred agent skills. During the **Scout** and **Analyst** stages of prompt rewriting or during task kickoff, agents consult this catalog, evaluate requirements, and select the optimal global or project-scoped skill bundle.

---

## 🧭 Architecture Principle: Prompt-Writer as a Pure Meta-Orchestrator

> [!IMPORTANT]
> **Zero Practice Redefinition**: `prompt` is a **Meta-Orchestrator**, not a domain practitioner. It does NOT redefine how specifications, testing, security, or documentation should be written. Instead, it systematically **composes, delegates to, and weaves** the authoritative global skills into the generated prompt deck:
> - **Socratic Grilling & Q&A** ➔ Delegated to [`grill`](file:///Users/ksprashanth/code/github/agent-skills/skills/grill)
> - **Specification & Source Grounding** ➔ Delegated to [`spec`](file:///Users/ksprashanth/code/github/agent-skills/skills/spec)
> - **Task Decomposition & Dependency DAGs** ➔ Delegated to [`plan`](file:///Users/ksprashanth/code/github/agent-skills/skills/plan)
> - **TDD & Prove-It Verification** ➔ Delegated to [`test`](file:///Users/ksprashanth/code/github/agent-skills/skills/test)
> - **EGA Dual-Verification & Blinded 6-Persona Rubrics** ➔ Delegated to [`verify`](file:///Users/ksprashanth/code/github/skills-expectation-harness/skills/expectation-harness)
> - **Code Review & Fowler Smells** ➔ Delegated to [`review`](file:///Users/ksprashanth/code/github/agent-skills/skills/review)
> - **Anti-AI Bloat & Code Simplification** ➔ Delegated to [`unslop`](file:///Users/ksprashanth/code/github/agent-skills/skills/unslop)
> - **Knowledge Bundles & OKF Indexing** ➔ Delegated to [`catalog`](file:///Users/ksprashanth/code/github/skills-knowledge-catalog/skills/knowledge-catalog)
> - **Documentation & Stitch 4-Theme HTML** ➔ Delegated to [`docs`](file:///Users/ksprashanth/code/github/skills-documentation/skills/documentation)
> - **Canonical Symlink & JIT Bootstrapper** ➔ Delegated to [`sync`](file:///Users/ksprashanth/code/github/agent-skill-sync/skills/skill-sync)
> - **Google Open Source Compliance** ➔ Delegated to [`google-oss`](file:///Users/ksprashanth/code/github/gcx-make-google-oss/skills/make-google-oss)
> - **Codelab Scaffolding & Validation** ➔ Delegated to [`codelab`](file:///Users/ksprashanth/code/github/skills-codelab-creator/skills/codelab-creator)
> - **Linguistic Voice & Persona Profiling** ➔ Delegated to [`voice`](file:///Users/ksprashanth/code/github/skills-extract-human-voice/skills/extract-human-voice)
> - **Writing Companion & Profile-Overlay** ➔ Delegated to [`copy-write`](file:///Users/ksprashanth/code/github/copy-write-bara)
> - **Multimodal Infographic & Diagram Gen** ➔ Delegated to [`image-gen`](file:///Users/ksprashanth/code/github/skills-image-gen-expert/skills/image-gen-expert)

---

## 🌟 1. Core Global Lifecycle Skills (15 Always Active)

These 15 primary verbs are active globally across Antigravity IDE, Antigravity CLI, Gemini CLI, and Claude Code:

| Primary Slug | Primary Slash Verb | Invocation Mode | Role & Capabilities |
| :--- | :--- | :--- | :--- |
| **`prompt`** | `/prompt` | User-only (`disable-model-invocation: true`) | Meta-task intent engineering & task DAG graph topology |
| **`grill`** | `/grill` | User-only (`disable-model-invocation: true`) | Socratic 1-question Q&A, hypothesis testing, 95% confidence stop test |
| **`spec`** | `/spec` | Autonomous / Model-invoked | Gated specifications, non-goals, and official source grounding |
| **`plan`** | `/plan` | Autonomous / Model-invoked | Vertical task slicing, dependency DAGs, checkpointing |
| **`test`** | `/test` | Autonomous / Model-invoked | TDD, Prove-It bug reproduction loops, test-first assertions |
| **`verify`** | `/verify` | Autonomous / Model-invoked | EGA static verifier + 6-persona blinded judge + doubt disproof |
| **`review`** | `/review` | Autonomous / Model-invoked | 5-axis code review (correctness, readability, architecture, security, perf) |
| **`unslop`** | `/unslop` | Autonomous / Model-invoked | Anti-AI bloat, deletes ghost wrappers/helpers, Laziness Protocol |
| **`docs`** | `/docs` | User-only (`disable-model-invocation: true`) | Full SDLC doc suite + 4 Stitch themes HTML presentation compiler |
| **`catalog`** | `/catalog` | Autonomous / Model-invoked | Google Open Knowledge Format (OKF) bundle scaffolding & retrieval |
| **`sync`** | `/sync` | User-only (`disable-model-invocation: true`) | Canonical symlink manager & JIT project-scoped bootstrapper |
| **`google-oss`**| `/google-oss` | User-only (`disable-model-invocation: true`) | Google OSS compliance, license sweep, header checks, repo sanitization |
| **`codelab`** | `/codelab` | User-only (`disable-model-invocation: true`) | Google Codelab scaffolding, polyglot blocks, readability validation |
| **`voice`** | `/voice` | User-only (`disable-model-invocation: true`) | Linguistic style markers, conversational pacing, and anti-slop guidelines |
| **`copy-write`**| `/copy-write` | User-only (`disable-model-invocation: true`) | Writing companion with 3-tier Profile-Overlay voice personalization |
| **`image-gen`** | `/image-gen` | User-only (`disable-model-invocation: true`) | Multimodal diagram and blog asset generator via Gemini Flash Image |

---

## 🛠️ 2. Curated Project-Scoped Domain Skills (JIT Bootstrapped)

Bootstrap domain-specific skills into an active project workspace using:
```bash
python3 ~/code/github/agent-skill-sync/skills/skill-sync/scripts/sync_skills.py \
  --project <workspace_dir> \
  --skills <skill_names>
```

### Curated Domain Skills Directory:
1. **Frontend & UI Engineering** (`frontend-ui-engineering`): Modern CSS, `:has()`, Container Queries, View Transitions, anti-AI component design.
2. **Performance Optimization** (`performance-optimization`): Core Web Vitals (CWV), LCP/INP budgets, memory leak detection, "Neutral is a revert".
3. **API & Interface Design** (`api-and-interface-design`): Hyrum's law, discriminated unions, idempotent routes, backward compatibility.
4. **Security & Hardening** (`security-and-hardening`): Trust boundary mapping, OWASP Top 10, CWE mitigations, secret scanning.
5. **Database Deprecation & Migration** (`deprecation-and-migration`): Expand/Contract schema evolution, non-blocking index additions, AlloyDB/PostgreSQL migrations.
6. **Browser DevTools Testing** (`browser-testing-with-devtools`): Headless Chrome debugging, console log captures, network payload inspection.
7. **Observability & Instrumentation** (`observability-and-instrumentation`): Structured JSON logging, OpenTelemetry tracing, Prometheus metrics.
8. **CI/CD Automation** (`ci-cd-and-automation`): GitHub Actions workflows, matrix testing, branch protections.
