# 🧪 Codelab Creator Skill

End-to-end Google Codelab tutorial authoring, multi-modal instruction generation, and deterministic quality validation.

By default, `codelab` generates clean, mascot-free developer tutorials using standard Google Codelab callouts (`> aside positive` **"Tip:"** and `> aside negative` **"Watch out:"**), validated against `scripts/validate_codelab.cjs` and `scripts/fog.cjs` (target Gunning Fog `< 12.0`).

---

## 🎭 Bring Your Own Characters (Optional)

If your team or series uses recurring companion characters (for example an enthusiastic builder paired with a systems debugger), you can plug a private or project-scoped character pack into `codelab` without modifying this repository:

1. **Create a character pack** matching [`references/characters.schema.json`](./references/characters.schema.json) (see the fictional Pip & Byte template at [`examples/characters.example/characters.json`](./examples/characters.example/characters.json)):
   ```text
   ~/.gemini/personas/default/characters/
   ├── CHARACTER_BIBLE.md       # Optional tone, likeness & visual prompt guide
   ├── characters.json          # Required schema-validated character definitions
   ├── icons/                   # Optional circular aside badges (e.g. pip-idea.png)
   └── common-comics/           # Optional 4-panel setup comics (e.g. activate_billing_comic.png)
   ```
2. **Point `codelab` at your pack** (either place it under `~/.gemini/personas/default/characters/` via your persona repository, or set `CODELAB_CHARACTERS_DIR=/path/to/pack` for a single project). You can also set `CODELAB_AUTHOR="Your Name"` to populate frontmatter automatically during scaffolding.
3. **Verify resolution**:
   ```bash
   node scripts/characters.cjs status
   ```
   - **Exit `0` (`tier: character-pack`)**: Prints `characters_dir`, `companion_theme`, character roles/icons, and `comics` paths so the agent incorporates your companions automatically.
   - **Exit `1` (`tier: neutral`)**: No pack installed; `codelab` stays mascot-free.
   - **Exit `2`**: Malformed JSON or schema error in `characters.json`.

---

## 👤 Attribution & Lineage
*   **Original Author & Architect**: Prashanth Subrahmanyam ([@ksprashu](https://github.com/ksprashu))
*   **Design Framework**: Visual-First storytelling, Doc-Driven Vibe Coding, and Apache-2.0 compliance.
*   **License**: Apache-2.0
