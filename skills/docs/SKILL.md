---
name: docs
description: Generate full SDLC documentation suites and compile interactive HTML presentations. Trigger via /docs.
disable-model-invocation: true
---

# Docs: SDLC Documentation & HTML Presentation Compiler

Scaffold standard SDLC documentation suites and compile markdown files into interactive, single-file HTML presentations.

---

## 🎯 Goal
Produce structured markdown documentation (PRDs, specs, user guides, architecture docs) and compile them into standalone HTML presentation portals with 4 themes (`technical`, `obsidian`, `proscript`, `dynamics`).

---

## 📋 Step-by-Step Workflow

1. **Scaffold Markdown Docs**: Author documents in `docs/` (`user_guide.md`, `architecture.md`, `prd_feature_doc.md`).
2. **Dual-Link Grounding**: Include both product and official documentation links for all referenced technologies.
3. **Declare Theme in Frontmatter**: Specify `theme: "technical"` (or `obsidian`, `proscript`, `dynamics`).
4. **Compile to HTML**: Run the compiler script:
   ```bash
   python3 scripts/compile_docs.py --dir ./docs
   # Or compile a single file:
   python3 scripts/compile_docs.py --file ./README.md --theme obsidian
   ```
5. **Verify Tag Balance**: Ensure all HTML containers and table layouts are cleanly closed and responsive.

---

## 💡 Concrete Example

### Markdown Frontmatter & Dual-Linking Fixture
```markdown
---
title: "Developer Integration Guide"
theme: "technical"
description: "Step-by-step API integration guide"
---

# Developer Integration Guide

Integrate with [FastAPI](https://fastapi.tiangolo.com) ([Docs](https://fastapi.tiangolo.com/tutorial/)) and deploy to [Google Cloud Run](https://cloud.google.com/run) ([Docs](https://cloud.google.com/run/docs)).

## 📚 References & Further Reading
* [FastAPI Official Docs](https://fastapi.tiangolo.com/)
* [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
```

---

## 🚫 Hard Constraints

*   **NEVER** leave unmatched HTML tags (`<div>` without `</div>`).
*   **NEVER** mention third-party tools/libraries without providing official documentation links.
*   **NEVER** use dark/light themes with unreadable text contrast.
