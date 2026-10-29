# 🛠️ Preferred Domain Skills Catalog

This catalog lists curated, specialized engineering skills for on-demand (JIT) project bootstrapping. These skills are **project-scoped**—they are installed directly into your repository when needed rather than cluttering global agent memory.

**Where they come from.** Every skill below except `agent-security-posture` is [`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills) (MIT, by Addy Osmani). None of them is vendored here. Each is pinned to a commit SHA in [`config/upstream.lock.json`](../config/upstream.lock.json) and fetched into `.upstream/<name>/` by `scripts/fetch_upstream.py`, which `install.sh` runs first. If the fetch has not run, the installers report those names as `[NOT FETCHED]` and skip them. `agent-security-posture` is the one local skill in `preferred/`.

---

## ⚡ How to Install Project-Scoped or Global Domain Skills

### Method 1: Cluster-Based Bootstrap (Recommended)
You can bootstrap entire clusters or individual skills into your project workspace:
```bash
# Bootstrap an entire cluster into .gemini/skills/ and .agents/skills/
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --clusters d1

# Bootstrap multiple clusters (e.g. Full-Stack + Security)
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --clusters d1,d2

# Bootstrap specific comma-separated skills
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,agent-security-posture
```

If you run `sync_skills.py` directly rather than through `install.sh`, fetch the pinned upstream skills first:
```bash
python3 ~/code/github/agent-skill-forge/scripts/fetch_upstream.py
```

### Method 2: Global Tool Installation
To install domain clusters globally across all AI tools:
```bash
# Install specific domain cluster globally
bash ~/code/github/agent-skill-forge/scripts/install.sh --clusters d1

# Or launch the interactive installer
bash ~/code/github/agent-skill-forge/scripts/install.sh
```

### Method 3: Global `npx skills` Registry (Zero Config)
```bash
# Pull directly from community / canonical remotes
npx skills add addyosmani/agent-skills --skill <skill-name>
```

---

## 📦 Curated Domain Skills Directory by Cluster

### 🌐 Cluster D1: Full-Stack & Quality (`fullstack`)
*Bootstrap cluster:* `python3 scripts/sync_skills.py --project . --clusters d1`

*   **`frontend-ui-engineering`**
    *   **What it does:** Enforces modern CSS (`:has()`, container queries, subgrid, View Transitions API) and bans obsolete layout hacks.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill frontend-ui-engineering`
*   **`performance-optimization`**
    *   **What it does:** Enforces LCP/INP performance budgets, identifies memory leaks, and fixes layout thrashing.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills performance-optimization`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill performance-optimization`
*   **`browser-testing-with-devtools`**
    *   **What it does:** Drives headless Chrome DevTools for UI testing, traps runtime console errors, and verifies network responses.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills browser-testing-with-devtools`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill browser-testing-with-devtools`
*   **`api-and-interface-design`**
    *   **What it does:** Designs resilient REST/gRPC interfaces, enforces Hyrum's law guardrails, discriminated unions, and idempotency keys.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills api-and-interface-design`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill api-and-interface-design`

---

### 🛡️ Cluster D2: Security, Diagnostics & Reliability (`security`)
*Bootstrap cluster:* `python3 scripts/sync_skills.py --project . --clusters d2`

*   **`agent-security-posture`**
    *   **What it does:** Scoped security posture for coding agents: authority rules for untrusted content, OSV/NVD dependency checks with a tested helper, secret handling, finding verdicts and severity, and a read-only infrastructure audit mode. Runs when code, dependencies or agent tools change, or on request.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills agent-security-posture`
    *   **Remote:** `npx skills add ksprashu/agent-skill-forge --skill agent-security-posture` (local preferred skill, not upstream)
*   **`debugging-and-error-recovery`**
    *   **What it does:** Deconstructs stack traces, isolates minimal reproducible examples, and applies defensive error recovery.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills debugging-and-error-recovery`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill debugging-and-error-recovery`
*   **`observability-and-instrumentation`**
    *   **What it does:** Configures structured JSON logging, OpenTelemetry distributed tracing, and RED/USE metrics emission.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills observability-and-instrumentation`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill observability-and-instrumentation`

---

### 🚀 Cluster D3: DevOps & Workflows (`devops`)
*Bootstrap cluster:* `python3 scripts/sync_skills.py --project . --clusters d3`

*   **`ci-cd-and-automation`**
    *   **What it does:** Scaffolds multi-platform GitHub Actions workflows, automated matrix tests, release tagging, and lint presubmits.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills ci-cd-and-automation`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill ci-cd-and-automation`
*   **`git-workflow-and-versioning`**
    *   **What it does:** Enforces conventional commits, atomic PRs, semantic versioning, and clean linear Git history.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills git-workflow-and-versioning`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill git-workflow-and-versioning`
*   **`deprecation-and-migration`**
    *   **What it does:** Executes Expand/Contract database migrations, non-blocking table alterations, and backward-compatible API deprecations.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills deprecation-and-migration`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill deprecation-and-migration`

---

### 🧠 Cluster D4: AI & Context (`ai`)
*Bootstrap cluster:* `python3 scripts/sync_skills.py --project . --clusters d4`

*   **`context-engineering`**
    *   **What it does:** Optimizes token context windows, designs compact system instructions, and manages memory eviction for LLM workflows.
    *   **Install:** `python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills context-engineering`
    *   **Remote:** `npx skills add addyosmani/agent-skills --skill context-engineering`
