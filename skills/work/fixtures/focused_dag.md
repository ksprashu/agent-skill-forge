# Focused Bugfix DAG Specification

## Task Graph
| ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| worker_alpha | Implement Fix | series | none | ORIGINAL_REQUEST.md | src/fix.py | test_pass | PASSED |
| reviewer | Code & Arch Review | parallel | worker_alpha | src/fix.py | .agents/reviewer/report.md | exit_0 | PASSED |
| challenger | Adversarial Test Challenge | parallel | worker_alpha | src/fix.py | .agents/challenger/report.md | exit_0 | PASSED |
| forensic | AST Anti-Mock Audit | parallel | worker_alpha | src/fix.py | .agents/forensic/report.md | zero_mock | PASSED |
| victory | Victory Certification | series | reviewer, challenger, forensic | .agents/reviewer/report.md, .agents/challenger/report.md, .agents/forensic/report.md | .agents/sentinel/VICTORY.md | all_passed | PENDING |

```mermaid
graph TD
    %% Task Nodes
    challenger["challenger<br/>[parallel] <b>PASSED</b>"]:::status-passed
    forensic["forensic<br/>[parallel] <b>PASSED</b>"]:::status-passed
    reviewer["reviewer<br/>[parallel] <b>PASSED</b>"]:::status-passed
    victory["victory<br/>[series] <b>PENDING</b>"]:::status-pending
    worker_alpha["worker_alpha<br/>[series] <b>PASSED</b>"]:::status-passed

    %% Dependency Edges
    challenger --> victory
    forensic --> victory
    reviewer --> victory
    worker_alpha --> challenger
    worker_alpha --> forensic
    worker_alpha --> reviewer

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
