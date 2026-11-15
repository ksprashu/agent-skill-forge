# Lyria Music, Full Vocal Songs & Instrumental Backing Tracks

Operational guide for `--mode bgm`, `--mode song`, and `--mode backing-track` in `<skill-dir>/scripts/audio_gen.py`.

---

## 1. Model Selection & Duration Envelope

| Model | Role | Single-Call Cap | Arbitrary-Length Behaviour |
| :--- | :--- | :--- | :--- |
| **`lyria-3.5`** | Default for `bgm`, `song`, and `backing-track` | `<= 180s` | Automatically splits `--duration > 180` into balanced segments overlapped by `--crossfade` (default `2.0s`) and stitches 24-bit WAV intermediates via `acrossfade=d=2:c1=tri:c2=tri`. |
| **`lyria-3-clip-preview`** | Default for `stinger` and fast `<= 30s` cues | `<= 30s` | Splits `--duration > 30` into crossfaded 24-bit WAV segments when explicitly selected via `--model lyria-3-clip-preview`. |

Transient `503`, `429`, or `deadline_exceeded` errors retry the **identical Lyria model** with exponential backoff before attempting clip failover (only eligible on `<= 30s` non-vocal cues).

---

## 2. Instrumental-Only Enforcement (`bgm` & `backing-track`)

- `--mode bgm` and `--mode backing-track` inject explicit negative vocal constraints (`"Strictly instrumental only: no vocals, no singing, no spoken words, no humming, no choir syllables."`) and add mandatory criterion `AC-2` (`instrumental_only`) audited by blinded `gemini-4-argon`.
- Passing `--lyrics` or `--lyrics-file` alongside `--mode bgm` or `--mode backing-track` fails closed with `exit 2`.
- Up to `10` visual mood/cover references can be attached via repeatable `-i` / `--image-ref <path>` (PNG, JPEG, or WebP magic-byte verified before execution).

### Stripping Vocals from an Existing Song (`--strip-vocals-from`)
```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode backing-track \
  --strip-vocals-from tracks/original_song.wav \
  --output tracks/instrumental_backing.wav
```
- When `creative-stack` (`/sound`) is discovered, delegates to `sound/scripts/karaoke.py` (Demucs v4 `htdemucs` with center-cut fallback).
- When standalone, executes a bass-preserving (`> 130 Hz` crossover) stereo phase-cancellation graph in `ffmpeg` so kick drums and bass guitar below `130 Hz` survive intact.

---

## 3. Full Vocal Songs (`--mode song`)

```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode song \
  --prompt "Uplifting acoustic indie-folk anthem with warm harmonies" \
  --genre "indie folk" --bpm 112 --key "G major" --locale en-US \
  --lyrics-file lyrics/chorus.txt \
  --duration 120 \
  --output out/anthem.wav
```

- Structure custom `--lyrics` / `--lyrics-file` with clear `[Verse 1]`, `[Chorus]`, and `[Bridge]` markers so phrasing aligns with bar boundaries.
- Match `--locale` (`--language` alias) to the language of the lyrics for natural vowel placement.
- Steer palette and mix transitions using `--mood`, `--instruments`, `--style`, and `--crossfade` (clamped automatically at 25% of single-segment ceiling during planning and stitching).
