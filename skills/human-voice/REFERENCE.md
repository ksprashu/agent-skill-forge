# Reference Guide: AI Developer Tool Storage Schemas

This reference lists where each supported tool stores its logs and how its user turns are read. The locations and readers live in `scripts/log_sources.py`, which `cognitive-profiler` ships an identical copy of; `extract_voice.py` calls it and keeps only your own turns.

`<app-data>` below is `~/Library/Application Support` on macOS, `%APPDATA%` on Windows, and `$XDG_CONFIG_HOME` (default `~/.config`) on Linux.

---

## 1. Directory Registry & File Formats

| Assistant Tool | Storage Path | File Type | What counts as your turn |
| :--- | :--- | :--- | :--- |
| **Antigravity CLI** | `~/.gemini/antigravity-cli/brain/` | JSONL (`transcript.jsonl`) | `source: "USER_EXPLICIT"`, or `type: "USER_INPUT"` with no `source`. The `<USER_REQUEST>` envelope is unwrapped. |
| **Antigravity IDE** | `~/.gemini/antigravity/brain/`, `~/.gemini/antigravity-ide/` | JSONL (`transcript.jsonl`) | Same as the CLI. |
| **Gemini CLI** | `~/.gemini/tmp/<project>/` | JSON with a `messages` list, or JSONL | `role`/`type`/`sender` of `user`, or a `user_input` key. |
| **Claude Code** | `~/.claude/projects/<slug>/<session>.jsonl` | JSONL | `type: "user"` records, text from `message.content`. Skips tool results, meta, sidechain (subagent), and compaction records, and slash-command, shell-output, or harness-notice records. |
| **Cline** | `<app-data>/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/` | JSON (`ui_messages.json`) | `say: "user_feedback"` or `say: "task"`, or `role: "user"`. |
| **Roo Code** | `<app-data>/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks/` | JSON (`ui_messages.json`) | Same as Cline. |
| **Aider** | `.aider.chat.history.md`, else `.aider.input.history` or `.aider.history`, in `~`, `~/*`, `~/code/*`, `~/git/*` | Markdown / plain text | `#### ` lines in the chat transcript; `+` lines (or plain lines) in the input history. |
| **Cursor** | `<app-data>/Cursor/User/**/state.vscdb` | SQLite | `ItemTable` rows whose key contains `chat`; chat bubbles with `type: 1` or `role: "user"`. Opened read-only. |

---

## 2. Parsing Schemas

### Antigravity Transcript (`transcript.jsonl`)
Lines are separate JSON documents detailing sequential conversation steps:
```json
{"step_index": 3, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "<USER_REQUEST>Review this repository and write unit tests.</USER_REQUEST>"}
```
* **Extraction Strategy**: Take `content` when `source == "USER_EXPLICIT"`, or when `type == "USER_INPUT"` and no `source` is recorded. Other sources are the harness talking to itself. `--tool antigravity-cli` and `--tool antigravity-ide` read only that surface's directories.

### Gemini CLI Session Chats
Session files hold a message list:
```json
{"messages": [{"type": "user", "content": "Please implement the new feature branch."}, {"type": "gemini", "content": "..."}]}
```
* **Extraction Strategy**: Matches when `role`, `type`, or `sender` is `user`, or a `user_input` key is present. `content` may be a string or a list of `{text}` parts.

### Claude Code Sessions (`<slug>/<session>.jsonl`)
Each line is a record; the turn sits under `message`:
```json
{"type": "user", "timestamp": "2026-09-20T10:00:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "Deploy to cloud run."}]}}
```
* **Extraction Strategy**: Read `type == "user"` records. If `message.content` is a string, take it; if it is a list, join its `type == "text"` parts, and skip the record entirely if any part is a `tool_result` (that is the harness feeding output back). Skip records marked `isMeta`, `isSidechain`, or `isCompactSummary`, and text starting with `<command-`, `<local-command`, `<bash-`, `Caveat:`, `<task-notification`, or `<system-reminder`.

### Cline & Roo Code task histories (`ui_messages.json`)
Consists of a JSON array containing UI logs:
```json
[
  {
    "type": "say",
    "say": "user_feedback",
    "text": "Tighten the spacing on the summary page."
  }
]
```
* **Extraction Strategy**: Loop through array. Extract `text` when `say` is `user_feedback` or `task`. `say == "text"` is the assistant, and `ask == "followup"` is the assistant asking you.

### Aider (`.aider.chat.history.md`, `.aider.input.history`)
The chat transcript marks your input with `#### ` and aider's own output with `> `:
```markdown
# aider chat started at 2026-09-20 10:00:00
> Added app.py to the chat.
#### add a retry to the upload call
```
* **Extraction Strategy**: Consecutive `#### ` lines form one turn. The input history is used only where no chat transcript sits beside it, since both record the same prompts.

### Cursor SQLite Databases (`state.vscdb`)
Chat state is a JSON blob in the `ItemTable` key-value table:
```sql
SELECT value FROM ItemTable WHERE key LIKE '%chat%';
```
* **Extraction Strategy**: Walk the JSON for objects carrying `text` (longer than 15 characters) and a role marker: `type: 1` or `role: "user"` is you, `type: 2` or `role: "assistant"` is the model. The database is opened read-only, and as immutable if Cursor holds a lock.

---

## 3. Linguistic & Behavioral Heuristics
The extractor applies static heuristics to synthesize tone parameters:
1. **Average Word Count**: Sum of words across extracted prompts divided by total counts. High-efficiency personas show average word counts between 20-60 words. Technical leader personas show 100+ words.
2. **Commonwealth Spelling Check**: Searches for key words containing `behaviour`, `optimise`, `prioritise`, `customise`. If occurrences exceed a low threshold, the writing dialect is classified as British/Commonwealth.
3. **Punctuation Triggers**: Counts double question marks (`??`) and ellipsis (`...`) to classify "conversational speed-typing" and "dialogue-driven debugging" frequency.
4. **Fingerprint Rates**: The share of prompts using em-dashes, `->`/`=>` arrows and contractions. These fill the matching lines of the draft profile; nothing else is inferred.
