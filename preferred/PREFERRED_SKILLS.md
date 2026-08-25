# 🛠️ Preferred Domain Skills Catalog

This catalog lists curated, specialized engineering skills for on-demand (JIT) project bootstrapping. These skills are **project-scoped**—they are installed directly into your repository when needed rather than cluttering global agent memory.

---

## ⚡ How to Install Project-Scoped Skills

### Method 1: Local Monorepo Sync (Instant Symlinks)
From your project's root directory:
```bash
# Bootstrap 1 or more domain skills into .gemini/skills/ and .agents/skills/
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization
```

### Method 2: Global `npx skills` Registry (Zero Config)
```bash
# Pull directly from community / canonical remotes
npx skills add addyosmani/agent-skills --skill <skill-name>
```

---

## 📦 Curated Domain Skills Directory

### 🎨 Frontend & Design
*   **`frontend-ui-engineering`**
    *   **What it does:** Enforces modern CSS (`:has()`, container queries, subgrid, View Transitions API) and bans obsolete layout hacks.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill frontend-ui-engineering`

### ⚡ Performance & Core Web Vitals
*   **`performance-optimization`**
    *   **What it does:** Enforces LCP/INP performance budgets, identifies memory leaks, and fixes layout thrashing.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills performance-optimization`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill performance-optimization`

### 🔌 Architecture & API Contracts
*   **`api-and-interface-design`**
    *   **What it does:** Designs resilient REST/gRPC interfaces, enforces Hyrum's law guardrails, discriminated unions, and idempotency keys.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills api-and-interface-design`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill api-and-interface-design`

### 🛡️ Security & Hardening
*   **`security-and-hardening`**
    *   **What it does:** Builds threat models, enforces OWASP Top 10 mitigations, remediates CWE vulnerabilities, and secures input boundaries.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills security-and-hardening`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill security-and-hardening`

### 🗄️ Database & Schema Migrations
*   **`deprecation-and-migration`**
    *   **What it does:** Executes Expand/Contract database migrations, non-blocking table alterations, and backward-compatible API deprecations.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills deprecation-and-migration`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill deprecation-and-migration`

### 🧪 Browser & E2E Testing
*   **`browser-testing-with-devtools`**
    *   **What it does:** Drives headless Chrome DevTools for UI testing, traps runtime console errors, and verifies network responses.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills browser-testing-with-devtools`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill browser-testing-with-devtools`

### 📊 Observability & Telemetry
*   **`observability-and-instrumentation`**
    *   **What it does:** Configures structured JSON logging, OpenTelemetry distributed tracing, and RED/USE metrics emission.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills observability-and-instrumentation`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill observability-and-instrumentation`

### 🚀 CI/CD & Automation
*   **`ci-cd-and-automation`**
    *   **What it does:** Scaffolds multi-platform GitHub Actions workflows, automated matrix tests, release tagging, and lint presubmits.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills ci-cd-and-automation`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill ci-cd-and-automation`

### 🐛 Debugging & Diagnostics
*   **`debugging-and-error-recovery`**
    *   **What it does:** Deconstructs stack traces, isolates minimal reproducible examples, and applies defensive error recovery.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills debugging-and-error-recovery`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill debugging-and-error-recovery`

### 🔀 Git Workflow & Versioning
*   **`git-workflow-and-versioning`**
    *   **What it does:** Enforces conventional commits, atomic PRs, semantic versioning, and clean linear Git history.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills git-workflow-and-versioning`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill git-workflow-and-versioning`

### 🧠 Context Engineering
*   **`context-engineering`**
    *   **What it does:** Optimizes token context windows, designs compact system instructions, and manages memory eviction for LLM workflows.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills context-engineering`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill context-engineering`

### ⚖️ Benchmark Harness
*   **`benchmark-harness`**
    *   **What it does:** Runs automated physical verification and Dual Gemini LLM-as-a-Judge scoring across 12 standardized software engineering use cases.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills benchmark-harness`
    *   **Remote:** `npx skills add agent-skill-forge --skill benchmark-harness`
