# agent-skill-forge - Agent Invariants & Operations Guide

> [!IMPORTANT]
> This document contains hot invariants distilled continuously by the `continuous-alignment` engine.
> Keep all modifications within the 200-line budget limit.

---

## 1. Fast-Path Verification & Operational Commands

- Standard verification command: `python3 scripts/validate_skills.py`
- Test suite: `python3 -m pytest -q` (E2E DAG suite: `python3 tests/e2e/run_e2e_tests.py`)
- Standard sync command: `python3 scripts/sync_skills.py --prune --fix`
- Windows installer: `pwsh scripts/install.ps1`
- POSIX installer: `bash scripts/install.sh`
- Install check for `npx skills` users: `npx skills add . --list`

---

## 2. Critical Negative Constraints & Architectural Invariants

- **Engineering Standard (normative)**: Read `docs/ENGINEERING_STANDARD.md` before adding any skill, script, verifier, gate, or test. It defines the script contract, the verifier contract (known-bad fixture first), the six required test patterns, the L1-L4 enforcement ladder, and the definition of done.
- **Executor Invariant**: Any claim using the words *gate*, *verify*, *audit*, *veto*, *certified*, *pass*, or *score* MUST have a function behind it that exits non-zero on failure. Agent self-reports are not enforcement. A gate name may not appear in a SKILL.md before its predicate and its rejection test exist.
- You must always keep AGENTS.md under 200 lines to prevent token bloat.
- **Branch + PR Invariant**: Never commit or push to `main`. Work on a branch and open a PR; the `main-via-pr` ruleset and the `pr-guardian/verdict` check gate the merge.
- **Skill Format Invariant**: Skills follow the `npx skills` format: `skills/<name>/SKILL.md` with `name` (matching the folder) and `description` frontmatter, optional `license` and `metadata.*`, and no harness-specific keys. A skill must work from its own folder after `npx skills add`; call bundled scripts as `<skill-dir>/scripts/...`, never by repo-relative path.
- Never commit unencrypted API keys or passwords.
- **Work Slash Command Invariant (`/work`)**: When `/work` is triggered, the primary chat agent operates strictly as the Work Sentinel. It is STRICTLY FORBIDDEN from writing functional code or executing fixes directly on the primary thread. It MUST scaffold `.agents/` and delegate execution to subagents using the harness's subagent tool.
- **Reserved Namespace Invariant**: Never name skills or aliases after Antigravity native slash commands (`grill-me`, `teamwork-preview`, `voice`, `goal`, `boost`, etc.) or built-in skills (`agy-customizations`, `antigravity_guide`, `generative_ui`, `migrate-workflows`, `permissioned-github`). Higher-priority forge links mask native Antigravity system features.

---

## 3. Verified Troubleshooting & Gotchas

- **Windows Symlink Privileges (WinError 1314)**: `os.symlink` fails without Developer Mode. Fall back to `_winapi.CreateJunction(src, dst)` for directory links on Windows.
- **Python Binary**: Commands here use `python3`. On a Windows host where only a versioned binary such as `python3.12` is on PATH, substitute it.
- **Windows Console Encoding (cp1252)**: Wrap `sys.stdout`/`sys.stderr` with UTF-8 `TextIOWrapper` when `sys.platform == 'win32'` or prepend `$env:PYTHONUTF8 = '1'` to avoid `UnicodeEncodeError` on emojis/markdown.
- **No Inline Multi-Line Python in PowerShell**: NEVER pass multi-line or quote-heavy code via `pwsh -Command "python -c \"...\""`. PowerShell quote interpolation corrupts syntax. Always write Python logic to a scratch script and run it as `python3 <path>`.
- **PowerShell Redirection Encoding**: Do not use raw `>` in pwsh to pipe script output to text files (defaults to UTF-16 LE/ANSI). Use Python's `open(..., 'w', encoding='utf-8')` or pwsh `Set-Content -Encoding utf8`.
- **Brain Directory Protection Boundary**: Antigravity tools (`list_dir`, `grep_search`) reject root `~/.gemini/antigravity/brain`. Run commands in pwsh targeting specific conversation subdirectories instead.
