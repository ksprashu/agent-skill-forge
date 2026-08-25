# ⚙️ Installer Specification

## Global Directories Managed
The installer (`sync_skills.py`) maintains clean symlinks across:
1. `~/.agents/skills/` (Universal AI Agent hub)
2. `~/.gemini/skills/` (Gemini CLI)
3. `~/.gemini/config/skills/` (Google Antigravity IDE)
4. `~/.claude/skills/` (Claude Code)
5. `~/.gemini/antigravity-cli/skills/` (Antigravity CLI)

## Project-Scoped Bootstrapping
When invoked with `--project <PATH> --skills <NAMES>`, the installer creates symlinks directly into:
- `<PATH>/.gemini/skills/<SKILL>`
- `<PATH>/.agents/skills/<SKILL>`
