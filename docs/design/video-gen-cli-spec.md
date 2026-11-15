# Arbitrary-Length Grounded Video Generation, Broadcast Audio, Typography & Creative-Stack Specification (`video-gen`)

Status: approved
Slug: video-gen-cli
Path: architectural
Date: 2026-11-14

---

## 1. Problem Statement & Objectives

Single-clip text-to-video wrappers break down on production explainer, walkthrough, and storytelling workloads in four predictable ways: (1) model duration ceilings (`15s` on `gemini-omni-1.2-flash`, `10s` on two-frame transitions and `--extend` turns) prevent generating `45s`–`3600s+` videos without manual ad-hoc slicing and crossfade duration drift; (2) in-scene kinetic text garbles without OCR rubric enforcement while post-composite captions/cards fail on stock macOS `ffmpeg` builds lacking `libass`/`drawtext`; (3) naive single-pass `loudnorm`, `sidechaincompress` ducking, and default `amix` scaling ruin narration intelligibility and loudness consistency; and (4) cramming timeline planning, post-compositing, and DSP into a single script creates an unmaintainable monolith.

This specification defines **`skills/video-gen`** (`PR 2: feat/video-gen-cli`) as a modular three-script, 100% Python 3.12 stdlib video production controller over the official `gemini-api` CLI (`https://aistudio.google.com/docs/cli` and `https://aistudio.google.com/docs/omni`) and `ffmpeg`, with optional seamless delegation to sibling skills (`skills/image-gen`, `skills/audio-gen`) and `creative-stack` (`/vidkit` & `/sound`).

### Explicit Non-Goals
- **No third-party Python packages (`S1`)**: Zero `google-genai`, `Pillow`, `numpy`, or `ffmpeg-python` imports; every module uses Python 3.12 standard library only.
- **No shared runtime package outside `skills/video-gen/`**: Preserves standalone `npx skills add` portability (`AGENTS.md`); cross-skill constant parity with `skills/image-gen` is enforced via `tests/test_media_cli_contract.py` (`T6`).
- **No hardcoded machine or user paths (`S5`, `K7`)**: `creative-stack` and `ffmpeg-full` discovery uses environment variables and `Path.home()` relative locations only.

---

## 2. Modular Script Architecture (`scope-architecture`, `S1`, `S2`)

All runtime modules reside under `skills/video-gen/scripts/`, insert `str(Path(__file__).resolve().parent)` onto `sys.path` for both CLI and `pytest` `importlib` execution, and avoid shadowing stdlib module names:

1. **`video_gen.py` (CLI & 4-Stage Single-Clip Controller)**:
   - Owns `build_parser()` (`--help` 100% synced with `SKILL.md` per `S6`), pre-upload constraint validation (`exit 2`), Stage 1 frozen `VisualRequirementSpec` (`spec.json`), Stage 2 `gemini-api video -m gemini-omni-1.2-flash -o json` execution (`AssetUploadCache`), Stage 3 `ffprobe` mechanical verification, Stage 4 blinded `VERIFIER_MODEL_CHAIN` (`gemini-4-argon` -> `gemini-4-carbon`) rubric verification (`edit_turn` vs `regenerate`), `--doctor`, and orchestration into `video_timeline` and `video_post`.
2. **`video_timeline.py` (Arbitrary-Length Planner, Continuity Chainer & Stitcher)**:
   - Compiles `timeline_plan.json` for `--duration > 15` (`3s..3600s+`) or `--script <json|md>`.
   - Implements `--continuity {keyframe-chain,scene-cuts,extend-blocks}`, boundary frame extraction (`ffmpeg -sseof -0.05 -i seg.mp4 -frames:v 1`), `image-gen` chained keyframe synthesis, per-segment verification/retry, `ffmpeg` `concat` / `xfade`+`acrossfade` stitching, and final stitched `ffprobe` validation.
3. **`video_post.py` (Creative-Stack Bridge, Captions/Cards & Broadcast DSP)**:
   - Owns `SECRET_PATTERNS` (including bare `key=<16+ chars>` capture-time redaction per `S8`), `discover_creative_stack`, `resolve_ffmpeg_binary` (`ffmpeg-full` resolver), `probe_ffmpeg_capabilities` (`ffmpeg -filters`), subtitle & audio magic-byte gates (`exit 2`), caption/card compositing (`vidkit` delegation or standalone `ffmpeg` + `mov_text`/RGBA PNG fallbacks), and broadcast `-14 LUFS` `48 kHz` audio mixing/mastering (`sound` delegation or standalone 2-pass `loudnorm` + `silencedetect` `volume` ducking + `amix=normalize=0` + optional `audio-gen` callout).

---

## 3. Arbitrary-Length Timeline & Overlap Specification

- **Direct Execution (`3..15s`)**: Single clips (`3..10s` when `--first-frame` + `--last-frame` or `--extend` is active) execute directly on `gemini-omni-1.2-flash` (with opt-in `--allow-legacy-video-fallback` to `gemini-omni-1.1-flash` when `duration <= 10s` and no extension image refs exist).
- **Multi-Segment Decomposition (`--duration > 15` or `--script <json|md>`)**:
  - Decomposes target duration $T$ into $N$ integer-second segments $d_1, \dots, d_N \in [5, M]$ ($M = 10$ for interpolated `start-end` or `extend-blocks` turns; $M = 15$ otherwise) satisfying $\sum_{i=1}^N d_i - c \cdot (N - 1) \approx T$ where $c$ is `--crossfade-sec` ($0.0 \le c \le 2.0$).
  - Carries up to `6` magic-byte-checked `--image-ref` anchors across every segment via `AssetUploadCache`.
  - Fails closed (`status: "PARTIAL"`, `exit 1`, `--output` absent) if any segment exhausts retries or `ffmpeg` is unavailable for boundary extraction or stitching.
  - Verifies final stitched output duration via `ffprobe` within `max(1.5s, 0.05 * T)` (`status: "FAILED_VERIFICATION"`, `exit 1` on mismatch).

---

## 4. Typography, Captions, Motion Cards & Audio Mastering Laws

1. **In-Scene Typography (`--scene-text` & Quoted Literals)**:
   - Injects anti-garbling typography instructions into `compiled_prompt` and freezes mandatory `TEXT_AC` OCR legibility and exact spelling criteria into `spec.json` audited by blinded `gemini-4-argon`.
2. **Post-Composite Captions & Motion Cards**:
   - Validates `--srt`, `--captions-json`, `--title-card`, `--lower-third`, and `--end-card` before generation (`exit 2` on missing/corrupt input).
   - Delegates to `vidkit/scripts/{captions,motion}.py` when discovered under `--creative-stack auto|<dir>`, else runs standalone `ffmpeg` (`libass`/`drawtext`, falling back to `-c:s mov_text` soft captions or pure-stdlib RGBA PNG card `overlay` when `ffmpeg -filters` lacks `subtitles`/`ass`/`drawtext`), recording exact renderers in `<output>.report.json`.
3. **Audio Magic-Byte Gate & Broadcast DSP Invariants**:
   - Inspects `--voice-track`, `--bgm-track`, and `--sfx-cue` binary headers (`RIFF....WAVE`, `ID3`/MPEG sync, `fLaC`, `OggS`, `ftyp` M4A) pre-upload (`exit 2` on non-audio files).
   - Supports optional synthesis callout to `--audio-gen-script` (`../audio-gen/scripts/audio_gen.py`) for `--narration-text` (`--mode voice`) and `--bgm-prompt` (`--mode bgm`).
   - Enforces three hard DSP invariants matching `creative-stack` `/sound`:
     - **2-Pass Linear `loudnorm` at `48000 Hz`**: Pass 1 JSON measurement (`dual_mono=true` on mono voice) feeding Pass 2 `linear=true` `loudnorm` with `-ar 48000` into lossless 24-bit WAV (`pcm_s24le`).
     - **Explicit Speech-Window `volume` Envelope**: Detects speech intervals via `silencedetect` and applies a frame-evaluated `volume` expression for exact `--duck-db` (`14.0 dB` default); never `sidechaincompress`.
     - **Unscaled Mixing**: Always passes `normalize=0` to `amix`.

---

## 5. Security, Loud Override & Verification Matrix (`S3`, `S8`, `V1-V6`, `T1-T6`)

- **Capture-Time Secret Redaction (`S8`)**: Redacts `AIza...`, `ya29...`, `sk-...`, `ghp_...`, `AKIA...`, `Bearer ...`, `GEMINI_API_KEY=...`, URL `[?&](key|api_key|access_token)=...`, bare `key=<16+ token chars>` (without corrupting short words like `key=char`), and PEM headers at subprocess capture time across both `video-gen` and `image-gen`.
- **Loud Unverified Override (`S3`)**: Passing `--allow-unverified` without a non-empty `--override-reason "<why>"` exits `2` immediately; valid overrides emit a loud stderr `WARNING` and persist `override_reason` in `.provenance.json` and `.report.json`.
- **Fixtures & Test Coverage**: Committed `known_bad` (corrupt SRT, non-audio BGM file, truncated stitched `ffprobe` JSON) and `known_good` (`timeline_plan`, `45s` stitched `ffprobe`, Pass 1 `loudnorm` JSON, valid WAV/SRT) fixtures exercised across unit, subprocess E2E (`test_media_cli_contract.py`), and `forensic_audit.py --mutate` checks.
