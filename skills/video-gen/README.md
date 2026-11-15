# Video-Gen Skill (`/video-gen`)

Grounded MP4 video generation of any length (`3s` to `3600s+`), keyframe chaining, broadcast `-14 LUFS` audio scoring/mastering, captions & motion cards, and two-layer verification built on `gemini-omni-1.2-flash` and the official `gemini-api` CLI (`https://aistudio.google.com/docs/cli`).

---

## Capabilities

- **Modular Zero-Dependency Architecture (`scripts/{video_gen,video_timeline,video_post}.py`)**: 100% Python 3.12 standard library with `shell=False` subprocess execution, capture-time credential redaction (including bare `key=` tokens), and loud override provenance (`--allow-unverified --override-reason`).
- **Arbitrary-Length Multi-Segment Timelines (`3s..3600s+`)**: Automatically compiles `timeline_plan.json` for `--duration > 15` or `--script <json|md>`, compensates segment durations for `--crossfade-sec` overlap, chains continuity via `keyframe-chain` (`image-gen` keyframes or `ffmpeg -sseof -0.05` boundary frames), `scene-cuts`, or `extend-blocks`, and stitches via `ffmpeg` `concat` or `xfade`+`acrossfade`.
- **Typography, Captions & Motion Cards**: Verifies in-scene text (`--scene-text`) via blinded `gemini-4-argon` OCR (`TEXT_AC`), and renders post-composite `--srt` / `--captions-json` (`pill`, `highlight`, `karaoke`, `soft`), `--title-card`, `--lower-third`, and `--end-card` via `creative-stack` `/vidkit` or standalone `ffmpeg` (with automatic `mov_text` and pure-stdlib RGBA PNG card fallbacks when `libass`/`drawtext` are absent).
- **Broadcast Audio Scoring & Mastering (`-14 LUFS`, `48 kHz`)**: Supports `native`, `silent`, `narration`, `bgm`, and `full-mix` modes with magic-byte audio validation, companion `audio-gen` delegation (`--narration-text`, `--bgm-prompt`), `creative-stack` `/sound` `mix.py` delegation, or standalone 2-pass linear `loudnorm` (`dual_mono=true` on mono voice), `silencedetect` `volume` ducking, and `amix=normalize=0`.

---

## Quick Usage

```bash
# 1. Inspect gemini-api, ffmpeg-full, creative-stack, and companion skills
python3 <skill-dir>/scripts/video_gen.py --doctor

# 2. Generate a verified 45-second chained video with ducked BGM and pill captions
python3 <skill-dir>/scripts/video_gen.py \
  --prompt "Isometric cloud region failing over cleanly with zero dropped requests." \
  --duration 45 \
  --continuity keyframe-chain \
  --crossfade-sec 0.5 \
  --audio-mode full-mix \
  --voice-track voice.wav \
  --bgm-track bed.wav \
  --srt captions.srt \
  --caption-style pill \
  --output failover_explainer.mp4
```

---

## Attribution & License

- **Maintainers**: Agent Skill Forge Contributors
- **License**: Apache-2.0
