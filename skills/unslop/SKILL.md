---
name: unslop
description: "Rewrite human-readable text (prose, dossiers, reports, readouts, docs, code comments, commit messages, analyses, emails, UI copy) to remove AI smells, promotional bloat, and needless words while keeping natural, connected cause-and-effect sentence flow. Integrates with voice-register when a personal voice profile is configured. Apply by default to every substantial text output."
type: workflow
lifecycle: active
---

# Unslop - Anti-Bloat & Connected Prose Engine

Remove AI tells, promotional padding, and clutter so the writing is clear, concrete, connected, and genuinely pleasant to read. `unslop` is persona-neutral by default: it enforces connected cause-and-effect sentence flow while keeping the author's existing regional spelling and punctuation unless a [`voice-register`](../voice-register) profile resolves (`tier 1` or `tier 2`).

**Apply by default** to all human-readable text: technical dossiers, post-planning readouts, architecture reports, code reviews, explanations, docs, comments, commit messages, analyses, UI copy, and emails. Skip only executable code logic, machine formats (JSON, YAML schemas, exact API payloads), or when the user explicitly says "raw" or "no unslop".

## Core Workflow

1. **Check for an Active Voice Profile (`voice-register` Integration)**:
   - If [`voice-register`](../voice-register) is installed alongside `unslop`, run `python3 <skill-dir>/../voice-register/scripts/persona.py status` once per session to check whether a personal voice profile resolves.
   - **When `tier 1` (local override) or `tier 2` (persona directory) resolves**: Load the resolved `voice_and_tone.md` (and `voice-samples.md` if present) and select the matching channel register (`R1`-`R5` for outward emails, blogs, PRDs, and notes sent under the user's name; `R6` for technical dossiers, post-planning readouts, code reviews, and analytical reports written for the user).
   - **When `tier 3` (neutral template) resolves or `voice-register` is not installed**: Stay persona-neutral, applying the connected cause-and-effect clarity rules in `references/writing-principles.md` while preserving the author's existing spelling and punctuation conventions.
2. **Detect & Subtract AI Smells**:
   - Strip promotional inflation, throat-clearing openings, filler rule-of-three lists, superficial `-ing` participial tails, and theatrical metaphors (see `references/ai-smells.md`).
3. **Write in Connected Cause-and-Effect Flow (Never Clipped Fragments)**:
   - Follow `references/writing-principles.md`. Pair **what a mechanism does** with **why it matters to the decision or workflow** in one smooth, connected sentence (`18-30 words` for technical prose) using `"because"`, `"whereas"`, `"so that"`, `"which means"`, or `" - "`.
   - Never chop a cause-and-effect explanation into 8-to-12-word telegraphic fragments. Cut corporate bloat, not the logical connectors that make prose flow naturally.
4. **Apply Resolved Profile Mechanics (Only When `tier 1` or `tier 2` Resolves)**:
   - Apply the resolved profile's regional spelling, dash/arrow punctuation rules, lexicon, and register structure (`R1`-`R6`), preserving exact original spelling inside quoted CLI flags, UI labels, API names, and code identifiers.
5. **Verify Technical Grounding**:
   - Confirm that 100% of facts, metrics, formulas, CLI flags, API signatures, and constraints are preserved unchanged. Never soften precision or invent claims.
6. **Output**:
   - Deliver the cleaned text directly without meta-commentary unless asked.

## References

- `references/writing-principles.md`: Zinsser clarity + connected cause-and-effect flow (anti-staccato rules).
- `references/ai-smells.md`: AI vocabulary, structural tells, and theatrical metaphors to remove.
- `examples/before-after.md`, `examples/samples.md`: Worked rewrites showing connected prose vs. AI bloat and clipped fragments.

## Hard Constraints

- Preserve 100% of factual meaning, technical accuracy, math, and constraints.
- Never chop related cause-and-effect clauses into robotic 8-to-12-word staccato sentences.
- Never replace AI buzzwords with corny idioms or theatrical metaphors (*"what the hand gives"*, *"spins like a centrifuge"*, *"stalls at 3 PM"*).
- Do not impose regional spelling or punctuation bans unless a `tier 1` or `tier 2` voice profile explicitly specifies them.
- If the original text is already clean, connected, and natural, leave it alone.
