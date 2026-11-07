Read this when running the scanners (step 2) and when triaging dependency or secret findings (step 5): lockfile and manifest diffs, new packages, install scripts, CI provenance, and anything the secret scanner reports.

# Secrets and software supply chain

Sources:
- OWASP Software Supply Chain Security Cheat Sheet: <https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html>
- OWASP NPM Security Cheat Sheet: <https://cheatsheetseries.owasp.org/cheatsheets/NPM_Security_Cheat_Sheet.html>
- OWASP Secrets Management Cheat Sheet: <https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html>
- SLSA specification: v1.0 <https://slsa.dev/spec/v1.0/> (levels: <https://slsa.dev/spec/v1.0/levels>), v1.1 <https://slsa.dev/spec/v1.1/>, v1.2 <https://slsa.dev/spec/v1.2/>
- OpenSSF Scorecard: <https://scorecard.dev/>, <https://github.com/ossf/scorecard>
- CISA Known Exploited Vulnerabilities: <https://www.cisa.gov/known-exploited-vulnerabilities-catalog>
- FIRST EPSS: <https://www.first.org/epss/>
- OSV: <https://osv.dev/>, OSV-Scanner: <https://google.github.io/osv-scanner/>

Per-ecosystem install flags (frozen lockfile, disabling install scripts, native audit) are in the package-manager matrix in `references/security-checklist.md`.

---

## Part 1: secrets

### Handling rules (non-negotiable)

- Report the **file, line and secret type** (for example "AWS access key id", "GitHub fine-grained PAT", "private key block"). Never copy the value, a prefix, a suffix or a hash of it into the finding, the summary, a commit message, a ticket or chat. If a scanner prints the value, redact it before quoting.
- Run Gitleaks with `--redact` so its own report does not contain the secret.
- A secret that reached a commit is compromised even if a later commit deletes it: history, forks, CI logs and caches keep it. The remediation is **rotate or revoke first**, then remove it from code, then (optionally) rewrite history. Removing it from the working tree is not a fix.
- Do not test a found credential against the live service to "confirm" it. Confirm by type, location and whether it looks like a real issued format versus an obvious placeholder.

### Tools

- Gitleaks: <https://github.com/gitleaks/gitleaks>. Scan the diff range or the working tree; current releases use `gitleaks git` (history) and `gitleaks dir` (files), older ones `gitleaks detect`. Use `--redact` and a JSON report.
- TruffleHog: <https://github.com/trufflesecurity/trufflehog> (can verify credentials against providers; do not enable verification without the owner's permission).
- GitHub secret scanning and push protection: <https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning>

### What to look for in a diff

- Literal credentials: API keys, tokens, passwords, connection strings with embedded passwords, private keys, `.pem`, `.p12`, `.jks`, kubeconfig, cloud credential JSON.
- `.env`, `.env.*`, `*.tfvars`, `secrets.yaml` added, or removed from `.gitignore`.
- Secrets in test fixtures, notebooks (`.ipynb` outputs), Dockerfiles (`ENV`, `ARG` used for secrets ends up in image layers), CI YAML, Helm values, frontend bundles (`NEXT_PUBLIC_*`, `VITE_*`, `REACT_APP_*` are shipped to browsers).
- Secrets written to logs, error messages, analytics events or LLM prompts.
- Fallback defaults such as `os.getenv("JWT_SECRET", "changeme")`: the code runs with a known secret when the variable is missing (CWE-798 / CWE-1188).

### Triage

| Signal | Verdict |
|---|---|
| Real-format key in tracked source, history or CI config | confirmed, CWE-798; severity by what the key can do |
| Placeholder (`xxx`, `<token>`, `example`, documented test keys) | rejected, note the rule id so it can be allowlisted |
| High-entropy string with no recognisable format | needs_validation; ask the owner, do not guess |
| Secret in a file that is gitignored and never committed | not a repository finding; mention only if it is shipped in an artifact |

---

## Part 2: dependencies and lockfiles

A scanner hit on a dependency is a lead. A finding still needs reachability: is the vulnerable function or code path used, in which environment (runtime vs dev vs build), and by whom.

### What to look for in a lockfile or manifest diff

- **New direct dependencies**: who publishes it, how old it is, download counts, whether the name is one edit away from a popular package (typosquat: `reqeusts`, `lodahs`, scope confusion `@types-foo/x` vs `@types/x`), whether the repository link matches the package.
- **New transitive dependencies** that appear without a matching manifest change, or a lockfile change much larger than the manifest change.
- **Resolved URL or registry changes**: `resolved` pointing at a non-default registry, a git URL, a tarball URL or a local path; `integrity` hashes removed or changed for the same version.
- **Version specifiers loosened**: `^`/`~`/`*`/`latest`, Python `>=` with no upper bound, Maven version ranges or `SNAPSHOT`, Go `replace` directives to forks.
- **Dependency confusion**: internal package names that could resolve from the public registry; missing scope or index pinning (`--extra-index-url` in pip is a classic cause, prefer `--index-url` plus a proxy).
- **Lockfile deleted or regenerated wholesale** in an unrelated change.

### Install-time code execution

Many ecosystems run package code at install or build time: npm `preinstall`/`install`/`postinstall`, Python sdists (`setup.py`, build backends), Cargo `build.rs` and proc macros, Gradle and Maven plugins. Look for:
- New dependencies that declare install scripts (npm `scripts.install`/`postinstall`, `binding.gyp`).
- Removal of `ignore-scripts`, pnpm build allowlists being widened, or new entries in Bun `trustedDependencies`.
- CI steps that install with scripts enabled while holding secrets.

npm lifecycle scripts: <https://docs.npmjs.com/cli/v11/using-npm/scripts/>

### Integrity and provenance checks

- npm: `npm audit signatures` verifies registry signatures and provenance attestations for installed packages (<https://docs.npmjs.com/verifying-registry-signatures/>). Publishing with `npm publish --provenance` from CI links the package to its source and build (<https://docs.npmjs.com/generating-provenance-statements/>).
- pip: `pip install --require-hashes -r requirements.txt` refuses any package whose hash is not pinned; generate hashes with `pip-compile --generate-hashes` or `uv pip compile --generate-hashes`. Secure installs guide: <https://pip.pypa.io/en/stable/topics/secure-installs/>
- Gradle: dependency verification via `gradle/verification-metadata.xml`, bootstrapped with `./gradlew --write-verification-metadata sha256 help` (<https://docs.gradle.org/current/userguide/dependency_verification.html>). Flag diffs that delete entries, add `<trust>` rules broadly, or switch verification to lenient.
- Go: `go.sum` plus the checksum database; `go mod verify`. Flag `GOSUMDB=off`, `GOINSECURE`, or `GONOSUMDB` / `GOPRIVATE` widened to public module paths.
- Containers: base images pinned by digest (`image@sha256:...`), not a moving tag.
- Sigstore signing and verification: <https://www.sigstore.dev/>

### SLSA, briefly

SLSA defines levels for how trustworthy an artifact's build is. v1.0 introduced the Build track (L0 none; L1 provenance exists; L2 hosted build platform with signed provenance; L3 hardened build platform that isolates builds and protects signing material). v1.1 is a revision of v1.0. v1.2 adds a Source track. In review, SLSA matters when a diff changes how release artifacts are built or signed: a change that moves publishing from CI to a developer laptop, drops provenance generation, or lets PR-triggered jobs touch release signing lowers the level. Cite the spec version you checked.

### OpenSSF Scorecard

Scorecard scores repositories on checks such as Dangerous-Workflow, Token-Permissions, Pinned-Dependencies, Branch-Protection, Code-Review, Signed-Releases, Binary-Artifacts, Maintained and Vulnerabilities. Use it two ways: to judge a new third-party dependency (a low score with no maintenance is a reason to say so in the finding), and as a checklist for the repository's own workflow changes (see `references/gha-hardening.md`). It is evidence, not a verdict.

---

## Part 3: prioritising known vulnerabilities

Native and third-party audit tools (`npm audit`, `pnpm audit`, `pip-audit` <https://github.com/pypa/pip-audit>, `cargo audit` <https://github.com/rustsec/rustsec/tree/main/cargo-audit>, `govulncheck` <https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck>, OWASP Dependency-Check <https://owasp.org/projects/dependency-check>, OSV-Scanner) list advisories. Rank them:

1. **In CISA KEV**: exploited in the wild. If the vulnerable code is reachable, treat as high or critical regardless of CVSS.
2. **High EPSS** (probability of exploitation activity in the next 30 days): raise priority; a high CVSS with a very low EPSS and no reachable path is usually a dependency-update note.
3. **Reachability**: `govulncheck` reports call-graph reachability for Go; for other ecosystems, check whether the vulnerable API is imported and called. Unreachable means needs_validation or a note, not a confirmed finding.
4. **Environment**: dev-only or build-only dependencies matter when they run in CI with secrets or ship in the artifact; otherwise lower.

Use the advisory id in `rule` (`CVE-...`, `GHSA-...`, `OSV-...`), the patched version in the remediation, and link the advisory in `references[]`.

### Triage order for a dependency alert

1. Is the advisory for a version actually resolved in the lockfile (not just allowed by the manifest)?
2. Is the package in the runtime, build or dev graph?
3. Is the vulnerable function reachable from this code?
4. Is there a fixed version within the allowed range? If yes, recommend the bump. If only a major bump fixes it, say so and give the interim mitigation.
5. KEV or high EPSS raises severity; neither lowers the bar for reachability.
