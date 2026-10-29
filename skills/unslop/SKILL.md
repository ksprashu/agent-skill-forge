---
name: unslop
description: "Rewrite human-readable text (prose, docs, code comments, commit messages, analyses, UI copy) to remove AI smells, promotional bloat, and needless words using Zinsser and light STE clarity principles. Persona-neutral; composes with a voice profile when one is set. Apply by default to every substantial text output."
type: workflow
lifecycle: active
---

# Unslop — Strip AI Smells and Bloat from Every Text Output

Remove AI tells, padding, and clutter so the writing is clear, concrete, and pleasant to read. Unslop is subtractive and persona-neutral: it carries no personal voice, name, or regional spelling rule. Personal style is the job of `voice-register`.

**Apply by default** to all human-readable text: explanations, docs, comments, commit messages, analyses, UI copy, emails, and similar. Skip only pure code logic, machine formats (JSON, YAML schemas, exact API payloads), or when the user explicitly says "raw" or "no unslop".

## Core Workflow

1. **Detect** AI smells, promotional inflation, and structural bloat (see `references/ai-smells.md`).
2. **Subtract** fluff, throat-clearing, filler rule-of-three lists, `-ing` participial tails, and unnecessary wrappers first.
3. **Clarify** using the Zinsser and light-STE principles in `references/writing-principles.md`: active voice, concrete nouns and verbs, omit needless words.
4. **Apply a voice overlay if one is set.** If the `voice-register` skill is installed and resolves a profile, apply the matching channel register (email, blog, strategy doc, notes). Otherwise keep clean, neutral practitioner prose and leave the author's existing spelling and punctuation conventions alone.
5. **Verify** that every fact, metric, CLI flag, API signature, and constraint is unchanged. Never invent details or soften precision.
6. **Output** the cleaned text. Prefer the rewritten text over commentary about the rewrite unless asked.

## When to Apply

- Every substantial explanation, documentation, comment, analysis, or UI string.
- Code comments and commit messages (keep them short and factual).
- Do **not** rewrite executable code logic, type signatures, or machine-readable structures.

## References

- `references/writing-principles.md` — Zinsser + practical clarity rules (the quality bar).
- `references/ai-smells.md` — Patterns to remove.
- `examples/before-after.md`, `examples/samples.md` — Worked rewrites.

Read the principles file when the text is longer than a few sentences or when the output will be read by humans.

## Hard Constraints

- Preserve 100% of factual meaning, technical accuracy, and constraints.
- Do not add hype, marketing language, or decorative filler.
- Do not impose a persona, regional spelling, or sign-off. Those come only from a voice profile.
- Prefer short, concrete sentences. Active voice. One clear idea per sentence where practical.
- Keep the writing human and readable, not rigid or mechanical.
- If the original is already clean, leave it mostly alone.
