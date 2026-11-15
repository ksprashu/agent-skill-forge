# Foley SFX, Sonic Stingers, Broadcast Mixing & `creative-stack` (`/sound`)

Operational guide for `--mode sfx`, `--mode stinger`, `--mode mix`, and `--creative-stack` in `<skill-dir>/scripts/audio_gen.py`.

---

## 1. Foley SFX & Musical Stingers (`--sfx-engine`)

| `--sfx-engine` | Mechanism | Envelope & Best Fit |
| :--- | :--- | :--- |
| **`omni-foley`** | `gemini-omni-1.2-flash` video foley + `ffmpeg -vn -acodec pcm_s24le -ar 48000` | `3s..15s` realistic physical foley (footsteps, rain on slate, mechanical latches, glass clinks). |
| **`lyria-sting`** | `lyria-3-clip-preview` (`gemini-api music`) | `<= 30s` musical logo stingers, harmonic transitions, podcast bumpers. |
| **`creative-bed`** | `creative-stack` `sound/scripts/bed.py --sting` (`--bed-style`) | Seeded, zero-attribution General MIDI stings (`ambient`, `corporate`, `upbeat`, `lofi`, `tension`). |
| **`lavfi-synth`** | Deterministic `ffmpeg -f lavfi` synthesis | Offline UI chimes, sweeps, and sub-bass impacts (`0.25s..30s`) with zero network calls. |

`--sfx-engine auto` routes `--mode sfx` to `omni-foley` and `--mode stinger` to `lyria-sting`.

---

## 2. Broadcast Mastering & Ducked Stem Mixing (`--mode mix`)

```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode mix \
  --voice-track stems/narration_raw.wav --clean-voice \
  --bgm-track stems/lofi_bed.wav \
  --sfx-cue "stems/chime.wav@2.5:-3" \
  --lead 2.5 --tail 4.0 --bgm-gain-db -16 --duck-db 14 \
  --lufs-target -14.0 --true-peak-dbtp -1.0 \
  --reaper-rpp out/episode.rpp \
  --output out/episode_master.wav
```

### Enforced Broadcast DSP Invariants
1. **Two-Pass Linear `loudnorm` Only:** Pass 1 measures `input_i`, `input_tp`, `input_lra`, `input_thresh`, and `target_offset` (`print_format=json`, rejecting `-inf` digital silence); Pass 2 applies `linear=true` pinned to `-ar 48000`, validates target within `+/- 1.0 LUFS` and `<= target_tp + 0.3 dBTP` (with `dynaudnorm+alimiter` linear retry if dynamic fallback misses target). Passing `--no-normalize` skips mastering and records `loudness_gate_2pass_ebur128` in `unchecked_surfaces`. Pass `--require-ffmpeg` to fail closed if `ffmpeg`/`ffprobe` are missing.
2. **Mono Voiceover Compensation (`dual_mono=true`):** Mono voice tracks automatically measure and normalise with `dual_mono=true` so voiceovers do not land `3 LU` hot against stereo beds.
3. **Explicit Speech-Window Envelope Ducking:** Active speech intervals are detected via `silencedetect` and balanced into a logarithmic binary `min(...)` `volume` ramp expression achieving exact `--duck-db` attenuation (`-/filter_complex` script spill above `20k` chars handles 200+ windows cleanly; `sidechaincompress` is never used).
4. **Gain-Preserving `amix` & Lossless Intermediates:** Every stem mix sets `amix=inputs=N:normalize=0` and routes multi-stage processing through 24-bit `48 kHz` WAV (`pcm_s24le`).

---

## 3. `creative-stack` (`/sound`) Discovery & Fallback

`--creative-stack` (`auto` default, `off`, or `<dir>`) checks `$CREATIVE_STACK_ROOT` followed by `~/.agents/skills/sound`, `~/.gemini/skills/sound`, and `~/.claude/skills/sound`:
- When found, `audio_gen.py` delegates voice repair (`clean.py`), ducked mixing (`mix.py`), procedural stings (`bed.py`), stem separation (`karaoke.py`), and REAPER sessions (`session.py`).
- When absent (or `--creative-stack off`), `audio_dsp.py` executes pure stdlib + `ffmpeg` implementations (including linear-amplitude `10 ** (dB / 20)` `<REAPER_PROJECT>` `.rpp` generation).
