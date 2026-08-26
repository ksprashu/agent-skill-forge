---
name: codelab
description: Scaffold and validate interactive Google Codelab tutorials. Trigger via /codelab.
disable-model-invocation: true
---

# Codelab Creator

## Overview

The Codelab Creator skill provides a structured, 7-phase workflow for designing and scaffolding high-quality, engaging Google Codelabs. It enforces a "Visual-First" storytelling approach, integrates "Doc-Driven Vibe Coding" to ensure accuracy, and applies automated, deterministic checks to validate technical structure and prose readability.

## Core Mandates

1.  **Licensing:** Every code snippet, script, or configuration file generated MUST include the following header:
    ```
    Copyright 2026 Google LLC.
    SPDX-License-Identifier: Apache-2.0
    ```
2.  **Code Hygiene:** All generated code must adhere to idiomatic style guides and maintain high readability. **Never use hardcoded paths**; always prefer relative paths, home directory expansion (`~`), or environment variables.
3.  **Character Integrity:** Maintain the female gender and specific traits for Malti (Maltipoo) and Raggy (Ragdoll) in all instructional narratives and visual prompts.
4.  **Deterministic Quality Guards:** Every authoring task MUST undergo automated syntax validation and readability checks using the bundled workspace tools before completion.

## Core Workflow

Always follow these phases sequentially when creating a new codelab, unless explicitly instructed otherwise.

### Phase 1: Brainstorming (Narrative & Persona)
Before writing any instructions, define the theme and narrative.
1. **Persona Check:** Ask the user for the target audience and preferred tone. Propose **Malti (the Maltipoo)** and **Raggy (the Ragdoll)** as the default "friendly and fun" persona duo if a generic theme is needed.
2. **Theme Design:** Establish a narrative thread that ties the technical steps together.
3. **Cloud Credits Check:** Ask the user: "Does this lab require Google Cloud Trial Credits (no credit card required)?" If yes, ask for the `REDEMPTION_URL` and plan to use the mascot-themed guidelines from `references/cloud-credits.md`.
4. *Reference:* Check `references/narration-guides.md` for inspiration on tone and pacing.

### Phase 2: Technical Architecture & Flow
Design the logical progression of the codelab.
1. **Standard Flow:** Setup -> Environment -> Backend -> Frontend -> Deploy -> Cleanup.
2. **Cloud Credits & Standard Setup (Reusable Snippets):** If the lab requires Google Cloud, you MUST use the following reusable building blocks from `references/snippets/`:
   - `setup-project.md`: Handles Cloud Project and Trial Credit redemption.
   - `setup-environment.md`: Covers Cloud Shell vs Local Terminal setup.
   - `intro-gemini-cli.md`: Standard introduction to Gemini CLI.
3. **Architecture:** Define the high-level architecture diagram concept that will be presented in the "Overview" step.
4. *Action:* You will draft a `design-doc.md` detailing this flow in Phase 4. Proceed to Phase 3.

### Phase 3: Reference Gathering & Knowledge Catalog Harvesting (Mandatory Pre-requisite)
Ensure code accuracy, teach the user how to fish, and ground every concept in official documentation.
1. **Identify Products & Concepts**: List all APIs, SDKs, services, frameworks, or tools introduced in the codelab (e.g., Gemini SDK, Fastify, Cloud Run, React).
2. **Knowledge Catalog Reference Indexing**: Invoke `knowledge-catalog` routines (or search tools like `google-developer-knowledge`, `context7`, `search_web`) to collect and consolidate reference links. Save the gathered URLs and citations into an OKF Concept Document under `.gemini/knowledge/<SHORT_ID>/scout/references.md`.
3. **Product Dual-Linking Mandate**: For every product or service introduced in any codelab step, provide markdown links to both the **Product Landing Page** and the **Official Documentation Landing Page** (e.g., `[Google Cloud Run](https://cloud.google.com/run) ([Docs](https://cloud.google.com/run/docs))`).
4. **Concept & Video References**: For technical concepts, protocols, or architecture patterns, gather authoritative spec links, deep-dive articles, and video walkthroughs.
5. **Embedding Reference Links**:
   - Embed inline product dual-links directly into step introductions.
   - Embed challenge/docs links directly into code-generation prompts and instructions so users learn to consult official docs.
   - Include a mandatory **"Further Reading & Reference Materials"** sub-section at the end of each major step or in the final "Summary & Congratulations" step.

### Phase 4: Scaffolding
Create the scoped directory structure for the codelab.
1. **Determine Slug:** Ask the user or propose a short, URL-friendly name for the codelab (e.g., `my-cool-codelab`).
2. *Action:* Execute `node scripts/init_codelab.cjs <codelab-slug>` to generate the scoped folder hierarchy.
3. **Draft Context:** Fill out the generated `<codelab-slug>/design-doc.md` with the plan from Phase 2, and use `<codelab-slug>/context.md` for any unstructured notes.

### Phase 5: Content Generation (The Markdown)
Write the actual `index.lab.md` using strict formatting.

*💡 Quick Tip:* You can build, insert, or non-destructively edit steps in your codelab interactively with our CLI authoring tool by executing:
```console
node scripts/manage_codelab.cjs
```

1. **YAML Frontmatter (Strict):** You MUST use this exact template for the metadata block. Do NOT include `summary`, `categories`, `environments`, or `status`.
    ```yaml
    ---
    description: [Short description]
    id: [codelab-slug]
    keywords: docType:Codelab, category:Cloud, skill:Intermediate
    feedback link: https://github.com/googlecodelabs/feedback/issues/new?title=[codelab-slug]%20Feedback&labels=gemini,codelab&assignees=<github-handle>
    authors: <AUTHOR_NAME>
    layout: paginated
    ---
    ```
2. *Steps:* Use `##` for major steps, `###` for sub-steps. Include `Duration: MM:SS` under each `##` step.
3. *Asides:* Use `> aside positive` and `> aside negative` for tips and warnings. Do NOT use non-standard aside types.
4. *Style and Tone:* Adhere to Google writing standards. Keep sentences direct and clear. Avoid jargon and filler modifiers (do not write "simply" or "just"). Check `references/style_guide/voice.md` and `references/style_guide/inclusive-documentation.md`.
5. *Polyglot Design:* If the tutorial supports multiple languages, implement modular blocks following the templates in `references/polyglot.md`.
6. *Reference Grounding & Further Reading Sub-section:* Every codelab MUST conclude the final step (e.g., "Summary & Congratulations") or each major module with a dedicated `### 📚 Further Reading & References` sub-section containing categorized links to official product pages, documentation landing pages, deep-dive blogs, GitHub repositories, and video walkthroughs.

### Phase 6: Multi-modal Asset Plan
Plan the visual elements.
1. Identify steps where screenshots, architecture diagrams, or character graphics are needed.
2. **Asset Library vs. Generation:**
   - **Pre-created Assets:** Use the standard 4-panel instructional comics in `assets/common-images/` (e.g., `activate_billing_comic.png`, `gemini_cli_comic.png`) for the common setup steps mentioned in Phase 2.
   - **On-the-fly Generation:** For codelab-specific visuals (like app screenshots or custom architecture diagrams), use `image-gen-expert` to generate new assets.
3. **Character Consistency:** When generating new assets, always use the Malti (beige Maltipoo) and Raggy (bicolor Ragdoll) mascots to maintain a consistent theme.
4. *Action:* Formulate explicit prompts for new assets and note them in the `design-doc.md`. Use the standard assets for the reusable snippets.

### Phase 7: Validation & Readability Check (Deterministic Gate)
Before finalizing the codelab, you MUST validate both structure and readability:
1. **Structural Quality Check:** Run `node scripts/validate_codelab.cjs <path-to-lab.md>` to verify frontmatter layout, heading hierarchy, step durations, and aside syntax. Fix any critical compiler failures immediately.
2. **Readability Scoring Check:** Run `node scripts/fog.cjs <path-to-lab.md>` to calculate the Gunning Fog Index of the prose. Target a Gunning Fog Score of **&lt; 12 (General Audience)**. If the score is higher, shorten sentences, remove filler phrases, and use simpler technical words.
3. **Inclusive Language Audit:** Review files against `references/style_guide/inclusive-documentation.md` to ensure all terminology matches standard inclusive conventions.

## Resources & Guides

- **Interactive Scaffolder & Authoring System:**
  - `scripts/init_codelab.cjs` (Generates project directories)
  - `scripts/manage_codelab.cjs` (CLI tool to interactively create, outline, insert, non-destructively edit, or delete steps with integrated validator diagnostics)
- **Quality & Readability Validators:**
  - `scripts/validate_codelab.cjs` (Verifies markdown compilation structure)
  - `scripts/fog.cjs` (Verifies sentence and vocabulary readability indexes)
- **Best Practices & Schemas:**
  - `references/best-practices.md` (Design guidelines, coding standards, and path hygiene)
  - `references/metadata-schemas.md` (Strict YAML frontmatter and structural definitions)
- **Writing & Style Manuals:**
  - `references/style_guide/voice.md` (Active voice procedures, direct language guidelines)
  - `references/style_guide/inclusive-documentation.md` (Inclusive terms table and clear language guidance)
  - `references/polyglot.md` (Multi-language and polyglot code-block layouts)
- **Creative Theme Assets:**
  - `references/narration-guides.md` (Character personality traits and storytelling cues)
  - `references/comic-scripts.md` (Step-by-step panel scripts for Malti & Raggy illustrators)
  - `references/cloud-credits.md` (Mascot guidelines for Cloud credits redemption instructions)
