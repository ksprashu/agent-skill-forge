---
trigger: always_on
description: Mandatory operational invariants for executing Python and shell commands in Windows PowerShell environments.
---

# Windows PowerShell & Python Operational Discipline

## 1. Executable Resolution
- The primary Python executable on this environment is `python3.12` (located in `~/.local/bin/python3.12.exe`).
- Do NOT invoke `python`, `py`, or `python3` directly without verifying availability, as they are not mapped cmdlets.

## 2. Scratch Script Invariant (Prohibition on Complex Inline `-c`)
- NEVER attempt complex, multi-line, or quote-nested Python code inside PowerShell `-Command "python -c \"...\""`.
- PowerShell argument parsing strips quotes and escapes inconsistently, causing syntax crashes.
- **Mandatory Procedure**:
  1. Create a `.py` file in the conversation scratch directory (`<appDataDir>\brain\<conversation-id>\scratch\<name>.py`) using `write_to_file`.
  2. Execute the script with `python3.12 "<path>"`.

## 3. Strict UTF-8 Encoding & Console Safety
- Always guard scripts that print non-ASCII or markdown symbols with:
  ```python
  import sys, io
  if sys.platform == "win32":
      sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
      sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
  ```
- Avoid PowerShell `>` output redirection to disk files; it defaults to ANSI/UTF-16LE. Write files directly within Python using `open(path, "w", encoding="utf-8")`.

## 4. Antigravity System Protection Boundaries
- Direct `read_file`, `list_dir`, and `grep_search` on root `~/.gemini/antigravity` and `~/.gemini/antigravity/brain` trigger hardcoded system protection boundary errors.
- Query individual nested conversation paths or run targeted PowerShell queries.

## 5. Antigravity Permission Engine & Project Configuration Hierarchy
- **Project Isolation Precedence**: Antigravity checks the active project file (`~/.gemini/config/projects/<id>.json`) before falling back to global settings (`~/.gemini/config/config.json`). If a project file exists, its `settings` and `permissionGrants` must be synchronized to prevent shadowing global grants.
- **Explicit Binary Wildcards**: Antigravity token matching on commands requires explicit coverage for the exact binary invoked. Use `command(python3.12*)`, `command(python3.12 *)`, and `command(python3.12 **)` in addition to generic python rules.
- **Zero Global Write Invariant**: No global `write_file` grants must exist. All file writes outside the workspace require interactive user consent.

