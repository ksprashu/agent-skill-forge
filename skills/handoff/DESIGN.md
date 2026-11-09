# Design Notes — `handoff`

Why this skill is shaped the way it is. Read `SKILL.md` for operational usage.

---

## 1. The Four Failure Modes of Existing Handoff Skills

Community handoff skills (such as `mattpocock/skills/handoff`, `EveryInc/compound-engineering-plugin` `ce-handoff`, and `REMvisual/claude-handoff`) solve context compaction across sessions, but fail the **"automagic zero-prompt cross-tool resume"** test in four predictable ways:

1. **The `$TMPDIR` Sandbox & Startup Black Hole:** Writing `handoff.md` to `$TMPDIR` (`/tmp/...`) keeps git clean, but **zero** AI coding harnesses inspect `$TMPDIR` on startup, OS reboots wipe `/tmp`, and sandboxed harnesses (`Codex`, `Antigravity`, `Claude Code`) frequently restrict filesystem reads outside `<workspace>/` and explicitly whitelisted directories.
2. **Harness Startup Fragmentation:** Even when `HANDOFF.md` sits inside the repo, no harness reads `HANDOFF.md` natively:
   - Google Antigravity (`agy` IDE & CLI) and OpenAI Codex read `AGENTS.md`.
   - Claude Code reads `CLAUDE.md` (`@path` file imports) and executes `.claude/settings.local.json` `SessionStart` hooks.
   - Cursor reads `.cursor/rules/*.mdc` (`alwaysApply: true`).
   Without wiring *all* of those entrypoints simultaneously, switching tools still requires manual copy-pasting.
3. **Permanent `AGENTS.md` Pollution & Non-Idempotent Cleanup:** Appending session state directly to `AGENTS.md` blows past the 200-line `AGENTS.md` token budget (`continuous-alignment`), dirties `.gitignore`, and leaves stale instructions steering sessions weeks later. Naive re-runs also lose track of which files existed before arming.
4. **Silent Post-Handoff Drift & Multi-Repo Blindness:** Real work often spans two or three sibling repositories and developers occasionally edit files or switch branches between sessions. A prose-only `HANDOFF.md` cannot tell the incoming agent *which* files or git refs drifted after capture.

---

## 2. Structural Countermeasures in `handoff_ops.py`

### A. Evidence / Judgement Split (`Engineering Standard §S9`)
`handoff_ops.py` strictly separates mechanical collection from LLM synthesis:

```text
capture (mechanical facts) -> .handoff/manifest.json -\
                                                       +-> validate -> render -> .handoff/HANDOFF.md -> arm
LLM summary (judgement)    -> .handoff/state.json    -/
```

- `capture` records git branches, `HEAD` SHAs, recent commits, porcelain v1 dirty status (preserving leading status columns), and SHA-256 digests of watched/modified files across `--root` and `--extra-repo`. It emits zero scores, ratings, or prose conclusions, and scrubs credentials at ingest (`§S8`).
- `validate` checks `state.json` against required keys, scans every string leaf against `SECRET_PATTERNS`, and (under `--check-paths`) verifies that every artifact named in `active_focus` and `completed` resolves strictly inside one of the captured workspace roots (`CWE-22` path-traversal confinement).
- `arm` re-runs `validate_state_dict` before writing any beacon and shell-quotes script paths (`shlex.quote`) in hook commands.

### B. Idempotent Bounded Beacons + `.git/info/exclude`
- `arm` wraps every injected instruction in `<!-- HANDOFF:AUTO:START --> ... <!-- HANDOFF:AUTO:END -->` and persists pre-arm ownership metadata in `.handoff/armed.json`. Re-running `arm` or `capture` while already armed preserves `created_files` and `claude_settings_existed` so idempotency never corrupts restoration state.
- Untracked local artefacts (`.handoff/`, `.cursor/rules/00-active-handoff.mdc`, `.claude/settings.local.json`, and newly created `AGENTS.md` / `CLAUDE.md`) are registered inside `.git/info/exclude` rather than `.gitignore`, keeping `git status` clean without modifying tracked files.
- `compute_drift` checks four orthogonal signals: git branch switches, `HEAD` SHA movement, live `git status --porcelain=v1` working-tree transitions (ignoring beacon-only edits on `AGENTS.md` / `CLAUDE.md`), and SHA-256 file digest changes.
- `disarm` strips bounded blocks, removes only the `_managed_by: "agent-skill-forge/handoff"` hook from `.claude/settings.local.json` (preserving user permissions/hooks), deletes files created solely for the beacon, and optionally archives the consumed handoff under `.handoff/archive/<timestamp>/`. `TestEndToEndLifecycleAndDrift` proves byte-for-byte restoration even across repeated `arm` + `capture` cycles.

### C. Sandboxed Multi-Repo Federation (`--link-repo`)
When `--link-repo <sibling>` is passed to `arm`, `handoff_ops.py` mirrors `{manifest.json, state.json, HANDOFF.md}` into `<sibling>/.handoff/` and arms `<sibling>` as well. That ensures a sandboxed agent opened in *either* repository can read `.handoff/HANDOFF.md` locally without crossing filesystem sandbox boundaries, while a single `disarm` on the primary workspace cleans up every linked repo at once.
