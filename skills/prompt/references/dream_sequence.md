# 🌙 Dream Sequence Protocol: Dialectical Evolution & Continuous Memory

The **Dream Sequence** is a dual-loop reflection, synthesis, and mutation mechanism designed to prevent AI complacency, eliminate subtle edge-case gaps, and ensure lifelong learning across agent sessions.

---

## 🔁 1. Dual-Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                      LOOP A: IN-FLIGHT DIALECTICAL EVOLUTION (Task Runtime)              │
│                                                                                         │
│   [ Producer / Builder ] ──► [ Challenger Stress Probe ]                                │
│                                      │                                                  │
│                                      ▼ (Adversarial Breach / Friction Detected?)        │
│                       ┌───────────────────────────────┐                                 │
│                       │ Breach / Broken Assumption?   │──► [ Synthesizer Arbitrates ]   │
│                       └──────────────┬────────────────┘          │                      │
│                                      │ (Zero Breaches)           ▼                      │
│                                      ▼                 [ Mutate Living Blueprint ]      │
│                       [ Forensic Proof Audit ]                   │                      │
│                                      │                           ▼                      │
│                                      ▼ (Exit Code 0 & Hashed) [ Re-execute & Re-probe ] │
│                           [ Node Verified ]                                             │
└──────────────────────────────────────┬──────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                   LOOP B: CROSS-SESSION DREAM SEQUENCE (Offline Memory Ingestion)       │
│                                                                                         │
│  1. Ingest Transcripts:  <appDataDir>/brain/<id>/.system_generated/logs/transcript.jsonl │
│  2. Telemetry Extract:   User corrections, tool failures, mutation trigger patterns     │
│  3. Pattern Crystal:     Promote successful bespoke blueprints to pattern library       │
│  4. Rule Consolidation:  Update AGENTS.md, CLAUDE.md, and skills via continuous-alignment │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 2. Loop A: In-Flight Dialectical Evolution (Self-Evolving Task DAG)

During execution of a `task_graph.json`, the Manager thread enforces the **Never-Satisfied Orchestration Rule**:

### Step 1: Challenger Adversarial Probe
When the Producer completes an implementation node, the Manager launches a specialized **Challenger Subagent**:
- **Role**: `Challenger - Adversarial Fuzzer & Stress Tester`
- **Attached Skills**: `review`, `test`, `security-and-hardening`
- **Model**: `inherit`
- **Directive**: Actively attempt to break the implementation with boundary fuzzing, race conditions, memory leaks, or unhandled exceptions.

### Step 2: Synthesizer Arbitration & Blueprint Mutation
If the Challenger detects a failure or architectural friction:
1. The **Synthesizer / Arbiter** evaluates the root cause and updates the data contract in `.gemini/knowledge/<SHORT_ID>/architecture/data_contracts.md`.
2. The Manager **mutates the Living Blueprint**, appending dedicated remediation nodes (`task_XX_mutation_remediate`) and incrementing `mutation_generation`.
3. Execution re-runs the remediation node followed by a fresh Challenger re-probe.

### Step 3: Forensic Proof & Anti-Mock Sign-off
Once the Challenger confirms zero breaches:
1. The **Forensic Auditor** executes tests on the physical disk environment.
2. The Auditor parses the test AST to ensure assertions are grounded in real execution rather than synthetic mocks.
3. Raw execution logs and SHA-256 evidence hashes are recorded in `.gemini/EVIDENCE.md`.
4. The node transitions to `VERIFIED`.

---

## 🌌 3. Loop B: Cross-Session Dream Sequence (Lifelong Memory Ingestion)

The Cross-Session Dream Sequence processes historical telemetry from Antigravity session transcripts to continuously upgrade the agent's behavior:

### Step 1: Transcript Ingestion
Session logs are located at:
`<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`

The Dream parser extracts:
- `USER_INPUT` steps where user corrected the agent or clarified intent.
- `PLANNER_RESPONSE` steps where tool errors or command retries occurred.
- In-flight mutation patterns that successfully resolved novel bugs.

### Step 2: Knowledge Distillation & Pattern Crystallization
Extracted insights are converted into standard **OKF Concept Documents** under `.gemini/knowledge/`:
- `scout/codebase_map.md` (Updated dependencies and endpoints)
- `analyst/user_decisions.md` (Codified user preferences, UI styling rules, CLI aliases)
- `sentry/secure_threat_model.md` (Discovered failure modes and mitigations)
- `patterns/crystallized_patterns.json` (Novel bespoke blueprints saved for future reuse)

### Step 3: Rule & Skill Upgrades
- High-confidence global habits are written to `~/.gemini/config/AGENTS.md` and `~/.claude/CLAUDE.md`.
- Living architectural patterns are indexed via `catalog` and synced via `continuous-alignment`.

---

## 🛠️ 4. Integration with Antigravity Native Mechanics

| Native AGY Feature | Role in Dream Sequence |
| :--- | :--- |
| **`/goal`** | Dispatches Challenger and Forensic Auditor subagents with autonomous non-terminating objectives. |
| **`invoke_subagent`** | Spawns isolated workers in `Workspace: "branch"` and auditors in `Workspace: "share"`. |
| **`verify_okf.py`** | Machine-verifiable gate verifying documentation and knowledge completeness. |
| **`/learn`** | User-facing slash command to manually promote a Dream insight into permanent memory. |
| **Artifacts (`walkthrough.md`)** | Embeds diffs, forensic evidence logs, and retrospective summaries for user transparency. |
