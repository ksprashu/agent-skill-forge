---
type: "Architecture Catalog"
title: "Multi-Agent Orchestration Patterns & Anti-Patterns"
description: "Reference catalog of endorsed agent orchestration patterns (direct invocation, parallel fan-out, sequential pipeline, research isolation) and anti-patterns."
resource: "file:///Users/ksprashanth/code/github/agent-skills/references/orchestration-patterns.md"
tags: ["architecture", "orchestration", "multi-agent", "patterns", "anti-patterns", "fan-out"]
---

# 🎭 Multi-Agent Orchestration Patterns Catalog

Architectural patterns for orchestrating AI agents, subagents, personas, and skill pipelines.

---

## 1. Endorsed Orchestration Patterns

### Pattern 1: Direct Invocation (Zero Orchestration)
- **Topology**: `User ──► Persona/Skill ──► Report ──► User`
- **Use Case**: Single perspective on a single artifact (e.g., "Review this PR diff").
- **Economics**: Lowest cost (1 round trip, baseline context).

### Pattern 2: Single-Persona Slash Command
- **Topology**: `/review ──► Reviewer Persona (with review skill) ──► Report`
- **Use Case**: Repeatable daily workflow wrapping a persona with standardized project skills.

### Pattern 3: Parallel Fan-Out with Merge (`/ship` pattern)
- **Topology**:
  ```
                      ┌─► Code Reviewer Subagent      ─┐
  /ship ──► Fan Out ──┼─► Security Auditor Subagent  ─┼─► Merge ──► Go/No-Go Decision
                      ├─► Test QA Engineer Subagent   ─┤
                      └─► Performance Auditor Subagent─┘
  ```
- **Use Case**: Completely independent investigations operating concurrently on the same codebase state.
- **Economics**: N parallel fresh contexts + 1 synthesis merge turn. Drastically cuts wall-clock latency while eliminating context contamination.

### Pattern 4: Sequential Pipeline with Human Checkpoints
- **Topology**: `User runs: /spec ──► /plan ──► /build ──► /test ──► /review ──► /ship`
- **Governing Invariant**: The human developer is the orchestrator. Each phase ends with verifiable artifacts reviewed before proceeding.

### Pattern 5: Research Isolation (Context Preservation)
- **Topology**: Spawns a background subagent to crawl heavy documentation or search logs, returning only a compact synthesis digest to the main session.

---

## 2. Invalid Orchestration Anti-Patterns

### Anti-Pattern 1: The "Meta-Orchestrator" Router Persona
- **Broken Design**: A generic orchestrator subagent whose only job is deciding which worker persona to call.
- **Failure Cause**: Adds 2 redundant paraphrasing hops, causes prompt token bloat, loses context fidelity, and duplicates slash command routing.

### Anti-Pattern 2: Nested Subagent Spawning
- **Broken Design**: Subagents attempting to recursively spawn their own subagents.
- **Failure Cause**: Platform runtime constraints in Claude Code and Antigravity prohibit nested agent trees. All parallel fan-out must be dispatched from the top-level orchestrator.
