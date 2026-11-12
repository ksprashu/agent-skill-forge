---
name: voice-register
description: "Apply a person's writing voice and channel-specific register (R1 quick internal email, R2 stakeholder email, R3 technical blog, R4 strategy doc, R5 working notes, and R6 technical dossiers/readouts/reports) alongside unslop. Automatically resolves a voice profile from a local override, ~/.gemini/personas/default/voice_and_tone.md (fetched from AGENT_PERSONA_REPO when set), or the neutral template."
---

# Voice Register - Personal Style and Channel Registers (`R1`-`R6`)

Write in a specific person's voice, in the register that fits the channel. `unslop` and `voice-register` work together as one unified voice pipeline: `unslop` strips AI bloat while preserving connected cause-and-effect sentence flow, and `voice-register` supplies the resolved profile (`~/.gemini/personas/default/voice_and_tone.md`) and the six channel registers (`R1`-`R6`). When no personal profile is configured (`tier 3`), both skills stay completely persona-neutral.

**When it applies.**
- **Outward texts sent under the user's name** (`R1`-`R5`): emails, technical blogs, strategy PRDs/BRDs, PR descriptions, and working notes.
- **Technical dossiers, post-planning readouts, code reviews, and analytical reports written for the user** (`R6`): uses the `R6: Technical Dossiers, Readouts & Analytical Reports` register when a personal profile resolves so reports and dossiers follow the user's preferred conventions rather than clipped 10-word fragments or chatty blog prose.

## Core Workflow

1. **Resolve the voice profile.** Run `python3 <skill-dir>/scripts/persona.py pull`. Add `--name <name>` only when the user asked for a named profile (`python3 <skill-dir>/scripts/persona.py status --name <name>` reports it). When `AGENT_PERSONA_REPO` is set, it clones the user's persona repo if missing, refreshes it at most once a day, and activates any optional `rules/` or `skills/` overlays inside the persona directory; when unset, it fetches nothing. If Python is unavailable, or the command resolves `tier 3`, do not treat placeholders in `references/voice_and_tone.template.md` as a persona. On an explicit "in my voice" request in that case, say that no personal profile was found and offer to scaffold one from that template or to continue in neutral `unslop` prose. First match wins:
   1. `references/voice_and_tone.local.md`: private override on this machine (gitignored).
   2. `~/.gemini/personas/default/voice_and_tone.md`: the user's persona directory, shared across every harness on this machine (`AGENT_PERSONA_DIR` overrides the location). A named profile lives at `~/.gemini/personas/<name>/voice_and_tone.md` and is used only with `--name`.
   3. `references/voice_and_tone.template.md`: neutral fallback template when no personal profile is installed (`tier 3`; `persona.py` exits `1`). The `<...>` placeholders in that file are blanks, not a voice.
2. **Load the samples.** If `voice-samples.md` sits next to the resolved profile, read it and use its before/after pairs as few-shot calibration across `R1`-`R6`. The bundled examples in `examples/voice-samples.md` and `examples/voice-samples.template.md` cover those registers, including `R6`.
3. **Run `unslop` connected-flow hygiene.** Remove AI smells, promotional throat-clearing, superficial `-ing` tails, and theatrical metaphors while keeping natural, connected 18-30 word cause-and-effect sentences (`"because"`, `"whereas"`, `"so that"`, `"which means"`, `" - "`). Never chop thoughts into 10-word staccato fragments.
4. **Pick the channel register (`R1`-`R6`)** from `references/channel-registers.md`:
   - `R1`: Quick internal email
   - `R2`: Stakeholder or external email
   - `R3`: Technical blog or tutorial
   - `R4`: Strategy doc, PRD, BRD, or proposal
   - `R5`: Working notes and comments
   - `R6`: Technical dossier, post-planning readout, code review, or analytical report written for the user
5. **Apply the profile's fingerprints (when `tier 1` or `tier 2` resolves)** for that register: spelling, punctuation, transitions, lexicon, and structure. When `tier 3` resolves, keep neutral connected prose and preserve the author's existing spelling and punctuation.
6. **Respect the live vs. polished boundary.** Shorthand the profile marks as live-only stays out of polished docs, dossiers (`R6`), blogs (`R3`), and external email (`R2`).
7. **Verify** that facts, numbers, formulas, names, flags, and commitments are 100% unchanged.

## References

- `scripts/persona.py`: resolves the profile, clones or refreshes the persona repo, reports optional `reader_pack` / `characters_pack` paths, and activates `rules/` + `skills/` overlays (`status`, `pull [--force]`, `activate`).
- `references/channel-registers.md`: what each register (`R1`-`R6`) controls.
- `references/voice_and_tone.template.md`: blank profile template.
- `examples/example-profile.md` & `examples/voice-samples.md`: worked examples across `R1`-`R6` using a fictional profile. Do not apply them unless the user asked for that example by name.

## Hard Constraints

- Never change facts, figures, formulas, flags, dates, or commitments to fit a voice.
- Never apply a named profile or `examples/example-profile.md` unless the user asked for it by name.
- Never fill tier 3 `<...>` placeholders in as the user's name, spelling, or sign-off.
- Never chop technical explanations into robotic 8-to-12-word staccato fragments.
- Never use blog storytelling hooks (`R3`) or theatrical metaphors inside a technical dossier or readout (`R6`).
- Preserve exact US spelling in quoted UI labels, CLI flags, API names, and code identifiers, whatever the profile's spelling rule.
- Do not commit `.local.md` files.
