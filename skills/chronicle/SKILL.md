---
name: chronicle
description: 'Transform dense technical reports, research dossiers, architecture briefs, and data-heavy playbooks into gripping nonfiction narrative stories in the tradition of Malcolm Gladwell and Adam Grant, paired with Atelier editorial book typography and interactive Field Guide checklists. Use whenever the user asks to tell a report or technical topic "like a story", "like a book", "in a storytelling format", "Malcolm Gladwell / Adam Grant style", or invokes /chronicle or @chronicle.'
type: quality-gate
lifecycle: post-synthesis
---

# Chronicle: Technical Nonfiction Storytelling & Interactive Field Book

Transform dense technical reports, research dossiers, and strategic briefs into immersive, book-grade nonfiction narratives. Where `atelier` turns raw analysis into structured editorial reference reports, `chronicle` turns technical evidence into a gripping human and systems story that reads like a chapter from Malcolm Gladwell or Adam Grant, without dropping a single denominator, citation, or action item.

## When to Use

Trigger this skill whenever the user asks to:

- Turn an existing report, brief, or technical investigation into a story, book, or narrative ("tell me this like a story", "like a nonfiction book", "storytelling format")
- Explain a technical, architectural, or leadership topic in the style of Malcolm Gladwell, Adam Grant, Michael Lewis, or narrative business/leadership books
- Make a dense technical dossier engaging to read from start to finish while preserving concrete actionables, to-dos, and evidence tags
- Run `/chronicle` or apply `@chronicle` to a topic or document

## Core Philosophy: Narrative Tension Meets Hard Receipts

Most technical reports fail reader attention because they open with a taxonomy and bury the human stakes under a wall of bullet points. Conversely, most business storytelling fails senior engineers because it trades away denominators, mechanisms, and failure bounds for platitudes.

Chronicle bridges both worlds through five non-negotiable rules:

1. **Open in a Concrete Room, Not an Abstract Thesis (The Gladwellian Cold Open)**
   Never open a chapter with a taxonomy or summary definition. Start with a specific moment, a puzzling anomaly, an engineering artifact, or a quiet Tuesday morning dilemma (e.g., an engineer staring at a commit file in `home-mixer/params/param.rs`, or a room of 500 builders in Bengaluru). Let the scene raise a counterintuitive question before introducing the framework.

2. **The Counterintuitive Pivot (The Grant / Gladwell Turn)**
   Frame every chapter around the gap between **Common Folklore** (what everyone in the industry assumes works) and **The Measured Mechanism** (what the primary source code, study, or production trace actually proves). Use the friction between intuition and evidence to pull the reader forward.

3. **Zero-Dilution Grounding (Storytelling Never Excuses Slop)**
   Narrative flow never means inventing facts or dropping citations. Every quantitative claim, ranker weight, latency figure, or study percentage must remain 100% faithful to the source material, carry an inline clickable source link, and preserve explicit evidence badges (`[P]` Platform primary, `[D]` Practitioner/research data, `[A]` Anecdote/inference, `[U]` Unverified). When illustrating a point with a hypothetical scenario or composite practitioner vignette, explicitly label it as a **Composite Scenario (`[A]`)** so narrative color never masquerades as a verified historical event.

4. **Every Chapter Ends with a "Field Notebook" (Actionables & To-Dos)**
   A great leadership or technical book does not leave the reader merely entertained; it changes what they do on Monday morning. Conclude every chapter with a structured **Field Notebook & Action Checklist** containing concrete, time-boxed to-dos, copy-pasteable templates, and explicit stop-rules.

5. **Enforce `@unslop` Prose Discipline**
   Write in crisp, active voice with straight quotes (`"` and `'`), clean hyphens (`-`), zero em-dashes, and zero AI throat-clearing ("In today's fast-paced landscape", "delve", "tapestry", "testament"). Vary sentence cadence: pair longer, scene-setting narrative sentences with short, punchy 6-to-10-word verdicts.

## Narrative Architecture: The 6-Beat Chapter Arc

Structure every Chronicle deliverable as a multi-chapter nonfiction book (typically 4 to 7 chapters plus a Prologue and a 90-Day Field Guide):

1. **The Cold Open (The Anomaly or Scene)**: A vivid, concrete vignette or primary-source discovery that surfaces a puzzle.
2. **The Conventional Wisdom Trap**: Why smart practitioners default to the wrong intuition on this problem, and what that mistake costs in practice.
3. **The Forensic Unpacking (The Mechanism)**: Walking through the exact code, study methodology, or system architecture as a detective story. Show *how* the system works under the hood (with exact figures, denominators, and SVG visual diagrams).
4. **The Practitioner Case Study**: How this mechanism plays out in the real world for a builder or technical leader, contrasting the high-noise path with the high-signal path.
5. **The Boundary Condition (Where the Rule Flips)**: Every honest framework names its own limits. State the exact conditions, caveats, or unverified zones (`[U]`) where the conclusion changes.
6. **The Chapter Field Notebook (Actionables & To-Dos)**: 2 to 4 concrete, checkable action items with time budgets and verification checks.

## Visual & Interactive Book Design (Atelier Literary Edition)

When rendering a Chronicle deliverable as an interactive HTML book in Canvas (`web-app-generation`) or saving to Google Drive (`05 - Outputs`), apply the **Atelier Literary Edition** aesthetic:

- **Palette**: Warm Archival Paper (`#FAF7F2`), Deep Espresso Ink (`#18181B`), Elevated Parchment Cards (`#FFFFFF`), Terracotta Editorial Accent (`#B84A27`), Deep Forest Teal for Primary Evidence (`#0F5C59`), and Warm Stone Rules (`#E4DFD7`). Include a toggleable **Evening Reading Mode** (`#141413` warm charcoal surface, `#EAE6DF` soft parchment text).
- **Typography**: Editorial serif for chapter titles, drop caps, pull quotes, and long-form narrative prose (`Newsreader` or `Source Serif 4`, `18px/1.72`, `65ch` measure for effortless reading); crisp sans-serif (`IBM Plex Sans` or `Inter`) for navigation, tables, evidence badges, and interactive Field Notebook checklists; monospace (`IBM Plex Mono`) for code paths, commit hashes, and weights.
- **Interactive Book Features**:
  - **Left-Rail Chapter Navigator & Reading Progress Bar**: Smooth chapter switching or scrolling with estimated reading times per chapter.
  - **Margin Evidence Lenses**: Interactive filter or highlight pills for `[P]`, `[D]`, `[A]`, and `[U]` claims so the reader can inspect the evidentiary skeleton behind the story at a glance.
  - **Interactive Field Notebook Checklists**: Persistent, checkable to-do boxes at the end of every chapter and a consolidated **Master Action Tracker** tab that tallies completed actions and weekly time budgets.
  - **Embedded Visual Exhibits**: High-contrast SVG diagrams and comparison tables styled as book plates (`Exhibit 1`, `Exhibit 2`) with full source captions.

## Execution Workflow

1. **Ingest & Map the Evidence Ledger**
   Read the source report or primary documents in full. Extract every hard number, commit SHA, study sample size, URL, caveated `[U]` item, and recommended action. Never summarize from snippets alone.

2. **Design the Narrative Spine**
   Map the technical sections into 4 to 7 narrative chapters. Give each chapter an evocative book-style title and subtitle (e.g., *Chapter 1: The Ghost in the Feed - Why Applause Is Worth 0.66 and Conversation Is Worth 20*).

3. **Draft the Dual Deliverables**
   - **Interactive HTML Storybook / Field Book**: Build a self-contained, single-file HTML application with full chapter prose, drop caps, pull quotes, SVG exhibits, evidence lenses, and interactive to-do trackers.
   - **Canonical Google Doc (Swarm `REPORTS-001a` Compliance)**: When operating in Prashanth's workspace, also save the complete narrative edition as a Google Doc in `05 - Outputs` (`1_1WSdHHYaE5wmWl5FIYLXmhvaapeFs0x`) so it is permanently accessible across devices and indexed for the reports archive.

4. **Self-Audit Against the Grounding Checklist**
   Before delivering, check that:
   - Every factual claim and metric from the source report is preserved with its exact denominator and inline clickable URL.
   - Zero em-dashes or banned AI slop words appear anywhere in the text.
   - Every chapter includes concrete anecdotes/case studies and an actionable Field Notebook checklist.

## Gotchas

- **Never sacrifice precision for drama**: If a study is nine years old or vendor-sponsored (like the 2017 and 2025 Edelman-LinkedIn surveys), weave that exact caveat *into* the narrative voice ("Now, any good engineer looking at that 84% number should immediately ask a skeptical question: who paid for the survey?"). Honesty makes the storyteller *more* compelling, not less.
- **Do not write a shallow summary**: A Chronicle piece is a comprehensive, long-form reading experience. Do not compress a 16-section report into a 500-word fairy tale; unpack every mechanism, table, and playbook through narrative prose and structured exhibits.
