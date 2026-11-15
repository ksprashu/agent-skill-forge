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

"""Cross-skill contract freshness (`T6`) and live subprocess E2E (`T5`/`T1`) tests.

Verifies that ``skills/image-gen/scripts/image_gen.py`` and
``skills/video-gen/scripts/video_gen.py`` share identical verifier/deprecation
constants and interoperate across real subprocess invocations for:
1. ``video_gen.py --synthesize-keyframes start-end`` delegating start and
   style-locked end frame synthesis to ``image_gen.py``.
2. ``image_gen.py --manifest`` emitting ``keyframes_manifest.json`` and
   ``video_gen.py --storyboard`` consuming it (including multi-segment
   ``ffmpeg`` concatenation).
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGE_GEN_DIR = REPO_ROOT / "skills" / "image-gen" / "scripts"
VIDEO_GEN_DIR = REPO_ROOT / "skills" / "video-gen" / "scripts"
AUDIO_GEN_DIR = REPO_ROOT / "skills" / "audio-gen" / "scripts"
IMAGE_GEN_SCRIPT = IMAGE_GEN_DIR / "image_gen.py"
VIDEO_GEN_SCRIPT = VIDEO_GEN_DIR / "video_gen.py"
AUDIO_GEN_SCRIPT = AUDIO_GEN_DIR / "audio_gen.py"

for _p in (str(IMAGE_GEN_DIR), str(VIDEO_GEN_DIR), str(AUDIO_GEN_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audio_engines  # noqa: E402
import audio_gen  # noqa: E402
import image_gen  # noqa: E402
import video_gen  # noqa: E402


def _make_valid_png_bytes(width: int, height: int) -> bytes:
    """Construct a minimal valid PNG header + IHDR chunk with valid CRC32."""
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    idat_crc = zlib.crc32(b"IDAT") & 0xFFFFFFFF
    idat_chunk = struct.pack(">I", 0) + b"IDAT" + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return b"\x89PNG\r\n\x1a\n" + ihdr_chunk + idat_chunk + iend_chunk


VALID_16X9_2K_PNG_HEX = _make_valid_png_bytes(1920, 1080).hex()
VALID_MP4_HEX = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08mdat\x01\x02\x03\x04"
).hex()


def _install_media_cli_stubs(bin_dir: Path, calls_log: Path) -> None:
    """Write executable stub gemini-api, ffprobe, and ffmpeg tools into bin_dir."""
    tiny_wav_hex = (
        REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "tiny_tone.wav"
    ).read_bytes().hex()
    gemini_stub = bin_dir / "gemini-api"
    gemini_stub.write_text(
        f"""#!{sys.executable}
import json
import pathlib
import re
import sys

argv = sys.argv[1:]
log_path = pathlib.Path({str(calls_log)!r})
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "gemini-api", "argv": argv}}) + "\\n")

sub = argv[0] if argv else ""
if sub == "--version":
    print("gemini-api 0.4.2-contract-stub")
    sys.exit(0)
if sub == "whoami":
    print(json.dumps({{"authenticated": True, "source": "keyring"}}))
    sys.exit(0)
if sub == "files" and len(argv) >= 2 and argv[1] == "upload":
    print("files/contract_cached_asset")
    sys.exit(0)
if sub in ("music", "tts"):
    out = pathlib.Path(argv[argv.index("--out") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = bytes.fromhex({tiny_wav_hex!r})
    out.write_bytes(payload)
    print(json.dumps({{
        "kind": sub,
        "path": str(out),
        "size_bytes": len(payload),
        "mime_type": "audio/wav",
        "response_id": f"v1_{{sub}}_stub",
        "status": "completed",
    }}))
    sys.exit(0)
if sub == "image":
    out = pathlib.Path(argv[argv.index("--out") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    real_out = out.with_suffix(".png")
    payload = bytes.fromhex({VALID_16X9_2K_PNG_HEX!r})
    real_out.write_bytes(payload)
    print(json.dumps({{
        "kind": "image",
        "path": str(real_out),
        "size_bytes": len(payload),
        "mime_type": "image/png",
        "response_id": "v1_img_stub",
        "status": "completed",
    }}))
    sys.exit(0)
if sub == "video":
    out = pathlib.Path(argv[argv.index("--out") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.loads(argv[argv.index("--body") + 1])
    dur_raw = str(body.get("response_format", {{}}).get("duration", "8s")).rstrip("s")
    payload = bytes.fromhex({VALID_MP4_HEX!r})
    out.write_bytes(payload)
    # Record expected duration alongside candidate MP4 so stub ffprobe returns exact timing.
    pathlib.Path(str(out) + ".dur").write_text(dur_raw, encoding="utf-8")
    print(json.dumps({{
        "kind": "video",
        "path": str(out),
        "size_bytes": len(payload),
        "mime_type": "video/mp4",
        "response_id": "v1_vid_stub",
        "status": "completed",
    }}))
    sys.exit(0)
if sub == "generate":
    prompt = argv[1]
    if "ACCEPTANCE_CRITERIA_JSON:" in prompt:
        acs = json.loads(prompt.split("ACCEPTANCE_CRITERIA_JSON:\\n", 1)[1])
        verdict = {{
            "overall_pass": True,
            "criteria_results": [
                {{
                    "id": a["id"],
                    "passed": True,
                    "observed_evidence": f"Verified {{a['id']}} in stubbed image.",
                    "fix_instruction": "",
                }}
                for a in acs
            ],
            "remediation_mode": "edit_turn",
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
        }}
    elif "- AC-" in prompt:
        ac_ids = re.findall(r"^- (AC-\\d+)\\b", prompt, flags=re.M)
        verdict = {{
            "criteria_results": [
                {{
                    "id": cid,
                    "passed": True,
                    "observed_evidence": f"Verified {{cid}} in stubbed video.",
                    "fix_instruction": "",
                }}
                for cid in ac_ids
            ],
            "remediation_mode": "edit_turn",
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
        }}
    else:
        verdict = {{"expanded_prompt": prompt}}
    print(json.dumps({{
        "id": "gen_stub",
        "status": "completed",
        "steps": [{{"type": "model_output", "content": [{{"type": "text", "text": json.dumps(verdict)}}]}}],
    }}))
    sys.exit(0)
sys.exit(1)
""",
        encoding="utf-8",
    )
    gemini_stub.chmod(0o755)

    ffprobe_stub = bin_dir / "ffprobe"
    ffprobe_stub.write_text(
        f"""#!{sys.executable}
import json
import pathlib
import sys

argv = sys.argv[1:]
log_path = pathlib.Path({str(calls_log)!r})
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "ffprobe", "argv": argv}}) + "\\n")

target = pathlib.Path(argv[-1])
if target.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
    print(json.dumps({{
        "streams": [{{"codec_type": "audio", "codec_name": "pcm_s16le", "sample_rate": "48000", "channels": 1, "duration": "8.000000"}}],
        "format": {{"duration": "8.000000"}},
    }}))
    sys.exit(0)
dur_file = pathlib.Path(str(target) + ".dur")
if dur_file.is_file():
    dur = float(dur_file.read_text(encoding="utf-8"))
else:
    stitched_dur = target.parent / (target.stem + "_segments") / "stitched_raw.mp4.dur"
    dur = float(stitched_dur.read_text(encoding="utf-8")) if stitched_dur.is_file() else 8.0
payload = {{
    "streams": [
        {{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "duration": f"{{dur:.6f}}"}},
        {{"codec_type": "audio", "codec_name": "aac"}},
    ],
    "format": {{"duration": f"{{dur:.6f}}"}},
}}
print(json.dumps(payload))
""",
        encoding="utf-8",
    )
    ffprobe_stub.chmod(0o755)

    tiny_wav_hex = (
        REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "tiny_tone.wav"
    ).read_bytes().hex()

    ffmpeg_stub = bin_dir / "ffmpeg"
    ffmpeg_stub.write_text(
        f"""#!{sys.executable}
import json
import os
import pathlib
import re
import sys

argv = sys.argv[1:]
log_path = pathlib.Path({str(calls_log)!r})
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "ffmpeg", "argv": argv}}) + "\\n")

if "-filters" in argv:
    if os.environ.get("STUB_FFMPEG_NO_LIBASS") == "1":
        print("Filters:\\n .. overlay           VV->V      Overlay.\\n")
    else:
        print("Filters:\\n .. ass               V->V       ASS.\\n .. subtitles         V->V       Sub.\\n .. drawtext          V->V       Text.\\n")
    sys.exit(0)

if argv and argv[-1] == "-" and "-f" in argv and "null" in argv:
    joined = " ".join(argv)
    if "loudnorm=" in joined and "print_format=json" in joined:
        src_path = argv[argv.index("-i") + 1].removeprefix("file:") if "-i" in argv else ""
        is_normed = bool(src_path and pathlib.Path(src_path + ".normed").is_file())
        sys.stderr.write(json.dumps({{
            "input_i": "-14.00" if is_normed else "-20.50",
            "input_tp": "-1.00" if is_normed else "-4.20",
            "input_lra": "5.80",
            "input_thresh": "-30.80",
            "target_offset": "0.10",
        }}) + "\\n")
    elif "silencedetect=" in joined:
        sys.stderr.write("[silencedetect @ 0x1] silence_start: 1.800\\n[silencedetect @ 0x1] silence_end: 2.600\\n")
    sys.exit(0)

out = pathlib.Path(argv[-1])
out.parent.mkdir(parents=True, exist_ok=True)
if out.suffix.lower() == ".png":
    out.write_bytes(bytes.fromhex({VALID_16X9_2K_PNG_HEX!r}))
    sys.exit(0)
if out.suffix.lower() == ".wav":
    out.write_bytes(bytes.fromhex({tiny_wav_hex!r}))
    if "linear=true" in " ".join(argv):
        pathlib.Path(str(out) + ".normed").write_text("1", encoding="utf-8")
        sys.stderr.write("Normalization Type: Linear\\n")
    sys.exit(0)

out.write_bytes(bytes.fromhex({VALID_MP4_HEX!r}))

# Preserve .dur across remux/overlay passes when single MP4 input has .dur
in_mp4s = [pathlib.Path(argv[idx + 1]) for idx, tok in enumerate(argv[:-1]) if tok == "-i" and argv[idx + 1].endswith(".mp4")]
if len(in_mp4s) == 1:
    in_dur = pathlib.Path(str(in_mp4s[0]) + ".dur")
    if in_dur.is_file():
        pathlib.Path(str(out) + ".dur").write_text(in_dur.read_text(encoding="utf-8"), encoding="utf-8")

if "-filter_complex" in argv and len(in_mp4s) >= 2:
    fc = argv[argv.index("-filter_complex") + 1]
    xfades = re.findall(r"xfade=transition=fade:duration=([0-9.]+):", fc)
    if xfades and log_path.is_file():
        c_sec = float(xfades[0])
        vid_durs = []
        for entry_line in log_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(entry_line)
            if rec.get("bin") == "gemini-api" and rec.get("argv", [None])[0] == "video":
                a = rec["argv"]
                if "--body" in a:
                    body = json.loads(a[a.index("--body") + 1])
                    d = str(body.get("response_format", {{}}).get("duration", "8s")).rstrip("s")
                    vid_durs.append(float(d))
        if len(vid_durs) >= len(in_mp4s):
            seg_durs = vid_durs[-len(in_mp4s):]
            net = sum(seg_durs) - c_sec * (len(seg_durs) - 1)
            pathlib.Path(str(out) + ".dur").write_text(f"{{net:.3f}}", encoding="utf-8")

if "-f" in argv and "concat" in argv and "-i" in argv:
    concat_file = pathlib.Path(argv[argv.index("-i") + 1])
    seg_count = sum(1 for line in concat_file.read_text(encoding="utf-8").splitlines() if line.strip().startswith("file "))
    if seg_count > 0 and log_path.is_file():
        vid_durs = []
        for entry_line in log_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(entry_line)
            if rec.get("bin") == "gemini-api" and rec.get("argv", [None])[0] == "video":
                a = rec["argv"]
                if "--body" in a:
                    body = json.loads(a[a.index("--body") + 1])
                    d = str(body.get("response_format", {{}}).get("duration", "8s")).rstrip("s")
                    vid_durs.append(float(d))
        if len(vid_durs) >= seg_count:
            total_dur = sum(vid_durs[-seg_count:])
            pathlib.Path(str(out) + ".dur").write_text(f"{{total_dur:.3f}}", encoding="utf-8")
""",
        encoding="utf-8",
    )
    ffmpeg_stub.chmod(0o755)


class MediaCliContractFreshnessTests(unittest.TestCase):
    """T6: shared constants, redaction patterns, and CLI flags match across image-gen and video-gen."""

    def test_verifier_chain_and_deprecated_prefixes_match_byte_for_byte(self):
        self.assertEqual(video_gen.VERIFIER_MODEL_CHAIN, ("gemini-4-argon", "gemini-4-carbon"))
        self.assertEqual(audio_gen.VERIFIER_MODEL_CHAIN, ("gemini-4-argon", "gemini-4-carbon"))
        self.assertTrue(all("gemini-3." not in m for m in video_gen.VERIFIER_MODEL_CHAIN))
        self.assertEqual(image_gen.VERIFIER_MODEL_CHAIN[:2], video_gen.VERIFIER_MODEL_CHAIN)
        self.assertEqual(image_gen.DEPRECATED_MODEL_PREFIXES, video_gen.DEPRECATED_MODEL_PREFIXES)
        self.assertEqual(audio_gen.DEPRECATED_MODEL_PREFIXES, video_gen.DEPRECATED_MODEL_PREFIXES)
        self.assertEqual(image_gen.SECRET_PATTERNS, video_gen.SECRET_PATTERNS)
        self.assertIn("Credential key assignment", [lbl for lbl, _ in video_gen.SECRET_PATTERNS])
        self.assertIn("Credential key assignment", [lbl for lbl, _ in audio_engines.SECRET_PATTERNS])
        self.assertIn("gemini-3.1-flash-image", image_gen.DEPRECATED_MODEL_PREFIXES)
        self.assertIn("veo-3.1", video_gen.DEPRECATED_MODEL_PREFIXES)
        # Bare key= & JSON redaction parity across all three modules
        secret_sample = 'err key=MySuperSecretToken12345678 and key=char {"key": null, "api_key": "tok_secret_99"}'
        self.assertEqual(image_gen.redact_secrets(secret_sample), video_gen.redact_secrets(secret_sample))
        self.assertNotIn("MySuperSecretToken12345678", video_gen.redact_secrets(secret_sample))
        self.assertNotIn("MySuperSecretToken12345678", audio_gen.redact_secrets(secret_sample))
        self.assertNotIn("tok_secret_99", audio_gen.redact_secrets(secret_sample))
        self.assertIn("key=char", audio_gen.redact_secrets(secret_sample))
        num_json = json.dumps({"key": 12345678901234567890, "api_key": 42})
        self.assertEqual(json.loads(audio_gen.redact_secrets(num_json)), json.loads(num_json))

    def test_both_clis_enforce_override_reason_on_allow_unverified(self):
        for script in (IMAGE_GEN_SCRIPT, VIDEO_GEN_SCRIPT, AUDIO_GEN_SCRIPT):
            proc = subprocess.run(
                [sys.executable, str(script), "--prompt", "Draft test", "--allow-unverified"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, f"{script.name} allowed --allow-unverified without --override-reason")
            self.assertIn("--override-reason", proc.stderr)

    def test_image_gen_cli_exposes_all_binding_plan_section_1_1_flags(self):
        proc = subprocess.run(
            [sys.executable, str(IMAGE_GEN_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        required_flags = (
            "--prompt",
            "--mode",
            "--style",
            "--reference",
            "--references",
            "--ar",
            "--size",
            "--output",
            "--manifest",
            "--manifest-out",
            "--previous-interaction-id",
            "--model",
            "--verifier-model",
            "--max-attempts",
            "--raw-prompt",
            "--no-verify",
            "--allow-unverified",
            "--dry-run",
            "--doctor",
        )
        for flag in required_flags:
            self.assertIn(flag, proc.stdout, f"image_gen.py --help missing binding §1.1 flag {flag}")


class CrossSkillSubprocessIntegrationTests(unittest.TestCase):
    """T5 + T1: real subprocess integration between video_gen.py and image_gen.py."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="forge_media_e2e_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.calls_log = self.root / "calls.jsonl"
        _install_media_cli_stubs(self.bin_dir, self.calls_log)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.bin_dir}{os.pathsep}{self.env.get('PATH', '')}"

    def _read_calls(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in self.calls_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_video_gen_synthesize_keyframes_start_end_invokes_real_image_gen_twice(self):
        out_mp4 = self.root / "malti_clouds.mp4"
        proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--prompt",
                "Malti leaps across clouds",
                "--synthesize-keyframes",
                "start-end",
                "--duration",
                "8",
                "--ar",
                "16:9",
                "--resolution",
                "1080p",
                "--raw-prompt",
                "--output",
                str(out_mp4),
            ],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out_mp4.read_bytes(), bytes.fromhex(VALID_MP4_HEX))

        start_png = self.root / "malti_clouds_keyframes" / "start_frame.png"
        end_png = self.root / "malti_clouds_keyframes" / "end_frame.png"
        self.assertGreater(start_png.stat().st_size, 0)
        self.assertGreater(end_png.stat().st_size, 0)

        calls = self._read_calls()
        image_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "image"]
        video_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "video"]
        generate_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "generate"]

        self.assertEqual(len(image_calls), 2, f"expected 2 image_gen calls, got {image_calls}")
        # Second keyframe call must reference start_frame.png via -i
        self.assertIn("-i", image_calls[1])
        self.assertEqual(
            Path(image_calls[1][image_calls[1].index("-i") + 1]).resolve(),
            start_png.resolve(),
        )
        # Both keyframes + final video were audited by blinded rubric generate
        self.assertGreaterEqual(len(generate_calls), 3)

        self.assertEqual(len(video_calls), 1)
        vid_argv = video_calls[0]
        self.assertEqual(vid_argv[vid_argv.index("-m") + 1], "gemini-omni-1.2-flash")
        i_vals = [vid_argv[idx + 1] for idx, tok in enumerate(vid_argv) if tok == "-i"]
        self.assertEqual(
            [Path(p).name for p in i_vals],
            ["start_frame.png", "end_frame.png"],
            f"unexpected keyframe order passed to gemini-api video: {i_vals}",
        )

        prov = json.loads(Path(f"{out_mp4}.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["status"], "VERIFIED")
        self.assertEqual(prov["model_used"], "gemini-omni-1.2-flash")

    def test_image_gen_manifest_to_video_gen_storyboard_handoff_end_to_end(self):
        # Step 1: Run image_gen.py --manifest with relative --output from a distinct cwd
        work_a = self.root / "author_dir"
        work_a.mkdir()
        manifest_in = work_a / "timeline_in.json"
        manifest_in.write_text(
            json.dumps(
                {
                    "mode": "timeline",
                    "style": "ligne claire comic",
                    "aspect_ratio": "16:9",
                    "size": "2K",
                    "anchor_prompt": "Canonical character sheet for Malti in a blue scarf",
                    "frames": [
                        {"prompt": "Malti steps onto the launchpad", "caption": "Step 1", "duration_s": 5},
                        {"prompt": "Malti ignites the booster", "caption": "Step 2", "duration_s": 6},
                        {"prompt": "Malti orbits above clouds", "caption": "Step 3", "duration_s": 5},
                    ],
                }
            ),
            encoding="utf-8",
        )
        img_proc = subprocess.run(
            [
                sys.executable,
                str(IMAGE_GEN_SCRIPT),
                "--manifest",
                str(manifest_in),
                "--raw-prompt",
                "--output",
                "seq_out",
            ],
            cwd=str(work_a),
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(img_proc.returncode, 0, img_proc.stdout + img_proc.stderr)

        emitted_manifest = work_a / "seq_out" / "keyframes_manifest.json"
        manifest_json = json.loads(emitted_manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest_json["frames"]), 3)
        self.assertEqual(manifest_json["frames"][0]["path"], "frames/frame_01.png")

        # Step 2: Feed that exact manifest into video_gen.py --storyboard from a DIFFERENT cwd
        work_b = self.root / "video_dir"
        work_b.mkdir()
        storyboard_mp4 = work_b / "storyboard.mp4"
        vid_proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--storyboard",
                str(emitted_manifest),
                "--resolution",
                "1080p",
                "--raw-prompt",
                "--output",
                str(storyboard_mp4),
            ],
            cwd=str(work_b),
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(vid_proc.returncode, 0, vid_proc.stdout + vid_proc.stderr)
        self.assertEqual(storyboard_mp4.read_bytes(), bytes.fromhex(VALID_MP4_HEX))

        calls = self._read_calls()
        video_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "video"]
        ffmpeg_calls = [c["argv"] for c in calls if c["bin"] == "ffmpeg"]
        # 3 frames -> 2 transition segments -> 2 video generations + 1 ffmpeg concat
        self.assertEqual(len(video_calls), 2, f"expected 2 storyboard segments, got {video_calls}")
        self.assertEqual(len(ffmpeg_calls), 1, f"expected ffmpeg concat call, got {ffmpeg_calls}")
        self.assertIn("concat", ffmpeg_calls[0])

        prov = json.loads(Path(f"{storyboard_mp4}.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["status"], "VERIFIED")
        self.assertEqual(len(prov["segments"]), 2)

    def test_r2_image_gen_manifest_parent_out_with_external_anchor_to_video_gen_storyboard(self):
        ext_dir = self.root / "external_assets"
        ext_dir.mkdir()
        ext_anchor = ext_dir / "hero_anchor.png"
        ext_anchor.write_bytes(bytes.fromhex(VALID_16X9_2K_PNG_HEX))

        parent_dir = self.root / "bundle"
        parent_dir.mkdir()
        manifest_in = self.root / "in_seq.json"
        manifest_in.write_text(
            json.dumps(
                {
                    "mode": "timeline",
                    "aspect_ratio": "16:9",
                    "size": "2K",
                    "frames": [
                        {"prompt": "Frame one open", "duration_s": 5},
                        {"prompt": "Frame two close", "duration_s": 6},
                    ],
                }
            ),
            encoding="utf-8",
        )
        emitted_manifest = parent_dir / "keyframes_manifest.json"
        img_proc = subprocess.run(
            [
                sys.executable,
                str(IMAGE_GEN_SCRIPT),
                "--manifest",
                str(manifest_in),
                "--manifest-out",
                str(emitted_manifest),
                "-r",
                str(ext_anchor),
                "--raw-prompt",
                "--output",
                str(parent_dir / "seq_out"),
            ],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(img_proc.returncode, 0, img_proc.stdout + img_proc.stderr)
        manifest_json = json.loads(emitted_manifest.read_text(encoding="utf-8"))
        self.assertNotIn("..", manifest_json["anchor_image"])
        self.assertNotIn("..", manifest_json["frames"][0]["path"])

        storyboard_mp4 = self.root / "r2_story.mp4"
        vid_proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--storyboard",
                str(emitted_manifest),
                "--resolution",
                "1080p",
                "--raw-prompt",
                "--output",
                str(storyboard_mp4),
            ],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(vid_proc.returncode, 0, vid_proc.stdout + vid_proc.stderr)

    def test_pr2_45s_chained_timeline_with_audio_gen_stub_and_missing_libass_fallback(self):
        # Create real executable companion audio_gen.py stub in temp dir
        audio_gen_stub = self.root / "audio_gen_stub.py"
        wav_fixture = REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "tiny_tone.wav"
        audio_gen_stub.write_text(
            f"""#!{sys.executable}
import json, pathlib, sys
argv = sys.argv[1:]
with pathlib.Path({str(self.calls_log)!r}).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "audio_gen.py", "argv": argv}}) + "\\n")
out = pathlib.Path(argv[argv.index("--output") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(pathlib.Path({str(wav_fixture)!r}).read_bytes())
print(json.dumps({{"status": "VERIFIED", "output": str(out)}}))
""",
            encoding="utf-8",
        )
        audio_gen_stub.chmod(0o755)

        srt_fixture = REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "sample_captions.srt"
        out_45s = self.root / "longform_45s.mp4"
        env_no_libass = dict(self.env)
        env_no_libass["STUB_FFMPEG_NO_LIBASS"] = "1"

        proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--prompt",
                "Continuous walkthrough of distributed storage engine",
                "--scene-text",
                "COMMITTED QUORUM",
                "--duration",
                "45",
                "--continuity",
                "keyframe-chain",
                "--crossfade-sec",
                "0.5",
                "--audio-mode",
                "full-mix",
                "--narration-text",
                "Every write commits across three fault domains.",
                "--voice-name",
                "Kore",
                "--bgm-prompt",
                "Minimal ambient synth pulse",
                "--audio-gen-script",
                str(audio_gen_stub),
                "--srt",
                str(srt_fixture),
                "--caption-style",
                "pill",
                "--title-card",
                "Consensus Engine|Zero Data Loss",
                "--creative-stack",
                "off",
                "--raw-prompt",
                "--output",
                str(out_45s),
            ],
            capture_output=True,
            text=True,
            env=env_no_libass,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out_45s.read_bytes(), bytes.fromhex(VALID_MP4_HEX))

        rep = json.loads(Path(f"{out_45s}.report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["status"], "VERIFIED")
        self.assertEqual(
            rep["post_processing"]["caption_renderer"],
            "ffmpeg:mov_text_soft_sub_fallback(missing_libass)",
        )
        self.assertEqual(
            rep["post_processing"]["card_renderer"],
            "ffmpeg:png_card_overlay_fallback(missing_drawtext)",
        )
        self.assertEqual(
            rep["post_processing"]["audio_renderer"],
            "ffmpeg:standalone_2pass_loudnorm",
        )

        calls = self._read_calls()
        ag_calls = [c["argv"] for c in calls if c["bin"] == "audio_gen.py"]
        self.assertEqual(len(ag_calls), 2)
        ff_calls = [" ".join(c["argv"]) for c in calls if c["bin"] == "ffmpeg"]
        self.assertTrue(any("xfade=transition=fade:duration=0.500" in c for c in ff_calls))
        self.assertTrue(any("amix=inputs=2:duration=longest:normalize=0" in c for c in ff_calls))
        self.assertTrue(any("linear=true" in c and "-ar 48000" in c for c in ff_calls))
        self.assertFalse(any("sidechaincompress" in c for c in ff_calls))

    def test_pr2_creative_stack_vidkit_and_sound_delegation_end_to_end(self):
        cs_root = self.root / "fake_creative_stack"
        vk_scripts = cs_root / "skills" / "vidkit" / "scripts"
        sd_scripts = cs_root / "skills" / "sound" / "scripts"
        vk_scripts.mkdir(parents=True)
        sd_scripts.mkdir(parents=True)

        wav_fixture = REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "tiny_tone.wav"
        srt_fixture = REPO_ROOT / "skills" / "video-gen" / "fixtures" / "known_good" / "sample_captions.srt"

        for name in ("captions.py", "motion.py"):
            (vk_scripts / name).write_text(
                f"""#!{sys.executable}
import json, pathlib, sys
argv = sys.argv[1:]
with pathlib.Path({str(self.calls_log)!r}).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "{name}", "argv": argv}}) + "\\n")
out = pathlib.Path(argv[argv.index("-o") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(bytes.fromhex({VALID_MP4_HEX!r}))
pathlib.Path(str(out) + ".dur").write_text("8.000", encoding="utf-8")
""",
                encoding="utf-8",
            )

        (sd_scripts / "mix.py").write_text(
            f"""#!{sys.executable}
import json, pathlib, sys
argv = sys.argv[1:]
with pathlib.Path({str(self.calls_log)!r}).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"bin": "mix.py", "argv": argv}}) + "\\n")
out = pathlib.Path(argv[argv.index("-o") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(pathlib.Path({str(wav_fixture)!r}).read_bytes())
""",
            encoding="utf-8",
        )

        out_cs = self.root / "cs_delegated.mp4"
        proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--prompt",
                "Developer walkthrough clip",
                "--duration",
                "8",
                "--audio-mode",
                "full-mix",
                "--voice-track",
                str(wav_fixture),
                "--bgm-track",
                str(wav_fixture),
                "--srt",
                str(srt_fixture),
                "--caption-style",
                "karaoke",
                "--lower-third",
                "Grace Hopper|Rear Admiral@1.0-4.0",
                "--creative-stack",
                str(cs_root),
                "--raw-prompt",
                "--output",
                str(out_cs),
            ],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rep = json.loads(Path(f"{out_cs}.report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["post_processing"]["audio_renderer"], "creative-stack:sound/mix.py")
        self.assertEqual(rep["post_processing"]["card_renderer"], "creative-stack:vidkit/motion.py")
        self.assertEqual(
            rep["post_processing"]["caption_renderer"],
            "creative-stack:vidkit/captions.py:karaoke",
        )

    def test_pr3_video_gen_full_mix_invokes_real_audio_gen_for_narration_and_bgm(self):
        out_mp4 = self.root / "video_plus_real_audio_gen.mp4"
        stub_env = dict(self.env)
        stub_env["CREATIVE_STACK_FFMPEG"] = str(self.bin_dir / "ffmpeg")
        stub_env["CREATIVE_STACK_FFPROBE"] = str(self.bin_dir / "ffprobe")
        proc = subprocess.run(
            [
                sys.executable,
                str(VIDEO_GEN_SCRIPT),
                "--prompt",
                "Walkthrough of active-active cloud failover",
                "--duration",
                "8",
                "--audio-mode",
                "full-mix",
                "--narration-text",
                "Traffic shifts seamlessly to the secondary region.",
                "--voice-name",
                "Kore",
                "--bgm-prompt",
                "Warm minimal electronic pulse",
                "--creative-stack",
                "off",
                "--raw-prompt",
                "--output",
                str(out_mp4),
            ],
            capture_output=True,
            text=True,
            env=stub_env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out_mp4.read_bytes(), bytes.fromhex(VALID_MP4_HEX))

        rep = json.loads(Path(f"{out_mp4}.report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["status"], "VERIFIED")
        self.assertEqual(rep["post_processing"]["audio_renderer"], "ffmpeg:standalone_2pass_loudnorm")

        calls = self._read_calls()
        tts_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "tts"]
        music_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "music"]
        judge_calls = [c["argv"] for c in calls if c["bin"] == "gemini-api" and c["argv"][0] == "generate"]
        ff_calls = [" ".join(c["argv"]) for c in calls if c["bin"] == "ffmpeg"]

        self.assertEqual(len(tts_calls), 1, f"expected 1 real audio_gen TTS call, got {tts_calls}")
        self.assertEqual(len(music_calls), 1, f"expected 1 real audio_gen Lyria call, got {music_calls}")
        self.assertGreaterEqual(len(judge_calls), 3)
        self.assertTrue(any("amix=inputs=2:duration=longest:normalize=0" in c for c in ff_calls))
        self.assertTrue(any("linear=true" in c and "-ar 48000" in c for c in ff_calls))


if __name__ == "__main__":
    unittest.main()
