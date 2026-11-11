---
description: "Expanded design principles and DESIGN.md patterns for Atelier. Read when planning visual direction or refining output quality."
---

# Design Principles for Atelier

## Subject-Grounded Direction

Every output starts from the content’s domain, audience, and job:

- Finance / metrics → precise, high-density, restrained ink and rules
- Research / science → clear hierarchy, evidence-first, calm surfaces
- Product / design critique → more spatial, stronger type contrast
- News / signals → journalistic density with clear sectioning
- Strategy / decision → recommendation-forward, strong callouts

Invent a 2–4 word direction name that could not apply to a different subject.

## DESIGN.md-Style Planning (Internal)

When planning, structure an internal note with these sections in order:

1. **Overview** — Personality, density, emotional tone, audience.
2. **Colors** — 3–5 roles with hex and usage (ink, surface, accent, muted). Justify from the subject.
3. **Typography** — Display and body families with roles and approximate scales. Avoid defaults.
4. **Layout** — Scanning strategy, section rhythm, use of tables vs prose.
5. **Do’s and Don’ts** — Specific rules for this piece.

Tokens are normative; prose explains why.

## Common AI Tells to Avoid

| Tell | Why it fails | Alternative |
|------|--------------|-------------|
| Cream background + terracotta accent | Default Claude/Anthropic look | Derive palette from subject materials |
| Near-black + acid green | Overused dark mode template | Choose density and contrast that serve the content |
| Identical rounded cards | SaaS kit default | Use hierarchy and tables instead of card grids |
| Single-word color in headline | Decorative, not structural | Use weight, size, or spacing for emphasis |
| ALL-CAPS section labels everywhere | Visual noise | Reserve caps for true labels or metadata |
| Soft gray shadows on everything | Generic elevation | Use borders, spacing, or one deliberate elevation |

## Hierarchy and Scannability Rules

- Comparisons and metrics → tables with clear headers
- Lists of findings or actions → bullets or numbered only when sequential
- Key terms and recommendations → bold
- Paragraphs → 2–4 sentences maximum
- Sections → explicit headings that describe content, not “Section 1”
- One primary accent color, used sparingly for emphasis or interactive-like elements

## Chart, SVG & Table Geometry Rules (Zero-Overlap Contract)

1. **No Floating Multi-Line Text in 2D SVG Scatter Plots:**
   - Raw `<svg>` `<text x="..." y="...">` elements have no CSS layout, wrapping, or collision engine. When data points cluster on one side of an axis (e.g., 5 points between `25s` and `80s` and 1 outlier at `260s`), floating text callouts and diagonal `<line>` annotations inevitably collide.
   - Instead, use **row-isolated horizontal lanes**: either CSS Grid dual-bar telemetry tables (`.telemetry-board` / `.pair-bars`) or row-per-item SVG dot plots where each row owns a dedicated `>= 36px` vertical band (`y = row_index * 36`), text labels sit in a fixed left column (`x = 8..280`), and only geometric markers sit on the plotted axis (`x = 290..950`).
2. **SVG Text Bounding-Box Clearance:**
   - Every `<text>` element in an `<svg>` must maintain at least `1.2x font-size` vertical separation from any other `<text>` element whose horizontal bounding box (`width ≈ 0.56 * font_size * len(text)`) overlaps within `6px`.
   - Never route `<line>` or `<path>` strokes through `<text>` bounding boxes.
3. **Table Column Discipline:**
   - Wrap wide tables in `.table-wrap { overflow-x: auto; }`.
   - Right-align numeric columns (`font-variant-numeric: tabular-nums; white-space: nowrap;`) and apply `white-space: nowrap` only to short model IDs or numbers so prose explanation cells wrap cleanly.
4. **Deterministic Validation Gate:**
   - Run `python3 <skill-dir>/scripts/validate_atelier_html.py <report.html>` before delivering any HTML output.

## Novelty Requirement

Do not reuse a previous aesthetic direction within the same conversation or for similar subjects. Each piece must invent its own short design direction grounded in that specific content. Serendipity comes from subject-specific choices, not random decoration.
