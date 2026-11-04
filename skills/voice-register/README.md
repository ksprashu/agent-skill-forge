# 🎙️ Voice Register Skill

Applies a person's writing voice and channel-specific register (quick email, stakeholder email, blog, strategy doc, notes) on top of [`unslop`](../unslop). `unslop` takes things out; `voice-register` adds the voice back in.

## Profile Resolution
1. `references/voice_and_tone.local.md`: private, gitignored
2. `~/.gemini/personas/default/voice_and_tone.md`: shared with `copy-write`
3. `references/voice_and_tone.template.md`: neutral baseline

No personal profile ships with this skill. Keep yours outside the repo, at `~/.gemini/personas/default/voice_and_tone.md` (or a named one at `~/.gemini/personas/<name>/voice_and_tone.md`, used only when you ask for it by name).

To build your own profile, copy the template or run [`human-voice`](../human-voice) over your own logs. `examples/example-profile.md` shows a complete profile for a fictional person.

## 👤 Attribution & Lineage
*   **Original Author**: Prashanth ([@ksprashu](https://github.com/ksprashu))
*   **License**: Apache-2.0
