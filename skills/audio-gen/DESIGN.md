# Design Notes (`skills/audio-gen`)

Why `audio-gen` separates binary/DSP verification, synthesis engines, and blinded multimodal rubric judgement across three stdlib-only modules (`audio_dsp.py`, `audio_engines.py`, `audio_gen.py`). Read `SKILL.md` for operational usage.

---

## 1. Failure Modes This Design Prevents

| Failure Mode | How Naive Audio Scripts Fail | Structural Defence in `skills/audio-gen` |
| :--- | :--- | :--- |
| **Spoken Stage-Direction Leaks** | Prepending `"Speak warmly: Hello"` in Gemini 3.8 TTS causes the model to vocalise `"Speak warmly"` aloud. | `build_gemini_tts_command` keeps `text` strictly verbatim and emits `annotations: [{"type": "speech_metadata", "speaker": ..., "style": ...}]`; Stage 4 Argon checks `AC-2` (`verbatim_speech`). |
| **Mid-Read Voice Timbre Shift** | Multi-chunk TTS scripts fail over from `gemini-3.8-flash-tts` on Chunk 1 to `gemini-3.8-flash-lite-tts` on Chunk 2 during a transient `503`, changing speaker identity mid-sentence. | `run_gemini_tts` allows failover only on Chunk 1 and pins `pinned_model` across Chunks `2..K`, retrying only `pinned_model` with backoff and failing closed rather than swapping voices. |
| **Unconsented Voice Cloning** | Replicating a voice from a single clip or reusing the reference clip as its own consent recording. | `create_replicated_voice` requires `10-30s` WAV `--source-audio` plus `--consent-audio` WAV and rejects identical raw or PCM `data`-chunk SHA-256 digests (`exit 2`). |
| **Digital-Silence Pass-Through** | Checking `os.path.getsize(out) > 44` clears a 48 kHz WAV header filled with `0x0000` zero-amplitude PCM samples. | `inspect_audio_file` scans PCM8/PCM16/PCM24/PCM32/Float32 sample amplitudes in pure stdlib and rejects silent (`peak < 1e-4`) or severely clipped (`> 5%` full-scale) audio at `$0` cost. |
| **Hot Mono Voiceovers & Gain Pumping** | Single-pass `loudnorm` drifts up to `2 LU`, omits `-ar 48000` (emitting `192 kHz`), leaves mono `3 LU` hot without `dual_mono=true`, and `sidechaincompress` ducks unpredictably (`0..30 dB`). | `normalize_audio_two_pass` runs Pass 1 JSON measurement -> Pass 2 linear `loudnorm` with `-ar 48000` and automatic `dual_mono=true` on mono; `mix_broadcast_stems` builds explicit `silencedetect` `volume` ramp envelopes and `amix=inputs=N:normalize=0`. |
| **Arbitrary File Exfiltration & Secret Leaks** | Passing `.txt`/`.pem` files to upload flags or echoing `?key=AIza...` / `voice_cloning_key` in HTTP error tracebacks. | `require_valid_audio` and `inspect_image_magic` reject non-media files before any CLI/HTTP call (`exit 2`); `redact_secrets` scrubs credentials at capture time (`S8`), and Cloud TTS sends `X-Goog-Api-Key` strictly in HTTP headers. |
| **Silent Unverified Bypass (`S3`)** | Saving failed retries to `--output` with `exit 0` hides broken audio from CI and downstream video pipelines. | Exhausting `--max-attempts` writes `<stem>.rejected.<ext>` + `<output>.report.json` and exits `1`; `--allow-unverified` requires `--override-reason "<why>"` (`exit 2` if omitted) and stamps `UNVERIFIED_OVERRIDE`. |

---

## 2. Evidence vs. Judgement Split (`S9`)

1. **Deterministic Evidence Collection (`audio_dsp.py`)**: Container magic bytes, RIFF/MPEG/FLAC/OGG/M4A headers, PCM sample peak/RMS/clipping ratios, `ffprobe` stream durations, and EBU R128 Pass 1/Pass 2 loudness measurements are settled purely in Python + `ffmpeg` before any LLM verifier runs.
2. **Blinded Multimodal Judgement (`audio_gen.py`)**: `run_blinded_audio_judge` passes only the candidate audio file and frozen `acceptance_criteria` to `gemini-4-argon` (`store: false`, `thinking_level: high`) with zero generator history. `validate_rubric_verdict` verifies every frozen `AC-*` ID is present with non-empty `observed_evidence`, computes `all_passed` in Python, and rejects self-contradictory `overall_pass: true` payloads.

---

## 3. Loud-Override Contract (`--allow-unverified --override-reason`)

Per `docs/ENGINEERING_STANDARD.md` §9, an override must be possible for human draft exploration and must never be silent:
- Passing `--allow-unverified` without `--override-reason "<non-empty justification>"` exits `2` immediately at argument validation.
- When both are supplied and verification fails, `audio_gen.py` prints a `WARNING` banner to `stderr` and records `"status": "UNVERIFIED_OVERRIDE"` plus `"override_reason"` in both `<output>.report.json` and `<output>.provenance.json`.

---

## 4. Rejected Alternatives

- **Third-party Python audio libraries (`pydub`, `soundfile`, `librosa`, `requests`)**: Rejected per `S1` so `audio-gen` runs identically across all five agent harnesses without virtualenv installation steps.
- **Registering `voice` as an alias**: Rejected per `K6` because `voice` is a reserved Antigravity native command (`config/harnesses.json:118`); aliases are `music-gen`, `sfx-gen`, and `tts-gen`.
- **Full-spectrum `c0 - c1` center-channel cancellation for vocal stripping**: Rejected because sub-130 Hz bass and kick drums sit dead-center alongside lead vocals; `strip_vocals_to_backing` delegates to `creative-stack` `karaoke.py` (Demucs v4 / center-cut) or applies a `130 Hz` crossover so stereo low end stays intact.
