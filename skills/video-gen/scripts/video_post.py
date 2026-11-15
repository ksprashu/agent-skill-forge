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

"""Post-composite text/captions/motion-cards, audio scoring/ducking/mastering,
and ``creative-stack`` (``/vidkit`` & ``/sound``) bridge for ``skills/video-gen``.

100% Python 3.12 standard library (Engineering Standard S1-S9, V1-V6):
  * Capture-time credential redaction (``SECRET_PATTERNS``, including bare
    ``key=<16+ token chars>``) and ``shell=False`` subprocess execution (``S4``, ``S8``).
  * Dynamic ``creative-stack`` discovery (``--creative-stack auto|off|<dir>``)
    across ``$CREATIVE_STACK_ROOT`` and ``~/.{agents,gemini,claude}/skills``
    for ``vidkit`` and ``sound`` with zero hardcoded usernames (``S5``, ``K7``).
  * Keg-only ``ffmpeg-full`` binary resolution (``$CREATIVE_STACK_FFMPEG`` ->
    ``/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`` ->
    ``/usr/local/opt/ffmpeg-full/bin/ffmpeg`` -> ``shutil.which("ffmpeg")``)
    plus ``ffmpeg -filters`` capability probing (``libass``/``subtitles``/``ass``/``drawtext``).
  * Subtitle (``.srt`` / ``.json``) and audio magic-byte (WAV, MP3, FLAC, OGG, M4A)
    pre-processing gates (``exit 2`` on missing, corrupt, or non-audio inputs).
  * Broadcast DSP invariants: 2-pass linear ``loudnorm`` at ``48000 Hz`` with
    ``dual_mono=true`` on mono voiceovers, explicit speech-window ``volume``
    envelope ducking via ``silencedetect`` (never ``sidechaincompress``), and
    ``amix=normalize=0``.

Audit scope & unchecked-surface reporting (Engineering Standard V3 / V5):
  * ``validate_audio_magic_bytes`` audits binary container headers of local
    audio stems (WAV/MP3/FLAC/OGG/M4A); it does not decode compressed frames.
  * ``validate_and_parse_subtitles`` audits ``.srt`` and ``.json`` cue syntax,
    monotonic positive timing, and non-empty text; it does not judge translation quality.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ---------------------------------------------------------------------------
# Shared Subprocess, Redaction & Host-Path Sanitation (S4, S7, S8, K7)
# ---------------------------------------------------------------------------

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
        re.compile(r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY)["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'),
    ),
    (
        "Env API key assignment",
        re.compile(r"(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY)[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')"),
    ),
    (
        "Env API key assignment",
        re.compile(
            r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY)["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
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
        "URL query credential",
        re.compile(r"(?i)([?&](?:key|api_key|access_token)=)(?!\[REDACTED\b)[^&\s\"']+"),
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
    ("PEM private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
)

AUDIO_SAMPLE_RATE = 48000
DEFAULT_LUFS_TARGET = -14.0
DEFAULT_TRUE_PEAK_DBTP = -1.0
DEFAULT_LRA = 11.0
DEFAULT_DUCK_DB = 14.0

VALID_CAPTION_STYLES: tuple[str, ...] = ("pill", "highlight", "karaoke", "soft")

DEFAULT_AUDIO_GEN_SCRIPT = (
    Path(__file__).resolve().parents[2] / "audio-gen" / "scripts" / "audio_gen.py"
)

DEFAULT_FFMPEG_FULL_DIRS: tuple[Path, ...] = (
    Path("/opt/homebrew/opt/ffmpeg-full/bin"),
    Path("/usr/local/opt/ffmpeg-full/bin"),
)

_FILES_URI_RE = re.compile(r"^files/[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]


RunnerCallable = Callable[[Sequence[str]], CommandResult]
WhichCallable = Callable[[str], str | None]


def redact_secrets(text: str) -> str:
    """Redact API keys, tokens, and credential query parameters at capture time (Rule S8)."""
    if not text:
        return ""
    cleaned = text
    for label, pattern in SECRET_PATTERNS:
        if label == "URL query credential":
            cleaned = pattern.sub(r"\1[REDACTED]", cleaned)
        elif label in ("Env API key assignment", "API key field", "Credential key assignment"):
            cleaned = pattern.sub(rf"\1[REDACTED:{label}]", cleaned)
        else:
            cleaned = pattern.sub(f"[REDACTED:{label}]", cleaned)
    return cleaned


def safe_ffmpeg_path(path: Path | str) -> str:
    """Resolve local filesystem path to an absolute string so FFmpeg never parses `-` or `concat:` as flags/protocols (CWE-88)."""
    raw = str(path)
    if "\x00" in raw or not raw.strip():
        raise ValueError("Media filesystem path must be a non-empty string without null bytes.")
    return str(Path(raw).expanduser().resolve())


def is_files_uri(val: str) -> bool:
    return bool(_FILES_URI_RE.fullmatch(val.strip()))


def contract_home(path: Path | str) -> str:
    """Replace user home directory prefix with ~ to prevent host-path leaks (K7)."""
    if isinstance(path, str) and is_files_uri(path):
        return path.strip()
    raw = str(Path(path).resolve())
    home = str(Path.home().resolve())
    if raw == home:
        return "~"
    sep = os.sep
    if raw.startswith(home + sep):
        return "~/" + raw[len(home) + 1 :].replace("\\", "/")
    return raw.replace("\\", "/")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_runner(argv: Sequence[str], *, timeout: int = 900) -> CommandResult:
    """Execute a subprocess with an explicit arg list and shell=False (S4, S8)."""
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
        return CommandResult(
            returncode=124,
            stdout=redact_secrets(str(exc.stdout or "")),
            stderr=redact_secrets(f"Command timed out after {timeout}s: {cmd_tuple[0]}"),
            argv=cmd_tuple,
        )


# ---------------------------------------------------------------------------
# Creative-Stack Skill Discovery & Keg-Only `ffmpeg-full` Resolver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreativeStackInfo:
    mode: str
    enabled: bool
    source: str
    vidkit_dir: Path | None = None
    sound_dir: Path | None = None
    captions_script: Path | None = None
    motion_script: Path | None = None
    mix_script: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "source": self.source,
            "vidkit_available": self.captions_script is not None or self.motion_script is not None,
            "sound_available": self.mix_script is not None,
            "vidkit_dir": contract_home(self.vidkit_dir) if self.vidkit_dir else None,
            "sound_dir": contract_home(self.sound_dir) if self.sound_dir else None,
        }


def _probe_skill_root(base: Path, skill_name: str) -> Path | None:
    for candidate in (base / "skills" / skill_name, base / skill_name):
        if (candidate / "scripts").is_dir():
            return candidate.resolve()
    return None


def discover_creative_stack(
    mode_or_dir: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
    home_dir: Path | None = None,
) -> CreativeStackInfo:
    """Discover `vidkit` and `sound` skills dynamically without hardcoded paths (S5, K7)."""
    cleaned = (mode_or_dir or "auto").strip()
    if not cleaned or "\x00" in cleaned:
        raise ValueError("Invalid --creative-stack value.")

    if cleaned.lower() == "off":
        return CreativeStackInfo(mode="off", enabled=False, source="off")

    effective_env = os.environ if env is None else env
    effective_home = (home_dir or Path.home()).resolve()

    if cleaned.lower() != "auto":
        explicit_base = Path(cleaned).expanduser().resolve()
        if not explicit_base.is_dir():
            raise ValueError(
                f"--creative-stack directory not found: {contract_home(explicit_base)}"
            )
        vidkit = _probe_skill_root(explicit_base, "vidkit")
        sound = _probe_skill_root(explicit_base, "sound")
        if vidkit is None and sound is None:
            raise ValueError(
                f"--creative-stack directory '{contract_home(explicit_base)}' contains neither "
                "'vidkit/scripts' nor 'sound/scripts'."
            )
        captions = (vidkit / "scripts" / "captions.py") if vidkit and (vidkit / "scripts" / "captions.py").is_file() else None
        motion = (vidkit / "scripts" / "motion.py") if vidkit and (vidkit / "scripts" / "motion.py").is_file() else None
        mix = (sound / "scripts" / "mix.py") if sound and (sound / "scripts" / "mix.py").is_file() else None
        return CreativeStackInfo(
            mode="explicit",
            enabled=bool(captions or motion or mix),
            source="explicit",
            vidkit_dir=vidkit,
            sound_dir=sound,
            captions_script=captions,
            motion_script=motion,
            mix_script=mix,
        )

    candidates: list[tuple[str, Path]] = []
    env_root = effective_env.get("CREATIVE_STACK_ROOT", "").strip()
    if env_root:
        candidates.append(("env:CREATIVE_STACK_ROOT", Path(env_root).expanduser()))
    candidates.extend(
        [
            ("home:.agents/skills", effective_home / ".agents" / "skills"),
            ("home:.gemini/skills", effective_home / ".gemini" / "skills"),
            ("home:.claude/skills", effective_home / ".claude" / "skills"),
        ]
    )

    found_vidkit: Path | None = None
    found_sound: Path | None = None
    sources: list[str] = []

    for label, base in candidates:
        if not base.is_dir():
            continue
        if found_vidkit is None:
            vk = _probe_skill_root(base, "vidkit")
            if vk is not None:
                found_vidkit = vk
                if label not in sources:
                    sources.append(label)
        if found_sound is None:
            sd = _probe_skill_root(base, "sound")
            if sd is not None:
                found_sound = sd
                if label not in sources:
                    sources.append(label)
        if found_vidkit is not None and found_sound is not None:
            break

    captions = (
        (found_vidkit / "scripts" / "captions.py")
        if found_vidkit and (found_vidkit / "scripts" / "captions.py").is_file()
        else None
    )
    motion = (
        (found_vidkit / "scripts" / "motion.py")
        if found_vidkit and (found_vidkit / "scripts" / "motion.py").is_file()
        else None
    )
    mix = (
        (found_sound / "scripts" / "mix.py")
        if found_sound and (found_sound / "scripts" / "mix.py").is_file()
        else None
    )
    return CreativeStackInfo(
        mode="auto",
        enabled=bool(captions or motion or mix),
        source="+".join(sources) if sources else "none",
        vidkit_dir=found_vidkit,
        sound_dir=found_sound,
        captions_script=captions,
        motion_script=motion,
        mix_script=mix,
    )


_SYSTEM_FFMPEG_BIN_DIRS: frozenset[str] = frozenset(
    {
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/opt/local/bin",
    }
)


def resolve_ffmpeg_binary(
    tool: str = "ffmpeg",
    *,
    env: Mapping[str, str] | None = None,
    which_fn: WhichCallable = shutil.which,
    ffmpeg_full_dirs: Sequence[Path] | None = None,
) -> str | None:
    """Resolve `ffmpeg`/`ffprobe` preferring keg-only `ffmpeg-full` over stock system builds.

    Precedence:
      1. ``$CREATIVE_STACK_FFMPEG`` (or ``$CREATIVE_STACK_FFPROBE`` / sibling of ``$CREATIVE_STACK_FFMPEG``)
      2. ``/opt/homebrew/opt/ffmpeg-full/bin/<tool>``
      3. ``/usr/local/opt/ffmpeg-full/bin/<tool>``
      4. ``which_fn(tool)`` (``shutil.which("ffmpeg")``)
    """
    if tool not in ("ffmpeg", "ffprobe"):
        return which_fn(tool)

    effective_env = os.environ if env is None else env
    direct_override = effective_env.get(f"CREATIVE_STACK_{tool.upper()}", "").strip()
    if direct_override:
        return direct_override

    if tool == "ffprobe":
        ffmpeg_override = effective_env.get("CREATIVE_STACK_FFMPEG", "").strip()
        if ffmpeg_override:
            sibling = Path(ffmpeg_override).expanduser().parent / "ffprobe"
            if sibling.is_file() and os.access(sibling, os.X_OK):
                return str(sibling)

    path_hit = which_fn(tool)

    # If a custom non-system directory (such as a hermetic test shim on PATH) was
    # prepended ahead of standard OS/Homebrew directories and `ffmpeg_full_dirs`
    # was not explicitly injected, honour that explicit PATH shim.
    if (
        ffmpeg_full_dirs is None
        and which_fn is shutil.which
        and path_hit is not None
        and str(Path(path_hit).parent) not in _SYSTEM_FFMPEG_BIN_DIRS
    ):
        return path_hit

    search_dirs: Sequence[Path]
    if ffmpeg_full_dirs is not None:
        search_dirs = ffmpeg_full_dirs
    elif which_fn is shutil.which:
        search_dirs = DEFAULT_FFMPEG_FULL_DIRS
    else:
        search_dirs = ()

    for directory in search_dirs:
        candidate = Path(directory) / tool
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return path_hit


_FILTER_LINE_RE = re.compile(r"^\s*[TSC.]{2,4}\s+([A-Za-z0-9_]+)\s+", re.MULTILINE)


def probe_ffmpeg_capabilities(
    ffmpeg_bin: str | None,
    *,
    runner: RunnerCallable = default_runner,
) -> dict[str, bool]:
    """Probe `ffmpeg -filters` for subtitle, text, audioloudnorm, and xfade support."""
    empty = {
        "available": False,
        "libass": False,
        "subtitles": False,
        "ass": False,
        "drawtext": False,
        "loudnorm": False,
        "xfade": False,
        "acrossfade": False,
    }
    if not ffmpeg_bin:
        return empty

    res = runner([ffmpeg_bin, "-hide_banner", "-filters"])
    if res.returncode != 0:
        return empty

    found = {m.group(1) for m in _FILTER_LINE_RE.finditer(res.stdout or "")}
    has_subtitles = "subtitles" in found
    has_ass = "ass" in found
    return {
        "available": True,
        "libass": has_subtitles or has_ass,
        "subtitles": has_subtitles,
        "ass": has_ass,
        "drawtext": "drawtext" in found,
        "loudnorm": "loudnorm" in found,
        "xfade": "xfade" in found,
        "acrossfade": "acrossfade" in found,
    }


# ---------------------------------------------------------------------------
# Pure-Stdlib Subtitle, Card & Audio Magic-Byte Validators (Exit 2 Gates)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class LowerThirdSpec:
    name: str
    role: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class SfxCueSpec:
    path: Path
    start_s: float
    gain_db: float = 0.0


def validate_safe_local_file(raw_path: str, *, label: str) -> Path:
    """Validate path safety (no null bytes or URL schemes) and existence."""
    cleaned = (raw_path or "").strip()
    if not cleaned or "\x00" in cleaned:
        raise ValueError(f"{label} path must be a non-empty local filesystem path.")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", cleaned):
        raise ValueError(f"{label} must be a local file path, not a remote URL: {cleaned!r}")
    resolved = Path(cleaned).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} file not found: {contract_home(resolved)}")
    return resolved


def validate_audio_magic_bytes(path: Path | str, *, label: str = "Audio file") -> str:
    """Verify local audio file magic bytes (WAV, MP3, FLAC, OGG, M4A); raise ValueError on mismatch."""
    resolved = validate_safe_local_file(str(path), label=label)
    try:
        with resolved.open("rb") as fh:
            header = fh.read(64)
    except OSError as exc:
        raise ValueError(f"Cannot read {label} '{contract_home(resolved)}': {exc}") from exc

    size = resolved.stat().st_size
    if size < 16 or len(header) < 12:
        raise ValueError(
            f"{label} '{contract_home(resolved)}' is empty or truncated ({size} bytes)."
        )

    # 1. RIFF....WAVE
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        if size < 44:
            raise ValueError(
                f"{label} '{contract_home(resolved)}' has truncated RIFF WAVE header ({size} bytes)."
            )
        return "wav"

    # 2. FLAC
    if header[:4] == b"fLaC":
        return "flac"

    # 3. Ogg (Vorbis / Opus)
    if header[:4] == b"OggS":
        return "ogg"

    # 4. ISO BMFF M4A / MP4 audio
    if header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"M4A ", b"M4B ", b"mp42", b"isom", b"iso2", b"dash", b"f4v "):
            return "m4a"
        raise ValueError(
            f"{label} '{contract_home(resolved)}' has unsupported ftyp brand {brand!r} for audio."
        )

    # 5. MP3: ID3v2 tag or MPEG audio frame sync (11-bit sync 0xFFE0, valid version & layer != 0)
    if header[:3] == b"ID3":
        return "mp3"
    if (
        header[0] == 0xFF
        and (header[1] & 0xE0) == 0xE0
        and ((header[1] >> 3) & 0x03) != 0x01
        and ((header[1] >> 1) & 0x03) != 0x00
    ):
        return "mp3"

    raise ValueError(
        f"{label} '{contract_home(resolved)}' failed audio magic-byte inspection "
        "(expected WAV 'RIFF..WAVE', MP3 'ID3'/sync, FLAC 'fLaC', OGG 'OggS', or M4A 'ftyp')."
    )


_SRT_TIME_RE = re.compile(
    r"^\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})(?:\s+.*)?$"
)


def _hms_ms_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    millis = int(ms.ljust(3, "0")[:3])
    mins = int(m)
    secs = int(s)
    if mins >= 60 or secs >= 60:
        raise ValueError(f"Invalid minute/second in SRT timestamp: {h}:{m}:{s},{ms}")
    return int(h) * 3600.0 + mins * 60.0 + secs + millis / 1000.0


def parse_srt_text(raw_text: str, *, source_label: str = "SRT") -> list[SubtitleCue]:
    """Strictly parse and validate SRT subtitle text; raise ValueError on corrupt blocks."""
    cleaned = raw_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise ValueError(f"{source_label} subtitle file is empty.")

    blocks = re.split(r"\n\s*\n", cleaned)
    cues: list[SubtitleCue] = []
    for blk_idx, block in enumerate(blocks, start=1):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip() != "" or False]
        raw_lines = block.splitlines()
        # Strip leading blank lines inside block
        while raw_lines and not raw_lines[0].strip():
            raw_lines.pop(0)
        if not raw_lines:
            continue

        time_line_idx = 0
        if re.fullmatch(r"\d+", raw_lines[0].strip()):
            if len(raw_lines) < 2:
                raise ValueError(f"{source_label} cue block {blk_idx} has index line without timestamp.")
            time_line_idx = 1

        time_line = raw_lines[time_line_idx]
        m = _SRT_TIME_RE.match(time_line)
        if not m:
            raise ValueError(
                f"{source_label} cue block {blk_idx} has malformed timestamp line: {time_line!r}"
            )
        start_s = _hms_ms_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end_s = _hms_ms_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        if end_s <= start_s:
            raise ValueError(
                f"{source_label} cue block {blk_idx} end time ({end_s:.3f}s) must exceed start time ({start_s:.3f}s)."
            )

        body_lines = [ln.strip() for ln in raw_lines[time_line_idx + 1 :] if ln.strip()]
        if not body_lines:
            raise ValueError(f"{source_label} cue block {blk_idx} contains empty subtitle text.")

        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_s=start_s,
                end_s=end_s,
                text="\n".join(body_lines),
            )
        )

    if not cues:
        raise ValueError(f"{source_label} subtitle file contains zero valid cues.")
    return cues


def validate_and_parse_subtitles(
    *,
    srt_path: str | None = None,
    captions_json_path: str | None = None,
) -> list[SubtitleCue]:
    """Validate `--srt` or `--captions-json` and return normalized non-empty `SubtitleCue` items."""
    if srt_path and captions_json_path:
        raise ValueError("--srt and --captions-json are mutually exclusive; pass one subtitle source.")
    if srt_path:
        resolved = validate_safe_local_file(srt_path, label="--srt")
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"--srt '{contract_home(resolved)}' is not valid UTF-8 text: {exc}") from exc
        return parse_srt_text(content, source_label=f"--srt '{contract_home(resolved)}'")

    if captions_json_path:
        resolved = validate_safe_local_file(captions_json_path, label="--captions-json")
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(
                f"Invalid JSON in --captions-json '{contract_home(resolved)}': {exc}"
            ) from exc

        raw_items: Any
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict):
            if isinstance(payload.get("cues"), list):
                raw_items = payload["cues"]
            elif isinstance(payload.get("segments"), list):
                raw_items = payload["segments"]
            elif isinstance(payload.get("transcription"), list):
                # whisper.cpp -ojf compatibility
                raw_items = [
                    {
                        "start": float(item.get("offsets", {}).get("from", 0)) / 1000.0,
                        "end": float(item.get("offsets", {}).get("to", 0)) / 1000.0,
                        "text": str(item.get("text", "")),
                    }
                    for item in payload["transcription"]
                    if isinstance(item, dict)
                ]
            else:
                raise ValueError(
                    f"--captions-json '{contract_home(resolved)}' must be a list or contain 'cues'/'segments'/'transcription'."
                )
        else:
            raise ValueError(f"--captions-json '{contract_home(resolved)}' must be a JSON list or object.")

        cues: list[SubtitleCue] = []
        for idx, entry in enumerate(raw_items, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"--captions-json item {idx} must be a JSON object.")
            raw_start = entry.get("start", entry.get("start_s"))
            raw_end = entry.get("end", entry.get("end_s"))
            raw_txt = entry.get("text", "")
            if isinstance(raw_start, bool) or isinstance(raw_end, bool):
                raise ValueError(f"--captions-json item {idx} start/end must be numeric seconds.")
            try:
                start_s = float(raw_start)
                end_s = float(raw_end)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"--captions-json item {idx} has non-numeric start/end timestamps."
                ) from exc
            if (
                not math.isfinite(start_s)
                or not math.isfinite(end_s)
                or start_s < 0
                or end_s <= start_s
            ):
                raise ValueError(
                    f"--captions-json item {idx} requires finite 0 <= start < end (got {start_s}..{end_s})."
                )
            txt = str(raw_txt or "").strip()
            if not txt:
                raise ValueError(f"--captions-json item {idx} has empty caption text.")
            cues.append(SubtitleCue(index=len(cues) + 1, start_s=start_s, end_s=end_s, text=txt))

        if not cues:
            raise ValueError(f"--captions-json '{contract_home(resolved)}' contains zero valid cues.")
        return cues

    return []


def format_srt(cues: Sequence[SubtitleCue]) -> str:
    """Serialize normalized `SubtitleCue` entries back into standard SubRip `.srt` format."""
    blocks: list[str] = []
    for idx, cue in enumerate(cues, start=1):
        blocks.append(f"{idx}\n{_seconds_to_srt_ts(cue.start_s)} --> {_seconds_to_srt_ts(cue.end_s)}\n{cue.text}")
    return "\n\n".join(blocks) + "\n"


def _seconds_to_srt_ts(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000.0)))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def parse_title_card_spec(raw: str) -> tuple[str, str]:
    """Parse `--title-card "<title>[|<subtitle>]"`."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("--title-card cannot be empty.")
    if "|" in cleaned:
        title, subtitle = cleaned.split("|", 1)
        if not title.strip():
            raise ValueError("--title-card requires a non-empty <title> before '|'.")
        return title.strip(), subtitle.strip()
    return cleaned, ""


def parse_lower_third_spec(raw: str) -> LowerThirdSpec:
    """Parse `--lower-third "<name>|<role>@<start>-<end>"`."""
    cleaned = (raw or "").strip()
    if "@" not in cleaned or "|" not in cleaned:
        raise ValueError(
            f"Invalid --lower-third '{raw}'; expected '<name>|<role>@<start>-<end>' (e.g. 'Ada|Lead@1.5-4.5')."
        )
    left, span = cleaned.rsplit("@", 1)
    name, role = left.split("|", 1)
    if not name.strip():
        raise ValueError(f"Invalid --lower-third '{raw}'; <name> cannot be empty.")
    if "-" not in span:
        raise ValueError(f"Invalid --lower-third time range '{span}'; expected '<start>-<end>'.")
    s_raw, e_raw = span.split("-", 1)
    try:
        start_s = float(s_raw.strip().rstrip("s"))
        end_s = float(e_raw.strip().rstrip("s"))
    except ValueError as exc:
        raise ValueError(f"Invalid --lower-third timestamps in '{raw}'.") from exc
    if not math.isfinite(start_s) or not math.isfinite(end_s) or start_s < 0 or end_s <= start_s:
        raise ValueError(
            f"--lower-third '{raw}' requires finite 0 <= start < end (got {start_s}..{end_s})."
        )
    return LowerThirdSpec(
        name=name.strip(),
        role=role.strip(),
        start_s=start_s,
        end_s=end_s,
    )


def parse_end_card_spec(raw: str) -> tuple[str, str]:
    """Parse `--end-card "<cta>"` (or `"<title>|<cta>"`)."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("--end-card cannot be empty.")
    if "|" in cleaned:
        title, cta = cleaned.split("|", 1)
        return (title.strip() or cta.strip()), cta.strip()
    return cleaned, ""


def parse_sfx_cue_spec(raw: str) -> SfxCueSpec:
    """Parse `--sfx-cue "<path>@<sec>[:<gain_db>]"` and magic-byte inspect the audio file."""
    cleaned = (raw or "").strip()
    if "@" not in cleaned:
        raise ValueError(f"Invalid --sfx-cue '{raw}'; expected '<path>@<seconds>[:<gain_db>]'.")
    path_part, rest = cleaned.rsplit("@", 1)
    sec_part, sep, gain_part = rest.partition(":")
    try:
        start_s = float(sec_part.strip().rstrip("s"))
        gain_db = float(gain_part.strip()) if sep and gain_part.strip() else 0.0
    except ValueError as exc:
        raise ValueError(f"Invalid numeric offset/gain in --sfx-cue '{raw}'.") from exc
    if not math.isfinite(start_s) or start_s < 0:
        raise ValueError(f"--sfx-cue timestamp must be finite >= 0s (got {start_s}s).")
    if not math.isfinite(gain_db) or gain_db < -60.0 or gain_db > 24.0:
        raise ValueError(f"--sfx-cue gain_db must be finite in [-60.0, 24.0] (got {gain_db}).")
    resolved = validate_safe_local_file(path_part, label="--sfx-cue")
    validate_audio_magic_bytes(resolved, label="--sfx-cue")
    return SfxCueSpec(path=resolved, start_s=start_s, gain_db=gain_db)


# ---------------------------------------------------------------------------
# Pure-Stdlib ASS Subtitle Generator & RGBA PNG Motion-Card Fallback
# ---------------------------------------------------------------------------


def _ass_timestamp(seconds: float) -> str:
    clamped = max(0.0, seconds)
    hours, rem = divmod(clamped, 3600.0)
    minutes, secs = divmod(rem, 60.0)
    return f"{int(hours)}:{int(minutes):02d}:{secs:05.2f}"


def _escape_ass_text(text: str, max_chars: int = 42) -> str:
    plain = re.sub(r"</?[A-Za-z0-9]+>", "", text)
    plain = plain.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    wrapped: list[str] = []
    for line in plain.splitlines():
        wrapped.extend(textwrap.wrap(line, max_chars) or [""])
    return "\\N".join(wrapped[:3])


def build_standalone_ass(
    cues: Sequence[SubtitleCue],
    *,
    style: str = "pill",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Build an ASS v4+ subtitle script supporting `pill`, `highlight`, and `karaoke`."""
    font_size = max(28, int(round(height * 0.044)))
    margin_v = max(48, int(round(height * 0.075)))
    border_style = 3 if style == "pill" else 1
    outline_w = 14 if style == "pill" else 3
    back_col = "&H55181818" if style == "pill" else "&H80000000"
    primary_col = "&H00FFFFFF"
    secondary_col = "&H0048D1FF"

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_size},{primary_col},{secondary_col},{back_col},{back_col},"
        f"1,0,0,0,100,100,0,0,{border_style},{outline_w},0,2,80,80,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: list[str] = []
    for cue in cues:
        words = [w for w in cue.text.replace("\n", " ").split(" ") if w]
        dur_s = max(0.05, cue.end_s - cue.start_s)
        if style == "karaoke" and words:
            total_chars = max(1, sum(len(w) for w in words))
            parts: list[str] = []
            for w in words:
                cs = max(5, int(round((len(w) / total_chars) * dur_s * 100.0)))
                safe_w = w.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
                parts.append(f"{{\\kf{cs}}}{safe_w}")
            events.append(
                f"Dialogue: 0,{_ass_timestamp(cue.start_s)},{_ass_timestamp(cue.end_s)},Default,,0,0,0,,{' '.join(parts)}"
            )
        elif style == "highlight" and len(words) > 1:
            total_chars = max(1, sum(len(w) for w in words))
            cursor = cue.start_s
            for idx, active_word in enumerate(words):
                slice_dur = dur_s * (len(active_word) / total_chars)
                seg_end = cue.end_s if idx == len(words) - 1 else min(cue.end_s, cursor + slice_dur)
                rendered_words = []
                for jdx, w in enumerate(words):
                    safe_w = w.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
                    if jdx == idx:
                        rendered_words.append(f"{{\\c&H0048D1FF&}}{safe_w}{{\\c&H00FFFFFF&}}")
                    else:
                        rendered_words.append(safe_w)
                events.append(
                    f"Dialogue: 0,{_ass_timestamp(cursor)},{_ass_timestamp(seg_end)},Default,,0,0,0,,{' '.join(rendered_words)}"
                )
                cursor = seg_end
        else:
            events.append(
                f"Dialogue: 0,{_ass_timestamp(cue.start_s)},{_ass_timestamp(cue.end_s)},Default,,0,0,0,,{_escape_ass_text(cue.text)}"
            )
    return header + "\n".join(events) + "\n"


def _ffmpeg_filter_escape_path(path: Path) -> str:
    """Escape a filesystem path across both FFmpeg option (`av_opt`) and filtergraph levels without outer quotes."""
    raw = str(path.resolve()).replace("\\", "/")
    return (
        raw.replace("\\", "\\\\")
        .replace(":", "\\\\:")
        .replace("'", "\\\\\\'")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(" ", "\\ ")
    )


def _escape_drawtext(text: str) -> str:
    """Two-level escape for inline FFmpeg `drawtext=text=...:expansion=none` literals."""
    return (
        text.replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\\", "\\\\\\\\")
        .replace(":", "\\\\:")
        .replace("'", "\\\\\\'")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("%", "\\%")
        .replace(" ", "\\ ")
    )


def _write_drawtext_file(tmp_dir: Path, tag: str, text: str) -> Path:
    """Write normalized card text to a staged file for `drawtext=textfile=...:expansion=none`."""
    txt_file = tmp_dir / f"dt_{tag}.txt"
    clean = text.replace("\r\n", "\n").replace("\r", "\n")
    txt_file.write_text(clean, encoding="utf-8")
    return txt_file


# Compact 5x7 uppercase/ASCII bitmap glyphs for zero-dependency PNG card fallback
_GLYPH_5X7: dict[str, tuple[int, ...]] = {
    " ": (0, 0, 0, 0, 0, 0, 0),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    ",": (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    "/": (0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "|": (0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
}


def render_text_card_png(
    output_png: Path,
    *,
    primary_text: str,
    secondary_text: str = "",
    width: int = 720,
    height: int = 160,
) -> Path:
    """Render a translucent dark RGBA PNG card in pure Python 3.12 stdlib (no Pillow/freetype)."""
    buf = bytearray(width * height * 4)
    bg_rgba = bytes((18, 22, 31, 224))
    accent_rgba = bytes((56, 189, 248, 255))
    white_rgba = bytes((248, 250, 252, 255))
    muted_rgba = bytes((190, 205, 222, 255))

    row_bg = bg_rgba * width
    for y in range(height):
        start = y * width * 4
        buf[start : start + width * 4] = row_bg

    # Left accent bar (8px wide)
    for y in range(height):
        for x in range(min(8, width)):
            idx = (y * width + x) * 4
            buf[idx : idx + 4] = accent_rgba

    def _draw_line(text: str, origin_x: int, origin_y: int, scale: int, color: bytes) -> None:
        cursor_x = origin_x
        for ch in text.upper()[:48]:
            glyph = _GLYPH_5X7.get(ch, _GLYPH_5X7["?"])
            if cursor_x + 6 * scale >= width - 12:
                break
            for gy, row_bits in enumerate(glyph):
                for gx in range(5):
                    if (row_bits >> (4 - gx)) & 1:
                        for sy in range(scale):
                            py = origin_y + gy * scale + sy
                            if 0 <= py < height:
                                for sx in range(scale):
                                    px = cursor_x + gx * scale + sx
                                    if 0 <= px < width:
                                        p_idx = (py * width + px) * 4
                                        buf[p_idx : p_idx + 4] = color
            cursor_x += 6 * scale

    _draw_line(primary_text, 28, 34 if secondary_text else 56, 4, white_rgba)
    if secondary_text:
        _draw_line(secondary_text, 28, 96, 3, muted_rgba)

    raw_scanlines = bytearray()
    stride = width * 4
    for y in range(height):
        raw_scanlines.append(0)  # Filter type 0 (None)
        raw_scanlines.extend(buf[y * stride : (y + 1) * stride])

    ihdr_payload = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = (
        struct.pack(">I", 13)
        + b"IHDR"
        + ihdr_payload
        + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_payload) & 0xFFFFFFFF)
    )
    compressed = zlib.compress(bytes(raw_scanlines), level=6)
    idat = (
        struct.pack(">I", len(compressed))
        + b"IDAT"
        + compressed
        + struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    )
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_png.write_bytes(b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend)
    return output_png


# ---------------------------------------------------------------------------
# Post-Composite Captions & Motion Cards Execution
# ---------------------------------------------------------------------------


def apply_post_text_and_cards(
    input_video: Path,
    output_video: Path,
    *,
    video_duration_s: float,
    width: int = 1920,
    height: int = 1080,
    srt_path: str | None = None,
    captions_json_path: str | None = None,
    caption_style: str = "pill",
    title_card: str | None = None,
    lower_thirds: Sequence[str] = (),
    end_card: str | None = None,
    creative_stack: CreativeStackInfo,
    ffmpeg_bin: str | None,
    runner: RunnerCallable = default_runner,
) -> dict[str, Any]:
    """Composite motion cards and captions via `vidkit` or standalone `ffmpeg` fallbacks."""
    cues = validate_and_parse_subtitles(srt_path=srt_path, captions_json_path=captions_json_path)
    parsed_title = parse_title_card_spec(title_card) if title_card else None
    parsed_lts = [parse_lower_third_spec(spec) for spec in lower_thirds]
    parsed_end = parse_end_card_spec(end_card) if end_card else None

    has_cards = bool(parsed_title or parsed_lts or parsed_end)
    has_captions = len(cues) > 0
    if not has_cards and not has_captions:
        if input_video.resolve() != output_video.resolve():
            output_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_video, output_video)
        return {
            "applied": False,
            "caption_renderer": None,
            "card_renderer": None,
            "cues_count": 0,
            "cards_applied": 0,
        }

    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg is required for post-composite captions and motion cards "
            "(install ffmpeg-full or set CREATIVE_STACK_FFMPEG)."
        )

    caps = probe_ffmpeg_capabilities(ffmpeg_bin, runner=runner)
    card_renderer: str | None = None
    caption_renderer: str | None = None
    cards_count = (1 if parsed_title else 0) + len(parsed_lts) + (1 if parsed_end else 0)

    with tempfile.TemporaryDirectory(prefix="video-gen-post-text-") as tmp_str:
        tmp_dir = Path(tmp_str)
        current = input_video
        step_idx = 0

        def _next_stage(suffix: str = ".mp4") -> Path:
            nonlocal step_idx
            step_idx += 1
            return tmp_dir / f"stage_{step_idx:02d}{suffix}"

        # 1. Motion Cards (before captions so burned captions never get covered by cards)
        if has_cards:
            title_dur = min(3.5, max(1.5, video_duration_s * 0.35))
            end_dur = min(3.5, max(1.5, video_duration_s * 0.35))
            end_start = max(0.0, video_duration_s - end_dur)

            delegated_cards_ok = False
            if creative_stack.enabled and creative_stack.motion_script is not None:
                delegated_cards_ok = True
                motion_py = str(creative_stack.motion_script)
                card_jobs: list[tuple[list[str], Path]] = []
                if parsed_title:
                    t_main, t_sub = parsed_title
                    dst = _next_stage()
                    cmd = [
                        sys.executable,
                        motion_py,
                        "-t",
                        "title",
                        "--overlay-on",
                        safe_ffmpeg_path(current),
                        "--at",
                        "0",
                        "-d",
                        f"{title_dur:.2f}",
                        "-o",
                        safe_ffmpeg_path(dst),
                        "-p",
                        f"title={t_main}",
                    ]
                    if t_sub:
                        cmd.extend(["-p", f"subtitle={t_sub}"])
                    card_jobs.append((cmd, dst))
                    current = dst

                for lt in parsed_lts:
                    dst = _next_stage()
                    cmd = [
                        sys.executable,
                        motion_py,
                        "-t",
                        "lower-third",
                        "--overlay-on",
                        safe_ffmpeg_path(current),
                        "--at",
                        f"{lt.start_s:.2f}",
                        "-d",
                        f"{lt.end_s - lt.start_s:.2f}",
                        "-o",
                        safe_ffmpeg_path(dst),
                        "-p",
                        f"name={lt.name}",
                        "-p",
                        f"role={lt.role}",
                    ]
                    card_jobs.append((cmd, dst))
                    current = dst

                if parsed_end:
                    e_title, e_cta = parsed_end
                    dst = _next_stage()
                    cmd = [
                        sys.executable,
                        motion_py,
                        "-t",
                        "end-card",
                        "--overlay-on",
                        safe_ffmpeg_path(current),
                        "--at",
                        f"{end_start:.2f}",
                        "-d",
                        f"{end_dur:.2f}",
                        "-o",
                        safe_ffmpeg_path(dst),
                        "-p",
                        f"title={e_title}",
                    ]
                    if e_cta:
                        cmd.extend(["-p", f"cta={e_cta}"])
                    card_jobs.append((cmd, dst))
                    current = dst

                stage_before_cards = input_video
                for cmd, expected_dst in card_jobs:
                    expected_dst.unlink(missing_ok=True)
                    res = runner(cmd)
                    if (
                        res.returncode != 0
                        or not expected_dst.is_file()
                        or expected_dst.stat().st_size == 0
                    ):
                        expected_dst.unlink(missing_ok=True)
                        print(
                            f"[video-gen] WARNING: vidkit motion.py failed ({res.stderr.strip() or 'missing output'}); "
                            "falling back to standalone ffmpeg card renderer.",
                            file=sys.stderr,
                        )
                        delegated_cards_ok = False
                        current = stage_before_cards
                        break
                if delegated_cards_ok:
                    card_renderer = "creative-stack:vidkit/motion.py"

            if not delegated_cards_ok:
                dst = _next_stage()
                if caps["drawtext"]:
                    vf_parts: list[str] = []
                    dt_seq = 0

                    def _dt_textfile_opt(label: str, text_val: str) -> str:
                        nonlocal dt_seq
                        dt_seq += 1
                        txt_p = _write_drawtext_file(tmp_dir, f"{dt_seq:02d}_{label}", text_val)
                        return f"textfile={_ffmpeg_filter_escape_path(txt_p)}:expansion=none"

                    if parsed_title:
                        t_main, t_sub = parsed_title
                        en = f"between(t,0,{title_dur:.3f})"
                        vf_parts.append(
                            f"drawbox=x=0:y=ih*0.34:w=iw:h=ih*0.28:color=black@0.72:t=fill:enable='{en}'"
                        )
                        vf_parts.append(
                            f"drawtext={_dt_textfile_opt('title', t_main)}:fontcolor=white:fontsize=56:"
                            f"x=(w-text_w)/2:y=h*0.42:enable='{en}'"
                        )
                        if t_sub:
                            vf_parts.append(
                                f"drawtext={_dt_textfile_opt('subtitle', t_sub)}:fontcolor=#93C5FD:fontsize=34:"
                                f"x=(w-text_w)/2:y=h*0.52:enable='{en}'"
                            )
                    for lt in parsed_lts:
                        en = f"between(t,{lt.start_s:.3f},{lt.end_s:.3f})"
                        vf_parts.append(
                            f"drawbox=x=64:y=ih-210:w=620:h=130:color=black@0.75:t=fill:enable='{en}'"
                        )
                        vf_parts.append(
                            f"drawtext={_dt_textfile_opt('lt_name', lt.name)}:fontcolor=white:fontsize=38:"
                            f"x=88:y=h-186:enable='{en}'"
                        )
                        if lt.role:
                            vf_parts.append(
                                f"drawtext={_dt_textfile_opt('lt_role', lt.role)}:fontcolor=#38BDF8:fontsize=26:"
                                f"x=88:y=h-134:enable='{en}'"
                            )
                    if parsed_end:
                        e_title, e_cta = parsed_end
                        en = f"between(t,{end_start:.3f},{video_duration_s + 1.0:.3f})"
                        vf_parts.append(
                            f"drawbox=x=0:y=ih*0.36:w=iw:h=ih*0.26:color=black@0.80:t=fill:enable='{en}'"
                        )
                        vf_parts.append(
                            f"drawtext={_dt_textfile_opt('end_title', e_title)}:fontcolor=white:fontsize=50:"
                            f"x=(w-text_w)/2:y=h*0.45:enable='{en}'"
                        )
                        if e_cta:
                            vf_parts.append(
                                f"drawtext={_dt_textfile_opt('end_cta', e_cta)}:fontcolor=#38BDF8:fontsize=32:"
                                f"x=(w-text_w)/2:y=h*0.54:enable='{en}'"
                            )
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        safe_ffmpeg_path(current),
                        "-vf",
                        ",".join(vf_parts),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "copy",
                        safe_ffmpeg_path(dst),
                    ]
                    res = runner(cmd)
                    if res.returncode != 0:
                        raise RuntimeError(
                            f"Standalone ffmpeg drawtext motion cards failed: {redact_secrets(res.stderr).strip()}"
                        )
                    current = dst
                    card_renderer = "ffmpeg:drawtext_filter"
                else:
                    # Pure-Python RGBA PNG card synthesis + universal `overlay` filtergraph!
                    overlay_inputs: list[str] = ["-i", safe_ffmpeg_path(current)]
                    filter_steps: list[str] = []
                    prev_label = "[0:v]"
                    in_idx = 1

                    card_specs: list[tuple[str, str, str, str, float, float]] = []
                    if parsed_title:
                        card_specs.append(
                            ("title", parsed_title[0], parsed_title[1], "(W-w)/2:(H-h)/2", 0.0, title_dur)
                        )
                    for lt_idx, lt in enumerate(parsed_lts, start=1):
                        card_specs.append(
                            (f"lt_{lt_idx}", lt.name, lt.role, "64:H-h-72", lt.start_s, lt.end_s)
                        )
                    if parsed_end:
                        card_specs.append(
                            ("end", parsed_end[0], parsed_end[1], "(W-w)/2:(H-h)/2", end_start, video_duration_s + 1.0)
                        )

                    for tag, p_txt, s_txt, pos_expr, st_s, en_s in card_specs:
                        png_path = render_text_card_png(
                            tmp_dir / f"card_{tag}.png",
                            primary_text=p_txt,
                            secondary_text=s_txt,
                            width=min(760, max(320, width - 96)),
                            height=160,
                        )
                        overlay_inputs.extend(["-i", safe_ffmpeg_path(png_path)])
                        out_label = "[vout]" if in_idx == len(card_specs) else f"[v{in_idx}]"
                        filter_steps.append(
                            f"{prev_label}[{in_idx}:v]overlay={pos_expr}:enable='between(t,{st_s:.3f},{en_s:.3f})'{out_label}"
                        )
                        prev_label = out_label
                        in_idx += 1

                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        *overlay_inputs,
                        "-filter_complex",
                        ";".join(filter_steps),
                        "-map",
                        "[vout]",
                        "-map",
                        "0:a?",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "copy",
                        safe_ffmpeg_path(dst),
                    ]
                    res = runner(cmd)
                    if res.returncode != 0:
                        raise RuntimeError(
                            f"Standalone ffmpeg PNG card overlay failed: {redact_secrets(res.stderr).strip()}"
                        )
                    current = dst
                    card_renderer = "ffmpeg:png_card_overlay_fallback(missing_drawtext)"

        # 2. Captions (vidkit/captions.py delegation -> libass burn -> mov_text soft-sub fallback)
        if has_captions:
            staged_srt = tmp_dir / "normalized_captions.srt"
            staged_srt.write_text(format_srt(cues), encoding="utf-8")
            dst = _next_stage()

            delegated_caps_ok = False
            if creative_stack.enabled and creative_stack.captions_script is not None:
                captions_py = str(creative_stack.captions_script)
                dst.unlink(missing_ok=True)
                cmd = [
                    sys.executable,
                    captions_py,
                    "-i",
                    safe_ffmpeg_path(current),
                    "-s",
                    safe_ffmpeg_path(staged_srt),
                    "-o",
                    safe_ffmpeg_path(dst),
                ]
                if caption_style == "soft":
                    cmd.append("--soft")
                else:
                    cmd.extend(["--style", caption_style])
                    if captions_json_path and caption_style in ("karaoke", "highlight"):
                        cmd.extend(["--words", safe_ffmpeg_path(captions_json_path)])
                res = runner(cmd)
                if res.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
                    current = dst
                    delegated_caps_ok = True
                    caption_renderer = f"creative-stack:vidkit/captions.py:{caption_style}"
                else:
                    dst.unlink(missing_ok=True)
                    print(
                        f"[video-gen] WARNING: vidkit captions.py failed ({res.stderr.strip() or 'missing output'}); "
                        "falling back to standalone ffmpeg caption renderer.",
                        file=sys.stderr,
                    )

            if not delegated_caps_ok:
                if caption_style != "soft" and (caps["ass"] or caps["subtitles"]):
                    if caps["ass"]:
                        ass_file = tmp_dir / "captions.ass"
                        ass_file.write_text(
                            build_standalone_ass(cues, style=caption_style, width=width, height=height),
                            encoding="utf-8",
                        )
                        vf_arg = f"ass={_ffmpeg_filter_escape_path(ass_file)}"
                    else:
                        vf_arg = f"subtitles={_ffmpeg_filter_escape_path(staged_srt)}"
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        safe_ffmpeg_path(current),
                        "-vf",
                        vf_arg,
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "copy",
                        safe_ffmpeg_path(dst),
                    ]
                    res = runner(cmd)
                    if res.returncode != 0:
                        raise RuntimeError(
                            f"Standalone ffmpeg subtitle burn failed: {redact_secrets(res.stderr).strip()}"
                        )
                    current = dst
                    caption_renderer = f"ffmpeg:libass:{caption_style}"
                else:
                    # Either explicit `soft` style OR `ffmpeg -filters` lacks `ass`/`subtitles` (missing libass)
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        safe_ffmpeg_path(current),
                        "-i",
                        safe_ffmpeg_path(staged_srt),
                        "-map",
                        "0",
                        "-map",
                        "1:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "copy",
                        "-c:s",
                        "mov_text",
                        "-metadata:s:s:0",
                        "language=eng",
                        "-disposition:s:0",
                        "default",
                        safe_ffmpeg_path(dst),
                    ]
                    res = runner(cmd)
                    if res.returncode != 0:
                        raise RuntimeError(
                            f"Standalone ffmpeg mov_text soft-caption mux failed: {redact_secrets(res.stderr).strip()}"
                        )
                    current = dst
                    caption_renderer = (
                        "ffmpeg:mov_text_soft_sub"
                        if caption_style == "soft"
                        else "ffmpeg:mov_text_soft_sub_fallback(missing_libass)"
                    )

        output_video.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, output_video)

    return {
        "applied": True,
        "caption_renderer": caption_renderer,
        "card_renderer": card_renderer,
        "cues_count": len(cues),
        "cards_applied": cards_count,
        "ffmpeg_capabilities": caps,
    }


# ---------------------------------------------------------------------------
# Broadcast Audio Scoring, Speech-Window Ducking & 2-Pass -14 LUFS Mastering
# ---------------------------------------------------------------------------

_LOUDNORM_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _detect_audio_channels(
    audio_path: Path,
    *,
    ffprobe_bin: str | None,
    runner: RunnerCallable = default_runner,
) -> tuple[int, float]:
    """Return `(channels, duration_s)` via `ffprobe` or RIFF WAVE `fmt ` header fallback."""
    if ffprobe_bin:
        res = runner(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                safe_ffmpeg_path(audio_path),
            ]
        )
        if res.returncode == 0:
            try:
                doc = json.loads(res.stdout)
                streams = doc.get("streams", [])
                astream = next(
                    (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
                    None,
                )
                channels = int(astream.get("channels", 1)) if isinstance(astream, dict) else 1
                dur_raw = (
                    (doc.get("format") or {}).get("duration")
                    or (astream or {}).get("duration")
                    or 0.0
                )
                dur_val = float(dur_raw)
                return max(1, channels), (max(0.0, dur_val) if math.isfinite(dur_val) else 0.0)
            except (ValueError, TypeError):
                pass

    # Pure-stdlib WAV `fmt ` fallback using seeked header reads (never loading multi-GB WAVs into RAM)
    try:
        file_size = audio_path.stat().st_size
        if file_size >= 44:
            with audio_path.open("rb") as fh:
                riff_hdr = fh.read(12)
                if len(riff_hdr) == 12 and riff_hdr[:4] == b"RIFF" and riff_hdr[8:12] == b"WAVE":
                    pos = 12
                    channels = 1
                    byte_rate = AUDIO_SAMPLE_RATE * 2
                    data_bytes = 0
                    while pos + 8 <= file_size:
                        fh.seek(pos)
                        chdr = fh.read(8)
                        if len(chdr) < 8:
                            break
                        chunk_id = chdr[:4]
                        chunk_sz = struct.unpack("<I", chdr[4:8])[0]
                        body_start = pos + 8
                        if chunk_id == b"fmt " and chunk_sz >= 16 and body_start + 16 <= file_size:
                            fmt_buf = fh.read(16)
                            if len(fmt_buf) == 16:
                                _, channels, _, byte_rate, _, _ = struct.unpack("<HHIIHH", fmt_buf)
                        elif chunk_id == b"data":
                            data_bytes = min(chunk_sz, max(0, file_size - body_start))
                            break
                        pos = body_start + chunk_sz + (chunk_sz % 2)
                    dur = (data_bytes / byte_rate) if byte_rate > 0 else 0.0
                    return max(1, int(channels)), dur
    except OSError:
        pass
    return 1, 0.0


def detect_speech_windows(
    voice_path: Path,
    *,
    fallback_duration_s: float,
    ffmpeg_bin: str,
    ffprobe_bin: str | None = None,
    noise_db: float = -38.0,
    min_silence_s: float = 0.4,
    merge_gap_s: float = 0.85,
    runner: RunnerCallable = default_runner,
) -> list[tuple[float, float]]:
    """Detect active speech intervals via `silencedetect` (never `sidechaincompress`)."""
    _, probed_dur = _detect_audio_channels(voice_path, ffprobe_bin=ffprobe_bin, runner=runner)
    duration = probed_dur if probed_dur > 0 else max(0.1, fallback_duration_s)

    res = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-i",
            safe_ffmpeg_path(voice_path),
            "-af",
            f"silencedetect=noise={noise_db:.1f}dB:d={min_silence_s:.2f}",
            "-f",
            "null",
            "-",
        ]
    )
    silences: list[tuple[float, float]] = []
    cur_start: float | None = None
    for line in (res.stderr or "").splitlines():
        if "silence_start:" in line:
            try:
                cur_start = float(line.rsplit("silence_start:", 1)[1].split()[0])
            except (ValueError, IndexError):
                cur_start = None
        elif "silence_end:" in line and cur_start is not None:
            try:
                sil_end = float(line.rsplit("silence_end:", 1)[1].split()[0])
                silences.append((cur_start, sil_end))
            except (ValueError, IndexError):
                pass
            cur_start = None
    if cur_start is not None:
        silences.append((cur_start, duration))

    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s_begin, s_end in silences:
        if s_begin > cursor:
            speech.append((cursor, s_begin))
        cursor = max(cursor, s_end)
    if cursor < duration:
        speech.append((cursor, duration))

    merged: list[tuple[float, float]] = []
    for begin, end in speech:
        if merged and (begin - merged[-1][1]) < merge_gap_s:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((begin, end))
    return merged


def build_duck_volume_expression(
    intervals: Sequence[tuple[float, float]],
    *,
    duck_db: float = DEFAULT_DUCK_DB,
    attack_s: float = 0.25,
    release_s: float = 0.60,
) -> str:
    """Build a balanced-tree `volume` envelope expression delivering exact `-duck_db` attenuation."""
    if not math.isfinite(float(duck_db)):
        raise ValueError(f"--duck-db must be a finite number (got {duck_db!r}).")
    if not intervals or duck_db <= 0:
        return "1"
    eff_attack = max(0.01, float(attack_s))
    eff_release = max(0.01, float(release_s))
    floor = 10.0 ** (-float(duck_db) / 20.0)
    terms: list[str] = []
    for begin, end in intervals:
        fade_in = max(0.0, begin - eff_attack)
        fade_out = end + eff_release
        terms.append(
            f"if(lt(t,{fade_in:.3f}),1,"
            f"if(lt(t,{begin:.3f}),1-{1.0 - floor:.5f}*(t-{fade_in:.3f})/{eff_attack:.3f},"
            f"if(lt(t,{end:.3f}),{floor:.5f},"
            f"if(lt(t,{fade_out:.3f}),{floor:.5f}+{1.0 - floor:.5f}*(t-{end:.3f})/{eff_release:.3f},"
            f"1))))"
        )
    terms.append("1")
    # Combine in a balanced binary tree so 100+ long-form speech windows stay well under
    # FFmpeg av_expr_parse's 100-frame recursion limit.
    while len(terms) > 1:
        paired: list[str] = []
        for idx in range(0, len(terms), 2):
            if idx + 1 < len(terms):
                paired.append(f"min({terms[idx]},{terms[idx + 1]})")
            else:
                paired.append(terms[idx])
        terms = paired
    return terms[0]


def parse_loudnorm_pass1_json(stderr_or_stdout: str) -> dict[str, float]:
    """Extract Pass 1 `loudnorm` JSON stats (`input_i`, `input_tp`, `input_lra`, `input_thresh`, `target_offset`)."""
    raw_match: dict[str, Any] | None = None
    for block in _LOUDNORM_JSON_RE.findall(stderr_or_stdout or ""):
        try:
            candidate = json.loads(block)
        except ValueError:
            continue
        if isinstance(candidate, dict) and "input_i" in candidate and "input_tp" in candidate:
            raw_match = candidate
    if raw_match is None:
        raise RuntimeError(
            "Pass 1 loudnorm JSON measurement missing from ffmpeg output (track may be unreadable or empty)."
        )
    stats = {
        "input_i": float(raw_match["input_i"]),
        "input_tp": float(raw_match["input_tp"]),
        "input_lra": float(raw_match.get("input_lra", 7.0)),
        "input_thresh": float(raw_match.get("input_thresh", -24.0)),
        "target_offset": float(raw_match.get("target_offset", 0.0)),
    }
    if not all(math.isfinite(v) for v in stats.values()):
        raise RuntimeError(
            "Audio stem measured at non-finite loudnorm stats (digital silence); refusing to normalise silent track."
        )
    return stats


def build_loudnorm_pass2_filter(
    stats: Mapping[str, float],
    *,
    lufs_target: float = DEFAULT_LUFS_TARGET,
    true_peak_dbtp: float = DEFAULT_TRUE_PEAK_DBTP,
    lra: float = DEFAULT_LRA,
    dual_mono: bool = False,
) -> str:
    """Build Pass 2 linear `loudnorm` filter seeded with Pass 1 measurements."""
    dm = "true" if dual_mono else "false"
    return (
        f"loudnorm=I={lufs_target:.2f}:TP={true_peak_dbtp:.2f}:LRA={lra:.2f}"
        f":measured_I={stats['input_i']:.2f}:measured_TP={stats['input_tp']:.2f}"
        f":measured_LRA={stats['input_lra']:.2f}:measured_thresh={stats['input_thresh']:.2f}"
        f":offset={stats['target_offset']:.2f}:dual_mono={dm}:linear=true:print_format=summary"
    )


def _resolve_emitted_audio_path(stdout: str, requested: Path) -> Path:
    text = (stdout or "").strip()
    if text:
        for candidate_line in (text, *reversed([ln.strip() for ln in text.splitlines() if ln.strip()])):
            try:
                obj = json.loads(candidate_line)
            except ValueError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("output"), str) and obj["output"].strip():
                p = Path(obj["output"].strip())
                resolved = (p if p.is_absolute() else (Path.cwd() / p)).resolve()
                if resolved.is_relative_to(requested.parent.resolve()) and resolved.is_file():
                    return resolved
    return requested


def synthesize_audio_via_audio_gen(
    *,
    mode: str,
    prompt_or_text: str,
    output_wav: Path,
    audio_gen_script: Path,
    duration_s: int | None = None,
    voice_name: str | None = None,
    raw_prompt: bool = False,
    no_verify: bool = False,
    runner: RunnerCallable = default_runner,
) -> Path:
    """Delegate narration (`--mode voice`) or music (`--mode bgm`) synthesis to sibling `audio_gen.py`."""
    if not audio_gen_script.is_file():
        raise FileNotFoundError(
            f"Companion skill script not found at '{contract_home(audio_gen_script)}'. "
            "Install audio-gen alongside video-gen via: "
            "npx skills add ksprashu/agent-skill-forge --skill audio-gen "
            "(or python3 scripts/sync_skills.py --skills audio-gen,video-gen)."
        )
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    prompt_args = (
        [f"--prompt={prompt_or_text}"]
        if prompt_or_text.lstrip().startswith("-")
        else ["--prompt", prompt_or_text]
    )
    cmd: list[str] = [
        sys.executable,
        str(audio_gen_script),
        "--mode",
        mode,
        *prompt_args,
        "--output",
        str(output_wav),
    ]
    if duration_s is not None and mode == "bgm":
        cmd.extend(["--duration", str(duration_s)])
    if voice_name and mode == "voice":
        cmd.extend(["--voice", voice_name])
    if raw_prompt:
        cmd.append("--raw-prompt")
    if no_verify:
        cmd.append("--no-verify")

    res = runner(cmd)
    if res.returncode != 0:
        raise RuntimeError(
            f"audio_gen.py ({mode}) failed: {redact_secrets(res.stderr or res.stdout).strip()}"
        )
    actual_path = _resolve_emitted_audio_path(res.stdout, output_wav)
    validate_audio_magic_bytes(actual_path, label=f"Synthesised {mode} track")
    return actual_path


def apply_audio_mix_and_master(
    input_video: Path,
    output_video: Path,
    *,
    audio_mode: str,
    target_duration_s: float,
    voice_track: str | None = None,
    bgm_track: str | None = None,
    sfx_cues: Sequence[str] = (),
    narration_text: str | None = None,
    voice_name: str | None = None,
    bgm_prompt: str | None = None,
    duck_db: float = DEFAULT_DUCK_DB,
    lufs_target: float = DEFAULT_LUFS_TARGET,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
    creative_stack: CreativeStackInfo,
    ffmpeg_bin: str | None,
    ffprobe_bin: str | None = None,
    raw_prompt: bool = False,
    no_verify: bool = False,
    runner: RunnerCallable = default_runner,
) -> dict[str, Any]:
    """Score, duck, 2-pass `-14 LUFS` master (`48 kHz`), and mux audio onto `output_video`."""
    has_custom_stems = bool(
        voice_track or bgm_track or sfx_cues or narration_text or bgm_prompt
    )
    if audio_mode in ("native", "auto", "required") and not has_custom_stems:
        if input_video.resolve() != output_video.resolve():
            output_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_video, output_video)
        return {"applied": False, "audio_renderer": "omni_native"}

    if audio_mode == "silent":
        if not ffmpeg_bin:
            if input_video.resolve() != output_video.resolve():
                shutil.copy2(input_video, output_video)
            return {"applied": False, "audio_renderer": "omni_silent"}
        with tempfile.TemporaryDirectory(prefix="video-gen-silent-") as tmp_s:
            stripped = Path(tmp_s) / "silent.mp4"
            res = runner(
                [ffmpeg_bin, "-y", "-i", safe_ffmpeg_path(input_video), "-c:v", "copy", "-an", safe_ffmpeg_path(stripped)]
            )
            if res.returncode != 0:
                raise RuntimeError(f"ffmpeg silent strip failed: {redact_secrets(res.stderr).strip()}")
            output_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stripped, output_video)
        return {"applied": True, "audio_renderer": "ffmpeg:strip_audio_silent"}

    if not ffmpeg_bin:
        raise RuntimeError(
            f"ffmpeg is required for --audio-mode '{audio_mode}' mixing and 2-pass loudnorm mastering."
        )

    parsed_sfx = [parse_sfx_cue_spec(raw) for raw in sfx_cues]

    with tempfile.TemporaryDirectory(prefix="video-gen-audio-") as tmp_str:
        tmp_dir = Path(tmp_str)

        resolved_voice: Path | None = None
        if voice_track:
            resolved_voice = validate_safe_local_file(voice_track, label="--voice-track")
            validate_audio_magic_bytes(resolved_voice, label="--voice-track")
        elif narration_text:
            resolved_voice = synthesize_audio_via_audio_gen(
                mode="voice",
                prompt_or_text=narration_text,
                output_wav=tmp_dir / "synthesized_voice.wav",
                audio_gen_script=audio_gen_script,
                voice_name=voice_name,
                raw_prompt=raw_prompt,
                no_verify=no_verify,
                runner=runner,
            )

        resolved_bgm: Path | None = None
        if bgm_track:
            resolved_bgm = validate_safe_local_file(bgm_track, label="--bgm-track")
            validate_audio_magic_bytes(resolved_bgm, label="--bgm-track")
        elif bgm_prompt:
            resolved_bgm = synthesize_audio_via_audio_gen(
                mode="bgm",
                prompt_or_text=bgm_prompt,
                output_wav=tmp_dir / "synthesized_bgm.wav",
                audio_gen_script=audio_gen_script,
                duration_s=max(5, int(round(target_duration_s))),
                raw_prompt=raw_prompt,
                no_verify=no_verify,
                runner=runner,
            )

        mastered_wav = tmp_dir / "mastered_48k.wav"
        audio_renderer = "ffmpeg:standalone_2pass_loudnorm"
        speech_windows: list[tuple[float, float]] = []
        pass1_stats: dict[str, float] | None = None
        dual_mono_used = False

        # Delegate to creative-stack `sound/scripts/mix.py` when present and voice track is active
        delegated_sound_ok = False
        if (
            creative_stack.enabled
            and creative_stack.mix_script is not None
            and resolved_voice is not None
            and (resolved_bgm is not None or len(parsed_sfx) > 0)
        ):
            mix_cmd: list[str] = [
                sys.executable,
                str(creative_stack.mix_script),
                "-v",
                str(resolved_voice),
                "-o",
                str(mastered_wav),
                "--duck",
                f"{duck_db:.2f}",
                "--target",
                f"{lufs_target:.2f}",
            ]
            if resolved_bgm is not None:
                mix_cmd.extend(["-m", str(resolved_bgm)])
            for cue in parsed_sfx:
                sfx_arg = (
                    f"{cue.path}@{cue.start_s:g}:{cue.gain_db:g}"
                    if cue.gain_db != 0.0
                    else f"{cue.path}@{cue.start_s:g}"
                )
                mix_cmd.extend(["-s", sfx_arg])

            mastered_wav.unlink(missing_ok=True)
            res_mix = runner(mix_cmd)
            if res_mix.returncode == 0 and mastered_wav.is_file() and mastered_wav.stat().st_size > 0:
                try:
                    validate_audio_magic_bytes(mastered_wav, label="Delegated sound/mix.py output")
                    delegated_sound_ok = True
                    audio_renderer = "creative-stack:sound/mix.py"
                except ValueError as exc:
                    mastered_wav.unlink(missing_ok=True)
                    print(
                        f"[video-gen] WARNING: creative-stack sound/mix.py emitted invalid audio ({exc}); "
                        "falling back to standalone 2-pass loudnorm DSP.",
                        file=sys.stderr,
                    )
            else:
                mastered_wav.unlink(missing_ok=True)
                print(
                    f"[video-gen] WARNING: creative-stack sound/mix.py failed ({res_mix.stderr.strip() or 'missing output'}); "
                    "falling back to standalone 2-pass loudnorm DSP.",
                    file=sys.stderr,
                )

        if not delegated_sound_ok:
            fmt = f"aformat=sample_fmts=fltp:sample_rates={AUDIO_SAMPLE_RATE}:channel_layouts=stereo"
            total_dur = max(1.0, float(target_duration_s))

            # Single-stem solo voiceover without BGM/SFX: preserve mono dual_mono=true measurement!
            if resolved_voice is not None and resolved_bgm is None and not parsed_sfx:
                v_channels, _ = _detect_audio_channels(
                    resolved_voice, ffprobe_bin=ffprobe_bin, runner=runner
                )
                dual_mono_used = v_channels == 1
                summed_source = resolved_voice
            else:
                # Multi-stem or BGM/SFX mix -> intermediate 24-bit 48kHz WAV (`pcm_s24le`)
                inputs: list[str] = []
                chains: list[str] = []
                mix_labels: list[str] = []
                stream_idx = 0

                if resolved_voice is not None:
                    v_channels, _ = _detect_audio_channels(
                        resolved_voice, ffprobe_bin=ffprobe_bin, runner=runner
                    )
                    dual_mono_used = v_channels == 1 and resolved_bgm is None and not parsed_sfx
                    inputs.extend(["-i", safe_ffmpeg_path(resolved_voice)])
                    chains.append(f"[{stream_idx}:a]{fmt}[voice]")
                    mix_labels.append("[voice]")
                    stream_idx += 1

                if resolved_bgm is not None:
                    inputs.extend(["-stream_loop", "-1", "-i", safe_ffmpeg_path(resolved_bgm)])
                    fade_dur = min(1.5, max(0.25, total_dur * 0.1))
                    fade_out_st = max(0.0, total_dur - fade_dur)
                    base_gain_db = -16.0 if resolved_voice is not None else 0.0
                    chains.append(
                        f"[{stream_idx}:a]{fmt},atrim=0:{total_dur:.3f},asetpts=N/SR/TB,"
                        f"volume={base_gain_db:.1f}dB,"
                        f"afade=t=in:st=0:d={fade_dur:.2f},"
                        f"afade=t=out:st={fade_out_st:.3f}:d={fade_dur:.2f}[bed]"
                    )
                    if resolved_voice is not None and duck_db > 0:
                        speech_windows = detect_speech_windows(
                            resolved_voice,
                            fallback_duration_s=total_dur,
                            ffmpeg_bin=ffmpeg_bin,
                            ffprobe_bin=ffprobe_bin,
                            runner=runner,
                        )
                        if speech_windows:
                            vol_expr = build_duck_volume_expression(speech_windows, duck_db=duck_db)
                            chains.append(f"[bed]volume=volume='{vol_expr}':eval=frame[bgm]")
                        else:
                            chains.append("[bed]anull[bgm]")
                    else:
                        chains.append("[bed]anull[bgm]")
                    mix_labels.append("[bgm]")
                    stream_idx += 1

                for sfx_i, cue in enumerate(parsed_sfx):
                    inputs.extend(["-i", safe_ffmpeg_path(cue.path)])
                    delay_ms = max(0, int(round(cue.start_s * 1000.0)))
                    chains.append(
                        f"[{stream_idx}:a]{fmt},volume={cue.gain_db:.1f}dB,"
                        f"adelay={delay_ms}|{delay_ms}[sfx{sfx_i}]"
                    )
                    mix_labels.append(f"[sfx{sfx_i}]")
                    stream_idx += 1

                if not mix_labels:
                    raise ValueError(f"No audio inputs supplied for --audio-mode '{audio_mode}'.")

                if len(mix_labels) == 1:
                    chains.append(f"{mix_labels[0]}atrim=0:{total_dur:.3f},asetpts=N/SR/TB[out]")
                else:
                    # Hard DSP Law (c): ALWAYS pass normalize=0 to amix!
                    chains.append(
                        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:"
                        f"duration=longest:normalize=0,"
                        f"atrim=0:{total_dur:.3f},asetpts=N/SR/TB[out]"
                    )

                summed_wav = tmp_dir / "summed_24bit.wav"
                res_sum = runner(
                    [
                        ffmpeg_bin,
                        "-y",
                        *inputs,
                        "-filter_complex",
                        ";".join(chains),
                        "-map",
                        "[out]",
                        "-ar",
                        str(AUDIO_SAMPLE_RATE),
                        "-c:a",
                        "pcm_s24le",
                        safe_ffmpeg_path(summed_wav),
                    ]
                )
                if res_sum.returncode != 0:
                    raise RuntimeError(
                        f"ffmpeg stem mixing failed: {redact_secrets(res_sum.stderr).strip()}"
                    )
                summed_source = summed_wav

            # Hard DSP Law (a): Pass 1 JSON loudness measurement -> Pass 2 linear loudnorm at 48000 Hz!
            dm_str = "true" if dual_mono_used else "false"
            res_p1 = runner(
                [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-nostdin",
                    "-i",
                    safe_ffmpeg_path(summed_source),
                    "-map",
                    "a:0",
                    "-af",
                    f"loudnorm=I={lufs_target:.2f}:TP={DEFAULT_TRUE_PEAK_DBTP:.2f}:LRA={DEFAULT_LRA:.2f}:dual_mono={dm_str}:print_format=json",
                    "-f",
                    "null",
                    "-",
                ]
            )
            if res_p1.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg loudnorm Pass 1 measurement failed: {redact_secrets(res_p1.stderr).strip()}"
                )
            pass1_stats = parse_loudnorm_pass1_json(f"{res_p1.stderr}\n{res_p1.stdout}")
            pass2_af = build_loudnorm_pass2_filter(
                pass1_stats,
                lufs_target=lufs_target,
                dual_mono=dual_mono_used,
            )

            res_p2 = runner(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    safe_ffmpeg_path(summed_source),
                    "-af",
                    pass2_af,
                    "-ar",
                    str(AUDIO_SAMPLE_RATE),
                    "-c:a",
                    "pcm_s24le",
                    safe_ffmpeg_path(mastered_wav),
                ]
            )
            if res_p2.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg loudnorm Pass 2 linear normalise failed: {redact_secrets(res_p2.stderr).strip()}"
                )

        # Mux mastered 48kHz WAV onto video container without re-encoding video
        muxed_mp4 = tmp_dir / "muxed_master.mp4"
        res_mux = runner(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                safe_ffmpeg_path(input_video),
                "-i",
                safe_ffmpeg_path(mastered_wav),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-map",
                "0:s?",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                str(AUDIO_SAMPLE_RATE),
                "-af",
                "apad",
                "-c:s",
                "copy",
                "-shortest",
                safe_ffmpeg_path(muxed_mp4),
            ]
        )
        if res_mux.returncode != 0:
            raise RuntimeError(
                f"ffmpeg final A/V mux failed: {redact_secrets(res_mux.stderr).strip()}"
            )

        output_video.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(muxed_mp4, output_video)

    return {
        "applied": True,
        "audio_renderer": audio_renderer,
        "lufs_target": lufs_target,
        "duck_db": duck_db,
        "sample_rate_hz": AUDIO_SAMPLE_RATE,
        "dual_mono": dual_mono_used,
        "speech_windows": [[round(a, 3), round(b, 3)] for a, b in speech_windows],
        "pass1_loudnorm": pass1_stats,
    }
