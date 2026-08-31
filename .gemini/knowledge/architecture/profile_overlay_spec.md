---
type: "Architecture Spec"
title: "3-Tier Profile-Overlay Personalization Engine"
description: "Specification for hierarchical persona resolution across gitignored local overrides, user home profiles, and sanitized templates."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/skills/copy-write/SKILL.md"
tags: ["architecture", "profile-overlay", "personalization", "security", "pii-isolation"]
---

# 🎭 3-Tier Profile-Overlay Personalization Engine

Architecture and resolution semantics for the Profile-Overlay pattern used in writing and voice skills (`copy-write`, `voice`).

---

## 1. The Personalization Challenge

Technical writing and communication skills (`/copy-write`) produce drastically higher-quality output when conditioned on authentic human voice markers, past writing samples, and preferred cadences. However, hardcoding personal style samples directly into public git repositories leaks Personally Identifiable Information (PII) and prevents open-source collaboration.

---

## 2. 3-Tier Resolution Engine

The Profile-Overlay engine resolves stylistic context dynamically at execution time following a strict hierarchical fallback:

```
                  ┌─────────────────────────────────────┐
                  │ Writing Request (/copy-write, etc.) │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 1. Local Workspace Override             │
                │ Check: `references/*.local.md`          │
                └───────┬─────────────────────────┬───────┘
                        │ Found                   │ Not Found
                        ▼                         ▼
            ┌──────────────────────┐  ┌───────────────────────────────────────┐
            │ Apply Local Persona  │  │ 2. User Home Profile                  │
            │ (Gitignored Private) │  │ Check: `~/.gemini/personas/default/`  │
            └──────────────────────┘  └───────┬───────────────────────┬───────┘
                                              │ Found                 │ Not Found
                                              ▼                       ▼
                                  ┌──────────────────────┐  ┌───────────────────┐
                                  │ Apply Home Profile   │  │ 3. OSS Template   │
                                  │ (User Machine Level) │  │ (Sanitized Fall-  │
                                  └──────────────────────┘  │  back Template)   │
                                                            └───────────────────┘
```

---

## 3. Tier Specifications

1. **Tier 1 (Gitignored Local Override)**:
   - File pattern: `references/*.local.md` (e.g., `references/style.local.md`, `references/samples.local.md`).
   - Priority: Highest.
   - Purpose: Project-specific author voice or sensitive corporate briefs.
   - Security: Must be matched by `.gitignore` in all repositories.

2. **Tier 2 (User Home Profile)**:
   - Location: `~/.gemini/personas/default/*.md` or `~/.config/agent-personas/default/*.md`.
   - Priority: Intermediate.
   - Purpose: Global developer identity across all workspaces on a local machine.
   - Security: Stored strictly in local user home directory, never committed to git.

3. **Tier 3 (Sanitized Open-Source Template)**:
   - File pattern: `references/*.template.md` (e.g., `references/style.template.md`).
   - Priority: Baseline Fallback.
   - Purpose: Clean, high-quality, zero-PII default template allowing any open-source contributor to use the skill immediately.
