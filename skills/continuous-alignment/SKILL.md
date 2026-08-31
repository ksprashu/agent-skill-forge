---
name: continuous-alignment
description: Autonomous continuous alignment and self-evolving project intelligence engine. Distills session transcripts, enforces a 200-line budget on AGENTS.md, manages path-scoped rules, records living ADRs, and compiles roadmap visualizers via Antigravity hooks. Trigger via /align or /evolve.
---

# Continuous Alignment & Project Evolution Engine

Maintain a growing, self-evolving vision, mission, direction, rules, and operational instructions for your software project as development progresses.

---

## 🎯 Goal
Prevent architectural drift and context rot by continuously distilling session insights, enforcing a strict 200-line token budget on root `AGENTS.md`, cascading path-scoped rules to `.agents/rules/*.md`, compiling living Architectural Decision Records (MADRs), and maintaining an interactive SVG roadmap.

---

## 🏗️ 4-Tier Memory Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Hot Invariants (`AGENTS.md` / `GEMINI.md`)                     │
│ • Capped at max 200 lines (~1,500 tokens)                             │
│ • Fast-path commands, negative constraints, root gotchas               │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Path-Scoped Rules (`.agents/rules/*.md`)                       │
│ • Subsystem rules progressively loaded via path proximity             │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: Strategic Direction (`docs/VISION.md`, `docs/ROADMAP.md`)      │
│ • Living roadmap, milestone tracking, glowing SVG branching visualizer │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 4: Architectural Decision Records (`.gemini/knowledge/ADRs/`)     │
│ • MADR formatted records capturing context, decisions, and trade-offs  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Operational Workflows

### 1. Autonomous Turn Distillation (Antigravity `Stop` Hook)
When an agent turn completes, Antigravity executes `skills/continuous-alignment/scripts/distill_session.py`:
1. Reads the turn execution `transcript.jsonl`.
2. Extracts verified user constraints, error troubleshooting fixes, and CLI commands.
3. Appends deduplicated entries to `.gemini/knowledge/memories.jsonl`.
4. Triggers rule consolidation and living roadmap synchronization.

### 2. Manual Alignment Trigger (`/align` or `/evolve`)
To manually reconcile project instructions, review living ADRs, or prune outdated rules:
```bash
# 1. Distill recent session learnings
python skills/continuous-alignment/scripts/distill_session.py

# 2. Synchronize AGENTS.md and enforce 200-line budget limit
python skills/continuous-alignment/scripts/sync_agents_rules.py

# 3. Compile living ADRs, VISION.md, and ROADMAP.md
python skills/continuous-alignment/scripts/compile_roadmap.py
```

### 3. Context Pulse Inspection (`PreInvocation` Hook)
Inspect the active workspace invariants and recommended commands injected before model turns:
```bash
python skills/continuous-alignment/scripts/sync_agents_rules.py --pulse
```

---

## 🛡️ Key Guarantees
- **Zero Third-Party Dependencies**: Pure Python standard library (`json`, `re`, `hashlib`, `tempfile`).
- **Sub-Second Execution**: Hook execution completes in $< 150\text{ms}$.
- **Zero Token Waste**: Strict 200-line budget cap prevents context bloat in root instruction files.
