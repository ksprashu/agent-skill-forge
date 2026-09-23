# Design notes

Why this skill is shaped the way it is. Read `SKILL.md` for how to use it.

---

## The problem

Every AI harness reads an instruction file — `CLAUDE.md`, `GEMINI.md`,
`AGENTS.md`, `.cursorrules`. Almost nobody writes a good one, because the
useful content is not facts about the codebase; it is facts about *you*: how
long an answer should be, whether a diagram helps or annoys, whether you want
a recommendation or the options.

Those facts are hard to state from a standing start and easy to get wrong.
But they leave traces: people complain when an answer is too long, ask for a
table, tell the assistant to stop hedging. This skill turns those traces into
an instruction file.

---

## The failure mode we are designing against

A profiling tool has a strong pull toward becoming a horoscope. It reads some
data, produces a confident personality description, and the description feels
true because it is vague enough to fit anyone. The output goes into a config
file, invisibly shapes thousands of responses, and nobody ever audits it —
because there is nothing to audit against.

The first version of this skill failed exactly this way. A Python script
counted keywords (including the bare word `stop` and the bare word `hello`),
a second script ignored the counts and returned a hardcoded profile, and the
exporter copied static templates. Every persona it produced was the same
persona. It had a passing test suite throughout, because the tests checked
that files were written, not that the content depended on the input.

Three things follow from that.

### 1. Evidence and judgement are separated by a file

`harvest.py` counts and quotes. It does not score, band, rank, or conclude —
`tests/test_harvest.py` asserts its output contains no such key and never
names a profile dimension. The model reads the counts and the quotes and
makes the judgement, because "does this person want tables" is a judgement
call and no amount of regex will make it arithmetic.

`profile.json` is the boundary. It is reviewable by a human, diffable in git,
and validated mechanically.

### 2. Claims carry provenance, and unsupported claims render nothing

Every band and every rule has a `source`:

| Source | Enforced requirement |
|---|---|
| `observed` | ≥1 quote ID that resolves in `evidence.json` |
| `declared` | A note recording what the user said or picked |
| `inferred` | Nothing — but counted, warned about, and stamped into output |

An axis with no support is `unknown`, and **an `unknown` axis renders no
instruction at all**. That is the anti-fabrication guarantee, and
`TestUnknownsRenderNothing` enforces it: a profile with every axis unknown
produces a config file containing no house style.

Every rendered file carries a provenance footer stating how many claims were
observed, declared, or inferred. The person living with the rules can see how
much of it was actually earned.

### 3. The output must be a function of the input

`TestDifferentiation` renders two opposite profiles and asserts that **every**
generated file differs. A static template with extra steps cannot pass it.
`test_no_template_hardcodes_a_persona` bans the specific phrases the old
version baked in. `test_low_and_high_are_genuinely_opposed` fails any
dimension whose extremes read similarly — if `low` and `high` produce
near-identical text, the dimension is decoration and should be deleted rather
than asked about.

---

## Why bands, not scores

The obvious design is a 0–100 score per trait. It is also dishonest: a number
implies an instrument, and the instrument here is a model reading a few dozen
chat messages. `73` and `68` would be indistinguishable in reality but look
meaningfully different on a page, and the difference would end up driving
generated text.

Ordinal bands — `low` / `medium` / `high` / `unknown` — say exactly as much as
the evidence supports. Crucially, `unknown` is a first-class value with a
defined behaviour, which a numeric scale cannot express (`0` means "strongly
dislikes", not "we never found out").

## Why six dimensions

Each one had to earn its place by changing the rendered output in a way the
others do not. The test for "genuinely opposed" extremes is the filter: a
dimension survives only if `low` and `high` produce instructions that overlap
less than 40%.

Rejected: reading speed, technical level, patience, working-memory load. Each
either could not be grounded in anything observable in a chat log, or
collapsed into one of the six once you asked what instruction it would
actually produce.

## Why the schema is generated

`references/profile.schema.json` is built by `profile_tool.py build_schema()`
from the same constants that validation uses, and a test asserts the committed
file matches. Adding a dimension cannot leave the schema stale, because there
is only one source of truth and the drift is a test failure.

---

## Privacy

Chat logs contain credentials, client names, and home directory paths.

- Redaction happens **at capture**, in `add_user_turn`, not at write time —
  so an exception between the two cannot leak anything.
- `harvest.py --check-redaction` re-scans a written file. Belt and braces: the
  file is meant to be safe to hand to a model, so verify rather than trust.
- `profile_tool.validate` re-checks at the contract layer, because a profile
  compiles into files that get committed.
- Nothing is uploaded. Every script is stdlib-only and offline.

The user is shown what sources were read before anything is parsed in earnest,
and `--sources` narrows it.

---

## What this skill deliberately does not do

- **Diagnose anything.** It has no view on cognition, attention, or ability.
  It observes reactions to text and produces formatting instructions. The
  dimensions are named after properties of *output*, not properties of people.
- **Profile anyone but the operator.** It reads local logs belonging to the
  person running it.
- **Run unattended.** Step 5 of the workflow is a mandatory confirmation. A
  profile the user has not seen is a profile they cannot correct.
- **Merge into existing config files.** `render.py` overwrites whole files.
  Automatic merging into a `CLAUDE.md` full of build instructions is a good
  way to destroy someone's afternoon; the skill tells you to render to a
  scratch directory instead.

---

## Extending it

**Adding a dimension:** add it to `DIMENSIONS` in `profile_tool.py` (with the
block it `drives`), add `low`/`medium`/`high` text to `BAND_TEXT` in
`render.py`, add a row to the threshold table in `references/rubric.md`, add a
calibration card, and extend both fixtures. Four tests will fail until all of
that is done — that is the intended behaviour, not friction to route around.

**Adding a harness:** add an entry to `HARNESSES` in `render.py`. If it shares
an output filename with an existing target, share the template too;
`test_harnesses_sharing_a_filename_agree` enforces that two targets cannot
disagree about one file.

**Adding a log source:** add candidate paths to `source_roots()` and a parser
method. List *every* directory layout seen in the wild — Antigravity has moved
its transcript directory twice, and missing one yields an empty harvest that
looks indistinguishable from "this user has no opinions".
