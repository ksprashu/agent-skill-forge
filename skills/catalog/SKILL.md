---
name: catalog
description: Scaffold and index Google OKF progressive disclosure trees for codebase and architectural memory. Trigger via /catalog.
---

# Catalog: Open Knowledge Format (OKF) Bundle Manager

Maintain and traverse self-describing, progressive disclosure knowledge bundles under `.gemini/knowledge/` (or `.agents/knowledge/`, `.claude/knowledge/`).

---

## 🎯 Goal
Preserve long-term architectural decisions, codebase topologies, and runbooks in a structured, searchable knowledge tree with bidirectional link integrity and AST drift detection.

---

## 📋 Step-by-Step Workflow

1. **Scaffold Bundle Structure**: Establish knowledge directory hierarchy (`scout/`, `analyst/`, `architecture/`, `builder/`, `sentry/`).
2. **Author Concept Documents**: Write focused Markdown docs with OKF v0.2 YAML frontmatter (`type`, `title`, `description`, `resource`, `resource_hash`). Use `scaffold_okf.py` to bootstrap concepts directly from source AST.
3. **Update Progressive Disclosure Index**: Maintain `index.md` linking to all concept files via clean workspace-relative paths.
4. **Log Updates**: Record modifications chronologically in `log.md`.
5. **Validate Integrity**:
   - Single concept file: `python3.12 skills/catalog/scripts/verify_okf.py <file>`
   - Full bundle bidirectional audit: `python3.12 skills/catalog/scripts/verify_okf.py --all`
   - Custom bundle directory: `python3.12 skills/catalog/scripts/verify_okf.py --dir <path>`
   - Code drift detection: `python3.12 skills/catalog/scripts/scaffold_okf.py --check-drift`

---

## 📦 OKF v0.2 Specification

### Frontmatter Schema
| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `type` | string | **Required** | Concept categorization (e.g. `Architecture Spec`, `Data Contract`, `Runbook`) |
| `title` | string | **Required** | High-signal human-readable title |
| `description` | string | **Required** | Concise summary of grounding scope |
| `resource` | string | Optional | Relative path or URI to grounded implementation source file |
| `resource_hash` | string | Optional (v0.2) | SHA-256 fingerprint (`sha256:<hex>`) for code drift tracking |
| `sources` | list[str] | Optional (v0.2) | Upstream authoritative citations and URLs |
| `verified` | string | Optional (v0.2) | Verification timestamp (ISO-8601) or certification ID |
| `stale_after` | string | Optional (v0.2) | Staleness boundary date (`YYYY-MM-DD`) triggering re-audit |
| `status` | string | Optional (v0.2) | Lifecycle status: `draft`, `active`, or `deprecated` |
| `tags` | list[str] | Optional | Topic tags for fast search indexing |

### Concept Document Fixture (`.gemini/knowledge/architecture/data_contracts.md`)
```markdown
---
type: "Data Contract"
title: "User Profile Schema"
description: "Pydantic and SQLite schema definitions for user records."
resource: "src/models/user.py"
resource_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
sources:
  - "https://docs.pydantic.dev/latest/"
verified: "2026-09-20T12:00:00Z"
stale_after: "2026-12-31"
status: "active"
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

*   **NEVER** create concept documents without required frontmatter (`type`, `title`, `description`).
*   **NEVER** allow orphaned concept files; every `.md` file must be indexed in `index.md`.
*   **NEVER** allow dead links in `index.md`; every link must resolve to an existing concept document on disk.
*   **NEVER** hardcode private machine paths (`file:///Users/...`) or credentials; use workspace-relative paths.
*   **NEVER** leave unresolved placeholders (`TBD`, `TODO`, `FIXME`, `as an AI`).
