# Upgrade Prompt-Writer Skill & Templates for Native Parallel Subagent Execution

Upgrade the `prompt-writer` skill instructions and prompt templates in `skills/prompt/` so that:
1. **The Rewriter Skill itself reliably spawns parallel scout and design subagents** during the prompt-writing phase, eliminating inline exploration traps and invalid `TypeName` errors.
2. **The Rewritten Prompt reliably commands executing agents to spin off parallel subagents** (via native `invoke_subagent` with explicit `TypeName`, `Role`, `Prompt`, and `Workspace: "branch"`) instead of falling back to sequential main-thread file editing or legacy Python SDK scripts.

## User Review Required

> [!IMPORTANT]
> - **Native In-Editor Subagents vs. Python SDK**: Prompt templates in `references/template.md` will be updated to replace the offline `execute_pipeline.py` Python SDK example with native Antigravity `invoke_subagent` tool-call blocks.
> - **Strict Tool Contracts**: Scout subagents will be standardized on `TypeName: "research"` (read-only research tools) and Worker subagents on `TypeName: "self"` (full read/write capabilities in branched workspaces).

## Proposed Changes

Grouped by component:

---

### Prompt Skill Definition & Instructions

#### [MODIFY] [`skills/prompt/SKILL.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/SKILL.md)
- **Scout Stage Subagent Invocations**:
  - Add explicit, copy-pasteable `invoke_subagent` JSON payload structures with valid `TypeName: "research"`, exact `Role` strings, and targeted `Prompt` directives.
  - Ban main-thread deep inline search/grep before launching the 3 parallel scouts.
  - Fix subagent type errors by noting that `self` and `research` are built-in, and any custom type must be preceded by `define_subagent`.
- **Mode Router Clarification**:
  - Update Lightweight Mode to ensure it still performs fast parallel context collection when necessary and generates a concise rewritten prompt rather than directly mutating workspace files.
- **Architect & Builder Stages**:
  - Mandate that generated prompts embed an explicit `<SUBAGENT_ORCHESTRATION>` block commanding the executing agent to call `invoke_subagent` for parallel implementation tasks.

---

### Prompt Templates & References

#### [MODIFY] [`skills/prompt/references/template.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/references/template.md)
- Replace the legacy offline `execute_pipeline.py` Python SDK script with native Antigravity `invoke_subagent` tool-call directives.
- Add `<SUBAGENT_ORCHESTRATION>` structure detailing parallel worker dispatch (`TypeName: "self"`, `Workspace: "branch"`, distinct roles like `Frontend Builder`, `Backend Builder`, `Sentry Verifier`).

#### [MODIFY] [`skills/prompt/references/dag_orchestration.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/references/dag_orchestration.md)
- Ensure all DAG task nodes in `task_graph.json` schema and examples explicitly include valid `TypeName`s (`self` / `research`) and imperative `invoke_subagent` dispatch commands.

#### [MODIFY] [`skills/prompt/references/subagents/codebase_scout.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/references/subagents/codebase_scout.md)
#### [MODIFY] [`skills/prompt/references/subagents/docs_crawler.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/references/subagents/docs_crawler.md)
#### [MODIFY] [`skills/prompt/references/subagents/web_intelligence_analyst.md`](file:///Users/ksprashanth/code/github/agent-skill-forge/skills/prompt/references/subagents/web_intelligence_analyst.md)
- Ensure all scout subagent instructions explicitly align with `TypeName: "research"` toolsets and message-passing handoffs (`send_message`).

---

## Verification Plan

### Automated Tests
- Run validation scripts / linters on the updated skill files to ensure markdown formatting, valid JSON schemas, and no broken links.
- Test documentation synchronization if applicable (`compile_docs.py`).

### Manual Verification
- Verify that `invoke_subagent` payloads in `SKILL.md` and `template.md` adhere strictly to Antigravity tool definitions (`Subagents: [{ TypeName, Role, Prompt, Workspace }]`).
- Verify that `/Users/ksprashanth/.gemini/config/skills/prompt-writer` symlink correctly reflects all changes.
