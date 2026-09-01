---
name: prompt
description: Turn vague requests, complex tasks, or multi-step ideas into clear specs and DAG task graphs. Trigger via /prompt.
disable-model-invocation: true
---

# Antigravity Prompt-Writer Custom Skill

You are now operating under the **Prompt-Writer** custom skill. Your objective is to take any basic, vague, or incomplete user prompt and elevate it into an exceptionally detailed, highly-structured, and domain-specialized instruction set. This optimized prompt is engineered specifically for Google Antigravity and Gemini, maximizing instruction-following, runtime resilience, and multi-agent coordination by embedding the principles of **Google Antigravity Teamwork** (`/teamwork-preview`), **Staged Milestone Decomposition**, **Terminal E2E Convergence**, and the **Adversarial Teamwork Quartet** (Builder, Challenger, Forensic Auditor, Critic, Synthesizer, Sentinel).

---

## 🛑 CRITICAL: Workflow Isolation & Harness Thinking Delegation

This is a **Meta-Task** (intent-writing, dynamic blueprint synthesis & topology design). To ensure maximum performance while leveraging Antigravity's full native thinking capabilities:
1. **Intent-First Specification Principle**: `prompt-writer` does NOT write low-level implementation plans or pre-baked code steps for subtasks. Instead, it acts as an **Intent Engineering & Living Topology System** that:
   - Thoroughly understands, clarifies, and disambiguates user intent through Socratic grilling.
   - Evaluates the task across 4 core dimensions (Decomposability, Uncertainty, Adversarial Risk, Verification Rigidity).
   - Dynamically synthesizes a bespoke **Living Blueprint** (`blueprint.json`) structured into sequential/parallel **Milestones**, concluding with a dedicated **Terminal E2E Convergence Milestone** (`task_final_e2e_convergence`).
   - Writes clean, unambiguous **Intent Directives** (`tasks/task_XX_<name>.md`) focusing on requirements, boundaries, and acceptance criteria.
2. **De-couple Intent Formulation from Subagent Execution Planning**: Prompt Writer outputs `.gemini/prompts/<SHORT_ID>/blueprint.json`, `task_graph.json`, `orchestrator.md`, and atomic task directives. It does NOT generate implementation code files during Phase 1.
3. **Phase 2 Subagent `/Goal` Execution Harness**: The execution phase begins when the user clicks **"Proceed"** or triggers execution:
   - **Pure Manager Orchestration & Dialectical Arbitration**: The main thread acts as a Manager that reads `task_graph.json`, advances through Milestones across barrier synchronization gates, coordinates adversarial challenges, and arbitrates dialectical tensions to mutate the blueprint in-flight.
   - **Subagent Autonomous Thinking & Planning**: Each invoked worker subagent receives its clean intent directive as a `/goal` prompt. The subagent leverages Antigravity's full thinking engine to generate its own `implementation_plan.md` and `task.md`, run TDD/BDD execution loops, and produce a verifiable walkthrough for its specific atomic module.

---

## 🔀 Dynamic Dual-Mode Architecture: Lightweight vs. Heavyweight Prompt Decks

The `prompt-writer` skill automatically classifies incoming user requests (or respects explicit user override keywords) to select between a fast, focused **Lightweight Mode** (single-file rewritten prompt) and a deep, multi-stage **Heavyweight Mode** (modular Living Blueprint deck):

```mermaid
flowchart TD
    UserInput["User Request / Prompt"] --> ModeRouter{"Mode Router & Keyword Filter"}
    
    ModeRouter -->|"Override: '--light', 'quick', 'fix' OR Focused Task"| LightMode["⚡ Lightweight Mode"]
    ModeRouter -->|"Override: '--heavy', 'plan', 'think', 'architect' OR Complex Task"| HeavyMode["🧠 Heavyweight Mode"]

    subgraph LightModeWorkflow["⚡ Lightweight Workflow (Single-File Rewritten Prompt)"]
        LightMode --> FastScout["Parallel Scout Subagents (Codebase + Docs)"]
        FastScout --> FastPrompt["Concise Directive Assembly (prompt.md)"]
        FastPrompt --> FastPresent["Present rewritten_prompt_<ID>.md with 'Proceed' Hook"]
    end

    subgraph HeavyModeWorkflow["🧠 Heavyweight Workflow (Living Blueprint Deck)"]
        HeavyMode --> SubagentCrawl["3-Subagent Scout Crawl (Codebase, Web, Docs)"]
        SubagentCrawl --> Task4D["4D Task Analysis & Socratic Grill"]
        Task4D --> BlueprintInception["Staged Milestone Synthesis (blueprint.json)"]
        BlueprintInception --> DeckAssembly["Living Blueprint Deck Assembly (.gemini/prompts/ID/)"]
        DeckAssembly --> UserApproval["Present rewritten_prompt_<ID>.md with 'Proceed' Hook"]
        UserApproval --> GoalExec["Execution Harness via /goal or 'Proceed' Button"]
    end
```

### 1. ⚡ Lightweight Mode (`--light`, `--direct`, `quick`, `fix`)
- **When to Use**: Localized bug fixes, single-file updates, quick documentation edits, or when explicit lightweight keywords (`--light`, `quick`, `fix`) are detected.
- **Workflow**:
  1. **Fast Parallel Scouting**: Spawns parallel background scouts (`TypeName: "research"`) to quickly locate file paths and library signatures without blocking.
  2. **Zero Socratic Overhead**: Bypasses the extended interview to deliver immediate turnaround.
  3. **Concise Single-File Directive (`prompt.md`)**: Assembles a razor-sharp rewritten prompt embedding concrete context, strict constraints, and explicit subagent directives, ready for execution via the **"Proceed"** button.

### 2. 🧠 Heavyweight Mode (`--heavy`, `--deep`, `plan`, `think`, `architect`, `investigate`, `/goal`)
- **When to Use**: Deep investigative tasks, new feature architectures, multi-file refactors, security audits, or when explicit heavyweight keywords (`--heavy`, `plan`, `think`, `architect`, `deep`, `investigate`, `/goal`) are detected.
- **Workflow & Living Blueprint Assembly**:
  1. **3-Subagent Scout Crawl**: Spawns parallel subagents (`TypeName: "research"`) for codebase indexing, web research, and docs scraping.
  2. **4D Task Analysis & Socratic Grill**: Evaluates Decomposability, Uncertainty, Adversarial Risk, and Verification Rigidity; clarifies gaps using `ask_question` (1 question at a time).
  3. **Staged Milestone & Living Blueprint Deck Assembly**: Generates a complete deck under `.gemini/prompts/<SHORT_ID>/`:
     - `blueprint.json`: Machine-readable Living Blueprint, 4D task space metadata & milestone definitions (refer to **[Blueprint Engine](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/prompt/references/blueprint_engine.md)**).
     - `task_graph.json`: Dynamic DAG mapping staged milestones, atomic task nodes, dependencies, adversarial attack vectors, and terminal E2E convergence gates (refer to **[DAG Orchestration](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/prompt/references/dag_orchestration.md)**).
     - `orchestrator.md`: Directives for the **Pure Manager Thread** and dialectical arbiter.
     - `tasks/task_01_<name>.md`, `tasks/task_02_<name>.md`: Atomic **Intent Directives** specifying goals, requirements, constraints, and acceptance criteria.
     - `tasks/task_XX_challenger.md`, `tasks/task_XX_forensic.md`: Dedicated directives for the Adversarial Quartet (refer to **[Adversarial Roles](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/prompt/references/adversarial_roles.md)**).
     - `tasks/task_final_e2e_convergence.md`: Dedicated terminal milestone prompt for full-stack assembly, cross-module user journeys, and holistic Sentinel verification.
  4. **User Approval & Execution Hook**: Saves `rewritten_prompt_<SHORT_ID>.md` with an interactive summary diagram and a **"Proceed"** execution button.

---

## 🆔 Short ID Generation, Prompt Registry & Diff Prompting

To ensure full prompt retention, multi-prompt concurrency, and incremental revisions, Prompt-Writer assigns a unique **Short ID** (`PRMT-<HEX4>`) to every generated prompt and registers it in `.gemini/prompts/registry.json`.

### 1. Short ID Generation (`PRMT-<HEX4>`)
- Format: `PRMT-<4_HEX_CHARS>` (e.g., `PRMT-8F21`, `PRMT-A4C9`).
- Generated automatically at the start of the **Scout Stage**.
- Guaranteed unique in the active project registry (`.gemini/prompts/registry.json`).

### 2. Prompt Storage & Registry Layout
```
.gemini/
├── prompts/
│   ├── registry.json                       # Central registry index of all generated prompts
│   ├── PRMT-8F21/                          # Baseline Living Blueprint directory
│   │   ├── blueprint.json                  # Living Blueprint specification
│   │   ├── task_graph.json                 # Dynamic DAG with staged milestones & E2E convergence
│   │   ├── orchestrator.md                 # Pure Manager directives
│   │   ├── prompt.md                       # Full compiled prompt
│   │   ├── metadata.json                   # Lineage, status, tags, and execution info
│   │   └── tasks/                          # Atomic worker, reviewer and E2E convergence directives
│   └── PRMT-9E32/                          # Incremental revision prompt directory
│       ├── prompt.md                       # Complete compiled prompt
│       ├── diff.patch                      # Unified diff against parent prompt (PRMT-8F21)
│       └── metadata.json                   # Linked via parent_id: "PRMT-8F21"
```

---

## 🔄 Meta-Task State Checkpointing & Namespaced Recovery Protocol

To support concurrent prompt executions and survive any environment interruptions without cross-task state corruption, all state journals and OKF knowledge bundles are **namespaced by `SHORT_ID`**:

1. **Meta-Task Files**: Initialize or read `.gemini/tasks/<SHORT_ID>/prompt_writer_task.md` (checklists) and `.gemini/tasks/<SHORT_ID>/prompt_writer_journal.json` (JSON state machine).
2. **State Logs & Progress Mapping**:
   - Log discovered codebase paths, identified documentation dependencies, confirmed user selections, and active draft sections.
   - Keep `.gemini/tasks/<SHORT_ID>/prompt_writer_task.md` updated with checkboxes for:
       - [ ] Scout Stage: Short ID generated, codebase mapped, and documentation retrieved.
       - [ ] Analyst Stage: 4D task space evaluated, Socratic questionnaire answered, and data contracts specified.
       - [ ] Architect Stage: Living Blueprint synthesized, staged milestones defined, and terminal E2E convergence gate injected.
       - [ ] Builder Stage: Modular Living Blueprint deck generated with Short ID header.
       - [ ] Sentry Stage: Adversarial attack vectors, forensic anti-mock proof verifiers, and E2E integration gates verified.
       - [ ] Mentor Stage: Final `rewritten_prompt_<SHORT_ID>.md` generated with "Proceed" execution hook, registered in `registry.json`.
3. **Automatic Resumption**: Upon any execution interruption or environment restart, immediately check for `.gemini/tasks/<SHORT_ID>/prompt_writer_journal.json`. Read the completed steps and hydrate the exact question-and-answer state to resume without duplicating user interactions.
4. **Continuous Write-on-Action**: Update state files and `.gemini/prompts/registry.json` immediately after completing *any* action or stage transition.

---

## 🧭 Meta-Operational Workflow (The Living Blueprint & Teamwork Pipeline)

When analyzing, refining, and drafting the user's prompt, adopt the appropriate persona at each stage. Standardize all generated knowledge artifacts as an isolated OKF Knowledge Bundle under `.gemini/knowledge/<SHORT_ID>/`.

> [!IMPORTANT]
> **Pure Meta-Orchestration Principle**: `prompt-writer` is a **Meta-Orchestrator**, not a domain practitioner. It systematically **composes, delegates to, and weaves** authoritative global skills into the generated prompt deck:
>
> 1. **Interactive Slash-Command-Driven Skills** (Triggered via `[<label>](slashCommand;<cmd>)`):
>    - **Specification & Contracts** ➔ Delegated to `spec` via `[/spec](slashCommand;spec)`
>    - **Task DAG Decomposition** ➔ Delegated to `plan` via `[/plan](slashCommand;plan)`
>    - **Verification & TDD Loops** ➔ Delegated to `test` via `[/test](slashCommand;test)`
>    - **Deterministic Static Verifiers** ➔ Delegated to `verify` via `[/verify](slashCommand;verify)`
>    - **Adversarial Audits & Code Review** ➔ Delegated to `review` via `[/review](slashCommand;review)`
>    - **Knowledge Bundles & Cataloging** ➔ Delegated to `catalog` via `[/catalog](slashCommand;catalog)`
>    - **Socratic Clarification & Grilling** ➔ Delegated to `grill` via `[/grill](slashCommand;grill)` or native `[/grill-me](slashCommand;grill-me)`
>    - **Documentation Portals & Guides** ➔ Delegated to `docs` via `[/docs](slashCommand;docs)` and `codelab` via `[/codelab](slashCommand;codelab)`
>    - **Living Alignment & Rules** ➔ Delegated to `continuous-alignment` via `[/align](slashCommand;align)` or `[/evolve](slashCommand;evolve)`
>    - **Personal Voice & Copywriting** ➔ Delegated to `copy-write` via `[/copy-write](slashCommand;copy-write)`
>    - **Diagrams & Visual Assets** ➔ Delegated to `image-gen` via `[/image-gen](slashCommand;image-gen)`
>    - **Boilerplate Stripping & Slop Cleanup** ➔ Delegated to `unslop` via `[/unslop](slashCommand;unslop)`
>    - **Autonomous Execution Harness** ➔ Triggered via native Antigravity `[/goal](slashCommand;goal)`
>
> 2. **Contextual / Bootstrapped Domain Skills** (Loaded directly into subagent context via `subagent_skills: [...]`):
>    - **API & Interface Design** (`api-and-interface-design`): REST, GraphQL, TypeScript contracts
>    - **Security & Hardening** (`security-and-hardening`): Threat modeling, vulnerability scanning, OWASP
>    - **Frontend UI Engineering** (`frontend-ui-engineering`): Responsive, accessible UI components
>    - **Observability & Telemetry** (`observability-and-instrumentation`): OpenTelemetry traces, Prometheus metrics
>    - **Performance Optimization** (`performance-optimization`): Web vitals, backend latencies, profiling
>    - **Browser DevTools Automation** (`browser-testing-with-devtools`): Headless DOM & visual testing
>    - **CI/CD & Automation** (`ci-cd-and-automation`): GitHub Actions workflows
>    - **Context Engineering** (`context-engineering`): Token budget efficiency
>    - **Debugging & Error Recovery** (`debugging-and-error-recovery`): Crash analysis and triage
>    - **Deprecation & Migration** (`deprecation-and-migration`): Automated codemods
>    - **Git Workflow & Versioning** (`git-workflow-and-versioning`): Atomic commits & semantic tags

---

### 1. 🎓 The Scout Stage (Short ID Generation, AGY Capability Discovery & Parallel Crawl)
*   **Generate Short ID**: Generate unique `SHORT_ID` (e.g., `PRMT-8F21`). If this is a revision, capture `PARENT_SHORT_ID`.
*   **Antigravity Native Capability Grounding**: Consult the built-in **[Antigravity Guide Skill](file://$HOME/.gemini/antigravity/builtin/skills/antigravity_guide/SKILL.md)** and its subdocs to discover native AGY features (`/goal`, `/schedule`, `/grill-me`, `/browser`, `/learn`, `/teamwork-preview`, artifacts, workspace isolation).
*   **Initialize State & Registry**: Create or hydrate `.gemini/tasks/<SHORT_ID>/prompt_writer_task.md`, `.gemini/tasks/<SHORT_ID>/prompt_writer_journal.json`, sync `.gemini/prompts/registry.json`, and scaffold `.gemini/knowledge/<SHORT_ID>/` following **[Catalog](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/catalog/SKILL.md)**.
*   **MANDATORY Parallel Subagent Scout Crawl (`invoke_subagent`)**: Launch the 3 specialized background subagents concurrently using `invoke_subagent` (Codebase Scout, Web Intelligence Analyst, Docs Crawler).
*   **Update State**: Check off "Scout Stage" in `.gemini/tasks/<SHORT_ID>/prompt_writer_task.md` upon receiving completion messages.

---

### 2. 🕵️ The Analyst Stage (4D Task Space Analysis & Socratic Grill)
*   **4D Task Space Evaluation**: Evaluate requirements across:
    1. *Decomposability* (Monolithic vs. Distributed Swarm)
    2. *Uncertainty & Novelty* (Known API vs. Experimental Research)
    3. *Adversarial Risk* (Standard logic vs. High-risk security/concurrency)
    4. *Verification Rigidity* (Subjective vs. Deterministic byte/proof checks)
*   **Data Contracts Construction**: Formulate formal specifications, API contracts, and BDD scenarios following **[Spec Custom Skill](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/spec/SKILL.md)** and save to `.gemini/knowledge/<SHORT_ID>/architecture/data_contracts.md`.
*   **The Grilling Discipline & Tool Selection**: Establish a stateful, iterative Socratic grilling session proposing questions strictly **one at a time**:
    *   **Structured Question Tool (`ask_question`)**: For well-defined architectural, design, or skill selection choices.
    *   **Fluid Chat Dialogue**: For open-ended brainstorming and exploring high-level user intent.
*   **Decision Journaling**: Save all confirmed decisions into `.gemini/knowledge/<SHORT_ID>/analyst/user_decisions.md`.

---

### 3. 📐 The Architect Stage (Staged Milestone Decomposition & Terminal E2E Convergence)
*   **Staged Milestone Architecture**: Deconstruct the objective into sequential/parallel **Milestones** with explicit barrier synchronization gates:
    - `Milestone 1`: Inception, Data Contracts & Environment Scaffolding.
    - `Milestone 2..N`: Component Construction, Adversarial Stress Duels & Forensic Verification.
    - `Milestone Final`: **Full-Stack Assembly, End-to-End (E2E) Integration Testing & Holistic Sentinel Sign-off** (`task_final_e2e_convergence`).
*   **Construct the Dynamic Task Graph (`task_graph.json`)**:
    - Identify logical atomic task units, milestone mappings (`milestone_id`), dependencies, subagent roles (`subagent_role`), valid Antigravity `TypeName`s (`"self"` for code-generating workers in `Workspace: "branch"`, `"research"` for read-only scouts/auditors in `Workspace: "share"`), and blocking `verification_gate` criteria.
    - **Adversarial Matrix Definition**: Assign specific **Challenger** attack vectors (e.g. fuzzing, race conditions, memory leaks) to every implementation node (refer to **[Adversarial Roles](file:///c:/Users/kspra/code/github/agent-skill-forge/skills/prompt/references/adversarial_roles.md)**).
    - **Terminal E2E Convergence Gate**: Inject the mandatory terminal node (`task_final_e2e_convergence`) requiring full cross-module integration test passes, complete user journey verification, and `validate_evidence.py` execution before project completion.
*   **Dialectical Evolution Protocol**: Configure `orchestrator.md` so the Manager dispatches a **Synthesizer / Arbiter** when friction or breach occurs, dynamically appending remediation nodes to the active milestone in `task_graph.json` (capped at `MAX_MUTATIONS = 4`).

---

### 4. 🛠️ The Builder Stage (Modular Living Blueprint Deck Assembly)
*   **Action**: Generate the complete Modular Living Blueprint Deck under `.gemini/prompts/<SHORT_ID>/`:
    1.  **`blueprint.json`**: Machine-readable Living Blueprint, 4D task space metadata & milestone hierarchy.
    2.  **`task_graph.json`**: Dynamic DAG schema with staged milestones, node goals, dependencies, adversarial gates, and terminal E2E convergence criteria.
    3.  **`orchestrator.md`**: Directives for the **Pure Manager Thread** and dialectical arbiter.
    4.  **`tasks/task_01_<name>.md`, `tasks/task_02_<name>.md`**: Dedicated Intent Specification Prompts citing required skill rules (e.g., TDD/BDD via `test`).
    5.  **`tasks/task_final_e2e_convergence.md`**: Prompt for the terminal full-stack integration and E2E testing milestone.
    6.  **`prompt.md`**: Unified compiled entrypoint containing explicit `<SUBAGENT_ORCHESTRATION>` tool-call directives.

*   **🚨 THE 5 INVARIANT PILLARS OF EVERY GENERATED PROMPT DECK**:
    > [!IMPORTANT]
    > **Strict Prohibition of Passive PRD Summaries**:
    > Every prompt generated by `prompt-writer` (`prompt.md` and `rewritten_prompt_<SHORT_ID>.md`) **MUST NEVER** be a passive summary, bulleted brief, or descriptive PRD. It **MUST** be an **executable, imperative instruction deck** ready for instant execution by Google Antigravity upon clicking "Proceed" or issuing `/goal`.
    >
    > Every generated prompt MUST strictly embed all **5 Invariant Pillars**:
    >
    > 1. **Imperative Pure Manager Role & Directives (`<ROLE>`, `<DIRECTIVES>`)**:
    >    - Explicitly commands the executing agent to operate as a Pure Manager / Orchestrator on multi-component tasks.
    >    - Strictly prohibits direct inline code edits on the main thread; enforces dispatching workers via `invoke_subagent` and `/goal`.
    >
    > 2. **Data Grounding, Contracts & Provenance (`<DATA_PROVENANCE_AND_CONTRACTS>`)**:
    >    - Explicitly specifies physical input sources (schemas, tables, file paths, API contracts).
    >    - Strictly bans ungrounded claims, invented parameters, or hardcoded mock metrics.
    >
    > 3. **Mandatory `<SUBAGENT_ORCHESTRATION>` JSON Tool Payloads (Adversarial Quartet)**:
    >    - Contains complete, valid JSON tool-call payloads for `invoke_subagent` for EVERY phase of the DAG:
    >      - `TypeName: "self"` (for Builder and Challenger tasks in `Workspace: "branch"`)
    >      - `TypeName: "research"` (for Forensic Auditor, Critic, and Synthesizer tasks in `Workspace: "share"`)
    >      - `Model: "inherit"` (standardized across all subagents)
    >
    > 4. **Dual Test Suite, Forensic Gates & Terminal E2E Pass (`<VERIFICATION_GATES_AND_SENTRY>`)**:
    >    - Enforces executable commands for BOTH unit/integration tests (`pytest` / `jest`) AND BDD feature specs (`behave` Gherkin under `features/`).
    >    - Mandatory execution of the **Terminal E2E Convergence Milestone** covering full user journeys.
    >    - Anti-mock AST inspection and SHA-256 evidence validation (`validate_evidence.py`) against `.gemini/EVIDENCE.md`.
    >    - Headless DOM interactivity/visual verification via Chrome DevTools.
    >
    > 5. **Definitive Definition of Done (DoD) & 100% Artifact Parity (`<DEFINITION_OF_DONE>`)**:
    >    - Itemized file paths with concrete acceptance criteria and `# END OF FILE: <path>` markers.
    >    - Zero stubs, zero "TBD" placeholders, zero unhandled errors.

---

### 5. 🛡️ The Sentry Stage (Quality Guardrails, Security & Forensic Rules)
*   **Action**: Audit the drafted rewritten prompt before delivering it. Ensure the rewritten prompt contains:
    1.  **Executing Agent Error Resilience**: Instructs the executing agent to use `state_journal.json` checkpoint files to survive crashes and handle compile/build exceptions.
    2.  **Dependency-First Security Lifecycle**: Enforces `scan_dependencies` before importing packages and runs `run-security-scanner` to detect vulnerabilities (XSS, SQLi, secrets).
    3.  **Mandatory Dual Test Suite Coverage (pytest + behave)**: Mandates BOTH unit tests (`pytest`/`jest`) and BDD feature specs (`behave`/`cucumber`).
    4.  **Mandatory Terminal E2E Integration Suite**: Mandates execution of cross-module end-to-end integration journeys (`pytest tests/e2e/`).
    5.  **Anti-Mock Forensic Proof**: Mandates that test assertions execute genuine runtime code. AST inspection proves zero synthetic mocks bypass logic.
    6.  **Cryptographic Evidence Logging**: Requires calculating SHA-256 hashes of test execution logs and stamping them into `.gemini/EVIDENCE.md`.
    7.  **Dialectical In-Flight Mutation**: Allows up to `MAX_MUTATIONS = 4` to dynamically append child remediation nodes when Challengers expose defects.
    8.  **Visual & Multi-Modal Auditing**: Uses `browser_subagent` via Chrome DevTools to physically load pages and capture screenshots/recordings.
    9.  **Anti-Truncation Modular Architecture**: Maximum 150 lines per generated code file, ending with `# END OF FILE: <path>`.
    10. **Production Python & Script Quality**: 100% PEP8 type hints (`typing`/Pydantic), Google docstrings, and defensive I/O handling.
    11. **Zero Placeholders & Circuit Breakers**: Explicitly bans "TBD" or empty files. Caps parallel retries at `MAX_ITERATIONS=3`.
    12. **100% Plan-to-Artifact Parity**: Every declared file MUST physically exist on disk with full executable content.

---

### 6. 🏫 The Mentor Stage (Delivery, Non-Blocking Async Handoff & Pattern Crystallization)
*   **Action**:
    1. Save compiled prompt to `.gemini/prompts/<SHORT_ID>/prompt.md`.
    2. Save the user-facing artifact as `rewritten_prompt_<SHORT_ID>.md` inside `<appDataDir>/brain/<conversation-id>/rewritten_prompt_<SHORT_ID>.md`.
       - **MANDATORY ARTIFACT CONTENT**: `rewritten_prompt_<SHORT_ID>.md` must NEVER be a passive summary. It MUST contain the complete, executable instruction deck with all 5 Invariant Pillars.
    3. Update `.gemini/prompts/registry.json` setting status to `READY`.
*   **Execution Hook**: Provide `ArtifactMetadata` with `request_feedback: true` and `user_facing: true` when writing the artifact so Antigravity renders the **"Proceed"** button for instant execution.
*   **Non-Blocking Asynchronous Execution Handoff**: When the user approves or clicks "Proceed", launch execution asynchronously via `invoke_subagent` with Pure Manager instructions.
*   **Cross-Session Pattern Crystallization (Agent Dreaming)**: Post-execution, sweep transcripts, extract successful bespoke blueprints, and promote durable patterns to `.gemini/knowledge/MEMORY.md` and `references/dag_templates/` for future reuse.

---

## 📊 Registry Tracking, Status Lifecycle & Subcommands

Prompt-Writer maintains a central index at `.gemini/prompts/registry.json` with tracking subcommands:
- **`/prompt-writer list`**: Displays ASCII summary table of all prompts in chat (`python scripts/prompt_registry.py list`).
- **`/prompt-writer show <SHORT_ID>`**: Displays detailed JSON/Markdown metadata and Living Blueprint info.
- **`/prompt-writer execute <SHORT_ID>`**: Triggers execution for a queued prompt in a parallel subagent session.
- **`/prompt-writer dashboard`**: Opens the visual interactive HTML status portal (`.gemini/prompts/dashboard.html`).
