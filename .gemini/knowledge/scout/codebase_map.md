---
type: "Codebase Map"
title: "Agent Skill Forge Repository Topology"
description: "Directory hierarchy, structural layout, and subsystem boundaries of the Agent Skill Forge monorepo."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/README.md"
tags: ["scout", "topology", "monorepo", "skills", "layout"]
---

# 🗺️ Codebase Map & Monorepo Topology

A comprehensive map of the directory hierarchy, subsystem boundaries, and role of each component in **Agent Skill Forge**.

---

## 📂 Repository Directory Layout

```
agent-skill-forge/
├── skills/                     # 🌟 Core Global Universal Skills (16 Action Verbs)
│   ├── prompt/                 # Intent engineering, Socratic grilling, DAG task graphs
│   ├── grill/                  # 1-question Socratic interviews & CONTEXT.md briefs
│   ├── spec/                   # Gated specs & official source documentation grounding
│   ├── plan/                   # Vertical task slicing & dependency DAG execution
│   ├── test/                   # Test-Driven Development & Prove-It bug reproduction
│   ├── verify/                 # EGA static verifiers + 6-persona blinded judge rubrics
│   ├── review/                 # 5-axis code & architecture reviews
│   ├── unslop/                 # Anti-AI bloat, Laziness Protocol, ghost helper deletion
│   ├── docs/                   # Markdown docs suite & 4-theme Stitch HTML compiler
│   ├── catalog/                # Google OKF progressive disclosure bundle builder
│   ├── sync/                   # Symlink manager & on-demand project bootstrapper
│   ├── google-oss/             # Google Open Source compliance & license headers
│   ├── codelab/                # Interactive Google Codelab tutorial generator
│   ├── voice/                  # Linguistic style analyzer & cadence profiler
│   ├── copy-write/             # Writing companion with 3-tier Profile-Overlay
│   └── image-gen/              # Gemini Flash multimodal diagram & image generator
│
├── preferred/                  # 🛠️ Curated Domain Skills (Project-Scoped JIT)
│   ├── catalog.json            # Machine-readable registry (npx commands & GH links)
│   ├── PREFERRED_SKILLS.md     # Developer catalog with 1-click bootstrap commands
│   ├── PREFERRED_SKILLS.html   # Compiled interactive documentation portal
│   ├── frontend-ui-engineering/
│   ├── performance-optimization/
│   ├── api-and-interface-design/
│   ├── security-and-hardening/
│   ├── deprecation-and-migration/
│   ├── browser-testing-with-devtools/
│   ├── observability-and-instrumentation/
│   ├── ci-cd-and-automation/
│   ├── debugging-and-error-recovery/
│   ├── git-workflow-and-versioning/
│   ├── context-engineering/
│   └── benchmark-harness/
│
├── scripts/                    # 🚀 Installer, Verification & Tooling
│   ├── install.sh              # 1-liner bash setup script
│   ├── sync_skills.py          # Symlink manager and JIT bootstrapper
│   └── validate_skills.py      # Frontmatter linter and PII audit
│
├── docs/                       # 📚 Full Documentation Portal Suite
│   ├── architecture.md         # Monorepo architecture & 2-tier design
│   ├── catalog_reference.md    # Skills dictionary & upstream attribution matrix
│   ├── skill_authoring_guide.md# 3-level progressive disclosure handbook
│   ├── user_guide.md           # End-user CLI & agent workflow manual
│   └── *.html                  # Compiled standalone interactive presentation sheets
│
├── .gemini/knowledge/          # 🧠 Open Knowledge Format (OKF) Bundle
│   ├── index.md                # Progressive disclosure index & concept registry
│   ├── log.md                  # Chronological knowledge log
│   ├── scout/                  # Topologies & skill taxonomies
│   ├── analyst/                # Design rationale & attribution
│   ├── architecture/           # Frontmatter contracts, installer specs & pipelines
│   ├── builder/                # Executable runbooks & authoring workflows
│   └── sentry/                 # Zero-PII policies & open-source compliance
│
├── LICENSE                     # Apache 2.0 License
├── CONTRIBUTING.md             # Contribution guidelines
├── CODE_OF_CONDUCT.md          # Contributor code of conduct
├── SECURITY.md                 # Security reporting policy
├── README.md                   # Monorepo landing page
└── README.html                 # Compiled landing page portal
```

---

## 🏛️ Subsystem Responsibilities

1. **Core Global Skills (`skills/`)**:
   - 16 universal action verbs covering the complete engineering and authoring lifecycle.
   - Symlinked globally into agent execution paths (`~/.agents/skills/`, `~/.gemini/config/skills/`, `~/.claude/skills/`).

2. **Preferred Domain Skills (`preferred/`)**:
   - 12 curated, deep-domain skill bundles covering web frontend, performance, distributed databases, security, and CI/CD.
   - Installed project-scoped on demand via `sync_skills.py --project <dir> --skills <names>` or `npx skills add`.

3. **Automation & Tooling (`scripts/`)**:
   - Python and shell automation for atomic symlinking, frontmatter linting, PII audits, and installer bootstrapping.

4. **Documentation & Portals (`docs/`)**:
   - Comprehensive markdown guides compiled into standalone HTML portals with embedded CSS themes and client-side tab switching.

5. **Knowledge Memory (`.gemini/knowledge/`)**:
   - Structured, searchable OKF knowledge base providing progressive disclosure grounding for autonomous agents.
