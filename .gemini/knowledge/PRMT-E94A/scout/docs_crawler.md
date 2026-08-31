# PRMT-E94A: Antigravity Lifecycle Hooks Specification & Contracts

## 1. Hook Registration & Discovery
- **Discovery Locations**:
  1. `<project-root>/.agents/hooks.json`
  2. `<project-root>/.gemini/hooks.json`
  3. `~/.gemini/config/hooks.json` (global)
  4. Plugin manifests (`<plugin-dir>/hooks.json`)

- **JSON Schema**:
```json
{
  "<hook-group-name>": {
    "<EventName>": [
      {
        "type": "command",
        "command": "python path/to/script.py",
        "timeout": 45,
        "matcher": "exact_tool_name_or_regex"
      }
    ]
  }
}
```

---

## 2. Supported Event Types
1. **`PreInvocation`**: Fires right before a prompt is processed. Can inject dynamic project context or instructions.
2. **`PostInvocation`**: Fires after prompt processing completes.
3. **`PreToolUse`**: Fires before a tool executes (supports `matcher` filter).
4. **`PostToolUse`**: Fires after a tool finishes execution (supports `matcher` filter).
5. **`Stop`**: Fires at turn completion when the agent finishes its tool execution and prepares to yield control to the user. Ideal for memory distillation, living ADR updates, and document compilation.

---

## 3. Stdin & Stdout Contract Schema

### Stdin Payload (Stop Event)
The Antigravity runtime pipes JSON directly to the script via standard input (`stdin`):
```json
{
  "conversationId": "95e4ec5c-10ab-420f-abbd-af7553e5fac1",
  "workspacePaths": [
    "/Users/ksprashanth/code/github/agent-skill-forge"
  ],
  "transcriptPath": "/Users/ksprashanth/.gemini/antigravity/brain/95e4ec5c-10ab-420f-abbd-af7553e5fac1/.system_generated/logs/transcript.jsonl",
  "artifactDirectoryPath": "/Users/ksprashanth/.gemini/antigravity/brain/95e4ec5c-10ab-420f-abbd-af7553e5fac1",
  "modelName": "gemini-2.5-pro",
  "terminationReason": "DONE",
  "fullyIdle": true
}
```

### Stdout Output Contract
- Normal completion: `{}` or clean JSON exit.
- Request continuation: `{"decision": "continue", "reason": "Follow-up verification required"}`.
- Blocking error: Exit code `2` with explanation in `stderr`.

---

## 4. Execution Sandbox & Timeouts
- **Execution Model**: Runs synchronously via subshell (`sh -c`) in the directory containing `hooks.json` or project root.
- **Timeout**: Configurable per hook item in seconds (`timeout: 45`). Default is 60s.
- **Fail-Safe**: Scripts should catch internal exceptions and emit clean logs to prevent blocking the agent execution loop unexpectedly.
