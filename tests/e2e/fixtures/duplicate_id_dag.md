# Declarative DAG: Duplicate Task ID Error

Topology: invalid_duplicate
Integrity Mode: development

---

## 📋 Task Graph

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_dup` | First Instance | series | none | ORIGINAL_REQUEST.md | src/first.py | exit_0 | PASSED |
| `task_dup` | Second Duplicate Instance | series | none | ORIGINAL_REQUEST.md | src/second.py | exit_0 | PENDING |
