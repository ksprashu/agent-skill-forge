---
type: "Architecture Spec"
title: "Cross-Platform Interoperability Specification"
description: "Multi-runtime compatibility mapping across Claude Code, Google Antigravity IDE, Gemini CLI, Cursor MDC, OpenAI Codex, and OpenCode."
resource: "file:///Users/ksprashanth/code/github/agent-skills/docs/comparison.md"
tags: ["architecture", "compatibility", "multi-platform", "claude-code", "cursor", "codex", "gemini-cli", "antigravity"]
---

# 🔌 Cross-Platform Interoperability Specification

Engineering specification for deploying and executing Agent Skill Forge skills across heterogeneous AI agent harnesses and IDEs.

---

## 1. Multi-Harness Compatibility Matrix

| Runtime Environment | Discovery Mechanism | Skill Location | Rule / Policy Location | Slash Command Support |
| :--- | :--- | :--- | :--- | :--- |
| **Claude Code** | Native Plugin Manifest (`plugin.json`) | `~/.claude/skills/` or `.claude-plugin/` | `CLAUDE.md` | Yes (`.claude/commands/*.md`) |
| **Google Antigravity IDE** | Antigravity Skills Hub & Customizations | `~/.gemini/config/skills/` | `.gemini/rules/` / Global Rules | Yes (`/spec`, `/plan`, `/prompt`, etc.) |
| **Gemini CLI** | Gemini Workspace Hub | `~/.gemini/skills/` | `GEMINI.md` | Yes (CLI commands) |
| **Cursor IDE** | Cursor Agent Auto-Discovery | `.cursor/skills/<name>/SKILL.md` | `.cursor/rules/*.mdc` | Implicit / Chat mention (`@skill`) |
| **OpenAI Codex / Operator** | Codex Marketplace Plugin | `~/.codex/plugins/` or `.codex-plugin/` | `AGENTS.md` | Implicit / Chat mention (`@skill`) |
| **OpenCode / Windsurf** | Open Agent Standard Hub | `~/.agents/skills/` | `AGENTS.md` | Implicit Lifecycle Mapping |

---

## 2. Universal Schema Neutrality

To serve all platforms from a single codebase without file duplication:
1. **Frontmatter Standard**: `SKILL.md` uses the neutral YAML frontmatter (`name`, `description`, optional `disable-model-invocation`). All runtimes (Claude, Codex, Cursor, Gemini, Antigravity) parse this schema identically.
2. **Path Portability**: Avoid hardcoded home directory paths. Use relative links or standard URL schemas (`file:///`).
3. **Manifest Co-Location**:
   - `plugin.json` at repository root for Claude Code.
   - `.codex-plugin/plugin.json` for OpenAI Codex.
   - `.agents/skills/` symlinks for Open Agent standards.
   - `.cursor/rules/agent-skills.mdc` pointer rule for Cursor.

---

## 3. Cursor MDC vs. Skill Coexistence Pattern

In Cursor, rules and skills must remain cleanly partitioned:

```
your-project/
├── .cursor/
│   ├── rules/
│   │   ├── agent-skills.mdc          # Thin routing pointer: "Route via .cursor/skills"
│   │   └── code-style.mdc            # Repo-specific policy (globs: "**/*.ts")
│   └── skills/                       # Full procedural workflows (SKILL.md)
│       ├── test/
│       ├── review/
│       └── spec/
```

- **Rule Policy (`.mdc`)**: Small, always-on or glob-scoped instructions ($\le 30$ lines).
- **Skill Workflow (`SKILL.md`)**: Complete step-by-step procedure loaded on demand. Never paste full `SKILL.md` bodies into `.mdc` files.
