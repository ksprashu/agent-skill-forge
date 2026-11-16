# H2O Loop Swarm Specification (`skills/h2o`)

Status: approved
Slug: h2o-swarm
Path: architectural
Date: 2026-11-16

---

## 1. Problem Statement & Objectives

`skills/work` is the forge's heavyweight swarm: a parallel DAG with design tournaments, explorers and a forensic auditor. Many tasks need less than that but more than a single agent: a well-scoped change that should be planned, built and attacked by reviewers from a different model family, with a hard stop when the loop stops converging.

This specification defines **`skills/h2o`** (Cluster `C1` `plan-spec`, capability `swarm-execution`, trigger `/h2o`), a lean sequential swarm in which **Hydrogen writes and Opus attacks**:
1. The coordinator grills the user, one question at a time, into `.agents/h2o/REQUIREMENTS.md`; `intent-reviewer` gates `>= 90%` clarity before criteria are written.
2. `criteria-writer` writes binary done criteria, non-goals and acceptance tests to `.agents/h2o/CRITERIA.md`; once the user approves them they are frozen by SHA-256.
3. `planner` writes `.agents/h2o/PLAN.md`; `plan-reviewer` attacks it against the criteria.
4. A single `implementer` builds on branch `h2o/<slug>` in the shared (`inherit`) workspace.
5. `functional-reviewer`, `code-reviewer` and `security-reviewer` attack the result in that order; after any rework all three run again.
6. `summarizer` writes the final report; `monitor` watches for stalls.
7. `skills/h2o/scripts/h2o_gate.py` (Python stdlib) backs the gates with `verdict`, `freeze`, `check-frozen`, `record`, `grant`, `status` and `diff-guard`.

Rationale, rejected alternatives and residual risks live in [`skills/h2o/DESIGN.md`](../../skills/h2o/DESIGN.md); this spec does not repeat them.

### Explicit Non-Goals
- **No parallel authoring:** no best-of-n planners or implementers, no `share`/`branch` workspaces, no merge step. Use `/work` for parallel DAG execution.
- **No quality judgement in scripts (`S9`):** `h2o_gate.py` checks shape, evidence presence, hashes, counts and diff patterns; it never decides whether code, plans or findings are correct.
- **No unbounded loops:** no gate iterates past its cap without an explicit user decision.
- **No reviewer fixes:** reviewers report findings; only authors change files.
- **No remote side effects by default:** nothing is pushed to a remote unless the user asks.
- **No third-party Python dependencies (`S1`).**

---

## 2. Roles & Models

[`skills/h2o/swarm.config.json`](../../skills/h2o/swarm.config.json) is the source of truth; `SKILL.md` must agree with it.

| Role | Model | Kind |
| :--- | :--- | :--- |
| `intent-reviewer` | `claude-opus-5-5-medium` | adversarial reviewer |
| `criteria-writer` | `gemini-4-hydrogen-high` | author |
| `planner` | `gemini-4-hydrogen-xhigh` | author |
| `plan-reviewer` | `claude-opus-5-5-medium` | adversarial reviewer |
| `implementer` | `gemini-4-hydrogen-high`, escalated to `gemini-4-hydrogen-xhigh` after its first NOT GOOD | author |
| `functional-reviewer` | `claude-opus-5-5-medium` | adversarial reviewer |
| `code-reviewer` | `claude-opus-5-5-medium` | adversarial reviewer |
| `security-reviewer` | `claude-opus-5-5-high` | adversarial reviewer |
| `summarizer` | `gemini-4-hydrogen-high` | author |
| `monitor` | `gemini-4-hydrogen-medium` | support (`swarm_monitor`) |

---

## 3. Requirements

| ID | Requirement |
| :--- | :--- |
| `R1` | Every author runs on a Gemini Hydrogen model and every adversarial reviewer on a Claude Opus model, so every review is cross-family. |
| `R2` | Every `swarm{action:"add"}` sets `model` explicitly; no worker inherits the coordinator's model. |
| `R3` | No plan exists before the user approves the done criteria. |
| `R4` | After approval, `CRITERIA.md` and the acceptance tests are frozen; `check-frozen` fails if any frozen file changes or disappears. |
| `R5` | Reviewer verdicts use the format `VERDICT: GOOD \| NOT GOOD \| NOT GOOD (DESIGN)` with evidence (command output or `file:line`) and, for NOT GOOD, numbered findings; `verdict` rejects any post that lacks them. |
| `R6` | Each gate (`intent-reviewer`, `plan-reviewer`, `functional-reviewer`, `code-reviewer`, `security-reviewer`) allows 3 NOT GOOD verdicts; the 3rd makes `record` exit `3` and the coordinator asks the user to stop or continue. `grant` extends one gate by 3 attempts. |
| `R7` | A `NOT GOOD (DESIGN)` verdict from any reviewer routes to `planner` and counts against the plan gate. |
| `R8` | Reviews run one at a time, in the order functional, code, security, so at most one Opus worker is busy. |
| `R9` | `diff-guard` fails a diff that deletes test files, adds skip markers or lint/type suppressions, or removes more assertions from tests than it adds. |
| `R10` | `h2o_gate.py` exits `0` pass, `1` fail, `2` invocation error, `3` loop cap reached, and reads gates, routing and caps from `swarm.config.json` rather than restating them. |
| `R11` | The skill is registered in Cluster `C1` with capability `swarm-execution` and listed in `README.md`, `docs/catalog_reference.md` and `docs/user_guide.md`. |

---

## 4. Binary Acceptance Criteria

| ID | Criterion | Proof |
| :--- | :--- | :--- |
| `A1` | `skills/h2o/SKILL.md` has valid frontmatter (`name: h2o`, `description` naming `/h2o`) and the repo validator passes. | `python3 scripts/validate_skills.py` exits `0` |
| `A2` | Every role, model, stage and loop limit in `SKILL.md` matches `swarm.config.json`. | `python3 -m pytest skills/h2o/tests/test_h2o_config.py` passes |
| `A3` | All authors are `gemini-4-hydrogen-*` and all adversarial reviewers are `claude-opus-5-5-*` in `swarm.config.json`. | config test passes |
| `A4` | `max_not_good_per_gate` is `3` and the implementer escalates to `gemini-4-hydrogen-xhigh` after 1 NOT GOOD. | config test passes |
| `A5` | `verdict` exits `1` on a verdict with no evidence and on a NOT GOOD with no numbered finding; exits `0` on a well-formed GOOD. | `python3 -m pytest skills/h2o/tests/test_h2o_gate.py` passes |
| `A6` | `check-frozen` exits `1` after a frozen file is edited or deleted, and `0` when untouched. | gate test passes |
| `A7` | `record` exits `3` on the 3rd NOT GOOD at a gate; after `grant`, the next NOT GOOD at that gate exits `0` or `1`, not `3`. | gate test passes |
| `A8` | `record` routes a `NOT GOOD (DESIGN)` verdict to `planner` and charges it to the plan gate. | gate test passes |
| `A9` | `diff-guard` exits `1` for each of: a deleted test file, an added skip marker, an added suppression, a net loss of assertions; exits `0` for a clean diff. | gate test passes |
| `A10` | `h2o_gate.py` imports only the Python standard library. | repo stdlib check (`scripts/check_stdlib_only.py`) passes |
| `A11` | `h2o` appears in the C1 tables of `README.md` and `docs/catalog_reference.md`, in the C1 directory and decision matrix of `docs/user_guide.md`, and in both attribution matrices. | `grep -n "h2o"` on each file returns the rows |
