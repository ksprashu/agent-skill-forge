# Reference Guide: AI Developer Tool Storage Schemas

This reference details the default storage locations, file formats, and data schemas for all supported AI developer assistant interfaces on macOS. It is utilized by the `extract_voice.py` script to parse prompts and construct writing style templates.

---

## 1. Directory Registry & File Formats

| Assistant Tool | Storage Path on macOS | File Type | Parser Method |
| :--- | :--- | :--- | :--- |
| **Antigravity CLI** | `~/.gemini/antigravity-cli/brain/*/` | JSONL | Parse line-by-line JSON objects, searching for `type: "USER_INPUT"` or `source: "USER_EXPLICIT"`. |
| **Gemini CLI** | `~/.gemini/tmp/*/chats/` | JSONL | Parse lines to match role-based keys (`role: "user"`, `sender: "user"`, or `user_input`). |
| **Claude Code** | `~/.claude/projects/*/` | JSONL | Parse file `chat_*.jsonl`, searching for `role: "user"` inside JSON lines. Handles list and string values. |
| **Cline** | `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/` | JSON | Parse `ui_messages.json` inside each task folder, matching objects with `sender: "user"` or `type: "say"`. |
| **Roo Code** | `~/Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks/` | JSON | Parse `ui_messages.json` identical to Cline, extracting text contents. |
| **Aider** | `~/.aider.history` (Global)<br>`.aider.chat.history.md` (Local workspace) | Plain Text / Markdown | Parse line-by-line commands in `.history`, and match blockquotes (`>`) in local markdown. |
| **Cursor** | `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` | SQLite (vscdb) | Query `globalState` table for keys containing `"chat"` or `"composer"`, parse nested JSON strings. |

---

## 2. Parsing Schemas

### Antigravity CLI Transcript (`transcript.jsonl`)
Lines are separate JSON documents detailing sequential conversation steps:
```json
{"step_index": 3, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "Review this repository and write unit tests."}
```
* **Extraction Strategy**: Inspect `type == "USER_INPUT"` and `source == "USER_EXPLICIT"`. The `content` string contains the user's raw prompt.

### Gemini CLI Session Chats (`chat_*.jsonl`)
Each chat step contains structured role arrays:
```json
{"role": "user", "content": "Please implement the new feature branch."}
```
* **Extraction Strategy**: Matches when `role == "user"`. Extracted from `content` string.

### Claude Code Chat History (`chat_*.jsonl`)
Contains nested content blocks for text and tool usage:
```json
{"role": "user", "content": [{"type": "text", "text": "Deploy to cloud run."}]}
```
* **Extraction Strategy**: Check if `role == "user"`. If `content` is a list, concatenate all text elements where `type == "text"`. If `content` is a string, extract directly.

### Cline & Roo Code task histories (`ui_messages.json`)
Consists of a JSON array containing UI logs:
```json
[
  {
    "type": "say",
    "say": "user_feedback",
    "text": "The view.html is pretty meh! Optimize the whitespace."
  }
]
```
* **Extraction Strategy**: Loop through array. Extract `text` when `say == "user_feedback"` and `type == "say"`.

### Cursor SQLite Databases (`state.vscdb`)
Uses SQLite database for storing global state values:
```sql
SELECT value FROM globalState WHERE key = 'workbench.panel.chat.state';
```
The nested `value` is a massive serialized JSON tree containing:
`{"tabs": [{"chats": [{"blocks": [{"text": "Query BigQuery tables"}]}]}]}`
* **Extraction Strategy**: Retrieve keys containing `"chat"` or `"composer"` from the `globalState` table, convert to string, and apply a robust regex pattern: `r'"text"\s*:\s*"([^"]+)"'`.

---

## 3. Linguistic & Behavioral Heuristics
The extractor applies static heuristics to synthesize tone parameters:
1. **Average Word Count**: Sum of words across extracted prompts divided by total counts. High-efficiency personas show average word counts between 20-60 words. Technical leader personas show 100+ words.
2. **Commonwealth Spelling Check**: Searches for key words containing `behaviour`, `optimise`, `prioritise`, `customise`. If occurrences exceed a low threshold, the writing dialect is classified as British/Commonwealth.
3. **Punctuation Triggers**: Counts double question marks (`??`) and ellipsis (`...`) to classify "conversational speed-typing" and "dialogue-driven debugging" frequency.
4. **Critique Indicators**: Matches key terms like `useless`, `waste`, `meh`, `revert`, `think about`, `broken`, `hung`, `slow` to filter out negative wording while highlighting core technical quality gates.
