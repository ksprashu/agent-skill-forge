# Image-Gen Skill

Closed-loop technical diagram, infographic, comic grid, character sheet, and sequential storyboard generator built on Python 3.12 stdlib and the official `gemini-api` CLI (`https://aistudio.google.com/docs/cli`).

## Capabilities

- **Zero Python package dependencies:** Runs on bare Python 3.12 stdlib with pure-Python PNG (`IHDR`), JPEG (`SOF0`), and WebP (`VP8X`/`VP8`/`VP8L`) binary header verification.
- **Active model routing:** Uses `gemini-nano-banana-2.1` and `gemini-3-pro-image` (auto-promoted for comic grids and dense quoted text) with `429`/`503` failover and hard parse-time rejection of shut-down models.
- **Blinded multimodal rubric verification:** Audits every candidate with `gemini-4-argon` (`store: false`, `thinking_level: high`) against a frozen `VisualRequirementSpec` (`spec.json`) and writes `<output>.provenance.json`.
- **Sequential continuity (`--manifest`):** Synthesizes or locks an anchor image, conditions each frame on `[anchor, previous_frame]`, and outputs `keyframes_manifest.json` for downstream storyboard workflows.

## Quick Verification

```bash
python3 skills/image-gen/scripts/image_gen.py --doctor
python3 -m pytest -q skills/image-gen/tests
```

## License

- **Contributors**: Agent Skill Forge Contributors
- **License**: Apache-2.0
