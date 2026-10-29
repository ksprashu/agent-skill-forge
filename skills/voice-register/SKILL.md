---
name: voice-register
description: "Apply a person's writing voice and channel-specific register (quick internal email, stakeholder email, technical blog, strategy doc, working notes) on top of unslop. Use when asked to write or rewrite something in my voice, as me, or in a given register. Resolves a voice profile from a local override, the shared home persona, or the bundled template."
---

# Voice Register — Personal Style and Channel Registers

Write in a specific person's voice, in the register that fits the channel. This skill is additive: it applies spelling, punctuation, lexicon, greetings, and structure from a voice profile. It does not strip AI smells; run `unslop` for that.

## Core Workflow

1. **Resolve the voice profile** (first match wins):
   1. `references/voice_and_tone.local.md`: private override on this machine (gitignored).
   2. `~/.gemini/personas/default/voice_and_tone.md`: shared home persona. `copy-write` reads the same file, so one profile drives both skills.
   3. `references/voice_and_tone.template.md`: neutral public baseline. Use it to bootstrap a profile; it carries no personal voice.

   `references/profiles/` holds named, committed profiles (for example `ksprashu.md`, the author's card). They are never applied implicitly. Use one only when the user names it, or when one of tiers 1 or 2 is a copy of or link to it.
2. **Run `unslop` hygiene first.** Remove AI smells, throat-clearing, `-ing` tails, and wrappers before adding any voice.
3. **Pick the channel register** from `references/channel-registers.md`: R1 quick internal email, R2 stakeholder or external email, R3 technical blog, R4 strategy doc or proposal, R5 working notes and comments. Infer it from the request (recipient, medium, length). Ask only when two registers would produce materially different output.
4. **Apply the profile's fingerprints** for that register: spelling, punctuation, transitions, lexicon, greeting, body shape, sign-off.
5. **Respect the live vs. polished boundary.** Shorthand the profile marks as live-only stays out of polished docs and external email.
6. **Verify** that facts, numbers, names, flags, and commitments are unchanged. Voice changes how something is said, never what is said.

## References

- `references/channel-registers.md`: what each register controls, independent of any one person.
- `references/voice_and_tone.template.md`: blank profile to copy into tier 1 or 2.
- `references/profiles/ksprashu.md`: the author's empirical voice card, a worked example of a full profile.
- `examples/voice-samples.md`: before/after rewrites across registers using the author's profile.
- `examples/voice-samples.template.md`: blank sample sheet for your own profile.

## Building Your Own Profile

Copy `references/voice_and_tone.template.md` to `~/.gemini/personas/default/voice_and_tone.md` and fill it in. Or run `human-voice` to extract markers from your own logs, then edit the result. Keep anything private in the `.local.md` tier.

## Hard Constraints

- Never change facts, figures, flags, dates, or commitments to fit a voice.
- Never apply a named profile from `references/profiles/` unless the user asked for it or tier 1 or 2 points at it.
- Preserve exact US spelling in quoted UI labels, CLI flags, API names, and code, whatever the profile's spelling rule.
- Do not commit `.local.md` files. They are gitignored for a reason.
