# 🎙️ Voice Register Skill

Applies a person's writing voice and channel-specific register (quick email, stakeholder email, blog, strategy doc, notes) on top of [`unslop`](../unslop). `unslop` takes things out; `voice-register` adds the voice back in.

The voice applies only to text that goes out under your name: emails, posts, docs, PR descriptions and messages you send. The agent's explanations and replies to you stay neutral.

## Profile Resolution

The first match wins:

1. `references/voice_and_tone.local.md`: private override for this one install (gitignored).
2. `~/.gemini/personas/default/voice_and_tone.md`: your persona directory, shared by every harness on the machine.
3. `references/voice_and_tone.template.md`: the neutral baseline. The skill says no personal profile was found and keeps neutral prose.

If `voice-samples.md` sits next to the resolved profile, the skill uses it as few-shot examples. A named profile at `~/.gemini/personas/<name>/voice_and_tone.md` is used only when you ask for it by name.

No personal profile ships with this skill. `examples/example-profile.md` is a complete profile for a fictional person, there to show the format.

## Your Voice on Every Machine

Keep the persona directory in a **private** git repo and point the skill at it with one environment variable. The bundled `scripts/persona.py` clones and refreshes it.

### One-time: create your persona repo

1. Write a profile. Copy `references/voice_and_tone.template.md` to `~/.gemini/personas/default/voice_and_tone.md` and fill it in, or run [`human-voice`](../human-voice) over your own logs and edit the draft. Optionally add `default/voice-samples.md` (start from `examples/voice-samples.template.md`).
2. Push it to a private repo:
   ```bash
   cd ~/.gemini/personas
   git init -b main && git add -A && git commit -m "Add voice profile"
   gh repo create <you>/agent-persona --private --source . --push
   ```

### Every machine

1. Sign in to GitHub so git can read the private repo: `gh auth login`.
2. Install the skills: `npx skills add ksprashu/agent-skill-forge` (or `bash scripts/install.sh` from a clone).
3. Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, or PowerShell `$PROFILE`):
   ```bash
   export AGENT_PERSONA_REPO=<you>/agent-persona
   ```
4. Fetch it. Any of these works:
   - Do nothing. The first time the skill needs a profile, it runs `persona.py pull`, which clones the repo to `~/.gemini/personas`.
   - Run the forge installer. When `AGENT_PERSONA_REPO` is set, it pulls the persona after linking skills.
   - Run `python3 <skill-dir>/scripts/persona.py pull` yourself (`<skill-dir>` is where this skill was installed, e.g. `~/.claude/skills/voice-register`).
5. Check it: `python3 <skill-dir>/scripts/persona.py status` should report `tier 2` and your repo.

### How `persona.py` behaves

| Situation | `pull` does |
|---|---|
| `AGENT_PERSONA_REPO` unset, no persona directory | Nothing. The skill stays neutral. |
| Variable set, directory missing or empty | Clones the repo (with `gh` for `owner/name` if installed, else `https://github.com/owner/name.git`; any git URL or path works too). |
| Directory is a git clone | `git pull --ff-only`, at most once every 24 hours. `--force` pulls now. |
| Pull fails (offline, signed out) | Keeps using the local copy and says why. |
| Directory exists but isn't a git clone | Leaves it alone and tells you to move it aside. It never overwrites a hand-made profile. |

Exit codes: `0` a personal profile resolves, `1` neutral template only, `2` error (clone failed, named profile missing). It never prompts for credentials, and every git call times out after 30 seconds.

Settings:

- `AGENT_PERSONA_REPO`: `owner/name`, a git URL, or a local path. The only setting most people need.
- `AGENT_PERSONA_DIR`: use a directory other than `~/.gemini/personas`.

### Editing

Edit the files in `~/.gemini/personas` and commit and push from there. The change applies on this machine at once, and other machines pick it up on their next daily pull.

## What a Public User Sees

Someone who installs this skill without setting `AGENT_PERSONA_REPO` gets:

- No network calls and no fetched profile.
- Neutral `unslop` prose from the agent and in drafts.
- When they ask for "my voice", a note that no personal profile was found, with a pointer to the template and `human-voice`.

To get their own voice, they follow the steps above with their own private repo. They can't reach anyone else's: persona repos are private, and the public skill names none.

## 👤 Attribution & Lineage
*   **Original Author**: Prashanth ([@ksprashu](https://github.com/ksprashu))
*   **License**: Apache-2.0
