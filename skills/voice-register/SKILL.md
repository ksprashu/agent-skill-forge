---
name: voice-register
description: "Apply a person's writing voice and channel-specific register (quick internal email, stakeholder email, technical blog, strategy doc, working notes) on top of unslop. Use when asked to write or rewrite something in my voice, as me, or in a given register, and when drafting text the user will send under their own name (emails, posts, docs, PR descriptions). Resolves a voice profile from a local override, the user's persona directory (fetched from their private repo when AGENT_PERSONA_REPO is set), or the neutral template."
---

# Voice Register — Personal Style and Channel Registers

Write in a specific person's voice, in the register that fits the channel. This skill is additive: it applies spelling, punctuation, lexicon, greetings, and structure from a voice profile. It does not strip AI smells; run `unslop` for that.

**When it applies.** Use the voice only for text that goes out under the user's name: emails, posts, docs, PR descriptions and messages they send. The agent's own explanations, summaries and replies to the user stay in neutral `unslop` prose, even when a profile resolves.

## Core Workflow

1. **Resolve the voice profile.** Run `python3 <skill-dir>/scripts/persona.py pull`. When `AGENT_PERSONA_REPO` is set, it clones the user's persona repo if missing, or refreshes it at most once a day; when unset, it fetches nothing. Then it prints the tier, the profile path and the samples path. First match wins:
   1. `references/voice_and_tone.local.md`: private override on this machine (gitignored).
   2. `~/.gemini/personas/default/voice_and_tone.md`: the user's persona directory, one profile for every harness on this machine. Usually a clone of their private repo. `AGENT_PERSONA_DIR` overrides the location.
   3. `references/voice_and_tone.template.md`: neutral public baseline (carries no personal voice). When resolution falls back here, keep neutral `unslop` prose, tell the user no personal profile was found, and point them to this template or `human-voice` to create one.

   If the script can't run (no Python), check the same paths directly. If a pull fails, say why (offline, not signed in to `gh`, repo not found) and continue with whatever resolved.

   Named profiles live outside the repo at `~/.gemini/personas/<name>/voice_and_tone.md` (`persona.py status --name <name>`). Use one only when the user names it. No personal profile ships with this skill.
2. **Load the samples.** If `voice-samples.md` sits next to the resolved profile, read it and use its before/after pairs as few-shot examples for the register.
3. **Run `unslop` hygiene first.** Remove AI smells, throat-clearing, `-ing` tails, and wrappers before adding any voice.
4. **Pick the channel register** from `references/channel-registers.md`: R1 quick internal email, R2 stakeholder or external email, R3 technical blog, R4 strategy doc or proposal, R5 working notes and comments. Infer it from the request (recipient, medium, length). Ask only when two registers would produce materially different output.
5. **Apply the profile's fingerprints** for that register: spelling, punctuation, transitions, lexicon, greeting, body shape, sign-off.
6. **Respect the live vs. polished boundary.** Shorthand the profile marks as live-only stays out of polished docs and external email.
7. **Verify** that facts, numbers, names, flags, and commitments are unchanged. Voice changes how something is said, never what is said.

## References

- `scripts/persona.py`: resolves the profile and clones or refreshes the persona repo (`status`, `pull [--force]`). Pulls at most once a day.
- `references/channel-registers.md`: what each register controls, independent of any one person.
- `references/voice_and_tone.template.md`: blank profile to copy into tier 1 or 2.
- `examples/example-profile.md`: a complete profile for a fictional person, showing what a filled-in template looks like. Never apply it unless the user asks for it by name.
- `examples/voice-samples.md`: before/after rewrites across registers using the example profile.
- `examples/voice-samples.template.md`: blank sample sheet for your own profile.

## Building Your Own Profile

Copy `references/voice_and_tone.template.md` to `~/.gemini/personas/default/voice_and_tone.md` and fill it in. Or run `human-voice` to extract markers from your own logs, then edit the result. Keep anything private in the `.local.md` tier.

To use the same profile on every machine, push `~/.gemini/personas` to a private git repo and set `AGENT_PERSONA_REPO=<owner>/<repo>` in your shell profile. The README covers the setup.

## Hard Constraints

- Never change facts, figures, flags, dates, or commitments to fit a voice.
- Never apply a named profile or the example profile unless the user asked for it by name.
- Never apply the voice to the agent's own replies to the user. It is for text sent under the user's name.
- Preserve exact US spelling in quoted UI labels, CLI flags, API names, and code, whatever the profile's spelling rule.
- Do not commit `.local.md` files. They are gitignored for a reason.
