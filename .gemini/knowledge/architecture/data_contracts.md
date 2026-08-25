# 📐 Data Contracts & YAML Frontmatter Schemas

## Standard Skill Frontmatter
Every `SKILL.md` in the forge must adhere to this schema:
```yaml
---
name: <slug>                          # Lowercase alphanumeric with hyphens (e.g., prompt, grill, unslop)
description: <concise summary>        # High-density trigger description explaining WHAT it does and WHEN to invoke
disable-model-invocation: true        # Required for user-only slash commands; omitted for autonomous model skills
---
```

## Invocation Modes
1. **User-Only Slash Commands (`disable-model-invocation: true`)**:
   - `prompt`, `grill`, `docs`, `sync`, `google-oss`, `codelab`, `voice`, `copy-write`, `image-gen`.
   - Never injected into standard LLM turns, saving context tokens until explicitly typed by the user.
2. **Autonomous Model Skills (Omitted `disable-model-invocation`)**:
   - `spec`, `plan`, `test`, `verify`, `review`, `unslop`, `catalog`.
   - Autonomously discovered and invoked by LLMs based on prompt intent and task phases.
