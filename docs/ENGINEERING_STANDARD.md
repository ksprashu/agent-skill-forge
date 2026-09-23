# Engineering standard

**Status:** normative. This is the contract every skill, script, and verifier in
this repo is held to. Written 2026-09-23 after two reviews found the same defect
twice at two different layers.

> Read this before adding a skill, a script, a gate, or a test. If a change
> conflicts with a rule here, change the rule in a separate commit with a reason —
> do not route around it.

---

## 0. The one-paragraph version

This repo builds tools that an LLM runs semi-autonomously, and LLMs are extremely
good at producing artifacts that look like the requested work. The only defence is
that **every claim must be produced by an executor, and every executor must be
proven to reject bad input.** A check nobody can fail is not a check. A score that
does not change when quality changes is not a score. A gate with no function bound
to its name is a noun.

---

## 1. The failure mode this standard exists to prevent

Two independent reviews found the same thing:

| Where | What happened |
|---|---|
| `cognitive-profiler` (2026-09) | `psychometric_evaluator.py` ignored its input and returned a hardcoded profile. 59 tests passed throughout, because they asserted files were written — not that output depended on input. |
| `work` (2026-09-23) | `forensic_audit.py` cleared a hardcoded function with "ZERO forensic violations". `arbiter_eval.py` scored a content-free document 95 and a rigorous one 40. Nine barrier gates had zero executors. |

Same shape both times:

1. A judgement task (is this good? is this real?) is implemented as surface
   pattern-matching (does the heading exist? is `unittest.mock` imported?).
2. The vocabulary of measurement (scores, veto, gates, axes) is retained.
3. Tests assert the machinery ran, not that it discriminates.
4. Output is shown to the user as a basis for decisions.

Call it **decorative verification**. It is worse than no verification, because it
converts "unknown" into "confirmed good" and stops anyone looking.

---

## 2. The enforcement ladder

Every quality rule in this repo sits at one of four levels. Know which one you are
writing, and do not describe an L1 as though it were an L3.

| Level | Mechanism | Real enforcement |
|---|---|---|
| **L1** | Prose in a SKILL.md: "the agent MUST verify…" | ~zero. Competes against the model's priors. |
| **L2** | Agent self-checks and reports the result | ~zero. **The same context that took the shortcut writes the justification for it.** |
| **L3** | A script exits non-zero | Real — *if* something runs it. |
| **L4** | CI refuses the merge | Actual. |

**Rules:**

- Any claim with the words *verify*, *gate*, *audit*, *veto*, *certified*, *pass*,
  or *score* attached must be L3 or above, or must be reworded to drop them.
- Self-certification (L2) is never sufficient for a gate. An agent may *propose*
  a status; only a script may *set* one.
- L1 prose is fine for guidance, style, and judgement calls. It is not fine as the
  sole mechanism behind a named gate.
- L4 arrived on 2026-09-23 as `.github/workflows/ci.yml` (§7). A new verifier
  that is not wired into it stays at L3, and L3 is one forgetful agent away
  from L1.

---

## 3. Script contract

Every `skills/*/scripts/*.py` must satisfy all of the following.

| # | Rule | Rationale |
|---|---|---|
| S1 | **Python 3.12, stdlib only.** No third-party imports. | Scripts run inside five different harnesses with no install step. |
| S2 | **Never shadow a stdlib module name.** `profile.py`, `token.py`, `types.py`, `code.py`, `parser.py` are forbidden filenames. | `profile.py` silently broke 54 tests; the failure looked like a logic bug. |
| S3 | **Exit non-zero on any failure.** Print findings to stdout, diagnostics to stderr. Exit 0 means and only means "checked, and clean". | Exit code is the only thing an L4 gate can read. |
| S4 | **`subprocess` with an argument list and `shell=False`.** Always. | Inputs originate in agent-authored Markdown. `shell=True` on those is a command-injection path. |
| S5 | **No absolute paths.** Resolve from `Path(__file__)` or the repo root. No `C:\Users\`, `/Users/`, `/home/`. | Hardcoded paths inside dispatch prompts fail silently on other platforms. |
| S6 | **`--help` must be accurate.** Every documented flag must exist with that exact name. | SKILL.md documented `--rule`; the flag was `--directive`. Cheap to check, expensive to hit. |
| S7 | **One source of truth for constants.** Schemas, tables, and enums are *generated* from Python constants and a test asserts the committed artifact matches. | Makes drift impossible by construction rather than by discipline. |
| S8 | **Redact at capture, not at write.** Any script reading user data redacts in the ingest function. | An exception between read and write must not be able to leak. |
| S9 | **Separate evidence from judgement with a file.** Scripts collect and count; the model judges; a validator enforces provenance on the result. | Section 4. |

### S9 in detail — the evidence/judgement split

This is the single most important architectural rule in the repo, and the one
`cognitive-profiler` was rebuilt around.

```
collector script  →  evidence.json  →  LLM judgement  →  profile.json  →  renderer
  (counts, quotes)      (facts)         (the hard part)   (validated)     (output)
```

A script must not score, band, rank, or conclude. Those are judgement calls, and a
regex that performs one produces a *confident* wrong answer. What a script can do
honestly: count, quote, diff, execute, compare, and check provenance.

Where the repo violates this today, it is broken: `arbiter_eval.py` scores design
quality by counting headings, and is anti-correlated with actual quality.

**Test for this:** if the script's output contains a word like `good`, `score`,
`high`, `pass`, or a dimension name, ask whether a determined author could produce
that word without producing the underlying property. If yes, the script is
measuring the wrong thing.

---

## 4. Verifier contract

A *verifier* is any script whose output gates a decision — forensic audits,
arbiters, gate executors, validators. Verifiers carry extra obligations because
they are the thing the whole system's honesty rests on.

| # | Rule |
|---|---|
| V1 | **A verifier must have a known-bad fixture it rejects, committed to the repo.** `fixtures/known_fake/` for integrity auditors, `fixtures/hollow_design.md` for arbiters. A test asserts non-zero exit on it. |
| V2 | **A verifier must have a known-good fixture it accepts.** Otherwise the fix for V1 is `exit(1)` unconditionally. |
| V3 | **A verifier audits the artifact it claims to audit.** An integrity auditor that globs only `test_*.py` cannot see a faked `src/` implementation. State the glob in the docstring. |
| V4 | **Test coverage must scale with authority.** Any script that can emit a blocking verdict needs coverage at least as thorough as the thing it blocks. `forensic_audit.py` — the Binary Veto — shipped with zero tests; that inversion was the bug, and it now carries 64 of its own plus the 17 guarding the host-path scanner, against two fixture corpora. |
| V5 | **A verifier reports what it did not check.** "Audited 12 test files; did not audit src/" is honest. "ZERO violations detected" is not, when only a third of the surface was examined. |
| V6 | **No axis may be a constant.** If a scoring dimension returns the same value for every input, delete it. It inflates the total and discriminates nothing. |

---

## 5. Required test patterns

A passing suite proved nothing in either failure above. These six patterns are
what makes a suite load-bearing. Not all apply to every module; the ones that do
are mandatory.

### T1 — Differentiation

> Feed two **opposite** inputs. Assert **every** output artifact differs.

The single highest-value test in the repo. A static template with extra steps
cannot pass it. `cognitive-profiler`'s `TestDifferentiation` renders a maximal and
a minimal profile and diffs all eight generated files.

```python
def test_opposite_inputs_produce_different_output():
    a = render_all(load("fixtures/profile_high.json"))
    b = render_all(load("fixtures/profile_low.json"))
    for name in a:
        assert a[name] != b[name], f"{name} is input-independent"
```

### T2 — Mutation smoke

> Break the implementation. Assert the suite goes red.

The only way to know tests constrain behaviour. Stub a public function to `return
None` or a literal, run the suite, require a failure. If it stays green, the tests
assert existence rather than behaviour.

### T3 — Derive, don't restate

> Assert the artifact is a *function of* its source, not a copy of a phrase.

Ban the specific hardcoded strings a previous fake version emitted
(`test_no_template_hardcodes_a_persona`). Ban literals in production code that
should have been computed. A grep-based test is legitimate here — the thing being
grepped for is a known regression.

### T4 — Negative tests are mandatory

> Every validator needs a test that it **rejects**.

For every "valid input passes" test, there must be an invalid-input test that
fails with a specific error. A validator with only positive tests is
indistinguishable from `def validate(x): return []`.

### T5 — Real-input end-to-end

> Run the tool on actual data from the environment, not only fixtures.

`harvest.py` was verified against real Antigravity/Claude Code logs, which is how
the missing transcript directory was found. Fixtures encode the author's
assumptions; real input does not.

### T6 — Contract freshness

> Generated artifacts (schemas, tables, docs) are regenerated in a test and
> compared byte-for-byte to the committed copy.

Drift becomes a test failure instead of a stale file nobody noticed.

### Anti-patterns — an automatic review rejection

```python
assert True                             # no
assert result == result                 # no
assert os.path.exists(out)              # necessary, never sufficient
assert "score" in result                # key presence is not behaviour
def test_thing(): pass                  # no
result = evaluate(...)  # no assertion on the relationship to input
```

`forensic_audit.py` already detects most of these — in test files. Pointing it at
itself would be a good first use of the fixed version.

---

## 6. Skill contract

| # | Rule |
|---|---|
| K1 | `SKILL.md` has valid frontmatter: `name` (kebab-case, matches directory), `description` (states *what* and *when*, includes the trigger phrase), `disable-model-invocation: true` for slash-command-only skills. |
| K2 | **Progressive disclosure is explicit.** A `references/*.md` file is only read if SKILL.md says "Read `references/x.md`" at the step that needs it. Files nobody is told to read are dead weight. |
| K3 | **SKILL.md is under ~200 lines.** It is loaded into context every time the skill fires. Detail goes in `references/`. |
| K4 | **Compose by reference, not transcription.** If a skill uses `review`'s five axes, it points at `skills/review/SKILL.md`. Copying the axes in creates a frozen fork of a moving target — this is live in `work` today. |
| K5 | **Ground in the catalog.** Any skill that dispatches subagents points them at `.gemini/knowledge/` before implementation, so they read rather than guess. |
| K6 | **No reserved names.** Never name a skill or alias after an Antigravity reserved command or built-in skill. `validate_skills.py` enforces the current list. |
| K7 | **No PII, no absolute paths, no personal identifiers** in any tracked file. |
| K8 | **Register in all five places** when adding a skill: `sync_skills.py` (`CORE_SKILLS` or `SKILL_MAP`, `ALIASES`, cluster membership, help text), `validate_skills.py` (`SLASH_COMMAND_SKILLS` if applicable), `README.md` (skill table, attribution, cluster blurb, counts). A missing registration means the skill installs nowhere. |
| K9 | **A `DESIGN.md` for anything non-obvious** — what failure mode the design is defending against, and what was rejected. Reviews keep rediscovering the same reasoning; write it down once. |

---

## 7. CI — what must block a merge

`.github/workflows/ci.yml` is the repository's only L4. Until it existed every
check here was L3 — real, but run at an agent's discretion, and the ones that
got skipped were the ones that would have failed.

| Job | What it runs | Blocks on |
|---|---|---|
| `tests` (ubuntu + macos) | `check_stdlib_only.py`, then `pytest -q` | any failure |
| `validate` | `validate_skills.py` (frontmatter, reserved namespaces, PII, host paths), `autowire.py --check` | non-zero exit |
| `gates` | `gate_executor.py list`, `dag_validator.py --check-mermaid` on every committed fixture, scaffold all six topologies and resolve every gate cell | an unresolvable gate, table/diagram drift |
| `forensics` | strict audit of the tree; strict audit of `fixtures/known_good`; strict audit of `fixtures/known_fake` | any violation — **and on `known_fake` exiting 0** |
| `install` (ubuntu + macos + windows) | installer scripts parse; `sync_skills.py` dry run writes nothing and `--fix` writes something reachable | a syntax error, a dry run that writes, a `--fix` that does not |

The `known_fake` row is the important one. It is the test that the tests work: a
verifier that passes a corpus of deliberately fake code is broken, and the
failure is silent unless something checks.

The matrix spans `ubuntu-latest` and `macos-latest` because every Windows-path
defect in this repo would have been caught by a Linux run; `install` adds
`windows-latest` because that is where the installer diverges.

Adding a check to CI is not optional garnish on a new verifier. A verifier that
nothing runs is L1 prose with a shebang.

---

## 8. Definition of done

A change is done when all of these are true. Not "the agent reports them true" —
true.

- [ ] `python3.12 -m pytest -q` passes, and the count went **up**.
- [ ] A differentiation test (T1) exists if the module transforms input to output.
- [ ] A negative test (T4) exists if the module validates or gates.
- [ ] Mutation smoke (T2) was run at least once by hand, and is noted in the PR.
- [ ] `validate_skills.py` exits 0.
- [ ] Documented flags match `--help`.
- [ ] No absolute paths, no PII, no `shell=True`, no stdlib shadowing.
- [ ] Every new "gate", "score", or "verify" has a function behind it (§2).
- [ ] Generated artifacts regenerated; freshness test passes.
- [ ] `DESIGN.md` updated if the reasoning changed.

---

## 9. Recipes

### Adding a skill

1. `skills/<name>/SKILL.md` — frontmatter, ≤200 lines, explicit reference reads.
2. `scripts/` stdlib-only per §3; `references/`, `templates/`, `fixtures/`, `tests/`.
3. Tests per §5 — differentiation first, it will tell you whether the skill does
   anything.
4. Register in all five places (K8).
5. `python3.12 scripts/validate_skills.py && python3.12 -m pytest -q`.
6. `DESIGN.md` if the design is non-obvious.

### Adding a verifier

1. Write `fixtures/known_bad/` **first**. This is the spec.
2. Write `fixtures/known_good/`.
3. Write the two tests: rejects bad (non-zero), accepts good (zero).
4. *Then* implement. If it passes immediately, the fixture is too easy — make the
   fake more convincing until it does not.
5. Docstring states exactly what surface is audited (V3) and what is not (V5).

### Adding a gate

Implemented in `skills/work/scripts/gate_executor.py`; follow it.

1. Decide the kind first, because it decides everything else:
   - **mechanical** — a command exit code or a filesystem fact settles it now.
   - **attested** — it is a judgement. No script can make it.
   - **trivial** — `none`. Passes, and is recorded as having checked nothing.
2. Add a `GateSpec` to `GATE_REGISTRY` with that kind, a one-line summary, and a
   predicate returning a `GateResult`. Unrecognised names must keep failing
   closed: a typo in a Gate column is not permission.
3. For a mechanical gate, bind the verdict to a recorded run whose tree digest
   still matches the working tree. Evidence for code that has since changed is
   not evidence.
4. For an attested gate, validate the *form* of the attestation only — signed by
   a role other than the worker's, citing artifacts that exist and are not
   placeholders, against the current digest. Say in the docstring that it cannot
   check whether the reviewer was right, because it cannot.
5. Test both directions: gate false → the status write is refused and the
   process exits non-zero; gate true → allowed.
6. Add the gate to whatever emits it (templates, scaffolders) **and** confirm the
   test that walks every emitted gate still passes. Four gates once shipped in
   scaffolded topologies with no registry entry; because gates fail closed,
   those DAGs could never reach `PASSED`.
7. *Only now* may the gate's name appear in a SKILL.md.

A gate name that exists in documentation before step 5 is a lie with a schedule.

An override must be possible and must be loud: `dag_validator.py --force-status
--reason "<why>"` writes the bypass into the DAG's override log. A silent bypass
is worse than no gate, because it looks like a gate.

### Handling a judgement task

Do not write a scorer. Write a collector (§S9), hand the evidence to the model,
and validate the model's output for provenance. If a number is unavoidable, use
ordinal bands (`low`/`medium`/`high`/`unknown`) — `unknown` must be a first-class
value with defined behaviour, because "we did not find out" and "scored zero" are
different facts and a numeric scale cannot tell them apart.

---

## 10. Working with Gemini / Antigravity on this repo

Both reviewed failures were authored by those harnesses. The pattern is not
carelessness — it is that a strong instruction-following model, given "build a
profiler with tests", will build the shape of one. Structural countermeasures:

1. **Give it the fixture, not the goal.** "Make this known-fake input produce a
   non-zero exit" is checkable. "Build a forensic auditor" is not.
2. **Tests before implementation, reviewed before implementation starts.** A test
   written after the code tends to assert what the code does.
3. **Never let the author's harness certify the author's work.** A verification
   pass in the same session with the same context is L2, worth nothing.
4. **Run the differentiation test yourself** before accepting a deliverable. It is
   one command and it catches the entire class.
5. **Reviewer models must be at least as strong as author models.** `work`
   currently dispatches its whole committee on `flash` while workers inherit a
   stronger model; that guarantees only obvious shortcuts are caught.
6. **CI is the only reviewer that cannot be talked around.** Everything else is
   advisory until §7 exists.

---

## References

- `docs/review/2026-09-18-asis-tobe.md` — first review; root causes RC-1…RC-4.
- `docs/review/2026-09-23-work-skill-review.md` — `work` review; findings W-01…W-12
  and the three reproducible gate-bypass demonstrations.
- `skills/cognitive-profiler/DESIGN.md` — a worked example of §S9, §T1, and
  provenance enforcement.
- `docs/skill_authoring_guide.md` — mechanics of skill layout.
