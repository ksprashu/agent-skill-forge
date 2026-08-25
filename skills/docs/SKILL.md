---
name: docs
description: Full SDLC documentation scaffolding and interactive 4-theme Stitch HTML compiler. Trigger via `/docs`, `/documentation`, or `/compile-docs` to scaffold project documentation or compile markdown into styled HTML presentations.
disable-model-invocation: true
---
# Unified Documentation & HTML Presentation Compiler

This skill provides a complete, unified documentation and reporting system for software projects. It acts as:
1. **A Visual-First Interactive Portal Builder**: Compiles project Markdown files with 4 premium Stitch themes (`technical`, `obsidian`, `proscript`, `dynamics`).
2. **An All-Inclusive Full SDLC Documentation Suite**: Covers internal structural engineering, external public guides, security threat models, ADRs, and operational playbooks.
3. **An HTML Report Scaffolder & Sanitizer**: Scaffolds zero-markdown, high-fidelity visual HTML review reports with Outfit/Inter typography, dark/light mode toggles, and responsive first-column `nowrap` tables. Automatically sweeps HTML reports to balance container closures (`</div>`) and verify responsive CSS.

---

## 1. All-Inclusive Full SDLC Document Suite

Every software project maintains a standardized set of Markdown documents under `docs/`. **Core Mandate**: All document types MUST strictly adhere to the **Reference Grounding Protocol**:
- **Inline Product Dual-Linking**: Any product, SDK, API, tool, or framework mentioned across PRDs, Specs, Architecture docs, or User Guides MUST include dual markdown links to both its **Product Landing Page** and its **Official Documentation Landing Page** (e.g., `[Google Cloud Run](https://cloud.google.com/run) ([Docs](https://cloud.google.com/run/docs))`).
- **Knowledge Catalog Synchronization**: All reference URLs, citations, and OKF concept dependencies MUST be harvested and cross-referenced with `knowledge-catalog` bundles (`.gemini/knowledge/index.md`).
- **Mandatory "References & Further Reading" Section**: Every document type listed below MUST conclude with a dedicated `## 📚 References & Further Reading` section listing official product pages, doc portals, deep-dive articles, and video walkthroughs.

### Tier 1: Strategic & Product (External & Executive)
| Document Name | Path (Markdown) | Path (HTML) | Scope & Purpose |
| :--- | :--- | :--- | :--- |
| **Product Requirements (PRD)** | `docs/prd_feature_doc.md` | `docs/prd_feature_doc.html` | High-level vision, target personas, product dual-links, and narrative milestones |
| **Master Roadmap & Feature Tree**| `docs/master_roadmap.md` | `docs/master_roadmap.html`| Consolidated timeline with interactive SVG branching trees and milestone references |
| **Release Notes & Public Changelog**| `docs/changelog.md` | `docs/changelog.html`| User-facing features, API deprecations, breaking change notices, and version tags |

### Tier 2: Technical Architecture & Security (Internal Structural)
| Document Name | Path (Markdown) | Path (HTML) | Scope & Purpose |
| :--- | :--- | :--- | :--- |
| **Specifications Blueprint** | `docs/specifications.md` | `docs/specifications.html` | UX/UI constraints, layout coordinates, performance SLAs, and primary spec links |
| **Architecture & Network Flows** | `docs/architecture.md` | `docs/architecture.html` | Flowcharts, network calls, data-relay channels, and protocol RFC links |
| **Architectural Decision Records** | `docs/adr/ADR-001.md` | `docs/adr/ADR-001.html` | Significant architectural choices, trade-off evaluations, rationale, and consequences |
| **Security Threat Model & Audit** | `docs/threat_model.md` | `docs/threat_model.html` | Trust boundaries, CWE mitigations, scanner findings, and evidence audit trails |
| **API & Database Schema Ref** | `docs/api_reference.md` | `docs/api_reference.html` | OpenAPI/GraphQL contracts, database ER diagrams, and migration runbooks |

### Tier 3: Operations, Delivery & Support (Internal & External Operations)
| Document Name | Path (Markdown) | Path (HTML) | Scope & Purpose |
| :--- | :--- | :--- | :--- |
| **User & Integration Guide** | `docs/user_guide.md` | `docs/user_guide.html` | Setup instructions, CLI commands, troubleshooting, and doc landing page links |
| **Operations & Incident Playbook**| `docs/operations_playbook.md`| `docs/operations_playbook.html`| Health check endpoints, deployment steps, on-call runbooks, and rollback procedures |
| **Developer Onboarding Guide** | `docs/developer_onboarding.md`| `docs/developer_onboarding.html`| Local setup prerequisites, test suite invocation commands, and PR guidelines |
| **Walkthrough & Dual Gate Audit** | `docs/walkthrough.md` | `docs/walkthrough.html` | Verification test cases, screenshots, audit reports, and test harness references |

---

## 2. Dynamic Visual Themes & HTML Compilation

### Visual Presentation Themes
Markdown documents declare their visual style via YAML frontmatter (`theme`):

```yaml
---
title: "Developer Integration Guide"
theme: "technical" # Options: technical | obsidian | proscript | dynamics
description: "Comprehensive step-by-step setup guides"
---
```

1. **`technical`** (Light Mode): Crisp white (`#fbf8ff`), institutional blue (`#1A237E`), cyan (`#00E5FF`), Inter + JetBrains Mono fonts.
2. **`obsidian`** (Dark Mode): Obsidian violet canvas (`#070512`), neon-cyan (`#00f0ff`), pink gradients, glassmorphism (`backdrop-filter: blur(32px)`).
3. **`proscript`** (Enterprise Light): Clean paper surface (`#f8f9fc`), authoritative blue (`#0f1c3f`), 12-column corporate grid.
4. **`dynamics`** (Telemetry Dark): Charcoal canvas (`#0f0f10`), navy containers, status green (`#2aff2d`).

---

## 3. Compilation Commands

### Single File Compilation:
```bash
python3 ~/code/github/skills-documentation/skills/documentation/scripts/compile_docs.py --file docs/user_guide.md
```

### Full Workspace Compilation:
```bash
python3 ~/code/github/skills-documentation/skills/documentation/scripts/compile_docs.py
```
