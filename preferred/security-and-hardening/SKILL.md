---
name: security-and-hardening
description: Retired. Code-level security review moved to the security-review skill; agent, tool and infrastructure posture lives in agent-security-posture. Use security-review for OWASP, injection, secrets and dependency checks on code.
lifecycle: retired
---

# Security and Hardening (retired)

This skill has been replaced. Its OWASP checklist, threat-modelling prompts and
secrets guidance now live, updated, in two skills.

- **`security-review`** (core skill, `/security-review`): code-level security
  review of a diff, a PR or a repository.
  - It runs the installed scanners: semgrep, gitleaks, osv-scanner, trivy,
    actionlint, zizmor and the native dependency audits.
  - It triages every lead with an exploitability test.
  - It reviews against OWASP Top 10 2025, ASVS 5, CWE Top 25 and the OWASP
    cheat sheets.
  - It emits findings in the shared JSON contract.
- **`agent-security-posture`**: secure behaviour during agent coding sessions,
  agent tool and MCP permissions, live CVE checks on lockfiles, and read-only
  infrastructure audits.

**What to do:** if `security-review` is installed, use it now. In a forge
checkout it is at `skills/security-review/SKILL.md`. If it is not installed, it
ships in the core set; install it with the forge installer, for example
`bash scripts/install.sh --clusters c2`.

This folder is kept only so that existing installs, catalogs and the `work`
domain autowiring do not point at a missing path.
