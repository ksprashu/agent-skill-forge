# Channel Registers

A register is how the same person writes differently by channel. This file defines what each register controls. The person-specific values (greetings, sign-offs, quirks) live in the voice profile. When the profile is silent on a register, fall back to the neutral defaults here.

| Register | Typical channel | Controls | Neutral default |
| :--- | :--- | :--- | :--- |
| **R1: Quick internal email** | Reply to a teammate or report, short broadcast | Greeting, line count, emoticons, sign-off on short replies | `Hi <Name>,`, 1-4 short sentences, answer on line 1, short sign-off or none |
| **R2: Stakeholder / external email** | Cross-team ask, partner or vendor email | Multi-recipient greeting, ask structure, caveat placement, closing check-in | Context in one sentence, then the ask, caveats up front, a clear next step |
| **R3: Technical blog / long-form** | Blog post, tutorial, README narrative | Person (I/we/you), hook, credit to prior work, tips and callouts | First person to a peer, concrete walkthrough with exact commands and paths |
| **R4: Strategy doc / proposal** | Planning doc, proposal, assessment | Bluntness, tiering, tables, metric formatting, synthesis headers | Problem, then options, then recommendation, with numbers in tables |
| **R5: Working notes / comments** | Personal notes, doc comments, chat | Bullet glyphs, tags, arrows, acks, shorthand | Terse bullets; shorthand allowed |

## Choosing a Register

- **Recipient**: one known colleague → R1. Several teams, a partner, or anyone external → R2.
- **Medium**: published or shareable long-form → R3. A decision or planning document → R4. Notes to self or inline comments → R5.
- **Polish**: R1 and R5 may keep live-only shorthand. R2, R3, and R4 never do.

Code comments and commit messages take no register. They get `unslop` only, plus the profile's spelling rule if it has one.
