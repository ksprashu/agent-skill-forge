# Project Strategic Roadmap

> [!NOTE]
> Living roadmap compiled continuously by `continuous-alignment` engine.

<svg class="w-full max-w-2xl my-6 rounded-xl border border-slate-700/60 bg-slate-900/90 shadow-2xl p-4" viewBox="0 0 760 385" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#818cf8"/>
    </linearGradient>
  </defs>
  <line x1="80" y1="40" x2="80" y2="345" stroke="url(#lineGrad)" stroke-width="4" stroke-linecap="round" stroke-dasharray="6 6"/>
  <g transform="translate(0, 50)">
    <circle cx="80" cy="0" r="10" fill="#0f172a" stroke="#10b981" stroke-width="3"/>
    <circle cx="80" cy="0" r="4" fill="#10b981"/>
    <rect x="110" y="-20" width="60" height="20" rx="4" fill="#064e3b"/>
    <text x="140" y="-6" fill="#6ee7b7" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">DONE</text>
    <text x="180" y="-5" fill="#f8fafc" font-size="14" font-family="sans-serif" font-weight="600">M1: 4-Tier Memory & Hook Protocol Spec</text>
    <text x="180" y="14" fill="#94a3b8" font-size="11" font-family="sans-serif">Schemas and contracts for transcript distillation and budgeting</text>
  </g>
  <g transform="translate(0, 110)">
    <circle cx="80" cy="0" r="10" fill="#0f172a" stroke="#10b981" stroke-width="3"/>
    <circle cx="80" cy="0" r="4" fill="#10b981"/>
    <rect x="110" y="-20" width="60" height="20" rx="4" fill="#064e3b"/>
    <text x="140" y="-6" fill="#6ee7b7" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">DONE</text>
    <text x="180" y="-5" fill="#f8fafc" font-size="14" font-family="sans-serif" font-weight="600">M2: Stop Hook & Distillation Engine</text>
    <text x="180" y="14" fill="#94a3b8" font-size="11" font-family="sans-serif">Sub-second transcript parser and deduplicating memory writer</text>
  </g>
  <g transform="translate(0, 170)">
    <circle cx="80" cy="0" r="10" fill="#0f172a" stroke="#10b981" stroke-width="3"/>
    <circle cx="80" cy="0" r="4" fill="#10b981"/>
    <rect x="110" y="-20" width="60" height="20" rx="4" fill="#064e3b"/>
    <text x="140" y="-6" fill="#6ee7b7" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">DONE</text>
    <text x="180" y="-5" fill="#f8fafc" font-size="14" font-family="sans-serif" font-weight="600">M3: AGENTS.md 200-Line Budget Enforcer</text>
    <text x="180" y="14" fill="#94a3b8" font-size="11" font-family="sans-serif">Semantic rule merge, conflict invalidation, and path-rule spillover</text>
  </g>
  <g transform="translate(0, 230)">
    <circle cx="80" cy="0" r="10" fill="#0f172a" stroke="#10b981" stroke-width="3"/>
    <circle cx="80" cy="0" r="4" fill="#10b981"/>
    <rect x="110" y="-20" width="60" height="20" rx="4" fill="#064e3b"/>
    <text x="140" y="-6" fill="#6ee7b7" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">DONE</text>
    <text x="180" y="-5" fill="#f8fafc" font-size="14" font-family="sans-serif" font-weight="600">M4: Living ADR & Roadmap Compiler</text>
    <text x="180" y="14" fill="#94a3b8" font-size="11" font-family="sans-serif">Automated MADR tracking and SVG visual timeline compilation</text>
  </g>
  <g transform="translate(0, 290)">
    <circle cx="80" cy="0" r="10" fill="#0f172a" stroke="#10b981" stroke-width="3"/>
    <circle cx="80" cy="0" r="4" fill="#10b981"/>
    <rect x="110" y="-20" width="60" height="20" rx="4" fill="#064e3b"/>
    <text x="140" y="-6" fill="#6ee7b7" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">DONE</text>
    <text x="180" y="-5" fill="#f8fafc" font-size="14" font-family="sans-serif" font-weight="600">M5: Full Verification & Skill Integration</text>
    <text x="180" y="14" fill="#94a3b8" font-size="11" font-family="sans-serif">Pytest harness, validate_skills.py passing, and live hook registration</text>
  </g>
</svg>

---

## Active Milestone Breakdown

### 1. Milestone Tracking
| Milestone | Status | Description |
| :--- | :--- | :--- |
| **M1: Spec & Protocol** | `Completed` | Memory schema and Antigravity hook contracts |
| **M2: Distillation Engine** | `Completed` | Zero-dependency transcript parser (< 150ms) |
| **M3: Rule Sync & Budgeting** | `Completed` | 200-line budget limit and path-scoped rules |
| **M4: Living ADR Compiler** | `Completed` | MADR template generation and SVG branching timeline |
| **M5: Verification & Deploy** | `Completed` | Pytest test suite and zero-lint skill validation |

---

## Architectural Decision Records (Living ADRs)
Currently recorded architectural decisions in `.gemini/knowledge/ADRs/`:

- **[ADR-001: Flat-File JSONL Storage for Session Memory Distillation](file:///Users/ksprashanth/code/github/agent-skill-forge/.gemini/knowledge/ADRs/ADR-001-flat_file_memory_store.md)** (`Accepted`)
