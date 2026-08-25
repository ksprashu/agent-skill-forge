---
name: plan
description: Decomposes specifications into small, vertically sliced, verifiable task DAGs with explicit checkpoints. Auto-invokes when a spec is ready or via `/plan`.
---

# Planning

## Overview

Break high-level specifications and requirements into small, sequential, verifiable tasks to structure the implementation phase.

## When to Use

- Use when a spec (such as SPEC.md) or clear requirements exist, and you need to plan the step-by-step implementation.
- Use before starting to write any functional code for a feature or project.
- Do NOT use to write high-level product requirements or specifications.

## Core Process

Read the existing spec (SPEC.md or equivalent) and the relevant codebase sections. Then:

1. Enter plan mode — read only, no code changes.
2. Identify the dependency graph between components.
3. Slice work vertically (one complete path per task, not horizontal layers).
4. Write tasks with acceptance criteria and verification steps.
5. Add checkpoints between phases.
6. Present the plan for human review.

Save the plan to `tasks/plan.md` and task list to `tasks/todo.md`.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The project is small enough that I can keep the plan in my head." | Writing the plan down forces you to think through dependencies and edge cases, and lets the human review it first. |
| "I can plan horizontal layers (database first, then api, then UI) instead of vertical slices." | Horizontal plans delay integration and verification. Vertical slices ensure you can verify working functionality at every step. |

## Red Flags

- Writing or modifying functional code during the planning phase.
- Creating tasks that are too large (e.g., touching more than 5 files per task).
- Omitting verification steps or acceptance criteria from tasks.

## Verification

After completing the planning phase, confirm:
- [ ] The plan is saved to `tasks/plan.md` and task list to `tasks/todo.md`.
- [ ] Tasks are structured as vertical slices with explicit acceptance and verification criteria.
- [ ] The human has reviewed and approved the plan before any code implementation begins.
