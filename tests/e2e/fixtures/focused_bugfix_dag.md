# Declarative DAG: Focused Bugfix Swarm

Topology: focused
Integrity Mode: development
Target Issue: Fix JSON deserialization crash on malformed payloads

---

## 📊 Live Mermaid Execution Topology

```mermaid
graph TD
  task_worker_fix["task_worker_fix<br/>(Worker Implementation)"]:::passed
  task_reviewer["task_reviewer<br/>(5-Axis Reviewer)"]:::running
  task_challenger["task_challenger<br/>(Adversarial Challenger)"]:::running
  task_forensic_auditor["task_forensic_auditor<br/>(Forensic Auditor)"]:::running
  task_victory_auditor["task_victory_auditor<br/>(Victory Certification)"]:::pending

  task_worker_fix --> task_reviewer
  task_worker_fix --> task_challenger
  task_worker_fix --> task_forensic_auditor
  task_reviewer --> task_victory_auditor
  task_challenger --> task_victory_auditor
  task_forensic_auditor --> task_victory_auditor

  classDef pending fill:#f1f5f9,stroke:#64748b,stroke-width:1px,color:#334155;
  classDef running fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#713f12;
  classDef passed fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d;
  classDef failed fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#7f1d1d;
  classDef blocked fill:#e2e8f0,stroke:#94a3b8,stroke-width:1px,stroke-dasharray: 5 5,color:#64748b;
```

---

## 📋 Declarative Task Graph Table

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `task_worker_fix` | Bugfix Implementation | series | none | ORIGINAL_REQUEST.md | src/parser.py, tests/test_parser.py, .agents/worker_fix/handoff.md | pytest tests/test_parser.py | PASSED |
| `task_reviewer` | 5-Axis Reviewer | parallel | task_worker_fix | src/parser.py, .agents/worker_fix/handoff.md | .agents/reviewer_fix/review.md | review_pass | RUNNING |
| `task_challenger` | Adversarial Boundary Fuzzer | parallel | task_worker_fix | src/parser.py, tests/test_parser.py | tests/test_hostile.py, .agents/challenger_fix/handoff.md | pytest tests/test_hostile.py | RUNNING |
| `task_forensic_auditor` | AST Anti-Mock Integrity Check | parallel | task_worker_fix | src/parser.py, tests/test_parser.py | .agents/auditor_fix/handoff.md, .agents/EVIDENCE.md | zero_mock | RUNNING |
| `task_victory_auditor` | Clean-Slate Certification | series | task_reviewer, task_challenger, task_forensic_auditor | .agents/reviewer_fix/review.md, .agents/challenger_fix/handoff.md, .agents/auditor_fix/handoff.md | .agents/victory_auditor/handoff.md | victory_gate | PENDING |
