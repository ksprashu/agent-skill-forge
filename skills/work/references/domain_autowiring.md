# 🔌 Domain Skill Autowiring: Dynamic Capability Injection

One of the key technical advancements over vanilla teamwork is **Domain Skill Autowiring**. Instead of relying on generic subagent knowledge, the Orchestrator dynamically scans the local `skills/` and `preferred/` catalogs in `agent-skill-forge` and injects specialized domain skills directly into subagent prompt briefs.

---

## 1. Skill Mapping Matrix

| Technical Domain | Applicable Core / Preferred Skill | Target Roles | Injected Instructions |
|------------------|-----------------------------------|--------------|------------------------|
| **Database & Schema** | `preferred/api-and-interface-design` | Explorer, Worker | Relational normalization, migration immutability, zero dummy seeds. |
| **Observability & Logging** | `preferred/observability-and-instrumentation` | Explorer, Worker | Structured JSON logs, sensitive data scrubbing, `/api/health`. |
| **Security & RBAC** | `preferred/security-and-hardening` | Challenger, Auditor | OWASP Top 10, constant-time token comparison, brute-force mitigation. |
| **CI/CD & Workflows** | `preferred/ci-cd-and-automation` | Worker, Reviewer | Deterministic caching, GitHub Actions, zero-secret hygiene. |
| **Testing & TDD** | `skills/test` & `skills/verify` | Challenger, Worker | Red-Green-Refactor, static verifier scripts, blinded rubrics. |
| **Code Review & Standards** | `skills/review` & `skills/unslop` | Reviewer | 5-axis review, boilerplate stripping, zero AI fluff. |
| **Performance & Benchmarking** | `preferred/performance-optimization` & `preferred/benchmark-harness` | Challenger, Worker | Latency budgets, p99 regression gates, memory leak detection. |

---

## 2. Autowiring Prompt Protocol

When authoring subagent dispatch payloads, the Orchestrator includes the exact path to the relevant domain skill file:

```json
{
  "Subagents": [
    {
      "Role": "Observability & Audit Specialist",
      "TypeName": "self",
      "Model": "flash",
      "Prompt": "You are the Worker for Milestone 3.\nWorking directory: .agents/worker_m3/\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nScope document: .agents/orchestrator/PROJECT.md\nDomain Skill: c:\\Users\\kspra\\code\\github\\agent-skill-forge\\preferred\\observability-and-instrumentation\\SKILL.md\n\nRead the domain skill instructions carefully before implementing structured logging and health endpoints."
    }
  ]
}
```

The subagent reads the referenced `SKILL.md` using `view_file` at the start of its turn, inheriting world-class engineering standards without polluting the Orchestrator's context window.
