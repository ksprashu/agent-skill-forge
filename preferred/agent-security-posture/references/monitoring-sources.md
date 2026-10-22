# Vulnerability Monitoring Sources & API Quick Reference

## Primary Sources (Prefer These)

- **NVD API 2.0**: `https://services.nvd.nist.gov/rest/json/cves/2.0`
  - Params: `cvssV3Severity=CRITICAL`, `pubStartDate`, `pubEndDate` (max 120 days), `keywordSearch`, `resultsPerPage`.
  - Example recent critical: `?cvssV3Severity=CRITICAL&pubStartDate=2026-10-15T00:00:00.000&resultsPerPage=20`
  - Rate limit: ~5 req/30s unauthenticated. Optional API key for higher limits.
  - Docs: https://nvd.nist.gov/developers/vulnerabilities

- **OSV.dev**: `https://api.osv.dev/v1/query` (POST) and `/v1/querybatch`
  - No key required. Query by package+version+ecosystem or commit.
  - Example: `{"package":{"name":"requests","ecosystem":"PyPI"},"version":"2.28.0"}`
  - Batch for lockfiles. Docs: https://osv.dev/api

- **CISA KEV**, **EPSS** (FIRST), **GitHub Advisories**, vendor feeds.

## Signal Sources

- X / Twitter: high-signal security researchers, official accounts (NVD, CISA, vendors).
- The Injection, Hacker News, security blogs focused on AI agents.
- GitHub Security Advisories, npm/PyPI advisory pages.

## MCP Servers (Use If Available)

- cve-mcp / similar: unified NVD + EPSS + KEV + more.
- vulnfeed-mcp: dependency scanning with EPSS and fix versions.
- security-framework-mcp / owasp-mcp: frameworks + live CVE data.
- AWS Security Agent MCP, mcp-scan for MCP server audits.

## Practical Patterns

- On start: query last 7 days critical CVEs + scan current lockfile with OSV/native audit.
- On dep change: re-query OSV for the new versions.
- Cache results for the session to avoid repeated calls.
- Triage: prioritize by CVSS + EPSS + KEV + reachability in the project.
- Always link to primary (NVD, OSV, GHSA) for verification.

Update this reference when better free APIs or MCP servers become standard.
