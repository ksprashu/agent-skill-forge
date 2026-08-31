# PRMT-E94A: System Architecture & Schemas

## 1. 4-Tier Memory Topology
```
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Hot Invariants (`AGENTS.md` / `GEMINI.md`)                     │
│ • Capped at max 200 lines (~1,500 tokens)                             │
│ • Frontloaded CLI commands, negative constraints, root gotchas         │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Path-Scoped Rules (`.agents/rules/*.md`)                       │
│ • Cascading proximity rules loaded only when touching specific paths  │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: Strategic Direction (`docs/VISION.md`, `docs/ROADMAP.md`)      │
│ • Long-range north star, release milestones, user personas            │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 4: Architectural Decision Records (`.gemini/knowledge/ADRs/`)     │
│ • MADR format: Context, Decision Drivers, Considered Options, Outcome  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pydantic / JSON Schemas

### Semantic Rule Extraction Schema
```json
{
  "rule_id": "RULE-A104",
  "category": "architecture | constraint | command | testing",
  "scope": "root | path-scoped",
  "target_path_glob": "skills/docs-sync/**",
  "statement": "Always compile HTML docs with compile_html_docs.py after modifying template assets.",
  "rationale": "Prevents stale rendered output in web portals.",
  "confidence": 0.95,
  "supersedes": null
}
```

### Living ADR Schema (MADR format)
```markdown
# ADR-001: JSONL Flat-File Storage for Session Distillation

## Status
Accepted

## Context
Antigravity Stop hooks run synchronously under 45-second budgets. External database dependencies introduce setup friction and binary compatibility risks across platforms.

## Decision
We use native Python `json`, `re`, and flat JSONL files for local rule indices and memory state.

## Consequences
- Positive: Zero external dependencies; instant execution (< 100ms).
- Positive: Git-diffable and version-controlled.
- Negative: Querying requires full file scans, acceptable for single-project scope (< 1,000 rules).
```

---

## 3. Hook Integration Contract (`hooks.json`)
```json
{
  "continuous-alignment": {
    "Stop": [
      {
        "type": "command",
        "command": "python skills/continuous-alignment/scripts/distill_session.py",
        "timeout": 45
      }
    ],
    "PreInvocation": [
      {
        "type": "command",
        "command": "python skills/continuous-alignment/scripts/sync_agents_rules.py --pulse",
        "timeout": 15
      }
    ]
  }
}
```
