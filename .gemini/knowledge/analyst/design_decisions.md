# 📊 Design Decisions

## 1. Universal Lifecycle vs. Project Scope
- **Problem**: Loading dozens of domain-specific skills into global agent prompts wastes context tokens and degrades model accuracy with irrelevant triggers.
- **Decision**: Restrict global scope strictly to the **15 Universal Core Verbs** needed on every project. Keep all domain-specific skills in `preferred/` and bootstrap them project-scoped on demand.

## 2. 1-Word Primary Action Verbs
- **Problem**: Verbose skill names like `skills-extract-human-voice` or `expectation-harness` are clunky to type and remember.
- **Decision**: Standardize on concise, intuitive 1-word verbs (`prompt`, `grill`, `spec`, `plan`, `test`, `verify`, `review`, `unslop`, `docs`, `catalog`, `sync`, `voice`, `copy-write`, `codelab`, `google-oss`, `image-gen`) while maintaining backward-compatible aliases.

## 3. Profile-Overlay Architecture
- **Problem**: Hardcoding personal writing styles and sample emails directly in public git repos leaks PII and limits open-source reuse.
- **Decision**: Implement a 3-tier resolution engine: Gitignored Local Override (`references/*.local.md`) $\rightarrow$ User Profile (`~/.gemini/personas/default/*.md`) $\rightarrow$ Generic Template (`references/*.template.md`).
