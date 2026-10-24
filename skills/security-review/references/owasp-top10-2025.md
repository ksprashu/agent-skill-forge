Read this when threat-modelling the change (step 1) and during manual review (step 4): it maps each OWASP Top 10:2025 category to the CWEs to cite and the diff patterns to look for.

# OWASP Top 10:2025, for diff review

Source: <https://top10.owasp.org/2025/> (the old `owasp.org/Top10/2025/` path redirects here). Each category page lists every mapped CWE; the CWEs below are the representative ones worth citing in a finding's `rule` field. The Top 10 category itself is not a valid `rule` value in the findings schema; cite the most specific CWE that fits, and put the category page in `references[]`.

Ordering changed from 2021: Security Misconfiguration rose to A02, Software Supply Chain Failures (an expansion of "Vulnerable and Outdated Components") is new at A03, SSRF folded into A01, and Mishandling of Exceptional Conditions is new at A10.

A scanner hit or a pattern below is a lead. It becomes a finding only after the six-element test in SKILL.md (step 3).

---

## A01:2025 Broken Access Control

<https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/>

CWEs to cite: CWE-862 Missing Authorization, CWE-863 Incorrect Authorization, CWE-639 Authorization Bypass Through User-Controlled Key (IDOR), CWE-284 Improper Access Control, CWE-22 Path Traversal, CWE-352 CSRF, CWE-918 SSRF, CWE-601 Open Redirect, CWE-200 Exposure of Sensitive Information, CWE-732 Incorrect Permission Assignment, CWE-1275 Cookie with Improper SameSite.

What to look for in a diff:
- A new route, handler, RPC method or GraphQL resolver with no authorization decorator, middleware or policy call, when its siblings have one.
- A lookup by an id taken from the request (`findById(req.params.id)`, `get_object_or_404(Model, pk=pk)`) with no owner or tenant predicate.
- Authorization done on the client only (hidden buttons, disabled fields) with no server check.
- File paths built from request input (`open(base + name)`, `path.join(root, req.query.f)`) without canonicalising and checking the prefix.
- Server-side fetch of a user-supplied URL (webhooks, image proxy, "import from URL") without scheme, host and resolved-IP checks.
- Redirects to `next`, `returnTo` or `url` parameters without an allowlist.
- State-changing GET endpoints, or cookie-authenticated POSTs without a CSRF token or `SameSite`.
- `chmod 777`, world-writable temp files, `0.0.0.0/0` in a security group, `Access-Control-Allow-Origin: *` with credentials.

## A02:2025 Security Misconfiguration

<https://top10.owasp.org/2025/A02_2025-Security_Misconfiguration/>

CWEs to cite: CWE-16 Configuration, CWE-611 XXE, CWE-776 XML Entity Expansion, CWE-489 Active Debug Code, CWE-614 Cookie without Secure, CWE-1004 Cookie without HttpOnly, CWE-942 Permissive Cross-domain Policy, CWE-260 Password in Configuration File, CWE-526 Sensitive Information in Environment Variables.

What to look for in a diff:
- `DEBUG = True`, `app.run(debug=True)`, verbose error pages or stack traces enabled outside a dev profile.
- XML parsers created without disabling DTDs or external entities (`DocumentBuilderFactory` without `disallow-doctype-decl`, `lxml.etree.XMLParser(resolve_entities=True)`).
- CORS set to reflect any origin, or `*` combined with `credentials: true`.
- Session cookies missing `Secure`, `HttpOnly` or `SameSite`.
- Security headers removed or loosened (CSP `unsafe-inline`/`unsafe-eval` added, HSTS dropped).
- Default credentials, sample apps, admin consoles or actuator/debug endpoints exposed.
- Dockerfiles running as root, Kubernetes manifests with `privileged: true`, `hostPath`, or no resource limits (trivy config flags these).

## A03:2025 Software Supply Chain Failures

<https://top10.owasp.org/2025/A03_2025-Software_Supply_Chain_Failures/>

CWEs to cite: CWE-1395 Dependency on Vulnerable Third-Party Component, CWE-1104 Use of Unmaintained Third-Party Components, CWE-1357 Reliance on Insufficiently Trustworthy Component, CWE-1329 Reliance on Component That is Not Updateable. For a known vulnerable version, cite the advisory itself (`CVE-...` or `GHSA-...`) rather than the CWE.

What to look for in a diff:
- New dependencies: name close to a popular package, very new, single maintainer, no repository link, or an install script.
- Lockfile churn not explained by the manifest change, resolved URLs pointing at an unexpected registry, or integrity hashes changing for an unchanged version.
- Version ranges widened (`^`, `*`, `latest`) or the lockfile deleted.
- CI actions referenced by tag or branch instead of a full commit SHA; `curl | sh` in build scripts.
- Read `references/secrets-and-supply-chain.md` for the full checklist.

## A04:2025 Cryptographic Failures

<https://top10.owasp.org/2025/A04_2025-Cryptographic_Failures/>

CWEs to cite: CWE-327 Broken or Risky Algorithm, CWE-328 Reversible One-Way Hash, CWE-326 Inadequate Encryption Strength, CWE-330 / CWE-338 Insufficiently Random Values / Weak PRNG, CWE-321 Hard-coded Cryptographic Key, CWE-319 Cleartext Transmission, CWE-347 Improper Verification of Cryptographic Signature, CWE-916 Password Hash With Insufficient Effort, CWE-329 Non-random IV with CBC.

What to look for in a diff:
- MD5 or SHA-1 used for passwords, signatures or integrity; unsalted or fast hashes (`sha256(password)`) for password storage.
- `Math.random()`, `random.random()`, `java.util.Random` or `math/rand` used for tokens, ids, nonces or reset codes.
- ECB mode, static IVs, reused nonces with GCM, keys or IVs as string literals.
- TLS verification disabled: `verify=False`, `InsecureSkipVerify: true`, `rejectUnauthorized: false`, trust-all `TrustManager`.
- JWT libraries configured to accept `alg: none` or to skip signature verification.
- `http://` endpoints for anything carrying credentials or personal data.

## A05:2025 Injection

<https://top10.owasp.org/2025/A05_2025-Injection/>

CWEs to cite: CWE-89 SQL Injection, CWE-78 OS Command Injection, CWE-77 Command Injection, CWE-88 Argument Injection, CWE-79 XSS, CWE-94 Code Injection, CWE-95 Eval Injection, CWE-90 LDAP Injection, CWE-643 XPath Injection, CWE-917 Expression Language Injection, CWE-113 HTTP Response Splitting, CWE-564 Hibernate SQL Injection. For server-side template injection, cite CWE-94.

What to look for in a diff:
- SQL, NoSQL, LDAP or XPath built by string formatting or concatenation (`f"... {x}"`, template literals, `"+ id +"`, `String.format`, `fmt.Sprintf`).
- ORM escape hatches with interpolated input: `.raw()`, `.extra()`, `text(f"...")`, `$queryRawUnsafe`, `createNativeQuery(... + ...)`.
- `subprocess` with `shell=True`, `os.system`, `exec.Command("sh", "-c", ...)`, `Runtime.exec(String)`, `child_process.exec` with request data; user-controlled arguments that can start with `-`.
- `eval`, `new Function`, `exec`, `pickle`, template rendering of user-supplied template strings.
- HTML sinks: `innerHTML`, `dangerouslySetInnerHTML`, `v-html`, `|safe`, `mark_safe`, `Html.Raw`, `template.HTML(...)` with request data.
- Model (LLM) output flowing into any of the sinks above (also LLM05; see `references/llm-and-api.md`).

## A06:2025 Insecure Design

<https://top10.owasp.org/2025/A06_2025-Insecure_Design/>

CWEs to cite: CWE-434 Unrestricted Upload of Dangerous File Type, CWE-269 Improper Privilege Management, CWE-501 Trust Boundary Violation, CWE-602 Client-Side Enforcement of Server-Side Security, CWE-807 Reliance on Untrusted Inputs in a Security Decision, CWE-841 Improper Enforcement of Behavioral Workflow, CWE-362 Race Condition, CWE-799 Improper Control of Interaction Frequency, CWE-522 Insufficiently Protected Credentials, CWE-656 Security Through Obscurity.

What to look for in a diff:
- Business flows that can be skipped or replayed: checkout without payment state check, coupon reuse, approval steps enforced only in the UI.
- Check-then-act on balances, quotas or inventory without a transaction or lock (TOCTOU).
- Trust decisions made on headers the client controls (`X-Forwarded-For`, `X-User-Id`, `Referer`).
- File uploads stored under the web root, keyed by the client's filename, or validated only by extension.
- No rate limit or anti-automation on login, signup, password reset, OTP verification or expensive endpoints.
- Missing abuse cases: a feature that clearly needs a threat model (multi-tenant data, money movement, admin actions) arriving with no tests for misuse.

## A07:2025 Authentication Failures

<https://top10.owasp.org/2025/A07_2025-Authentication_Failures/>

CWEs to cite: CWE-287 Improper Authentication, CWE-306 Missing Authentication for Critical Function, CWE-798 Hard-coded Credentials, CWE-307 Excessive Authentication Attempts, CWE-384 Session Fixation, CWE-613 Insufficient Session Expiration, CWE-640 Weak Password Recovery, CWE-295 Improper Certificate Validation, CWE-1392 Default Credentials, CWE-521 Weak Password Requirements.

What to look for in a diff:
- An endpoint that performs a privileged action with no authentication middleware.
- Credentials, API keys or tokens in source, config or test fixtures that look real (gitleaks leads land here and in A04).
- Session id not rotated on login or privilege change; logout that does not invalidate the server-side session.
- Password reset tokens that are guessable, long-lived, not single-use, or leaked in URLs or logs.
- Username enumeration through different error messages or timings.
- Comparing secrets with `==` instead of a constant-time comparison (`hmac.compare_digest`, `crypto.timingSafeEqual`, `subtle.ConstantTimeCompare`, `MessageDigest.isEqual`).

## A08:2025 Software or Data Integrity Failures

<https://top10.owasp.org/2025/A08_2025-Software_or_Data_Integrity_Failures/>

CWEs to cite: CWE-502 Deserialization of Untrusted Data, CWE-494 Download of Code Without Integrity Check, CWE-829 Inclusion of Functionality from Untrusted Control Sphere, CWE-915 Mass Assignment, CWE-345 Insufficient Verification of Data Authenticity, CWE-565 Reliance on Cookies without Integrity Checking, CWE-426 Untrusted Search Path.

What to look for in a diff:
- `pickle.loads`, `yaml.load` without `SafeLoader`, `ObjectInputStream.readObject`, `BinaryFormatter`, `Marshal.load`, `unserialize` on data from a request, queue, cache or file a user can write.
- Request bodies bound straight to models (`Model(**request.json)`, `Object.assign(user, req.body)`, Spring binding without an allowlist) so a client can set `is_admin` or `owner_id`.
- Scripts loaded from third-party CDNs without Subresource Integrity; downloads executed without a checksum or signature check.
- Auto-update or plugin mechanisms that fetch code without verifying a signature.
- Webhooks accepted without verifying the sender's HMAC signature.

## A09:2025 Security Logging and Alerting Failures

<https://top10.owasp.org/2025/A09_2025-Security_Logging_and_Alerting_Failures/>

CWEs to cite: CWE-778 Insufficient Logging, CWE-117 Improper Output Neutralization for Logs, CWE-532 Sensitive Information in Log File, CWE-223 Omission of Security-relevant Information.

What to look for in a diff:
- Tokens, passwords, full card numbers, session cookies or whole request bodies written to logs or telemetry.
- User input written into log lines without neutralising newlines (log forging).
- Authentication failures, authorization denials and admin actions not logged at all.
- Exceptions swallowed in security code so failures leave no trace.

## A10:2025 Mishandling of Exceptional Conditions

<https://top10.owasp.org/2025/A10_2025-Mishandling_of_Exceptional_Conditions/>

CWEs to cite: CWE-636 Not Failing Securely (Failing Open), CWE-209 Error Message Containing Sensitive Information, CWE-754 Improper Check for Unusual Conditions, CWE-755 Improper Handling of Exceptional Conditions, CWE-252 Unchecked Return Value, CWE-476 NULL Pointer Dereference, CWE-396 Catch for Generic Exception, CWE-248 Uncaught Exception.

What to look for in a diff:
- Authorization or signature checks wrapped in `try/except: pass` (or `catch (Exception e) {}`) so an error grants access.
- Feature flags, policy lookups or remote checks that default to "allow" when the call times out or fails.
- Ignored error returns in Go (`_ = verify(...)`), unchecked `err` before using the result.
- Stack traces, SQL errors or internal paths returned in API responses.
- Partial failures that leave state inconsistent (money debited, order not created) with no rollback.

---

## Quick STRIDE to Top 10 bridge

| STRIDE threat | Usual Top 10 home |
|---|---|
| Spoofing | A07 Authentication Failures |
| Tampering | A05 Injection, A08 Integrity Failures |
| Repudiation | A09 Logging and Alerting Failures |
| Information disclosure | A01 Access Control, A04 Crypto, A10 error leakage |
| Denial of service | A06 Insecure Design (no limits), A10 |
| Elevation of privilege | A01 Access Control, A05 Injection |
