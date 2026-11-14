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

"""Grounded Audio Generation, Mastering & Blinded Verification Controller.

What this script audits and enforces (Engineering Standard V3)
--------------------------------------------------------------
1. Parse-time model routing, consent, and deprecation fence (``exit 2``):
   blocks shut-down TTS/music/video models, enforces distinct ``--source-audio``
   (10-30s WAV) + ``--consent-audio`` WAV digests on ``voice-replicate``,
    blocks non-multimodal/generator models passed to ``--verifier-model``, and
    requires ``--override-reason`` whenever ``--allow-unverified`` or ``--no-verify`` is requested.
 2. Stage 1 frozen ``AudioRequirementSpec`` (``spec_sha256``):
    compiles explicit musical/vocal/mixing constraints and implicit craft rules
    into atomic ``AC-*`` items (rejecting zero-mandatory specs with ``exit 2``).
 3. Stage 3 deterministic mechanical & loudness gate (``L3``, ``$0`` tokens):
    inspects WAV/MP3/FLAC/OGG/M4A binary headers and WAV PCM16/PCM24 sample
    amplitudes (rejecting digital silence and severe clipping), probes streams
    and duration via ``ffprobe``, and enforces 2-pass ``-14 LUFS`` (+/- 1.0) /
    ``-1.0 dBTP`` linear ``loudnorm`` at ``-ar 48000`` (``dual_mono=true`` on mono voiceovers).
 4. Stage 4 stateless blinded multimodal rubric judge + Python provenance
    validator (``S9``): invokes ``gemini-4-argon`` -> ``gemini-4-carbon`` with
    ``store: false``, verifies every frozen ``AC-*`` item has boolean ``passed``
    and non-empty ``observed_evidence``, computes ``all_passed`` in Python, and
    rejects self-contradictory model verdicts.

 What this script does NOT audit (Engineering Standard V5)
 ---------------------------------------------------------
 * Full compressed-frame psychoacoustic decoding on MP3/FLAC/OGG/M4A when
   ``ffmpeg``/``ffprobe`` are absent on ``PATH`` (recorded in ``unchecked_surfaces``).
 * Semantic musical/spoken adherence when ``--no-verify --override-reason`` is set
   (recorded as ``"stage4_multimodal_rubric"`` in ``unchecked_surfaces``).
 * Live API quota or remote synthesis when ``--dry-run`` is set (recorded as
   ``"live_generation_and_verification"`` in ``unchecked_surfaces``).

Exit codes: ``0`` verified pass (or ``--dry-run`` / healthy ``--doctor``),
``1`` verification or runtime synthesis failure, ``2`` invalid CLI flags,
deprecated model ID, consent failure, or corrupt input asset.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if sys.platform == "win32":  # pragma: no cover - Windows console UTF-8 guard
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audio_dsp  # noqa: E402
import audio_engines  # noqa: E402
from audio_engines import (  # noqa: E402
    AudioEngineError,
    ConfigError,
    DEPRECATED_MODEL_PREFIXES,
    HttpTransportCallable,
    RunnerCallable,
    VERIFIER_MODEL_CHAIN,
    contract_home,
    default_http_transport,
    default_runner,
    redact_secrets,
    validate_audio_model_id,
)

SUPPORTED_MODES: tuple[str, ...] = (
    "auto",
    "bgm",
    "song",
    "backing-track",
    "voice",
    "dialogue",
    "voice-design",
    "voice-replicate",
    "sfx",
    "stinger",
    "mix",
)

SUPPORTED_ENGINES: tuple[str, ...] = (
    "auto",
    "lyria",
    "gemini-tts",
    "chirp3",
    "voices-rest",
    "sfx",
    "mix",
)

SUPPORTED_SFX_ENGINES: tuple[str, ...] = (
    "auto",
    "omni-foley",
    "lyria-sting",
    "lavfi-synth",
    "creative-bed",
)

SUPPORTED_BED_STYLES: tuple[str, ...] = (
    "ambient",
    "corporate",
    "upbeat",
    "lofi",
    "tension",
)

AUDIO_RUBRIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_pass": {"type": "boolean"},
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
        "remediation_prompt": {"type": "string"},
    },
    "required": ["criteria_results", "remediation_prompt"],
}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Stage 1: Mode Resolution & Frozen AudioRequirementSpec Compilation
# ---------------------------------------------------------------------------


def compute_spec_sha256(acceptance_criteria: Sequence[Mapping[str, Any]]) -> str:
    """Compute canonical SHA-256 digest over frozen ``acceptance_criteria``."""
    canonical = json.dumps(list(acceptance_criteria), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def resolve_chirp_cloning_key(
    args: argparse.Namespace,
    env: Mapping[str, str],
    *,
    warn: bool = False,
) -> str | None:
    """Resolve Instant Custom Voice cloning key from file, env, or legacy argv flag."""
    cli_val = (getattr(args, "chirp_cloning_key", None) or "").strip()
    file_val = (getattr(args, "chirp_cloning_key_file", None) or "").strip()
    if cli_val and file_val:
        raise ConfigError("Specify at most one of --chirp-cloning-key or --chirp-cloning-key-file.")
    if file_val:
        kf = Path(file_val).expanduser().resolve()
        if not kf.is_file():
            raise ConfigError(f"--chirp-cloning-key-file not found: {contract_home(kf)}")
        key_text = kf.read_text(encoding="utf-8").strip()
        if not key_text:
            raise ConfigError("--chirp-cloning-key-file is empty.")
        return key_text
    if cli_val:
        if warn:
            print(
                "WARNING: Passing --chirp-cloning-key in argv exposes secrets via process listings "
                "(CWE-214); prefer CHIRP_VOICE_CLONING_KEY env var or --chirp-cloning-key-file.",
                file=sys.stderr,
            )
        return cli_val
    env_val = env.get("CHIRP_VOICE_CLONING_KEY", "").strip()
    return env_val or None


def resolve_mode_and_engine(
    args: argparse.Namespace,
    prompt_text: str,
    *,
    has_cloning_key: bool = False,
) -> tuple[str, str]:
    """Deterministically resolve ``(mode, engine)`` from flags and prompt cues."""
    req_mode = (args.mode or "auto").strip().lower()
    req_engine = (args.engine or "auto").strip().lower()
    if req_mode not in SUPPORTED_MODES:
        raise ConfigError(f"Unsupported --mode '{args.mode}'. Choose from: {', '.join(SUPPORTED_MODES)}")
    if req_engine not in SUPPORTED_ENGINES:
        raise ConfigError(
            f"Unsupported --engine '{args.engine}'. Choose from: {', '.join(SUPPORTED_ENGINES)}"
        )

    if req_mode == "auto":
        if args.strip_vocals_from:
            mode = "backing-track"
        elif args.source_audio or args.consent_audio:
            mode = "voice-replicate"
        elif args.voice_prompt:
            mode = "voice-design"
        elif args.voice_track and not prompt_text.strip():
            mode = "mix"
        elif args.lyrics or args.lyrics_file:
            mode = "song"
        elif args.speakers:
            mode = "dialogue"
        elif req_engine in ("chirp3", "gemini-tts"):
            mode = "voice"
        else:
            low = prompt_text.lower()
            if any(k in low for k in ("sound effect", "foley", "sfx", "whoosh", "footstep")):
                mode = "sfx"
            elif any(k in low for k in ("stinger", "logo sting", "sonic logo", "jingle cue")):
                mode = "stinger"
            elif any(k in low for k in ("backing track", "karaoke instrumental")):
                mode = "backing-track"
            elif any(k in low for k in ("bgm", "background music", "instrumental", "lofi", "ambient bed", "soundtrack")):
                mode = "bgm"
            elif any(k in low for k in ("full song", "vocal song", "singing", "verse", "chorus")):
                mode = "song"
            else:
                mode = "voice"
    else:
        mode = req_mode

    if req_engine == "auto":
        if mode in ("bgm", "song", "backing-track"):
            engine = "lyria"
        elif mode in ("voice", "dialogue"):
            engine = (
                "chirp3"
                if (has_cloning_key or args.chirp_cloning_key or args.pronunciations)
                else "gemini-tts"
            )
        elif mode in ("voice-design", "voice-replicate"):
            engine = "voices-rest"
        elif mode in ("sfx", "stinger"):
            engine = "sfx"
        else:
            engine = "mix"
    else:
        engine = req_engine

    if engine == "chirp3" and mode == "dialogue":
        raise ConfigError(
            "'--engine chirp3' supports single-speaker '--mode voice' only; "
            "use '--engine gemini-tts' for multi-speaker '--mode dialogue'."
        )
    if mode in ("bgm", "backing-track") and (args.lyrics or args.lyrics_file):
        raise ConfigError(
            f"--lyrics / --lyrics-file cannot be used with '--mode {mode}' (strictly instrumental)."
        )
    return mode, engine


def load_and_validate_spec_file(spec_file: str) -> dict[str, Any]:
    """Load ``--spec-file`` JSON, verify ``spec_sha256``, and enforce >=1 mandatory AC."""
    spec_path = Path(spec_file).expanduser().resolve()
    if not spec_path.is_file():
        raise ConfigError(f"--spec-file not found: {contract_home(spec_path)}")
    try:
        loaded = json.loads(spec_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"Invalid JSON in --spec-file '{contract_home(spec_path)}': {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError("--spec-file must contain a JSON object.")

    acs = loaded.get("acceptance_criteria")
    if not isinstance(acs, list) or not acs:
        raise ConfigError("--spec-file must define a non-empty 'acceptance_criteria' list.")

    mandatory_count = 0
    seen_ids: set[str] = set()
    for idx, item in enumerate(acs, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] must be an object.")
        for req_key in ("id", "category", "requirement"):
            val = item.get(req_key)
            if not isinstance(val, str) or not val.strip():
                raise ConfigError(
                    f"--spec-file acceptance_criteria[{idx}] missing non-empty '{req_key}'."
                )
        cid = item["id"].strip()
        if cid in seen_ids:
            raise ConfigError(f"--spec-file contains duplicate acceptance criterion id '{cid}'.")
        seen_ids.add(cid)
        mand = item.get("mandatory", True)
        if not isinstance(mand, bool):
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] 'mandatory' must be boolean.")
        if mand:
            mandatory_count += 1

    if mandatory_count == 0:
        raise ConfigError(
            "--spec-file defines zero mandatory acceptance criteria (S9 vacuous-pass refusal)."
        )

    expected_sha = compute_spec_sha256(acs)
    recorded_sha = loaded.get("spec_sha256")
    if recorded_sha is not None:
        if not isinstance(recorded_sha, str) or recorded_sha != expected_sha:
            raise ConfigError(
                "--spec-file 'spec_sha256' does not match canonical SHA-256 of 'acceptance_criteria'."
            )

    spec = dict(loaded)
    spec["spec_sha256"] = expected_sha
    raw_p = str(spec.get("raw_prompt") or spec.get("compiled_prompt") or "").strip()
    comp_p = str(spec.get("compiled_prompt") or raw_p).strip()
    if not raw_p:
        raise ConfigError("--spec-file must contain a non-empty 'raw_prompt' or 'compiled_prompt'.")
    spec["raw_prompt"] = raw_p
    spec["compiled_prompt"] = comp_p

    ec = spec.get("explicit_constraints")
    if ec is None:
        ec = {}
    elif not isinstance(ec, dict):
        raise ConfigError("--spec-file 'explicit_constraints' must be a JSON object.")
    else:
        ec = dict(ec)

    if ec.get("duration_s") is not None:
        dur_v = ec["duration_s"]
        if (
            isinstance(dur_v, bool)
            or not isinstance(dur_v, (int, float))
            or not math.isfinite(float(dur_v))
            or float(dur_v) <= 0.0
        ):
            raise ConfigError(f"--spec-file invalid explicit_constraints.duration_s: {dur_v!r}.")
    if ec.get("bpm") is not None:
        bpm_v = ec["bpm"]
        if isinstance(bpm_v, bool) or not isinstance(bpm_v, int) or not (40 <= bpm_v <= 240):
            raise ConfigError(f"--spec-file invalid explicit_constraints.bpm: {bpm_v!r} (expected 40..240).")
    if ec.get("image_refs") is not None:
        raw_refs = ec["image_refs"]
        if not isinstance(raw_refs, list) or not all(isinstance(r, str) for r in raw_refs):
            raise ConfigError("--spec-file explicit_constraints.image_refs must be a list of strings.")
        spec_dir = spec_path.parent.resolve()
        resolved_refs: list[str] = []
        for ref_item in raw_refs:
            ref_clean = ref_item.strip()
            if ref_clean.startswith("files/"):
                resolved_refs.append(ref_clean)
                continue
            cand = (spec_dir / ref_clean).resolve() if not Path(ref_clean).is_absolute() else Path(ref_clean).resolve()
            if not cand.is_relative_to(spec_dir):
                raise ConfigError(
                    f"--spec-file image_ref '{ref_clean}' escapes spec directory '{contract_home(spec_dir)}'."
                )
            resolved_refs.append(str(cand))
        ec["image_refs"] = audio_engines.validate_lyria_image_refs(resolved_refs, allowed_root=spec_dir)

    spec["explicit_constraints"] = ec
    return spec


def compile_audio_spec(
    args: argparse.Namespace,
    *,
    mode: str,
    engine: str,
    prompt_text: str,
    lyrics_text: str | None,
) -> dict[str, Any]:
    """Compile an immutable Stage 1 ``AudioRequirementSpec`` with ``spec_sha256``."""
    if args.spec_file:
        return load_and_validate_spec_file(args.spec_file)

    effective_prompt = (
        prompt_text.strip()
        or (args.voice_prompt or "").strip()
        or (args.sample_text or "").strip()
        or (f"Backing track stripped from {Path(args.strip_vocals_from).name}" if args.strip_vocals_from else "")
        or ("Broadcast stem mix" if mode == "mix" else "")
    )
    if not effective_prompt:
        raise ConfigError(
            "Provide --prompt (or --text-file, --spec-file, --voice-prompt, --strip-vocals-from, "
            "--voice-track, or --doctor)."
        )

    delivery_style = (args.delivery_style or args.style or "").strip() or None
    default_dur = 5.0 if mode in ("sfx", "stinger") else 30.0
    duration_s = float(args.duration) if args.duration is not None else default_dur

    implicit_rules: list[str] = [
        "Broadcast-clean studio fidelity at 48 kHz without digital silence, severe clipping, or static bursts"
    ]
    criteria: list[dict[str, Any]] = [
        {
            "id": "AC-1",
            "category": "subject",
            "requirement": f"Delivers the requested {mode} audio content: {effective_prompt[:240]}",
            "mandatory": True,
        }
    ]

    if mode in ("bgm", "backing-track"):
        implicit_rules.append("Strictly instrumental arrangement with zero spoken words, singing, or vocal bleed")
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "instrumental_only",
                "requirement": "Strictly instrumental throughout with zero singing, humming, or spoken words.",
                "mandatory": True,
            }
        )
        compiled_prompt = (
            audio_engines.build_lyria_prompt(
                raw_prompt=effective_prompt,
                mode=mode,
                genre=args.genre,
                bpm=args.bpm,
                musical_key=args.key,
                mood=args.mood,
                instruments=args.instruments,
                lyrics=None,
                language=args.locale,
            )
            if not args.strip_vocals_from
            else effective_prompt
        )
    elif mode == "song":
        compiled_prompt = audio_engines.build_lyria_prompt(
            raw_prompt=effective_prompt,
            mode="song",
            genre=args.genre,
            bpm=args.bpm,
            musical_key=args.key,
            mood=args.mood,
            instruments=args.instruments,
            lyrics=lyrics_text,
            language=args.locale,
        )
        if lyrics_text:
            criteria.append(
                {
                    "id": f"AC-{len(criteria) + 1}",
                    "category": "lyrics",
                    "requirement": f"Sings the custom lyrics intelligibly in the requested style: {lyrics_text[:160]}",
                    "mandatory": True,
                }
            )
    elif mode in ("voice", "dialogue", "voice-design", "voice-replicate"):
        implicit_rules.append(
            "Spoken output renders only the script text and never vocalises delivery-style metadata"
        )
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "verbatim_speech",
                "requirement": (
                    "Speaks the target script intelligibly with natural prosody and zero spoken "
                    "stage-direction or speech_metadata style strings."
                ),
                "mandatory": True,
            }
        )
        compiled_prompt = effective_prompt
    else:
        compiled_prompt = effective_prompt

    criteria.append(
        {
            "id": f"AC-{len(criteria) + 1}",
            "category": "craft",
            "requirement": implicit_rules[0],
            "mandatory": True,
        }
    )

    spec_sha256 = compute_spec_sha256(criteria)
    return {
        "schema_version": 1,
        "mode": mode,
        "engine": engine,
        "raw_prompt": effective_prompt,
        "compiled_prompt": compiled_prompt,
        "explicit_constraints": {
            "duration_s": duration_s if mode in ("bgm", "song", "backing-track", "sfx", "stinger") else args.duration,
            "genre": args.genre,
            "bpm": args.bpm,
            "key": args.key,
            "mood": args.mood,
            "instruments": args.instruments,
            "locale": args.locale,
            "voice_name": args.voice_name,
            "delivery_style": delivery_style,
            "instrumental_only": mode in ("bgm", "backing-track"),
            "lufs_target": float(args.lufs_target),
            "true_peak_dbtp": float(args.true_peak_dbtp),
        },
        "implicit_constraints": implicit_rules,
        "acceptance_criteria": criteria,
        "spec_sha256": spec_sha256,
    }


# ---------------------------------------------------------------------------
# Stage 3 & Stage 4: Mechanical Gate & Blinded Multimodal Audio Rubric Judge
# ---------------------------------------------------------------------------


def verify_audio_mechanical(
    candidate_path: Path,
    *,
    expected_duration_s: float | None,
    loudness_report: Mapping[str, Any] | None,
    target_i: float,
    target_tp: float,
    require_ffmpeg: bool,
    runner: RunnerCallable,
    ffprobe_bin: str | None,
) -> tuple[bool, dict[str, Any], list[str], list[str]]:
    """Run deterministic Stage 3 binary/PCM, stream, duration, and loudness checks."""
    failures: list[str] = []
    unchecked: list[str] = []

    inspection = audio_dsp.inspect_audio_file(candidate_path)
    metrics: dict[str, Any] = {"binary_inspection": inspection.to_dict()}
    if not inspection.valid:
        failures.extend(inspection.errors)
        return False, metrics, failures, unchecked

    measured_duration = inspection.duration_s
    if ffprobe_bin:
        try:
            probe_info = audio_dsp.probe_audio_ffprobe(
                candidate_path, runner=runner, ffprobe_bin=ffprobe_bin
            )
            metrics["ffprobe"] = probe_info
            measured_duration = probe_info["duration_s"]
        except audio_dsp.AudioFormatError as exc:
            failures.append(str(exc))
    elif require_ffmpeg:
        failures.append("--require-ffmpeg set, but ffprobe was not found on PATH or ffmpeg-full.")
    else:
        unchecked.append("ffprobe_stream_metadata")

    if expected_duration_s is not None and measured_duration > 0.0:
        tolerance = max(2.5, 0.15 * float(expected_duration_s))
        if abs(measured_duration - float(expected_duration_s)) > tolerance:
            failures.append(
                f"Audio duration {measured_duration:.2f}s outside expected "
                f"{expected_duration_s:.2f}s +- {tolerance:.2f}s."
            )

    if loudness_report is not None:
        metrics["loudness"] = dict(loudness_report)
        out_lufs = float(loudness_report["output_lufs"])
        out_tp = float(loudness_report["output_tp_dbtp"])
        out_sr = int(loudness_report["sample_rate"])
        if out_sr != audio_dsp.BROADCAST_SAMPLE_RATE:
            failures.append(
                f"Post-loudnorm sample rate is {out_sr} Hz (mandatory {audio_dsp.BROADCAST_SAMPLE_RATE} Hz)."
            )
        if abs(out_lufs - target_i) > 1.0:
            failures.append(
                f"Post-loudnorm integrated loudness {out_lufs:.2f} LUFS missed target {target_i:.2f} LUFS (+/- 1.0)."
            )
        if out_tp > target_tp + 0.3:
            failures.append(
                f"Post-loudnorm true peak {out_tp:.2f} dBTP exceeded ceiling {target_tp:.2f} dBTP."
            )
    else:
        unchecked.append("loudness_gate_2pass_ebur128")

    return len(failures) == 0, metrics, failures, unchecked


def build_verifier_chain(explicit_verifier: str | None) -> list[str]:
    """Validate ``--verifier-model`` (exit 2 on invalid) and build failover chain."""
    if explicit_verifier:
        validated = validate_audio_model_id(explicit_verifier, role="verifier")
        lead = [validated]
    else:
        lead = []
    ordered: list[str] = []
    for item in (*lead, *VERIFIER_MODEL_CHAIN):
        if item not in ordered:
            ordered.append(item)
    return ordered


def extract_generate_json_text(stdout_text: str) -> dict[str, Any]:
    """Parse ``gemini-api generate --stream=false -o json`` envelope into verdict dict."""
    outer = json.loads(stdout_text)
    if not isinstance(outer, dict):
        raise ValueError("Expected JSON object from gemini-api generate -o json.")

    if "criteria_results" in outer:
        return outer

    steps = outer.get("steps")
    if isinstance(steps, list):
        text_parts: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            for item in step.get("content") or ():
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
        joined = "".join(text_parts).strip()
        if joined:
            parsed = json.loads(joined)
            if isinstance(parsed, dict):
                return parsed

    for key in ("text", "output", "response"):
        val = outer.get(key)
        if isinstance(val, str) and val.strip():
            parsed = json.loads(val.strip())
            if isinstance(parsed, dict):
                return parsed

    raise ValueError("Could not locate structured rubric JSON inside gemini-api generate output.")


def validate_rubric_verdict(
    verdict_doc: Mapping[str, Any],
    acceptance_criteria: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Enforce S9 provenance over untrusted multimodal rubric JSON."""
    results_raw = verdict_doc.get("criteria_results")
    if not isinstance(results_raw, list):
        return {
            "valid_schema": False,
            "all_passed": False,
            "contradiction_detected": False,
            "missing_criteria": [str(ac["id"]) for ac in acceptance_criteria],
            "failed_criteria": [],
            "errors": ["Rubric JSON missing 'criteria_results' list."],
        }

    expected_ids = {str(ac["id"]).strip() for ac in acceptance_criteria}
    by_id: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for entry in results_raw:
        if not isinstance(entry, dict):
            errors.append("Non-object entry in criteria_results.")
            continue
        cid = str(entry.get("id") or "").strip()
        passed = entry.get("passed")
        evidence = str(entry.get("observed_evidence") or "").strip()
        fix = str(entry.get("fix_instruction") or "").strip()
        if not cid:
            errors.append("Criterion result missing 'id'.")
            continue
        if cid in by_id:
            errors.append(f"Duplicate criterion result id '{cid}' in rubric JSON (S9 violation).")
            continue
        if cid not in expected_ids:
            errors.append(f"Unknown criterion id '{cid}' not in frozen spec (S9 violation).")
            continue
        if not isinstance(passed, bool):
            errors.append(f"Criterion '{cid}' has non-boolean 'passed'.")
            continue
        if not evidence:
            errors.append(f"Criterion '{cid}' has empty 'observed_evidence' (S9 provenance violation).")
            continue
        by_id[cid] = {
            "id": cid,
            "passed": passed,
            "observed_evidence": evidence,
            "fix_instruction": fix,
        }

    missing: list[str] = []
    failed: list[dict[str, Any]] = []
    mandatory_bools: list[bool] = []

    for ac in acceptance_criteria:
        cid = str(ac["id"])
        is_mandatory = bool(ac.get("mandatory", True))
        if cid not in by_id:
            missing.append(cid)
            if is_mandatory:
                mandatory_bools.append(False)
            continue
        res_item = by_id[cid]
        if is_mandatory:
            mandatory_bools.append(res_item["passed"])
            if not res_item["passed"]:
                failed.append(res_item)

    if missing:
        errors.append(f"Rubric omitted frozen criteria: {', '.join(missing)}")

    computed_pass = bool(mandatory_bools) and all(mandatory_bools) and not errors
    claimed_pass = verdict_doc.get("overall_pass")
    contradiction = isinstance(claimed_pass, bool) and (claimed_pass != computed_pass)
    if contradiction:
        errors.append(
            f"Self-contradictory model rubric: overall_pass={claimed_pass} disagrees with "
            f"mandatory criteria computed_pass={computed_pass}."
        )

    return {
        "valid_schema": len(errors) == 0,
        "all_passed": computed_pass and not contradiction,
        "contradiction_detected": contradiction,
        "missing_criteria": missing,
        "failed_criteria": failed,
        "criteria_by_id": by_id,
        "remediation_prompt": str(verdict_doc.get("remediation_prompt") or "").strip(),
        "errors": errors,
    }


def run_blinded_audio_judge(
    candidate_path: Path,
    *,
    spec: Mapping[str, Any],
    verifier_chain: Sequence[str],
    runner: RunnerCallable,
) -> dict[str, Any]:
    """Invoke stateless blinded ``gemini-4-argon`` -> ``gemini-4-carbon`` audio judge."""
    acs = spec["acceptance_criteria"]
    judge_prompt = (
        "You are a stateless, blinded multimodal audio quality and compliance auditor.\n"
        "Listen carefully to the attached audio file from start to finish and evaluate EVERY "
        "acceptance criterion below using concrete acoustic/spoken/musical observations.\n"
        "Do NOT assume compliance; cite what you actually hear in 'observed_evidence'.\n"
        "ACCEPTANCE_CRITERIA_JSON:\n"
        + json.dumps(acs, indent=2)
    )
    body = json.dumps(
        {
            "store": False,
            "generation_config": {"thinking_level": "high"},
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": AUDIO_RUBRIC_SCHEMA,
            },
        },
        separators=(",", ":"),
    )

    last_err = ""
    for verifier_model in verifier_chain:
        cmd = [
            "gemini-api",
            "generate",
            judge_prompt,
            "-m",
            verifier_model,
            "-i",
            str(candidate_path),
            "--stream=false",
            "-o",
            "json",
            "--body",
            body,
        ]
        res = runner(cmd)
        if res.returncode != 0:
            last_err = (res.stderr or res.stdout).strip()
            if audio_engines.is_transient_error(res):
                continue
            break
        try:
            raw_verdict = extract_generate_json_text(res.stdout)
        except ValueError as exc:
            last_err = f"Invalid JSON from verifier '{verifier_model}': {exc}"
            break
        validated = validate_rubric_verdict(raw_verdict, acs)
        validated["verifier_model_used"] = verifier_model
        return validated

    return {
        "valid_schema": False,
        "all_passed": False,
        "contradiction_detected": False,
        "missing_criteria": [str(ac["id"]) for ac in acs],
        "failed_criteria": [],
        "verifier_model_used": None,
        "errors": [f"Blinded audio verifier failed: {last_err or 'no verifier succeeded'}"],
    }


# ---------------------------------------------------------------------------
# Diagnostics (--doctor), Dry-Run & Orchestrated Execution Loop
# ---------------------------------------------------------------------------


def run_doctor(
    *,
    creative_stack_arg: str,
    runner: RunnerCallable = default_runner,
    which_fn: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
    keg_dirs: Sequence[Path] | None = None,
) -> int:
    """Inspect ``gemini-api``, ``ffmpeg``/``ffprobe``, ``creative-stack``, and auth state."""
    active_env = env if env is not None else os.environ
    gemini_bin = which_fn("gemini-api")
    keg_kw = {"keg_dirs": keg_dirs} if keg_dirs is not None else {}
    ffmpeg_bin = audio_dsp.resolve_media_binary("ffmpeg", env=active_env, which_fn=which_fn, **keg_kw)
    ffprobe_bin = audio_dsp.resolve_media_binary("ffprobe", env=active_env, which_fn=which_fn, **keg_kw)
    gcloud_bin = which_fn("gcloud")
    sound_dir = audio_dsp.discover_creative_stack_sound(creative_stack_arg, env=active_env)

    warnings: list[str] = []
    gemini_version: str | None = None
    authenticated = False
    if gemini_bin:
        ver_res = runner(["gemini-api", "--version"])
        if ver_res.returncode == 0:
            gemini_version = ver_res.stdout.strip()
        who_res = runner(["gemini-api", "whoami", "-o", "json"])
        if who_res.returncode == 0:
            authenticated = True
        if active_env.get("GEMINI_API_KEY", "").strip():
            warnings.append(
                "GEMINI_API_KEY is set in environment and may shadow stored OS keyring credentials."
            )
    else:
        warnings.append(
            "gemini-api CLI not found on PATH (install via 'bash scripts/install.sh --with-media-tools' "
            "or see https://aistudio.google.com/docs/cli)."
        )

    if not ffmpeg_bin or not ffprobe_bin:
        warnings.append(
            "ffmpeg/ffprobe not found (install ffmpeg-full or ffmpeg for 2-pass -14 LUFS mastering and crossfades)."
        )

    report = {
        "ok": bool(gemini_bin),
        "tools": {
            "gemini_api": {"found": bool(gemini_bin), "version": gemini_version, "authenticated": authenticated},
            "ffmpeg": {"found": bool(ffmpeg_bin), "path": contract_home(ffmpeg_bin) if ffmpeg_bin else None},
            "ffprobe": {"found": bool(ffprobe_bin), "path": contract_home(ffprobe_bin) if ffprobe_bin else None},
            "gcloud": {"found": bool(gcloud_bin)},
            "creative_stack_sound": {
                "found": sound_dir is not None,
                "path": contract_home(sound_dir) if sound_dir else None,
            },
        },
        "cloud_tts_auth_env": bool(
            active_env.get("GOOGLE_CLOUD_ACCESS_TOKEN", "").strip()
            or active_env.get("GOOGLE_CLOUD_API_KEY", "").strip()
            or gcloud_bin
        ),
        "warnings": warnings,
    }
    print(json.dumps(report, indent=2))
    return 0 if gemini_bin else 1


def rejected_artifact_path(output_path: Path) -> Path:
    """Return ``<stem>.rejected.<ext>`` sibling path on verification failure."""
    ext = output_path.suffix.lstrip(".") or "wav"
    return output_path.with_name(f"{output_path.stem}.rejected.{ext}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio_gen.py",
        description=(
            "Generate, master, mix, and verify music (Lyria 3.5), speech & custom voices "
            "(Gemini 3.8 TTS, /v1beta/voices, Cloud TTS Chirp 3: HD), SFX/stingers, and "
            "broadcast -14 LUFS mixes."
        ),
    )
    parser.add_argument("--prompt", "-p", default="", help="Prompt, spoken script, or sound direction.")
    parser.add_argument("--text-file", help="UTF-8 text file containing spoken script or dialogue.")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=SUPPORTED_MODES,
        help="Audio production mode (default: auto).",
    )
    parser.add_argument(
        "--engine",
        default="auto",
        choices=SUPPORTED_ENGINES,
        help="Synthesis/DSP backend (default: auto).",
    )
    parser.add_argument("--output", "-o", default="output.wav", help="Output audio path (.wav, .mp3, .flac, .m4a, .ogg).")
    parser.add_argument("--spec-file", help="Load a pre-compiled frozen AudioRequirementSpec JSON.")
    parser.add_argument("--spec-out", help="Write the compiled frozen AudioRequirementSpec JSON to this path.")
    parser.add_argument(
        "--raw-prompt",
        action="store_true",
        help="Forward --prompt verbatim without extra style/framing expansion (used for companion delegation).",
    )

    # Lyria music, songs & backing tracks
    parser.add_argument("--lyrics", help="Custom song lyrics (--mode song only; forbidden on bgm/backing-track).")
    parser.add_argument("--lyrics-file", help="UTF-8 file containing custom song lyrics (--mode song only).")
    parser.add_argument("--genre", help="Musical genre (e.g. 'lofi', 'cinematic orchestral', 'indie rock').")
    parser.add_argument("--bpm", type=int, help="Target musical tempo in BPM (40..240).")
    parser.add_argument("--key", help="Musical key/scale (e.g. 'C', 'F# minor', 'Bb major').")
    parser.add_argument("--mood", help="Musical mood or energy descriptor.")
    parser.add_argument("--instruments", help="Target instrument palette.")
    parser.add_argument("--locale", "--language", dest="locale", default="en-US", help="BCP-47 locale or vocal language (default: en-US).")
    parser.add_argument("--duration", type=float, help="Target duration in seconds (supports >180s crossfaded stitching).")
    parser.add_argument("--crossfade", type=float, default=2.0, help="Crossfade overlap in seconds for multi-segment music (default: 2.0).")
    parser.add_argument(
        "--image-ref",
        "-i",
        action="append",
        default=[],
        help="Visual mood/scene image reference for Lyria (repeatable, max 10, magic-byte checked).",
    )
    parser.add_argument(
        "--strip-vocals-from",
        help="Existing song file to strip vocals from via creative-stack karaoke.py or >130Hz center-cut.",
    )

    # Gemini 3.8 TTS, /v1beta/voices & Cloud TTS Chirp 3: HD
    parser.add_argument("--voice-name", "--voice", dest="voice_name", default="Kore", help="Prebuilt voice (Kore, Aoede, Charon, Fenrir, Leda, Puck, Zephyr) or voice_.../voicekey_... ID.")
    parser.add_argument("--delivery-style", help="Delivery style placed strictly in speech_metadata (never spoken verbatim).")
    parser.add_argument("--style", help="Alias for --delivery-style (or musical style direction).")
    parser.add_argument(
        "--speakers",
        action="append",
        default=[],
        help="Multi-speaker dialogue mapping 'Speaker=Voice[:delivery style]' (repeatable).",
    )
    parser.add_argument("--chunk-chars", type=int, default=1800, help="Max characters per TTS chunk; pins Chunk 1 model across all chunks (default: 1800).")
    parser.add_argument("--voice-prompt", help="Natural-language persona description for '--mode voice-design'.")
    parser.add_argument("--sample-text", help="Audition sentence spoken when designing or replicating a custom voice.")
    parser.add_argument("--source-audio", help="10-30s speaker reference WAV for '--mode voice-replicate'.")
    parser.add_argument("--consent-audio", help="Distinct spoken consent WAV required for '--mode voice-replicate'.")
    parser.add_argument("--ephemeral", action="store_true", help="Set store=false on voice-replicate to return an ephemeral voicekey_... token.")
    parser.add_argument("--voice-meta-out", help="Optional JSON path to record created voice_... or voicekey_... metadata.")
    parser.add_argument("--speaking-rate", type=float, default=1.0, help="Cloud TTS Chirp 3 HD speaking rate 0.25..2.0 (default: 1.0).")
    parser.add_argument(
        "--pronunciations",
        action="append",
        default=[],
        help="Chirp 3 HD custom pronunciation 'phrase=phoneme[:ipa|xsampa]' or JSON file path (repeatable).",
    )
    parser.add_argument(
        "--chirp-cloning-key",
        help="Cloud TTS Chirp 3 Instant Custom Voice cloning key (uses v1beta1; prefer CHIRP_VOICE_CLONING_KEY env or --chirp-cloning-key-file).",
    )
    parser.add_argument(
        "--chirp-cloning-key-file",
        help="Path to UTF-8 file containing Cloud TTS Chirp 3 Instant Custom Voice cloning key (avoids argv exposure).",
    )

    # SFX, Stingers, Mastering, Mixing & creative-stack (/sound)
    parser.add_argument(
        "--sfx-engine",
        default="auto",
        choices=SUPPORTED_SFX_ENGINES,
        help="SFX/stinger synthesis backend (default: auto).",
    )
    parser.add_argument(
        "--bed-style",
        default="corporate",
        choices=SUPPORTED_BED_STYLES,
        help="Procedural style when --sfx-engine creative-bed is selected (default: corporate).",
    )
    parser.add_argument("--voice-track", help="Voiceover stem path for broadcast stem mixing.")
    parser.add_argument("--bgm-track", help="Background music bed path to duck under speech.")
    parser.add_argument(
        "--sfx-cue",
        action="append",
        default=[],
        help="One-shot effect cue 'FILE@SECONDS[:GAIN_DB]' for stem mixing (repeatable).",
    )
    parser.add_argument("--clean-voice", action="store_true", help="Repair --voice-track via clean.py or rumble/denoise/compress chain before mixing.")
    parser.add_argument("--lead", type=float, default=0.0, help="Seconds of music bed before voice starts (default: 0.0).")
    parser.add_argument("--tail", type=float, default=0.0, help="Seconds of music bed after voice ends (default: 0.0).")
    parser.add_argument("--bgm-gain-db", type=float, default=-16.0, help="Base BGM level in dB relative to voice before ducking (default: -16.0).")
    parser.add_argument("--duck-db", type=float, default=14.0, help="Exact dB attenuation of BGM during speech windows via volume envelope (default: 14.0).")
    parser.add_argument("--lufs-target", type=float, default=-14.0, help="Target integrated loudness in LUFS for 2-pass loudnorm (default: -14.0).")
    parser.add_argument("--true-peak-dbtp", type=float, default=-1.0, help="Target true-peak ceiling in dBTP (default: -1.0).")
    parser.add_argument("--no-normalize", action="store_true", help="Skip post-generation 2-pass loudnorm mastering.")
    parser.add_argument("--reaper-rpp", help="Emit a non-destructive REAPER .rpp multitrack project session.")
    parser.add_argument("--creative-stack", default="auto", help="creative-stack (/sound) integration: auto, off, or directory path (default: auto).")

    # Models, Verification, Retry & Diagnostics
    parser.add_argument("--model", "-m", help="Explicit generator model ID (validated against active allowlists and deprecation fence).")
    parser.add_argument("--verifier-model", help="Blinded multimodal verifier model (default: gemini-4-argon).")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum generation + verification attempts (1..10, default: 3).")
    parser.add_argument("--require-ffmpeg", action="store_true", help="Fail closed if ffmpeg/ffprobe are unavailable.")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip Stage 4 blinded multimodal rubric judge (requires --override-reason; records in unchecked_surfaces).",
    )
    parser.add_argument("--allow-unverified", action="store_true", help="Allow writing unverified output if retries exhaust (requires --override-reason).")
    parser.add_argument("--override-reason", help="Mandatory human justification required whenever --allow-unverified or --no-verify is passed.")
    parser.add_argument("--dry-run", action="store_true", help="Validate spec, inputs, and models and print planned execution JSON without API calls.")
    parser.add_argument("--doctor", action="store_true", help="Inspect gemini-api, ffmpeg-full, creative-stack, and auth readiness.")
    return parser


def _has_valid_forge_provenance(output_path: Path) -> bool:
    """Return True only when ``<output>.provenance.json`` belongs to audio_gen."""
    prov_path = Path(f"{output_path}.provenance.json")
    if not prov_path.is_file():
        return False
    try:
        doc = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and "schema_version" in doc and "status" in doc


def _validate_numeric_options(args: argparse.Namespace) -> None:
    """Validate finite bounds for all numeric CLI parameters up front (exit 2)."""
    if args.chunk_chars < 80:
        raise ConfigError(f"--chunk-chars must be >= 80 (got {args.chunk_chars}).")
    if args.bpm is not None and not (40 <= int(args.bpm) <= 240):
        raise ConfigError(f"--bpm must be between 40 and 240 (got {args.bpm}).")
    if args.duration is not None and (
        not math.isfinite(float(args.duration)) or float(args.duration) <= 0.0
    ):
        raise ConfigError(f"--duration must be finite and > 0 (got {args.duration}).")
    if not math.isfinite(float(args.crossfade)) or not (0.0 <= float(args.crossfade) <= 15.0):
        raise ConfigError(f"--crossfade must be finite and between 0.0 and 15.0 (got {args.crossfade}).")
    if not math.isfinite(float(args.lead)) or float(args.lead) < 0.0:
        raise ConfigError(f"--lead must be finite and >= 0.0 (got {args.lead}).")
    if not math.isfinite(float(args.tail)) or float(args.tail) < 0.0:
        raise ConfigError(f"--tail must be finite and >= 0.0 (got {args.tail}).")
    if not math.isfinite(float(args.bgm_gain_db)):
        raise ConfigError(f"--bgm-gain-db must be finite (got {args.bgm_gain_db}).")
    if not math.isfinite(float(args.duck_db)) or float(args.duck_db) < 0.0:
        raise ConfigError(f"--duck-db must be finite and >= 0.0 (got {args.duck_db}).")
    if not math.isfinite(float(args.lufs_target)) or not (-70.0 <= float(args.lufs_target) <= -5.0):
        raise ConfigError(f"--lufs-target must be between -70.0 and -5.0 LUFS (got {args.lufs_target}).")
    if not math.isfinite(float(args.true_peak_dbtp)) or not (-9.0 <= float(args.true_peak_dbtp) <= 0.0):
        raise ConfigError(
            f"--true-peak-dbtp must be between -9.0 and 0.0 dBTP (got {args.true_peak_dbtp})."
        )
    if not math.isfinite(float(args.speaking_rate)) or not (0.25 <= float(args.speaking_rate) <= 2.0):
        raise ConfigError(
            f"--speaking-rate must be between 0.25 and 2.0 (got {args.speaking_rate})."
        )


def _validate_pre_execution_inputs(
    args: argparse.Namespace,
    *,
    mode: str,
    engine: str,
    prompt_text: str,
    output_path: Path,
    cloning_key: str | None,
    env: Mapping[str, str] | None = None,
) -> tuple[list[str], list[tuple[Path, float, float]]]:
    """Validate models, override flags, local media files, and consent before execution."""
    if not (1 <= int(args.max_attempts) <= 10):
        raise ConfigError(f"--max-attempts must be between 1 and 10 (got {args.max_attempts}).")
    bypassing = bool(args.allow_unverified or args.no_verify)
    if bypassing and (not args.override_reason or not args.override_reason.strip()):
        flag_used = "--no-verify" if args.no_verify else "--allow-unverified"
        raise ConfigError(
            f"{flag_used} requires a non-empty --override-reason '<why>' "
            "(Engineering Standard §9 loud-override rule)."
        )
    if args.override_reason and not bypassing:
        raise ConfigError("--override-reason is only valid alongside --allow-unverified or --no-verify.")

    _validate_numeric_options(args)
    _ = build_verifier_chain(args.verifier_model)

    if args.model:
        audio_engines.enforce_deprecation_fence(args.model)
        if args.strip_vocals_from:
            raise ConfigError(
                "--model cannot be passed with --strip-vocals-from (deterministic DSP separation)."
            )
        if engine in ("chirp3", "voices-rest", "mix"):
            raise ConfigError(
                f"--model '{args.model}' is not supported with '--engine {engine}'; "
                f"omit --model to use the fixed endpoint."
            )
        if engine == "sfx":
            eff_sfx_m = (
                args.sfx_engine
                if args.sfx_engine != "auto"
                else ("lyria-sting" if mode == "stinger" else "omni-foley")
            )
            if eff_sfx_m == "lyria-sting":
                validate_audio_model_id(args.model, role="music")
            elif eff_sfx_m == "omni-foley":
                validate_audio_model_id(args.model, role="sfx")
            else:
                raise ConfigError(
                    f"--model '{args.model}' is not supported with '--sfx-engine {eff_sfx_m}'."
                )
        else:
            role_map = {"lyria": "music", "gemini-tts": "tts"}
            validate_audio_model_id(args.model, role=role_map[engine])

    checked_img_refs = audio_engines.validate_lyria_image_refs(args.image_ref)
    if checked_img_refs and engine != "lyria":
        raise ConfigError("'-i / --image-ref' visual conditioning is only supported on Lyria music modes.")

    try:
        sfx_cues = [audio_dsp.parse_sfx_cue(spec) for spec in args.sfx_cue]
        if args.strip_vocals_from:
            if args.strip_vocals_from.strip().startswith("files/"):
                raise ConfigError("--strip-vocals-from requires a local audio file, not a remote files/<id> URI.")
            audio_dsp.require_valid_audio(Path(args.strip_vocals_from).expanduser(), label="--strip-vocals-from")
        if args.voice_track:
            if args.voice_track.strip().startswith("files/"):
                raise ConfigError("--voice-track requires a local audio file, not a remote files/<id> URI.")
            audio_dsp.require_valid_audio(Path(args.voice_track).expanduser(), label="--voice-track")
        if args.bgm_track:
            if args.bgm_track.strip().startswith("files/"):
                raise ConfigError("--bgm-track requires a local audio file, not a remote files/<id> URI.")
            audio_dsp.require_valid_audio(Path(args.bgm_track).expanduser(), label="--bgm-track")
    except audio_dsp.AudioFormatError as exc:
        raise ConfigError(str(exc)) from exc

    if mode == "mix" and not (args.voice_track or args.bgm_track or sfx_cues):
        raise ConfigError(
            "'--mode mix' requires at least one of --voice-track, --bgm-track, or --sfx-cue."
        )

    # Prevent overwriting any input asset or auxiliary artifact via --output aliasing.
    input_candidates: list[tuple[str, str | Path | None]] = [
        ("--voice-track", args.voice_track),
        ("--bgm-track", args.bgm_track),
        ("--strip-vocals-from", args.strip_vocals_from),
        ("--source-audio", args.source_audio),
        ("--consent-audio", args.consent_audio),
        ("--spec-file", args.spec_file),
        ("--text-file", args.text_file),
        ("--lyrics-file", args.lyrics_file),
        ("--chirp-cloning-key-file", getattr(args, "chirp_cloning_key_file", None)),
        ("--reaper-rpp", args.reaper_rpp),
        ("--spec-out", args.spec_out),
        ("--voice-meta-out", args.voice_meta_out),
    ]
    for cue_path, _, _ in sfx_cues:
        input_candidates.append(("--sfx-cue", cue_path))
    for img_ref in checked_img_refs:
        if not img_ref.startswith("files/"):
            input_candidates.append(("--image-ref", img_ref))
    for flag_name, raw_cand in input_candidates:
        if not raw_cand:
            continue
        if Path(raw_cand).expanduser().resolve() == output_path:
            raise ConfigError(
                f"--output '{contract_home(output_path)}' must not alias {flag_name} input path."
            )

    if mode == "voice-design":
        _ = audio_engines.resolve_api_base_url(
            "FORGE_GEMINI_API_BASE_URL", audio_engines.DEFAULT_GEMINI_API_BASE_URL, env=env
        )
        if not (args.voice_prompt and args.voice_prompt.strip()):
            raise ConfigError("'--mode voice-design' requires --voice-prompt.")
        if not (args.sample_text or prompt_text).strip():
            raise ConfigError("'--mode voice-design' requires --sample-text (or --prompt).")

    if mode == "voice-replicate":
        _ = audio_engines.resolve_api_base_url(
            "FORGE_GEMINI_API_BASE_URL", audio_engines.DEFAULT_GEMINI_API_BASE_URL, env=env
        )
        if not args.source_audio or not args.consent_audio:
            raise ConfigError(
                "'--mode voice-replicate' requires BOTH --source-audio (10-30s WAV) and --consent-audio WAV."
            )
        src_p = Path(args.source_audio).expanduser().resolve()
        con_p = Path(args.consent_audio).expanduser().resolve()
        if not src_p.is_file():
            raise ConfigError(f"--source-audio file not found: {contract_home(src_p)}")
        if not con_p.is_file():
            raise ConfigError(f"--consent-audio file not found: {contract_home(con_p)}")
        src_b = src_p.read_bytes()
        con_b = con_p.read_bytes()
        if hashlib.sha256(src_b).hexdigest() == hashlib.sha256(con_b).hexdigest():
            raise ConfigError(
                "--consent-audio has identical SHA-256 to --source-audio; distinct consent recording required."
            )
        try:
            s_info = audio_dsp.require_valid_audio(src_b, label="--source-audio", require_wav=True)
            c_info = audio_dsp.require_valid_audio(con_b, label="--consent-audio", require_wav=True)
        except audio_dsp.AudioFormatError as exc:
            raise ConfigError(str(exc)) from exc
        if s_info.pcm_sha256 and s_info.pcm_sha256 == c_info.pcm_sha256:
            raise ConfigError("--consent-audio has identical PCM audio payload to --source-audio.")
        if not (10.0 <= s_info.duration_s <= 30.0):
            raise ConfigError(
                f"--source-audio duration must be 10.0s..30.0s (got {s_info.duration_s:.2f}s)."
            )

    if engine == "lyria" and not args.strip_vocals_from:
        dur_plan = float(args.duration) if args.duration is not None else 30.0
        plan_model = (
            validate_audio_model_id(args.model, role="music")
            if args.model
            else (
                audio_engines.CLIP_MUSIC_MODEL
                if mode == "stinger" and dur_plan <= audio_engines.LYRIA_CLIP_MAX_SEGMENT_S
                else audio_engines.PRIMARY_MUSIC_MODEL
            )
        )
        _ = audio_engines.plan_music_segments(dur_plan, model=plan_model, crossfade_s=float(args.crossfade))

    if engine == "chirp3":
        _ = audio_engines.resolve_api_base_url(
            "FORGE_CLOUD_TTS_BASE_URL", audio_engines.DEFAULT_CLOUD_TTS_BASE_URL, env=env
        )
        if not cloning_key:
            _ = audio_engines.format_chirp3_voice_name(args.voice_name, locale=args.locale)
        _ = audio_engines.validate_chirp3_text_markup(prompt_text)
        _ = audio_engines.parse_pronunciation_specs(args.pronunciations)
    elif engine == "gemini-tts":
        if mode == "dialogue":
            smap = audio_engines.parse_speaker_map(args.speakers)
            _ = audio_engines.parse_dialogue_turns(prompt_text, smap, default_voice=args.voice_name)
        else:
            _ = audio_engines.validate_inline_vocal_tags(prompt_text)

    if engine == "sfx":
        dur_check = float(args.duration) if args.duration is not None else 5.0
        eff_sfx = args.sfx_engine if args.sfx_engine != "auto" else ("lyria-sting" if mode == "stinger" else "omni-foley")
        if eff_sfx == "omni-foley" and not (3 <= int(round(dur_check)) <= 15):
            raise ConfigError(f"'omni-foley' requires --duration 3..15s (got {dur_check}s).")
        if eff_sfx == "lyria-sting" and dur_check > audio_engines.LYRIA_CLIP_MAX_SEGMENT_S:
            raise ConfigError(f"'lyria-sting' requires --duration <= 30s (got {dur_check}s).")

    return checked_img_refs, sfx_cues


def run_audio_pipeline(
    argv: Sequence[str] | None = None,
    *,
    runner: RunnerCallable = default_runner,
    http_transport: HttpTransportCallable = default_http_transport,
    which_fn: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    keg_dirs: Sequence[Path] | None = None,
) -> int:
    """CLI entrypoint returning POSIX exit code (0 pass, 1 verification/runtime fail, 2 config error)."""
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    active_env = env if env is not None else os.environ
    keg_kw = {"keg_dirs": keg_dirs} if keg_dirs is not None else {}

    try:
        if args.doctor:
            return run_doctor(
                creative_stack_arg=args.creative_stack,
                runner=runner,
                which_fn=which_fn,
                env=active_env,
                **keg_kw,
            )

        cloning_key = resolve_chirp_cloning_key(args, active_env, warn=(not args.dry_run))
        output_path = Path(args.output).expanduser().resolve()
        _ = audio_dsp.encode_args_for_output(output_path)

        prompt_text = args.prompt or ""
        if args.text_file:
            tf = Path(args.text_file).expanduser().resolve()
            if not tf.is_file():
                raise ConfigError(f"--text-file not found: {contract_home(tf)}")
            file_script = tf.read_text(encoding="utf-8")
            prompt_text = f"{prompt_text}\n{file_script}".strip() if prompt_text.strip() else file_script

        lyrics_text = args.lyrics
        if args.lyrics_file:
            lf = Path(args.lyrics_file).expanduser().resolve()
            if not lf.is_file():
                raise ConfigError(f"--lyrics-file not found: {contract_home(lf)}")
            lyrics_text = lf.read_text(encoding="utf-8").strip()

        if args.spec_file:
            loaded_spec = load_and_validate_spec_file(args.spec_file)
            if args.mode == "auto" and isinstance(loaded_spec.get("mode"), str):
                args.mode = loaded_spec["mode"]
            if args.engine == "auto" and isinstance(loaded_spec.get("engine"), str):
                args.engine = loaded_spec["engine"]
            if not prompt_text.strip():
                prompt_text = str(loaded_spec["raw_prompt"])
            ec_in = loaded_spec.get("explicit_constraints") or {}
            if args.duration is None and ec_in.get("duration_s") is not None:
                args.duration = float(ec_in["duration_s"])
            if args.genre is None and ec_in.get("genre"):
                args.genre = str(ec_in["genre"])
            if args.bpm is None and ec_in.get("bpm") is not None:
                args.bpm = int(ec_in["bpm"])
            if args.key is None and ec_in.get("key"):
                args.key = str(ec_in["key"])
            if not args.image_ref and ec_in.get("image_refs"):
                args.image_ref = list(ec_in["image_refs"])

        mode, engine = resolve_mode_and_engine(args, prompt_text, has_cloning_key=bool(cloning_key))
        creative_sound_dir = audio_dsp.discover_creative_stack_sound(args.creative_stack, env=active_env)
        spec = compile_audio_spec(
            args,
            mode=mode,
            engine=engine,
            prompt_text=prompt_text,
            lyrics_text=lyrics_text,
        )
        frozen_sha = spec["spec_sha256"]

        checked_img_refs, sfx_cues = _validate_pre_execution_inputs(
            args,
            mode=mode,
            engine=engine,
            prompt_text=spec["raw_prompt"],
            output_path=output_path,
            cloning_key=cloning_key,
            env=active_env,
        )

        if args.spec_out:
            spec_out_p = Path(args.spec_out).expanduser().resolve()
            spec_out_p.parent.mkdir(parents=True, exist_ok=True)
            spec_out_p.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

        ffmpeg_bin = audio_dsp.resolve_media_binary("ffmpeg", env=active_env, which_fn=which_fn, **keg_kw)
        ffprobe_bin = audio_dsp.resolve_media_binary("ffprobe", env=active_env, which_fn=which_fn, **keg_kw)
        if args.require_ffmpeg and (not ffmpeg_bin or not ffprobe_bin):
            raise ConfigError("--require-ffmpeg set, but ffmpeg/ffprobe were not found.")

        verifier_chain = build_verifier_chain(args.verifier_model)

        if args.dry_run:
            planned_model = (
                args.model
                or (
                    audio_engines.CLIP_MUSIC_MODEL
                    if mode == "stinger"
                    else audio_engines.PRIMARY_MUSIC_MODEL
                    if engine == "lyria"
                    else audio_engines.PRIMARY_TTS_MODEL
                    if engine == "gemini-tts"
                    else audio_engines.format_chirp3_voice_name(args.voice_name, args.locale)
                    if (engine == "chirp3" and not cloning_key)
                    else f"{args.locale}-Chirp3-InstantCustomVoice"
                    if engine == "chirp3"
                    else f"voices-rest:{mode}"
                    if engine == "voices-rest"
                    else audio_engines.OMNI_FOLEY_MODEL
                    if engine == "sfx"
                    else "broadcast-stem-mixer"
                )
            )
            dry_payload = {
                "dry_run": True,
                "mode": mode,
                "engine": engine,
                "planned_model": planned_model,
                "verifier_chain": verifier_chain,
                "spec_sha256": frozen_sha,
                "spec": spec,
                "output": contract_home(output_path),
                "creative_stack_sound": contract_home(creative_sound_dir) if creative_sound_dir else None,
                "ffmpeg_resolved": contract_home(ffmpeg_bin) if ffmpeg_bin else None,
                "unchecked_surfaces": ["live_generation_and_verification"],
            }
            print(json.dumps(dry_payload, indent=2))
            return 0

    except (ConfigError, audio_dsp.AudioFormatError) as exc:
        print(f"Configuration error: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2

    # Execute closed-loop synthesis -> post-DSP -> Stage 3 -> Stage 4 -> retry
    attempts_history: list[dict[str, Any]] = []
    remediation_suffix = ""
    delivery_style = (args.delivery_style or args.style or "").strip() or None
    default_dur = 5.0 if mode in ("sfx", "stinger") else 30.0
    target_dur = float(args.duration) if args.duration is not None else default_dur

    existed_before = output_path.exists()
    prior_prov_owned = _has_valid_forge_provenance(output_path)
    staging_parent = Path(tempfile.mkdtemp(prefix="forge-audio-gen-"))
    last_candidate: Path | None = None
    last_engine_meta: dict[str, Any] = {}

    try:
        max_tries = 1 if (mode == "mix" or bool(args.strip_vocals_from)) else int(args.max_attempts)
        for attempt_idx in range(1, max_tries + 1):
            # Invariant check: frozen spec_sha256 MUST NOT mutate across retries
            if compute_spec_sha256(spec["acceptance_criteria"]) != frozen_sha:
                raise RuntimeError("Frozen AudioRequirementSpec digest mutated mid-run (S9 violation).")

            attempt_dir = staging_parent / f"attempt_{attempt_idx:02d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            attempt_record: dict[str, Any] = {"attempt": attempt_idx, "spec_sha256": frozen_sha}

            try:
                # 1. Synthesis or DSP Stem Source
                if args.strip_vocals_from:
                    stripped_wav = attempt_dir / "stripped_backing.wav"
                    strip_info = audio_dsp.strip_vocals_to_backing(
                        Path(args.strip_vocals_from).expanduser().resolve(),
                        stripped_wav,
                        creative_sound_dir=creative_sound_dir,
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                    )
                    raw_generated = stripped_wav
                    engine_meta: dict[str, Any] = {
                        "model_used": strip_info["backend"],
                        "response_ids": [],
                    }
                elif mode == "mix":
                    v_stem = Path(args.voice_track).expanduser().resolve() if args.voice_track else None
                    if v_stem is not None and args.clean_voice:
                        cleaned_v = attempt_dir / "voice_cleaned.wav"
                        audio_dsp.clean_voice_track(
                            v_stem,
                            cleaned_v,
                            creative_sound_dir=creative_sound_dir,
                            runner=runner,
                            ffmpeg_bin=ffmpeg_bin,
                        )
                        v_stem = cleaned_v
                    b_stem = Path(args.bgm_track).expanduser().resolve() if args.bgm_track else None
                    mixed_dst = attempt_dir / f"mixed_master{output_path.suffix or '.wav'}"
                    mix_info = audio_dsp.mix_broadcast_stems(
                        voice_path=v_stem,
                        bgm_path=b_stem,
                        sfx_cues=sfx_cues,
                        dst_path=mixed_dst,
                        lead_s=args.lead,
                        tail_s=args.tail,
                        bgm_gain_db=args.bgm_gain_db,
                        duck_db=args.duck_db,
                        target_i=args.lufs_target,
                        target_tp=args.true_peak_dbtp,
                        creative_sound_dir=creative_sound_dir,
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                        ffprobe_bin=ffprobe_bin,
                    )
                    raw_generated = mixed_dst
                    engine_meta = {
                        "model_used": mix_info["backend"],
                        "mix_details": mix_info,
                        "already_mastered": True,
                        "response_ids": [],
                    }
                elif engine == "lyria":
                    prompt_for_attempt = (
                        f"{spec['raw_prompt']}. Corrective notes: {remediation_suffix}"
                        if remediation_suffix
                        else spec["raw_prompt"]
                    )
                    engine_meta = audio_engines.run_lyria_generation(
                        raw_prompt=prompt_for_attempt,
                        mode=mode,
                        explicit_model=args.model,
                        duration_s=target_dur,
                        crossfade_s=args.crossfade,
                        image_refs=checked_img_refs,
                        genre=args.genre,
                        bpm=args.bpm,
                        musical_key=args.key,
                        mood=args.mood,
                        instruments=args.instruments,
                        lyrics=lyrics_text,
                        language=args.locale,
                        staging_dir=attempt_dir,
                        prefer_wav=not args.no_normalize or output_path.suffix.lower() == ".wav",
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                        sleep_fn=sleep_fn,
                    )
                    raw_generated = engine_meta["path"]
                elif engine == "gemini-tts":
                    # Hard Law (a): remediation notes go into delivery_style metadata, NEVER spoken text!
                    style_for_attempt = (
                        f"{delivery_style}; {remediation_suffix}".strip("; ")
                        if remediation_suffix
                        else delivery_style
                    )
                    engine_meta = audio_engines.run_gemini_tts(
                        script_text=spec["raw_prompt"],
                        mode=mode,
                        explicit_model=args.model,
                        voice_name=args.voice_name,
                        delivery_style=style_for_attempt,
                        speakers_spec=args.speakers,
                        chunk_chars=args.chunk_chars,
                        staging_dir=attempt_dir,
                        runner=runner,
                        sleep_fn=sleep_fn,
                    )
                    raw_generated = engine_meta["path"]
                elif engine == "chirp3":
                    engine_meta = audio_engines.run_chirp3_tts(
                        text=spec["raw_prompt"],
                        voice_name=args.voice_name,
                        locale=args.locale,
                        speaking_rate=args.speaking_rate,
                        pronunciations=args.pronunciations,
                        chirp_cloning_key=cloning_key,
                        staging_dir=attempt_dir,
                        http_transport=http_transport,
                        runner=runner,
                        env=active_env,
                    )
                    raw_generated = engine_meta["path"]
                elif engine == "voices-rest":
                    audition_text = (args.sample_text or spec["raw_prompt"]).strip()
                    if mode == "voice-design":
                        vp = (
                            f"{args.voice_prompt}. {remediation_suffix}".strip()
                            if remediation_suffix
                            else args.voice_prompt
                        )
                        engine_meta = audio_engines.create_designed_voice(
                            voice_prompt=vp,
                            sample_text=audition_text,
                            locale=args.locale,
                            staging_dir=attempt_dir,
                            http_transport=http_transport,
                            env=active_env,
                        )
                    else:
                        engine_meta = audio_engines.create_replicated_voice(
                            source_audio_path=args.source_audio,
                            consent_audio_path=args.consent_audio,
                            sample_text=audition_text,
                            locale=args.locale,
                            ephemeral=args.ephemeral,
                            staging_dir=attempt_dir,
                            http_transport=http_transport,
                            env=active_env,
                        )
                    raw_generated = engine_meta["path"]
                else:
                    sfx_p = (
                        f"{spec['raw_prompt']}. {remediation_suffix}".strip()
                        if remediation_suffix
                        else spec["raw_prompt"]
                    )
                    engine_meta = audio_engines.run_sfx_or_stinger(
                        prompt=sfx_p,
                        mode=mode,
                        sfx_engine=args.sfx_engine,
                        explicit_model=args.model,
                        duration_s=target_dur,
                        bed_style=args.bed_style,
                        musical_key=args.key,
                        bpm=args.bpm,
                        creative_sound_dir=creative_sound_dir,
                        staging_dir=attempt_dir,
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                        sleep_fn=sleep_fn,
                    )
                    raw_generated = engine_meta["path"]

                # 2. Optional Post-Synthesis Stem Mix (e.g. generated TTS + --bgm-track / --sfx-cue)
                loudness_report: dict[str, Any] | None = None
                unchecked_attempt: list[str] = []
                candidate_file = raw_generated

                if mode != "mix" and (args.bgm_track or sfx_cues):
                    b_stem = Path(args.bgm_track).expanduser().resolve() if args.bgm_track else None
                    mixed_cand = attempt_dir / f"post_mixed{output_path.suffix or '.wav'}"
                    mix_res = audio_dsp.mix_broadcast_stems(
                        voice_path=raw_generated,
                        bgm_path=b_stem,
                        sfx_cues=sfx_cues,
                        dst_path=mixed_cand,
                        lead_s=args.lead,
                        tail_s=args.tail,
                        bgm_gain_db=args.bgm_gain_db,
                        duck_db=args.duck_db,
                        target_i=args.lufs_target,
                        target_tp=args.true_peak_dbtp,
                        creative_sound_dir=creative_sound_dir,
                        runner=runner,
                        ffmpeg_bin=ffmpeg_bin,
                        ffprobe_bin=ffprobe_bin,
                    )
                    candidate_file = mixed_cand
                    loudness_report = mix_res.get("loudness")
                elif not args.no_normalize and not engine_meta.get("already_mastered"):
                    if ffmpeg_bin:
                        mastered_cand = attempt_dir / f"mastered{output_path.suffix or '.wav'}"
                        loudness_report = audio_dsp.normalize_audio_two_pass(
                            raw_generated,
                            mastered_cand,
                            target_i=args.lufs_target,
                            target_tp=args.true_peak_dbtp,
                            runner=runner,
                            ffmpeg_bin=ffmpeg_bin,
                        )
                        candidate_file = mastered_cand
                    else:
                        unchecked_attempt.append("ffmpeg_ebur128_loudnorm")
                elif engine_meta.get("already_mastered"):
                    loudness_report = (engine_meta.get("mix_details") or {}).get("loudness")

                last_candidate = candidate_file
                last_engine_meta = engine_meta

            except ConfigError as exc:
                print(f"Configuration error: {redact_secrets(str(exc))}", file=sys.stderr)
                return 2
            except (AudioEngineError, audio_dsp.AudioFormatError) as exc:
                attempt_record["stage"] = "synthesis_or_dsp"
                attempt_record["passed"] = False
                attempt_record["errors"] = [redact_secrets(str(exc))]
                attempts_history.append(attempt_record)
                remediation_suffix = "Avoid silent or clipped output; generate clean, full-bandwidth audio."
                continue

            # 3. Stage 3 Mechanical & Loudness Gate
            exp_dur = (
                float(args.duration)
                if (args.duration is not None and mode in ("bgm", "song", "backing-track", "sfx", "stinger"))
                else None
            )
            mech_ok, mech_metrics, mech_failures, mech_unchecked = verify_audio_mechanical(
                candidate_file,
                expected_duration_s=exp_dur,
                loudness_report=loudness_report,
                target_i=args.lufs_target,
                target_tp=args.true_peak_dbtp,
                require_ffmpeg=args.require_ffmpeg,
                runner=runner,
                ffprobe_bin=ffprobe_bin,
            )
            all_unchecked = list(dict.fromkeys([*unchecked_attempt, *mech_unchecked]))
            attempt_record["mechanical_passed"] = mech_ok
            attempt_record["mechanical_metrics"] = mech_metrics
            attempt_record["mechanical_failures"] = mech_failures

            if not mech_ok:
                attempt_record["passed"] = False
                attempt_record["unchecked_surfaces"] = all_unchecked
                attempts_history.append(attempt_record)
                remediation_suffix = "; ".join(mech_failures)
                continue

            # 4. Stage 4 Stateless Blinded Multimodal Audio Rubric Judge
            if args.no_verify:
                reason_nv = redact_secrets((args.override_reason or "").strip())
                print(
                    f"WARNING: Stage 4 blinded audio rubric verification skipped "
                    f"(--no-verify --override-reason: {reason_nv}).",
                    file=sys.stderr,
                )
                all_unchecked.append("stage4_multimodal_rubric")
                rubric_result: dict[str, Any] = {
                    "skipped": True,
                    "all_passed": True,
                    "verifier_model_used": None,
                    "override_reason": reason_nv,
                }
                stage4_ok = True
            else:
                rubric_result = run_blinded_audio_judge(
                    candidate_file,
                    spec=spec,
                    verifier_chain=verifier_chain,
                    runner=runner,
                )
                stage4_ok = bool(rubric_result.get("all_passed"))

            attempt_record["rubric"] = rubric_result
            attempt_record["unchecked_surfaces"] = all_unchecked
            attempt_record["passed"] = stage4_ok
            attempts_history.append(attempt_record)

            if stage4_ok:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(candidate_file, output_path)
                rej_p = rejected_artifact_path(output_path)
                rej_p.unlink(missing_ok=True)
                Path(f"{output_path}.report.json").unlink(missing_ok=True)

                rpp_meta = _maybe_write_reaper_rpp(
                    args,
                    output_path=output_path,
                    creative_sound_dir=creative_sound_dir,
                    sfx_cues=sfx_cues,
                    runner=runner,
                )
                _maybe_write_voice_meta(args.voice_meta_out, engine_meta, output_path)

                run_status = (
                    "MECHANICAL_ONLY"
                    if args.no_verify
                    else ("PARTIAL_VERIFIED" if all_unchecked else "VERIFIED")
                )
                provenance = {
                    "schema_version": 1,
                    "status": run_status,
                    "timestamp_utc": utc_now_iso(),
                    "mode": mode,
                    "engine": engine,
                    "model_used": engine_meta.get("model_used"),
                    "delegate_script": (
                        engine_meta.get("delegate_script")
                        or (engine_meta.get("mix_details") or {}).get("delegate_script")
                        or (rpp_meta or {}).get("delegate_script")
                    ),
                    "pinned_tts_model": engine_meta.get("pinned_model"),
                    "verifier_model_used": rubric_result.get("verifier_model_used"),
                    "spec_sha256": frozen_sha,
                    "attempts_used": attempt_idx,
                    "output": contract_home(output_path),
                    "voice_id": redact_secrets(str(engine_meta["voice_id"]))
                    if engine_meta.get("ephemeral")
                    else engine_meta.get("voice_id"),
                    "reaper_session": rpp_meta,
                    "mechanical": mech_metrics,
                    "rubric": rubric_result,
                    "unchecked_surfaces": all_unchecked,
                }
                if args.no_verify and args.override_reason:
                    provenance["override_reason"] = redact_secrets(args.override_reason.strip())
                prov_path = Path(f"{output_path}.provenance.json")
                prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({"status": provenance["status"], "output": contract_home(output_path), "attempts": attempt_idx}))
                return 0

            fixes = [
                f["fix_instruction"]
                for f in rubric_result.get("failed_criteria", ())
                if f.get("fix_instruction")
            ]
            remediation_suffix = (
                "; ".join(fixes)
                or rubric_result.get("remediation_prompt")
                or "Satisfy every acceptance criterion cleanly."
            )

        # Exhausted all attempts without passing verification
        report_path = Path(f"{output_path}.report.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.allow_unverified and last_candidate is not None and last_candidate.is_file():
            reason_clean = redact_secrets(args.override_reason.strip())
            print(
                f"WARNING: Verification failed after {len(attempts_history)} attempt(s); writing "
                f"UNVERIFIED_OVERRIDE output (--override-reason: {reason_clean}).",
                file=sys.stderr,
            )
            shutil.copyfile(last_candidate, output_path)
            _maybe_write_voice_meta(args.voice_meta_out, last_engine_meta, output_path)
            override_doc = {
                "schema_version": 1,
                "status": "UNVERIFIED_OVERRIDE",
                "override_reason": reason_clean,
                "timestamp_utc": utc_now_iso(),
                "mode": mode,
                "engine": engine,
                "spec_sha256": frozen_sha,
                "output": contract_home(output_path),
                "attempts": attempts_history,
                "unchecked_surfaces": ["unverified_override_bypass"],
            }
            report_path.write_text(json.dumps(override_doc, indent=2) + "\n", encoding="utf-8")
            Path(f"{output_path}.provenance.json").write_text(
                json.dumps(override_doc, indent=2) + "\n", encoding="utf-8"
            )
            return 0

        # Fail closed (exit 1): remove stale output only if created by audio_gen (never delete unrelated files)
        if not existed_before or prior_prov_owned:
            output_path.unlink(missing_ok=True)
        Path(f"{output_path}.provenance.json").unlink(missing_ok=True)
        rejected_out: str | None = None
        if last_candidate is not None and last_candidate.is_file():
            rej_target = rejected_artifact_path(output_path)
            shutil.copyfile(last_candidate, rej_target)
            rejected_out = contract_home(rej_target)

        failure_report = {
            "schema_version": 1,
            "status": "FAILED",
            "timestamp_utc": utc_now_iso(),
            "mode": mode,
            "engine": engine,
            "spec_sha256": frozen_sha,
            "rejected_candidate": rejected_out,
            "attempts": attempts_history,
        }
        report_path.write_text(json.dumps(failure_report, indent=2) + "\n", encoding="utf-8")
        print(
            f"Verification failed after {len(attempts_history)} attempt(s); wrote report to "
            f"{contract_home(report_path)}.",
            file=sys.stderr,
        )
        return 1
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def _maybe_write_reaper_rpp(
    args: argparse.Namespace,
    *,
    output_path: Path,
    creative_sound_dir: Path | None,
    sfx_cues: Sequence[tuple[Path, float, float]],
    runner: RunnerCallable,
) -> dict[str, Any] | None:
    if not args.reaper_rpp:
        return None
    rpp_path = Path(args.reaper_rpp).expanduser().resolve()
    tracks: list[tuple[str, Path, float, float]] = []
    if args.voice_track:
        tracks.append(("Voice", Path(args.voice_track).expanduser().resolve(), float(args.lead), 0.0))
    else:
        tracks.append(("Master Stem", output_path, 0.0, 0.0))
    if args.bgm_track:
        tracks.append(("BGM Bed", Path(args.bgm_track).expanduser().resolve(), 0.0, float(args.bgm_gain_db)))
    for idx, (cue_p, when_s, gain_db) in enumerate(sfx_cues, start=1):
        tracks.append((f"SFX {idx}", cue_p, when_s, gain_db))
    res = audio_dsp.emit_reaper_session(
        rpp_path,
        tracks=tracks,
        duck=float(args.duck_db) > 0.0,
        creative_sound_dir=creative_sound_dir,
        runner=runner,
    )
    return {"backend": res["backend"], "delegate_script": res.get("delegate_script"), "path": contract_home(res["path"])}


def _maybe_write_voice_meta(
    voice_meta_out: str | None,
    engine_meta: Mapping[str, Any],
    output_path: Path,
) -> None:
    if not voice_meta_out or not engine_meta.get("voice_id"):
        return
    meta_path = Path(voice_meta_out).expanduser().resolve()
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "voice_id": engine_meta["voice_id"],
        "ephemeral": bool(engine_meta.get("ephemeral", False)),
        "store": bool(engine_meta.get("store", True)),
        "sample_output": contract_home(output_path),
    }
    meta_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    return run_audio_pipeline()


if __name__ == "__main__":
    sys.exit(main())
