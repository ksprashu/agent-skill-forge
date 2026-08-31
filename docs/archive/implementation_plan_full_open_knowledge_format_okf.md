# Implementation Plan: Full Open Knowledge Format (OKF) Knowledgebase

Build a comprehensive, deterministic, progressive disclosure knowledge base for the **Agent Skill Forge** monorepo under `.gemini/knowledge/` following the Open Knowledge Format (OKF) specification and `catalog` skill standards.

---

## User Review Required

> [!NOTE]
> All concept files will strictly adhere to the OKF YAML frontmatter schema (`type`, `title`, `description`, `resource`, `tags`), include deterministic clickable file links (`file:///...`), and pass `verify_okf.py` validation with 0 errors and zero PII.

---

## Proposed Knowledgebase Architecture

The knowledgebase will be organized into 5 progressive disclosure domains:

```
.gemini/knowledge/
├── index.md                                 # Master Progressive Disclosure Tree & Concept Lookup Table
├── log.md                                   # Chronological Knowledge Log
│
├── scout/                                   # 🗺️ Codebase Topology & Inventories
│   ├── codebase_map.md                      # Monorepo directory tree, layout & subsystem boundaries
│   └── skill_inventory.md                   # Full taxonomy of 16 core verbs + 12 preferred domain skills
│
├── analyst/                                 # 📊 Design Decisions & Tradeoffs
│   ├── design_decisions.md                  # 2-Tier architecture, token economy, 1-word verbs & laziness
│   └── attribution_matrix.md                # Upstream lineage, creator credits & adaptation models
│
├── architecture/                            # 📐 Contracts, Schemas & Pipelines
│   ├── data_contracts.md                    # SKILL.md YAML frontmatter schema & slash command gating
│   ├── installer_spec.md                    # Symlink orchestrator across 5 agent hubs & JIT bootstrapper
│   ├── docs_compiler_pipeline.md            # Stitch 4-theme HTML documentation compiler architecture
│   └── profile_overlay_spec.md              # 3-Tier personality resolution engine & PII isolation
│
├── builder/                                 # 🔨 Operations, Runbooks & Authoring
│   ├── runbooks.md                          # Developer runbooks for validation, syncing & compilation
│   └── skill_authoring_guide.md             # 3-Level progressive disclosure authoring handbook
│
└── sentry/                                  # 🛡️ Security, Compliance & Quality
    ├── security_and_pii.md                  # Zero-PII sanitization patterns & regex guardrails
    └── oss_compliance_spec.md               # Google Open Source / Apache-2.0 compliance & SPDX headers
```

---

## Detailed File Specifications

### 1. Index & Navigation
#### [MODIFY] [index.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/index.md)
* Comprehensive progressive disclosure tree linking all 12 concept documents.
* Searchable Concept Matrix (`Concept ID`, `Concept Title`, `Type`, `File Path`, `Grounding Scope`).

#### [MODIFY] [log.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/log.md)
* Chronological update history logging genesis and full OKF knowledgebase expansion.

---

### 2. Scout Subsystem
#### [MODIFY] [codebase_map.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/scout/codebase_map.md)
* Valid OKF frontmatter (`type: "Codebase Map"`).
* Full monorepo directory layout, subsystem descriptions, and path references.

#### [NEW] [skill_inventory.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/scout/skill_inventory.md)
* Comprehensive taxonomy of all 16 core universal action verbs (`prompt`, `grill`, `spec`, `plan`, `test`, `verify`, `review`, `unslop`, `docs`, `catalog`, `sync`, `google-oss`, `codelab`, `voice`, `copy-write`, `image-gen`).
* Complete directory of all 12 preferred domain skills in `preferred/`.
* Aliases, execution modes (Autonomous vs. Slash command), and trigger signatures.

---

### 3. Analyst Subsystem
#### [MODIFY] [design_decisions.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/analyst/design_decisions.md)
* Valid OKF frontmatter (`type: "Design Decision"`).
* In-depth rationale: 2-tier architecture (Global vs Project-Scoped JIT), Token context economics, 1-word action verbs, Laziness Protocol ("Subtract before you add"), and Profile-Overlay isolation.

#### [NEW] [attribution_matrix.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/analyst/attribution_matrix.md)
* Upstream lineage and creator attribution (Matt Pocock, Addy Osmani, Anthropic, Cursor, Google OSPO, DeepMind).
* Monorepo consolidation lineage and adaptation models.

---

### 4. Architecture Subsystem
#### [MODIFY] [data_contracts.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/architecture/data_contracts.md)
* Valid OKF frontmatter (`type: "Data Contract"`).
* Formal schema for `SKILL.md` frontmatter (`name`, `description`, `disable-model-invocation`), structural rules, subfolder contracts (`references/`, `scripts/`, `assets/`).

#### [MODIFY] [installer_spec.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/architecture/installer_spec.md)
* Valid OKF frontmatter (`type: "Architecture Spec"`).
* Multi-runtime directory matrix (`~/.agents/skills/`, `~/.gemini/skills/`, `~/.gemini/config/skills/`, `~/.claude/skills/`, `~/.gemini/antigravity-cli/skills/`), symlink resolution, prune/fix algorithms, and JIT workspace bootstrapping.

#### [NEW] [docs_compiler_pipeline.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/architecture/docs_compiler_pipeline.md)
* Documentation compiler architecture (`compile_docs.py`), 4 Stitch themes (`technical`, `obsidian`, `proscript`, `dynamics`), AST markdown regex parsing, single-page bundle emission, responsive CSS rules.

#### [NEW] [profile_overlay_spec.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/architecture/profile_overlay_spec.md)
* 3-tier personality resolution engine (`*.local.md` -> `~/.gemini/personas/default/` -> `*.template.md`) and Zero-PII fallback flow.

---

### 5. Builder Subsystem
#### [MODIFY] [runbooks.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/builder/runbooks.md)
* Valid OKF frontmatter (`type: "Runbook"`).
* Executable developer runbooks for skill validation, symlink synchronization, project bootstrapping, doc compilation, and OKF verification.

#### [NEW] [skill_authoring_guide.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/builder/skill_authoring_guide.md)
* Authoring guide for building new skills: 3-level progressive disclosure hierarchy, markdown formatting rules, token budget limits, and presubmit verification checklist.

---

### 6. Sentry Subsystem
#### [MODIFY] [security_and_pii.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/sentry/security_and_pii.md)
* Valid OKF frontmatter (`type: "Security Policy"`).
* Zero-PII sanitization patterns, dynamic user lookups (`getpass.getuser()`), regex audit tests, gitignore isolation rules.

#### [NEW] [oss_compliance_spec.md](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/sentry/oss_compliance_spec.md)
* Google Open Source / Apache-2.0 licensing rules, SPDX headers, repository cleanliness audits, and copyright notice automation.

---

## Verification Plan

### Automated Static Verification
1. **OKF Schema & Link Verifier**:
   Run `python3 skills/catalog/scripts/verify_okf.py` across all concept files in `.gemini/knowledge/**/*.md`.
2. **Skill Validation & PII Audit**:
   Run `python3 scripts/validate_skills.py` to ensure zero PII leaks and clean frontmatter.
3. **HTML Documentation Compilation**:
   Run `python3 skills/docs/scripts/compile_docs.py --dir ./docs` and `python3 skills/docs/scripts/compile_docs.py --file ./README.md` to ensure all doc portals build cleanly.
