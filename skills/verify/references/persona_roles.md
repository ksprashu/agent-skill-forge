# Persona Role Assignments in EGA Task Graph Nodes

## Executive Overview

In **Expectation-Grounded Alignment (EGA)** (`expectation-harness`), work is executed through an **Automated Dual-Verification Control Loop** (`verify_static.py` + `rubric.json`).

Rather than treating the **6-Personas Framework** as a rigid, multi-file document pipeline, EGA incorporates 6-personas as **Subagent Role Assignments** inside task graph nodes (`task_graph.json`).

This provides **maximum cognitive specialization** for worker subagents without introducing persistent file bloat or human-in-the-loop breakpoint friction.

---

## The 6 Persona Role Primers

When dispatching worker subagents for a task node, pass the `persona_role` parameter as the `Role` argument in `invoke_subagent`.

| Persona Role | Primary Mandate | Tool Constraints & Prompt Priming |
| :--- | :--- | :--- |
| **`Scout-Researcher`** | Codebase exploration, fact-finding, dependency auditing. | **Read-Only**: Restricted from modifying source files or committing code. Must ground all facts in actual file paths. |
| **`Analyst-Inquirer`** | Requirement disambiguation, edge case identification, risk modeling. | **Analytical**: Formulates precise constraints, identifies missing edge cases, and maps out failure modes. |
| **`Architect-Blueprint`** | API contract design, data schemas, module boundaries. | **Structural**: Defines interfaces, types, schemas, and task node dependencies without writing inner business logic. |
| **`Builder-Coder`** | Feature construction, code refactoring, complete implementation. | **Implementation**: Reconstructs stubs, implements production logic, ensures zero syntax/linter errors. |
| **`Sentry-Gatekeeper`** | Security auditing, adversarial testing, quality assurance. | **Adversarial**: Writes unit/integration tests, scans for OWASP vulnerabilities, and attempts to break assumptions. |
| **`Mentor-Educator`** | Documentation synthesis, migration guides, knowledge transfer. | **Pedagogical**: Formulates clear READMEs, architecture walkthroughs, and inline documentation. |

---

## Schema Integration in `task_graph.json`

```json
{
  "short_id": "EGA-89A1",
  "goal_summary": "Implement OAuth2 Token Refresh Endpoint",
  "nodes": [
    {
      "id": "node_01_scout",
      "name": "Audit OAuth Configs",
      "persona_role": "Scout-Researcher",
      "spec_file": ".gemini/harness/EGA-89A1/tasks/task_01_spec.md",
      "target_artifact": ".gemini/harness/EGA-89A1/scout_report.md",
      "static_verifier": ".gemini/harness/EGA-89A1/verify_scout.py",
      "dynamic_rubric": ".gemini/harness/EGA-89A1/rubric_scout.json",
      "status": "COMPLETED"
    },
    {
      "id": "node_02_construction",
      "name": "Implement Middleware",
      "persona_role": "Builder-Coder",
      "spec_file": ".gemini/harness/EGA-89A1/tasks/task_02_spec.md",
      "target_artifact": "src/auth/middleware.py",
      "static_verifier": ".gemini/harness/EGA-89A1/verify_code.py",
      "dynamic_rubric": ".gemini/harness/EGA-89A1/rubric_code.json",
      "status": "PENDING"
    },
    {
      "id": "node_03_audit",
      "name": "Security Test Suite",
      "persona_role": "Sentry-Gatekeeper",
      "spec_file": ".gemini/harness/EGA-89A1/tasks/task_03_spec.md",
      "target_artifact": "tests/test_sentry.py",
      "static_verifier": ".gemini/harness/EGA-89A1/verify_tests.py",
      "dynamic_rubric": ".gemini/harness/EGA-89A1/rubric_sentry.json",
      "status": "PENDING"
    }
  ]
}
```

---

## Subagent Dispatch Specimen

When dispatching worker subagents in python or agent code:

```python
invoke_subagent(
    Subagents=[{
        "Model": "flash",
        "Role": "Sentry-Gatekeeper",
        "TypeName": "self",
        "Prompt": """You are operating in the 'Sentry-Gatekeeper' persona role under EGA Task Node node_03.
Mandate: Approach the deliverable with pure adversarial skepticism. Write unit tests for expired tokens, signature tampering, and privilege escalation.
Task Directive: .gemini/harness/EGA-89A1/tasks/task_03_spec.md"""
    }]
)
```

---

## Benefits

1. **Focused Subagent Output**: Subagents adopt exact cognitive mindsets tailored to their node's specific responsibility.
2. **Zero Persistent Overhead**: Eliminates 6 mandatory markdown files per task run.
3. **Pinpointed Delta Feedback**: Delta reports (`<node_id>_delta_report.md`) are returned directly to the targeted persona role.
