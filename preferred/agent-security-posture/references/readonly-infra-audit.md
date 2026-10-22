# Read-Only Infrastructure Audit

Read this only when the user explicitly asks for a security audit of deployed infrastructure: their GitHub org, DNS or CDN accounts, or hosts they run. It covers what is live, which a codebase audit can't see. Adapted from a community read-only audit prompt.

**The whole mode is read-only: gather a report, change nothing.** Fixes wait for the user's go-ahead on the report.

## Before starting

1. **Scope in writing.** List each asset class and account the user named: for example "all repos in org X", "all zones in the logged-in DNS account", "these hosts over SSH". Audit nothing outside it.
2. **Check access per section.** If a CLI is unauthenticated (`gh auth status`, the DNS or CDN provider's CLI, SSH), stop that section and ask the user for access. Never skip a section silently; record it under "Needs access".
3. **Output location.** Write only to `./security-audit-<YYYY-MM-DD>/` (or a directory the user names). Touch nothing else.

## Hard rules

- Only list, get, describe, status, show and scan-style commands. Prefer `--dry-run` where it exists.
- No writes, config edits, deploys, dependency or version updates, secret rotation, firewall, WAF or branch-protection changes, console mutations, package installs on remote hosts, or `sudo`.
- If a check needs a mutating command, don't run it. Record it as "SKIPPED: needs approval" with the command you would have run, and move on.
- No active external port scans, brute force or exploitation without the user's explicit go-ahead for that specific action.
- Never print a full secret or token. Mask to prefix plus last 4 characters plus a fingerprint (for example a SHA-256 prefix of the value), and say where it was found.
- Sub-agents, if used, get these same rules and report in the same format.

## What to check

**Dependencies** (each repo or deployed project): known CVEs and end-of-life versions, with native read-only tooling: `npm audit`, `pip-audit`, `cargo audit`, `govulncheck`, `apt list --upgradable`; or `scripts/check_vulns.py lockfile`.

**Secrets**: committed `.env` files, keys and tokens; secrets in git history; hardcoded credentials in CI configuration.

**GitHub** (org and repos):
- Repo and org settings, visibility, branch protection on default branches.
- Secrets and environment variables in repo settings (names and scopes only).
- Default workflow token permissions (read-only is the safe default).
- `pull_request_target` workflows that check out or run untrusted PR code, and script injection through `${{ github.event.* }}` in `run:` steps.
- Third-party actions pinned to a tag or branch rather than a full commit SHA.
- OIDC trust settings and secret exposure to forks.
- Token, deploy-key and GitHub App scopes.
- Dependabot and secret-scanning status.

**DNS, CDN and edge** (for example Cloudflare):
- DNS records proxied versus DNS-only, and any record that exposes an origin IP behind a proxied name.
- SSL/TLS mode (anything short of full strict on a proxied origin), certificate expiry.
- WAF managed rulesets and custom rules, rate limits.
- Zero-trust access apps and policies.
- API token and service-token scopes.
- Worker and environment secrets (names only), page or redirect rules.
- Tunnel and origin exposure.

**Hosts** (publicly reachable ones):
- Listening sockets, and which are reachable from outside.
- `sshd` config: root login and password authentication should be off.
- `sudo` rules, world-writable files, SUID binaries.
- Cron jobs and systemd timers, running service versions.
- `.env` and config file permissions.
- Firewall and fail2ban status, failed-login spikes in auth logs.
- Pending security updates, expired TLS certificates.
- For every public project on the host, the dependency and secret checks above.

## Report: `security-audit-<date>/REPORT.md`

1. **Executive summary**: the top 10 risks, ranked, with quick wins first.
2. **Per-asset sections**, one finding at a time: finding, severity (Critical, High, Medium, Low; use the anchors in `references/audit-method.md`), evidence (the exact command and its output, secrets masked), concrete remediation (what to patch, update or disable), confidence.
3. **Three separate lists at the end**: "Skipped: needs approval", "Needs access", "Couldn't verify".

End with: "Report only. No changes made. Waiting for your go-ahead before any fix."
