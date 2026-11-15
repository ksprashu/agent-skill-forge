# Grounded Audio Generation, Mastering & Verification Specification (`audio-gen`)

Status: approved
Slug: audio-gen-cli
Path: architectural
Date: 2026-11-14

---

## 1. Problem Statement & Objectives

`agent-skill-forge` provides closed-loop visual (`skills/image-gen`) and video (`skills/video-gen`) controllers, yet lacks a first-class audio generation, voice synthesis, foley/stinger, and broadcast stem-mixing skill. Without a dedicated, mechanically verified audio skill, agents fall back to deprecated TTS endpoints (`gemini-2.5-*-preview-tts`, `chirp-2`, `wavenet`), leak delivery instructions into spoken `text` payloads, switch TTS models mid-article (shifting speaker timbre across chunks), omit consent checks on voice replication, single-pass normalise audio without `-ar 48000` or `dual_mono=true`, and accept zero-amplitude silent WAV files.

This specification introduces **`skills/audio-gen`** (with aliases `music-gen`, `sfx-gen`, and `tts-gen`, while never registering the reserved Antigravity command `voice`) implemented as modular **100% Python 3.12 stdlib-only scripts** (`audio_dsp.py`, `audio_engines.py`, `audio_gen.py`) with optional delegation to `creative-stack` (`/sound`).

### Explicit Non-Goals
- **No third-party Python packages (`S1`):** Zero `librosa`, `soundfile`, `pydub`, `scipy`, `numpy`, `requests`, or `google-genai` imports. Binary header/PCM inspection uses Python `struct` and `math`; HTTP calls use `urllib.request`; CLI tools run via `subprocess.run(..., shell=False)`.
- **No reserved namespace collisions (`K6`):** `voice` is reserved in `config/harnesses.json` and `scripts/validate_skills.py`; `voice` may be used as a `--mode voice` flag value inside `audio_gen.py`, never as a skill directory or alias name.
- **No silent unverified writes (`S3`):** Exhausting `--max-attempts` writes `<stem>.rejected.<ext>` and `<output>.report.json`, preserves non-forge files, and exits `1` unless `--allow-unverified --override-reason "<why>"` is explicitly supplied (`--no-verify` likewise requires `--override-reason`).

---

## 2. Active Model Routing, REST Endpoints & Deprecation Fence

All deprecated or cross-role model identifiers fail closed at argument validation (`exit 2`) before any network or subprocess call executes:

| Capability Role | Primary Model / Endpoint | Failover / Secondary | Hard Invariants & Constraints | Blocked Deprecated IDs (`exit 2`) |
| :--- | :--- | :--- | :--- | :--- |
| **Music, Songs & Backing Tracks** | `lyria-3.5` (`gemini-api music`) | `lyria-3-clip-preview` (`<= 30s` instrumental clips/stingers) | Identical-model backoff retry on `503`/`deadline_exceeded` before failover; `> 180s` (`> 30s` clip) stitched via `acrossfade=d=2:c1=tri:c2=tri` on 24-bit WAV intermediates; `bgm` & `backing-track` enforce explicit non-vocal constraints and forbid `--lyrics`. | `lyria-1*`, `lyria-2*`, `imagen-*`, `veo-*` |
| **Expressive TTS & Multi-Speaker Dialogue** | `gemini-3.8-flash-tts` (`gemini-api tts`) | `gemini-3.8-flash-lite-tts` *(Chunk 1 failover only)* | Delivery style emitted strictly in `annotations: [{"type": "speech_metadata", "speaker": "...", "style": "..."}]`, never in `text`; supports `<laugh>`, `<sigh>`, `<gasp>`, `<whisper>`, `<short pause>`, `<medium pause>`; pins Chunk 1 model across all chunks `1..K`. | `gemini-2.5-flash-preview-tts`, `gemini-2.5-pro-preview-tts`, `gemini-3.1-flash-tts-preview`, `gemini-2.0-*` |
| **Custom Voice Design & Replication** | `POST https://generativelanguage.googleapis.com/v1beta/voices` | Backoff retry on `429`/`503` | `type: "prompted"` (`voice-design`) decodes `sample_audio` WAV + `voice_...` ID; `type: "replicated"` (`voice-replicate`) requires distinct `10-30s` `--source-audio` WAV + `--consent-audio` WAV (`exit 2` if missing or matching SHA-256); `--ephemeral` sets `store: false` (`voicekey_...`). | Plain `http://` non-loopback base URLs (`exit 2`) |
| **Broadcast Locale & Phoneme TTS** | Cloud TTS `Chirp 3: HD` (`POST /v1/text:synthesize`; `/v1beta1` with `CHIRP_VOICE_CLONING_KEY` / `--chirp-cloning-key-file`) | Backoff retry on `429`/`503` | `<locale>-Chirp3-HD-<Voice>` (`Kore`, `Aoede`, `Charon`, `Fenrir`, `Leda`, `Puck`, `Zephyr`, etc.), `--speaking-rate` `0.25..2.0`, `[pause]` / `[pause short]` / `[pause long]` via `input.markup`, IPA/X-SAMPA `custom_pronunciations`; auth via Bearer token or `X-Goog-Api-Key` header (never URL query). | `chirp-2`, `wavenet`, `neural2`, `standard-*` |
| **SFX, Foley & Musical Stingers** | `gemini-omni-1.2-flash` (`omni-foley`) / `lyria-3-clip-preview` (`lyria-sting`) | `creative-bed` (`sound/scripts/bed.py --sting`) / `lavfi-synth` | `omni-foley` generates `3..15s` foley clip and extracts lossless audio via `ffmpeg -vn -acodec pcm_s24le -ar 48000`. | `veo-2*`, `veo-3.1*`, `gemini-omni-flash-preview` |
| **Blinded Multimodal Audio Verifier** | `gemini-4-argon` (`gemini-api generate -i <audio>`) | `gemini-4-carbon` | Stateless (`store: false`, `thinking_level: high`); rejects generator/non-multimodal models passed as `--verifier-model` (`exit 2`). | `flash_medium`, `gemini-1.5-*`, `gemini-2.5-*`, `gemini-3.1-*`, `gemini-3.8-flash` |

### Documented Offline Test Seams
- `FORGE_GEMINI_API_BASE_URL`: Overrides `https://generativelanguage.googleapis.com` for offline tests. Enforces `https://` or loopback `http://127.0.0.1` / `http://localhost`; non-loopback `http://` exits `2`.
- `FORGE_CLOUD_TTS_BASE_URL`: Overrides `https://texttospeech.googleapis.com` under the identical scheme policy.
- `CREATIVE_STACK_FFMPEG` / `CREATIVE_STACK_FFPROBE` / `CREATIVE_STACK_ROOT`: Optional local overrides for keg-only `ffmpeg-full` and `creative-stack` `/sound` discovery.

---

## 3. Modular Stdlib Architecture & Broadcast DSP Laws

1. **`skills/audio-gen/scripts/audio_dsp.py`:**
   - **Pure-Stdlib Binary & PCM Inspector (`inspect_audio_file`):** Parses WAV (`RIFF....WAVE`, `fmt `, `data`, duration, plus PCM16/PCM24/PCM32/Float32 sample scanning for digital silence and clipping without external tools), MP3 (`ID3` skip + `0xFFE0` MPEG sync + bitrate/sample-rate header + non-zero payload), FLAC (`fLaC` + `STREAMINFO`), OGG (`OggS` + Vorbis/Opus identification), and M4A (`ftyp` + `mdat`). Rejects non-audio files (`.txt`, PEM keys, JSON) before upload or `ffmpeg` execution (`exit 2`).
   - **Keg-Only `ffmpeg-full` Resolver:** Checks `$CREATIVE_STACK_FFMPEG` -> `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` -> `/usr/local/opt/ffmpeg-full/bin/ffmpeg` -> `shutil.which("ffmpeg")`.
   - **Broadcast Mastering & Mixing Invariants:**
     - **2-Pass Linear `loudnorm`:** Pass 1 measures `input_i`, `input_tp`, `input_lra`, `input_thresh`, `target_offset` (`print_format=json`, rejecting `-inf` digital silence); Pass 2 applies `linear=true` at `-ar 48000` with `dual_mono=true` automatically enabled on mono voiceovers. Never uses single-pass `loudnorm`.
     - **Deterministic Speech-Window Ducking:** Detects speech intervals via `silencedetect` and constructs an explicit `volume` filter ramp expression (`min(if(lt(t,...),...),...)`) for exact `--duck-db` attenuation. Never uses `sidechaincompress`.
     - **Gain-Preserving Stem Mix & Lossless Intermediates:** Always passes `amix=inputs=N:normalize=0` and uses 24-bit 48 kHz WAV (`pcm_s24le`) for all intermediate crossfades (`acrossfade=d=2:c1=tri:c2=tri`) and vocal separation stages.
   - **`creative-stack` `/sound` Bridge:** Discovers `sound/scripts/{clean,mix,bed,karaoke,session}.py` via `--creative-stack auto|off|<dir>` (`$CREATIVE_STACK_ROOT` and `~/.{agents,gemini,claude}/skills/sound`) with standalone stdlib + `ffmpeg` fallbacks (including bass-preserving `>130 Hz` stereo center-cut vocal removal and linear-gain `<REAPER_PROJECT>` `.rpp` generation).
2. **`skills/audio-gen/scripts/audio_engines.py`:**
   - Capture-time `S8` secret redaction across both `subprocess` and `urllib.request` error/body paths (`AIza...`, `ya29...`, `Bearer ...`, env key assignments, URL `[?&](key|api_key|access_token)=...`, bare `key=<16+ chars>`, `voice_cloning_key`, PEM private keys).
   - Implements Lyria music/clip generation + `503` backoff + multi-segment planning, Gemini 3.8 TTS with `speech_metadata` separation + chunk model-pinning, `/v1beta/voices` Voice Design & consent-gated Voice Replication, Cloud TTS `Chirp 3: HD` (`X-Goog-Api-Key` / Bearer header auth), and `sfx`/`stinger` multi-engine synthesis.
3. **`skills/audio-gen/scripts/audio_gen.py`:**
   - Compiles frozen `AudioRequirementSpec` (`spec_sha256`, `>= 1` mandatory `AC-*`), executes generation + post-DSP mastering, runs Stage 3 mechanical/loudness gates and Stage 4 stateless blinded `VERIFIER_MODEL_CHAIN` rubric verification (`S9` Python provenance check), drives targeted retries (`--max-attempts`), and enforces fail-closed exit `1` or `--allow-unverified --override-reason "<why>"`.

---

## 4. Verification, Fixtures & Registration Contract (`V1-V6`, `T1-T6`, `K8`)

- **Fixtures (`skills/audio-gen/fixtures/`):** Real binary `known_good/` (48 kHz sine PCM16 WAV, valid MPEG Layer III MP3 frame, passing `ffprobe`/`ebur128`/Argon rubric/spec JSONs) and `known_bad/` (corrupt WAV header, zero-amplitude digital-silence WAV, clipped WAV, text disguised as `.wav`, zero-mandatory spec JSON, self-contradictory/missing-AC/failing rubric JSONs).
- **Five-Place Registration (`K8`):** `scripts/sync_skills.py` (`CORE_SKILLS['audio-gen']`, `ALIASES` `music-gen`/`sfx-gen`/`tts-gen`, Cluster `c3`, `--content` help), `config/harnesses.json` (`audio-generation`), `skills/work/scripts/autowire.py` + `domain_autowiring.md`, `scripts/check_stdlib_only.py` + `tests/test_stdlib_only.py`, and `README.md` + `docs/catalog_reference.md`.
