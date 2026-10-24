Read this when scoping the review (step 1: threat model, trust boundaries, what the diff touches) and during manual review (step 4: per-area checks, language patterns, package-manager matrix).

# Security review checklist

Lineage: adapted and generalised from the `security-and-hardening` skill in addyosmani/agent-skills (<https://github.com/addyosmani/agent-skills/tree/main/skills/security-and-hardening>). That skill is written for building TypeScript web apps; this version is for reviewing diffs in any language and feeds the six-element finding test in SKILL.md.

Companion references: `owasp-top10-2025.md` (categories and CWEs), `cwe-top25.md` (choosing the `rule`), `asvs-5.md` (citing controls), `llm-and-api.md`, `gha-hardening.md`, `secrets-and-supply-chain.md`, `cheat-sheets.md` (fix links).

---

## 1. Threat model first (step 1)

A control without a threat model is a guess. Before reading code line by line, spend a few minutes on:

1. **Trust boundaries the diff touches.** HTTP handlers, form fields, file uploads, webhooks, message queues, CLI arguments, environment variables set by others, third-party API responses, CI events, and **LLM output**. Each is attack surface.
2. **Assets.** Credentials, PII, payment data, admin actions, money movement, signing keys, CI secrets.
3. **Principals.** Who can reach the changed code: anonymous internet, authenticated user, another tenant, fork contributor, operator. A finding needs a lower-trust principal reaching something it should not.
4. **STRIDE over each boundary:**

| Threat | Ask | Typical mitigation | Top 10:2025 |
|---|---|---|---|
| Spoofing | Can someone impersonate a user or service? | Authentication, signature verification | A07 |
| Tampering | Can data be altered in transit, at rest, or in the build? | Parameterised queries, integrity checks, TLS, signed artifacts | A05, A08, A03 |
| Repudiation | Can an action be denied later? | Audit logging of security events | A09 |
| Information disclosure | Can data leak? | Field allowlists, encryption, generic errors | A01, A04, A02 |
| Denial of service | Can it be overwhelmed? | Rate limits, size caps, timeouts | A06, A10 |
| Elevation of privilege | Can a user gain rights they should not? | Authorization on every request, least privilege | A01 |

5. **Abuse cases.** For each feature in the diff, ask "how would I misuse this?" If you cannot name the trust boundary for a feature, say so in the summary rather than guessing findings.

Design flaws (A06 Insecure Design) are real findings when the diff introduces them: a password reset with no token expiry, a money transfer with no idempotency, an approval flow the requester can approve.

---

## 2. Expectation tiers

Use these to judge whether a gap is a finding, a question, or fine.

### Always (absence on reachable code is usually a finding)

- External input validated at the boundary (type, length, range, allowlist), server-side.
- Database queries parameterised; no string-built SQL, NoSQL or LDAP queries.
- Output encoded for its context; framework auto-escaping not bypassed.
- Authorization checked on every request for every object and function, not only authentication.
- Passwords hashed with argon2id, scrypt, bcrypt or PBKDF2 with a work factor; never plaintext or fast hashes.
- Session cookies `HttpOnly`, `Secure`, `SameSite`; session id rotated on login.
- TLS for external traffic; certificate verification on.
- Secrets from the environment or a secret manager, never in source.
- The project's native dependency audit run against the committed lockfile.

### Ask first (flag for human review even when the code looks right)

- New or changed authentication flows, MFA, password reset, SSO.
- New categories of stored sensitive data (PII, payment, health).
- New external integrations, webhooks or outbound fetches.
- CORS changes.
- New file upload or download handlers.
- Rate-limit or throttling changes.
- New roles, permissions or privilege grants; CI permission changes.

### Never (presence is a finding unless clearly unreachable)

- Secrets committed to version control.
- Passwords, tokens, full card numbers or session ids written to logs.
- Client-side validation treated as the security boundary.
- Security headers or CSRF protection disabled for convenience.
- `eval`, `exec`, `Function()`, `innerHTML`, `dangerouslySetInnerHTML`, `v-html` with user-influenced data.
- Auth tokens in `localStorage` or other script-readable storage.
- Stack traces or internal errors returned to users.
- TLS verification disabled (`verify=False`, `InsecureSkipVerify: true`, `rejectUnauthorized: false`, trust-all `TrustManager`).

---

## 3. Per-area checks (step 4)

### Injection (A05; CWE-89, CWE-78, CWE-77, CWE-94, CWE-79)
- [ ] Every query uses bound parameters or a query builder that binds; identifiers (table, column, sort field) come from an allowlist.
- [ ] No shell invocation with interpolated input; argument arrays used; `--` before user-supplied positional arguments (CWE-88).
- [ ] No template rendering of user-supplied template strings (server-side template injection, CWE-94).
- [ ] HTML sinks use auto-escaping or a sanitizer such as DOMPurify; URL attributes reject `javascript:`.

### Authentication and session (A07; CWE-287, CWE-306, CWE-384, CWE-307)
- [ ] Credential endpoints rate-limited or locked out.
- [ ] Reset and verification tokens random (CSPRNG), single-use, expiring, compared in constant time.
- [ ] JWTs verified: signature, `alg` pinned, `exp`, `aud`, `iss`.
- [ ] Session rotated on login and privilege change; invalidated on logout and password change.

### Access control (A01; CWE-862, CWE-863, CWE-639, CWE-284)
- [ ] Each new route has authentication and an authorization decision.
- [ ] Objects fetched by id are scoped to the caller or tenant in the query, not filtered afterwards.
- [ ] Admin functions check role server-side; UI hiding is not a control.
- [ ] Mass assignment blocked: request bodies bound to explicit DTOs or allowlists.
- [ ] CSRF protection on cookie-authenticated state-changing requests (CWE-352).

### Misconfiguration (A02; CWE-16, CWE-942, CWE-1004)
- [ ] Security headers: CSP, HSTS, `X-Content-Type-Options: nosniff`, frame protection (`frame-ancestors` or `X-Frame-Options`).
- [ ] CORS origins allowlisted; never reflect `Origin` with `credentials: true`; never `*` with credentials.
- [ ] Debug modes, admin consoles, directory listings and default credentials off in production config.
- [ ] Cloud and IaC: no public buckets, no `0.0.0.0/0` on admin ports, least-privilege IAM.

### Sensitive data (A04, A01; CWE-200, CWE-359, CWE-532, CWE-312)
- [ ] API responses use explicit field allowlists; whole ORM objects not serialised.
- [ ] PII and secrets not logged; logs not shipped with tokens in URLs.
- [ ] Sensitive data at rest encrypted where required; keys not stored beside the data.
- [ ] Modern algorithms: no MD5/SHA-1 for security, no ECB, no static IVs, no `Math.random()`/`random` for tokens.

### SSRF (CWE-918)
- [ ] Server-side fetches of user-influenced URLs allowlist scheme and host.
- [ ] Every resolved address checked; loopback, link-local (`169.254.169.254` cloud metadata), private, unique-local and IPv4-mapped IPv6 rejected.
- [ ] Redirects disabled or each hop re-validated.
- [ ] TOCTOU: validating the hostname then letting the HTTP client resolve again leaves a DNS-rebinding gap. The robust fix checks the IP at connect time (custom dialer or resolver hook) or connects to the pinned, already-validated IP.

### Input validation
- [ ] Schemas at the boundary (Zod, Pydantic, Bean Validation, JSON Schema, struct tags with a validator) with length and range limits; reject unknown fields where mass assignment is a risk.
- [ ] Validation happens server-side, after decoding and normalisation.

### File handling (CWE-434, CWE-22)
- [ ] Upload type checked by content (magic bytes), not extension or client `Content-Type` alone; size capped.
- [ ] Stored outside the web root under a generated name; served with `Content-Disposition: attachment` and `nosniff`.
- [ ] Archive extraction rejects entries that escape the target (zip slip), symlinks and excessive expansion.
- [ ] Download-by-name resolves and confines the path (see section 4).

### Rate limiting and resources (CWE-770, CWE-400)
- [ ] Limits on auth, signup, password reset, expensive search, export and paid third-party calls.
- [ ] Pagination capped server-side; request body size and decompression limited; timeouts on outbound calls.

### Error handling and logging (A09, A10; CWE-209, CWE-117, CWE-755)
- [ ] Errors fail closed: an exception in an auth or authorization check denies.
- [ ] Generic messages to clients; details to logs.
- [ ] Security events (login failure, permission denied, privilege change) logged with actor, without secrets; log lines strip CR/LF from user input.

### Secrets (CWE-798)
- [ ] No literal credentials; `.env`, keys and credential files gitignored; `.env.example` holds placeholders only.
- [ ] No insecure fallback defaults for secrets.
- [ ] A committed secret is rotated, not just deleted. See `secrets-and-supply-chain.md` for reporting rules (file, line, type; never the value).

### AI and LLM features (see `llm-and-api.md`)
- [ ] Model output treated as untrusted input at every sink (LLM05).
- [ ] Permissions enforced in code at the tool boundary, not in the prompt (LLM01, LLM06).
- [ ] No secrets, other tenants' data or authorization rules in prompts (LLM02, LLM07).
- [ ] Retrieval filtered per tenant (LLM08); token, rate and loop limits (LLM10).

### CI and supply chain (see `gha-hardening.md`, `secrets-and-supply-chain.md`)
- [ ] One authoritative lockfile per install root; CI uses frozen install.
- [ ] Dependency install scripts blocked unless explicitly approved; new dependencies reviewed.
- [ ] Workflows: no untrusted checkout under `pull_request_target`, no `${{ }}` of event data in `run:`, actions pinned by SHA, minimal `permissions:`.

---

## 4. BAD / GOOD patterns by language

These show the shape to look for in a diff. They are illustrations, not drop-in fixes; check the framework's own guidance via `cheat-sheets.md`.

### SQL injection (CWE-89)

```python
# BAD
cur.execute(f"SELECT * FROM users WHERE email = '{email}'")
# GOOD (DB-API placeholder style depends on the driver: %s, ?, :name)
cur.execute("SELECT * FROM users WHERE email = %s", (email,))
```

```ts
// BAD
await db.query(`SELECT * FROM users WHERE id = '${id}'`);
// GOOD
await db.query("SELECT * FROM users WHERE id = $1", [id]);
```

```go
// BAD
db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", id))
// GOOD (placeholder is driver-specific: $1 for pgx/lib/pq, ? for MySQL/SQLite)
db.QueryContext(ctx, "SELECT * FROM users WHERE id = $1", id)
```

```java
// BAD
stmt.executeQuery("SELECT * FROM users WHERE id = '" + id + "'");
// GOOD
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
ps.setString(1, id);
```

ORM escape hatches are the same sink: Django `raw()`/`extra()`, SQLAlchemy `text()` with f-strings, Sequelize `literal`, Prisma `$queryRawUnsafe`, GORM `Where(fmt.Sprintf(...))`, JPA `createQuery` with concatenation.

### Command execution (CWE-78, CWE-88)

```python
# BAD
subprocess.run(f"git log {branch}", shell=True)
# GOOD
subprocess.run(["git", "log", "--", branch], check=True)
```

```ts
// BAD
exec(`convert ${file} out.png`);
// GOOD
execFile("convert", ["--", file, "out.png"]);
```

```go
// BAD
exec.Command("sh", "-c", "tar xf "+name)
// GOOD
exec.CommandContext(ctx, "tar", "xf", "--", name)
```

```java
// BAD
Runtime.getRuntime().exec("ping " + host);
// GOOD
new ProcessBuilder("ping", "-c", "1", "--", host).start();
```

Argument arrays stop shell metacharacters, not option injection: a value starting with `-` can still be read as a flag, hence `--` (when the program supports it) or validation.

### Deserialization (CWE-502)

```python
# BAD
obj = pickle.loads(request.body)
cfg = yaml.load(text, Loader=yaml.Loader)
# GOOD
obj = json.loads(request.body)
cfg = yaml.safe_load(text)
```

```ts
// BAD: libraries that revive functions or classes (node-serialize, funcster), or eval on JSON-ish text
const obj = serialize.unserialize(req.body.data);
// GOOD
const obj = Schema.parse(JSON.parse(req.body.data));
```

```go
// Go has no common gadget-chain deserializer; the risk is unbounded or loosely typed decoding.
// BAD
json.NewDecoder(r.Body).Decode(&anyMap)
// GOOD
dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20))
dec.DisallowUnknownFields()
err := dec.Decode(&req) // concrete struct
```

```java
// BAD
Object o = new ObjectInputStream(in).readObject();
mapper.activateDefaultTyping(ptv, ObjectMapper.DefaultTyping.EVERYTHING);
// GOOD
MyDto dto = mapper.readValue(in, MyDto.class); // no default typing
// If Java serialization is unavoidable, set an allowlisting ObjectInputFilter.
```

### Path traversal (CWE-22)

```python
# BAD
open(os.path.join(BASE, name))
# GOOD
p = (BASE / name).resolve()
if not p.is_relative_to(BASE.resolve()):
    raise PermissionError
```

```ts
// BAD
fs.readFile(path.join(BASE, req.params.name));
// GOOD
const p = path.resolve(BASE, req.params.name);
if (!p.startsWith(path.resolve(BASE) + path.sep)) throw new Error("forbidden");
```

```go
// BAD
os.Open(filepath.Join(base, name))
// GOOD (Go 1.24+): os.Root confines all access, including symlinks
root, _ := os.OpenRoot(base)
f, err := root.Open(name)
// Older Go: reject unless filepath.IsLocal(name)
```

```java
// BAD
Files.readAllBytes(Paths.get(BASE, name));
// GOOD
Path base = Paths.get(BASE).toRealPath();
Path p = base.resolve(name).normalize();
if (!p.startsWith(base)) throw new SecurityException();
```

Prefix checks without a trailing separator (`/data/app` vs `/data/app-secrets`) and checks done before URL-decoding are common bypasses.

### SSRF (CWE-918)

```python
# BAD
requests.get(user_url)
# GOOD (still subject to the TOCTOU caveat in section 3 because requests resolves again)
u = urlparse(user_url)
if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
    raise ValueError
for info in socket.getaddrinfo(u.hostname, 443):
    if not ipaddress.ip_address(info[4][0]).is_global:
        raise ValueError
requests.get(user_url, allow_redirects=False, timeout=5)
```

```ts
// BAD
await fetch(req.body.webhookUrl);
// GOOD: allowlist host, resolve all records, reject non-unicast, forbid redirects
const url = new URL(req.body.webhookUrl);
if (url.protocol !== "https:" || !ALLOWED_HOSTS.has(url.hostname)) throw new Error("blocked");
const addrs = await lookup(url.hostname, { all: true });
if (addrs.some((a) => ipaddr.parse(a.address).range() !== "unicast")) throw new Error("blocked");
await fetch(url, { redirect: "error" });
// For high-risk surfaces use a filtering agent that checks at connect time.
```

```go
// GOOD: check the IP at connect time, which closes the DNS-rebinding gap
dialer := &net.Dialer{Control: func(_, address string, _ syscall.RawConn) error {
    host, _, _ := net.SplitHostPort(address)
    ip := net.ParseIP(host)
    if ip == nil || ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsUnspecified() {
        return errors.New("blocked address")
    }
    return nil
}}
client := &http.Client{
    Transport:     &http.Transport{DialContext: dialer.DialContext},
    CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
    Timeout:       5 * time.Second,
}
```

```java
// BAD
new URL(userUrl).openStream();
// GOOD: allowlist host, resolve, reject site-local/loopback/link-local/any-local, no redirects
InetAddress[] addrs = InetAddress.getAllByName(uri.getHost());
for (InetAddress a : addrs) {
    if (a.isLoopbackAddress() || a.isSiteLocalAddress() || a.isLinkLocalAddress() || a.isAnyLocalAddress())
        throw new SecurityException("blocked");
}
HttpClient client = HttpClient.newBuilder().followRedirects(HttpClient.Redirect.NEVER).build();
// Note: isSiteLocalAddress does not cover IPv6 unique-local (fc00::/7); check it explicitly.
```

---

## 5. Package-manager matrix

First find the install boundary: the workspace root that owns the lockfile (or an independent nested project outside that workspace). Corroborate the manager from `packageManager`, the lockfile and CI; competing lockfiles at one root are themselves a finding to raise. Then use the matching row. "Scripts" means dependency code that runs at install or build time.

| Manager | Lockfile | Frozen install | Disable or gate install scripts | Native audit |
|---|---|---|---|---|
| npm | `package-lock.json` | `npm ci` | `npm ci --ignore-scripts`, or `ignore-scripts=true` in `.npmrc` | `npm audit`; `npm audit signatures` |
| pnpm | `pnpm-lock.yaml` | `pnpm install --frozen-lockfile` (default in CI) | v10+ skips dependency build scripts unless allowlisted; check the settings page for your version's key (`allowBuilds`, `strictDepBuilds`) | `pnpm audit` |
| Yarn (Berry) | `yarn.lock` | `yarn install --immutable` | `enableScripts: false` in `.yarnrc.yml` | `yarn npm audit` |
| Yarn (classic 1.x) | `yarn.lock` | `yarn install --frozen-lockfile` | `--ignore-scripts` | `yarn audit` |
| Bun | `bun.lock` (older `bun.lockb`) | `bun install --frozen-lockfile` | dependency lifecycle scripts run only for `trustedDependencies`; `--ignore-scripts` | `bun audit` (recent releases) |
| pip | `requirements.txt` with hashes | `pip install --require-hashes -r requirements.txt` | `--only-binary :all:` avoids building sdists (which runs their build code) | none native; `pip-audit` |
| uv | `uv.lock` | `uv sync --locked` (or `--frozen`) | `--no-build` refuses to build sdists | none assumed; `pip-audit` or OSV-Scanner |
| Poetry | `poetry.lock` | `poetry check --lock` then `poetry install` (`poetry sync` in 2.x) | `installer.only-binary` config | none native; `pip-audit` or OSV-Scanner |
| Cargo | `Cargo.lock` | `cargo build --locked` | cannot disable `build.rs` or proc macros; review them | none native; `cargo audit`, `cargo deny` |
| Go | `go.sum` | default `-mod=readonly`; `go mod verify` | no install hooks; `go generate` never runs on build | `govulncheck` |
| Maven | none native; exact versions in `pom.xml` | avoid version ranges and `SNAPSHOT`; `--strict-checksums` | plugins execute during the build; pin plugin versions | none native; OWASP Dependency-Check |
| Gradle | `gradle.lockfile` (dependency locking, `--write-locks`) | locking plus `gradle/verification-metadata.xml` | plugins and build scripts execute; pin plugin versions | none native; OWASP Dependency-Check |

Docs: npm ci <https://docs.npmjs.com/cli/v11/commands/npm-ci/>, npm install <https://docs.npmjs.com/cli/v11/commands/npm-install/>, npm audit <https://docs.npmjs.com/cli/v11/commands/npm-audit/>, pnpm settings <https://pnpm.io/settings>, Yarn config <https://yarnpkg.com/configuration/yarnrc>, Bun install <https://bun.sh/docs/pm/cli/install>, pip install <https://pip.pypa.io/en/stable/cli/pip_install/>, uv sync <https://docs.astral.sh/uv/concepts/projects/sync/>, Poetry CLI <https://python-poetry.org/docs/cli/>, Go vulnerability management <https://go.dev/doc/security/vuln/>, Gradle verification <https://docs.gradle.org/current/userguide/dependency_verification.html>.

Rules:
- Never run forced remediation (`npm audit fix --force` or equivalent) as part of a review; it can cross declared ranges. Recommend the specific bump.
- Do not install a project's dependencies with scripts enabled just to scan it. Use lockfile-only scanners (OSV-Scanner, `npm audit` reads the lockfile) where possible.
- An audit only finds known advisories; it does not detect a new malicious or typosquatted package.

### Dependency audit triage

```
Audit reports an advisory
├── Is the advisory's version actually resolved in the lockfile?    no  -> rejected
├── Runtime, build/CI, or dev-only?                                 dev-only and not in CI with secrets -> note
├── Is the vulnerable function reachable from this code?            no  -> needs_validation or note
├── In CISA KEV, or high EPSS?                                      yes -> raise severity
└── Fix available in range?  yes -> recommend the bump
                             no  -> workaround, replace, or accept with a review date
```

---

## 6. Rationalizations to reject

| Rationalization | Reality |
|---|---|
| "It's an internal tool" | Internal tools get compromised; attackers target the weakest link. |
| "We'll add security later" | Retrofitting is much harder; flag it now. |
| "No one would try that" | Automated scanners will. Obscurity is not a control. |
| "The framework handles it" | Only if it is used correctly; check the escape hatches. |
| "It's just a prototype" | Prototypes ship. |
| "It's only LLM output" | That text can be SQL, a script tag or a shell command. |
| "The audit passed" | Audits match known advisories, not new malicious packages or install scripts. |
| "The scanner flagged it, so it's a finding" | A scanner hit is a lead. Apply the six-element test. |
| "The scanner didn't flag it, so it's fine" | Scanners miss authorization and business-logic flaws entirely. |

## 7. Red flags (stop and look closer)

- User input reaching queries, shells, templates, HTML, file paths or URL fetches.
- Secrets in source, history, CI config or images.
- Routes without authentication or authorization; object lookups by id with no owner scope.
- Wildcard CORS with credentials; disabled CSRF or TLS verification.
- No rate limiting on auth endpoints.
- Stack traces returned to clients; fail-open `catch` blocks around security checks.
- Competing lockfiles, non-frozen CI installs, blanket-approved install scripts, unpinned actions.
- Model output reaching a query, the DOM, a shell or `eval`; secrets or other tenants' data in prompts.

## 8. Verification before reporting

- [ ] Each finding names all six elements and cites a specific file and line from the diff.
- [ ] `rule` is a CWE (or `LLMxx`, `APIx`, advisory id); ASVS ids only in rationale or references.
- [ ] Secrets reported by file, line and type only.
- [ ] Dependency findings checked for resolved version and reachability.
- [ ] Workflow changes checked against `gha-hardening.md`.
- [ ] Every reference link is https and points at the specific category or cheat sheet.
