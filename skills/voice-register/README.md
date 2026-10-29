# 🎙️ Voice Register Skill

Applies a person's writing voice and channel-specific register (quick email, stakeholder email, blog, strategy doc, notes) on top of [`unslop`](../unslop). `unslop` takes things out; `voice-register` adds the voice back in.

## Profile Resolution
1. `references/voice_and_tone.local.md`: private, gitignored
2. `~/.gemini/personas/default/voice_and_tone.md`: shared home persona
3. `references/voice_and_tone.template.md`: neutral baseline

Named profiles in `references/profiles/` (the author's is `ksprashu.md`) apply only when you ask for them or link one into tier 1 or 2:

```bash
mkdir -p ~/.gemini/personas/default
ln -s "$PWD/references/profiles/ksprashu.md" ~/.gemini/personas/default/voice_and_tone.md
```

To build your own profile, copy the template or run [`human-voice`](../human-voice) over your own logs.

## 👤 Attribution & Lineage
*   **Original Author**: Prashanth ([@ksprashu](https://github.com/ksprashu))
*   **License**: Apache-2.0
