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

6. **Critique and deliver.** Ensure scannability (tables for comparisons, bullets for lists, short paragraphs), sufficient contrast, consistent spacing, and that the result feels specific to this subject. Deliver the file or formatted content.

## Design Principles (Mandatory)

- **Subject-specific, not thematic.** Every piece invents its own direction. Never apply a fixed theme library.
- **Hierarchy is structure.** Use heading levels, tables, and spatial grouping to encode meaning. Avoid decorative elements that do not carry information.
- **Restraint.** Spend boldness in one place. Remove one accessory before finishing.
- **Typography carries personality.** Choose type deliberately. Line length under ~80 characters for body. Distinct roles for display vs body.
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
