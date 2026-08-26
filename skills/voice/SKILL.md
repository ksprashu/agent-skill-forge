---
name: voice
description: Extract and profile human typing cadence, style markers, and tone across AI tool logs. Trigger via /voice.
disable-model-invocation: true
---

# Voice: Persona & Speech Cadence Profiler

Scan developer conversation logs, scrub PII, and extract authentic writing style markers.

---

## 🎯 Goal
Analyze prompt histories across developer tools (Antigravity, Claude Code, Gemini CLI, Cursor) and generate reusable voice profiles without leaking credentials.

---

## 📋 Step-by-Step Workflow

1. **Run Extraction Pipeline**:
   ```bash
   python3 scripts/extract_voice.py
   ```
2. **Automatic PII Scrubbing**: The script sanitizes private emails, corporate domains, and API tokens.
3. **Inspect Output**: Review generated `output/voice_and_tone.md` and `output/golden_examples.md`.
4. **Deploy Local Profile**: Copy to `references/voice_and_tone.local.md` for local writing personalization.

---

## 💡 Concrete Example

### Extracted Style Marker Fixture (`voice_and_tone.md`)
```markdown
# Writing Style Profile

## Core Cadence
* Direct, command-driven sentences ("Subtract before you add").
* Prefers bulleted checklists over narrative paragraphs.
* Banned filler phrases: "delve into", "tapestry", "it's worth noting".
* Product linking: Always uses dual links `[Product](landing) ([Docs](docs))`.
```

---

## 🚫 Hard Constraints

*   **NEVER** commit unscrubbed chat logs with real API keys or personal emails.
*   **NEVER** output private corporate intranet URLs without placeholder redaction.
