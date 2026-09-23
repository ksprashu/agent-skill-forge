# Judging rubric: evidence to profile

Read this before writing any value into `profile.json`. `harvest.py` gives you
counts and quotes; it deliberately draws no conclusions. Turning those into
bands and rules is your job, and this is the standard you are held to.

---

## The one rule that matters

**Never write a claim you cannot point at.**

Every dimension band and every rule carries a `source`:

| Source | Means | Requires |
|---|---|---|
| `observed` | Seen in the logs | ≥1 quote ID (`q7`) that resolves in `evidence.json` |
| `declared` | The user said or chose it | A note recording what they said or picked |
| `inferred` | You reasoned it out | Nothing — but it is counted and stamped into output |

`validate` enforces the first two. Nothing enforces restraint on `inferred`,
so restrain yourself: **if you cannot cite it, prefer `unknown`.**

An `unknown` dimension is not a failure. It renders no instruction, which
leaves the agent free to use judgement. That is strictly better than a
confident guess the user never made and cannot easily find to correct.

---

## Reading the evidence file

Three things decide how much you are entitled to conclude.

- **`coverage.level`** — `thin` means do not judge from logs at all; go
  straight to calibration. `partial` means ground what you can and leave the
  rest unknown. `adequate` means most dimensions can be `observed`.
- **`signals[].count`** — frequency. One complaint is an anecdote; six is a
  pattern.
- **`quotes[]`** — texture. Read them. A `length_complaint` on a 2,000-word
  design doc means something different from one on a three-line answer.

Watch for these traps:

- **Sparse denominators.** Three `diagram_rejection` hits out of 2,000 turns
  is noise. Three out of 40 is a pattern. Always divide by
  `coverage.user_turns`.
- **Absence is not preference.** No `diagram_request` hits does not mean they
  dislike diagrams — it may mean the assistant never offered one. Absence
  supports `unknown`, never `low`.
- **The complaint is about the instance, not the class.** "This flowchart
  didn't help" is evidence about one flowchart. Six of those across different
  sessions is evidence about flowcharts.
- **Recency beats volume.** A preference stated last week outranks a pattern
  from a year ago. Use `--since` if the logs are long.

---

## Band thresholds

Rates are `signal count ÷ coverage.user_turns`.

| Dimension | `high` when | `low` when |
|---|---|---|
| `visual_scaffolding` | `structure_request` or `diagram_request` ≥2% of turns and few rejections | `diagram_rejection` ≥1% of turns, or rejections outnumber requests |
| `text_density` | `length_complaint` ≥2% of turns, or `assistant_words_when_length_complained.median` is well below `assistant_words.median` | `structure_rejection` present and `length_complaint` ≈0 |
| `orientation_need` | Repeated "what is this about" / context-seeking follow-ups | `preamble_complaint` ≥1% of turns |
| `metaphor_affinity` | `analogy_request` present and `analogy_rejection` absent | Any `analogy_rejection` at all — this one is asymmetric; being patronised is remembered |
| `decision_directness` | `directness_request` ≥1.5% of turns | They routinely ask for alternatives after a single recommendation |
| `evidence_depth` | `depth_request` ≥2% of turns | `length_complaint` is high *and* `depth_request` ≈0 |

Below the `high` bar but clearly present → `medium`. No usable signal →
`unknown`.

These are starting points, not arithmetic. If the quotes tell a different
story than the counts, follow the quotes — and say so in `rationale`.

---

## Writing a good rule

Bands set the general shape. Rules capture the specific, quotable things —
the stuff a band cannot express.

A rule is good when it is:

- **Actionable.** "Put the recommendation in the first line" beats "be
  decisive."
- **Falsifiable.** Someone reading a response should be able to say whether
  the rule was followed.
- **Scoped.** Use the narrowest scope that fits. A rule that only applies to
  incident work should not be `always`.
- **Cited.** Pointing at the quote it came from.

Bad rule: *"Be clear and concise."* Unfalsifiable, unscoped, uncited.
Good rule: *"For any platform comparison, lead with a table of the two or
three real candidates before discussing any of them"* — scope `architecture`,
source `observed`, evidence `["q12", "q31"]`.

Use `forbidden` for prohibitions. They carry more weight than instructions,
and they are what people actually notice when violated.

---

## Tone and limits

`tone.default` is one phrase describing register, e.g. *"a senior colleague
who already knows the domain"*. Per-scope overrides only where the register
genuinely differs.

Limits must come from data or a direct statement, never from a round number
that feels right:

- `response_ceiling_words` — use the median of
  `assistant_words_when_length_complained`, if that distribution has `n ≥ 3`.
  Otherwise leave it `null`.
- The rest — set only if the user asked for them.

**`null` is the correct value for a limit you have not established.** A
fabricated ceiling silently truncates useful answers forever.

---

## Before you hand it over

1. Run `profile_tool.py validate profile.json -e evidence.json`. Fix every error.
2. Read the `inferred` count. If it is more than about a third of claims, you
   guessed too much — downgrade the weakest ones to `unknown`.
3. **Show the user the profile and the quotes behind it before rendering.**
   They are the only authority on whether it is right. Ask specifically about
   anything `inferred`.
4. Render, then tell them `profile_tool.py amend` exists. The first wrong rule they
   hit is the moment this either becomes trusted or gets deleted.
