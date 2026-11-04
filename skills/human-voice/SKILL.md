---
name: human-voice
description: Extract and profile human typing cadence, style markers, and tone across AI tool logs. Trigger via /human-voice.
disable-model-invocation: true
---

# Human-Voice: Persona & Speech Cadence Profiler

Scan developer conversation logs, scrub PII, and extract authentic writing style markers.

---

## 🎯 Goal
Analyze prompt histories across developer tools (Antigravity, Claude Code, Gemini CLI, Cline, Roo Code, Aider, Cursor) and generate reusable voice profiles without leaking credentials.

---

## 📋 Step-by-Step Workflow

1. **Run Extraction Pipeline**:
   ```bash
   python3 <skill-dir>/scripts/extract_voice.py [--internal-domain your-company.example]
   ```
2. **Automatic PII Scrubbing**: The script redacts emails, IPv4 and IPv6 addresses, API keys and tokens (Google, OpenAI, Anthropic, AWS, GitHub, GitLab, Slack, JWTs, bearer headers, `password=`-style assignments), home-directory paths (shown as `~`), your OS user name, and URLs and hostnames on generic internal suffixes (`.internal`, `.corp`, `.intranet`, plus `.lan` and `.local` for URLs). Pass `--internal-domain` (repeatable) for your employer's domains, and `--user-name`/`--user-nickname` for names. No employer domain is built in. Log reading and redaction live in `<skill-dir>/scripts/log_sources.py`, which `cognitive-profiler` ships an identical copy of. Use `--tool` to read one tool only, and `-v` to see which log locations exist.
3. **Inspect the Drafts**: The script writes `voice_and_tone.draft.md` and `voice-samples.draft.md` to `~/.gemini/personas/default/` (or `$AGENT_PERSONA_DIR/default`, or `-o <dir>`). It never overwrites a live `voice_and_tone.md`. The draft uses `voice-register`'s template layout, with measured habits (spelling, dashes, arrows, contractions, prompt length) filled in and `<...>` placeholders for everything a script can't know. The samples file holds raw redacted excerpts; check it for anything private.
4. **Finish and Deploy the Profile**: Fill in the placeholders, then rename the draft to `voice_and_tone.md`. `voice-register` applies it. If `~/.gemini/personas` is your private persona repo, commit and push from there.

This skill measures how you write. How you react to AI output (what frustrates you, what you want more or less of) is `cognitive-profiler`'s job.

---

## 💡 Concrete Example

### Draft excerpt (`voice_and_tone.draft.md`)
```markdown
## Linguistic & Punctuation Fingerprints
- **Spelling**: US-English. <Confirm, and list words you always spell a particular way.>
- **Dashes**: em-dashes in 4% of prompts. <Keep, or ban?>
- **Arrows and slashes**: `->` or `=>` in 12% of prompts. <Which form, with spaces?>
```

---

## 🚫 Hard Constraints

*   **NEVER** commit unscrubbed chat logs with real API keys or personal emails.
*   **NEVER** output private corporate intranet URLs without placeholder redaction.
*   **NEVER** ship a persona, sample, or employer domain in this skill. Output comes only from the user's own logs.
*   **NEVER** overwrite a live `voice_and_tone.md`; write drafts.
