---
type: "Security Policy"
title: "Zero-PII Sanitization & Security Isolation Policy"
description: "Zero-PII compliance rules, dynamic runtime username lookups, regex security audits, and gitignore isolation."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/SECURITY.md"
tags: ["sentry", "security", "pii", "sanitization", "policy"]
---

# 🛡️ Zero-PII Sanitization & Security Isolation

Security policies, PII elimination rules, and isolation patterns governing **Agent Skill Forge**.

---

## 1. Zero-PII Mandate

To maintain complete open-source safety and prevent personal data leakage:
- **No Hardcoded Usernames or Paths**: Never hardcode machine usernames or private home directory paths in committed scripts or documentation.
- **Dynamic System Resolution**: Scripts requiring user identity or home directory resolution must use runtime lookups:
  ```python
  import getpass
  import os
  
  username = getpass.getuser()
  home_dir = os.path.expanduser('~')
  ```
- **Generic Documentation Placeholders**: Sample domains and mock emails in fixtures must strictly use RFC-standardized or generic names (`example.com`, `user@example.com`, `corp.internal`).

---

## 2. Automated Regex Linter Guardrails

The repository presubmit suite (`scripts/validate_skills.py`) automatically evaluates all skills against PII regex patterns:

```python
PII_PATTERNS = [
    re.compile(r'ksprashanth@', re.IGNORECASE),
    re.compile(r'ksprashu@', re.IGNORECASE),
    re.compile(r'Prashanth Subrahmanyam', re.IGNORECASE),
]
```

Any un-ignored match in skill instructions or code produces an immediate presubmit build failure.

---

## 3. Gitignore Isolation Rules for Profile Overlays

Personal user styles and sensitive writing samples must be stored exclusively in gitignored overlay paths:

```gitignore
*.local.md
references/*.local.md
output/
__pycache__/
.DS_Store
```
