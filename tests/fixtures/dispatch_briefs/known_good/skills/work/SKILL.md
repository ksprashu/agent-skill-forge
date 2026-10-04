---
name: work
description: Verifier fixture for the dispatch-brief lint.
disable-model-invocation: true
---

# work (fixture)

Every brief below meets its contract in BRIEF_CONTRACTS.

```json
{
  "Subagents": [
    {
      "Role": "5-Axis Code Reviewer",
      "Prompt": "Grounding: read the relevant subtrees of .gemini/knowledge/ first (see skills/catalog/SKILL.md).\nRead skills/review/SKILL.md and skills/unslop/SKILL.md."
    },
    {
      "Role": "Adversarial Challenger",
      "Prompt": "Grounding: read the relevant subtrees of .gemini/knowledge/ first (see skills/catalog/SKILL.md).\nFollow skills/test/SKILL.md."
    },
    {
      "Role": "Victory Auditor",
      "Prompt": "Run the terminal gate cold, from a clean checkout."
    }
  ]
}
```
