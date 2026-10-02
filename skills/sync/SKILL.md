---
name: sync
description: Synchronize global agent skill symlinks and bootstrap project-scoped skills on demand. Trigger via /sync.
disable-model-invocation: true
---

# Sync: Skill Symlink & JIT Project Bootstrapper

Manage symlinks across global agent directories and bootstrap project-scoped domain skills on demand.

---

## 🎯 Goal
Maintain unified skill access across Antigravity, Claude Code, and Gemini CLI without duplicating files.

---

## 📋 Step-by-Step Workflow

1. **Audit Global Symlinks**: Run the audit script to check for broken or missing links:
   ```bash
   python3 scripts/sync_skills.py
   ```
2. **Repair & Synchronize**: Fix broken paths and prune obsolete links:
   ```bash
   python3 scripts/sync_skills.py --prune --fix
   ```
3. **Bootstrap Project-Scoped Skills (JIT)**:
   ```bash
   python3 scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization
   ```

---

## 💡 Concrete Example

### Bootstrapping Command Output
Without `--fix` the command is a dry run and writes nothing:
```bash
$ python3 scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization
📦 Bootstrapping skills into project: .
  [WOULD BOOTSTRAP] frontend-ui-engineering (preferred) -> ./.gemini/skills/frontend-ui-engineering  (dry run; re-run with --fix to create it)
  [WOULD BOOTSTRAP] performance-optimization (preferred) -> ./.gemini/skills/performance-optimization  (dry run; re-run with --fix to create it)
```

Add `--fix` to actually create the entries:
```bash
$ python3 scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization --fix
📦 Bootstrapping skills into project: .
  [BOOTSTRAP] frontend-ui-engineering (preferred) -> ./.gemini/skills/frontend-ui-engineering
    -> Created entry to /path/to/agent-skill-forge/preferred/frontend-ui-engineering
  [BOOTSTRAP] performance-optimization (preferred) -> ./.gemini/skills/performance-optimization
    -> Created entry to /path/to/agent-skill-forge/preferred/performance-optimization
```

---

## 🚫 Hard Constraints

*   **NEVER** install heavy domain-specific skills into global agent directories.
*   **NEVER** create hard copies when symlinks can be used.
