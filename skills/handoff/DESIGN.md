# Design Notes — `handoff`

Why this skill is shaped the way it is. Read `SKILL.md` for operational usage.

---

## 1. The Four Failure Modes of Existing Handoff Skills

Community `handoff` skills (such as `mattpocock/skills/handoff` and manual `HANDOFF.md` templates) solve context compaction across sessions, but fail the **"automagic zero-prompt resume"** test in four predictable ways:

1. **The `/tmp` Black Hole:** Writing `handoff.md` to `$TMPDIR` keeps git clean, but **zero** AI coding harnesses inspect `$TMPDIR` on startup. The human has to remember the temp filename, copy-paste it into the next tool, and lose everything if the OS reboots overnight.
2. **Harness Startup Fragmentation:** Even when `HANDOFF.md` sits in the repo root, no harness reads `HANDOFF.md` natively:
   - Antigravity (`agy`) and OpenAI Codex read `AGENTS.md`.
   - Claude Code reads `CLAUDE.md` and executes `.claude/settings.local.json` `SessionStart` hooks.
   - Gemini CLI reads `GEMINI.md` (supporting `@file` imports).
   - Cursor reads `.cursor/rules/*.mdc` (`alwaysApply: true`).
   Without wiring *all* of those entrypoints simultaneously, switching tools still requires manual prompting.
3. **Permanent `AGENTS.md` Pollution & Context Rot:** Agents told to "just append session state to `AGENTS.md`" blow past the 200-line `AGENTS.md` token budget (`continuous-alignment`), dirty `.gitignore`, and leave stale instructions steering sessions weeks later.
4. **Silent Post-Handoff Drift & Multi-Repo Blindness:** Real work often spans two or three sibling repositories (for example, a toolchain repo, a content repo, and a skills repo) and users occasionally edit files between sessions. A prose-only `HANDOFF.md` cannot tell the incoming agent *which* files changed after the snapshot was written, and opening the sibling repo in a sandboxed harness fails if `.handoff/HANDOFF.md` only exists in the first repo.

---

## 2. Structural Countermeasures in `handoff_ops.py`

### A. Evidence / Judgement Split (`Engineering Standard §S9`)
`handoff_ops.py` strictly separates mechanical collection from LLM synthesis:

```text
capture (mechanical facts) -> .handoff/manifest.json -\
                                                       +-> validate -> render -> .handoff/HANDOFF.md -> arm
LLM summary (judgement)    -> .handoff/state.json    -/
```

- `capture` records git branches, `HEAD` SHAs, recent commits, porcelain dirty status, and SHA-256 digests of watched/modified files across `--root` and `--extra-repo`. It emits zero scores, ratings, or prose conclusions, and scrubs credentials at ingest (`§S8`).
- `validate` checks `state.json` against required keys, scans every string leaf against `SECRET_PATTERNS`, and (under `--check-paths`) verifies that every artifact named in `active_focus` and `completed` actually exists on disk.

### B. Reversible Bounded Beacons + `.git/info/exclude`
- `arm` wraps every injected instruction in `<!-- HANDOFF:AUTO:START --> ... <!-- HANDOFF:AUTO:END -->` and records which files existed beforehand in `.handoff/armed.json`.
- Untracked local artefacts (`.handoff/`, `.cursor/rules/00-active-handoff.mdc`, `.claude/settings.local.json`, and newly created `GEMINI.md`) are registered inside `.git/info/exclude` rather than `.gitignore`, keeping `git status` free of untracked clutter without modifying a tracked file.
- `disarm` strips the bounded blocks, removes only the `_managed_by: "agent-skill-forge/handoff"` hook from `.claude/settings.local.json` (preserving all user permissions/hooks), deletes files created solely for the beacon, and optionally archives the consumed handoff under `.handoff/archive/<timestamp>/`. `TestEndToEndLifecycleAndDrift` proves byte-for-byte restoration of pre-existing `AGENTS.md` and `CLAUDE.md` files.

### C. Sandboxed Multi-Repo Federation (`--link-repo`)
When `--link-repo <sibling>` is passed to `arm`, `handoff_ops.py` mirrors `{manifest.json, state.json, HANDOFF.md}` into `<sibling>/.handoff/` and arms `<sibling>` as well. That ensures a sandboxed agent opened in *either* repository can read `.handoff/HANDOFF.md` locally without crossing filesystem sandbox boundaries, while a single `disarm` on the primary workspace cleans up every linked repo at once.
