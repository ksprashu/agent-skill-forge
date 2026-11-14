# Gemini 3.8 TTS, Custom Voices (`/v1beta/voices`) & Cloud TTS `Chirp 3: HD`

Operational guide for `--mode voice`, `--mode dialogue`, `--mode voice-design`, and `--mode voice-replicate` in `<skill-dir>/scripts/audio_gen.py`.

---

## 1. Gemini 3.8 TTS (`--engine gemini-tts`)

Active models: `gemini-3.8-flash-tts` (primary) -> `gemini-3.8-flash-lite-tts` (Chunk-1 failover only).

### Three Non-Negotiable Engineering Laws
1. **Separate spoken `text` from `speech_metadata`:** Everything passed in `--prompt` / `--text-file` is spoken verbatim. Put tone, pacing, and persona instructions strictly in `--delivery-style` (or `--style` alias, or `:style` inside `--speakers`), which `audio_gen.py` serialises as `annotations: [{"type": "speech_metadata", "speaker": "...", "style": "..."}]`.
2. **Inline expressive vocal tags:** Only validated vocal tags may appear inside spoken text: `<laugh>`, `<sigh>`, `<gasp>`, `<whisper>`, `</whisper>`, `<short pause>`, `<medium pause>`. Arbitrary HTML/XML tags exit `2`.
3. **Chunk-1 model pinning:** Scripts exceeding `--chunk-chars` (default `1800`) split on paragraph/sentence boundaries. Whichever model succeeded on Chunk 1 is **pinned across all remaining chunks** so speaker timbre never shifts mid-article.

### Multi-Speaker Dialogue Example
```bash
python3 <skill-dir>/scripts/audio_gen.py \
  --mode dialogue \
  --text-file scripts/podcast_intro.txt \
  --speakers "Host=Kore:energetic, curious podcast host" \
  --speakers "Guest=Charon:calm, measured systems architect" \
  --output out/dialogue_intro.wav
```
Format `scripts/podcast_intro.txt` as `Speaker: spoken line` per turn.

---

## 2. Custom Voice Design & Voice Replication (`/v1beta/voices`)

Requires `GEMINI_API_KEY` (sent via `x-goog-api-key` header over `https://generativelanguage.googleapis.com/v1beta/voices`).

- **Voice Design (`--mode voice-design`):**
  ```bash
  python3 <skill-dir>/scripts/audio_gen.py \
    --mode voice-design \
    --voice-prompt "Warm baritone documentary narrator with crisp British diction and relaxed pacing" \
    --sample-text "Beneath the glacier, meltwater carved a cathedral of blue ice." \
    --locale en-GB \
    --voice-meta-out out/narrator_voice.json \
    --output out/narrator_audition.wav
  ```
- **Consent-Gated Voice Replication (`--mode voice-replicate`):**
  - Requires **both** `--source-audio` (`10.0s..30.0s` uncompressed WAV) and `--consent-audio` (distinct spoken consent WAV).
  - Fails closed (`exit 2`) if `--consent-audio` is omitted, non-WAV, digitally silent, outside duration bounds, or matches `--source-audio` by file SHA-256 or raw PCM `data`-chunk SHA-256.
  - Pass `--ephemeral` (`store: false`) to obtain an unstored `voicekey_...` token instead of a persistent `voice_...` resource.

---

## 3. Cloud TTS `Chirp 3: HD` & Instant Custom Voice (`--engine chirp3`)

Use `--engine chirp3` when deterministic `--speaking-rate` (`0.25..2.0`), `[pause]` / `[pause short]` / `[pause long]` markup, `<locale>-Chirp3-HD-<Voice>` locale matching, or IPA/X-SAMPA `--pronunciations` are required. (When `[pause*]` tags appear, `audio_gen.py` routes the payload to Cloud TTS `input.markup`; undocumented tags such as `[pause medium]` fail `exit 2`.)

- **Prebuilt voices:** `Kore`, `Aoede`, `Charon`, `Fenrir`, `Leda`, `Puck`, `Zephyr`, `Orus`, `Callirrhoe`, `Autonoe`, `Enceladus`, `Iapetus`, `Umbriel`, `Despina`, `Erinome`, `Sulafat` (pass `--voice-name` / `--voice` + `--locale en-US`, or full `en-US-Chirp3-HD-Kore`).
- **Custom pronunciations:** `--pronunciations "kubectl=ˈkuːbˌkʌtəl:ipa"` or `--pronunciations glossaries/ipa.json`.
- **Instant Custom Voice:** Prefer `CHIRP_VOICE_CLONING_KEY` env var or `--chirp-cloning-key-file <path>` (legacy `--chirp-cloning-key <key>` warns for CWE-214 process-listing exposure). Switches to `/v1beta1/text:synthesize` and redacts `voiceCloningKey` from all logs/errors (`S8`).
- **Authentication:** Uses `GOOGLE_CLOUD_ACCESS_TOKEN`, `gcloud auth print-access-token`, or `GOOGLE_CLOUD_API_KEY` via `X-Goog-Api-Key` HTTP header (never URL query parameters).
