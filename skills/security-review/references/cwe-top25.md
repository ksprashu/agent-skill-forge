Read this when triaging scanner leads (step 3) and when emitting findings (step 6): pick the most specific CWE for each finding's `rule` field.

# CWE Top 25 Most Dangerous Software Weaknesses (2025)

Source: <https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html>, fetched 2026-10-24. The 2025 list is the latest published by MITRE as of that date (the landing page <https://cwe.mitre.org/top25/> points to it). Check the landing page for a newer year before citing ranks; the CWE ids themselves do not change.

Methodology: <https://cwe.mitre.org/top25/archive/2025/2025_methodology.html>. KEV-weighted companion list: <https://cwe.mitre.org/top25/archive/2025/2025_kev_list.html>.

| Rank | CWE | Name | Change vs 2024 |
|---:|---|---|---|
| 1 | CWE-79 | Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting') | 0 |
| 2 | CWE-89 | Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection') | +1 |
| 3 | CWE-352 | Cross-Site Request Forgery (CSRF) | +1 |
| 4 | CWE-862 | Missing Authorization | +5 |
| 5 | CWE-787 | Out-of-bounds Write | -3 |
| 6 | CWE-22 | Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal') | -1 |
| 7 | CWE-416 | Use After Free | +1 |
| 8 | CWE-125 | Out-of-bounds Read | -2 |
| 9 | CWE-78 | Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection') | -2 |
| 10 | CWE-94 | Improper Control of Generation of Code ('Code Injection') | +1 |
| 11 | CWE-120 | Buffer Copy without Checking Size of Input ('Classic Buffer Overflow') | new |
| 12 | CWE-434 | Unrestricted Upload of File with Dangerous Type | -2 |
| 13 | CWE-476 | NULL Pointer Dereference | +8 |
| 14 | CWE-121 | Stack-based Buffer Overflow | new |
| 15 | CWE-502 | Deserialization of Untrusted Data | +1 |
| 16 | CWE-122 | Heap-based Buffer Overflow | new |
| 17 | CWE-863 | Incorrect Authorization | +1 |
| 18 | CWE-20 | Improper Input Validation | -6 |
| 19 | CWE-284 | Improper Access Control | new |
| 20 | CWE-200 | Exposure of Sensitive Information to an Unauthorized Actor | -3 |
| 21 | CWE-306 | Missing Authentication for Critical Function | +4 |
| 22 | CWE-918 | Server-Side Request Forgery (SSRF) | -3 |
| 23 | CWE-77 | Improper Neutralization of Special Elements used in a Command ('Command Injection') | -10 |
| 24 | CWE-639 | Authorization Bypass Through User-Controlled Key | +6 |
| 25 | CWE-770 | Allocation of Resources Without Limits or Throttling | +1 |

## Choosing the CWE for a finding

1. **Prefer the most specific base weakness that matches the root cause.** CWE-89 over CWE-74; CWE-639 over CWE-284; CWE-78 over CWE-77 when an OS shell is involved.
2. **Avoid the broad classes as a `rule` unless nothing narrower fits.** CWE-20 (Improper Input Validation), CWE-284 (Improper Access Control) and CWE-200 are on the list partly because they are catch-alls. A reviewer can act on CWE-862 ("no check") or CWE-863 ("wrong check"); "CWE-284" says less.
3. **Name the root cause, not the consequence.** Missing tenant filter that leaks data: CWE-639, not CWE-200. Hard-coded key that lets anyone forge tokens: CWE-321 or CWE-798, not CWE-287.
4. **Scanner-reported CWEs are leads too.** Semgrep rules often carry a CWE in their metadata; confirm it matches what the code actually does before copying it into the finding.
5. **Dependency advisories are cited by advisory id** (`CVE-2024-12345`, `GHSA-xxxx-xxxx-xxxx`), not by CWE, so the reader can look the fix up directly.
6. **Agent, LLM and API risks** may use `ASI01`..`ASI10`, `LLM01`..`LLM10` or `API1`..`API10` when no CWE captures them (for example prompt injection). See `references/llm-and-api.md`.

## Common lead-to-CWE mappings

| Lead | CWE |
|---|---|
| String-built SQL / ORM raw query with input | CWE-89 |
| `shell=True`, `sh -c`, `Runtime.exec(String)` with input | CWE-78 |
| User-controlled argument to a fixed binary (`git`, `curl`, `tar`) starting with `-` | CWE-88 |
| `eval`, `new Function`, template-from-input | CWE-94 / CWE-95 |
| `innerHTML`, `dangerouslySetInnerHTML`, `|safe` | CWE-79 |
| Path join with request input | CWE-22 |
| Fetch of user URL | CWE-918 |
| Route with no auth check | CWE-306 (authn) / CWE-862 (authz) |
| Lookup by id without owner/tenant predicate | CWE-639 |
| `pickle`, `yaml.load`, `ObjectInputStream` on untrusted data | CWE-502 |
| Hard-coded password or API key | CWE-798 (CWE-259 for a password specifically) |
| Hard-coded crypto key | CWE-321 |
| `verify=False`, `InsecureSkipVerify` | CWE-295 |
| MD5/SHA-1 for passwords or signatures | CWE-327 / CWE-328 / CWE-916 |
| `Math.random()` for tokens | CWE-338 |
| Secret in a log line | CWE-532 |
| XML parser with DTDs enabled | CWE-611 |
| Mass assignment from request body | CWE-915 |
| Open redirect | CWE-601 |
| Missing CSRF protection on cookie-authenticated state change | CWE-352 |
| No size/rate limit on an expensive operation | CWE-770 |
| Error handler that fails open | CWE-636 |
| Stack trace or SQL error returned to the client | CWE-209 |

Individual CWE pages follow the pattern `https://cwe.mitre.org/data/definitions/<number>.html`, for example <https://cwe.mitre.org/data/definitions/89.html>; use that page as the finding's reference when no better fix guide exists.
