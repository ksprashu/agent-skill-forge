---
name: work
description: Verifier fixture for the dispatch-brief lint.
disable-model-invocation: true
---

# work (fixture)

Each brief below breaks one rule. validate_skills.py must exit non-zero here.

Ungrounded (W-07):

```json
{
  "Subagents": [
    {
      "Role": "Acceptance Reviewer",
      "Prompt": "Audit .agents/SPEC.md."
    }
  ]
}
```

Restates instead of citing (W-08):

```json
{
  "Subagents": [
    {
      "Role": "5-Axis Code Reviewer",
      "Prompt": "Grounding: read the relevant subtrees of .gemini/knowledge/ first (see skills/catalog/SKILL.md).\nCheck correctness, security, performance, architecture and readability."
    }
  ]
}
```

No prompt at all:

```json
{
  "Subagents": [
    {
      "Role": "Adversarial Challenger"
    }
  ]
}
```

A role nobody decided the grounding for:

```json
{
  "Subagents": [
    {
      "Role": "Freelance Optimiser",
      "Prompt": "Grounding: read the relevant subtrees of .gemini/knowledge/ first (see skills/catalog/SKILL.md).\n"
    }
  ]
}
```
