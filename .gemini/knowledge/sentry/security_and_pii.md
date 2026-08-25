# 🛡️ Sentry & Security Guidelines

## Zero-PII Mandate
- Never commit private email addresses, personal names, internal corp domains, or machine usernames.
- Scripts must use dynamic system lookups: `getpass.getuser()` or `os.getlogin()`.
- Sample examples must use generic documentation domains: `example.com`, `corp.internal`, `user@example.com`.

## Gitignore Rules for Personal Profiles
All private personalization files must follow the pattern `*.local.md` and be ignored in `.gitignore`:
```gitignore
*.local.md
references/*.local.md
output/
__pycache__/
```
