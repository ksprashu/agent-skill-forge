# 🎙️ Voice Register Skill (`R1`-`R6`)

Applies a person's writing voice and channel-specific register (`R1` quick email, `R2` stakeholder email, `R3` technical blog, `R4` strategy doc/PRD, `R5` working notes, and `R6` technical dossiers/readouts/reports) alongside [`unslop`](../unslop). Out of the box, with no persona configured, it stays completely neutral (`tier 3`).

## Profile Resolution

The first match wins:

1. `references/voice_and_tone.local.md`: private override for this one install (gitignored).
2. `~/.gemini/personas/default/voice_and_tone.md`: your persona directory, shared by every harness on the machine.
3. `references/voice_and_tone.template.md`: the neutral fallback template.

If `voice-samples.md` sits next to the resolved profile, the skill uses it as few-shot examples across `R1`-`R6` (the bundled `examples/voice-samples.md` includes an `R6` dossier pair). `scripts/persona.py status` also reports optional `reader_pack` (`default/reader/profile.json`) and `characters_pack` (`default/characters/characters.json`) bundles when present, and `persona.py pull` / `persona.py activate` links any optional `rules/*.md` or `skills/*/` overlays from your persona repo into harnesses that are already installed. A named profile at `~/.gemini/personas/<name>/voice_and_tone.md` is used only when you ask for it by name (`persona.py status --name <name>`). When resolution falls through to the template (`tier 3`), its `<...>` placeholders are blanks, not a voice.

## Your Voice on Every Machine

Keep the persona directory in a **private** git repo and point the installer or skill at it with `--persona <owner>/agent-persona` or `AGENT_PERSONA_REPO`. The bundled `scripts/persona.py` clones and refreshes it.

### One-time: create your persona repo

1. Write a profile. Copy `references/voice_and_tone.template.md` to `~/.gemini/personas/default/voice_and_tone.md` and fill it in, or run [`human-voice`](../human-voice) over your own logs and edit the draft. Optionally add `default/voice-samples.md` (start from `examples/voice-samples.template.md`).
2. Push it to a private repo:
   ```bash
   cd ~/.gemini/personas
   git init -b main && git add -A && git commit -m "Add voice profile"
   gh repo create <owner>/agent-persona --private --source . --push
   ```

### Every machine

1. Sign in to GitHub so git can read the private repo: `gh auth login`.
2. Install the skills (passing `--persona <owner>/agent-persona` to fetch your private profile immediately, or run `bash scripts/install.sh` for a neutral public install):
   ```bash
   bash scripts/install.sh --persona <owner>/agent-persona
   ```
3. Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, or PowerShell `$PROFILE`) so daily refreshes stay automatic:
   ```bash
   export AGENT_PERSONA_REPO=<owner>/agent-persona
   ```
4. Check or refresh it anytime:
   ```bash
   python3 <skill-dir>/scripts/persona.py pull
   python3 <skill-dir>/scripts/persona.py status
   ```

## 👤 Attribution & Lineage
*   **Original Author & Architect**: Prashanth Subrahmanyam ([@ksprashu](https://github.com/ksprashu))
*   **License**: Apache-2.0
