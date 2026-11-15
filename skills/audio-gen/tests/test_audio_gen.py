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

"""Comprehensive T1-T6, V1-V6, and S1-S9 test suite for skills/audio-gen.

Zero unittest.mock usage (Engineering Standard / forensic_audit.py --strict):
all subprocess calls use injectable runners or real binaries, and all REST calls
exercise real urllib.request sockets against an ephemeral 127.0.0.1 HTTP server.
"""

from __future__ import annotations

import base64
import email.message
import hashlib
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import zlib
from pathlib import Path
from typing import Any, Sequence

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_GOOD = SKILL_DIR / "fixtures" / "known_good"
FIXTURES_BAD = SKILL_DIR / "fixtures" / "known_bad"
POTENTIAL_REPO_ROOT = SKILL_DIR.parents[1] if len(SKILL_DIR.parents) >= 2 else None

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audio_dsp  # noqa: E402
import audio_engines  # noqa: E402
import audio_gen  # noqa: E402
from audio_engines import CommandResult  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic Binary Fixture Builders (Zero External Libraries)
# ---------------------------------------------------------------------------


def make_sine_pcm16_wav(
    duration_s: float = 0.25,
    *,
    sample_rate: int = 48000,
    channels: int = 1,
    freq_hz: float = 440.0,
    amplitude: float = 8200.0,
) -> bytes:
    frames = max(1, int(round(duration_s * sample_rate)))
    samples: list[int] = []
    for idx in range(frames):
        val = int(round(amplitude * math.sin(2.0 * math.pi * freq_hz * idx / sample_rate)))
        for ch in range(channels):
            samples.append(val if ch == 0 else -val)
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, channels, sample_rate, byte_rate, block_align, 16)
    data = struct.pack("<4sI", b"data", len(pcm)) + pcm
    return struct.pack("<4sI4s", b"RIFF", 4 + len(fmt) + len(data), b"WAVE") + fmt + data


def make_tiny_png() -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return b"\x89PNG\r\n\x1a\n" + ihdr + iend


def make_minimal_flac(sample_rate: int = 48000, channels: int = 2, bits: int = 24, samples: int = 48000) -> bytes:
    streaminfo = bytearray(34)
    packed = (
        ((sample_rate & 0xFFFFF) << 44)
        | (((channels - 1) & 0x07) << 41)
        | (((bits - 1) & 0x1F) << 36)
        | (samples & 0xFFFFFFFFF)
    )
    struct.pack_into(">Q", streaminfo, 10, packed)
    hdr = bytes([0x80 | 0, 0x00, 0x00, 34])
    frame_bytes = b"\xff\xf8\x69\x18\x00\x11\x22\x33"
    return b"fLaC" + hdr + bytes(streaminfo) + frame_bytes


def make_minimal_ogg(codec: str = "opus") -> bytes:
    if codec == "vorbis":
        ident = b"\x01vorbis" + struct.pack("<IBI", 0, 2, 48000) + b"\x00" * 13
    else:
        ident = b"OpusHead" + struct.pack("<BBHIhB", 1, 2, 312, 48000, 0, 0)
    page1 = bytearray(b"OggS\x00\x02" + b"\x00" * 20 + bytes([1, len(ident)])) + ident
    audio_pkt = b"\xde\xad\xbe\xef\x42\x99"
    page2 = bytearray(b"OggS\x00\x04" + b"\x00" * 20 + bytes([1, len(audio_pkt)])) + audio_pkt
    return bytes(page1 + page2)


def make_minimal_m4a() -> bytes:
    ftyp = struct.pack(">I4s4sI4s", 20, b"ftyp", b"M4A ", 0, b"isom")
    mdat = struct.pack(">I4s", 16, b"mdat") + b"\x11\x22\x33\x44\x55\x66\x77\x88"
    return ftyp + mdat


def make_passing_rubric_for_prompt(judge_prompt: str) -> dict[str, Any]:
    acs = json.loads(judge_prompt.split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
    return {
        "overall_pass": True,
        "criteria_results": [
            {
                "id": ac["id"],
                "passed": True,
                "observed_evidence": f"Audited audio and confirmed {ac['id']} ({ac['category']}).",
                "fix_instruction": "",
            }
            for ac in acs
        ],
        "remediation_prompt": "",
    }


def wrap_generate_envelope(verdict: dict[str, Any]) -> str:
    return json.dumps(
        {
            "id": "gen_judge_01",
            "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(verdict)}]}],
        }
    )


class PipelineFakeRunner:
    """Deterministic shell=False subprocess fake recording every argv vector."""

    def __init__(
        self,
        *,
        wav_bytes: bytes | None = None,
        loudnorm_i: str | None = None,
        loudnorm_tp: str = "-1.10",
        duration_s: float = 15.0,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.wav_bytes = wav_bytes or (FIXTURES_GOOD / "valid_sine.wav").read_bytes()
        self.loudnorm_i = loudnorm_i
        self.loudnorm_tp = loudnorm_tp
        self.duration_s = duration_s
        self.lyria_failures_remaining = 0
        self.tts_fail_models: dict[str, int] = {}
        self.judge_verdicts: list[dict[str, Any]] = []
        self.judge_fail_models: dict[str, tuple[int, str]] = {}
        self.judge_raw_stdout: str | None = None
        self.dynamic_first_pass2 = False

    def __call__(self, argv: Sequence[str]) -> CommandResult:
        cmd = tuple(str(x) for x in argv)
        self.calls.append(cmd)
        exe = Path(cmd[0]).name

        if exe == "gemini-api":
            sub = cmd[1] if len(cmd) > 1 else ""
            if sub == "--version":
                return CommandResult(0, "gemini-api 0.5.0-test\n", "", cmd)
            if sub == "whoami":
                return CommandResult(0, '{"authenticated": true}\n', "", cmd)
            if sub == "music":
                if self.lyria_failures_remaining > 0:
                    self.lyria_failures_remaining -= 1
                    return CommandResult(1, "", "503 deadline_exceeded: backend overloaded", cmd)
                out_p = Path(cmd[cmd.index("--out") + 1])
                out_p.parent.mkdir(parents=True, exist_ok=True)
                payload = (
                    (FIXTURES_GOOD / "valid_frame.mp3").read_bytes()
                    if out_p.suffix.lower() == ".mp3"
                    else self.wav_bytes
                )
                out_p.write_bytes(payload)
                return CommandResult(
                    0,
                    json.dumps({"path": str(out_p), "response_id": "resp_lyria_1", "status": "completed"}),
                    "",
                    cmd,
                )
            if sub == "tts":
                model = cmd[cmd.index("-m") + 1]
                rem = self.tts_fail_models.get(model, 0)
                if rem > 0:
                    self.tts_fail_models[model] = rem - 1
                    return CommandResult(1, "", f"503 service unavailable on {model}", cmd)
                out_p = Path(cmd[cmd.index("--out") + 1])
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_bytes(self.wav_bytes)
                return CommandResult(
                    0,
                    json.dumps({"path": str(out_p), "response_id": "resp_tts_1", "status": "completed"}),
                    "",
                    cmd,
                )
            if sub == "video":
                out_p = Path(cmd[cmd.index("--out") + 1])
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_bytes(make_minimal_m4a())
                return CommandResult(
                    0,
                    json.dumps({"path": str(out_p), "response_id": "resp_foley_1", "status": "completed"}),
                    "",
                    cmd,
                )
            if sub == "generate":
                judge_model = cmd[cmd.index("-m") + 1] if "-m" in cmd else ""
                if judge_model in self.judge_fail_models:
                    rc_j, msg_j = self.judge_fail_models[judge_model]
                    return CommandResult(rc_j, "", msg_j, cmd)
                if self.judge_raw_stdout is not None:
                    return CommandResult(0, self.judge_raw_stdout, "", cmd)
                prompt = cmd[2]
                verdict = (
                    self.judge_verdicts.pop(0)
                    if self.judge_verdicts
                    else make_passing_rubric_for_prompt(prompt)
                )
                return CommandResult(0, wrap_generate_envelope(verdict), "", cmd)

        if exe == "ffprobe":
            return CommandResult(
                0,
                json.dumps(
                    {
                        "streams": [
                            {
                                "codec_type": "audio",
                                "codec_name": "pcm_s24le",
                                "sample_rate": "48000",
                                "channels": 2,
                                "duration": f"{self.duration_s:.6f}",
                            }
                        ],
                        "format": {"duration": f"{self.duration_s:.6f}", "bit_rate": "2304000"},
                    }
                ),
                "",
                cmd,
            )

        if exe == "ffmpeg":
            cmd_join = " ".join(cmd)
            if "silencedetect" in cmd_join:
                stderr = (
                    "[silencedetect @ 0x1] silence_start: 0.000\n"
                    "[silencedetect @ 0x1] silence_end: 0.500 | silence_duration: 0.500\n"
                    "[silencedetect @ 0x1] silence_start: 3.200\n"
                    "[silencedetect @ 0x1] silence_end: 4.000 | silence_duration: 0.800\n"
                )
                return CommandResult(0, "", stderr, cmd)
            if "print_format=json" in cmd_join:
                target_match = re.search(r"loudnorm=I=([-0-9.]+):TP=([-0-9.]+)", cmd_join)
                dyn_i = target_match.group(1) if target_match else "-14.00"
                reported_i = self.loudnorm_i if self.loudnorm_i is not None else dyn_i
                if self.dynamic_first_pass2 and "prelimited" not in cmd_join and "pre_norm" not in cmd_join:
                    reported_i = "-15.40"
                stderr = json.dumps(
                    {
                        "input_i": reported_i,
                        "input_tp": self.loudnorm_tp,
                        "input_lra": "5.20",
                        "input_thresh": "-24.10",
                        "target_offset": "0.05",
                    }
                )
                return CommandResult(0, "", stderr, cmd)
            out_p = Path(cmd[-1])
            if out_p.name != "-":
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_bytes(self.wav_bytes)
            p2_err = ""
            if self.dynamic_first_pass2 and "linear=true" in cmd_join:
                if "prelimited" in cmd_join:
                    p2_err = "Normalization Type: Dynamic Linear\n"
                    self.dynamic_first_pass2 = False
                else:
                    p2_err = "Normalization Type: Dynamic\n"
            return CommandResult(0, "", p2_err, cmd)

        if exe == "gcloud":
            return CommandResult(0, "gcloud_oauth_stub_token_xyz123\n", "", cmd)

        return CommandResult(127, "", f"Unhandled fake binary: {exe}", cmd)


# ---------------------------------------------------------------------------
# 1. Pure-Stdlib Binary Container & PCM Amplitude Tests (V1, V2, T4)
# ---------------------------------------------------------------------------


class BinaryAudioInspectionTests(unittest.TestCase):
    def test_known_good_wav_pcm16_pcm24_and_mp3_fixtures_pass(self):
        sine16 = audio_dsp.inspect_audio_file(FIXTURES_GOOD / "valid_sine.wav")
        self.assertTrue(sine16.valid, sine16.errors)
        self.assertEqual(sine16.format, "wav")
        self.assertEqual(sine16.sample_rate, 48000)
        self.assertEqual(sine16.channels, 1)
        self.assertEqual(sine16.bits_per_sample, 16)
        self.assertAlmostEqual(sine16.duration_s, 0.25, places=3)
        self.assertFalse(sine16.is_silent)
        self.assertFalse(sine16.is_clipped)
        self.assertIsNotNone(sine16.pcm_sha256)
        as_dict = sine16.to_dict()
        self.assertEqual(as_dict["format"], "wav")
        self.assertGreater(as_dict["peak_norm"], 0.2)

        sine24 = audio_dsp.inspect_audio_file(FIXTURES_GOOD / "valid_stereo_24bit.wav")
        self.assertTrue(sine24.valid, sine24.errors)
        self.assertEqual(sine24.channels, 2)
        self.assertEqual(sine24.bits_per_sample, 24)
        self.assertAlmostEqual(sine24.duration_s, 0.10, places=3)
        self.assertFalse(sine24.is_silent)

        mp3_info = audio_dsp.inspect_audio_file(FIXTURES_GOOD / "valid_frame.mp3")
        self.assertTrue(mp3_info.valid, mp3_info.errors)
        self.assertEqual(mp3_info.format, "mp3")
        self.assertEqual(mp3_info.sample_rate, 48000)
        self.assertGreater(mp3_info.duration_s, 0.15)

    def test_pcm8_pcm32_float32_flac_ogg_and_m4a_containers_pass(self):
        # PCM 8-bit unsigned
        pcm8 = bytes([128 + int(60 * math.sin(2 * math.pi * i / 32)) for i in range(640)])
        wav8 = (
            struct.pack("<4sI4s", b"RIFF", 36 + len(pcm8), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, 16000, 16000, 1, 8)
            + struct.pack("<4sI", b"data", len(pcm8))
            + pcm8
        )
        self.assertTrue(audio_dsp.inspect_audio_file(wav8).valid)

        # PCM 32-bit signed
        pcm32 = struct.pack("<200i", *[int(400_000_000 * math.sin(i * 0.2)) for i in range(200)])
        wav32 = (
            struct.pack("<4sI4s", b"RIFF", 36 + len(pcm32), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, 48000, 192000, 4, 32)
            + struct.pack("<4sI", b"data", len(pcm32))
            + pcm32
        )
        self.assertTrue(audio_dsp.inspect_audio_file(wav32).valid)

        # IEEE Float32
        flt32 = struct.pack("<200f", *[0.35 * math.sin(i * 0.2) for i in range(200)])
        wavf = (
            struct.pack("<4sI4s", b"RIFF", 36 + len(flt32), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 3, 1, 48000, 192000, 4, 32)
            + struct.pack("<4sI", b"data", len(flt32))
            + flt32
        )
        self.assertTrue(audio_dsp.inspect_audio_file(wavf).valid)

        flac_res = audio_dsp.inspect_audio_file(make_minimal_flac())
        self.assertTrue(flac_res.valid, flac_res.errors)
        self.assertEqual(flac_res.format, "flac")
        self.assertAlmostEqual(flac_res.duration_s, 1.0, places=3)

        ogg_opus = audio_dsp.inspect_audio_file(make_minimal_ogg("opus"))
        self.assertTrue(ogg_opus.valid, ogg_opus.errors)
        ogg_vorbis = audio_dsp.inspect_audio_file(make_minimal_ogg("vorbis"))
        self.assertTrue(ogg_vorbis.valid, ogg_vorbis.errors)

        m4a_res = audio_dsp.inspect_audio_file(make_minimal_m4a())
        self.assertTrue(m4a_res.valid, m4a_res.errors)
        self.assertEqual(m4a_res.format, "m4a")

    def test_known_bad_corrupt_silent_clipped_and_disguised_files_rejected(self):
        corrupt = audio_dsp.inspect_audio_file(FIXTURES_BAD / "corrupt_header.wav")
        self.assertFalse(corrupt.valid)

        silent = audio_dsp.inspect_audio_file(FIXTURES_BAD / "digital_silence.wav")
        self.assertFalse(silent.valid)
        self.assertTrue(silent.is_silent)
        self.assertTrue(any("digitally silent" in e for e in silent.errors))

        clipped = audio_dsp.inspect_audio_file(FIXTURES_BAD / "severely_clipped.wav")
        self.assertFalse(clipped.valid)
        self.assertTrue(clipped.is_clipped)
        self.assertTrue(any("severely clipped" in e for e in clipped.errors))

        disguised = audio_dsp.inspect_audio_file(FIXTURES_BAD / "disguised_text.wav")
        self.assertFalse(disguised.valid)
        self.assertEqual(disguised.format, "unknown")

        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.require_valid_audio(FIXTURES_BAD / "disguised_text.wav", label="bad input")
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.require_valid_audio(
                FIXTURES_GOOD / "valid_frame.mp3", label="must be wav", require_wav=True
            )

    def test_image_magic_accepts_png_jpeg_webp_and_rejects_text(self):
        self.assertEqual(audio_dsp.inspect_image_magic(make_tiny_png()), "png")
        self.assertEqual(audio_dsp.inspect_image_magic(b"\xff\xd8\xff\xe0" + b"\x00" * 16), "jpeg")
        self.assertEqual(audio_dsp.inspect_image_magic(b"RIFF\x20\x00\x00\x00WEBP" + b"\x00" * 8), "webp")
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.inspect_image_magic(FIXTURES_BAD / "disguised_text.wav")

    def test_stereo_right_channel_streaming_wav_adts_aac_and_mpeg2_l1(self):
        # REV-015: Stereo WAV with left=0, right=sine MUST NOT be falsely flagged silent
        sr = 48000
        frames = 2400
        samples_lr: list[int] = []
        for i in range(frames):
            samples_lr.append(0)  # Left silent
            samples_lr.append(int(round(9000.0 * math.sin(2.0 * math.pi * 440.0 * i / sr))))  # Right active
        pcm_lr = struct.pack(f"<{len(samples_lr)}h", *samples_lr)
        wav_r_only = (
            struct.pack("<4sI4s", b"RIFF", 36 + len(pcm_lr), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 2, sr, sr * 4, 4, 16)
            + struct.pack("<4sI", b"data", len(pcm_lr))
            + pcm_lr
        )
        r_info = audio_dsp.inspect_audio_file(wav_r_only)
        self.assertTrue(r_info.valid, r_info.errors)
        self.assertFalse(r_info.is_silent)

        all_zero_stereo = struct.pack(f"<{frames * 2}h", *([0] * (frames * 2)))
        wav_zero_lr = (
            struct.pack("<4sI4s", b"RIFF", 36 + len(all_zero_stereo), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 2, sr, sr * 4, 4, 16)
            + struct.pack("<4sI", b"data", len(all_zero_stereo))
            + all_zero_stereo
        )
        z_info = audio_dsp.inspect_audio_file(wav_zero_lr)
        self.assertFalse(z_info.valid)
        self.assertTrue(z_info.is_silent)

        # REV-016: Streaming WAV sizes (0xFFFFFFFF) accepted cleanly
        sine_raw = make_sine_pcm16_wav(duration_s=0.1)
        pcm_only = sine_raw[44:]
        streaming_wav = (
            struct.pack("<4sI4s", b"RIFF", 0xFFFFFFFF, b"WAVE")
            + sine_raw[12:36]
            + struct.pack("<4sI", b"data", 0xFFFFFFFF)
            + pcm_only
        )
        s_info = audio_dsp.inspect_audio_file(streaming_wav)
        self.assertTrue(s_info.valid, s_info.errors)
        self.assertAlmostEqual(s_info.duration_s, 0.1, places=3)

        # REV-017: ADTS AAC detected accurately (not misread as 1-frame MP3), single random sync rejected
        adts_frame_len = 32
        adts_hdr = bytearray(7)
        adts_hdr[0] = 0xFF
        adts_hdr[1] = 0xF1
        adts_hdr[2] = (1 << 6) | (3 << 2) | 0  # profile=LC, sr_idx=3 (48kHz), ch_msb=0
        adts_hdr[3] = (2 << 6) | ((adts_frame_len >> 11) & 0x03)
        adts_hdr[4] = (adts_frame_len >> 3) & 0xFF
        adts_hdr[5] = ((adts_frame_len & 0x07) << 5) | 0x1F
        adts_hdr[6] = 0xFC
        adts_blob = (bytes(adts_hdr) + b"\x21\x43\x65\x87" * 6 + b"\x01") * 10
        aac_info = audio_dsp.inspect_audio_file(adts_blob)
        self.assertTrue(aac_info.valid, aac_info.errors)
        self.assertEqual(aac_info.format, "aac")
        self.assertAlmostEqual(aac_info.duration_s, (10 * 1024) / 48000.0, places=3)

        noise_one_sync = b"\xff\xfb\x90\x00" + (b"\x12\x34\x56\x78" * 160)
        self.assertFalse(audio_dsp.inspect_audio_file(noise_one_sync).valid)

        # REV-023: MPEG-2 Layer I bitrate index 2 == 48 kbps
        self.assertEqual(audio_dsp._mpeg_bitrate_kbps(2, 3, 2), 48)


# ---------------------------------------------------------------------------
# 2. DSP Resolver, 2-Pass Loudnorm, Ducking, Crossfade & /sound Bridge Tests
# ---------------------------------------------------------------------------


class BroadcastDspAndCreativeStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="audio_dsp_t_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_keg_only_ffmpeg_resolver_precedence(self):
        custom_dir = self.root / "custom_bin"
        keg_dir = self.root / "keg_bin"
        custom_dir.mkdir()
        keg_dir.mkdir()
        custom_ff = custom_dir / "ffmpeg"
        custom_fp = custom_dir / "ffprobe"
        keg_ff = keg_dir / "ffmpeg"
        for p in (custom_ff, custom_fp, keg_ff):
            p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            p.chmod(0o755)

        # 1. $CREATIVE_STACK_FFMPEG wins and also resolves sibling ffprobe
        env1 = {"CREATIVE_STACK_FFMPEG": str(custom_ff)}
        self.assertEqual(
            audio_dsp.resolve_media_binary("ffmpeg", env=env1, which_fn=lambda _: "/usr/bin/ffmpeg", keg_dirs=(keg_dir,)),
            str(custom_ff),
        )
        self.assertEqual(
            audio_dsp.resolve_media_binary("ffprobe", env=env1, which_fn=lambda _: "/usr/bin/ffprobe", keg_dirs=(keg_dir,)),
            str(custom_fp),
        )
        # 2. Keg-only ffmpeg-full wins over PATH which()
        self.assertEqual(
            audio_dsp.resolve_media_binary("ffmpeg", env={}, which_fn=lambda _: "/usr/bin/ffmpeg", keg_dirs=(keg_dir,)),
            str(keg_ff),
        )
        # 3. Fallback to which_fn when neither env nor keg exists
        self.assertEqual(
            audio_dsp.resolve_media_binary("ffmpeg", env={}, which_fn=lambda _: "/usr/bin/ffmpeg", keg_dirs=()),
            "/usr/bin/ffmpeg",
        )

    def test_ffprobe_and_ebur128_parsers_and_negative_cases(self):
        probe_info = audio_dsp.parse_ffprobe_audio_json(
            (FIXTURES_GOOD / "passing_ffprobe.json").read_text(encoding="utf-8")
        )
        self.assertEqual(probe_info["sample_rate"], 48000)
        self.assertEqual(probe_info["channels"], 2)
        self.assertAlmostEqual(probe_info["duration_s"], 15.0)

        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.parse_ffprobe_audio_json('{"streams":[{"codec_type":"video"}]}')

        ebur_stats = audio_dsp.parse_ebur128_and_loudnorm(
            (FIXTURES_GOOD / "passing_ebur128.txt").read_text(encoding="utf-8")
        )
        self.assertAlmostEqual(ebur_stats["i"], -14.02, places=2)
        self.assertAlmostEqual(ebur_stats["tp"], -1.15, places=2)

        summary_only = audio_dsp.parse_ebur128_and_loudnorm(
            "Summary:\n  I: -15.5 LUFS\n  LRA: 6.1 LU\n  Peak: -1.3 dBFS\n"
        )
        self.assertAlmostEqual(summary_only["i"], -15.5)
        self.assertEqual(summary_only["source"], "ebur128_summary")

        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.parse_ebur128_and_loudnorm('{"input_i": "-inf", "input_tp": "-inf"}')

    def test_two_pass_loudnorm_enforces_48khz_and_dual_mono_for_mono_voice(self):
        fake = PipelineFakeRunner()
        mono_src = FIXTURES_GOOD / "valid_sine.wav"
        stereo_src = FIXTURES_GOOD / "valid_stereo_24bit.wav"
        mono_dst = self.root / "mono_norm.wav"
        stereo_dst = self.root / "stereo_norm.mp3"

        mono_res = audio_dsp.normalize_audio_two_pass(
            mono_src, mono_dst, target_i=-14.0, target_tp=-1.0, runner=fake, ffmpeg_bin="ffmpeg"
        )
        self.assertTrue(mono_res["dual_mono"])
        self.assertEqual(mono_res["sample_rate"], 48000)
        self.assertIn("dual_mono=true:linear=true", mono_res["filter_pass2"])

        stereo_res = audio_dsp.normalize_audio_two_pass(
            stereo_src, stereo_dst, target_i=-14.0, target_tp=-1.0, runner=fake, ffmpeg_bin="ffmpeg"
        )
        self.assertFalse(stereo_res["dual_mono"])
        self.assertIn("dual_mono=false:linear=true", stereo_res["filter_pass2"])
        # Pass 2 encode command must include -ar 48000 and libmp3lame
        pass2_cmds = [c for c in fake.calls if "linear=true" in " ".join(c)]
        self.assertEqual(len(pass2_cmds), 2)
        self.assertIn("48000", pass2_cmds[1])
        self.assertIn("libmp3lame", pass2_cmds[1])

    def test_acrossfade_stitcher_and_envelope_ducking_and_amix_normalize_zero(self):
        fake = PipelineFakeRunner()
        seg1 = self.root / "seg1_3s.wav"
        seg2 = self.root / "seg2_3s.wav"
        seg1.write_bytes(make_sine_pcm16_wav(duration_s=3.0))
        seg2.write_bytes(make_sine_pcm16_wav(duration_s=3.0, channels=2))
        stitched = self.root / "stitched.wav"
        audio_dsp.stitch_audio_segments([seg1, seg2], stitched, crossfade_s=2.0, runner=fake, ffmpeg_bin="ffmpeg")
        xf_cmd = " ".join(fake.calls[-1])
        self.assertIn("acrossfade=d=2.000:c1=tri:c2=tri", xf_cmd)
        self.assertIn("pcm_s24le", xf_cmd)

        # Short segments swallowed by >= crossfade overlap MUST fail closed (REV-019)
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.stitch_audio_segments(
                [FIXTURES_GOOD / "valid_sine.wav", FIXTURES_GOOD / "valid_stereo_24bit.wav"],
                self.root / "too_short_stitch.wav",
                crossfade_s=2.0,
                runner=fake,
                ffmpeg_bin="ffmpeg",
            )

        cue_spec = f"{seg1}@1.25:-3.5"
        parsed_cue = audio_dsp.parse_sfx_cue(cue_spec)
        self.assertAlmostEqual(parsed_cue[1], 1.25)
        self.assertAlmostEqual(parsed_cue[2], -3.5)

        fake.calls.clear()
        mix_out = self.root / "episode.wav"
        mix_info = audio_dsp.mix_broadcast_stems(
            voice_path=seg1,
            bgm_path=seg2,
            sfx_cues=[parsed_cue],
            dst_path=mix_out,
            lead_s=1.0,
            tail_s=2.0,
            bgm_gain_db=-16.0,
            duck_db=14.0,
            runner=fake,
            ffmpeg_bin="ffmpeg",
            ffprobe_bin="ffprobe",
        )
        self.assertEqual(mix_info["backend"], "ffmpeg:envelope_duck_amix_2pass_loudnorm")
        self.assertIn("if(lt(t,", mix_info["duck_volume_expr"])
        multi_win_expr = audio_dsp.build_duck_volume_expr([(0.5, 2.0), (4.0, 6.0)], duck_db=12.0)
        self.assertTrue(multi_win_expr.startswith("min("))
        all_ffmpeg = "\n".join(" ".join(c) for c in fake.calls)
        self.assertIn("amix=inputs=3:normalize=0", all_ffmpeg)
        self.assertNotIn("sidechaincompress", all_ffmpeg)

    def test_creative_stack_discovery_delegation_and_standalone_fallbacks(self):
        # Standalone fallbacks first (--creative-stack off)
        self.assertIsNone(audio_dsp.discover_creative_stack_sound("off"))
        fake = PipelineFakeRunner()
        src_wav = FIXTURES_GOOD / "valid_stereo_24bit.wav"

        stripped = self.root / "stripped.wav"
        s_res = audio_dsp.strip_vocals_to_backing(
            src_wav, stripped, creative_sound_dir=None, runner=fake, ffmpeg_bin="ffmpeg"
        )
        self.assertEqual(s_res["backend"], "ffmpeg:bass_preserving_center_cut_130hz")
        self.assertIn("lowpass=f=130", " ".join(fake.calls[-1]))
        self.assertIn("highpass=f=130", " ".join(fake.calls[-1]))

        cleaned = self.root / "cleaned.wav"
        c_res = audio_dsp.clean_voice_track(
            src_wav, cleaned, creative_sound_dir=None, runner=fake, ffmpeg_bin="ffmpeg"
        )
        self.assertEqual(c_res["backend"], "ffmpeg:clean_chain_2pass_dual_mono")

        rpp_path = self.root / "show.rpp"
        r_res = audio_dsp.emit_reaper_session(
            rpp_path,
            tracks=[("Voice", src_wav, 0.0, 0.0), ("BGM", src_wav, 2.0, -6.0)],
            duck=True,
            creative_sound_dir=None,
            runner=fake,
        )
        self.assertEqual(r_res["backend"], "stdlib:reaper_rpp_v0.1")
        rpp_text = rpp_path.read_text(encoding="utf-8")
        self.assertIn("<REAPER_PROJECT", rpp_text)
        self.assertIn(f"{audio_dsp.db_to_reaper_linear_gain(-6.0):.6f}", rpp_text)

        # Now create a synthetic creative-stack skills/sound tree and verify delegation
        cs_root = self.root / "fake_cs"
        scripts_d = cs_root / "skills" / "sound" / "scripts"
        scripts_d.mkdir(parents=True)
        wav_hex = (FIXTURES_GOOD / "valid_sine.wav").read_bytes().hex()
        for sname in ("mix.py", "clean.py", "karaoke.py", "session.py", "bed.py"):
            (scripts_d / sname).write_text(
                f"import pathlib, sys\n"
                f"argv = sys.argv[1:]\n"
                f"out = pathlib.Path(argv[argv.index('-o') + 1])\n"
                f"out.parent.mkdir(parents=True, exist_ok=True)\n"
                f"if out.suffix == '.rpp':\n"
                f"    out.write_text('<REAPER_PROJECT 0.1>\\n', encoding='utf-8')\n"
                f"else:\n"
                f"    out.write_bytes(bytes.fromhex({wav_hex!r}))\n",
                encoding="utf-8",
            )

        discovered = audio_dsp.discover_creative_stack_sound("auto", env={"CREATIVE_STACK_ROOT": str(cs_root)})
        self.assertEqual(discovered, (cs_root / "skills" / "sound").resolve())

        real_runner = audio_engines.default_runner
        del_strip = audio_dsp.strip_vocals_to_backing(
            src_wav, self.root / "cs_strip.wav", creative_sound_dir=discovered, runner=real_runner, ffmpeg_bin=None
        )
        self.assertEqual(del_strip["backend"], "creative-stack:karaoke.py")
        self.assertEqual(del_strip["delegate_script"], "sound/scripts/karaoke.py")

        del_clean = audio_dsp.clean_voice_track(
            src_wav, self.root / "cs_clean.wav", creative_sound_dir=discovered, runner=real_runner, ffmpeg_bin=None
        )
        self.assertEqual(del_clean["backend"], "creative-stack:clean.py")
        self.assertEqual(del_clean["delegate_script"], "sound/scripts/clean.py")

        del_mix = audio_dsp.mix_broadcast_stems(
            voice_path=src_wav,
            bgm_path=src_wav,
            sfx_cues=[],
            dst_path=self.root / "cs_mix.wav",
            creative_sound_dir=discovered,
            runner=real_runner,
            ffmpeg_bin=None,
        )
        self.assertEqual(del_mix["backend"], "creative-stack:mix.py")
        self.assertEqual(del_mix["delegate_script"], "sound/scripts/mix.py")

        del_rpp = audio_dsp.emit_reaper_session(
            self.root / "cs_show.rpp",
            tracks=[("Voice", src_wav, 0.0, 0.0)],
            creative_sound_dir=discovered,
            runner=real_runner,
        )
        self.assertEqual(del_rpp["backend"], "creative-stack:session.py")
        self.assertEqual(del_rpp["delegate_script"], "sound/scripts/session.py")

    def test_dsp_failure_modes_and_security_controls(self):
        # REV-018: Out-of-tolerance loudnorm fails closed; dynamic fallback triggers dynaudnorm+alimiter retry
        bad_fake = PipelineFakeRunner(loudnorm_i="-15.50")
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.normalize_audio_two_pass(
                FIXTURES_GOOD / "valid_sine.wav",
                self.root / "bad_norm.wav",
                target_i=-14.0,
                target_tp=-1.0,
                runner=bad_fake,
                ffmpeg_bin="ffmpeg",
            )

        dyn_fake = PipelineFakeRunner()
        dyn_fake.dynamic_first_pass2 = True
        dyn_res = audio_dsp.normalize_audio_two_pass(
            FIXTURES_GOOD / "valid_sine.wav",
            self.root / "dyn_recovered.wav",
            target_i=-14.0,
            target_tp=-1.0,
            runner=dyn_fake,
            ffmpeg_bin="ffmpeg",
        )
        self.assertAlmostEqual(dyn_res["output_lufs"], -14.0, places=1)
        self.assertTrue(any("dynaudnorm" in " ".join(c) for c in dyn_fake.calls))

        # REV-020: NaN / Inf rejected cleanly in DSP & music planning
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.parse_sfx_cue(f"{FIXTURES_GOOD / 'valid_sine.wav'}@nan:0")
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.parse_sfx_cue(f"{FIXTURES_GOOD / 'valid_sine.wav'}@1.0:inf")
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.build_duck_volume_expr([(0.5, 2.0)], duck_db=float("nan"))
        with self.assertRaises(audio_engines.ConfigError):
            audio_engines.plan_music_segments(float("inf"), model="lyria-3.5")

        # REV-021: Unprobable container without ffprobe fails closed instead of guessing 10s
        m4a_p = self.root / "unknown_dur.m4a"
        m4a_p.write_bytes(make_minimal_m4a())
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.mix_broadcast_stems(
                voice_path=None,
                bgm_path=m4a_p,
                sfx_cues=[],
                dst_path=self.root / "fail_dur.wav",
                creative_sound_dir=None,
                runner=bad_fake,
                ffmpeg_bin="ffmpeg",
                ffprobe_bin=None,
            )

        # REV-022: Stale pre-existing file at dst_path does NOT masquerade as delegate success
        cs_root = self.root / "noop_cs"
        scripts_d = cs_root / "skills" / "sound" / "scripts"
        scripts_d.mkdir(parents=True)
        (scripts_d / "karaoke.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        stale_dst = self.root / "stale_strip.wav"
        stale_dst.write_bytes((FIXTURES_GOOD / "valid_sine.wav").read_bytes())
        noop_res = audio_dsp.strip_vocals_to_backing(
            FIXTURES_GOOD / "valid_stereo_24bit.wav",
            stale_dst,
            creative_sound_dir=cs_root / "skills" / "sound",
            runner=bad_fake,
            ffmpeg_bin="ffmpeg",
        )
        self.assertEqual(noop_res["backend"], "ffmpeg:bass_preserving_center_cut_130hz")

        # SEC-002: Reject CWE-74 newline/quote injection inside REAPER .rpp metadata
        with self.assertRaises(audio_dsp.AudioFormatError):
            audio_dsp.emit_reaper_session(
                self.root / "bad_track.rpp",
                tracks=[('Bad"\nName', FIXTURES_GOOD / "valid_sine.wav", 0.0, 0.0)],
                creative_sound_dir=None,
                runner=bad_fake,
            )

        # Verify _ffmpeg_script_flag detects both ffmpeg flag spellings
        self.assertEqual(
            audio_dsp._ffmpeg_script_flag("ffmpeg", lambda c: CommandResult(0, "-/filter_complex", "", tuple(c))),
            "-/filter_complex",
        )
        self.assertEqual(
            audio_dsp._ffmpeg_script_flag("ffmpeg", lambda c: CommandResult(0, "-filter_complex_script", "", tuple(c))),
            "-filter_complex_script",
        )
        self.assertIsNone(
            audio_dsp._ffmpeg_script_flag("ffmpeg", lambda c: CommandResult(0, "none", "", tuple(c)))
        )


# ---------------------------------------------------------------------------
# 3. Secret Redaction (S8) & Real urllib.request Transport REST Tests
# ---------------------------------------------------------------------------


class _InProcessGoogleAudioHandler(urllib.request.BaseHandler):
    """Drives real urllib.request.OpenerDirector + HTTPError/URLError in-process."""

    handler_order = 10

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def http_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        parsed = urllib.parse.urlparse(req.full_url)
        path_with_query = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        raw_body = req.data or b""
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        hdrs = {k.lower(): v for k, v in req.header_items()}
        self.state["requests"].append(
            {"path": path_with_query, "headers": hdrs, "payload": payload}
        )

        msg = email.message.Message()
        msg["Content-Type"] = "application/json"

        if self.state.get("force_500_secret_echo"):
            fake_ai_key = "AIza" + "SyTestSecretEchoKey0123456789abcdefXYZ"
            err_doc = {
                "error": {
                    "message": (
                        f"Upstream error echoing key={fake_ai_key} and "
                        f"voice_cloning_key=secret_clone_tok_9999999999999999"
                    )
                }
            }
            err_bytes = json.dumps(err_doc).encode("utf-8")
            raise urllib.error.HTTPError(
                req.full_url, 500, "Internal Server Error", msg, io.BytesIO(err_bytes)
            )

        sample_b64 = base64.b64encode(make_sine_pcm16_wav(0.3)).decode("ascii")
        if parsed.path == "/v1beta/voices":
            if payload.get("type") == "prompted":
                resp = {"name": "voices/voice_designed_baritone_01", "sample_audio": sample_b64}
            else:
                vid = (
                    "voicekey_ephemeral_abc1234567890"
                    if payload.get("store") is False
                    else "voice_replicated_persist_01"
                )
                resp = {"id": vid, "sample_audio": sample_b64}
        elif parsed.path in ("/v1/text:synthesize", "/v1beta1/text:synthesize"):
            resp = {"audioContent": sample_b64}
        else:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", msg, io.BytesIO(b"{}"))

        body_bytes = json.dumps(resp).encode("utf-8")
        resp_obj = urllib.response.addinfourl(io.BytesIO(body_bytes), msg, req.full_url, 200)
        resp_obj.msg = "OK"
        return resp_obj


class SecretRedactionAndLocalhostRestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="audio_rest_t_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.state: dict[str, Any] = {"requests": [], "force_500_secret_echo": False}
        self.base_url = "http://127.0.0.1:18080"
        self.opener = urllib.request.build_opener(_InProcessGoogleAudioHandler(self.state))

    def _transport(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: int = 120,
    ) -> audio_engines.HttpResponseData:
        return audio_engines.default_http_transport(
            method, url, headers, body, timeout, opener=self.opener
        )

    def test_s8_secret_redaction_in_real_subprocess_and_text(self):
        pem_hdr = "-----BEGIN " + "PRIVATE KEY-----"
        pem_ftr = "-----END " + "PRIVATE KEY-----"
        pem_b64 = "".join(["MIIE", "vQIB", "ADAN", "Bgkq", "hkiG", "9w0B", "AQEF", "AASC", "BKcw", "ggSj", "AgEA", "AoIB", "AQC"])
        google_key = "AIza" + "SyDummy" + "CredentialValue" + "1234567890" + "abcdef"
        oauth_tok = "ya29." + "a0AfH6SMC_" + "dummy_oauth_" + "access_token_value"
        gcp_val = "gcp_test_" + "val_12345"
        bare_tok = "SuperSecret" + "TokenValue" + "9876543210"
        bare_key = "key=" + bare_tok
        gcp_env_name = "GOOGLE_CLOUD_API" + "_KEY"
        gem_env_name = "GEMINI_API" + "_KEY"
        acc_env_name = "GOOGLE_CLOUD_ACCESS" + "_TOKEN"
        clone_field = "voice_cloning" + "_key"
        raw_secret_blob = (
            f"url=https://api.example/v1?key={google_key}&access_token={oauth_tok} "
            f"Authorization: Bearer {'my_super_secret_' + 'bearer_token_123456'} "
            f"{gem_env_name}={google_key} {gcp_env_name}={gcp_val} "
            f"{acc_env_name}={oauth_tok} "
            f'{clone_field}="{"clone_secret_" + "xyz987654321"}" {"voicekey_" + "ephemeralSecret123456"} '
            f"{bare_key} musical_hint key=F# "
            f"{pem_hdr}\n{pem_b64}\n{pem_ftr}"
        )

        proc = audio_engines.default_runner(
            [sys.executable, "-c", f"import sys; sys.stderr.write({raw_secret_blob!r})"]
        )
        self.assertEqual(proc.returncode, 0)
        for forbidden in (
            google_key,
            oauth_tok,
            "my_super_secret_" + "bearer_token_123456",
            gcp_val,
            "clone_secret_" + "xyz987654321",
            "ephemeralSecret123456",
            bare_tok,
            pem_b64,
        ):
            self.assertNotIn(forbidden, proc.stderr)
        # Benign short musical key must survive untouched
        self.assertIn("key=F#", proc.stderr)

        # JSON-preserving redaction + Base64 (+ / ==) tail redaction + null safety
        b64_secret = "".join(["Ab", "3+", "Xyz/", "1234", "5678", "90+/", "TA", "IL=="])
        raw_json = json.dumps(
            {
                "api_key": "secret_json_" + "val_987654",
                "empty_api": None,
                "api_key_null_check": None,
                "key": b64_secret,
            }
        )
        redacted_json = audio_engines.redact_secrets(raw_json + ', "api_key": null')
        # Also verify pure JSON object round-trips cleanly via json.loads
        parsed_redacted = json.loads(audio_engines.redact_secrets(raw_json))
        self.assertTrue(parsed_redacted["api_key"].startswith("[REDACTED:"))
        self.assertTrue(parsed_redacted["key"].startswith("[REDACTED:"))
        self.assertNotIn("TAIL==", audio_engines.redact_secrets(f"key={b64_secret}"))
        self.assertIn('"api_key": null', redacted_json)

        # REV-031: Numeric/boolean/null JSON values under bare key / api_key stay valid JSON
        numeric_json = json.dumps({"key": 12345678901234567890, "api_key": 42, "flag": True})
        self.assertEqual(json.loads(audio_engines.redact_secrets(numeric_json)), json.loads(numeric_json))

        # Home path contraction & CWE-88 positional prompt normalization
        self.assertEqual(
            audio_engines.contract_home(Path.home() / "proj" / "clip.wav"),
            "~/proj/clip.wav",
        )
        self.assertEqual(audio_engines.contract_home("files/clip_01"), "files/clip_01")
        self.assertEqual(
            audio_engines.normalize_cli_positional_prompt("- spoken bullet", verbatim_speech=True),
            " - spoken bullet",
        )
        self.assertEqual(
            audio_engines.normalize_cli_positional_prompt("- ambient synth", verbatim_speech=False),
            "Prompt: - ambient synth",
        )
        self.assertEqual(
            audio_engines.validate_chirp3_text_markup("One [pause] two [pause short] three [pause long]"),
            ["default", "short", "long"],
        )
        with self.assertRaises(audio_engines.ConfigError):
            audio_engines.validate_chirp3_text_markup("Bad [pause medium] pause tag")
        with self.assertRaises(audio_engines.ConfigError):
            audio_engines.validate_chirp3_text_markup("Invalid [pause forever] markup")

    def test_non_loopback_plain_http_base_url_is_rejected_exit_2(self):
        out = self.root / "bad_url.wav"
        rc = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice-design",
                "--voice-prompt",
                "Warm alto",
                "--sample-text",
                "Testing scheme enforcement.",
                "--no-verify",
                "--override-reason",
                "HTTP scheme allowlist verification",
                "--no-normalize",
                "-o",
                str(out),
            ],
            env={
                "FORGE_GEMINI_API_BASE_URL": "http://insecure.example.com",
                "GEMINI_API_KEY": "test_key_value",
            },
        )
        self.assertEqual(rc, 2)
        self.assertFalse(out.exists())

    def test_v1beta_voices_design_and_consent_gated_replication_end_to_end(self):
        env = {
            "FORGE_GEMINI_API_BASE_URL": self.base_url,
            "GEMINI_API_KEY": "test_gemini_header_key_value",
        }
        fake_cli = PipelineFakeRunner()

        # 1. Voice Design (type: prompted)
        designed_out = self.root / "designed.wav"
        designed_meta = self.root / "designed_meta.json"
        rc_design = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice-design",
                "--voice-prompt",
                "Warm baritone documentary narrator",
                "--sample-text",
                "Glacial meltwater carved blue ice.",
                "--locale",
                "en-GB",
                "--voice-meta-out",
                str(designed_meta),
                "-o",
                str(designed_out),
            ],
            runner=fake_cli,
            http_transport=self._transport,
            which_fn=lambda name: f"/usr/bin/{name}",
            env=env,
        )
        self.assertEqual(rc_design, 0)
        self.assertTrue(audio_dsp.inspect_audio_file(designed_out).valid)
        d_meta = json.loads(designed_meta.read_text(encoding="utf-8"))
        self.assertEqual(d_meta["voice_id"], "voice_designed_baritone_01")
        self.assertFalse(d_meta["ephemeral"])
        req0 = self.state["requests"][-1]
        self.assertEqual(req0["path"], "/v1beta/voices")
        self.assertNotIn("key=", req0["path"])
        self.assertEqual(req0["headers"]["x-goog-api-key"], "test_gemini_header_key_value")
        self.assertEqual(req0["payload"]["type"], "prompted")

        # 2. Voice Replication negative consent gates (all MUST exit 2 before any HTTP request!)
        before_req_count = len(self.state["requests"])
        src_12s = self.root / "source_12s.wav"
        consent_ok = self.root / "consent_distinct.wav"
        src_short_4s = self.root / "source_4s.wav"
        src_12s.write_bytes(make_sine_pcm16_wav(12.0, sample_rate=16000, freq_hz=220.0))
        consent_ok.write_bytes(make_sine_pcm16_wav(4.0, sample_rate=16000, freq_hz=330.0))
        src_short_4s.write_bytes(make_sine_pcm16_wav(4.0, sample_rate=16000, freq_hz=220.0))

        # 2a. Missing consent-audio -> exit 2
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "voice-replicate", "--source-audio", str(src_12s), "-o", str(self.root / "x.wav")],
                runner=fake_cli,
                env=env,
            ),
            2,
        )
        # 2b. Identical SHA-256 source and consent -> exit 2
        same_copy = self.root / "consent_same.wav"
        same_copy.write_bytes(src_12s.read_bytes())
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                [
                    "--mode",
                    "voice-replicate",
                    "--source-audio",
                    str(src_12s),
                    "--consent-audio",
                    str(same_copy),
                    "-o",
                    str(self.root / "x.wav"),
                ],
                runner=fake_cli,
                env=env,
            ),
            2,
        )
        # 2c. Source audio < 10s -> exit 2
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                [
                    "--mode",
                    "voice-replicate",
                    "--source-audio",
                    str(src_short_4s),
                    "--consent-audio",
                    str(consent_ok),
                    "-o",
                    str(self.root / "x.wav"),
                ],
                runner=fake_cli,
                env=env,
            ),
            2,
        )
        self.assertEqual(len(self.state["requests"]), before_req_count)

        # 3. Valid ephemeral Voice Replication (store: false -> voicekey_...)
        rep_out = self.root / "replicated.wav"
        rep_meta = self.root / "rep_meta.json"
        rc_rep = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice-replicate",
                "--source-audio",
                str(src_12s),
                "--consent-audio",
                str(consent_ok),
                "--sample-text",
                "Verified ephemeral custom voice sample.",
                "--ephemeral",
                "--voice-meta-out",
                str(rep_meta),
                "-o",
                str(rep_out),
            ],
            runner=fake_cli,
            http_transport=self._transport,
            which_fn=lambda name: f"/usr/bin/{name}",
            env=env,
        )
        self.assertEqual(rc_rep, 0)
        r_meta = json.loads(rep_meta.read_text(encoding="utf-8"))
        self.assertTrue(r_meta["voice_id"].startswith("voicekey_"))
        self.assertTrue(r_meta["ephemeral"])
        self.assertFalse(r_meta["store"])
        # Ephemeral voicekey must be redacted in public provenance file
        prov_text = Path(f"{rep_out}.provenance.json").read_text(encoding="utf-8")
        self.assertNotIn("voicekey_ephemeral_abc1234567890", prov_text)

    def test_chirp3_hd_header_auth_pronunciations_v1beta1_cloning_and_500_redaction(self):
        fake_cli = PipelineFakeRunner()
        env = {
            "FORGE_CLOUD_TTS_BASE_URL": self.base_url,
            "GOOGLE_CLOUD_API_KEY": "gcp_tts_header_only_secret_key",
        }
        out_v1 = self.root / "chirp_v1.wav"
        rc_v1 = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice",
                "--engine",
                "chirp3",
                "--prompt",
                "Deploying Istio [pause short] across clusters.",
                "--locale",
                "en-GB",
                "--voice-name",
                "Aoede",
                "--speaking-rate",
                "1.1",
                "--pronunciations",
                "Istio=ˈɪstioʊ:ipa",
                "-o",
                str(out_v1),
            ],
            runner=fake_cli,
            http_transport=self._transport,
            which_fn=lambda name: f"/usr/bin/{name}",
            env=env,
        )
        self.assertEqual(rc_v1, 0)
        req_v1 = self.state["requests"][-1]
        self.assertEqual(req_v1["path"], "/v1/text:synthesize")
        self.assertNotIn("key=", req_v1["path"])
        self.assertEqual(req_v1["headers"]["x-goog-api-key"], "gcp_tts_header_only_secret_key")
        self.assertEqual(req_v1["payload"]["voice"]["name"], "en-GB-Chirp3-HD-Aoede")
        self.assertEqual(
            req_v1["payload"]["input"]["markup"],
            "Deploying Istio [pause short] across clusters.",
        )
        self.assertNotIn("text", req_v1["payload"]["input"])
        self.assertEqual(
            req_v1["payload"]["input"]["customPronunciations"]["pronunciations"][0]["phoneticEncoding"],
            "PHONETIC_ENCODING_IPA",
        )

        # Plain text without [pause*] routes to input.text; [pause] routes to input.markup
        out_plain = self.root / "chirp_plain.wav"
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "voice", "--engine", "chirp3", "--prompt", "Plain text sentence.", "-o", str(out_plain)],
                runner=fake_cli,
                http_transport=self._transport,
                which_fn=lambda name: f"/usr/bin/{name}",
                env=env,
            ),
            0,
        )
        self.assertEqual(self.state["requests"][-1]["payload"]["input"]["text"], "Plain text sentence.")
        self.assertNotIn("markup", self.state["requests"][-1]["payload"]["input"])

        # Instant Custom Voice (--chirp-cloning-key -> /v1beta1/text:synthesize) + gcloud auth fallback
        out_clone = self.root / "chirp_clone.wav"
        rc_clone = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice",
                "--engine",
                "chirp3",
                "--prompt",
                "Testing instant custom voice [pause] synthesis.",
                "--chirp-cloning-key",
                "clone_tok_live_1234567890abcdef",
                "-o",
                str(out_clone),
            ],
            runner=fake_cli,
            http_transport=self._transport,
            which_fn=lambda name: f"/usr/bin/{name}",
            env={"FORGE_CLOUD_TTS_BASE_URL": self.base_url},
        )
        self.assertEqual(rc_clone, 0)
        req_beta = self.state["requests"][-1]
        self.assertEqual(req_beta["path"], "/v1beta1/text:synthesize")
        self.assertIn("Bearer gcloud_oauth_stub_token_xyz123", req_beta["headers"]["authorization"])
        self.assertEqual(req_beta["payload"]["input"]["markup"], "Testing instant custom voice [pause] synthesis.")
        self.assertEqual(
            req_beta["payload"]["voice"]["voiceClone"]["voiceCloningKey"],
            "clone_tok_live_1234567890abcdef",
        )

        # Force HTTP 500 echoing secrets and verify capture-time redaction in .report.json
        self.state["force_500_secret_echo"] = True
        fail_out = self.root / "chirp_500.wav"
        rc_500 = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice",
                "--engine",
                "chirp3",
                "--prompt",
                "Trigger server error.",
                "--max-attempts",
                "1",
                "-o",
                str(fail_out),
            ],
            runner=fake_cli,
            http_transport=self._transport,
            which_fn=lambda name: f"/usr/bin/{name}",
            env=env,
        )
        self.assertEqual(rc_500, 1)
        report_txt = Path(f"{fail_out}.report.json").read_text(encoding="utf-8")
        self.assertNotIn("SyTestSecretEchoKey0123456789abcdefXYZ", report_txt)
        self.assertNotIn("secret_clone_tok_9999999999999999", report_txt)
        self.assertIn("[REDACTED", report_txt)

    def test_gcloud_token_bypass_redaction_and_chirp_cloning_key_file_and_env(self):
        # REV-025: Real default_runner bypasses capture-time redaction for in-memory Bearer token
        fake_bin = self.root / "fake_gcloud_bin"
        fake_bin.mkdir()
        fake_gcloud = fake_bin / "gcloud"
        real_tok = "ya29." + "a0AfH6SMC_real_gcloud_token_should_survive_12345"
        fake_gcloud.write_text(f"#!/bin/sh\necho '{real_tok}'\n", encoding="utf-8")
        fake_gcloud.chmod(0o755)

        saved_path = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = f"{fake_bin}{os.pathsep}{saved_path}"
            hdrs, src_label = audio_engines.resolve_cloud_tts_auth_headers(
                env={},
                runner=audio_engines.default_runner,
            )
            self.assertEqual(src_label, "gcloud:print-access-token")
            self.assertEqual(hdrs["Authorization"], f"Bearer {real_tok}")
        finally:
            os.environ["PATH"] = saved_path

        # SEC-001: --chirp-cloning-key-file and CHIRP_VOICE_CLONING_KEY env work cleanly without stderr warning
        fake_cli = PipelineFakeRunner()
        key_file = self.root / "cloning_key.txt"
        key_file.write_text("file_clone_secret_abcdef012345\n", encoding="utf-8")
        stderr_buf = io.StringIO()
        prev_err = sys.stderr
        try:
            sys.stderr = stderr_buf
            rc_file = audio_gen.run_audio_pipeline(
                [
                    "--mode",
                    "voice",
                    "--engine",
                    "chirp3",
                    "--prompt",
                    "File secret check.",
                    "--chirp-cloning-key-file",
                    str(key_file),
                    "-o",
                    str(self.root / "clone_from_file.wav"),
                ],
                runner=fake_cli,
                http_transport=self._transport,
                which_fn=lambda name: f"/usr/bin/{name}",
                env={
                    "FORGE_CLOUD_TTS_BASE_URL": self.base_url,
                    "GOOGLE_CLOUD_API_KEY": "gcp_tts_header_key_check",
                },
            )
            self.assertEqual(rc_file, 0)
            self.assertNotIn("CWE-214", stderr_buf.getvalue())
            self.assertEqual(
                self.state["requests"][-1]["payload"]["voice"]["voiceClone"]["voiceCloningKey"],
                "file_clone_secret_abcdef012345",
            )

            # CHIRP_VOICE_CLONING_KEY env auto-routes to chirp3 v1beta1 without argv exposure
            rc_env = audio_gen.run_audio_pipeline(
                ["--prompt", "Env cloning key route.", "-o", str(self.root / "clone_from_env.wav")],
                runner=fake_cli,
                http_transport=self._transport,
                which_fn=lambda name: f"/usr/bin/{name}",
                env={
                    "FORGE_CLOUD_TTS_BASE_URL": self.base_url,
                    "GOOGLE_CLOUD_API_KEY": "gcp_tts_header_key_check",
                    "CHIRP_VOICE_CLONING_KEY": "env_clone_secret_987654",
                },
            )
            self.assertEqual(rc_env, 0)
            self.assertEqual(self.state["requests"][-1]["path"], "/v1beta1/text:synthesize")

            # Legacy --chirp-cloning-key argv prints explicit CWE-214 warning
            stderr_buf.truncate(0)
            stderr_buf.seek(0)
            rc_cli = audio_gen.run_audio_pipeline(
                [
                    "--mode",
                    "voice",
                    "--engine",
                    "chirp3",
                    "--prompt",
                    "CLI key warning check.",
                    "--chirp-cloning-key",
                    "cli_clone_secret_xyz",
                    "-o",
                    str(self.root / "clone_from_cli.wav"),
                ],
                runner=fake_cli,
                http_transport=self._transport,
                which_fn=lambda name: f"/usr/bin/{name}",
                env={
                    "FORGE_CLOUD_TTS_BASE_URL": self.base_url,
                    "GOOGLE_CLOUD_API_KEY": "gcp_tts_header_key_check",
                },
            )
            self.assertEqual(rc_cli, 0)
            self.assertIn("CWE-214", stderr_buf.getvalue())
        finally:
            sys.stderr = prev_err


# ---------------------------------------------------------------------------
# 4. Lyria, Gemini 3.8 TTS Hard Laws, SFX Engines, Deprecation & Retry Tests
# ---------------------------------------------------------------------------


class EnginesVerificationAndContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="audio_eng_t_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_t1_differentiation_across_modes_specs_and_dry_run(self):
        bgm_spec = audio_gen.compile_audio_spec(
            audio_gen.build_parser().parse_args(
                ["--mode", "bgm", "--prompt", "Warm lofi beats", "--genre", "lofi", "--bpm", "84"]
            ),
            mode="bgm",
            engine="lyria",
            prompt_text="Warm lofi beats",
            lyrics_text=None,
        )
        voice_spec = audio_gen.compile_audio_spec(
            audio_gen.build_parser().parse_args(
                ["--mode", "voice", "--prompt", "Hello world", "--delivery-style", "calm"]
            ),
            mode="voice",
            engine="gemini-tts",
            prompt_text="Hello world",
            lyrics_text=None,
        )
        self.assertNotEqual(bgm_spec["spec_sha256"], voice_spec["spec_sha256"])
        self.assertNotEqual(bgm_spec["compiled_prompt"], voice_spec["compiled_prompt"])
        self.assertTrue(bgm_spec["explicit_constraints"]["instrumental_only"])
        self.assertFalse(voice_spec["explicit_constraints"]["instrumental_only"])

        # Dry-run writes spec-out and exits 0 without invoking gemini-api
        fake = PipelineFakeRunner()
        spec_out = self.root / "frozen_spec.json"
        rc = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "bgm",
                "--prompt",
                "Ambient synth arpeggio",
                "--duration",
                "30",
                "--spec-out",
                str(spec_out),
                "--dry-run",
                "-o",
                str(self.root / "dry.wav"),
            ],
            runner=fake,
        )
        self.assertEqual(rc, 0)
        self.assertTrue(spec_out.is_file())
        self.assertEqual(fake.calls, [])

    def test_lyria_503_identical_model_retry_long_duration_stitch_and_instrumental_law(self):
        # --lyrics on bgm MUST exit 2
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Calm piano", "--lyrics", "La la la", "-o", str(self.root / "bad.wav")],
                runner=PipelineFakeRunner(),
            ),
            2,
        )

        img_ref = self.root / "mood.png"
        img_ref.write_bytes(make_tiny_png())
        fake = PipelineFakeRunner(wav_bytes=make_sine_pcm16_wav(duration_s=3.0), duration_s=240.0)
        fake.lyria_failures_remaining = 2  # First two attempts hit 503 deadline_exceeded
        sleeps: list[float] = []
        out_wav = self.root / "long_bgm.wav"

        rc = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "bgm",
                "--prompt",
                "Atmospheric synthwave horizon",
                "--genre",
                "synthwave",
                "--bpm",
                "100",
                "--key",
                "D minor",
                "--duration",
                "240",
                "-i",
                str(img_ref),
                "-o",
                str(out_wav),
            ],
            runner=fake,
            which_fn=lambda name: f"/usr/bin/{name}",
            env={},
            sleep_fn=sleeps.append,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(sleeps), 2)
        music_calls = [c for c in fake.calls if len(c) > 1 and c[1] == "music"]
        # 240s (>180s) -> 2 segments; segment 1 had 2 transient 503s + 1 success = 3 calls, segment 2 = 1 call -> 4 calls, ALL on lyria-3.5!
        self.assertEqual(len(music_calls), 4)
        for mc in music_calls:
            self.assertEqual(mc[mc.index("-m") + 1], "lyria-3.5")
            self.assertIn("Strictly instrumental only", mc[2])

    def test_gemini_tts_verbatim_text_vs_speech_metadata_and_chunk1_model_pinning(self):
        script = (
            "First paragraph with <short pause> expressive pacing that exceeds our small test chunk size.\n\n"
            "Second paragraph <sigh> continuing the exact same narrator voice across chunk two.\n\n"
            "Third paragraph concluding the technical walkthrough cleanly."
        )
        # Case A: gemini-3.8-flash-tts fails all 3 retries on Chunk 1 -> fails over to gemini-3.8-flash-lite-tts,
        # and Chunks 2 & 3 MUST stay pinned to gemini-3.8-flash-lite-tts!
        fake = PipelineFakeRunner()
        fake.tts_fail_models["gemini-3.8-flash-tts"] = 3
        out_tts = self.root / "narration.wav"

        rc = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice",
                "--prompt",
                script,
                "--voice-name",
                "Kore",
                "--delivery-style",
                "warm, brisk studio narrator",
                "--chunk-chars",
                "110",
                "-o",
                str(out_tts),
            ],
            runner=fake,
            which_fn=lambda name: f"/usr/bin/{name}",
            sleep_fn=lambda _: None,
        )
        self.assertEqual(rc, 0)
        tts_calls = [c for c in fake.calls if len(c) > 1 and c[1] == "tts"]
        # First 3 calls tried flash-tts on Chunk 1; remaining 3 calls (Chunk 1 failover + Chunk 2 + Chunk 3) MUST all use flash-lite-tts!
        models_called = [c[c.index("-m") + 1] for c in tts_calls]
        self.assertEqual(
            models_called,
            [
                "gemini-3.8-flash-tts",
                "gemini-3.8-flash-tts",
                "gemini-3.8-flash-tts",
                "gemini-3.8-flash-lite-tts",
                "gemini-3.8-flash-lite-tts",
                "gemini-3.8-flash-lite-tts",
            ],
        )
        for tc in tts_calls:
            spoken_arg = tc[2]
            cfg_json = json.loads(tc[tc.index("-c") + 1])
            self.assertNotIn("warm, brisk studio narrator", spoken_arg)
            self.assertEqual(cfg_json["annotations"][0]["type"], "speech_metadata")
            self.assertEqual(cfg_json["annotations"][0]["style"], "warm, brisk studio narrator")

        # Case B: Chunk 1 succeeds on flash-tts, then Chunk 2 hits persistent 503 -> MUST NOT failover to lite-tts!
        fake_b = PipelineFakeRunner()
        call_counter = {"n": 0}
        orig_call = fake_b.__call__

        def chunk2_fail_runner(argv: Sequence[str]) -> CommandResult:
            if len(argv) > 1 and argv[1] == "tts":
                call_counter["n"] += 1
                if call_counter["n"] >= 2:
                    return CommandResult(1, "", "503 overloaded on chunk 2", tuple(str(x) for x in argv))
            return orig_call(argv)

        out_fail = self.root / "timbre_pin_fail.wav"
        rc_b = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "voice",
                "--prompt",
                script,
                "--chunk-chars",
                "110",
                "--max-attempts",
                "1",
                "-o",
                str(out_fail),
            ],
            runner=chunk2_fail_runner,
            which_fn=lambda name: f"/usr/bin/{name}",
            sleep_fn=lambda _: None,
        )
        self.assertEqual(rc_b, 1)
        self.assertFalse(out_fail.exists())
        rep_b = json.loads(Path(f"{out_fail}.report.json").read_text(encoding="utf-8"))
        self.assertIn("pinned to 'gemini-3.8-flash-tts'", json.dumps(rep_b))

        # Case C: Multi-speaker dialogue + invalid inline XML tag rejection
        fake_dlg = PipelineFakeRunner()
        rc_dlg = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "dialogue",
                "--prompt",
                "Alex: Did the deployment finish? <short pause>\nSam: <laugh> Green across all regions!",
                "--speakers",
                "Alex=Kore:curious lead",
                "--speakers",
                "Sam=Puck:upbeat SRE",
                "-o",
                str(self.root / "dlg.wav"),
            ],
            runner=fake_dlg,
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_dlg, 0)

        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "voice", "--prompt", "Bad <script>alert(1)</script> tag", "-o", str(self.root / "bad.wav")],
                runner=fake_dlg,
            ),
            2,
        )

    def test_sfx_engines_omni_foley_lyria_sting_and_deprecation_verifier_fences(self):
        fake = PipelineFakeRunner(duration_s=5.0)
        rc_foley = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "sfx",
                "--sfx-engine",
                "omni-foley",
                "--prompt",
                "Crisp footsteps on wet gravel",
                "--duration",
                "5",
                "-o",
                str(self.root / "foley.wav"),
            ],
            runner=fake,
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_foley, 0)
        self.assertTrue(any(len(c) > 1 and c[1] == "video" and "gemini-omni-1.2-flash" in c for c in fake.calls))
        self.assertTrue(any("-vn" in c and "pcm_s24le" in c for c in fake.calls))

        rc_sting = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "stinger",
                "--sfx-engine",
                "lyria-sting",
                "--prompt",
                "Bright brass logo cadence",
                "--duration",
                "4",
                "-o",
                str(self.root / "sting.wav"),
            ],
            runner=PipelineFakeRunner(duration_s=4.0),
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_sting, 0)

        # Deprecated models & invalid --verifier-model MUST exit 2
        deprecated_cases = (
            ["--mode", "voice", "--model", "gemini-2.5-flash-preview-tts", "--prompt", "Hi"],
            ["--mode", "voice", "--model", "gemini-2.5-pro-preview-tts", "--prompt", "Hi"],
            ["--mode", "voice", "--model", "gemini-3.1-flash-tts-preview", "--prompt", "Hi"],
            ["--mode", "voice", "--engine", "chirp3", "--voice-name", "en-US-Wavenet-D", "--prompt", "Hi"],
            ["--mode", "voice", "--engine", "chirp3", "--voice-name", "chirp-2", "--prompt", "Hi"],
            ["--mode", "bgm", "--model", "gemini-2.0-flash", "--prompt", "Music"],
            ["--mode", "sfx", "--model", "veo-3.1-generate-preview", "--prompt", "Boom"],
            ["--mode", "bgm", "--verifier-model", "lyria-3.5", "--prompt", "Music"],
            ["--mode", "voice", "--verifier-model", "gemini-3.8-flash-tts", "--prompt", "Hi"],
        )
        for bad_args in deprecated_cases:
            with self.subTest(bad_args=bad_args):
                self.assertEqual(
                    audio_gen.run_audio_pipeline([*bad_args, "-o", str(self.root / "never.wav")], runner=fake),
                    2,
                )

    def test_s9_rubric_provenance_retry_loop_rejected_artifact_and_loud_override(self):
        # 1. Zero-mandatory spec fixture -> exit 2
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--spec-file", str(FIXTURES_BAD / "zero_mandatory_spec.json"), "-o", str(self.root / "z.wav")],
                runner=PipelineFakeRunner(),
            ),
            2,
        )

        # 2. Contradictory and missing-AC rubric fixtures fail validation deterministically
        sample_spec = json.loads((FIXTURES_GOOD / "sample_spec.json").read_text(encoding="utf-8"))
        contradict = json.loads((FIXTURES_BAD / "contradictory_argon_rubric.json").read_text(encoding="utf-8"))
        missing_ac = json.loads((FIXTURES_BAD / "missing_ac_argon_rubric.json").read_text(encoding="utf-8"))
        passing_ac = json.loads((FIXTURES_GOOD / "passing_argon_rubric.json").read_text(encoding="utf-8"))
        failing_ac = json.loads((FIXTURES_BAD / "failing_argon_rubric.json").read_text(encoding="utf-8"))

        v_con = audio_gen.validate_rubric_verdict(contradict, sample_spec["acceptance_criteria"])
        self.assertFalse(v_con["all_passed"])
        self.assertTrue(v_con["contradiction_detected"])

        v_mis = audio_gen.validate_rubric_verdict(missing_ac, sample_spec["acceptance_criteria"])
        self.assertFalse(v_mis["all_passed"])
        self.assertEqual(v_mis["missing_criteria"], ["AC-3"])

        # 3. Attempt 1 fails rubric -> Attempt 2 succeeds against unmodified spec_sha256
        fake_retry = PipelineFakeRunner(duration_s=15.0)
        fake_retry.judge_verdicts = [failing_ac, passing_ac]
        retry_out = self.root / "retry_bgm.wav"
        rc_ok = audio_gen.run_audio_pipeline(
            ["--spec-file", str(FIXTURES_GOOD / "sample_spec.json"), "-o", str(retry_out)],
            runner=fake_retry,
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_ok, 0)
        prov = json.loads(Path(f"{retry_out}.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["attempts_used"], 2)
        self.assertEqual(prov["spec_sha256"], sample_spec["spec_sha256"])

        # 4. Exhausted retries -> exit 1, <stem>.rejected.wav + .report.json, --output absent
        fake_fail = PipelineFakeRunner(duration_s=15.0)
        fake_fail.judge_verdicts = [contradict, failing_ac]
        exh_out = self.root / "exhausted.wav"
        rc_fail = audio_gen.run_audio_pipeline(
            [
                "--spec-file",
                str(FIXTURES_GOOD / "sample_spec.json"),
                "--max-attempts",
                "2",
                "-o",
                str(exh_out),
            ],
            runner=fake_fail,
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_fail, 1)
        self.assertFalse(exh_out.exists())
        self.assertTrue((self.root / "exhausted.rejected.wav").is_file())
        self.assertTrue(Path(f"{exh_out}.report.json").is_file())

        # Subsequent verified pass on the same output path cleans up stale .rejected.wav and .report.json
        fake_recover = PipelineFakeRunner(duration_s=15.0)
        fake_recover.judge_verdicts = [passing_ac]
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--spec-file", str(FIXTURES_GOOD / "sample_spec.json"), "-o", str(exh_out)],
                runner=fake_recover,
                which_fn=lambda name: f"/usr/bin/{name}",
            ),
            0,
        )
        self.assertTrue(exh_out.is_file())
        self.assertFalse((self.root / "exhausted.rejected.wav").exists())
        self.assertFalse(Path(f"{exh_out}.report.json").exists())
        rec_prov = json.loads(Path(f"{exh_out}.provenance.json").read_text(encoding="utf-8"))
        self.assertTrue(isinstance(rec_prov["timestamp_utc"], str) and rec_prov["timestamp_utc"].endswith("Z"))
        self.assertTrue(isinstance(rec_prov["output"], str) and rec_prov["output"].endswith("exhausted.wav"))

        # 5. --allow-unverified without --override-reason -> exit 2; with --override-reason -> exit 0
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--spec-file", str(FIXTURES_GOOD / "sample_spec.json"), "--allow-unverified", "-o", str(exh_out)],
                runner=fake_fail,
            ),
            2,
        )
        fake_ovr = PipelineFakeRunner(duration_s=15.0)
        fake_ovr.judge_verdicts = [failing_ac]
        ovr_out = self.root / "override_draft.wav"
        rc_ovr = audio_gen.run_audio_pipeline(
            [
                "--spec-file",
                str(FIXTURES_GOOD / "sample_spec.json"),
                "--max-attempts",
                "1",
                "--allow-unverified",
                "--override-reason",
                "Human scratchpad draft check",
                "-o",
                str(ovr_out),
            ],
            runner=fake_ovr,
            which_fn=lambda name: f"/usr/bin/{name}",
        )
        self.assertEqual(rc_ovr, 0)
        self.assertTrue(ovr_out.is_file())
        ovr_rep = json.loads(Path(f"{ovr_out}.report.json").read_text(encoding="utf-8"))
        self.assertEqual(ovr_rep["status"], "UNVERIFIED_OVERRIDE")
        self.assertEqual(ovr_rep["override_reason"], "Human scratchpad draft check")

    def test_doctor_s6_flag_parity_t6_constants_and_real_ffmpeg_e2e(self):
        fake = PipelineFakeRunner()
        self.assertEqual(
            audio_gen.run_doctor(
                creative_stack_arg="off",
                runner=fake,
                which_fn=lambda name: f"/usr/bin/{name}",
                env={"GEMINI_API_KEY": "shadow_check"},
            ),
            0,
        )
        self.assertEqual(
            audio_gen.run_doctor(creative_stack_arg="off", runner=fake, which_fn=lambda _: None, env={}),
            1,
        )

        # S6: SKILL.md <= 200 lines, cites all 3 reference docs, and every audio_gen.py --flag exists in --help
        skill_md_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill_md_text.splitlines()), 200)
        for ref_name in (
            "references/lyria_music_and_backing.md",
            "references/tts_voices_and_chirp3.md",
            "references/sfx_mixing_and_creative_stack.md",
        ):
            self.assertIn(ref_name, skill_md_text)
            self.assertTrue((SKILL_DIR / ref_name).is_file())

        help_proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "audio_gen.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_proc.returncode, 0)
        help_flags = set(re.findall(r"--[a-z0-9-]+", help_proc.stdout))
        for doc_path in [SKILL_DIR / "SKILL.md", *(SKILL_DIR / "references").glob("*.md")]:
            doc_text = doc_path.read_text(encoding="utf-8")
            for block in re.findall(r"audio_gen\.py\s+\\?\n?(.*?)(?:\n\n|```)", doc_text, flags=re.S):
                used_flags = set(re.findall(r"(?<!\w)(--[a-z0-9-]+)", block))
                unknown = used_flags - help_flags
                self.assertEqual(unknown, set(), f"{doc_path.name} cites undocumented flags: {unknown}")

        # Repo-level T6 & K6 checks when running inside monorepo checkout
        if POTENTIAL_REPO_ROOT and (POTENTIAL_REPO_ROOT / "scripts" / "sync_skills.py").is_file():
            img_script = POTENTIAL_REPO_ROOT / "skills" / "image-gen" / "scripts"
            if img_script.is_dir() and str(img_script) not in sys.path:
                sys.path.insert(0, str(img_script))
                import image_gen  # noqa: PLC0415

                self.assertEqual(audio_gen.VERIFIER_MODEL_CHAIN, ("gemini-4-argon", "gemini-4-carbon"))
                self.assertTrue(set(audio_gen.VERIFIER_MODEL_CHAIN).issubset(set(image_gen.VERIFIER_MODEL_CHAIN)))
                self.assertEqual(audio_gen.DEPRECATED_MODEL_PREFIXES, image_gen.DEPRECATED_MODEL_PREFIXES)

            repo_scripts = POTENTIAL_REPO_ROOT / "scripts"
            if str(repo_scripts) not in sys.path:
                sys.path.insert(0, str(repo_scripts))
            import sync_skills  # noqa: PLC0415

            self.assertIn("audio-gen", sync_skills.CORE_SKILLS)
            self.assertEqual(sync_skills.ALIASES.get("music-gen"), "audio-gen")
            self.assertEqual(sync_skills.ALIASES.get("sfx-gen"), "audio-gen")
            self.assertEqual(sync_skills.ALIASES.get("tts-gen"), "audio-gen")
            # CRITICAL K6 invariant: 'voice' MUST NEVER be registered as a skill or alias!
            self.assertNotIn("voice", sync_skills.ALIASES)
            self.assertNotIn("voice", sync_skills.CORE_SKILLS)

        # T5: Real host ffmpeg-full E2E synthesis + 2-pass -14 LUFS mastering when present
        real_ff = audio_dsp.resolve_media_binary("ffmpeg")
        real_fp = audio_dsp.resolve_media_binary("ffprobe")
        if not (real_ff and real_fp):
            self.skipTest("ffmpeg-full / ffprobe not installed on host")
        real_out = self.root / "real_lavfi_master.wav"
        real_rpp = self.root / "real_session.rpp"
        rc_real = audio_gen.run_audio_pipeline(
            [
                "--mode",
                "sfx",
                "--sfx-engine",
                "lavfi-synth",
                "--prompt",
                "Clean UI confirmation chime",
                "--duration",
                "1.5",
                "--creative-stack",
                "off",
                "--no-verify",
                "--override-reason",
                "Deterministic offline lavfi E2E test",
                "--reaper-rpp",
                str(real_rpp),
                "-o",
                str(real_out),
            ],
            env={},
        )
        self.assertEqual(rc_real, 0)
        inspected = audio_dsp.inspect_audio_file(real_out)
        self.assertTrue(inspected.valid, inspected.errors)
        self.assertEqual(inspected.sample_rate, 48000)
        self.assertEqual(inspected.bits_per_sample, 24)
        self.assertFalse(inspected.is_silent)
        self.assertTrue(real_rpp.is_file())

    def test_review_regressions_tts_chunk_overflow_crossfade_clamp_and_sfx_model_fence(self):
        # REV-024: Long run-on sentence after short sentences MUST NOT overwrite preceding sentences!
        s1 = "Alpha beta gamma delta."
        s2 = "Epsilon zeta eta theta."
        long_words = [f"w{i:02d}" for i in range(60)]
        text_64 = f"{s1} {s2} {' '.join(long_words)}."
        chunks = audio_engines.split_tts_chunks(text_64, max_chars=90)
        rejoined = " ".join(chunks).split()
        self.assertEqual(rejoined, text_64.split())

        # REV-027: Clamped crossfade applies equally to planning AND stitch_audio_segments
        fake = PipelineFakeRunner(wav_bytes=make_sine_pcm16_wav(duration_s=10.0), duration_s=45.0)
        audio_engines.run_lyria_generation(
            raw_prompt="Short clip loop",
            mode="stinger",
            explicit_model="lyria-3-clip-preview",
            duration_s=45.0,
            crossfade_s=12.0,
            image_refs=(),
            genre=None,
            bpm=None,
            musical_key=None,
            mood=None,
            instruments=None,
            lyrics=None,
            language=None,
            staging_dir=self.root / "xf_clamp",
            prefer_wav=True,
            runner=fake,
            ffmpeg_bin="ffmpeg",
        )
        xf_calls = [c for c in fake.calls if "acrossfade=" in " ".join(c)]
        self.assertEqual(len(xf_calls), 1)
        self.assertIn("acrossfade=d=7.500:c1=tri:c2=tri", " ".join(xf_calls[0]))

        # REV-028: role="sfx" strictly permits OMNI_FOLEY_MODEL (never Lyria models)
        with self.assertRaises(audio_engines.ConfigError):
            audio_engines.validate_audio_model_id("lyria-3.5", role="sfx")
        self.assertEqual(audio_engines.validate_audio_model_id("gemini-omni-1.2-flash", role="sfx"), "gemini-omni-1.2-flash")

    def test_full_pipeline_gate_fail_paths_aliasing_dups_overrides_and_carbon_failover(self):
        good_wav = self.root / "input_song.wav"
        good_wav.write_bytes((FIXTURES_GOOD / "valid_sine.wav").read_bytes())
        fake = PipelineFakeRunner(duration_s=15.0)

        # REV-001: Output aliasing input exits 2 and NEVER deletes input file!
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--strip-vocals-from", str(good_wav), "-o", str(good_wav)],
                runner=fake,
                env={},
            ),
            2,
        )
        self.assertTrue(good_wav.is_file())
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "mix", "--voice-track", str(good_wav), "-o", str(good_wav)],
                runner=fake,
                env={},
            ),
            2,
        )
        self.assertTrue(good_wav.is_file())

        # REV-001: Unrelated pre-existing non-forge file at --output is preserved when exit 1 fails
        preexisting_unowned = self.root / "user_existing.wav"
        preexisting_unowned.write_bytes(b"NOT_FORGE_CREATED")
        fail_r = PipelineFakeRunner(duration_s=15.0)
        fail_r.judge_verdicts = [json.loads((FIXTURES_BAD / "failing_argon_rubric.json").read_text(encoding="utf-8"))]
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                [
                    "--spec-file",
                    str(FIXTURES_GOOD / "sample_spec.json"),
                    "--max-attempts",
                    "1",
                    "-o",
                    str(preexisting_unowned),
                ],
                runner=fail_r,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )
        self.assertEqual(preexisting_unowned.read_bytes(), b"NOT_FORGE_CREATED")

        # REV-001 complementary half: previously verified forge output IS unlinked when re-run fails exit 1
        owned_out = self.root / "forge_owned.wav"
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--spec-file", str(FIXTURES_GOOD / "sample_spec.json"), "-o", str(owned_out)],
                runner=PipelineFakeRunner(duration_s=15.0),
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            0,
        )
        self.assertTrue(owned_out.is_file())
        self.assertTrue(audio_gen._has_valid_forge_provenance(owned_out))
        fail_owned_r = PipelineFakeRunner(duration_s=15.0)
        fail_owned_r.judge_verdicts = [json.loads((FIXTURES_BAD / "failing_argon_rubric.json").read_text(encoding="utf-8"))]
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--spec-file", str(FIXTURES_GOOD / "sample_spec.json"), "--max-attempts", "1", "-o", str(owned_out)],
                runner=fail_owned_r,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )
        self.assertFalse(owned_out.exists())
        self.assertFalse(Path(f"{owned_out}.provenance.json").exists())

        # REV-002 & REV-003 & REV-010: Duplicate/unknown AC IDs and bidirectional contradiction fail closed
        spec_acs = json.loads((FIXTURES_GOOD / "sample_spec.json").read_text(encoding="utf-8"))["acceptance_criteria"]
        dup_rubric = {
            "overall_pass": True,
            "criteria_results": [
                {"id": "AC-1", "passed": False, "observed_evidence": "First fail", "fix_instruction": "Fix"},
                {"id": "AC-1", "passed": True, "observed_evidence": "Second overwrite", "fix_instruction": ""},
                {"id": "AC-2", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-3", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
            ],
            "remediation_prompt": "",
        }
        v_dup = audio_gen.validate_rubric_verdict(dup_rubric, spec_acs)
        self.assertFalse(v_dup["all_passed"])
        self.assertFalse(v_dup["valid_schema"])

        unknown_rubric = {
            "overall_pass": True,
            "criteria_results": [
                {"id": "AC-1", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-2", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-3", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-99", "passed": True, "observed_evidence": "Hallucinated", "fix_instruction": ""},
            ],
            "remediation_prompt": "",
        }
        v_unk = audio_gen.validate_rubric_verdict(unknown_rubric, spec_acs)
        self.assertFalse(v_unk["all_passed"])

        false_contradiction = {
            "overall_pass": False,
            "criteria_results": [
                {"id": "AC-1", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-2", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
                {"id": "AC-3", "passed": True, "observed_evidence": "Ok", "fix_instruction": ""},
            ],
            "remediation_prompt": "",
        }
        v_fcon = audio_gen.validate_rubric_verdict(false_contradiction, spec_acs)
        self.assertFalse(v_fcon["all_passed"])
        self.assertTrue(v_fcon["contradiction_detected"])

        dup_spec = json.loads((FIXTURES_GOOD / "sample_spec.json").read_text(encoding="utf-8"))
        dup_spec["acceptance_criteria"] = [dup_spec["acceptance_criteria"][0], dup_spec["acceptance_criteria"][0]]
        dup_spec["spec_sha256"] = audio_gen.compute_spec_sha256(dup_spec["acceptance_criteria"])
        dup_spec_p = self.root / "dup_spec.json"
        dup_spec_p.write_text(json.dumps(dup_spec), encoding="utf-8")
        self.assertEqual(
            audio_gen.run_audio_pipeline(["--spec-file", str(dup_spec_p), "-o", str(self.root / "z.wav")], runner=fake, env={}),
            2,
        )

        # REV-004, REV-007, REV-008, REV-009, REV-020: Invalid numeric bounds, --max-attempts > 10, unused --model, --no-verify without reason -> exit 2
        bad_cli_cases = (
            ["--mode", "voice", "--prompt", "Hi", "--chunk-chars", "10"],
            ["--mode", "bgm", "--prompt", "Loop", "--duration", "-5"],
            ["--mode", "bgm", "--prompt", "Loop", "--duration", "nan"],
            ["--mode", "bgm", "--prompt", "Loop", "--crossfade", "-1"],
            ["--mode", "bgm", "--prompt", "Long", "--duration", "300", "--crossfade", "0", "--dry-run"],
            ["--mode", "bgm", "--prompt", "Clip", "--duration", "45", "-m", "lyria-3-clip-preview", "--crossfade", "0"],
            ["--mode", "bgm", "--prompt", "Loop", "--bpm", "10"],
            ["--mode", "bgm", "--prompt", "Loop", "--max-attempts", "0"],
            ["--mode", "bgm", "--prompt", "Loop", "--max-attempts", "99"],
            ["--mode", "mix"],
            ["--mode", "voice", "--engine", "chirp3", "-m", "gemini-3.8-flash-tts", "--prompt", "Hi"],
            ["--mode", "voice-design", "--voice-prompt", "Warm", "--sample-text", "Hi", "-m", "lyria-3.5"],
            ["--mode", "sfx", "--sfx-engine", "lavfi-synth", "--prompt", "Chime", "-m", "gemini-omni-1.2-flash"],
            ["--mode", "sfx", "--sfx-engine", "omni-foley", "--prompt", "Step", "-m", "lyria-3.5"],
            ["--mode", "sfx", "--sfx-engine", "lavfi-synth", "--prompt", "Chime", "--no-verify"],
            ["--mode", "voice", "--prompt", "Hi", "--override-reason", "orphan reason"],
        )
        for bad_argv in bad_cli_cases:
            with self.subTest(bad_argv=bad_argv):
                self.assertEqual(
                    audio_gen.run_audio_pipeline([*bad_argv, "-o", str(self.root / "bad_opt.wav")], runner=fake, env={}),
                    2,
                )

        # REV-005 & REV-007: --no-normalize records unchecked surface & PARTIAL_VERIFIED
        no_norm_out = self.root / "no_norm.wav"
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm pad", "--no-normalize", "-o", str(no_norm_out)],
                runner=PipelineFakeRunner(duration_s=30.0),
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            0,
        )
        nn_prov = json.loads(Path(f"{no_norm_out}.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(nn_prov["status"], "PARTIAL_VERIFIED")
        self.assertIn("loudness_gate_2pass_ebur128", nn_prov["unchecked_surfaces"])

        # REV-011 & REV-013: Full pipeline rejects known-bad audio, bad LUFS, invalid judge JSON, non-transient judge fail; and tests Carbon failover + missing ffmpeg
        for bad_name in ("digital_silence.wav", "severely_clipped.wav", "corrupt_header.wav", "disguised_text.wav"):
            bad_runner = PipelineFakeRunner(wav_bytes=(FIXTURES_BAD / bad_name).read_bytes(), duration_s=15.0)
            self.assertEqual(
                audio_gen.run_audio_pipeline(
                    [
                        "--mode",
                        "voice",
                        "--prompt",
                        "Test full pipeline rejection",
                        "--no-normalize",
                        "--max-attempts",
                        "1",
                        "-o",
                        str(self.root / f"rej_{bad_name}"),
                    ],
                    runner=bad_runner,
                    which_fn=lambda n: f"/usr/bin/{n}",
                    env={},
                ),
                1,
                f"Expected exit 1 when generator returns {bad_name}",
            )

        lufs_bad_runner = PipelineFakeRunner(loudnorm_i="-22.00", duration_s=15.0)
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--max-attempts", "1", "-o", str(self.root / "lufs_fail.wav")],
                runner=lufs_bad_runner,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )

        # Carbon failover when gemini-4-argon hits transient 503
        carbon_runner = PipelineFakeRunner(duration_s=15.0)
        carbon_runner.judge_fail_models["gemini-4-argon"] = (1, "503 service unavailable")
        carbon_out = self.root / "carbon_failover.wav"
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--max-attempts", "1", "-o", str(carbon_out)],
                runner=carbon_runner,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            0,
        )
        c_prov = json.loads(Path(f"{carbon_out}.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(c_prov["verifier_model_used"], "gemini-4-carbon")

        # Invalid judge JSON -> exit 1 fail closed
        bad_json_runner = PipelineFakeRunner(duration_s=15.0)
        bad_json_runner.judge_raw_stdout = "not valid json"
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--max-attempts", "1", "-o", str(self.root / "bad_judge_json.wav")],
                runner=bad_json_runner,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )

        # Non-transient judge error -> exit 1
        err_judge_runner = PipelineFakeRunner(duration_s=15.0)
        err_judge_runner.judge_fail_models["gemini-4-argon"] = (1, "400 invalid request payload")
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--max-attempts", "1", "-o", str(self.root / "bad_judge_400.wav")],
                runner=err_judge_runner,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )

        # Missing ffmpeg with --require-ffmpeg exits 2 cleanly (env={} & keg_dirs=() isolated from host)
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--require-ffmpeg", "-o", str(self.root / "need_ff.wav")],
                runner=fake,
                which_fn=lambda n: None if n in ("ffmpeg", "ffprobe") else f"/usr/bin/{n}",
                env={},
                keg_dirs=(),
            ),
            2,
        )

        # Stage 3 duration gate enforced end-to-end when generated audio duration disagrees with --duration
        short_dur_runner = PipelineFakeRunner(duration_s=5.0)
        self.assertEqual(
            audio_gen.run_audio_pipeline(
                ["--mode", "bgm", "--prompt", "Warm synth", "--duration", "60", "--max-attempts", "1", "-o", str(self.root / "dur_fail.wav")],
                runner=short_dur_runner,
                which_fn=lambda n: f"/usr/bin/{n}",
                env={},
            ),
            1,
        )

    def test_verify_audio_mechanical_rejects_every_stage3_failure_directly(self):
        good_wav = FIXTURES_GOOD / "valid_sine.wav"
        fake_025 = PipelineFakeRunner(duration_s=0.25)
        passing_loud = {"output_lufs": -14.0, "output_tp_dbtp": -1.0, "sample_rate": 48000}

        # Happy path passes cleanly with zero unchecked surfaces
        ok_pass, _, f_pass, u_pass = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=0.25,
            loudness_report=passing_loud,
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=True,
            runner=fake_025,
            ffprobe_bin="ffprobe",
        )
        self.assertTrue(ok_pass, f_pass)
        self.assertEqual(u_pass, [])

        # Known-bad binary fixtures must fail Stage 3 directly
        for bad_name in ("digital_silence.wav", "severely_clipped.wav", "corrupt_header.wav", "disguised_text.wav"):
            ok_bad, _, f_bad, _ = audio_gen.verify_audio_mechanical(
                FIXTURES_BAD / bad_name,
                expected_duration_s=None,
                loudness_report=passing_loud,
                target_i=-14.0,
                target_tp=-1.0,
                require_ffmpeg=False,
                runner=fake_025,
                ffprobe_bin=None,
            )
            self.assertFalse(ok_bad, f"verify_audio_mechanical should reject {bad_name}")
            self.assertTrue(f_bad)

        # Duration mismatch against expected_duration_s -> False
        ok_dur, _, f_dur, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=60.0,
            loudness_report=passing_loud,
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=True,
            runner=fake_025,
            ffprobe_bin="ffprobe",
        )
        self.assertFalse(ok_dur)
        self.assertTrue(any("outside expected" in m for m in f_dur))

        # LUFS mismatch (-20.0 vs -14.0 target) -> False
        ok_lufs, _, f_lufs, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report={"output_lufs": -20.0, "output_tp_dbtp": -1.0, "sample_rate": 48000},
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=False,
            runner=fake_025,
            ffprobe_bin=None,
        )
        self.assertFalse(ok_lufs)
        self.assertTrue(any("LUFS" in m for m in f_lufs))

        # True peak excess (0.0 vs -1.0 dBTP ceiling) -> False
        ok_tp, _, f_tp, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report={"output_lufs": -14.0, "output_tp_dbtp": 0.0, "sample_rate": 48000},
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=False,
            runner=fake_025,
            ffprobe_bin=None,
        )
        self.assertFalse(ok_tp)
        self.assertTrue(any("true peak" in m.lower() for m in f_tp))

        # Non-48kHz post-loudnorm sample rate -> False
        ok_sr, _, f_sr, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report={"output_lufs": -14.0, "output_tp_dbtp": -1.0, "sample_rate": 44100},
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=False,
            runner=fake_025,
            ffprobe_bin=None,
        )
        self.assertFalse(ok_sr)
        self.assertTrue(any("48000 Hz" in m for m in f_sr))

        # require_ffmpeg=True with ffprobe_bin=None -> False
        ok_req, _, f_req, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report=passing_loud,
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=True,
            runner=fake_025,
            ffprobe_bin=None,
        )
        self.assertFalse(ok_req)
        self.assertTrue(any("--require-ffmpeg" in m for m in f_req))

        # Corrupted ffprobe stream response -> False
        ok_fp_err, _, f_fp_err, _ = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report=passing_loud,
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=True,
            runner=lambda c: CommandResult(0, '{"streams":[{"codec_type":"video"}]}', "", tuple(c)),
            ffprobe_bin="ffprobe",
        )
        self.assertFalse(ok_fp_err)
        self.assertTrue(f_fp_err)

        # Unchecked tracking when ffprobe and loudness_report omitted without require_ffmpeg
        ok_unchk, _, _, unchk = audio_gen.verify_audio_mechanical(
            good_wav,
            expected_duration_s=None,
            loudness_report=None,
            target_i=-14.0,
            target_tp=-1.0,
            require_ffmpeg=False,
            runner=fake_025,
            ffprobe_bin=None,
        )
        self.assertTrue(ok_unchk)
        self.assertEqual(unchk, ["ffprobe_stream_metadata", "loudness_gate_2pass_ebur128"])


# ---------------------------------------------------------------------------
# 5. Real Host FFmpeg Multi-Window Integration & Acrossfade Tests
# ---------------------------------------------------------------------------


class ZRealFfmpegIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="audio_real_ff_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_real_ffmpeg_200plus_window_ducking_mix_and_acrossfade_stitch(self):
        # REV-012 & REV-014: Real ffmpeg execution (skipped cleanly only when binary absent)
        ff = audio_dsp.resolve_media_binary("ffmpeg")
        fp = audio_dsp.resolve_media_binary("ffprobe")
        if not (ff and fp):
            self.skipTest("ffmpeg-full / ffprobe not installed on host")

        # 205 speech bursts (0.05s active + 0.45s silence > 0.40s merge_gap_s -> ~102s track) at 8 kHz
        sr = 8000
        silence_samples = [0] * int(0.45 * sr)
        tone_samples = [
            int(round(12000.0 * math.sin(2.0 * math.pi * 440.0 * i / sr)))
            for i in range(int(0.05 * sr))
        ]
        cycle = tone_samples + silence_samples
        all_pcm = (cycle * 205) + tone_samples
        pcm_bytes = struct.pack(f"<{len(all_pcm)}h", *all_pcm)
        pulsed_voice = self.root / "pulsed_205_voice.wav"
        pulsed_voice.write_bytes(
            struct.pack("<4sI4s", b"RIFF", 36 + len(pcm_bytes), b"WAVE")
            + struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16)
            + struct.pack("<4sI", b"data", len(pcm_bytes))
            + pcm_bytes
        )
        bgm_wav = self.root / "real_bgm_loop.wav"
        bgm_wav.write_bytes(make_sine_pcm16_wav(duration_s=5.0, sample_rate=8000, channels=2, freq_hz=220.0))

        mixed_out = self.root / "real_205win_mix.wav"
        mix_meta = audio_dsp.mix_broadcast_stems(
            voice_path=pulsed_voice,
            bgm_path=bgm_wav,
            sfx_cues=[],
            dst_path=mixed_out,
            lead_s=0.25,
            tail_s=0.25,
            bgm_gain_db=-16.0,
            duck_db=14.0,
            creative_sound_dir=None,
            runner=audio_engines.default_runner,
            ffmpeg_bin=ff,
            ffprobe_bin=fp,
        )
        self.assertGreaterEqual(len(mix_meta["speech_intervals"]), 200)
        mixed_insp = audio_dsp.inspect_audio_file(mixed_out)
        self.assertTrue(mixed_insp.valid, mixed_insp.errors)
        self.assertEqual(mixed_insp.sample_rate, 48000)

        # Real ffmpeg acrossfade stitch verification
        s1 = self.root / "real_s1.wav"
        s2 = self.root / "real_s2.wav"
        s1.write_bytes(make_sine_pcm16_wav(duration_s=3.0, freq_hz=440.0))
        s2.write_bytes(make_sine_pcm16_wav(duration_s=3.0, freq_hz=554.37))
        stitched_real = self.root / "real_stitched.wav"
        audio_dsp.stitch_audio_segments(
            [s1, s2],
            stitched_real,
            crossfade_s=2.0,
            runner=audio_engines.default_runner,
            ffmpeg_bin=ff,
            ffprobe_bin=fp,
        )
        st_insp = audio_dsp.inspect_audio_file(stitched_real)
        self.assertTrue(st_insp.valid, st_insp.errors)
        self.assertEqual(st_insp.sample_rate, 48000)
        self.assertEqual(st_insp.bits_per_sample, 24)
        self.assertAlmostEqual(st_insp.duration_s, 4.0, places=1)


if __name__ == "__main__":
    unittest.main()
