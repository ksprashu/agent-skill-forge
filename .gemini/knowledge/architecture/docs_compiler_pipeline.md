---
type: "Pipeline Architecture"
title: "Stitch 4-Theme Documentation Compiler Pipeline"
description: "Architectural design of the single-page HTML documentation compiler, AST markdown transformations, and responsive CSS styling."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/skills/docs/scripts/compile_docs.py"
tags: ["architecture", "docs", "compiler", "stitch", "html", "theming"]
---

# 📑 Stitch Documentation Compiler Pipeline

Architecture and design specification for the documentation compiler in `skills/docs/scripts/compile_docs.py`.

---

## 1. Compiler Architecture Overview

The Stitch documentation compiler transforms standard markdown files into interactive, self-contained single-page HTML presentation portals with zero external runtime JavaScript or CSS dependencies.

```
Markdown Source (*.md)
  ├── 1. Frontmatter Extractor (Extracts title, theme, description)
  ├── 2. AST Markdown Transformer (Headers, Code blocks, Alert banners, Tables)
  ├── 3. Theme Engine (Injects 1 of 4 embedded CSS variable themes)
  ├── 4. Navigation & Table of Contents Generator (Sidebar links & anchor tags)
  └── 5. HTML Packager (Emits standalone *.html file)
```

---

## 2. 4 Embedded Theme Configurations

The compiler provides 4 built-in aesthetic themes configurable via markdown YAML frontmatter (`theme: <theme-name>`):

| Theme Key | Visual Style | Typography & Palette | Best Suited For |
| :--- | :--- | :--- | :--- |
| **`technical`** | Clean, high-contrast light theme | Inter, JetBrains Mono, Deep Navy accents (`#1e40af`) | API contracts, system specs, runbooks. |
| **`obsidian`** | Modern dark mode | Outfit, Fira Code, Indigo/Cyan accents (`#6366f1`) | Developer tools, terminal guides, night reading. |
| **`proscript`** | Editorial serif aesthetic | Merriweather, Source Code Pro, Amber accents (`#b45309`) | Whitepapers, design decisions, articles. |
| **`dynamics`** | Vibrant contemporary tech | Plus Jakarta Sans, Emerald/Teal accents (`#059669`) | Product guides, marketing copy, quickstarts. |

---

## 3. Responsive Table & Typography Handling

To ensure tables and code elements display cleanly without awkward word-wraps:
1. **First-Column Wraps**: Standard table columns containing short commands or package names are locked to single-line rendering:
   ```css
   th:first-child, td:first-child {
       white-space: nowrap;
   }
   td:first-child code {
       white-space: nowrap !important;
       word-break: normal !important;
   }
   ```
2. **Container Tag Symmetry**: The compiler strictly verifies opening and closing `<div>` tag balance to avoid premature `<main>` container collapses.
3. **Responsive Grid**: Uses CSS Grid layout with a sticky table-of-contents navigation sidebar, central reading column, and metadata header.
