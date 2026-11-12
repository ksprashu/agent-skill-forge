---
name: codelab
description: Scaffold and validate interactive technical tutorials, workshops, and developer guides. Trigger via /codelab.
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
3.  **Optional Character Pack Resolution (Neutral Default):** Run `node <skill-dir>/scripts/characters.cjs status` before drafting callouts or visuals (`CODELAB_CHARACTERS_DIR` -> `~/.gemini/personas/default/characters/` -> none).
    - **Exit `1` (`tier: neutral`, public default):** Use clean, mascot-free callouts (`> aside positive` **"Tip:"** and `> aside negative` **"Watch out:"**) and standard technical diagrams or annotated UI screenshots.
    - **Exit `0` (`tier: character-pack`):** Load the resolved `CHARACTER_BIBLE.md` (if present), `characters.json`, avatar icons, and setup comics from `characters_dir`. **Show, Don't Describe in Prose:** Keep physical appearance prompts strictly inside image-generation calls; in tutorial prose, introduce characters briefly by name and role, and let their illustrations and inline avatar badges show them visually.
4.  **Cloud Naming, Antigravity URL, Credits Banner & Gemini Models:**
    - Google Antigravity (`agy`) is ONLY at `https://antigravity.google` (docs: `https://antigravity.google/docs`). Never use legacy `https://idx.dev` URLs anywhere.
    - Always include `Enable_GDP_Credits_Banner: True` in the YAML frontmatter of any codelab that uses Google Cloud credits.
    - Use **Gemini Platform** (`https://cloud.google.com/products/gemini-enterprise-agent-platform`) instead of legacy "Vertex AI" naming or URLs.
    - Default to the latest stable **Gemini Pro** model for primary agentic reasoning, architecture, and multimodal critique, and **Gemini Flash** for fast utility tasks (or respect workspace-configured model defaults).
5.  **100% Prompt-Driven Antigravity Mandate:** For all Google Antigravity (`agy`) codelabs, drive workflows via **natural-language prompts inside Antigravity** rather than asking the learner to run raw internal Python scripts manually from the command line. Explain what each underlying tool does and why it is needed before every setup command or prompt.
6.  **Deterministic Quality Guards:** Every authoring task MUST undergo automated syntax validation and readability checks using the bundled workspace tools before completion.

## Core Workflow

Always follow these phases sequentially when creating a new codelab, unless explicitly instructed otherwise.

### Phase 1: Brainstorming (Narrative & Persona)
Before writing any instructions, define the theme and narrative.
1. **Character Pack & Tone Check:** Run `node <skill-dir>/scripts/characters.cjs status` first, then ask the user for the target audience and preferred tone. If a character pack resolves (`exit 0`), confirm using the resolved `companion_theme` (`CHARACTER_BIBLE.md` and `characters.json`); if `exit 1` (`tier: neutral`), default to a direct, mascot-free developer voice unless the user requests a custom persona.
2. **Theme Design:** Establish a narrative thread that ties the technical steps together.
3. **Cloud Credits Check:** Ask the user: "Does this lab require Google Cloud Trial Credits (no credit card required)?" If yes, ask for the `REDEMPTION_URL` and follow `references/cloud-credits.md`.
4. *Reference:* Check `references/narration-guides.md` (plus the resolved character bible when `characters.cjs status` exits `0`) for tone and callout conventions.

### Phase 2: Technical Architecture & Flow
Design the logical progression of the codelab.
1. **Standard Flow:** Setup -> Environment -> Backend -> Frontend -> Deploy -> Cleanup.
2. **Cloud Credits & Standard Setup (Reusable Snippets):** If the lab requires Google Cloud, you MUST use the following reusable building blocks from `references/snippets/`:
   - `setup-project.md`: Handles Cloud Project and Trial Credit redemption.
   - `setup-environment.md`: Covers Cloud Shell vs Local Terminal setup.
   - `intro-gemini-cli.md`: Standard introduction to configuring the AI coding harness.
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
2. *Action:* Execute `node <skill-dir>/scripts/init_codelab.cjs <codelab-slug>` to generate the scoped folder hierarchy.
3. **Draft Context:** Fill out the generated `<codelab-slug>/design-doc.md` with the plan from Phase 2, and use `<codelab-slug>/context.md` for any unstructured notes.

### Phase 5: Content Generation (The Markdown)
Write the actual `index.lab.md` using strict formatting.

*💡 Quick Tip:* You can build, insert, or non-destructively edit steps in your codelab interactively with our CLI authoring tool by executing:
```console
node <skill-dir>/scripts/manage_codelab.cjs
```

1. **YAML Frontmatter (Strict):** You MUST use this exact template for the metadata block. Do NOT include `summary`, `categories`, `environments`, or `status`. Add `Enable_GDP_Credits_Banner: True` as an extra line only when the lab offers Google Cloud / GDP credits (see `references/cloud-credits.md`). Leave it out otherwise, which is what `scripts/init_codelab.cjs` scaffolds.
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
2. *Steps & Visuals:* Use `##` for major steps, `###` for sub-steps. Include `Duration: MM:SS` under each `##` step. Every `##` step page MUST include at least one visual (architecture diagram, setup comic, or annotated screenshot).
3. *Asides & Callouts:* Use only `> aside positive` (**"Tip:"**) and `> aside negative` (**"Watch out:"**) by default. When `characters.cjs status` exits `0`, use each character's configured `callout_label` and copy their circular avatar badges from `characters_dir` into `<codelab-slug>/codelab/img/` to embed inside the aside blocks. Do NOT use non-standard aside types.
4. *Style and Tone:* Adhere to Google writing standards. Keep sentences direct and clear. Avoid jargon and filler modifiers (do not write "simply" or "just"). Check `references/style_guide/voice.md` and `references/style_guide/inclusive-documentation.md`.
5. *Polyglot Design:* If the tutorial supports multiple languages, implement modular blocks following the templates in `references/polyglot.md`.
6. *Reference Grounding & Further Reading Sub-section:* Every codelab MUST conclude the final step (e.g., "Summary & Congratulations") or each major module with a dedicated `### 📚 Further Reading & References` sub-section containing categorized links to official product pages, documentation landing pages, deep-dive blogs, GitHub repositories, and video walkthroughs.

### Phase 6: Multi-modal Asset Plan
Plan the visual elements.
1. Identify steps where screenshots, architecture diagrams, or optional companion graphics are needed.
2. **Asset Library vs. Generation:**
   - **Character Pack Assets (When `characters.cjs status` Exits `0`):** Copy any pre-created setup comics (`comics` map) and avatar icons from `characters_dir` into the codelab's `img/` folder, and pass the pack's `reference_photo` / `character_sheet` files and `visual_prompt_descriptor` strings when generating new character illustrations.
   - **On-the-fly Generation (Default):** For architecture diagrams, conceptual illustrations, or annotated UI screenshots, use `image-gen` or `anot8` to produce crisp, self-explanatory visuals.
3. *Action:* Formulate explicit prompts for new assets and note them in `design-doc.md`.

### Phase 7: Validation & Readability Check (Deterministic Gate)
Before finalizing the codelab, you MUST validate both structure and readability:
1. **Structural Quality Check:** Run `node <skill-dir>/scripts/validate_codelab.cjs <path-to-lab.md>` to verify frontmatter layout, heading hierarchy, step durations, and aside syntax. Fix any critical compiler failures immediately.
2. **Readability Scoring Check:** Run `node <skill-dir>/scripts/fog.cjs <path-to-lab.md>` to calculate the Gunning Fog Index of the prose. Target a Gunning Fog Score of **&lt; 12 (General Audience)**. If the score is higher, shorten sentences, remove filler phrases, and use simpler technical words.
3. **Inclusive Language Audit:** Review files against `references/style_guide/inclusive-documentation.md` to ensure all terminology matches standard inclusive conventions.

## Resources & Guides

- **Interactive Scaffolder, Character Resolver & Authoring System:**
  - `scripts/init_codelab.cjs` (Generates project directories; honours `CODELAB_AUTHOR`)
  - `scripts/characters.cjs` (Resolves and schema-validates optional companion character packs)
  - `scripts/manage_codelab.cjs` (CLI tool to interactively create, outline, insert, non-destructively edit, or delete steps with integrated validator diagnostics)
- **Quality & Readability Validators:**
  - `scripts/validate_codelab.cjs` (Verifies markdown compilation structure)
  - `scripts/fog.cjs` (Verifies sentence and vocabulary readability indexes)
- **Best Practices & Schemas:**
  - `references/best-practices.md` (Design guidelines, coding standards, and path hygiene)
  - `references/metadata-schemas.md` (Strict YAML frontmatter and structural definitions)
  - `references/characters.schema.json` & `examples/characters.example/characters.json` (Optional character pack schema and Pip & Byte starter template)
- **Writing & Style Manuals:**
  - `references/style_guide/voice.md` (Active voice procedures, direct language guidelines)
  - `references/style_guide/inclusive-documentation.md` (Inclusive terms table and clear language guidance)
  - `references/polyglot.md` (Multi-language and polyglot code-block layouts)
- **Narrative & Cloud Credit Guides:**
  - `references/narration-guides.md` (Storytelling cues and optional companion callout conventions)
  - `references/comic-scripts.md` (4-panel setup comic storyboard templates for character packs)
  - `references/cloud-credits.md` (Google Cloud trial credit redemption and Antigravity sign-in guidelines)
