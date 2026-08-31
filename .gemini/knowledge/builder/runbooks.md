---
type: "Runbook"
title: "Agent Skill Forge Developer Runbooks"
description: "Step-by-step developer operations for skill validation, symlink synchronization, documentation compilation, and OKF verification."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/docs/user_guide.md"
tags: ["builder", "runbooks", "operations", "cli", "workflow"]
---

# 🔨 Developer Runbooks & Operational Commands

Standard operational workflows and CLI commands for maintaining and testing **Agent Skill Forge**.

---

## 🏃 Runbook 1: Skill Validation & Security Linter

Run the automated linter to verify that all skills contain valid frontmatter and zero PII leaks:

```bash
python3 scripts/validate_skills.py
```

### Expected Output:
- Scans `skills/` (16 core) and `preferred/` (12 preferred).
- Confirms zero PII leaks and clean frontmatter syntax.
- Returns exit code 0.

---

## 🔗 Runbook 2: Synchronize Global Agent Symlinks

Link all 16 core universal action verbs into your global agent environments (`.agents/skills`, `.gemini/skills`, `.gemini/config/skills`, `.claude/skills`):

```bash
# Preview status and active symlinks
python3 scripts/sync_skills.py

# Automatically fix broken links and prune orphaned symlinks
python3 scripts/sync_skills.py --fix --prune
```

---

## 📦 Runbook 3: Project-Scoped JIT Bootstrapping

Inject domain-specific skills directly into a project repository without polluting global agent memory:

```bash
# Bootstrap specific domain skills into current directory
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization
```

---

## 📑 Runbook 4: Compiling Interactive Documentation Portals

Compile markdown documentation suites into standalone, 4-theme interactive HTML presentation sheets:

```bash
# Compile all documentation files in docs/
python3 skills/docs/scripts/compile_docs.py --dir ./docs

# Compile a single file (e.g., README.md)
python3 skills/docs/scripts/compile_docs.py --file ./README.md
```

---

## 🧠 Runbook 5: Validating Open Knowledge Format (OKF) Bundles

Verify that knowledge concept documents adhere to OKF YAML frontmatter schemas and contain valid markdown formatting:

```bash
# Verify a single concept document
python3 skills/catalog/scripts/verify_okf.py .gemini/knowledge/scout/codebase_map.md

# Verify all concept documents in the bundle
for f in .gemini/knowledge/**/*.md; do
    python3 skills/catalog/scripts/verify_okf.py "$f"
done
```
