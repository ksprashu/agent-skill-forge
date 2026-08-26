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
2. **Slice Vertically**: Design tasks that deliver an end-to-end slice of functionality (schema + logic + test) rather than horizontal layers (all schemas first, all APIs second).
3. **Map Dependencies**: Order tasks so prerequisites execute first.
4. **Define Verifiable Checkpoints**: Every task must have an automated command to prove completion.
5. **Output Artifact**: Save the execution plan to `tasks/plan.md` and actionable checkboxes to `tasks/todo.md`.

---

## 💡 Concrete Example

### Fixture: `tasks/plan.md`
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

---

## 🚫 Hard Constraints

*   **NEVER** modify or create functional source code during the planning phase.
*   **NEVER** plan horizontal slices (e.g. "write all database tables across all 10 features").
*   **NEVER** create tasks touching more than 3–5 related files.
