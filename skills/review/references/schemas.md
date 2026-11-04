# Findings document, severity, and renderings

The **primary output** of every review is one JSON findings document. The
canonical schema is `findings.schema.json`, next to this file. It is
generated from the constants in `scripts/findings.py`, and a test keeps the
two in sync. Markdown (section 5) is a rendering of the JSON for humans. It
is never the source of truth, and it can't close a finding.

```bash
python3 <skill-dir>/scripts/findings.py schema              # print the schema
python3 <skill-dir>/scripts/findings.py validate FILE       # 0 valid, 1 invalid, 2 unreadable
python3 <skill-dir>/scripts/findings.py gate FILE           # 0 none open, 1 open P0-P3 or invalid
python3 <skill-dir>/scripts/findings.py sarif FILE          # SARIF 2.1.0 for code scanning
```

`FILE` may be `-` for stdin.

---

## 1. Severity: one scale for every producer

| Severity | Definition | Merge effect (via `gate`) |
| :---: | --- | --- |
| **P0** | Exploitable vulnerability (RCE, SQLi, auth bypass, cross-tenant IDOR), silent data loss or corruption, or a crash on a critical path. No workaround. | blocks |
| **P1** | Broken business invariant, race condition (TOCTOU), resource leak, breaking public contract. | blocks |
| **P2** | Edge-case logic defect, N+1 or unindexed query, missing validation, fragile error recovery. | blocks |
| **P3** | Hygiene: dead code, single-use wrapper, readability, style that no linter covers. | blocks |
| **nit** | Optional polish. The author may ignore it. | never blocks |

`security-review` severities map onto the same scale: critical is P0, high
is P1, medium is P2, low is P3, and informational is nit
(`SECURITY_SEVERITY_MAP` in `findings.py`).

`gate` treats every P0–P3 as blocking until its status is `fixed` or
`accepted_pushback`. It doesn't encode a "soft blocker" or a lead sign-off.
If a P2/P3 shouldn't hold the merge, the author pushes back with a reason
and the reviewer records `accepted_pushback`.

Questions are not findings. Put them in `summary`, or ask them in
conversation. If the answer reveals a defect, raise it as a finding.

**Don't downgrade a blocker.** A disputed P0/P1 goes to a human with its
repro attached. Its severity doesn't move to fit a schedule.

## 2. Evidence tiers

| Severity | Required in the finding | Enforced by `validate`? |
| --- | --- | --- |
| P0, P1 | `evidence` of 20 or more characters: the repro command and its output, a failing test, or a concrete trace. `confidence` medium or high. | yes |
| P2, P3 | `evidence` quoting the code, plus a `rule` or behaviour citation | no: reviewer discipline |
| nit | nothing beyond rationale | n/a |
| any `style` | at least one `references[]` URL (the guide section or the linter rule doc) | yes |
| any `security` | `rule` is a CWE, CVE, GHSA, OSV, ASI, LLM or API id; `security_verdict` is `confirmed` or `needs_validation`; a `needs_validation` finding can't be P0/P1 | yes |

## 3. The document

```json
{
  "schema_version": "1",
  "producer": "review",
  "mode": "pr",
  "summary": "Adds user search. One injection (P0) and one style issue (P3) open.",
  "inspected": ["app/search.py", "app/utils.py", "ruff-check (ran, exit 1)"],
  "not_inspected": [
    {"what": "mypy", "reason": "skipped: mypy not found on PATH"},
    {"what": "security-review", "reason": "skill not installed; basic OWASP pass only"}
  ],
  "findings": [
    {
      "id": "REV-001",
      "severity": "P0",
      "axis": "security",
      "rule": "CWE-89",
      "title": "User input is interpolated into a SQL string",
      "file": "app/search.py",
      "start_line": 14,
      "end_line": 15,
      "rationale": "q from request.args reaches cursor.execute via an f-string; any caller can run SQL.",
      "evidence": "curl '/search?q=x%27%20OR%201=1--' returned all 1,204 users (expected 0).",
      "suggestion": "cursor.execute(\"SELECT * FROM users WHERE name = ?\", (q,))",
      "references": [{"title": "CWE-89", "url": "https://cwe.mitre.org/data/definitions/89.html"}],
      "confidence": "high",
      "status": "new",
      "prior_id": "",
      "security_verdict": "confirmed"
    }
  ]
}
```

| Field | Notes |
| --- | --- |
| `mode` | `pr`, `diff` or `repo` |
| `inspected` / `not_inspected` | What you looked at, and what you didn't, with a reason (V5). Copy every collector `not_inspected` entry here. |
| `id` | `PREFIX-NNN`, unique within the document. Use a new id each round. `prior_id` links back. |
| `axis` | `scope-architecture`, `correctness`, `security`, `reliability`, `performance`, `data-integrity`, `tests`, `observability`, `style` |
| `rule` | `CWE-89`, `google-pystyle-2.12`, `ruff:B006`, `eslint:no-eval`, `SC2086`... Use an empty string only for nits. |
| `file`, `start_line`, `end_line` | Repo-relative POSIX path. Absolute paths, `..`, and backslashes are rejected. |
| `suggestion` | A drop-in replacement for lines `start_line`..`end_line`, or an empty string |
| `confidence` | `high`, `medium` or `low` |
| `status` | `new`, `still_open`, `reopened`, `fixed` or `accepted_pushback` (see section 4) |
| `prior_id` | The id this finding continues from the previous round. Required for every status except `new`. |
| `security_verdict` | `confirmed` or `needs_validation` on the security axis, `n/a` elsewhere |

Every field is required and no extra fields are allowed. There is no score,
verdict or "approved" field, because approval is the `gate` exit code.

## 4. Status across re-review rounds

| Status | Set when | Blocks? |
| --- | --- | --- |
| `new` | First raised this round | yes (P0–P3) |
| `still_open` | The prior finding is unchanged in the new code | yes |
| `reopened` | The thread is marked resolved but the code didn't change or the fix doesn't work | yes |
| `fixed` | You verified the defect is gone (re-ran the repro, or read the new code) | no |
| `accepted_pushback` | The author's reply refutes the finding with evidence, and you agree | no |

Carry `fixed` and `accepted_pushback` findings into the next document for
traceability. SARIF output omits closed findings. Never re-raise an
`accepted_pushback` finding unless the code it covers changes again. If it
does, the finding gets a new id with `status: new`.

## 5. Markdown rendering (secondary)

When a human reads the review, render the JSON as one block per finding,
ordered by severity. Don't edit the markdown instead of the JSON.

````markdown
### REV-001 · P0 · security · CWE-89 — User input is interpolated into a SQL string
`app/search.py:14-15` · confidence high · confirmed · new

**Why:** q from request.args reaches cursor.execute via an f-string; any caller can run SQL.

**Evidence:**
```
curl '/search?q=x%27%20OR%201=1--' returned all 1,204 users (expected 0).
```

**Suggested fix (replaces lines 14-15):**
```python
cursor.execute("SELECT * FROM users WHERE name = ?", (q,))
```

**Refs:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
````

A review summary for a PR lists the following, then the finding blocks:

1. the scope (PR number or diff base) and lines changed
2. the `gate` result: open blocking count by severity, and ids
3. `not_inspected`, verbatim
4. what's good about the change: one or two specific lines, no filler

For a repository audit (`--repo`), add a table of findings by module and
severity, built by counting findings by file prefix. It's a count, not a
score.

The older long-form defect write-up (description, blast radius, repro,
before/after, verification command) is still a good shape for a P0/P1 in
prose. `scripts/defect_validator.py --file <report.md>` checks that shape.
It doesn't replace `findings.py validate`, and it shouldn't be applied to
P2/P3/nit renderings, which don't need a repro.
