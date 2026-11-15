# Grounded Image Generation & Verification Specification (`image-gen`)

Status: approved
Slug: image-gen-cli
Path: architectural
Date: 2026-11-14

---

## 1. Problem Statement & Objectives

`skills/image-gen` previously relied on `google-genai` and `Pillow`, defaulted to `gemini-3.1-flash-image` (shut down on 2026-10-29), called legacy `generateContent` endpoints, used an image-generation model as its own vision judge, verified retries against a mutated prompt, saved unverified images with exit code `0`, and shipped zero tests. Meanwhile, the repository carried stale model tier strings (`flash_medium`, `gemini-3-pro-image-preview`, reviewer `flash`) across skill configs.

This specification replaces the SDK image script with a **Python 3.12 stdlib-only controller driving the official `gemini-api` CLI** (`https://aistudio.google.com/docs/cli`), upgrades `skills/image-gen` to cover full visual and sequential storytelling workflows, enforces a two-layer mechanical + blinded multimodal verification loop, adds opt-in `--with-media-tools` bootstrapping to the installers, and removes deprecated model references across repository configs.

### Explicit Non-Goals
- **No shared runtime library outside the skill directory:** Per the `npx skills` standalone invariant (`AGENTS.md`), `skills/image-gen` must execute solely from `<skill-dir>/scripts/...` when installed individually without the monorepo checkout.
- **No unprompted binary installation or `sudo` invocation:** Default `install.sh` and `install.ps1` runs never download third-party binaries or elevate privileges; binary bootstrapping occurs strictly behind `--with-media-tools`.
- **No internal corporate URLs:** All tracked documentation, CLI help text, and error hints reference public `https://aistudio.google.com/docs/...` endpoints only.

---

## 2. Active Model Routing & Deprecation Fence

All deprecated and shut-down model IDs are rejected at argument-parse time (`exit 2`) with an explicit replacement hint. Every role defines an active primary model and an ordered `429`/`503` quota-failover chain:

| Capability Role | Primary Model | Ordered Backup Chain (`429` / `503` Failover) | Routing & Constraint Rules | Hard-Blocked Deprecated IDs (`exit 2`) |
| :--- | :--- | :--- | :--- | :--- |
| **Image Gen - Standard, Style, Character Refs & Timelines** | `gemini-nano-banana-2.1` | `gemini-3-pro-image` -> `gemini-3.1-flash-lite-image` *(1-shot unreferenced only)* | Drops `gemini-3.1-flash-lite-image` whenever references `> 0`, panels `> 1`, or quoted text exists. | `gemini-3.1-flash-image`, `gemini-3-pro-image-preview`, `gemini-2.5-flash-image`, `imagen-*`, `veo-2*`, `veo-3.1*`, `gemini-omni-flash-preview` |
| **Image Gen - Multi-Panel Comic Grids & Dense Infographics** | `gemini-3-pro-image` *(or `gemini-nano-banana-2.1` with `thinking_level: high`)* | `gemini-nano-banana-2.1` (`thinking_level: high`) | Enforces `--image-size 2K` minimum (or `4K`) so panel speech bubbles and labels stay legible; never falls back to `lite`. | Same as above |
| **Blinded Multimodal Verifier & Prompt Repair** | `gemini-4-argon` | `gemini-4-carbon` -> `gemini-3.8-flash` *(emergency total-outage fallback only, logs `stderr` warning)* | Invoked via `gemini-api generate --stream=false -o json` with `thinking_level: high` and `store: false`. | `gemini-3.1-flash-image`, `gemini-3.1-pro*`, `gemini-2.5-*`, `gemini-2.0-*`, `gemini-1.5-*` |
| **Repo Subagent & DAG Configs (`prompt`, `verify`)** | `"inherit"` / `"pro"` | `"flash"` *(mechanical scouts/runners only, never reviewers)* | Replaces invalid `"flash_medium"` in `skills/prompt/references/dag_templates/*.json` and `example_dag_deck/task_graph.json`, and replaces `"Model": "flash"` reviewer specimen in `skills/verify/references/persona_roles.md` per `ENGINEERING_STANDARD.md` §10.5. | `"flash_medium"` |

---

## 3. Closed-Loop Pipeline Architecture (`skills/image-gen`)

`skills/image-gen/scripts/image_gen.py` implements the four-stage evidence/judgement split (`ENGINEERING_STANDARD.md` §3 `S9`):

### Stage 1: Intent Expansion & Frozen Requirement Spec (`spec.json`)
Before calling the generator, the script compiles (or loads via `--spec-file`) an immutable `VisualRequirementSpec` JSON object:
- **`explicit_constraints`**: Exact user-stated subjects, subject counts, quoted text literals (`"..."`), aspect ratio, resolution floor, and reference asset bindings.
- **`implicit_constraints`**: Medium-specific craft defaults injected deterministically from `--mode` and `--style`:
  - `comic-grid`: Explicit panel count and grid geometry (`2x2`, `1x3`, `1x4`), clear gutters/borders, left-to-right top-to-bottom reading order, high-contrast speech bubbles, locked character traits across panels, `>= 2K` output floor.
  - `comic-panels` / `timeline`: Canonical style/character anchor lock, consistent horizon/lighting progression across frames `1..N`, per-frame continuity delta.
  - `diagram`: Crisp vector/orthographic hierarchy, zero garbled pseudo-labels, high-contrast connectors.
- **`acceptance_criteria`**: List of atomic `{id: "AC-1", category, requirement, mandatory: true}` items. **This list is frozen before Attempt 1 and never mutated across retries; specs with zero mandatory criteria fail closed (`exit 2`).**

Optionally (`--expand-prompt` default on when live, skippable via `--raw-prompt`), `gemini-4-argon` (`--body` JSON schema, `store: false`) expands terse user prompts into rich art-direction prompts while preserving every explicit token and quoted literal verbatim; a deterministic Python check verifies no quoted literal from the raw prompt was dropped during expansion.

### Stage 2: Stateful CLI Generation, Asset Caching & Capture-Time Redaction
- All subprocess calls use argument lists with `shell=False` (`S4`) and redact credentials (`AIza...`, `ya29...`, `sk-*`, `Bearer`, `GEMINI_API_KEY`, `api_key`, URL `key=`, and bare `key=<16+ token chars>`) at capture time inside `default_runner` (`S8`).
- Every local reference or manifest `anchor_image` passes `inspect_image_header()` magic-byte validation (`exit 2` on non-image files; manifest anchors are also confined within `manifest_dir`).
- Assets `> 12 MB` or reused across multi-frame sequences / retries are uploaded once via `gemini-api files upload <path> --wait` to obtain a reusable `files/<id>` URI (48h TTL).
- Generation runs `gemini-api image ... -o json`, reading `{path, mime_type, size_bytes, response_id, status}` from stdout JSON and rewriting `--output` suffixes when `gemini-api` returns a different image MIME type.

### Stage 3: Deterministic Mechanical Gate (`L3`, `$0` Tokens)
Executed locally before invoking the multimodal judge:
- **Image Mechanical Verifier (Pure Python 3.12 Stdlib):** Parses PNG (`IHDR` + CRC32), JPEG (`SOF0`–`SOF3`+), and WebP (`VP8 `/`VP8L`/`VP8X`) binary headers without `Pillow` to extract exact `width` and `height`, verifying non-empty bytes, valid magic header, aspect-ratio match within `3.5%` tolerance, and minimum pixel floor (`>= 1500px` long edge when `image_size >= 2K`, `>= 3000px` for `4K`).

### Stage 4: Blinded Multimodal Rubric Judge, Dual-Mode Retry & Loud Override
1. **Stateless Blinded Judge:** Calls `gemini-api generate -m <verifier_model> -i <candidate_path> [-i <ref_paths>...] --stream=false -o json --body @judge_body.json` with `"store": false` and zero generation history or chain-of-thought exposed (`L2` prevention).
2. **Structured Verdict Schema:** Returns `{overall_pass, criteria_results: [{id, passed, observed_evidence, fix_instruction}], remediation_mode: "edit_turn" | "regenerate", edit_delta_prompt, regenerated_prompt}`.
3. **Deterministic Provenance & Consistency Validator (`S9`):**
   - Verifies every `AC-1..N` from the frozen `spec.json` is present in `criteria_results` with non-empty `observed_evidence` (missing IDs fail closed).
   - Computes `all_passed = all(item["passed"] for item in mandatory_results)` in Python and rejects self-contradictory `overall_pass` values.
4. **Targeted Remediation (`attempt < max_attempts`, default `3`):**
   - **`edit_turn` (`--previous-interaction-id <response_id>`):** Selected when mechanical checks passed and `>= 70%` of mandatory criteria (including structural layout/panel/style criteria) passed, issuing a surgical conversational delta (`"Keep everything else the same. <fix_instruction>"`).
   - **`regenerate`:** Selected when mechanical geometry, aspect ratio, panel count, or core style failed, rebuilding the full prompt with explicit corrective directives while retaining anchor `-i` references.
5. **Hard Exit & Loud Override Contract (`S3`, §9):**
   - **Pass:** Moves verified file to `--output`, writes `<output>.provenance.json`, and exits `0`.
   - **Exhausted Failure:** Moves last candidate to `<stem>.rejected<ext>`, writes `<output>.report.json` with exact failed `AC` items, removes any stale `--output` / `.provenance.json`, and **exits `1`**.
   - **Loud Override:** `--allow-unverified` requires a non-empty `--override-reason "<why>"` (`exit 2` at parse time if missing or whitespace-only). On retry exhaustion with a generated candidate, logs a loud `WARNING` on `stderr` and records `override_reason` in both `<output>.report.json` and `<output>.provenance.json` (`"status": "UNVERIFIED_OVERRIDE"`).

---

## 4. `skills/image-gen` Surface (Autonomous + `/image-gen`)

- **Frontmatter:** Removes `disable-model-invocation: true` (and removes `'image-gen'` from `SLASH_COMMAND_SKILLS` in `scripts/validate_skills.py`) so both `/image-gen` slash users and autonomous agents (`codelab`, `atelier`, `/work` workers) can invoke it directly.
- **Modes & CLI Flags (`skills/image-gen/scripts/image_gen.py`):**
  - `--prompt` / `--spec-file` / `--manifest` (JSON batch/sequence spec for `comic-panels` and `timeline`)
  - `--mode {auto,single,diagram,comic-grid,comic-panels,timeline}`
  - `--style` (free-form art direction, e.g. `"gritty noir b&w ink"`, `"ligne claire comic"`, `"ukiyo-e woodblock"`, `"watercolour botanical"`, `"isometric dark-mode vector"`)
  - `--reference` / `-r` (repeatable or comma-separated, up to 14 images; supports role tags `char:path.png`, `style:path.png`, `prop:path.png`, `anchor:path.png`)
  - `--ar` (`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`, `1:4`, `4:1`, `1:8`, `8:1`) and `--size` (`1K`, `2K`, `4K`)
  - `--previous-interaction-id`, `--max-attempts` (default `3`), `--model`, `--verifier-model`, `--raw-prompt`, `--expand-prompt`, `--no-verify`, `--allow-unverified` + `--override-reason`, `--verify-only` + `--rubric-file`, `--dry-run`, `--doctor`, `--output`
- **Sequential Series (`comic-panels` & `timeline`):** Generates or loads an anchor reference first, then loops frame `1..N`, verifying and retrying Frame $k$ to completion before conditioning Frame $k+1$ on `[anchor, frame_k]`, and emits `keyframes_manifest.json` (`[{index, path, response_id, prompt, caption, duration_s}]`).

---

## 5. Installer `--with-media-tools` Opt-In & `--doctor` Design

Adding `--with-media-tools` as an explicit opt-in flag across `scripts/install.sh` and `scripts/install.ps1` preserves fast, side-effect-free default skill syncing while giving interactive and scripted C3 installs a one-command setup:

1. **Flag Validation:**
   - Combining `--with-media-tools` with `--offline` exits `2` immediately with a clear conflict message rather than failing mid-download.
2. **Default Mode (Flag Omitted):**
   - When `image-gen` is among the synced skills, prints a 2-line read-only readiness summary (`gemini-api`: found/missing; `ffmpeg`+`ffprobe`: found/missing) and shows `--with-media-tools` hints without failing the sync.
3. **Opt-In Mode (`--with-media-tools` Passed):**
   - **`gemini-api` CLI:** Checks `command -v gemini-api` / `Get-Command gemini-api`. If absent, runs the official user-space installer (`curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash` on macOS/Linux; official GitHub release archive download into `~/.local/bin` on Windows PowerShell) with **zero `sudo`**.
   - **Offline Test / Mirror Env Seams (Documented & Hardened):**
     - `FORGE_GEMINI_API_INSTALL_CMD`: Optional custom shell/PowerShell command seam for offline test harnesses.
     - `FORGE_GEMINI_API_INSTALL_URL`: Optional custom installer script URL (`install.sh` / parity validation in `install.ps1`).
     - `FORGE_GEMINI_API_RELEASE_URL`: Optional custom GitHub releases JSON endpoint (`install.ps1` / parity validation in `install.sh`).
     - Custom URL overrides (`FORGE_GEMINI_API_INSTALL_URL`, `FORGE_GEMINI_API_RELEASE_URL`, and release asset download URLs) **only accept `https://` or `file://` schemes**; plain `http://` or unknown schemes exit `2`.
   - **Windows Release Checksum Verification (`install.ps1`):** Inspects release assets for a matching `.sha256` or `checksums.txt` asset; when present, verifies `Get-FileHash -Algorithm SHA256` against the downloaded archive and exits non-zero on mismatch. Emits a loud `stderr` warning when an upstream release lacks a checksum asset.
   - **`ffmpeg` & `ffprobe` Readiness & Optional Install:** Checks `ffmpeg` and `ffprobe` for media workflows. If absent, uses user-space package managers where non-elevated (`brew install ffmpeg` on macOS; `winget install --id Gyan.FFmpeg -e` or `scoop install ffmpeg` on Windows) and prints the informational distro command (`sudo apt install ffmpeg`, `sudo dnf install ffmpeg`, `sudo pacman -S ffmpeg`) on Linux as text only (never executed).
   - **Auth & Shadowing Check:** Runs `gemini-api --version` and `gemini-api whoami -o json` (non-fatal if unauthenticated), warning explicitly if `GEMINI_API_KEY` is set alongside stored keyring credentials.
4. **Standalone `npx skills` Parity (`--doctor`):**
   - `image_gen.py --doctor` performs binary, version, and redacted `whoami` auth inspection in stdlib Python so users who install `image-gen` standalone via `npx skills add` get full preflight diagnostics without `install.sh`.

---

## 6. Repository Registration (`K8`), Stdlib Promotion (`S1`) & Test Matrix (`V1-V6`, `T1-T6`)

1. **Registration & Cross-Skill Wiring:**
   - `scripts/validate_skills.py`: Remove `'image-gen'` from `SLASH_COMMAND_SKILLS` (now model-invocable alongside `/image-gen`).
   - `config/harnesses.json`: Broaden `"image-generation"` capability description.
   - `skills/work/scripts/autowire.py` & `skills/work/references/domain_autowiring.md`: Add `"Visual Media, Diagrams & Comics"` `Domain` row mapping visual triggers to `("skills/image-gen",)` (keeping `test_autowire.py` table-parity green).
   - `skills/codelab/SKILL.md`, `skills/atelier/SKILL.md`, `README.md`, `docs/catalog_reference.md`: Replace stale `image-gen-expert` in `codelab/SKILL.md` with `skills/image-gen/SKILL.md` (`K4`), link `image-gen` in `atelier/SKILL.md`, update `README.md` Cluster `C3` + Attribution tables, and mark `/image-gen` primary with `/image-gen-expert` explicitly labelled as a legacy alias in `docs/catalog_reference.md`.
2. **Stdlib-Only Promotion (`S1`):**
   - Add `"skills/image-gen/scripts"` to `ENFORCED_ROOTS` in `scripts/check_stdlib_only.py`.
   - Update `tests/test_stdlib_only.py` (`test_the_cli_exits_one_where_dependencies_are_declared`) to point at `skills/catalog/scripts` (`yaml`) and assert `skills/image-gen/scripts` belongs to `ENFORCED_ROOTS`.
3. **Verifier Fixtures & Required Tests (`V1-V6`, `T1-T6`):**
   - `skills/image-gen/fixtures/{known_good,known_bad}/`: real tiny valid PNG/JPEG/WebP headers vs wrong-aspect/undersized/corrupt headers, non-image anchors, traversal manifests, zero-mandatory specs, and passing vs partial-fail vs self-contradictory judge rubric JSONs.
   - Unit + integration suites (`skills/image-gen/tests/test_image_gen.py`, `tests/test_install_media_tools.py`): covering `T1` differentiation, `T2` mutation smoke, `T3` quoted literal & blocklist derivation, `T4` fail-closed negative paths + loud override (`exit 2` missing reason / `exit 0` valid reason) + bare `key=` redaction + URL scheme/checksum guards, `T5` real subprocess runner checks, and `T6` `--help` / `SKILL.md` flag parity.
