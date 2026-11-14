#!/usr/bin/env python3
# Copyright 2026 Agent Skill Forge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Audio synthesis & REST engines for Lyria, Gemini 3.8 TTS, /v1beta/voices, Chirp 3 & SFX.

Enforces:
1. Capture-time S8 secret redaction across both subprocess (``shell=False``) and
   ``urllib.request`` HTTP error/response handlers.
2. Hard deprecation fence (``exit 2``) blocking retired TTS, Cloud TTS, image,
   and video model identifiers with migration guidance.
3. Lyria (``lyria-3.5``, ``lyria-3-clip-preview``) identical-model transient
   ``503``/``deadline_exceeded`` backoff retry, ``>180s``/``>30s`` crossfaded
   segment planning, and explicit non-vocal constraints on ``bgm``/``backing-track``.
4. Gemini 3.8 TTS (``gemini-3.8-flash-tts`` -> ``gemini-3.8-flash-lite-tts``)
   strict separation between verbatim spoken ``text`` and ``speech_metadata``
   annotations, validated inline vocal tags, and Chunk-1 model pinning across
   multi-chunk scripts.
5. ``/v1beta/voices`` REST custom Voice Design (``type: "prompted"``) and
   consent-gated Voice Replication (``type: "replicated"``, requiring distinct
   10-30s ``--source-audio`` WAV and ``--consent-audio`` WAV).
6. Cloud TTS ``Chirp 3: HD`` & Instant Custom Voice REST client with header-only
   authentication (``Authorization: Bearer`` or ``X-Goog-Api-Key``, never URL query).
7. Multi-engine SFX & stinger generation (``omni-foley``, ``lyria-sting``,
   ``creative-bed``, ``lavfi-synth``).
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audio_dsp  # noqa: E402

# ---------------------------------------------------------------------------
# Shared Inter-Skill Constants (T6 Parity with image-gen & video-gen)
# ---------------------------------------------------------------------------

VERIFIER_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-4-argon",
    "gemini-4-carbon",
)

DEPRECATED_MODEL_PREFIXES: tuple[str, ...] = (
    "gemini-1.5",
    "gemini-2.0",
    "gemini-2.5",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image-preview",
    "gemini-3.1-pro",
    "imagen-",
    "veo-2",
    "veo-3.1",
    "gemini-omni-flash-preview",
)

DEPRECATED_AUDIO_MODEL_RULES: tuple[tuple[str, str], ...] = (
    ("gemini-2.5-flash-preview-tts", "Use 'gemini-3.8-flash-tts' instead."),
    ("gemini-2.5-pro-preview-tts", "Use 'gemini-3.8-flash-tts' instead."),
    ("gemini-3.1-flash-tts-preview", "Use 'gemini-3.8-flash-tts' instead."),
    ("chirp-2", "Use Cloud TTS Chirp 3: HD ('<locale>-Chirp3-HD-<Voice>') via '--engine chirp3'."),
    ("chirp2", "Use Cloud TTS Chirp 3: HD ('<locale>-Chirp3-HD-<Voice>') via '--engine chirp3'."),
    ("wavenet", "WaveNet voices are legacy; use '--engine chirp3' ('<locale>-Chirp3-HD-<Voice>') or 'gemini-3.8-flash-tts'."),
    ("neural2", "Neural2 voices are legacy; use '--engine chirp3' ('<locale>-Chirp3-HD-<Voice>')."),
    ("standard-", "Standard voices are legacy; use '--engine chirp3' ('<locale>-Chirp3-HD-<Voice>')."),
    ("lyria-1", "Use 'lyria-3.5' or 'lyria-3-clip-preview' instead."),
    ("lyria-2", "Use 'lyria-3.5' or 'lyria-3-clip-preview' instead."),
    ("veo-", "Veo models are retired; use 'gemini-omni-1.2-flash' for foley/video instead."),
    ("gemini-2.0-", "Gemini 2.0 models are retired; use 'gemini-3.8-flash-tts' or 'gemini-4-argon'."),
)

PRIMARY_MUSIC_MODEL = "lyria-3.5"
CLIP_MUSIC_MODEL = "lyria-3-clip-preview"
ALLOWED_MUSIC_MODELS = frozenset({PRIMARY_MUSIC_MODEL, CLIP_MUSIC_MODEL})

PRIMARY_TTS_MODEL = "gemini-3.8-flash-tts"
LITE_TTS_MODEL = "gemini-3.8-flash-lite-tts"
ALLOWED_GEMINI_TTS_MODELS = frozenset({PRIMARY_TTS_MODEL, LITE_TTS_MODEL})

OMNI_FOLEY_MODEL = "gemini-omni-1.2-flash"
ALLOWED_VERIFIER_MODELS = frozenset(VERIFIER_MODEL_CHAIN)

LYRIA_FULL_MAX_SEGMENT_S = 180.0
LYRIA_CLIP_MAX_SEGMENT_S = 30.0
MAX_LYRIA_IMAGE_REFS = 10

CHIRP3_HD_VOICES: frozenset[str] = frozenset(
    {
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Aoede",
        "Autonoe",
        "Callirrhoe",
        "Charon",
        "Despina",
        "Enceladus",
        "Erinome",
        "Fenrir",
        "Gacrux",
        "Iapetus",
        "Kore",
        "Laomedeia",
        "Leda",
        "Orus",
        "Puck",
        "Pulcherrima",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zephyr",
        "Zubenelgenubi",
    }
)

ALLOWED_INLINE_VOCAL_TAGS: frozenset[str] = frozenset(
    {
        "laugh",
        "sigh",
        "gasp",
        "whisper",
        "/whisper",
        "short pause",
        "medium pause",
    }
)

ALLOWED_CHIRP_PAUSES: frozenset[str] = frozenset({"", "short", "long"})

DEFAULT_GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_CLOUD_TTS_BASE_URL = "https://texttospeech.googleapis.com"

_FILES_URI_RE = re.compile(r"^files/[A-Za-z0-9_-]+$")
_ANGLE_TAG_RE = re.compile(r"<\s*(/?[A-Za-z][A-Za-z0-9 _:-]*)\s*>")
_CHIRP_PAUSE_RE = re.compile(r"\[\s*pause(?:\s+([^\]]+))?\s*\]", re.IGNORECASE)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35,}\b")),
    ("Google OAuth token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Secret key", re.compile(r"\bsk-(?!ant-)(?:live-|test-|proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b")),
    (
        "Env API key assignment",
        re.compile(
            r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_ACCESS_TOKEN|GOOGLE_CLOUD_API_KEY|CHIRP_VOICE_CLONING_KEY)["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'
        ),
    ),
    (
        "Env API key assignment",
        re.compile(
            r"(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_ACCESS_TOKEN|GOOGLE_CLOUD_API_KEY|CHIRP_VOICE_CLONING_KEY)[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')",
        ),
    ),
    (
        "Env API key assignment",
        re.compile(
            r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_ACCESS_TOKEN|GOOGLE_CLOUD_API_KEY|CHIRP_VOICE_CLONING_KEY)["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
    ),
    (
        "Voice cloning key",
        re.compile(r'(?i)(\b(?:voice_cloning_key|voiceCloningKey)["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'),
    ),
    (
        "Voice cloning key",
        re.compile(r"(?i)(\b(?:voice_cloning_key|voiceCloningKey)[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')"),
    ),
    (
        "Voice cloning key",
        re.compile(
            r'(?i)(\b(?:voice_cloning_key|voiceCloningKey)["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
    ),
    ("Ephemeral voicekey", re.compile(r"\bvoicekey_[A-Za-z0-9_+/\-=]{12,}")),
    (
        "URL query credential",
        re.compile(r"(?i)([?&](?:key|api_key|access_token)=)(?!\[REDACTED\b)[^&\s\"']+"),
    ),
    (
        "API key field",
        re.compile(r'(?i)(\bapi_key["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'),
    ),
    (
        "API key field",
        re.compile(r"(?i)(\bapi_key[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')"),
    ),
    (
        "API key field",
        re.compile(
            r'(?i)(\bapi_key["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
    ),
    (
        "Credential key assignment",
        re.compile(r'(?i)(\bkey["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]{16,}(?=")'),
    ),
    (
        "Credential key assignment",
        re.compile(r"(?i)(\bkey[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]{16,}(?=')"),
    ),
    (
        "Credential key assignment",
        re.compile(
            r'(?i)(\bkey["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]{16,})'
        ),
    ),
    (
        "PEM private key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
            r"(?:[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----)?"
        ),
    ),
)


class ConfigError(ValueError):
    """Raised on invalid CLI arguments, consent failures, or deprecated model IDs (exit 2)."""


class AudioEngineError(RuntimeError):
    """Raised when an external CLI or REST synthesis engine fails at runtime (exit 1)."""


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result with S8-redacted stdout and stderr."""

    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class HttpResponseData:
    """Structured HTTP response returned by ``HttpTransportCallable``."""

    status: int
    body: bytes
    headers: Mapping[str, str]


RunnerCallable = Callable[[Sequence[str]], CommandResult]
HttpTransportCallable = Callable[[str, str, Mapping[str, str], bytes | None, int], HttpResponseData]


# ---------------------------------------------------------------------------
# Capture-Time Secret Redaction, Subprocess Runner & HTTP Transport (S4, S8)
# ---------------------------------------------------------------------------


def redact_secrets(text: str) -> str:
    """Redact credentials, tokens, cloning keys, and PEM blocks at capture time (S8)."""
    if not text:
        return ""
    cleaned = text
    for label, pattern in SECRET_PATTERNS:
        if label == "URL query credential":
            cleaned = pattern.sub(r"\1[REDACTED]", cleaned)
        elif pattern.groups >= 1:
            cleaned = pattern.sub(rf"\1[REDACTED:{label}]", cleaned)
        else:
            cleaned = pattern.sub(f"[REDACTED:{label}]", cleaned)
    return cleaned


def contract_home(path: Path | str) -> str:
    """Normalise user home directory prefixes to ``~/...`` (Rule K7)."""
    text = str(path).strip()
    if _FILES_URI_RE.fullmatch(text):
        return text
    resolved = str(Path(text).expanduser().resolve())
    home = str(Path.home().resolve())
    if resolved == home:
        return "~"
    if resolved.startswith(home + os.sep):
        return "~/" + resolved[len(home) + 1 :].replace("\\", "/")
    return resolved.replace("\\", "/")


def normalize_cli_positional_prompt(text: str, *, verbatim_speech: bool = False) -> str:
    """Prevent leading '-' in positional CLI prompts from being parsed as options (CWE-88)."""
    if text.lstrip().startswith("-"):
        if verbatim_speech:
            return " " + text.lstrip(" ")
        return f"Prompt: {text.lstrip()}"
    return text


def default_runner(argv: Sequence[str], *, timeout: int = 300) -> CommandResult:
    """Execute a CLI binary with ``shell=False`` and capture-time S8 redaction."""
    if isinstance(argv, (str, bytes)) or not argv:
        raise ValueError("Subprocess argv must be a non-empty sequence of strings (S4).")
    cmd_tuple = tuple(str(part) for part in argv)
    try:
        proc = subprocess.run(
            list(cmd_tuple),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            returncode=proc.returncode,
            stdout=redact_secrets(proc.stdout or ""),
            stderr=redact_secrets(proc.stderr or ""),
            argv=cmd_tuple,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            returncode=127,
            stdout="",
            stderr=redact_secrets(f"Command not found: {cmd_tuple[0]} ({exc})"),
            argv=cmd_tuple,
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = (
            exc.stdout.decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else str(exc.stdout or "")
        )
        return CommandResult(
            returncode=124,
            stdout=redact_secrets(raw_out),
            stderr=redact_secrets(f"Command timed out after {timeout}s: {cmd_tuple[0]}"),
            argv=cmd_tuple,
        )


def default_http_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None = None,
    timeout: int = 120,
    *,
    opener: urllib.request.OpenerDirector | None = None,
) -> HttpResponseData:
    """Execute an HTTPS (or loopback HTTP test-seam) request with S8 error redaction."""
    req = urllib.request.Request(url=url, data=body, method=method.upper())
    for header_k, header_v in headers.items():
        req.add_header(header_k, header_v)

    open_fn = opener.open if opener is not None else urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            status_code = int(getattr(resp, "status", None) or resp.getcode() or 200)
            return HttpResponseData(status=status_code, body=raw_bytes, headers=resp_headers)
    except urllib.error.HTTPError as exc:
        err_bytes = exc.read() if hasattr(exc, "read") else b""
        err_text = redact_secrets(err_bytes.decode("utf-8", errors="replace"))
        safe_url = redact_secrets(url)
        raise AudioEngineError(
            f"HTTP {exc.code} from {safe_url}: {err_text[:600] or redact_secrets(str(exc))}"
        ) from None
    except urllib.error.URLError as exc:
        safe_url = redact_secrets(url)
        reason = redact_secrets(str(exc.reason))
        raise AudioEngineError(f"Network error contacting {safe_url}: {reason}") from None


def resolve_api_base_url(
    env_var: str,
    default_url: str,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Validate API base URL allowing only ``https://`` or loopback ``http://127.0.0.1``."""
    active_env = env if env is not None else os.environ
    raw = active_env.get(env_var, "").strip() or default_url
    parsed = urllib.parse.urlparse(raw)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme == "https" and host:
        return raw.rstrip("/")
    if scheme == "http" and host in ("127.0.0.1", "localhost", "::1"):
        return raw.rstrip("/")
    raise ConfigError(
        f"Insecure or invalid {env_var}={redact_secrets(raw)!r}: must use 'https://' "
        f"(or loopback 'http://127.0.0.1' in offline tests)."
    )


def is_transient_error(text_or_result: str | CommandResult) -> bool:
    """Return True if a CLI result or HTTP error represents transient capacity/timeout."""
    if isinstance(text_or_result, CommandResult):
        if text_or_result.returncode == 0:
            return False
        if text_or_result.returncode == 124:
            return True
        haystack = f"{text_or_result.stderr}\n{text_or_result.stdout}".lower()
    else:
        haystack = text_or_result.lower()

    markers = (
        "503",
        "429",
        "deadline_exceeded",
        "deadline exceeded",
        "resource_exhausted",
        "rate limit",
        "too many requests",
        "overloaded",
        "temporarily unavailable",
        "service unavailable",
    )
    return any(tok in haystack for tok in markers)


# ---------------------------------------------------------------------------
# Model Validation & Hard Deprecation Fence (Exit 2)
# ---------------------------------------------------------------------------


def enforce_deprecation_fence(identifier: str, *, context: str = "model") -> str:
    """Reject deprecated/retired models or legacy voice tiers with exit-2 ConfigError."""
    cleaned = identifier.strip()
    if not cleaned:
        raise ConfigError(f"Empty {context} identifier.")
    lowered = cleaned.lower()

    if lowered == "flash_medium":
        raise ConfigError(
            "Model 'flash_medium' is obsolete. Use 'lyria-3.5' for music, "
            "'gemini-3.8-flash-tts' for TTS, or 'gemini-4-argon' for verification."
        )

    for token, hint in DEPRECATED_AUDIO_MODEL_RULES:
        if lowered.startswith(token) or f"-{token}" in lowered or token in lowered:
            raise ConfigError(
                f"Model '{cleaned}' is deprecated/retired (matched '{token}'). {hint}"
            )

    for prefix in DEPRECATED_MODEL_PREFIXES:
        if lowered.startswith(prefix.lower()):
            raise ConfigError(
                f"Model '{cleaned}' is deprecated/shut down (matched '{prefix}'). "
                f"Use 'lyria-3.5', 'gemini-3.8-flash-tts', or 'gemini-4-argon'."
            )
    return cleaned


def validate_audio_model_id(model_id: str, *, role: str) -> str:
    """Validate a model identifier against role allowlists and the deprecation fence."""
    cleaned = enforce_deprecation_fence(model_id, context=f"{role} model")
    lowered = cleaned.lower()

    if role == "verifier":
        if lowered not in ALLOWED_VERIFIER_MODELS:
            raise ConfigError(
                f"Invalid --verifier-model '{cleaned}': audio/image/TTS generator or non-multimodal "
                f"models cannot act as a rubric judge. Allowed: {', '.join(VERIFIER_MODEL_CHAIN)}."
            )
        return lowered

    if role == "music":
        if lowered not in ALLOWED_MUSIC_MODELS:
            raise ConfigError(
                f"Unsupported music model '{cleaned}'. Supported Lyria models: "
                f"'{PRIMARY_MUSIC_MODEL}', '{CLIP_MUSIC_MODEL}'."
            )
        return lowered

    if role == "tts":
        if lowered not in ALLOWED_GEMINI_TTS_MODELS:
            raise ConfigError(
                f"Unsupported Gemini TTS model '{cleaned}'. Supported: "
                f"'{PRIMARY_TTS_MODEL}', '{LITE_TTS_MODEL}' (or pass '--engine chirp3')."
            )
        return lowered

    if role == "sfx":
        if lowered != OMNI_FOLEY_MODEL:
            raise ConfigError(
                f"Unsupported SFX foley model '{cleaned}'. Supported: '{OMNI_FOLEY_MODEL}' "
                f"(or pass '--sfx-engine lyria-sting -m {CLIP_MUSIC_MODEL}' for musical stingers)."
            )
        return lowered

    raise ConfigError(
        f"Explicit --model '{cleaned}' is not valid for role '{role}'. "
        f"Use default engine routing or pass a supported engine/mode."
    )


def _confine_cli_output_path(
    stdout_text: str,
    requested_out: Path,
    staging_dir: Path,
) -> tuple[Path, str | None]:
    """Resolve and confine ``gemini-api -o json`` written ``.path`` inside ``staging_dir``."""
    staging_root = staging_dir.resolve()
    response_id: str | None = None
    text = stdout_text.strip()
    if text.startswith("{"):
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
        if isinstance(doc, dict):
            rid = doc.get("response_id") or doc.get("id")
            if isinstance(rid, str) and rid.strip():
                response_id = rid.strip()
            raw_path = doc.get("path") or doc.get("output")
            if isinstance(raw_path, str) and raw_path.strip():
                candidate = Path(raw_path.strip()).resolve()
                if not candidate.is_relative_to(staging_root):
                    raise AudioEngineError(
                        f"CLI returned output path outside staging directory: {contract_home(candidate)}"
                    )
                if candidate.is_file():
                    return candidate, response_id

    # Fallback: check requested_out or extension-rewritten sibling inside staging_root
    if requested_out.is_file():
        return requested_out.resolve(), response_id
    for ext in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".mp4"):
        alt = requested_out.with_suffix(ext).resolve()
        if alt.is_relative_to(staging_root) and alt.is_file():
            return alt, response_id
    raise AudioEngineError("CLI exited 0 without producing an output file inside staging directory.")


# ---------------------------------------------------------------------------
# Engine A: Lyria Music, Vocal Songs, Backing Tracks & Stingers
# ---------------------------------------------------------------------------


def validate_lyria_image_refs(
    image_refs: Sequence[str],
    *,
    allowed_root: Path | None = None,
) -> list[str]:
    """Validate up to 10 Lyria ``-i`` visual reference images via magic bytes."""
    if len(image_refs) > MAX_LYRIA_IMAGE_REFS:
        raise ConfigError(
            f"Lyria supports at most {MAX_LYRIA_IMAGE_REFS} '-i' image references (got {len(image_refs)})."
        )
    validated: list[str] = []
    for raw in image_refs:
        cleaned = raw.strip()
        if not cleaned:
            raise ConfigError("Empty --image-ref path.")
        local = Path(cleaned).expanduser()
        if _FILES_URI_RE.fullmatch(cleaned) and not local.exists():
            validated.append(cleaned)
            continue
        resolved = local.resolve()
        if allowed_root is not None and not resolved.is_relative_to(allowed_root.resolve()):
            raise ConfigError(
                f"Image reference '{cleaned}' escapes allowed directory '{contract_home(allowed_root)}'."
            )
        try:
            audio_dsp.inspect_image_magic(resolved, label=f"Lyria image ref '{resolved.name}'")
        except audio_dsp.AudioFormatError as exc:
            raise ConfigError(str(exc)) from exc
        validated.append(str(resolved))
    return validated


def effective_crossfade_s(model: str, crossfade_s: float) -> float:
    """Clamp crossfade overlap safely to at most 25% of single-segment duration."""
    if not math.isfinite(crossfade_s) or crossfade_s < 0.0:
        raise ConfigError(f"--crossfade must be finite and >= 0.0 (got {crossfade_s}).")
    max_seg = LYRIA_CLIP_MAX_SEGMENT_S if model == CLIP_MUSIC_MODEL else LYRIA_FULL_MAX_SEGMENT_S
    return max(0.0, min(float(crossfade_s), max_seg * 0.25))


def plan_music_segments(
    duration_s: float,
    *,
    model: str,
    crossfade_s: float = 2.0,
) -> list[float]:
    """Decompose ``duration_s`` into segment durations accounting for crossfade overlap."""
    if not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ConfigError(f"--duration must be finite and positive (got {duration_s}).")
    max_seg = LYRIA_CLIP_MAX_SEGMENT_S if model == CLIP_MUSIC_MODEL else LYRIA_FULL_MAX_SEGMENT_S
    if duration_s <= max_seg:
        return [round(float(duration_s), 3)]
    xfade = effective_crossfade_s(model, crossfade_s)
    if xfade <= 0.0:
        raise ConfigError(
            f"--duration {duration_s}s exceeds single-segment cap ({int(max_seg)}s for '{model}') "
            f"and requires multi-segment acrossfade stitching with --crossfade > 0.0 (got {crossfade_s})."
        )
    step = max_seg - xfade
    count = max(2, math.ceil((duration_s - xfade) / step))
    seg_dur = (duration_s + (count - 1) * xfade) / count
    return [round(seg_dur, 3) for _ in range(count)]


def build_lyria_prompt(
    *,
    raw_prompt: str,
    mode: str,
    genre: str | None = None,
    bpm: int | None = None,
    musical_key: str | None = None,
    mood: str | None = None,
    instruments: str | None = None,
    lyrics: str | None = None,
    language: str | None = None,
    segment_index: int | None = None,
    total_segments: int | None = None,
) -> str:
    """Compile a grounded Lyria prompt enforcing instrumental vs vocal rules."""
    if mode in ("bgm", "backing-track") and lyrics and lyrics.strip():
        raise ConfigError(
            f"--lyrics cannot be combined with '--mode {mode}' (instrumental-only mode). "
            f"Use '--mode song' for vocal lyrics."
        )
    parts: list[str] = [raw_prompt.strip().rstrip(".") + "."]
    if genre and genre.strip():
        parts.append(f"Genre: {genre.strip()}.")
    if bpm is not None:
        if not (40 <= int(bpm) <= 240):
            raise ConfigError(f"--bpm must be between 40 and 240 (got {bpm}).")
        parts.append(f"Tempo: {int(bpm)} BPM.")
    if musical_key and musical_key.strip():
        parts.append(f"Key: {musical_key.strip()}.")
    if mood and mood.strip():
        parts.append(f"Mood: {mood.strip()}.")
    if instruments and instruments.strip():
        parts.append(f"Instruments: {instruments.strip()}.")
    if language and language.strip() and mode == "song":
        parts.append(f"Vocal language: {language.strip()}.")
    if segment_index is not None and total_segments is not None and total_segments > 1:
        parts.append(
            f"Section {segment_index} of {total_segments}: maintain consistent tempo, key, and mix timbre for crossfading."
        )

    if mode in ("bgm", "backing-track"):
        parts.append(
            "Strictly instrumental only: no vocals, no singing, no spoken words, no humming, no choir syllables."
        )
    elif mode == "stinger":
        parts.append("Short resolving musical stinger cue with a crisp cadence and clean decay tail.")
    elif mode == "song" and lyrics and lyrics.strip():
        parts.append(f"Lyrics:\n{lyrics.strip()}")

    return " ".join(parts)


def build_lyria_cli_command(
    *,
    prompt: str,
    model: str,
    out_path: Path,
    image_refs: Sequence[str] = (),
    duration_s: float | None = None,
    prefer_wav: bool = True,
) -> list[str]:
    """Construct ``gemini-api music ... -c '<json>' --out <path> -o json`` argv."""
    safe_prompt = normalize_cli_positional_prompt(prompt, verbatim_speech=False)
    cmd: list[str] = ["gemini-api", "music", safe_prompt, "-m", model]
    for ref in image_refs:
        cmd.extend(["-i", ref])
    resp_fmt: dict[str, Any] = {"type": "audio"}
    if prefer_wav:
        resp_fmt["mime_type"] = "audio/wav"
    cfg: dict[str, Any] = {"response_format": resp_fmt}
    if duration_s is not None:
        cfg["duration_seconds"] = round(float(duration_s), 2)
    cmd.extend(["-c", json.dumps(cfg, separators=(",", ":")), "--out", str(out_path), "-o", "json"])
    return cmd


def run_lyria_generation(
    *,
    raw_prompt: str,
    mode: str,
    explicit_model: str | None,
    duration_s: float,
    crossfade_s: float,
    image_refs: Sequence[str],
    genre: str | None,
    bpm: int | None,
    musical_key: str | None,
    mood: str | None,
    instruments: str | None,
    lyrics: str | None,
    language: str | None,
    staging_dir: Path,
    prefer_wav: bool,
    runner: RunnerCallable,
    ffmpeg_bin: str | None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Execute single- or multi-segment Lyria synthesis with identical-model 503 retry."""
    if explicit_model:
        primary_model = validate_audio_model_id(explicit_model, role="music")
    elif mode == "stinger" and duration_s <= LYRIA_CLIP_MAX_SEGMENT_S:
        primary_model = CLIP_MUSIC_MODEL
    else:
        primary_model = PRIMARY_MUSIC_MODEL

    checked_refs = validate_lyria_image_refs(image_refs)
    seg_durations = plan_music_segments(duration_s, model=primary_model, crossfade_s=crossfade_s)
    if len(seg_durations) > 1 and not ffmpeg_bin:
        raise AudioEngineError(
            f"Duration {duration_s}s requires {len(seg_durations)}-segment acrossfade stitching, "
            f"which needs ffmpeg."
        )

    segment_paths: list[Path] = []
    models_used: list[str] = []
    response_ids: list[str] = []

    for idx, seg_dur in enumerate(seg_durations, start=1):
        seg_prompt = build_lyria_prompt(
            raw_prompt=raw_prompt,
            mode=mode,
            genre=genre,
            bpm=bpm,
            musical_key=musical_key,
            mood=mood,
            instruments=instruments,
            lyrics=lyrics if idx == 1 else None,
            language=language,
            segment_index=idx,
            total_segments=len(seg_durations),
        )
        candidate_models = [primary_model]
        if (
            explicit_model is None
            and primary_model == PRIMARY_MUSIC_MODEL
            and seg_dur <= LYRIA_CLIP_MAX_SEGMENT_S
            and mode != "song"
        ):
            candidate_models.append(CLIP_MUSIC_MODEL)

        seg_written: Path | None = None
        last_err = ""
        for model_candidate in candidate_models:
            # Identical-model backoff retry on transient 503 / deadline_exceeded before failover
            for retry_idx in range(3):
                target_ext = ".wav" if (prefer_wav or len(seg_durations) > 1) else ".mp3"
                req_out = staging_dir / f"lyria_seg_{idx:02d}_{retry_idx}{target_ext}"
                cmd = build_lyria_cli_command(
                    prompt=seg_prompt,
                    model=model_candidate,
                    out_path=req_out,
                    image_refs=checked_refs,
                    duration_s=seg_dur,
                    prefer_wav=(target_ext == ".wav"),
                )
                res = runner(cmd)
                if res.returncode == 0:
                    actual_path, rid = _confine_cli_output_path(res.stdout, req_out, staging_dir)
                    audio_dsp.require_valid_audio(actual_path, label=f"Lyria segment {idx}")
                    seg_written = actual_path
                    models_used.append(model_candidate)
                    if rid:
                        response_ids.append(rid)
                    break
                last_err = (res.stderr or res.stdout).strip()
                if is_transient_error(res) and retry_idx < 2:
                    sleep_fn(0.5 * (2**retry_idx))
                    continue
                break
            if seg_written is not None:
                break

        if seg_written is None:
            raise AudioEngineError(f"Lyria generation failed on segment {idx}: {last_err}")
        segment_paths.append(seg_written)

    if len(segment_paths) == 1:
        final_stage_path = segment_paths[0]
    else:
        assert ffmpeg_bin is not None
        stitched = staging_dir / "lyria_stitched_24bit.wav"
        clamped_xfade = min(effective_crossfade_s(m, crossfade_s) for m in models_used)
        final_stage_path = audio_dsp.stitch_audio_segments(
            segment_paths,
            stitched,
            crossfade_s=clamped_xfade,
            runner=runner,
            ffmpeg_bin=ffmpeg_bin,
        )

    return {
        "path": final_stage_path,
        "model_used": models_used[0],
        "segment_count": len(segment_paths),
        "segment_durations": seg_durations,
        "response_ids": response_ids,
    }


# ---------------------------------------------------------------------------
# Engine B: Gemini 3.8 TTS & /v1beta/voices Custom Voice Design / Replication
# ---------------------------------------------------------------------------


def validate_inline_vocal_tags(text: str) -> list[str]:
    """Validate angle-bracket vocal tags in Gemini 3.8 TTS spoken text."""
    found: list[str] = []
    for match in _ANGLE_TAG_RE.finditer(text):
        tag_norm = " ".join(match.group(1).strip().lower().split())
        if tag_norm not in ALLOWED_INLINE_VOCAL_TAGS:
            allowed_disp = ", ".join(f"<{t}>" for t in sorted(ALLOWED_INLINE_VOCAL_TAGS))
            raise ConfigError(
                f"Unsupported tag '<{match.group(1).strip()}>' inside spoken TTS text. "
                f"Allowed inline vocal tags: {allowed_disp}. Put delivery directions in --delivery-style."
            )
        found.append(tag_norm)
    return found


def split_tts_chunks(text: str, *, max_chars: int = 1800) -> list[str]:
    """Split long TTS text on paragraph/sentence boundaries without dropping text."""
    cleaned = text.strip()
    if not cleaned:
        raise ConfigError("TTS spoken script text must not be empty.")
    if max_chars < 80:
        raise ConfigError(f"--chunk-chars must be >= 80 (got {max_chars}).")
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    current = ""

    def _flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        if len(para) <= max_chars:
            candidate = f"{current}\n\n{para}".strip() if current else para
            if len(candidate) <= max_chars:
                current = candidate
            else:
                _flush()
                current = para
            continue

        _flush()
        sentences = re.split(r"(?<=[.!?])\s+", para)
        for sent in sentences:
            if not sent:
                continue
            if len(sent) > max_chars:
                # Flush accumulated preceding sentences before splitting the long sentence.
                _flush()
                # Hard word-boundary fallback for giant unpunctuated sentences
                words = sent.split()
                buf = ""
                for w in words:
                    cand_w = f"{buf} {w}".strip() if buf else w
                    if len(cand_w) <= max_chars:
                        buf = cand_w
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = w
                if buf:
                    current = buf
                continue
            cand_s = f"{current} {sent}".strip() if current else sent
            if len(cand_s) <= max_chars:
                current = cand_s
            else:
                _flush()
                current = sent
    _flush()
    return chunks


def parse_speaker_map(raw_speakers: Sequence[str] | None) -> dict[str, dict[str, str]]:
    """Parse repeatable ``Speaker=Voice[:style]`` mappings for multi-speaker dialogue."""
    mapping: dict[str, dict[str, str]] = {}
    for entry in raw_speakers or ():
        if "=" not in entry:
            raise ConfigError(
                f"Invalid --speakers entry '{entry}'; expected 'SpeakerName=VoiceName[:delivery style]'."
            )
        speaker_raw, rhs = entry.split("=", 1)
        speaker = speaker_raw.strip()
        voice_part, _, style_part = rhs.partition(":")
        voice = voice_part.strip()
        if not speaker or not voice:
            raise ConfigError(f"Invalid --speakers entry '{entry}'; speaker and voice must be non-empty.")
        mapping[speaker] = {"voice": voice, "style": style_part.strip()}
    return mapping


def parse_dialogue_turns(
    script_text: str,
    speaker_map: Mapping[str, Mapping[str, str]],
    *,
    default_voice: str = "Kore",
    default_style: str = "",
) -> list[dict[str, str]]:
    """Parse ``Speaker: spoken line`` dialogue scripts keeping styles out of ``text``."""
    turns: list[dict[str, str]] = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ConfigError(
                f"Dialogue line missing 'Speaker: utterance' prefix: {line[:80]!r}"
            )
        spk_raw, utterance_raw = line.split(":", 1)
        speaker = spk_raw.strip()
        utterance = utterance_raw.strip()
        if not speaker or not utterance:
            raise ConfigError(f"Empty speaker or utterance in dialogue line: {line[:80]!r}")
        validate_inline_vocal_tags(utterance)
        cfg = speaker_map.get(speaker, {})
        turns.append(
            {
                "speaker": speaker,
                "voice": cfg.get("voice") or default_voice,
                "style": cfg.get("style") or default_style,
                "text": utterance,
            }
        )
    if not turns:
        raise ConfigError("Dialogue script produced zero spoken turns.")
    return turns


def build_gemini_tts_command(
    *,
    spoken_text: str,
    model: str,
    voice_name: str,
    speaker: str,
    delivery_style: str | None,
    out_path: Path,
    dialogue_turns: Sequence[Mapping[str, str]] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Build ``gemini-api tts`` command separating ``text`` from ``speech_metadata``."""
    annotations: list[dict[str, Any]] = []
    if dialogue_turns:
        seen_speakers: dict[str, dict[str, str]] = {}
        for turn in dialogue_turns:
            spk = turn["speaker"]
            seen_speakers[spk] = {"voice": turn["voice"], "style": turn.get("style", "")}
            ann: dict[str, Any] = {"type": "speech_metadata", "speaker": spk}
            if turn.get("style"):
                ann["style"] = turn["style"]
            annotations.append(ann)
        speaker_configs = [
            {"speaker": spk, "voice_config": {"prebuilt_voice_config": {"voice_name": info["voice"]}}}
            for spk, info in seen_speakers.items()
        ]
        config_obj: dict[str, Any] = {
            "annotations": annotations,
            "turns": [{"speaker": t["speaker"], "text": t["text"]} for t in dialogue_turns],
            "speech_config": {"multi_speaker_voice_config": {"speaker_voice_configs": speaker_configs}},
            "response_format": {"type": "audio", "mime_type": "audio/wav"},
        }
    else:
        meta: dict[str, Any] = {"type": "speech_metadata", "speaker": speaker or voice_name}
        if delivery_style and delivery_style.strip():
            meta["style"] = delivery_style.strip()
        annotations.append(meta)
        config_obj = {
            "annotations": annotations,
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}},
            "response_format": {"type": "audio", "mime_type": "audio/wav"},
        }

    safe_spoken = normalize_cli_positional_prompt(spoken_text, verbatim_speech=True)
    cmd = [
        "gemini-api",
        "tts",
        safe_spoken,
        "-m",
        model,
        "--voice",
        voice_name,
        "-c",
        json.dumps(config_obj, separators=(",", ":")),
        "--out",
        str(out_path),
        "-o",
        "json",
    ]
    return cmd, config_obj


def concatenate_wav_files_stdlib(wav_paths: Sequence[Path], dst_wav: Path) -> Path:
    """Concatenate matching PCM WAV chunks losslessly in pure Python stdlib."""
    if not wav_paths:
        raise AudioEngineError("Cannot concatenate zero WAV chunks.")
    if len(wav_paths) == 1:
        if wav_paths[0].resolve() != dst_wav.resolve():
            dst_wav.write_bytes(wav_paths[0].read_bytes())
        return dst_wav

    base_info = audio_dsp.require_valid_audio(wav_paths[0], label="TTS chunk 1", require_wav=True)
    combined_pcm = bytearray()
    for idx, wav_p in enumerate(wav_paths, start=1):
        raw = wav_p.read_bytes()
        info = audio_dsp.require_valid_audio(raw, label=f"TTS chunk {idx}", require_wav=True)
        if (
            info.sample_rate != base_info.sample_rate
            or info.channels != base_info.channels
            or info.bits_per_sample != base_info.bits_per_sample
            or info.audio_format_code != base_info.audio_format_code
        ):
            raise AudioEngineError(
                f"TTS chunk {idx} audio format mismatch ({info.sample_rate}Hz/{info.channels}ch) "
                f"vs chunk 1 ({base_info.sample_rate}Hz/{base_info.channels}ch)."
            )
        # Extract data chunk slice
        cursor = 12
        while cursor + 8 <= len(raw):
            cid = raw[cursor : cursor + 4]
            (csize,) = struct.unpack_from("<I", raw, cursor + 4)
            if cid == b"data":
                combined_pcm.extend(raw[cursor + 8 : cursor + 8 + csize])
                break
            cursor += 8 + csize + (csize & 1)

    pad = b"\x00" if (len(combined_pcm) & 1) else b""
    byte_rate = base_info.sample_rate * base_info.channels * (base_info.bits_per_sample // 8)
    block_align = base_info.channels * (base_info.bits_per_sample // 8)
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        16,
        base_info.audio_format_code,
        base_info.channels,
        base_info.sample_rate,
        byte_rate,
        block_align,
        base_info.bits_per_sample,
    )
    data_chunk = struct.pack("<4sI", b"data", len(combined_pcm)) + bytes(combined_pcm) + pad
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    dst_wav.write_bytes(struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE") + fmt_chunk + data_chunk)
    return dst_wav


def run_gemini_tts(
    *,
    script_text: str,
    mode: str,
    explicit_model: str | None,
    voice_name: str,
    delivery_style: str | None,
    speakers_spec: Sequence[str] | None,
    chunk_chars: int,
    staging_dir: Path,
    runner: RunnerCallable,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Synthesize single-speaker or multi-speaker Gemini 3.8 TTS with Chunk-1 model pinning."""
    if explicit_model:
        initial_chain = [validate_audio_model_id(explicit_model, role="tts")]
    else:
        initial_chain = [PRIMARY_TTS_MODEL, LITE_TTS_MODEL]

    if mode == "dialogue":
        speaker_map = parse_speaker_map(speakers_spec)
        turns = parse_dialogue_turns(
            script_text,
            speaker_map,
            default_voice=voice_name,
            default_style=delivery_style or "",
        )
        # Group turns into chunks by character count while preserving turn atomicity
        turn_batches: list[list[dict[str, str]]] = []
        cur_batch: list[dict[str, str]] = []
        cur_len = 0
        for turn in turns:
            t_len = len(turn["text"]) + len(turn["speaker"]) + 4
            if cur_batch and cur_len + t_len > chunk_chars:
                turn_batches.append(cur_batch)
                cur_batch = [turn]
                cur_len = t_len
            else:
                cur_batch.append(turn)
                cur_len += t_len
        if cur_batch:
            turn_batches.append(cur_batch)
        chunk_units: list[tuple[str, list[dict[str, str]] | None]] = [
            ("\n".join(f"{t['speaker']}: {t['text']}" for t in batch), batch)
            for batch in turn_batches
        ]
    else:
        validate_inline_vocal_tags(script_text)
        text_chunks = split_tts_chunks(script_text, max_chars=chunk_chars)
        chunk_units = [(chunk, None) for chunk in text_chunks]

    pinned_model: str | None = None
    chunk_paths: list[Path] = []
    configs_emitted: list[dict[str, Any]] = []
    response_ids: list[str] = []

    for chunk_idx, (chunk_text, batch_turns) in enumerate(chunk_units, start=1):
        # Hard Law (c): Chunk 1 may failover across initial_chain; Chunks 2..K MUST pin Chunk 1's model!
        allowed_models = initial_chain if pinned_model is None else [pinned_model]
        chunk_written: Path | None = None
        last_err = ""

        for candidate_model in allowed_models:
            for retry_idx in range(3):
                req_out = staging_dir / f"tts_chunk_{chunk_idx:03d}_{retry_idx}.wav"
                cmd, cfg_obj = build_gemini_tts_command(
                    spoken_text=chunk_text,
                    model=candidate_model,
                    voice_name=voice_name,
                    speaker=voice_name,
                    delivery_style=delivery_style,
                    out_path=req_out,
                    dialogue_turns=batch_turns,
                )
                res = runner(cmd)
                if res.returncode == 0:
                    actual_path, rid = _confine_cli_output_path(res.stdout, req_out, staging_dir)
                    audio_dsp.require_valid_audio(actual_path, label=f"TTS chunk {chunk_idx}")
                    chunk_written = actual_path
                    configs_emitted.append(cfg_obj)
                    if rid:
                        response_ids.append(rid)
                    if pinned_model is None:
                        pinned_model = candidate_model
                    break
                last_err = (res.stderr or res.stdout).strip()
                if is_transient_error(res) and retry_idx < 2:
                    sleep_fn(0.5 * (2**retry_idx))
                    continue
                break
            if chunk_written is not None:
                break

        if chunk_written is None:
            pin_note = (
                f" (pinned to '{pinned_model}' from Chunk 1 to prevent mid-read voice timbre shift)"
                if chunk_idx > 1 and pinned_model
                else ""
            )
            raise AudioEngineError(f"Gemini TTS failed on chunk {chunk_idx}{pin_note}: {last_err}")
        chunk_paths.append(chunk_written)

    assert pinned_model is not None
    if len(chunk_paths) == 1:
        combined_out = chunk_paths[0]
    else:
        combined_out = concatenate_wav_files_stdlib(chunk_paths, staging_dir / "tts_stitched.wav")

    return {
        "path": combined_out,
        "model_used": pinned_model,
        "pinned_model": pinned_model,
        "chunk_count": len(chunk_paths),
        "configs_emitted": configs_emitted,
        "response_ids": response_ids,
    }


def _resolve_gemini_rest_headers(env: Mapping[str, str] | None = None) -> dict[str, str]:
    active_env = env if env is not None else os.environ
    api_key = (
        active_env.get("GEMINI_API_KEY", "").strip()
        or active_env.get("GOOGLE_API_KEY", "").strip()
    )
    bearer = active_env.get("GOOGLE_CLOUD_ACCESS_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-goog-api-key"] = api_key
        return headers
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
        return headers
    raise ConfigError(
        "Custom Voices REST API (/v1beta/voices) requires GEMINI_API_KEY (or GOOGLE_API_KEY) "
        "in the environment."
    )


def _wrap_pcm16_as_wav_if_raw(audio_bytes: bytes, sample_rate: int = 48000) -> bytes:
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return audio_bytes
    if len(audio_bytes) < 4 or (len(audio_bytes) % 2 != 0):
        return audio_bytes
    byte_rate = sample_rate * 2
    fmt_chunk = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sample_rate, byte_rate, 2, 16)
    data_chunk = struct.pack("<4sI", b"data", len(audio_bytes)) + audio_bytes
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    return struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE") + fmt_chunk + data_chunk


def _extract_voice_rest_result(
    resp_json: Mapping[str, Any],
    *,
    expect_ephemeral: bool,
) -> tuple[str, bytes | None]:
    raw_id = (
        resp_json.get("voice_cloning_key")
        or resp_json.get("voiceCloningKey")
        or resp_json.get("id")
        or resp_json.get("voice_id")
        or resp_json.get("name")
        or ""
    )
    voice_id = str(raw_id).strip()
    if voice_id.startswith("voices/"):
        voice_id = voice_id.split("/", 1)[1]
    if not voice_id:
        raise AudioEngineError("'/v1beta/voices' response missing voice identifier.")
    if expect_ephemeral and not voice_id.startswith("voicekey_"):
        raise AudioEngineError(
            f"Expected ephemeral 'voicekey_...' identifier when store=false, got '{redact_secrets(voice_id)}'."
        )
    if not expect_ephemeral and not voice_id.startswith("voice_"):
        raise AudioEngineError(
            f"Expected persistent 'voice_...' identifier when store=true, got '{redact_secrets(voice_id)}'."
        )

    b64_audio = (
        resp_json.get("sample_audio")
        or resp_json.get("sampleAudio")
        or (resp_json.get("audio", {}) if isinstance(resp_json.get("audio"), dict) else {}).get("data")
    )
    if isinstance(b64_audio, str) and b64_audio.strip():
        decoded = base64.b64decode(b64_audio)
        return voice_id, _wrap_pcm16_as_wav_if_raw(decoded, sample_rate=24000)
    return voice_id, None


def create_designed_voice(
    *,
    voice_prompt: str,
    sample_text: str,
    locale: str,
    staging_dir: Path,
    http_transport: HttpTransportCallable = default_http_transport,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create a custom voice from description via ``POST /v1beta/voices`` (``type: prompted``)."""
    if not voice_prompt.strip():
        raise ConfigError("--voice-prompt is required for '--mode voice-design'.")
    if not sample_text.strip():
        raise ConfigError("--sample-text is required for '--mode voice-design'.")

    base_url = resolve_api_base_url("FORGE_GEMINI_API_BASE_URL", DEFAULT_GEMINI_API_BASE_URL, env=env)
    headers = _resolve_gemini_rest_headers(env=env)
    payload = {
        "type": "prompted",
        "voice_prompt": voice_prompt.strip(),
        "sample_text": sample_text.strip(),
        "language_code": locale.strip() or "en-US",
        "store": True,
    }
    resp = http_transport(
        "POST",
        f"{base_url}/v1beta/voices",
        headers,
        json.dumps(payload).encode("utf-8"),
        120,
    )
    try:
        doc = json.loads(resp.body.decode("utf-8"))
    except ValueError as exc:
        raise AudioEngineError("Malformed JSON returned by /v1beta/voices.") from exc
    if not isinstance(doc, dict):
        raise AudioEngineError("/v1beta/voices response must be a JSON object.")

    voice_id, wav_bytes = _extract_voice_rest_result(doc, expect_ephemeral=False)
    if not wav_bytes:
        raise AudioEngineError("/v1beta/voices 'prompted' response omitted sample_audio WAV payload.")
    audio_dsp.require_valid_audio(wav_bytes, label="designed voice sample_audio", require_wav=True)

    out_wav = staging_dir / "voice_design_sample.wav"
    out_wav.write_bytes(wav_bytes)
    return {
        "path": out_wav,
        "voice_id": voice_id,
        "ephemeral": False,
        "store": True,
        "model_used": "voices-rest:prompted",
    }


def create_replicated_voice(
    *,
    source_audio_path: Path | str | None,
    consent_audio_path: Path | str | None,
    sample_text: str | None,
    locale: str,
    ephemeral: bool,
    staging_dir: Path,
    http_transport: HttpTransportCallable = default_http_transport,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Replicate a voice via ``POST /v1beta/voices`` enforcing distinct 10-30s WAV + consent."""
    if not source_audio_path:
        raise ConfigError("'--mode voice-replicate' requires --source-audio (10-30s WAV).")
    if not consent_audio_path:
        raise ConfigError(
            "'--mode voice-replicate' requires --consent-audio WAV; voice replication without "
            "explicit recorded speaker consent is forbidden (exit 2)."
        )

    src_path = Path(source_audio_path).expanduser().resolve()
    con_path = Path(consent_audio_path).expanduser().resolve()
    if not src_path.is_file():
        raise ConfigError(f"--source-audio file not found: {contract_home(src_path)}")
    if not con_path.is_file():
        raise ConfigError(f"--consent-audio file not found: {contract_home(con_path)}")

    src_bytes = src_path.read_bytes()
    con_bytes = con_path.read_bytes()
    src_sha256 = hashlib.sha256(src_bytes).hexdigest()
    con_sha256 = hashlib.sha256(con_bytes).hexdigest()
    if src_sha256 == con_sha256:
        raise ConfigError(
            "--consent-audio has identical SHA-256 digest to --source-audio; "
            "consent must be a separate spoken consent recording."
        )

    try:
        src_info = audio_dsp.require_valid_audio(
            src_bytes, label="--source-audio", require_wav=True
        )
        con_info = audio_dsp.require_valid_audio(
            con_bytes, label="--consent-audio", require_wav=True
        )
    except audio_dsp.AudioFormatError as exc:
        raise ConfigError(str(exc)) from exc

    if src_info.pcm_sha256 and src_info.pcm_sha256 == con_info.pcm_sha256:
        raise ConfigError(
            "--consent-audio contains identical PCM audio samples to --source-audio; "
            "re-wrapping source samples as consent is forbidden."
        )
    if not (10.0 <= src_info.duration_s <= 30.0):
        raise ConfigError(
            f"--source-audio WAV must be between 10.0s and 30.0s for voice replication "
            f"(got {src_info.duration_s:.2f}s)."
        )

    base_url = resolve_api_base_url("FORGE_GEMINI_API_BASE_URL", DEFAULT_GEMINI_API_BASE_URL, env=env)
    headers = _resolve_gemini_rest_headers(env=env)
    payload: dict[str, Any] = {
        "type": "replicated",
        "source_audio": base64.b64encode(src_bytes).decode("ascii"),
        "consent_audio": base64.b64encode(con_bytes).decode("ascii"),
        "language_code": locale.strip() or "en-US",
        "store": not ephemeral,
    }
    if sample_text and sample_text.strip():
        payload["sample_text"] = sample_text.strip()

    resp = http_transport(
        "POST",
        f"{base_url}/v1beta/voices",
        headers,
        json.dumps(payload).encode("utf-8"),
        120,
    )
    try:
        doc = json.loads(resp.body.decode("utf-8"))
    except ValueError as exc:
        raise AudioEngineError("Malformed JSON returned by /v1beta/voices.") from exc
    if not isinstance(doc, dict):
        raise AudioEngineError("/v1beta/voices response must be a JSON object.")

    voice_id, wav_bytes = _extract_voice_rest_result(doc, expect_ephemeral=ephemeral)
    if not wav_bytes:
        raise AudioEngineError("/v1beta/voices 'replicated' response omitted sample_audio WAV payload.")
    audio_dsp.require_valid_audio(wav_bytes, label="replicated voice sample_audio", require_wav=True)

    out_wav = staging_dir / "voice_replicate_sample.wav"
    out_wav.write_bytes(wav_bytes)
    return {
        "path": out_wav,
        "voice_id": voice_id,
        "ephemeral": bool(ephemeral),
        "store": not ephemeral,
        "source_sha256": src_sha256,
        "consent_sha256": con_sha256,
        "model_used": "voices-rest:replicated",
    }


# ---------------------------------------------------------------------------
# Engine C: Cloud TTS Chirp 3: HD & Instant Custom Voice
# ---------------------------------------------------------------------------


def format_chirp3_voice_name(voice_name: str, locale: str = "en-US") -> str:
    """Format or validate ``<locale>-Chirp3-HD-<Voice>`` rejecting legacy tiers."""
    cleaned = voice_name.strip()
    if not cleaned:
        raise ConfigError("Empty --voice-name for Chirp 3 HD.")
    enforce_deprecation_fence(cleaned, context="Chirp 3 voice")

    loc = locale.strip() or "en-US"
    if "-Chirp3-HD-" in cleaned:
        voice_short = cleaned.rsplit("-Chirp3-HD-", 1)[1]
        if voice_short not in CHIRP3_HD_VOICES:
            raise ConfigError(
                f"Unknown Chirp 3 HD voice '{voice_short}'. Supported examples: "
                f"Kore, Aoede, Charon, Fenrir, Leda, Puck, Zephyr."
            )
        return cleaned

    matched = next((v for v in CHIRP3_HD_VOICES if v.lower() == cleaned.lower()), None)
    if matched is None:
        raise ConfigError(
            f"Unknown Chirp 3 HD voice '{cleaned}'. Choose from: "
            f"{', '.join(sorted(CHIRP3_HD_VOICES)[:10])}..."
        )
    return f"{loc}-Chirp3-HD-{matched}"


def validate_chirp3_text_markup(text: str) -> list[str]:
    """Validate Chirp 3 HD ``[pause]``, ``[pause short]``, or ``[pause long]`` markup."""
    if not text.strip():
        raise ConfigError("Chirp 3 HD text must not be empty.")
    pauses: list[str] = []
    for match in _CHIRP_PAUSE_RE.finditer(text):
        dur_kind = (match.group(1) or "").strip().lower()
        if dur_kind not in ALLOWED_CHIRP_PAUSES:
            raise ConfigError(
                f"Invalid Chirp 3 pause tag '{match.group(0)}'; use [pause], "
                f"[pause short], or [pause long]."
            )
        pauses.append(dur_kind or "default")
    return pauses


def parse_pronunciation_specs(
    specs: Sequence[str] | None,
) -> list[dict[str, str]]:
    """Parse ``phrase=phoneme[:ipa|xsampa]`` or a JSON file into ``custom_pronunciations``."""
    if not specs:
        return []
    entries: list[dict[str, str]] = []
    for raw in specs:
        cleaned = raw.strip()
        if not cleaned:
            continue
        maybe_file = Path(cleaned).expanduser()
        if "=" not in cleaned and maybe_file.is_file():
            try:
                loaded = json.loads(maybe_file.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ConfigError(f"Invalid JSON in --pronunciations file: {exc}") from exc
            if not isinstance(loaded, list):
                raise ConfigError("--pronunciations JSON file must contain a list of objects.")
            for item in loaded:
                if not isinstance(item, dict) or not item.get("phrase") or not item.get("pronunciation"):
                    raise ConfigError("Each --pronunciations JSON item needs 'phrase' and 'pronunciation'.")
                enc_raw = str(item.get("phonetic_encoding", "PHONETIC_ENCODING_IPA")).upper()
                if enc_raw in ("IPA", "PHONETIC_ENCODING_IPA"):
                    enc = "PHONETIC_ENCODING_IPA"
                elif enc_raw in ("XSAMPA", "X-SAMPA", "X_SAMPA", "PHONETIC_ENCODING_X_SAMPA"):
                    enc = "PHONETIC_ENCODING_X_SAMPA"
                else:
                    raise ConfigError(f"Unsupported phonetic encoding '{enc_raw}'.")
                entries.append(
                    {
                        "phrase": str(item["phrase"]),
                        "phoneticEncoding": enc,
                        "pronunciation": str(item["pronunciation"]),
                    }
                )
            continue

        if "=" not in cleaned:
            raise ConfigError(
                f"Invalid --pronunciations spec '{cleaned}'; expected 'phrase=phoneme[:ipa|xsampa]' or JSON path."
            )
        phrase_raw, rhs = cleaned.split("=", 1)
        phoneme_raw, _, scheme_raw = rhs.rpartition(":")
        if not phoneme_raw or scheme_raw.lower() not in ("ipa", "xsampa", "x-sampa"):
            phoneme = rhs.strip()
            scheme = "ipa"
        else:
            phoneme = phoneme_raw.strip()
            scheme = scheme_raw.lower()
        phrase = phrase_raw.strip()
        if not phrase or not phoneme:
            raise ConfigError(f"Invalid --pronunciations spec '{cleaned}'.")
        enc = (
            "PHONETIC_ENCODING_X_SAMPA"
            if scheme in ("xsampa", "x-sampa")
            else "PHONETIC_ENCODING_IPA"
        )
        entries.append(
            {
                "phrase": phrase,
                "phoneticEncoding": enc,
                "pronunciation": phoneme,
            }
        )
    return entries


def resolve_cloud_tts_auth_headers(
    *,
    env: Mapping[str, str] | None = None,
    runner: RunnerCallable = default_runner,
) -> tuple[dict[str, str], str]:
    """Resolve Cloud TTS auth headers (Bearer or X-Goog-Api-Key, NEVER URL query)."""
    active_env = env if env is not None else os.environ
    headers: dict[str, str] = {"Content-Type": "application/json"}
    project = active_env.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if project:
        headers["x-goog-user-project"] = project

    access_token = active_env.get("GOOGLE_CLOUD_ACCESS_TOKEN", "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        return headers, "env:GOOGLE_CLOUD_ACCESS_TOKEN"

    api_key = active_env.get("GOOGLE_CLOUD_API_KEY", "").strip()

    # Try gcloud auth print-access-token if GOOGLE_CLOUD_API_KEY is not set.
    # Bypass default_runner capture-time redaction so real ya29.* Bearer tokens remain
    # usable in memory for Authorization headers without ever being logged.
    if not api_key:
        if runner is default_runner:
            try:
                proc = subprocess.run(
                    ["gcloud", "auth", "print-access-token"],
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                raw_tok = proc.stdout.strip()
                if proc.returncode == 0 and raw_tok:
                    headers["Authorization"] = f"Bearer {raw_tok}"
                    return headers, "gcloud:print-access-token"
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            gcloud_res = runner(["gcloud", "auth", "print-access-token"])
            raw_tok = gcloud_res.stdout.strip()
            if gcloud_res.returncode == 0 and raw_tok and not raw_tok.startswith("[REDACTED"):
                headers["Authorization"] = f"Bearer {raw_tok}"
                return headers, "gcloud:print-access-token"

    if api_key:
        headers["X-Goog-Api-Key"] = api_key
        return headers, "header:X-Goog-Api-Key"

    raise ConfigError(
        "Cloud TTS Chirp 3 HD requires GOOGLE_CLOUD_ACCESS_TOKEN, GOOGLE_CLOUD_API_KEY "
        "(sent via X-Goog-Api-Key header), or an authenticated 'gcloud' session."
    )


def run_chirp3_tts(
    *,
    text: str,
    voice_name: str,
    locale: str,
    speaking_rate: float,
    pronunciations: Sequence[str] | None,
    chirp_cloning_key: str | None,
    staging_dir: Path,
    http_transport: HttpTransportCallable = default_http_transport,
    runner: RunnerCallable = default_runner,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Synthesize speech via Cloud TTS ``Chirp 3: HD`` or Instant Custom Voice REST."""
    if not (0.25 <= float(speaking_rate) <= 2.0):
        raise ConfigError(
            f"--speaking-rate for Chirp 3 HD must be between 0.25 and 2.0 (got {speaking_rate})."
        )
    pauses = validate_chirp3_text_markup(text)
    pron_entries = parse_pronunciation_specs(pronunciations)
    base_url = resolve_api_base_url("FORGE_CLOUD_TTS_BASE_URL", DEFAULT_CLOUD_TTS_BASE_URL, env=env)
    headers, auth_source = resolve_cloud_tts_auth_headers(env=env, runner=runner)

    active_env = env if env is not None else os.environ
    loc = locale.strip() or "en-US"
    cloning_key = (
        chirp_cloning_key
        if chirp_cloning_key is not None
        else active_env.get("CHIRP_VOICE_CLONING_KEY", "")
    ).strip()
    if cloning_key:
        endpoint = f"{base_url}/v1beta1/text:synthesize"
        voice_block: dict[str, Any] = {
            "languageCode": loc,
            "voiceClone": {"voiceCloningKey": cloning_key},
        }
        resolved_voice_label = f"{loc}-Chirp3-InstantCustomVoice"
    else:
        endpoint = f"{base_url}/v1/text:synthesize"
        full_voice = format_chirp3_voice_name(voice_name, locale=loc)
        resolved_loc = "-".join(full_voice.split("-")[:2])
        voice_block = {"languageCode": resolved_loc, "name": full_voice}
        resolved_voice_label = full_voice

    # Chirp 3: HD interprets [pause*] tags only in input.markup, not input.text.
    input_block: dict[str, Any] = {"markup": text.strip()} if pauses else {"text": text.strip()}
    if pron_entries:
        input_block["customPronunciations"] = {"pronunciations": pron_entries}

    req_body = {
        "input": input_block,
        "voice": voice_block,
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": audio_dsp.BROADCAST_SAMPLE_RATE,
            "speakingRate": round(float(speaking_rate), 3),
        },
    }

    resp = http_transport(
        "POST",
        endpoint,
        headers,
        json.dumps(req_body).encode("utf-8"),
        120,
    )
    try:
        doc = json.loads(resp.body.decode("utf-8"))
    except ValueError as exc:
        raise AudioEngineError("Malformed JSON returned by Cloud TTS synthesize endpoint.") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("audioContent"), str):
        raise AudioEngineError("Cloud TTS response missing base64 'audioContent'.")

    raw_audio = base64.b64decode(doc["audioContent"])
    wav_bytes = _wrap_pcm16_as_wav_if_raw(raw_audio, sample_rate=audio_dsp.BROADCAST_SAMPLE_RATE)
    audio_dsp.require_valid_audio(wav_bytes, label="Chirp 3 HD audioContent", require_wav=True)

    out_wav = staging_dir / "chirp3_hd.wav"
    out_wav.write_bytes(wav_bytes)
    return {
        "path": out_wav,
        "model_used": resolved_voice_label,
        "endpoint_version": "v1beta1" if cloning_key else "v1",
        "auth_source": auth_source,
        "pronunciation_count": len(pron_entries),
    }


# ---------------------------------------------------------------------------
# Engine D: SFX, Foley & Musical Stingers
# ---------------------------------------------------------------------------


def run_sfx_or_stinger(
    *,
    prompt: str,
    mode: str,
    sfx_engine: str,
    explicit_model: str | None,
    duration_s: float,
    bed_style: str,
    musical_key: str | None,
    bpm: int | None,
    creative_sound_dir: Path | None,
    staging_dir: Path,
    runner: RunnerCallable,
    ffmpeg_bin: str | None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Generate SFX foley or musical stinger across the four supported SFX engines."""
    chosen = sfx_engine.strip().lower() if sfx_engine else "auto"
    if chosen not in ("auto", "omni-foley", "lyria-sting", "lavfi-synth", "creative-bed"):
        raise ConfigError(
            f"Unsupported --sfx-engine '{sfx_engine}'. Choose from: "
            f"auto, omni-foley, lyria-sting, lavfi-synth, creative-bed."
        )
    if chosen == "auto":
        chosen = "lyria-sting" if mode == "stinger" else "omni-foley"

    if chosen == "lyria-sting":
        if duration_s > LYRIA_CLIP_MAX_SEGMENT_S:
            raise ConfigError(
                f"'lyria-sting' supports <= {int(LYRIA_CLIP_MAX_SEGMENT_S)}s cues (got {duration_s}s)."
            )
        lyria_model = validate_audio_model_id(explicit_model, role="music") if explicit_model else CLIP_MUSIC_MODEL
        res = run_lyria_generation(
            raw_prompt=prompt,
            mode="stinger",
            explicit_model=lyria_model,
            duration_s=duration_s,
            crossfade_s=1.0,
            image_refs=(),
            genre=None,
            bpm=bpm,
            musical_key=musical_key,
            mood=None,
            instruments=None,
            lyrics=None,
            language=None,
            staging_dir=staging_dir,
            prefer_wav=True,
            runner=runner,
            ffmpeg_bin=ffmpeg_bin,
            sleep_fn=sleep_fn,
        )
        res["sfx_engine"] = "lyria-sting"
        return res

    if chosen == "omni-foley":
        int_dur = int(round(duration_s))
        if not (3 <= int_dur <= 15):
            raise ConfigError(
                f"'omni-foley' (gemini-omni-1.2-flash) requires --duration between 3s and 15s (got {duration_s}s)."
            )
        if not ffmpeg_bin:
            raise AudioEngineError("'omni-foley' requires ffmpeg to extract 48kHz 24-bit WAV audio.")
        foley_model = validate_audio_model_id(explicit_model, role="sfx") if explicit_model else OMNI_FOLEY_MODEL
        tmp_mp4 = staging_dir / "omni_foley_raw.mp4"
        foley_prompt = normalize_cli_positional_prompt(
            f"{prompt.strip().rstrip('.')}. Isolated high-fidelity foley sound effect, "
            f"clean studio acoustics, zero background music, zero spoken dialogue.",
            verbatim_speech=False,
        )
        body = json.dumps({"response_format": {"duration": f"{int_dur}s"}}, separators=(",", ":"))
        vid_cmd = [
            "gemini-api",
            "video",
            foley_prompt,
            "-m",
            foley_model,
            "--aspect-ratio",
            "16:9",
            "--resolution",
            "360p",
            "--body",
            body,
            "--out",
            str(tmp_mp4),
            "-o",
            "json",
        ]
        vid_res = runner(vid_cmd)
        if vid_res.returncode != 0:
            raise AudioEngineError(f"gemini-omni-1.2-flash foley generation failed: {vid_res.stderr.strip()}")
        actual_mp4, rid = _confine_cli_output_path(vid_res.stdout, tmp_mp4, staging_dir)

        out_wav = staging_dir / "omni_foley_48k.wav"
        ext_res = runner(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                audio_dsp._ffmpeg_input_path(actual_mp4),
                "-vn",
                "-acodec",
                "pcm_s24le",
                "-ar",
                str(audio_dsp.BROADCAST_SAMPLE_RATE),
                str(out_wav.resolve()),
            ]
        )
        if ext_res.returncode != 0:
            raise AudioEngineError(f"ffmpeg foley audio extraction failed: {ext_res.stderr.strip()}")
        audio_dsp.require_valid_audio(out_wav, label="extracted omni-foley WAV", require_wav=True)
        return {
            "path": out_wav,
            "model_used": foley_model,
            "sfx_engine": "omni-foley",
            "response_ids": [rid] if rid else [],
        }

    if chosen == "creative-bed":
        if creative_sound_dir is None:
            raise ConfigError(
                "'--sfx-engine creative-bed' requires creative-stack (/sound) to be installed."
            )
        bed_py = creative_sound_dir / "scripts" / "bed.py"
        if not bed_py.is_file():
            raise ConfigError("creative-stack sound/scripts/bed.py not found.")
        print("INFO: Delegating stinger cue to creative-stack sound/scripts/bed.py", file=sys.stderr)
        out_wav = staging_dir / "creative_bed_sting.wav"
        cmd = [sys.executable, str(bed_py), "-o", str(out_wav), "--style", bed_style or "corporate", "--sting"]
        if musical_key:
            cmd.extend(["--key", musical_key])
        if bpm is not None:
            cmd.extend(["--bpm", str(bpm)])
        bed_res = runner(cmd)
        if bed_res.returncode != 0:
            raise AudioEngineError(f"creative-stack bed.py --sting failed: {bed_res.stderr.strip()}")
        audio_dsp.require_valid_audio(out_wav, label="creative-bed sting WAV")
        return {
            "path": out_wav,
            "model_used": f"creative-stack:bed.py:{bed_style or 'corporate'}",
            "delegate_script": "sound/scripts/bed.py",
            "sfx_engine": "creative-bed",
            "response_ids": [],
        }

    # lavfi-synth deterministic procedural acoustic cue
    if not ffmpeg_bin:
        raise AudioEngineError("'--sfx-engine lavfi-synth' requires ffmpeg.")
    dur = max(0.25, min(30.0, float(duration_s)))
    low_p = prompt.lower()
    if any(k in low_p for k in ("whoosh", "wind", "sweep", "noise")):
        lavfi_src = f"anoisesrc=d={dur:.3f}:c=pink:r={audio_dsp.BROADCAST_SAMPLE_RATE}:a=0.35"
        post_af = f"bandpass=f=900:width_type=h:w=600,afade=t=in:st=0:d={min(0.25, dur * 0.3):.3f},afade=t=out:st={max(0.0, dur * 0.45):.3f}:d={max(0.1, dur * 0.55):.3f}"
    elif any(k in low_p for k in ("bass", "impact", "boom", "thud")):
        lavfi_src = f"sine=frequency=68:sample_rate={audio_dsp.BROADCAST_SAMPLE_RATE}:duration={dur:.3f}"
        post_af = f"volume=0.6,afade=t=out:st=0.05:d={max(0.1, dur - 0.05):.3f}"
    else:
        lavfi_src = f"sine=frequency=660:sample_rate={audio_dsp.BROADCAST_SAMPLE_RATE}:duration={dur:.3f}"
        post_af = f"volume=0.45,afade=t=in:st=0:d=0.02,afade=t=out:st={max(0.02, dur * 0.3):.3f}:d={max(0.05, dur * 0.7):.3f}"

    out_wav = staging_dir / "lavfi_synth_cue.wav"
    synth_res = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            lavfi_src,
            "-af",
            post_af,
            "-ar",
            str(audio_dsp.BROADCAST_SAMPLE_RATE),
            "-c:a",
            "pcm_s24le",
            str(out_wav.resolve()),
        ]
    )
    if synth_res.returncode != 0:
        raise AudioEngineError(f"ffmpeg lavfi-synth failed: {synth_res.stderr.strip()}")
    audio_dsp.require_valid_audio(out_wav, label="lavfi-synth WAV", require_wav=True)
    return {
        "path": out_wav,
        "model_used": "ffmpeg:lavfi-synth",
        "sfx_engine": "lavfi-synth",
        "response_ids": [],
    }
