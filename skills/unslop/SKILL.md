---
name: unslop
description: "Rewrite all human-readable text (prose, docs, comments, analyses, UI copy) to remove AI smells and match Prashanth's pragmatic Dev Advocate voice: clear, direct, concrete, human, and free of fluff. Apply by default to every substantial text output."
type: workflow
lifecycle: active
---

# Unslop — Clear Voice for Every Text Output

Strip AI tells and rewrite into Prashanth's voice: pragmatic, direct, technically grounded, and human. Make the writing clear, concrete, and pleasant to read.

**Apply by default** to all human-readable text: explanations, docs, comments, commit messages, analyses, UI copy, emails, and similar. Skip only pure code logic, machine formats (JSON, YAML schemas, exact API payloads), or when the user explicitly says "raw" or "no unslop".

## Core Workflow

1. **Detect** AI smells and bloat (see `references/ai-smells.md`).
2. **Subtract** fluff, throat-clearing, promotional padding, and unnecessary wrappers first.
3. **Rewrite** into the target voice using the principles in `references/writing-principles.md` and the persona in `references/voice_and_tone.md`.
4. **Verify** that facts, technical accuracy, and required constraints are unchanged. Never invent details or soften precision.
5. **Output** the cleaned version. Prefer the rewritten text over commentary about the rewrite unless asked.

## When to Apply

- Every substantial explanation, documentation, comment, analysis, or UI string.
- Code comments and commit messages (keep them short and factual).
- Do **not** rewrite executable code logic, type signatures, or machine-readable structures.

## References

- `references/voice_and_tone.md` — Prashanth's actual voice and preferences (source of truth).
- `references/writing-principles.md` — Zinsser + practical clarity rules (the quality bar).
- `references/ai-smells.md` — Patterns to remove.

Read the voice and principles files when the text is longer than a few sentences or when the output will be read by humans.

## Hard Constraints

- Preserve 100% of factual meaning, technical accuracy, and constraints.
- Do not add hype, marketing language, or decorative filler.
- Prefer short, concrete sentences. Active voice. One clear idea per sentence where practical.
- Keep the writing human and readable — not rigid or mechanical.
- If the original is already clean and in voice, leave it mostly alone.
