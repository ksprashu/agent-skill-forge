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

"""Arbitrary-duration multi-segment timeline planner, ``--script <json|md>`` beat
parser, boundary-keyframe continuity chainer, ``image-gen`` keyframe orchestrator,
and ``ffmpeg`` concat / ``xfade``+``acrossfade`` stitcher for ``skills/video-gen``.

100% Python 3.12 standard library (Engineering Standard S1-S9, V1-V6):
  * Compiles ``timeline_plan.json`` for any ``--duration > 15`` (``3s..3600s+``)
    or multi-beat ``--script <json|md>`` into ``5..15s`` (or ``5..10s`` interpolated /
    extended) segments compensating for ``--crossfade-sec * (N - 1)`` overlap so
    stitched duration lands within ``max(1.5s, 0.05 * target_duration)``.
  * Enforces magic-byte image validation on persistent ``--image-ref`` anchors
    (``<= 6``) and extracted boundary frames (``ffmpeg -sseof -0.05 -i seg.mp4 -frames:v 1``).
  * Verifies & retries each segment independently before advancing; fails closed
    (``PARTIAL`` / ``FAILED_VERIFICATION``, ``exit 1``) if any segment fails or
    ``ffmpeg`` is missing for multi-segment stitching.

Audit scope & unchecked-surface reporting (Engineering Standard V3 / V5):
  * ``validate_image_file_header`` inspects PNG (``IHDR`` + CRC32), JPEG (``SOF``),
    and WebP (``VP8*``) binary headers; it does not decode full pixel scanlines.
  * Final stitched MP4 files are audited via Stage 3 ``ffprobe`` stream & duration
    checks (or recorded in ``unchecked_surfaces`` when ``ffprobe`` is absent).
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from video_post import (  # noqa: E402
    CommandResult,
    RunnerCallable,
    WhichCallable,
    contract_home,
    is_files_uri,
    redact_secrets,
    resolve_ffmpeg_binary,
    safe_ffmpeg_path,
    utc_now_iso,
    validate_safe_local_file,
)

VALID_ASPECT_RATIOS: tuple[str, ...] = ("16:9", "9:16")

VALID_CONTINUITY_MODES: tuple[str, ...] = (
    "keyframe-chain",
    "scene-cuts",
    "extend-blocks",
)

MIN_SEGMENT_S = 5
MIN_EXPLICIT_BEAT_S = 3
MAX_STANDARD_SEGMENT_S = 15
MAX_INTERPOLATED_SEGMENT_S = 10
MAX_CROSSFADE_S = 2.0
MAX_EXTEND_BLOCK_CUMULATIVE_S = 25
MAX_IMAGE_REFS = 6

FORBIDDEN_LEGACY_XML_TAGS: tuple[str, ...] = (
    "<FIRST_FRAME>",
    "</FIRST_FRAME>",
    "<LAST_FRAME>",
    "</LAST_FRAME>",
    "<IMAGE_REF",
    "</IMAGE_REF",
    "<VIDEO_REF",
)

_JPEG_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)

_STATUS_SEVERITY: dict[str, int] = {
    "FAILED_VERIFICATION": 4,
    "REJECTED": 4,
    "PARTIAL": 3,
    "UNVERIFIED_OVERRIDE": 2,
    "MECHANICAL_ONLY": 1,
    "VERIFIED": 0,
}


# ---------------------------------------------------------------------------
# Image Header Validation & Manifest Asset Resolution
# ---------------------------------------------------------------------------


def validate_image_file_header(path: Path) -> None:
    """Verify a local image file has a valid PNG (with IHDR CRC32), JPEG SOF, or WebP header."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read image '{contract_home(path)}': {exc}") from exc
    size = len(data)
    if size < 16:
        raise ValueError(f"Image '{contract_home(path)}' is empty or truncated ({size} bytes).")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if size < 33:
            raise ValueError(f"Truncated PNG header in '{contract_home(path)}'.")
        ihdr_len = struct.unpack(">I", data[8:12])[0]
        if data[12:16] != b"IHDR" or ihdr_len != 13:
            raise ValueError(f"Invalid PNG IHDR chunk in '{contract_home(path)}'.")
        expected_crc = struct.unpack(">I", data[29:33])[0]
        actual_crc = zlib.crc32(data[12:29]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"Corrupt PNG IHDR CRC32 in '{contract_home(path)}'.")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid PNG dimensions in '{contract_home(path)}'.")
        return
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos < size:
            if data[pos] != 0xFF:
                break
            while pos < size and data[pos] == 0xFF:
                pos += 1
            if pos >= size:
                break
            marker = data[pos]
            pos += 1
            if marker in (0xD9, 0xDA):
                break
            if marker in (0x00, 0x01) or (0xD0 <= marker <= 0xD8):
                continue
            if pos + 2 > size:
                break
            seg_len = struct.unpack(">H", data[pos : pos + 2])[0]
            if seg_len < 2 or pos + seg_len > size:
                break
            if marker in _JPEG_SOF_MARKERS and seg_len >= 7:
                height, width = struct.unpack(">HH", data[pos + 3 : pos + 7])
                if width > 0 and height > 0:
                    return
            pos += seg_len
        raise ValueError(f"Invalid or corrupt JPEG SOF header in '{contract_home(path)}'.")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and size >= 20:
        if data[12:16] in (b"VP8 ", b"VP8L", b"VP8X"):
            return
    raise ValueError(f"File '{contract_home(path)}' is not a valid PNG, JPEG, or WebP image.")


def resolve_manifest_asset(
    raw_path: str, manifest_dir: Path, *, require_image: bool = True
) -> Path | str:
    """Resolve manifest asset strictly within `manifest_dir` (or files/<id> URI) and verify header."""
    cleaned = raw_path.strip()
    if not cleaned:
        raise ValueError("Empty asset path in storyboard/script manifest.")
    if is_files_uri(cleaned) and not (manifest_dir / cleaned).exists():
        return cleaned
    manifest_root = manifest_dir.resolve()
    candidate = Path(cleaned)
    resolved = (candidate if candidate.is_absolute() else (manifest_root / candidate)).resolve()
    if not resolved.is_relative_to(manifest_root):
        raise ValueError(
            f"Storyboard asset path '{raw_path}' escapes manifest directory '{contract_home(manifest_root)}'."
        )
    if not resolved.is_file():
        raise ValueError(f"Storyboard asset file not found: {contract_home(resolved)}")
    if require_image:
        validate_image_file_header(resolved)
    return resolved


# ---------------------------------------------------------------------------
# Companion `image_gen.py` Keyframe Synthesis Delegation
# ---------------------------------------------------------------------------


def build_keyframe_commands(
    config: Any,
    *,
    output_path: Path,
    image_gen_script: Path,
) -> tuple[list[list[str]], Path, Path | None]:
    """Build deterministic `image_gen.py` argv vectors for `--synthesize-keyframes` (S7)."""
    frame_size = "2K" if config.resolution in ("1080p", "4k") else "1K"
    keyframes_dir = output_path.parent / f"{output_path.stem}_keyframes"
    start_png = keyframes_dir / "start_frame.png"

    start_prompt = (
        f"Opening keyframe still for video scene: {config.prompt.strip()}"
        if config.synthesize_keyframes == "start-end"
        else config.prompt.strip()
    )
    start_cmd: list[str] = [
        sys.executable,
        str(image_gen_script),
        "--prompt",
        start_prompt,
        "--ar",
        config.aspect_ratio,
        "--size",
        frame_size,
        "--output",
        str(start_png),
    ]
    if config.style:
        start_cmd.extend(["--style", config.style])
    for ref in config.image_refs:
        start_cmd.extend(["-r", ref])
    if config.raw_prompt:
        start_cmd.append("--raw-prompt")
    if config.no_verify:
        start_cmd.append("--no-verify")

    if config.synthesize_keyframes != "start-end":
        return [start_cmd], start_png, None

    end_png = keyframes_dir / "end_frame.png"
    end_prompt = (
        config.end_frame_prompt.strip()
        if config.end_frame_prompt
        else (
            f"Final concluding keyframe still matching exact character, lighting, and environment "
            f"identity from the reference start frame: {config.prompt.strip()}"
        )
    )
    end_cmd: list[str] = [
        sys.executable,
        str(image_gen_script),
        "--prompt",
        end_prompt,
        "--ar",
        config.aspect_ratio,
        "--size",
        frame_size,
        "-r",
        str(start_png),
    ]
    for ref in config.image_refs:
        end_cmd.extend(["-r", ref])
    if config.style:
        end_cmd.extend(["--style", config.style])
    if config.raw_prompt:
        end_cmd.append("--raw-prompt")
    if config.no_verify:
        end_cmd.append("--no-verify")
    end_cmd.extend(["--output", str(end_png)])
    return [start_cmd, end_cmd], start_png, end_png


def resolve_synthesized_keyframe(stdout: str, requested: Path) -> Path:
    """Resolve real output path from `image_gen.py` JSON stdout after MIME-suffix rewrite (R1)."""
    req_root = requested.parent.resolve()
    text = (stdout or "").strip()
    if text:
        for candidate_text in (text, *reversed([ln.strip() for ln in text.splitlines() if ln.strip()])):
            try:
                payload = json.loads(candidate_text)
            except ValueError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("output"), str) and payload["output"].strip():
                raw_out = Path(payload["output"].strip())
                resolved_out = (raw_out if raw_out.is_absolute() else (Path.cwd() / raw_out)).resolve()
                if resolved_out.is_relative_to(req_root) and resolved_out.is_file():
                    return resolved_out
                break
    if requested.is_file():
        return requested
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    matches = sorted(
        p
        for p in requested.parent.glob(f"{requested.stem}.*")
        if p.is_file() and p.suffix.lower() in image_exts
    )
    if matches:
        return matches[0].resolve()
    return requested


def synthesize_keyframes_via_image_gen(
    config: Any,
    *,
    output_path: Path,
    image_gen_script: Path,
    runner: RunnerCallable,
) -> tuple[Path, Path | None]:
    """Delegate start (and optional style-locked end) keyframe synthesis to `image_gen.py`."""
    if not image_gen_script.is_file():
        raise FileNotFoundError(
            f"Companion skill script not found at '{contract_home(image_gen_script)}'. "
            "Install image-gen alongside video-gen via: "
            "npx skills add ksprashu/agent-skill-forge --skill image-gen "
            "(or python3 scripts/sync_skills.py --skills image-gen,video-gen)."
        )

    commands, start_png, end_png = build_keyframe_commands(
        config, output_path=output_path, image_gen_script=image_gen_script
    )
    start_png.parent.mkdir(parents=True, exist_ok=True)

    res_start = runner(commands[0])
    if res_start.returncode != 0:
        raise RuntimeError(
            f"image_gen.py failed synthesising start keyframe: {redact_secrets(res_start.stderr).strip()}"
        )
    actual_start = resolve_synthesized_keyframe(res_start.stdout, start_png)

    if len(commands) == 1:
        return actual_start, None

    end_cmd = list(commands[1])
    if "-r" in end_cmd:
        for idx, tok in enumerate(end_cmd):
            if tok == "-r" and idx + 1 < len(end_cmd) and end_cmd[idx + 1] == str(start_png):
                end_cmd[idx + 1] = str(actual_start)
                break

    res_end = runner(end_cmd)
    if res_end.returncode != 0:
        raise RuntimeError(
            f"image_gen.py failed synthesising end keyframe: {redact_secrets(res_end.stderr).strip()}"
        )
    assert end_png is not None
    actual_end = resolve_synthesized_keyframe(res_end.stdout, end_png)
    return actual_start, actual_end


# ---------------------------------------------------------------------------
# `--script <json|md>` Parser & Multi-Segment Duration Decomposition
# ---------------------------------------------------------------------------

_MD_TIMECODE_BEAT_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)]|#{1,4})?\s*\[\s*(\d+(?::\d+)?)s?\s*-\s*(\d+(?::\d+)?)s?\s*\]\s*(.+)$"
)
_MD_PAREN_DUR_BEAT_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)]|#{1,4})?\s*(?:Beat\s+\d+\s*)?\(\s*(\d+)s\s*\)\s*:?\s*(.+)$",
    re.IGNORECASE,
)
_MD_BULLET_BEAT_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")


def _parse_clock_s(token: str) -> int:
    cleaned = token.strip().rstrip("s")
    if ":" in cleaned:
        parts = [int(p) for p in cleaned.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return int(float(cleaned))


def _check_no_legacy_xml(text: str, *, label: str) -> None:
    lowered = text.lower()
    for bad in FORBIDDEN_LEGACY_XML_TAGS:
        if bad.lower() in lowered:
            raise ValueError(
                f"Deprecated XML media tag '{bad}' detected in {label}. "
                "Use natural-language bindings instead."
            )


def _validate_script_metadata(
    doc: Mapping[str, Any],
    *,
    valid_aspect_ratios: Sequence[str] = VALID_ASPECT_RATIOS,
) -> dict[str, Any]:
    """Validate optional top-level JSON script metadata before merging onto runtime config."""
    meta: dict[str, Any] = {}
    if "style" in doc and doc["style"] is not None:
        val = doc["style"]
        if not isinstance(val, str) or not val.strip():
            raise ValueError("--script metadata 'style' must be a non-empty string.")
        _check_no_legacy_xml(val, label="--script metadata 'style'")
        meta["style"] = val.strip()

    if "aspect_ratio" in doc and doc["aspect_ratio"] is not None:
        val = doc["aspect_ratio"]
        if not isinstance(val, str) or val.strip() not in valid_aspect_ratios:
            raise ValueError(
                f"--script metadata 'aspect_ratio' must be one of {', '.join(valid_aspect_ratios)} (got {val!r})."
            )
        meta["aspect_ratio"] = val.strip()

    if "continuity" in doc and doc["continuity"] is not None:
        val = doc["continuity"]
        if not isinstance(val, str) or val.strip() not in VALID_CONTINUITY_MODES:
            raise ValueError(
                f"--script metadata 'continuity' must be one of {', '.join(VALID_CONTINUITY_MODES)} (got {val!r})."
            )
        meta["continuity"] = val.strip()

    if "crossfade_sec" in doc and doc["crossfade_sec"] is not None:
        val = doc["crossfade_sec"]
        if (
            isinstance(val, bool)
            or not isinstance(val, (int, float))
            or not math.isfinite(float(val))
            or float(val) < 0.0
            or float(val) > MAX_CROSSFADE_S
        ):
            raise ValueError(
                f"--script metadata 'crossfade_sec' must be a finite number between 0.0 and {MAX_CROSSFADE_S:.1f}s "
                f"(got {val!r})."
            )
        meta["crossfade_sec"] = float(val)

    if "narration_text" in doc and doc["narration_text"] is not None:
        val = doc["narration_text"]
        if not isinstance(val, str) or not val.strip():
            raise ValueError("--script metadata 'narration_text' must be a non-empty string.")
        _check_no_legacy_xml(val, label="--script metadata 'narration_text'")
        meta["narration_text"] = val.strip()

    return meta


def parse_script_file(
    script_path_raw: str,
    *,
    valid_aspect_ratios: Sequence[str] = VALID_ASPECT_RATIOS,
) -> dict[str, Any]:
    """Parse `--script <json|md>` into normalized beat dicts and optional metadata."""
    resolved = validate_safe_local_file(script_path_raw, label="--script")
    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"--script '{contract_home(resolved)}' is not valid UTF-8: {exc}") from exc

    stripped = raw_text.lstrip("\ufeff").strip()
    if not stripped:
        raise ValueError(f"--script '{contract_home(resolved)}' is empty.")

    script_dir = resolved.parent
    is_json = resolved.suffix.lower() == ".json" or stripped[0] in ("{", "[")

    if is_json:
        try:
            doc = json.loads(stripped)
        except ValueError as exc:
            raise ValueError(f"Invalid JSON in --script '{contract_home(resolved)}': {exc}") from exc

        meta: dict[str, Any] = {}
        if isinstance(doc, list):
            raw_beats = doc
        elif isinstance(doc, dict) and isinstance(doc.get("beats"), list):
            raw_beats = doc["beats"]
            meta = _validate_script_metadata(doc, valid_aspect_ratios=valid_aspect_ratios)
        else:
            raise ValueError(
                f"--script JSON '{contract_home(resolved)}' must be a list or object with 'beats'."
            )

        if not raw_beats:
            raise ValueError(f"--script '{contract_home(resolved)}' contains zero beats.")

        beats: list[dict[str, Any]] = []
        for idx, entry in enumerate(raw_beats, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"--script beat {idx} must be a JSON object.")
            prompt_val = entry.get("prompt")
            if not isinstance(prompt_val, str) or not prompt_val.strip():
                raise ValueError(f"--script beat {idx} missing non-empty 'prompt'.")
            _check_no_legacy_xml(prompt_val, label=f"--script beat {idx} prompt")

            dur_val = entry.get("duration_s")
            if dur_val is not None:
                if isinstance(dur_val, bool) or not isinstance(dur_val, int) or dur_val < MIN_EXPLICIT_BEAT_S:
                    raise ValueError(
                        f"--script beat {idx} 'duration_s' must be integer >= {MIN_EXPLICIT_BEAT_S} (got {dur_val!r})."
                    )

            scene_texts: list[str] = []
            raw_st = entry.get("scene_text")
            if isinstance(raw_st, str) and raw_st.strip():
                scene_texts.append(raw_st.strip())
            elif isinstance(raw_st, list):
                for st_item in raw_st:
                    if isinstance(st_item, str) and st_item.strip():
                        scene_texts.append(st_item.strip())

            first_f = None
            if entry.get("first_frame"):
                first_f = str(resolve_manifest_asset(str(entry["first_frame"]), script_dir, require_image=True))
            last_f = None
            if entry.get("last_frame"):
                last_f = str(resolve_manifest_asset(str(entry["last_frame"]), script_dir, require_image=True))

            beats.append(
                {
                    "prompt": prompt_val.strip(),
                    "duration_s": dur_val,
                    "scene_texts": scene_texts,
                    "narration": str(entry.get("narration") or "").strip(),
                    "first_frame": first_f,
                    "last_frame": last_f,
                }
            )
        return {"path": resolved, "metadata": meta, "beats": beats}

    # Markdown / plain-text beat script
    beats_md: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(stripped.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("#") and not _MD_PAREN_DUR_BEAT_RE.match(line) and not _MD_TIMECODE_BEAT_RE.match(line):
            # Top-level Markdown title/heading; skip unless it defines a timed beat
            continue
        m_tc = _MD_TIMECODE_BEAT_RE.match(line)
        if m_tc:
            t0 = _parse_clock_s(m_tc.group(1))
            t1 = _parse_clock_s(m_tc.group(2))
            if t1 <= t0 or (t1 - t0) < MIN_EXPLICIT_BEAT_S:
                raise ValueError(
                    f"--script line {line_no} timecode [{m_tc.group(1)}-{m_tc.group(2)}] must span >= {MIN_EXPLICIT_BEAT_S}s."
                )
            prompt_txt = m_tc.group(3).strip()
            _check_no_legacy_xml(prompt_txt, label=f"--script line {line_no}")
            beats_md.append(
                {
                    "prompt": prompt_txt,
                    "duration_s": t1 - t0,
                    "scene_texts": [],
                    "narration": "",
                    "first_frame": None,
                    "last_frame": None,
                }
            )
            continue

        m_dur = _MD_PAREN_DUR_BEAT_RE.match(line)
        if m_dur:
            dur_i = int(m_dur.group(1))
            if dur_i < MIN_EXPLICIT_BEAT_S:
                raise ValueError(f"--script line {line_no} beat duration ({dur_i}s) must be >= {MIN_EXPLICIT_BEAT_S}s.")
            prompt_txt = m_dur.group(2).strip()
            _check_no_legacy_xml(prompt_txt, label=f"--script line {line_no}")
            beats_md.append(
                {
                    "prompt": prompt_txt,
                    "duration_s": dur_i,
                    "scene_texts": [],
                    "narration": "",
                    "first_frame": None,
                    "last_frame": None,
                }
            )
            continue

        m_bul = _MD_BULLET_BEAT_RE.match(line)
        prompt_txt = m_bul.group(1).strip() if m_bul else line
        _check_no_legacy_xml(prompt_txt, label=f"--script line {line_no}")
        beats_md.append(
            {
                "prompt": prompt_txt,
                "duration_s": None,
                "scene_texts": [],
                "narration": "",
                "first_frame": None,
                "last_frame": None,
            }
        )

    if not beats_md:
        raise ValueError(f"--script Markdown '{contract_home(resolved)}' contains zero beats.")
    return {"path": resolved, "metadata": {}, "beats": beats_md}


def decompose_duration_into_segments(
    target_duration_s: int,
    *,
    crossfade_sec: float = 0.0,
    min_seg_s: int = MIN_SEGMENT_S,
    max_seg_s: int = MAX_STANDARD_SEGMENT_S,
    min_segments: int = 1,
) -> list[int]:
    """Partition `target_duration_s` into integer segments `d_i` in `[min_seg_s, max_seg_s]`
    such that `sum(d_i) - crossfade_sec * (N - 1)` matches `target_duration_s` within `<= 0.5s`.
    """
    if target_duration_s < MIN_EXPLICIT_BEAT_S:
        raise ValueError(f"target_duration_s must be >= {MIN_EXPLICIT_BEAT_S}s (got {target_duration_s}s).")
    if not math.isfinite(crossfade_sec) or crossfade_sec < 0.0 or crossfade_sec > MAX_CROSSFADE_S:
        raise ValueError(
            f"--crossfade-sec must be finite between 0.0 and {MAX_CROSSFADE_S:.1f}s (got {crossfade_sec}s)."
        )

    if target_duration_s <= max_seg_s and min_segments <= 1:
        return [int(target_duration_s)]

    eff_step = float(max_seg_s) - crossfade_sec
    n_lower = max(
        2,
        min_segments,
        int(math.ceil((float(target_duration_s) - crossfade_sec) / eff_step)),
    )

    best_n: int | None = None
    best_sum: int | None = None
    best_err = float("inf")

    for cand_n in range(n_lower, n_lower + 12):
        needed_sum = int(round(float(target_duration_s) + crossfade_sec * (cand_n - 1)))
        lo_bound = cand_n * min_seg_s
        hi_bound = cand_n * max_seg_s
        if needed_sum < lo_bound:
            needed_sum = lo_bound
        elif needed_sum > hi_bound:
            continue
        stitched = float(needed_sum) - crossfade_sec * (cand_n - 1)
        err = abs(stitched - float(target_duration_s))
        if err < best_err - 1e-9:
            best_err = err
            best_n = cand_n
            best_sum = needed_sum
            if err <= 1e-6:
                break

    if best_n is None or best_sum is None:
        best_n = n_lower
        best_sum = max(best_n * min_seg_s, min(best_n * max_seg_s, int(round(target_duration_s + crossfade_sec * (best_n - 1)))))

    base, rem = divmod(best_sum, best_n)
    return [base + (1 if idx < rem else 0) for idx in range(best_n)]


def _split_long_beat(duration_s: int, *, min_seg_s: int, max_seg_s: int) -> list[int]:
    if duration_s <= max_seg_s:
        return [max(MIN_EXPLICIT_BEAT_S, duration_s)]
    return decompose_duration_into_segments(
        duration_s,
        crossfade_sec=0.0,
        min_seg_s=min_seg_s,
        max_seg_s=max_seg_s,
    )


def compile_timeline_plan(
    config: Any,
    *,
    valid_aspect_ratios: Sequence[str] = VALID_ASPECT_RATIOS,
) -> dict[str, Any]:
    """Compile deterministic `timeline_plan.json` for `--duration > 15` or `--script`."""
    parsed_script: dict[str, Any] | None = None
    if config.script:
        parsed_script = parse_script_file(config.script, valid_aspect_ratios=valid_aspect_ratios)
    script_meta = dict(parsed_script["metadata"]) if parsed_script is not None else {}

    effective_continuity = (
        config.continuity
        if getattr(config, "_explicit_continuity", False)
        else str(script_meta.get("continuity") or config.continuity)
    )
    raw_meta_xfade = script_meta.get("crossfade_sec")
    effective_crossfade = (
        float(config.crossfade_sec)
        if getattr(config, "_explicit_crossfade", False)
        else float(raw_meta_xfade if raw_meta_xfade is not None else config.crossfade_sec)
    )

    if effective_continuity not in VALID_CONTINUITY_MODES:
        raise ValueError(
            f"Unsupported --continuity '{effective_continuity}'. Valid: {', '.join(VALID_CONTINUITY_MODES)}."
        )
    if (
        not math.isfinite(effective_crossfade)
        or effective_crossfade < 0.0
        or effective_crossfade > MAX_CROSSFADE_S
    ):
        raise ValueError(
            f"--crossfade-sec must be finite between 0.0 and {MAX_CROSSFADE_S:.1f}s "
            f"(got {effective_crossfade}s)."
        )

    is_interpolated = config.synthesize_keyframes == "start-end"
    max_seg_s = (
        MAX_INTERPOLATED_SEGMENT_S
        if (is_interpolated or effective_continuity == "extend-blocks")
        else MAX_STANDARD_SEGMENT_S
    )
    min_seg_s = MIN_SEGMENT_S

    raw_beats: list[dict[str, Any]] = []
    if parsed_script is not None:
        raw_beats = list(parsed_script["beats"])
    else:
        # Check if --prompt contains multiple `[start-end]` timecode beats spanning the timeline
        tc_matches = list(
            re.finditer(
                r"\[\s*(\d+(?::\d+)?)s?\s*-\s*(\d+(?::\d+)?)s?\s*\]\s*([^\[\n]+)",
                config.prompt,
            )
        )
        if len(tc_matches) >= 2:
            for m in tc_matches:
                t0 = _parse_clock_s(m.group(1))
                t1 = _parse_clock_s(m.group(2))
                if t1 > t0:
                    raw_beats.append(
                        {
                            "prompt": m.group(3).strip(),
                            "duration_s": max(MIN_EXPLICIT_BEAT_S, t1 - t0),
                            "scene_texts": list(config.scene_texts),
                            "narration": "",
                            "first_frame": None,
                            "last_frame": None,
                        }
                    )

    segments: list[dict[str, Any]] = []
    crossfade = effective_crossfade

    if raw_beats:
        all_have_dur = all(b.get("duration_s") is not None for b in raw_beats)
        if all_have_dur and not config._explicit_duration:
            expanded_beats: list[dict[str, Any]] = []
            for b in raw_beats:
                sub_durs = _split_long_beat(int(b["duration_s"]), min_seg_s=min_seg_s, max_seg_s=max_seg_s)
                for sub_i, sd in enumerate(sub_durs, start=1):
                    sub_prompt = (
                        b["prompt"]
                        if len(sub_durs) == 1
                        else f"{b['prompt']} (part {sub_i} of {len(sub_durs)})"
                    )
                    expanded_beats.append(
                        {
                            **b,
                            "prompt": sub_prompt,
                            "duration_s": sd,
                            "first_frame": b["first_frame"] if sub_i == 1 else None,
                            "last_frame": b["last_frame"] if sub_i == len(sub_durs) else None,
                        }
                    )
            target_duration_s = sum(int(b["duration_s"]) for b in expanded_beats)
            # Compensate for crossfade overlap across expanded beats so net stitched hits target_duration_s
            if crossfade > 0 and len(expanded_beats) > 1:
                extra_needed = int(round(crossfade * (len(expanded_beats) - 1)))
                idx_cursor = 0
                safety = 0
                while extra_needed > 0 and safety < 500:
                    safety += 1
                    cur_b = expanded_beats[idx_cursor % len(expanded_beats)]
                    if int(cur_b["duration_s"]) < max_seg_s:
                        cur_b["duration_s"] = int(cur_b["duration_s"]) + 1
                        extra_needed -= 1
                    idx_cursor += 1
                    if idx_cursor >= len(expanded_beats) * 2 and all(
                        int(x["duration_s"]) >= max_seg_s for x in expanded_beats
                    ):
                        break
            for s_idx, eb in enumerate(expanded_beats, start=1):
                segments.append(
                    {
                        "segment_index": s_idx,
                        "duration_s": int(eb["duration_s"]),
                        "prompt": eb["prompt"],
                        "scene_texts": list(eb.get("scene_texts") or []),
                        "first_frame": eb.get("first_frame"),
                        "last_frame": eb.get("last_frame"),
                    }
                )
        else:
            target_duration_s = (
                config.duration_s
                if config._explicit_duration
                else max(config.duration_s, len(raw_beats) * 8)
            )
            durs = decompose_duration_into_segments(
                target_duration_s,
                crossfade_sec=crossfade,
                min_seg_s=min_seg_s,
                max_seg_s=max_seg_s,
                min_segments=len(raw_beats),
            )
            for s_idx, seg_dur in enumerate(durs, start=1):
                beat_idx = min(len(raw_beats) - 1, int((s_idx - 1) * len(raw_beats) / len(durs)))
                b = raw_beats[beat_idx]
                segments.append(
                    {
                        "segment_index": s_idx,
                        "duration_s": seg_dur,
                        "prompt": b["prompt"],
                        "scene_texts": list(b.get("scene_texts") or []),
                        "first_frame": b.get("first_frame") if s_idx == 1 else None,
                        "last_frame": b.get("last_frame") if s_idx == len(durs) else None,
                    }
                )
    else:
        target_duration_s = int(config.duration_s)
        durs = decompose_duration_into_segments(
            target_duration_s,
            crossfade_sec=crossfade,
            min_seg_s=min_seg_s,
            max_seg_s=max_seg_s,
        )
        total_segs = len(durs)
        base_prompt = config.prompt.strip()
        for s_idx, seg_dur in enumerate(durs, start=1):
            if total_segs == 1:
                seg_prompt = base_prompt
            else:
                phase = (
                    "establishing opening action"
                    if s_idx == 1
                    else ("concluding resolution" if s_idx == total_segs else "continuous progression")
                )
                seg_prompt = (
                    f"Segment {s_idx} of {total_segs} ({phase}, maintaining seamless visual, lighting, "
                    f"and subject continuity): {base_prompt}"
                )
            segments.append(
                {
                    "segment_index": s_idx,
                    "duration_s": seg_dur,
                    "prompt": seg_prompt,
                    "scene_texts": list(config.scene_texts) if s_idx == 1 else [],
                    "first_frame": config.first_frame if s_idx == 1 else None,
                    "last_frame": config.last_frame if s_idx == total_segs else None,
                }
            )

    # Annotate continuity chain strategy and exact xfade offsets
    cumulative_raw = 0
    block_elapsed = 0
    for idx, seg in enumerate(segments):
        seg_dur = int(seg["duration_s"])
        if crossfade > 0 and len(segments) > 1 and seg_dur <= crossfade * 2.0:
            raise ValueError(
                f"Segment {idx + 1} duration ({seg_dur}s) is too short for --crossfade-sec {crossfade}s."
            )

        if idx == 0:
            seg["xfade_offset_s"] = None
            if config.synthesize_keyframes == "start-end":
                seg["chain_mode"] = "synthesized_start_end_keyframes"
            elif config.synthesize_keyframes == "start":
                seg["chain_mode"] = "synthesized_start_keyframe"
            elif seg.get("first_frame"):
                seg["chain_mode"] = "explicit_first_frame"
            else:
                seg["chain_mode"] = "seed"
            block_elapsed = seg_dur
        else:
            seg["xfade_offset_s"] = (
                round(float(cumulative_raw) - crossfade * idx, 3) if crossfade > 0 else None
            )
            if effective_continuity == "scene-cuts":
                seg["chain_mode"] = (
                    "synthesized_start_keyframe" if config.synthesize_keyframes else "scene_cut_with_refs"
                )
            elif effective_continuity == "extend-blocks":
                # Source clip passed to Omni --extend must be <= 15s and cumulative block <= 25..30s
                prev_dur = int(segments[idx - 1]["duration_s"])
                if (
                    segments[idx - 1]["chain_mode"] in ("seed", "block_boundary_first_frame")
                    and prev_dur <= MAX_STANDARD_SEGMENT_S
                    and (block_elapsed + seg_dur) <= MAX_EXTEND_BLOCK_CUMULATIVE_S
                    and seg_dur <= MAX_INTERPOLATED_SEGMENT_S
                ):
                    seg["chain_mode"] = "omni_extend_turn"
                    block_elapsed += seg_dur
                else:
                    seg["chain_mode"] = "block_boundary_first_frame"
                    block_elapsed = seg_dur
            else:
                if config.synthesize_keyframes == "start-end":
                    seg["chain_mode"] = "synthesized_start_end_keyframes"
                elif config.synthesize_keyframes == "start":
                    seg["chain_mode"] = "synthesized_start_keyframe"
                else:
                    seg["chain_mode"] = "extracted_boundary_frame"

        cumulative_raw += seg_dur

    effective_crossfade = crossfade if len(segments) > 1 else 0.0
    total_overlap = round(effective_crossfade * max(0, len(segments) - 1), 3)
    expected_stitched = round(float(cumulative_raw) - total_overlap, 3)
    tolerance_s = round(max(1.5, 0.05 * float(target_duration_s)), 3)

    plan: dict[str, Any] = {
        "schema_version": 1,
        "target_duration_s": int(target_duration_s),
        "continuity": effective_continuity,
        "crossfade_sec": effective_crossfade,
        "segment_count": len(segments),
        "raw_segment_sum_s": cumulative_raw,
        "total_overlap_s": total_overlap,
        "expected_stitched_duration_s": expected_stitched,
        "tolerance_s": tolerance_s,
        "persistent_image_refs_count": len(config.image_refs),
        "segments": segments,
    }
    if parsed_script is not None:
        plan["script_path"] = contract_home(parsed_script["path"])
        plan["script_metadata"] = parsed_script["metadata"]
    return plan


# ---------------------------------------------------------------------------
# Boundary Frame Extraction & Multi-Segment Stitching (`concat` / `xfade`)
# ---------------------------------------------------------------------------


def extract_boundary_frame(
    segment_mp4: Path,
    output_png: Path,
    *,
    ffmpeg_bin: str,
    runner: RunnerCallable,
) -> Path:
    """Extract segment's final rendered video frame via `ffmpeg -sseof -0.05` and validate PNG header."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    for sseof_val in ("-0.05", "-0.15"):
        cmd = [
            ffmpeg_bin,
            "-y",
            "-sseof",
            sseof_val,
            "-i",
            safe_ffmpeg_path(segment_mp4),
            "-frames:v",
            "1",
            safe_ffmpeg_path(output_png),
        ]
        res = runner(cmd)
        if res.returncode == 0 and output_png.is_file():
            validate_image_file_header(output_png)
            return output_png
    raise RuntimeError(
        f"Failed extracting valid boundary PNG frame from '{contract_home(segment_mp4)}'."
    )


def build_xfade_stitch_command(
    segment_paths: Sequence[Path],
    segment_durations_s: Sequence[float],
    output_path: Path,
    *,
    crossfade_sec: float,
    include_audio: bool,
    ffmpeg_bin: str,
) -> list[str]:
    """Build deterministic multi-input `xfade` (+ `acrossfade`) stitcher argv (`shell=False`)."""
    if len(segment_paths) < 2:
        raise ValueError("build_xfade_stitch_command requires at least 2 segment paths.")

    cmd: list[str] = [ffmpeg_bin, "-y"]
    for seg_p in segment_paths:
        cmd.extend(["-i", safe_ffmpeg_path(seg_p)])

    filter_parts: list[str] = []
    n = len(segment_paths)
    cum_dur = float(segment_durations_s[0])

    prev_v = "[0:v]"
    for idx in range(1, n):
        offset = max(0.0, cum_dur - crossfade_sec * idx)
        out_v = "[vout]" if idx == n - 1 else f"[vx{idx}]"
        filter_parts.append(
            f"{prev_v}[{idx}:v]xfade=transition=fade:duration={crossfade_sec:.3f}:offset={offset:.3f}{out_v}"
        )
        prev_v = out_v
        cum_dur += float(segment_durations_s[idx])

    if include_audio:
        prev_a = "[0:a]"
        for idx in range(1, n):
            out_a = "[aout]" if idx == n - 1 else f"[ax{idx}]"
            filter_parts.append(
                f"{prev_a}[{idx}:a]acrossfade=d={crossfade_sec:.3f}:c1=tri:c2=tri{out_a}"
            )
            prev_a = out_a

    cmd.extend(["-filter_complex", ";".join(filter_parts), "-map", "[vout]"])
    if include_audio:
        cmd.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"])
    else:
        cmd.append("-an")
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", safe_ffmpeg_path(output_path)])
    return cmd


def stitch_segments(
    segment_paths: Sequence[Path],
    segment_durations_s: Sequence[float],
    output_path: Path,
    *,
    crossfade_sec: float,
    include_audio: bool,
    ffmpeg_bin: str,
    runner: RunnerCallable,
) -> dict[str, Any]:
    """Stitch `segment_paths` into `output_path` via stream-copy `concat` or `xfade`+`acrossfade`."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if len(segment_paths) == 1:
        if segment_paths[0].resolve() != output_path.resolve():
            shutil.copy2(segment_paths[0], output_path)
        return {"stitcher": "single_segment_passthrough", "crossfade_sec": 0.0}

    if crossfade_sec > 0.0:
        cmd = build_xfade_stitch_command(
            segment_paths,
            segment_durations_s,
            output_path,
            crossfade_sec=crossfade_sec,
            include_audio=include_audio,
            ffmpeg_bin=ffmpeg_bin,
        )
        res = runner(cmd)
        if res.returncode != 0:
            if output_path.exists():
                output_path.unlink()
            raise RuntimeError(
                f"ffmpeg xfade/acrossfade stitch failed: {redact_secrets(res.stderr).strip()}"
            )
        return {"stitcher": "ffmpeg_xfade_acrossfade", "crossfade_sec": crossfade_sec}

    with tempfile.TemporaryDirectory(prefix="video-gen-concat-") as tmp_concat:
        concat_list = Path(tmp_concat) / "concat.txt"
        lines = ["file '" + safe_ffmpeg_path(p).replace("'", "'\\''") + "'" for p in segment_paths]
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        res = runner(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                safe_ffmpeg_path(concat_list),
                "-c",
                "copy",
                safe_ffmpeg_path(output_path),
            ]
        )
        if res.returncode != 0:
            if output_path.exists():
                output_path.unlink()
            raise RuntimeError(
                f"ffmpeg concat stitch failed: {redact_secrets(res.stderr).strip()}"
            )
    return {"stitcher": "ffmpeg_concat_demuxer", "crossfade_sec": 0.0}


def synthesize_timeline_keyframes(
    plan: Mapping[str, Any],
    config: Any,
    *,
    keyframes_dir: Path,
    image_gen_script: Path,
    runner: RunnerCallable,
) -> list[Path]:
    """Synthesize chained style-locked keyframes across `N` (or `N + 1` for `start-end`) beats."""
    if not image_gen_script.is_file():
        raise FileNotFoundError(
            f"Companion skill script not found at '{contract_home(image_gen_script)}'. "
            "Install image-gen alongside video-gen."
        )
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    frame_size = "2K" if config.resolution in ("1080p", "4k") else "1K"
    segments = list(plan["segments"])
    need_closing_frame = config.synthesize_keyframes == "start-end"
    total_frames = len(segments) + (1 if need_closing_frame else 0)

    emitted: list[Path] = []
    for f_idx in range(total_frames):
        target_png = keyframes_dir / f"chain_frame_{f_idx + 1:03d}.png"
        if f_idx < len(segments):
            prompt_text = f"Keyframe {f_idx + 1} for continuous video sequence: {segments[f_idx]['prompt']}"
        else:
            prompt_text = (
                config.end_frame_prompt.strip()
                if config.end_frame_prompt
                else f"Concluding final keyframe matching identity and lighting of prior frame: {segments[-1]['prompt']}"
            )

        cmd: list[str] = [
            sys.executable,
            str(image_gen_script),
            "--prompt",
            prompt_text,
            "--ar",
            config.aspect_ratio,
            "--size",
            frame_size,
        ]
        if emitted:
            cmd.extend(["-r", str(emitted[-1])])
        for ref in config.image_refs:
            cmd.extend(["-r", ref])
        if config.style:
            cmd.extend(["--style", config.style])
        if config.raw_prompt:
            cmd.append("--raw-prompt")
        if config.no_verify:
            cmd.append("--no-verify")
        cmd.extend(["--output", str(target_png)])

        res = runner(cmd)
        if res.returncode != 0:
            raise RuntimeError(
                f"image_gen.py failed synthesising timeline keyframe {f_idx + 1}: "
                f"{redact_secrets(res.stderr).strip()}"
            )
        actual_png = resolve_synthesized_keyframe(res.stdout, target_png)
        validate_image_file_header(actual_png)
        emitted.append(actual_png)
    return emitted


# ---------------------------------------------------------------------------
# Arbitrary-Length Timeline & Storyboard Execution Pipelines
# ---------------------------------------------------------------------------


def read_probed_segment_duration_s(
    segment_out: Path,
    planned_duration_s: float,
    *,
    unchecked: list[str] | None = None,
) -> tuple[dict[str, Any] | None, float]:
    """Read `<segment>.provenance.json`, merge `unchecked_surfaces`, and return actual probed duration."""
    seg_prov_path = Path(f"{segment_out}.provenance.json")
    probed_dur = float(planned_duration_s)
    if not seg_prov_path.is_file():
        return None, probed_dur
    p_doc = json.loads(seg_prov_path.read_text(encoding="utf-8"))
    if unchecked is not None:
        for surf in p_doc.get("unchecked_surfaces") or ():
            if isinstance(surf, str) and surf not in unchecked:
                unchecked.append(surf)
    mech_d = (p_doc.get("mechanical_verification") or {}).get("duration_s")
    if isinstance(mech_d, (int, float)) and not isinstance(mech_d, bool) and math.isfinite(mech_d) and mech_d > 0:
        probed_dur = float(mech_d)
    return p_doc, probed_dur


def _emit_partial_failure(
    output_path: Path,
    *,
    reason: str,
    plan_or_manifest_key: str,
    plan_or_manifest_val: Any,
    preserved_segments: Sequence[Path],
    segment_provenance: Sequence[dict[str, Any]],
    unchecked: Sequence[str],
    extra: Mapping[str, Any] | None = None,
    status: str = "PARTIAL",
    exit_code: int = 1,
) -> int:
    if output_path.exists():
        output_path.unlink()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "generated_at": utc_now_iso(),
        plan_or_manifest_key: plan_or_manifest_val,
        "output_path": contract_home(output_path),
        "preserved_segments": [contract_home(p) for p in preserved_segments],
        "segments": list(segment_provenance),
        "unchecked_surfaces": list(unchecked),
        "failure_reason": reason,
    }
    if extra:
        payload.update(extra)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{output_path}.provenance.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    Path(f"{output_path}.report.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"error: {reason}", file=sys.stderr)
    return exit_code


def run_timeline_pipeline(
    config: Any,
    *,
    run_single_segment_fn: Callable[..., int],
    run_mechanical_check_fn: Callable[..., tuple[dict[str, Any], list[str]]],
    run_post_pipeline_fn: Callable[..., tuple[dict[str, Any], list[str]]],
    parse_image_ref_fn: Callable[[str], tuple[str | None, str]],
    asset_cache_cls: type[Any],
    sanitize_fn: Callable[[Any], Any],
    runner: RunnerCallable,
    which_fn: WhichCallable,
    sleep_fn: Callable[[float], None],
    env: Mapping[str, str],
    image_gen_script: Path,
    validate_constraints_fn: Callable[[Any], list[str]] | None = None,
) -> int:
    """Compile `timeline_plan.json`, generate/chain/verify segments, stitch, and post-process."""
    try:
        plan = compile_timeline_plan(config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Apply script metadata defaults if CLI did not explicitly override
    script_meta = plan.get("script_metadata") or {}
    effective_ar = (
        config.aspect_ratio
        if getattr(config, "_explicit_ar", False)
        else str(script_meta.get("aspect_ratio") or config.aspect_ratio)
    )
    effective_style = config.style if config.style is not None else script_meta.get("style")
    effective_continuity = (
        config.continuity
        if getattr(config, "_explicit_continuity", False)
        else str(script_meta.get("continuity") or config.continuity)
    )
    raw_meta_xfade = script_meta.get("crossfade_sec")
    effective_crossfade = (
        float(config.crossfade_sec)
        if getattr(config, "_explicit_crossfade", False)
        else float(raw_meta_xfade if raw_meta_xfade is not None else config.crossfade_sec)
    )
    effective_narration = config.narration_text or script_meta.get("narration_text")
    active_base = dataclasses.replace(
        config,
        aspect_ratio=effective_ar,
        style=effective_style,
        continuity=effective_continuity,
        crossfade_sec=effective_crossfade,
        narration_text=effective_narration,
    )

    if validate_constraints_fn is not None:
        merged_errors = validate_constraints_fn(active_base)
        if merged_errors:
            for err in merged_errors:
                print(f"error: {err}", file=sys.stderr)
            return 2

    output_path = Path(active_base.output).resolve()

    if active_base.dry_run:
        dry_payload = {
            "dry_run": True,
            "mode": "multi-segment-timeline",
            "timeline_plan": sanitize_fn(plan),
            "output": contract_home(output_path),
        }
        print(json.dumps(dry_payload, indent=2))
        return 0

    # Validate persistent --image-ref magic bytes pre-upload (<= 6 refs)
    for raw_ref in active_base.image_refs:
        _, ref_target = parse_image_ref_fn(raw_ref)
        if not is_files_uri(ref_target):
            ref_path = Path(ref_target).resolve()
            if not ref_path.is_file():
                print(f"error: Input asset not found: {contract_home(ref_path)}", file=sys.stderr)
                return 2
            try:
                validate_image_file_header(ref_path)
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

    segments_dir = output_path.parent / f"{output_path.stem}_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    plan_path = segments_dir / "timeline_plan.json"
    plan_path.write_text(json.dumps(sanitize_fn(plan), indent=2) + "\n", encoding="utf-8")

    segments_list: list[dict[str, Any]] = list(plan["segments"])
    ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg", env=env, which_fn=which_fn)

    # Pre-synthesize chained keyframes if --synthesize-keyframes was requested
    synthesized_chain_frames: list[Path] = []
    if active_base.synthesize_keyframes:
        try:
            synthesized_chain_frames = synthesize_timeline_keyframes(
                plan,
                active_base,
                keyframes_dir=segments_dir / "keyframes",
                image_gen_script=image_gen_script,
                runner=runner,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except (RuntimeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    verified_segments: list[Path] = []
    actual_segment_durations: list[float] = []
    segment_provenance: list[dict[str, Any]] = []
    unchecked: list[str] = []
    shared_cache = asset_cache_cls(runner)

    # During multi-segment generation with custom post-scored audio (narration/bgm/full-mix),
    # generate raw visual segments in native/silent mode and run audio scoring once on stitched output.
    seg_audio_mode = "silent" if active_base.audio_mode == "silent" else "auto"

    for idx, seg in enumerate(segments_list):
        seg_num = int(seg["segment_index"])
        seg_out = segments_dir / f"segment_{seg_num:03d}.mp4"
        first_f = seg.get("first_frame")
        last_f = seg.get("last_frame")
        ext_clip: str | None = None
        chain_mode = str(seg.get("chain_mode") or "seed")

        if synthesized_chain_frames:
            first_f = str(synthesized_chain_frames[idx])
            if active_base.synthesize_keyframes == "start-end" and idx + 1 < len(synthesized_chain_frames):
                last_f = str(synthesized_chain_frames[idx + 1])
        elif idx > 0 and chain_mode in ("extracted_boundary_frame", "block_boundary_first_frame"):
            if not ffmpeg_bin:
                unchecked.append("ffmpeg_boundary_frame_extraction")
                return _emit_partial_failure(
                    output_path,
                    reason=(
                        f"ffmpeg not found; cannot extract boundary frame after segment {idx} "
                        f"for {active_base.continuity} chaining."
                    ),
                    plan_or_manifest_key="timeline_plan_path",
                    plan_or_manifest_val=contract_home(plan_path),
                    preserved_segments=verified_segments,
                    segment_provenance=segment_provenance,
                    unchecked=unchecked,
                )
            boundary_png = segments_dir / f"boundary_{idx:03d}.png"
            try:
                extract_boundary_frame(
                    verified_segments[-1],
                    boundary_png,
                    ffmpeg_bin=ffmpeg_bin,
                    runner=runner,
                )
            except (RuntimeError, ValueError) as exc:
                return _emit_partial_failure(
                    output_path,
                    reason=str(exc),
                    plan_or_manifest_key="timeline_plan_path",
                    plan_or_manifest_val=contract_home(plan_path),
                    preserved_segments=verified_segments,
                    segment_provenance=segment_provenance,
                    unchecked=unchecked,
                )
            first_f = str(boundary_png)
        elif idx > 0 and chain_mode == "omni_extend_turn":
            ext_clip = str(verified_segments[-1])
            first_f = None
            last_f = None

        seg_scene_texts = list(seg.get("scene_texts") or [])
        seg_cfg = dataclasses.replace(
            active_base,
            script=None,
            storyboard=None,
            prompt=str(seg["prompt"]),
            duration_s=int(seg["duration_s"]),
            first_frame=first_f,
            last_frame=last_f,
            extend=ext_clip,
            video=None,
            synthesize_keyframes=None,
            audio_mode=seg_audio_mode,
            scene_texts=seg_scene_texts,
            srt=None,
            captions_json=None,
            title_card=None,
            lower_thirds=[],
            end_card=None,
            voice_track=None,
            bgm_track=None,
            sfx_cues=[],
            narration_text=None,
            bgm_prompt=None,
            single_shot=True,
            output=str(seg_out),
        )

        rc = run_single_segment_fn(
            seg_cfg,
            runner=runner,
            which_fn=which_fn,
            sleep_fn=sleep_fn,
            env=env,
            image_gen_script=image_gen_script,
            asset_cache=shared_cache,
            skip_post_processing=True,
        )
        if rc != 0:
            return _emit_partial_failure(
                output_path,
                reason=f"Timeline segment {seg_num} of {len(segments_list)} failed verification (exit {rc}).",
                plan_or_manifest_key="timeline_plan_path",
                plan_or_manifest_val=contract_home(plan_path),
                preserved_segments=verified_segments,
                segment_provenance=segment_provenance,
                unchecked=unchecked,
            )

        verified_segments.append(seg_out)
        p_doc, probed_seg_dur = read_probed_segment_duration_s(
            seg_out, float(seg["duration_s"]), unchecked=unchecked
        )
        if p_doc is not None:
            segment_provenance.append(p_doc)
        actual_segment_durations.append(probed_seg_dur)

    if len(verified_segments) > 1 and not ffmpeg_bin:
        unchecked.append("ffmpeg_multi_segment_stitch")
        return _emit_partial_failure(
            output_path,
            reason=(
                f"ffmpeg not found; cannot stitch {len(verified_segments)} segments into "
                f"{contract_home(output_path)}."
            ),
            plan_or_manifest_key="timeline_plan_path",
            plan_or_manifest_val=contract_home(plan_path),
            preserved_segments=verified_segments,
            segment_provenance=segment_provenance,
            unchecked=unchecked,
        )

    stitched_target = segments_dir / "stitched_raw.mp4" if len(verified_segments) > 1 else verified_segments[0]
    stitch_info: dict[str, Any] = {"stitcher": "single_segment_passthrough", "crossfade_sec": 0.0}
    if len(verified_segments) > 1:
        assert ffmpeg_bin is not None
        try:
            stitch_info = stitch_segments(
                verified_segments,
                actual_segment_durations,
                stitched_target,
                crossfade_sec=float(plan["crossfade_sec"]),
                include_audio=(active_base.audio_mode != "silent"),
                ffmpeg_bin=ffmpeg_bin,
                runner=runner,
            )
        except RuntimeError as exc:
            return _emit_partial_failure(
                output_path,
                reason=str(exc),
                plan_or_manifest_key="timeline_plan_path",
                plan_or_manifest_val=contract_home(plan_path),
                preserved_segments=verified_segments,
                segment_provenance=segment_provenance,
                unchecked=unchecked,
            )

    # Apply post-production audio scoring/mastering + captions/motion cards onto final output_path
    try:
        post_report, post_unchecked = run_post_pipeline_fn(
            active_base,
            stitched_target,
            output_path,
            video_duration_s=float(plan["target_duration_s"]),
            runner=runner,
            which_fn=which_fn,
            env=env,
        )
    except ValueError as exc:
        return _emit_partial_failure(
            output_path,
            reason=str(exc),
            plan_or_manifest_key="timeline_plan_path",
            plan_or_manifest_val=contract_home(plan_path),
            preserved_segments=verified_segments,
            segment_provenance=segment_provenance,
            unchecked=unchecked,
            status="FAILED_VERIFICATION",
            exit_code=2,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        return _emit_partial_failure(
            output_path,
            reason=str(exc),
            plan_or_manifest_key="timeline_plan_path",
            plan_or_manifest_val=contract_home(plan_path),
            preserved_segments=verified_segments,
            segment_provenance=segment_provenance,
            unchecked=unchecked,
        )

    for surf in post_unchecked:
        if surf not in unchecked:
            unchecked.append(surf)

    expected_final_audio = (
        "silent"
        if active_base.audio_mode == "silent"
        else (
            "required"
            if active_base.audio_mode in ("required", "narration", "bgm", "full-mix")
            else "any"
        )
    )
    final_mech, final_unchecked = run_mechanical_check_fn(
        output_path,
        expected_ar=active_base.aspect_ratio,
        expected_resolution=active_base.resolution,
        expected_duration_s=int(plan["target_duration_s"]),
        expected_audio=expected_final_audio,
        duration_tolerance_s=float(plan["tolerance_s"]),
        require_ffprobe=active_base.require_ffprobe,
        runner=runner,
        which_fn=which_fn,
    )
    for surf in final_unchecked:
        if surf not in unchecked:
            unchecked.append(surf)

    if not final_mech["passed"]:
        if output_path.exists():
            output_path.unlink()
        failed_doc = {
            "schema_version": 1,
            "status": "FAILED_VERIFICATION",
            "generated_at": utc_now_iso(),
            "timeline_plan_path": contract_home(plan_path),
            "timeline_plan": sanitize_fn(plan),
            "output_path": contract_home(output_path),
            "stitch": stitch_info,
            "post_processing": post_report,
            "stitched_mechanical": final_mech,
            "segments": segment_provenance,
            "unchecked_surfaces": unchecked,
        }
        Path(f"{output_path}.provenance.json").write_text(
            json.dumps(failed_doc, indent=2) + "\n", encoding="utf-8"
        )
        Path(f"{output_path}.report.json").write_text(
            json.dumps(failed_doc, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"error: Stitched timeline output failed mechanical verification: {final_mech['failures']}",
            file=sys.stderr,
        )
        return 1

    overall_status = (
        max(
            (str(p.get("status") or "VERIFIED") for p in segment_provenance),
            key=lambda st: _STATUS_SEVERITY.get(st, 3),
        )
        if segment_provenance
        else ("MECHANICAL_ONLY" if active_base.no_verify else "VERIFIED")
    )
    prov_doc: dict[str, Any] = {
        "schema_version": 1,
        "status": overall_status,
        "generated_at": utc_now_iso(),
        "timeline_plan_path": contract_home(plan_path),
        "timeline_plan": sanitize_fn(plan),
        "output_path": contract_home(output_path),
        "stitch": stitch_info,
        "post_processing": post_report,
        "stitched_mechanical": final_mech,
        "segments": segment_provenance,
        "unchecked_surfaces": unchecked,
    }
    if active_base.allow_unverified and active_base.override_reason:
        prov_doc["override_reason"] = redact_secrets(active_base.override_reason.strip())

    Path(f"{output_path}.provenance.json").write_text(json.dumps(prov_doc, indent=2) + "\n", encoding="utf-8")
    Path(f"{output_path}.report.json").write_text(json.dumps(prov_doc, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": overall_status,
                "output": contract_home(output_path),
                "segments_count": len(verified_segments),
                "timeline_plan": contract_home(plan_path),
            }
        )
    )
    return 0


def run_storyboard_pipeline(
    config: Any,
    *,
    validate_constraints_fn: Callable[[Any], list[str]],
    run_single_segment_fn: Callable[..., int],
    run_mechanical_check_fn: Callable[..., tuple[dict[str, Any], list[str]]],
    run_post_pipeline_fn: Callable[..., tuple[dict[str, Any], list[str]]],
    asset_cache_cls: type[Any],
    valid_aspect_ratios: Sequence[str],
    runner: RunnerCallable,
    which_fn: WhichCallable,
    sleep_fn: Callable[[float], None],
    env: Mapping[str, str] | None = None,
) -> int:
    """Consume `keyframes_manifest.json` (§1.2) to generate, stitch, and post-process segment clips."""
    assert config.storyboard is not None
    effective_env = {} if env is None else env
    manifest_path = Path(config.storyboard).resolve()
    if not manifest_path.is_file():
        print(f"error: Storyboard manifest not found: {contract_home(manifest_path)}", file=sys.stderr)
        return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"error: Invalid JSON in storyboard manifest: {exc}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict):
        print("error: Storyboard manifest JSON must be an object.", file=sys.stderr)
        return 2

    frames = manifest.get("frames")
    if not isinstance(frames, list) or not frames:
        print("error: Storyboard manifest must contain a non-empty 'frames' list.", file=sys.stderr)
        return 2

    manifest_dir = manifest_path.parent
    raw_manifest_ar = manifest.get("aspect_ratio")
    if raw_manifest_ar is not None and raw_manifest_ar not in valid_aspect_ratios:
        print(
            f"error: Invalid storyboard manifest aspect_ratio {raw_manifest_ar!r} (valid: {tuple(valid_aspect_ratios)}).",
            file=sys.stderr,
        )
        return 2
    ar = str(raw_manifest_ar or config.aspect_ratio)

    raw_style = config.style if config.style is not None else manifest.get("style")
    if raw_style is not None and not isinstance(raw_style, str):
        print("error: Storyboard manifest 'style' must be a string.", file=sys.stderr)
        return 2
    style = raw_style

    anchor_path: Path | str | None = None
    if "anchor_image" in manifest and manifest["anchor_image"] is not None:
        anchor_raw = manifest["anchor_image"]
        if not isinstance(anchor_raw, str) or not anchor_raw.strip():
            print("error: Storyboard manifest 'anchor_image' must be a non-empty string path.", file=sys.stderr)
            return 2
        try:
            anchor_path = resolve_manifest_asset(anchor_raw, manifest_dir, require_image=True)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    output_path = Path(config.output).resolve()
    segments_dir = output_path.parent / f"{output_path.stem}_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    use_transitions = config.storyboard_mode == "transitions" and len(frames) >= 2
    max_seg_dur = MAX_INTERPOLATED_SEGMENT_S if use_transitions else MAX_STANDARD_SEGMENT_S

    resolved_frames: list[dict[str, Any]] = []
    for idx, frame in enumerate(frames, start=1):
        if not isinstance(frame, dict):
            print(f"error: Storyboard frame {idx} must be a JSON object.", file=sys.stderr)
            return 2
        raw_fpath = frame.get("path")
        if not isinstance(raw_fpath, str) or not raw_fpath.strip():
            print(f"error: Storyboard frame {idx} missing non-empty 'path'.", file=sys.stderr)
            return 2
        try:
            resolved_img = resolve_manifest_asset(raw_fpath, manifest_dir, require_image=True)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        prompt_val = frame.get("prompt", "")
        caption_val = frame.get("caption", "")
        for field_name, text_val in (("prompt", prompt_val), ("caption", caption_val)):
            if text_val is not None and not isinstance(text_val, str):
                print(
                    f"error: Storyboard frame {idx} '{field_name}' must be a string.",
                    file=sys.stderr,
                )
                return 2
            lowered_val = str(text_val or "").lower()
            for bad_tag in FORBIDDEN_LEGACY_XML_TAGS:
                if bad_tag.lower() in lowered_val:
                    print(
                        f"error: Deprecated XML media tag '{bad_tag}' detected in storyboard frame {idx} '{field_name}'.",
                        file=sys.stderr,
                    )
                    return 2

        raw_dur = (
            frame["duration_s"]
            if "duration_s" in frame
            else (frame["duration_hint_s"] if "duration_hint_s" in frame else config.duration_s)
        )
        if isinstance(raw_dur, bool) or not isinstance(raw_dur, int) or not (
            MIN_EXPLICIT_BEAT_S <= raw_dur <= max_seg_dur
        ):
            print(
                f"error: Storyboard frame {idx} duration {raw_dur!r} out of valid range {MIN_EXPLICIT_BEAT_S}..{max_seg_dur}s.",
                file=sys.stderr,
            )
            return 2
        resolved_frames.append(
            {
                "resolved_path": resolved_img,
                "prompt": str(prompt_val or "").strip(),
                "caption": str(caption_val or "").strip(),
                "duration_s": raw_dur,
            }
        )

    segment_specs: list[dict[str, Any]] = []
    if use_transitions:
        for idx in range(len(resolved_frames) - 1):
            f_start = resolved_frames[idx]
            f_end = resolved_frames[idx + 1]
            seg_prompt = (
                f"Transition smoothly from ({f_start['caption'] or f_start['prompt'] or 'start'}) "
                f"to ({f_end['caption'] or f_end['prompt'] or 'end'}). "
                f"{f_start['prompt']} -> {f_end['prompt']}"
            ).strip()
            segment_specs.append(
                {
                    "segment_index": idx + 1,
                    "first_frame": str(f_start["resolved_path"]),
                    "last_frame": str(f_end["resolved_path"]),
                    "duration_s": f_start["duration_s"],
                    "prompt": seg_prompt,
                }
            )
    else:
        for idx, frame in enumerate(resolved_frames):
            seg_prompt = frame["prompt"] or frame["caption"] or "Animate keyframe scene."
            segment_specs.append(
                {
                    "segment_index": idx + 1,
                    "first_frame": str(frame["resolved_path"]),
                    "last_frame": None,
                    "duration_s": frame["duration_s"],
                    "prompt": seg_prompt,
                }
            )

    seg_audio_mode = "silent" if config.audio_mode == "silent" else (
        "required" if config.audio_mode == "required" else "auto"
    )
    segment_configs: list[tuple[dict[str, Any], Any]] = []
    for seg in segment_specs:
        seg_out = segments_dir / f"segment_{seg['segment_index']:02d}.mp4"
        refs = list(config.image_refs)
        if anchor_path is not None and (
            isinstance(anchor_path, str) or (isinstance(anchor_path, Path) and anchor_path.exists())
        ):
            if str(anchor_path) not in {seg["first_frame"], seg["last_frame"]}:
                refs = [f"style:{anchor_path}", *refs][:MAX_IMAGE_REFS]
        seg_cfg = dataclasses.replace(
            config,
            storyboard=None,
            script=None,
            prompt=seg["prompt"],
            first_frame=seg["first_frame"],
            last_frame=seg["last_frame"],
            image_refs=refs,
            aspect_ratio=ar,
            duration_s=seg["duration_s"],
            audio_mode=seg_audio_mode,
            style=style,
            single_shot=True,
            srt=None,
            captions_json=None,
            title_card=None,
            lower_thirds=[],
            end_card=None,
            voice_track=None,
            bgm_track=None,
            sfx_cues=[],
            narration_text=None,
            bgm_prompt=None,
            output=str(seg_out),
        )
        seg_errors = validate_constraints_fn(seg_cfg)
        if seg_errors:
            for err in seg_errors:
                print(f"error: Storyboard segment {seg['segment_index']}: {err}", file=sys.stderr)
            return 2
        segment_configs.append((seg, seg_cfg))

    if config.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "storyboard": contract_home(manifest_path),
                    "aspect_ratio": ar,
                    "segments": segment_specs,
                },
                indent=2,
            )
        )
        return 0

    verified_segments: list[Path] = []
    actual_segment_durations: list[float] = []
    segment_provenance: list[dict[str, Any]] = []
    unchecked: list[str] = []
    if config.no_verify:
        unchecked.append("stage4_multimodal_rubric")
    shared_cache = asset_cache_cls(runner)

    for seg, seg_cfg in segment_configs:
        seg_out = Path(seg_cfg.output)
        rc = run_single_segment_fn(
            seg_cfg,
            runner=runner,
            which_fn=which_fn,
            sleep_fn=sleep_fn,
            env=effective_env,
            asset_cache=shared_cache,
            skip_post_processing=True,
        )
        if rc != 0:
            return rc
        verified_segments.append(seg_out)
        p_doc, probed_seg_dur = read_probed_segment_duration_s(
            seg_out, float(seg["duration_s"]), unchecked=unchecked
        )
        if p_doc is not None:
            segment_provenance.append(p_doc)
        actual_segment_durations.append(probed_seg_dur)

    concat_mech: dict[str, Any] | None = None
    post_report: dict[str, Any] | None = None

    raw_output: Path
    if len(verified_segments) > 1:
        ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg", env=effective_env, which_fn=which_fn)
        if ffmpeg_bin is None:
            if "ffmpeg_multi_segment_concat" not in unchecked:
                unchecked.append("ffmpeg_multi_segment_concat")
            return _emit_partial_failure(
                output_path,
                reason=(
                    f"ffmpeg not found on PATH; cannot concatenate {len(verified_segments)} storyboard segments "
                    f"into {contract_home(output_path)} (preserved segments in {contract_home(segments_dir)})."
                ),
                plan_or_manifest_key="storyboard_manifest",
                plan_or_manifest_val=contract_home(manifest_path),
                preserved_segments=verified_segments,
                segment_provenance=segment_provenance,
                unchecked=unchecked,
            )

        raw_output = segments_dir / "stitched_raw.mp4"
        try:
            stitch_segments(
                verified_segments,
                actual_segment_durations,
                raw_output,
                crossfade_sec=float(config.crossfade_sec),
                include_audio=(config.audio_mode != "silent"),
                ffmpeg_bin=ffmpeg_bin,
                runner=runner,
            )
        except RuntimeError as exc:
            return _emit_partial_failure(
                output_path,
                reason=str(exc),
                plan_or_manifest_key="storyboard_manifest",
                plan_or_manifest_val=contract_home(manifest_path),
                preserved_segments=verified_segments,
                segment_provenance=segment_provenance,
                unchecked=unchecked,
            )
    else:
        raw_output = verified_segments[0]

    raw_sum = sum(int(s["duration_s"]) for s in segment_specs)
    expected_total_dur = max(
        MIN_EXPLICIT_BEAT_S,
        int(round(raw_sum - float(config.crossfade_sec) * max(0, len(segment_specs) - 1))),
    )
    actual_total_dur = max(
        float(MIN_EXPLICIT_BEAT_S),
        sum(actual_segment_durations)
        - float(config.crossfade_sec) * max(0, len(verified_segments) - 1),
    )
    active_storyboard_cfg = dataclasses.replace(config, aspect_ratio=ar, style=style)

    try:
        post_report, post_unchecked = run_post_pipeline_fn(
            active_storyboard_cfg,
            raw_output,
            output_path,
            video_duration_s=actual_total_dur,
            runner=runner,
            which_fn=which_fn,
            env=effective_env,
        )
    except ValueError as exc:
        return _emit_partial_failure(
            output_path,
            reason=str(exc),
            plan_or_manifest_key="storyboard_manifest",
            plan_or_manifest_val=contract_home(manifest_path),
            preserved_segments=verified_segments,
            segment_provenance=segment_provenance,
            unchecked=unchecked,
            status="FAILED_VERIFICATION",
            exit_code=2,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        return _emit_partial_failure(
            output_path,
            reason=str(exc),
            plan_or_manifest_key="storyboard_manifest",
            plan_or_manifest_val=contract_home(manifest_path),
            preserved_segments=verified_segments,
            segment_provenance=segment_provenance,
            unchecked=unchecked,
        )

    for surf in post_unchecked:
        if surf not in unchecked:
            unchecked.append(surf)

    if len(verified_segments) > 1 or post_report.get("applied"):
        expected_audio = (
            "silent"
            if config.audio_mode == "silent"
            else (
                "required"
                if config.audio_mode in ("required", "narration", "bgm", "full-mix")
                else "any"
            )
        )
        concat_mech, concat_unchecked = run_mechanical_check_fn(
            output_path,
            expected_ar=ar,
            expected_resolution=config.resolution,
            expected_duration_s=expected_total_dur,
            expected_audio=expected_audio,
            duration_tolerance_s=max(1.2, 1.2 * len(segment_specs)),
            require_ffprobe=config.require_ffprobe,
            runner=runner,
            which_fn=which_fn,
        )
        for surf in concat_unchecked:
            if surf not in unchecked:
                unchecked.append(surf)
        if not concat_mech["passed"]:
            if output_path.exists():
                output_path.unlink()
            failed_prov = {
                "schema_version": 1,
                "status": "FAILED_VERIFICATION",
                "generated_at": utc_now_iso(),
                "storyboard_manifest": contract_home(manifest_path),
                "output_path": contract_home(output_path),
                "post_processing": post_report,
                "concat_mechanical": concat_mech,
                "segments": segment_provenance,
                "unchecked_surfaces": unchecked,
            }
            Path(f"{output_path}.provenance.json").write_text(
                json.dumps(failed_prov, indent=2) + "\n", encoding="utf-8"
            )
            Path(f"{output_path}.report.json").write_text(
                json.dumps(failed_prov, indent=2) + "\n", encoding="utf-8"
            )
            print(
                f"error: Storyboard output failed mechanical verification: {concat_mech['failures']}",
                file=sys.stderr,
            )
            return 1

    if segment_provenance:
        overall_status = max(
            (str(p.get("status") or "VERIFIED") for p in segment_provenance),
            key=lambda st: _STATUS_SEVERITY.get(st, 3),
        )
    else:
        overall_status = "MECHANICAL_ONLY" if config.no_verify else "VERIFIED"

    storyboard_prov: dict[str, Any] = {
        "schema_version": 1,
        "status": overall_status,
        "generated_at": utc_now_iso(),
        "storyboard_manifest": contract_home(manifest_path),
        "output_path": contract_home(output_path),
        "segments": segment_provenance,
        "unchecked_surfaces": unchecked,
    }
    if concat_mech is not None:
        storyboard_prov["concat_mechanical"] = concat_mech
    if post_report and post_report.get("applied"):
        storyboard_prov["post_processing"] = post_report
    Path(f"{output_path}.provenance.json").write_text(
        json.dumps(storyboard_prov, indent=2) + "\n", encoding="utf-8"
    )
    if post_report and post_report.get("applied"):
        Path(f"{output_path}.report.json").write_text(
            json.dumps(storyboard_prov, indent=2) + "\n", encoding="utf-8"
        )
    else:
        Path(f"{output_path}.report.json").unlink(missing_ok=True)
    print(json.dumps({"status": storyboard_prov["status"], "output": contract_home(output_path)}))
    return 0
