---
type: "Authoring Guide"
title: "Agent Skill Authoring & Progressive Disclosure Handbook"
description: "Authoritative design patterns, 3-level progressive disclosure hierarchies, and formatting guidelines for authoring agent skills."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/docs/skill_authoring_guide.md"
tags: ["builder", "authoring", "skills", "progressive-disclosure", "best-practices"]
---

# ✍️ Agent Skill Authoring Handbook

Engineering guide for authoring, testing, and formatting high-performance agent skills for Google Antigravity, Gemini CLI, Claude Code, and `skills.sh`.

---

## 1. 3-Level Progressive Disclosure Hierarchy

Skills must be structured to maximize agent context window efficiency:

```
Level 1: YAML Frontmatter (~50 words)
└── Always in system context. Explains WHAT the skill does and WHEN to invoke.

Level 2: SKILL.md Execution Body (<500 lines)
└── Loaded only when triggered. Contains imperative workflows and hard constraints.

Level 3: Bundled Resources (references/, scripts/, assets/)
└── Loaded on demand. Heavy reference tables, rubrics, and AST tools.
```

---

## 2. Standard `SKILL.md` Template

Every `SKILL.md` must adhere to this structural sequence:

```markdown
---
name: your-skill-name
description: Concise 1-2 sentence description stating WHAT it does and WHEN it triggers.
---

# Skill Name

Brief 1-sentence overview of the capability.

---

## 🎯 Goal
Concrete definition of what successful execution looks like.

---

## 📋 Step-by-Step Workflow
1. **Step 1 (Inspection & Ingestion)**: Inspect files, state, or parameters.
2. **Step 2 (Transformation & Action)**: Execute primary logic or modifications.
3. **Step 3 (Verification & Validation)**: Verify results against acceptance criteria.

---

## 💡 Concrete Examples
Show clear before/after diffs, sample payloads, or expected CLI outputs.

---

## 🚫 Hard Constraints
* **NEVER** violate X.
* **NEVER** introduce unverified Y.
```

---

## 3. Pre-Publish Validation Checklist

Before submitting a new skill or modifying existing skills:
1. **Lint Frontmatter**: Run `python3 scripts/validate_skills.py` to ensure schema conformance.
2. **Scan for PII**: Ensure no personal names, internal corp hostnames, or private emails exist.
3. **Validate Length**: Keep `SKILL.md` under 500 lines; move auxiliary docs into `references/`.
4. **Test Bootstrapping**: Test local linking via `python3 scripts/sync_skills.py --project <test-dir> --skills <skill-name>`.
