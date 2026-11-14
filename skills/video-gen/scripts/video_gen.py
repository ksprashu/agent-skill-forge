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

"""Grounded Video Generation, Keyframe Delegation & Verification Controller.

Drives the official ``gemini-api`` CLI on ``gemini-omni-1.2-flash`` using 100%
Python 3.12 standard library modules with a four-stage evidence/judgement loop
(Engineering Standard S1-S9, V1-V6):

  Stage 1: Compile frozen ``VisualRequirementSpec`` (``spec.json``) with explicit
           timecodes, quoted literals, negative constraints, single-shot camera
           directives, and natural-language ``-i`` asset bindings.
  Stage 2: Execute ``gemini-api video -m gemini-omni-1.2-flash -o json`` with
           reusable ``files/<id>`` caching (>12 MB or retry reuse) and bounded
           quota backoff.
  Stage 3: Deterministic mechanical check: ISO BMFF ``ftyp`` container check plus
           ``ffprobe`` stream verification (video stream presence, resolution,
           aspect ratio, duration +-1.2s, and expected audio stream state).
  Stage 4: Stateless blinded multimodal rubric judge (``VERIFIER_MODEL_CHAIN``)
           validated deterministically in Python (``S9``), driving dual-mode
           remediation (``edit_turn`` via ``--previous-interaction-id`` vs full
           ``regenerate``) against the unmodified frozen ``spec.json``.

Audit scope & unchecked-surface reporting (Engineering Standard V3 / V5):
  * Stage 3 audits ``*.mp4`` output files via container header inspection and
    ``ffprobe`` JSON stream metadata. When ``ffprobe`` is absent on ``PATH`` and
    ``--require-ffprobe`` is not set, ``"ffprobe_stream_metadata"`` is recorded
    explicitly in ``unchecked_surfaces``.
  * Stage 4 audits visual/audio semantic adherence via blinded multimodal model
    judgement and enforces AC provenance in Python. When ``--no-verify`` is set,
    ``"stage4_multimodal_rubric"`` is recorded in ``unchecked_surfaces``.
  * Neither verifier can prove subjective artistic taste beyond the explicit and
    implicit criteria recorded in ``spec.json``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

if sys.platform == "win32":  # pragma: no cover - platform specific
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import video_post  # noqa: E402
import video_timeline  # noqa: E402
from video_post import (  # noqa: E402
    CommandResult,
    DEFAULT_AUDIO_GEN_SCRIPT,
    DEFAULT_DUCK_DB,
    DEFAULT_LUFS_TARGET,
    RunnerCallable,
    SECRET_PATTERNS,
    VALID_CAPTION_STYLES,
    WhichCallable,
    contract_home,
    default_runner,
    discover_creative_stack,
    is_files_uri as _is_files_uri,
    parse_end_card_spec,
    parse_lower_third_spec,
    parse_sfx_cue_spec,
    parse_title_card_spec,
    probe_ffmpeg_capabilities,
    redact_secrets,
    resolve_ffmpeg_binary,
    safe_ffmpeg_path,
    utc_now_iso,
    validate_and_parse_subtitles,
    validate_audio_magic_bytes,
    validate_safe_local_file,
)
from video_timeline import (  # noqa: E402
    VALID_CONTINUITY_MODES,
    build_keyframe_commands,
    resolve_manifest_asset as _resolve_manifest_asset,
    resolve_synthesized_keyframe as _resolve_synthesized_keyframe,
    synthesize_keyframes_via_image_gen,
    validate_image_file_header as _validate_image_file_header,
)

# ---------------------------------------------------------------------------
# Shared Inter-Skill Constants (T6 Parity with skills/image-gen)
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

PRIMARY_VIDEO_MODEL = "gemini-omni-1.2-flash"
LEGACY_VIDEO_FALLBACK_MODEL = "gemini-omni-1.1-flash"
ALLOWED_VIDEO_MODELS = frozenset({PRIMARY_VIDEO_MODEL, LEGACY_VIDEO_FALLBACK_MODEL})
IMAGE_ONLY_MODELS = frozenset(
    {"gemini-nano-banana-2.1", "gemini-3-pro-image", "gemini-3.1-flash-lite-image"}
)

VALID_ASPECT_RATIOS: tuple[str, ...] = ("16:9", "9:16")
VALID_RESOLUTIONS: tuple[str, ...] = ("360p", "720p", "1080p", "4k")
RESOLUTION_DIMENSIONS: dict[str, tuple[int, int]] = {
    "360p": (360, 640),
    "720p": (720, 1280),
    "1080p": (1080, 1920),
    "4k": (2160, 3840),
}
ASPECT_RATIO_FLOATS: dict[str, float] = {
    "16:9": 16.0 / 9.0,
    "9:16": 9.0 / 16.0,
}

MIN_DURATION_S = 3
MAX_DURATION_S = 15
MAX_INTERPOLATION_OR_EXTEND_S = 10
MAX_SOURCE_VIDEO_S = 15.0
MAX_CUMULATIVE_EXTEND_S = 30.0
MAX_IMAGE_REFS = 6
LARGE_ASSET_THRESHOLD_BYTES = 12 * 1024 * 1024

KNOWN_ROLE_PREFIXES: dict[str, str] = {
    "char": "character appearance and identity reference",
    "character": "character appearance and identity reference",
    "style": "visual style and palette reference",
    "prop": "prop and object reference",
    "subject": "subject appearance reference",
    "background": "environment and background reference",
}

FORBIDDEN_LEGACY_XML_TAGS: tuple[str, ...] = (
    "<FIRST_FRAME>",
    "</FIRST_FRAME>",
    "<LAST_FRAME>",
    "</LAST_FRAME>",
    "<IMAGE_REF",
    "</IMAGE_REF",
    "<VIDEO_REF",
)

DEFAULT_IMAGE_GEN_SCRIPT = (
    Path(__file__).resolve().parents[2] / "image-gen" / "scripts" / "image_gen.py"
)

VALID_AUDIO_MODES: tuple[str, ...] = (
    "native",
    "silent",
    "narration",
    "bgm",
    "full-mix",
    "auto",
    "required",
)

VERDICT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "criteria_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "observed_evidence": {"type": "string"},
                    "fix_instruction": {"type": "string"},
                },
                "required": ["id", "passed", "observed_evidence", "fix_instruction"],
            },
        },
        "remediation_mode": {
            "type": "string",
            "enum": ["edit_turn", "regenerate"],
        },
        "edit_delta_prompt": {"type": "string"},
        "regenerated_prompt": {"type": "string"},
    },
    "required": [
        "criteria_results",
        "remediation_mode",
        "edit_delta_prompt",
        "regenerated_prompt",
    ],
}

EXPANSION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "expanded_prompt": {"type": "string"},
    },
    "required": ["expanded_prompt"],
}


def _is_transient_quota_or_capacity_error(result: CommandResult) -> bool:
    combined = f"{result.stderr}\n{result.stdout}".lower()
    markers = (
        "429",
        "503",
        "resource_exhausted",
        "quota",
        "rate limit",
        "too many requests",
        "overloaded",
        "capacity",
        "temporarily unavailable",
    )
    return result.returncode != 0 and any(m in combined for m in markers)


# ---------------------------------------------------------------------------
# Configuration & Pre-Upload Omni Constraint Validator (Exit 2)
# ---------------------------------------------------------------------------


@dataclass
class VideoJobConfig:
    prompt: str = ""
    spec_file: str | None = None
    spec_out: str | None = None
    storyboard: str | None = None
    storyboard_mode: str = "transitions"
    script: str | None = None
    continuity: str = "keyframe-chain"
    crossfade_sec: float = 0.0
    first_frame: str | None = None
    last_frame: str | None = None
    synthesize_keyframes: str | None = None
    end_frame_prompt: str | None = None
    image_refs: list[str] = field(default_factory=list)
    video_refs: list[str] = field(default_factory=list)
    video: str | None = None
    extend: str | None = None
    task: str | None = None
    strip_audio: bool = False
    prep_clip: bool = False
    aspect_ratio: str = "16:9"
    resolution: str = "1080p"
    duration_s: int = 8
    single_shot: bool = False
    audio_mode: str = "native"
    voice_track: str | None = None
    bgm_track: str | None = None
    sfx_cues: list[str] = field(default_factory=list)
    narration_text: str | None = None
    voice_name: str | None = None
    bgm_prompt: str | None = None
    audio_gen_script: str | None = None
    duck_db: float = DEFAULT_DUCK_DB
    lufs_target: float = DEFAULT_LUFS_TARGET
    scene_texts: list[str] = field(default_factory=list)
    srt: str | None = None
    captions_json: str | None = None
    caption_style: str = "pill"
    title_card: str | None = None
    lower_thirds: list[str] = field(default_factory=list)
    end_card: str | None = None
    creative_stack: str = "auto"
    style: str | None = None
    previous_interaction_id: str | None = None
    max_attempts: int = 3
    model: str = PRIMARY_VIDEO_MODEL
    verifier_model: str = VERIFIER_MODEL_CHAIN[0]
    raw_prompt: bool = False
    expand_prompt: bool = False
    no_verify: bool = False
    allow_unverified: bool = False
    override_reason: str | None = None
    allow_legacy_video_fallback: bool = False
    require_ffprobe: bool = False
    dry_run: bool = False
    doctor: bool = False
    output: str = "output.mp4"
    _explicit_ar: bool = False
    _explicit_resolution: bool = False
    _explicit_duration: bool = False
    _explicit_audio: bool = False


def parse_duration_seconds(raw_val: str) -> int:
    cleaned = raw_val.strip().lower()
    if cleaned.endswith("s"):
        cleaned = cleaned[:-1].strip()
    try:
        return int(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{raw_val}'; expected integer seconds >= 3 (e.g. 8, 45, 600)."
        ) from exc


def parse_image_ref(raw_ref: str) -> tuple[str | None, str]:
    """Split optional role prefix ('char:hero.png') safely across POSIX and Windows."""
    text = raw_ref.strip()
    if ":" in text:
        prefix, rest = text.split(":", 1)
        if prefix.lower() in KNOWN_ROLE_PREFIXES and rest:
            return prefix.lower(), rest
    return None, text


def validate_model_id(model_id: str, *, role: str) -> list[str]:
    """Validate active model IDs and hard-block deprecated prefixes (Spec §2)."""
    errors: list[str] = []
    normalized = model_id.strip().lower()
    if not normalized:
        return [f"Empty {role} model identifier."]

    if normalized == "flash_medium":
        errors.append(
            f"Model '{model_id}' for {role} is obsolete ('flash_medium' is invalid). "
            f"Use '{PRIMARY_VIDEO_MODEL}' for video generation or '{VERIFIER_MODEL_CHAIN[0]}' for verification."
        )
        return errors

    for prefix in DEPRECATED_MODEL_PREFIXES:
        if normalized.startswith(prefix):
            replacement = (
                PRIMARY_VIDEO_MODEL if role == "video" else VERIFIER_MODEL_CHAIN[0]
            )
            errors.append(
                f"Deprecated or shut-down {role} model '{model_id}' (matched '{prefix}'). "
                f"Use '{replacement}' instead (see https://aistudio.google.com/docs/omni)."
            )
            return errors

    if role == "video" and normalized in IMAGE_ONLY_MODELS:
        errors.append(
            f"Model '{model_id}' is an image generation model, not a video model. "
            f"Use '{PRIMARY_VIDEO_MODEL}' or pass '--synthesize-keyframes' to delegate image keyframes."
        )
    elif role == "video" and normalized not in ALLOWED_VIDEO_MODELS:
        errors.append(
            f"Unsupported video model '{model_id}'. Supported active video model: '{PRIMARY_VIDEO_MODEL}'."
        )
    elif role == "verifier" and normalized not in VERIFIER_MODEL_CHAIN:
        errors.append(
            f"Unsupported verifier model '{model_id}'. Supported verifier models: {', '.join(VERIFIER_MODEL_CHAIN)}."
        )
    return errors


def _validate_post_and_audio_constraints(
    config: VideoJobConfig,
    *,
    env: Mapping[str, str] | None = None,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
) -> list[str]:
    """Validate post-composite text/captions, audio stems, DSP parameters, and creative-stack."""
    errors: list[str] = []

    if config.allow_unverified and (
        config.override_reason is None or not str(config.override_reason).strip()
    ):
        errors.append(
            "--allow-unverified requires a non-empty --override-reason explaining why verification is bypassed."
        )

    if config.continuity not in VALID_CONTINUITY_MODES:
        errors.append(
            f"Unsupported --continuity '{config.continuity}'. Supported: {', '.join(VALID_CONTINUITY_MODES)}."
        )

    if (
        not math.isfinite(config.crossfade_sec)
        or config.crossfade_sec < 0.0
        or config.crossfade_sec > video_timeline.MAX_CROSSFADE_S
    ):
        errors.append(
            f"--crossfade-sec must be finite between 0.0 and {video_timeline.MAX_CROSSFADE_S:.1f}s "
            f"(got {config.crossfade_sec}s)."
        )

    if config.audio_mode not in VALID_AUDIO_MODES:
        errors.append(
            f"Unsupported --audio-mode '{config.audio_mode}'. Supported: {', '.join(VALID_AUDIO_MODES)}."
        )

    if not math.isfinite(config.duck_db) or config.duck_db < 0.0 or config.duck_db > 48.0:
        errors.append(f"--duck-db must be finite between 0.0 and 48.0 dB (got {config.duck_db}).")

    if not math.isfinite(config.lufs_target) or config.lufs_target < -36.0 or config.lufs_target > -5.0:
        errors.append(f"--lufs-target must be finite between -36.0 and -5.0 LUFS (got {config.lufs_target}).")

    if config.caption_style not in VALID_CAPTION_STYLES:
        errors.append(
            f"Unsupported --caption-style '{config.caption_style}'. Supported: {', '.join(VALID_CAPTION_STYLES)}."
        )

    for st_idx, st_val in enumerate(config.scene_texts, start=1):
        if not isinstance(st_val, str) or not st_val.strip():
            errors.append(f"--scene-text #{st_idx} must be a non-empty text string.")
            continue
        for bad_tag in FORBIDDEN_LEGACY_XML_TAGS:
            if bad_tag.lower() in st_val.lower():
                errors.append(f"Deprecated XML media tag '{bad_tag}' detected in --scene-text.")
                break

    try:
        discover_creative_stack(config.creative_stack, env=env)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        validate_and_parse_subtitles(srt_path=config.srt, captions_json_path=config.captions_json)
    except ValueError as exc:
        errors.append(str(exc))

    if config.title_card is not None:
        try:
            parse_title_card_spec(config.title_card)
        except ValueError as exc:
            errors.append(str(exc))

    for lt_raw in config.lower_thirds:
        try:
            parse_lower_third_spec(lt_raw)
        except ValueError as exc:
            errors.append(str(exc))

    if config.end_card is not None:
        try:
            parse_end_card_spec(config.end_card)
        except ValueError as exc:
            errors.append(str(exc))

    has_voice_input = bool(config.voice_track or (config.narration_text and config.narration_text.strip()))
    has_bgm_input = bool(config.bgm_track or (config.bgm_prompt and config.bgm_prompt.strip()))
    has_sfx_input = len(config.sfx_cues) > 0

    if config.audio_mode == "silent" and (has_voice_input or has_bgm_input or has_sfx_input):
        errors.append(
            "--audio-mode silent cannot be combined with --voice-track, --bgm-track, "
            "--sfx-cue, --narration-text, or --bgm-prompt."
        )
    elif config.audio_mode == "narration" and not has_voice_input:
        errors.append("--audio-mode narration requires --voice-track or --narration-text.")
    elif config.audio_mode == "bgm" and not has_bgm_input:
        errors.append("--audio-mode bgm requires --bgm-track or --bgm-prompt.")
    elif config.audio_mode == "full-mix" and not (has_voice_input or has_bgm_input or has_sfx_input):
        errors.append(
            "--audio-mode full-mix requires at least one of --voice-track, --narration-text, "
            "--bgm-track, --bgm-prompt, or --sfx-cue."
        )

    if config.voice_track and config.narration_text:
        errors.append("--voice-track and --narration-text are mutually exclusive.")
    if config.bgm_track and config.bgm_prompt:
        errors.append("--bgm-track and --bgm-prompt are mutually exclusive.")

    if config.voice_track:
        try:
            validate_audio_magic_bytes(config.voice_track, label="--voice-track")
        except ValueError as exc:
            errors.append(str(exc))

    if config.bgm_track:
        try:
            validate_audio_magic_bytes(config.bgm_track, label="--bgm-track")
        except ValueError as exc:
            errors.append(str(exc))

    for sfx_raw in config.sfx_cues:
        try:
            parse_sfx_cue_spec(sfx_raw)
        except ValueError as exc:
            errors.append(str(exc))

    if (config.narration_text and config.narration_text.strip()) or (
        config.bgm_prompt and config.bgm_prompt.strip()
    ):
        eff_audio_gen = (
            Path(config.audio_gen_script).expanduser().resolve()
            if config.audio_gen_script
            else audio_gen_script
        )
        if not eff_audio_gen.is_file():
            errors.append(
                f"Companion audio-gen script not found at '{contract_home(eff_audio_gen)}'. "
                "Install audio-gen alongside video-gen or pass --voice-track / --bgm-track."
            )

    return errors


def is_multi_segment_job(config: VideoJobConfig) -> bool:
    """Return True when job routes to `video_timeline.run_timeline_pipeline`."""
    if config.storyboard or config.video or config.extend or config.spec_file:
        return False
    if config.first_frame and config.last_frame and not config.script:
        return False
    return bool(config.script) or config.duration_s > MAX_DURATION_S


def validate_omni_constraints(
    config: VideoJobConfig,
    *,
    env: Mapping[str, str] | None = None,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
) -> list[str]:
    """Pre-upload validator for Gemini Omni 1.2 video & post-processing constraints (exits 2)."""
    errors: list[str] = []

    errors.extend(validate_model_id(config.model, role="video"))
    errors.extend(validate_model_id(config.verifier_model, role="verifier"))
    errors.extend(
        _validate_post_and_audio_constraints(
            config, env=env, audio_gen_script=audio_gen_script
        )
    )

    if config.max_attempts < 1 or config.max_attempts > 10:
        errors.append("--max-attempts must be between 1 and 10.")

    out_resolved = Path(config.output).expanduser().resolve()
    candidate_inputs: list[tuple[str, str]] = []
    for flag_lbl, raw_in in (
        ("--video", config.video),
        ("--extend", config.extend),
        ("--first-frame", config.first_frame),
        ("--last-frame", config.last_frame),
        ("--voice-track", config.voice_track),
        ("--bgm-track", config.bgm_track),
        ("--srt", config.srt),
        ("--captions-json", config.captions_json),
        ("--script", config.script),
        ("--storyboard", config.storyboard),
        ("--spec-file", config.spec_file),
    ):
        if raw_in and not _is_files_uri(raw_in):
            candidate_inputs.append((flag_lbl, raw_in))
    for iref in config.image_refs:
        _, ipath = parse_image_ref(iref)
        if ipath and not _is_files_uri(ipath):
            candidate_inputs.append(("--image-ref", ipath))
    for vref in config.video_refs:
        if vref and not _is_files_uri(vref):
            candidate_inputs.append(("--video-ref", vref))
    for sfx_raw in config.sfx_cues:
        sfx_path_part = sfx_raw.rsplit("@", 1)[0].strip() if "@" in sfx_raw else sfx_raw.strip()
        if sfx_path_part:
            candidate_inputs.append(("--sfx-cue", sfx_path_part))
    for flag_lbl, raw_in in candidate_inputs:
        try:
            if "\x00" not in raw_in and Path(raw_in).expanduser().resolve() == out_resolved:
                errors.append(
                    f"--output '{contract_home(out_resolved)}' must not alias input {flag_lbl}."
                )
        except OSError:
            pass

    if len(config.image_refs) > MAX_IMAGE_REFS:
        errors.append(
            f"At most {MAX_IMAGE_REFS} --image-ref assets are supported (got {len(config.image_refs)})."
        )

    if config.storyboard:
        if (
            config.script
            or config.video
            or config.extend
            or config.first_frame
            or config.last_frame
            or config.synthesize_keyframes
            or config.video_refs
        ):
            errors.append(
                "--storyboard cannot be combined with --script, --video, --extend, --first-frame, "
                "--last-frame, --synthesize-keyframes, or --video-ref."
            )
        if config.style:
            for bad_tag in FORBIDDEN_LEGACY_XML_TAGS:
                if bad_tag.lower() in config.style.lower():
                    errors.append(f"Deprecated XML media tag '{bad_tag}' detected in --style.")
                    break
        return errors

    if config.script:
        if config.video or config.extend or config.spec_file:
            errors.append("--script cannot be combined with --video, --extend, or --spec-file.")
        try:
            video_timeline.parse_script_file(config.script)
        except ValueError as exc:
            errors.append(str(exc))

    if not config.prompt.strip() and not config.spec_file and not config.script:
        errors.append("One of --prompt, --script, --spec-file, --storyboard, or --doctor is required.")

    for bad_tag in FORBIDDEN_LEGACY_XML_TAGS:
        if bad_tag.lower() in config.prompt.lower():
            errors.append(
                f"Deprecated XML media tag '{bad_tag}' detected in --prompt. "
                "Gemini Omni 1.2 binds '-i' inputs via natural-language instructions, not XML tags."
            )
            break

    if config.duration_s < MIN_DURATION_S:
        errors.append(
            f"--duration must be at least {MIN_DURATION_S}s (got {config.duration_s}s)."
        )

    if config.video and config.duration_s > MAX_DURATION_S:
        errors.append(
            f"--video (edit) caps single-clip --duration at {MAX_DURATION_S}s (got {config.duration_s}s)."
        )

    if config.spec_file and config.duration_s > MAX_DURATION_S:
        errors.append(
            f"--spec-file single-clip jobs cap --duration at {MAX_DURATION_S}s (got {config.duration_s}s)."
        )

    if config.last_frame and not config.first_frame:
        errors.append("--last-frame requires --first-frame.")

    explicit_two_frame = bool(config.first_frame and config.last_frame)
    if explicit_two_frame and config.duration_s > MAX_INTERPOLATION_OR_EXTEND_S:
        errors.append(
            f"Two-frame start+end interpolation caps --duration at {MAX_INTERPOLATION_OR_EXTEND_S}s "
            f"(got {config.duration_s}s)."
        )

    if (
        config.synthesize_keyframes == "start-end"
        and not is_multi_segment_job(config)
        and config.duration_s > MAX_INTERPOLATION_OR_EXTEND_S
    ):
        errors.append(
            f"Single-clip --synthesize-keyframes start-end caps --duration at {MAX_INTERPOLATION_OR_EXTEND_S}s "
            f"(got {config.duration_s}s)."
        )

    if config.extend and config.duration_s > MAX_INTERPOLATION_OR_EXTEND_S:
        errors.append(
            f"--extend turns cap per-turn --duration at {MAX_INTERPOLATION_OR_EXTEND_S}s "
            f"(got {config.duration_s}s; cumulative cap is {int(MAX_CUMULATIVE_EXTEND_S)}s)."
        )

    if config.video and config.extend:
        errors.append("--video (edit) and --extend are mutually exclusive.")

    if config.synthesize_keyframes:
        if config.first_frame or config.last_frame:
            errors.append(
                "--synthesize-keyframes cannot be combined with explicit --first-frame or --last-frame."
            )
        if config.video or config.extend:
            errors.append(
                "--synthesize-keyframes cannot be combined with --video or --extend."
            )

    if (config.first_frame or config.last_frame) and (config.video or config.extend):
        errors.append(
            "--first-frame / --last-frame cannot be combined with --video or --extend."
        )

    if config.task == "extend" and config.image_refs:
        errors.append(
            "Explicit '--task extend' does not support --image-ref in Omni 1.2. "
            "Omit '--task' to use prompt-based extension alongside reference images."
        )

    if config.video_refs:
        if config.video or config.extend or config.previous_interaction_id:
            errors.append(
                "--video-ref is strictly forbidden with --video, --extend, or --previous-interaction-id."
            )
        if config.duration_s <= 10 and len(config.video_refs) > 3:
            errors.append(
                f"3s-10s generation supports at most 3 --video-ref clips (got {len(config.video_refs)})."
            )
        elif config.duration_s >= 11 and len(config.video_refs) > 1:
            errors.append(
                f"11s-15s generation supports at most 1 --video-ref clip (got {len(config.video_refs)})."
            )

    if config.strip_audio and not (config.video or config.extend):
        errors.append("--strip-audio requires --video or --extend source clip.")

    src_media = config.extend or config.video
    if src_media and _is_files_uri(src_media) and (config.strip_audio or config.prep_clip):
        errors.append(
            "--strip-audio and --prep-clip require a local video file, not a remote 'files/<id>' URI."
        )
    if config.prep_clip and any(_is_files_uri(vr) for vr in config.video_refs):
        errors.append(
            "--prep-clip requires local --video-ref files, not a remote 'files/<id>' URI."
        )

    if config.model == LEGACY_VIDEO_FALLBACK_MODEL:
        if (not is_multi_segment_job(config) and config.duration_s > 10) or (
            config.extend and config.image_refs
        ):
            errors.append(
                f"'{LEGACY_VIDEO_FALLBACK_MODEL}' only supports duration <= 10s and no extension image refs."
            )

    return errors


# ---------------------------------------------------------------------------
# Stage 1: Intent Parsing & Frozen VisualRequirementSpec (spec.json)
# ---------------------------------------------------------------------------

_QUOTED_RE = re.compile(r'"([^"\n]{1,120})"')
_TIMECODE_RE = re.compile(
    r"(\[\s*\d+(?::\d+)?s?\s*-\s*\d+(?::\d+)?s?\s*\])\s*([^\[\n]+)"
)
_NEGATIVE_RE = re.compile(
    r"\b((?:no|without|avoid|never)\s+[A-Za-z0-9 ,'-]{3,60}?)(?=[.;,]|$)",
    re.IGNORECASE,
)


def extract_prompt_signals(raw_prompt: str) -> dict[str, Any]:
    """Deterministically extract quoted literals, timecodes, and negative constraints (T3)."""
    quoted = [m.group(1).strip() for m in _QUOTED_RE.finditer(raw_prompt) if m.group(1).strip()]
    beats = [
        {"range": m.group(1).strip(), "instruction": m.group(2).strip()}
        for m in _TIMECODE_RE.finditer(raw_prompt)
    ]
    negatives = [m.group(1).strip() for m in _NEGATIVE_RE.finditer(raw_prompt)]
    return {
        "quoted_literals": list(dict.fromkeys(quoted)),
        "timecode_beats": beats,
        "negative_constraints": list(dict.fromkeys(negatives)),
    }


def _as_asset_ref(raw_val: str) -> Path | str:
    return raw_val.strip() if _is_files_uri(raw_val) else Path(raw_val).resolve()


def collect_ordered_input_paths(
    config: VideoJobConfig,
    *,
    source_video_override: Path | str | None = None,
    video_ref_overrides: Sequence[Path | str] | None = None,
) -> list[Path | str]:
    """Return local asset paths (or files/<id> URIs) in exact Omni 1.2 -i input order (1..5)."""
    ordered: list[Path | str] = []
    if config.first_frame:
        ordered.append(_as_asset_ref(config.first_frame))
    if config.last_frame:
        ordered.append(_as_asset_ref(config.last_frame))
    for raw_ref in config.image_refs:
        _, ref_path = parse_image_ref(raw_ref)
        ordered.append(_as_asset_ref(ref_path))
    if config.extend or config.video:
        if source_video_override is not None:
            ordered.append(
                source_video_override.strip()
                if isinstance(source_video_override, str)
                else source_video_override.resolve()
            )
        else:
            src_raw = config.extend or config.video
            assert src_raw is not None
            ordered.append(_as_asset_ref(src_raw))
    if video_ref_overrides is not None:
        ordered.extend(p.strip() if isinstance(p, str) else p.resolve() for p in video_ref_overrides)
    else:
        for vref in config.video_refs:
            ordered.append(_as_asset_ref(vref))
    return ordered


def _determine_mode(config: VideoJobConfig) -> str:
    if config.extend:
        return "extend"
    if config.video:
        return "edit"
    if config.first_frame and config.last_frame:
        if Path(config.first_frame).resolve() == Path(config.last_frame).resolve():
            return "seamless-loop"
        return "keyframe-transition"
    if config.first_frame:
        return "keyframe-start"
    if config.video_refs or config.image_refs:
        return "reference-to-video"
    if config.single_shot:
        return "single-shot"
    return "multi-shot"


def _validate_and_load_spec_file(spec_file: str) -> dict[str, Any]:
    """Load and deterministically validate `--spec-file` JSON schema and digest (P1 #6, P2 #14)."""
    spec_path = Path(spec_file)
    if not spec_path.is_file():
        raise ValueError(f"Spec file not found: {contract_home(spec_path)}")
    try:
        loaded = json.loads(spec_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"Invalid JSON in --spec-file '{contract_home(spec_path)}': {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError("--spec-file must contain a JSON object.")

    spec = dict(loaded)
    has_raw = "raw_prompt" in spec
    has_compiled = "compiled_prompt" in spec
    if has_raw and (not isinstance(spec["raw_prompt"], str) or not spec["raw_prompt"].strip()):
        raise ValueError("--spec-file 'raw_prompt' must be a non-empty string.")
    if has_compiled and (
        not isinstance(spec["compiled_prompt"], str) or not spec["compiled_prompt"].strip()
    ):
        raise ValueError("--spec-file 'compiled_prompt' must be a non-empty string.")
    if not has_raw and not has_compiled:
        raise ValueError("--spec-file must contain 'compiled_prompt' and/or 'raw_prompt'.")
    if not has_raw:
        spec["raw_prompt"] = spec["compiled_prompt"]
    if not has_compiled:
        spec["compiled_prompt"] = spec["raw_prompt"]

    acs = spec.get("acceptance_criteria")
    if not isinstance(acs, list) or not acs:
        raise ValueError("--spec-file must contain a non-empty 'acceptance_criteria' list.")
    mandatory_count = 0
    seen_ac_ids: set[str] = set()
    for idx, item in enumerate(acs, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"--spec-file acceptance_criteria[{idx}] must be a JSON object.")
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError(f"--spec-file acceptance_criteria[{idx}] missing non-empty 'id'.")
        ac_id_clean = item["id"].strip()
        if ac_id_clean in seen_ac_ids:
            raise ValueError(
                f"--spec-file contains duplicate acceptance criterion id '{ac_id_clean}'."
            )
        seen_ac_ids.add(ac_id_clean)
        if not isinstance(item.get("category"), str) or not item["category"].strip():
            raise ValueError(f"--spec-file acceptance_criteria[{idx}] missing non-empty 'category'.")
        if not isinstance(item.get("requirement"), str) or not item["requirement"].strip():
            raise ValueError(
                f"--spec-file acceptance_criteria[{idx}] missing non-empty 'requirement'."
            )
        if "mandatory" in item and not isinstance(item["mandatory"], bool):
            raise ValueError(
                f"--spec-file acceptance_criteria[{idx}] 'mandatory' must be boolean."
            )
        if item.get("mandatory", True):
            mandatory_count += 1
    if mandatory_count == 0:
        raise ValueError("--spec-file defines zero mandatory acceptance criteria (S9).")

    ac_canonical = json.dumps(acs, sort_keys=True)
    expected_digest = hashlib.sha256(ac_canonical.encode("utf-8")).hexdigest()
    if "spec_digest" in spec:
        if not isinstance(spec["spec_digest"], str) or spec["spec_digest"] != expected_digest:
            raise ValueError(
                "--spec-file 'spec_digest' does not match SHA-256 of 'acceptance_criteria'."
            )
    else:
        spec["spec_digest"] = expected_digest

    ec = spec.get("explicit_constraints")
    if ec is None:
        ec = {}
    elif not isinstance(ec, dict):
        raise ValueError("--spec-file 'explicit_constraints' must be a JSON object.")
    else:
        ec = dict(ec)

    if "aspect_ratio" in ec and ec["aspect_ratio"] is not None:
        if ec["aspect_ratio"] not in VALID_ASPECT_RATIOS:
            raise ValueError(f"--spec-file invalid explicit_constraints.aspect_ratio: {ec['aspect_ratio']!r}.")
    if "resolution" in ec and ec["resolution"] is not None:
        if ec["resolution"] not in VALID_RESOLUTIONS:
            raise ValueError(f"--spec-file invalid explicit_constraints.resolution: {ec['resolution']!r}.")
    if "duration_s" in ec and ec["duration_s"] is not None:
        dur_val = ec["duration_s"]
        if isinstance(dur_val, bool) or not isinstance(dur_val, int) or not (
            MIN_DURATION_S <= dur_val <= MAX_DURATION_S
        ):
            raise ValueError(
                f"--spec-file invalid explicit_constraints.duration_s: {dur_val!r} (must be 3..15)."
            )
    if "audio_mode" in ec and ec["audio_mode"] is not None:
        if ec["audio_mode"] not in VALID_AUDIO_MODES:
            raise ValueError(f"--spec-file invalid explicit_constraints.audio_mode: {ec['audio_mode']!r}.")
    if "style" in ec and ec["style"] is not None and not isinstance(ec["style"], str):
        raise ValueError("--spec-file 'explicit_constraints.style' must be a string or null.")
    if "asset_bindings" in ec and ec["asset_bindings"] is not None:
        bindings = ec["asset_bindings"]
        if not isinstance(bindings, list):
            raise ValueError("--spec-file 'explicit_constraints.asset_bindings' must be a list.")
        for b_idx, binding in enumerate(bindings, start=1):
            if not isinstance(binding, dict):
                raise ValueError(f"--spec-file explicit_constraints.asset_bindings[{b_idx}] must be an object.")
            idx_val = binding.get("input_index")
            if isinstance(idx_val, bool) or not isinstance(idx_val, int) or idx_val < 1:
                raise ValueError(
                    f"--spec-file explicit_constraints.asset_bindings[{b_idx}] 'input_index' must be int >= 1."
                )
            if not isinstance(binding.get("role"), str) or not binding["role"].strip():
                raise ValueError(
                    f"--spec-file explicit_constraints.asset_bindings[{b_idx}] missing non-empty 'role'."
                )
            if (
                not isinstance(binding.get("natural_language_directive"), str)
                or not binding["natural_language_directive"].strip()
            ):
                raise ValueError(
                    f"--spec-file explicit_constraints.asset_bindings[{b_idx}] missing non-empty 'natural_language_directive'."
                )

    spec["explicit_constraints"] = ec
    return spec


def compile_visual_spec(config: VideoJobConfig) -> dict[str, Any]:
    """Compile the frozen Stage 1 VisualRequirementSpec (spec.json)."""
    if config.spec_file:
        return _validate_and_load_spec_file(config.spec_file)

    signals = extract_prompt_signals(config.prompt)
    explicit_scene_texts = [t.strip() for t in config.scene_texts if isinstance(t, str) and t.strip()]
    all_text_literals = list(dict.fromkeys([*explicit_scene_texts, *signals["quoted_literals"]]))
    mode = _determine_mode(config)

    asset_bindings: list[dict[str, Any]] = []
    nl_directives: list[str] = []
    next_input_idx = 1

    has_image_refs = len(config.image_refs) > 0
    if config.first_frame and config.last_frame:
        same_frame = Path(config.first_frame).resolve() == Path(config.last_frame).resolve()
        if same_frame:
            directive = "Use this image as both the starting frame and the final frame."
            asset_bindings.append(
                {
                    "input_index": next_input_idx,
                    "role": "first_frame",
                    "role_hint": "seamless_loop_anchor",
                    "natural_language_directive": directive,
                }
            )
            next_input_idx += 1
            asset_bindings.append(
                {
                    "input_index": next_input_idx,
                    "role": "last_frame",
                    "role_hint": "seamless_loop_anchor",
                    "natural_language_directive": directive,
                }
            )
            next_input_idx += 1
            nl_directives.append(directive)
        else:
            directive = (
                "Use the first image as the starting frame and the second image as the final frame."
            )
            asset_bindings.append(
                {
                    "input_index": next_input_idx,
                    "role": "first_frame",
                    "role_hint": None,
                    "natural_language_directive": "Use the first image as the starting frame.",
                }
            )
            next_input_idx += 1
            asset_bindings.append(
                {
                    "input_index": next_input_idx,
                    "role": "last_frame",
                    "role_hint": None,
                    "natural_language_directive": "Use the second image as the final frame.",
                }
            )
            next_input_idx += 1
            nl_directives.append(directive)
    elif config.first_frame:
        directive = (
            "Use the first image as the starting frame."
            if has_image_refs
            else "Use this image as the starting frame."
        )
        asset_bindings.append(
            {
                "input_index": next_input_idx,
                "role": "first_frame",
                "role_hint": None,
                "natural_language_directive": directive,
            }
        )
        next_input_idx += 1
        nl_directives.append(directive)

    for raw_ref in config.image_refs:
        role_key, _ = parse_image_ref(raw_ref)
        role_desc = KNOWN_ROLE_PREFIXES.get(role_key or "", "visual reference")
        img_directive = f"Use image {next_input_idx} as the {role_desc}."
        asset_bindings.append(
            {
                "input_index": next_input_idx,
                "role": "image_ref",
                "role_hint": role_key,
                "natural_language_directive": img_directive,
            }
        )
        nl_directives.append(img_directive)
        next_input_idx += 1

    if config.extend:
        ext_directive = "Extend this video seamlessly while preserving scene and subject continuity."
        asset_bindings.append(
            {
                "input_index": next_input_idx,
                "role": "extend_video",
                "role_hint": None,
                "natural_language_directive": ext_directive,
            }
        )
        next_input_idx += 1
    elif config.video:
        edit_directive = "Edit the provided source video clip. Keep everything else the same."
        asset_bindings.append(
            {
                "input_index": next_input_idx,
                "role": "source_video",
                "role_hint": None,
                "natural_language_directive": edit_directive,
            }
        )
        next_input_idx += 1

    for vref_idx, _ in enumerate(config.video_refs, start=1):
        vref_directive = f"Use reference video clip {vref_idx} for motion and pacing guidance."
        asset_bindings.append(
            {
                "input_index": next_input_idx,
                "role": "video_ref",
                "role_hint": None,
                "natural_language_directive": vref_directive,
            }
        )
        nl_directives.append(vref_directive)
        next_input_idx += 1

    implicit_constraints: list[str] = []
    prompt_prefixes: list[str] = []
    prompt_suffixes: list[str] = []

    if config.extend and config.task != "extend":
        if "extend this video" not in config.prompt.lower():
            prompt_prefixes.append("Extend this video.")
        implicit_constraints.append(
            "Maintain seamless temporal, motion, lighting, and character continuity from the source clip"
        )
    elif config.video:
        if "keep everything else the same" not in config.prompt.lower():
            prompt_prefixes.append("Keep everything else the same.")
        implicit_constraints.append(
            "Keep everything else the same; preserve unedited subjects, camera trajectory, and background geometry"
        )

    if config.single_shot:
        single_shot_rule = "In a single continuous unbroken shot, no scene cuts"
        prompt_prefixes.append(f"{single_shot_rule}.")
        implicit_constraints.append(single_shot_rule)

    if mode == "seamless-loop":
        implicit_constraints.append(
            "Seamless cyclical motion returning cleanly to the exact starting frame composition"
        )
    elif mode == "keyframe-transition":
        implicit_constraints.append(
            "Smooth physically plausible transition from the starting frame to the final frame"
        )

    if config.audio_mode == "silent":
        silent_rule = "Silent video track with zero dialogue, music, or sound effects"
        implicit_constraints.append(silent_rule)
        prompt_prefixes.append("Generate a silent video with no audio, dialogue, or music.")
    else:
        implicit_constraints.append(
            "Coherent foley and ambience aligned with on-screen motion; avoid hallucinated off-screen speech unless prompted"
        )

    if all_text_literals:
        joined_lits = ", ".join(f'"{lit}"' for lit in all_text_literals)
        typo_rule = (
            f"Anti-garbling typography discipline: render exact text {joined_lits} with crisp, "
            "high-contrast, geometrically stable letterforms and zero warped or misspelled glyphs"
        )
        implicit_constraints.append(typo_rule)
        prompt_suffixes.append(f"{typo_rule}.")

    if config.style:
        prompt_prefixes.append(f"Visual style: {config.style.strip()}.")

    prompt_parts = [*prompt_prefixes, *nl_directives, config.prompt.strip(), *prompt_suffixes]
    compiled_prompt = " ".join(part for part in prompt_parts if part).strip()

    criteria: list[dict[str, Any]] = []

    def add_ac(category: str, requirement: str) -> None:
        ac_id = f"AC-{len(criteria) + 1}"
        criteria.append(
            {
                "id": ac_id,
                "category": category,
                "requirement": requirement,
                "mandatory": True,
            }
        )

    add_ac(
        "subject_and_action",
        f"Depicts requested scene and action accurately: {config.prompt.strip()}",
    )
    if config.single_shot:
        add_ac(
            "shot_continuity",
            "Video plays as a single continuous unbroken shot with zero hard scene cuts.",
        )
    for beat in signals["timecode_beats"]:
        add_ac(
            "temporal_beat",
            f"Beat {beat['range']} executes: {beat['instruction']}",
        )
    if config.first_frame:
        add_ac(
            "start_frame_lock",
            "Opening frame matches the supplied starting keyframe image.",
        )
    if config.last_frame:
        add_ac(
            "end_frame_lock",
            "Closing frame converges cleanly to the supplied final keyframe image.",
        )
    if config.image_refs:
        add_ac(
            "reference_fidelity",
            f"Preserves subject/style consistency with the {len(config.image_refs)} supplied reference image(s).",
        )
    if config.video:
        add_ac(
            "edit_preservation",
            "Applies requested edit while keeping everything else in the source clip unchanged.",
        )
    if config.extend:
        add_ac(
            "extension_continuity",
            "Extends the source clip seamlessly without jarring jump cuts or identity drift.",
        )
    for lit in all_text_literals:
        add_ac(
            "TEXT_AC",
            f'OCR legibility & exact character-for-character spelling (TEXT_AC): visible or spoken literal matches exact text "{lit}" with zero garbled glyphs.',
        )
    for neg in signals["negative_constraints"]:
        add_ac(
            "negative_constraint",
            f"Strictly respects negative constraint: {neg}.",
        )
    if config.style:
        add_ac(
            "art_direction",
            f"Maintains consistent visual art direction: {config.style.strip()}.",
        )

    ac_canonical = json.dumps(criteria, sort_keys=True)
    spec_digest = hashlib.sha256(ac_canonical.encode("utf-8")).hexdigest()

    return {
        "schema_version": 1,
        "mode": mode,
        "raw_prompt": config.prompt.strip(),
        "compiled_prompt": compiled_prompt,
        "explicit_constraints": {
            "aspect_ratio": config.aspect_ratio,
            "resolution": config.resolution,
            "duration_s": config.duration_s,
            "quoted_literals": signals["quoted_literals"],
            "scene_texts": explicit_scene_texts,
            "timecode_beats": signals["timecode_beats"],
            "negative_constraints": signals["negative_constraints"],
            "audio_mode": config.audio_mode,
            "style": config.style.strip() if config.style else None,
            "asset_bindings": asset_bindings,
        },
        "implicit_constraints": implicit_constraints,
        "acceptance_criteria": criteria,
        "spec_digest": spec_digest,
    }


def validate_expanded_prompt(
    raw_prompt: str,
    expanded_prompt: str,
    *,
    extra_literals: Sequence[str] = (),
) -> list[str]:
    """Verify prompt expansion dropped zero quoted/scene literals and added zero XML tags (T3/T4)."""
    errors: list[str] = []
    signals = extract_prompt_signals(raw_prompt)
    required_literals = list(dict.fromkeys([*signals["quoted_literals"], *(x.strip() for x in extra_literals if x and x.strip())]))
    for literal in required_literals:
        if literal not in expanded_prompt:
            errors.append(f'Expanded prompt dropped required quoted literal: "{literal}"')
    for bad_tag in FORBIDDEN_LEGACY_XML_TAGS:
        if bad_tag.lower() in expanded_prompt.lower():
            errors.append(f"Expanded prompt introduced forbidden legacy tag: {bad_tag}")
    if not expanded_prompt.strip():
        errors.append("Expanded prompt is empty.")
    return errors


def _extract_generate_text(stdout_raw: str) -> str:
    """Extract text payload from `gemini-api generate --stream=false -o json` stdout."""
    data = json.loads(stdout_raw)
    if isinstance(data, dict) and "steps" in data and isinstance(data["steps"], list):
        chunks: list[str] = []
        for step in data["steps"]:
            if not isinstance(step, dict):
                continue
            for item in step.get("content", []):
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    chunks.append(item["text"])
        if chunks:
            return "\n".join(chunks)
    return stdout_raw


def maybe_expand_prompt(
    *,
    raw_prompt: str,
    deterministic_prompt: str,
    verifier_model: str,
    runner: RunnerCallable,
    extra_literals: Sequence[str] = (),
) -> str:
    """Optionally enrich cinematographic detail via Argon while enforcing literal preservation."""
    expand_instruction = (
        "Expand this video prompt into crisp cinematographic direction (camera motion, lighting, "
        "subject movement, and soundscape) while preserving EVERY explicit instruction, natural-language "
        "image/video reference binding, timecode, and exact double-quoted text literal verbatim. "
        f"Source prompt:\n{deterministic_prompt}"
    )
    body = {
        "store": False,
        "generation_config": {"thinking_level": "high"},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": EXPANSION_JSON_SCHEMA,
        },
    }
    cmd = [
        "gemini-api",
        "generate",
        expand_instruction,
        "-m",
        verifier_model,
        "--stream=false",
        "-o",
        "json",
        "--body",
        json.dumps(body, sort_keys=True),
    ]
    res = runner(cmd)
    if res.returncode != 0:
        print(
            f"[video-gen] Prompt expansion skipped (generator fallback to deterministic spec): {res.stderr.strip()}",
            file=sys.stderr,
        )
        return deterministic_prompt
    try:
        inner = json.loads(_extract_generate_text(res.stdout))
        candidate = str(inner.get("expanded_prompt", "")).strip()
    except (ValueError, TypeError, AttributeError):
        return deterministic_prompt

    errs = validate_expanded_prompt(raw_prompt, candidate, extra_literals=extra_literals)
    if errs:
        print(
            f"[video-gen] Rejected lossy prompt expansion ({'; '.join(errs)}); keeping deterministic prompt.",
            file=sys.stderr,
        )
        return deterministic_prompt
    return candidate


# ---------------------------------------------------------------------------
# Stage 2: Asset Caching, Media Prep & gemini-api video Execution
# ---------------------------------------------------------------------------


class AssetUploadCache:
    """Uploads files >12 MB or reused across retries/segments once via `gemini-api files upload`."""

    def __init__(self, runner: RunnerCallable) -> None:
        self._runner = runner
        self._uploaded: dict[Path, str] = {}

    def resolve(self, path: Path | str, *, force_upload: bool = False) -> str:
        if isinstance(path, str) and _is_files_uri(path):
            return path.strip()
        resolved = Path(path).resolve()
        if resolved in self._uploaded:
            return self._uploaded[resolved]
        size_bytes = resolved.stat().st_size if resolved.exists() else 0
        if not force_upload and size_bytes <= LARGE_ASSET_THRESHOLD_BYTES:
            return str(resolved)
        uri = self._upload(resolved)
        self._uploaded[resolved] = uri
        return uri

    def _upload(self, path: Path) -> str:
        res = self._runner(["gemini-api", "files", "upload", str(path), "--wait", "-o", "json"])
        if res.returncode != 0:
            raise RuntimeError(
                f"gemini-api files upload failed for {contract_home(path)}: {redact_secrets(res.stderr).strip()}"
            )
        out = res.stdout.strip()
        try:
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                for key in ("name", "uri", "id"):
                    val = parsed.get(key)
                    if isinstance(val, str) and val.strip():
                        cleaned = val.strip()
                        if _is_files_uri(cleaned):
                            return cleaned
                        uri_match = re.search(r"(?:^|/)(files/[A-Za-z0-9_-]+)(?:$|[/?#])", cleaned)
                        if uri_match:
                            return uri_match.group(1)
                        if re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
                            return f"files/{cleaned}"
        except ValueError:
            pass
        match = re.search(r"(?:^|\s)(files/[A-Za-z0-9_-]+)(?=\s|$)", out)
        if match:
            return match.group(1)
        raise RuntimeError(
            f"Could not parse 'files/<id>' URI from gemini-api files upload output: {redact_secrets(out)}"
        )


def build_video_cli_command(
    *,
    config: VideoJobConfig,
    prompt_text: str,
    ordered_inputs: Sequence[str],
    candidate_out: Path,
    model_id: str,
    previous_interaction_id: str | None,
) -> tuple[list[str], dict[str, Any]]:
    """Build exact `gemini-api video` argv and `--body` JSON payload."""
    body: dict[str, Any] = {
        "response_format": {
            "duration": f"{config.duration_s}s",
        }
    }
    if config.task:
        body["generation_config"] = {
            "video_config": {
                "task": config.task,
            }
        }

    safe_prompt = (
        f"Scene: {prompt_text}" if prompt_text.lstrip().startswith("-") else prompt_text
    )
    cmd: list[str] = [
        "gemini-api",
        "video",
        safe_prompt,
        "-m",
        model_id,
    ]
    if config.task != "extend":
        cmd.extend(["--aspect-ratio", config.aspect_ratio])
    cmd.extend(["--resolution", config.resolution])
    for item in ordered_inputs:
        cmd.extend(["-i", item])
    if previous_interaction_id:
        cmd.extend(["--previous-interaction-id", previous_interaction_id])
    cmd.extend(
        [
            "--body",
            json.dumps(body, sort_keys=True),
            "--out",
            str(candidate_out),
            "-o",
            "json",
        ]
    )
    return cmd, body


def _probe_video_duration_s(path: Path, runner: RunnerCallable, which_fn: WhichCallable) -> float | None:
    ffprobe_bin = resolve_ffmpeg_binary("ffprobe", which_fn=which_fn)
    if ffprobe_bin is None:
        return None
    res = runner(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            safe_ffmpeg_path(path),
        ]
    )
    if res.returncode != 0:
        return None
    try:
        data = json.loads(res.stdout)
    except ValueError:
        return None
    return _extract_duration_from_ffprobe(data)


def _prepare_media_inputs(
    config: VideoJobConfig,
    temp_dir: Path,
    runner: RunnerCallable,
    which_fn: WhichCallable,
) -> tuple[Path | str | None, list[Path | str]]:
    """Run optional `--prep-clip` and `--strip-audio` via ffmpeg (`shell=False`) inside temp_dir."""
    needs_ffmpeg = config.strip_audio or config.prep_clip
    ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg", which_fn=which_fn) if needs_ffmpeg else None
    if needs_ffmpeg and ffmpeg_bin is None:
        raise ValueError(
            "ffmpeg is required on PATH for --strip-audio / --prep-clip. "
            "Install ffmpeg (or run scripts/install.sh --with-media-tools)."
        )

    source_override: Path | str | None = None
    src_raw = config.extend or config.video
    if src_raw:
        if _is_files_uri(src_raw):
            if config.prep_clip or config.strip_audio:
                raise ValueError(
                    "--strip-audio and --prep-clip require a local video file, not a remote 'files/<id>' URI."
                )
            source_override = src_raw.strip()
        else:
            current_src = Path(src_raw).resolve()
            if config.prep_clip:
                assert ffmpeg_bin is not None
                prepped = temp_dir / "prepped_source.mp4"
                prep_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    safe_ffmpeg_path(current_src),
                    "-t",
                    "15",
                    "-vf",
                    "scale=-2:720",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                ]
                if config.strip_audio:
                    prep_cmd.append("-an")
                else:
                    prep_cmd.extend(["-c:a", "aac"])
                prep_cmd.append(safe_ffmpeg_path(prepped))
                res = runner(prep_cmd)
                if res.returncode != 0:
                    raise RuntimeError(f"ffmpeg --prep-clip failed: {redact_secrets(res.stderr).strip()}")
                current_src = prepped
            elif config.strip_audio:
                assert ffmpeg_bin is not None
                stripped = temp_dir / "stripped_silent_source.mp4"
                strip_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    safe_ffmpeg_path(current_src),
                    "-c:v",
                    "copy",
                    "-an",
                    safe_ffmpeg_path(stripped),
                ]
                res = runner(strip_cmd)
                if res.returncode != 0:
                    raise RuntimeError(f"ffmpeg --strip-audio failed: {redact_secrets(res.stderr).strip()}")
                current_src = stripped
            source_override = current_src

    vref_overrides: list[Path | str] = []
    for idx, vref_str in enumerate(config.video_refs, start=1):
        if _is_files_uri(vref_str):
            if config.prep_clip:
                raise ValueError(
                    "--prep-clip requires local --video-ref files, not a remote 'files/<id>' URI."
                )
            vref_overrides.append(vref_str.strip())
            continue
        vref_path = Path(vref_str).resolve()
        if config.prep_clip:
            assert ffmpeg_bin is not None
            prepped_ref = temp_dir / f"prepped_vref_{idx}.mp4"
            ref_cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                safe_ffmpeg_path(vref_path),
                "-t",
                "3",
                "-vf",
                "scale=-2:720",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                safe_ffmpeg_path(prepped_ref),
            ]
            res = runner(ref_cmd)
            if res.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg --prep-clip failed on --video-ref {idx}: {redact_secrets(res.stderr).strip()}"
                )
            vref_overrides.append(prepped_ref)
        else:
            vref_overrides.append(vref_path)

    return source_override, vref_overrides


def execute_video_generation_with_backoff(
    *,
    config: VideoJobConfig,
    prompt_text: str,
    ordered_inputs: Sequence[str],
    candidate_out: Path,
    previous_interaction_id: str | None,
    runner: RunnerCallable,
    sleep_fn: Callable[[float], None],
    max_rpc_tries: int = 3,
) -> tuple[dict[str, Any], str]:
    """Run `gemini-api video` with bounded backoff and opt-in 1.1 legacy failover."""
    models_to_try = [config.model]
    can_legacy_fallback = (
        config.allow_legacy_video_fallback
        and config.model == PRIMARY_VIDEO_MODEL
        and config.duration_s <= MAX_INTERPOLATION_OR_EXTEND_S
        and not (config.extend and len(config.image_refs) > 0)
    )
    if can_legacy_fallback:
        models_to_try.append(LEGACY_VIDEO_FALLBACK_MODEL)

    last_error = "Unknown gemini-api video failure"
    for model_idx, model_id in enumerate(models_to_try):
        if model_idx > 0:
            print(
                f"[video-gen] WARNING: Quota/capacity exhausted on {PRIMARY_VIDEO_MODEL}; "
                f"falling back to opt-in legacy model {model_id}.",
                file=sys.stderr,
            )
        tries = max_rpc_tries if model_idx == 0 else 1
        for rpc_idx in range(tries):
            cmd, _ = build_video_cli_command(
                config=config,
                prompt_text=prompt_text,
                ordered_inputs=ordered_inputs,
                candidate_out=candidate_out,
                model_id=model_id,
                previous_interaction_id=previous_interaction_id,
            )
            res = runner(cmd)
            if res.returncode == 0:
                try:
                    payload = json.loads(res.stdout)
                except ValueError as exc:
                    raise RuntimeError(
                        f"Malformed JSON from gemini-api video: {redact_secrets(res.stdout)[:300]}"
                    ) from exc
                if payload.get("status") not in (None, "completed"):
                    raise RuntimeError(
                        f"gemini-api video returned non-completed status: {payload.get('status')}"
                    )
                return payload, model_id

            last_error = redact_secrets(res.stderr or res.stdout).strip()
            if _is_transient_quota_or_capacity_error(res):
                if rpc_idx + 1 < tries:
                    sleep_fn(float(2**rpc_idx))
                    continue
                break
            raise RuntimeError(f"gemini-api video exited {res.returncode}: {last_error}")

    raise RuntimeError(f"gemini-api video failed after bounded retries: {last_error}")


# ---------------------------------------------------------------------------
# Stage 3: Deterministic Mechanical Verifier (Container + ffprobe)
# ---------------------------------------------------------------------------


def verify_mp4_container_header(path: Path) -> tuple[bool, str]:
    """Pure-stdlib ISO BMFF `ftyp` magic header and byte-size check."""
    if not path.is_file():
        return False, "missing_output_file"
    size = path.stat().st_size
    if size < 16:
        return False, f"empty_or_truncated_mp4:{size}B"
    with path.open("rb") as fh:
        header = fh.read(16)
    if header[4:8] != b"ftyp":
        return False, "invalid_mp4_ftyp_header"
    return True, "ok"


def _extract_duration_from_ffprobe(ffprobe_data: dict[str, Any]) -> float | None:
    streams = ffprobe_data.get("streams", [])
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == "video":
                raw_dur = stream.get("duration")
                if raw_dur is not None:
                    try:
                        val = float(raw_dur)
                        if val > 0:
                            return val
                    except (TypeError, ValueError):
                        pass
    fmt = ffprobe_data.get("format", {})
    if isinstance(fmt, dict) and fmt.get("duration") is not None:
        try:
            val = float(fmt["duration"])
            if val > 0:
                return val
        except (TypeError, ValueError):
            pass
    return None


def _extract_rotation_degrees(video_stream: dict[str, Any]) -> int:
    tags = video_stream.get("tags", {})
    if isinstance(tags, dict) and "rotate" in tags:
        try:
            return int(float(tags["rotate"])) % 360
        except (TypeError, ValueError):
            pass
    side_data = video_stream.get("side_data_list", [])
    if isinstance(side_data, list):
        for entry in side_data:
            if isinstance(entry, dict) and "rotation" in entry:
                try:
                    return abs(int(float(entry["rotation"]))) % 360
                except (TypeError, ValueError):
                    pass
    return 0


def verify_ffprobe_payload(
    ffprobe_data: dict[str, Any],
    *,
    expected_ar: str,
    expected_resolution: str,
    expected_duration_s: int,
    expected_audio: str = "any",
    duration_tolerance_s: float = 1.2,
) -> dict[str, Any]:
    """Pure Stage 3 verifier over parsed `ffprobe` JSON facts (S9, V1, V2)."""
    failures: list[str] = []
    streams = ffprobe_data.get("streams")
    if not isinstance(streams, list):
        return {
            "passed": False,
            "failures": ["malformed_ffprobe_streams"],
            "width": 0,
            "height": 0,
            "duration_s": None,
            "video_codec": None,
            "audio_streams": 0,
        }

    video_streams = [
        s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"
    ]
    audio_streams = [
        s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"
    ]

    if not video_streams:
        return {
            "passed": False,
            "failures": ["missing_video_stream"],
            "width": 0,
            "height": 0,
            "duration_s": _extract_duration_from_ffprobe(ffprobe_data),
            "video_codec": None,
            "audio_streams": len(audio_streams),
        }

    vstream = video_streams[0]
    raw_w = int(vstream.get("width") or 0)
    raw_h = int(vstream.get("height") or 0)
    rotation = _extract_rotation_degrees(vstream)
    width, height = (raw_h, raw_w) if rotation in (90, 270) else (raw_w, raw_h)
    video_codec = vstream.get("codec_name")

    if width <= 0 or height <= 0:
        failures.append(f"invalid_dimensions:{width}x{height}")
    else:
        target_ratio = ASPECT_RATIO_FLOATS[expected_ar]
        actual_ratio = width / height
        rel_diff = abs(actual_ratio - target_ratio) / target_ratio
        if rel_diff > 0.035:
            failures.append(
                f"wrong_aspect_ratio:expected={expected_ar},actual={width}x{height}({actual_ratio:.3f})"
            )

        exp_short, exp_long = RESOLUTION_DIMENSIONS[expected_resolution]
        actual_short, actual_long = min(width, height), max(width, height)
        if abs(actual_short - exp_short) > 32 or abs(actual_long - exp_long) > 32:
            failures.append(
                f"wrong_resolution:expected={expected_resolution}({exp_short}x{exp_long}),"
                f"actual={actual_short}x{actual_long}"
            )

    actual_duration = _extract_duration_from_ffprobe(ffprobe_data)
    if actual_duration is None:
        failures.append("missing_duration")
    elif abs(actual_duration - float(expected_duration_s)) > duration_tolerance_s:
        failures.append(
            f"wrong_duration:expected={expected_duration_s}s+-{duration_tolerance_s}s,actual={actual_duration:.2f}s"
        )

    if expected_audio == "silent" and len(audio_streams) > 0:
        failures.append(f"residual_audio_stream:count={len(audio_streams)}")
    elif expected_audio == "required" and len(audio_streams) == 0:
        failures.append("missing_audio_stream")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "width": width,
        "height": height,
        "duration_s": actual_duration,
        "video_codec": video_codec,
        "audio_streams": len(audio_streams),
    }


def run_mechanical_video_check(
    video_path: Path,
    *,
    expected_ar: str,
    expected_resolution: str,
    expected_duration_s: int,
    expected_audio: str = "any",
    duration_tolerance_s: float = 1.2,
    require_ffprobe: bool = False,
    runner: RunnerCallable = default_runner,
    which_fn: WhichCallable = shutil.which,
) -> tuple[dict[str, Any], list[str]]:
    """Run container + `ffprobe` stream checks and report unchecked surfaces honestly (V5)."""
    unchecked: list[str] = []
    ok_container, container_msg = verify_mp4_container_header(video_path)
    if not ok_container:
        return (
            {
                "passed": False,
                "failures": [container_msg],
                "container_ok": False,
            },
            unchecked,
        )

    ffprobe_bin = resolve_ffmpeg_binary("ffprobe", which_fn=which_fn)
    if ffprobe_bin is None:
        if require_ffprobe:
            return (
                {
                    "passed": False,
                    "failures": ["ffprobe_missing_on_path (--require-ffprobe set)"],
                    "container_ok": True,
                },
                unchecked,
            )
        print(
            "[video-gen] WARNING: ffprobe not found on PATH; stream dimensions/duration/audio "
            "could not be mechanically audited (recorded in unchecked_surfaces).",
            file=sys.stderr,
        )
        unchecked.append("ffprobe_stream_metadata")
        return (
            {
                "passed": True,
                "failures": [],
                "container_ok": True,
                "ffprobe_skipped": True,
            },
            unchecked,
        )

    res = runner(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            safe_ffmpeg_path(video_path),
        ]
    )
    if res.returncode != 0:
        return (
            {
                "passed": False,
                "failures": [f"ffprobe_error:{redact_secrets(res.stderr).strip()}"],
                "container_ok": True,
            },
            unchecked,
        )
    try:
        ffprobe_json = json.loads(res.stdout)
    except ValueError:
        return (
            {
                "passed": False,
                "failures": ["ffprobe_invalid_json"],
                "container_ok": True,
            },
            unchecked,
        )

    verdict = verify_ffprobe_payload(
        ffprobe_json,
        expected_ar=expected_ar,
        expected_resolution=expected_resolution,
        expected_duration_s=expected_duration_s,
        expected_audio=expected_audio,
        duration_tolerance_s=duration_tolerance_s,
    )
    verdict["container_ok"] = True
    return verdict, unchecked


# ---------------------------------------------------------------------------
# Stage 4: Blinded Multimodal Judge & S9 Provenance Validator
# ---------------------------------------------------------------------------


def build_blinded_judge_prompt(spec: dict[str, Any]) -> str:
    """Build a stateless blinded rubric prompt with ZERO generator CoT or attempt history (L2/S9)."""
    criteria_lines = [
        f"- {item['id']} [{item['category']}] (mandatory={item.get('mandatory', True)}): {item['requirement']}"
        for item in spec["acceptance_criteria"]
    ]
    bindings = spec.get("explicit_constraints", {}).get("asset_bindings", [])
    binding_lines = [
        f"- Reference input #{int(b['input_index']) + 1} ({b['role']}): {b['natural_language_directive']}"
        for b in bindings
    ]
    parts = [
        "You are an independent blinded multimodal quality auditor.",
        "Input #1 is the candidate MP4 video under audit. Any subsequent inputs are reference assets.",
        "Evaluate EVERY acceptance criterion strictly from observable visual and audio evidence in the video.",
        "Do NOT assume unobserved details passed. Populate criteria_results for every AC ID listed below:",
        *criteria_lines,
    ]
    if binding_lines:
        parts.append("Reference asset roles supplied alongside candidate video:")
        parts.extend(binding_lines)
    parts.append(
        "If any criterion fails, provide a concrete fix_instruction, edit_delta_prompt "
        "(starting with 'Keep everything else the same.'), and regenerated_prompt."
    )
    return "\n".join(parts)


def validate_rubric_verdict(verdict_data: Any, spec: dict[str, Any]) -> dict[str, Any]:
    """Deterministic Python provenance & consistency validator over model judgement (S9)."""
    validation_errors: list[str] = []
    if not isinstance(verdict_data, dict):
        return {
            "all_passed": False,
            "pass_ratio": 0.0,
            "failed_ids": [item["id"] for item in spec.get("acceptance_criteria", [])],
            "fix_instructions": [],
            "validation_errors": ["verdict_not_json_object"],
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
        }

    raw_results = verdict_data.get("criteria_results")
    if not isinstance(raw_results, list):
        return {
            "all_passed": False,
            "pass_ratio": 0.0,
            "failed_ids": [item["id"] for item in spec.get("acceptance_criteria", [])],
            "fix_instructions": [],
            "validation_errors": ["missing_criteria_results_list"],
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
        }

    by_id: dict[str, dict[str, Any]] = {}
    for entry in raw_results:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            validation_errors.append("malformed_criterion_entry")
            continue
        cid = entry["id"]
        if cid in by_id:
            validation_errors.append(f"duplicate_criterion_id:{cid}")
            continue
        by_id[cid] = entry

    mandatory_items = [
        item for item in spec.get("acceptance_criteria", []) if item.get("mandatory", True)
    ]
    mandatory_ids = [item["id"] for item in mandatory_items]
    if not mandatory_ids:
        validation_errors.append("zero_mandatory_acceptance_criteria")
        return {
            "all_passed": False,
            "pass_ratio": 0.0,
            "passed_count": 0,
            "total_mandatory": 0,
            "failed_ids": [item["id"] for item in spec.get("acceptance_criteria", [])],
            "fix_instructions": [],
            "validation_errors": validation_errors,
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
            "criteria_results": raw_results,
        }

    passed_count = 0
    failed_ids: list[str] = []
    fix_instructions: list[str] = []

    for spec_item in mandatory_items:
        ac_id = spec_item["id"]
        if ac_id not in by_id:
            validation_errors.append(f"missing_mandatory_ac:{ac_id}")
            failed_ids.append(ac_id)
            fix_instructions.append(f"Satisfy missing requirement {ac_id}: {spec_item['requirement']}")
            continue

        judged = by_id[ac_id]
        passed_val = judged.get("passed")
        evidence = str(judged.get("observed_evidence") or "").strip()
        fix_text = str(judged.get("fix_instruction") or "").strip()

        if not isinstance(passed_val, bool):
            validation_errors.append(f"non_boolean_passed:{ac_id}")
            failed_ids.append(ac_id)
            continue

        if not evidence:
            validation_errors.append(f"empty_observed_evidence:{ac_id}")
            failed_ids.append(ac_id)
            continue

        if passed_val:
            passed_count += 1
        else:
            failed_ids.append(ac_id)
            fix_instructions.append(fix_text or f"Fix failed requirement: {spec_item['requirement']}")

    # Detect two-way self-contradictory top-level model claims (S9 anti-rubber-stamp guard)
    computed_pass = (len(failed_ids) == 0) and (len(validation_errors) == 0)
    status_lower = str(verdict_data.get("status", "")).lower()
    claimed_pass = verdict_data.get("overall_passed") is True or (
        status_lower in {"pass", "passed", "verified"}
    )
    claimed_fail = verdict_data.get("overall_passed") is False or (
        status_lower in {"fail", "failed", "rejected"}
    )
    if (claimed_pass and not computed_pass) or (claimed_fail and computed_pass):
        validation_errors.append("self_contradictory_model_summary")

    total_mandatory = len(mandatory_ids)
    pass_ratio = passed_count / total_mandatory
    all_passed = (len(failed_ids) == 0) and (len(validation_errors) == 0)

    return {
        "all_passed": all_passed,
        "pass_ratio": pass_ratio,
        "passed_count": passed_count,
        "total_mandatory": total_mandatory,
        "failed_ids": failed_ids,
        "fix_instructions": fix_instructions,
        "validation_errors": validation_errors,
        "edit_delta_prompt": str(verdict_data.get("edit_delta_prompt") or "").strip(),
        "regenerated_prompt": str(verdict_data.get("regenerated_prompt") or "").strip(),
        "criteria_results": raw_results,
    }


def _regenerated_prompt_preserves_directives(regen: str, spec: dict[str, Any]) -> bool:
    """Ensure model-proposed regenerated_prompt retains NL asset bindings & core directives (P2 #22)."""
    if validate_expanded_prompt(spec.get("raw_prompt", ""), regen):
        return False
    regen_lower = regen.lower()
    ec = spec.get("explicit_constraints", {})
    for binding in ec.get("asset_bindings", []):
        directive = str(binding.get("natural_language_directive") or "").strip()
        if directive and directive.lower() not in regen_lower:
            return False
    compiled_lower = str(spec.get("compiled_prompt") or "").lower()
    if (spec.get("mode") == "single-shot" or "single continuous unbroken shot" in compiled_lower) and (
        "single continuous unbroken shot" not in regen_lower
    ):
        return False
    if ec.get("audio_mode") == "silent" and "no audio" not in regen_lower and "silent" not in regen_lower:
        return False
    if "extend this video" in compiled_lower and "extend this video" not in regen_lower:
        return False
    if "keep everything else the same" in compiled_lower and "keep everything else the same" not in regen_lower:
        return False
    return True


def select_remediation_mode(
    *,
    mechanical_passed: bool,
    rubric_validation: dict[str, Any],
    previous_response_id: str | None,
    has_video_refs: bool,
    spec: dict[str, Any],
) -> tuple[str, str]:
    """Deterministically select `edit_turn` (>=70% ACs + mech pass) vs `regenerate`."""
    pass_ratio = float(rubric_validation.get("pass_ratio", 0.0))
    fixes = rubric_validation.get("fix_instructions", [])
    joined_fixes = " ".join(f.strip() for f in fixes if f.strip())

    can_edit_turn = (
        mechanical_passed
        and pass_ratio >= 0.70
        and bool(previous_response_id)
        and not has_video_refs
        and not rubric_validation.get("validation_errors")
    )
    if can_edit_turn:
        delta = str(rubric_validation.get("edit_delta_prompt") or "").strip()
        if not delta:
            delta = f"Keep everything else the same. {joined_fixes}".strip()
        elif not delta.lower().startswith("keep everything else the same"):
            delta = f"Keep everything else the same. {delta}"
        return "edit_turn", delta

    regen = str(rubric_validation.get("regenerated_prompt") or "").strip()
    if regen and _regenerated_prompt_preserves_directives(regen, spec):
        base_regen = regen
    else:
        base_regen = str(spec["compiled_prompt"])
    if joined_fixes:
        return "regenerate", f"{base_regen} Mandatory corrections: {joined_fixes}".strip()
    return "regenerate", base_regen


def run_blinded_multimodal_judge(
    *,
    candidate_input: str,
    reference_inputs: Sequence[str],
    spec: dict[str, Any],
    preferred_verifier: str,
    runner: RunnerCallable,
) -> tuple[dict[str, Any], str, bool]:
    """Invoke blinded judge across VERIFIER_MODEL_CHAIN with deterministic validation."""
    if preferred_verifier in VERIFIER_MODEL_CHAIN:
        start_idx = VERIFIER_MODEL_CHAIN.index(preferred_verifier)
        chain = VERIFIER_MODEL_CHAIN[start_idx:]
    else:
        chain = (preferred_verifier, *VERIFIER_MODEL_CHAIN)

    judge_prompt = build_blinded_judge_prompt(spec)
    body = {
        "store": False,
        "generation_config": {"thinking_level": "high"},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": VERDICT_JSON_SCHEMA,
        },
    }
    body_str = json.dumps(body, sort_keys=True)

    last_err = "Blinded multimodal judge failed"
    for verifier_model in chain:
        cmd: list[str] = [
            "gemini-api",
            "generate",
            judge_prompt,
            "-m",
            verifier_model,
            "-i",
            candidate_input,
        ]
        for ref_item in reference_inputs:
            cmd.extend(["-i", ref_item])
        cmd.extend(["--stream=false", "-o", "json", "--body", body_str])

        res = runner(cmd)
        if res.returncode == 0:
            try:
                verdict_obj = json.loads(_extract_generate_text(res.stdout))
            except ValueError as exc:
                last_err = f"Invalid JSON from verifier {verifier_model}: {exc}"
                continue
            validated = validate_rubric_verdict(verdict_obj, spec)
            return validated, verifier_model, False

        last_err = redact_secrets(res.stderr or res.stdout).strip()
        if _is_transient_quota_or_capacity_error(res):
            continue
        raise RuntimeError(f"Verifier {verifier_model} exited {res.returncode}: {last_err}")

    raise RuntimeError(f"All verifier models in chain exhausted: {last_err}")


# ---------------------------------------------------------------------------
# Post-Processing, Storyboard & Multi-Segment Timeline Delegation
# ---------------------------------------------------------------------------


def _has_post_processing(config: VideoJobConfig) -> bool:
    has_custom_audio = (
        config.audio_mode in ("narration", "bgm", "full-mix")
        or bool(config.voice_track)
        or bool(config.bgm_track)
        or bool(config.sfx_cues)
        or bool(config.narration_text)
        or bool(config.bgm_prompt)
    )
    has_text_overlays = bool(
        config.srt
        or config.captions_json
        or config.title_card
        or config.lower_thirds
        or config.end_card
    )
    return has_custom_audio or has_text_overlays


def _expected_resolution_pixels(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    short_edge, long_edge = RESOLUTION_DIMENSIONS[resolution]
    return (long_edge, short_edge) if aspect_ratio == "16:9" else (short_edge, long_edge)


def _run_post_processing_pipeline(
    config: VideoJobConfig,
    input_video: Path,
    output_video: Path,
    *,
    video_duration_s: float,
    runner: RunnerCallable,
    which_fn: WhichCallable,
    env: Mapping[str, str] | None = None,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
) -> tuple[dict[str, Any], list[str]]:
    """Run audio scoring/2-pass loudnorm and post-composite captions/motion cards."""
    effective_env = os.environ if env is None else env
    unchecked: list[str] = []

    if not _has_post_processing(config):
        if input_video.resolve() != output_video.resolve():
            output_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_video, output_video)
        return {"applied": False}, unchecked

    cs_info = discover_creative_stack(config.creative_stack, env=effective_env)
    ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg", env=effective_env, which_fn=which_fn)
    ffprobe_bin = resolve_ffmpeg_binary("ffprobe", env=effective_env, which_fn=which_fn)
    eff_audio_gen = (
        Path(config.audio_gen_script).expanduser().resolve()
        if config.audio_gen_script
        else audio_gen_script
    )
    width, height = _expected_resolution_pixels(config.aspect_ratio, config.resolution)

    with tempfile.TemporaryDirectory(prefix="video-gen-post-") as tmp_str:
        tmp_dir = Path(tmp_str)
        after_audio = tmp_dir / "post_audio.mp4"
        audio_rep = video_post.apply_audio_mix_and_master(
            input_video,
            after_audio,
            audio_mode=config.audio_mode,
            target_duration_s=video_duration_s,
            voice_track=config.voice_track,
            bgm_track=config.bgm_track,
            sfx_cues=config.sfx_cues,
            narration_text=config.narration_text,
            voice_name=config.voice_name,
            bgm_prompt=config.bgm_prompt,
            duck_db=config.duck_db,
            lufs_target=config.lufs_target,
            audio_gen_script=eff_audio_gen,
            creative_stack=cs_info,
            ffmpeg_bin=ffmpeg_bin,
            ffprobe_bin=ffprobe_bin,
            raw_prompt=config.raw_prompt,
            no_verify=config.no_verify,
            runner=runner,
        )
        text_rep = video_post.apply_post_text_and_cards(
            after_audio,
            output_video,
            video_duration_s=video_duration_s,
            width=width,
            height=height,
            srt_path=config.srt,
            captions_json_path=config.captions_json,
            caption_style=config.caption_style,
            title_card=config.title_card,
            lower_thirds=config.lower_thirds,
            end_card=config.end_card,
            creative_stack=cs_info,
            ffmpeg_bin=ffmpeg_bin,
            runner=runner,
        )

    return (
        {
            "applied": bool(audio_rep.get("applied") or text_rep.get("applied")),
            "creative_stack": cs_info.to_dict(),
            "ffmpeg_binary": contract_home(ffmpeg_bin) if ffmpeg_bin else None,
            "audio_renderer": audio_rep.get("audio_renderer"),
            "caption_renderer": text_rep.get("caption_renderer"),
            "card_renderer": text_rep.get("card_renderer"),
            "audio": audio_rep,
            "text_and_cards": text_rep,
        },
        unchecked,
    )


def run_storyboard_pipeline(
    config: VideoJobConfig,
    *,
    runner: RunnerCallable,
    which_fn: WhichCallable,
    sleep_fn: Callable[[float], None],
    env: Mapping[str, str] | None = None,
) -> int:
    """Delegate storyboard manifest orchestration to `video_timeline.run_storyboard_pipeline`."""
    return video_timeline.run_storyboard_pipeline(
        config,
        validate_constraints_fn=lambda cfg: validate_omni_constraints(cfg, env=env),
        run_single_segment_fn=run_single_video_job,
        run_mechanical_check_fn=run_mechanical_video_check,
        run_post_pipeline_fn=_run_post_processing_pipeline,
        asset_cache_cls=AssetUploadCache,
        valid_aspect_ratios=VALID_ASPECT_RATIOS,
        runner=runner,
        which_fn=which_fn,
        sleep_fn=sleep_fn,
        env=env,
    )


# ---------------------------------------------------------------------------
# `--doctor` Diagnostics & Single-Job Orchestrator
# ---------------------------------------------------------------------------


def run_doctor(
    *,
    runner: RunnerCallable,
    which_fn: WhichCallable,
    env: Mapping[str, str],
    image_gen_script: Path,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
) -> int:
    """Inspect gemini-api, auth, keyring shadowing, ffmpeg-full, creative-stack, and companions."""
    gemini_bin = which_fn("gemini-api")
    ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg", env=env, which_fn=which_fn)
    ffprobe_bin = resolve_ffmpeg_binary("ffprobe", env=env, which_fn=which_fn)
    warnings: list[str] = []

    version_str: str | None = None
    whoami_info: dict[str, Any] | None = None

    if gemini_bin:
        ver_res = runner(["gemini-api", "--version"])
        if ver_res.returncode == 0:
            version_str = ver_res.stdout.strip()
        who_res = runner(["gemini-api", "whoami", "-o", "json"])
        if who_res.returncode == 0:
            try:
                whoami_info = json.loads(who_res.stdout)
            except ValueError:
                whoami_info = {"raw": who_res.stdout.strip()}
    else:
        warnings.append(
            "gemini-api binary not found on PATH. Install via https://aistudio.google.com/docs/cli "
            "or run: bash scripts/install.sh --with-media-tools"
        )

    if env.get("GEMINI_API_KEY"):
        msg = (
            "GEMINI_API_KEY is set in the environment and may shadow OS keyring credentials "
            "configured via 'gemini-api auth login' (see https://aistudio.google.com/docs/cli)."
        )
        warnings.append(msg)
        print(f"[video-gen] WARNING: {msg}", file=sys.stderr)

    if not ffmpeg_bin or not ffprobe_bin:
        warnings.append(
            "ffmpeg/ffprobe missing on PATH; Stage 3 stream metadata inspection, multi-segment "
            "stitching, post-composite captions/cards, and 2-pass loudnorm require ffmpeg/ffprobe."
        )

    cs_info = discover_creative_stack("auto", env=env)

    report = {
        "tool": "video-gen",
        "ready": bool(gemini_bin),
        "primary_video_model": PRIMARY_VIDEO_MODEL,
        "verifier_model_chain": list(VERIFIER_MODEL_CHAIN),
        "binaries": {
            "gemini-api": contract_home(gemini_bin) if gemini_bin else None,
            "ffmpeg": contract_home(ffmpeg_bin) if ffmpeg_bin else None,
            "ffprobe": contract_home(ffprobe_bin) if ffprobe_bin else None,
        },
        "gemini_api_version": version_str,
        "auth": whoami_info,
        "creative_stack": cs_info.to_dict(),
        "companion_image_gen_available": image_gen_script.is_file(),
        "companion_audio_gen_available": audio_gen_script.is_file(),
        "warnings": warnings,
    }
    print(json.dumps(report, indent=2))
    return 0 if gemini_bin else 1


def _sanitize_spec_paths(obj: Any) -> Any:
    """Recursively redact secrets and replace user home prefixes across spec payloads (S8, K7)."""
    if isinstance(obj, str):
        cleaned = redact_secrets(obj)
        home = str(Path.home().resolve())
        if home and home != "/" and home in cleaned:
            cleaned = cleaned.replace(home, "~")
        return cleaned
    if isinstance(obj, list):
        return [_sanitize_spec_paths(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_spec_paths(v) for k, v in obj.items()}
    return obj


def run_single_video_job(
    config: VideoJobConfig,
    *,
    runner: RunnerCallable,
    which_fn: WhichCallable,
    sleep_fn: Callable[[float], None],
    env: Mapping[str, str] | None = None,
    image_gen_script: Path = DEFAULT_IMAGE_GEN_SCRIPT,
    audio_gen_script: Path = DEFAULT_AUDIO_GEN_SCRIPT,
    asset_cache: AssetUploadCache | None = None,
    skip_post_processing: bool = False,
) -> int:
    """Execute the 4-stage video generation, verification, and post-processing pipeline."""
    effective_env = os.environ if env is None else env
    output_path = Path(config.output).resolve()

    # Validate user-supplied --image-ref magic headers before keyframe delegation or upload
    if not config.dry_run:
        for raw_ref in config.image_refs:
            _, ref_target = parse_image_ref(raw_ref)
            if not _is_files_uri(ref_target):
                ref_path = Path(ref_target).resolve()
                if not ref_path.is_file():
                    print(f"error: Input asset not found: {contract_home(ref_path)}", file=sys.stderr)
                    return 2
                try:
                    _validate_image_file_header(ref_path)
                except ValueError as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    return 2

    # Delegate keyframe synthesis first if requested
    active_config = config
    planned_keyframe_cmds: list[list[str]] = []
    if config.synthesize_keyframes and not config.dry_run:
        try:
            start_png, end_png = synthesize_keyframes_via_image_gen(
                config,
                output_path=output_path,
                image_gen_script=image_gen_script,
                runner=runner,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        active_config = dataclasses.replace(
            config,
            synthesize_keyframes=None,
            first_frame=str(start_png),
            last_frame=str(end_png) if end_png else None,
        )
    elif config.synthesize_keyframes and config.dry_run:
        if not image_gen_script.is_file():
            print(
                f"error: Companion skill script missing at '{contract_home(image_gen_script)}'.",
                file=sys.stderr,
            )
            return 2
        raw_kf_cmds, start_png, end_png = build_keyframe_commands(
            config, output_path=output_path, image_gen_script=image_gen_script
        )
        planned_keyframe_cmds = [[_sanitize_spec_paths(tok) for tok in cmd] for cmd in raw_kf_cmds]
        active_config = dataclasses.replace(
            config,
            synthesize_keyframes=None,
            first_frame=str(start_png),
            last_frame=str(end_png) if end_png else None,
        )

    try:
        frozen_spec = compile_visual_spec(active_config)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if active_config.spec_file:
        ec = frozen_spec.get("explicit_constraints", {})
        spec_ar = ec.get("aspect_ratio")
        spec_res = ec.get("resolution")
        spec_dur = ec.get("duration_s")
        spec_audio = ec.get("audio_mode")
        spec_style = ec.get("style")

        if spec_ar and active_config._explicit_ar and active_config.aspect_ratio != spec_ar:
            print(
                f"error: CLI --aspect-ratio '{active_config.aspect_ratio}' conflicts with --spec-file "
                f"constraint '{spec_ar}'.",
                file=sys.stderr,
            )
            return 2
        if spec_res and active_config._explicit_resolution and active_config.resolution != spec_res:
            print(
                f"error: CLI --resolution '{active_config.resolution}' conflicts with --spec-file "
                f"constraint '{spec_res}'.",
                file=sys.stderr,
            )
            return 2
        if spec_dur is not None and active_config._explicit_duration and active_config.duration_s != spec_dur:
            print(
                f"error: CLI --duration '{active_config.duration_s}s' conflicts with --spec-file "
                f"constraint '{spec_dur}s'.",
                file=sys.stderr,
            )
            return 2
        if spec_audio and active_config._explicit_audio and active_config.audio_mode != spec_audio:
            print(
                f"error: CLI --audio-mode '{active_config.audio_mode}' conflicts with --spec-file "
                f"constraint '{spec_audio}'.",
                file=sys.stderr,
            )
            return 2

        active_config = dataclasses.replace(
            active_config,
            aspect_ratio=str(spec_ar) if spec_ar else active_config.aspect_ratio,
            resolution=str(spec_res) if spec_res else active_config.resolution,
            duration_s=int(spec_dur) if spec_dur is not None else active_config.duration_s,
            audio_mode=str(spec_audio) if spec_audio else active_config.audio_mode,
            style=spec_style if (active_config.style is None and spec_style is not None) else active_config.style,
        )
        post_spec_errors = validate_omni_constraints(
            active_config, env=effective_env, audio_gen_script=audio_gen_script
        )
        if post_spec_errors:
            for err in post_spec_errors:
                print(f"error: {err}", file=sys.stderr)
            return 2

    frozen_digest = str(frozen_spec["spec_digest"])

    if active_config.spec_out:
        spec_out_path = Path(active_config.spec_out).resolve()
        spec_out_path.parent.mkdir(parents=True, exist_ok=True)
        spec_out_path.write_text(
            json.dumps(_sanitize_spec_paths(frozen_spec), indent=2) + "\n", encoding="utf-8"
        )

    if active_config.dry_run:
        planned_inputs = [contract_home(p) for p in collect_ordered_input_paths(active_config)]
        cmd, body = build_video_cli_command(
            config=active_config,
            prompt_text=str(frozen_spec["compiled_prompt"]),
            ordered_inputs=planned_inputs,
            candidate_out=Path(contract_home(output_path)),
            model_id=active_config.model,
            previous_interaction_id=active_config.previous_interaction_id,
        )
        dry_payload: dict[str, Any] = {
            "dry_run": True,
            "spec": _sanitize_spec_paths(frozen_spec),
            "planned_command": [_sanitize_spec_paths(tok) for tok in cmd],
            "planned_body": body,
        }
        if planned_keyframe_cmds:
            dry_payload["planned_keyframe_commands"] = planned_keyframe_cmds
        if _has_post_processing(active_config) and not skip_post_processing:
            cs_preview = discover_creative_stack(active_config.creative_stack, env=effective_env)
            dry_payload["planned_post_processing"] = {
                "creative_stack": cs_preview.to_dict(),
                "audio_mode": active_config.audio_mode,
                "caption_style": active_config.caption_style if (active_config.srt or active_config.captions_json) else None,
            }
        print(json.dumps(dry_payload, indent=2))
        return 0

    # Verify local input files exist and obey 15s / 30s source duration caps pre-upload
    raw_input_paths = collect_ordered_input_paths(active_config)
    for in_path in raw_input_paths:
        if isinstance(in_path, Path) and not in_path.is_file():
            print(f"error: Input asset not found: {contract_home(in_path)}", file=sys.stderr)
            return 2

    src_video_raw = active_config.extend or active_config.video
    if src_video_raw and not active_config.prep_clip and not _is_files_uri(src_video_raw):
        probed_dur = _probe_video_duration_s(Path(src_video_raw).resolve(), runner, which_fn)
        if probed_dur is not None:
            if probed_dur > MAX_SOURCE_VIDEO_S + 0.25:
                print(
                    f"error: Source video duration ({probed_dur:.2f}s) exceeds {int(MAX_SOURCE_VIDEO_S)}s "
                    "Omni input cap. Pass --prep-clip to trim/normalise.",
                    file=sys.stderr,
                )
                return 2
            if active_config.extend and (probed_dur + active_config.duration_s) > MAX_CUMULATIVE_EXTEND_S + 0.25:
                print(
                    f"error: Cumulative extended duration ({probed_dur:.2f}s + {active_config.duration_s}s) "
                    f"exceeds {int(MAX_CUMULATIVE_EXTEND_S)}s cap.",
                    file=sys.stderr,
                )
                return 2

    if active_config.require_ffprobe and resolve_ffmpeg_binary("ffprobe", env=effective_env, which_fn=which_fn) is None:
        print("error: ffprobe not found on PATH (--require-ffprobe set).", file=sys.stderr)
        return 2

    if which_fn("gemini-api") is None:
        print(
            "error: 'gemini-api' CLI not found on PATH. Install from https://aistudio.google.com/docs/cli "
            "or run scripts/install.sh --with-media-tools.",
            file=sys.stderr,
        )
        return 1

    # Stage 1 optional prompt expansion (default on unless --raw-prompt)
    initial_prompt = str(frozen_spec["compiled_prompt"])
    if not active_config.raw_prompt:
        initial_prompt = maybe_expand_prompt(
            raw_prompt=str(frozen_spec["raw_prompt"]),
            deterministic_prompt=initial_prompt,
            verifier_model=active_config.verifier_model,
            runner=runner,
            extra_literals=active_config.scene_texts,
        )

    cache = asset_cache or AssetUploadCache(runner)
    attempts_ledger: list[dict[str, Any]] = []
    unchecked_surfaces: list[str] = []

    with tempfile.TemporaryDirectory(prefix="video-gen-work-") as work_tmp_str:
        work_tmp = Path(work_tmp_str)
        try:
            source_override, vref_overrides = _prepare_media_inputs(
                active_config, work_tmp, runner, which_fn
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        effective_paths = collect_ordered_input_paths(
            active_config,
            source_video_override=source_override,
            video_ref_overrides=vref_overrides,
        )
        path_counts: dict[Path | str, int] = {}
        for p in effective_paths:
            path_counts[p] = path_counts.get(p, 0) + 1

        current_prompt = initial_prompt
        current_prev_id = active_config.previous_interaction_id
        last_candidate_file: Path | None = None
        last_response_id: str | None = None
        last_model_used = active_config.model
        last_verifier_used: str | None = None
        degraded_verifier = False

        for attempt_num in range(1, active_config.max_attempts + 1):
            # Invariant check: frozen spec acceptance_criteria NEVER mutated across retries
            current_ac_canonical = json.dumps(frozen_spec["acceptance_criteria"], sort_keys=True)
            if hashlib.sha256(current_ac_canonical.encode("utf-8")).hexdigest() != frozen_digest:
                raise AssertionError("Frozen VisualRequirementSpec mutated across retry attempts!")

            force_cache = attempt_num > 1
            try:
                resolved_inputs = [
                    cache.resolve(p, force_upload=(force_cache or path_counts[p] > 1))
                    for p in effective_paths
                ]
            except RuntimeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1

            candidate_target = work_tmp / f"candidate_attempt_{attempt_num}.mp4"
            inputs_for_call = [] if (attempt_num > 1 and current_prev_id) else resolved_inputs

            try:
                gen_json, model_used = execute_video_generation_with_backoff(
                    config=active_config,
                    prompt_text=current_prompt,
                    ordered_inputs=inputs_for_call,
                    candidate_out=candidate_target,
                    previous_interaction_id=current_prev_id,
                    runner=runner,
                    sleep_fn=sleep_fn,
                )
            except RuntimeError as exc:
                attempts_ledger.append(
                    {
                        "attempt": attempt_num,
                        "stage": "generation",
                        "error": redact_secrets(str(exc)),
                    }
                )
                current_prev_id = active_config.previous_interaction_id
                current_prompt = initial_prompt
                if attempt_num == active_config.max_attempts:
                    break
                continue

            work_root = work_tmp.resolve()
            raw_gen_path = gen_json.get("path")
            written_path: Path | None = None
            if isinstance(raw_gen_path, str) and raw_gen_path.strip():
                raw_p = Path(raw_gen_path.strip())
                if raw_p.is_absolute():
                    resolved_gen = raw_p.resolve()
                else:
                    cwd_candidate = (Path.cwd() / raw_p).resolve()
                    dir_candidate = (work_root / raw_p).resolve()
                    resolved_gen = (
                        cwd_candidate
                        if cwd_candidate.is_relative_to(work_root) and cwd_candidate.is_file()
                        else dir_candidate
                    )
                if (
                    resolved_gen.is_relative_to(work_root)
                    and (
                        resolved_gen.stem == candidate_target.stem
                        or resolved_gen.stem.startswith(f"{candidate_target.stem}_")
                    )
                    and resolved_gen.is_file()
                ):
                    written_path = resolved_gen
                else:
                    attempts_ledger.append(
                        {
                            "attempt": attempt_num,
                            "stage": "generation",
                            "error": f"Refused generation output path outside staging dir: {raw_gen_path!r}",
                        }
                    )
                    current_prev_id = active_config.previous_interaction_id
                    current_prompt = initial_prompt
                    if attempt_num == active_config.max_attempts:
                        break
                    continue
            else:
                matches = sorted(
                    p
                    for p in work_root.glob(f"{candidate_target.stem}.*")
                    if p.is_file() and p.resolve().is_relative_to(work_root)
                )
                if matches:
                    written_path = matches[0].resolve()
                else:
                    attempts_ledger.append(
                        {
                            "attempt": attempt_num,
                            "stage": "generation",
                            "error": "Generation JSON omitted 'path' and no staged candidate file was found.",
                        }
                    )
                    current_prev_id = active_config.previous_interaction_id
                    current_prompt = initial_prompt
                    if attempt_num == active_config.max_attempts:
                        break
                    continue

            last_candidate_file = written_path
            last_response_id = str(gen_json.get("response_id") or "") or None
            last_model_used = model_used

            # During raw clip check, custom post-scored modes (narration/bgm/full-mix) accept "any"
            # audio stream from Omni and apply authoritative 2-pass loudnorm audio during post-processing.
            expected_audio = (
                "silent"
                if active_config.audio_mode == "silent"
                else ("required" if active_config.audio_mode == "required" else "any")
            )
            mech_verdict, mech_unchecked = run_mechanical_video_check(
                written_path,
                expected_ar=active_config.aspect_ratio,
                expected_resolution=active_config.resolution,
                expected_duration_s=active_config.duration_s,
                expected_audio=expected_audio,
                require_ffprobe=active_config.require_ffprobe,
                runner=runner,
                which_fn=which_fn,
            )
            for surf in mech_unchecked:
                if surf not in unchecked_surfaces:
                    unchecked_surfaces.append(surf)

            rubric_result: dict[str, Any] | None = None
            if not mech_verdict["passed"]:
                attempts_ledger.append(
                    {
                        "attempt": attempt_num,
                        "model_used": model_used,
                        "response_id": last_response_id,
                        "mechanical": mech_verdict,
                        "rubric": None,
                    }
                )
                if attempt_num < active_config.max_attempts:
                    current_prev_id = None
                    mech_fix = ", ".join(mech_verdict["failures"])
                    current_prompt = (
                        f"{frozen_spec['compiled_prompt']} "
                        f"Ensure output strictly matches {active_config.aspect_ratio} "
                        f"{active_config.resolution} {active_config.duration_s}s ({mech_fix})."
                    )
                    continue
            elif active_config.no_verify:
                if "stage4_multimodal_rubric" not in unchecked_surfaces:
                    unchecked_surfaces.append("stage4_multimodal_rubric")
                post_report: dict[str, Any] = {"applied": False}
                if not skip_post_processing and _has_post_processing(active_config):
                    try:
                        post_report, post_un = _run_post_processing_pipeline(
                            active_config,
                            written_path,
                            output_path,
                            video_duration_s=float(mech_verdict.get("duration_s") or active_config.duration_s),
                            runner=runner,
                            which_fn=which_fn,
                            env=effective_env,
                            audio_gen_script=audio_gen_script,
                        )
                    except ValueError as exc:
                        print(f"error: {exc}", file=sys.stderr)
                        return 2
                    except RuntimeError as exc:
                        print(f"error: {exc}", file=sys.stderr)
                        return 1
                    for s in post_un:
                        if s not in unchecked_surfaces:
                            unchecked_surfaces.append(s)
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(written_path, output_path)
                prov: dict[str, Any] = {
                    "schema_version": 1,
                    "status": "MECHANICAL_ONLY",
                    "generated_at": utc_now_iso(),
                    "model_used": last_model_used,
                    "verifier_model_used": None,
                    "degraded_verifier_fallback": False,
                    "attempts_used": attempt_num,
                    "max_attempts": active_config.max_attempts,
                    "response_id": last_response_id,
                    "output_path": contract_home(output_path),
                    "spec_digest": frozen_digest,
                    "spec": _sanitize_spec_paths(frozen_spec),
                    "mechanical_verification": mech_verdict,
                    "rubric_verification": None,
                    "unchecked_surfaces": unchecked_surfaces,
                }
                if post_report.get("applied"):
                    prov["post_processing"] = post_report
                    Path(f"{output_path}.report.json").write_text(
                        json.dumps(prov, indent=2) + "\n", encoding="utf-8"
                    )
                else:
                    Path(f"{output_path}.report.json").unlink(missing_ok=True)
                Path(f"{output_path}.provenance.json").write_text(
                    json.dumps(prov, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps({"status": "MECHANICAL_ONLY", "output": contract_home(output_path)}))
                return 0
            else:
                try:
                    cand_judge_arg = cache.resolve(written_path, force_upload=False)
                    rubric_result, verifier_used, deg = run_blinded_multimodal_judge(
                        candidate_input=cand_judge_arg,
                        reference_inputs=resolved_inputs,
                        spec=frozen_spec,
                        preferred_verifier=active_config.verifier_model,
                        runner=runner,
                    )
                    last_verifier_used = verifier_used
                    degraded_verifier = degraded_verifier or deg
                except RuntimeError as exc:
                    attempts_ledger.append(
                        {
                            "attempt": attempt_num,
                            "model_used": model_used,
                            "response_id": last_response_id,
                            "mechanical": mech_verdict,
                            "judge_error": redact_secrets(str(exc)),
                        }
                    )
                    current_prev_id = active_config.previous_interaction_id
                    current_prompt = initial_prompt
                    if attempt_num == active_config.max_attempts:
                        break
                    continue

                attempts_ledger.append(
                    {
                        "attempt": attempt_num,
                        "model_used": model_used,
                        "verifier_model_used": last_verifier_used,
                        "response_id": last_response_id,
                        "mechanical": mech_verdict,
                        "rubric": rubric_result,
                    }
                )

                if rubric_result["all_passed"]:
                    post_report = {"applied": False}
                    if not skip_post_processing and _has_post_processing(active_config):
                        try:
                            post_report, post_un = _run_post_processing_pipeline(
                                active_config,
                                written_path,
                                output_path,
                                video_duration_s=float(mech_verdict.get("duration_s") or active_config.duration_s),
                                runner=runner,
                                which_fn=which_fn,
                                env=effective_env,
                                audio_gen_script=audio_gen_script,
                            )
                        except ValueError as exc:
                            print(f"error: {exc}", file=sys.stderr)
                            return 2
                        except RuntimeError as exc:
                            print(f"error: {exc}", file=sys.stderr)
                            return 1
                        for s in post_un:
                            if s not in unchecked_surfaces:
                                unchecked_surfaces.append(s)
                    else:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(written_path, output_path)
                    prov = {
                        "schema_version": 1,
                        "status": "VERIFIED",
                        "generated_at": utc_now_iso(),
                        "model_used": last_model_used,
                        "verifier_model_used": last_verifier_used,
                        "degraded_verifier_fallback": degraded_verifier,
                        "attempts_used": attempt_num,
                        "max_attempts": active_config.max_attempts,
                        "response_id": last_response_id,
                        "output_path": contract_home(output_path),
                        "spec_digest": frozen_digest,
                        "spec": _sanitize_spec_paths(frozen_spec),
                        "mechanical_verification": mech_verdict,
                        "rubric_verification": rubric_result,
                        "unchecked_surfaces": unchecked_surfaces,
                    }
                    if post_report.get("applied"):
                        prov["post_processing"] = post_report
                        Path(f"{output_path}.report.json").write_text(
                            json.dumps(prov, indent=2) + "\n", encoding="utf-8"
                        )
                    else:
                        Path(f"{output_path}.report.json").unlink(missing_ok=True)
                    Path(f"{output_path}.provenance.json").write_text(
                        json.dumps(prov, indent=2) + "\n", encoding="utf-8"
                    )
                    print(
                        json.dumps(
                            {
                                "status": "VERIFIED",
                                "output": contract_home(output_path),
                                "attempts_used": attempt_num,
                                "response_id": last_response_id,
                            }
                        )
                    )
                    return 0

                if attempt_num < active_config.max_attempts:
                    rem_mode, next_prompt = select_remediation_mode(
                        mechanical_passed=True,
                        rubric_validation=rubric_result,
                        previous_response_id=last_response_id,
                        has_video_refs=bool(active_config.video_refs),
                        spec=frozen_spec,
                    )
                    current_prompt = next_prompt
                    current_prev_id = last_response_id if rem_mode == "edit_turn" else None

        # Retries exhausted! Enforce S3 hard exit contract unless --allow-unverified + --override-reason
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path = Path(f"{output_path}.report.json")

        if active_config.allow_unverified and last_candidate_file and last_candidate_file.is_file():
            reason_clean = _sanitize_spec_paths(str(active_config.override_reason or "").strip())
            print(
                f"[video-gen] WARNING: Verification failed after {active_config.max_attempts} attempt(s), "
                f"but --allow-unverified override is set (reason: {reason_clean!r}); "
                f"writing UNVERIFIED artefact to {contract_home(output_path)}.",
                file=sys.stderr,
            )
            shutil.copy2(last_candidate_file, output_path)
            override_prov = {
                "schema_version": 1,
                "status": "UNVERIFIED_OVERRIDE",
                "override_reason": reason_clean,
                "generated_at": utc_now_iso(),
                "model_used": last_model_used,
                "verifier_model_used": last_verifier_used,
                "degraded_verifier_fallback": degraded_verifier,
                "attempts_used": len(attempts_ledger),
                "max_attempts": active_config.max_attempts,
                "response_id": last_response_id,
                "output_path": contract_home(output_path),
                "spec_digest": frozen_digest,
                "spec": _sanitize_spec_paths(frozen_spec),
                "attempts": attempts_ledger,
                "unchecked_surfaces": unchecked_surfaces,
            }
            Path(f"{output_path}.provenance.json").write_text(
                json.dumps(override_prov, indent=2) + "\n", encoding="utf-8"
            )
            report_path.write_text(json.dumps(override_prov, indent=2) + "\n", encoding="utf-8")
            return 0

        rejected_path: Path | None = None
        if last_candidate_file and last_candidate_file.is_file():
            rej_suffix = last_candidate_file.suffix or output_path.suffix or ".mp4"
            rejected_path = output_path.parent / f"{output_path.stem}.rejected{rej_suffix}"
            shutil.copy2(last_candidate_file, rejected_path)

        if output_path.exists():
            output_path.unlink()
        stale_prov = Path(f"{output_path}.provenance.json")
        if stale_prov.is_file():
            stale_prov.unlink()

        failure_report = {
            "schema_version": 1,
            "status": "FAILED_VERIFICATION",
            "generated_at": utc_now_iso(),
            "spec_digest": frozen_digest,
            "rejected_candidate_path": contract_home(rejected_path) if rejected_path else None,
            "attempts": attempts_ledger,
            "unchecked_surfaces": unchecked_surfaces,
        }
        report_path.write_text(json.dumps(failure_report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED_VERIFICATION", "report": contract_home(report_path)}))
        print(
            f"error: Video verification failed after {active_config.max_attempts} attempt(s). "
            f"See {contract_home(report_path)}.",
            file=sys.stderr,
        )
        return 1


# ---------------------------------------------------------------------------
# CLI Argument Parser & Entrypoint (S6)
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video_gen.py",
        description=(
            "Generate, chain, score, caption, extend, edit, and verify MP4 videos of any length "
            "with Gemini Omni 1.2 Flash via the official gemini-api CLI."
        ),
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default="",
        help="Scene, camera trajectory, action, soundscape, or edit prompt.",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Path to multi-beat JSON or Markdown script file for arbitrary-duration timelines.",
    )
    parser.add_argument(
        "--continuity",
        choices=VALID_CONTINUITY_MODES,
        default="keyframe-chain",
        help="Multi-segment continuity strategy: keyframe-chain (default), scene-cuts, or extend-blocks.",
    )
    parser.add_argument(
        "--crossfade-sec",
        type=float,
        default=0.0,
        help="Crossfade overlap in seconds (0.0..2.0) between stitched timeline segments (default: 0.0).",
    )
    parser.add_argument(
        "--spec-file",
        default=None,
        help="Load a pre-compiled VisualRequirementSpec JSON file instead of compiling from --prompt.",
    )
    parser.add_argument(
        "--spec-out",
        default=None,
        help="Optional path to write the frozen VisualRequirementSpec JSON (spec.json).",
    )
    parser.add_argument(
        "--storyboard",
        default=None,
        help="Path to keyframes_manifest.json emitted by image-gen for multi-segment video production.",
    )
    parser.add_argument(
        "--storyboard-mode",
        choices=("transitions", "clips"),
        default="transitions",
        help="Generate frame-to-frame transitions (default) or per-frame clips from --storyboard.",
    )
    parser.add_argument(
        "--first-frame",
        default=None,
        help="Starting keyframe image path (bound as input #1 via natural language).",
    )
    parser.add_argument(
        "--last-frame",
        default=None,
        help="Ending keyframe image path (requires --first-frame and --duration <= 10s).",
    )
    parser.add_argument(
        "--synthesize-keyframes",
        choices=("start", "start-end"),
        default=None,
        help="Delegate verified keyframe PNG synthesis to sibling skills/image-gen/scripts/image_gen.py.",
    )
    parser.add_argument(
        "--end-frame-prompt",
        default=None,
        help="Optional explicit end-frame prompt when --synthesize-keyframes start-end is used.",
    )
    parser.add_argument(
        "--image-ref",
        action="append",
        default=[],
        help="Reference image path (repeatable up to 6; supports char:/style:/prop: prefixes).",
    )
    parser.add_argument(
        "--video-ref",
        action="append",
        default=[],
        help="Reference motion clip (~3s; max 3 for 3-10s, max 1 for 11-15s; blocked on edit/extend).",
    )
    parser.add_argument(
        "--video",
        default=None,
        help="Source video clip (<= 15s) to edit.",
    )
    parser.add_argument(
        "--extend",
        default=None,
        help="Source video clip (<= 15s) to extend (3-10s per turn, <= 30s cumulative).",
    )
    parser.add_argument(
        "--task",
        choices=("extend", "edit", "interpolate"),
        default=None,
        help="Optional explicit generation_config.video_config.task (omitted by default on --extend).",
    )
    parser.add_argument(
        "--strip-audio",
        action="store_true",
        help="Strip audio via ffmpeg (-c:v copy -an) before upload so Omni 1.2 regenerates audio.",
    )
    parser.add_argument(
        "--prep-clip",
        action="store_true",
        help="Trim and 720p-normalise input video clips via ffmpeg before upload.",
    )
    parser.add_argument(
        "--ar",
        "--aspect-ratio",
        dest="aspect_ratio",
        choices=VALID_ASPECT_RATIOS,
        default="16:9",
        help="Target video aspect ratio: 16:9 or 9:16 (default: 16:9).",
    )
    parser.add_argument(
        "--resolution",
        choices=VALID_RESOLUTIONS,
        default="1080p",
        help="Target output resolution: 360p, 720p, 1080p, or 4k (default: 1080p).",
    )
    parser.add_argument(
        "--duration",
        dest="duration_s",
        type=parse_duration_seconds,
        default=8,
        help="Target video duration in integer seconds >= 3 (3..15s direct; > 15s auto-chains segments).",
    )
    parser.add_argument(
        "--single-shot",
        action="store_true",
        help="Enforce a single continuous unbroken shot with zero scene cuts.",
    )
    parser.add_argument(
        "--audio-mode",
        choices=VALID_AUDIO_MODES,
        default="native",
        help="Audio mode: native (Omni soundscape), silent, narration, bgm, or full-mix.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Shorthand for --audio-mode silent (verifies zero residual audio streams).",
    )
    parser.add_argument(
        "--voice-track",
        default=None,
        help="Local voiceover audio file (WAV/MP3/FLAC/OGG/M4A; magic-byte validated).",
    )
    parser.add_argument(
        "--bgm-track",
        default=None,
        help="Local background music audio file (looped/trimmed and ducked under speech).",
    )
    parser.add_argument(
        "--sfx-cue",
        dest="sfx_cues",
        action="append",
        default=[],
        help="Timed sound effect cue '<path>@<sec>[:<gain_db>]' (repeatable; magic-byte validated).",
    )
    parser.add_argument(
        "--narration-text",
        default=None,
        help="Narration script text delegated to sibling audio-gen (--mode voice).",
    )
    parser.add_argument(
        "--voice-name",
        default=None,
        help="Optional voice name forwarded to sibling audio-gen when --narration-text is used.",
    )
    parser.add_argument(
        "--bgm-prompt",
        default=None,
        help="Instrumental background music prompt delegated to sibling audio-gen (--mode bgm).",
    )
    parser.add_argument(
        "--audio-gen-script",
        default=None,
        help="Optional path to companion audio_gen.py (defaults to ../audio-gen/scripts/audio_gen.py).",
    )
    parser.add_argument(
        "--duck-db",
        type=float,
        default=DEFAULT_DUCK_DB,
        help=f"Exact dB to duck BGM under active speech windows via volume envelope (default: {DEFAULT_DUCK_DB}).",
    )
    parser.add_argument(
        "--lufs-target",
        type=float,
        default=DEFAULT_LUFS_TARGET,
        help=f"2-pass linear loudnorm target integrated loudness in LUFS at 48 kHz (default: {DEFAULT_LUFS_TARGET}).",
    )
    parser.add_argument(
        "--scene-text",
        dest="scene_texts",
        action="append",
        default=[],
        help="Exact in-scene kinetic/diegetic text verified via blinded gemini-4-argon OCR rubric (repeatable).",
    )
    parser.add_argument(
        "--srt",
        default=None,
        help="Post-composite SubRip (.srt) subtitle file path.",
    )
    parser.add_argument(
        "--captions-json",
        default=None,
        help="Post-composite JSON timed captions file path.",
    )
    parser.add_argument(
        "--caption-style",
        choices=VALID_CAPTION_STYLES,
        default="pill",
        help="Caption style: pill (default), highlight, karaoke, or soft (mov_text track).",
    )
    parser.add_argument(
        "--title-card",
        default=None,
        help="Opening motion title card '<title>[|<subtitle>]'.",
    )
    parser.add_argument(
        "--lower-third",
        dest="lower_thirds",
        action="append",
        default=[],
        help="Timed lower-third overlay '<name>|<role>@<start>-<end>' (repeatable).",
    )
    parser.add_argument(
        "--end-card",
        default=None,
        help="Closing call-to-action card '<cta>' (or '<title>|<cta>').",
    )
    parser.add_argument(
        "--creative-stack",
        default="auto",
        help="Creative-stack bridge discovery mode: auto (default), off, or <dir>.",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Optional visual style / cinematography direction.",
    )
    parser.add_argument(
        "--previous-interaction-id",
        default=None,
        help="Prior response_id (v1_...) for conversational multi-turn video editing.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum closed-loop generation + verification attempts (default: 3).",
    )
    parser.add_argument(
        "--model",
        default=PRIMARY_VIDEO_MODEL,
        help=f"Video generation model ID (default: {PRIMARY_VIDEO_MODEL}).",
    )
    parser.add_argument(
        "--verifier-model",
        default=VERIFIER_MODEL_CHAIN[0],
        help=f"Blinded multimodal rubric judge model ID (default: {VERIFIER_MODEL_CHAIN[0]}).",
    )
    parser.add_argument(
        "--raw-prompt",
        action="store_true",
        help="Skip Stage 1 LLM cinematographic prompt expansion.",
    )
    parser.add_argument(
        "--expand-prompt",
        action="store_true",
        help="Explicitly enable Stage 1 LLM prompt expansion (default unless --raw-prompt).",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip Stage 4 multimodal rubric verification (Stage 3 mechanical check still runs).",
    )
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Permit writing an unverified output with UNVERIFIED_OVERRIDE status (requires --override-reason).",
    )
    parser.add_argument(
        "--override-reason",
        default=None,
        help="Mandatory non-empty justification required whenever --allow-unverified is set.",
    )
    parser.add_argument(
        "--allow-legacy-video-fallback",
        action="store_true",
        help="Permit fallback to gemini-omni-1.1-flash on 429/503 when duration <= 10s and no extend refs.",
    )
    parser.add_argument(
        "--require-ffprobe",
        action="store_true",
        help="Fail closed if ffprobe is not installed on PATH.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate constraints, compile spec/timeline, and print planned JSON without network calls.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Inspect gemini-api CLI, auth status, ffmpeg-full, creative-stack, and companion skills.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="output.mp4",
        help="Verified MP4 output path (default: output.mp4).",
    )
    return parser


def parse_job_config(argv: Sequence[str] | None = None) -> VideoJobConfig:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    ns = parser.parse_args(raw_argv)
    audio_mode = "silent" if ns.silent else ns.audio_mode
    explicit_ar = any(
        tok in ("--ar", "--aspect-ratio")
        or tok.startswith("--ar=")
        or tok.startswith("--aspect-ratio=")
        for tok in raw_argv
    )
    explicit_resolution = any(
        tok == "--resolution" or tok.startswith("--resolution=") for tok in raw_argv
    )
    explicit_duration = any(
        tok == "--duration" or tok.startswith("--duration=") for tok in raw_argv
    )
    explicit_audio = any(
        tok in ("--audio-mode", "--silent") or tok.startswith("--audio-mode=")
        for tok in raw_argv
    )
    return VideoJobConfig(
        prompt=ns.prompt,
        spec_file=ns.spec_file,
        spec_out=ns.spec_out,
        storyboard=ns.storyboard,
        storyboard_mode=ns.storyboard_mode,
        script=ns.script,
        continuity=ns.continuity,
        crossfade_sec=float(ns.crossfade_sec),
        first_frame=ns.first_frame,
        last_frame=ns.last_frame,
        synthesize_keyframes=ns.synthesize_keyframes,
        end_frame_prompt=ns.end_frame_prompt,
        image_refs=list(ns.image_ref or []),
        video_refs=list(ns.video_ref or []),
        video=ns.video,
        extend=ns.extend,
        task=ns.task,
        strip_audio=bool(ns.strip_audio),
        prep_clip=bool(ns.prep_clip),
        aspect_ratio=ns.aspect_ratio,
        resolution=ns.resolution,
        duration_s=ns.duration_s,
        single_shot=bool(ns.single_shot),
        audio_mode=audio_mode,
        voice_track=ns.voice_track,
        bgm_track=ns.bgm_track,
        sfx_cues=list(ns.sfx_cues or []),
        narration_text=ns.narration_text,
        voice_name=ns.voice_name,
        bgm_prompt=ns.bgm_prompt,
        audio_gen_script=ns.audio_gen_script,
        duck_db=float(ns.duck_db),
        lufs_target=float(ns.lufs_target),
        scene_texts=list(ns.scene_texts or []),
        srt=ns.srt,
        captions_json=ns.captions_json,
        caption_style=ns.caption_style,
        title_card=ns.title_card,
        lower_thirds=list(ns.lower_thirds or []),
        end_card=ns.end_card,
        creative_stack=ns.creative_stack,
        style=ns.style,
        previous_interaction_id=ns.previous_interaction_id,
        max_attempts=ns.max_attempts,
        model=ns.model,
        verifier_model=ns.verifier_model,
        raw_prompt=bool(ns.raw_prompt),
        expand_prompt=bool(ns.expand_prompt),
        no_verify=bool(ns.no_verify),
        allow_unverified=bool(ns.allow_unverified),
        override_reason=ns.override_reason,
        allow_legacy_video_fallback=bool(ns.allow_legacy_video_fallback),
        require_ffprobe=bool(ns.require_ffprobe),
        dry_run=bool(ns.dry_run),
        doctor=bool(ns.doctor),
        output=ns.output,
        _explicit_ar=explicit_ar,
        _explicit_resolution=explicit_resolution,
        _explicit_duration=explicit_duration,
        _explicit_audio=explicit_audio,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: RunnerCallable = default_runner,
    which_fn: WhichCallable = shutil.which,
    env: Mapping[str, str] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    image_gen_script: Path | None = None,
    audio_gen_script: Path | None = None,
) -> int:
    try:
        config = parse_job_config(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    resolved_img_script = image_gen_script or DEFAULT_IMAGE_GEN_SCRIPT
    resolved_aud_script = (
        Path(config.audio_gen_script).expanduser().resolve()
        if config.audio_gen_script
        else (audio_gen_script or DEFAULT_AUDIO_GEN_SCRIPT)
    )
    effective_env = os.environ if env is None else env

    if config.doctor:
        return run_doctor(
            runner=runner,
            which_fn=which_fn,
            env=effective_env,
            image_gen_script=resolved_img_script,
            audio_gen_script=resolved_aud_script,
        )

    constraint_errors = validate_omni_constraints(
        config, env=effective_env, audio_gen_script=resolved_aud_script
    )
    if constraint_errors:
        for err in constraint_errors:
            print(f"error: {err}", file=sys.stderr)
        return 2

    if config.storyboard:
        return run_storyboard_pipeline(
            config,
            runner=runner,
            which_fn=which_fn,
            sleep_fn=sleep_fn,
            env=effective_env,
        )

    if is_multi_segment_job(config):
        return video_timeline.run_timeline_pipeline(
            config,
            run_single_segment_fn=lambda seg_cfg, **kw: run_single_video_job(
                seg_cfg, audio_gen_script=resolved_aud_script, **kw
            ),
            run_mechanical_check_fn=run_mechanical_video_check,
            run_post_pipeline_fn=lambda p_cfg, in_v, out_v, **kw: _run_post_processing_pipeline(
                p_cfg, in_v, out_v, audio_gen_script=resolved_aud_script, **kw
            ),
            parse_image_ref_fn=parse_image_ref,
            asset_cache_cls=AssetUploadCache,
            sanitize_fn=_sanitize_spec_paths,
            runner=runner,
            which_fn=which_fn,
            sleep_fn=sleep_fn,
            env=effective_env,
            image_gen_script=resolved_img_script,
        )

    return run_single_video_job(
        config,
        runner=runner,
        which_fn=which_fn,
        sleep_fn=sleep_fn,
        env=effective_env,
        image_gen_script=resolved_img_script,
        audio_gen_script=resolved_aud_script,
    )


if __name__ == "__main__":
    sys.exit(main())
