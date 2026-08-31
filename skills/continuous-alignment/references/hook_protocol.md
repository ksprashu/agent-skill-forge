# Antigravity Lifecycle Hook Protocol Specification

This document defines the interface and lifecycle contracts between the Antigravity agent runtime and the `continuous-alignment` engine.

---

## 1. Supported Hook Triggers

### 1.1 `Stop` Event (Turn-Completion Distillation)
* **Trigger Timing**: Invoked synchronously after the agent completes all tool calls and finishes its turn.
* **Working Directory**: Directory containing `hooks.json` (usually repository root).
* **Timeout Limit**: Default 45 seconds (must complete < 200ms in practice).

#### Inbound Payload Schema (via `stdin`)
```json
{
  "conversationId": "string (UUID)",
  "workspacePaths": ["string (absolute directory path)"],
  "transcriptPath": "string (absolute file path to transcript.jsonl)",
  "artifactDirectoryPath": "string (absolute path to brain directory)",
  "modelName": "string",
  "terminationReason": "DONE | CANCELLED | ERROR",
  "fullyIdle": true
}
```

#### Outbound Return Contract (via `stdout`)
* **Standard Completion**:
  ```json
  {}
  ```
* **Request Turn Continuation** (if critical invariant is missing or auto-fix triggered):
  ```json
  {
    "decision": "continue",
    "reason": "Living ADR compiled; please review generated decision record."
  }
  ```

---

### 1.2 `PreInvocation` Event (Dynamic Context Invariant Injection)
* **Trigger Timing**: Invoked before the model processes a prompt.
* **Purpose**: Injects real-time workspace rules, active milestone statuses, or path constraints without bloating static system instructions.
* **Command**: `python skills/continuous-alignment/scripts/sync_agents_rules.py --pulse`
* **Timeout Limit**: 15 seconds (target < 50ms).

---

## 2. Error Handling & Fail-Safe Invariants
1. **Never Crash the Agent**: All hook scripts must wrap top-level execution in `try / except Exception` blocks and log warnings to `stderr` or `.gemini/knowledge/alignment_debug.log` rather than exiting with non-zero codes unless a deliberate security veto is intended.
2. **Deterministic & Portable**: All scripts must run on standard Python 3.9+ without external package requirements.
3. **Atomic File Writes**: File modifications to `AGENTS.md`, `.agents/rules/`, and `.gemini/knowledge/` must use atomic temp file swaps to prevent corrupted state if interrupted.
