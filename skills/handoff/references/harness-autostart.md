# Cross-Harness Automagic Pickup Matrix

How `handoff_ops.py arm` makes every major AI coding tool load `.handoff/HANDOFF.md` automatically on Turn 1 without the user needing to paste file paths.

---

## Harness Entrypoint Matrix

| AI Coding Tool / Harness | Native Startup Mechanism | What `handoff_ops.py arm` Installs | How Turn 1 Behaves |
| :--- | :--- | :--- | :--- |
| **Claude Code** (`claude`) | Executes `.claude/settings.local.json` `SessionStart` hooks (`stdout` injected directly into Turn 0 context) + reads `CLAUDE.md` | Adds `_managed_by: "agent-skill-forge/handoff"` `SessionStart` hook (`handoff_ops.py status --root . --inject`) + bounded `@.handoff/HANDOFF.md` block in `CLAUDE.md` (if present) | **100% deterministic Turn-0 injection:** Before the user types anything, Claude receives both the live SHA-256 drift report and the complete `HANDOFF.md`. |
| **Google Antigravity** (`agy` IDE & CLI) | Automatically loads workspace `AGENTS.md` into `<user_rules>` on every turn | Prepends a compact 6-line bounded `<!-- HANDOFF:AUTO:START -->` beacon to `AGENTS.md` | Antigravity sees the mandatory `ACTIVE SESSION HANDOFF` rule in `<user_rules>`, reads `.handoff/HANDOFF.md` immediately, checks drift, and continues. |
| **Gemini CLI** (`gemini`) | Automatically loads workspace `GEMINI.md` and expands `@path` file imports | Prepends a bounded beacon + `@.handoff/HANDOFF.md` import to `GEMINI.md` (excluded via `.git/info/exclude` if newly created) | Gemini CLI expands `@.handoff/HANDOFF.md` straight into initial session memory at startup. |
| **OpenAI Codex** (`codex`) | Automatically loads workspace `AGENTS.md` across repo hierarchy | Uses the bounded `AGENTS.md` beacon | Codex reads `AGENTS.md` at boot, inspects `.handoff/HANDOFF.md`, and resumes from Action #1. |
| **Cursor** (Agent / Composer) | Automatically injects `.cursor/rules/*.mdc` rules marked `alwaysApply: true` | Creates `.cursor/rules/00-active-handoff.mdc` (`alwaysApply: true`, excluded via `.git/info/exclude`) + `AGENTS.md` beacon | Every new Cursor Composer / Agent chat receives the active handoff rule automatically. |
| **Windsurf / Amp / Jules** | Reads `AGENTS.md` at workspace root | Uses the bounded `AGENTS.md` beacon | Picks up `.handoff/HANDOFF.md` on the first turn. |

---

## Multi-Repo Sessions (`--extra-repo` + `--link-repo`)

When a session modifies files across multiple repositories (for example, `content`, `creative-stack`, and `agent-skill-forge`):

1. Pass `--extra-repo <sibling>` during `capture` so `manifest.json` records git branches, `HEAD` commits, dirty files, and SHA-256 digests across **every** repo.
2. Pass `--link-repo <sibling>` during `arm` so `.handoff/{manifest.json,state.json,HANDOFF.md}` and the startup beacons are mirrored into each sibling repo as well.
3. Whichever repository directory the user opens in the new AI tool, `.handoff/HANDOFF.md` is locally readable inside that workspace's sandbox boundary.
4. Running `handoff_ops.py disarm --root <primary> --archive` automatically disarms both the primary workspace and every linked repository recorded in `.handoff/armed.json`.
