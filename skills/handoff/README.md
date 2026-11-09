# 🤝 Handoff Skill (`/handoff`, `/handover`)

Packages multi-repository session state, locked decisions, and cryptographic SHA-256 file digests into `.handoff/HANDOFF.md`, and arms reversible **Turn-0 auto-pickup beacons** so a fresh session in **Google Antigravity (`agy`)**, **Claude Code**, **OpenAI Codex**, or **Cursor** resumes seamlessly without manual copy-pasting.

---

## Why `/handoff` Exists (vs. `/compact`)

- **`/compact`** compresses history *inside the same session of one harness*.
- **`/handoff`** serializes state **across boundaries**: switching coding tools mid-feature, starting a clean context window on a multi-day arc, coordinating across sibling repositories, or handing an active branch to a teammate.

Community handoff skills either write prose to `$TMPDIR` (wiped across reboots and invisible to workspace startup hooks) or leave an unwired `HANDOFF.md` in the repository root that dirties `git status` and still requires manual copy-pasting. `skills/handoff` solves both problems through a stdlib-only engine (`scripts/handoff_ops.py`).

---

## Quick Usage

### 1. Outgoing Session (Save & Arm)
Invoke **`/handoff`** (or **`/handoff <next session focus>`**) in your active agent, or run the four deterministic stages directly:

```bash
# 1. Collect mechanical git branches, HEAD SHAs, porcelain dirty files & SHA-256 digests
python3 <skill-dir>/scripts/handoff_ops.py capture \
  --root . \
  --extra-repo ~/path/to/sibling-repo

# 2. Validate structured judgement (.handoff/state.json) for schema, secrets & CWE-22 path confinement
python3 <skill-dir>/scripts/handoff_ops.py validate \
  --state .handoff/state.json \
  --manifest .handoff/manifest.json \
  --check-paths

# 3. Compile .handoff/HANDOFF.md
python3 <skill-dir>/scripts/handoff_ops.py render \
  --manifest .handoff/manifest.json \
  --state .handoff/state.json \
  --out .handoff/HANDOFF.md \
  --check-paths

# 4. Arm reversible Turn-0 startup beacons (and optionally mirror into sibling repos)
python3 <skill-dir>/scripts/handoff_ops.py arm \
  --root . \
  --link-repo ~/path/to/sibling-repo
```

### 2. Incoming Session (Zero-Prompt Resume)
Open **Antigravity (`agy`)**, **Claude Code (`claude`)**, **OpenAI Codex (`codex`)**, or **Cursor** in the workspace and type `"Continue"`. The incoming agent automatically:
1. Receives the Turn-0 startup beacon / `SessionStart` injection.
2. Runs `handoff_ops.py status --root .` to detect any out-of-band file modifications, branch switches, or commits since capture.
3. Loads the recommended skills (`suggested_skills`) and resumes from **Next Immediate Action #1**.

### 3. Disarm & Archive When Consumed
Once steady-state work has resumed, clean up all startup beacons (restoring pre-existing `AGENTS.md`, `CLAUDE.md`, and `.claude/settings.local.json` byte-for-byte) and archive the consumed handoff:

```bash
python3 <skill-dir>/scripts/handoff_ops.py disarm --root . --archive
```

---

## Turn-0 Auto-Pickup Matrix

| AI Coding Tool | Native Startup Entrypoint | What `handoff_ops.py arm` Wires |
| :--- | :--- | :--- |
| **Google Antigravity (`agy` IDE & CLI)** | Injects workspace `AGENTS.md` into `<user_rules>` on Turn 0 | Bounded `<!-- HANDOFF:AUTO:START -->` beacon at top of `AGENTS.md` |
| **Claude Code (`claude` CLI & IDE)** | Reads `CLAUDE.md` (`@path` expansion) + `.claude/settings.local.json` `SessionStart` hooks | **Double-wired:** `CLAUDE.md` `@.handoff/HANDOFF.md` import + `SessionStart` hook (`status --root . --inject`) |
| **OpenAI Codex (`codex`)** | Walks workspace `AGENTS.md` on session start | Bounded `AGENTS.md` beacon + `~/.agents/skills/handoff` |
| **Cursor (Agent / Composer)** | Injects `.cursor/rules/*.mdc` rules with `alwaysApply: true` | `.cursor/rules/00-active-handoff.mdc` (`alwaysApply: true`) + `AGENTS.md` |

All untracked local files (`.handoff/`, `.cursor/rules/00-active-handoff.mdc`, `.claude/settings.local.json`, and any newly created `AGENTS.md` / `CLAUDE.md`) are hidden via `.git/info/exclude` so tracked `.gitignore` files remain untouched.

---

## CLI Subcommand Reference (`scripts/handoff_ops.py`)

| Subcommand | Key Flags | Purpose |
| :--- | :--- | :--- |
| `capture` | `--root`, `--extra-repo`, `--watch-file`, `--out` | Collects purely factual git/digest snapshot into `.handoff/manifest.json`; redacts credentials at ingest. |
| `validate` | `--state`, `--manifest`, `--check-paths` | Audits `state.json` schema, 8 secret/token regexes, and workspace-confined artifact paths (exits `1` on violation). |
| `render` | `--manifest`, `--state`, `--out`, `--check-paths` | Validates inputs and renders `.handoff/HANDOFF.md`. |
| `arm` | `--root`, `--link-repo`, `--no-tracked-edits` | Idempotently installs Turn-0 beacons across all harnesses and mirrors sandbox-local copies to linked repos. |
| `status` | `--root`, `--json`, `--inject` | Checks post-handoff branch, `HEAD`, porcelain working-tree, and SHA-256 file drift; `--inject` emits Turn-0 hook output. |
| `disarm` | `--root`, `--archive` | Restores pre-existing instruction/settings files byte-for-byte, removes temporary beacons, and archives consumed state. |

---

## 👤 Attribution & Lineage
* **Author**: [@ksprashu](https://github.com/ksprashu) for `agent-skill-forge`
* **Ecosystem Inspirations**: Matt Pocock (`mattpocock/skills/handoff`), Compound Engineering (`EveryInc/compound-engineering-plugin` `ce-handoff`), and `REMvisual/claude-handoff`
* **License**: Apache-2.0
