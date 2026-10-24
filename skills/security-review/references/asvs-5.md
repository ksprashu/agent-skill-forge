Read this during manual review (step 4) when a finding should cite a verification requirement, or when deciding whether a missing control is an L1 or an L2 expectation.

# OWASP ASVS 5.0, chapter map for code review

Sources:
- Project site: <https://asvs.owasp.org/>
- Chapters at the 5.0.0 tag: <https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en>
- Levels and citation format: <https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x03-What-is-the-ASVS.md>

ASVS is a verification standard, not a vulnerability list. Use it to say *which control is missing*, then decide with the six-element test (SKILL.md, step 3) whether that absence is an exploitable finding or only a hardening note. A missing ASVS requirement with no reachable boundary violation is not a vulnerability.

## How to cite a requirement

Requirement ids are `<chapter>.<section>.<requirement>`. Because ids move between versions, cite with the version prefix: `v5.0.0-1.2.5` (lowercase `v`). Example from the standard: `v5.0.0-1.2.5` is "Verify that the application protects against OS command injection and that operating system calls use parameterized OS queries or use contextual command line output encoding."

The findings schema's `rule` field does not accept ASVS ids. Put the CWE in `rule` and the ASVS requirement in the `rationale` or as a `references[]` entry pointing at the chapter file, e.g. `{"title": "ASVS v5.0.0-1.2.5", "url": "https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x10-V1-Encoding-and-Sanitization.md"}`.

## Levels: when to cite L1 vs L2

From the standard (0x03, "Application Security Verification Levels"):

- **L1** (about 20% of requirements): the minimum. "Critical or basic, first-layer of defense requirements for preventing common attacks that do not require other vulnerabilities or preconditions to be exploitable."
- **L2** (about a further 50%; L2 compliance means all L1 + L2, about 70%): "Most applications should be striving to achieve this level." Less common attacks, or more complicated protections against common ones; may need preconditions.
- **L3** (the final ~30%): defence-in-depth and hard-to-implement controls, for the highest-assurance applications.

Rules of thumb for review:
- A missing **L1** control on reachable code (parameterised queries, output encoding, authorization on every request, no hard-coded secrets) is usually a confirmed finding if the six elements can be named.
- A missing **L2** control is a finding when the application handles sensitive data, authentication, money or multiple tenants, which is most production systems. Otherwise note it.
- A missing **L3** control is almost always a hardening note, not a finding: by definition it is defence in depth.
- Documentation requirements (the `x.1` sections, e.g. V2.1, V8.1) are not code findings. Mention them in the summary only if the absence blocked the review.

## Chapter map (ASVS 5.0.0)

| Chapter | Sections | Typical diff triggers |
|---|---|---|
| V1 Encoding and Sanitization | V1.1 Architecture, V1.2 Injection Prevention, V1.3 Sanitization, V1.4 Memory, String, and Unmanaged Code, V1.5 Safe Deserialization | SQL/command/template building, HTML sinks, `pickle`/`ObjectInputStream`, C/C++ buffers |
| V2 Validation and Business Logic | V2.1 Documentation, V2.2 Input Validation, V2.3 Business Logic Security, V2.4 Anti-automation | new request schemas, multi-step flows, coupons/limits, signup/login throttling |
| V3 Web Frontend Security | V3.1 Documentation, V3.2 Unintended Content Interpretation, V3.3 Cookie Setup, V3.4 Browser Security Mechanism Headers, V3.5 Browser Origin Separation, V3.6 External Resource Integrity, V3.7 Other Browser Security Considerations | cookies, CSP/HSTS headers, CORS, postMessage, CDN scripts without SRI |
| V4 API and Web Service | V4.1 Generic Web Service Security, V4.2 HTTP Message Structure Validation, V4.3 GraphQL, V4.4 WebSocket | new REST/GraphQL/WebSocket endpoints, content-type handling, query depth limits |
| V5 File Handling | V5.1 Documentation, V5.2 File Upload and Content, V5.3 File Storage, V5.4 File Download | upload handlers, archive extraction, download-by-name endpoints |
| V6 Authentication | V6.1 Documentation, V6.2 Password Security, V6.3 General Authentication Security, V6.4 Factor Lifecycle and Recovery, V6.5 General MFA, V6.6 Out-of-Band, V6.7 Cryptographic authentication, V6.8 Authentication with an Identity Provider | login, password reset, MFA, SSO callback code |
| V7 Session Management | V7.1 Documentation, V7.2 Fundamental Session Security, V7.3 Session Timeout, V7.4 Session Termination, V7.5 Defenses Against Session Abuse, V7.6 Federated Re-authentication | session creation/rotation, logout, remember-me |
| V8 Authorization | V8.1 Documentation, V8.2 General Authorization Design, V8.3 Operation Level Authorization, V8.4 Other Authorization Considerations | new routes, object lookups by id, admin actions, tenant filters |
| V9 Self-contained Tokens | V9.1 Token source and integrity, V9.2 Token content | JWT parsing, `alg` handling, audience/issuer/expiry checks |
| V10 OAuth and OIDC | V10.1 Generic, V10.2 OAuth Client, V10.3 Resource Server, V10.4 Authorization Server, V10.5 OIDC Client, V10.6 OpenID Provider, V10.7 Consent Management | redirect URI handling, PKCE, state/nonce, scope checks |
| V11 Cryptography | V11.1 Inventory and Documentation, V11.2 Secure Implementation, V11.3 Encryption Algorithms, V11.4 Hashing, V11.5 Random Values, V11.6 Public Key Cryptography, V11.7 In-Use Data Cryptography | hashing passwords, token generation, cipher modes, key storage |
| V12 Secure Communication | V12.1 General TLS, V12.2 HTTPS with External Facing Services, V12.3 Service to Service | `verify=False`, plain HTTP clients, mTLS config |
| V13 Configuration | V13.1 Documentation, V13.2 Backend Communication Configuration, V13.3 Secret Management, V13.4 Unintended Information Leakage | secrets in code/config, debug modes, exposed `.git` or source maps |
| V14 Data Protection | V14.1 Documentation, V14.2 General Data Protection, V14.3 Client-side Data Protection | PII in responses, logs or localStorage; caching of sensitive pages |
| V15 Secure Coding and Architecture | V15.1 Documentation, V15.2 Security Architecture and Dependencies, V15.3 Defensive Coding, V15.4 Safe Concurrency | new dependencies, mass assignment, type juggling, races |
| V16 Security Logging and Error Handling | V16.1 Documentation, V16.2 General Logging, V16.3 Security Events, V16.4 Log Protection, V16.5 Error Handling | secrets in logs, log injection, fail-open error paths, stack traces to clients |
| V17 WebRTC | V17.1 TURN Server, V17.2 Media, V17.3 Signaling | only if the change touches WebRTC |

Chapter files are `0x10-V1-...` through `0x26-V17-WebRTC.md` in the tag directory above; open the one you cite to copy the exact requirement text and its level.

## Mapping to the Top 10 and CWE

ASVS chapters roughly line up with Top 10:2025 as follows: V1/V2 to A05 Injection and A06 Insecure Design; V6/V7/V9/V10 to A07 Authentication Failures; V8 to A01 Broken Access Control; V11/V12 to A04 Cryptographic Failures; V13 to A02 Misconfiguration; V15.2 to A03 Supply Chain; V16 to A09 and A10. See `references/owasp-top10-2025.md` for the CWEs to put in `rule`.
