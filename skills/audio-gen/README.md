# Audio-Gen Skill (`/audio-gen`, `/music-gen`, `/sfx-gen`, `/tts-gen`)

Zero-dependency Python 3.12 stdlib controller for grounded music synthesis, expressive & broadcast speech, custom Voice Design & consent-gated Voice Replication, foley sound effects, sonic stingers, and `-14 LUFS` broadcast stem mixing.

---

## Capabilities at a Glance

| Domain | Engines & Models | Key Capabilities |
| :--- | :--- | :--- |
| **Music & Songs** | `lyria-3.5`, `lyria-3-clip-preview` (`gemini-api music`) | Instrumental BGMs, custom-lyric vocal songs, `>180s` `acrossfade` stitching, up to 10 `-i` visual mood refs, `503` backoff retry |
| **Backing Tracks** | `lyria-3.5` / `creative-stack` `karaoke.py` | Instrumental-only generation or vocal stripping (`--strip-vocals-from`) with `>130 Hz` bass preservation |
| **Expressive TTS & Dialogue** | `gemini-3.8-flash-tts` -> `gemini-3.8-flash-lite-tts` | Strict `text` vs `speech_metadata` separation, `<laugh>` / `<sigh>` / `<whisper>` tags, Chunk-1 model pinning across long scripts |
| **Custom Voices** | `POST /v1beta/voices` (`prompted` & `replicated`) | Natural-language Voice Design (`voice_...`) and consent-enforced Voice Replication (`--source-audio` + `--consent-audio`, `--ephemeral` `voicekey_...`) |
| **Broadcast Locale TTS** | Cloud TTS `Chirp 3: HD` (`/v1` & `/v1beta1`) | `<locale>-Chirp3-HD-<Voice>`, `--speaking-rate` `0.25..2.0`, `[pause short\|medium\|long]`, IPA/X-SAMPA `--pronunciations`, Instant Custom Voice |
| **SFX & Stingers** | `omni-foley`, `lyria-sting`, `creative-bed`, `lavfi-synth` | `gemini-omni-1.2-flash` `3..15s` foley extraction (`48 kHz` 24-bit WAV), Lyria clip stingers, `/sound` `bed.py --sting`, deterministic `lavfi` cues |
| **Broadcast Mastering & Mix** | `creative-stack` `/sound` or standalone `ffmpeg` | 2-pass `-14 LUFS` / `-1.0 dBTP` linear `loudnorm` (`-ar 48000`, `dual_mono=true`), explicit speech-window `volume` ducking, `amix=normalize=0`, `.rpp` export |

---

## Module Layout

- `scripts/audio_dsp.py`: Pure-stdlib binary container & PCM16/PCM24 sample inspector, keg-only `ffmpeg-full` resolver, 2-pass EBU R128 normaliser, `acrossfade` stitcher, speech-window envelope ducker, and `creative-stack` (`/sound`) bridge.
- `scripts/audio_engines.py`: `S8` secret-redacting subprocess & HTTPS transports, deprecation fence, Lyria, Gemini 3.8 TTS, `/v1beta/voices`, Cloud TTS `Chirp 3: HD`, and SFX/stinger engines.
- `scripts/audio_gen.py`: CLI controller, frozen `AudioRequirementSpec` (`spec_sha256`), Stage 3 mechanical/loudness verifier, Stage 4 stateless blinded `gemini-4-argon` rubric judge, and retry orchestrator.

See [`SKILL.md`](./SKILL.md) for usage and [`DESIGN.md`](./DESIGN.md) for architectural rationale.
