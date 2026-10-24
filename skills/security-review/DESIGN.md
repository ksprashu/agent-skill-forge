# security-review: design notes

This file records why the skill works the way it does, and what was rejected,
so reviews do not have to rediscover the reasoning.

## Leads are not findings

Scanners report hits. Most hits on a typical repository are not exploitable:
test fixtures, unreachable code, and dependencies whose vulnerable function is
never called. If raw scanner output were the result, you would get two
failures:

- Teams learn to ignore the gate.
- An agent "fixes" non-issues, which adds churn.

So `run_scanners.py` emits **leads** under a separate schema
(`security-review/leads@1`), and its SARIF output labels each one an
"unreviewed lead". Only the model's triage turns a lead into a **finding** in
the shared contract.

The triage uses the six-element test from agent-security-posture's audit
method. The contract enforces the boundary in two ways:

- `security_verdict` has no `rejected` value.
- `needs_validation` findings cannot be P0 or P1.

Rejected alternative: emitting findings directly from scanner severity. CVSS
or a semgrep severity is not exploitability.

## Missing is never clean

A security tool that exits 0 because it ran nothing is worse than no tool. The
script's exit status is computed from the relevance and status of each tool:

- A tool that fits the repository but is not installed, times out, exits with
  a code it does not document, or prints output that does not parse makes the
  run `partial` (exit 2). It is listed in `not_inspected`, which flows
  unchanged into the findings document.
- A relevant tool that the user deselected with `--tools` is also listed, but
  the run is not partial, because the user chose that.
- Tools that do not fit the repository are skipped with a reason, and do not
  make the run partial. Examples are zizmor with no workflows, or cargo-audit
  with no `Cargo.lock`.

## Redaction at capture (S8)

Secrets must not reach stdout, `--json-out`, SARIF, stderr or the model's
context. Three layers enforce this:

1. gitleaks runs with `--redact`.
2. The normalisers copy whitelisted fields only. They never copy the following:
   - gitleaks `Secret`, `Match`, `Author` or `Email`
   - trivy secret `Match` or `Code`
   - semgrep `extra.lines`
3. `redact()` masks known credential shapes, and any long mixed
   letter-and-digit run, in every message and stderr tail.

The raw gitleaks report goes to a temporary file, which is deleted after
parsing.

The end-to-end test simulates a gitleaks that ignored `--redact`. It checks
that the planted token is absent from every output channel.

## One trivy pass

`trivy fs --scanners vuln,misconfig,secret` covers what `trivy config` does,
because the misconfiguration scanner is the same. A second pass would double
the runtime and duplicate the leads.

Trivy's secret scanner overlaps with gitleaks. It is kept because it finds
secret types that gitleaks does not. `dedupe` removes exact repeats.

## Diff mode

How each kind of tool is scoped to the diff:

- **semgrep** uses `--baseline-commit`, so only leads new since the base remain.
- **gitleaks** scans the commit range `base..HEAD`, plus a temporary copy of
  the uncommitted changed files. Scanning the working directory would
  re-report every old secret.
- **trivy, actionlint and zizmor** run over the tree. Their file-level leads
  are filtered to changed files, and the number dropped is reported as
  `filtered_unchanged`.
- **Dependency tools** run only when a lockfile changed, and they are not
  filtered. The SKILL.md tells the reviewer to count a dependency lead only if
  the change introduced or exposed the package.

## Bundled contract copy

`npx skills add` installs a skill folder on its own, so this skill cannot
import `skills/review/scripts/findings.py` at run time. Instead it carries
byte-identical copies of `findings.py` and `findings.schema.json`.
`tests/test_security_review_contract_sync.py` fails when they drift.

Rejected alternative: a symlink. It breaks when the folder is copied out of
the repository.
