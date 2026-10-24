# Read-Only Infrastructure Audit

Read this only when the user explicitly asks for a security audit of deployed infrastructure: their GitHub org, DNS or CDN accounts, or hosts they run. It covers what is live, which a codebase audit can't see. The checklist was inspired by a read-only audit prompt shared publicly as a screenshot, with no author or licence given; the wording here is written for this skill.

**The whole mode is read-only: gather a report, change nothing.** Fixes wait for the user's go-ahead on the report.

## Before starting

1. **Scope in writing.** List each asset class and account the user named: for example "all repos in org X", "all zones in the logged-in DNS account", "these hosts over SSH". Audit nothing outside it.
2. **Check access per section.** If a CLI is unauthenticated (`gh auth status`, the DNS or CDN provider's CLI, SSH), stop that section and ask the user for access. Never skip a section silently; record it under "Needs access".
3. **Output location.** Write only to `./security-audit-<YYYY-MM-DD>/` (or a directory the user names). Touch nothing else.

## Hard rules

- Read-only means by effect, not by command name: no change to any remote state; no installs, builds, target scripts or dependency fetches; local writes only to the output folder. A `describe` or `scan` command can still write or call out, and `--dry-run` isn't a guarantee. Before running a command you haven't used this way, check what it does.
- Known traps: `gh api` with `-X POST/PATCH/PUT/DELETE`, or with `-f`/`-F` (which switch it to POST); `npm audit fix` and anything that installs; `pip-audit -r requirements.txt`, which resolves the file into a temporary environment and downloads packages. Prefer passive reads: provider list and get calls, and static reading of lockfiles already on disk (`scripts/check_vulns.py lockfile`, `npm audit --package-lock-only`).
- Tools that refresh an advisory database or module cache (for example `cargo audit`, `govulncheck`) fetch into a local cache. Run them only where the user has accepted that, and say so in the report.
- If you can't establish what a check would change, don't run it: record it as "SKIPPED: needs approval" or "Couldn't verify".
- No writes, config edits, deploys, dependency or version updates, secret rotation, firewall, WAF or branch-protection changes, console mutations, package installs on remote hosts, or `sudo`.
- If a check needs a mutating command, don't run it. Record it as "SKIPPED: needs approval" with the command you would have run, and move on.
- No active external port scans, brute force or exploitation without the user's explicit go-ahead for that specific action.
- Report a secret by location (file and line, or the setting's name) and type only, with a local finding ID such as SECRET-03. Never include the value, any fragment of it (prefix or last characters), or a hash of it: for short or structured credentials those can give away most of the value.
- Sub-agents, if used, get these same rules and report in the same format.

## What to check

**Dependencies** (each repo or deployed project): known CVEs and end-of-life versions, from lockfiles already on disk: `scripts/check_vulns.py lockfile`, `npm audit --package-lock-only`, `apt list --upgradable`. See the traps above before using `pip-audit`, `cargo audit` or `govulncheck`.

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

1. **Executive summary**: up to 10 confirmed risks, ranked, quick wins first. Only `confirmed` findings go here. Never fill the list to reach ten.
2. **Per-asset sections**, one finding at a time: finding, verdict (`confirmed`, `needs_validation` or `rejected`, as defined in `references/audit-method.md`), severity for confirmed findings only (Critical, High, Medium, Low, using the same anchors), evidence (the exact command and its output, with secrets reported by location and type only), concrete remediation (what to patch, update or disable), confidence.
3. **Hardening notes**: checklist gaps with no demonstrated boundary failure. No severity, never in the top 10.
4. **Needs validation**: each open hypothesis with the exact missing fact and a safe way for the owner to check it. No severity.
5. **Three separate lists at the end**: "Skipped: needs approval", "Needs access", "Couldn't verify".

End with: "Report only. No changes made. Waiting for your go-ahead before any fix."
