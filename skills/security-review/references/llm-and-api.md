Read this during manual review (step 4) when the change calls an LLM, builds an agent or tool, or adds or changes an HTTP/GraphQL API.

# OWASP LLM Top 10 (2025) and API Security Top 10 (2023)

## Rule ids the findings schema accepts

The `rule` field accepts `LLM` plus two digits and `API` plus one or two digits:

- LLM risks: `LLM01` .. `LLM10` (not `LLM1`, not `LLM01:2025`).
- API risks: `API1` .. `API10` (not `API01`, not `API1:2023`).

Prefer a CWE when one captures the root cause exactly (an LLM output reaching `eval` is CWE-94; a BOLA is CWE-639). Use the `LLMxx` / `APIx` id when the risk has no good CWE (prompt injection, excessive agency, unbounded consumption of model tokens) or when the category is the clearer signal to the reader. Agent-specific risks (goal hijack, tool misuse, memory poisoning) use `ASI01`..`ASI10` from the OWASP Agentic Top 10 2026: <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>. If the `agent-security-posture` skill is installed, its `references/owasp-agentic-2026.md` covers those in depth.

---

## OWASP Top 10 for LLM Applications 2025

Index: <https://genai.owasp.org/llm-top-10/>

| Id | Risk | What to look for in a diff | Related CWE |
|---|---|---|---|
| LLM01 | Prompt Injection <https://genai.owasp.org/llmrisk/llm01-prompt-injection/> | Untrusted text (user message, fetched page, email, PDF, tool output) concatenated into a prompt that also grants tools or authority; security decisions delegated to the system prompt ("never reveal X") instead of enforced in code. | none exact; use LLM01 |
| LLM02 | Sensitive Information Disclosure <https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/> | Secrets, other users' records or internal data placed in the context window; model output returned to users without filtering; prompts and completions logged with PII. | CWE-200, CWE-532 |
| LLM03 | Supply Chain <https://genai.owasp.org/llmrisk/llm032025-supply-chain/> | Models, adapters or datasets pulled by name or `latest` from a hub with no pinned revision or hash; `trust_remote_code=True`; model files loaded with `pickle`/`torch.load` without `weights_only=True`. | CWE-494, CWE-502, CWE-829 |
| LLM04 | Data and Model Poisoning <https://genai.owasp.org/llmrisk/llm042025-data-and-model-poisoning/> | Fine-tuning or RAG ingestion from user-writable sources with no provenance or review step. | CWE-345 |
| LLM05 | Improper Output Handling <https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/> | Model output passed to `eval`, SQL, a shell, `innerHTML`, a file path, a URL fetch or a deserializer without validation; markdown rendered with raw HTML or auto-loaded images (exfiltration via image URLs). | CWE-94, CWE-89, CWE-78, CWE-79, CWE-918 |
| LLM06 | Excessive Agency <https://genai.owasp.org/llmrisk/llm062025-excessive-agency/> | Tools with broader scope than the feature needs (write when read suffices, arbitrary shell, arbitrary HTTP); destructive tool calls with no human confirmation; tools running with the service's credentials rather than the end user's. | CWE-250, CWE-269 |
| LLM07 | System Prompt Leakage <https://genai.owasp.org/llmrisk/llm072025-system-prompt-leakage/> | Credentials, internal URLs or authorization rules embedded in the system prompt. The prompt is not a secret store. | CWE-200, CWE-798 |
| LLM08 | Vector and Embedding Weaknesses <https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/> | One shared vector index for all tenants; retrieval queries with no tenant or ACL filter; documents indexed without validation. | CWE-639, CWE-284 |
| LLM09 | Misinformation <https://genai.owasp.org/llmrisk/llm092025-misinformation/> | Model output presented as authoritative in high-stakes flows (medical, legal, financial, code that is auto-merged) with no grounding or human review. Rarely a code finding on its own. | none; use LLM09 |
| LLM10 | Unbounded Consumption <https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/> | No cap on input size, output tokens, tool-loop iterations, recursion depth or per-user request rate; user-controlled `max_tokens`. | CWE-770, CWE-400 |

Review rules for LLM features:
- Treat model output exactly like raw user input at every sink.
- Enforce permissions in code, at the tool boundary, using the end user's identity.
- A prompt injection finding still needs the six elements: who controls the injected text, what tool or data it reaches, and the concrete result. "The model could be tricked" with no reachable tool or data is a note, not a finding.

Fix guidance: LLM Prompt Injection Prevention <https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html>, AI Agent Security <https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html>, RAG Security <https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html>, MCP Security <https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html>.

---

## OWASP API Security Top 10 2023

Index: <https://api-security.owasp.org/editions/2023/en/0x11-t10/>

| Id | Risk | What to look for in a diff | Related CWE |
|---|---|---|---|
| API1 | Broken Object Level Authorization <https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/> | Handler reads an object id from path, query or body and fetches it without checking the caller owns it or shares its tenant. | CWE-639, CWE-862 |
| API2 | Broken Authentication <https://api-security.owasp.org/editions/2023/en/0xa2-broken-authentication/> | Endpoints missing auth middleware; JWTs not verified (signature, `exp`, `aud`, `iss`); API keys in query strings; no lockout on credential endpoints. | CWE-287, CWE-306, CWE-347 |
| API3 | Broken Object Property Level Authorization <https://api-security.owasp.org/editions/2023/en/0xa3-broken-object-property-level-authorization/> | Serialising whole ORM objects (`return user`, `to_dict()`) so hidden fields leak; binding the whole request body so clients can set `role`, `owner_id`, `price` (mass assignment). | CWE-213, CWE-915 |
| API4 | Unrestricted Resource Consumption <https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/> | No pagination cap (`limit` from the client unbounded), no upload size limit, no GraphQL depth/complexity limit, no timeouts, paid third-party calls per request with no rate limit. | CWE-770, CWE-400 |
| API5 | Broken Function Level Authorization <https://api-security.owasp.org/editions/2023/en/0xa5-broken-function-level-authorization/> | Admin or internal endpoints reachable by ordinary users because the role check is missing or only applied in the UI; HTTP method changes (`GET` safe, `DELETE` unchecked). | CWE-285, CWE-862 |
| API6 | Unrestricted Access to Sensitive Business Flows <https://api-security.owasp.org/editions/2023/en/0xa6-unrestricted-access-to-sensitive-business-flows/> | Purchase, signup, voucher, booking or messaging flows with no anti-automation (rate limits, device or account checks). | CWE-799, CWE-841 |
| API7 | Server Side Request Forgery <https://api-security.owasp.org/editions/2023/en/0xa7-server-side-request-forgery/> | Endpoint accepts a URL (webhook, avatar, import) and fetches it server-side without allowlisting scheme and host and rejecting private and metadata addresses after resolution. | CWE-918 |
| API8 | Security Misconfiguration <https://api-security.owasp.org/editions/2023/en/0xa8-security-misconfiguration/> | Permissive CORS, verbose errors, missing TLS, unnecessary HTTP methods enabled, default credentials. | CWE-16, CWE-942, CWE-209 |
| API9 | Improper Inventory Management <https://api-security.owasp.org/editions/2023/en/0xa9-improper-inventory-management/> | New `v2` endpoints added while `v1` stays live without the same controls; debug or beta routes deployed to production; undocumented endpoints. | none exact; use API9 |
| API10 | Unsafe Consumption of APIs <https://api-security.owasp.org/editions/2023/en/0xaa-unsafe-consumption-of-apis/> | Responses from third-party APIs trusted without validation (used in SQL, redirects, HTML); following redirects from partners blindly; no timeouts on outbound calls. | CWE-20, CWE-918 |

Fix guidance: REST Security <https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html>, GraphQL <https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html>, Mass Assignment <https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html>, IDOR Prevention <https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html>.
