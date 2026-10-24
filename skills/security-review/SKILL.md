---
name: security-review
description: Code-level security review of a diff, pull request or whole repository. Runs a threat model, runs the installed scanners (semgrep, gitleaks, osv-scanner, trivy, actionlint, zizmor and the native dependency audits), triages every lead with an exploitability test, does a manual review against OWASP Top 10 2025, ASVS 5, CWE Top 25 and the OWASP cheat sheets, checks live advisories, and emits findings in the same JSON contract as `review`. Use for /security-review, or when asked for a security review, a vulnerability check of code, a secrets scan, or whether a change is safe to merge.
license: Apache-2.0
---

# Security Review

You produce **security findings**: confirmed or plausible vulnerabilities, each
tied to specific lines and a CWE, CVE or GHSA id. Scanners produce **leads**,
which are unreviewed hits. A lead becomes a finding only once you have triaged
it. The output is a JSON findings document that `scripts/findings.py`
validates and gates on.

**Paths:** `<skill-dir>` is the directory that contains this SKILL.md. Run
scripts as `python3 <skill-dir>/scripts/<name>.py`. They use only the Python
standard library (3.12+).

**Scope.** This skill reviews code, dependencies, CI workflows and IaC in a
repository. Agent behaviour, tool and MCP permissions, and read-only audits of
GitHub orgs, DNS or hosts belong to `agent-security-posture`, if it is installed.

## Modes

| Invocation | Scope | Scanner call | `mode` |
| --- | --- | --- | --- |
| `/security-review` | working tree vs HEAD, untracked files included | `--diff HEAD` | `diff` |
| `/security-review --base <ref>` | merge-base(ref, HEAD) to the working tree | `--diff $(git merge-base <ref> HEAD)` | `diff` |
| `/security-review --pr <n>` | GitHub PR `n` (check out its head with `gh pr checkout <n>` first) | `--diff <pr base sha>` | `pr` |
| `/security-review --repo` | whole tree, plus full git history for secrets | `--audit` | `repo` |

## Rules that do not bend

- **Never print a secret.** Report the file, the line and the secret type only:
  never the value, a fragment of it, or a hash. The scanner script already
  redacts at capture. Do not undo that by quoting the source line.
- **Missing is not clean.** A scanner that is not installed, times out or fails
  goes in `not_inspected`. Exit 2 from either script means unchecked, not safe.
- **Evidence and judgement are separate.** Scanner output is evidence. The
  verdict is yours, and you must be able to defend it with the six elements below.
- **Read-only.** Do not fix, commit or push unless the user asks. Do not
  install scanners without approval. Report each missing one, with its install
  command.

## Workflow

### 1. Threat model (STRIDE-lite)

Read `references/security-checklist.md` and `references/owasp-top10-2025.md`.

Write five short lines in your notes before you read any code. Each line names
something specific to this change. Do not pad them with generic advice.

- **Assets**: data, credentials or capabilities this code touches.
- **Entry points**: HTTP handlers, CLI args, files, queues, webhooks, model
  output, CI events (`pull_request_target`, `issue_comment`).
- **Trust boundaries**: where lower-trust input meets higher-trust code.
- **STRIDE**: which of spoofing, tampering, repudiation, information disclosure,
  denial of service or elevation of privilege are plausible here, and where.
- **Out of scope**: what you will not look at, and why.

### 2. Run the scanners

Read `references/secrets-and-supply-chain.md` if a scanner is missing or a
secret lead appears.

```bash
python3 <skill-dir>/scripts/run_scanners.py --diff <base> --json-out leads.json
```

Use `--audit` instead of `--diff` for `--repo`. Use `--tools a,b` to run a subset.

The script runs only the installed tools that fit the repository: semgrep (with
language packs), gitleaks, osv-scanner, trivy, actionlint and zizmor (only if
there are workflows), npm audit, pip-audit, govulncheck and cargo-audit (only
if there are lockfiles). It prints `{status, tools, leads, not_inspected}`.

Exit codes: 0 clean, 1 leads, 2 partial, 64 usage error. Copy its
`not_inspected` list into your findings document unchanged.

In diff mode, file-level leads are filtered to changed files. Dependency leads
cover the whole lockfile. Count each one as a finding only if the change adds
the package or makes it reachable.

### 3. Triage every lead

Read `references/cwe-top25.md` to choose the rule id.

A lead is a finding only when you can name all six of these:

1. the **lower-trust principal** (anonymous user, PR author, tenant, model output)
2. the **input they control**
3. the **control that should stop it**, and why it fails here
4. the **trust boundary** crossed
5. the **principal or resource affected**
6. a **concrete result** (data read or changed, code run, money moved, service down)

Give each lead one verdict:

- **confirmed**: all six hold, and you traced the path in the code.
- **needs_validation**: plausible, but one element depends on something you
  cannot see, such as config or a deployment detail. Severity is capped at P2.
- **rejected**: an element is missing. Record why in your notes. A rejected
  lead never becomes a finding.

Common rejections: test-only code, unreachable code, input that is already
trusted, or a dependency whose vulnerable function is not called.

Defence-in-depth suggestions on their own are not vulnerabilities. Report them
as `nit`, if at all.

When `agent-security-posture` is installed, its `references/audit-method.md`
has the full method and the severity anchors. Where possible, have a second
agent or a fresh pass check confirmed P0/P1 findings. The finder should not be
its own checker.

### 4. Manual review

Scanners miss logic flaws. Read the changed code, plus enough of its callers to
follow data across each trust boundary from step 1. Use these references:

- `references/owasp-top10-2025.md` and `references/security-checklist.md`: always.
- `references/asvs-5.md`: when the change touches authentication, sessions,
  access control, crypto, file handling or data protection.
- `references/llm-and-api.md`: when the code calls an LLM, handles model
  output, gives an agent tools, or exposes an HTTP API.
- `references/gha-hardening.md`: when `.github/workflows/` or actions change.
- `references/cheat-sheets.md`: for the fix you will suggest.

Look especially for these, because no scanner here finds them:

- missing or wrong authorisation (IDOR, tenant checks)
- authentication logic, sessions and token lifetimes
- business-logic abuse
- server-side request forgery (SSRF) through URL parameters
- unsafe deserialisation of trusted-looking data
- race conditions on money or quotas
- secrets in logs or errors
- model output that reaches a shell, SQL, HTML or a tool call

### 5. Live advisories

Read `references/secrets-and-supply-chain.md`.

Run this when dependencies changed, or when a lead names a CVE or GHSA.

- **If `agent-security-posture` is installed:**
  `python3 <its-dir>/scripts/check_vulns.py lockfile <lockfile> --enrich`.
  This adds OSV aliases, CISA KEV membership, EPSS and GHSA details. Exit 2
  means partial.
- **Otherwise:** use the osv-scanner and native-audit leads from step 2. You
  can also query `https://api.osv.dev/v1/query` with the ecosystem, package and
  version only.

Send only ecosystem, package and version to outside services. Never send
lockfiles, paths or code.

Raise the severity of a confirmed, reachable dependency finding if it is on
KEV or has EPSS above 0.1. Never raise one only because it has a high CVSS score.

### 6. Emit findings

Read `references/cheat-sheets.md` for the `references[]` URLs, and
`references/cwe-top25.md` for rule ids. Write one document:

```json
{"schema_version": "1", "producer": "security-review", "mode": "diff",
 "summary": "One sentence: what you reviewed and what matters most.",
 "inspected": ["app.py", "semgrep", "gitleaks"],
 "not_inspected": [{"what": "trivy", "reason": "not installed"}],
 "findings": [{
   "id": "SEC-001", "severity": "P1", "axis": "security", "rule": "CWE-89",
   "title": "User id interpolated into SQL in get_user",
   "file": "app.py", "start_line": 12, "end_line": 12,
   "rationale": "Anonymous caller controls `id`; the f-string bypasses parameterisation; attacker reads any row in users.",
   "evidence": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")  # semgrep formatted-sql-query",
   "suggestion": "cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))",
   "references": [{"title": "OWASP SQL Injection Prevention Cheat Sheet",
                   "url": "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"}],
   "confidence": "high", "status": "new", "prior_id": "", "security_verdict": "confirmed"}]}
```

Field rules:

- `axis` is always `security`.
- `rule` matches `CWE-n`, `CVE-…`, `GHSA-…`, `OSV-…`, `ASInn`, `LLMnn` or `APInn`.
  Prefer the most specific CWE. Use the advisory id for a dependency.
- Severity: critical = `P0`, high = `P1`, medium = `P2`, low = `P3`,
  informational = `nit`.
- `needs_validation` findings cannot be P0 or P1.
- `evidence` holds the code or the tool output, with any secret redacted.
- `rationale` states the six elements in a sentence or two.
- `inspected` lists the files and tools you actually covered.

Validate the document, then gate on it and convert it to SARIF:

```bash
python3 <skill-dir>/scripts/findings.py validate findings.json
python3 <skill-dir>/scripts/findings.py gate findings.json          # exit 1: open P0-P3
python3 <skill-dir>/scripts/findings.py sarif findings.json > findings.sarif
```

Fix every validation error before you report.

Then give the user a short rendering:

- findings by severity
- what was not inspected, and why
- the install commands for missing scanners

Do not report anything else.

## Scanner install hints

`brew install semgrep gitleaks osv-scanner trivy actionlint zizmor`,
`pipx install pip-audit`, `go install golang.org/x/vuln/cmd/govulncheck@latest`,
`cargo install cargo-audit`.

Suggest these to the user. Do not run them.
