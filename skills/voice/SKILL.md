---
name: voice
description: Linguistic profiling, speech cadence, and tone extraction engine. Analyzes chat logs across AI developer tools to extract authentic persona traits and anti-slop guidelines. Trigger via `/voice` or `/extract-human-voice`.
disable-model-invocation: true
---

# Human Voice & Persona Extraction Engine

This skill provides an automated pipeline for scanning conversation history logs and databases from all major AI developer tools on your system (e.g., Antigravity CLI, Gemini CLI, Claude Code, Cline, Roo Code, Aider, and Cursor), scrubbing any sensitive metadata or PII, analyzing linguistic style markers, and generating a standard copybara-compatible writing persona profile.

## Quick Start

To extract your voice profile, run the helper script in this skill folder:

```bash
python3 $HOME/.agents/skills/extract-human-voice/scripts/extract_voice.py
```

This will walk the configured storage directories, analyze user prompts, and output three packaged canonical files under `$HOME/.agents/skills/extract-human-voice/output/`:
* `voice_and_tone.md` - Your core style and linguistic guidelines
* `golden_examples.md` - Sample high-bar engineering instructions
* `SKILL.md` - Frontmatter template for the writing assistant

## Workflows

### 1. Verification of Target Folders
Before running the extraction script, verify which AI coding tools you have installed on your Mac. The script automatically probes:
* `~/.gemini/antigravity-cli/brain/` (Antigravity logs)
* `~/.gemini/tmp/` (Gemini CLI logs)
* `~/.claude/projects/` (Claude Code logs)
* `~/Library/Application Support/Code/User/globalStorage/` (Cline and Roo Code)
* `~/.aider.history` (Aider logs)
* `~/Library/Application Support/Cursor/` (Cursor workspace and database logs)

If any directory does not exist, the script skips it gracefully.

### 2. PII & Sensitive Information Scrubbing
To ensure your template is ready for public or team sharing (e.g., in a git repo), the script scrubs:
* **Emails**: Replaced with `<EMAIL>`
* **Domains & URLs**: Corporate or internal endpoints are replaced with `<COMPANY_DOMAIN>` and `<INTERNAL_URL>`
* **Personal Identities**: Full names and specific usernames are replaced with `<USER_NAME>`, `<USER_NICKNAME>`, and `<USER_ID>`
* **Credentials**: API keys, JWTs, and GitHub Personal Access Tokens are replaced with `<REDACTED_SECRET>`

### 3. Packaging into copy-writer-bara
Once the script has completed, you can move the generated files from the `output/` folder into your custom copy-writer skill (e.g., `copy-writer-bara/`):
```bash
cp $HOME/.agents/skills/extract-human-voice/output/voice_and_tone.md $HOME/.agents/skills/copy-writer-bara/references/
cp $HOME/.agents/skills/extract-human-voice/output/golden_examples.md $HOME/.agents/skills/copy-writer-bara/references/
```

### 4. Hyperlinking & Reference Grounding Pattern Extraction
The extraction pipeline analyzes and extracts the user's hyperlinking habits, reference citation patterns, product dual-linking conventions (`[Product](landing) ([Docs](docs))`), and `knowledge-catalog` retrieval workflows, preserving them in the output `voice_and_tone.md`.

## Advanced Technical Specifications
For list of directory paths, schema types, database structures, and linguistic heuristics, see [REFERENCE.md](REFERENCE.md).
For processing comparisons and scrubbing examples, see [EXAMPLES.md](EXAMPLES.md).

