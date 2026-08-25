---
name: catalog
description: Scaffolds and maintains Google Open Knowledge Format (OKF) index bundles and progressive disclosure trees. Auto-invokes when documenting codebase concepts or via `/catalog`.
---
# Google Open Knowledge Format (OKF) Knowledge Catalog Skill

You are now operating under the **Knowledge Catalog** custom skill, specializing in Google's **Open Knowledge Format (OKF)**. Your mandate is to maintain, traverse, and dynamically construct a self-describing, human-readable, and machine-traversable **Knowledge Bundle** under `.gemini/knowledge/` (or the project root) to solve the context-assembly problem for developers and AI agents.

---

## 📂 1. The OKF Bundle Directory Structure

An OKF bundle organizes complex workspace intelligence into modular **Concept Documents**. A standard project-level bundle MUST be structured as follows:

```
.gemini/knowledge/
├── index.md                      # Required. Table of Contents & Progressive Disclosure Index
├── log.md                        # Recommended. Chronological changelog of knowledge updates
├── scout/                        # Environment mapping & system metadata
│   └── codebase_map.md
├── analyst/                      # User decisions, visual preferences, and BDD scenarios
│   └── user_decisions.md
├── architecture/                 # Component designs, DB models, and API endpoints
│   └── data_contracts.md
├── builder/                      # Playbooks, runbooks, and setup documentation
│   └── local_setup_runbook.md
├── sentry/                       # Security threat models, audits, and evidence logs
│   └── secure_threat_model.md
└── mentor/                       # Explanations of design patterns and practices
    └── solid_design_patterns.md
```

---

## 📝 2. OKF Concept Document Specification

Every Concept Document is a standard UTF-8 Markdown file containing:
1.  **YAML Frontmatter Block**: Standardized metadata keys.
2.  **Markdown Body**: Free-form documentation, claims, and links.

### Mandatory & Recommended Frontmatter Fields:
```yaml
---
type: <Type name>                  # REQUIRED. (e.g., "BigQuery Table", "API Endpoint", "Scenario", "Threat Model", "Playbook")
title: <Display name>              # Recommended. Human-readable name. If omitted, derived from filename.
description: <One-line summary>    # Recommended. Short snippet used in index files or search previews.
resource: <Canonical URI>          # Recommended. Unique URI/file URL referencing the actual codebase asset.
tags: [<tag1>, <tag2>, ...]        # Optional. Semantic taxonomy grouping tags.
timestamp: <ISO 8601 datetime>     # Optional. Modification timestamp.
---
# Concept Title
Markdown body text...
```

---

## 🛠️ 3. Deterministic Static Verifier (`verify_okf.py`)

This skill includes a native, machine-verifiable static check script at `scripts/verify_okf.py` to validate concept file structure:

```bash
python3 skills/knowledge-catalog/scripts/verify_okf.py .gemini/knowledge/scout/codebase_map.md
```

The script verifies:
1. YAML frontmatter opening (`---`) and closing markers.
2. Required keys (`type`, `title`).
3. Absence of placeholders (`TBD`, `TODO`, `FIXME`).

---

## ⚡ 4. Selective Context Grounding (On-Demand RAG)

To prevent prompt-token bloat, never ingest entire documentation logs at once. Follow the **[Selective Grounding Specification](file://$HOME/code/github/skills-knowledge-catalog/skills/knowledge-catalog/references/selective_grounding.md)**:
1.  **Read Index**: Check `.gemini/knowledge/index.md` first.
2.  **Filter Concepts**: Identify relevant Concept IDs based on active task goals.
3.  **Hydrate Context**: Run `view_file` only on target documents.

---

## 🚦 5. Guidelines for Prompt Writers & Developers

*   **Zero Placeholders**: Concepts must be fully written out. Do not write "TBD", "To be completed later", or empty files.
*   **VCS Integrity**: Ensure that `.gemini/knowledge/` is committed to git to bind conceptual "why" directly to "how" in code.
*   **Tag & Link Consistency**: Concepts can reference other concepts using standard Markdown links (e.g., `[API Spec](file:///.gemini/knowledge/architecture/api_endpoint.md)`).
