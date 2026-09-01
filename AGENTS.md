# agent-skill-forge - Agent Invariants & Operations Guide

> [!IMPORTANT]
> This document contains hot invariants distilled continuously by the `continuous-alignment` engine.
> Keep all modifications within the 200-line budget limit.

---

## 1. Fast-Path Verification & Operational Commands

- Standard verification command: `python3 scripts/validate_skills.py`
- Standard sync command: `python3 scripts/sync_skills.py --prune --fix`
- Windows installer: `pwsh scripts/install.ps1`
- POSIX installer: `bash scripts/install.sh`

---

## 2. Critical Negative Constraints & Architectural Invariants

- You must always keep AGENTS.md under 200 lines to prevent token bloat.
- Never commit unencrypted API keys or passwords.

---

## 3. Verified Troubleshooting & Gotchas

- **Windows Symlink Privileges (WinError 1314)**: `os.symlink` fails without Developer Mode. Fall back to `_winapi.CreateJunction(src, dst)` for directory links on Windows.
- **Windows Console Encoding (cp1252)**: Wrap `sys.stdout`/`sys.stderr` with UTF-8 `TextIOWrapper` when `sys.platform == 'win32'` to avoid `UnicodeEncodeError`.
- **Windows Python Binaries**: Fallback search across `python3.12`, `python3.13`, `py`, `python3`, `python`.
