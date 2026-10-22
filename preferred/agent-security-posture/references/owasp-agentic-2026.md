# OWASP Top 10 for Agentic Applications 2026 — Quick Reference

Source: OWASP Gen AI Security Project (December 2025 / Version 2026). Distilled for agent use. Always cross-check primary sources.

| ID | Risk | Core Description | Key Mitigations for Agents |
|----|------|------------------|----------------------------|
| ASI01 | Agent Goal Hijack | Attacker redirects agent objectives via injected instructions in content, tools, or memory. | Treat all external data as untrusted. Validate intent/goal integrity. Use policy engines that block out-of-scope tool calls. Input guardrails. |
| ASI02 | Tool Misuse & Exploitation | Legitimate tools used harmfully (wrong params, destructive side effects, exfil). | Per-tool policies, argument validation/allowlists, tool integrity checks, confirmation for high-risk. |
| ASI03 | Identity & Privilege Abuse | Agent runs with excessive privileges or attacker elevates effective identity. | Least privilege, scoped short-lived credentials, distinct agent identity, ABAC, no standing admin. |
| ASI04 | Agentic Supply Chain Vulnerabilities | Compromised tools, MCP servers, skills, models, or deps (poisoned descriptions, typosquats). | Pin tools/MCP by fingerprint/contract, AI-BOM/SBOM, verify provenance, sandbox. |
| ASI05 | Unexpected Code Execution | Agent tricked into running arbitrary code (sandbox escape, eval, payload to interpreter). | Sandboxing, code-execution detection, hard separation of reasoning and execution, no raw eval. |
| ASI06 | Memory & Context Poisoning | False data planted in memory, RAG, or context that persists and influences later decisions. | Validate memory writes, provenance tracking, trust scoring on retrieval, TTL, integrity checks. |
| ASI07 | Insecure Inter-Agent Communication | Compromised agent injects into peers via unsecured channels. | Message signing/validation, treat inter-agent as untrusted, gateway policies, allowed identities. |
| ASI08 | Cascading Failures | Failure or compromise spreads and amplifies across agents/tools. | Circuit breakers, fail-closed on high-risk, decision boundaries, rate limits, isolation. |
| ASI09 | Human-Agent Trust Exploitation | Agent exploits human trust by burying harmful actions or misrepresenting them. | Full context on approval prompts, progressive disclosure, avoid rubber-stamping, confidence signals. |
| ASI10 | Rogue Agents | Agents operating outside authorized scope or unregistered ones acting. | Discovery of all agents, monitoring/behavior baselines, kill switches, shadow mode for unknowns. |

## Companion Guidance

- Combine with OWASP LLM Top 10 (Prompt Injection remains #1, Excessive Agency elevated, etc.).
- OWASP Secure Coding with AI Cheat Sheet: hallucinated deps, MCP/tool security, agent sandboxing, human accountability.
- Prefer primary: https://genai.owasp.org/

When reviewing code or agent configs, map changes to the relevant ASI/LLM items and document residual risk.
