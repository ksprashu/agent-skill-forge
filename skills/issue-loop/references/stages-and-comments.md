# Stages, JSON Contracts, and GitHub Comments

Read this before executing Stage 1 or Stage 2 of `issue-loop`.

---

## 1. Stage 1 Triage Taxonomy

Inspect the codebase at `file:line` for every issue in `evidence.json` before
assigning one classification:

| Classification | Track Required? | Stage 5 PR Link | Action |
| :--- | :--- | :--- | :--- |
| `valid_bug` | Yes | `Fixes #N` | Reproduce with failing test (TDD), fix root cause, open PR. |
| `valid_enhancement` | Yes | `Fixes #N` | Write acceptance test, implement minimal change, open PR. |
| `partially_addressed` | Yes | `Refs #N` | Fix scoped slice, record `partial_issues`, never auto-close `#N`. |
| `open_pr_exists` | No (`null`) | None | Link open PR in triage comment; skip duplicate implementation. |
| `already_fixed` | No (`null`) | None | Cite `file:line` and commit fixing it in triage comment. |
| `operational_report` | No (`null`) | None | Explain config/runtime gap in triage comment; do not edit code. |
| `deferred_external` | No (`null`) | None | Cite upstream dependency/blocker; leave issue open with note. |

---

## 2. Stage 2 `plan.json` Schema

Pass `plan.json` to `scripts/plan_tracks.py --plan plan.json --from-evidence evidence.json --check-disjoint`:

```json
{
  "schema_version": "1",
  "mode": "standalone",
  "issues": [
    {
      "issue": 101,
      "classification": "valid_bug",
      "evidence": ["src/auth/tokens.py:42 indexes parts[1] on empty string"],
      "track_id": "track-auth"
    },
    {
      "issue": 102,
      "classification": "partially_addressed",
      "evidence": ["src/cli/flags.py:88 fixes export path; import flag deferred"],
      "track_id": "track-cli"
    }
  ],
  "tracks": [
    {
      "track_id": "track-auth",
      "issues": [101],
      "partial_issues": [],
      "summary": "Guard empty bearer token header in verify_token.",
      "owned_files": ["src/auth/tokens.py"],
      "test_files": ["tests/test_tokens.py"],
      "acceptance_tests": ["python3 -m unittest tests/test_tokens.py"]
    }
  ]
}
```

Every `owned_files` and `test_files` entry must be a normalised repo-relative
POSIX file path with no `..` traversal and no wildcards.

---

## 3. Stage 4 `gate_bundle.json` Schema

Pass `gate_bundle.json` to `scripts/verify_gate.py --bundle gate_bundle.json --repo-root .`:

```json
{
  "schema_version": "1",
  "mode": "standalone",
  "track_id": "track-auth",
  "branch": "fix/issue-101-auth-token",
  "head_sha": "abc1234def5678",
  "author_model": "gemini-4-carbon-high",
  "review_model": "opus-5.5-high",
  "security_model": "opus-5.5-high",
  "tests": {
    "head_sha": "abc1234def5678",
    "command": "python3 -m unittest tests/test_tokens.py",
    "exit_code": 0,
    "passed": 12,
    "failed": 0,
    "skipped": 0,
    "red_green_verified": true
  },
  "scope": {
    "allowed_files": ["src/auth/tokens.py", "tests/test_tokens.py"],
    "changed_files": ["src/auth/tokens.py", "tests/test_tokens.py"]
  },
  "review": {
    "head_sha": "abc1234def5678",
    "findings_file": "review_findings.json"
  },
  "security": {
    "head_sha": "abc1234def5678",
    "secrets_found": 0,
    "scanners": {
      "semgrep": "clean",
      "gitleaks": "clean",
      "actionlint": "not_applicable",
      "zizmor": "not_applicable",
      "osv-scanner": "not_applicable",
      "trivy": "not_applicable"
    },
    "findings_file": "security_findings.json"
  }
}
```

Inline `findings_doc` objects may be used instead of `findings_file`. Both must
conform to `skills/review/references/findings.schema.json` with `0` open `P0-P3`
findings (`review` requires producer `review`; `security` requires producer
`security-review`). Any expected scanner omitted or marked `not_installed` must
appear in `not_inspected`.

---

## 4. Stage Comment Templates

`scripts/stage_comment.py` prepends `<!-- issue-loop:stage=<stage> v1 -->`
automatically and refuses duplicate posts unless `--update` is passed.

### Stage 1 (`--stage triage`)
```markdown
### Issue Triage
- **Classification:** `valid_bug`
- **Code Evidence:** `src/auth/tokens.py:42` (`verify_token` splits header without bounds check)
- **Existing PRs:** None
- **Next Step:** Reproduce with a failing unit test and scope fix under `track-auth`.
```

### Stage 2 (`--stage plan`)
```markdown
### Fix Plan (`track-auth`)
- **Owned Files:** `src/auth/tokens.py`, `tests/test_tokens.py`
- **Root Cause:** Missing empty-string check before splitting authorization scheme.
- **Acceptance Test:** `python3 -m unittest tests/test_tokens.py` (`test_empty_header_returns_false`)
- **Link Mode:** `Fixes #101`
```

### Stage 5 (`--stage pr`)
```markdown
### PR Ready for Review
- **Pull Request:** https://github.com/<owner>/<repo>/pull/<PR>
- **Commit:** `<head_sha>`
- **Verification:** `python3 -m unittest tests/test_tokens.py` (`12 passed, 0 failed`; `verify_gate.py` `PASS`)
- **Resolution:** `Fixes #101` (or `Refs #102` — remaining sub-tasks stay open)
```
