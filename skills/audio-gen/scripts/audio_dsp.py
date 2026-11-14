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

"""Pure-stdlib binary audio inspector, EBU R128 mastering, crossfading & /sound bridge.

Implements the deterministic mechanical audio inspection and DSP pipeline for
``skills/audio-gen`` using 100% Python 3.12 standard library modules:

1. Pure-stdlib binary container and PCM inspector (``inspect_audio_file``):
   validates magic headers and parses WAV (``RIFF....WAVE``, ``fmt ``, ``data``,
   duration, plus PCM8/PCM16/PCM24/PCM32/Float32 sample amplitude scanning for
   digital silence and clipping without external binaries), MP3 (``ID3`` skip +
   ``0xFFE0`` MPEG frame sync + bitrate/sample-rate header + non-zero payload),
   FLAC (``fLaC`` + ``STREAMINFO``), OGG (``OggS`` + Vorbis/Opus), and M4A
   (``ftyp`` + ``mdat``). Rejects arbitrary non-audio files before upload or DSP.
2. Keg-only ``ffmpeg-full`` / ``ffprobe`` resolver checking
   ``$CREATIVE_STACK_FFMPEG`` -> ``/opt/homebrew/opt/ffmpeg-full/bin`` ->
   ``/usr/local/opt/ffmpeg-full/bin`` -> ``shutil.which``.
3. Broadcast mastering & stem mixing laws:
   - Two-pass linear ``loudnorm`` (Pass 1 JSON measurement -> Pass 2 linear gain)
     pinned to ``-ar 48000`` with ``dual_mono=true`` on mono voiceovers.
   - Explicit ``silencedetect`` speech-window ``volume`` ramp ducking (zero
     ``sidechaincompress``).
   - ``amix=inputs=N:normalize=0`` and 24-bit WAV (``pcm_s24le``) intermediates
     for ``acrossfade=d=2:c1=tri:c2=tri`` stitching and bass-preserving
     (``>130 Hz``) stereo center-cut vocal stripping.
   - Optional ``creative-stack`` (``/sound``) delegation for ``clean.py``,
     ``mix.py``, ``bed.py``, ``karaoke.py``, and ``session.py``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

BROADCAST_SAMPLE_RATE = 48000

_KEG_FFMPEG_BIN_DIRS: tuple[Path, ...] = (
    Path("/opt/homebrew/opt/ffmpeg-full/bin"),
    Path("/usr/local/opt/ffmpeg-full/bin"),
)

_OUTPUT_CODEC_FLAGS: dict[str, tuple[str, ...]] = {
    ".wav": ("-c:a", "pcm_s24le"),
    ".flac": ("-c:a", "flac", "-compression_level", "8"),
    ".mp3": ("-c:a", "libmp3lame", "-b:a", "192k"),
    ".m4a": ("-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"),
    ".aac": ("-c:a", "aac", "-b:a", "192k"),
    ".ogg": ("-c:a", "libvorbis", "-q:a", "6"),
    ".opus": ("-c:a", "libopus", "-b:a", "128k"),
}

_MPEG_BITRATES_V1_L3 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0)
_MPEG_BITRATES_V2_L3 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0)
_MPEG_BITRATES_V1_L2 = (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0)
_MPEG_BITRATES_V1_L1 = (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0)
_MPEG_BITRATES_V2_L1 = (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0)

_ADTS_SAMPLE_RATES = (
    96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350
)

_EXTENSIBLE_GUID_TAIL = b"\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"

_MPEG_SAMPLE_RATES: dict[int, tuple[int, int, int]] = {
    3: (44100, 48000, 32000),  # MPEG Version 1
    2: (22050, 24000, 16000),  # MPEG Version 2
    0: (11025, 12000, 8000),   # MPEG Version 2.5
}

_VALID_M4A_BRANDS = frozenset(
    {b"M4A ", b"M4B ", b"mp42", b"isom", b"iso2", b"mp41", b"dash", b"f4a "}
)

_JSON_BRACE_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.S)
_EBUR128_I_RE = re.compile(r"\bI:\s*(-?\d+(?:\.\d+)?|-inf)\s*LUFS")
_EBUR128_LRA_RE = re.compile(r"\bLRA:\s*(-?\d+(?:\.\d+)?)\s*LU")
_EBUR128_PEAK_RE = re.compile(r"\bPeak:\s*(-?\d+(?:\.\d+)?|-inf)\s*dBFS")


class AudioFormatError(ValueError):
    """Raised when an audio or media input fails binary validation or DSP rules."""


@dataclass(frozen=True)
class AudioInspection:
    """Result of pure-stdlib binary container and PCM amplitude inspection."""

    valid: bool
    format: str
    sample_rate: int
    channels: int
    bits_per_sample: int
    audio_format_code: int
    duration_s: float
    data_bytes: int
    peak_norm: float | None = None
    rms_dbfs: float | None = None
    clip_ratio: float | None = None
    is_silent: bool = False
    is_clipped: bool = False
    pcm_sha256: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "format": self.format,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bits_per_sample": self.bits_per_sample,
            "audio_format_code": self.audio_format_code,
            "duration_s": round(self.duration_s, 4),
            "data_bytes": self.data_bytes,
            "peak_norm": round(self.peak_norm, 6) if self.peak_norm is not None else None,
            "rms_dbfs": round(self.rms_dbfs, 2) if (self.rms_dbfs is not None and math.isfinite(self.rms_dbfs)) else None,
            "clip_ratio": round(self.clip_ratio, 6) if self.clip_ratio is not None else None,
            "is_silent": self.is_silent,
            "is_clipped": self.is_clipped,
            "pcm_sha256": self.pcm_sha256,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Pure-Stdlib Binary Audio & Image Magic Inspectors
# ---------------------------------------------------------------------------


def _scan_wav_pcm_samples(
    pcm_bytes: bytes,
    *,
    audio_format: int,
    bits_per_sample: int,
    channels: int = 1,
) -> tuple[float, float, float]:
    """Return ``(peak_norm, rms_dbfs, clip_ratio)`` scanning ALL channels per sampled frame."""
    bytes_per_sample = bits_per_sample // 8
    ch_count = max(1, int(channels))
    bytes_per_frame = bytes_per_sample * ch_count
    if bytes_per_sample <= 0 or len(pcm_bytes) < bytes_per_frame:
        return 0.0, float("-inf"), 0.0

    total_frames = len(pcm_bytes) // bytes_per_frame
    frame_step = max(1, total_frames // 100_000)
    peak = 0.0
    sum_sq = 0.0
    clipped = 0
    counted = 0

    if audio_format == 1 and bits_per_sample == 16:
        for frame_idx in range(0, total_frames, frame_step):
            base_off = frame_idx * bytes_per_frame
            for ch in range(ch_count):
                (raw_val,) = struct.unpack_from("<h", pcm_bytes, base_off + ch * 2)
                norm = abs(raw_val) / 32768.0
                if norm > peak:
                    peak = norm
                sum_sq += norm * norm
                if abs(raw_val) >= 32767:
                    clipped += 1
                counted += 1
    elif audio_format == 1 and bits_per_sample == 24:
        for frame_idx in range(0, total_frames, frame_step):
            base_off = frame_idx * bytes_per_frame
            for ch in range(ch_count):
                offset = base_off + ch * 3
                b0 = pcm_bytes[offset]
                b1 = pcm_bytes[offset + 1]
                b2 = pcm_bytes[offset + 2]
                unsigned = b0 | (b1 << 8) | (b2 << 16)
                signed = unsigned - 0x1000000 if (b2 & 0x80) else unsigned
                norm = abs(signed) / 8388608.0
                if norm > peak:
                    peak = norm
                sum_sq += norm * norm
                if abs(signed) >= 8388607:
                    clipped += 1
                counted += 1
    elif audio_format == 1 and bits_per_sample == 32:
        for frame_idx in range(0, total_frames, frame_step):
            base_off = frame_idx * bytes_per_frame
            for ch in range(ch_count):
                (raw_val,) = struct.unpack_from("<i", pcm_bytes, base_off + ch * 4)
                norm = abs(raw_val) / 2147483648.0
                if norm > peak:
                    peak = norm
                sum_sq += norm * norm
                if abs(raw_val) >= 2147483647:
                    clipped += 1
                counted += 1
    elif audio_format == 3 and bits_per_sample == 32:
        for frame_idx in range(0, total_frames, frame_step):
            base_off = frame_idx * bytes_per_frame
            for ch in range(ch_count):
                (flt_val,) = struct.unpack_from("<f", pcm_bytes, base_off + ch * 4)
                if not math.isfinite(flt_val):
                    clipped += 1
                    counted += 1
                    continue
                norm = abs(flt_val)
                if norm > peak:
                    peak = norm
                sum_sq += min(norm, 2.0) ** 2
                if norm >= 0.9999:
                    clipped += 1
                counted += 1
    elif audio_format == 1 and bits_per_sample == 8:
        for frame_idx in range(0, total_frames, frame_step):
            base_off = frame_idx * bytes_per_frame
            for ch in range(ch_count):
                centered = pcm_bytes[base_off + ch] - 128
                norm = abs(centered) / 128.0
                if norm > peak:
                    peak = norm
                sum_sq += norm * norm
                if abs(centered) >= 127:
                    clipped += 1
                counted += 1
    else:
        return 0.0, float("-inf"), 0.0

    if counted == 0:
        return 0.0, float("-inf"), 0.0
    rms = math.sqrt(sum_sq / counted)
    rms_dbfs = 20.0 * math.log10(rms) if rms > 1e-12 else float("-inf")
    return peak, rms_dbfs, clipped / counted


def _inspect_wav_bytes(
    buf: bytes,
    *,
    min_peak_norm: float,
    max_clip_ratio: float,
) -> AudioInspection:
    errors: list[str] = []
    warnings: list[str] = []
    if len(buf) < 44 or buf[:4] != b"RIFF" or buf[8:12] != b"WAVE":
        return AudioInspection(
            valid=False,
            format="wav",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("Invalid RIFF/WAVE magic header.",),
        )

    (riff_chunk_size,) = struct.unpack_from("<I", buf, 4)
    if riff_chunk_size not in (0, 0xFFFFFFFF) and riff_chunk_size + 8 > len(buf) + 4:
        warnings.append(
            f"RIFF container size mismatch: header declares {riff_chunk_size + 8} bytes, file has {len(buf)}."
        )

    offset = 12
    fmt_info: tuple[int, int, int, int] | None = None
    pcm_slice: bytes | None = None

    while offset + 8 <= len(buf):
        chunk_id = buf[offset : offset + 4]
        (chunk_size,) = struct.unpack_from("<I", buf, offset + 4)
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(buf):
            if chunk_id == b"data":
                # Streaming WAVs from pipes emit 0xFFFFFFFF or 0; clamp trailing data chunk to EOF.
                pcm_slice = buf[payload_start:]
                if chunk_size not in (0, 0xFFFFFFFF):
                    warnings.append(
                        f"Trailing WAV 'data' chunk truncated ({len(pcm_slice)} < {chunk_size} declared bytes)."
                    )
                break
            errors.append(
                f"WAV chunk {chunk_id.decode('latin1', 'replace')!r} declares {chunk_size} bytes beyond EOF."
            )
            break

        if chunk_id == b"fmt ":
            if chunk_size < 16:
                errors.append(f"WAV 'fmt ' chunk too short ({chunk_size} bytes < 16).")
            else:
                audio_fmt, channels, sample_rate, _byte_rate, _align, bits_per_sample = (
                    struct.unpack_from("<HHIIHH", buf, payload_start)
                )
                if audio_fmt == 0xFFFE:
                    if chunk_size < 40:
                        errors.append("WAVE_FORMAT_EXTENSIBLE 'fmt ' chunk shorter than 40 bytes.")
                    else:
                        subfmt_guid = buf[payload_start + 24 : payload_start + 40]
                        if subfmt_guid[4:] != _EXTENSIBLE_GUID_TAIL:
                            errors.append("Invalid WAVE_FORMAT_EXTENSIBLE SubFormat GUID.")
                        else:
                            (audio_fmt,) = struct.unpack_from("<H", subfmt_guid, 0)
                fmt_info = (audio_fmt, channels, sample_rate, bits_per_sample)
        elif chunk_id == b"data":
            pcm_slice = buf[payload_start:payload_end]

        offset = payload_end + (chunk_size & 1)

    if fmt_info is None:
        errors.append("Missing WAV 'fmt ' chunk.")
        return AudioInspection(
            valid=False,
            format="wav",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    audio_fmt, channels, sample_rate, bits_per_sample = fmt_info
    supported_pcm = (audio_fmt == 1 and bits_per_sample in (8, 16, 24, 32)) or (
        audio_fmt == 3 and bits_per_sample == 32
    )
    if audio_fmt not in (1, 3):
        errors.append(f"Unsupported WAV audio format code {audio_fmt} (expected 1=PCM or 3=IEEE float).")
    if channels < 1 or channels > 16:
        errors.append(f"Invalid WAV channel count: {channels}.")
    if sample_rate < 8000 or sample_rate > 384000:
        errors.append(f"Invalid WAV sample rate: {sample_rate} Hz.")
    if not supported_pcm:
        errors.append(
            f"Unsupported WAV format/bit-depth combination: format={audio_fmt}, bits_per_sample={bits_per_sample}."
        )

    if pcm_slice is None or len(pcm_slice) == 0:
        errors.append("Missing or empty WAV 'data' chunk.")
        return AudioInspection(
            valid=False,
            format="wav",
            sample_rate=sample_rate,
            channels=channels,
            bits_per_sample=bits_per_sample,
            audio_format_code=audio_fmt,
            duration_s=0.0,
            data_bytes=0,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    bytes_per_frame = max(1, channels * max(1, bits_per_sample // 8))
    aligned_len = (len(pcm_slice) // bytes_per_frame) * bytes_per_frame
    pcm_aligned = pcm_slice[:aligned_len]
    duration_s = aligned_len / float(max(1, sample_rate) * bytes_per_frame)
    pcm_sha256 = hashlib.sha256(pcm_aligned).hexdigest()

    is_silent = False
    is_clipped = False
    peak_norm: float | None = None
    rms_dbfs: float | None = None
    clip_ratio: float | None = None

    if supported_pcm and 1 <= channels <= 16:
        peak_norm, rms_dbfs, clip_ratio = _scan_wav_pcm_samples(
            pcm_aligned,
            audio_format=audio_fmt,
            bits_per_sample=bits_per_sample,
            channels=channels,
        )
        is_silent = peak_norm < min_peak_norm
        is_clipped = clip_ratio > max_clip_ratio
        if is_silent:
            errors.append(
                f"WAV PCM payload is digitally silent (peak amplitude {peak_norm:.6f} < {min_peak_norm})."
            )
        if is_clipped:
            errors.append(
                f"WAV PCM payload is severely clipped ({clip_ratio * 100.0:.2f}% full-scale samples > "
                f"{max_clip_ratio * 100.0:.2f}%)."
            )

    return AudioInspection(
        valid=len(errors) == 0,
        format="wav",
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        audio_format_code=audio_fmt,
        duration_s=duration_s,
        data_bytes=len(pcm_aligned),
        peak_norm=peak_norm,
        rms_dbfs=rms_dbfs,
        clip_ratio=clip_ratio,
        is_silent=is_silent,
        is_clipped=is_clipped,
        pcm_sha256=pcm_sha256,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _mpeg_bitrate_kbps(version_id: int, layer_id: int, bitrate_idx: int) -> int:
    if bitrate_idx in (0, 15):
        return 0
    if version_id == 3:  # MPEG 1
        if layer_id == 3:
            return _MPEG_BITRATES_V1_L1[bitrate_idx]
        if layer_id == 2:
            return _MPEG_BITRATES_V1_L2[bitrate_idx]
        if layer_id == 1:
            return _MPEG_BITRATES_V1_L3[bitrate_idx]
    else:  # MPEG 2 / 2.5
        if layer_id == 3:
            return _MPEG_BITRATES_V2_L1[bitrate_idx]
        return _MPEG_BITRATES_V2_L3[bitrate_idx]
    return 0


def _parse_mpeg_frame_header(buf: bytes, pos: int) -> tuple[int, int, int, int, int] | None:
    """Return ``(version_id, layer_id, sr, channels, frame_len)`` or None if invalid."""
    if pos + 4 > len(buf):
        return None
    b0, b1, b2, b3 = buf[pos], buf[pos + 1], buf[pos + 2], buf[pos + 3]
    if not (b0 == 0xFF and (b1 & 0xE0) == 0xE0):
        return None
    version_id = (b1 >> 3) & 0x03
    layer_id = (b1 >> 1) & 0x03
    bitrate_idx = (b2 >> 4) & 0x0F
    sr_idx = (b2 >> 2) & 0x03
    padding = (b2 >> 1) & 0x01
    chan_mode = (b3 >> 6) & 0x03
    if version_id == 1 or layer_id == 0 or sr_idx == 3:
        return None
    kbps = _mpeg_bitrate_kbps(version_id, layer_id, bitrate_idx)
    sr = _MPEG_SAMPLE_RATES[version_id][sr_idx]
    if kbps <= 0 or sr <= 0:
        return None
    if layer_id == 3:
        frame_len = ((12 * kbps * 1000 // sr) + padding) * 4
    else:
        coef = 144 if (version_id == 3 or layer_id == 2) else 72
        frame_len = (coef * kbps * 1000 // sr) + padding
    if frame_len < 24 or pos + frame_len > len(buf):
        return None
    channels = 1 if chan_mode == 3 else 2
    return version_id, layer_id, sr, channels, frame_len


def _inspect_adts_aac_bytes(buf: bytes, start_pos: int) -> AudioInspection | None:
    """Detect valid chained ADTS AAC frames starting at ``start_pos``."""
    cursor = start_pos
    frames = 0
    first_sr = 0
    first_ch = 0
    while cursor + 7 <= len(buf):
        b0, b1, b2, b3, b4, b5 = (
            buf[cursor],
            buf[cursor + 1],
            buf[cursor + 2],
            buf[cursor + 3],
            buf[cursor + 4],
            buf[cursor + 5],
        )
        if b0 != 0xFF or (b1 & 0xF6) != 0xF0:
            break
        sr_idx = (b2 >> 2) & 0x0F
        if sr_idx >= len(_ADTS_SAMPLE_RATES):
            break
        ch = ((b2 & 0x01) << 2) | ((b3 >> 6) & 0x03)
        frame_len = ((b3 & 0x03) << 11) | (b4 << 3) | ((b5 >> 5) & 0x07)
        if frame_len < 7 or cursor + frame_len > len(buf):
            break
        if frames == 0:
            first_sr = _ADTS_SAMPLE_RATES[sr_idx]
            first_ch = ch if ch > 0 else 2
        frames += 1
        cursor += frame_len
    if frames < 2:
        return None
    duration_s = (frames * 1024) / float(first_sr) if first_sr > 0 else 0.0
    return AudioInspection(
        valid=True,
        format="aac",
        sample_rate=first_sr,
        channels=first_ch,
        bits_per_sample=16,
        audio_format_code=0x00FF,
        duration_s=duration_s,
        data_bytes=cursor - start_pos,
        errors=(),
    )


def _inspect_mp3_bytes(buf: bytes) -> AudioInspection:
    offset = 0
    if len(buf) >= 10 and buf[:3] == b"ID3":
        flags = buf[5]
        size_bytes = buf[6:10]
        if any(b & 0x80 for b in size_bytes):
            return AudioInspection(
                valid=False,
                format="mp3",
                sample_rate=0,
                channels=0,
                bits_per_sample=0,
                audio_format_code=0,
                duration_s=0.0,
                data_bytes=0,
                errors=("Corrupt ID3v2 synchsafe header size.",),
            )
        tag_size = (
            ((size_bytes[0] & 0x7F) << 21)
            | ((size_bytes[1] & 0x7F) << 14)
            | ((size_bytes[2] & 0x7F) << 7)
            | (size_bytes[3] & 0x7F)
        )
        offset = 10 + tag_size + (10 if (flags & 0x10) else 0)

    # Check ADTS AAC first when frame header carries layer == 0 (0xFFF0/0xFFF1)
    if offset + 7 <= len(buf) and buf[offset] == 0xFF and (buf[offset + 1] & 0xF6) == 0xF0:
        adts_info = _inspect_adts_aac_bytes(buf, offset)
        if adts_info is not None:
            return adts_info

    # Locate chained MPEG audio sync (require >= 2 consecutive frames unless 1 frame reaches EOF)
    scan_limit = min(len(buf) - 4, offset + 8192)
    first_sync = -1
    first_sr = 0
    first_channels = 0
    first_frame_len = 0

    pos = offset
    while pos <= scan_limit:
        parsed = _parse_mpeg_frame_header(buf, pos)
        if parsed is not None:
            v1, l1, sr1, ch1, flen1 = parsed
            if pos + flen1 == len(buf):
                # Single complete frame spanning exact remainder of stream
                first_sync, first_sr, first_channels, first_frame_len = pos, sr1, ch1, flen1
                break
            parsed_next = _parse_mpeg_frame_header(buf, pos + flen1)
            if parsed_next is not None and parsed_next[0] == v1 and parsed_next[1] == l1:
                first_sync, first_sr, first_channels, first_frame_len = pos, sr1, ch1, flen1
                break
        pos += 1

    if first_sync < 0:
        return AudioInspection(
            valid=False,
            format="mp3",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("No valid chained MPEG audio frame sync (0xFFE0) found.",),
        )

    payload = buf[first_sync:]
    frame_body = payload[4:first_frame_len]
    non_trivial = any(b not in (0x00, 0xFF) for b in frame_body)
    errors: list[str] = []
    if not non_trivial:
        errors.append("MP3 frame payload contains only zero/padding bytes.")

    # Walk frames to compute duration accurately
    cursor = first_sync
    total_samples = 0
    frames_parsed = 0
    while cursor + 4 <= len(buf):
        parsed = _parse_mpeg_frame_header(buf, cursor)
        if parsed is None:
            break
        version_id, layer_id, _sr, _ch, flen = parsed
        spf = 384 if layer_id == 3 else (1152 if (layer_id == 2 or version_id == 3) else 576)
        total_samples += spf
        frames_parsed += 1
        cursor += flen

    if frames_parsed == 0:
        errors.append("Zero complete MPEG frames in MP3 stream.")

    duration_s = total_samples / float(first_sr) if first_sr > 0 else 0.0
    return AudioInspection(
        valid=len(errors) == 0,
        format="mp3",
        sample_rate=first_sr,
        channels=first_channels,
        bits_per_sample=16,
        audio_format_code=0x0055,
        duration_s=duration_s,
        data_bytes=len(payload),
        is_silent=not non_trivial,
        errors=tuple(errors),
    )


def _inspect_flac_bytes(buf: bytes) -> AudioInspection:
    if len(buf) < 42 or buf[:4] != b"fLaC":
        return AudioInspection(
            valid=False,
            format="flac",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("Invalid FLAC magic header or truncated STREAMINFO.",),
        )
    block_header = buf[4]
    block_type = block_header & 0x7F
    block_len = (buf[5] << 16) | (buf[6] << 8) | buf[7]
    if block_type != 0 or block_len != 34:
        return AudioInspection(
            valid=False,
            format="flac",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("FLAC missing mandatory 34-byte STREAMINFO block at offset 4.",),
        )
    # STREAMINFO bytes 10..17 (absolute 18..25): 20b sample_rate, 3b channels-1, 5b bps-1, 36b total_samples
    packed = struct.unpack_from(">Q", buf, 18)[0]
    sample_rate = (packed >> 44) & 0xFFFFF
    channels = ((packed >> 41) & 0x07) + 1
    bits_per_sample = ((packed >> 36) & 0x1F) + 1
    total_samples = packed & 0xFFFFFFFFF

    # Advance past metadata blocks to find frame bytes
    cursor = 4
    while cursor + 4 <= len(buf):
        hdr = buf[cursor]
        is_last = bool(hdr & 0x80)
        blen = (buf[cursor + 1] << 16) | (buf[cursor + 2] << 8) | buf[cursor + 3]
        cursor += 4 + blen
        if is_last:
            break

    frame_bytes = max(0, len(buf) - cursor)
    errors: list[str] = []
    if sample_rate <= 0:
        errors.append("FLAC STREAMINFO has zero sample_rate.")
    if frame_bytes < 4:
        errors.append("FLAC container contains no compressed audio frame payload.")

    duration_s = (total_samples / float(sample_rate)) if sample_rate > 0 else 0.0
    return AudioInspection(
        valid=len(errors) == 0,
        format="flac",
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        audio_format_code=0xF1AC,
        duration_s=duration_s,
        data_bytes=frame_bytes,
        errors=tuple(errors),
    )


def _inspect_ogg_bytes(buf: bytes) -> AudioInspection:
    if len(buf) < 36 or buf[:4] != b"OggS" or buf[4] != 0:
        return AudioInspection(
            valid=False,
            format="ogg",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("Invalid OggS page magic or unsupported Ogg version.",),
        )
    page_segments = buf[26]
    header_end = 27 + page_segments
    if header_end > len(buf):
        return AudioInspection(
            valid=False,
            format="ogg",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("Truncated Ogg page segment table.",),
        )
    seg_total = sum(buf[27:header_end])
    pkt = buf[header_end : header_end + seg_total]
    sample_rate = 48000
    channels = 2
    errors: list[str] = []
    if pkt.startswith(b"\x01vorbis") and len(pkt) >= 16:
        channels = pkt[11]
        (sample_rate,) = struct.unpack_from("<I", pkt, 12)
    elif pkt.startswith(b"OpusHead") and len(pkt) >= 16:
        channels = pkt[9]
        (orig_sr,) = struct.unpack_from("<I", pkt, 12)
        sample_rate = orig_sr if orig_sr > 0 else 48000
    else:
        errors.append("Ogg first packet is neither Vorbis nor Opus identification header.")

    if channels < 1 or sample_rate < 8000:
        errors.append(f"Invalid Ogg stream header (channels={channels}, sample_rate={sample_rate}).")
    if len(buf) <= header_end + seg_total:
        errors.append("Ogg container has identification header only and zero audio packets.")

    return AudioInspection(
        valid=len(errors) == 0,
        format="ogg",
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=16,
        audio_format_code=0x674F,
        duration_s=0.0,
        data_bytes=max(0, len(buf) - header_end - seg_total),
        errors=tuple(errors),
    )


def _inspect_m4a_bytes(buf: bytes) -> AudioInspection:
    if len(buf) < 24 or buf[4:8] != b"ftyp":
        return AudioInspection(
            valid=False,
            format="m4a",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=("Missing ISO BMFF 'ftyp' box header.",),
        )
    (ftyp_size,) = struct.unpack_from(">I", buf, 0)
    major_brand = buf[8:12]
    errors: list[str] = []
    if ftyp_size < 16 or ftyp_size > len(buf):
        errors.append("Corrupt ISO BMFF 'ftyp' box size.")
    if major_brand not in _VALID_M4A_BRANDS:
        errors.append(f"Unsupported ISO BMFF major brand {major_brand!r} for M4A audio.")

    # Walk top-level atoms to verify non-empty mdat payload
    cursor = 0
    mdat_bytes = 0
    while cursor + 8 <= len(buf):
        (atom_size,) = struct.unpack_from(">I", buf, cursor)
        atom_type = buf[cursor + 4 : cursor + 8]
        header_len = 8
        if atom_size == 1:
            if cursor + 16 > len(buf):
                break
            (atom_size,) = struct.unpack_from(">Q", buf, cursor + 8)
            header_len = 16
        elif atom_size == 0:
            atom_size = len(buf) - cursor
        if atom_size < header_len or cursor + atom_size > len(buf):
            break
        if atom_type == b"mdat":
            mdat_bytes += atom_size - header_len
        cursor += atom_size

    if mdat_bytes <= 0:
        errors.append("M4A container has no non-empty 'mdat' audio payload box.")

    return AudioInspection(
        valid=len(errors) == 0,
        format="m4a",
        sample_rate=48000,
        channels=2,
        bits_per_sample=16,
        audio_format_code=0x4D34,
        duration_s=0.0,
        data_bytes=mdat_bytes,
        errors=tuple(errors),
    )


def inspect_audio_file(
    target: Path | str | bytes,
    *,
    min_peak_norm: float = 1e-4,
    max_clip_ratio: float = 0.05,
) -> AudioInspection:
    """Inspect binary audio magic headers, framing, and WAV PCM amplitude in stdlib."""
    if isinstance(target, (bytes, bytearray)):
        buf = bytes(target)
    else:
        path = Path(target)
        if not path.is_file():
            return AudioInspection(
                valid=False,
                format="missing",
                sample_rate=0,
                channels=0,
                bits_per_sample=0,
                audio_format_code=0,
                duration_s=0.0,
                data_bytes=0,
                errors=(f"Audio file does not exist: {path.name}",),
            )
        try:
            buf = path.read_bytes()
        except OSError as exc:
            return AudioInspection(
                valid=False,
                format="unreadable",
                sample_rate=0,
                channels=0,
                bits_per_sample=0,
                audio_format_code=0,
                duration_s=0.0,
                data_bytes=0,
                errors=(f"Unable to read audio file: {exc}",),
            )

    if len(buf) < 12:
        return AudioInspection(
            valid=False,
            format="unknown",
            sample_rate=0,
            channels=0,
            bits_per_sample=0,
            audio_format_code=0,
            duration_s=0.0,
            data_bytes=0,
            errors=(f"File is too small ({len(buf)} bytes) to be a valid audio container.",),
        )

    if buf[:4] == b"RIFF" and buf[8:12] == b"WAVE":
        return _inspect_wav_bytes(buf, min_peak_norm=min_peak_norm, max_clip_ratio=max_clip_ratio)
    if buf[:4] == b"fLaC":
        return _inspect_flac_bytes(buf)
    if buf[:4] == b"OggS":
        return _inspect_ogg_bytes(buf)
    if len(buf) >= 12 and buf[4:8] == b"ftyp":
        return _inspect_m4a_bytes(buf)
    if buf[:3] == b"ID3" or (buf[0] == 0xFF and (buf[1] & 0xE0) == 0xE0):
        return _inspect_mp3_bytes(buf)

    return AudioInspection(
        valid=False,
        format="unknown",
        sample_rate=0,
        channels=0,
        bits_per_sample=0,
        audio_format_code=0,
        duration_s=0.0,
        data_bytes=0,
        errors=(
            "Unrecognised non-audio binary header (expected WAV RIFF/WAVE, MP3 ID3/0xFFE0, "
            "FLAC fLaC, OGG OggS, or M4A ftyp).",
        ),
    )


def require_valid_audio(
    target: Path | str | bytes,
    *,
    label: str = "audio file",
    require_wav: bool = False,
    allow_silence: bool = False,
    allow_clipping: bool = False,
) -> AudioInspection:
    """Validate an audio input or raise ``AudioFormatError`` before any upload/DSP."""
    min_peak = 0.0 if allow_silence else 1e-4
    max_clip = 1.0 if allow_clipping else 0.05
    info = inspect_audio_file(target, min_peak_norm=min_peak, max_clip_ratio=max_clip)
    if not info.valid:
        detail = "; ".join(info.errors) or "invalid audio container"
        raise AudioFormatError(f"Invalid {label}: {detail}")
    if require_wav and info.format != "wav":
        raise AudioFormatError(f"{label} must be an uncompressed WAV file (got '{info.format}').")
    return info


def inspect_image_magic(
    target: Path | str | bytes,
    *,
    label: str = "image reference",
) -> str:
    """Validate PNG, JPEG, or WebP magic bytes for Lyria ``-i`` visual references."""
    if isinstance(target, (bytes, bytearray)):
        header = bytes(target[:16])
    else:
        path = Path(target)
        if not path.is_file():
            raise AudioFormatError(f"{label} does not exist: {path.name}")
        with path.open("rb") as fh:
            header = fh.read(16)

    if len(header) >= 8 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(header) >= 3 and header[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    raise AudioFormatError(
        f"{label} is not a valid PNG, JPEG, or WebP image (rejected non-image bytes)."
    )


# ---------------------------------------------------------------------------
# Keg-Only ffmpeg-full / ffprobe Resolver & Stream / Loudness Probing
# ---------------------------------------------------------------------------


def resolve_media_binary(
    tool: str,
    *,
    env: Mapping[str, str] | None = None,
    which_fn: Callable[[str], str | None] = shutil.which,
    keg_dirs: Sequence[Path] = _KEG_FFMPEG_BIN_DIRS,
) -> str | None:
    """Resolve ``ffmpeg`` or ``ffprobe`` honoring keg-only ``ffmpeg-full`` precedence."""
    if tool not in ("ffmpeg", "ffprobe"):
        return which_fn(tool)
    active_env = env if env is not None else os.environ

    if tool == "ffmpeg":
        explicit = active_env.get("CREATIVE_STACK_FFMPEG", "").strip()
        if explicit:
            candidate = Path(explicit).expanduser()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    else:
        explicit_probe = active_env.get("CREATIVE_STACK_FFPROBE", "").strip()
        if explicit_probe:
            candidate = Path(explicit_probe).expanduser()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        explicit_ffmpeg = active_env.get("CREATIVE_STACK_FFMPEG", "").strip()
        if explicit_ffmpeg:
            sibling = Path(explicit_ffmpeg).expanduser().with_name("ffprobe")
            if sibling.is_file() and os.access(sibling, os.X_OK):
                return str(sibling)

    for directory in keg_dirs:
        keg_bin = directory / tool
        if keg_bin.is_file() and os.access(keg_bin, os.X_OK):
            return str(keg_bin)

    return which_fn(tool)


def parse_ffprobe_audio_json(stdout_text: str) -> dict[str, Any]:
    """Parse ``ffprobe -print_format json -show_format -show_streams`` output."""
    try:
        doc = json.loads(stdout_text)
    except ValueError as exc:
        raise AudioFormatError(f"Malformed JSON from ffprobe: {exc}") from exc
    if not isinstance(doc, dict):
        raise AudioFormatError("ffprobe output must be a JSON object.")

    streams = doc.get("streams")
    if not isinstance(streams, list):
        raise AudioFormatError("ffprobe JSON missing 'streams' list.")
    audio_stream = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise AudioFormatError("ffprobe found zero audio streams in container.")

    fmt_obj = doc.get("format") if isinstance(doc.get("format"), dict) else {}
    raw_dur = fmt_obj.get("duration") or audio_stream.get("duration") or 0.0
    try:
        duration_s = float(raw_dur)
        sample_rate = int(audio_stream.get("sample_rate") or 0)
        channels = int(audio_stream.get("channels") or 0)
        raw_br = fmt_obj.get("bit_rate") or audio_stream.get("bit_rate") or 0
        bit_rate = int(raw_br) if str(raw_br).isdigit() else 0
    except (TypeError, ValueError) as exc:
        raise AudioFormatError(f"Non-numeric stream metadata in ffprobe output: {exc}") from exc
    if not math.isfinite(duration_s) or sample_rate <= 0 or channels <= 0 or duration_s <= 0.0:
        raise AudioFormatError(
            f"ffprobe reported degenerate audio stream (sr={sample_rate}, ch={channels}, dur={duration_s})."
        )
    return {
        "codec_name": str(audio_stream.get("codec_name") or "unknown"),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_s": duration_s,
        "bit_rate": bit_rate,
    }


def probe_audio_ffprobe(
    path: Path,
    *,
    runner: Callable[[Sequence[str]], Any],
    ffprobe_bin: str,
) -> dict[str, Any]:
    """Run ``ffprobe`` on ``path`` and return validated audio stream metadata."""
    proc = runner(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            _ffmpeg_input_path(path),
        ]
    )
    if proc.returncode != 0:
        raise AudioFormatError(f"ffprobe failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return parse_ffprobe_audio_json(proc.stdout)


def parse_ebur128_and_loudnorm(stderr_text: str) -> dict[str, Any]:
    """Extract loudness metrics from ``loudnorm`` JSON and/or ``ebur128`` summary stderr."""
    loudnorm_raw: dict[str, Any] | None = None
    for block in _JSON_BRACE_BLOCK_RE.findall(stderr_text or ""):
        try:
            candidate = json.loads(block)
        except ValueError:
            continue
        if isinstance(candidate, dict) and "input_i" in candidate:
            loudnorm_raw = candidate

    if loudnorm_raw is not None:
        input_i = float(loudnorm_raw["input_i"])
        input_tp = float(loudnorm_raw["input_tp"])
        input_lra = float(loudnorm_raw.get("input_lra", 0.0))
        input_thresh = float(loudnorm_raw.get("input_thresh", -70.0))
        target_offset = float(loudnorm_raw.get("target_offset", 0.0))
        if not math.isfinite(input_i) or not math.isfinite(input_tp):
            raise AudioFormatError(
                "Audio measured as -inf LUFS / dBTP (digitally silent); refusing to normalise silence."
            )
        return {
            "i": input_i,
            "tp": input_tp,
            "lra": input_lra,
            "thresh": input_thresh,
            "offset": target_offset,
            "source": "loudnorm_json",
        }

    m_i = _EBUR128_I_RE.search(stderr_text or "")
    if m_i:
        val_i = float(m_i.group(1))
        m_lra = _EBUR128_LRA_RE.search(stderr_text or "")
        m_pk = _EBUR128_PEAK_RE.search(stderr_text or "")
        val_tp = float(m_pk.group(1)) if m_pk else 0.0
        if not math.isfinite(val_i) or not math.isfinite(val_tp):
            raise AudioFormatError("ebur128 measured -inf LUFS (digitally silent).")
        return {
            "i": val_i,
            "tp": val_tp,
            "lra": float(m_lra.group(1)) if m_lra else 0.0,
            "thresh": val_i - 10.0,
            "offset": 0.0,
            "source": "ebur128_summary",
        }

    raise AudioFormatError("Could not parse loudness statistics from ffmpeg stderr.")


# ---------------------------------------------------------------------------
# Broadcast Two-Pass Loudnorm, Crossfading, Envelope Ducking & Mixing
# ---------------------------------------------------------------------------


def measure_loudnorm_pass1(
    path: Path,
    *,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
    dual_mono: bool = False,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str,
) -> dict[str, Any]:
    """Execute Pass 1 EBU R128 loudness measurement via ``loudnorm=print_format=json``."""
    dm = "true" if dual_mono else "false"
    af = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":dual_mono={dm}:print_format=json"
    )
    proc = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "a:0",
            "-af",
            af,
            "-f",
            "null",
            "-",
        ]
    )
    if proc.returncode != 0:
        raise AudioFormatError(
            f"Pass 1 loudness measurement failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    stats = parse_ebur128_and_loudnorm(f"{proc.stderr}\n{proc.stdout}")
    stats["dual_mono"] = bool(dual_mono)
    return stats


def build_loudnorm_pass2_filter(
    stats: Mapping[str, Any],
    *,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
) -> str:
    """Build Pass 2 linear ``loudnorm`` filter string from Pass 1 measurements."""
    dm = "true" if stats.get("dual_mono") else "false"
    return (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={stats['i']}:measured_TP={stats['tp']}"
        f":measured_LRA={stats['lra']}:measured_thresh={stats['thresh']}"
        f":offset={stats['offset']}:dual_mono={dm}:linear=true:print_format=summary"
    )


def encode_args_for_output(
    output_path: Path,
    *,
    sample_rate: int = BROADCAST_SAMPLE_RATE,
    channels: int | None = None,
) -> list[str]:
    """Return deterministic encoder flags pinned to ``-ar 48000``."""
    suffix = output_path.suffix.lower() or ".wav"
    if suffix not in _OUTPUT_CODEC_FLAGS:
        supported = ", ".join(sorted(_OUTPUT_CODEC_FLAGS))
        raise AudioFormatError(f"Unsupported output extension '{suffix}'. Supported: {supported}")
    args = ["-ar", str(sample_rate), *_OUTPUT_CODEC_FLAGS[suffix]]
    if channels is not None:
        args.extend(["-ac", str(channels)])
    return args


_NORM_TYPE_RE = re.compile(r"Normalization Type:\s*(Linear|Dynamic)", re.IGNORECASE)


def _ffmpeg_input_path(path: Path) -> str:
    """Resolve and guard local path before passing to ffmpeg (prevents protocol/option confusion)."""
    resolved = path.resolve()
    return f"file:{resolved}"


def _ffmpeg_script_flag(ffmpeg_bin: str, runner: Callable[[Sequence[str]], Any]) -> str | None:
    """Detect whether this ffmpeg build expects ``-/filter_complex`` or ``-filter_complex_script``."""
    proc = runner([ffmpeg_bin, "-hide_banner", "-h", "long"])
    help_text = f"{proc.stdout}\n{proc.stderr}"
    if "-/filter_complex" in help_text:
        return "-/filter_complex"
    if "-filter_complex_script" in help_text:
        return "-filter_complex_script"
    return None


def _parse_pass2_normalization_type(stderr_text: str) -> str:
    m = _NORM_TYPE_RE.search(stderr_text or "")
    if m:
        return m.group(1).lower()
    for block in _JSON_BRACE_BLOCK_RE.findall(stderr_text or ""):
        try:
            doc = json.loads(block)
        except ValueError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("normalization_type"), str):
            return doc["normalization_type"].strip().lower()
    return "linear"


def normalize_audio_two_pass(
    src_path: Path,
    dst_path: Path,
    *,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
    channels_hint: int | None = None,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str,
) -> dict[str, Any]:
    """Master ``src_path`` to ``dst_path`` via 2-pass linear ``loudnorm`` at 48 kHz."""
    src_info = inspect_audio_file(src_path)
    inferred_channels = channels_hint if channels_hint is not None else (src_info.channels or 2)
    dual_mono = inferred_channels == 1

    pass1 = measure_loudnorm_pass1(
        src_path,
        target_i=target_i,
        target_tp=target_tp,
        target_lra=target_lra,
        dual_mono=dual_mono,
        runner=runner,
        ffmpeg_bin=ffmpeg_bin,
    )
    pass2_af = build_loudnorm_pass2_filter(
        pass1,
        target_i=target_i,
        target_tp=target_tp,
        target_lra=target_lra,
    )
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    enc_flags = encode_args_for_output(dst_path, sample_rate=BROADCAST_SAMPLE_RATE)
    proc = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            _ffmpeg_input_path(src_path),
            "-map",
            "a:0",
            "-af",
            pass2_af,
            *enc_flags,
            str(dst_path.resolve()),
        ]
    )
    if proc.returncode != 0:
        raise AudioFormatError(f"Pass 2 loudnorm failed (exit {proc.returncode}): {proc.stderr.strip()}")

    norm_type = _parse_pass2_normalization_type(f"{proc.stderr}\n{proc.stdout}")
    post = measure_loudnorm_pass1(
        dst_path,
        target_i=target_i,
        target_tp=target_tp,
        target_lra=target_lra,
        dual_mono=dual_mono,
        runner=runner,
        ffmpeg_bin=ffmpeg_bin,
    )
    # If loudnorm fell back to dynamic mode and missed loudness/true-peak targets, brickwall-limit peaks and re-run 2-pass linear!
    if norm_type == "dynamic" and (
        abs(post["i"] - target_i) > 0.8 or post["tp"] > target_tp + 0.1
    ):
        with tempfile.TemporaryDirectory(prefix="forge-prelimit-") as tmp:
            limited_wav = Path(tmp) / "prelimited.wav"
            peak_ceiling_lin = min(0.95, max(0.2, 10.0 ** (float(target_tp) / 20.0)))
            lim_proc = runner(
                [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-nostdin",
                    "-y",
                    "-i",
                    _ffmpeg_input_path(src_path),
                    "-map",
                    "a:0",
                    "-af",
                    f"dynaudnorm=f=150:g=15:p={peak_ceiling_lin:.3f},alimiter=limit={peak_ceiling_lin:.3f}:attack=5:release=50",
                    "-ar",
                    str(BROADCAST_SAMPLE_RATE),
                    "-c:a",
                    "pcm_s24le",
                    str(limited_wav),
                ]
            )
            if lim_proc.returncode == 0 and limited_wav.is_file():
                pass1_lim = measure_loudnorm_pass1(
                    limited_wav,
                    target_i=target_i,
                    target_tp=target_tp,
                    target_lra=target_lra,
                    dual_mono=dual_mono,
                    runner=runner,
                    ffmpeg_bin=ffmpeg_bin,
                )
                pass2_lim = build_loudnorm_pass2_filter(
                    pass1_lim, target_i=target_i, target_tp=target_tp, target_lra=target_lra
                )
                p2_lim = runner(
                    [
                        ffmpeg_bin,
                        "-hide_banner",
                        "-nostdin",
                        "-y",
                        "-i",
                        _ffmpeg_input_path(limited_wav),
                        "-map",
                        "a:0",
                        "-af",
                        pass2_lim,
                        *enc_flags,
                        str(dst_path.resolve()),
                    ]
                )
                if p2_lim.returncode == 0:
                    norm_type = _parse_pass2_normalization_type(f"{p2_lim.stderr}\n{p2_lim.stdout}")
                    pass2_af = pass2_lim
                    post = measure_loudnorm_pass1(
                        dst_path,
                        target_i=target_i,
                        target_tp=target_tp,
                        target_lra=target_lra,
                        dual_mono=dual_mono,
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                    )

    if abs(post["i"] - target_i) > 1.0 or post["tp"] > target_tp + 0.3:
        raise AudioFormatError(
            f"Two-pass loudnorm ({norm_type}) missed target ({post['i']:.2f} LUFS / {post['tp']:.2f} dBTP "
            f"vs target {target_i:.2f} LUFS / {target_tp:.2f} dBTP)."
        )

    return {
        "input_lufs": pass1["i"],
        "input_tp_dbtp": pass1["tp"],
        "output_lufs": post["i"],
        "output_tp_dbtp": post["tp"],
        "output_lra": post["lra"],
        "dual_mono": dual_mono,
        "normalization_type": norm_type,
        "dynamic_fallback": norm_type == "dynamic",
        "sample_rate": BROADCAST_SAMPLE_RATE,
        "filter_pass2": pass2_af,
    }


def _probe_or_inspect_duration(
    item_path: Path,
    *,
    runner: Callable[[Sequence[str]], Any],
    ffprobe_bin: str | None = None,
) -> float:
    info = inspect_audio_file(item_path)
    if info.duration_s > 0.0:
        return info.duration_s
    if ffprobe_bin:
        return probe_audio_ffprobe(item_path, runner=runner, ffprobe_bin=ffprobe_bin)["duration_s"]
    raise AudioFormatError(
        f"Cannot determine duration of '{item_path.name}' without ffprobe (container={info.format})."
    )


def stitch_audio_segments(
    segments: Sequence[Path],
    output_wav: Path,
    *,
    crossfade_s: float = 2.0,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str,
    ffprobe_bin: str | None = None,
) -> Path:
    """Stitch multi-clip segments via ``acrossfade=d=2:c1=tri:c2=tri`` into 24-bit WAV."""
    if not segments:
        raise AudioFormatError("Cannot stitch an empty segment list.")
    if not math.isfinite(crossfade_s) or crossfade_s < 0.0:
        raise AudioFormatError(f"--crossfade must be finite and >= 0 (got {crossfade_s}).")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    if len(segments) == 1:
        proc_single = runner(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                _ffmpeg_input_path(segments[0]),
                "-ar",
                str(BROADCAST_SAMPLE_RATE),
                "-c:a",
                "pcm_s24le",
                str(output_wav.resolve()),
            ]
        )
        if proc_single.returncode != 0:
            raise AudioFormatError(f"WAV intermediate transcode failed: {proc_single.stderr.strip()}")
        return output_wav

    if crossfade_s <= 0.0:
        raise AudioFormatError("Multi-segment acrossfade requires crossfade_s > 0.0.")

    probe_bin = ffprobe_bin or resolve_media_binary("ffprobe")
    durs = [
        _probe_or_inspect_duration(seg, runner=runner, ffprobe_bin=probe_bin)
        for seg in segments
    ]
    for idx, dur in enumerate(durs):
        min_needed = crossfade_s if idx in (0, len(durs) - 1) else (2.0 * crossfade_s)
        if dur <= min_needed:
            raise AudioFormatError(
                f"Segment {idx + 1} duration {dur:.2f}s is too short for {crossfade_s:.2f}s acrossfade "
                f"(needs > {min_needed:.2f}s so adjacent fades do not swallow it)."
            )

    inputs: list[str] = []
    filter_parts: list[str] = []
    fmt = f"aformat=sample_fmts=fltp:sample_rates={BROADCAST_SAMPLE_RATE}:channel_layouts=stereo"
    for idx, seg in enumerate(segments):
        inputs.extend(["-i", _ffmpeg_input_path(seg)])
        filter_parts.append(f"[{idx}:a]{fmt}[s{idx}]")

    prev_label = "s0"
    for idx in range(1, len(segments)):
        next_label = f"xf{idx}" if idx < len(segments) - 1 else "outa"
        filter_parts.append(
            f"[{prev_label}][s{idx}]acrossfade=d={crossfade_s:.3f}:c1=tri:c2=tri[{next_label}]"
        )
        prev_label = next_label

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        f"[{prev_label}]",
        "-ar",
        str(BROADCAST_SAMPLE_RATE),
        "-c:a",
        "pcm_s24le",
        str(output_wav.resolve()),
    ]
    proc = runner(cmd)
    if proc.returncode != 0:
        raise AudioFormatError(f"Multi-segment acrossfade stitch failed: {proc.stderr.strip()}")
    return output_wav


def detect_speech_intervals(
    voice_path: Path,
    *,
    duration_s: float,
    noise_db: float = -38.0,
    min_silence_s: float = 0.35,
    merge_gap_s: float = 0.4,
    offset_s: float = 0.0,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str,
) -> list[tuple[float, float]]:
    """Detect active speech intervals ``[(start_s, end_s)]`` via ``silencedetect``."""
    proc = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-i",
            _ffmpeg_input_path(voice_path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
            "-f",
            "null",
            "-",
        ]
    )
    if proc.returncode != 0:
        raise AudioFormatError(f"silencedetect failed: {proc.stderr.strip()}")

    silences: list[tuple[float, float]] = []
    cur_start: float | None = None
    for line in (proc.stderr or "").splitlines():
        if "silence_start:" in line:
            token = line.rsplit("silence_start:", 1)[1].split()[0]
            cur_start = float(token)
        elif "silence_end:" in line and cur_start is not None:
            token = line.rsplit("silence_end:", 1)[1].split()[0]
            silences.append((cur_start, float(token)))
            cur_start = None
    if cur_start is not None:
        silences.append((cur_start, duration_s))

    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s_begin, s_end in silences:
        if s_begin > cursor:
            speech.append((cursor, s_begin))
        cursor = max(cursor, s_end)
    if cursor < duration_s:
        speech.append((cursor, duration_s))

    merged: list[tuple[float, float]] = []
    for begin, end in speech:
        if merged and (begin - merged[-1][1]) < merge_gap_s:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((begin, end))
    return [(round(a + offset_s, 4), round(b + offset_s, 4)) for a, b in merged]


def build_duck_volume_expr(
    intervals: Sequence[tuple[float, float]],
    *,
    duck_db: float = 14.0,
    attack_s: float = 0.25,
    release_s: float = 0.6,
) -> str:
    """Build balanced-tree ``volume`` ramp expression (O(log N) AST depth, never ``sidechaincompress``)."""
    if not (math.isfinite(duck_db) and math.isfinite(attack_s) and math.isfinite(release_s)):
        raise AudioFormatError("Ducking parameters (duck_db, attack_s, release_s) must be finite.")
    if duck_db <= 0.0 or not intervals:
        return "1"
    for begin, end in intervals:
        if not (math.isfinite(begin) and math.isfinite(end)):
            raise AudioFormatError(f"Non-finite speech interval {(begin, end)!r}.")
    floor = 10.0 ** (-float(duck_db) / 20.0)
    att = max(0.01, float(attack_s))
    rel = max(0.01, float(release_s))
    segments: list[str] = []
    for begin, end in intervals:
        fade_in = max(0.0, begin - att)
        fade_out = end + rel
        ramp_in = max(0.001, begin - fade_in)
        segments.append(
            f"if(lt(t,{fade_in:.3f}),1,"
            f"if(lt(t,{begin:.3f}),1-{1.0 - floor:.5f}*(t-{fade_in:.3f})/{ramp_in:.3f},"
            f"if(lt(t,{end:.3f}),{floor:.5f},"
            f"if(lt(t,{fade_out:.3f}),{floor:.5f}+{1.0 - floor:.5f}*(t-{end:.3f})/{rel:.3f},"
            f"1))))"
        )
    # Pairwise balanced min() tree keeps AST nesting depth O(log2(N)) (depth <= 10 for 1,000+ windows)
    nodes = segments
    while len(nodes) > 1:
        nxt: list[str] = []
        for idx in range(0, len(nodes), 2):
            if idx + 1 < len(nodes):
                nxt.append(f"min({nodes[idx]},{nodes[idx + 1]})")
            else:
                nxt.append(nodes[idx])
        nodes = nxt
    return nodes[0]


def parse_sfx_cue(
    spec: str,
    *,
    allowed_root: Path | None = None,
) -> tuple[Path, float, float]:
    """Parse ``FILE@SECONDS[:GAIN_DB]`` and binary-verify the effect file."""
    raw = spec.strip()
    path_part, sep, rest = raw.rpartition("@")
    if not sep or not path_part.strip() or not rest.strip():
        raise AudioFormatError(f"Invalid --sfx-cue '{spec}'; expected FILE@SECONDS[:GAIN_DB].")
    when_str, _, gain_str = rest.partition(":")
    try:
        when_s = float(when_str)
        gain_db = float(gain_str) if gain_str else 0.0
    except ValueError as exc:
        raise AudioFormatError(
            f"Invalid timestamp/gain in --sfx-cue '{spec}'; expected numeric SECONDS[:GAIN_DB]."
        ) from exc
    if not math.isfinite(when_s) or when_s < 0.0:
        raise AudioFormatError(f"--sfx-cue timestamp must be finite and >= 0s (got {when_s}).")
    if not math.isfinite(gain_db):
        raise AudioFormatError(f"--sfx-cue gain_db must be finite (got {gain_db}).")

    resolved = Path(path_part.strip()).expanduser().resolve()
    if allowed_root is not None and not resolved.is_relative_to(allowed_root.resolve()):
        raise AudioFormatError(f"--sfx-cue path '{path_part}' escapes allowed directory.")
    require_valid_audio(resolved, label=f"SFX cue '{resolved.name}'")
    return resolved, when_s, gain_db


# ---------------------------------------------------------------------------
# creative-stack (/sound) Discovery & Delegation with Standalone Fallbacks
# ---------------------------------------------------------------------------


def discover_creative_stack_sound(
    mode_or_path: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
    home_dir: Path | None = None,
) -> Path | None:
    """Discover ``creative-stack`` ``skills/sound`` directory or return ``None``."""
    cleaned = (mode_or_path or "auto").strip()
    if cleaned.lower() == "off":
        return None

    active_env = env if env is not None else os.environ
    active_home = (home_dir if home_dir is not None else Path.home()).resolve()

    if cleaned.lower() != "auto":
        explicit = Path(cleaned).expanduser().resolve()
        for candidate in (explicit, explicit / "skills" / "sound", explicit / "sound"):
            if (candidate / "scripts" / "mix.py").is_file():
                return candidate
        raise AudioFormatError(
            f"--creative-stack path '{cleaned}' does not contain sound/scripts/mix.py."
        )

    candidates: list[Path] = []
    cs_root = active_env.get("CREATIVE_STACK_ROOT", "").strip()
    if cs_root:
        root_p = Path(cs_root).expanduser().resolve()
        candidates.extend((root_p / "skills" / "sound", root_p))

    candidates.extend(
        (
            active_home / ".agents" / "skills" / "sound",
            active_home / ".gemini" / "skills" / "sound",
            active_home / ".claude" / "skills" / "sound",
            active_home / ".gemini" / "config" / "skills" / "sound",
        )
    )
    for candidate in candidates:
        if (candidate / "scripts" / "mix.py").is_file():
            return candidate.resolve()
    return None


def strip_vocals_to_backing(
    src_song: Path,
    dst_wav: Path,
    *,
    creative_sound_dir: Path | None,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str | None,
) -> dict[str, Any]:
    """Strip lead vocals via ``creative-stack`` ``karaoke.py`` or >130Hz stereo center-cut."""
    require_valid_audio(src_song, label="source song for vocal stripping")
    dst_wav.parent.mkdir(parents=True, exist_ok=True)

    if creative_sound_dir is not None:
        karaoke_py = creative_sound_dir / "scripts" / "karaoke.py"
        if karaoke_py.is_file():
            print("INFO: Delegating vocal strip to creative-stack sound/scripts/karaoke.py", file=sys.stderr)
            with tempfile.TemporaryDirectory(prefix="forge-karaoke-") as tmp:
                tmp_out = Path(tmp) / "backing_work.wav"
                proc = runner([sys.executable, str(karaoke_py), "-i", str(src_song), "-o", str(tmp_out)])
                inst_candidate = Path(tmp) / "backing_work.instrumental.wav"
                chosen = inst_candidate if inst_candidate.is_file() else tmp_out
                if proc.returncode == 0 and chosen.is_file():
                    require_valid_audio(chosen, label="karaoke.py instrumental output")
                    shutil.copyfile(chosen, dst_wav)
                    return {
                        "backend": "creative-stack:karaoke.py",
                        "delegate_script": "sound/scripts/karaoke.py",
                        "path": str(dst_wav),
                    }
                print(
                    f"WARNING: creative-stack karaoke.py exited {proc.returncode}; falling back to ffmpeg: "
                    f"{(proc.stderr or '').strip()[:240]}",
                    file=sys.stderr,
                )

    if not ffmpeg_bin:
        raise AudioFormatError(
            "Vocal stripping requires ffmpeg (or creative-stack /sound karaoke.py)."
        )

    # Bass-preserving (>130 Hz) stereo phase cancellation per /sound engineering law:
    # kick & bass stay intact below 130 Hz while center-panned vocals above 130 Hz cancel.
    fmt = f"aformat=sample_fmts=fltp:sample_rates={BROADCAST_SAMPLE_RATE}:channel_layouts=stereo"
    filter_graph = (
        f"[0:a]{fmt},asplit=2[low_in][high_in];"
        "[low_in]lowpass=f=130[bass];"
        "[high_in]highpass=f=130,"
        "pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0[side];"
        "[bass][side]amix=inputs=2:normalize=0[outa]"
    )
    proc = runner(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            _ffmpeg_input_path(src_song),
            "-filter_complex",
            filter_graph,
            "-map",
            "[outa]",
            "-ar",
            str(BROADCAST_SAMPLE_RATE),
            "-c:a",
            "pcm_s24le",
            str(dst_wav.resolve()),
        ]
    )
    if proc.returncode != 0:
        raise AudioFormatError(f"Bass-preserving vocal strip failed: {proc.stderr.strip()}")
    return {"backend": "ffmpeg:bass_preserving_center_cut_130hz", "path": str(dst_wav)}


def clean_voice_track(
    src_voice: Path,
    dst_wav: Path,
    *,
    creative_sound_dir: Path | None,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str | None,
) -> dict[str, Any]:
    """Repair a voice stem via ``creative-stack`` ``clean.py`` or standalone FFmpeg chain."""
    require_valid_audio(src_voice, label="voice stem")
    dst_wav.parent.mkdir(parents=True, exist_ok=True)

    if creative_sound_dir is not None:
        clean_py = creative_sound_dir / "scripts" / "clean.py"
        if clean_py.is_file():
            print("INFO: Delegating voice repair to creative-stack sound/scripts/clean.py", file=sys.stderr)
            with tempfile.TemporaryDirectory(prefix="forge-cs-clean-") as tmp_cs:
                cs_out = Path(tmp_cs) / dst_wav.name
                proc = runner(
                    [sys.executable, str(clean_py), "-i", str(src_voice), "-o", str(cs_out), "--mono"]
                )
                if proc.returncode == 0 and cs_out.is_file():
                    require_valid_audio(cs_out, label="clean.py output")
                    shutil.copyfile(cs_out, dst_wav)
                    return {
                        "backend": "creative-stack:clean.py",
                        "delegate_script": "sound/scripts/clean.py",
                        "path": str(dst_wav),
                    }
                print(
                    f"WARNING: creative-stack clean.py exited {proc.returncode}; falling back to ffmpeg: "
                    f"{(proc.stderr or '').strip()[:240]}",
                    file=sys.stderr,
                )

    if not ffmpeg_bin:
        raise AudioFormatError("Voice cleanup requires ffmpeg (or creative-stack /sound clean.py).")

    with tempfile.TemporaryDirectory(prefix="forge-clean-") as tmp:
        pre_norm = Path(tmp) / "pre_norm.wav"
        chain = (
            "highpass=f=80,"
            "afftdn=nf=-25:nr=12:tn=1,"
            "agate=threshold=0.015:ratio=2:attack=10:release=250,"
            "acompressor=threshold=-18dB:ratio=3:attack=15:release=180:makeup=2,"
            "pan=mono|c0=0.5*c0+0.5*c1"
        )
        proc = runner(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                _ffmpeg_input_path(src_voice),
                "-af",
                chain,
                "-ar",
                str(BROADCAST_SAMPLE_RATE),
                "-ac",
                "1",
                "-c:a",
                "pcm_s24le",
                str(pre_norm),
            ]
        )
        if proc.returncode != 0:
            raise AudioFormatError(f"Standalone voice cleanup failed: {proc.stderr.strip()}")
        loudness = normalize_audio_two_pass(
            pre_norm,
            dst_wav,
            target_i=-16.0,
            target_tp=-1.0,
            channels_hint=1,
            runner=runner,
            ffmpeg_bin=ffmpeg_bin,
        )
    return {"backend": "ffmpeg:clean_chain_2pass_dual_mono", "path": str(dst_wav), "loudness": loudness}


def mix_broadcast_stems(
    *,
    voice_path: Path | None,
    bgm_path: Path | None,
    sfx_cues: Sequence[tuple[Path, float, float]],
    dst_path: Path,
    lead_s: float = 0.0,
    tail_s: float = 0.0,
    bgm_gain_db: float = -16.0,
    duck_db: float = 14.0,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    creative_sound_dir: Path | None = None,
    runner: Callable[[Sequence[str]], Any],
    ffmpeg_bin: str | None,
    ffprobe_bin: str | None = None,
) -> dict[str, Any]:
    """Mix voice, ducked music bed, and timestamped SFX cues, then 2-pass master."""
    if voice_path is None and bgm_path is None and not sfx_cues:
        raise AudioFormatError("Mix requires at least one of --voice-track, --bgm-track, or --sfx-cue.")
    if voice_path is not None:
        require_valid_audio(voice_path, label="voice track")
    if bgm_path is not None:
        require_valid_audio(bgm_path, label="BGM track")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Delegate to creative-stack /sound mix.py when installed and voice_path is supplied
    if creative_sound_dir is not None and voice_path is not None:
        mix_py = creative_sound_dir / "scripts" / "mix.py"
        if mix_py.is_file():
            print("INFO: Delegating stem mix to creative-stack sound/scripts/mix.py", file=sys.stderr)
            with tempfile.TemporaryDirectory(prefix="forge-cs-mix-") as tmp_cs:
                cs_out = Path(tmp_cs) / dst_path.name
                cmd = [
                    sys.executable,
                    str(mix_py),
                    "-v",
                    str(voice_path),
                    "-o",
                    str(cs_out),
                    "--lead",
                    str(lead_s),
                    "--tail",
                    str(tail_s),
                    "--music-gain",
                    str(bgm_gain_db),
                    "--duck",
                    str(duck_db),
                    "--target",
                    str(target_i),
                    "--true-peak",
                    str(target_tp),
                ]
                if bgm_path is not None:
                    cmd.extend(["-m", str(bgm_path)])
                for cue_path, when_s, gain_db in sfx_cues:
                    spec_tok = f"{cue_path}@{when_s}:{gain_db}" if gain_db != 0.0 else f"{cue_path}@{when_s}"
                    cmd.extend(["-s", spec_tok])
                proc = runner(cmd)
                if proc.returncode == 0 and cs_out.is_file():
                    require_valid_audio(cs_out, label="creative-stack mix.py output")
                    shutil.copyfile(cs_out, dst_path)
                    loudness_res: dict[str, Any] | None = None
                    if ffmpeg_bin:
                        post = measure_loudnorm_pass1(
                            dst_path,
                            target_i=target_i,
                            target_tp=target_tp,
                            dual_mono=False,
                            runner=runner,
                            ffmpeg_bin=ffmpeg_bin,
                        )
                        loudness_res = {
                            "output_lufs": post["i"],
                            "output_tp_dbtp": post["tp"],
                            "output_lra": post["lra"],
                            "sample_rate": BROADCAST_SAMPLE_RATE,
                        }
                    return {
                        "backend": "creative-stack:mix.py",
                        "delegate_script": "sound/scripts/mix.py",
                        "duck_db": duck_db,
                        "target_i": target_i,
                        "target_tp": target_tp,
                        "loudness": loudness_res,
                    }
                print(
                    f"WARNING: creative-stack mix.py exited {proc.returncode}; falling back to ffmpeg: "
                    f"{(proc.stderr or '').strip()[:240]}",
                    file=sys.stderr,
                )

    if not ffmpeg_bin:
        raise AudioFormatError("Broadcast stem mixing requires ffmpeg.")

    probe_bin = ffprobe_bin or resolve_media_binary("ffprobe")
    voice_dur = (
        _probe_or_inspect_duration(voice_path, runner=runner, ffprobe_bin=probe_bin)
        if voice_path is not None
        else 0.0
    )
    bgm_dur = (
        _probe_or_inspect_duration(bgm_path, runner=runner, ffprobe_bin=probe_bin)
        if bgm_path is not None
        else 0.0
    )
    max_sfx_end = max(
        (
            when_s + _probe_or_inspect_duration(cue_p, runner=runner, ffprobe_bin=probe_bin)
            for cue_p, when_s, _ in sfx_cues
        ),
        default=0.0,
    )
    total_dur = max(lead_s + voice_dur + tail_s, max_sfx_end, bgm_dur if voice_path is None else 0.0, 1.0)

    intervals: list[tuple[float, float]] = []
    if voice_path is not None and bgm_path is not None and duck_db > 0.0:
        intervals = detect_speech_intervals(
            voice_path,
            duration_s=voice_dur,
            offset_s=lead_s,
            runner=runner,
            ffmpeg_bin=ffmpeg_bin,
        )
    duck_expr = build_duck_volume_expr(intervals, duck_db=duck_db)

    fmt = f"aformat=sample_fmts=fltp:sample_rates={BROADCAST_SAMPLE_RATE}:channel_layouts=stereo"
    inputs: list[str] = []
    filters: list[str] = []
    mix_labels: list[str] = []
    in_idx = 0

    if voice_path is not None:
        inputs.extend(["-i", _ffmpeg_input_path(voice_path)])
        delay_ms = int(round(max(0.0, lead_s) * 1000.0))
        v_chain = f"[{in_idx}:a]{fmt}"
        if delay_ms > 0:
            v_chain += f",adelay={delay_ms}:all=1"
        v_chain += f",apad=whole_dur={total_dur:.3f}[vstem]"
        filters.append(v_chain)
        mix_labels.append("[vstem]")
        in_idx += 1

    if bgm_path is not None:
        if bgm_dur > 0.0 and bgm_dur < total_dur:
            inputs.extend(["-stream_loop", "-1"])
        inputs.extend(["-i", _ffmpeg_input_path(bgm_path)])
        fade_out_st = max(0.0, total_dur - max(0.5, min(2.5, tail_s if tail_s > 0 else 1.5)))
        fade_out_d = max(0.2, total_dur - fade_out_st)
        m_chain = (
            f"[{in_idx}:a]{fmt},atrim=0:{total_dur:.3f},asetpts=N/SR/TB,"
            f"volume={bgm_gain_db}dB"
        )
        if duck_expr != "1":
            m_chain += f",volume='{duck_expr}':eval=frame"
        m_chain += f",afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}[mstem]"
        filters.append(m_chain)
        mix_labels.append("[mstem]")
        in_idx += 1

    for sfx_idx, (cue_path, when_s, gain_db) in enumerate(sfx_cues):
        inputs.extend(["-i", _ffmpeg_input_path(cue_path)])
        delay_ms = int(round(when_s * 1000.0))
        lbl = f"sfx{sfx_idx}"
        s_chain = f"[{in_idx}:a]{fmt}"
        if gain_db != 0.0:
            s_chain += f",volume={gain_db}dB"
        if delay_ms > 0:
            s_chain += f",adelay={delay_ms}:all=1"
        s_chain += f",apad=whole_dur={total_dur:.3f}[{lbl}]"
        filters.append(s_chain)
        mix_labels.append(f"[{lbl}]")
        in_idx += 1

    if len(mix_labels) == 1:
        filters.append(f"{mix_labels[0]}anull[mixed]")
    else:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:normalize=0:dropout_transition=0[mixed]"
        )

    filter_graph = ";".join(filters)
    with tempfile.TemporaryDirectory(prefix="forge-mix-") as tmp:
        raw_mix_wav = Path(tmp) / "mixed_24bit.wav"
        fc_flag = "-filter_complex"
        fc_arg = filter_graph
        if len(filter_graph) > 20000:
            detected_script_flag = _ffmpeg_script_flag(ffmpeg_bin, runner)
            if detected_script_flag:
                fc_path = Path(tmp) / "mix_graph.fc"
                fc_path.write_text(filter_graph, encoding="utf-8")
                fc_flag = detected_script_flag
                fc_arg = str(fc_path)

        mix_cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-nostdin",
            "-y",
            *inputs,
            fc_flag,
            fc_arg,
            "-map",
            "[mixed]",
            "-ar",
            str(BROADCAST_SAMPLE_RATE),
            "-c:a",
            "pcm_s24le",
            str(raw_mix_wav),
        ]
        proc = runner(mix_cmd)
        if proc.returncode != 0:
            err_tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
            raise AudioFormatError(f"Stem amix stage failed: {err_tail}")

        loudness = normalize_audio_two_pass(
            raw_mix_wav,
            dst_path,
            target_i=target_i,
            target_tp=target_tp,
            channels_hint=2,
            runner=runner,
            ffmpeg_bin=ffmpeg_bin,
        )

    return {
        "backend": "ffmpeg:envelope_duck_amix_2pass_loudnorm",
        "speech_intervals": intervals,
        "duck_volume_expr": duck_expr,
        "loudness": loudness,
    }


def db_to_reaper_linear_gain(db_val: float) -> float:
    """Convert dB gain to REAPER linear amplitude ratio ``10 ** (db / 20)``."""
    return 10.0 ** (float(db_val) / 20.0)


def _validate_rpp_token(value: str, *, field_name: str) -> str:
    """Reject newlines, control characters, and quote delimiters before writing .rpp (CWE-74)."""
    for bad in ('"', "'", "`", "\n", "\r", "\x00"):
        if bad in value:
            raise AudioFormatError(
                f"Unsafe character {bad!r} in REAPER .rpp {field_name} (CWE-74 injection guard)."
            )
    return value


def emit_reaper_session(
    rpp_path: Path,
    *,
    tracks: Sequence[tuple[str, Path, float, float]],
    duck: bool = False,
    creative_sound_dir: Path | None = None,
    runner: Callable[[Sequence[str]], Any],
) -> dict[str, Any]:
    """Emit a REAPER ``.rpp`` multitrack project via ``session.py`` or stdlib fallback."""
    if not tracks:
        raise AudioFormatError("Cannot emit a REAPER .rpp session with zero tracks.")
    rpp_path.parent.mkdir(parents=True, exist_ok=True)

    if creative_sound_dir is not None:
        session_py = creative_sound_dir / "scripts" / "session.py"
        if session_py.is_file():
            print("INFO: Delegating REAPER session to creative-stack sound/scripts/session.py", file=sys.stderr)
            with tempfile.TemporaryDirectory(prefix="forge-cs-rpp-") as tmp_cs:
                cs_rpp = Path(tmp_cs) / rpp_path.name
                cmd = [sys.executable, str(session_py), "-o", str(cs_rpp)]
                for _name, stem_path, offset_s, gain_db in tracks:
                    cmd.extend(["-t", f"{stem_path}@{offset_s}:{gain_db}"])
                if duck:
                    cmd.append("--duck")
                proc = runner(cmd)
                if proc.returncode == 0 and cs_rpp.is_file():
                    rpp_txt = cs_rpp.read_text(encoding="utf-8", errors="replace")
                    if "<REAPER_PROJECT" in rpp_txt:
                        shutil.copyfile(cs_rpp, rpp_path)
                        return {
                            "backend": "creative-stack:session.py",
                            "delegate_script": "sound/scripts/session.py",
                            "path": str(rpp_path),
                        }
                print(
                    f"WARNING: creative-stack session.py exited {proc.returncode}; falling back to stdlib .rpp: "
                    f"{(proc.stderr or '').strip()[:240]}",
                    file=sys.stderr,
                )

    source_tags = {
        ".wav": "WAVE",
        ".mp3": "MP3",
        ".flac": "FLAC",
        ".ogg": "VORBIS",
        ".opus": "OPUS",
        ".m4a": "VIDEO",
        ".aac": "VIDEO",
    }
    lines = [
        '<REAPER_PROJECT 0.1 "7.0" 1731571200',
        f"  SAMPLERATE {BROADCAST_SAMPLE_RATE} 0 0",
        "  TEMPO 120 4 4",
    ]
    for name, stem_path, offset_s, gain_db in tracks:
        safe_name = _validate_rpp_token(name, field_name="track name")
        safe_item = _validate_rpp_token(stem_path.name, field_name="item filename")
        safe_file = _validate_rpp_token(str(stem_path.resolve()), field_name="file path")
        lin_gain = db_to_reaper_linear_gain(gain_db)
        src_tag = source_tags.get(stem_path.suffix.lower(), "WAVE")
        lines.extend(
            [
                "  <TRACK",
                f'    NAME "{safe_name}"',
                f"    VOLPAN {lin_gain:.6f} 0 -1 -1 1",
                "    MAINSEND 1 0",
                "    <ITEM",
                f"      POSITION {max(0.0, float(offset_s)):.4f}",
                f'      NAME "{safe_item}"',
                f"      <SOURCE {src_tag}",
                f'        FILE "{safe_file}"',
                "      >",
                "    >",
                "  >",
            ]
        )
    lines.append(">")
    rpp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"backend": "stdlib:reaper_rpp_v0.1", "path": str(rpp_path)}
