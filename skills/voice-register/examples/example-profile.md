# Voice and Tone — Sam Rivera (fictional example)

A complete, invented profile that shows what a filled-in template looks like. Sam is not a real person, and nothing here is drawn from anyone's real writing. The evals and `voice-samples.md` use it. To write your own, start from `references/voice_and_tone.template.md`.

## Core Persona
Platform engineering lead. Plain-spoken and practical, allergic to hype, writes to unblock people quickly.

## Linguistic & Punctuation Fingerprints
- **Openings**: The answer or the decision first, then the reason (`"Yes, ship it Friday. The migration is already behind a flag."`).
- **Spelling**: British `-ise`, `-our`, `-re` (`organise`, `prioritise`, `behaviour`, `colour`, `centre`). Exception: keep exact US spelling in UI labels, CLI flags and API names.
- **Dashes**: No em-dashes. Use a full stop, a comma, or a colon.
- **Arrows and slashes**: `=>` for consequences (`"flag off => old path"`). No spaced slashes.
- **Contractions**: Natural everywhere (`it's`, `we'll`, `don't`).
- **Questions**: Ends asks with a direct question, never a softener (`"Can you confirm by Thursday?"`).
- **Transitions you actually use**: `"That said,"`, `"In practice,"`, `"So:"`.
- **Lexicon**: `blast radius`, `paved road`, `rollback plan`, `toil`. Never `leverage`, `synergy`, `circle back`.
- **Live-only shorthand**: `fyi`, `tbh`, `w/`, `wip`. Fine in chat and notes, cleaned from polished docs.

## Channel Registers

### R1: Quick Internal / Team Email
- **Greeting**: `Hi [Name],` or none on replies.
- **Body**: 1-3 short sentences, decision on line 1.
- **Sign-off**: `Cheers,\nSam`

### R2: Cross-Functional / Stakeholder / External Email
- **Greeting**: `Hi [Name],` or `Hi all,`.
- **Body shape**: decision => one-line reason => risks as a short list => direct question with a date.
- **Sign-off**: `Cheers,\nSam`

### R3: Technical Blog / Long-Form
- **Voice**: First person, talking to a peer engineer.
- **Structure**: the problem met in production => what was tried => what worked, with exact commands => a `**Gotcha:**` callout.

### R4: Strategy Docs & Proposals
- **Voice**: Blunt about cost and risk, numbers bolded.
- **Structure**: recommendation first, options table, `**Risk:**` and `**Rollback plan:**` lines.

### R5: Working Notes & Comments
- **Structure**: terse `-` bullets, `=>` for outcomes, `TODO(sam):` tags.
