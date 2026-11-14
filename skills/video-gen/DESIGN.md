# Design Notes (`skills/video-gen`)

Why `video-gen` is structured as three cohesive, stdlib-only Python 3.12 modules (`video_gen.py`, `video_timeline.py`, `video_post.py`) over `gemini-api` and `ffmpeg` rather than a thin SDK wrapper or single-file monolith. Read `SKILL.md` for operational usage.

---

## 1. Modular Architecture (`scope-architecture`, `S1`, `S2`)

| Module | Responsibility |
| :--- | :--- |
| `scripts/video_gen.py` | CLI parser (`--help` 100% synced with `SKILL.md` per `S6`), pre-upload constraint validation, Stage 1 frozen `VisualRequirementSpec`, Stage 2 `gemini-api video` controller, Stage 3 `ffprobe` verifier, Stage 4 blinded `gemini-4-argon` rubric loop, `--doctor`, and top-level dispatch. |
| `scripts/video_timeline.py` | Arbitrary-length (`3s..3600s+`) multi-segment planner (`timeline_plan.json`), `--script <json|md>` beat parser, `keyframe-chain` / `scene-cuts` / `extend-blocks` continuity chainer, boundary frame extraction (`ffmpeg -sseof -0.05`), `image-gen` keyframe delegation, and `ffmpeg` `concat` / `xfade`+`acrossfade` stitcher. |
| `scripts/video_post.py` | Shared capture-time secret redaction (`SECRET_PATTERNS` including bare `key=<16+ chars>`), `creative-stack` (`vidkit` & `sound`) discovery, keg-only `ffmpeg-full` binary resolver + `-filters` capability probe, subtitle & audio magic-byte gates, captions/motion-card compositing (with `mov_text` & pure-stdlib RGBA PNG card fallbacks), and 2-pass `-14 LUFS` `48 kHz` audio mastering. |

All three modules insert `Path(__file__).resolve().parent` onto `sys.path`, use zero third-party dependencies (`S1`), and avoid shadowing any Python stdlib module name (`S2`).

---

## 2. Failure Modes This Design Prevents

| Failure Mode | How Naive Media Wrappers Fail | Structural Defence in `video-gen` |
| :--- | :--- | :--- |
| **Silent Legacy Model Downgrade** | Omitting `-m` lets older `gemini-api` binaries default to `gemini-omni-1.1-flash` (`10s` ceiling, no reference-guided extension), while stale prompts invoke shut-down `veo-3.1-*` IDs. | Always passes `-m gemini-omni-1.2-flash` explicitly; rejects `DEPRECATED_MODEL_PREFIXES` at parse time with `exit 2`. |
| **Crossfade Duration Shrinkage on Long Videos** | Splitting a `45s` video into `3 x 15s` clips and applying `1.0s` crossfades yields `43.0s` (or `54s` on `12` cuts), drifting monotonically further off target as duration scales. | `video_timeline.py` solves $\sum d_i - c(N-1) \approx T$ in integer seconds before generation and audits stitched output via `ffprobe` within `max(1.5s, 0.05 * T)`. |
| **Multi-Segment Identity & Boundary Drift** | Independent segment calls invent new actor faces, lighting, and camera framing every 10-15 seconds. | Carries persistent magic-byte-checked `--image-ref` anchors (`<= 6`) via `AssetUploadCache` and chains either `image_gen.py` keyframes or extracted `ffmpeg -sseof -0.05` final frames across segment boundaries. |
| **Single-Pass Loudness & `sidechaincompress` Pumping** | Single-pass `loudnorm` guesses gain dynamically (`+-2 LU` error, 192 kHz sample-rate surprises, `+3 dB` hot mono voice), `sidechaincompress` ducks unpredictably, and default `amix` drops voice gain by `1/N`. | Enforces Pass 1 JSON measurement (`dual_mono=true` on mono voice) -> Pass 2 `linear=true` `loudnorm` at `-ar 48000`, `silencedetect` speech-window `volume` expressions, and `amix=normalize=0`. |
| **macOS Homebrew `ffmpeg` Missing `libass` / `drawtext`** | Stock `brew install ffmpeg` omits `libass` and `freetype`, crashing caption burns and `drawtext` title cards mid-pipeline. | Resolves keg-only `ffmpeg-full` first; probes `ffmpeg -filters`; falls back cleanly to `-c:s mov_text` soft captions and pure-stdlib RGBA PNG card `overlay`, recording the exact renderer in `<output>.report.json`. |
| **Non-Audio / Corrupt Subtitle Injection** | Passing an HTML error page disguised as `.mp3` or a broken `.srt` wastes full video generation quota before post-processing crashes. | Pre-upload gate inspects binary audio magic headers (`RIFF..WAVE`, `ID3`/MPEG sync, `fLaC`, `OggS`, `ftyp`) and parses all SRT/JSON cues before Stage 2 starts (`exit 2`). |
| **Silent Unverified Bypass & Credential Leaks (`S3`, `S8`, `K7`)** | `--allow-unverified` silently ships broken media without audit trail; subprocess stderr leaks `AIza...` or `key=<token>` secrets. | `--allow-unverified` requires non-empty `--override-reason` (`exit 2` if omitted), logging a loud stderr warning and writing `override_reason` into `.report.json`; `default_runner` redacts credentials (including bare `key=`) at capture time. |

---

## 3. Evidence vs. Judgement Split (`S9`)

1. **Mechanical Gates Before Multimodal Tokens**: Container `ftyp`, `ffprobe` resolution/aspect/duration/audio checks, audio magic-byte validation, and subtitle parsing run deterministically in Python (`$0` tokens).
2. **Python Provenance Validation Over Blinded Judge Output**: `validate_rubric_verdict` verifies every mandatory `AC-1..N` (including `TEXT_AC` OCR legibility/spelling checks) from frozen `spec.json` is present with boolean `passed` and non-empty `observed_evidence`, computing `all_passed` in Python and flagging `self_contradictory_model_summary`.

---

## 4. What Was Rejected

- **Growing `video_gen.py` into a 5,500-line single file**: Rejected in favour of sibling stdlib modules (`video_timeline.py`, `video_post.py`) inside `skills/video-gen/scripts/` so standalone `npx skills add` keeps working (`AGENTS.md`) without violating modularity (`scope-architecture`).
- **Hardcoding `creative-stack` filesystem paths**: Rejected per `S5` / `K7`; `discover_creative_stack` probes `$CREATIVE_STACK_ROOT` and `~/.{agents,gemini,claude}/skills` dynamically and degrades cleanly to standalone `ffmpeg`.
