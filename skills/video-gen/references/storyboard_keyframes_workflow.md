# Keyframe Delegation & Multi-Segment Storyboard Workflow

Reference for composing `skills/video-gen` with `skills/image-gen` (`skills/image-gen/SKILL.md`) to lock character identity, typography, and scene layout across single clips and multi-shot sequences.

---

## 1. Why Synthesize Keyframes First

Direct text-to-video generation has to invent composition, character proportions, typography, and motion simultaneously. Delegating keyframe synthesis to `image-gen` (`gemini-nano-banana-2.1` / `gemini-3-pro-image`) solves layout and legible text in still-image space first, then hands verified PNG anchors to `gemini-omni-1.2-flash` to animate motion and audio.

---

## 2. Single-Command Keyframe Delegation (`--synthesize-keyframes`)

`video_gen.py` resolves its companion script at `<skills-root>/image-gen/scripts/image_gen.py`. If `image-gen` is not installed alongside `video-gen` (for example, in a single-skill standalone install), `video_gen.py` exits `2` immediately with exact installation instructions.

### Mode A: `--synthesize-keyframes start` (`3s..15s`)
Generates and verifies a single opening frame (`<stem>_keyframes/start_frame.png`), sizing automatically to `2K` for `1080p`/`4k` video or `1K` for `360p`/`720p`, then binds it as `--first-frame`:

```bash
python3 <skill-dir>/scripts/video_gen.py \
  --prompt 'Isometric dark-mode server rack powering on with status display "CLUSTER HEALTHY".' \
  --synthesize-keyframes start \
  --style "crisp technical 3D render" \
  --ar 16:9 \
  --resolution 1080p \
  --duration 8 \
  --single-shot \
  --output assets/cluster_boot.mp4
```

### Mode B: `--synthesize-keyframes start-end` (`3s..10s` Cap)
1. Generates and verifies `start_frame.png` from `--prompt` (plus any `--image-ref` and `--style`).
2. Generates and verifies `end_frame.png` (using `--end-frame-prompt` if supplied, else derived concluding state) **while passing `-r start_frame.png` first** so character geometry, palette, and lighting remain locked across both endpoints.
3. Invokes `gemini-api video` with `-i start_frame.png -i end_frame.png` and `"Use the first image as the starting frame and the second image as the final frame."`

```bash
python3 <skill-dir>/scripts/video_gen.py \
  --prompt "Seedling sprouts through rich soil into a sunlit sapling." \
  --end-frame-prompt "Sunlit green sapling standing tall in the same terracotta pot and studio lighting." \
  --synthesize-keyframes start-end \
  --style "macro botanical time-lapse photography" \
  --ar 9:16 \
  --resolution 1080p \
  --duration 8 \
  --output assets/sapling_growth.mp4
```

---

## 3. Seamless Loops

Pass the **exact same image path** to both `--first-frame` and `--last-frame` (`--duration` `3..10`):

```bash
python3 <skill-dir>/scripts/video_gen.py \
  --prompt "Subtle neon reflections rippling across wet cobblestones at night." \
  --first-frame assets/alley_anchor.png \
  --last-frame assets/alley_anchor.png \
  --duration 6 \
  --silent \
  --output assets/alley_loop.mp4
```

`video_gen.py` uploads the anchor once via `gemini-api files upload`, passes `-i files/<id> -i files/<id>` twice, and instructs Omni 1.2: `"Use this image as both the starting frame and the final frame."`

---

## 4. Multi-Scene Storyboards (`keyframes_manifest.json`)

For multi-step walkthroughs, architectural explainers, or narrative sequences:

### Step 1: Generate Verified Sequential Keyframes in `image-gen`
Run `image-gen` in `timeline` or `comic-panels` mode (see `skills/image-gen/SKILL.md`) to emit `keyframes_manifest.json`:

```json
{
  "schema_version": 1,
  "mode": "timeline",
  "style": "cinematic storyboard",
  "aspect_ratio": "16:9",
  "anchor_image": "frames/anchor.png",
  "frames": [
    {
      "index": 1,
      "path": "frames/frame_01.png",
      "response_id": "v1_abc",
      "prompt": "Wide establishing shot of an alpine research station at dawn",
      "caption": "Step 1",
      "duration_s": 6
    },
    {
      "index": 2,
      "path": "frames/frame_02.png",
      "response_id": "v1_def",
      "prompt": "Solar array unfolding across the snowy ridge",
      "caption": "Step 2",
      "duration_s": 6
    }
  ]
}
```

### Step 2: Animate & Concatenate Verified Segments in `video-gen`
```bash
python3 <skill-dir>/scripts/video_gen.py \
  --storyboard story/keyframes_manifest.json \
  --storyboard-mode transitions \
  --resolution 1080p \
  --output story/alpine_walkthrough.mp4
```

- **`--storyboard-mode transitions` (default)**: Generates `N - 1` interpolated clips (`frame_k -> frame_{k+1}`, clamped to `3..10s`), conditioning each segment on `anchor_image` via `style:<anchor>` and reusing uploaded `files/<id>` URIs across adjacent segments.
- **`--storyboard-mode clips`**: Generates `N` independent clips (`3..15s` each) anchored on `frame_k` as `--first-frame`.
- **Verification & Concatenation**: Every segment must pass Stage 3 (`ffprobe`) and Stage 4 (`VERIFIER_MODEL_CHAIN`) independently before `ffmpeg -f concat -safe 0 -c copy` assembles `--output` and writes `<output>.provenance.json`. If any segment exhausts retries, the pipeline exits `1`.
