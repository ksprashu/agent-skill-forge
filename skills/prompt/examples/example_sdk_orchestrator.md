# Prompt-Writer Showcase: Multi-Agent SDK Orchestration

This file demonstrates how the `prompt-writer` skill transforms an agentic AI request into an exceptionally detailed, subagent-orchestrated, and dual-test verified Antigravity task deck.

---

## 1. Before: The Initial User Request
> "I want to build a multi-agent triage system using the Google Antigravity Python SDK that takes incoming customer bug reports, analyzes stack traces, and generates reproduction scripts."

---

## 2. The Socratic Grill & Propose Session
Instead of asking open-ended questions, the agent adopts the Analyst archetype to propose architecture, data contracts, and verification plans.

```markdown
### Prompt-Writer Diagnosis:
Your multi-agent triage system architecture is high-impact. To formulate the optimal Antigravity execution deck, let's align on technical and operational parameters:

#### Q1: Orchestration Architecture & Workflow Topology
- **[Recommended] Option A (Linear Pipeline with Sentry Gate)**:
  * Ingestion & Sanitizer -> Stack Trace Parser -> Reproduction Script Generator -> Sentry Sandbox Verifier.
- **Option B (Hierarchical Swarm)**:
  * Central Supervisor agent delegating dynamically to ad-hoc parser subagents.

#### Q2: BDD User Scenarios (Behavior-Driven Development)
- **[Recommended] Option A (End-to-End Triage & Verified Reproduction)**:
  * *Given* an unformatted customer bug ticket containing Python traceback logs
  * *When* the triage pipeline processes the ticket
  * *Then* the system extracts root-cause error signatures and generates a sandboxed `reproduce_bug.py` script that executes and exits with non-zero exit codes.
- **Option B (Classification & Jira Sync Only)**:
  * *Given* an error report
  * *When* classified
  * *Then* JSON metadata is emitted to an external ticketing webhook.

#### Q3: Verification & Execution Isolation
- **[Recommended] Dual Suite (pytest + behave) & Sandboxed Subprocesses**:
  * Unit tests validating error regex parsers, Gherkin feature scenarios validating end-to-end triage pipelines, and isolated subprocess execution for repro scripts.
```

*The user selects **Option A** for all three.*

---

## 3. After: The Archetype-Embedded Rewrite
This is the final, highly structured prompt output by the skill, engineered to leverage the 6 AI Archetypes, Pure Manager orchestration, and Citation Hygiene.

```markdown
<!-- ======================================================================= -->
<!-- STATIC CONTEXT PREFIX (STABLE BLOCKS OPTIMIZED FOR GEMINI CACHING)     -->
<!-- ======================================================================= -->

<PROMPT_METADATA>
- SHORT_ID: PRMT-C719
- PARENT_SHORT_ID: NULL
- REVISION_MODE: FULL
- DOMAIN: coding
- CREATED_AT: 2026-08-30T09:00:00Z
</PROMPT_METADATA>

<ROLE>
You are an expert Lead Multi-Agent Systems Architect operating inside Google Antigravity. Your objective is to build an autonomous Bug Triage & Reproduction System using Python 3.11 and the Google Antigravity Agentic SDK, managing execution across specialized worker subagents.
</ROLE>

<DIRECTIVES>
1. **Pure Manager Execution**: The main thread acts strictly as an Orchestrator / Manager. Do NOT edit code directly on the main thread for multi-component tasks.
2. **Subagent Delegation**: Dispatch implementation workers and sentries via `invoke_subagent` using the precise parameters in `<SUBAGENT_ORCHESTRATION>`.
3. **Dual-Testing Verification**: Enforce BOTH unit tests (`pytest`) AND BDD feature specs (`behave` under `features/`) before sign-off.
</DIRECTIVES>

<CONTEXT>
We are building an autonomous Bug Triage & Reproduction pipeline. The system ingests raw customer bug reports containing complex tracebacks, parses error frames, categorizes issue severity, generates standalone reproduction test cases, and verifies them inside isolated subprocess sandboxes.
</CONTEXT>

<DATA_PROVENANCE_AND_CONTRACTS>
### 1. Data Contracts & Pydantic Schemas
- **Triage Ticket Input Schema (`schemas/ticket.py`)**:
  ```python
  from pydantic import BaseModel, Field
  from typing import List, Optional

  class BugTicket(BaseModel):
      ticket_id: str
      title: str
      raw_description: str
      environment_info: dict = Field(default_factory=dict)
      traceback_text: Optional[str] = None
  ```
- **Triage Result Output Schema (`schemas/triage_result.py`)**:
  ```python
  class TriageResult(BaseModel):
      ticket_id: str
      error_type: str
      root_cause_summary: str
      reproduction_code: str
      is_reproduced: bool
      execution_stdout: str
  ```
- **Strict Anti-Mock Invariant**: Execution stdout must capture actual subprocess runs of generated reproduction scripts. Hardcoded simulated outputs are strictly forbidden.
</DATA_PROVENANCE_AND_CONTRACTS>

<RESOURCES_AND_KNOWLEDGE_BASES>
### 1. Technology Stack
- **Language & Runtime**: Python 3.11+, Pydantic v2, pytest, behave.
- **SDKs**: Google Antigravity Agentic SDK, AST parser utilities.

### 2. Live Knowledge Retrieval (MANDATORY SCHOLAR SEARCH)
- `developer-knowledge`: Search for "python ast parse exception traceback frame extraction" for robust stack trace parsing.
- `context7`: Query documentation for "pydantic v2 validation error handling".
</RESOURCES_AND_KNOWLEDGE_BASES>

<SUBAGENT_ORCHESTRATION>
### Mandatory Subagent Tool-Call Payloads
The executing Manager MUST dispatch parallel worker subagents using the native `invoke_subagent` tool:

```json
{
  "Subagents": [
    {
      "TypeName": "self",
      "Role": "Builder - Stack Trace Parser Engineer",
      "Model": "inherit",
      "Workspace": "branch",
      "Prompt": "/goal Implement the AST and regex-based stack trace parser in triage/parser.py according to schemas/ticket.py. Write comprehensive pytest unit tests in tests/test_parser.py. Enforce PEP8 type hints. Signal completion via send_message."
    },
    {
      "TypeName": "self",
      "Role": "Builder - Reproduction Generator Engineer",
      "Model": "inherit",
      "Workspace": "branch",
      "Prompt": "/goal Implement the reproduction script synthesizer and sandbox runner in triage/runner.py. Ensure reproduction scripts run in isolated subprocesses with timeout limits. Write pytest tests in tests/test_runner.py. Signal completion via send_message."
    }
  ]
}
```
</SUBAGENT_ORCHESTRATION>

<CONSTRAINTS>
1. **Subprocess Isolation**: Reproduction scripts must execute with explicit timeouts (max 10s) and non-root execution privileges.
2. **Mandatory Dual Test Suite**: Implement unit tests (`pytest`) AND Gherkin BDD specs (`behave`).
3. **No Monolithic Files**: No file may exceed 150 lines. Every file must end with `# END OF FILE: <path>`.
4. **No Placeholders**: Zero stub code, "TBD", or un-implemented methods.
</CONSTRAINTS>

<!-- ======================================================================= -->
<!-- DYNAMIC STATE SUFFIX (DYNAMIC BLOCKS THAT CHANGE FREQUENTLY)           -->
<!-- ======================================================================= -->

<GOAL>
/goal Build a production-grade, multi-agent Bug Triage & Reproduction System in Python. Ensure all components are fully typed, covered by dual test suites (pytest + behave), and verified with active execution evidence.
</GOAL>

<TASK_BREAKDOWN>
Deconstruct the objective into independent milestones, mapping each to a primary archetype stage.

### Milestone 1: Data Contracts & Test Fixture Setup (Sequence: 1) [Architect]
- [ ] Define Pydantic models in `schemas/ticket.py` and `schemas/triage_result.py`.
- [ ] Create realistic test fixtures with multi-frame Python exceptions in `tests/fixtures/sample_tracebacks.json`.
- [ ] Record verification evidence as `[E-101]` in `.gemini/EVIDENCE.md`.

### Milestone 2: Parallel Parser & Runner Construction (Sequence: 2, Parallel) [Builder]
- [ ] Dispatch Parser Builder subagent (`TypeName: "self"`, `Workspace: "branch"`) to build `triage/parser.py`.
- [ ] Dispatch Runner Builder subagent (`TypeName: "self"`, `Workspace: "branch"`) to build `triage/runner.py`.
- [ ] Merge branches and connect the pipeline in `triage/pipeline.py`.

### Milestone 3: Dual Test Suite & Sentry Audit (Sequence: 3) [Sentry]
- [ ] Implement Gherkin BDD feature spec in `features/triage_pipeline.feature` and steps in `features/steps/triage_steps.py`.
- [ ] Run `pytest tests/ -v` and `behave features/`.
- [ ] Run `run-security-scanner` to verify sandbox isolation and safe subprocess execution.
- [ ] Execute `validate_evidence.py` to programmatically verify `.gemini/EVIDENCE.md`.

### Milestone 4: Architecture Documentation & Walkthrough (Sequence: 4) [Mentor]
- [ ] Generate `walkthrough.md` with a Mermaid.js execution sequence diagram.
- [ ] Compile final interactive HTML documentation portal under `docs/`.
</TASK_BREAKDOWN>

<DEFINITION_OF_DONE>
### Mandatory Acceptance Criteria
- [ ] **Data Contracts & Parser**: Fully typed Pydantic models and robust AST traceback parser.
- [ ] **Sandbox Runner**: Isolated subprocess runner with timeout guards executing reproduction scripts.
- [ ] **Dual Test Pass**:
  - `pytest tests/` passes with 100% success.
  - `behave features/` passes with 100% scenario steps passing.
- [ ] **Evidence & Provenance**: `.gemini/EVIDENCE.md` validated via `python validate_evidence.py`.
- [ ] **No Placeholders**: Zero stub files, TBDs, or empty handlers.
</DEFINITION_OF_DONE>

<VERIFICATION_PLAN>
### 1. Automated Verification (Builder/Sentry)
- **Unit Suite**: `pytest tests/ -v`
- **BDD Behavior Suite**: `behave features/`
- **Evidence Audit**: `python validate_evidence.py`

### 2. Manual & Security Audit (Sentry/Mentor)
- Verify sandbox isolation by executing a sample malformed script and confirming timeout protection.
</VERIFICATION_PLAN>
```
