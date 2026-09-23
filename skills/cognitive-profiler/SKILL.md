---
name: cognitive-profiler
description: Work out how a specific person wants an AI agent to write to them, from evidence, and compile it into CLAUDE.md / GEMINI.md / AGENTS.md / .cursorrules. Trigger via /cognitive-profiler.
disable-model-invocation: true
---

# Cognitive Profiler

Turn evidence about how someone reacts to AI output into per-harness
instruction files — with every claim traceable to a quote or a direct answer.

---

## 🎯 Goal

Produce a `profile.json` that describes **how this person wants to be written
to**, then compile it into the config files their tools actually read.

The hard part is not writing the files. It is not making things up. A config
file is invisible infrastructure: once it exists, it shapes every response
forever, and the user has no easy way to notice a rule they never agreed to.
So the whole design is built around one invariant:

> **Every claim in the profile is `observed` (cites a quote), `declared` (cites
> something the user said), or `unknown`. `inferred` claims are counted and
> stamped into the output. An axis left `unknown` renders no instruction at
> all.**

Silence beats a plausible guess.

---

## 🧭 Division of labour

| Layer | Does | Never does |
|---|---|---|
| `scripts/harvest.py` | Counts signals, keeps redacted quotes | Scores, bands, concludes |
| **You** | Read the evidence, judge, write the profile | Invent a claim you cannot cite |
| `scripts/profile_tool.py` | Enforces the evidence invariant | Decides anything |
| `scripts/render.py` | Compiles profile → config files | Contain a default persona |

Keyword counts cannot tell you what someone wants. That is a judgement, and
judgement is your job. The scripts exist to give you facts to judge from and
to stop you shipping a claim you cannot support.

---

## 📋 Workflow

### 1. Gather evidence

```bash
python3 scripts/harvest.py -o evidence.json
python3 scripts/harvest.py --list-sources     # which logs exist here
python3 scripts/harvest.py --since 2026-06-01 # recent history only
```

Reads Claude Code, Antigravity, Gemini CLI, Cline, Roo, and Cursor logs.
Everything is redacted on the way in. Verify before sharing:

```bash
python3 scripts/harvest.py --check-redaction evidence.json
```

**Show the user what was found before going further** — how many sessions,
which tools, and the coverage level. If they object to any source being read,
re-run with `--sources`.

### 2. Read the evidence honestly

Open `evidence.json` and check `coverage.level` first:

| Level | What you may conclude |
|---|---|
| `thin` | Nothing. Skip to step 3 and ask instead. |
| `partial` | Ground what you can; leave the rest `unknown`. |
| `adequate` | Most dimensions can be `observed`. Still confirm. |

**Now read `references/rubric.md` in full.** It holds the band thresholds, the
traps in reading sparse evidence, and the standard for writing a rule. Do not
write a band without it.

### 3. Close the gaps by asking

Whatever the logs did not settle, ask about. **Read
`references/calibration.md`** — it contains A/B cards showing the *same*
answer rendered two ways. Show a pair, ask which one they would rather have
received, and record the answer as `declared`.

Four cards cover all six dimensions. Ask only about what is still unknown; do
not run a questionnaire on things the logs already answered.

### 4. Write and validate the profile

```bash
python3 scripts/profile_tool.py init --subject "how I read" -o profile.json
```

Fill in the six dimensions, `tone`, `limits`, `rules`, and `forbidden`. Then:

```bash
python3 scripts/profile_tool.py validate profile.json -e evidence.json
```

Fix every error. Read the `inferred` count in the summary — **if more than
about a third of claims are inferred, you guessed too much.** Downgrade the
weakest ones to `unknown`.

### 5. Confirm before rendering

Show the user the profile in plain language, with the quotes behind each
claim. Ask specifically about anything `inferred`. They are the only authority
on whether it is right.

### 6. Compile

```bash
python3 scripts/render.py profile.json --dry-run          # preview
python3 scripts/render.py profile.json -t claude -o ~/.claude
python3 scripts/render.py profile.json -o /tmp/out        # all harnesses
```

**Read `references/harnesses.md`** before choosing `-o`. It covers global vs
per-project placement, merging into an existing `CLAUDE.md` (render
overwrites — do not point it at a file you care about), and the precedence
traps that make a config silently never load.

### 7. Hand over the amend command

```bash
python3 scripts/profile_tool.py amend profile.json \
    --directive "Never open with a restatement of my question" \
    --scope always --source declared --evidence "Said so on 2026-09-21."
python3 scripts/render.py profile.json -o ~/.claude    # re-render after
```

The first wrong rule they hit decides whether this gets trusted or deleted.
Make sure they know how to fix it.

---

## 📐 The six dimensions

Each is a band: `low` / `medium` / `high` / `unknown`. Not a score — there is
no instrument here precise enough to justify a number.

| Dimension | The question it answers |
|---|---|
| `visual_scaffolding` | Tables and diagrams, or prose and code? |
| `text_density` | Broken-up text, or continuous paragraphs? |
| `orientation_need` | Frame the problem first, or start at the answer? |
| `metaphor_affinity` | Analogies, or the real vocabulary? |
| `decision_directness` | One recommendation, or the options laid out? |
| `evidence_depth` | Exhaustive rigour, or just the question asked? |

`low` and `high` render genuinely opposed instructions — a test enforces it.
If a dimension's extremes produced similar text, it would not be worth asking
about.

---

## 🚫 Hard constraints

- **NEVER** write a band or rule you cannot point at a quote or an answer for.
  Use `unknown`.
- **NEVER** render without the user confirming the profile first.
- **NEVER** set a numeric limit that was not measured or requested. `null` is
  the correct value for a ceiling you have not established — a fabricated one
  silently truncates useful answers forever.
- **NEVER** overwrite an existing `CLAUDE.md` / `GEMINI.md` that holds project
  instructions. Render to a scratch directory and merge.
- **NEVER** commit `evidence.json` or `profile.json` to a shared repo without
  asking. They describe a person.
- **NEVER** let a presentation rule override accuracy. Every template says so
  explicitly; keep that clause when merging.

---

## 📁 Layout

```
scripts/profile_tool.py   Schema, validation, the evidence invariant
scripts/harvest.py        Evidence collection (counts + quotes, no judgement)
scripts/render.py         profile.json -> config files
references/rubric.md      How to judge evidence into bands   (read at step 2)
references/calibration.md A/B cards for asking directly      (read at step 3)
references/harnesses.md   Where the rendered files go        (read at step 6)
references/profile.schema.json  Generated from profile_tool.py constants
fixtures/                 Worked examples: two opposite profiles
templates/                Structural only; no persona baked in
tests/                    Contract tests, including differentiation
```

Verify with `python3 -m pytest tests/ -q`.
