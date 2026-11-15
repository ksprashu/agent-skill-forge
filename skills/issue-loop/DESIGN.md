# Design Notes — `issue-loop`

Why `issue-loop` is structured around five deterministic L3 boundaries. Read
`SKILL.md` for operational usage.

---

## 1. Failure Modes Defended Against

Automated GitHub issue fixers routinely fail in five predictable ways:

1. **Prompt Injection via Issue Text:** Public GitHub issues are attacker-controlled
   input. An issue body containing `Ignore previous instructions`, fake HTML stage
   markers, or `curl ... | bash` can hijack an unguarded agent into leaking tokens
   or editing unintended files.
2. **Duplicate Comment Spam Across Re-Runs:** Re-running an issue loop on a
   repository posts duplicate triage and status comments on every pass unless
   comments carry machine-readable idempotency markers checked prior to posting.
3. **Parallel Worker Merge Conflicts:** Dispatching multiple subagents against an
   issue queue without deterministic file-ownership partitioning causes concurrent
   edits to the same module or test suite and silent clobbering on merge.
4. **Premature Issue Auto-Closure on Partial Fixes:** Including `Fixes #N` in a PR
   body for an issue classified as `partially_addressed` closes the ticket on merge
   while remaining requirements stay unresolved.
5. **Same-Context Self-Certification (L2 Theatre):** Allowing the model that wrote
   a fix to certify its own tests, scope, and review without a SHA-bound gate or
   cross-family verifier turns verification into prose.

---

## 2. Structural Countermeasures (`Engineering Standard §S1–S9, §V1–V6`)

### A. Capture-Time Redaction & Untrusted Framing (`§S8`, `§S9`)
- `scripts/issue_state.py` separates mechanical GitHub GraphQL collection from
  LLM triage judgement (`§S9`). It never emits triage classifications or priority
  scores.
- Every issue title, body, and comment passes through `issue_common.redact_secrets()`
  at ingest (`§S8`) so tokens, credentialed URIs, private keys, email PII, and
  host home paths are scrubbed before entering the evidence file or agent context.
- `issue_common.frame_untrusted()` wraps untrusted strings with explicit
  instruction warnings, neutralises HTML comment delimiters (`<!--` -> `&lt;!--`),
  and surfaces factual `suspicious_directives` flags. Genuine stage markers are
  read only from issue comments with author and comment ID provenance.
- *Rejected alternative:* regex-based auto-triage in Python. Determining whether
  a bug is `already_fixed` or `operational_report` requires inspecting live code
  against the claim; regex heuristics produce confident wrong answers (`§S9`).

### B. Author-Verified Idempotent Stage Markers (`scripts/stage_comment.py`)
- Each pipeline milestone writes a versioned HTML marker on line 1:
  `<!-- issue-loop:stage=triage|plan|pr v1 -->`.
- Before posting, `stage_comment.py` fetches paginated comments (`--paginate`),
  resolves the authenticated viewer (`gh api user -q .login`, plus optional
  `--trusted-login`), and matches ONLY comments whose author is trusted and
  whose body leads with the stage marker. Third-party spoofed markers are
  ignored so attackers cannot block comments or hijack `--update` targets.
- Outgoing bodies are scanned for unredacted secrets and AI attribution trailers
  (including `Co-Authored-By` and `Generated with [Claude Code]...` links).

### C. File-Disjoint Swarm Track Partitioning (`scripts/plan_tracks.py`, `§V1–V6`)
- `plan_tracks.py` validates Stage 2 `plan.json` against `tests/fixtures/known_good/`
  and `tests/fixtures/known_bad/`:
  - Rejects exact file collisions, case-insensitive collisions (`Auth.py` vs
    `auth.py`), and directory-prefix containment (`src/auth` vs `src/auth/tokens.py`)
    across concurrent tracks' `owned_files` and `test_files` in `swarm` mode
    or when `--check-disjoint` is passed.
  - Enforces `--from-evidence` parity so no open issue from Stage 1 is silently
    dropped during planning.
  - Requires any `partially_addressed` issue to appear in its track's
    `partial_issues` list so Stage 5 derives `Refs #N` instead of `Fixes #N`.
- *Rejected alternative:* advisory file lists in markdown prose. Subagents ignore
  overlapping file warnings under parallel execution unless an L3 gate blocks
  before branch creation.

### D. SHA-Bound Verification & Cross-Family Gate (`scripts/verify_gate.py`, `§V1–V6`)
- `verify_gate.py` binds test runs, code review (`skills/review` schema), and
  security scans (`skills/security-review` schema, requiring producer
  `security-review`) to `head_sha` (and live `git rev-parse HEAD` when
  `--repo-root` is given), and emits `head_sha` + `branch` in its PASS output.
- Enforces `0` open `P0–P3` findings across both review and security contracts,
  refuses omitted or `"not_installed"` expected scanners absent from
  `not_inspected`, enforces `changed_files ⊆ allowed_files`, and in swarm mode
  requires distinct author vs verifier model families unless
  `--allow-intra-family-fallback` is paired with a written disclosure reason
  (`>= 20` characters).

### E. Partial-Fix Reference & Gate Guard (`scripts/ship_pr.py`)
- `ship_pr.py` requires a matching-SHA and matching-branch `PASS` gate report
  (or explicit `--no-gate --no-gate-reason` override), blocks protected branches
  (`main`/`master`), non-conventional PR titles, AI attribution trailers,
  unredacted secrets, and closing clauses (`Fixes`/`Closes`/`Resolves`, `#N` or
  GitHub issue URLs) across both the PR body and branch commit messages for any
  issue declared under `--refs`.
- *Rejected alternative:* stripping `Fixes #N` silently at PR creation. Silent
  rewriting masks author confusion; failing closed with exit `1` makes the
  partial-fix distinction explicit before the PR opens.
