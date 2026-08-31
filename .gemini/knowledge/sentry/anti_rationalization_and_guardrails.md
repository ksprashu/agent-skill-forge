---
type: "Security & Quality Policy"
title: "Anti-Rationalization Matrix, Red Flags & Definition of Done"
description: "Defensive guardrails against agent shortcuts, behavioral red flags, the Prove-It verification protocol, and the Definition of Done standard."
resource: "file:///Users/ksprashanth/code/github/agent-skills/references/definition-of-done.md"
tags: ["sentry", "anti-rationalization", "red-flags", "definition-of-done", "prove-it", "quality"]
---

# 🛑 Anti-Rationalization Matrix & Definition of Done

Defensive mechanisms for preventing AI agents from taking shortcuts, skipping verification steps, or fabricating progress.

---

## 1. The Anti-Rationalization Matrix

AI agents frequently construct plausible-sounding excuses to skip arduous validation steps. Every skill must embed explicit rebuttals against known rationalizations:

| Common Agent Rationalization | Concrete Technical Reality | Mandated Correct Behavior |
| :--- | :--- | :--- |
| *"This change is trivially small, so I can skip writing tests."* | Small changes without tests frequently introduce subtle regressions. | Write a reproducing test first regardless of size. |
| *"I will implement the feature now and add tests later."* | "Later" tests verify what was built rather than specifying requirements. | Enforce strict Test-Driven Development (Red-Green-Refactor). |
| *"I've verified the code mentally; it is guaranteed to work."* | LLM mental models fail on syntax subtleties, import paths, and runtime I/O. | Physically execute the code/test runner and inspect stdout. |
| *"I cannot run tests in this environment, so I will skip verification."* | Mock harnesses or static syntax checks (`py_compile`, `tsc`) are always available. | Run local static checks or request sandbox bypass. |
| *"The user is in a hurry, so I will skip updating the docs/plan."* | Out-of-sync documentation creates technical debt for all subsequent turns. | Synchronize `task.md`, docs, and OKF index immediately. |

---

## 2. Behavioral Red Flags

Observable indicators that an agent is violating quality standards:
- 🚩 **Unverified File Edits**: Making code modifications without running linters or compilers immediately after.
- 🚩 **Silent Assumption**: Guessing database schemas or API contracts instead of asking or inspecting files.
- 🚩 **Premature Completion**: Declaring work complete while failing tests or unaddressed tasks remain in `task.md`.
- 🚩 **Placeholder Pollution**: Leaving unfinished markers, temporary placeholders, or mock stubs in delivered production files.

---

## 3. The Definition of Done (DoD) Standard

No task is marked complete until it satisfies all 5 criteria:

1. **Specification Adherence**: 100% of functional requirements and edge cases specified in the plan are met.
2. **Automated Test Coverage**: Unit tests and BDD feature scenarios physically executed and passing.
3. **Security & Zero-PII Audit**: Clean scans from `scan_dependencies` and zero hardcoded credentials.
4. **Documentation & OKF Sync**: Markdown documentation compiled and OKF concept files updated.
5. **Verifiable Evidence**: Real execution outputs and test results logged in the final walkthrough artifact.
