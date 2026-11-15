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

"""Comprehensive test suite for skills/video-gen/scripts/video_gen.py.

Covers Engineering Standard S1-S9, V1-V6, and T1-T6 without unittest.mock.
"""

from __future__ import annotations

import json
import math
import os
import re
import struct
import sys
import wave
import zlib
from pathlib import Path
from typing import Any, Sequence

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_GOOD = SKILL_DIR / "fixtures" / "known_good"
FIXTURES_BAD = SKILL_DIR / "fixtures" / "known_bad"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import video_gen  # noqa: E402
import video_post  # noqa: E402
import video_timeline  # noqa: E402


VALID_MP4_BYTES = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08mdat\x01\x02\x03\x04"
)


def _make_valid_1080p_png_bytes() -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", 1920, 1080, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return b"\x89PNG\r\n\x1a\n" + ihdr + iend


TINY_PNG_BYTES = _make_valid_1080p_png_bytes()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_generate_envelope(verdict_obj: dict[str, Any], resp_id: str = "gen_judge_1") -> str:
    return json.dumps(
        {
            "id": resp_id,
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(verdict_obj),
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 400, "output_tokens": 120},
        }
    )


def _passing_verdict_for_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "criteria_results": [
            {
                "id": item["id"],
                "passed": True,
                "observed_evidence": f"Verified on-screen alignment for {item['id']}: {item['category']}.",
                "fix_instruction": "",
            }
            for item in spec["acceptance_criteria"]
        ],
        "remediation_mode": "edit_turn",
        "edit_delta_prompt": "",
        "regenerated_prompt": "",
    }


class FakeCLIRunner:
    """Deterministic physical runner writing real files in tmp_path (zero mocks)."""

    def __init__(
        self,
        *,
        ffprobe_payload: dict[str, Any] | None = None,
        source_ffprobe_payload: dict[str, Any] | None = None,
        concat_ffprobe_payload: dict[str, Any] | None = None,
        judge_verdicts: list[dict[str, Any]] | None = None,
        video_errors: list[tuple[int, str]] | None = None,
        judge_errors_by_model: dict[str, tuple[int, str]] | None = None,
        expanded_prompt_text: str | None = None,
        ffmpeg_fail: bool = False,
        ffmpeg_filters_output: str | None = None,
        loudnorm_pass1_payload: dict[str, Any] | None = None,
        silencedetect_stderr: str | None = None,
        match_requested_duration: bool = False,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.ffprobe_payload = ffprobe_payload or _load_json(
            FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json"
        )
        self.source_ffprobe_payload = source_ffprobe_payload
        self.concat_ffprobe_payload = concat_ffprobe_payload
        self.judge_verdicts = list(judge_verdicts) if judge_verdicts else []
        self.video_errors = list(video_errors) if video_errors else []
        self.judge_errors_by_model = dict(judge_errors_by_model) if judge_errors_by_model else {}
        self.expanded_prompt_text = expanded_prompt_text
        self.ffmpeg_fail = ffmpeg_fail
        self.ffmpeg_filters_output = (
            ffmpeg_filters_output
            if ffmpeg_filters_output is not None
            else (
                "Filters:\n"
                " .. ass               V->V       Render ASS subtitles.\n"
                " .. subtitles         V->V       Render text subtitles.\n"
                " .. drawtext          V->V       Draw text on top of video.\n"
                " .. loudnorm          A->A       EBU R128 loudness normalization.\n"
                " .. xfade             VV->V      Cross fade one video with another.\n"
                " .. acrossfade        AA->A      Cross fade two input audio streams.\n"
            )
        )
        self.loudnorm_pass1_payload = loudnorm_pass1_payload or _load_json(
            FIXTURES_GOOD / "loudnorm_pass1_voice_mono.json"
        )
        self.silencedetect_stderr = (
            silencedetect_stderr
            if silencedetect_stderr is not None
            else (
                "[silencedetect @ 0x1] silence_start: 2.200\n"
                "[silencedetect @ 0x1] silence_end: 3.100 | silence_duration: 0.900\n"
            )
        )
        self.match_requested_duration = match_requested_duration
        self._video_attempt = 0
        self._upload_counter = 0
        self._ffmpeg_outputs: set[str] = set()
        self._candidate_durations: dict[str, float] = {}
        self.temp_inputs_seen_existing: list[tuple[str, bool]] = []

    def __call__(self, argv: Sequence[str]) -> video_gen.CommandResult:
        cmd = tuple(str(x) for x in argv)
        self.calls.append(cmd)
        binary = Path(cmd[0]).name

        if binary == "gemini-api" and len(cmd) >= 2 and cmd[1] == "--version":
            return video_gen.CommandResult(0, "gemini-api 0.4.2\n", "", cmd)

        if binary == "gemini-api" and len(cmd) >= 2 and cmd[1] == "whoami":
            return video_gen.CommandResult(
                0,
                json.dumps({"authenticated": True, "source": "keyring", "account": "studio-user"}),
                "",
                cmd,
            )

        if binary == "gemini-api" and len(cmd) >= 3 and cmd[1] == "files" and cmd[2] == "upload":
            self._upload_counter += 1
            src_path = Path(cmd[3])
            self.temp_inputs_seen_existing.append((str(src_path), src_path.exists()))
            return video_gen.CommandResult(0, f"files/uploaded_{self._upload_counter}\n", "", cmd)

        if binary == "gemini-api" and len(cmd) >= 2 and cmd[1] == "video":
            for idx, token in enumerate(cmd):
                if token == "-i" and idx + 1 < len(cmd):
                    val = cmd[idx + 1]
                    if not val.startswith("files/"):
                        p = Path(val)
                        self.temp_inputs_seen_existing.append((val, p.exists()))
            if self.video_errors:
                code, err = self.video_errors.pop(0)
                return video_gen.CommandResult(code, "", err, cmd)
            self._video_attempt += 1
            out_idx = cmd.index("--out") + 1
            out_path = Path(cmd[out_idx])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(VALID_MP4_BYTES)
            if self.match_requested_duration and "--body" in cmd:
                body_doc = json.loads(cmd[cmd.index("--body") + 1])
                req_d = str(body_doc.get("response_format", {}).get("duration", "8s")).rstrip("s")
                self._candidate_durations[str(out_path.resolve())] = float(req_d)
            payload = {
                "kind": "video",
                "path": str(out_path),
                "size_bytes": len(VALID_MP4_BYTES),
                "mime_type": "video/mp4",
                "response_id": f"v1_vid_{self._video_attempt}",
                "status": "completed",
            }
            return video_gen.CommandResult(0, json.dumps(payload), "", cmd)

        if binary == "gemini-api" and len(cmd) >= 2 and cmd[1] == "generate":
            model_idx = cmd.index("-m") + 1
            model_id = cmd[model_idx]
            prompt_arg = cmd[2]
            if "Expand this video prompt" in prompt_arg:
                expanded = self.expanded_prompt_text or prompt_arg
                return video_gen.CommandResult(
                    0,
                    _make_generate_envelope({"expanded_prompt": expanded}, "gen_expand_1"),
                    "",
                    cmd,
                )
            if model_id in self.judge_errors_by_model:
                code, err = self.judge_errors_by_model[model_id]
                return video_gen.CommandResult(code, "", err, cmd)
            if self.judge_verdicts:
                verdict = self.judge_verdicts.pop(0)
            else:
                ac_ids = re.findall(r"\b(AC-\d+)\b", prompt_arg)
                unique_ids = list(dict.fromkeys(ac_ids)) or ["AC-1"]
                verdict = {
                    "criteria_results": [
                        {
                            "id": ac_id,
                            "passed": True,
                            "observed_evidence": f"Confirmed {ac_id} in rendered video stream.",
                            "fix_instruction": "",
                        }
                        for ac_id in unique_ids
                    ],
                    "remediation_mode": "edit_turn",
                    "edit_delta_prompt": "",
                    "regenerated_prompt": "",
                }
            return video_gen.CommandResult(0, _make_generate_envelope(verdict), "", cmd)

        if binary == "ffprobe":
            target = cmd[-1]
            target_p = Path(target)
            resolved_target = str(target_p.resolve())
            if self.concat_ffprobe_payload is not None and (
                resolved_target in self._ffmpeg_outputs
                or (
                    len(self._ffmpeg_outputs) > 0
                    and "candidate" not in target_p.name
                    and not target_p.name.startswith("segment_")
                    and target_p.suffix.lower() == ".mp4"
                )
            ):
                return video_gen.CommandResult(0, json.dumps(self.concat_ffprobe_payload), "", cmd)
            if resolved_target in self._candidate_durations:
                dyn = json.loads(json.dumps(self.ffprobe_payload))
                d_str = f"{self._candidate_durations[resolved_target]:.6f}"
                for st in dyn.get("streams", []):
                    if st.get("codec_type") == "video":
                        st["duration"] = d_str
                dyn["format"]["duration"] = d_str
                return video_gen.CommandResult(0, json.dumps(dyn), "", cmd)
            if Path(target).suffix.lower() in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
                audio_probe = {
                    "streams": [
                        {
                            "codec_type": "audio",
                            "codec_name": "pcm_s16le",
                            "sample_rate": "48000",
                            "channels": 1,
                            "duration": "8.000000",
                        }
                    ],
                    "format": {"duration": "8.000000"},
                }
                return video_gen.CommandResult(0, json.dumps(audio_probe), "", cmd)
            if self.source_ffprobe_payload is not None and "candidate" not in Path(target).name:
                return video_gen.CommandResult(0, json.dumps(self.source_ffprobe_payload), "", cmd)
            return video_gen.CommandResult(0, json.dumps(self.ffprobe_payload), "", cmd)

        if binary == "ffmpeg":
            if "-filters" in cmd:
                return video_gen.CommandResult(0, self.ffmpeg_filters_output, "", cmd)
            if self.ffmpeg_fail:
                return video_gen.CommandResult(1, "", "ffmpeg failed to decode stream", cmd)
            if cmd[-1] == "-" and "-f" in cmd and "null" in cmd:
                joined = " ".join(cmd)
                if "loudnorm=" in joined and "print_format=json" in joined:
                    stderr_txt = "[Parsed_loudnorm_0 @ 0x100]\n" + json.dumps(self.loudnorm_pass1_payload)
                    return video_gen.CommandResult(0, "", stderr_txt, cmd)
                if "silencedetect=" in joined:
                    return video_gen.CommandResult(0, "", self.silencedetect_stderr, cmd)
                return video_gen.CommandResult(0, "", "", cmd)
            dst = Path(cmd[-1])
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.suffix.lower() == ".png":
                dst.write_bytes(TINY_PNG_BYTES)
            elif dst.suffix.lower() == ".wav":
                dst.write_bytes((FIXTURES_GOOD / "tiny_tone.wav").read_bytes())
            else:
                dst.write_bytes(VALID_MP4_BYTES)
                self._ffmpeg_outputs.add(str(dst.resolve()))
            return video_gen.CommandResult(0, "", "", cmd)

        if cmd[0] == sys.executable and len(cmd) >= 2:
            script_name = Path(cmd[1]).name
            if script_name == "image_gen.py":
                out_idx = cmd.index("--output") + 1
                frame_out = Path(cmd[out_idx])
                frame_out.parent.mkdir(parents=True, exist_ok=True)
                frame_out.write_bytes(TINY_PNG_BYTES)
                return video_gen.CommandResult(0, json.dumps({"output": str(frame_out)}), "", cmd)
            if script_name == "audio_gen.py":
                out_idx = cmd.index("--output") + 1
                aud_out = Path(cmd[out_idx])
                aud_out.parent.mkdir(parents=True, exist_ok=True)
                aud_out.write_bytes((FIXTURES_GOOD / "tiny_tone.wav").read_bytes())
                return video_gen.CommandResult(0, json.dumps({"status": "VERIFIED", "output": str(aud_out)}), "", cmd)
            if script_name in ("captions.py", "motion.py"):
                out_idx = cmd.index("-o") + 1
                vid_out = Path(cmd[out_idx])
                vid_out.parent.mkdir(parents=True, exist_ok=True)
                vid_out.write_bytes(VALID_MP4_BYTES)
                self._ffmpeg_outputs.add(str(vid_out.resolve()))
                return video_gen.CommandResult(0, f"✓ {vid_out}\n", "", cmd)
            if script_name == "mix.py":
                out_idx = cmd.index("-o") + 1
                mix_out = Path(cmd[out_idx])
                mix_out.parent.mkdir(parents=True, exist_ok=True)
                mix_out.write_bytes((FIXTURES_GOOD / "tiny_tone.wav").read_bytes())
                return video_gen.CommandResult(0, f"✓ {mix_out}\n", "", cmd)

        return video_gen.CommandResult(127, "", f"unexpected binary: {binary}", cmd)


def _all_tools_present(name: str) -> str | None:
    if name in {"gemini-api", "ffmpeg", "ffprobe"}:
        return f"/usr/local/bin/{name}"
    return None


# ---------------------------------------------------------------------------
# T6 & S6: Contract Parity & --help Flag Accuracy
# ---------------------------------------------------------------------------


def test_t6_shared_model_and_deprecation_constants_exact_parity() -> None:
    assert video_gen.VERIFIER_MODEL_CHAIN == (
        "gemini-4-argon",
        "gemini-4-carbon",
    )
    assert all("gemini-3." not in m for m in video_gen.VERIFIER_MODEL_CHAIN)
    assert video_gen.DEPRECATED_MODEL_PREFIXES == (
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
    assert video_gen.PRIMARY_VIDEO_MODEL == "gemini-omni-1.2-flash"


def test_s6_every_flag_documented_in_skill_md_exists_in_argparse() -> None:
    parser = video_gen.build_parser()
    known_flags: set[str] = set()
    for action in parser._actions:
        for opt in action.option_strings:
            known_flags.add(opt)

    skill_md_path = SKILL_DIR / "SKILL.md"
    assert skill_md_path.is_file()
    skill_text = skill_md_path.read_text(encoding="utf-8")
    for line in skill_text.splitlines():
        if "gemini-api files upload" in line:
            continue
        for match in re.finditer(r"(?<![A-Za-z0-9-])(--[a-z][a-z0-9-]*)", line):
            flag = match.group(1)
            assert flag in known_flags, f"SKILL.md documents unknown video_gen.py flag: {flag}"

    required_core_flags = {
        "--prompt",
        "--spec-file",
        "--storyboard",
        "--first-frame",
        "--last-frame",
        "--synthesize-keyframes",
        "--image-ref",
        "--video-ref",
        "--video",
        "--extend",
        "--strip-audio",
        "--prep-clip",
        "--ar",
        "--resolution",
        "--duration",
        "--single-shot",
        "--previous-interaction-id",
        "--max-attempts",
        "--model",
        "--verifier-model",
        "--raw-prompt",
        "--no-verify",
        "--allow-unverified",
        "--allow-legacy-video-fallback",
        "--require-ffprobe",
        "--dry-run",
        "--doctor",
        "--output",
    }
    missing = required_core_flags - known_flags
    assert missing == set()


# ---------------------------------------------------------------------------
# T1: Differentiation Across Modes, Spec Compilation & CLI Vectors
# ---------------------------------------------------------------------------


def test_t1_opposite_video_modes_produce_distinct_specs_and_cli_vectors(tmp_path: Path) -> None:
    first_png = tmp_path / "start.png"
    last_png = tmp_path / "end.png"
    clip_mp4 = tmp_path / "source.mp4"
    ref_png = tmp_path / "hero_char.png"
    for p, data in ((first_png, TINY_PNG_BYTES), (last_png, TINY_PNG_BYTES), (ref_png, TINY_PNG_BYTES)):
        p.write_bytes(data)
    clip_mp4.write_bytes(VALID_MP4_BYTES)

    cfg_single = video_gen.parse_job_config(
        [
            "--prompt",
            '[0-4s] Tracking shot past neon sign "OPEN 24H", no rain.',
            "--single-shot",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "8",
            "--raw-prompt",
            "--output",
            str(tmp_path / "single.mp4"),
        ]
    )
    cfg_transition = video_gen.parse_job_config(
        [
            "--prompt",
            "Morph clay sculpture from seed into blooming lotus.",
            "--first-frame",
            str(first_png),
            "--last-frame",
            str(last_png),
            "--ar",
            "9:16",
            "--resolution",
            "720p",
            "--duration",
            "6",
            "--silent",
            "--raw-prompt",
            "--output",
            str(tmp_path / "transition.mp4"),
        ]
    )
    cfg_extend = video_gen.parse_job_config(
        [
            "--prompt",
            "The explorer enters the cavern holding a lantern.",
            "--extend",
            str(clip_mp4),
            "--image-ref",
            f"char:{ref_png}",
            "--ar",
            "16:9",
            "--resolution",
            "720p",
            "--duration",
            "6",
            "--raw-prompt",
            "--output",
            str(tmp_path / "extended.mp4"),
        ]
    )

    spec_single = video_gen.compile_visual_spec(cfg_single)
    spec_transition = video_gen.compile_visual_spec(cfg_transition)
    spec_extend = video_gen.compile_visual_spec(cfg_extend)

    assert spec_single["mode"] != spec_transition["mode"]
    assert spec_transition["mode"] != spec_extend["mode"]
    assert spec_single["compiled_prompt"] != spec_transition["compiled_prompt"]
    assert spec_transition["compiled_prompt"] != spec_extend["compiled_prompt"]
    assert spec_single["acceptance_criteria"] != spec_transition["acceptance_criteria"]
    assert spec_transition["acceptance_criteria"] != spec_extend["acceptance_criteria"]

    cmd_single, body_single = video_gen.build_video_cli_command(
        config=cfg_single,
        prompt_text=spec_single["compiled_prompt"],
        ordered_inputs=[],
        candidate_out=tmp_path / "c1.mp4",
        model_id=video_gen.PRIMARY_VIDEO_MODEL,
        previous_interaction_id=None,
    )
    cmd_trans, body_trans = video_gen.build_video_cli_command(
        config=cfg_transition,
        prompt_text=spec_transition["compiled_prompt"],
        ordered_inputs=[str(first_png), str(last_png)],
        candidate_out=tmp_path / "c2.mp4",
        model_id=video_gen.PRIMARY_VIDEO_MODEL,
        previous_interaction_id=None,
    )
    cmd_ext, body_ext = video_gen.build_video_cli_command(
        config=cfg_extend,
        prompt_text=spec_extend["compiled_prompt"],
        ordered_inputs=[str(ref_png), str(clip_mp4)],
        candidate_out=tmp_path / "c3.mp4",
        model_id=video_gen.PRIMARY_VIDEO_MODEL,
        previous_interaction_id=None,
    )

    assert cmd_single != cmd_trans
    assert cmd_trans != cmd_ext
    assert body_single["response_format"]["duration"] == "8s"
    assert body_trans["response_format"]["duration"] == "6s"
    assert "generation_config" not in body_ext  # default prompt-based extend omits task!
    assert spec_extend["compiled_prompt"].startswith("Extend this video.")


def test_t1_each_individual_axis_moves_compiled_spec(tmp_path: Path) -> None:
    base_args = [
        "--prompt",
        "Ocean waves crashing against basalt cliffs.",
        "--ar",
        "16:9",
        "--resolution",
        "720p",
        "--duration",
        "5",
        "--raw-prompt",
        "--output",
        str(tmp_path / "out.mp4"),
    ]
    base_spec = video_gen.compile_visual_spec(video_gen.parse_job_config(base_args))

    flipped_single_shot = video_gen.compile_visual_spec(
        video_gen.parse_job_config(base_args + ["--single-shot"])
    )
    flipped_silent = video_gen.compile_visual_spec(
        video_gen.parse_job_config(base_args + ["--silent"])
    )
    flipped_style = video_gen.compile_visual_spec(
        video_gen.parse_job_config(base_args + ["--style", "16mm Kodachrome grain"])
    )

    assert flipped_single_shot["implicit_constraints"] != base_spec["implicit_constraints"]
    assert "In a single continuous unbroken shot, no scene cuts" in flipped_single_shot["compiled_prompt"]
    assert flipped_silent["explicit_constraints"]["audio_mode"] == "silent"
    assert flipped_silent["implicit_constraints"] != base_spec["implicit_constraints"]
    assert flipped_style["explicit_constraints"]["style"] == "16mm Kodachrome grain"
    assert flipped_style["acceptance_criteria"] != base_spec["acceptance_criteria"]


# ---------------------------------------------------------------------------
# T3: Natural-Language Role Bindings, Input Ordering & Derived Literals
# ---------------------------------------------------------------------------


def test_t3_natural_language_asset_bindings_and_input_ordering_never_emit_xml_tags(
    tmp_path: Path,
) -> None:
    start_f = tmp_path / "f1.png"
    end_f = tmp_path / "f2.png"
    char_r = tmp_path / "char.png"
    style_r = tmp_path / "style.png"
    for p in (start_f, end_f, char_r, style_r):
        p.write_bytes(TINY_PNG_BYTES)

    cfg = video_gen.parse_job_config(
        [
            "--prompt",
            '[0-3s] Messenger sprints across courtyard holding banner "DAWN EXPRESS" without motion blur.',
            "--first-frame",
            str(start_f),
            "--last-frame",
            str(end_f),
            "--image-ref",
            f"char:{char_r}",
            "--image-ref",
            f"style:{style_r}",
            "--duration",
            "6",
            "--raw-prompt",
            "--output",
            str(tmp_path / "courtyard.mp4"),
        ]
    )
    spec = video_gen.compile_visual_spec(cfg)
    compiled = spec["compiled_prompt"]

    # Zero legacy XML tags
    for forbidden in ("<FIRST_FRAME>", "<LAST_FRAME>", "<IMAGE_REF", "</FIRST_FRAME>"):
        assert forbidden not in compiled

    assert "Use the first image as the starting frame and the second image as the final frame." in compiled
    assert "image 3" in compiled.lower() and "character" in compiled.lower()
    assert "image 4" in compiled.lower() and "style" in compiled.lower()
    assert spec["explicit_constraints"]["quoted_literals"] == ["DAWN EXPRESS"]
    assert spec["explicit_constraints"]["timecode_beats"][0]["range"] == "[0-3s]"
    assert any("motion blur" in neg.lower() for neg in spec["explicit_constraints"]["negative_constraints"])

    ordered_paths = video_gen.collect_ordered_input_paths(cfg)
    assert ordered_paths == [start_f.resolve(), end_f.resolve(), char_r.resolve(), style_r.resolve()]


def test_t3_seamless_loop_identical_first_and_last_frame_passes_asset_twice(
    tmp_path: Path,
) -> None:
    loop_png = tmp_path / "loop_anchor.png"
    loop_png.write_bytes(TINY_PNG_BYTES)

    cfg = video_gen.parse_job_config(
        [
            "--prompt",
            "Campfire embers swirling gently in the night breeze.",
            "--first-frame",
            str(loop_png),
            "--last-frame",
            str(loop_png),
            "--duration",
            "6",
            "--raw-prompt",
            "--output",
            str(tmp_path / "loop.mp4"),
        ]
    )
    spec = video_gen.compile_visual_spec(cfg)
    assert spec["mode"] == "seamless-loop"
    assert "Use this image as both the starting frame and the final frame." in spec["compiled_prompt"]
    ordered = video_gen.collect_ordered_input_paths(cfg)
    assert ordered == [loop_png.resolve(), loop_png.resolve()]


def test_t3_task_extend_explicit_flag_omits_aspect_ratio_and_sets_video_config(
    tmp_path: Path,
) -> None:
    src_mp4 = tmp_path / "clip.mp4"
    src_mp4.write_bytes(VALID_MP4_BYTES)
    cfg = video_gen.parse_job_config(
        [
            "--prompt",
            "Continue tracking forward.",
            "--extend",
            str(src_mp4),
            "--task",
            "extend",
            "--duration",
            "5",
            "--raw-prompt",
            "--output",
            str(tmp_path / "out.mp4"),
        ]
    )
    cmd, body = video_gen.build_video_cli_command(
        config=cfg,
        prompt_text="Extend this video. Continue tracking forward.",
        ordered_inputs=[str(src_mp4)],
        candidate_out=tmp_path / "cand.mp4",
        model_id=video_gen.PRIMARY_VIDEO_MODEL,
        previous_interaction_id=None,
    )
    assert "--aspect-ratio" not in cmd
    assert body["generation_config"]["video_config"]["task"] == "extend"
    assert body["response_format"]["duration"] == "5s"


def test_t3_expanded_prompt_validator_catches_dropped_quoted_literals() -> None:
    raw = 'A robot barista holds a chalkboard sign reading "ESPRESSO 2.0" and waves.'
    good_expanded = (
        'Medium tracking shot in warm morning café light: a brushed-steel robot barista '
        'holds a chalkboard sign reading "ESPRESSO 2.0" and waves cheerfully.'
    )
    bad_expanded = (
        "Medium tracking shot in warm morning café light: a brushed-steel robot barista "
        "holds a chalkboard sign with coffee specials and waves cheerfully."
    )
    assert video_gen.validate_expanded_prompt(raw, good_expanded) == []
    errors = video_gen.validate_expanded_prompt(raw, bad_expanded)
    assert len(errors) == 1
    assert "ESPRESSO 2.0" in errors[0]


# ---------------------------------------------------------------------------
# V1, V2 & T4: Known-Good & Known-Bad Mechanical + Rubric Fixtures
# ---------------------------------------------------------------------------


def test_v2_known_good_ffprobe_and_rubric_fixtures_pass() -> None:
    good_1080p = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    res_1080p = video_gen.verify_ffprobe_payload(
        good_1080p,
        expected_ar="16:9",
        expected_resolution="1080p",
        expected_duration_s=10,
        expected_audio="required",
    )
    assert res_1080p["passed"] is True
    assert res_1080p["failures"] == []
    assert res_1080p["width"] == 1920
    assert res_1080p["height"] == 1080

    good_silent = _load_json(FIXTURES_GOOD / "ffprobe_720p_9x16_6s_silent.json")
    res_silent = video_gen.verify_ffprobe_payload(
        good_silent,
        expected_ar="9:16",
        expected_resolution="720p",
        expected_duration_s=6,
        expected_audio="silent",
    )
    assert res_silent["passed"] is True
    assert res_silent["audio_streams"] == 0

    spec = _load_json(FIXTURES_GOOD / "spec_single_shot_10s.json")
    good_rubric = _load_json(FIXTURES_GOOD / "rubric_pass_single_shot.json")
    rubric_res = video_gen.validate_rubric_verdict(good_rubric, spec)
    assert rubric_res["all_passed"] is True
    assert rubric_res["failed_ids"] == []
    assert rubric_res["pass_ratio"] == 1.0


@pytest.mark.parametrize(
    ("fixture_name", "ar", "res", "dur", "audio", "expected_code"),
    [
        ("ffprobe_missing_video_stream.json", "16:9", "1080p", 10, "any", "missing_video_stream"),
        ("ffprobe_wrong_duration_4s_vs_12s.json", "16:9", "1080p", 12, "any", "wrong_duration"),
        ("ffprobe_wrong_aspect_9x16_vs_16x9.json", "16:9", "1080p", 10, "any", "wrong_aspect_ratio"),
        ("ffprobe_residual_audio_when_silent.json", "16:9", "720p", 6, "silent", "residual_audio_stream"),
        ("ffprobe_wrong_resolution_360p_vs_1080p.json", "16:9", "1080p", 10, "any", "wrong_resolution"),
    ],
)
def test_v1_known_bad_ffprobe_fixtures_rejected_with_specific_code(
    fixture_name: str,
    ar: str,
    res: str,
    dur: int,
    audio: str,
    expected_code: str,
) -> None:
    payload = _load_json(FIXTURES_BAD / fixture_name)
    verdict = video_gen.verify_ffprobe_payload(
        payload,
        expected_ar=ar,
        expected_resolution=res,
        expected_duration_s=dur,
        expected_audio=audio,
    )
    assert verdict["passed"] is False
    assert any(expected_code in f for f in verdict["failures"])


def test_v1_known_bad_rubric_fixtures_rejected_and_provenance_enforced() -> None:
    spec = _load_json(FIXTURES_GOOD / "spec_single_shot_10s.json")

    # 1. Partial fail (3/4 = 75% pass -> fails overall, selects edit_turn)
    partial = _load_json(FIXTURES_BAD / "rubric_partial_fail.json")
    res_partial = video_gen.validate_rubric_verdict(partial, spec)
    assert res_partial["all_passed"] is False
    assert res_partial["failed_ids"] == ["AC-4"]
    assert res_partial["pass_ratio"] == 0.75
    mode_p, prompt_p = video_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation=res_partial,
        previous_response_id="v1_prev_123",
        has_video_refs=False,
        spec=spec,
    )
    assert mode_p == "edit_turn"
    assert prompt_p.startswith("Keep everything else the same.")
    assert "CHRONOS LAB" in prompt_p

    # 2. Major fail (1/4 = 25% pass -> fails overall, selects regenerate)
    major = _load_json(FIXTURES_BAD / "rubric_major_fail_regenerate.json")
    res_major = video_gen.validate_rubric_verdict(major, spec)
    assert res_major["all_passed"] is False
    assert res_major["pass_ratio"] == 0.25
    mode_m, prompt_m = video_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation=res_major,
        previous_response_id="v1_prev_123",
        has_video_refs=False,
        spec=spec,
    )
    assert mode_m == "regenerate"
    assert "CHRONOS LAB" in prompt_m

    # 3. Self-contradictory model summary (claims overall_passed=True while AC-2 passed=False)
    contradictory = _load_json(FIXTURES_BAD / "rubric_self_contradictory.json")
    res_contra = video_gen.validate_rubric_verdict(contradictory, spec)
    assert res_contra["all_passed"] is False
    assert res_contra["failed_ids"] == ["AC-2"]
    assert "self_contradictory_model_summary" in res_contra["validation_errors"]

    # 4. Missing AC-3 in criteria_results -> fails closed!
    missing_ac = _load_json(FIXTURES_BAD / "rubric_missing_ac_id.json")
    res_missing = video_gen.validate_rubric_verdict(missing_ac, spec)
    assert res_missing["all_passed"] is False
    assert any("AC-3" in err for err in res_missing["validation_errors"])


# ---------------------------------------------------------------------------
# T4: Pre-Upload Omni Constraint & Deprecated Model Rejections (Exit 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_model",
    [
        "veo-3.1-generate-preview",
        "veo-2.0-generate-001",
        "gemini-omni-flash-preview",
        "gemini-3.1-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-3.1-pro-high",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "imagen-3.0-generate-002",
        "flash_medium",
    ],
)
def test_t4_deprecated_models_rejected_with_exit_2(
    bad_model: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeCLIRunner()
    rc_gen = video_gen.main(
        ["--prompt", "A calm mountain lake.", "--model", bad_model, "--output", str(tmp_path / "x.mp4")],
        runner=runner,
        which_fn=_all_tools_present,
    )
    err_gen = capsys.readouterr().err
    assert rc_gen == 2
    assert bad_model in err_gen
    assert runner.calls == []

    rc_ver = video_gen.main(
        [
            "--prompt",
            "A calm mountain lake.",
            "--verifier-model",
            bad_model,
            "--output",
            str(tmp_path / "x.mp4"),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    assert rc_ver == 2
    assert runner.calls == []


def test_t4_omni_invalid_combinations_all_exit_2_before_upload(tmp_path: Path) -> None:
    f1 = tmp_path / "f1.png"
    f2 = tmp_path / "f2.png"
    src_vid = tmp_path / "src.mp4"
    vref = tmp_path / "vref.mp4"
    for p in (f1, f2):
        p.write_bytes(TINY_PNG_BYTES)
    for p in (src_vid, vref):
        p.write_bytes(VALID_MP4_BYTES)

    seven_refs: list[str] = []
    for idx in range(7):
        rp = tmp_path / f"ref_{idx}.png"
        rp.write_bytes(TINY_PNG_BYTES)
        seven_refs.extend(["--image-ref", str(rp)])

    four_vrefs = []
    for idx in range(4):
        vp = tmp_path / f"vref_{idx}.mp4"
        vp.write_bytes(VALID_MP4_BYTES)
        four_vrefs.extend(["--video-ref", str(vp)])

    two_vrefs = four_vrefs[:4]  # 2 --video-ref pairs

    invalid_cases = [
        # --last-frame without --first-frame
        ["--prompt", "Test", "--last-frame", str(f2)],
        # two-frame transition > 10s
        ["--prompt", "Test", "--first-frame", str(f1), "--last-frame", str(f2), "--duration", "12"],
        # --extend > 10s per turn
        ["--prompt", "Test", "--extend", str(src_vid), "--duration", "11"],
        # duration < 3s or single-clip --video edit > 15s or --allow-unverified without --override-reason
        ["--prompt", "Test", "--duration", "2"],
        ["--prompt", "Test", "--video", str(src_vid), "--duration", "16"],
        ["--prompt", "Test", "--allow-unverified"],
        ["--prompt", "Test", "--allow-unverified", "--override-reason", "   "],
        # > 6 --image-ref
        ["--prompt", "Test", *seven_refs],
        # --video-ref combined with --video, --extend, or --previous-interaction-id
        ["--prompt", "Test", "--video", str(src_vid), "--video-ref", str(vref)],
        ["--prompt", "Test", "--extend", str(src_vid), "--video-ref", str(vref)],
        ["--prompt", "Test", "--previous-interaction-id", "v1_abc", "--video-ref", str(vref)],
        # > 3 --video-ref on 3-10s
        ["--prompt", "Test", "--duration", "8", *four_vrefs],
        # > 1 --video-ref on 11-15s
        ["--prompt", "Test", "--duration", "12", *two_vrefs],
        # --strip-audio without --video or --extend
        ["--prompt", "Test", "--strip-audio"],
        # --task extend combined with --image-ref
        ["--prompt", "Test", "--extend", str(src_vid), "--task", "extend", "--image-ref", str(f1)],
        # deprecated <FIRST_FRAME> tag in prompt
        ["--prompt", "<FIRST_FRAME> walk forward", "--first-frame", str(f1)],
    ]

    runner = FakeCLIRunner()
    for argv in invalid_cases:
        rc = video_gen.main(
            [*argv, "--output", str(tmp_path / "never.mp4")],
            runner=runner,
            which_fn=_all_tools_present,
        )
        assert rc == 2, f"Expected exit 2 for invalid argv: {argv}"
    assert runner.calls == []


def test_t4_extend_cumulative_duration_over_30s_exits_2(tmp_path: Path) -> None:
    src_vid = tmp_path / "already_25s.mp4"
    src_vid.write_bytes(VALID_MP4_BYTES)
    source_probe = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    source_probe["streams"][0]["duration"] = "25.000000"
    source_probe["format"]["duration"] = "25.000000"
    # Note: source clip > 15s (or cumulative > 30s) must exit 2 before generation!
    runner = FakeCLIRunner(source_ffprobe_payload=source_probe)
    rc = video_gen.main(
        [
            "--prompt",
            "Keep walking along the pier.",
            "--extend",
            str(src_vid),
            "--duration",
            "8",
            "--raw-prompt",
            "--output",
            str(tmp_path / "out.mp4"),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    assert rc == 2
    assert not any(c[:2] == ("gemini-api", "video") for c in runner.calls)


# ---------------------------------------------------------------------------
# End-to-End Closed-Loop Retries, Frozen Spec, Hard Exit 1 & Asset Caching
# ---------------------------------------------------------------------------


def test_e2e_dual_mode_edit_turn_retry_preserves_frozen_spec_and_passes(tmp_path: Path) -> None:
    start_png = tmp_path / "start.png"
    start_png.write_bytes(TINY_PNG_BYTES)
    out_mp4 = tmp_path / "observatory.mp4"

    # Attempt 1 fails only quoted literal AC (3/4 = 75% >= 70% -> edit_turn); Attempt 2 passes all!
    cfg_preview = video_gen.parse_job_config(
        [
            "--prompt",
            'Owl on desk beside plaque "CHRONOS LAB".',
            "--single-shot",
            "--first-frame",
            str(start_png),
            "--duration",
            "10",
            "--resolution",
            "1080p",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ]
    )
    expected_spec = video_gen.compile_visual_spec(cfg_preview)
    ac_ids = [item["id"] for item in expected_spec["acceptance_criteria"]]
    assert len(ac_ids) == 4

    verdict_attempt_1 = {
        "criteria_results": [
            {
                "id": ac_id,
                "passed": idx < 3,
                "observed_evidence": "Matches spec." if idx < 3 else "Plaque text garbled.",
                "fix_instruction": "" if idx < 3 else 'Fix plaque text to read "CHRONOS LAB".',
            }
            for idx, ac_id in enumerate(ac_ids)
        ],
        "remediation_mode": "edit_turn",
        "edit_delta_prompt": 'Keep everything else the same. Fix plaque text to read "CHRONOS LAB".',
        "regenerated_prompt": "",
    }
    verdict_attempt_2 = _passing_verdict_for_spec(expected_spec)

    runner = FakeCLIRunner(judge_verdicts=[verdict_attempt_1, verdict_attempt_2])
    rc = video_gen.main(
        [
            "--prompt",
            'Owl on desk beside plaque "CHRONOS LAB".',
            "--single-shot",
            "--first-frame",
            str(start_png),
            "--duration",
            "10",
            "--resolution",
            "1080p",
            "--max-attempts",
            "3",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
        sleep_fn=lambda _: None,
    )
    assert rc == 0
    assert out_mp4.read_bytes() == VALID_MP4_BYTES

    video_calls = [c for c in runner.calls if c[:2] == ("gemini-api", "video")]
    assert len(video_calls) == 2
    assert "--previous-interaction-id" not in video_calls[0]
    assert "--previous-interaction-id" in video_calls[1]
    prev_idx = video_calls[1].index("--previous-interaction-id") + 1
    assert video_calls[1][prev_idx] == "v1_vid_1"
    assert video_calls[1][2].startswith("Keep everything else the same.")

    # Start frame was reused on Attempt 2 -> uploaded once via gemini-api files upload!
    upload_calls = [c for c in runner.calls if c[:3] == ("gemini-api", "files", "upload")]
    assert len(upload_calls) == 1

    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert prov["status"] == "VERIFIED"
    assert prov["attempts_used"] == 2
    assert prov["spec_digest"] == expected_spec["spec_digest"]
    assert prov["unchecked_surfaces"] == []


def test_t4_retry_exhaustion_writes_rejected_and_report_and_exits_1_without_output(
    tmp_path: Path,
) -> None:
    out_mp4 = tmp_path / "strict_target.mp4"
    out_mp4.write_bytes(b"stale_prior_file")

    bad_probe = _load_json(FIXTURES_BAD / "ffprobe_wrong_aspect_9x16_vs_16x9.json")
    runner = FakeCLIRunner(ffprobe_payload=bad_probe)

    rc = video_gen.main(
        [
            "--prompt",
            "Aerial drone sweep over alpine ridge.",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "10",
            "--max-attempts",
            "2",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
        sleep_fn=lambda _: None,
    )
    assert rc == 1
    assert out_mp4.exists() is False  # stale target removed; never left with unverified media!
    rejected_mp4 = tmp_path / "strict_target.rejected.mp4"
    report_json = Path(f"{out_mp4}.report.json")
    assert rejected_mp4.read_bytes() == VALID_MP4_BYTES
    report = _load_json(report_json)
    assert report["status"] == "FAILED_VERIFICATION"
    assert len(report["attempts"]) == 2
    assert "wrong_aspect_ratio" in report["attempts"][-1]["mechanical"]["failures"][0]


def test_allow_unverified_override_writes_output_with_warning_and_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_mp4 = tmp_path / "override.mp4"
    bad_probe = _load_json(FIXTURES_BAD / "ffprobe_wrong_aspect_9x16_vs_16x9.json")
    runner = FakeCLIRunner(ffprobe_payload=bad_probe)

    rc = video_gen.main(
        [
            "--prompt",
            "Quick rough draft motion test.",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "10",
            "--max-attempts",
            "1",
            "--allow-unverified",
            "--override-reason",
            "Rough blocking preview requested by user",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    err = capsys.readouterr().err
    assert rc == 0
    assert "UNVERIFIED" in err.upper()
    assert out_mp4.read_bytes() == VALID_MP4_BYTES
    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert prov["status"] == "UNVERIFIED_OVERRIDE"
    assert prov["override_reason"] == "Rough blocking preview requested by user"
    rep = _load_json(Path(f"{out_mp4}.report.json"))
    assert rep["override_reason"] == "Rough blocking preview requested by user"


# ---------------------------------------------------------------------------
# Large Assets (>12 MB), --strip-audio Temp Cleanup, Missing ffprobe (V5)
# ---------------------------------------------------------------------------


def test_large_file_uploaded_once_before_attempt_1_and_strip_audio_cleaned_up(
    tmp_path: Path,
) -> None:
    big_clip = tmp_path / "big_source.mp4"
    # Write >12 MB sparse/real file
    big_clip.write_bytes(VALID_MP4_BYTES + (b"\x00" * (12 * 1024 * 1024 + 64)))
    out_mp4 = tmp_path / "edited.mp4"

    good_720p_6s = {
        "streams": [
            {
                "index": 0,
                "codec_name": "h264",
                "codec_type": "video",
                "width": 1280,
                "height": 720,
                "duration": "6.000000",
            },
            {
                "index": 1,
                "codec_name": "aac",
                "codec_type": "audio",
                "duration": "6.000000",
            },
        ],
        "format": {"duration": "6.000000"},
    }
    runner = FakeCLIRunner(ffprobe_payload=good_720p_6s, source_ffprobe_payload=good_720p_6s)
    rc = video_gen.main(
        [
            "--prompt",
            "Replace rain sound with cheerful jazz piano.",
            "--video",
            str(big_clip),
            "--strip-audio",
            "--ar",
            "16:9",
            "--resolution",
            "720p",
            "--duration",
            "6",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    assert rc == 0
    ffmpeg_calls = [c for c in runner.calls if Path(c[0]).name == "ffmpeg"]
    assert len(ffmpeg_calls) == 1
    ffmpeg_cmd = ffmpeg_calls[0]
    assert Path(ffmpeg_cmd[0]).name == "ffmpeg"
    assert ffmpeg_cmd[1:5] == ("-y", "-i", str(big_clip.resolve()), "-c:v")
    assert "-an" in ffmpeg_cmd
    stripped_temp = Path(ffmpeg_cmd[-1])
    # Guaranteed finally-cleanup: stripped temp file no longer exists on disk!
    assert stripped_temp.exists() is False


def test_v5_missing_ffprobe_records_unchecked_surface_or_fails_when_required(
    tmp_path: Path,
) -> None:
    def which_no_ffprobe(name: str) -> str | None:
        if name == "gemini-api":
            return "/usr/local/bin/gemini-api"
        return None

    out_mp4 = tmp_path / "no_ffprobe.mp4"
    runner = FakeCLIRunner()
    rc_soft = video_gen.main(
        [
            "--prompt",
            "Sunrise over desert dunes.",
            "--duration",
            "6",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=which_no_ffprobe,
    )
    assert rc_soft == 0
    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert "ffprobe_stream_metadata" in prov["unchecked_surfaces"]

    rc_strict = video_gen.main(
        [
            "--prompt",
            "Sunrise over desert dunes.",
            "--duration",
            "6",
            "--require-ffprobe",
            "--raw-prompt",
            "--output",
            str(tmp_path / "strict_ffprobe.mp4"),
        ],
        runner=FakeCLIRunner(),
        which_fn=which_no_ffprobe,
    )
    assert rc_strict != 0


# ---------------------------------------------------------------------------
# Failover Chains, Secret Redaction (S8), Keyframe Delegation & Storyboard
# ---------------------------------------------------------------------------


def test_verifier_chain_failover_and_legacy_video_fallback_and_secret_redaction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_mp4 = tmp_path / "failover.mp4"
    leaked_key = "AIza" + "SyD1234567890abcdefghijklmnopqrstuvwx"
    leaked_oauth = "ya29." + "a0AfH6SMBx1234567890abcdefghijklmnop"

    runner = FakeCLIRunner(
        video_errors=[
            (1, f"HTTP 429 quota exhausted for key={leaked_key}"),
            (1, f"HTTP 503 capacity unavailable token {leaked_oauth}"),
            (1, "HTTP 429 still throttled on 1.2"),
        ],
        judge_errors_by_model={
            "gemini-4-argon": (1, "HTTP 429 quota exhausted"),
        },
    )
    rc = video_gen.main(
        [
            "--prompt",
            "Slow pan across ancient library shelves.",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "10",
            "--allow-legacy-video-fallback",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
        sleep_fn=lambda _: None,
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert leaked_key not in captured.err
    assert leaked_oauth not in captured.err

    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert prov["model_used"] == "gemini-omni-1.1-flash"
    assert prov["verifier_model_used"] == "gemini-4-carbon"
    assert prov["degraded_verifier_fallback"] is False

    # Passing deprecated gemini-3.8-flash as --verifier-model exits 2 cleanly
    assert (
        video_gen.main(
            ["--prompt", "Test clip", "--verifier-model", "gemini-3.8-flash", "--dry-run"],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )
    _ = capsys.readouterr()


def test_synthesize_keyframes_missing_image_gen_exits_2_and_start_end_chains_ref(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_script = tmp_path / "nonexistent" / "image_gen.py"
    rc_missing = video_gen.main(
        [
            "--prompt",
            "Paper boat sailing down rainy gutter.",
            "--synthesize-keyframes",
            "start",
            "--output",
            str(tmp_path / "boat.mp4"),
        ],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
        image_gen_script=missing_script,
    )
    err = capsys.readouterr().err
    assert rc_missing == 2
    assert "image-gen" in err

    stub_image_gen = tmp_path / "image-gen" / "scripts" / "image_gen.py"
    stub_image_gen.parent.mkdir(parents=True, exist_ok=True)
    stub_image_gen.write_text("# stub\n", encoding="utf-8")

    runner = FakeCLIRunner()
    out_mp4 = tmp_path / "boat_transition.mp4"
    rc_ok = video_gen.main(
        [
            "--prompt",
            "Paper boat launches at storm drain and arrives at calm pond.",
            "--synthesize-keyframes",
            "start-end",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "10",
            "--style",
            "watercolour storybook",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
        image_gen_script=stub_image_gen,
    )
    assert rc_ok == 0
    img_calls = [c for c in runner.calls if len(c) >= 2 and "image_gen.py" in c[1]]
    assert len(img_calls) == 2
    # 1080p -> 2K keyframe size!
    size_idx_1 = img_calls[0].index("--size") + 1
    assert img_calls[0][size_idx_1] == "2K"
    start_out_idx = img_calls[0].index("--output") + 1
    start_png_path = img_calls[0][start_out_idx]
    # Second call (end frame) MUST chain -r <start_png_path>!
    assert "-r" in img_calls[1]
    r_idx = img_calls[1].index("-r") + 1
    assert img_calls[1][r_idx] == start_png_path


def test_storyboard_manifest_generates_verified_transitions_and_concatenates(
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for name in ("anchor.png", "frame_01.png", "frame_02.png", "frame_03.png"):
        (frames_dir / name).write_bytes(TINY_PNG_BYTES)

    manifest_data = _load_json(FIXTURES_GOOD / "keyframes_manifest_sample.json")
    manifest_path = tmp_path / "keyframes_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    probe_6s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_6s["streams"][0]["duration"] = "5.800000"
    probe_6s["format"]["duration"] = "5.800000"

    probe_12s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_12s["streams"][0]["duration"] = "11.800000"
    probe_12s["format"]["duration"] = "11.800000"

    out_mp4 = tmp_path / "alpine_story.mp4"
    runner = FakeCLIRunner(ffprobe_payload=probe_6s, concat_ffprobe_payload=probe_12s)
    rc = video_gen.main(
        [
            "--storyboard",
            str(manifest_path),
            "--resolution",
            "1080p",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    assert rc == 0
    assert out_mp4.read_bytes() == VALID_MP4_BYTES
    video_calls = [c for c in runner.calls if c[:2] == ("gemini-api", "video")]
    # 3 frames -> 2 transition segments (1->2 and 2->3)
    assert len(video_calls) == 2
    sb_prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert sb_prov["status"] == "VERIFIED"
    assert sb_prov["concat_mechanical"]["passed"] is True
    assert len(sb_prov["segments"]) == 2


def test_doctor_and_dry_run_modes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeCLIRunner()
    rc_doc_warn = video_gen.main(
        ["--doctor"],
        runner=runner,
        which_fn=_all_tools_present,
        env={"GEMINI_API_KEY": "shadowing-dummy-key"},
    )
    captured_warn = capsys.readouterr()
    assert rc_doc_warn == 0
    assert "GEMINI_API_KEY" in captured_warn.err

    rc_doc_missing = video_gen.main(
        ["--doctor"],
        runner=runner,
        which_fn=lambda _: None,
        env={},
    )
    _ = capsys.readouterr()
    assert rc_doc_missing == 1

    dry_runner = FakeCLIRunner()
    rc_dry = video_gen.main(
        [
            "--prompt",
            "Time-lapse clouds over mountain observatory.",
            "--single-shot",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "8",
            "--dry-run",
            "--output",
            str(tmp_path / "dry.mp4"),
        ],
        runner=dry_runner,
        which_fn=_all_tools_present,
    )
    dry_out = json.loads(capsys.readouterr().out)
    assert rc_dry == 0
    assert dry_out["dry_run"] is True
    assert "-m" in dry_out["planned_command"]
    m_idx = dry_out["planned_command"].index("-m") + 1
    assert dry_out["planned_command"][m_idx] == "gemini-omni-1.2-flash"
    assert dry_runner.calls == []


def test_s4_s8_default_runner_real_subprocess_and_capture_redaction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty sequence"):
        video_gen.default_runner("gemini-api --version")  # type: ignore[arg-type]

    missing_res = video_gen.default_runner(["nonexistent_binary_xyz_987"])
    assert missing_res.returncode == 127
    assert "nonexistent_binary_xyz_987" in missing_res.stderr

    helper_script = tmp_path / "emit_secret.py"
    fake_api_key = "AIza" + "SyB9876543210abcdefghijklmnopqrstuvwx"
    helper_script.write_text(
        "import sys\n"
        f'sys.stdout.write("url=https://example.com?api_key={fake_api_key}\\n")\n'
        f'sys.stderr.write("GEMINI_API_KEY={fake_api_key}\\n")\n',
        encoding="utf-8",
    )
    real_res = video_gen.default_runner([sys.executable, str(helper_script)])
    assert real_res.returncode == 0
    assert fake_api_key not in real_res.stdout
    assert fake_api_key not in real_res.stderr
    assert "[REDACTED" in real_res.stdout
    assert "[REDACTED" in real_res.stderr


def test_container_header_negatives_and_rotation_metadata(tmp_path: Path) -> None:
    ok_missing, code_missing = video_gen.verify_mp4_container_header(tmp_path / "none.mp4")
    assert ok_missing is False
    assert code_missing == "missing_output_file"

    tiny_file = tmp_path / "tiny.mp4"
    tiny_file.write_bytes(b"short")
    ok_tiny, code_tiny = video_gen.verify_mp4_container_header(tiny_file)
    assert ok_tiny is False
    assert "empty_or_truncated_mp4" in code_tiny

    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_bytes(b"\x89PNG\r\n\x1a\n0123456789abcdef")
    ok_corrupt, code_corrupt = video_gen.verify_mp4_container_header(corrupt_file)
    assert ok_corrupt is False
    assert code_corrupt == "invalid_mp4_ftyp_header"

    # Mobile portrait stream stored as 1920x1080 with 90-degree rotation tag -> effective 1080x1920 (9:16)
    rotated_probe = {
        "streams": [
            {
                "index": 0,
                "codec_name": "h264",
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "duration": "8.000000",
                "tags": {"rotate": "90"},
            }
        ],
        "format": {"duration": "8.000000"},
    }
    rot_verdict = video_gen.verify_ffprobe_payload(
        rotated_probe,
        expected_ar="9:16",
        expected_resolution="1080p",
        expected_duration_s=8,
        expected_audio="silent",
    )
    assert rot_verdict["passed"] is True
    assert rot_verdict["width"] == 1080
    assert rot_verdict["height"] == 1920


def test_prep_clip_no_verify_spec_roundtrip_and_storyboard_negatives(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vref = tmp_path / "raw_vref.mp4"
    vref.write_bytes(VALID_MP4_BYTES)
    spec_out = tmp_path / "frozen.spec.json"
    out_mp4 = tmp_path / "mechanical_only.mp4"

    probe_8s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_8s["streams"][0]["duration"] = "8.000000"
    probe_8s["format"]["duration"] = "8.000000"

    runner = FakeCLIRunner(ffprobe_payload=probe_8s)
    rc = video_gen.main(
        [
            "--prompt",
            "Skater glides across sunlit plaza.",
            "--video-ref",
            str(vref),
            "--prep-clip",
            "--no-verify",
            "--spec-out",
            str(spec_out),
            "--duration",
            "8",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    cap_ok = capsys.readouterr()
    assert rc == 0, f"stdout={cap_ok.out}\nstderr={cap_ok.err}"
    ffmpeg_calls = [c for c in runner.calls if Path(c[0]).name == "ffmpeg"]
    assert len(ffmpeg_calls) == 1
    assert "-t" in ffmpeg_calls[0]
    assert ffmpeg_calls[0][ffmpeg_calls[0].index("-t") + 1] == "3"

    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert prov["status"] == "MECHANICAL_ONLY"
    assert "stage4_multimodal_rubric" in prov["unchecked_surfaces"]

    # Round-trip --spec-file in --dry-run
    stub_img = tmp_path / "image_gen.py"
    stub_img.write_text("# stub\n", encoding="utf-8")
    rc_dry_kf = video_gen.main(
        [
            "--prompt",
            "Lantern rises into night sky.",
            "--synthesize-keyframes",
            "start-end",
            "--duration",
            "6",
            "--dry-run",
            "--output",
            str(tmp_path / "kf_dry.mp4"),
        ],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
        image_gen_script=stub_img,
    )
    dry_kf_json = json.loads(capsys.readouterr().out)
    assert rc_dry_kf == 0
    assert len(dry_kf_json["planned_keyframe_commands"]) == 2

    rc_spec_file = video_gen.main(
        ["--spec-file", str(spec_out), "--dry-run", "--output", str(tmp_path / "from_spec.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_spec_file == 0

    # Storyboard negative tests (missing, invalid JSON, empty frames -> all exit 2)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    empty_frames = tmp_path / "empty_frames.json"
    empty_frames.write_text(json.dumps({"schema_version": 1, "frames": []}), encoding="utf-8")

    for sb_path in (tmp_path / "missing_sb.json", bad_json, empty_frames):
        rc_sb = video_gen.main(
            ["--storyboard", str(sb_path), "--output", str(tmp_path / "sb_out.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        assert rc_sb == 2


def test_live_prompt_expansion_and_utc_timestamp(tmp_path: Path) -> None:
    iso_ts = video_gen.utc_now_iso()
    assert isinstance(iso_ts, str) and iso_ts.endswith("Z") and "T" in iso_ts

    rich_expanded = (
        'Golden-hour anamorphic tracking shot: courier cycles past kiosk reading "PARCEL HUB" '
        "with crisp ambient city foley."
    )
    runner_good = FakeCLIRunner(expanded_prompt_text=rich_expanded)
    out_good = tmp_path / "expanded_ok.mp4"
    rc_ok = video_gen.main(
        [
            "--prompt",
            'Courier cycles past kiosk reading "PARCEL HUB".',
            "--duration",
            "10",
            "--resolution",
            "1080p",
            "--expand-prompt",
            "--output",
            str(out_good),
        ],
        runner=runner_good,
        which_fn=_all_tools_present,
    )
    assert rc_ok == 0
    vid_calls = [c for c in runner_good.calls if c[:2] == ("gemini-api", "video")]
    assert len(vid_calls) == 1
    assert vid_calls[0][2] == rich_expanded
    prov = _load_json(Path(f"{out_good}.provenance.json"))
    assert prov["generated_at"].endswith("Z")

    # Lossy expansion dropping quoted literal "PARCEL HUB" must fall back to deterministic prompt
    runner_lossy = FakeCLIRunner(expanded_prompt_text="Courier cycles past a street kiosk at dusk.")
    fallback_prompt = video_gen.maybe_expand_prompt(
        raw_prompt='Courier cycles past kiosk reading "PARCEL HUB".',
        deterministic_prompt='Deterministic: Courier cycles past kiosk reading "PARCEL HUB".',
        verifier_model="gemini-4-argon",
        runner=runner_lossy,
    )
    assert fallback_prompt == 'Deterministic: Courier cycles past kiosk reading "PARCEL HUB".'


def test_p1_storyboard_traversal_non_image_and_worst_status_and_p2_concat_gates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. P1 #4 & R5: Reject path traversal (pointing at real file outside fixtures/known_bad) and non-image frame fixtures
    trav_manifest = _load_json(FIXTURES_BAD / "manifest_traversal.json")
    assert (FIXTURES_BAD / trav_manifest["frames"][0]["path"]).resolve().is_file()
    runner_idle = FakeCLIRunner()
    rc_trav = video_gen.main(
        [
            "--storyboard",
            str(FIXTURES_BAD / "manifest_traversal.json"),
            "--dry-run",
            "--output",
            str(tmp_path / "bad_sb_trav.mp4"),
        ],
        runner=runner_idle,
        which_fn=_all_tools_present,
    )
    assert rc_trav == 2
    assert "escapes" in capsys.readouterr().err.lower()

    rc_nonimg = video_gen.main(
        [
            "--storyboard",
            str(FIXTURES_BAD / "manifest_non_image_frame.json"),
            "--dry-run",
            "--output",
            str(tmp_path / "bad_sb_nonimg.mp4"),
        ],
        runner=runner_idle,
        which_fn=_all_tools_present,
    )
    assert rc_nonimg == 2
    assert len(runner_idle.calls) == 0

    # Manifest with non-image anchor_image also exits 2
    bad_anchor_txt = tmp_path / "anchor.txt"
    bad_anchor_txt.write_text("not png", encoding="utf-8")
    (tmp_path / "f1.png").write_bytes(TINY_PNG_BYTES)
    bad_anchor_sb = tmp_path / "bad_anchor_sb.json"
    bad_anchor_sb.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aspect_ratio": "16:9",
                "anchor_image": "anchor.txt",
                "frames": [{"path": "f1.png", "prompt": "Scene", "duration_s": 5}],
            }
        ),
        encoding="utf-8",
    )
    assert (
        video_gen.main(
            ["--storyboard", str(bad_anchor_sb), "--dry-run", "--output", str(tmp_path / "out.mp4")],
            runner=runner_idle,
            which_fn=_all_tools_present,
        )
        == 2
    )

    # Setup valid 3-frame storyboard for #5 and #20 tests
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for name in ("anchor.png", "frame_01.png", "frame_02.png", "frame_03.png"):
        (frames_dir / name).write_bytes(TINY_PNG_BYTES)
    sb_manifest = tmp_path / "valid_sb.json"
    sb_manifest.write_text(
        json.dumps(_load_json(FIXTURES_GOOD / "keyframes_manifest_sample.json")),
        encoding="utf-8",
    )

    probe_6s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_6s["streams"][0]["duration"] = "5.800000"
    probe_6s["format"]["duration"] = "5.800000"
    probe_12s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_12s["streams"][0]["duration"] = "11.800000"
    probe_12s["format"]["duration"] = "11.800000"

    # 2. P1 #5: Storyboard provenance reflects worst segment status (UNVERIFIED_OVERRIDE != VERIFIED)
    fail_verdict = {
        "overall_passed": False,
        "criteria_results": [
            {
                "id": "AC-1",
                "passed": False,
                "observed_evidence": "Subject drifted off frame.",
                "fix_instruction": "Keep subject centered.",
            }
        ],
        "remediation_mode": "regenerate",
        "edit_delta_prompt": "",
        "regenerated_prompt": "",
    }
    out_override = tmp_path / "override_sb.mp4"
    runner_override = FakeCLIRunner(
        ffprobe_payload=probe_6s,
        concat_ffprobe_payload=probe_12s,
        judge_verdicts=[fail_verdict],
    )
    rc_override = video_gen.main(
        [
            "--storyboard",
            str(sb_manifest),
            "--max-attempts",
            "1",
            "--allow-unverified",
            "--override-reason",
            "Storyboard animatic draft",
            "--raw-prompt",
            "--output",
            str(out_override),
        ],
        runner=runner_override,
        which_fn=_all_tools_present,
    )
    assert rc_override == 0
    override_prov = _load_json(Path(f"{out_override}.provenance.json"))
    assert override_prov["status"] == "UNVERIFIED_OVERRIDE"

    # 3. P2 #20: Multi-segment storyboard WITHOUT ffmpeg exits 1 as PARTIAL and does NOT copy seg 1
    out_no_ffmpeg = tmp_path / "no_ffmpeg_sb.mp4"
    rc_no_ff = video_gen.main(
        [
            "--storyboard",
            str(sb_manifest),
            "--raw-prompt",
            "--output",
            str(out_no_ffmpeg),
        ],
        runner=FakeCLIRunner(ffprobe_payload=probe_6s),
        which_fn=lambda n: None if n == "ffmpeg" else f"/usr/bin/{n}",
    )
    assert rc_no_ff == 1
    assert not out_no_ffmpeg.exists()
    partial_prov = _load_json(Path(f"{out_no_ffmpeg}.provenance.json"))
    assert partial_prov["status"] == "PARTIAL"
    assert len(partial_prov["preserved_segments"]) == 2

    # 4. P2 #20: Multi-segment storyboard WITH failing concat ffprobe exits 1 and removes output
    probe_bad_concat = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_bad_concat["streams"][0]["duration"] = "2.000000"
    probe_bad_concat["format"]["duration"] = "2.000000"
    out_bad_concat = tmp_path / "bad_concat_sb.mp4"
    rc_bad_concat = video_gen.main(
        [
            "--storyboard",
            str(sb_manifest),
            "--raw-prompt",
            "--output",
            str(out_bad_concat),
        ],
        runner=FakeCLIRunner(ffprobe_payload=probe_6s, concat_ffprobe_payload=probe_bad_concat),
        which_fn=_all_tools_present,
    )
    assert rc_bad_concat == 1
    assert not out_bad_concat.exists()
    bad_concat_prov = _load_json(Path(f"{out_bad_concat}.provenance.json"))
    assert bad_concat_prov["status"] == "FAILED_VERIFICATION"
    _ = capsys.readouterr()


def test_p1_judge_binding_indices_zero_mandatory_ac_and_verifier_allowlist(tmp_path: Path) -> None:
    # 1. P1 #7: Judge prompt lists candidate as Input #1 and reference bindings as input_index + 1 (#2, #3)
    spec_single = _load_json(FIXTURES_GOOD / "spec_single_shot_10s.json")
    judge_prompt = video_gen.build_blinded_judge_prompt(spec_single)
    assert "Reference input #2 (first_frame)" in judge_prompt

    # 2. P1 #6: validate_rubric_verdict fails closed when mandatory_ids is empty
    zero_spec = _load_json(FIXTURES_BAD / "zero_mandatory_spec.json")
    verdict_zero = video_gen.validate_rubric_verdict(
        {
            "overall_passed": True,
            "criteria_results": [
                {"id": "AC-1", "passed": True, "observed_evidence": "Nice lighting.", "fix_instruction": ""}
            ],
        },
        zero_spec,
    )
    assert verdict_zero["all_passed"] is False
    assert "zero_mandatory_acceptance_criteria" in verdict_zero["validation_errors"]

    rc_zero = video_gen.main(
        ["--spec-file", str(FIXTURES_BAD / "zero_mandatory_spec.json"), "--dry-run", "-o", str(tmp_path / "z.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    assert rc_zero == 2

    # 3. P1 #8: Verifier role rejects video/image models (exit 2)
    for bad_ver in ("gemini-omni-1.2-flash", "gemini-3.1-flash-lite-image"):
        assert (
            video_gen.main(
                ["--prompt", "Hero clip", "--verifier-model", bad_ver, "--dry-run"],
                runner=FakeCLIRunner(),
                which_fn=_all_tools_present,
            )
            == 2
        )


def test_p2_spec_constraints_digest_malformed_and_storyboard_omni_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. P2 #14: Malformed and digest-mismatched --spec-file exit 2 cleanly (no traceback)
    for bad_spec in (
        FIXTURES_BAD / "malformed_spec.json",
        FIXTURES_BAD / "digest_mismatch_spec.json",
    ):
        assert (
            video_gen.main(
                ["--spec-file", str(bad_spec), "--dry-run", "-o", str(tmp_path / "bad.mp4")],
                runner=FakeCLIRunner(),
                which_fn=_all_tools_present,
            )
            == 2
        )

    # 2. P2 #18: --spec-file explicit_constraints override CLI defaults in planned command/body
    custom_spec_path = tmp_path / "vertical_spec.json"
    spec_obj = video_gen.compile_visual_spec(
        video_gen.VideoJobConfig(
            prompt="Owl in moonlight",
            aspect_ratio="9:16",
            resolution="720p",
            duration_s=12,
            audio_mode="silent",
            single_shot=True,
        )
    )
    custom_spec_path.write_text(json.dumps(spec_obj), encoding="utf-8")

    rc_apply = video_gen.main(
        ["--spec-file", str(custom_spec_path), "--dry-run", "-o", str(tmp_path / "spec_out.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    assert rc_apply == 0
    dry_out = json.loads(capsys.readouterr().out)
    assert dry_out["planned_body"]["response_format"]["duration"] == "12s"
    assert dry_out["planned_command"][dry_out["planned_command"].index("--aspect-ratio") + 1] == "9:16"
    assert dry_out["planned_command"][dry_out["planned_command"].index("--resolution") + 1] == "720p"

    # Explicit conflicting CLI flag (--duration 8 vs spec 12s) exits 2
    rc_conflict = video_gen.main(
        ["--spec-file", str(custom_spec_path), "--duration", "8", "--dry-run", "-o", str(tmp_path / "c.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    assert rc_conflict == 2

    # 3. P2 #19: --storyboard blocks --video / --extend / --first-frame / --video-ref & bad caption XML tags
    (tmp_path / "s.mp4").write_bytes(VALID_MP4_BYTES)
    (tmp_path / "k.png").write_bytes(TINY_PNG_BYTES)
    good_sb = tmp_path / "good_sb.json"
    good_sb.write_text(
        json.dumps({"schema_version": 1, "aspect_ratio": "16:9", "frames": [{"path": "k.png", "prompt": "p", "duration_s": 5}]}),
        encoding="utf-8",
    )
    for bad_flag in (["--video", str(tmp_path / "s.mp4")], ["--extend", str(tmp_path / "s.mp4")], ["--first-frame", str(tmp_path / "k.png")], ["--synthesize-keyframes", "start"]):
        assert (
            video_gen.main(
                ["--storyboard", str(good_sb), *bad_flag, "--dry-run", "-o", str(tmp_path / "x.mp4")],
                runner=FakeCLIRunner(),
                which_fn=_all_tools_present,
            )
            == 2
        )
    assert (
        video_gen.main(
            ["--storyboard", str(FIXTURES_BAD / "manifest_bad_caption_tag.json"), "--dry-run", "-o", str(tmp_path / "t.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )
    _ = capsys.readouterr()


def test_p2_upload_json_path_confinement_rejected_suffix_provenance_and_redaction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. P2 #16: AssetUploadCache prefers -o json and ignores path prefixes like /files/big.mp4
    fake_asset = tmp_path / "big.mp4"
    fake_asset.write_bytes(VALID_MP4_BYTES)
    calls_seen: list[tuple[str, ...]] = []

    def upload_json_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        calls_seen.append(tuple(cmd))
        return video_gen.CommandResult(0, json.dumps({"name": "files/json_999"}), "", tuple(cmd))

    cache_json = video_gen.AssetUploadCache(upload_json_runner)
    assert cache_json.resolve(fake_asset, force_upload=True) == "files/json_999"
    assert "-o" in calls_seen[0] and "json" in calls_seen[0]

    def upload_prefix_trap_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        return video_gen.CommandResult(0, "Uploaded /tmp/files/big.mp4 -> files/abc123\n", "", tuple(cmd))

    cache_plain = video_gen.AssetUploadCache(upload_prefix_trap_runner)
    assert cache_plain.resolve(fake_asset, force_upload=True) == "files/abc123"

    # 2. P2 #21: Real default_runner catches & redacts JSON GEMINI_API_KEY and api_key fields
    leaked_val = "SecretValue_JsonEnv987"
    leaked_q = "AIza" + "SyTestVideoRedact0123456789abcdefghi"
    proc = video_gen.default_runner(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                f"print('{{\"GEMINI_API_KEY\": \"{leaked_val}\", \"api_key\": \"raw_api_token_123\"}}');"
                f"sys.stderr.write('https://api.test/v1?key={leaked_q}&z=1\\n')"
            ),
        ]
    )
    assert proc.returncode == 0
    assert leaked_val not in proc.stdout
    assert "raw_api_token_123" not in proc.stdout
    assert leaked_q not in proc.stderr

    # 3. P2 #11, #15, #17: Escaping generation .path refused; custom candidate suffix preserved in .rejected; stale .provenance.json unlinked
    outside_mp4 = tmp_path / "outside_safe.mp4"
    outside_mp4.write_bytes(VALID_MP4_BYTES)
    target_mp4 = tmp_path / "target_clip.mp4"
    target_mp4.write_bytes(b"stale clip")
    stale_prov = Path(f"{target_mp4}.provenance.json")
    stale_prov.write_text('{"status": "VERIFIED"}\n', encoding="utf-8")

    def escape_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        if len(cmd) >= 2 and cmd[1] == "video":
            return video_gen.CommandResult(0, json.dumps({"kind": "video", "path": str(outside_mp4), "response_id": "r1"}), "", tuple(cmd))
        return video_gen.CommandResult(0, "", "", tuple(cmd))

    rc_escape = video_gen.main(
        ["--prompt", "Escape test", "--raw-prompt", "--max-attempts", "1", "-o", str(target_mp4)],
        runner=escape_runner,
        which_fn=_all_tools_present,
    )
    assert rc_escape == 1
    assert outside_mp4.is_file()
    assert not target_mp4.exists()
    assert not stale_prov.exists()

    # Custom .webm candidate suffix preserved as .rejected.webm on failure
    webm_target = tmp_path / "custom_fail.mp4"

    def webm_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        if len(cmd) >= 2 and cmd[1] == "video":
            out_arg = Path(cmd[cmd.index("--out") + 1])
            webm_cand = out_arg.with_suffix(".webm")
            webm_cand.write_bytes(b"\x1a\x45\xdf\xa3fakewebm")
            return video_gen.CommandResult(0, json.dumps({"kind": "video", "path": str(webm_cand), "response_id": "r_w"}), "", tuple(cmd))
        return FakeCLIRunner()(cmd)

    rc_webm = video_gen.main(
        ["--prompt", "Fail webm", "--raw-prompt", "--max-attempts", "1", "-o", str(webm_target)],
        runner=webm_runner,
        which_fn=_all_tools_present,
    )
    assert rc_webm == 1
    assert (tmp_path / "custom_fail.rejected.webm").is_file()

    # 4. P2 #22: regenerated_prompt dropping NL directives or single-shot falls back to compiled_prompt
    (tmp_path / "start_f.png").write_bytes(TINY_PNG_BYTES)
    spec_directives = video_gen.compile_visual_spec(
        video_gen.VideoJobConfig(
            prompt='Drone reveals "SUMMIT"',
            first_frame=str(tmp_path / "start_f.png"),
            single_shot=True,
            audio_mode="silent",
        )
    )
    mode_regen, chosen_prompt = video_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation={
            "pass_ratio": 0.25,
            "fix_instructions": ["Fix logo"],
            "regenerated_prompt": 'Generic shot showing "SUMMIT" with loud music.',
        },
        previous_response_id="v1_r",
        has_video_refs=False,
        spec=spec_directives,
    )
    assert mode_regen == "regenerate"
    assert "single continuous unbroken shot" in chosen_prompt.lower()
    assert "use this image as the starting frame" in chosen_prompt.lower()
    _ = capsys.readouterr()


def test_r1_to_r4_keyframe_rewrite_files_uri_anchor_spec_schema_and_upload_uri(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # R1: synthesize-keyframes tracks MIME suffix rewrite (.png requested -> .jpg emitted by image_gen)
    stub_image_gen = tmp_path / "image-gen" / "scripts" / "image_gen.py"
    stub_image_gen.parent.mkdir(parents=True, exist_ok=True)
    stub_image_gen.write_text("# stub\n", encoding="utf-8")

    base_runner = FakeCLIRunner()
    img_cmds_seen: list[list[str]] = []

    def jpg_rewrite_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        if cmd[0] == sys.executable and "image_gen.py" in cmd[1]:
            cmd_list = [str(x) for x in cmd]
            img_cmds_seen.append(cmd_list)
            req_out = Path(cmd_list[cmd_list.index("--output") + 1])
            jpg_out = req_out.with_suffix(".jpg")
            jpg_out.parent.mkdir(parents=True, exist_ok=True)
            jpg_out.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
            return video_gen.CommandResult(
                0,
                json.dumps({"status": "VERIFIED", "output": str(jpg_out)}),
                "",
                tuple(cmd_list),
            )
        return base_runner(cmd)

    out_kf_mp4 = tmp_path / "kf_rewrite.mp4"
    rc_kf = video_gen.main(
        [
            "--prompt",
            "Paper boat launches and arrives at pier.",
            "--synthesize-keyframes",
            "start-end",
            "--ar",
            "16:9",
            "--resolution",
            "1080p",
            "--duration",
            "10",
            "--raw-prompt",
            "--output",
            str(out_kf_mp4),
        ],
        runner=jpg_rewrite_runner,
        which_fn=_all_tools_present,
        image_gen_script=stub_image_gen,
    )
    assert rc_kf == 0
    assert len(img_cmds_seen) == 2
    assert img_cmds_seen[1][img_cmds_seen[1].index("-r") + 1].endswith("start_frame.jpg")
    vid_calls = [c for c in base_runner.calls if c[:2] == ("gemini-api", "video")]
    assert len(vid_calls) == 1
    vid_inputs = [vid_calls[0][i + 1] for i, t in enumerate(vid_calls[0]) if t == "-i"]
    assert any(inp.endswith("start_frame.jpg") for inp in vid_inputs)
    assert any(inp.endswith("end_frame.jpg") for inp in vid_inputs)

    # R3: Storyboard manifest with files/<id> anchor_image passes through to gemini-api video -i
    f1 = tmp_path / "f1.png"
    f1.write_bytes(TINY_PNG_BYTES)
    sb_uri = tmp_path / "sb_files_uri.json"
    sb_uri.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aspect_ratio": "16:9",
                "anchor_image": "files/anchor_roundtrip_1",
                "frames": [{"path": "f1.png", "prompt": "Animate hero ship", "duration_s": 8}],
            }
        ),
        encoding="utf-8",
    )
    probe_8s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_8s["streams"][0]["duration"] = "8.000000"
    probe_8s["format"]["duration"] = "8.000000"
    uri_runner = FakeCLIRunner(ffprobe_payload=probe_8s)
    rc_uri = video_gen.main(
        [
            "--storyboard",
            str(sb_uri),
            "--storyboard-mode",
            "clips",
            "--raw-prompt",
            "--output",
            str(tmp_path / "uri_sb.mp4"),
        ],
        runner=uri_runner,
        which_fn=_all_tools_present,
    )
    assert rc_uri == 0
    uri_vid = [c for c in uri_runner.calls if c[:2] == ("gemini-api", "video")]
    assert "files/anchor_roundtrip_1" in uri_vid[0]

    # R4: --spec-file missing AC category or malformed asset_bindings exits 2 cleanly (no KeyError crash)
    base_spec = _load_json(FIXTURES_GOOD / "spec_single_shot_10s.json")
    missing_cat = json.loads(json.dumps(base_spec))
    del missing_cat["acceptance_criteria"][0]["category"]
    p_missing_cat = tmp_path / "spec_no_cat.json"
    p_missing_cat.write_text(json.dumps(missing_cat), encoding="utf-8")
    assert (
        video_gen.main(
            ["--spec-file", str(p_missing_cat), "--dry-run", "-o", str(tmp_path / "s1.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )

    bad_bindings = json.loads(json.dumps(base_spec))
    bad_bindings["explicit_constraints"]["asset_bindings"] = [{"input_index": "bad", "role": "first_frame"}]
    p_bad_bind = tmp_path / "spec_bad_bind.json"
    p_bad_bind.write_text(json.dumps(bad_bindings), encoding="utf-8")
    assert (
        video_gen.main(
            ["--spec-file", str(p_bad_bind), "--dry-run", "-o", str(tmp_path / "s2.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )

    # P3: uri-only JSON from files upload extracts files/<id> cleanly without double 'files/https://...' prefix
    dummy_vid = tmp_path / "u.mp4"
    dummy_vid.write_bytes(VALID_MP4_BYTES)
    cache_uri = video_gen.AssetUploadCache(
        lambda cmd: video_gen.CommandResult(
            0,
            json.dumps({"uri": "https://generativelanguage.googleapis.com/v1beta/files/abc789"}),
            "",
            tuple(cmd),
        )
    )
    assert cache_uri.resolve(dummy_vid, force_upload=True) == "files/abc789"

    # N5: files/<id> passed to --video, --extend, or --video-ref passes URI intact (no host-path resolve),
    # while combining --strip-audio or --prep-clip with a remote URI exits 2
    n5_runner = FakeCLIRunner()
    assert (
        video_gen.main(
            [
                "--prompt",
                "Apply neon lighting",
                "--video",
                "files/vid001",
                "--duration",
                "10",
                "--raw-prompt",
                "--output",
                str(tmp_path / "n5_edit.mp4"),
            ],
            runner=n5_runner,
            which_fn=_all_tools_present,
        )
        == 0
    )
    edit_vid_calls = [c for c in n5_runner.calls if c[:2] == ("gemini-api", "video")]
    assert "files/vid001" in edit_vid_calls[0]
    assert not any("files/vid001" in tok and tok != "files/vid001" for tok in edit_vid_calls[0])

    n5_vref_runner = FakeCLIRunner()
    assert (
        video_gen.main(
            [
                "--prompt",
                "Reference clip motion",
                "--video-ref",
                "files/ref001",
                "--duration",
                "10",
                "--raw-prompt",
                "--output",
                str(tmp_path / "n5_vref.mp4"),
            ],
            runner=n5_vref_runner,
            which_fn=_all_tools_present,
        )
        == 0
    )
    vref_vid_calls = [c for c in n5_vref_runner.calls if c[:2] == ("gemini-api", "video")]
    assert "files/ref001" in vref_vid_calls[0]
    assert not any("files/ref001" in tok and tok != "files/ref001" for tok in vref_vid_calls[0])

    assert (
        video_gen.main(
            [
                "--prompt",
                "Strip remote audio",
                "--video",
                "files/vid001",
                "--strip-audio",
                "--raw-prompt",
                "--output",
                str(tmp_path / "n5_bad_strip.mp4"),
            ],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )
    assert (
        video_gen.main(
            [
                "--prompt",
                "Prep remote clip",
                "--video-ref",
                "files/ref001",
                "--prep-clip",
                "--raw-prompt",
                "--output",
                str(tmp_path / "n5_bad_prep.mp4"),
            ],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )
    _ = capsys.readouterr()




# ---------------------------------------------------------------------------
# PR 2: Arbitrary-Length Timelines, Boundary Chaining & xfade Overlap Math
# ---------------------------------------------------------------------------


def test_arbitrary_duration_decomposition_45s_90s_600s_3600s_and_overlap_math() -> None:
    good_plan_fixture = _load_json(FIXTURES_GOOD / "timeline_plan_45s_keyframe_chain.json")
    assert good_plan_fixture["target_duration_s"] == 45
    assert abs(
        good_plan_fixture["expected_stitched_duration_s"] - good_plan_fixture["target_duration_s"]
    ) <= good_plan_fixture["tolerance_s"]

    for target_s, crossfade, synth_kf in (
        (45, 0.0, None),
        (45, 0.5, None),
        (45, 1.0, "start-end"),
        (90, 0.5, None),
        (600, 0.5, None),
        (3600, 0.0, None),
    ):
        cfg = video_gen.parse_job_config(
            [
                "--prompt",
                "Continuous orbital flyover above sunlit cloud deck",
                "--duration",
                str(target_s),
                "--crossfade-sec",
                str(crossfade),
                *(["--synthesize-keyframes", synth_kf] if synth_kf else []),
            ]
        )
        assert video_gen.is_multi_segment_job(cfg) is True
        plan = video_timeline.compile_timeline_plan(cfg)
        segs = plan["segments"]
        assert len(segs) >= 2
        max_cap = 10 if synth_kf == "start-end" else 15
        assert all(5 <= s["duration_s"] <= max_cap for s in segs)

        raw_sum = sum(s["duration_s"] for s in segs)
        net_dur = raw_sum - crossfade * (len(segs) - 1)
        tol = max(1.5, 0.05 * target_s)
        assert abs(net_dur - target_s) <= tol
        assert plan["raw_segment_sum_s"] == raw_sum
        assert abs(plan["expected_stitched_duration_s"] - net_dur) < 1e-6

    with pytest.raises(ValueError, match="target_duration_s"):
        video_timeline.decompose_duration_into_segments(2)
    with pytest.raises(ValueError, match="crossfade-sec"):
        video_timeline.decompose_duration_into_segments(30, crossfade_sec=3.0)


def test_script_parser_json_and_markdown_beats_and_negative_gates(tmp_path: Path) -> None:
    anchor_png = tmp_path / "beat_start.png"
    anchor_png.write_bytes(TINY_PNG_BYTES)

    script_json = tmp_path / "beats.json"
    script_json.write_text(
        json.dumps(
            {
                "style": "isometric architectural film",
                "aspect_ratio": "16:9",
                "continuity": "keyframe-chain",
                "crossfade_sec": 0.5,
                "beats": [
                    {
                        "prompt": "Cluster control plane boots cleanly",
                        "duration_s": 12,
                        "scene_text": "CLUSTER READY",
                        "first_frame": "beat_start.png",
                    },
                    {
                        "prompt": "Regional load balancer shifts live traffic",
                        "duration_s": 22,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    parsed_j = video_timeline.parse_script_file(str(script_json))
    assert len(parsed_j["beats"]) == 2
    assert parsed_j["beats"][0]["scene_texts"] == ["CLUSTER READY"]
    assert parsed_j["metadata"]["style"] == "isometric architectural film"

    # 22s beat automatically splits into two <=15s sub-segments when compiling plan
    cfg_j = video_gen.parse_job_config(["--script", str(script_json), "--crossfade-sec", "0.5"])
    plan_j = video_timeline.compile_timeline_plan(cfg_j)
    assert plan_j["segment_count"] == 3
    assert all(5 <= s["duration_s"] <= 15 for s in plan_j["segments"])

    script_md = tmp_path / "walkthrough.md"
    script_md.write_text(
        "# Deployment Walkthrough\n"
        "- [0-12s] Developer commits release manifest.\n"
        "- (10s) Canary pod passes health checks.\n"
        "- Full production traffic cutover completes.\n",
        encoding="utf-8",
    )
    parsed_m = video_timeline.parse_script_file(str(script_md))
    assert len(parsed_m["beats"]) == 3
    assert parsed_m["beats"][0]["duration_s"] == 12
    assert parsed_m["beats"][1]["duration_s"] == 10
    assert parsed_m["beats"][2]["duration_s"] is None

    empty_md = tmp_path / "empty.md"
    empty_md.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        video_timeline.parse_script_file(str(empty_md))

    bad_xml_md = tmp_path / "bad_xml.md"
    bad_xml_md.write_text("- [0-8s] <FIRST_FRAME> zoom into server\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Deprecated XML"):
        video_timeline.parse_script_file(str(bad_xml_md))


def test_45s_keyframe_chain_boundary_extraction_xfade_and_known_bad_stitched_duration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    char_ref = tmp_path / "hero_ref.png"
    char_ref.write_bytes(TINY_PNG_BYTES)
    out_45s = tmp_path / "chained_45s.mp4"
    good_45s_probe = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_45s_stitched.json")

    runner = FakeCLIRunner(
        concat_ffprobe_payload=good_45s_probe,
        match_requested_duration=True,
    )
    rc = video_gen.main(
        [
            "--prompt",
            "Presenter walks through sunlit alpine research station",
            "--duration",
            "45",
            "--continuity",
            "keyframe-chain",
            "--crossfade-sec",
            "0.5",
            "--image-ref",
            f"char:{char_ref}",
            "--raw-prompt",
            "--output",
            str(out_45s),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    cap_ok = capsys.readouterr()
    assert rc == 0, f"stdout={cap_ok.out}\nstderr={cap_ok.err}"
    assert out_45s.read_bytes() == VALID_MP4_BYTES

    plan_file = tmp_path / "chained_45s_segments" / "timeline_plan.json"
    plan_doc = _load_json(plan_file)
    n_segs = plan_doc["segment_count"]
    assert n_segs >= 4

    vid_calls = [c for c in runner.calls if c[:2] == ("gemini-api", "video")]
    assert len(vid_calls) == n_segs

    # Boundary frame extraction (`ffmpeg -sseof -0.05 ... -frames:v 1`) ran between every adjacent pair
    sseof_calls = [c for c in runner.calls if Path(c[0]).name == "ffmpeg" and "-sseof" in c]
    assert len(sseof_calls) == n_segs - 1
    for b_idx, sc in enumerate(sseof_calls, start=1):
        assert sc[sc.index("-sseof") + 1] == "-0.05"
        boundary_out = sc[-1]
        assert f"boundary_{b_idx:03d}.png" in boundary_out
        # Next segment's video call received the extracted boundary frame as first -i input
        next_vid_call = vid_calls[b_idx]
        first_i = next_vid_call[next_vid_call.index("-i") + 1]
        assert first_i.endswith(f"boundary_{b_idx:03d}.png")

    # xfade + acrossfade stitcher invoked with exact filter_complex
    xfade_calls = [
        c for c in runner.calls if Path(c[0]).name == "ffmpeg" and "-filter_complex" in c
    ]
    assert len(xfade_calls) == 1
    fc_str = xfade_calls[0][xfade_calls[0].index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.500:offset=" in fc_str
    assert "acrossfade=d=0.500:c1=tri:c2=tri" in fc_str

    # V1 Negative test: known_bad stitched duration (21.4s vs 45s target) MUST fail closed (exit 1)!
    bad_stitched_out = tmp_path / "bad_stitched_45s.mp4"
    bad_45s_probe = _load_json(FIXTURES_BAD / "ffprobe_failed_stitched_duration.json")
    bad_runner = FakeCLIRunner(
        concat_ffprobe_payload=bad_45s_probe,
        match_requested_duration=True,
    )
    rc_bad = video_gen.main(
        [
            "--prompt",
            "Truncated multi-segment stitch",
            "--duration",
            "45",
            "--raw-prompt",
            "--output",
            str(bad_stitched_out),
        ],
        runner=bad_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_bad == 1
    assert bad_stitched_out.exists() is False
    bad_rep = _load_json(Path(f"{bad_stitched_out}.report.json"))
    assert bad_rep["status"] == "FAILED_VERIFICATION"
    assert any("wrong_duration" in f for f in bad_rep["stitched_mechanical"]["failures"])


def test_timeline_extend_blocks_and_synthesized_keyframes_and_partial_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_img_gen = tmp_path / "image_gen.py"
    stub_img_gen.write_text("# stub\n", encoding="utf-8")

    # 1. Multi-segment timeline with --synthesize-keyframes start-end chains style-locked keyframes
    out_kf = tmp_path / "synth_chain_24s.mp4"
    probe_24s = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_45s_stitched.json")
    probe_24s["streams"][0]["duration"] = "24.000000"
    probe_24s["format"]["duration"] = "24.000000"
    kf_runner = FakeCLIRunner(concat_ffprobe_payload=probe_24s, match_requested_duration=True)
    rc_kf = video_gen.main(
        [
            "--prompt",
            "Origami crane glides across lantern courtyard",
            "--duration",
            "24",
            "--synthesize-keyframes",
            "start-end",
            "--raw-prompt",
            "--output",
            str(out_kf),
        ],
        runner=kf_runner,
        which_fn=_all_tools_present,
        image_gen_script=stub_img_gen,
    )
    _ = capsys.readouterr()
    assert rc_kf == 0
    img_calls = [c for c in kf_runner.calls if len(c) > 1 and Path(c[1]).name == "image_gen.py"]
    assert len(img_calls) == 4  # 3 segments + 1 closing frame
    assert "-r" in img_calls[1]

    # 2. extend-blocks continuity uses Omni extend turns within <=25s blocks
    cfg_ext = video_gen.parse_job_config(
        ["--prompt", "Rover traverses red canyon", "--duration", "20", "--continuity", "extend-blocks"]
    )
    plan_ext = video_timeline.compile_timeline_plan(cfg_ext)
    assert plan_ext["segments"][0]["chain_mode"] == "seed"
    assert plan_ext["segments"][1]["chain_mode"] == "omni_extend_turn"

    # 3. Missing ffmpeg on multi-segment job fails closed with PARTIAL status (exit 1)
    out_missing_ff = tmp_path / "missing_ff_30s.mp4"
    no_ff_runner = FakeCLIRunner(match_requested_duration=True)
    rc_no_ff = video_gen.main(
        [
            "--prompt",
            "Multi-segment without ffmpeg",
            "--duration",
            "30",
            "--raw-prompt",
            "--output",
            str(out_missing_ff),
        ],
        runner=no_ff_runner,
        which_fn=lambda name: None if name == "ffmpeg" else f"/usr/bin/{name}",
    )
    _ = capsys.readouterr()
    assert rc_no_ff == 1
    assert out_missing_ff.exists() is False
    partial_rep = _load_json(Path(f"{out_missing_ff}.report.json"))
    assert partial_rep["status"] == "PARTIAL"


# ---------------------------------------------------------------------------
# PR 2: Scene Text OCR, Captions, Motion Cards, Creative-Stack & ffmpeg-full
# ---------------------------------------------------------------------------


def test_scene_text_injects_text_ac_ocr_criterion_and_guards_prompt_expansion() -> None:
    cfg = video_gen.parse_job_config(
        [
            "--prompt",
            "Close-up of spacecraft bulkhead door latching shut.",
            "--scene-text",
            "AIRLOCK SEALED",
            "--duration",
            "8",
        ]
    )
    spec = video_gen.compile_visual_spec(cfg)
    assert spec["explicit_constraints"]["scene_texts"] == ["AIRLOCK SEALED"]
    assert "Anti-garbling typography discipline" in spec["compiled_prompt"]
    text_acs = [ac for ac in spec["acceptance_criteria"] if ac["category"] == "TEXT_AC"]
    assert len(text_acs) == 1
    assert '"AIRLOCK SEALED"' in text_acs[0]["requirement"]

    errs = video_gen.validate_expanded_prompt(
        cfg.prompt,
        "Close-up of bulkhead door latching shut without any label.",
        extra_literals=["AIRLOCK SEALED"],
    )
    assert any("AIRLOCK SEALED" in e for e in errs)


def test_ffmpeg_full_resolver_creative_stack_discovery_and_missing_libass_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. Keg-only ffmpeg-full precedence: $CREATIVE_STACK_FFMPEG -> /opt/homebrew -> /usr/local -> which
    fake_hb_full = tmp_path / "opt_hb" / "ffmpeg"
    fake_usr_full = tmp_path / "usr_local" / "ffmpeg"
    fake_env_ff = tmp_path / "custom_env" / "ffmpeg"
    for b in (fake_hb_full, fake_usr_full, fake_env_ff):
        b.parent.mkdir(parents=True, exist_ok=True)
        b.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        b.chmod(0o755)

    assert (
        video_post.resolve_ffmpeg_binary(
            "ffmpeg",
            env={"CREATIVE_STACK_FFMPEG": str(fake_env_ff)},
            ffmpeg_full_dirs=(fake_hb_full.parent, fake_usr_full.parent),
        )
        == str(fake_env_ff)
    )
    assert (
        video_post.resolve_ffmpeg_binary(
            "ffmpeg",
            env={},
            which_fn=lambda _: "/usr/bin/ffmpeg",
            ffmpeg_full_dirs=(fake_hb_full.parent, fake_usr_full.parent),
        )
        == str(fake_hb_full)
    )
    assert (
        video_post.resolve_ffmpeg_binary(
            "ffmpeg",
            env={},
            which_fn=lambda _: "/usr/bin/ffmpeg",
            ffmpeg_full_dirs=(tmp_path / "absent_hb", fake_usr_full.parent),
        )
        == str(fake_usr_full)
    )

    # 2. V1 Negative test: corrupt SRT fixture fails pre-upload with exit 2 and zero RPC calls!
    bad_srt_runner = FakeCLIRunner()
    rc_bad_srt = video_gen.main(
        [
            "--prompt",
            "Product walkthrough",
            "--srt",
            str(FIXTURES_BAD / "corrupt_captions.srt"),
            "--output",
            str(tmp_path / "never_srt.mp4"),
        ],
        runner=bad_srt_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_bad_srt == 2
    assert bad_srt_runner.calls == []

    # 3. Missing libass & drawtext fallback: emits pure-stdlib RGBA PNG cards + mov_text soft-sub!
    out_fallback = tmp_path / "fallback_cards_caps.mp4"
    no_libass_runner = FakeCLIRunner(
        ffmpeg_filters_output="Filters:\n .. overlay           VV->V      Overlay video.\n",
    )
    rc_fb = video_gen.main(
        [
            "--prompt",
            "Terminal deployment walkthrough",
            "--duration",
            "10",
            "--srt",
            str(FIXTURES_GOOD / "sample_captions.srt"),
            "--caption-style",
            "pill",
            "--title-card",
            "Cloud Deploy|Zero Cold Starts",
            "--lower-third",
            "Ada Lovelace|Principal SRE@1.5-5.0",
            "--end-card",
            "Try it today",
            "--creative-stack",
            "off",
            "--raw-prompt",
            "--output",
            str(out_fallback),
        ],
        runner=no_libass_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_fb == 0
    fb_rep = _load_json(Path(f"{out_fallback}.report.json"))
    assert (
        fb_rep["post_processing"]["caption_renderer"]
        == "ffmpeg:mov_text_soft_sub_fallback(missing_libass)"
    )
    assert (
        fb_rep["post_processing"]["card_renderer"]
        == "ffmpeg:png_card_overlay_fallback(missing_drawtext)"
    )

    # Verify standalone PNG card generator emits valid PNG IHDR + CRC32
    sample_card = video_post.render_text_card_png(
        tmp_path / "verify_card.png",
        primary_text="DEPLOY READY",
        secondary_text="99.99% AVAILABILITY",
    )
    video_timeline.validate_image_file_header(sample_card)
    assert sample_card.stat().st_size > 200

    # 4. Creative-Stack discovery & delegation to vidkit captions.py + motion.py
    cs_home = tmp_path / "fake_home"
    vk_scripts = cs_home / ".agents" / "skills" / "vidkit" / "scripts"
    sd_scripts = cs_home / ".agents" / "skills" / "sound" / "scripts"
    vk_scripts.mkdir(parents=True)
    sd_scripts.mkdir(parents=True)
    for sc_name in ("captions.py", "motion.py"):
        (vk_scripts / sc_name).write_text("# stub\n", encoding="utf-8")
    (sd_scripts / "mix.py").write_text("# stub\n", encoding="utf-8")

    cs_found = video_post.discover_creative_stack("auto", env={}, home_dir=cs_home)
    assert cs_found.enabled is True
    assert cs_found.source == "home:.agents/skills"
    assert cs_found.captions_script == (vk_scripts / "captions.py").resolve()
    assert cs_found.mix_script == (sd_scripts / "mix.py").resolve()

    #Standalone ASS karaoke & highlight generators produce distinct valid ASS scripts (T1)
    cues = video_post.validate_and_parse_subtitles(srt_path=str(FIXTURES_GOOD / "sample_captions.srt"))
    ass_karaoke = video_post.build_standalone_ass(cues, style="karaoke")
    ass_highlight = video_post.build_standalone_ass(cues, style="highlight")
    assert "\\kf" in ass_karaoke
    assert ass_karaoke != ass_highlight
    assert "00:00:00,200 --> 00:00:03,400" in video_post.format_srt(cues)


# ---------------------------------------------------------------------------
# PR 2: Broadcast Audio Laws (2-Pass Loudnorm, Volume Ducking, amix=normalize=0)
# ---------------------------------------------------------------------------


def test_audio_magic_bytes_2pass_loudnorm_volume_ducking_amix_and_audio_gen_delegation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. V1 Negative gate: non-audio BGM file rejected with exit 2 BEFORE any RPC or ffmpeg call!
    bad_bgm_runner = FakeCLIRunner()
    rc_bad_bgm = video_gen.main(
        [
            "--prompt",
            "Tutorial video",
            "--audio-mode",
            "bgm",
            "--bgm-track",
            str(FIXTURES_BAD / "non_audio_bgm.mp3"),
            "--output",
            str(tmp_path / "never_bgm.mp4"),
        ],
        runner=bad_bgm_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_bad_bgm == 2
    assert bad_bgm_runner.calls == []

    # Verify all 5 magic-byte formats pass positive inspection
    assert video_post.validate_audio_magic_bytes(FIXTURES_GOOD / "tiny_tone.wav") == "wav"
    mp3_id3 = tmp_path / "valid_id3.mp3"
    mp3_id3.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x10" + b"\x00" * 32)
    assert video_post.validate_audio_magic_bytes(mp3_id3) == "mp3"
    flac_f = tmp_path / "valid.flac"
    flac_f.write_bytes(b"fLaC\x00\x00\x00\x22" + b"\x00" * 32)
    assert video_post.validate_audio_magic_bytes(flac_f) == "flac"
    ogg_f = tmp_path / "valid.ogg"
    ogg_f.write_bytes(b"OggS\x00\x02" + b"\x00" * 32)
    assert video_post.validate_audio_magic_bytes(ogg_f) == "ogg"
    m4a_f = tmp_path / "valid.m4a"
    m4a_f.write_bytes(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A isom" + b"\x00" * 16)
    assert video_post.validate_audio_magic_bytes(m4a_f) == "m4a"

    # 2. Standalone full-mix enforces ALL THREE DSP LAWS:
    #    (a) 2-pass linear loudnorm at -ar 48000, (b) silencedetect volume envelope (ZERO sidechaincompress),
    #    (c) amix=inputs=3:duration=longest:normalize=0!
    sfx_wav = tmp_path / "whoosh.wav"
    sfx_wav.write_bytes((FIXTURES_GOOD / "tiny_tone.wav").read_bytes())
    out_mix = tmp_path / "mastered_mix.mp4"
    dsp_runner = FakeCLIRunner()
    rc_mix = video_gen.main(
        [
            "--prompt",
            "Architecture walkthrough scene",
            "--duration",
            "10",
            "--audio-mode",
            "full-mix",
            "--voice-track",
            str(FIXTURES_GOOD / "tiny_tone.wav"),
            "--bgm-track",
            str(mp3_id3),
            "--sfx-cue",
            f"{sfx_wav}@2.5:-3",
            "--duck-db",
            "14.0",
            "--lufs-target",
            "-14.0",
            "--creative-stack",
            "off",
            "--raw-prompt",
            "--output",
            str(out_mix),
        ],
        runner=dsp_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_mix == 0

    ff_cmds = [" ".join(c) for c in dsp_runner.calls if Path(c[0]).name == "ffmpeg"]
    joined_all_ff = "\n".join(ff_cmds)
    assert "sidechaincompress" not in joined_all_ff
    assert "silencedetect=noise=-38.0dB" in joined_all_ff
    assert "volume=volume='min(" in joined_all_ff and "if(lt(t," in joined_all_ff
    assert ":eval=frame" in joined_all_ff
    assert "amix=inputs=3:duration=longest:normalize=0" in joined_all_ff
    assert any("loudnorm=" in c and "print_format=json" in c for c in ff_cmds)
    assert any(
        "loudnorm=" in c and "measured_I=-21.40" in c and "linear=true" in c and "-ar 48000" in c
        for c in ff_cmds
    )

    # 3. Solo mono narration enforces dual_mono=true on both Pass 1 and Pass 2 loudnorm!
    out_mono = tmp_path / "solo_narration.mp4"
    mono_runner = FakeCLIRunner()
    rc_mono = video_gen.main(
        [
            "--prompt",
            "Presenter speaking on camera",
            "--duration",
            "10",
            "--audio-mode",
            "narration",
            "--voice-track",
            str(FIXTURES_GOOD / "tiny_tone.wav"),
            "--creative-stack",
            "off",
            "--raw-prompt",
            "--output",
            str(out_mono),
        ],
        runner=mono_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_mono == 0
    mono_ff = [" ".join(c) for c in mono_runner.calls if Path(c[0]).name == "ffmpeg"]
    assert any("dual_mono=true:print_format=json" in c for c in mono_ff)
    assert any("dual_mono=true:linear=true" in c and "-ar 48000" in c for c in mono_ff)

    # 4. Companion audio-gen CLI delegation (--narration-text + --bgm-prompt)
    stub_audio_gen = tmp_path / "audio_gen.py"
    stub_audio_gen.write_text("# stub\n", encoding="utf-8")
    out_delegated_aud = tmp_path / "delegated_audio.mp4"
    aud_del_runner = FakeCLIRunner()
    rc_aud_del = video_gen.main(
        [
            "--prompt",
            "Cloud dashboard demo",
            "--duration",
            "10",
            "--audio-mode",
            "full-mix",
            "--narration-text",
            "Deploy globally in seconds.",
            "--voice-name",
            "Kore",
            "--bgm-prompt",
            "Warm ambient synth pad",
            "--audio-gen-script",
            str(stub_audio_gen),
            "--creative-stack",
            "off",
            "--raw-prompt",
            "--output",
            str(out_delegated_aud),
        ],
        runner=aud_del_runner,
        which_fn=_all_tools_present,
    )
    _ = capsys.readouterr()
    assert rc_aud_del == 0
    ag_calls = [c for c in aud_del_runner.calls if len(c) > 1 and Path(c[1]).name == "audio_gen.py"]
    assert len(ag_calls) == 2
    assert "--mode" in ag_calls[0] and ag_calls[0][ag_calls[0].index("--mode") + 1] == "voice"
    assert "--voice" in ag_calls[0] and ag_calls[0][ag_calls[0].index("--voice") + 1] == "Kore"
    assert "--mode" in ag_calls[1] and ag_calls[1][ag_calls[1].index("--mode") + 1] == "bgm"


def test_bare_key_secret_redaction_preserves_short_words(tmp_path: Path) -> None:
    emit_py = tmp_path / "emit_bare_key.py"
    secret_tok = "SecretCredentialToken9876543210"
    emit_py.write_text(
        "import sys\n"
        f'sys.stdout.write(\'{{"key": "{secret_tok}", "status": "err"}}\\n\')\n'
        f'sys.stderr.write("auth failed key={secret_tok} while parsing key=char\\n")\n'
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    res = video_post.default_runner([sys.executable, str(emit_py)])
    assert res.returncode == 1
    assert secret_tok not in res.stderr
    assert secret_tok not in res.stdout
    assert "key=[REDACTED:Credential key assignment]" in res.stderr
    assert "key=char" in res.stderr
    redacted_json = json.loads(res.stdout)
    assert redacted_json["key"] == "[REDACTED:Credential key assignment]"

    # JSON null/false/numeric literals stay valid JSON and unredacted
    json_edge = json.dumps({"key": None, "api_key": False, "nested": {"api_key": 42, "key": secret_tok}})
    parsed_edge = json.loads(video_post.redact_secrets(json_edge))
    assert parsed_edge["key"] is None
    assert parsed_edge["api_key"] is False
    assert parsed_edge["nested"]["api_key"] == 42
    assert parsed_edge["nested"]["key"] == "[REDACTED:Credential key assignment]"

    # Verify loudnorm_pass1_voice_mono.json fixture parsing + non-finite rejection
    pass1_raw = (FIXTURES_GOOD / "loudnorm_pass1_voice_mono.json").read_text(encoding="utf-8")
    p1_stats = video_post.parse_loudnorm_pass1_json(f"[Parsed_loudnorm_0 @ 0x1] \n{pass1_raw}\n")
    assert p1_stats["input_i"] == -21.4
    p2_flt = video_post.build_loudnorm_pass2_filter(p1_stats, lufs_target=-14.0, dual_mono=True)
    assert "measured_I=-21.40" in p2_flt and "dual_mono=true:linear=true" in p2_flt

    with pytest.raises(RuntimeError, match="non-finite"):
        video_post.parse_loudnorm_pass1_json('{"input_i": "-inf", "input_tp": "-inf"}')

    # Verify 120-phrase ducking expression stays shallow via balanced binary min() tree
    windows_120 = [(float(i * 10), float(i * 10 + 4)) for i in range(120)]
    expr_120 = video_post.build_duck_volume_expression(windows_120, duck_db=14.0, attack_s=0.0, release_s=0.0)
    max_depth = 0
    cur_depth = 0
    for ch in expr_120:
        if ch == "(":
            cur_depth += 1
            max_depth = max(max_depth, cur_depth)
        elif ch == ")":
            cur_depth -= 1
    assert cur_depth == 0
    assert max_depth <= 20

    # Verify leading-dash CWE-88 prompt protection on gemini-api video
    dash_cfg = video_gen.VideoJobConfig(prompt="-o /tmp/hijack --raw-prompt", raw_prompt=True)
    dash_cmd, _ = video_gen.build_video_cli_command(
        config=dash_cfg,
        prompt_text=dash_cfg.prompt,
        ordered_inputs=[],
        candidate_out=tmp_path / "cand.mp4",
        model_id=video_gen.PRIMARY_VIDEO_MODEL,
        previous_interaction_id=None,
    )
    assert not dash_cmd[2].startswith("-")
    assert "-o /tmp/hijack" in dash_cmd[2]


def test_input_aliasing_max_attempts_duplicate_ac_and_two_way_contradiction_gates(
    tmp_path: Path,
) -> None:
    # 1. --output aliasing an input (--video or --voice-track) exits 2 before execution
    src_mp4 = tmp_path / "in_place.mp4"
    src_mp4.write_bytes(VALID_MP4_BYTES)
    assert (
        video_gen.main(
            ["--prompt", "Edit clip", "--video", str(src_mp4), "--output", str(src_mp4)],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )
    assert src_mp4.is_file()

    # 2. --max-attempts > 10 exits 2
    assert (
        video_gen.main(
            ["--prompt", "Hero clip", "--max-attempts", "99", "--dry-run"],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )

    # 3. Duplicate AC IDs in --spec-file exit 2
    dup_spec = json.loads((FIXTURES_GOOD / "spec_single_shot_10s.json").read_text(encoding="utf-8"))
    dup_spec["acceptance_criteria"].append(dict(dup_spec["acceptance_criteria"][0]))
    dup_spec_file = tmp_path / "dup_ac.json"
    dup_spec_file.write_text(json.dumps(dup_spec), encoding="utf-8")
    assert (
        video_gen.main(
            ["--spec-file", str(dup_spec_file), "--dry-run", "-o", str(tmp_path / "d.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )

    # 4. Two-way contradiction: overall_passed=False with all criteria passing fails closed
    base_spec = _load_json(FIXTURES_GOOD / "spec_single_shot_10s.json")
    contradict_verdict = {
        "overall_passed": False,
        "criteria_results": [
            {
                "id": ac["id"],
                "passed": True,
                "observed_evidence": "Looks fine.",
                "fix_instruction": "",
            }
            for ac in base_spec["acceptance_criteria"]
        ],
    }
    validated = video_gen.validate_rubric_verdict(contradict_verdict, base_spec)
    assert validated["all_passed"] is False
    assert "self_contradictory_model_summary" in validated["validation_errors"]

    # 5. Duplicate criterion ID in judge output cannot overwrite a failed AC with a later pass!
    dup_judge_verdict = {
        "criteria_results": [
            {
                "id": base_spec["acceptance_criteria"][0]["id"],
                "passed": False,
                "observed_evidence": "Missing prompt subject.",
                "fix_instruction": "Fix subject.",
            },
            {
                "id": base_spec["acceptance_criteria"][0]["id"],
                "passed": True,
                "observed_evidence": "Actually looks ok.",
                "fix_instruction": "",
            },
            *[
                {
                    "id": ac["id"],
                    "passed": True,
                    "observed_evidence": "Ok.",
                    "fix_instruction": "",
                }
                for ac in base_spec["acceptance_criteria"][1:]
            ],
        ]
    }
    dup_validated = video_gen.validate_rubric_verdict(dup_judge_verdict, base_spec)
    assert dup_validated["all_passed"] is False
    assert any("duplicate_criterion_id" in e for e in dup_validated["validation_errors"])

    # 6. Non-finite float CLI and cue arguments (nan / inf / -inf) MUST exit 2 cleanly!
    for bad_float_argv in (
        ["--prompt", "T", "--crossfade-sec", "nan", "--dry-run"],
        ["--prompt", "T", "--crossfade-sec", "inf", "--dry-run"],
        ["--prompt", "T", "--duck-db", "nan", "--dry-run"],
        ["--prompt", "T", "--lufs-target", "-inf", "--dry-run"],
        ["--prompt", "T", "--lower-third", "Ada|Lead@nan-4.0", "--dry-run"],
        ["--prompt", "T", "--sfx-cue", f"{FIXTURES_GOOD / 'tiny_tone.wav'}@inf", "--dry-run"],
        ["--prompt", "T", "--sfx-cue", f"{FIXTURES_GOOD / 'tiny_tone.wav'}@1.0:nan", "--dry-run"],
    ):
        assert (
            video_gen.main(bad_float_argv, runner=FakeCLIRunner(), which_fn=_all_tools_present) == 2
        )

    nan_caps = tmp_path / "nan_caps.json"
    nan_caps.write_text(json.dumps([{"start": "nan", "end": 2.0, "text": "hi"}]), encoding="utf-8")
    assert (
        video_gen.main(
            ["--prompt", "T", "--captions-json", str(nan_caps), "--dry-run"],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        == 2
    )

    # 7. Delegate leaving no output (even with exit 0) falls back cleanly to standalone ffmpeg
    cs_home = tmp_path / "silent_fail_cs"
    vk_dir = cs_home / "skills" / "vidkit" / "scripts"
    sd_dir = cs_home / "skills" / "sound" / "scripts"
    vk_dir.mkdir(parents=True)
    sd_dir.mkdir(parents=True)
    for sc in (vk_dir / "captions.py", vk_dir / "motion.py", sd_dir / "mix.py"):
        sc.write_text("# noop\n", encoding="utf-8")

    base_fb_runner = FakeCLIRunner()

    def noop_delegate_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        if cmd[0] == sys.executable and Path(cmd[1]).name in ("captions.py", "motion.py", "mix.py"):
            return video_gen.CommandResult(0, "", "", tuple(cmd))  # exits 0 without writing -o!
        return base_fb_runner(cmd)

    cs_out = tmp_path / "delegate_fallback.mp4"
    rc_noop = video_gen.main(
        [
            "--prompt",
            "Walkthrough clip",
            "--duration",
            "10",
            "--audio-mode",
            "full-mix",
            "--voice-track",
            str(FIXTURES_GOOD / "tiny_tone.wav"),
            "--bgm-track",
            str(FIXTURES_GOOD / "tiny_tone.wav"),
            "--srt",
            str(FIXTURES_GOOD / "sample_captions.srt"),
            "--title-card",
            "Intro",
            "--creative-stack",
            str(cs_home),
            "--raw-prompt",
            "--output",
            str(cs_out),
        ],
        runner=noop_delegate_runner,
        which_fn=_all_tools_present,
    )
    assert rc_noop == 0
    noop_rep = _load_json(Path(f"{cs_out}.report.json"))
    assert noop_rep["post_processing"]["audio_renderer"] == "ffmpeg:standalone_2pass_loudnorm"
    assert noop_rep["post_processing"]["caption_renderer"].startswith("ffmpeg:")
    assert noop_rep["post_processing"]["card_renderer"].startswith("ffmpeg:")


def test_real_ffmpeg_200_speech_windows_loudnorm_and_xfade_integration(tmp_path: Path) -> None:
    real_ff = video_post.resolve_ffmpeg_binary("ffmpeg", env={})
    real_fp = video_post.resolve_ffmpeg_binary("ffprobe", env={})
    if not real_ff or not real_fp:
        pytest.skip("Real ffmpeg/ffprobe not installed on host")

    # 1. 200 speech windows compile & execute cleanly in real FFmpeg av_expr_parse
    windows_200 = [(float(i * 2), float(i * 2 + 1)) for i in range(200)]
    expr_200 = video_post.build_duck_volume_expression(windows_200, duck_db=14.0)
    res_200 = video_post.default_runner(
        [
            real_ff,
            "-hide_banner",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-filter_complex",
            f"[0:a]volume=volume='{expr_200}':eval=frame[out]",
            "-map",
            "[out]",
            "-f",
            "null",
            "-",
        ]
    )
    assert res_200.returncode == 0

    # 2. Synthesize two real 2.0s MP4 clips + voice/BGM/SFX WAVs and run real xfade + 2-pass loudnorm!
    seg1 = tmp_path / "seg1.mp4"
    seg2 = tmp_path / "seg2.mp4"
    for idx, seg_p in enumerate((seg1, seg2), start=1):
        r_seg = video_post.default_runner(
            [
                real_ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=navy:s=320x180:r=24:d=2.0",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={300 + idx * 100}:sample_rate=48000:duration=2.0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(seg_p),
            ]
        )
        assert r_seg.returncode == 0

    stitched = tmp_path / "stitched_real.mp4"
    st_meta = video_timeline.stitch_segments(
        [seg1, seg2],
        [2.0, 2.0],
        stitched,
        crossfade_sec=0.5,
        include_audio=True,
        ffmpeg_bin=real_ff,
        runner=video_post.default_runner,
    )
    assert st_meta["stitcher"] == "ffmpeg_xfade_acrossfade"
    assert stitched.is_file() and stitched.stat().st_size > 500

    voice_wav = tmp_path / "voice_real.wav"
    bgm_wav = tmp_path / "bgm_real.wav"
    for freq, out_w in ((520, voice_wav), (220, bgm_wav)):
        r_w = video_post.default_runner(
            [
                real_ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={freq}:sample_rate=48000:duration=3.5",
                "-af",
                "volume=-12dB",
                str(out_w),
            ]
        )
        assert r_w.returncode == 0

    mastered_mp4 = tmp_path / "mastered_real.mp4"
    mix_rep = video_post.apply_audio_mix_and_master(
        stitched,
        mastered_mp4,
        audio_mode="full-mix",
        target_duration_s=3.5,
        voice_track=str(voice_wav),
        bgm_track=str(bgm_wav),
        duck_db=14.0,
        lufs_target=-14.0,
        creative_stack=video_post.CreativeStackInfo(mode="off", enabled=False, source="off"),
        ffmpeg_bin=real_ff,
        ffprobe_bin=real_fp,
        runner=video_post.default_runner,
    )
    assert mix_rep["applied"] is True
    assert mix_rep["sample_rate_hz"] == 48000
    assert mastered_mp4.is_file() and mastered_mp4.stat().st_size > 1000


@pytest.mark.parametrize(
    "card_text",
    [
        "50% OFF",
        "C:\\path\\to\\file",
        "a,b;[c]=d",
        "it's 100% #{var}",
    ],
)
def test_drawtext_escaping_and_textfile_special_characters(
    tmp_path: Path, card_text: str
) -> None:
    # 1. Unit verification of two-level _escape_drawtext + path escaping helpers
    escaped = video_post._escape_drawtext(card_text)
    assert "%" not in escaped or "\\%" in escaped
    assert "\n" not in escaped
    nasty_dir = tmp_path / "it's a, [dir];1"
    nasty_dir.mkdir(parents=True, exist_ok=True)
    esc_path = video_post._ffmpeg_filter_escape_path(nasty_dir / "note.txt")
    assert "\\\\\\'" in esc_path
    assert "\\," in esc_path and "\\;" in esc_path and "\\ " in esc_path

    # 2. FakeCLIRunner verifies apply_post_text_and_cards uses textfile= + expansion=none
    in_mp4 = tmp_path / "in.mp4"
    out_mp4 = tmp_path / "out.mp4"
    in_mp4.write_bytes(VALID_MP4_BYTES)
    captured_cmds: list[tuple[str, ...]] = []

    def drawtext_stub_runner(cmd: Sequence[str]) -> video_gen.CommandResult:
        t_cmd = tuple(str(x) for x in cmd)
        captured_cmds.append(t_cmd)
        if "-filters" in t_cmd:
            return video_gen.CommandResult(
                0, "Filters:\n .. drawtext V->V Draw text.\n", "", t_cmd
            )
        Path(t_cmd[-1]).write_bytes(VALID_MP4_BYTES)
        return video_gen.CommandResult(0, "", "", t_cmd)

    rep = video_post.apply_post_text_and_cards(
        in_mp4,
        out_mp4,
        video_duration_s=5.0,
        title_card=card_text,
        creative_stack=video_post.CreativeStackInfo(mode="off", enabled=False, source="off"),
        ffmpeg_bin="/usr/local/bin/ffmpeg",
        runner=drawtext_stub_runner,
    )
    assert rep["card_renderer"] == "ffmpeg:drawtext_filter"
    dt_cmds = [c for c in captured_cmds if "-vf" in c]
    assert len(dt_cmds) == 1
    vf = dt_cmds[0][dt_cmds[0].index("-vf") + 1]
    assert "textfile=" in vf
    assert ":expansion=none:" in vf

    # 3. Real FFmpeg execution when ffmpeg-full drawtext is installed on host
    real_ff = video_post.resolve_ffmpeg_binary("ffmpeg", env={})
    if real_ff and video_post.probe_ffmpeg_capabilities(real_ff, runner=video_post.default_runner)["drawtext"]:
        real_src = tmp_path / "real_src.mp4"
        real_dst = tmp_path / "real_dst.mp4"
        r_make = video_post.default_runner(
            [
                real_ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x180:r=24:d=2.0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(real_src),
            ]
        )
        assert r_make.returncode == 0
        real_rep = video_post.apply_post_text_and_cards(
            real_src,
            real_dst,
            video_duration_s=2.0,
            title_card=card_text,
            creative_stack=video_post.CreativeStackInfo(mode="off", enabled=False, source="off"),
            ffmpeg_bin=real_ff,
            runner=video_post.default_runner,
        )
        assert real_rep["card_renderer"] == "ffmpeg:drawtext_filter"
        assert real_dst.is_file() and real_dst.stat().st_size > 500


def test_storyboard_stitch_uses_probed_provenance_duration_for_xfade_offsets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for name in ("anchor.png", "frame_01.png", "frame_02.png", "frame_03.png"):
        (frames_dir / name).write_bytes(TINY_PNG_BYTES)
    sb_manifest = tmp_path / "sb.json"
    sb_manifest.write_text(
        json.dumps(_load_json(FIXTURES_GOOD / "keyframes_manifest_sample.json")),
        encoding="utf-8",
    )

    # Manifest frames have planned durations [6s, 6s], whereas probed segments render slightly short at 5.40s!
    probe_short = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_short["streams"][0]["duration"] = "5.400000"
    probe_short["format"]["duration"] = "5.400000"
    probe_concat = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_concat["streams"][0]["duration"] = "10.300000"
    probe_concat["format"]["duration"] = "10.300000"

    runner = FakeCLIRunner(ffprobe_payload=probe_short, concat_ffprobe_payload=probe_concat)
    out_mp4 = tmp_path / "probed_sb.mp4"
    rc = video_gen.main(
        [
            "--storyboard",
            str(sb_manifest),
            "--crossfade-sec",
            "0.5",
            "--raw-prompt",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
    )
    cap_ok = capsys.readouterr()
    assert rc == 0, f"stdout={cap_ok.out}\nstderr={cap_ok.err}"
    xfade_calls = [
        c for c in runner.calls if Path(c[0]).name == "ffmpeg" and "-filter_complex" in c
    ]
    assert len(xfade_calls) == 1
    fc_str = xfade_calls[0][xfade_calls[0].index("-filter_complex") + 1]
    # Probed 5.400s - 0.500s crossfade = offset=4.900 (NOT planned 6.000 - 0.500 = 5.500!)
    assert "offset=4.900" in fc_str
    assert "offset=5.500" not in fc_str


# ---------------------------------------------------------------------------
# pr-guardian Round 1 Regression Coverage (R-001..R-004)
# ---------------------------------------------------------------------------


def test_r001_single_segment_storyboard_runs_post_processing_and_forwards_audio_gen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frame_png = tmp_path / "hero.png"
    frame_png.write_bytes(TINY_PNG_BYTES)
    manifest = {
        "aspect_ratio": "9:16",
        "frames": [{"path": str(frame_png), "caption": "Vertical reveal", "duration_s": 6}],
    }
    sb_path = tmp_path / "single_sb.json"
    sb_path.write_text(json.dumps(manifest), encoding="utf-8")

    srt_file = tmp_path / "captions.srt"
    srt_file.write_text(
        "1\n00:00:00,000 --> 00:00:02,500\nVertical reveal\n",
        encoding="utf-8",
    )

    fake_audio_gen = tmp_path / "audio_gen.py"
    fake_audio_gen.write_text("# stub audio-gen\n", encoding="utf-8")

    # 1. Forwarded audio_gen_script rejects missing companion pre-generation in storyboard mode
    out_missing = tmp_path / "missing_ag.mp4"
    rc_missing = video_gen.main(
        [
            "--storyboard",
            str(sb_path),
            "--storyboard-mode",
            "clips",
            "--narration-text",
            "Opening voiceover line",
            "--audio-mode",
            "narration",
            "--output",
            str(out_missing),
        ],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
        audio_gen_script=tmp_path / "does_not_exist_audio_gen.py",
    )
    err_missing = capsys.readouterr().err
    assert rc_missing == 2
    assert "companion audio-gen script not found" in err_missing.lower()

    # 2. Single-segment storyboard executes post-processing (audio synthesis + captions + title card)
    probe_9x16 = _load_json(FIXTURES_GOOD / "ffprobe_1080p_16x9_10s_audio.json")
    probe_9x16["streams"][0]["width"] = 1080
    probe_9x16["streams"][0]["height"] = 1920
    probe_9x16["streams"][0]["duration"] = "6.000000"
    probe_9x16["format"]["duration"] = "6.000000"
    runner = FakeCLIRunner(ffprobe_payload=probe_9x16)

    out_mp4 = tmp_path / "sb_single.mp4"
    rc = video_gen.main(
        [
            "--storyboard",
            str(sb_path),
            "--storyboard-mode",
            "clips",
            "--srt",
            str(srt_file),
            "--title-card",
            "Launch Day|Series A",
            "--narration-text",
            "Opening voiceover line",
            "--audio-mode",
            "narration",
            "--creative-stack",
            "off",
            "--no-verify",
            "--output",
            str(out_mp4),
        ],
        runner=runner,
        which_fn=_all_tools_present,
        audio_gen_script=fake_audio_gen,
    )
    cap_ok = capsys.readouterr()
    assert rc == 0, f"stdout={cap_ok.out}\nstderr={cap_ok.err}"
    assert out_mp4.is_file()
    assert (tmp_path / "sb_single_segments" / "segment_01.mp4").is_file()
    assert any(Path(c[1]) == fake_audio_gen for c in runner.calls if len(c) > 1)
    assert any("loudnorm" in " ".join(c) for c in runner.calls)
    assert any("-vf" in c for c in runner.calls)

    report = _load_json(Path(f"{out_mp4}.report.json"))
    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert report["post_processing"]["applied"] is True
    assert report["post_processing"]["card_renderer"] != "none"
    assert "concat_mechanical" in prov


def test_r001_multi_segment_storyboard_post_failure_emits_report_and_cleans_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for name in ("anchor.png", "frame_01.png", "frame_02.png", "frame_03.png"):
        (frames_dir / name).write_bytes(TINY_PNG_BYTES)
    sb_manifest = tmp_path / "sb_multi.json"
    sb_manifest.write_text(
        json.dumps(_load_json(FIXTURES_GOOD / "keyframes_manifest_sample.json")),
        encoding="utf-8",
    )

    out_mp4 = tmp_path / "multi_post_fail.mp4"
    cfg = video_gen.parse_job_config(
        ["--storyboard", str(sb_manifest), "--no-verify", "--output", str(out_mp4)]
    )

    def _boom_post(*_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], list[str]]:
        raise FileNotFoundError("ffmpeg audio mux dependency vanished")

    rc = video_timeline.run_storyboard_pipeline(
        cfg,
        validate_constraints_fn=lambda c: video_gen.validate_omni_constraints(c, env={}),
        run_single_segment_fn=video_gen.run_single_video_job,
        run_mechanical_check_fn=video_gen.run_mechanical_video_check,
        run_post_pipeline_fn=_boom_post,
        asset_cache_cls=video_gen.AssetUploadCache,
        valid_aspect_ratios=video_gen.VALID_ASPECT_RATIOS,
        runner=FakeCLIRunner(match_requested_duration=True),
        which_fn=_all_tools_present,
        sleep_fn=lambda _s: None,
        env={},
    )
    err = capsys.readouterr().err
    assert rc == 1
    assert "vanished" in err
    assert not out_mp4.exists()
    assert (tmp_path / "multi_post_fail_segments" / "stitched_raw.mp4").is_file()
    report = _load_json(Path(f"{out_mp4}.report.json"))
    prov = _load_json(Path(f"{out_mp4}.provenance.json"))
    assert report["status"] == "PARTIAL"
    assert prov["status"] == "PARTIAL"
    assert "vanished" in report["failure_reason"]


def _write_mono_sine_wav(path: Path, *, duration_s: float, sample_rate: int = 16000) -> None:
    total_frames = max(1, int(round(duration_s * sample_rate)))
    frames = bytearray()
    for i in range(total_frames):
        val = int(12000 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
        frames.extend(struct.pack("<h", val))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def test_r002_audio_mux_pads_shorter_audio_with_apad_and_preserves_video_duration(
    tmp_path: Path,
) -> None:
    # 1. Command invariant check (FakeCLIRunner): mux must apply '-af apad' before '-shortest'
    in_mp4 = tmp_path / "in.mp4"
    out_mp4 = tmp_path / "out.mp4"
    in_mp4.write_bytes(VALID_MP4_BYTES)
    short_wav = tmp_path / "short_voice.wav"
    _write_mono_sine_wav(short_wav, duration_s=1.5)

    runner = FakeCLIRunner()
    video_post.apply_audio_mix_and_master(
        in_mp4,
        out_mp4,
        audio_mode="narration",
        target_duration_s=8.0,
        voice_track=str(short_wav),
        creative_stack=video_post.CreativeStackInfo(mode="off", enabled=False, source="off"),
        ffmpeg_bin="/usr/local/bin/ffmpeg",
        ffprobe_bin="/usr/local/bin/ffprobe",
        runner=runner,
    )
    mux_cmds = [c for c in runner.calls if Path(c[0]).name == "ffmpeg" and "-shortest" in c]
    assert len(mux_cmds) == 1
    mux_cmd = mux_cmds[0]
    assert "-af" in mux_cmd
    af_idx = mux_cmd.index("-af")
    assert mux_cmd[af_idx + 1] == "apad"
    assert af_idx < mux_cmd.index("-shortest")

    # 2. Real FFmpeg execution when ffmpeg-full + ffprobe are installed on host
    real_ff = video_post.resolve_ffmpeg_binary("ffmpeg", env={})
    real_fp = video_post.resolve_ffmpeg_binary("ffprobe", env={})
    if real_ff and real_fp:
        real_src = tmp_path / "real_4s.mp4"
        real_dst = tmp_path / "real_muxed.mp4"
        r_make = video_post.default_runner(
            [
                real_ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=navy:s=320x180:r=24:d=4.0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(real_src),
            ]
        )
        assert r_make.returncode == 0
        rep = video_post.apply_audio_mix_and_master(
            real_src,
            real_dst,
            audio_mode="narration",
            target_duration_s=4.0,
            voice_track=str(short_wav),
            creative_stack=video_post.CreativeStackInfo(mode="off", enabled=False, source="off"),
            ffmpeg_bin=real_ff,
            ffprobe_bin=real_fp,
            runner=video_post.default_runner,
        )
        assert rep["applied"] is True
        assert real_dst.is_file()
        r_probe = video_post.default_runner(
            [
                real_fp,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(real_dst),
            ]
        )
        assert r_probe.returncode == 0
        probed = json.loads(r_probe.stdout)
        probed_dur = float(probed["format"]["duration"])
        assert probed_dur >= 3.7, f"Expected ~4.0s duration preserved via apad, got {probed_dur}s"
        codec_types = {s.get("codec_type") for s in probed.get("streams", [])}
        assert {"video", "audio"} <= codec_types


def test_r003_regenerated_prompt_rejection_when_scene_text_dropped() -> None:
    cfg = video_gen.VideoJobConfig(
        prompt="Wide drone pan over a rain-slicked neon storefront at midnight",
        scene_texts=["OPEN 24 HOURS"],
    )
    spec = video_gen.compile_visual_spec(cfg)
    assert spec["explicit_constraints"]["scene_texts"] == ["OPEN 24 HOURS"]

    dropped_regen = "Wide drone pan over a rain-slicked neon storefront glowing in twilight mist."
    preserved_regen = (
        'Wide drone pan over a rain-slicked neon storefront displaying "OPEN 24 HOURS" in crisp sans-serif light.'
    )
    assert video_gen._regenerated_prompt_preserves_directives(dropped_regen, spec) is False
    assert video_gen._regenerated_prompt_preserves_directives(preserved_regen, spec) is True

    rem_mode, next_prompt = video_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation={
            "all_passed": False,
            "failed_criteria": [
                {"id": "AC-2", "category": "TEXT_AC", "fix_instruction": "Render neon sign clearly."}
            ],
            "remediation_mode": "regenerate",
            "edit_delta_prompt": "",
            "regenerated_prompt": dropped_regen,
        },
        previous_response_id="resp_1",
        has_video_refs=False,
        spec=spec,
    )
    assert rem_mode == "regenerate"
    assert "OPEN 24 HOURS" in next_prompt
    assert next_prompt != dropped_regen


def test_r004_script_metadata_validation_and_continuity_crossfade_propagation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. Invalid metadata fields must fail pre-dry-run with exit 2
    bad_cases: list[tuple[str, dict[str, Any]]] = [
        ("bad_ar", {"aspect_ratio": "4:3", "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
        ("xml_style", {"style": "<IMAGE_REF id='1'>noir</IMAGE_REF>", "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
        ("xml_narr", {"narration_text": "Say <FIRST_FRAME> hi", "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
        ("bad_cont", {"continuity": "warp-jump", "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
        ("bool_xfade", {"crossfade_sec": True, "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
        ("high_xfade", {"crossfade_sec": 5.0, "beats": [{"prompt": "Opening scene.", "duration_s": 8}]}),
    ]
    for idx, (tag, payload) in enumerate(bad_cases):
        s_path = tmp_path / f"{tag}.json"
        s_path.write_text(json.dumps(payload), encoding="utf-8")
        rc_bad = video_gen.main(
            ["--script", str(s_path), "--dry-run", "--output", str(tmp_path / f"out_{idx}.mp4")],
            runner=FakeCLIRunner(),
            which_fn=_all_tools_present,
        )
        _ = capsys.readouterr()
        assert rc_bad == 2, f"Expected exit 2 for invalid script metadata case '{tag}', got {rc_bad}"

    # 2. Valid script continuity + crossfade_sec + aspect_ratio propagate unless overridden on CLI
    good_script = tmp_path / "good_script.json"
    good_script.write_text(
        json.dumps(
            {
                "aspect_ratio": "9:16",
                "style": "crisp anamorphic lighting",
                "continuity": "scene-cuts",
                "crossfade_sec": 0.5,
                "beats": [
                    {"prompt": "Act 1 skyline reveal.", "duration_s": 10},
                    {"prompt": "Act 2 rooftop hero.", "duration_s": 10},
                ],
            }
        ),
        encoding="utf-8",
    )
    rc_prop = video_gen.main(
        ["--script", str(good_script), "--dry-run", "--output", str(tmp_path / "prop.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    out_prop = json.loads(capsys.readouterr().out)
    assert rc_prop == 0
    assert out_prop["timeline_plan"]["continuity"] == "scene-cuts"
    assert out_prop["timeline_plan"]["crossfade_sec"] == 0.5
    assert out_prop["timeline_plan"]["segments"][1]["chain_mode"] == "scene_cut_with_refs"

    # Explicit CLI flags override script continuity + crossfade_sec cleanly
    rc_ovr = video_gen.main(
        [
            "--script",
            str(good_script),
            "--continuity",
            "extend-blocks",
            "--crossfade-sec",
            "0.25",
            "--dry-run",
            "--output",
            str(tmp_path / "ovr.mp4"),
        ],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
    )
    out_ovr = json.loads(capsys.readouterr().out)
    assert rc_ovr == 0
    assert out_ovr["timeline_plan"]["continuity"] == "extend-blocks"
    assert out_ovr["timeline_plan"]["crossfade_sec"] == 0.25

    # 3. Post-merge validation enforces narration conflicts and missing audio-gen pre-dry-run (exit 2)
    fake_audio_gen = tmp_path / "audio_gen.py"
    fake_audio_gen.write_text("# stub audio-gen\n", encoding="utf-8")
    narr_script = tmp_path / "narrated_script.json"
    narr_script.write_text(
        json.dumps(
            {
                "narration_text": "Introducing the all-new workflow engine.",
                "beats": [
                    {"prompt": "Beat 1 dashboard reveal.", "duration_s": 8},
                    {"prompt": "Beat 2 deploy button.", "duration_s": 8},
                ],
            }
        ),
        encoding="utf-8",
    )
    rc_silent_conflict = video_gen.main(
        ["--script", str(narr_script), "--silent", "--dry-run", "--output", str(tmp_path / "silent_c.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
        audio_gen_script=fake_audio_gen,
    )
    err_silent = capsys.readouterr().err
    assert rc_silent_conflict == 2
    assert "--audio-mode silent" in err_silent

    rc_missing_ag = video_gen.main(
        ["--script", str(narr_script), "--dry-run", "--output", str(tmp_path / "missing_ag_s.mp4")],
        runner=FakeCLIRunner(),
        which_fn=_all_tools_present,
        audio_gen_script=tmp_path / "missing_audio_gen.py",
    )
    err_ag = capsys.readouterr().err
    assert rc_missing_ag == 2
    assert "audio-gen" in err_ag.lower()
