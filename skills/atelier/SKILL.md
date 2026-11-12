---
name: atelier
description: "Produces distinctive, human-grade visual and structured outputs for any significant human-facing deliverable. Use whenever creating a report, brief, digest, summary, memo, one-pager, news roundup, research analysis, executive overview, or any substantial document, presentation, or structured content intended for human consumption. Applies subject-grounded design direction, strong hierarchy, tables, scannability, and anti-AI-slop principles. Prefer professional file formats (docx, pptx, pdf) for substantial work."
type: workflow
lifecycle: active
---

# Atelier — Distinctive Human-Grade Output

Atelier produces reports, briefs, digests, and documents that feel designed for the specific subject and audience, not templated. It grounds visual choices in the content, prioritizes scannability and hierarchy, and avoids common AI aesthetic defaults.

## When to Activate

Activate for any request that produces a significant human-facing artifact:
- Reports, research briefs, executive summaries
- News digests, technology signal digests, weekly roundups
- Memos, one-pagers, decision briefs
- Structured analyses with tables, findings, recommendations

Do not activate for pure code, data queries, or short factual answers.

## Core Process

1. **Ground in the subject.** Identify the content’s domain, audience, and primary job before any visual or structural choices. A finance brief and a product design critique must look and feel different.

2. **Invent a short design direction.** Create a compact, unique aesthetic direction for this piece only. Name it in 2–4 words (e.g., “Quiet Ledger”, “Signal Paper”, “Field Notes”). Do not reuse previous directions. Base it on the subject’s materials, tone, or vernacular.

3. **Plan tokens and structure.** Write a brief internal DESIGN.md-style plan (do not show the user unless asked):
   - **Overview**: 1–2 sentence personality and emotional tone.
   - **Colors**: 3–5 named roles with hex (primary text/ink, surface, one accent, neutrals). Justify each by the subject.
   - **Typography**: Distinct display and body choices with roles. Avoid Inter, Arial, or system defaults unless the subject demands them.
   - **Layout & hierarchy**: How information will be scanned (sections, tables, callouts, density).
   - **Do’s and Don’ts**: Explicit anti-patterns for this piece.

4. **Review against AI defaults.** Check the plan for common tells and revise if present:
   - Warm cream (#F4F1EA) + terracotta/clay accent
   - Near-black + single acid-green or vermilion
   - Identical rounded cards with soft gray shadows
   - Single-word color accents in headlines
   - ALL-CAPS eyebrows on every section
   - Generic “01 / 02 / 03” numbering unless content is truly sequential

5. **Produce the output.** Prefer structured professional formats for substantial work:
   - Multi-page or formal reports → use the **docx** skill with clear heading hierarchy, tables, and the planned tokens.
   - Slide-based briefs or decks → use the **pptx** skill.
   - Fixed-layout or print-like pieces → PDF via the **pdf** skill or conversion.
   - Short or conversational pieces → rich markdown with tables, bold labels, and short paragraphs.
   Apply one memorable element (a strong header treatment, a single accent color used sparingly, distinctive type pairing) and keep everything else quiet.

   **Use visuals liberally when they improve clarity or impact.** Not every section needs an image, but include graphics, diagrams, icons, or infographics wherever they help the reader understand faster than text alone:
   - Generate custom diagrams, icons, or conceptual illustrations when the subject benefits from them.
   - Source relevant existing images or charts via search when appropriate and available.
   - Prefer generated visuals (including high-quality image generation) for original diagrams, process flows, or subject-specific illustrations.
   - Embed visuals with clear captions and ensure they reinforce the content rather than decorate it.

   **Zero-Collision Chart, SVG & Table Guardrails (Mandatory for HTML):**
   - **Never hand-code floating multi-line text inside 2D SVG scatter plots:** Raw `<svg>` `<text x="..." y="...">` elements have no CSS flow layout, line wrapping, or collision engine. When data points cluster (for example, 5 fast models between `25-80s` and 1 outlier at `260s`), floating `<text>` labels and diagonal `<line>` annotations inevitably collide on top of each other.
   - **Use Row-Isolated Lanes for Multi-Metric Charts:** Whenever plotting multi-metric comparisons (score vs latency, cost vs throughput, benchmark comparisons), use **CSS Grid horizontal bar-tables** (`.telemetry-board` / `.pair-bars`) or **row-per-item SVG dot plots** where each item owns a dedicated vertical band (`>= 36px` tall) and text labels live in a fixed left column outside the plotted axis.
   - **Validate Every HTML Report Before Delivery:** Run `python3 <skill-dir>/scripts/validate_atelier_html.py <path/to/report.html>` (adding `--forbid-dashes` when the active voice profile forbids typographic em-dashes, or inspect a rendered browser screenshot) before delivering any HTML report to verify 100% balanced HTML tags and zero overlapping `<svg>` `<text>` bounding boxes.

6. **Critique, validate, and deliver.** Ensure scannability (tables for comparisons, bullets for lists, short paragraphs), sufficient contrast, consistent spacing, zero overlapping chart labels, and that the result feels specific to this subject. Deliver the file or formatted content.

## Design Principles (Mandatory)

- **Subject-specific, not thematic.** Every piece invents its own direction. Never apply a fixed theme library.
- **Hierarchy is structure.** Use heading levels, tables, and spatial grouping to encode meaning. Avoid decorative elements that do not carry information.
- **Restraint.** Spend boldness in one place. Remove one accessory before finishing.
- **Typography carries personality.** Choose type deliberately. Line length under ~80 characters for body. Distinct roles for display vs body.
- **Connected Prose & Voice Register (`unslop` + `R6` When Active).** Apply the `unslop` skill to every Atelier report, dossier, readout, or decision brief so prose follows its connected cause-and-effect flow and anti-slop rules. When a `voice-register` persona profile resolves (`tier 1` or `tier 2`), apply that skill's `R6` report register, regional spelling, and punctuation rules.
- **Tables and scannability.** Prefer tables for any comparison, metrics, or multi-item data. Bold key terms and labels.
- **Visuals where they help.** Use diagrams, icons, generated illustrations, or sourced images liberally when they convey information faster or more clearly than text. Caption them and tie them to the content.
- **Accessibility floor.** Maintain readable contrast. Respect reduced-motion where relevant. Do not rely on color alone.

## Output Preferences

| Request type | Preferred format | Notes |
|--------------|------------------|-------|
| Formal report, memo, multi-page brief | docx | Use heading styles, TOC if long, proper tables |
| Presentation-style brief or digest | pptx | One idea per slide, strong hierarchy |
| Fixed one-pager or visual brief | PDF or HTML | Tight control over layout |
| Quick digest or in-conversation summary | Markdown | Tables + short sections + bold labels |

Always offer the file for download when generating one. For in-chat markdown, keep it dense and scannable.

## Anti-Patterns to Reject

- Generic SaaS card grids
- Warm cream + clay/terracotta palettes
- Monospace for non-code labels
- Decorative numbered markers on non-sequential content
- Overuse of accent color (more than one primary accent role)
- Walls of text without tables or hierarchy

## References

See `references/design-principles.md` for expanded guidance on subject-grounded direction, DESIGN.md-style planning, AI tells to avoid, and hierarchy rules.
