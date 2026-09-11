# Declarative DAG: Async Watchdog and Barrier Gates

Topology: mixed
Integrity Mode: development

---

## 📋 Task Graph

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `watchdog` | Liveness Heartbeat Watchdog | async_background | none | none | .agents/sentinel/heartbeat.log | cron: */10 * * * * | RUNNING |
| `task_init` | Initialization Step | series | none | ORIGINAL_REQUEST.md | src/init.py | exit_0 | PASSED |
| `task_worker` | Core Worker | series | task_init | src/init.py | src/app.py | exit_0 | RUNNING |
| `task_gate` | Milestone Gate | series | task_worker | src/app.py | dist/app.bin | build_pass | PENDING |
