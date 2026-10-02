# 🔌 Domain Skill Autowiring: Dynamic Capability Injection

Subagents dispatched by `/work` start with no knowledge of which local skills
apply to the task they were handed. Autowiring closes that gap: before writing
a dispatch payload, the Orchestrator runs `autowire.py`, which scans the
`skills/` and `preferred/` catalogs on disk, matches the task description
against the mapping matrix below, and emits the exact injection lines — with
the paths verified to exist.

```bash
python3.12 skills/work/scripts/autowire.py \
  --task "Implement structured JSON logging and a /api/health endpoint" \
  --role Worker
```

```
Domain Skills (read each with view_file before you start; matched for role Worker):
- preferred/observability-and-instrumentation/SKILL.md — Observability & Logging (matched: health endpoint, logging)
- preferred/api-and-interface-design/SKILL.md — Database, Schema & API Contracts (matched: api, endpoint)
These are keyword matches against the task text, not a judgement about what the
task needs. Read them and apply the ones that apply.
```

**What the script decides and what it does not.** It decides which domains
contain a trigger word present in the task text, and it decides whether the
skill paths those domains name exist on disk. Both are mechanical. It does not
decide which skill the task actually needs — a keyword hit is a candidate. The
dispatching agent reads the candidates and picks; a subagent handed five paths
is expected to open them and use the ones that apply, not all five.

---

## 1. Skill Mapping Matrix

This table is the human-readable copy of `DOMAIN_MATRIX` in
`skills/work/scripts/autowire.py`. `tests/test_autowire.py` parses it and fails
if the two disagree, so a row cannot rot here without breaking the build.

| Technical Domain | Applicable Core / Preferred Skill | Target Roles | Injected Instructions |
|------------------|-----------------------------------|--------------|------------------------|
| **Database, Schema & API Contracts** | `preferred/api-and-interface-design` | Explorer, Worker | Relational normalization, migration immutability, zero dummy seeds. |
| **Observability & Logging** | `preferred/observability-and-instrumentation` | Explorer, Worker | Structured JSON logs, sensitive data scrubbing, /api/health. |
| **Security & RBAC** | `preferred/security-and-hardening` | Challenger, Auditor | OWASP Top 10, constant-time token comparison, brute-force mitigation. |
| **CI/CD & Workflows** | `preferred/ci-cd-and-automation` | Worker, Reviewer | Deterministic caching, GitHub Actions, zero-secret hygiene. |
| **Testing & TDD** | `skills/test` & `skills/verify` | Challenger, Worker | Red-Green-Refactor, static verifier scripts, blinded rubrics. |
| **Code Review & Standards** | `skills/review` & `skills/unslop` | Reviewer | 5-axis review, boilerplate stripping, zero AI fluff. |
| **Performance & Benchmarking** | `preferred/performance-optimization` & `preferred/benchmark-harness` | Challenger, Worker | Latency budgets, p99 regression gates, memory leak detection. |

Run `autowire.py --list` to print the matrix together with each skill's
frontmatter description, its catalog tags, and its resolution status.

---

## 2. Autowiring Prompt Protocol

The Orchestrator pastes the emitted block verbatim into the dispatch payload:

```json
{
  "Subagents": [
    {
      "Role": "Observability & Audit Specialist",
      "TypeName": "self",
      "Model": "inherit",
      "Prompt": "You are the Worker for Milestone 3.\nWorking directory: .agents/worker_m3/\nAuthoritative requirements: .agents/ORIGINAL_REQUEST.md\nScope document: .agents/orchestrator/PROJECT.md\nGrounding: .gemini/knowledge/ (read the index first)\n\nDomain Skills (read each with view_file before you start; matched for role Worker):\n- preferred/observability-and-instrumentation/SKILL.md — Observability & Logging (matched: health endpoint, logging)\n\nRead the referenced skills before implementing structured logging and health endpoints."
    }
  ]
}
```

The subagent opens each referenced `SKILL.md` at the start of its turn,
inheriting the engineering standard without the Orchestrator having to hold any
of it in context.

---

## 3. Keeping the Matrix Honest

`autowire.py --check` exits non-zero when a matrix row names a skill that is
not on disk, maps to no skill at all, or carries no triggers (and so could
never fire). Run it in CI after any skill rename:

```bash
python3.12 skills/work/scripts/autowire.py --check --repo-root .
```

When a task matches nothing, the brief says so explicitly and points the
subagent at `.gemini/knowledge/`. Silence would let a subagent assume no
standard applied.
