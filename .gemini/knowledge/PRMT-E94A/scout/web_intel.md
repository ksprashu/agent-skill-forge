# PRMT-E94A: Web Intelligence & Industry Best Practices Report

## 1. Executive Summary & Industry Landscape
As AI pair programming shifts from single-turn autocomplete to autonomous, multi-turn agentic workflows (Cursor, Windsurf, Claude Code, Aider, Antigravity), context management is the central operational bottleneck. Naive context ingestion (dumping thousands of lines into prompts) causes **attention dilution**, **reasoning degradation**, and context rot.

5 foundational pillars define modern agentic context lifecycles:
1. **Continuous Context Synchronization**: Background AST/LSP semantic daemons, Git-aware state stacks, and MCP feeds.
2. **Dynamic `AGENTS.md` Generation**: Lean, bootstrapped project profiles prioritizing front-loaded commands, negative constraints, and hierarchical proximity cascading.
3. **Living ADRs & Drift Detection**: Event-driven MADR drafting on PR boundaries, automated drift classification (`Compliant`, `Not Compliant`, `Code Insufficient to Answer`), and CI/CD Decision Guardians.
4. **Memory Distillation from Transcripts**: Cognitive transformation of episodic execution transcripts into durable semantic rules and procedural playbooks via reflection loops (Reflexion, NEMORI, HeLa-Mem) and prediction-error filtering.
5. **Token Budget Management for Agent Instructions**: Multi-tiered progressive disclosure, prompt cache prefix stabilization, 50–60% compaction triggers, filesystem spillover, and subagent firewalls.

---

## 2. Dynamic `AGENTS.md` & Rule Synchronization Architecture
- **Hierarchical Cascading**: Global root conventions (`AGENTS.md`) cascaded into subfolder path-scoped rules (`.agents/rules/*.md`).
- **Anatomy of High-Yield Instructions**:
  1. Front-loaded executable commands (build, test, lint).
  2. Negative constraints (banned patterns, security rules).
  3. Domain-specific invariants & gotchas.
  4. Module pointers rather than full tree listings.
- **Budget Enforcer**: Root `AGENTS.md` capped at strict line budgets (e.g. 200 lines / ~2,000 tokens) with automatic spillover to `.agents/rules/` or `.gemini/knowledge/`.

---

## 3. Cognitive Memory Distillation Pipeline
- **Episodic Store**: Raw session transcripts (`transcript.jsonl`) captured in background.
- **Surprise-Based Distillation (NEMORI/Reflexion)**: Routine actions are ignored; unexpected errors, workarounds, or user-supplied corrections trigger semantic distillation.
- **Truth Maintenance & Conflict Invalidation**: When new rules contradict obsolete patterns, the engine deprecates/replaces legacy rules rather than creating duplicate contradictory directives.
- **Output Artifacts**: Structured semantic markdown rules and living ADRs in version-controlled directories.
