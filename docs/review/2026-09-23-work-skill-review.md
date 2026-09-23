# Review — the `work` skill (multi-agent swarm engine)

| | |
|---|---|
| **Review date** | 2026-09-23 |
| **Commit reviewed** | `3569d1c` + uncommitted working tree |
| **Scope** | `skills/work/` — SKILL.md, 4 scripts, 6 references, 5 test suites (8,819 lines) |
| **Method** | Full read of SKILL.md and all references; full read of `forensic_audit.py`; targeted read of `arbiter_eval.py` and `dag_validator.py`; **three live adversarial experiments** against the gates |
| **Changes made to the repo** | None at review time — read-only. Remediation followed the same day; see § 6 |

---

## 1. Executive summary

`work` is the most ambitious thing in the repo and, structurally, the best idea in it. The
decomposition is right: a Sentinel that never writes code, a dispatch-only Orchestrator, a
declarative DAG as shared state, competing design proposals, and a six-role verification
committee. That topology is genuinely well designed, and the DAG engine underneath it is the
best-engineered component in the repository.

**The problem is that almost none of the quality machinery it describes is connected to
anything.** The skill defines nine barrier gates, six verification personas, a scored design
tournament, and a Binary Veto. I tested three of these adversarially. All three passed content
that they exist specifically to reject:

| Gate | Test | Result |
|---|---|---|
| Forensic Integrity Auditor (`zero_mock`, "Binary Veto") | A function that ignores its input and returns a hardcoded dict — the exact `psychometric_evaluator.py` failure that shipped | ✅ **"ZERO forensic violations"**, exit 0, in `--strict --integrity-mode benchmark` |
| Architectural Arbiter (`arbiter_pass`) | A content-free proposal with the right headings vs. a rigorous one with different headings | ✅ **Hollow doc wins 95–40**, "SELECT_BETA (Decisive lead)" |
| Barrier gates (all nine) | Grep for a gate executor | **None exists.** Gates are parsed into a string field and never evaluated |

The gates are not weak. They are **absent** — the vocabulary is real, the enforcement is not.
Every `PENDING → PASSED` transition in a `/work` run is an agent asserting its own success, and
`dag_validator.py --set-status task=PASSED` writes that assertion to disk unconditionally.

This is the same root cause that produced the fake `cognitive-profiler`: **a judgement task
implemented as string-matching, wearing the vocabulary of measurement.** `work` did not fail to
catch that skill by accident. It cannot catch it.

**Overall health**

| Area | Verdict | Confidence |
|---|---|---|
| Topology and role design | 🟢 Genuinely good; keep it | High |
| DAG engine (parse/validate/render) | 🟢 Well-built, 2,559 lines of real tests | High — read + tests run |
| Barrier gate enforcement | 🔴 Does not exist | High — demonstrated |
| Forensic auditor fitness | 🔴 Cannot detect faked implementations | High — demonstrated |
| Arbiter scoring fitness | 🔴 Anti-correlated with quality | High — demonstrated |
| Skill composition (`spec`/`review`/`test`/`catalog`) | 🔴 Restated, never invoked; `catalog` absent | High |
| Cross-platform correctness | 🔴 Hardcoded Windows paths inside dispatch prompts | High |

---

## 2. What holds up

Worth stating plainly, because the defect register below is long and the good parts are load-bearing.

- **The Sentinel / Orchestrator / Worker split is correct.** Separating the user liaison from the
  dispatcher from the implementer is exactly right, and the "dispatch-only" constraint on the
  Orchestrator is the kind of thing most agent frameworks get wrong.
- **A declarative Markdown DAG as shared state is a strong choice.** Human-readable,
  diffable, model-parseable, and it survives context loss — an agent that wakes up cold can
  reconstruct where it is. This is better than the in-memory task lists most orchestrators use.
- **`dag_validator.py` is real engineering.** 1,239 lines with clean parse/validate/render
  separation, 632 lines of unit tests, a 522-line adversarial hardening suite, and 77 e2e cases.
  It correctly detects cycles, missing dependencies, duplicate IDs, and Mermaid/table drift.
- **The six-persona committee is the right *set* of perspectives** — design drift, code quality,
  hostile edge cases, integrity, acceptance, and cold-run certification genuinely cover the space.
- **Fresh subagents per milestone** (Invariant, SKILL.md:348) is the correct instinct about
  context contamination.

The design is sound. The instrumentation is missing.

---

## 3. Defect register

### 🔴 W-01 — Barrier gates are decorative (Critical)

`SKILL.md:176` defines nine deterministic gates: `spec_approved`, `design_pass`, `arbiter_pass`,
`spike_pass`, `exit_0`, `review_pass`, `zero_mock`, `acceptance_pass`, `victory_cert`.

`dag_validator.py:104` parses `gate` into a `str` field. It is stored (`:117`), re-rendered
(`:397`, `:485`), and **never evaluated**. There is no gate executor, no registry mapping a gate
name to a predicate, and no code path that can refuse a status transition on gate grounds.

`dag_validator.py:1186-1194` — `--set-status <id>=PASSED` splits the string and writes it. Any
subagent can mark any task `PASSED` at any time, including tasks it does not own.

**Consequence:** the entire verification lifecycle is advisory. A worker that writes nothing, a
reviewer that writes "LGTM", and a Victory Auditor that emits `VICTORY CONFIRMED` without running
anything all produce byte-identical DAG state to a real run.

**This is the finding to fix first.** Every other defect below is survivable if gates are real.

---

### 🔴 W-02 — The Forensic Auditor cannot detect a faked implementation (Critical)

`forensic_audit.py:294-310` builds `test_files` from six test-file globs and audits only those.
**Production source is never parsed.** The AST auditor is capable — it finds mock imports,
tautological assertions, self-comparisons, and empty test bodies — but it is pointed exclusively
at the test suite, so a hardcoded return value in `src/` is structurally invisible to it.

It also has no mutation check, so it cannot distinguish a test that constrains behaviour from one
that asserts a file exists.

**Demonstrated** (reproduction in Appendix A): a module whose `evaluate()` ignores its argument
and returns a fixed dict, with two tests that pass, audited in the strictest available mode:

```
🔍 Forensic Integrity Audit Engine — Mode: BENCHMARK
📁 Discovered 1 test suite files to audit.
✅ ZERO forensic violations detected. Test suite displays high physical integrity.
exit=0
```

That is the precise shape of `skills/cognitive-profiler/scripts/psychometric_evaluator.py` as it
shipped. The gate named `zero_mock`, carrying "BINARY VETO" authority, cleared it.

---

### 🔴 W-03 — The Arbiter scores structure, and is anti-correlated with quality (Critical)

`arbiter_eval.py:evaluate_design_file` computes its 100-point score from:

- heading regex matches (`architecture|topology|system design|overview`, `data model|schema|…`)
- count of fenced code blocks
- total line count ≥ 40
- occurrences of 17 hardcoded "AI slop" words

`arbiter_eval.py:156-157` — `alpha_maint = 15.0` / `beta_maint = 15.0`. The Maintainability axis
is a constant for both candidates. It contributes 15 points to each total and can never
discriminate; it exists only to make the weights sum to 100.

**Demonstrated** (Appendix B): a rigorous proposal (`SKIP LOCKED` semantics, a measured 4,100
jobs/sec ceiling, an idle-transaction-timeout failure mode, a named migration path) versus a
content-free document with the right headings and four ` ```TBD``` ` fences:

| Axis | Substantive | Hollow |
|---|---|---|
| Architecture & Spec Grounding | 10.0 | 30.0 |
| Interface & Data Contracts | 5.0 | 25.0 |
| Failure Modes & Resilience | 5.0 | 20.0 |
| **TOTAL** | **40.0** | **95.0** |

Verdict emitted: `SELECT_BETA (Decisive lead: 95.0 vs 40.0)`.

**Consequence:** this scorecard is rendered into `.agents/design/arbiter_scorecard.md` and shown
to the user as the basis for an architectural decision. It actively rewards documents that
perform rigour over documents that contain it — and it teaches the two Design Architect agents,
who can read the scoring script, to optimise for headings.

---

### 🟠 W-04 — The Binary Veto script has zero tests (High)

| Script | LOC | Test files referencing it |
|---|---|---|
| `dag_validator.py` | 1,239 | 4 |
| `scaffold_work.py` | 932 | 5 |
| `arbiter_eval.py` | 420 | 1 |
| **`forensic_audit.py`** | **340** | **0** |

The component with veto authority over every milestone is the only one with no coverage. W-02
would have been caught on day one by a single test asserting the auditor rejects a known-fake
fixture.

---

### 🟠 W-05 — Hardcoded Windows paths inside subagent dispatch prompts (High)

Five occurrences across four files: `SKILL.md:94`, `SKILL.md:217`,
`references/domain_autowiring.md:32`, `references/competitive_branching.md`,
`references/sentinel_protocol.md`.

`domain_autowiring.md:32` is the damaging one, because it sits inside a JSON dispatch payload a
subagent is meant to copy:

```
"Domain Skill: c:\\Users\\kspra\\code\\github\\agent-skill-forge\\preferred\\observability-and-instrumentation\\SKILL.md"
```

On macOS or Linux that `view_file` fails. The subagent then proceeds **without its domain skill
and without surfacing the failure** — the swarm silently loses the capability injection that
`domain_autowiring.md` describes as its "key technical advancement over vanilla teamwork".

Secondary: this is also an unredacted home-directory leak. `validate_skills.py:44-46` scans for
`ksprashanth@` and `ksprashu@` and therefore reports zero PII while `kspra` sits in four files —
a live instance of finding F-17 from the 2026-09-18 review.

---

### 🟠 W-06 — Domain Skill Autowiring is not implemented (High)

`domain_autowiring.md:3` states the Orchestrator "dynamically scans the local `skills/` and
`preferred/` catalogs in `agent-skill-forge` and injects specialized domain skills directly into
subagent prompt briefs."

`skills/work/scripts/` contains `arbiter_eval.py`, `dag_validator.py`, `forensic_audit.py`,
`scaffold_work.py`, and `visual_engine/`. There is no scanner, no resolver, no autowire module.

What exists is a seven-row Markdown table and an instruction to an LLM to remember it. That is a
reasonable prompt, but it is not autowiring, and the document should not claim a mechanism that
does not exist — a future contributor will build on the claim rather than the reality.

---

### 🟡 W-07 — The knowledge catalog is not wired in at all (Medium)

Reference counts across `skills/work/` (SKILL.md, references, scripts):

```
spec: 81   test: 68   review: 63   unslop: 29   prompt: 20   verify: 8   grill: 2
docs: 1    plan: 0    catalog: 0
```

`catalog` — the OKF progressive-disclosure knowledge bundle intended as the grounding layer — is
referenced **zero times**. Workers and Design Architects are dispatched with `.agents/SPEC.md` and
a role prompt, and are never pointed at `.gemini/knowledge/`.

This is the gap between the stated design intent (catalog as grounding for the swarm) and the
artifact. Every subagent currently rediscovers the codebase from scratch, which is both the
expensive path and the hallucination-prone one.

---

### 🟡 W-08 — Skills are restated, not invoked (Medium)

`work` re-describes its siblings inline rather than delegating to them:

| Sibling | How `work` uses it |
|---|---|
| `review` | The five axes are retyped in SKILL.md:149, :292, `adversarial_committee.md:12`, `team_topologies.md:37` |
| `test` | Red-Green-Refactor restated in `domain_autowiring.md:15` |
| `grill` | "Matt Pocock Socratic protocols" paraphrased in SKILL.md:71 |
| `spec` | "Official Source Grounding" paraphrased in SKILL.md:74 |
| `unslop` | Reimplemented as a 17-word list in `arbiter_eval.py:36-40` |

Three consequences: the descriptions drift the moment a sibling changes (already true — `review`'s
Empirical Challenger Mode is not reflected in `work`'s reviewer prompt); the same content is paid
for twice in tokens; and improvements to `review` never reach `work`.

The composition the user designed — `work` as a meta-skill orchestrating the core skills — is the
right model. It is currently implemented as copy-paste rather than reference.

---

### 🟡 W-09 — The verification committee runs on the weakest model (Medium)

`SKILL.md:285, 291, 297, 303` — all four Verification Committee members dispatch with
`"Model": "flash"`. Implementation workers and Design Architects use `"Model": "inherit"`.

This is backwards. The committee's job is to catch sophisticated shortcuts taken by a stronger
model; giving it less capability than the author guarantees it catches only the obvious ones. If
token budget is the constraint, spend it here rather than on a second design proposal.

---

### 🟡 W-10 — The Sentinel invariant is unenforceable (Medium)

SKILL.md:13-24 and AGENTS.md both declare the primary thread "STRICTLY FORBIDDEN" from editing
files. Nothing enforces it. It is a prose instruction competing against the model's strong prior
to just fix the thing it can see.

Not fixable inside the skill — it needs a harness-level hook (Antigravity `hooks/`, which this
repo already has a directory for) that rejects write tools on the primary thread while a
`/work` run is active.

---

### 🟡 W-11 — `shell=True` on DAG-supplied strings (Medium)

`forensic_audit.py:272-281` and `arbiter_eval.py:run_command` both execute with `shell=True` on
values that originate in agent-authored Markdown. A task name or command field containing `;` or
`$()` executes. Matches F-09 from the prior review; still open.

---

### 🔵 W-12 — Six topologies documented, two templated (Low)

`team_topologies.md` specifies six topologies. `scaffold_work.py:922` accepts all six. SKILL.md
provides canonical DAG templates for two (`lifecycle`, `focused`). `proof`, `massive`, and
`review` are described in prose only, so their DAG shape is improvised per run and cannot be
regression-tested.

---

## 4. Root causes

| RC | Description | Findings |
|---|---|---|
| **RC-W1 — Vocabulary without executors.** Gate names, veto authority, and point-weighted axes are defined as *nouns* in Markdown with no function bound to them. The DAG validates graph shape; nothing validates graph *substance*. | W-01, W-02, W-03, W-06, W-10 |
| **RC-W2 — Judgement implemented as string-matching.** Where a mechanism does exist, it substitutes surface features (headings, code fences, import names) for the property it claims to measure. Same category error as the old `cognitive-profiler`. | W-02, W-03 |
| **RC-W3 — Coverage inverted against authority.** The scripts with the most power to block have the least test coverage; `forensic_audit.py` has none. | W-04 |
| **RC-W4 — Composition by transcription.** Sibling skills are quoted into `work` instead of referenced, so `work` holds a frozen copy of a moving target and the catalog grounding layer was simply forgotten. | W-07, W-08 |

RC-W1 and RC-W2 are the same failure the 2026-09-18 review recorded as RC-3 ("claims are prose,
not derived"), now reproduced one layer up: `work` is a quality system built from descriptions of
quality checks.

---

## 5. What to change

Ordered by ratio of correctness recovered to work required.

| # | Change | Closes |
|---|---|---|
| 1 | **Build `gate_executor.py`.** One registry mapping each of the nine gate names to a predicate that returns `(bool, evidence_path)`. `--set-status X=PASSED` refuses unless the gate returns true. Start with the three that are mechanically checkable today: `exit_0` (test command exit status), `zero_mock` (forensic audit exit status), `victory_cert` (cold-run exit status). | W-01 |
| 2 | **Point `forensic_audit.py` at source, and add a mutation check.** Audit `src/` for functions that return a literal with no reference to their parameters; then stub each public function body and assert the suite goes red. Ship `fixtures/known_fake/` as a permanent regression target. | W-02, W-04 |
| 3 | **Demote the arbiter from scorer to evidence collector.** It should emit the facts (sections present, code blocks, measured claims, unresolved TBDs) and let the Arbiter *agent* judge, exactly as `harvest.py` → LLM → `profile.json` works in the rebuilt `cognitive-profiler`. Delete the point totals, or keep them only as a structural-completeness checklist explicitly labelled as such. Remove the constant Maintainability axis. | W-03 |
| 4 | **Replace all absolute paths with repo-relative ones** and extend `validate_skills.py` to fail on `C:\Users\`, `/Users/`, and `/home/` in any tracked file. | W-05 |
| 5 | **Wire in `catalog`.** Dispatch briefs should point every Explorer and Worker at `.gemini/knowledge/` and require the OKF index be read before implementation. | W-07 |
| 6 | **Reference siblings instead of restating them.** Dispatch prompts carry `skills/review/SKILL.md` as a path to read, not a paraphrase of its contents. | W-08 |
| 7 | **Raise committee models to `inherit`**, and drop a design proposal if budget requires. | W-09 |
| 8 | **`shell=False` with argument lists** in both scripts. | W-11 |

Items 1–3 are the substance. Items 4–8 are hygiene that can ride along.

---

## 6. Remediation log — 2026-09-23

Implemented the same day as the review, in six phases. Every claim below is
backed by a command in this repository that exits non-zero when the claim stops
being true; where something is still open, it says so.

| # | Finding | Status | What changed | Proof |
|---|---|---|---|---|
| W-01 | Barrier gates are decorative | ✅ Closed | `skills/work/scripts/gate_executor.py` (946 lines). Every gate name resolves to a predicate in `GATE_REGISTRY`; `dag_validator.py` refuses a `PASSED` transition whose gate returns false and exits 3. Unknown gate names fail closed. | `skills/work/tests/test_gate_executor.py` — 69 tests |
| W-02 | Auditor cannot detect a faked implementation | ✅ Closed | `forensic_audit.py` rebuilt to walk production source, not just tests: hardcoded returns, ignored parameters, dead computation, stubs, tautological assertions, plus an opt-in mutation check (`--mutate --test-cmd`). | Appendix A now exits 1; `known_fake`/`known_good` corpora, 64 tests |
| W-03 | Arbiter scoring anti-correlated with quality | ✅ Closed | Scoring deleted. `arbiter_eval.py` emits evidence — substantive/trivial/placeholder blocks, measured claims, named alternatives, hedges, unresolved markers — and a verdict of `JUDGEMENT_REQUIRED`. | Appendix B now returns `JUDGEMENT_REQUIRED`; 40 tests |
| W-04 | Binary Veto script has zero tests | ✅ Closed | 593 lines of tests against the auditor, including the two committed fixture corpora as permanent regression targets. | CI job `forensics` fails if the auditor ever passes `known_fake` |
| W-05 | Hardcoded machine paths in dispatch prompts | ✅ Closed | All absolute paths replaced repo-wide; `validate_skills.py` now fails on `/Users/`, `C:\Users\`, `/home/` in any tracked file, reporting every line, with five documented whole-file exemptions and an inline `host-path-ok` marker. | `tests/test_host_path_scan.py` — 17 tests |
| W-06 | Domain Skill Autowiring not implemented | ✅ Closed | `skills/work/scripts/autowire.py` scans `skills/` and `preferred/`, matches the task text against the mapping matrix, verifies every emitted path exists, and reports the terms that matched. `--check` fails on a matrix row that names a skill that is not on disk. | `skills/work/tests/test_autowire.py` — 52 tests, including a parse of the reference table to pin doc against code |
| W-07 | Knowledge catalog not wired in | ✅ Closed | Every dispatch brief in `SKILL.md` and `orchestrator_protocol.md` now names `.gemini/knowledge/` as required grounding and points at `skills/catalog/SKILL.md`. | Prose; no executor. See "Still open" below. |
| W-08 | Skills restated, not invoked | ✅ Closed | Committee prompts cite `skills/review/SKILL.md`, `skills/unslop/SKILL.md`, `skills/test/SKILL.md` as paths to read rather than paraphrasing their rubrics. | Prose; no executor. |
| W-09 | Committee runs on the weakest model | ✅ Closed | Every `"Model": "flash"` in the work skill and its references is now `"inherit"`. | Grep; the autowire suite asserts the reference doc stays clean |
| W-10 | Sentinel invariant unenforceable | ⚠️ Open | Unchanged. A primary thread that decides to write code cannot be stopped by a script in the repository it is editing; this needs harness-level enforcement. | — |
| W-11 | `shell=True` on DAG-supplied strings | ✅ Closed | Argument lists via `shlex.split` throughout; the gate executor's own test suite asserts the string `shell=True` does not appear in its source. | `test_gate_executor.py::TestExecutionSafety` |
| W-12 | Six topologies, two templated | ✅ Closed | `full`, `proof` and `massive` emitted byte-identical DAGs — two of the six names had nothing behind them. `proof` now adds a validation spike and splits the committee into three independently gated verifiers with a join; `massive` defaults to 8 milestones. All six are templated in `SKILL.md`. | `TestScaffoldedGatesAreExecutable` scaffolds all six and checks every gate resolves |

**Found during remediation, not in the original review:**

- Four gates emitted by the scaffolder — `survey_pass`, `fact_check_pass`, `analysis_pass`, `unslop_clean` — had no entry in the registry. Because gates fail closed, the `review` and `full` topologies produced DAGs whose tasks could never reach `PASSED`. Registered as attested gates, with a test that scaffolds every topology and checks every gate cell.
- `sync_skills.py --project X --skills Y` printed `[BOOTSTRAP] ... -> path` and created nothing, because writes require `--fix`; `skills/sync/SKILL.md` reproduced that output and captioned it "successfully bootstrapped". Now prints `[WOULD BOOTSTRAP] ... (dry run; re-run with --fix)`. `tests/test_sync_bootstrap.py`, 12 tests.
- The repository had no CI. Every check above was opt-in, and the checks that got skipped were the ones that would have failed. `.github/workflows/ci.yml` is the first L4 enforcement in the repo: five jobs across Linux, macOS and Windows covering the suite, skill validation, gate and DAG integrity, the known-corpus regression, and an installer smoke test.
- Three tamper-detection tests built a throwaway git repo and committed into it without disabling commit signing. On any machine with `commit.gpgsign = true` globally — and the author's is one — the commit failed against an unreachable signing agent and the test reported a tampering-detection failure that had nothing to do with tampering. The temp repo now sets `commit.gpgsign false` locally.
- `scripts/check_stdlib_only.py` enforces the stdlib-only rule where the repo actually claims it (`scripts/`, `hooks/`, `skills/work/scripts/`), rather than repo-wide — `skills/image-gen` legitimately needs Pillow.

**Still open, deliberately:**

- **W-10** as above: harness-level, not script-level.
- **W-07 and W-08 have no executor.** Both are now correct prose in the dispatch briefs, and prose is L1. Nothing fails if a future edit drops the grounding line from a brief. A linter over the dispatch payloads in `SKILL.md` would close that; it is not written.
- **Attested gates check form, not correctness.** `gate_executor.py attest` rejects an attestation that is unsigned, self-signed, cites missing or empty artifacts, or was written against a different tree digest. It cannot check whether the reviewer was right, and nothing can. That ceiling is stated in the module docstring so the next reader does not mistake the gate for more than it is.

Repository state after remediation: **624 tests pass**; `validate_skills.py`, `autowire.py --check`, `check_stdlib_only.py` and a strict `forensic_audit.py` over the tree all exit 0.

---

## Appendix A — Reproduction: forensic auditor clears a faked implementation

```bash
mkdir -p /tmp/fakeprobe/{src,tests} && cd /tmp/fakeprobe
cat > src/evaluator.py <<'EOF'
def evaluate(evidence):
    """Compute the cognitive profile from evidence."""
    return {"visual_scaffolding": 87, "text_density": 72, "decision_directness": 91}
EOF
cat > tests/test_evaluator.py <<'EOF'
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from evaluator import evaluate

def test_evaluate_returns_scores():
    result = evaluate({"signals": {"length_complaint": 12}})
    assert "visual_scaffolding" in result
    assert result["visual_scaffolding"] > 0
EOF
python3 -m pytest tests/ -q          # 1 passed
python3 <repo>/skills/work/scripts/forensic_audit.py \
    --target-dir . --integrity-mode benchmark --strict
# -> "✅ ZERO forensic violations detected."  exit 0
```

Re-run against the rebuilt auditor (post-remediation), same inputs:

```
VETO  [HARDCODED_RETURN] src/evaluator.py:1 -> Function 'evaluate(evidence)' returns
only literal values and never references any parameter. Its output cannot depend on
its input — this is a hardcoded facade.
VERDICT: VETO (1 blocking, 0 advisory)          exit 1
```

## Appendix B — Reproduction: arbiter prefers the hollow proposal

```bash
# good.md  : 17 lines of dense prose on SKIP LOCKED, measured throughput,
#            a concrete failure mode, and a migration path. No headings
#            matching the scorer's regexes, no code fences.
# hollow.md: the five expected headings, four ```TBD``` fences, padded to 47 lines.
python3 <repo>/skills/work/scripts/arbiter_eval.py \
    --design-alpha good.md --design-beta hollow.md --output-scorecard card.md
# -> Recommendation: SELECT_BETA (Decisive lead: 95.0 vs 40.0)
```

Both documents are now committed as `skills/work/fixtures/designs/substantive_proposal.md`
and `hollow_proposal.md`. Post-remediation, the same invocation emits no score
and no winner:

```
> **Verdict: JUDGEMENT_REQUIRED.** This script collects evidence; it does not rank
> proposals and does not produce a score. The Arbiter agent reads the evidence
> and both proposals, and decides.
```

## Appendix C — Scope and limits

Read in full: `SKILL.md`, all six `references/*.md`, `forensic_audit.py`.
Read in part: `arbiter_eval.py` (~250 of 420 lines), `dag_validator.py` (parse, gate, and
`--set-status` paths), `scaffold_work.py` (topology and template generation).
Not read: `visual_engine/` (1,395 lines) and its 1,143 lines of tests; `what_if_compiler.py`.
The visual subsystem is therefore **unassessed** — its two test suites pass, and nothing in this
review should be read as a judgement on it.

Test suites were run (`316 passed, 1 failed` repo-wide; the failure is the stale `skills/voice`
directory, unrelated to `work`).
