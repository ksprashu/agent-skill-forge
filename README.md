# 🔨 Agent Skill Forge

A curated, unified monorepo of high-performance skills for **Google Antigravity**, **Claude Code**, **Gemini CLI**, and agentic AI coding assistants.

Built for engineering rigor, token context economy, and zero AI slop.

---

## 🧭 The Four-Gate Spine

Most agent failures are not coding failures. The model built the wrong thing,
or it built the right thing without being asked to think, or it said "done"
without checking, or it produced something technically correct that no human
wanted to read. The spine is twelve skills arranged as four gates against
exactly those four failures.

```
  UNDERSTAND ──► THINK ──► [gate] ──► BUILD ──► VERIFY ──► HUMAN
```

| Gate | Skills | The failure it prevents |
| :--- | :--- | :--- |
| **Understand** | `echo` · `grill` · `done` | Building a confident answer to the wrong question. |
| **Think** | `brainstorm` · `research` · `doubt` | Taking the first idea because it arrived first. |
| **Verify** | `prove` · `bar` · `scope` | Claiming done without evidence that it is. |
| **Human** | `profile` · `land` · `nudge` | Correct output that reads like machine sludge. |

The gate between THINK and BUILD is the only one with teeth. On Claude Code it
is a `PreToolUse` hook that **blocks** edits to product code until a design
artefact is stamped `status: approved`. Docs, tests, and Markdown are never
blocked, so exploration stays free.

```bash
bash scripts/install.sh --spine --hard-gate     # install the spine, enforce the gate
python3 hooks/design_gate.py --status           # is it open, and why
FORGE_GATE=off claude                           # bypass for one session
```

Eleven of the twelve spine skills are **not written here**. They are referenced
from upstream repositories at pinned commit SHAs and fetched at install time —
nothing is vendored, nothing is forked. See
[§ Reference-Only Upstream Skills](#-reference-only-upstream-skills).

### One spine, every harness

Each skill claims a *capability*, not a name. Each harness declares which
capabilities it already covers. The installer subtracts, so a harness never
receives a skill that duplicates something it already ships — and your own
slash commands are detected too.

```bash
python3 scripts/sync_skills.py --list-harnesses
```

| Harness | Installs to | Hooks | Design gate |
| :--- | :--- | :--- | :--- |
| Claude Code | `~/.claude/skills` | ✅ `settings.json` | **Enforced** |
| Antigravity IDE | `~/.gemini/config/skills` | ❌ | Advisory |
| Antigravity CLI | `~/.gemini/antigravity-cli/skills` | ❌ | Advisory |
| Gemini CLI | `~/.gemini/skills` | ❌ | Advisory |
| OpenAI Codex | `~/.codex/skills` | ❌ | Advisory |
| Universal Agent Hub | `~/.agents/skills` | ❌ | Advisory |

Only Claude Code exposes a hook API, so it is the only harness where the design
gate can actually stop an edit. Everywhere else the gate is instruction text in
the `brainstorm` skill — a strong instruction, not an enforced one. If you need
it to hold on those harnesses, use a pre-commit hook or a CI check.

📖 **[docs/harness_capabilities.md](docs/harness_capabilities.md)** — what each
harness ships natively, and how to drive those defaults canonically alongside
the spine.

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

`install.ps1` takes the same flags as `install.sh` — `--spine`, `--clusters`,
`--hard-gate`, `--offline`, `--no-fetch`, `--uninstall` — and runs the same
three steps: fetch the pinned upstream skills, link what each harness lacks,
then optionally install the design-gate hook. Symlinks on Windows need
Developer Mode or an elevated shell; the script warns if you have neither, and
`--copy` installs physical copies instead.

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

# Install the COMPLETE Forge (All 31 Core + Domain skills)
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

The 19 Core Action Skills cover the complete end-to-end engineering lifecycle and are organized into 4 functional clusters:

### 📐 Cluster C1: Planning, Specification & Swarm Execution (`plan-spec`)
*Grounds requirements, gathers intent, conducts Socratic alignment, plans dependency DAGs, and executes autonomous swarms.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`spec`](./skills/spec)** | `/spec` | Autonomous | **Grounded Specifications**: Writes specifications with official documentation citations, interface contracts, and explicit non-goals before coding. Prevents API hallucinations and scope creep. |
| **[`plan`](./skills/plan)** | `/plan` | Autonomous | **Task Slicing & Dependency DAGs**: Slices complex features or refactors into small, vertically testable tasks with verifiable checkpoints. Ensures incremental progress and rollback points. |
| **[`work`](./skills/work)** | `/work` | User Slash | **Autonomous Multi-Agent Swarm Engine**: Coordinates parallel swarms with Sentinel oversight, dispatch-only orchestration, competitive branching tournaments, and adversarial verification. Six scaffold topologies, a DAG whose gates are settled by a script rather than by the agent's own say-so, and a forensic auditor calibrated against a known-fake corpus. |
| **[`grill`](./skills/grill)** | `/grill` | User Slash | **Socratic Requirements Interview**: 1-question Socratic interview with attached technical hypotheses to clarify requirements and tradeoffs until 95% confident. Eliminates hidden assumptions. |
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
*Designs step-by-step developer tutorials, extracts human writing cadence, profiles how you want agents to write back, drafts articles, and synthesizes diagrams.*

| Skill | Triggers | Execution Mode | What It Does & How It Helps |
| :--- | :--- | :--- | :--- |
| **[`codelab`](./skills/codelab)** | `/codelab` | User Slash | **Google Codelab Creator**: 7-phase workflow scaffolding engaging, interactive developer tutorials and workshops formatted for `claat` with automated quality guards. |
| **[`human-voice`](./skills/human-voice)** | `/human-voice` | User Slash | **Persona & Cadence Profiler**: Scans developer conversation logs, scrubs PII, and extracts authentic human writing style markers and typing cadence for personalization. |
| **[`cognitive-profiler`](./skills/cognitive-profiler)** | `/cognitive-profiler`, `/profile-me` | User Slash | **Agent Communication Profiler**: Harvests redacted evidence of how you react to AI output, judges it against a rubric, and compiles a cited profile into `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `.cursorrules`. |
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

## 🔗 Reference-Only Upstream Skills

Eleven of the twelve spine skills are somebody else's work, and they stay that
way. This repository contains **no copy** of them. Only `profile` is written
here. Instead
[`config/upstream.lock.json`](config/upstream.lock.json) pins each one to a
40-character commit SHA, and `scripts/fetch_upstream.py` resolves it at install
time into `.upstream/` (gitignored).

Why reference rather than vendor:

- **No silent drift.** A fork diverges the day after you make it. A SHA pin
  either resolves or fails loudly.
- **Upgrades are reviewable.** `--upgrade` prints a GitHub compare link for
  every skill with a newer commit. You read the diff, then bump the pin.
- **Attribution is structural.** The upstream author's content is never edited.
  Forge-specific glue lives in [`overlays/`](overlays/) and is appended at
  fetch time, below the upstream text and above a provenance block.
- **Tamper-evident.** Every materialised tree is sha256-hashed into
  `.forge-manifest.json`. `--verify` exits non-zero if anything changed.

```bash
python3 scripts/fetch_upstream.py            # resolve all pinned skills
python3 scripts/fetch_upstream.py --verify   # check nothing was tampered with
python3 scripts/fetch_upstream.py --upgrade  # show what moved upstream
python3 scripts/fetch_upstream.py --offline  # install from local cache only
```

| Skill | Gate | Upstream | Licence |
| :--- | :--- | :--- | :--- |
| **`grill`** | understand | [`mattpocock/skills` · productivity/grilling](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) | MIT |
| **`echo`** | understand | [`Shubhamsaboo/awesome-llm-apps` · thinking-out-loud](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/thinking-out-loud) | Apache-2.0 |
| **`done`** | understand | [`affaan-m/ECC` · intent-driven-development](https://github.com/affaan-m/ECC/tree/main/skills/intent-driven-development) | MIT |
| **`brainstorm`** | think | [`obra/superpowers` · brainstorming](https://github.com/obra/superpowers/tree/main/skills/brainstorming) | MIT |
| **`research`** | think | [`mattpocock/skills` · engineering/research](https://github.com/mattpocock/skills/tree/main/skills/engineering/research) | MIT |
| **`doubt`** | think | [`addyosmani/agent-skills` · doubt-driven-development](https://github.com/addyosmani/agent-skills/tree/main/skills/doubt-driven-development) | MIT |
| **`prove`** | verify | [`obra/superpowers` · verification-before-completion](https://github.com/obra/superpowers/tree/main/skills/verification-before-completion) | MIT |
| **`bar`** | verify | [`addyosmani/agent-skills` · constraint-driven-development](https://github.com/addyosmani/agent-skills/tree/main/skills/constraint-driven-development) | MIT |
| **`scope`** | verify | [`Shubhamsaboo/awesome-llm-apps` · scope-creep-detector](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/scope-creep-detector) | Apache-2.0 |
| **`land`** | human | [`Shubhamsaboo/awesome-llm-apps` · first-reader](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/first-reader) | Apache-2.0 |
| **`nudge`** | human | [`anthropics/skills` · discernment-nudge](https://github.com/anthropics/skills/tree/main/skills/discernment-nudge) | Custom — see upstream `LICENSE.txt` |

Thank you to **Matt Pocock**, **Addy Osmani**, **Jesse Vincent (obra)**,
**Affaan Mustafa**, **Shubham Saboo**, and **Anthropic**. The forge is glue
around your work, not a replacement for it.

> `anthropics/skills` ships custom licence terms rather than a standard OSS
> licence. It is fetched at install time onto your machine and is never
> redistributed by this repository. Read the upstream terms before use.

Two caveats, stated plainly:

- **Installing needs the network.** That is inherent to reference-only. Use
  `--offline` once the cache is warm, or `--no-fetch` to skip the spine.
- **Four skills need a responsive human** — `grill`, `echo`, `land`, `nudge`.
  They are excluded from `--non-interactive` installs because an unattended
  agent has nobody to ask. `brainstorm` interviews you too, but it installs
  everywhere on purpose: an autonomous run that hits the design gate with no
  brainstorm skill present gets blocked without being told why.

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
| **`work`** | **Google DeepMind Antigravity Team** | Google Antigravity Teamwork Architecture | Fully open, decoupled multi-agent swarm with Sentinel, Dispatch-Only Orchestrator, Explorers, Competitive Workers, Adversarial Quartet, and Victory Auditor. |
| **`prompt`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/prompt`](https://github.com/ksprashu/agent-skill-forge) | Intent engineering, 6-persona framework, and DAG task graph compiler. |
| **`verify`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/verify`](https://github.com/ksprashu/agent-skill-forge) | Expectation-Grounded Alignment (EGA) with static checks + blinded judge rubrics. |
| **`continuous-alignment`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/continuous-alignment`](https://github.com/ksprashu/agent-skill-forge) | Autonomous alignment, 200-line AGENTS.md budget engine, and living ADR compiler. |
| **`docs`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/docs`](https://github.com/ksprashu/agent-skill-forge) | Full SDLC documentation scaffolding + Stitch 4-theme interactive HTML compiler. |
| **`catalog`** | **Prashanth Subrahmanyam** | [Google Open Knowledge Format (OKF)](https://github.com/ksprashu/agent-skill-forge) | Codebase memory and progressive disclosure index tree specification. |
| **`sync`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/sync`](https://github.com/ksprashu/agent-skill-forge) | Multi-runtime symlink synchronizer and JIT workspace bootstrapper. |
| **`google-oss`** | **Google Open Source Programs Office (OSPO)** | [Google Open Source Docs](https://opensource.google/documentation) | Apache-2.0 compliance, header automation, and repository sanitization. |
| **`codelab`** | **Google Developer Relations** | [Google Codelabs](https://codelabs.developers.google.com/) | Interactive step-by-step developer tutorial authoring and quality validation. |
| **`human-voice`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/human-voice`](https://github.com/ksprashu/agent-skill-forge) | PII-sanitized linguistic style and typing cadence extraction. |
| **`cognitive-profiler`** | **Prashanth Subrahmanyam** | [`agent-skill-forge/skills/cognitive-profiler`](https://github.com/ksprashu/agent-skill-forge) | Evidence-cited agent communication preferences compiled to per-harness config files. |
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

## ✅ How This Repo Checks Itself

A skill that tells an agent to verify its work is a suggestion. A script that
exits non-zero is a fact. Everything in this section is the second kind, and
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs all of it on every
pull request — so the checks that used to be skipped are the ones that now
block.

| Command | What it settles |
| :--- | :--- |
| `python3 -m pytest -q` | 624 tests across `skills/`, `tests/` and `tests/e2e/` |
| `python3 scripts/validate_skills.py` | Frontmatter, reserved-namespace collisions, author PII, absolute host paths |
| `python3 scripts/check_stdlib_only.py` | No third-party import reaches a script that runs inside a harness |
| `python3 skills/work/scripts/gate_executor.py list` | Every gate a topology can emit has a predicate behind it |
| `python3 skills/work/scripts/dag_validator.py --check-mermaid <dag>` | The table and the rendered diagram agree |
| `python3 skills/work/scripts/forensic_audit.py --target-dir . --strict` | Stubs, tautological assertions, and mocked "passes" |
| `python3 skills/work/scripts/autowire.py --check` | Every skill the autowiring matrix names exists on disk |

Two rules hold throughout, and they are the reason the above is short:

**Scripts collect evidence; models make judgements.** A script counts, quotes,
measures, and executes. It never scores, bands, or concludes. `arbiter_eval.py`
emits per-candidate evidence and the model picks a winner — because a script
that awards 95/100 to the worse implementation is confidently wrong in a format
that looks authoritative.

**Gates fail closed.** A gate is `mechanical` (a script settles it now),
`attested` (a judgement, where the script validates only the *form* of the
attestation), or `trivial`. An unknown gate name is an error, not a pass.

`skills/work/fixtures/known_fake` is a corpus of deliberately fake code and
`known_good` is its honest twin. CI asserts the auditor rejects the first and
accepts the second. It is the test that the tests work.

📖 **[docs/ENGINEERING_STANDARD.md](docs/ENGINEERING_STANDARD.md)** — the
enforcement ladder, the evidence/judgement split, and the recipe for adding a
gate without adding theatre.

---

## 📁 Monorepo Structure

```
agent-skill-forge/
├── skills/                     # Core Universal Global Action Verbs
├── preferred/                  # 12 Curated Domain-Specific Skills (JIT)
│   ├── catalog.json            # Machine-readable registry
│   └── PREFERRED_SKILLS.md     # Quick bootstrap guide
├── config/
│   ├── harnesses.json          # Harness capability matrix — drives subtraction
│   └── upstream.lock.json      # SHA-pinned reference-only skills
├── overlays/                   # Forge glue appended to upstream skills at fetch
├── hooks/
│   └── design_gate.py          # PreToolUse hard gate (Claude Code)
├── .upstream/                  # Fetched upstream skills (gitignored)
├── scripts/                    # Installer & Verification Scripts
│   ├── install.sh              # 1-liner installer
│   ├── fetch_upstream.py       # Pinned upstream resolver / verifier / upgrader
│   ├── sync_skills.py          # Symlink manager & JIT bootstrapper
│   ├── validate_skills.py      # Frontmatter linter & PII scanner
│   └── check_stdlib_only.py    # Engine scripts must run on a bare interpreter
├── skills/work/                # The parallel-subagent engine
│   ├── scripts/                # scaffold · dag_validator · gate_executor
│   │                           # forensic_audit · arbiter_eval · autowire
│   ├── fixtures/               # known_good / known_fake auditor calibration
│   └── tests/                  # Engine suite (pytest)
├── tests/                      # Repo-level suites (PII, host paths, installer)
├── pytest.ini                  # Test discovery across both trees
├── .github/workflows/ci.yml    # The only L4: what blocks a merge
├── docs/                       # Full Documentation Suite & Stitch Portals
│   ├── ENGINEERING_STANDARD.md # How verification is built here, and why
│   ├── harness_capabilities.md # Native skills per harness + canonical usage
│   └── skill_authoring_guide.md# Official Skill Authoring Guide
├── .gemini/knowledge/          # Google OKF Knowledge Bundle
└── README.md                   # Monorepo Entrypoint & Attribution Matrix
```

---

## 📜 License & Compliance

Distributed under the **Apache-2.0 License**. All skill definitions are free of hardcoded PII and ready for enterprise collaboration.
