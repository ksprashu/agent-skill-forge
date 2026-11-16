# H2O models

Read this if a model below is missing from `swarm{action:"models"}`, if a
worker runs out of quota, or before changing any model.

## Assignments

`swarm.config.json` is the source of truth; this table mirrors it.

| Role | Model | Family | Why this tier |
| :--- | :--- | :--- | :--- |
| `criteria-writer` | `gemini-4-hydrogen-high` | Gemini 4 Hydrogen | Turns agreed intent into binary criteria |
| `planner` | `gemini-4-hydrogen-xhigh` | Gemini 4 Hydrogen | Planning errors are cheapest to catch, costliest to miss |
| `implementer` | `gemini-4-hydrogen-high` -> `-xhigh` | Gemini 4 Hydrogen | Reviewed plans are well-specified; escalate after the first NOT GOOD |
| `summarizer` | `gemini-4-hydrogen-high` | Gemini 4 Hydrogen | Reports what the board already shows |
| `monitor` | `gemini-4-hydrogen-medium` | Gemini 4 Hydrogen | Reads the board on a timer |
| `plan-reviewer` | `claude-opus-5-5-medium` | Claude Opus 5.5 | Token budget |
| `intent-reviewer` | `claude-opus-5-5-medium` | Claude Opus 5.5 | Token budget |
| `functional-reviewer` | `claude-opus-5-5-medium` | Claude Opus 5.5 | Token budget |
| `code-reviewer` | `claude-opus-5-5-medium` | Claude Opus 5.5 | Token budget |
| `security-reviewer` | `claude-opus-5-5-high` | Claude Opus 5.5 | A missed vulnerability is the costliest miss |

The coordinator runs on whatever model the user chose for the conversation.

## Rules

- **H2O has its own model ruleset.** These assignments override any global
  swarm routing rules or catalogue bindings installed on the machine,
  including reviewer tier floors (for example "never review below `high`").
  Do not raise or lower an H2O tier to satisfy a global rule.
- Set `model` on every `swarm{action:"add"}`. Never let a worker inherit.
- Authors are Hydrogen, reviewers are Opus. Never put a reviewer on Hydrogen
  or an author on Opus: the point of H2O is that no work is reviewed by its
  own family.
- Reviews run one at a time, so at most one Opus worker is busy at once.
  Hydrogen and Opus draw on separate quota pools.

## Resolving IDs on other catalogues

The IDs above are the public Antigravity catalogue IDs. Some catalogues serve
the same models under different IDs. When an ID is not listed in
`swarm{action:"models", all:true}`, pick the ID whose display name is the
**same family and the same tier** (for example "Gemini 4 Hydrogen (High)" or
"Claude Opus 5.5 (Medium)"). That is a naming substitution, not a model
change, so no user prompt is needed; note it in the summary.

## When a model is missing or out of quota

1. **Out of quota, model listed:** wait for the reset shown in
   `swarm{action:"models"}`, or step down one tier within the same family
   (`claude-opus-5-5-high` -> `claude-opus-5-5-medium`, `gemini-4-hydrogen-xhigh` ->
   `gemini-4-hydrogen-high`) with `swarm{action:"model"}`. Tell the user.
2. **Family or tier not served at all:** stop and ask the user before
   substituting. Offer the closest same-family IDs from the live catalogue. Do
   not silently swap families: a Gemini reviewer on Gemini-authored work
   removes the cross-family check, and the user must agree to that.
3. Record any substitution in the final summary.
