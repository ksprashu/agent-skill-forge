# H2O: design notes

Why the H2O swarm is shaped the way it is, what each choice defends against,
and what was tried or considered and rejected. Read this before changing the
topology, the models, or the loop limits.

## The failure modes

A multi-agent coding loop fails in a small number of repeatable ways. Each H2O
rule exists to block one of them.

| # | Failure mode | What it looks like | H2O defence |
| :--- | :--- | :--- | :--- |
| F1 | Building the wrong thing | Confident, tested code that answers a question nobody asked | Coordinator grills into `REQUIREMENTS.md`; `intent-reviewer` gates >= 90% clarity; user approves the done criteria before any plan exists |
| F2 | Moving goalposts | Each loop iteration quietly redefines "done" until the current attempt passes | Criteria and acceptance tests are frozen by SHA-256 (`h2o_gate.py freeze` / `check-frozen`) |
| F3 | Self-grading | The reviewer shares the author's blind spots and prefers its own family's output | Authors are Gemini 4 Hydrogen, every reviewer is Claude Opus 5.5 |
| F4 | Passing by weakening the tests | Deleted tests, new skips, suppressions, loosened assertions | `h2o_gate.py diff-guard` fails the change; the code reviewer must run it |
| F5 | Opinion as evidence | "Looks good to me" with nothing run | `h2o_gate.py verdict` rejects a verdict with no command output or `file:line` |
| F6 | The loop that never ends | An unsolvable task burns quota indefinitely | 3 NOT GOOD verdicts per gate, then the user decides (`h2o_gate.py record` exits 3) |
| F7 | Rework on a broken plan | The implementer retries forever because the design is wrong | Reviewers can return `NOT GOOD (DESIGN)`, which routes to the planner |
| F8 | Reviewers cannot see the change | Verifiers test the unchanged working copy | One implementer on the shared (`inherit`) workspace, on branch `h2o/<slug>` |

## Decisions and rejected alternatives

### 1. Hydrogen writes, Opus attacks

The first version ran every role, reviewers included, on Gemini 4 Hydrogen.
Same-family review is weak: LLM evaluators recognise and favour their own
generations ([Panickssery et al., 2024](https://arxiv.org/abs/2404.13076)), so
a Hydrogen reviewer misses what a Hydrogen author misses. Moving every reviewer
to Claude Opus 5.5 makes every review cross-family without giving up
Hydrogen's speed and separate quota pool for the token-heavy authoring work.

**Rejected:** Hydrogen-only (F3); Opus everywhere (authoring is the bulk of the
tokens, and Opus shares a short-window cap with Fable).

### 2. One planner, attacked, instead of best-of-n planning

The original whiteboard sketch had two parallel planners ("adversarial analysis
x2"). Two copies of one model working blind produce correlated plans, and
choosing between them needs a judge, which brings back F3. Parallel sampling
pays off on hard problems where the first idea is usually wrong, whereas
sequential revision with feedback wins on easier ones
([Snell et al., 2024](https://arxiv.org/abs/2408.03314)). H2O already is a
sequential-revision loop, so one planner plus an adversarial plan reviewer
gets the diversity where it matters (the critique) at half the planning cost.

**Rejected:** two independent planners plus a judge.

### 3. One implementer instead of best-of-n implementation

Best-of-n implementation only works with a reliable selector. Repeated
sampling with unit-test selection lifted SWE-bench Lite from 15.9% to 56%, but
model-based selection (majority vote, reward models) plateaued at around 100
samples ([Brown et al., 2024](https://arxiv.org/abs/2407.21787)). H2O's tests
are written by the same model family, so the selector is not strong enough to
justify n implementations, and merging two independent implementations of the
same change rarely produces coherent code.

**Rejected:** n implementers in `share` workspaces with a merge step (cost,
merge incoherence, and F8 when verifiers sit on a different workspace).

### 4. Three reviews, in sequence

Functional review runs first because it is the cheapest and fails most often;
the code reviewer and the security reviewer only ever see working code.
Running them in sequence also keeps at most one Opus worker busy, which stays
inside the Claude short-window cap. Self-correction without external feedback
does not reliably help ([Huang et al., 2023](https://arxiv.org/abs/2310.01798)),
so every review must be grounded in something executed.

**Rejected:** parallel functional and security review (reviewing broken code,
concurrent Opus workers); a single combined reviewer (too much for one
context at `medium`).

### 5. Reviewer tiers: medium, except security at high

Reviewers run at `claude-opus-5-5-medium` to keep token use down, which was an
explicit owner decision. The deep security review runs at `claude-opus-5-5-high`
because a missed vulnerability is the costliest miss and it runs at most once
per attempt that already passed two reviews.

### 6. Author tiers

| Role | Tier | Reason |
| :--- | :--- | :--- |
| `planner` | `xhigh` | Planning mistakes are the cheapest to catch and the most expensive to miss |
| `implementer` | `high`, `xhigh` after its first NOT GOOD | A reviewed plan is well-specified work; escalate only when it fails |
| `criteria-writer`, `summarizer` | `high` | Translation of agreed intent, not open reasoning |
| `monitor` | `medium` | Reads the board on a timer |

### 7. Loop caps with a human gate

"Iterate until solved" with no cap was the first design. It has no termination
guarantee (F6). Each gate now allows 3 NOT GOOD verdicts; the 3rd stops the
loop and asks the user to stop (with the best attempt and open findings) or
grant 3 more attempts. A `DESIGN` verdict counts against the plan gate, so a
bad plan cannot loop forever through the implementer.

### 8. The coordinator asks; `intent-reviewer` decides

Swarm workers cannot talk to the user; only the coordinator can. A grilling
worker would have to relay every question through the coordinator, adding two
relay turns per question. So the coordinator runs the grilling session and
writes `.agents/h2o/REQUIREMENTS.md`, while a separate `intent-reviewer`
worker (`claude-opus-5-5-medium`) owns the ">= 90% clear" gate. That removes the last
self-graded gate without paying relay overhead. If the user picked Opus for
the coordinator itself, this gate is same-family, which is acceptable here
because it checks the user's answers rather than model-authored code. The
user approving the written criteria remains the hard boundary before planning.

### 9. Full re-review after rework

After any rework, all three code reviews run again in order. A fix for a
security finding can break behaviour, so re-running only the rejecting
reviewer is cheaper but unsafe. Revisit only if token use proves a problem.

## The evidence and judgement split

Following the standard's S9 rule, `scripts/h2o_gate.py` collects and checks
evidence; it never judges quality.

| The script decides | The reviewers decide |
| :--- | :--- |
| A verdict has the required shape, evidence and numbered findings | Whether the findings are right |
| The frozen files are byte-identical | Whether the criteria were good |
| The NOT GOOD count is under the cap, and where the loop goes next | Whether the code is correct, readable or secure |
| The diff deletes no tests and adds no skips or suppressions | Whether the remaining tests are meaningful |

## What H2O does not defend against

- **Medium-tier false negatives.** A `medium` reviewer can miss subtle
  defects. The deterministic gates narrow this; they do not close it.
- **Weak acceptance tests.** If the criteria writer's tests are shallow,
  every gate can pass on shallow code.
- **Truthful-looking fake evidence.** `verdict` checks that evidence exists,
  not that it is genuine output. Reviewers are instructed to paste real output.
- **Catalogue availability.** The model IDs are public Antigravity IDs.
  Catalogues that name the same models differently are resolved by family and
  tier; see `references/models.md`.

## Relationship to global routing rules

Machine-wide swarm routing rules (capability slots, reviewer tier floors such
as "never review below `high`") do not apply to H2O. H2O pins its own models
because its cost model differs: Hydrogen absorbs the token-heavy authoring and
rework, so the reviewers can stay at `medium` while the deterministic gates in
`h2o_gate.py` carry the evidence burden. Changing an H2O tier is a change to
this skill, not to the global rules.
