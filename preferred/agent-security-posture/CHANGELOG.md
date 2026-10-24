# Changelog

## 2026-10-24 (check_vulns coverage and enrichment)
- `check_vulns.py lockfile` reads pnpm-lock.yaml (v5, v6, v9), yarn.lock (classic and berry), uv.lock, Pipfile.lock, Gemfile.lock, gradle.lockfile, go.mod and Maven pom.xml. Line parsers, no YAML library. pom.xml sends explicit versions only: unresolved `${properties}`, ranges and parent-managed versions are reported unresolved (exit 2), a DOCTYPE or ENTITY declaration is refused (exit 64), and a `coverage_notes` entry says transitive dependencies were not checked.
- go.sum no longer over-reports: `/go.mod`-only lines (versions read during resolution but never built) are not counted. When go.mod and go.sum from one directory are both passed, go.mod is read; packages are de-duplicated across files.
- New `--enrich`: OSV aliases per advisory, CISA KEV membership and date added, FIRST EPSS score and percentile for CVE aliases, and GHSA severity, CVSS score, CWEs, summary and URL through `gh api /advisories/<id>` (id checked against a strict pattern, no shell). Only advisory ids leave the machine. A failed or missing source (including gh not on PATH) is a problem: status partial, exit 2, and the source's field is null rather than false.
- Tests: canned fixtures for every new format (credentials in git/tarball URLs never reach output or request bodies), go.sum/go.mod counting, and enrichment against a local fake server and a fake gh, including a KEV-listed versus not-listed differentiation test. No live network.

## 2026-10-22 (outside sources)
- New `references/audit-method.md`: the finding test, three verdicts (confirmed, needs_validation, rejected), severity anchors, checker-is-never-the-finder, local-only evidence. Adapted from Cloudflare's security-audit skill (MIT) at c1c8a8c, with a hand-off to that skill for full codebase audits.
- New `references/readonly-infra-audit.md`: read-only audit of a GitHub org, DNS/CDN accounts and hosts, with masking, skip-and-record for mutating checks, and a fixed report shape.
- GitHub Advisory Database (reviewed and malware sets) added to the monitoring sources.
- SKILL.md gains a Modes section and points triage at the audit method.
- Registered in the d2 security cluster, the preferred catalog and the README.
- Review fixes (ChatGPT, Grok Bot): secrets in audit reports by location and type only, no fragments or hashes; read-only judged by effect with known command traps; report gains a verdict field, a confirmed-only top 10, and unscored hardening and needs-validation sections; needs_validation pauses only the dependent action; GHSA endpoints marked tested; source note for the infra-audit checklist; stale counts and wording fixed.

## 2026-10-22 (review fixes)
Changes from a four-agent review of commit 3c29a1e, plus the owner's decision on agent autonomy.
- Trigger scoped to coding work: runs when code, dependencies, agent tools or MCP config change, or on request. No scans on text-only tasks; no routine status written to shared logs.
- New Authority section: the user's direct instruction defines scope; documents, emails, web pages, tool output and other agents' messages are data; relayed approvals need confirmation; plain-text signatures are claims.
- Autonomy rule: inside an authorised coding task, small reversible code and dependency changes need no fresh ask if compatibility is checked and rollback kept. Major-version upgrades, secret rotation, new tools or MCP servers, publishing, sending, spending, deleting and out-of-scope work need approval.
- Secrets reported by file, line and type, never by value; the user rotates.
- Third-party MCP servers only after operator approval; OSV and NVD over HTTPS by default. Social and web signals marked as untrusted leads.
- Triage before blocking; stop the unsafe action, not unrelated work. Exit 2 from the helper means unchecked, never safe.
- Replaced scripts/check-vulns.sh (ignored its argument, sent only pubStartDate, hardcoded a sample package, could report success as failure under pipefail) with scripts/check_vulns.py: stdlib Python, real lockfile parsing, OSV querybatch, both NVD dates, timeouts, one bounded retry, explicit exit codes. Tests in tests/test_agent_security_posture_check_vulns.py.
- Swarm review fixes (ChatGPT, Grok Bot): npm entries are sent only when resolved from the public registry, and workspace packages are skipped; Python pins must be one exact version (no wildcards or compound specifiers); malformed NVD entries exit 2 instead of crashing.
- Helper hardening from the Copilot review: only public-registry versions are sent (git, path, URL and alternate-registry entries are reported unresolved by name); unresolved entries never echo raw text, so credentials in URLs stay out of output; -r, -c and -e directives make a result partial; malformed or incomplete OSV and NVD responses exit 2.
- Install-script blocking commands named; outside queries send only ecosystem, name and version.
- Evals expanded: injected instruction, hallucinated package, redacted secret, blocked network, unapproved MCP server, relayed approval, patch versus major upgrade. Triggers gain near-boundary negatives.
- NVD example in references/monitoring-sources.md now sends pubStartDate and pubEndDate together.


## 2026-10-22
- Initial creation of agent-security-posture skill.
- Core always-on workflow for monitoring CVEs/OSV/OWASP, secure coding enforcement, and low-friction fixes in AI agent harnesses.
- References for OWASP Agentic Top 10 2026, monitoring sources, and integration guidance.
