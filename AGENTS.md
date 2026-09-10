# agent-skill-forge - Agent Invariants & Operations Guide

> [!IMPORTANT]
> This document contains hot invariants distilled continuously by the `continuous-alignment` engine.
> Keep all modifications within the 200-line budget limit.

---

## 1. Fast-Path Verification & Operational Commands

- Standard verification command: `python3.12 scripts/validate_skills.py`
- Standard sync command: `python3.12 scripts/sync_skills.py --prune --fix`
- Windows installer: `pwsh scripts/install.ps1`
- POSIX installer: `bash scripts/install.sh`

---

## 2. Critical Negative Constraints & Architectural Invariants

- You must always keep AGENTS.md under 200 lines to prevent token bloat.
- Never commit unencrypted API keys or passwords.
- **Work Slash Command Invariant (`/work`)**: When `/work` is triggered, the primary chat agent operates strictly as the Work Sentinel. It is STRICTLY FORBIDDEN from writing functional code or executing fixes directly on the primary thread. It MUST scaffold `.agents/` and delegate execution to subagents via `invoke_subagent`.

---

## 3. Verified Troubleshooting & Gotchas

- **Windows Symlink Privileges (WinError 1314)**: `os.symlink` fails without Developer Mode. Fall back to `_winapi.CreateJunction(src, dst)` for directory links on Windows.
- **Windows Python Binary & PATH**: The primary installed Python on this host is `python3.12` (at `~/.local/bin/python3.12.exe`). Generic `python`, `python3`, and `py` cmdlets are not registered. Always invoke `python3.12`.
- **Windows Console Encoding (cp1252)**: Wrap `sys.stdout`/`sys.stderr` with UTF-8 `TextIOWrapper` when `sys.platform == 'win32'` or prepend `$env:PYTHONUTF8 = '1'` to avoid `UnicodeEncodeError` on emojis/markdown.
- **No Inline Multi-Line Python in PowerShell**: NEVER pass multi-line or quote-heavy code via `pwsh -Command "python -c \"...\""`. PowerShell quote interpolation corrupts syntax. Always write Python logic to a scratch script (`<appDataDir>\brain\<id>\scratch\<name>.py`) via `write_to_file` and execute it cleanly via `python3.12 <path>`.
- **PowerShell Redirection Encoding**: Do not use raw `>` in pwsh to pipe script output to text files (defaults to UTF-16 LE/ANSI). Use Python's `open(..., 'w', encoding='utf-8')` or pwsh `Set-Content -Encoding utf8`.
- **Brain Directory Protection Boundary**: Antigravity tools (`list_dir`, `grep_search`) reject root `~/.gemini/antigravity/brain`. Run commands in pwsh targeting specific conversation subdirectories instead.
