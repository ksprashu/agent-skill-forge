# 🧹 Unslop Skill (Anti-Bloat & Connected Prose Engine)

Strips AI smells, promotional bloat, and needless words from human-readable text - technical dossiers, post-planning readouts, architecture reports, prose, docs, code comments, commit messages, analyses, emails, and UI copy - while keeping natural, connected cause-and-effect sentence flow. It leaves executable code logic alone.

---

## ✨ Default Behaviour vs. Personal Voice Integration

- **Public Neutral Default (`tier 3`)**: Out of the box, `unslop` is completely persona-neutral. It strips AI throat-clearing and promotional filler, enforces connected cause-and-effect sentences (`18-30 words` linked by `"because"`, `"whereas"`, `"so that"`, `"which means"`, or `" - "` rather than robotic 10-word staccato fragments), and preserves your existing regional spelling and punctuation.
- **Automatic [`voice-register`](../voice-register) Integration (`tier 1` / `tier 2`)**: When you configure a personal voice profile (either locally or via `AGENT_PERSONA_REPO=<owner>/agent-persona`), `unslop` automatically applies that profile's spelling, punctuation, and channel register rules across outward communications (`R1`-`R5`) and technical dossiers/readouts (`R6`).

---

## 👤 Attribution & Lineage
*   **Original Inspirations & Lineage**:
    *   **Matt Pocock**: Author of [`deslop`](https://github.com/mattpocock/skills/tree/main/skills/deslop) (*"Cut AI tells from any writing"*)
    *   **poteto / Cursor pstack**: Creator of [`poteto/unslop`](https://github.com/poteto) and [`cursor/plugins/pstack`](https://github.com/cursor/plugins/tree/main/pstack) (*Code & content anti-bloat engine*)
*   **Adapted, Unified & Curated by**: Prashanth Subrahmanyam ([@ksprashu](https://github.com/ksprashu)) for `agent-skill-forge`
*   **License**: Apache-2.0 / MIT
