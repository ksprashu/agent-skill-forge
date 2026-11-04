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
2. **Include Clean YAML Frontmatter** in the [`npx skills`](https://github.com/vercel-labs/skills) format:
   ```yaml
   ---
   name: <skill-name>          # kebab-case, must match the folder name
   description: <concise summary of WHAT and WHEN>
   license: Apache-2.0         # optional
   metadata:                   # optional
     internal: true            # repo-maintenance skills only; hides them from `npx skills add`
   ---
   ```
   Don't add harness-specific keys (`allowed-tools`, `disable-model-invocation`, and the like) or reference a tool by one harness's name as the only option. Skills must work in every harness.
3. **Make the Skill Self-Contained**: `npx skills add` installs only the skill's folder. Bundle scripts under `scripts/` and call them as `python3 <skill-dir>/scripts/<name>.py`, never by a repo-relative path such as `skills/<name>/scripts/...`.
4. **Link It for In-Repo Discovery**: keep the canonical copy in `skills/` and symlink it rather than duplicating files:
   ```bash
   ln -s ../../skills/<skill-name> .claude/skills/<skill-name>
   ln -s ../../skills/<skill-name> .agents/skills/<skill-name>
   ```
5. **Pick the Right Home**: `skills/` holds skills this repo owns. `preferred/` vendors curated domain skills listed in `preferred/catalog.json`. Third-party skills that are tracked upstream are pinned in `config/upstream.lock.json` (with any local additions in `overlays/`) and fetched by `scripts/fetch_upstream.py`, never copied in.
6. **Zero PII Policy**:
   - Never hardcode personal usernames, real emails, or internal domains.
   - Use dynamic username resolution (`getpass.getuser()`) or generic placeholders (`user@example.com`).
7. **Validate Before Committing**:
   ```bash
   python3 scripts/validate_skills.py
   python3 -m pytest -q
   npx skills add . --list    # confirm the skill is discovered (and internal ones are hidden)
   ```

Read [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) before adding a script, verifier, gate or test. It defines the script and verifier contracts, the required test patterns and the definition of done. [`docs/skill_authoring_guide.md`](docs/skill_authoring_guide.md) covers writing the skill itself.

---

## 🔀 Submitting Changes

1. Work on a branch; `main` only accepts changes through a pull request.
2. Open a PR with `gh pr create`. CI runs the test suite, skill validation, gate and DAG integrity checks, the forensic audit corpus and an installer smoke test.
3. The automated reviewer (pr-guardian) posts findings as review threads. Fix each one or reply with evidence; the `pr-guardian/verdict` check stays red until every P0-P3 thread is closed, and every conversation must be resolved before merge.
4. Use conventional commit messages (`fix(sync): ...`, `feat(review): ...`, `docs: ...`).
