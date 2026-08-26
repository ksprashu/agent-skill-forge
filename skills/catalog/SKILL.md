---
name: catalog
description: Scaffold and index Google OKF progressive disclosure trees for codebase memory.
---

# Catalog: Open Knowledge Format (OKF) Bundle Manager

Maintain and traverse self-describing, progressive disclosure knowledge bundles under `.gemini/knowledge/`.

---

## 🎯 Goal
Preserve long-term architectural decisions, codebase topologies, and runbooks in a structured, searchable knowledge tree.

---

## 📋 Step-by-Step Workflow

1. **Scaffold Bundle Structure**: Create `.gemini/knowledge/` with subdirectories (`scout/`, `analyst/`, `architecture/`, `builder/`, `sentry/`).
2. **Author Concept Documents**: Write focused Markdown docs with YAML frontmatter (`type`, `title`, `description`, `resource`).
3. **Update Progressive Disclosure Index**: Maintain `.gemini/knowledge/index.md` linking to all concept files.
4. **Log Updates**: Record modifications chronologically in `.gemini/knowledge/log.md`.
5. **Validate Integrity**: Run `python3 scripts/verify_okf.py` to ensure valid schemas and clickable links.

---

## 💡 Concrete Example

### Concept Document Fixture (`.gemini/knowledge/architecture/data_contracts.md`)
```markdown
---
type: "Data Contract"
title: "User Profile Schema"
description: "Pydantic and SQLite schema definitions for user records."
resource: "file:///src/models/user.py"
tags: ["database", "schema", "auth"]
---

# User Profile Data Contract

Defines the core `User` model attributes and SQLite table constraints.

## Schema Definition
* `id` (INTEGER PRIMARY KEY)
* `email` (TEXT UNIQUE NOT NULL)
* `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
```

---

## 🚫 Hard Constraints

*   **NEVER** create concept documents without valid YAML frontmatter.
*   **NEVER** omit updating `index.md` when adding new concept files.
*   **NEVER** hardcode private machine paths or credentials in knowledge documents.
