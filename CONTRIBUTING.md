# 🤝 Contributing to Agent Skill Forge

We welcome contributions of high-performance, slop-free skills for AI developer tools.

---

## 📝 Authoring a New Skill

1. **Follow the Standard Structure**:
   ```
   skills/<skill-name>/
   ├── SKILL.md
   ├── references/
   └── scripts/
   ```
2. **Include Clean YAML Frontmatter**:
   ```yaml
   ---
   name: <skill-name>
   description: <concise summary of WHAT and WHEN>
   ---
   ```
3. **Zero PII Policy**:
   - Never hardcode personal usernames, real emails, or internal domains.
   - Use dynamic username resolution (`getpass.getuser()`) or generic placeholders (`user@example.com`).
4. **Validate Before Committing**:
   ```bash
   python3 scripts/validate_skills.py
   ```
