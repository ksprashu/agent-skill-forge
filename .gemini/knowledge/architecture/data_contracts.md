---
type: "Data Contract"
title: "Agent Skill Data Contracts & Frontmatter Schemas"
description: "Formal specification of SKILL.md YAML frontmatter schemas, invocation modes, subfolder boundaries, and metadata contracts."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/docs/skill_authoring_guide.md"
tags: ["architecture", "data-contracts", "schema", "frontmatter", "specification"]
---

# 📐 Agent Skill Data Contracts & Schemas

Formal data contracts and structural interface specifications for all skills in **Agent Skill Forge**.

---

## 1. `SKILL.md` YAML Frontmatter Contract

Every skill must begin with a YAML frontmatter block at byte offset 0 adhering to this schema:

```yaml
---
name: <slug>                          # Required. Lowercase alphanumeric with hyphens (e.g. prompt, unslop, frontend-ui-engineering)
description: <concise summary>        # Required. 1-2 punchy sentences describing WHAT it does and WHEN to invoke
disable-model-invocation: true        # Optional. Required for user-only slash commands; omitted for autonomous skills
aliases:                              # Optional. Array of legacy or convenience aliases
  - <alias-1>
---
```

### Field Definitions & Constraints

| Field | Type | Mandatory | Description & Rules |
| :--- | :--- | :--- | :--- |
| `name` | `string` | **Yes** | Unique identifier slug. Must match directory basename. Alphanumeric with hyphens only. |
| `description` | `string` | **Yes** | High-density semantic description. Injected into global LLM system prompt. Maximum 60 words. |
| `disable-model-invocation` | `boolean` | **Conditional** | Set to `true` for skills triggered strictly via user slash commands (e.g., `/copy-write`, `/codelab`). Omitted for autonomous skills (`spec`, `plan`, `test`, `verify`, `review`, `unslop`, `catalog`). |
| `aliases` | `list[str]` | No | Optional alternative trigger names recognized by the installer and router. |

---

## 2. Standard Directory Layout Contract

Each skill bundle must follow this canonical internal layout:

```
skills/<skill-name>/
├── SKILL.md                          # Mandatory. Primary execution instructions (<500 lines)
├── README.md                         # Mandatory. Human-facing overview and attribution
├── scripts/                          # Optional. Deterministic helper scripts and verifiers
│   └── *.py / *.sh
├── references/                       # Optional. Heavy reference docs, rubrics, and templates
│   ├── *.md
│   ├── *.template.md                 # Public generic fallback template
│   └── *.local.md                    # Gitignored private user override
└── assets/                           # Optional. Static diagram templates or images
```

---

## 3. Structural Rules & Execution Invariants

1. **Heading Hierarchy**: Instructions must use `#`, `##`, and `###` markdown headings to define unambiguous semantic sections (`## 🎯 Goal`, `## 📋 Step-by-Step Workflow`, `## 💡 Concrete Examples`, `## 🚫 Hard Constraints`).
2. **Code Fences**: All code examples, payloads, and CLI commands must be wrapped in language-specified fences (` ```bash `, ` ```json `, ` ```python `).
3. **Attribution Separation**: Biographical author credits, license texts, and upstream change logs must live in `README.md` rather than `SKILL.md` to prevent agent procedural thinking from being contaminated by historical metadata.
