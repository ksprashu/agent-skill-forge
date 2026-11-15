# Gemini Omni 1.2 Flash Prompting & Constraint Reference

Authoritative reference for `skills/video-gen/scripts/video_gen.py` targeting `gemini-omni-1.2-flash` via the official `gemini-api` CLI (`https://aistudio.google.com/docs/cli` and `https://aistudio.google.com/docs/omni`).

---

## 1. CLI Contract & Explicit Model Pinning

`video_gen.py` invokes `gemini-api video` with `shell=False` and explicit `-m gemini-omni-1.2-flash`:

```bash
gemini-api video "<compiled_prompt>" \
  -m gemini-omni-1.2-flash \
  --aspect-ratio 16:9 \
  --resolution 1080p \
  -i <asset_1> -i <asset_2> \
  --body '{"response_format": {"duration": "8s"}}' \
  --out candidate.mp4 \
  -o json
```

- **Why `-m gemini-omni-1.2-flash` is always explicit**: Older `gemini-api` CLI releases default to `1.1`, which caps clips at `10s` and lacks reference-guided video extension.
- **JSON completion envelope (`-o json`)**: Polls the interaction until completion, writes the MP4 to disk, and prints `{"kind": "video", "path": "...", "size_bytes": ..., "mime_type": "video/mp4", "response_id": "v1_...", "status": "completed"}`.
- **Opt-in legacy failover (`--allow-legacy-video-fallback`)**: Permits stepping down to `gemini-omni-1.1-flash` on `429`/`503` quota exhaustion **only** when `--duration <= 10` and `--extend` has zero `--image-ref` inputs.
- **Hard-blocked deprecated prefixes (`exit 2`)**: `veo-3.1`, `veo-2`, `gemini-omni-flash-preview`, `gemini-3.1-flash-image`, `gemini-3-pro-image-preview`, `gemini-3.1-pro`, `gemini-2.5`, `gemini-2.0`, `gemini-1.5`, `imagen-`, and `flash_medium`.

---

## 2. Parameter & Combination Matrix (Enforced Pre-Upload)

Every invalid flag combination exits `2` before any `gemini-api files upload` or generation request runs:

| Parameter / Mode | Allowed Values | Hard Constraints (`exit 2` on Violation) |
| :--- | :--- | :--- |
| `--ar` / `--aspect-ratio` | `16:9`, `9:16` | Omitted from CLI flags when explicit `--task extend` is passed. |
| `--resolution` | `360p`, `720p`, `1080p`, `4k` | Stage 3 checks `(360x640)`, `(720x1280)`, `(1080x1920)`, `(2160x3840)` (`+-32px`). |
| `--duration` | `3..15` (`1s` increments) | Passed via `--body '{"response_format": {"duration": "<N>s"}}'`. |
| `--first-frame` + `--last-frame` | Local PNG/JPEG/WebP | `--last-frame` requires `--first-frame`; two-frame transitions cap `--duration` at `3..10s`; mutually exclusive with `--video` and `--extend`. |
| `--image-ref` | Repeatable up to `6` | Supports `char:`, `style:`, `prop:`, `subject:`, `background:` prefixes. Cannot combine with explicit `--task extend` (omit `--task` for prompt-based extension). |
| `--video` (edit) | Source MP4 `<= 15s` | Mutually exclusive with `--extend`, `--first-frame`, `--last-frame`, and `--video-ref`. |
| `--extend` | Source MP4 `<= 15s` | Per-turn `--duration` capped at `3..10s`; cumulative duration (`source + turn`) capped at `30s`. |
| `--video-ref` | ~`3s` motion clips | Max `3` clips for `3..10s` generation; max `1` clip for `11..15s` generation; strictly forbidden with `--video`, `--extend`, or `--previous-interaction-id`. |
| `--strip-audio` | Boolean flag | Requires `--video` or `--extend`; runs `ffmpeg -y -i <src> -c:v copy -an <tmp>` in a guaranteed `finally`-cleaned temp directory. |

---

## 3. Canonical `-i` Input Ordering & Natural-Language Role Binding

`gemini-omni-1.2-flash` binds multimodal inputs strictly by `-i` position paired with natural-language instructions. **Never use legacy XML tags (`<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_1>`).**

`video_gen.py` orders `-i` arguments deterministically from `1` to `5`:

1. **`--first-frame`**:
   - Sole image input: `"Use this image as the starting frame."`
   - Followed by `--image-ref`: `"Use the first image as the starting frame."`
2. **`--last-frame`**:
   - Distinct from `--first-frame`: `"Use the first image as the starting frame and the second image as the final frame."`
   - Identical path to `--first-frame` (seamless loop): Passes `-i <path> -i <path>` **twice** with `"Use this image as both the starting frame and the final frame."`
3. **`--image-ref` (`1..6`)**:
   - Computes exact 1-based image ordinal after any keyframes: e.g., `"Use image 3 as the character appearance and identity reference."`
4. **`--extend` or `--video` source clip**:
   - Prompt-based `--extend` (default): Omits `generation_config.video_config.task` and prepends `"Extend this video."` so `--image-ref` works alongside extension.
   - `--video` edit: Prepends `"Keep everything else the same."` so unedited subjects, background geometry, and camera motion stay locked.
5. **`--video-ref` (`1..3`)**:
   - Appended last with ordinal pacing/motion guidance.

Assets exceeding `12 MB` (or reused across retries / seamless loops / storyboard segments) are uploaded once via `gemini-api files upload <path> --wait` and passed as `-i files/<id>`.

---

## 4. Shot Structure, Timecodes & Audio Control

- **Countering Multi-Cut Default (`--single-shot`)**: By default, Omni Flash often stages cinematic cuts across longer durations. Passing `--single-shot` injects `"In a single continuous unbroken shot, no scene cuts."` into both the compiled prompt and mandatory acceptance criteria (`AC-*`).
- **Multi-Beat Timecodes (`[0-5s]`)**: Write explicit bracketed beat ranges (`"[0-4s] Wide shot of harbour at dusk. [4-9s] Cut to close-up of lighthouse lamp igniting."`). Stage 1 parses each beat into an atomic `temporal_beat` criterion verified in Stage 4.
- **Audio Regeneration (`--strip-audio`) & Silent Clips (`--silent`)**:
  - When editing or extending a clip whose existing audio track would clash with new visuals, pass `--strip-audio` so Omni 1.2 synthesizes fresh foley/ambience from scratch.
  - When producing silent UI loops or muted b-roll, pass `--silent` (`--audio-mode silent`); Stage 3 `ffprobe` fails any output containing a residual `codec_type == "audio"` stream.
