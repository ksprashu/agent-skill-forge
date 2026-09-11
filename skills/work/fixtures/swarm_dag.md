# Multi-Milestone Swarm DAG Specification

## Task Graph
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| survey_1 | Codebase Survey | parallel | none | ORIGINAL_REQUEST.md | .agents/survey_1/report.md | file_exists | PASSED |
| survey_2 | Architectural Survey | parallel | none | ORIGINAL_REQUEST.md | .agents/survey_2/report.md | file_exists | PASSED |
| worker_m1 | DAG Harness Implementer | parallel | survey_1, survey_2 | .agents/survey_1/report.md | skills/work/scripts/dag_validator.py | exit_0 | PASSED |
| worker_m2 | Markdown Schema Implementer | parallel | survey_1, survey_2 | .agents/survey_2/report.md | skills/plan/SKILL.md | exit_0 | PASSED |
| watchdog | Liveness Watchdog | async_background | none | none | .agents/sentinel/progress.md | none | RUNNING |
| arbiter | Integration Arbiter | series | worker_m1, worker_m2 | skills/work/scripts/dag_validator.py | .agents/arbiter/scorecard.md | exit_0 | PENDING |
| forensic | AST Integrity Audit | series | arbiter | skills/work/scripts/dag_validator.py | .agents/forensic/report.md | zero_mock | PENDING |
| victory | Swarm Certification | series | forensic | .agents/forensic/report.md | .agents/sentinel/VICTORY.md | all_passed | PENDING |

```mermaid
graph TD
    %% Task Nodes
    arbiter["arbiter<br/>[series] <b>PENDING</b>"]:::status-pending
    forensic["forensic<br/>[series] <b>PENDING</b>"]:::status-pending
    survey_1["survey_1<br/>[parallel] <b>PASSED</b>"]:::status-passed
    survey_2["survey_2<br/>[parallel] <b>PASSED</b>"]:::status-passed
    victory["victory<br/>[series] <b>PENDING</b>"]:::status-pending
    watchdog["watchdog<br/>[async_background] <b>RUNNING</b>"]:::status-running
    worker_m1["worker_m1<br/>[parallel] <b>PASSED</b>"]:::status-passed
    worker_m2["worker_m2<br/>[parallel] <b>PASSED</b>"]:::status-passed

    %% Dependency Edges
    arbiter --> forensic
    forensic --> victory
    survey_1 --> worker_m1
    survey_1 --> worker_m2
    survey_2 --> worker_m1
    survey_2 --> worker_m2
    worker_m1 --> arbiter
    worker_m2 --> arbiter

    %% Node Status Styling
    classDef status-pending fill:#2d3748,stroke:#4a5568,color:#cbd5e0;
    classDef status-running fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#93c5fd;
    classDef status-passed fill:#14532d,stroke:#22c55e,color:#86efac;
    classDef status-blocked fill:#78350f,stroke:#f59e0b,color:#fde68a;
    classDef status-failed fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fca5a5;
    classDef pending fill:#2d3748,stroke:#4a5568,color:#cbd5e0;
    classDef running fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#93c5fd;
    classDef passed fill:#14532d,stroke:#22c55e,color:#86efac;
    classDef blocked fill:#78350f,stroke:#f59e0b,color:#fde68a;
    classDef failed fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fca5a5;
```
