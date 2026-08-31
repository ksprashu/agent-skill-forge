# Task 05: Scaffold Skill Definition & Antigravity Hook Manifest

## Objective
Create the primary `SKILL.md` for `continuous-alignment` and register the `Stop` and `PreInvocation` hooks in `.agents/hooks.json`.

## Key Capabilities
1. `skills/continuous-alignment/SKILL.md`:
   - Valid YAML frontmatter (`name`, `description`).
   - Trigger commands: `/align`, `/evolve`, `/prune-memory`.
   - Clear workflows for manual alignment vs background hook distillation.
2. `.agents/hooks.json` (and project `.gemini/hooks.json`):
   - Register `Stop` event with `distill_session.py` (timeout 45s).
   - Register `PreInvocation` event with `sync_agents_rules.py --pulse` (timeout 15s).
