# Channel Registers (`R1`–`R6`)

A register is how the same person writes and reads differently by channel. This file defines what each register controls. Person-specific values (spelling, punctuation, greetings, sign-offs, sentence rhythm) live in the resolved voice profile (`~/.gemini/personas/default/voice_and_tone.md`).

| Register | Typical channel | Controls | Default Structure & Flow |
| :--- | :--- | :--- | :--- |
| **R1: Quick internal email** | Reply to a teammate or report, short broadcast | Greeting, line count, emoticons, sign-off on short replies | `Hi <Name>,`, 1-4 concise sentences, direct answer on line 1, short sign-off or none |
| **R2: Stakeholder / external email** | Cross-team ask, partner or vendor email | Multi-recipient greeting, ask structure, caveat placement, closing check-in | Context in one sentence -> numbered ask -> caveats up front (`"The caveat, however, is that..."`) -> check-in |
| **R3: Technical blog / long-form** | Blog post, codelab, tutorial, README narrative | Person (`I`/`you`), friction hook, credit to prior work, tips and callouts | First person to a peer developer, concrete friction hook, exact commands and paths |
| **R4: Strategy doc / PRD / proposal** | Planning doc, PRD, BRD, MRD, assessment | Bluntness on scale bottlenecks, tiering, tables, metric formatting, synthesis headers | Problem & scale bottleneck -> tiered options table -> clear recommendation with bolded metrics |
| **R5: Working notes / comments** | Personal notes, doc comments, chat | Bullet glyphs, tags, arrows, acks, shorthand | Compact `+`/`-` bullets, `->` arrows; live shorthand allowed |
| **R6: Technical dossier / readout / report** | Atelier HTML dossiers, post-planning readouts, code reviews, benchmark analyses, technical summaries for the user | Connected cause-and-effect sentence rhythm (`18–30 words`), orientation -> tables -> strengths vs limits -> hidden catch | Orientation & verdict up front -> comparison tables paired with connected cause-and-effect prose (`"because"`, `"whereas"`, `"so that"`, `"which means"`, `" - "`) -> strengths vs hard limits -> "what you didn't consider" (hidden bottleneck/math). Zero blog hooks, zero theatrical metaphors, zero clipped 10-word fragments. |

## Choosing a Register

- **Recipient / Direction**:
  - Outward to one known colleague -> `R1`.
  - Outward to several teams, a partner, or anyone external -> `R2`.
  - Outward published blog or tutorial -> `R3`.
  - Strategy proposal, PRD, BRD, or MRD -> `R4`.
  - Quick notes to self or inline review comments -> `R5`.
  - **Dossier, post-planning readout, code review summary, benchmark bake-off, or deep technical report written for the user** -> **`R6`**.
- **Polish**: `R1` and `R5` may keep live-only shorthand. `R2`, `R3`, `R4`, and `R6` never do.

## R3 & R6 Technical Grounding Rules

Technical articles (`R3`) and engineering dossiers/readouts (`R6`) carry claims readers will act on:

- Check every CLI flag, API parameter, config key, formula, and quota weight against primary sources before writing it. Never invent one.
- In `R3`, introduce a product or tool with a landing link and a docs link: `[Product](landing) ([Docs](docs))`, and end with `References & Further Reading`.
- In `R6`, cite exact source files (`path/to/file:line`) and pair every comparison table with connected cause-and-effect prose that explains the operational consequence of the numbers.

Code comments and commit messages take no register: they get `unslop` clarity plus the profile's spelling rule (except on code identifiers).
