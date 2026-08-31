# PRMT-E94A: Analyst Stage Specification & BDD Scenarios

## 1. Problem Formulation & Core Persona Needs
Developers working in complex, fast-moving codebases face rapid context drift:
- Architectural decisions made during conversations get lost in transcripts.
- Project instructions (`AGENTS.md` / `GEMINI.md`) grow stale or bloat beyond context budget limits.
- Rules become contradictory or fragmented across multiple subdirectories.
- Vision and roadmap milestones evolve during development but are not updated in living documentation.

### Core Solution
An automated **Continuous Alignment & Project Evolution Engine** (`continuous-alignment` skill + Antigravity `Stop` / `PreInvocation` hooks) that:
1. Distills transcripts into structured semantic rules, avoiding duplicates and noise.
2. Maintains `AGENTS.md` within a strict 200-line budget limit with path-scoped rule spillover.
3. Compiles living ADRs, roadmap milestones (`docs/ROADMAP.md`), and vision declarations (`docs/VISION.md`).
4. Generates rich visual HTML/SVG project dashboards synchronized at the end of every turn.

---

## 2. BDD Gherkin Feature Specifications

```gherkin
Feature: Continuous Context Alignment and Rule Evolution
  As an AI software engineering agent
  I want my workspace instructions and architectural memory to continuously evolve
  So that future agent turns remain strictly aligned with verified project truths.

  Scenario: Distilling learning from session transcripts on turn completion
    Given an agent has completed a development turn with 3 file edits and 1 test failure resolution
    When the Antigravity "Stop" lifecycle hook executes "distill_session.py"
    Then the script parses the session transcript JSONL
    And extracts newly verified architectural invariants, constraints, and test patterns
    And updates the semantic memory catalog without duplicating existing entries.

  Scenario: Enforcing line budget and path scoping on AGENTS.md
    Given the root "AGENTS.md" file has reached 195 lines
    When new rules specific to "skills/docs-sync" are discovered
    Then the sync engine routes the subproject rules to ".agents/rules/docs-sync.md"
    And preserves the root "AGENTS.md" under the 200-line token budget cap.

  Scenario: Reconciling contradictory architectural decisions
    Given an existing rule mandates "Use SQLite for metadata storage"
    When the developer explicitly refactors and confirms "Switch to JSONL flat files for zero-dependency portability"
    Then the memory engine invalidates the SQLite rule
    And records an Architectural Decision Record (ADR) capturing the superseding rationale.
```
