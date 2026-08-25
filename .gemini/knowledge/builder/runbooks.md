# 🔨 Builder Runbooks

## Runbook 1: Validating Skills & Checking PII
```bash
python3 scripts/validate_skills.py
```

## Runbook 2: Synchronizing Global Symlinks
```bash
python3 scripts/sync_skills.py --prune --fix
```

## Runbook 3: Compiling Documentation Portals
```bash
python3 skills/docs/scripts/compile_docs.py --dir ./docs
python3 skills/docs/scripts/compile_docs.py --file ./README.md
```
