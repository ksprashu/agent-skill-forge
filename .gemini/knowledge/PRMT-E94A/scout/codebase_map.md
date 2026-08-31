# PRMT-E94A: Codebase Structural Map & Existing Lifecycle Assets

## 1. Repository Topology: `agent-skill-forge`
The repository is the central authority for canonical agent skills and lifecycle tools.

```
agent-skill-forge/
├── .gemini/
│   ├── knowledge/       # OKF knowledge base & concept documents
│   ├── prompts/         # Prompt registry and modular decks
│   └── tasks/           # Active tasks & state journals
├── preferred/           # Curated domain-specific skills (JIT bootstrapped)
├── scripts/
│   ├── install.sh       # Universal installer
│   ├── sync_skills.py   # Canonical symlink manager across IDE/CLI hubs
│   └── validate_skills.py # Linter & PII verifier
├── skills/              # 16 Core Global Action-Verb Skills
│   ├── catalog/         # OKF tree structuring & indexing
│   ├── codelab/         # Step-by-step interactive codelab creation
│   ├── copy-write/      # Clear concise technical copywriting
│   ├── docs/            # HTML presentation portal compiler (Tailwind)
│   ├── google-oss/      # Open-source hygiene & compliance
│   ├── grill/           # Socratic questioning engine
│   ├── image-gen/       # Image generation prompt engineering
│   ├── plan/            # DAG dependency decomposition
│   ├── prompt/          # Intent engineering & Prompt-Writer meta-skill
│   ├── review/          # Multi-persona code review
│   ├── spec/            # BDD / SDD formal specification
│   ├── sync/            # Global & project skill synchronization
│   ├── test/            # TDD & BDD test harness enforcement
│   ├── unslop/          # AI boilerplate removal
│   ├── verify/          # Deterministic static verification
│   └── voice/           # Voice & tone adaptation
└── docs/                # Project documentation suite
```

## 2. Integration Points for New Skill (`continuous-alignment` / `orbit`)
- **Location**: `skills/continuous-alignment/` (or `skills/orbit/` / `skills/evolve/`).
- **Core Files**:
  - `SKILL.md`: Frontmatter with trigger commands (`/align`, `/evolve`, `/prune-memory`).
  - `scripts/distill_session.py`: Primary Antigravity Stop hook handler.
  - `scripts/sync_agents_rules.py`: Semantic rule merge, deduplication, and `AGENTS.md` updater.
  - `scripts/compile_project_memory.py`: Master memory hub and SVG visualizer.
  - `tests/test_distill_session.py`: Deterministic test suite for transcript parsing and rule extraction.
  - `features/continuous_alignment.feature`: BDD Gherkin test suite.
- **Hook Integration**:
  - `.agents/hooks.json` or `.gemini/hooks.json` registering `Stop` and `PreInvocation` events.
