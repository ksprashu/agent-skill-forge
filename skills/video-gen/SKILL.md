---
name: video-gen
description: Generate, chain, score, caption, extend, edit, and verify MP4 videos of any length (3s to 3600s+) using Gemini Omni 1.2 Flash via the official gemini-api CLI, with keyframe delegation to image-gen, -14 LUFS broadcast audio mixing (or audio-gen delegation), kinetic/SRT captions and motion cards, and creative-stack (/vidkit & /sound) integration. Trigger via /video-gen or when creating walkthroughs, explainers, animations, motion graphics, or multi-scene videos.
---

# Video-Gen: Grounded Gemini Omni 1.2 Video Production

Generate, chain, score, caption, extend, edit, and verify MP4 videos of any duration (`3s` to `3600s+`) through `<skill-dir>/scripts/video_gen.py` (with modular sibling engines `video_timeline.py` and `video_post.py`) driving the official `gemini-api` CLI (`gemini-omni-1.2-flash`).

---

## Goal

Produce verified MP4 deliverables whose container headers, stream dimensions, aspect ratio, stitched duration, broadcast loudness (`-14 LUFS` at `48 kHz`), caption/card overlays, and blinded multimodal acceptance criteria (`gemini-4-argon`) are verified before `--output` is written.

---

## Step-by-Step Workflow

### Step 1: Preflight Environment & Grounding Check
If executing inside a repository with `.gemini/knowledge/`, read `.gemini/knowledge/` first for brand tokens and domain terminology. Check CLI, `ffmpeg` (`ffmpeg-full`), `creative-stack`, and companion skill readiness:

```bash
python3 <skill-dir>/scripts/video_gen.py --doctor
```

- Requires `gemini-api` (`https://aistudio.google.com/docs/cli`).
- Resolves keg-only `ffmpeg-full` automatically (`$CREATIVE_STACK_FFMPEG`, Homebrew `ffmpeg-full`, then `PATH`) for Stage 3 `ffprobe` checks, multi-segment stitching, captions/cards, and 2-pass loudness mastering.

### Step 2: Choose Duration, Continuity & Generation Envelope
Read `references/omni_prompting_and_constraints.md` before composing single-clip, edited, or reference-conditioned prompts so `-i` input ordering and Omni 1.2 caps match.

| Workflow | Key Flags | Duration Envelope |
| :--- | :--- | :--- |
| **Single continuous shot** | `--prompt "..." [--style "..."] --single-shot` | `3s..15s` (`1s` steps) |
| **Arbitrary-length video** | `--duration 45` (or `--script beats.md`) `--continuity keyframe-chain --crossfade-sec 0.5` | `3s..3600s+` (`timeline_plan.json` into `5..15s` / `5..10s` segments) |
| **Start / end transition** | `--first-frame a.png --last-frame b.png` | `3s..10s` (`--last-frame` requires `--first-frame`) |
| **Auto-synthesised keyframes** | `--synthesize-keyframes {start,start-end}` | `3s..15s` (`start`) / `3s..10s` (`start-end`) or multi-segment |
| **Video edit / extension** | `--video src.mp4` or `--extend src.mp4 [--strip-audio]` | Source `<= 15s`; `--extend` `3s..10s` (`<= 30s` cumulative) |
| **Motion reference-to-video** | `--video-ref ref1.mp4` (`--prep-clip` optional) | Up to `3` clips (`3-10s`) or `1` clip (`11-15s`) |
| **Storyboard manifest** | `--storyboard keyframes_manifest.json [--storyboard-mode transitions]` | Verified per-segment transitions + `ffmpeg` stitch |

### Step 3: Lock Keyframes, Long-Form Audio, Captions & Motion Cards
- Read `references/storyboard_keyframes_workflow.md` whenever locking character identity (`--image-ref`, `--end-frame-prompt`), synthesising keyframes via `skills/image-gen/SKILL.md`, or animating `keyframes_manifest.json`.
- Read `references/longform_audio_text_and_creative_stack.md` whenever generating `--duration > 15` or `--script` timelines, rendering in-scene `--scene-text` or post-composite captions/cards (`--srt`, `--captions-json`, `--caption-style`, `--title-card`, `--lower-third`, `--end-card`), scoring voiceover/BGM/SFX (`--audio-mode`, `--voice-track`, `--bgm-track`, `--sfx-cue`, `--narration-text`, `--voice-name`, `--bgm-prompt`, `--audio-gen-script`, `--duck-db`, `--lufs-target`), or configuring `--creative-stack`.

### Step 4: Execute Closed-Loop Generation, Verification & Post-Production
Preview planned specs and timelines with `--dry-run` (and optionally `--spec-out` or `--spec-file`), then execute:

```bash
# 1. Single unbroken shot with OCR-verified in-scene typography
python3 <skill-dir>/scripts/video_gen.py \
  --prompt 'Close-up of brass desk plaque, then smooth dolly back revealing starlit observatory dome.' \
  --scene-text "CHRONOS LAB" \
  --single-shot \
  --ar 16:9 \
  --resolution 1080p \
  --duration 8 \
  --output docs/assets/observatory_intro.mp4
```

```bash
# 2. 60-second chained explainer with voiceover + ducked BGM + captions + cards
python3 <skill-dir>/scripts/video_gen.py \
  --script docs/scripts/cloud_explainer.md \
  --duration 60 \
  --continuity keyframe-chain \
  --crossfade-sec 0.5 \
  --image-ref char:assets/presenter_sheet.png \
  --audio-mode full-mix \
  --voice-track audio/narration.wav \
  --bgm-track audio/ambient_bed.wav \
  --sfx-cue audio/chime.wav@12.5 \
  --duck-db 14.0 \
  --lufs-target -14.0 \
  --srt captions/cloud_explainer.srt \
  --caption-style pill \
  --title-card "Zero-Downtime Rollouts|Cloud Platform Architecture" \
  --lower-third "Ada Lovelace|Principal Engineer@4.0-9.0" \
  --end-card "Read the full guide" \
  --creative-stack auto \
  --output docs/assets/cloud_explainer_60s.mp4
```

What `video_gen.py` enforces automatically:
1. **Stage 1 (`spec.json` / `timeline_plan.json`)**: Freezes `VisualRequirementSpec` (`AC-1..N`, including `TEXT_AC` OCR checks for `--scene-text` and quoted literals), validates audio magic bytes and subtitle syntax (`exit 2` on corrupt input), and partitions `--duration > 15` into overlap-compensated segments.
2. **Stage 2 (`gemini-api video`)**: Passes explicit `-m gemini-omni-1.2-flash` (`--model`, `--allow-legacy-video-fallback`, `--task`), caches reused/large assets via `gemini-api files upload --wait`, and chains segment boundary anchors.
3. **Stage 3 (`ffprobe`)**: Audits MP4 `ftyp` headers, video dimensions (`--ar` / `--aspect-ratio`, `--resolution`), stitched duration tolerance, and audio streams (`--silent`, `--require-ffprobe`).
4. **Stage 4 (`--verifier-model`)**: Runs stateless blinded rubric verification (`gemini-4-argon` -> `gemini-4-carbon`, or skips only when `--no-verify` is explicit), retrying up to `--max-attempts` via `--previous-interaction-id` (`edit_turn`) or `regenerate` (`--raw-prompt` / `--expand-prompt`).
5. **Post-Production (`video_post.py`)**: Delegates to `creative-stack` (`vidkit` & `sound`) when discovered, or executes standalone `ffmpeg` 2-pass linear `loudnorm` (`48 kHz`), speech-window `volume` ducking, `amix=normalize=0`, and subtitle/card compositing.

On exhausted retries or multi-segment failure, `video_gen.py` leaves `--output` absent, writes `<output>.report.json`, and **exits `1`**.

---

## Hard Constraints

- **NEVER** pass deprecated models (`veo-3.1-*`, `veo-2*`, `gemini-omni-flash-preview`, `gemini-3.1-flash-image`, `gemini-2.5-*`); `video_gen.py` rejects them with exit code `2`.
- **NEVER** write legacy `<FIRST_FRAME>`, `<LAST_FRAME>`, or `<IMAGE_REF_*>` XML tags in prompts or scripts; Omni 1.2 binds `-i` inputs via natural language.
- **NEVER** use single-pass `loudnorm`, `sidechaincompress` for fixed-dB ducking, or `amix` without `normalize=0`; `video_post.py` enforces 2-pass linear `loudnorm` (`48 kHz`, `dual_mono=true` on mono voice), `silencedetect` `volume` envelopes, and `amix=normalize=0`.
- **NEVER** pass `--allow-unverified` without a non-empty `--override-reason "<why>"` (`exit 2` if omitted); never use unverified overrides in automated pipelines without explicit human direction.
- **NEVER** hardcode machine-specific home paths or API credentials in prompts, scripts, or committed markdown.
