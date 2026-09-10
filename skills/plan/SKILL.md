---
name: plan
description: Slice complex features, refactors, or projects into a dependency DAG with verifiable checkpoints. Trigger via /plan.
---

# Plan: Task Slicing & Dependency DAGs

Decompose specifications into small, vertically sliced, verifiable task sequences before writing code.

---

## 🎯 Goal
Structure implementation into independent, incrementally testable vertical slices with clear checkpoints.

---

## 📋 Step-by-Step Workflow

1. **Read-Only Inspection**: Inspect existing `SPEC.md` or context without writing implementation code.
2. **Environment & Tool Scoping**: If the task requires external services (databases, cloud deployment), plan prerequisite setup to scaffold project-level plugins in `.agents/plugins/` or configure local environment variables/CLIs rather than global tools.
3. **Select Execution Topology**:
   - **Single-Agent Slice Mode**: For self-contained tasks, design end-to-end vertical slices (schema + logic + test) touching 3–5 related files. Save to `tasks/plan.md` and `tasks/todo.md`.
   - **Multi-Agent Work Swarm Mode**: For large initiatives, rearchitectures, or multi-stage systems, decompose into staged milestones for the autonomous Work engine. Save master architecture to `.agents/orchestrator/PROJECT.md`.
4. **Map Feature Inventory & Dependencies**: Catalog features ($F_1 \dots F_n$) mapped to user requirements and sequence milestones ($M_1 \dots M_k$) with barrier gates.
5. **Define Subagent & Adversary Matrix**: For each milestone, assign parallel Explorers, Worker implementers, and Adversarial Committee members (Reviewer, Challenger, Forensic Auditor).
6. **Define Verifiable Checkpoints**: Every task/milestone must have an automated, objective command or verifier script to prove completion.

---

## 💡 Concrete Examples

### 1. Single-Agent Fixture: `tasks/plan.md`
```markdown
# Implementation Plan: User Authentication

## Phase 1: Core Session Storage
- [ ] Task 1: SQLite schema migration for `sessions` table (`migrations/001_sessions.sql`).
  - *Verification*: `pytest tests/test_migrations.py`
- [ ] Task 2: Session repository create & validate methods (`src/auth/repo.py`).
  - *Verification*: `pytest tests/test_auth_repo.py`

## Phase 2: HTTP Middleware Slice
- [ ] Task 3: Auth middleware verifying Bearer tokens against repository (`src/middleware/auth.py`).
  - *Verification*: `pytest tests/test_auth_middleware.py`

## Checkpoint A: End-to-End Smoke Test
- Run `npm test` or `pytest` to ensure all Phase 1-2 tests pass before building frontend UI.
```

### 2. Multi-Agent Work Swarm Fixture: `.agents/orchestrator/PROJECT.md`
```markdown
# Project Master Plan: CheckInn Rearchitecture

## Feature Inventory
| ID | Feature Name | Description | Milestone | Ref Requirements |
|----|--------------|-------------|-----------|------------------|
| F1 | Clean Multi-Tenant Schema | Supabase PostgreSQL + Drizzle ORM | M1 | R1 |
| F2 | RBAC & QR Checkin Gate | Multi-persona routing & physical scanner | M2 | R2 |
| F3 | Observability & Audit Logs | Centralized JSON logger & sensitive scrubber | M3 | R3 |

## Staged Milestones & Agent Matrix
| # | Name | Explorer Swarm | Worker | Adversarial Gate | Status |
|---|------|----------------|--------|------------------|--------|
| M1 | Multi-Tenant DB Schema | DB & Migration Explorers | Schema Worker | Reviewer + SQL Injection Challenger + Auditor | DONE |
| M2 | Persona Auth & Routing | Session & QR Explorers | Auth Worker | Reviewer + Tenant Isolation Challenger + Auditor | PENDING |
| M3 | Observability & Health | Metrics Explorer | Logging Worker | Reviewer + Sensitive Scrubber Challenger + Auditor | PENDING |
```

---

## 🚫 Hard Constraints

*   **NEVER** modify or create functional source code during the planning phase.
*   **NEVER** plan horizontal slices (e.g. "write all database tables across all 10 features").
*   **NEVER** create tasks touching more than 3–5 related files in single-agent mode.
*   **NEVER** assume global MCP servers—plan project-level plugins under `.agents/plugins/` or local CLI/env configurations for external service dependencies.
*   **NEVER** advance milestones in Work Swarm mode without passing the Adversarial Committee gate.
