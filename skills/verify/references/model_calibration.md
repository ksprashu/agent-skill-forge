# Model Calibration: Maximizing Performance Under Fixed Model Constraints

In environments where model selection is uniform or fixed across all subagents (i.e. model tiering cannot be varied dynamically), the `Goal-Harness` framework achieves maximum performance through **Prompt-Level Calibration** and **Context Slicing**.

---

## 1. The Fixed-Model Optimization Problem

When every agent runs on the same model tier, weak or medium models face two failure modes:
1. **Context Bloat / Instruction Dropping**: As conversation history grows, the model misses subtle constraints embedded deep in the prompt.
2. **Context Pollution / Trial-and-Error Confusion**: Failed execution attempts in memory distort the model's judgment on subsequent attempts.

---

## 2. Four Mechanisms for Model Calibration

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      CALIBRATION ARCHITECTURE                             │
├──────────────────────────────┬────────────────────────────────────────────┤
│ 1. Dynamic Context Slicing   │ Prune all non-essential history before    │
│                              │ dispatching task directives.              │
├──────────────────────────────┼────────────────────────────────────────────┤
│ 2. Micro-Chunked Sub-Goals   │ Limit task directives to single-file or    │
│                              │ single-outcome atomic units.               │
├──────────────────────────────┼────────────────────────────────────────────┤
│ 3. Scratchpad State Dumps    │ Force writing intermediate tool state to   │
│                              │ disk (`.gemini/tasks/<ID>/state.json`).    │
├──────────────────────────────┼────────────────────────────────────────────┤
│ 4. Pinpointed Delta Reports  │ Feed only the exact line failure / defect  │
│                              │ report during retry loops.                 │
└──────────────────────────────┴────────────────────────────────────────────┘
```

### Mechanism 1: Dynamic Context Slicing
Never send the global conversation history to worker subagents. Before spawning a worker subagent, the Orchestrator builds a **Clean Context Slice**:
* **Included**:
  - Immediate atomic task spec (`tasks/task_01_spec.md`)
  - Target artifact path (`docs/architecture.md`)
  - Pre-generated static check script / rubric JSON
* **Excluded**:
  - Previous subagent chat transcripts
  - Unrelated codebase exploration logs
  - Raw web search dumps

### Mechanism 2: Micro-Chunked Sub-Goal Slicing
When a complex goal is ingested, the Orchestrator decomposes it into atomic nodes where each node touches **no more than 1-2 files** or **1 discrete deliverable section**.

For example, instead of:
* *"Write the complete system architecture document."*

The Orchestrator creates four micro-chunked nodes:
* Node 1: *"Draft Section 1: System Context & Boundaries"* (Verify & Sign-off)
* Node 2: *"Draft Section 2: Data Models & Pydantic Schemas"* (Verify & Sign-off)
* Node 3: *"Draft Section 3: Security Threat Matrix"* (Verify & Sign-off)
* Node 4: *"Compile & Link Sections into Architecture Spec"* (Verify & Sign-off)

### Mechanism 3: Disk Scratchpad State Persistence
Weak models lose track of intermediate state during multi-step tool calls. The Orchestrator enforces disk scratchpads:
* After every tool invocation, the subagent appends its current working hypothesis and active state to `.gemini/tasks/[SHORT_ID]/scratchpad.json`.
* If a subagent crashes or loses context mid-execution, the Orchestrator resumes execution by reading `scratchpad.json` directly.

### Mechanism 4: Pinpointed Delta Retry Reports
When a static verifier or dynamic judge fails, the retry loop does **not** re-send the full instruction set. It generates a concise **10-line Delta Report**:

```markdown
# RETRY DELTA REPORT (Attempt 2/3)

Your previous implementation failed the Dual-Verification Gate.

## FAILED CHECKS:
1. Static Check: Section 'Security Threat Matrix' is missing.
2. Dynamic Judge Defect: Table 2 lacks explicit mitigation steps for OWASP API #1.

## ACTION REQUIRED:
Edit `docs/architecture.md` to add Section 3 ('Security Threat Matrix') and include the OWASP mitigation table. Do NOT alter Sections 1 or 2.
```
