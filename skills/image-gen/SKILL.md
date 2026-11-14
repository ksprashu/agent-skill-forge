---
name: image-gen
description: Generate and verify technical diagrams, infographics, styled illustrations, multi-panel comic grids, character sheets, and sequential storyboard/timeline frames via the official gemini-api CLI. Use when visual assets, diagrams, comics, or video keyframes are needed, or trigger via /image-gen.
---

# Image-Gen: Closed-Loop Visual & Sequential Asset Synthesis

Generate verified PNG, JPEG, and WebP visual assets using a zero-dependency Python 3.12 controller around the official `gemini-api` CLI (`https://aistudio.google.com/docs/cli`). Every run compiles a frozen `VisualRequirementSpec`, generates via `gemini-nano-banana-2.1` or `gemini-3-pro-image`, checks binary image headers deterministically, and audits visual compliance through a stateless blinded `gemini-4-argon` rubric judge before writing `--output`.

---

## Preflight & Readiness Check

Run `--doctor` before a batch if `gemini-api` readiness or authentication is uncertain:

```bash
python3 <skill-dir>/scripts/image_gen.py --doctor
```

- Verifies `gemini-api --version` and `gemini-api whoami -o json`.
- Warns if `GEMINI_API_KEY` is set in the environment and could shadow OS keyring credentials stored by `gemini-api auth login`.
- To bootstrap missing CLI tools in a forge checkout, run `bash scripts/install.sh --with-media-tools` (or `pwsh scripts/install.ps1 -WithMediaTools`).

---

## Workflow

### 1. Select Mode, Aspect Ratio, and Resolution Tier
Read `references/aspect_ratio_cheatsheet.md` when choosing among the 14 supported aspect ratios (`1:1` through `8:1`), sizing tiers (`1K`, `2K`, `4K`), and craft modes:

| `--mode` | Best For | Automatic Safeguards |
| :--- | :--- | :--- |
| `auto` | General requests (infers mode from prompt cues) | Routes diagrams, comic grids, and timelines automatically |
| `single` | Hero banners, spot illustrations, icons, portraits | `gemini-nano-banana-2.1` primary with quota failover |
| `diagram` | Architecture flows, topologies, schematics, charts | `thinking_level: "high"`, crisp connectors, zero pseudo-labels |
| `comic-grid` | Single-image `2x2`, `1x3`, or `1x4` comic strips | Auto-promotes `gemini-3-pro-image` and enforces `>= 2K` floor |
| `comic-panels` | Multi-file sequential comic frames with anchor lock | Conditions Frame `k+1` on `[anchor, frame_k]`; writes manifest |
| `timeline` | Step-by-step progressions & storyboard sequences | Emits `keyframes_manifest.json` with per-frame metadata |

### 2. Compose the Prompt & Reference Bindings
Read `references/prompt_recipes.md` when drafting art-direction prompts for 1-shot styles, noir or ligne-claire comic grids, sequential panels, timelines, architecture diagrams, or turnaround character sheets.

- Wrap exact required labels, titles, or speech-bubble lines in quotes (`"API Gateway"`, `"Ship it!"`). Quoted literals are extracted into mandatory `AC-*` checks and protected against prompt-expansion drift.
- Attach up to 14 reference images via repeatable `-r` / `--reference` (or comma-separated `--references`) with optional role tags: `char:hero.png`, `style:palette.png`, `prop:device.png`, `anchor:frame0.png`.
- Assets larger than 12 MB or reused across retries/frames are uploaded once via `gemini-api files upload <path> --wait` and referenced by `files/<id>`.

### 3. Execute Closed-Loop Generation

#### Single Diagram or Hero Illustration
```bash
python3 <skill-dir>/scripts/image_gen.py \
  --prompt 'Orthographic cloud mesh diagram with boxes "Ingress Gateway" and "Policy Engine"' \
  --mode diagram \
  --style "clean dark-mode isometric vector" \
  --ar 16:9 \
  --output docs/assets/mesh_flow.png
```

#### Multi-Panel Comic Grid (`2K` Auto-Promoted)
```bash
python3 <skill-dir>/scripts/image_gen.py \
  --prompt '2x2 comic strip: panel 1 "Tests pass locally", panel 2 "Push branch", panel 3 "CI linter fails", panel 4 "Fixed in two lines"' \
  --mode comic-grid \
  --style "ligne claire comic, flat cel shading" \
  -r char:assets/dev_sheet.png \
  --ar 1:1 \
  --output docs/assets/ci_comic.png
```

#### Multi-Frame Sequential Series (`--manifest`)
```bash
python3 <skill-dir>/scripts/image_gen.py \
  --manifest specs/release_timeline.json \
  --manifest-out build/keyframes_manifest.json \
  --output build/timeline_run
```

#### Surgical Conversational Edit Turn
```bash
python3 <skill-dir>/scripts/image_gen.py \
  --prompt 'Keep everything else the same. Change the "Policy Engine" node border from cyan to amber.' \
  --previous-interaction-id v1_prev_turn_id \
  --raw-prompt \
  --ar 16:9 \
  --output docs/assets/mesh_flow_v2.png
```

---

## CLI Flag Reference

- `--prompt`: Text prompt (required unless `--spec-file`, `--manifest`, `--verify-only`, or `--doctor` is used).
- `--spec-file`: Pre-compiled `VisualRequirementSpec` JSON path.
- `--mode`: `{auto,single,diagram,comic-grid,comic-panels,timeline}` (default: `auto`).
- `--style`: Art-direction string applied to prompt compilation and rubric criteria.
- `-r`, `--reference`, `--references`: Reference image path or `role:path` (repeatable or comma-separated, max 14).
- `--ar`: `{1:1,2:3,3:2,3:4,4:3,4:5,5:4,9:16,16:9,21:9,1:4,4:1,1:8,8:1}` (default: `1:1`).
- `--size`: `{1K,2K,4K}` (default: `1K`; upgraded to `2K` for `comic-grid` or dense quoted text).
- `-o`, `--output`: Destination image path (or directory for `--manifest`; default: `output.png`). If binary output MIME differs from the requested suffix, `image_gen.py` rewrites the file suffix via `MIME_TO_EXT`, removes any stale requested-suffix artefact, and records `requested_output` in provenance.
- `--manifest`, `--manifest-out`: Input sequence JSON and output `keyframes_manifest.json` path.
- `--previous-interaction-id`: Prior `response_id` for multi-turn edits.
- `--model`: Primary generator override (`gemini-nano-banana-2.1` default; `gemini-3-pro-image` for grids/dense text). Deprecated or shut-down model prefixes (`DEPRECATED_MODEL_PREFIXES` in `scripts/image_gen.py`) exit `2`.
- `--verifier-model`: Blinded judge override (`gemini-4-argon` -> `gemini-4-carbon` -> `gemini-3.8-flash`).
- `--max-attempts`: Closed-loop retry ceiling (default: `3`).
- `--raw-prompt` / `--expand-prompt`: Disable or enable Argon prompt expansion before Attempt 1.
- `--no-verify`: Skip Stage 4 multimodal rubric judge while keeping Stage 3 binary header verification active.
- `--allow-unverified`: Require `--override-reason "<why>"` (`exit 2` if omitted); writes `--output` with a loud `stderr` `WARNING`, `.report.json`, and `UNVERIFIED_OVERRIDE` provenance if retries exhaust (otherwise failed runs save `<stem>.rejected<ext>` + `<output>.report.json` and exit `1`).
- `--override-reason`: Mandatory non-empty justification string recorded in `<output>.report.json` and `<output>.provenance.json` when `--allow-unverified` is set (`ENGINEERING_STANDARD.md` §9).
- `--dry-run`: Validate arguments, compile `spec`, and print planned CLI JSON with zero network calls.
- `--verify-only`, `--rubric-file`: Offline verification of an existing image file against `--ar`/`--size`/`--spec-file`.

---

## Hard Invariants

- **Never** pass shut-down or deprecated model IDs (all prefixes in `DEPRECATED_MODEL_PREFIXES` exit `2`); let default routing select active models.
- **Never** generate multi-image series without reference grounding (`-r` or `--manifest`); unreferenced follow-up frames drift in palette and character geometry.
- **Never** treat an exit code `1` `.rejected` image as publishable output; inspect `<output>.report.json`, adjust constraints or prompt clarity, and re-run.
