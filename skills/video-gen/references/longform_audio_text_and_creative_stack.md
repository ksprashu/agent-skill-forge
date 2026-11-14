# Long-Form Timelines, Broadcast Audio, Typography & Creative-Stack Integration

Authoritative reference for arbitrary-duration multi-segment generation (`video_timeline.py`), typography/captions/motion cards, `-14 LUFS` audio scoring/mastering, and `creative-stack` (`/vidkit` & `/sound`) integration (`video_post.py`).

---

## 1. Arbitrary-Length Videos (`3s` to `3600s+`)

Single clips (`3s..15s`, or `3s..10s` for two-frame interpolation and `--extend` turns) execute directly on `gemini-omni-1.2-flash`. Any job with `--duration > 15` (for example `45`, `120`, `600`, `3600`) or `--script <json|md>` automatically compiles `<stem>_segments/timeline_plan.json`.

### Segment Decomposition & Crossfade Overlap Compensation
When stitching $N$ segments with `--crossfade-sec` $c \in [0.0, 2.0]$, each `xfade` / `acrossfade` transition consumes $c$ seconds of overlap. `video_timeline.py` selects segment count $N$ and integer segment durations $d_1, \dots, d_N \in [5, M]$ ($M = 10$ for `--synthesize-keyframes start-end` or `--continuity extend-blocks`, else $M = 15$) such that:

$$\sum_{i=1}^{N} d_i - c \cdot (N - 1) \approx T_{\text{target}}$$

Final stitched duration is mechanically verified via `ffprobe` within `max(1.5s, 0.05 * target_duration)`. If stitched duration or any individual segment fails verification, `video_gen.py` removes `--output`, writes `<output>.provenance.json` + `<output>.report.json` (`PARTIAL` or `FAILED_VERIFICATION`), and **exits `1`**.

### Continuity Modes (`--continuity`)
- **`keyframe-chain` (default)**:
  - With `--synthesize-keyframes {start,start-end}`: delegates $N$ (or $N + 1$) chained keyframes up front to `../image-gen/scripts/image_gen.py`, passing frame $k$ and persistent `--image-ref` anchors into frame $k+1$ so character proportions, outfits, and lighting remain locked across long sequences.
  - Without `--synthesize-keyframes`: generates and verifies segment $i$, extracts its final rendered frame via `ffmpeg -y -sseof -0.05 -i segment_i.mp4 -frames:v 1 boundary_i.png` (validating PNG header + CRC32), and binds `boundary_i.png` as segment $i+1$'s `--first-frame`.
- **`scene-cuts`**: Generates independent editorial shots per beat while carrying persistent `--image-ref` (`<= 6`, magic-byte validated) character/style/prop anchors across every segment via `AssetUploadCache`.
- **`extend-blocks`**: Groups turns into `<= 25s..30s` cumulative Omni blocks (seed clip `<= 15s` followed by `--extend` turns `<= 10s`), starting each subsequent block from the extracted boundary frame of the prior block so Omni's `15s` source cap and `30s` cumulative cap are never exceeded.

### `--script <json|md>` Formats
1. **JSON Script (`.json`)**:
   ```json
   {
     "style": "clean isometric product film",
     "aspect_ratio": "16:9",
     "continuity": "keyframe-chain",
     "crossfade_sec": 0.5,
     "beats": [
       {"prompt": "Wide shot of control plane cluster booting", "duration_s": 12, "scene_text": "CLUSTER READY"},
       {"prompt": "Traffic routing smoothly across three regional nodes", "duration_s": 12},
       {"prompt": "Dashboard settling on green SLO latency graph", "duration_s": 12}
     ]
   }
   ```
2. **Markdown Beat Script (`.md`)**:
   ```markdown
   # Regional Failover Walkthrough
   - [0-15s] Wide establishing shot of global traffic map with calm cyan arcs.
   - [15-30s] Close-up of primary region draining gracefully during maintenance window.
   - [30-45s] Traffic rebalancing cleanly across secondary regions with zero packet loss.
   ```

---

## 2. In-Scene Typography, Post-Composite Captions & Motion Cards

### Layer A: In-Scene Kinetic / Diegetic Text (`--scene-text`)
Passing `--scene-text "<exact text>"` (repeatable) or quoting `"..."` literals in `--prompt`:
1. Appends anti-garbling typography instructions (`crisp, high-contrast, geometrically stable letterforms and zero warped or misspelled glyphs`) to the compiled generation prompt.
2. Freezes a mandatory `TEXT_AC` OCR legibility and exact character-for-character spelling criterion in `spec.json`, audited by blinded `gemini-4-argon` in Stage 4.

### Layer B: Post-Composite Captions & Motion Cards
Validated pre-generation (`exit 2` on missing, empty, or malformed SRT/JSON cues or invalid card syntax):
- **Captions**: `--srt <file>` or `--captions-json <file>` (supports `{start, end, text}` arrays or Whisper `-ojf` token JSON) with `--caption-style {pill,highlight,karaoke,soft}`.
- **Motion Cards**:
  - `--title-card "<title>[|<subtitle>]"`
  - `--lower-third "<name>|<role>@<start>-<end>"` (repeatable, e.g. `"Ada Lovelace|Staff SRE@2.5-7.5"`)
  - `--end-card "<cta>"` (or `"<title>|<cta>"`)

**Renderer Selection & Graceful Fallbacks (recorded in `<output>.report.json`):**
1. **`creative-stack` `/vidkit` present (`--creative-stack auto|<dir>`)**: Delegates cards to `vidkit/scripts/motion.py` and captions to `vidkit/scripts/captions.py`.
2. **Standalone `ffmpeg` with `libass` / `drawtext`**: Renders ASS v4+ (`pill` box, word-by-word `highlight`, `\kf` `karaoke`) via `-vf ass=...` and cards via timed `drawbox`+`drawtext`.
3. **Stock `ffmpeg` missing `libass` / `drawtext` (e.g. unlinked macOS build)**:
   - Captions fall back cleanly to selectable `-c:s mov_text` soft subtitle tracks (`ffmpeg:mov_text_soft_sub_fallback(missing_libass)`).
   - Motion cards rasterise crisp translucent RGBA PNG cards in pure Python 3.12 stdlib (`struct` + `zlib`, zero Pillow) and composite them via universal `overlay=enable='between(t,...)'` (`ffmpeg:png_card_overlay_fallback(missing_drawtext)`).

---

## 3. Broadcast Audio Scoring, Ducking & Mastering (`-14 LUFS`)

### Flags & Companion `audio-gen` Delegation
- `--audio-mode {native,silent,narration,bgm,full-mix}`
- Local stems (magic-byte inspected for `RIFF....WAVE`, `ID3`/MPEG sync, `fLaC`, `OggS`, or `ftyp` M4A before upload/encode — `exit 2` on non-audio files): `--voice-track <path>`, `--bgm-track <path>`, `--sfx-cue <path@sec[:gain_db]>`.
- Companion synthesis delegation (invoking `--audio-gen-script`, default `../audio-gen/scripts/audio_gen.py`): `--narration-text "<text>"`, `--voice-name <name>`, `--bgm-prompt "<prompt>"`.
- Mastering controls: `--duck-db <float>` (default `14.0`), `--lufs-target <float>` (default `-14.0`).

### Non-Negotiable DSP Laws (`creative-stack` `/sound` Parity)
When `sound/scripts/mix.py` is discovered under `--creative-stack`, multi-stem voice+BGM/SFX mixes delegate directly to `mix.py`. When running standalone, `video_post.py` enforces identical broadcast DSP laws:
1. **Two-Pass Linear `loudnorm` at `48000 Hz`**: Never normalises in a single pass. Pass 1 measures `input_i`, `input_tp`, `input_lra`, `input_thresh`, and `target_offset` (`print_format=json`, setting `dual_mono=true` on mono voiceovers so speech is never boosted `+3 LU` hot); Pass 2 applies `linear=true` `loudnorm` pinned to `-ar 48000` into a lossless 24-bit WAV intermediate (`pcm_s24le`).
2. **Explicit Speech-Window `volume` Envelope Ducking**: Never uses `sidechaincompress` for fixed-dB ducking. Runs `silencedetect=noise=-38.0dB:d=0.4` on the voice stem, merges adjacent phrases, and builds a frame-evaluated `volume=volume='...':eval=frame` ramp expression delivering exact `--duck-db` attenuation.
3. **Unscaled Stem Summing (`amix=normalize=0`)**: Always passes `normalize=0` to `amix` so adding a music bed or SFX cues never divides narration gain by $1/N$.

---

## 4. `creative-stack` Discovery & `ffmpeg-full` Resolution

- **`--creative-stack auto|off|<dir>`**: In `auto` mode, inspects `$CREATIVE_STACK_ROOT`, `~/.agents/skills`, `~/.gemini/skills`, and `~/.claude/skills` for `vidkit` and `sound` with zero hardcoded usernames or machine paths. Passing `off` forces standalone stdlib + `ffmpeg` execution.
- **Keg-Only `ffmpeg-full` Precedence**: Resolves `$CREATIVE_STACK_FFMPEG` -> `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` -> `/usr/local/opt/ffmpeg-full/bin/ffmpeg` -> `PATH` (`shutil.which("ffmpeg")`), ensuring `libass` and `freetype` filters are found automatically on macOS when `brew install ffmpeg-full` is installed.
