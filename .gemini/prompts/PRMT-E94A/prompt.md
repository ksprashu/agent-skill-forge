# [PROMPT-PRMT-E94A] Continuous Context Alignment & Self-Evolving Project Intelligence Engine

<SYSTEM_CONTEXT>
Short ID: PRMT-E94A
Target Domain: Autonomous AI Agent Lifecycle & Dynamic Project Intelligence
Workspace: /Users/ksprashanth/code/github/agent-skill-forge
Standards: 4-Tier Memory Hierarchy, Antigravity Hooks (hooks.json), Zero External Dependencies
</SYSTEM_CONTEXT>

<OBJECTIVE>
Design and implement the `continuous-alignment` skill and Antigravity lifecycle hooks that automatically distill session transcripts, synchronize `AGENTS.md` and `.agents/rules/*.md` within a 200-line token budget, record living ADRs in `.gemini/knowledge/ADRs/`, and compile strategic milestones into `docs/VISION.md` and `docs/ROADMAP.md`.
</OBJECTIVE>

<ARCHITECTURE_REQUIREMENTS>
1. **Tier 1 (Hot Invariants)**: `AGENTS.md` (max 200 lines). Frontloaded build/test commands, negative constraints, root gotchas.
2. **Tier 2 (Path-Scoped Rules)**: `.agents/rules/*.md`. Proximity-cascaded rules for subsystems.
3. **Tier 3 (Strategic Direction)**: `docs/VISION.md` & `docs/ROADMAP.md`. Living roadmap with completion status and SVG timeline.
4. **Tier 4 (Living ADRs)**: `.gemini/knowledge/ADRs/*.md`. MADR formatted decision records capturing architectural rationale.
5. **Lifecycle Hooks**: `.agents/hooks.json` registering `Stop` (turn distillation) and `PreInvocation` (context pulse).
</ARCHITECTURE_REQUIREMENTS>

<EXECUTION_PLAN>
Follow `.gemini/prompts/PRMT-E94A/task_graph.json`:
- Task 01: `skills/continuous-alignment/references/memory_schema.json` & `hook_protocol.md`
- Task 02: `skills/continuous-alignment/scripts/distill_session.py`
- Task 03: `skills/continuous-alignment/scripts/sync_agents_rules.py`
- Task 04: `skills/continuous-alignment/scripts/compile_roadmap.py`
- Task 05: `skills/continuous-alignment/SKILL.md` & `.agents/hooks.json`
- Task 06: `skills/continuous-alignment/tests/test_distill.py`, `test_sync_rules.py` & validation
</EXECUTION_PLAN>

<VERIFICATION_CRITERIA>
- Zero third-party dependencies (Python standard library only).
- Sub-second execution (< 200ms) for hook commands.
- `scripts/validate_skills.py` passes with 0 lint and 0 PII errors.
- Unit tests pass with 100% test coverage for transcript parsing and rule deduplication.
</VERIFICATION_CRITERIA>
