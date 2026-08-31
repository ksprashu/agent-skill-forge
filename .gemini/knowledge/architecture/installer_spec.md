---
type: "Architecture Spec"
title: "Universal Skill Installer & Symlink Orchestration"
description: "Architectural specification for multi-runtime symlink synchronization, prune/fix algorithms, and JIT workspace bootstrapping."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/scripts/sync_skills.py"
tags: ["architecture", "installer", "symlinks", "sync", "runtime-hubs"]
---

# ⚙️ Universal Installer & Symlink Orchestration

Technical specification for `sync_skills.py` and `install.sh`, managing global skill hubs and project-scoped bootstrapping.

---

## 1. Multi-Runtime Skill Hubs

Agent Skill Forge manages symbolic links across 5 distinct AI agent runtime directories:

```
~ (User Home)
├── .agents/skills/                   # Universal AI Agent Hub (Open agent standard)
├── .gemini/skills/                   # Gemini CLI Skills Hub
├── .gemini/config/skills/            # Google Antigravity IDE Skills Hub
├── .claude/skills/                   # Claude Code CLI Skills Hub
└── .gemini/antigravity-cli/skills/   # Antigravity CLI Skills Hub
```

---

## 2. Global Synchronization Algorithm

When executed as `python3 scripts/sync_skills.py` or via `bash scripts/install.sh`:

1. **Discovery**: Scans `skills/` for all 16 core universal action verbs.
2. **Directory Scaffolding**: Ensures target global directories exist.
3. **Atomic Symlinking**: For each core skill:
   - Resolves absolute source path in the monorepo.
   - Creates relative or absolute symlinks into all 5 active hubs.
   - Links all legacy aliases (e.g., `prompt-writer` $\rightarrow$ `prompt`).
4. **Pruning & Cleanup (`--prune` / `--fix`)**:
   - Detects dangling symlinks pointing to deleted skills.
   - Identifies corrupted directories or misplaced legacy skills.
   - Safely removes stale links and replaces them with active targets.

---

## 3. Project-Scoped JIT Bootstrapping

When invoked with `--project <TARGET_PATH> --skills <SKILL_LIST>`:

```bash
python3 scripts/sync_skills.py --project /path/to/repo --skills frontend-ui-engineering,performance-optimization
```

### Execution Flow:
1. **Target Verification**: Validates that `<TARGET_PATH>` exists.
2. **Skill Resolution**: Resolves requested skill names against `skills/`, `preferred/`, and alias maps.
3. **Workspace Injection**:
   - Creates `<TARGET_PATH>/.gemini/skills/<skill-name>` symlink.
   - Creates `<TARGET_PATH>/.agents/skills/<skill-name>` symlink.
4. **Context Activation**: The workspace AI agent immediately discovers the bootstrapped skills on its next turn without reloading global configuration.
