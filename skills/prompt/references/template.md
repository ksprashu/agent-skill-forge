# Domain-Agnostic Living Blueprint & Modular Prompt Deck Templates

This repository supports two execution prompt layouts depending on complexity:

1. **⚡ Lightweight Mode**: A single, concise, context-focused directive prompt file (`prompt.md`) for direct execution of quick patches, single-file fixes, or localized refactors.
2. **🧠 Heavyweight Mode (Modular Living Blueprint Deck / Staged Milestones & E2E Convergence)**: An orchestrated deck structure designed to prevent LLM context pollution and instruction decay, leveraging Google Antigravity's **Teamwork** principles, **Staged Milestone Decomposition**, and the **Adversarial Teamwork Quartet** (Builder, Challenger, Forensic Auditor, Critic, Synthesizer, Sentinel):
   - `blueprint.json`: Machine-readable Living Blueprint, 4D task space metadata & milestone definitions.
   - `task_graph.json`: Dynamic DAG with staged milestones, adversarial attack vectors, and terminal E2E convergence gates.
   - `orchestrator.md`: Directives for the **Pure Manager Thread** and dialectical arbiter.
   - `tasks/task_01_<name>.md`: Focused, atomic worker, challenger, forensic, and E2E integration prompts.

---

## 1. Single Prompt Template (Lightweight Mode)

This is a structural blueprint designed to format highly-optimized, structured prompts for Google Antigravity and Gemini. It is fully optimized for **Gemini 3+ Context Caching** by placing static instructions, guidelines, and schemas first, and placing dynamic states, checklists, and goals last.

```markdown
<!-- ======================================================================= -->
<!-- STATIC CONTEXT PREFIX (STABLE BLOCKS OPTIMIZED FOR GEMINI CACHING)     -->
<!-- ======================================================================= -->

<PROMPT_METADATA>
- SHORT_ID: PRMT-<HEX4>
- PARENT_SHORT_ID: [PRMT-XXXX or NULL]
- REVISION_MODE: [FULL | DIFF_INCREMENTAL]
- CREATED_AT: [ISO_TIMESTAMP]
</PROMPT_METADATA>

<ROLE>
Define a highly specialized, expert role-play persona tailored to the task (e.g., "Senior Lead Engineer", "Director of Research", "Lead Multi-Agent Systems Architect").
State clearly that the executing agent manages and orchestrates the implementation under Google Antigravity.
</ROLE>

<DIRECTIVES>
1. **Pure Manager Execution**: The executing agent operates as a Pure Manager / Orchestrator on the main thread for multi-component tasks.
2. **Subagent Delegation**: Dispatch implementation workers, challengers, and forensic auditors via `invoke_subagent` using the precise parameters defined in `<SUBAGENT_ORCHESTRATION>`.
3. **No Direct Inline Edits on Multi-Stage Work**: Use worker subagents in isolated workspaces (`Workspace: "branch"`) for code generation, and review/sentry/auditor subagents (`Workspace: "share"`) for audits.
</DIRECTIVES>

<CONTEXT>
Provide comprehensive context on the objective. Detail:
- What is being built, researched, or analyzed.
- Why it is being done (underlying value, target audience, business drivers).
- The current state of the workspace, active files, or background constraints.
</CONTEXT>

<DATA_PROVENANCE_AND_CONTRACTS>
### 1. Data Contracts, Schemas & System Interfaces
Specify the exact physical datasets, schemas, database tables, API signatures, and file interfaces required for execution:
- **Input Datasets / Sources**: [e.g., `project.dataset.table_name`, local config paths, or live API endpoints]
- **Target Schemas / Data Models**: [e.g., Pydantic models, JSON schema definitions, or SQL schema definitions]
- **Environment Variables & Secrets**: [e.g., required environment keys, parameter names, zero hardcoded tokens]

### 2. Strict Prohibition of Synthetic Heuristics & Mock Metrics
- Every performance measurement, token count, latency metric, and statistical figure MUST be grounded in real measurements (`time.time()`, `usage_metadata`, actual SQL outputs, or real tool responses).
- Synthetic heuristic offsets (e.g., `+ 5.0s if vanilla`) or ungrounded mock metrics are STRICTLY PROHIBITED. If simulated data is required for a sandbox run, explicitly flag with `is_simulated: true`.
</DATA_PROVENANCE_AND_CONTRACTS>

<RESOURCES_AND_KNOWLEDGE_BASES>
### 1. Technology Stack & Frameworks
Define the precise tools, frameworks, libraries, datasets, methodologies, or standard guidelines required.

### 2. Live Knowledge Retrieval (MANDATORY SCOUT)
Specify live knowledge retrieval to ground syntax and avoid hallucinating deprecated APIs:
- `developer-knowledge`: Search for official library usage and current SDK syntax.
- `context7`: Query documentation for exact responsive styling, component props, and runtime APIs.
</RESOURCES_AND_KNOWLEDGE_BASES>

<SUBAGENT_ORCHESTRATION>
### Mandatory Subagent Tool-Call Payloads (Teamwork Multi-Agent Quartet)
The executing Manager MUST dispatch worker subagents using the native `invoke_subagent` tool. Follow this standardized payload structure:

```json
{
  "Subagents": [
    {
      "TypeName": "self",
      "Role": "Builder - Component Developer",
      "Model": "inherit",
      "Workspace": "branch",
      "Prompt": "/goal Implement the core module in <path>. Adhere strictly to data contracts and PEP8/TypeScript types. Write comprehensive unit tests in tests/test_<name>.py. Ensure all files pass compilation. Send completion signal via send_message when done."
    },
    {
      "TypeName": "self",
      "Role": "Challenger - Adversarial Fuzzer",
      "Model": "inherit",
      "Workspace": "branch",
      "Prompt": "/goal Adversarially stress-test the newly generated implementation. Build hostile test fixtures probing race conditions, integer overflows, and malformed payload boundaries. Report any breach in .gemini/knowledge/<SHORT_ID>/sentry/breach_report.md."
    },
    {
      "TypeName": "research",
      "Role": "Forensic Auditor - Anti-Mock Proof Verifier",
      "Model": "inherit",
      "Workspace": "share",
      "Prompt": "/goal Independently audit the test evidence. Physically execute pytest and behave suites, capture raw stdout/stderr, verify exit code 0, inspect test ASTs to confirm zero synthetic mocks bypass logic, calculate SHA-256 evidence hashes, and write verified audit sheet to .gemini/EVIDENCE.md."
    }
  ]
}
```
</SUBAGENT_ORCHESTRATION>

<CONSTRAINTS>
State all development, security, or research restrictions:
1.  **Factual Hygiene [Scout]**: No ungrounded assertions. Never invent parameters or mock specifications.
2.  **Sandbox Isolation [Builder]**: Perform all complex generations and testing in isolated task directories (`Workspace: "branch"`).
3.  **Perfect Symmetry**: No unbalanced tags (e.g., `</div>` or `</main>`) which cause blank-page rendering breakages.
4.  **No Placeholders**: All deliverables must be fully written, functional, and complete. Zero "TBD" or stub structures.
5.  **Dependency-First Security [Sentry]**:
    - You MUST run `scan_dependencies` first before any new package is imported or added to dependencies.
    - Run the `run-security-scanner` skill on new source files to detect potential security issues (XSS, SQLi, secrets).
    - Establish a clear security plan using the `create-security-implementation-plan` skill.
6.  **Interactive Design Excellence [Builder]**:
    - **Default Theme**: Always default to a clean, highly polished **Light Theme** for interactive documentation, pages, and web dashboards, with a custom-themed **Dark/Light toggle**.
    - **Layout Principles**: Ensure layouts are information-dense, comprehensive, yet minimalist and extremely readable. Avoid generic default colors. Use elegant HSL variables, smooth transitions, and responsive grids.
    - **User Documentation**: Maintain thorough, extensive, and easy-to-read user documentation within the project workspace.
7.  **Strict Data Contract Schemas [Architect]**: All Inter-Process Communication (IPC) and file exchange between parallel subagents inside the shared workspace must be governed by rigid, formal schemas (such as Pydantic models or JSON schemas). Raw, schema-less file exchange is strictly forbidden.
8.  **Self-Resuming State Checkpointing**: You MUST implement and maintain the State Checkpoint & Error Recovery Protocol. Create and continuously update `.gemini/tasks/state_journal.json` and `.gemini/tasks/task.md` immediately after completing any task, action, or stage transition.
9.  **Anti-Truncation Modular Architecture**: No single generated code file may exceed 150 lines. Large routers, pipelines, or schemas must be broken into modular sub-files (`module_get.py`, `module_post.py`). Every file must conclude with an explicit `# END OF FILE: <path>` handshake marker and pass syntax validation (`py_compile`/`node --check`).
10. **Production Python & Script Quality**: 100% of Python source files, test runners, and helper scripts must include static type annotations (`typing`/Pydantic), Google-style docstrings (`Args:`, `Returns:`), and defensive `try-except` blocks for I/O and JSON parsing operations.
11. **Non-Python Linters & Defensive JSON Escaping**: Run non-Python static analysis (`tflint` for Terraform, `hadolint` for Dockerfiles, `htmlhint` for web markup) where applicable. Enforce strict string escaping across all structured JSON output schemas to ensure 100% parseability by High Thinking LLM judges.
12. **Asynchronous Memory Consolidation (Agent Dreaming)**: Post-execution, you MUST execute an offline background "dreaming" sweep. Clean up intermediate workspace scratch clutter (Light phase), extract high-level procedural patterns and design insights (REM phase), and permanently promote durable insights/user preferences to `.gemini/knowledge/MEMORY.md` while logging narrative reflections in `.gemini/knowledge/DREAMS.md` (Deep phase).
</CONSTRAINTS>

<!-- ======================================================================= -->
<!-- DYNAMIC STATE SUFFIX (DYNAMIC BLOCKS THAT CHANGE FREQUENTLY)           -->
<!-- ======================================================================= -->

<GOAL>
/goal [State the unified, high-level success metric and done criteria. Be extremely specific.]

### Definition of Done (Exit Criteria)
- [ ] Deliverable A: [Specific functional behavior, report section, or technical setup]
- [ ] Deliverable B: [Specific quality metrics, visual designs, or data schema]
- [ ] **Self-Resuming State Checkpointing & Resilience**: Create and maintain both `.gemini/tasks/state_journal.json` (programmatic JSON state machine) and `.gemini/tasks/task.md` (interactive checklist) to survive errors, crashes, or context resets.
- [ ] **Forensic Evidence Audit [Forensic Auditor]**: All verification checks, test outputs, and claims must reference an authentic, physical Evidence ID recorded in `.gemini/EVIDENCE.md` with zero synthetic mocks.
- [ ] **E2E Full-Stack Verification [Sentinel]**: Multi-step end-to-end integration journeys, API workflows, and browser tests executed and verified with exit code 0.
- [ ] **Programmatic Evidence Validation [Sentry]**: An automated verification script (`validate_evidence.py`) must be executed successfully during auditing to programmatically verify that all Evidence IDs map to physical output files and actual test run assets on disk.
- [ ] **Memory Consolidation & Agent Dreaming [Mentor]**: Run a background memory consolidation sweep to compile all lessons and preferences into durable long-term storage `.gemini/knowledge/MEMORY.md`.
</GOAL>

<TASK_BREAKDOWN>
Deconstruct the objective into structured, staged Milestones concluding with a dedicated Final E2E Convergence Milestone:

### Milestone 1: Context Grounding & Living Blueprint Inception [Scout/Architect]
- [ ] Ingest the current codebase, active files, or guidelines. Avoid any speculation on technical APIs.
- [ ] **Living Blueprint Inception**: Analyze task across 4 dimensions (Decomposability, Uncertainty, Adversarial Risk, Verification Rigidity) and synthesize `blueprint.json` and `task_graph.json` under `.gemini/prompts/<SHORT_ID>/`.
- [ ] **Data Contract & Schema Freeze**: Formulate and validate all inter-module Pydantic/JSON contracts in `.gemini/knowledge/<SHORT_ID>/architecture/data_contracts.md`.
- [ ] Initialize execution state from `.gemini/tasks/state_journal.json` and `.gemini/tasks/task.md`.

### Milestone 2: Parallel Component Construction & Adversarial Stress Duels [Builder/Challenger]
- [ ] Dispatch parallel Builder subagents in isolated workspaces (`Workspace: "branch"`) to implement modular components.
- [ ] **Adversarial Stress Testing**: Challenger subagents attack implementations with boundary fuzzing, race condition simulations, and poison pill injections.
- [ ] **Dialectical Reconciliation & In-Flight Mutation**: Synthesizer / Arbiter resolves conflicts and injects remediation nodes if Challengers uncover defects (capped at `MAX_MUTATIONS=4`).
- [ ] **Forensic Proof Gate**: Forensic Auditor verifies non-mocked execution and stamps SHA-256 evidence hashes.

### Milestone 3: Cross-Module Integration & Security/A11y Audit [Sentry/Critic]
- [ ] Synchronize and merge all parallel branches at the Milestone Barrier Gate.
- [ ] Run automated vulnerability scans (`run-security-scanner`) and dependency checks (`scan_dependencies`).
- [ ] Verify frontend rendering and layout alignment via Chrome DevTools (`browser_subagent`).

### Milestone Final: Full-Stack Assembly, End-to-End (E2E) Integration Testing & Sentinel Sign-off [Sentinel/Forensic]
- [ ] **Full System Assembly**: Assemble all backend routes, database migrations, message queues, and UI components into a unified execution environment.
- [ ] **End-to-End User Journey Tests**: Execute multi-step user scenarios covering CLI commands, REST/GraphQL API workflows, and browser interactions from start to finish.
- [ ] **Holistic Sentinel Sign-off**: Verify 100% Plan-to-Artifact Parity, ensure zero "TODO" placeholders remain, and run `validate_evidence.py` to confirm all evidence logs match physical disk reality.
- [ ] Generate comprehensive walkthrough report named `walkthrough.md` in workspace root.

### Post-Execution: Asynchronous Memory Consolidation & Agent Dreaming [Mentor]
- [ ] **Light Phase (Ingestion)**: Scan workspace, checklists, and logs to stage significant changes and decisions, pruning scratch files.
- [ ] **REM Phase (Reflection)**: Synthesize patterns, procedural recipes, and preferences. Crystallize novel successful blueprints.
- [ ] **Deep Phase (Promotion)**: Promote high-importance insights to durable storage in `.gemini/knowledge/MEMORY.md`.
</TASK_BREAKDOWN>

<CONSTRAINTS>
1. **Zero Monolithic Files**: Maximum 150 lines per generated file. Large modules must be decomposed, with each file concluding with `# END OF FILE: <path>` and passing syntax validation (`py_compile`/`node --check`).
2. **Mandatory Dual Test Suite Coverage**: Implement BOTH unit/integration tests (`tests/test_*.py` via `pytest`) AND BDD feature specifications (`features/*.feature` via `behave` Gherkin) across all domain problem statements.
3. **100% Static Typing & Google Docstrings**: All Python functions, classes, and helper scripts must include explicit PEP8 type annotations (`typing`/Pydantic) and Google-style docstrings (`Args:`, `Returns:`, `Raises:`).
4. **100% Plan-to-Artifact Parity**: Every file, module, or document promised in `task.md` or `implementation_plan.md` MUST physically exist on disk with complete executable content.
5. **Anti-Mock Forensic Proof**: BDD, unit, and E2E tests must execute genuine runtime code. Hardcoded heuristic returns or synthetic mocks that bypass core logic are strictly rejected by the Forensic Auditor.
6. **Mandatory E2E Integration Pass**: The project CANNOT be marked complete without executing the final full-stack E2E integration milestone.
7. **100% Cloud Resource Parameterization**: IaC files (`.tf`) must contain zero hardcoded ARNs, credentials, or subnet IDs.
8. **Programmatic Evidence Verification**: No task checkbox `[x]` may be marked complete without passing `validate_evidence.py` to confirm physical disk existence and non-empty size for all reported Evidence IDs.
</CONSTRAINTS>

<DEFINITION_OF_DONE>
### Mandatory Acceptance Criteria & Artifact Parity
- [ ] **Physical Code Assets**: All declared implementation files exist on disk with complete functionality, zero "TBD" stubs, and end with `# END OF FILE: <path>`.
- [ ] **Dual Test Verification**:
  - `pytest tests/` passes with 100% success.
  - `behave features/` passes with 100% scenario steps passing.
- [ ] **Adversarial & Forensic Verification**:
  - Challenger stress tests pass with zero unhandled panics or concurrency races.
  - Forensic Auditor certifies genuine, un-mocked execution traces and valid SHA-256 hashes in `.gemini/EVIDENCE.md`.
- [ ] **Terminal E2E Integration Suite**:
  - Full end-to-end multi-step user journeys and system integration tests execute and pass with exit code 0.
- [ ] **Visual & DOM Interactivity**: Frontend rendering verified via Chrome DevTools / headless browser check without layout overlap.
- [ ] **Security & Quality**: Zero secrets or high-severity vulnerabilities flagged by `run-security-scanner`.
- [ ] **Evidence & Documentation**: `.gemini/EVIDENCE.md` ledger populated and verified by `validate_evidence.py`. Walkthrough documentation compiled in `walkthrough.md`.
</DEFINITION_OF_DONE>

<VERIFICATION_PLAN>
### 1. Automated Verification (Builder/Challenger/Forensic/Sentinel)
- **Unit & Integration Suite**:
  ```bash
  pytest tests/ -v
  ```
- **BDD Behavior Specifications**:
  ```bash
  behave features/
  ```
- **Terminal E2E Integration Suite**:
  ```bash
  pytest tests/e2e/ -v
  ```
- **Programmatic Evidence Audit**:
  ```bash
  python validate_evidence.py
  ```

### 2. Manual, Visual, or Qualitative Audit (Sentry/Sentinel)
- **DOM & Visual Interactivity**: Launch a headless/DevTools browser check to inspect UI components, glassmorphism CSS, light/dark mode toggling, and table nowrap layout rules.
- **Contract & Spec Parity**: Verify that all dataclasses, API endpoints, and UI tables match the exact specifications defined in `<DATA_PROVENANCE_AND_CONTRACTS>`.
</VERIFICATION_PLAN>
```
