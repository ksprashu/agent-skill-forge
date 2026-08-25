---
name: sync
description: Scans canonical skill source repositories in ~/code/github and manages symlinks across global skill directories and project workspaces. Trigger via `/sync` or `/skill-sync` to audit, repair, or bootstrap skills.
disable-model-invocation: true
---

# Skill Sync - Canonical Skill Symlink & JIT Bootstrapper

Use this skill whenever you need to verify, audit, repair, or synchronize custom AI agent skills across user skill directories, or bootstrap curated project-scoped skills into an active workspace.

## Overview
Canonical skill sources are maintained in individual git repositories under `~/code/github/`. To ensure agents across Antigravity IDE, Antigravity CLI, Gemini CLI, Claude, and Cline have access to skills without duplicating files, `sync` maintains symlinks across:
1. `~/.agents/skills/`
2. `~/.gemini/skills/`
3. `~/.gemini/config/skills/`
4. `~/.claude/skills/`
5. `~/.gemini/antigravity-cli/skills/`

## Usage Instructions

### 1. Audit Global Skill Symlinks
Run the sync audit script to inspect missing, broken, or legacy symlinks:
```bash
python3 ~/code/github/agent-skill-sync/skills/skill-sync/scripts/sync_skills.py
```

### 2. Automatically Repair & Synchronize Global Symlinks
To automatically create missing symlinks, prune uncurated directories, and fix broken target paths:
```bash
python3 ~/code/github/agent-skill-sync/skills/skill-sync/scripts/sync_skills.py --prune --fix
```

### 3. Bootstrap Curated Skills into a Project Workspace (JIT Bootstrapping)
To attach domain-specific skills (e.g., frontend, performance, API design) to the active project:
```bash
python3 ~/code/github/agent-skill-sync/skills/skill-sync/scripts/sync_skills.py \
  --project . \
  --skills frontend-ui-engineering,performance-optimization,api-and-interface-design
```

## Best Practices
- Keep global scope strictly limited to the curated 15 lifecycle skills.
- Use `--project <workspace> --skills <names>` to bootstrap specialized domain skills into `<project>/.gemini/skills/` on demand.
- Ensure each canonical skill includes a valid `SKILL.md` file with token-efficient YAML frontmatter.
