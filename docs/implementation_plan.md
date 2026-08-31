# Implementation Plan: Continuous Alignment & Self-Evolving Project Intelligence

Build and deploy the `continuous-alignment` skill and Antigravity lifecycle hooks (`hooks.json`) to establish a self-evolving project intelligence system that distills transcripts, maintains `AGENTS.md` under a 200-line budget, updates living ADRs, and synchronizes strategic roadmaps.

## User Review Required

> [!IMPORTANT]
> **Hook Configuration**: The project `.agents/hooks.json` will register a `Stop` hook (`distill_session.py`) and a `PreInvocation` hook (`sync_agents_rules.py --pulse`). The `Stop` hook runs synchronously in the subshell on every agent turn completion. Execution is designed to take < 150ms with zero third-party dependencies.

> [!NOTE]
> **200-Line Budget Limit**: Root `AGENTS.md` is strictly capped at 200 lines to prevent token budget waste and attention dilution. Rules specific to subdirectories (e.g. `skills/docs/`) will automatically spill over to `.agents/rules/<subsystem>.md`.

---

## Proposed Changes

### Core Engine & Scripts (`skills/continuous-alignment/`)

#### [NEW] [SKILL.md](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/SKILL.md)
- Primary skill definition with YAML frontmatter (`name: continuous-alignment`), `/align`, `/evolve`, and `/prune-memory` commands, and step-by-step alignment playbooks.

#### [NEW] [distill_session.py](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/scripts/distill_session.py)
- Handles Antigravity `Stop` lifecycle event on `stdin`.
- Reads `transcriptPath` JSONL logs, extracts verified architectural decisions, constraints, error resolutions, and command patterns.
- Serializes deduplicated memory entries into `.gemini/knowledge/memories.jsonl`.

#### [NEW] [sync_agents_rules.py](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/scripts/sync_agents_rules.py)
- Consolidates extracted memories into `AGENTS.md` and `.agents/rules/*.md`.
- Enforces 200-line budget cap, handles conflict invalidation, and provides `--pulse` for `PreInvocation` hooks.

#### [NEW] [compile_roadmap.py](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/scripts/compile_roadmap.py)
- Compiles active milestones into `docs/ROADMAP.md` and `docs/VISION.md`.
- Generates MADR decision records in `.gemini/knowledge/ADRs/`.

---

### Project Configuration & Hooks

#### [NEW] [.agents/hooks.json](file:///Users/ksprashanth/code/github/agent-skill-forge/.agents/hooks.json)
- Configures `Stop` and `PreInvocation` hooks for the workspace.

---

### Verification & Test Suite

#### [NEW] [test_distill.py](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/tests/test_distill.py)
- Pytest unit tests for transcript JSONL parsing, rule deduplication, and error resolution extraction.

#### [NEW] [test_sync_rules.py](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/continuous-alignment/tests/test_sync_rules.py)
- Pytest unit tests for 200-line budget enforcement, path-scoped rule spillover, and rule invalidation.

---

## Verification Plan

### Automated Tests
1. **Pytest Unit Suite**:
   ```bash
   pytest skills/continuous-alignment/tests/ -v
   ```
2. **Skill Linter & PII Audit**:
   ```bash
   python scripts/validate_skills.py
   ```
3. **Simulated Hook Ingestion**:
   ```bash
   echo '{"conversationId": "test", "workspacePaths": ["/Users/ksprashanth/code/github/agent-skill-forge"], "transcriptPath": "skills/continuous-alignment/tests/fixtures/sample_transcript.jsonl"}' | python skills/continuous-alignment/scripts/distill_session.py
   ```

### Manual Verification
- Execute `/align` command to verify manual alignment reporting.
- Validate generated `AGENTS.md` line count is <= 200 lines.
