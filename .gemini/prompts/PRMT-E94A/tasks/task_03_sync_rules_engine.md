# Task 03: Implement Semantic Rule Sync & 200-Line Budget Enforcer

## Objective
Implement `skills/continuous-alignment/scripts/sync_agents_rules.py` to synchronize extracted rules into `AGENTS.md` and `.agents/rules/*.md`.

## Key Capabilities
1. Merge new rules with existing rules, resolving conflicts and invalidating superseded rules.
2. Maintain root `AGENTS.md` under a strict 200-line (~1,500 token) budget limit.
3. Automatically route path-scoped rules to `.agents/rules/<subsystem>.md` when touched.
4. Support `--pulse` mode for the `PreInvocation` hook to output active workspace invariants.
