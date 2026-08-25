# 🌙 Dream Sequence Protocol: Retrospective Intelligence & Continuous Evolution

The **Dream Sequence** is a dual-loop reflection and synthesis mechanism designed to prevent AI complacency, eliminate subtle edge-case gaps, and ensure lifelong learning across agent sessions.

---

## 🔁 1. Dual-Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           IN-FLIGHT DREAM LOOP (During Task DAG)                         │
│                                                                                         │
│   [ Implementation Nodes ] ──► [ Retrospective Checkpoint ]                             │
│                                           │                                             │
│                                           ▼ (Adversarial Audit & Gap Analysis)          │
│                              ┌─────────────────────────┐                                │
│                              │ Gaps / Flaws Detected?   │──► [ Append Evolution Nodes ] │
│                              └────────────┬────────────┘           │                    │
│                                           │ (ZERO_GAPS)            ▼                    │
│                                           ▼            [ Re-execute & Re-evaluate ]     │
│                               [ Verification Passed ]                                   │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                      CROSS-SESSION DREAM SEQUENCE (Offline Memory Consolidation)        │
│                                                                                         │
│  1. Ingest Transcripts:  <appDataDir>/brain/<id>/.system_generated/logs/transcript.jsonl│
│  2. Telemetry Extract:   User corrections, tool failure patterns, repetitive commands   │
│  3. OKF Synthesis:       Compile findings into .gemini/knowledge/ concept docs           │
│  4. Rule Consolidation:  Update AGENTS.md, CLAUDE.md, and skill definitions via /learn   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 2. Loop A: In-Flight Dream Cycle (Self-Evolving Task DAG)

During execution of a `task_graph.json`, the Manager thread enforces the **Never-Satisfied Orchestration Rule**:

### Step 1: Retrospective Checkpoint Trigger
At key integration milestones (e.g. post-core-logic, post-integration, post-test), the Manager dispatches a specialized **Sentry / Critic Subagent** via `/goal`:
- **Role**: Sentry - Adversarial Reviewer & Critic
- **Attached Skills**: `review`, `expectation-harness`, `doubt-driven-development`
- **Model**: `inherit`
- **Directive**: Adversarially challenge the implementation against the original intent specification in `.gemini/prompts/<SHORT_ID>/prompt.md`.

### Step 2: Gap & Friction Analysis
The Critic executes:
1. **Static Spec Compliance**: Runs `verify_okf.py` on all concept docs and verifies zero placeholder text (`TODO`, `TBD`).
2. **Behavioral Edge Cases**: Probes error handling, network failure recovery, concurrency races, and validation boundaries.
3. **5-Axis Review**: Correctness, readability, architecture, security, and performance.

### Step 3: Dynamic DAG Evolution
- If flaws are found, the Critic returns a structured proposal:
  ```json
  {
    "status": "GAPS_IDENTIFIED",
    "gaps": [
      "Missing exponential backoff on HTTP 429 retries",
      "Table cell text wrapping in markdown views"
    ],
    "evolution_tasks": [
      {
        "id": "task_04_evolution_retry_backoff",
        "name": "Implement exponential jitter backoff in client SDK",
        "subagent_role": "Backend Engineer",
        "subagent_skills": ["source-driven-development", "test"]
      }
    ]
  }
  ```
- The Manager **dynamically appends** these new child nodes to `task_graph.json` and dispatches worker subagents to resolve them.
- Execution loop repeats until the Critic explicitly returns:
  ```
  STATUS: OPTIMAL / ZERO_GAPS
  ```

---

## 🌌 3. Loop B: Cross-Session Dream Sequence (Lifelong Memory Ingestion)

The Cross-Session Dream Sequence processes historical telemetry from Antigravity session transcripts to continuously upgrade the agent's behavior:

### Step 1: Transcript Ingestion
Session logs are located at:
`<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`

The Dream parser extracts:
- `USER_INPUT` steps where user corrected the agent or clarified intent.
- `PLANNER_RESPONSE` steps where tool errors or command retries occurred.
- Repetitive command chains that can be automated as standalone custom skills.

### Step 2: Knowledge Distillation
Extracted insights are converted into standard **OKF Concept Documents** under `.gemini/knowledge/`:
- `scout/codebase_map.md` (Updated dependencies and endpoints)
- `analyst/user_decisions.md` (Codified user preferences, UI styling rules, CLI aliases)
- `sentry/secure_threat_model.md` (Discovered failure modes and mitigations)

### Step 3: Rule & Skill Upgrades
- High-confidence global habits are written to `~/.gemini/config/AGENTS.md` and `~/.claude/CLAUDE.md`.
- As Antigravity introduces new platform features (e.g. updated slash commands, hooks, auxiliary panes), the Dream cycle integrates these features into `prompt-writer` references, ensuring prompt generation never becomes stale.

---

## 🛠️ 4. Integration with Antigravity Native Mechanics

| Native AGY Feature | Role in Dream Sequence |
| :--- | :--- |
| **`/goal`** | Dispatches the Critic subagent with an autonomous objective that doesn't terminate until verification is solid. |
| **`invoke_subagent`** | Spawns isolated Critic in `Workspace: "share"` to audit files without risking accidental overwrites. |
| **`verify_okf.py`** | Machine-verifiable gate verifying documentation and knowledge completeness. |
| **`/learn`** | User-facing slash command to manually promote a Dream insight into permanent memory. |
| **Artifacts (`walkthrough.md`)** | Embeds diffs, test logs, and retrospective summaries for user transparency. |
