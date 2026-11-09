---
name: handoff
description: Package full multi-repo session state, locked decisions, and cryptographic drift digests into `.handoff/HANDOFF.md`, and arm zero-prompt auto-pickup beacons so any AI coding tool (Claude Code, Antigravity, Gemini CLI, Codex, Cursor) resumes automatically on Turn 1. Trigger via /handoff or /handover.
disable-model-invocation: true
---

# Automagic Cross-Harness Session Handoff

Serialize an active engineering or authoring session into a verified, secret-redacted `.handoff/` bundle and arm reversible auto-pickup beacons so the next AI coding tool or fresh session picks up seamlessly on Turn 1 without manual copy-pasting.

---

## 🎯 When to Use `/handoff` vs `/compact`

- **`/compact`**: Compresses history *inside the same session and harness*.
- **`/handoff`**: Transfers state **across boundaries** — switching harnesses (e.g., Antigravity -> Claude Code -> Cursor -> Codex -> Gemini CLI), starting a clean context window on a multi-day series, spanning multiple repositories, or handing work to a teammate.

---

## 📋 Outgoing Agent Workflow (Saving & Arming the Handoff)

Execute these four steps in order whenever the user invokes `/handoff` (or asks to save state and resume in another tool/session):

### Step 1: Capture Mechanical Workspace & Git Truth (`manifest.json`)
Run the stdlib collector (`<skill-dir>/scripts/handoff_ops.py`) on the primary workspace and pass `--extra-repo` for every additional repository touched during the session:

```bash
python3 <skill-dir>/scripts/handoff_ops.py capture \
  --root . \
  --extra-repo ~/path/to/sibling-repo \
  --watch-file path/to/active-file.md
```

This creates `<root>/.handoff/manifest.json` (git branch, `HEAD` SHA, recent commits, dirty/untracked files, and SHA-256 digests of active files), redacts secrets at capture, and adds `.handoff/` to `.git/info/exclude` so `git status` stays clean.

### Step 2: Author Structured Judgement (`.handoff/state.json`)
Read `references/state-schema.md` for the exact JSON contract, then write `<root>/.handoff/state.json`.

**Authoring rules:**
1. **Never duplicate large files on disk:** Link to existing PRDs, specs, blogs, codelabs, or scripts by path in `active_focus.active_files` and `completed[*].artifacts`.
2. **Preserve hard-won corrections in `locked_decisions`:** Record every non-negotiable user preference, naming rule, URL correction, or architectural constraint discovered during the session so the next tool never regresses.
3. **Make `next_actions` immediately executable:** Write ordered steps (`1, 2, 3`) with the exact command or prompt and expected outcome. If the user passed arguments to `/handoff <next focus>`, tailor `next_actions` around that focus.
4. **Name `suggested_skills`:** List the exact skills (e.g., `codelab`, `voice-register`, `unslop`, `atelier`, `test`, `review`) the resuming agent should read before editing.

### Step 3: Validate & Render `.handoff/HANDOFF.md`
Run the deterministic verifier and renderer (exits non-zero on schema errors, secret/token leaks, or hallucinated artifact paths):

```bash
python3 <skill-dir>/scripts/handoff_ops.py validate \
  --state .handoff/state.json \
  --manifest .handoff/manifest.json \
  --check-paths

python3 <skill-dir>/scripts/handoff_ops.py render \
  --manifest .handoff/manifest.json \
  --state .handoff/state.json \
  --out .handoff/HANDOFF.md \
  --check-paths
```

### Step 4: Arm Zero-Prompt Auto-Pickup Beacons Across All Harnesses
Read `references/harness-autostart.md` if customising harness behaviour, then arm the workspace (and mirror to any sibling `--link-repo` where the user might open the next session):

```bash
python3 <skill-dir>/scripts/handoff_ops.py arm \
  --root . \
  --link-repo ~/path/to/sibling-repo
```

What `arm` wires automatically (and `.git/info/exclude` hides from untracked noise):
- **Antigravity IDE/CLI, OpenAI Codex, Windsurf:** Bounded `<!-- HANDOFF:AUTO:START -->` beacon at the top of `AGENTS.md`.
- **Claude Code:** Deterministic `SessionStart` hook in `.claude/settings.local.json` (`status --inject` pipes live drift check + `HANDOFF.md` straight into Turn 0 context) plus `@.handoff/HANDOFF.md` beacon in `CLAUDE.md` when present.
- **Gemini CLI:** Bounded `@.handoff/HANDOFF.md` import beacon in `GEMINI.md`.
- **Cursor:** `.cursor/rules/00-active-handoff.mdc` with `alwaysApply: true`.

*(Pass `--no-tracked-edits` if a strict repo forbids temporary edits to tracked `AGENTS.md` / `CLAUDE.md` files.)*

---

## 🔄 Incoming Agent Workflow (Resuming Automagically)

When starting a session in a workspace containing `.handoff/HANDOFF.md` (or when triggered by an auto-pickup beacon):

1. **Check Drift First:** Run `python3 <skill-dir>/scripts/handoff_ops.py status --root .` to verify whether any watched files or `git HEAD` commits changed after the handoff was captured. If drift is reported, re-read the drifted files before editing.
2. **Load Suggested Skills:** Read the `SKILL.md` files listed under **Suggested Skills** in `.handoff/HANDOFF.md`.
3. **Confirm & Execute:** Greet the user in 3–5 concise lines confirming the loaded mission, drift status, and **Next Immediate Action #1**, then execute directly (or ask if an item in **Open Questions** blocks progress).
4. **Disarm When Consumed:** Once steady-state work has resumed and you no longer want future sessions to replay the old handoff, disarm and archive:
   ```bash
   python3 <skill-dir>/scripts/handoff_ops.py disarm --root . --archive
   ```
   `disarm` restores `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.claude/settings.local.json` byte-for-byte and archives the consumed bundle under `.handoff/archive/<UTC-timestamp>/`.

---

## 🚫 Hard Constraints

- **NEVER** store raw API keys, OAuth tokens, passwords, or private keys in `state.json` or `HANDOFF.md` — `validate` blocks on secret patterns because handoff files travel across tools and logs.
- **NEVER** write handoff files only to `/tmp` or `$TMPDIR` unless explicitly requested — OS temp directories are invisible to workspace startup hooks and wiped across reboots.
- **NEVER** edit `.gitignore` to hide `.handoff/` — `handoff_ops.py` writes to `.git/info/exclude` so tracked repository files stay untouched.
- **NEVER** skip `--check-paths` when validating completed or active workspace files — hallucinated paths send the resuming agent on a wild-goose chase on Turn 1.
