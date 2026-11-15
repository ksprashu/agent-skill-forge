---
name: audio-gen
description: Generate, master, mix, and verify background music, full vocal songs, instrumental backing tracks, expressive single/multi-speaker voices, custom Voice Design & consent-gated Voice Replication, Cloud TTS Chirp 3 HD speech, foley SFX, stingers, and broadcast -14 LUFS mixes via Lyria 3.5, Gemini 3.8 TTS, /v1beta/voices, Gemini Omni 1.2 Flash, and creative-stack (/sound). Trigger via /audio-gen or when creating BGMs, songs, voiceovers, podcasts, sound effects, or mixed audio stems.
---

# Audio-Gen: Grounded Music, Voice, Foley & Broadcast Mastering

Produce verified audio deliverables across music, speech, custom voices, sound effects, and ducked broadcast mixes through `<skill-dir>/scripts/audio_gen.py` (100% Python 3.12 stdlib).

---

## Goal

Emit broadcast-ready `-14 LUFS` / `-1.0 dBTP` (`48 kHz`) audio whose binary container, PCM amplitude (non-silent, unclipped), loudness, and blinded `gemini-4-argon` acceptance criteria pass before `--output` is written.

---

## Step-by-Step Workflow

### Step 1: Preflight Environment & Domain Grounding
If working inside a repository with `.gemini/knowledge/`, read `.gemini/knowledge/` first for brand sonic guidelines, pronunciation glossaries, and target loudness standards. Check tool and auth readiness:

```bash
python3 <skill-dir>/scripts/audio_gen.py --doctor
python3 <skill-dir>/scripts/audio_gen.py --help
```

- Resolves `gemini-api` (`https://aistudio.google.com/docs/cli`), keg-only `ffmpeg-full` / `ffmpeg` + `ffprobe`, `gcloud`, and optional `creative-stack` (`/sound`).

### Step 2: Select Audio Mode & Active Engine
Choose the workflow matching your deliverable and read its progressive-disclosure reference before composing complex prompts:

| Deliverable | `--mode` | Default `--engine` / Model | Reference to Read |
| :--- | :--- | :--- | :--- |
| **Instrumental BGM** | `bgm` | `lyria` (`lyria-3.5`, crossfaded `>180s`) | Read `references/lyria_music_and_backing.md` |
| **Full Vocal Song** | `song` | `lyria` (`lyria-3.5` + `--lyrics` / `--locale`) | Read `references/lyria_music_and_backing.md` |
| **Instrumental Backing Track** | `backing-track` | `lyria` or `--strip-vocals-from` (`karaoke.py`) | Read `references/lyria_music_and_backing.md` |
| **Expressive Narration / Dialogue** | `voice` / `dialogue` | `gemini-tts` (`gemini-3.8-flash-tts`) | Read `references/tts_voices_and_chirp3.md` |
| **Locale / IPA Broadcast TTS** | `voice` | `--engine chirp3` (`<locale>-Chirp3-HD-<Voice>`) | Read `references/tts_voices_and_chirp3.md` |
| **Prompted Custom Voice Design** | `voice-design` | `voices-rest` (`POST /v1beta/voices`) | Read `references/tts_voices_and_chirp3.md` |
| **Consent-Gated Voice Replication** | `voice-replicate` | `voices-rest` (`--source-audio` + `--consent-audio`) | Read `references/tts_voices_and_chirp3.md` |
| **Foley SFX / Sonic Stinger** | `sfx` / `stinger` | `sfx` (`omni-foley` / `lyria-sting` / `lavfi-synth`) | Read `references/sfx_mixing_and_creative_stack.md` |
| **Ducked Broadcast Stem Mix** | `mix` | `mix` (`/sound` `mix.py` or 2-pass `loudnorm`) | Read `references/sfx_mixing_and_creative_stack.md` |

### Step 3: Preview Spec & Execute Closed-Loop Synthesis
Validate constraints and inspect the frozen `AudioRequirementSpec` (`spec_sha256`) with `--dry-run`, then execute:

```bash
# 1. Instrumental 90s lofi BGM (enforces explicit non-vocal constraints + 2-pass -14 LUFS)
python3 <skill-dir>/scripts/audio_gen.py \
  --mode bgm \
  --prompt "Warm Rhodes seventh chords over brushed snare and upright bass" \
  --genre lofi --bpm 84 --key "F minor" --duration 90 \
  --output assets/audio/tutorial_bgm.wav

# 2. Expressive Gemini 3.8 TTS narration (delivery style in speech_metadata, never in text!)
python3 <skill-dir>/scripts/audio_gen.py \
  --mode voice \
  --prompt "Welcome back <short pause> let's inspect the latency trace together." \
  --voice-name Kore \
  --delivery-style "warm, brisk engineering walkthrough host" \
  --bgm-track assets/audio/tutorial_bgm.wav --duck-db 14 \
  --output assets/audio/intro_master.wav
```

### Step 4: Inspect Verification & Handle Failures
`audio_gen.py` executes four gates automatically:
1. **Stage 1 (`spec_sha256`)**: Freezes mandatory `AC-*` items before Attempt 1 (rejecting zero-mandatory `--spec-file` inputs with `exit 2`).
2. **Stage 2 (Synthesis + Post-DSP)**: Runs the active engine, stitches multi-segment tracks via 24-bit WAV `acrossfade=d=2:c1=tri:c2=tri`, ducks beds via explicit speech-window `volume` envelopes (`amix=inputs=N:normalize=0`), and runs 2-pass linear `loudnorm` at `-ar 48000` (`dual_mono=true` on mono voice).
3. **Stage 3 (Mechanical Gate)**: Pure-stdlib binary & PCM16/PCM24 sample scan rejects corrupt containers, zero-amplitude digital silence, and severe clipping (`$0` tokens) alongside `ffprobe` duration checks.
4. **Stage 4 (`VERIFIER_MODEL_CHAIN`)**: Stateless blinded `gemini-4-argon` -> `gemini-4-carbon` audio rubric check (`store: false`) validated in Python (`S9`).

If `--max-attempts` (1..10, default `3`) exhausts, `audio_gen.py` writes `<stem>.rejected.<ext>` and `<output>.report.json`, leaves non-forge files untouched, and **exits `1`**.

### Spec, DSP & Verification Controls
- `--spec-file <json>` / `--spec-out <json>` / `--raw-prompt`: Reuse, export frozen `AudioRequirementSpec` (`spec_sha256`), or pass prompts directly from companion workflows (`video-gen`).
- `--mood`, `--instruments`, `--style`, `--voice`, `--crossfade`: Steer Lyria palette/overlap, alias `--delivery-style`, or alias `--voice-name`.
- `--require-ffmpeg` / `--no-normalize`: Fail closed if `ffmpeg`/`ffprobe` are missing, or skip post-DSP mastering (records `loudness_gate_2pass_ebur128` in `unchecked_surfaces`).
- `--verifier-model`, `--no-verify`, `--allow-unverified`, `--override-reason`: Override defaults loudly (`--no-verify` and `--allow-unverified` both fail `exit 2` without `--override-reason`).

---

## Concrete Examples

### Cloud TTS `Chirp 3: HD` with IPA Pronunciations
```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode voice --engine chirp3 \
  --prompt "Deploying Kubernetes [pause short] via Istio ingress." \
  --locale en-GB --voice-name Aoede --speaking-rate 1.05 \
  --pronunciations "Istio=ˈɪstioʊ:ipa" \
  --output assets/audio/uk_narration.wav
```

### Consent-Gated Custom Voice Replication (`--ephemeral`)
```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode voice-replicate \
  --source-audio recordings/speaker_ref_15s.wav \
  --consent-audio recordings/speaker_consent.wav \
  --sample-text "Checking ephemeral custom voice timbre." \
  --ephemeral --voice-meta-out recordings/voice_meta.json \
  --output recordings/replicated_sample.wav
```

---

## Hard Constraints

- **NEVER** register `voice` as a skill name or alias (`voice` is a reserved Antigravity slash command; use `audio-gen`, `music-gen`, `sfx-gen`, or `tts-gen`).
- **NEVER** put delivery style instructions inside spoken `--prompt` text on Gemini 3.8 TTS (`text` is spoken verbatim); always pass `--delivery-style` so `audio_gen.py` emits `speech_metadata` annotations.
- **NEVER** use deprecated models (`gemini-2.5-*-preview-tts`, `gemini-3.1-flash-tts-preview`, `chirp-2`, `wavenet`, `gemini-2.0-*`, `veo-*`) or pass generator models to `--verifier-model`; `audio_gen.py` blocks them with `exit 2`.
- **NEVER** run `--mode voice-replicate` without a distinct `--consent-audio` WAV (`exit 2` if missing or SHA-256-identical to `--source-audio`), pass Cloud TTS API keys in URL query strings (`X-Goog-Api-Key` header only), or expose cloning keys in argv when `CHIRP_VOICE_CLONING_KEY` / `--chirp-cloning-key-file` can be used.
- **NEVER** use single-pass `loudnorm`, `sidechaincompress` for fixed-dB ducking, `amix` without `normalize=0`, or lossy MP3 intermediates across multi-stage chains.
- **NEVER** pass `--allow-unverified` or `--no-verify` without an explicit `--override-reason "<why>"` (`exit 2`).
