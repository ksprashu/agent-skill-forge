# Declarative DAG: Missing Dependency Error

Topology: invalid_dep
Integrity Mode: development

---

## 📋 Task Graph

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_valid` | Valid Base Task | series | none | ORIGINAL_REQUEST.md | src/base.py | exit_0 | PASSED |
| `task_orphan` | Orphan Task with Missing Dep | series | ghost_task_99 | src/base.py | src/orphan.py | exit_0 | PENDING |
