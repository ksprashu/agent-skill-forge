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

"""Stdlib-only Gemini API CLI controller & closed-loop verifier for image-gen.

What this script audits and enforces (V3)
-----------------------------------------
1. Model routing & deprecation fence: blocks shut-down image/verifier models at
   parse time (exit 2) before any subprocess runs.
2. Stage 1 frozen VisualRequirementSpec (`spec.json`): extracts explicit subject,
   aspect ratio, size floor, reference bindings, and exact quoted text literals
   plus medium-specific craft rules; computes an immutable SHA-256 spec digest.
3. Stage 3 mechanical binary gate (`L3`, `$0` tokens): parses PNG (`IHDR` + CRC32),
   JPEG (`SOF0`-`SOF3`+), and WebP (`VP8X`/`VP8 `/`VP8L`) headers in pure Python
   stdlib to verify non-empty bytes, decodable header dimensions, aspect ratio
   within 3.5% tolerance, and pixel long-edge floors (`>=1500px` for `>=2K`).
4. Stage 4 blinded multimodal rubric judge + deterministic Python provenance
   validator (`S9`): invokes `VERIFIER_MODEL_CHAIN` with `store: false` and
   `thinking_level: high`, checks that every frozen `AC-*` item is present with
   non-empty `observed_evidence`, recomputes `all_passed` in Python, and flags
   self-contradictory model verdicts.

What this script does NOT audit (V5)
------------------------------------
* Full pixel decompression beyond header & chunk framing (corrupt trailing scanlines
  inside an otherwise valid container header require a full codec decode).
* Semantic visual compliance when `--no-verify` is explicitly set (recorded in
  `<output>.provenance.json` under `unchecked_surfaces`).
* Network/account quota availability when `--dry-run` is set (recorded under
  `unchecked_surfaces`).

Exit codes: `0` verified pass (or `--dry-run` / healthy `--doctor`), `1` verification
or generation failure, `2` invalid CLI invocation or deprecated model ID.
"""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if sys.platform == "win32":  # pragma: no cover - Windows console encoding guard
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Model Routing & Deprecation Constants
# ---------------------------------------------------------------------------

VERIFIER_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-3.8-flash",
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

PRIMARY_IMAGE_MODEL = "gemini-nano-banana-2.1"
PRO_IMAGE_MODEL = "gemini-3-pro-image"
LITE_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
DEFAULT_VERIFIER_MODEL = VERIFIER_MODEL_CHAIN[0]
ALLOWED_VERIFIER_MODELS = frozenset(VERIFIER_MODEL_CHAIN)

MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

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

SUPPORTED_ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
)

SUPPORTED_SIZES: tuple[str, ...] = ("1K", "2K", "4K")
SUPPORTED_MODES: tuple[str, ...] = (
    "auto",
    "single",
    "diagram",
    "comic-grid",
    "comic-panels",
    "timeline",
)

MAX_REFERENCE_IMAGES = 14
UPLOAD_THRESHOLD_BYTES = 12 * 1024 * 1024
ASPECT_RATIO_TOLERANCE = 0.035
MIN_LONG_EDGE_BY_SIZE: dict[str, int] = {
    "1K": 512,
    "2K": 1500,
    "4K": 3000,
}

VALID_REFERENCE_ROLES = frozenset({"char", "character", "style", "prop", "anchor", "layout", "ref"})

JPEG_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)

RUBRIC_VERDICT_SCHEMA: dict[str, Any] = {
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

PROMPT_EXPANDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "expanded_prompt": {"type": "string"},
    },
    "required": ["expanded_prompt"],
}


class ConfigError(ValueError):
    """Raised on invalid CLI flags, bad manifests, or deprecated model IDs (exit 2)."""


# ---------------------------------------------------------------------------
# Subprocess Runner & Model Validation
# ---------------------------------------------------------------------------


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


def default_runner(
    cmd: Sequence[str], *, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    """Execute a CLI command with shell=False and capture-time redaction (Rules S4, S8)."""
    argv = [str(part) for part in cmd]
    try:
        proc = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return subprocess.CompletedProcess(
            argv,
            proc.returncode,
            redact_secrets(proc.stdout or ""),
            redact_secrets(proc.stderr or ""),
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(
            argv,
            127,
            "",
            redact_secrets(f"Command not found: {argv[0]} ({exc})"),
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        return subprocess.CompletedProcess(
            argv,
            124,
            redact_secrets(raw_out),
            redact_secrets(f"Command timed out after {timeout}s: {argv[0]}"),
        )


def validate_model_id(model_id: str, role: str = "image") -> None:
    """Reject shut-down, deprecated, or cross-role model IDs with an actionable hint."""
    cleaned = model_id.strip()
    if not cleaned:
        raise ConfigError(f"Empty {role} model identifier.")
    lowered = cleaned.lower()
    if lowered == "flash_medium":
        raise ConfigError(
            f"Model '{cleaned}' is obsolete ('flash_medium' is invalid). "
            f"Use '{PRIMARY_IMAGE_MODEL}' for image generation or '{DEFAULT_VERIFIER_MODEL}' for verification."
        )
    if role == "verifier":
        if lowered not in ALLOWED_VERIFIER_MODELS:
            raise ConfigError(
                f"Verifier model '{cleaned}' is not in VERIFIER_MODEL_CHAIN "
                f"({', '.join(VERIFIER_MODEL_CHAIN)}). Use '{DEFAULT_VERIFIER_MODEL}' instead."
            )
        return
    if lowered == LITE_IMAGE_MODEL:
        return
    if lowered.startswith("gemini-omni"):
        raise ConfigError(
            f"Model '{cleaned}' is a video model, not an image generation model. "
            f"Use '{PRIMARY_IMAGE_MODEL}' or '{PRO_IMAGE_MODEL}' instead."
        )
    for prefix in DEPRECATED_MODEL_PREFIXES:
        if lowered.startswith(prefix.lower()):
            raise ConfigError(
                f"Model '{cleaned}' is deprecated/shut down (matched '{prefix}'). "
                f"Use '{PRIMARY_IMAGE_MODEL}' or '{PRO_IMAGE_MODEL}' instead (see https://aistudio.google.com/docs/cli)."
            )


def target_mime_for_output(output_path: Path) -> str:
    """Infer desired response MIME type from the target filename extension."""
    ext = output_path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def parse_aspect_ratio_value(ar: str) -> float:
    """Convert an aspect ratio token such as '16:9' to its float width/height ratio."""
    if ar not in SUPPORTED_ASPECT_RATIOS:
        raise ConfigError(
            f"Unsupported aspect ratio '{ar}'. Supported: {', '.join(SUPPORTED_ASPECT_RATIOS)}"
        )
    w_str, h_str = ar.split(":", 1)
    return int(w_str) / int(h_str)


# ---------------------------------------------------------------------------
# Stage 1: Intent Parsing & Frozen VisualRequirementSpec Compilation
# ---------------------------------------------------------------------------

_DOUBLE_QUOTED_RE = re.compile(r'"([^"\n]{1,160})"')
_SINGLE_QUOTED_RE = re.compile(r"(?<![A-Za-z0-9])'([^'\n]{1,160})'(?![A-Za-z0-9])")


def extract_quoted_literals(prompt: str) -> list[str]:
    """Extract exact double- or single-quoted text literals while ignoring contractions."""
    found: list[str] = []
    spans: list[tuple[int, int, str]] = []
    for match in _DOUBLE_QUOTED_RE.finditer(prompt):
        val = match.group(1).strip()
        if val:
            spans.append((match.start(), match.end(), val))
    for match in _SINGLE_QUOTED_RE.finditer(prompt):
        val = match.group(1).strip()
        if val:
            spans.append((match.start(), match.end(), val))
    spans.sort(key=lambda item: item[0])
    for _, _, literal in spans:
        if literal not in found:
            found.append(literal)
    return found


def parse_reference_arg(raw_refs: Sequence[str] | None) -> list[dict[str, str]]:
    """Parse repeatable and comma-separated reference specs (`role:path` or `path`)."""
    if not raw_refs:
        return []
    parsed: list[dict[str, str]] = []
    for entry in raw_refs:
        for token in entry.split(","):
            item = token.strip()
            if not item:
                continue
            role = "ref"
            path_part = item
            if ":" in item:
                candidate_role, rest = item.split(":", 1)
                # Guard Windows drive letters like C:\img.png by whitelisting role names
                if candidate_role.lower() in VALID_REFERENCE_ROLES and rest.strip():
                    role = "char" if candidate_role.lower() == "character" else candidate_role.lower()
                    path_part = rest.strip()
            parsed.append({"role": role, "path": path_part})
    if len(parsed) > MAX_REFERENCE_IMAGES:
        raise ConfigError(
            f"Received {len(parsed)} reference images; maximum supported is {MAX_REFERENCE_IMAGES}."
        )
    return parsed


def resolve_mode(requested_mode: str, prompt: str, has_manifest: bool = False) -> str:
    """Resolve 'auto' deterministically from prompt structure and flags."""
    if requested_mode not in SUPPORTED_MODES:
        raise ConfigError(
            f"Unsupported mode '{requested_mode}'. Choose from: {', '.join(SUPPORTED_MODES)}"
        )
    if requested_mode != "auto":
        return requested_mode
    if has_manifest:
        return "timeline"
    lowered = prompt.lower()
    if any(
        cue in lowered
        for cue in ("comic grid", "comic strip", "2x2", "1x3", "1x4", "4-panel", "3-panel", "panel grid")
    ):
        return "comic-grid"
    if "comic panel" in lowered or "sequential panel" in lowered:
        return "comic-panels"
    if any(cue in lowered for cue in ("timeline", "step-by-step sequence", "progression sequence")):
        return "timeline"
    if any(
        cue in lowered
        for cue in (
            "diagram",
            "flowchart",
            "architecture",
            "topology",
            "infographic",
            "orthographic",
            "schematic",
            "sequence flow",
        )
    ):
        return "diagram"
    return "single"


def _implicit_constraints_for_mode(mode: str) -> list[str]:
    if mode == "comic-grid":
        return [
            "Explicit multi-panel grid geometry with crisp gutters and panel borders",
            "Left-to-right, top-to-bottom panel reading order",
            "High-contrast legible speech bubbles/captions with zero clipped lettering",
            "Locked character attire, facial features, and palette across all panels",
            "Minimum 2K output resolution floor so panel typography stays sharp",
        ]
    if mode in ("comic-panels", "timeline"):
        return [
            "Canonical style and character identity locked to the anchor reference",
            "Consistent horizon line, palette, and lighting progression across sequential frames",
            "Clear per-frame narrative beat delta without unwanted costume or prop drift",
        ]
    if mode == "diagram":
        return [
            "Crisp vector or orthographic visual hierarchy with unambiguous directional connectors",
            "Zero garbled pseudo-labels or illegible filler text",
            "High-contrast foreground nodes cleanly separated from background surface",
        ]
    return [
        "Clear focal hierarchy and intentional lighting direction",
        "Cohesive colour palette free of anatomical, geometric, or compression artefacts",
    ]


def _role_binding_sentence(references: Sequence[Mapping[str, str]]) -> str:
    if not references:
        return ""
    clauses: list[str] = []
    for idx, ref in enumerate(references, start=1):
        role = ref.get("role", "ref")
        if role == "char":
            clauses.append(f"reference image {idx} locks character identity and wardrobe")
        elif role == "style":
            clauses.append(f"reference image {idx} locks colour palette, brushwork, and lighting style")
        elif role == "prop":
            clauses.append(f"reference image {idx} locks object/prop geometry")
        elif role == "anchor":
            clauses.append(f"reference image {idx} is the canonical sequence style/character anchor")
        else:
            clauses.append(f"reference image {idx} provides visual continuity grounding")
    return "Reference grounding: " + "; ".join(clauses) + "."


def compile_spec(
    *,
    prompt: str,
    mode: str,
    style: str | None,
    aspect_ratio: str,
    image_size: str,
    references: Sequence[Mapping[str, str]],
    panel_index: int | None = None,
    total_panels: int | None = None,
) -> dict[str, Any]:
    """Compile an immutable Stage 1 VisualRequirementSpec dictionary."""
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ConfigError("Prompt must not be empty.")
    _ = parse_aspect_ratio_value(aspect_ratio)
    if image_size not in SUPPORTED_SIZES:
        raise ConfigError(f"Unsupported image size '{image_size}'. Choose from: {', '.join(SUPPORTED_SIZES)}")

    resolved_mode = resolve_mode(mode, cleaned_prompt, has_manifest=panel_index is not None)
    quoted_literals = extract_quoted_literals(cleaned_prompt)
    has_dense_text = len(quoted_literals) >= 2 or sum(len(lit) for lit in quoted_literals) >= 24

    effective_size = image_size
    if effective_size == "1K" and (resolved_mode == "comic-grid" or has_dense_text):
        effective_size = "2K"

    implicit_rules = _implicit_constraints_for_mode(resolved_mode)

    prompt_parts = [cleaned_prompt.rstrip(".") + "."]
    if style and style.strip():
        prompt_parts.append(f"Art direction & style: {style.strip()}.")
    if panel_index is not None and total_panels is not None:
        prompt_parts.append(
            f"Sequential frame {panel_index} of {total_panels}: preserve canonical anchor identity and lighting continuity."
        )
    ref_sentence = _role_binding_sentence(references)
    if ref_sentence:
        prompt_parts.append(ref_sentence)
    if quoted_literals:
        exact_list = ", ".join(f'"{lit}"' for lit in quoted_literals)
        prompt_parts.append(f"Render exact legible text verbatim: {exact_list}.")
    prompt_parts.append("Craft requirements: " + "; ".join(implicit_rules) + ".")
    compiled_prompt = " ".join(prompt_parts)

    criteria: list[dict[str, Any]] = []
    criteria.append(
        {
            "id": f"AC-{len(criteria) + 1}",
            "category": "subject",
            "requirement": f"Accurately depicts the requested subject and action: {cleaned_prompt}",
            "mandatory": True,
        }
    )
    if style and style.strip():
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "style",
                "requirement": f"Consistently executes the requested art direction: {style.strip()}",
                "mandatory": True,
            }
        )
    if resolved_mode == "comic-grid":
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "geometry",
                "requirement": (
                    "Displays a multi-panel comic grid with clear panel borders/gutters, "
                    "left-to-right top-to-bottom reading flow, and consistent character appearance across panels."
                ),
                "mandatory": True,
            }
        )
    if references or resolved_mode in ("comic-panels", "timeline"):
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "continuity",
                "requirement": "Preserves character, palette, and structural continuity with supplied reference image(s).",
                "mandatory": True,
            }
        )
    if quoted_literals:
        exact_list = ", ".join(f'"{lit}"' for lit in quoted_literals)
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "category": "text",
                "requirement": f"Renders exact text literal(s) {exact_list} legibly with zero spelling errors or clipped glyphs.",
                "mandatory": True,
            }
        )
    criteria.append(
        {
            "id": f"AC-{len(criteria) + 1}",
            "category": "craft",
            "requirement": implicit_rules[0] + (f" ({implicit_rules[1]})" if len(implicit_rules) > 1 else ""),
            "mandatory": True,
        }
    )

    return {
        "schema_version": 1,
        "mode": resolved_mode,
        "raw_prompt": cleaned_prompt,
        "compiled_prompt": compiled_prompt,
        "style": style.strip() if style and style.strip() else None,
        "aspect_ratio": aspect_ratio,
        "image_size": effective_size,
        "has_dense_text": has_dense_text,
        "explicit_constraints": {
            "aspect_ratio": aspect_ratio,
            "image_size": effective_size,
            "quoted_literals": quoted_literals,
            "reference_count": len(references),
            "references": [dict(r) for r in references],
            "panel_index": panel_index,
            "total_panels": total_panels,
        },
        "implicit_constraints": implicit_rules,
        "acceptance_criteria": criteria,
    }


def compute_spec_digest(spec: Mapping[str, Any]) -> str:
    """Return canonical SHA-256 hex digest of the frozen acceptance spec."""
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_expanded_prompt(
    raw_prompt: str, expanded_prompt: str, quoted_literals: Sequence[str]
) -> tuple[bool, list[str]]:
    """Ensure LLM prompt expansion is non-empty and never drops quoted literals."""
    cleaned = expanded_prompt.strip()
    if not cleaned or not raw_prompt.strip():
        return False, list(quoted_literals)
    missing = [lit for lit in quoted_literals if lit not in cleaned]
    return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# Stage 2: Model Routing, Asset Upload Caching & CLI Command Builders
# ---------------------------------------------------------------------------


def build_image_model_chain(
    explicit_model: str | None,
    *,
    mode: str,
    has_references: bool,
    has_quoted_text: bool,
    multi_panel: bool,
) -> list[str]:
    """Construct the primary + 429/503 quota-failover chain for image generation."""
    allow_lite = (
        not has_references
        and not multi_panel
        and not has_quoted_text
        and mode not in ("comic-grid", "comic-panels", "timeline")
    )
    if explicit_model:
        validate_model_id(explicit_model, role="image")
        primary = explicit_model.strip()
        if primary.lower() == LITE_IMAGE_MODEL and not allow_lite:
            raise ConfigError(
                f"Model '{LITE_IMAGE_MODEL}' is restricted to 1-shot unreferenced images without quoted text or multi-panel sequences "
                f"(use '{PRIMARY_IMAGE_MODEL}' or '{PRO_IMAGE_MODEL}' instead)."
            )
    elif mode == "comic-grid" or has_quoted_text:
        primary = PRO_IMAGE_MODEL
    else:
        primary = PRIMARY_IMAGE_MODEL

    candidates = [primary, PRO_IMAGE_MODEL, PRIMARY_IMAGE_MODEL]
    if allow_lite:
        candidates.append(LITE_IMAGE_MODEL)

    deduped: list[str] = []
    for model_id in candidates:
        if model_id not in deduped:
            deduped.append(model_id)
    return deduped


def build_verifier_model_chain(explicit_verifier: str | None) -> list[str]:
    """Construct the ordered blinded multimodal verifier model failover chain."""
    if explicit_verifier:
        validate_model_id(explicit_verifier, role="verifier")
        start = [explicit_verifier.strip()]
    else:
        start = []
    chain: list[str] = []
    for item in [*start, *VERIFIER_MODEL_CHAIN]:
        if item not in chain:
            chain.append(item)
    return chain


def normalize_cli_positional_prompt(prompt: str) -> str:
    """Ensure positional CLI prompt text never starts with '-' so it cannot be parsed as a flag (CWE-88)."""
    text = str(prompt)
    if text.lstrip().startswith("-"):
        return f"Prompt: {text.lstrip()}"
    return text


def build_image_cli_command(
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    image_size: str,
    out_path: Path,
    references: Sequence[str],
    previous_interaction_id: str | None,
    mode: str,
    has_quoted_text: bool,
    target_mime: str,
) -> list[str]:
    """Build the exact `gemini-api image ... -o json` argv list."""
    cmd: list[str] = [
        "gemini-api",
        "image",
        normalize_cli_positional_prompt(prompt),
        "-m",
        model,
        "--aspect-ratio",
        aspect_ratio,
        "--image-size",
        image_size,
    ]
    for ref in references:
        cmd.extend(["-i", str(ref)])
    if previous_interaction_id:
        cmd.extend(["--previous-interaction-id", previous_interaction_id])

    body: dict[str, Any] = {
        "response_format": {"mime_type": target_mime},
    }
    if mode in ("comic-grid", "diagram") or has_quoted_text:
        body["generation_config"] = {"thinking_level": "high"}

    cmd.extend(["--body", json.dumps(body, separators=(",", ":"))])
    cmd.extend(["--out", str(out_path), "-o", "json"])
    return cmd


_FILES_URI_RE = re.compile(r"^files/[A-Za-z0-9_-]+$")


def validate_image_reference_asset(
    path_or_uri: str,
    *,
    allowed_root: Path | None = None,
    label: str = "reference image",
) -> str:
    """Validate a reference URI or verify local file existence, containment, and image magic header."""
    cleaned = str(path_or_uri).strip()
    if not cleaned:
        raise ConfigError(f"Empty {label} path.")
    local = Path(cleaned)
    if _FILES_URI_RE.fullmatch(cleaned) and not local.exists():
        return cleaned
    try:
        resolved = local.resolve()
    except OSError as exc:
        raise ConfigError(f"Invalid {label} path '{path_or_uri}': {exc}") from exc
    if allowed_root is not None:
        root_resolved = allowed_root.resolve()
        if not resolved.is_relative_to(root_resolved):
            raise ConfigError(
                f"{label} path '{path_or_uri}' escapes allowed directory '{root_resolved}'."
            )
    if not resolved.is_file():
        raise ConfigError(f"{label} file does not exist: {path_or_uri}")
    try:
        inspect_image_header(resolved.read_bytes())
    except (OSError, ValueError) as exc:
        raise ConfigError(
            f"{label} '{path_or_uri}' is not a valid PNG, JPEG, or WebP image: {exc}"
        ) from exc
    return str(resolved)


class AssetCache:
    """Uploads >12MB or reused local reference assets once via `gemini-api files upload`."""

    def __init__(self, runner: Callable[..., Any]) -> None:
        self._runner = runner
        self._uploaded: dict[str, str] = {}

    def resolve(self, path_or_uri: str, *, reused: bool = False) -> str:
        local = Path(path_or_uri)
        if _FILES_URI_RE.fullmatch(path_or_uri) and not local.exists():
            return path_or_uri
        resolved_str = validate_image_reference_asset(path_or_uri, label="Reference image")
        local = Path(resolved_str)
        key = str(local)
        if key in self._uploaded:
            return self._uploaded[key]
        size_bytes = local.stat().st_size
        if size_bytes <= UPLOAD_THRESHOLD_BYTES and not reused:
            return str(local)

        proc = self._runner(["gemini-api", "files", "upload", str(local), "--wait"], timeout=180)
        if proc.returncode == 0:
            uri = _parse_uploaded_file_uri(proc.stdout)
            if uri:
                self._uploaded[key] = uri
                return uri
        if size_bytes > UPLOAD_THRESHOLD_BYTES:
            diag = redact_secrets((proc.stderr or "").strip() or (proc.stdout or "").strip())
            raise RuntimeError(
                f"Failed to upload >12MB reference '{path_or_uri}' via `gemini-api files upload`: {diag}"
            )
        return str(local)


def _parse_uploaded_file_uri(stdout: str) -> str | None:
    text = stdout.strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            payload = json.loads(text)
            for field in ("uri", "name", "id"):
                val = payload.get(field)
                if isinstance(val, str) and _FILES_URI_RE.fullmatch(val.strip()):
                    return val.strip()
        except ValueError:
            pass
    match = re.search(r"(?:^|\s)(files/[A-Za-z0-9_-]+)(?=\s|$)", text)
    return match.group(1) if match else None


def extract_generate_text(stdout: str) -> str:
    """Extract model text payload from `gemini-api generate --stream=false -o json` stdout."""
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from `gemini-api generate -o json`.")
    steps = data.get("steps")
    if isinstance(steps, list):
        chunks: list[str] = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                        chunks.append(part["text"])
        if chunks:
            return "\n".join(chunks).strip()
    if isinstance(data.get("text"), str):
        return data["text"].strip()
    raise ValueError("No `model_output` text content found in `gemini-api generate` JSON output.")


def expand_prompt_via_cli(
    spec: Mapping[str, Any],
    verifier_chain: Sequence[str],
    runner: Callable[..., Any],
) -> str:
    """Optionally enrich prompt art direction via Argon while locking quoted literals."""
    quoted = list(spec["explicit_constraints"]["quoted_literals"])
    expander_instruction = (
        "Expand the following image generation request into a vivid, concrete art-direction prompt "
        "preserving subject counts, composition, and EVERY exact quoted string literal character-for-character.\n"
        f"MODE: {spec['mode']}\n"
        f"BASE_PROMPT: {spec['compiled_prompt']}"
    )
    body = {
        "store": False,
        "generation_config": {"thinking_level": "high"},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": PROMPT_EXPANDER_SCHEMA,
        },
    }
    for model_id in verifier_chain:
        cmd = [
            "gemini-api",
            "generate",
            normalize_cli_positional_prompt(expander_instruction),
            "-m",
            model_id,
            "--stream=false",
            "-o",
            "json",
            "--body",
            json.dumps(body, separators=(",", ":")),
        ]
        proc = runner(cmd, timeout=120)
        if proc.returncode != 0:
            continue
        try:
            raw_text = extract_generate_text(proc.stdout)
            parsed = json.loads(raw_text)
            candidate = str(parsed.get("expanded_prompt", "")).strip()
        except (ValueError, TypeError):
            continue
        ok, missing = validate_expanded_prompt(spec["raw_prompt"], candidate, quoted)
        if ok:
            return candidate
        print(
            f"[image-gen] Prompt expansion dropped quoted literal(s) {missing}; keeping deterministic compiled prompt.",
            file=sys.stderr,
        )
        return str(spec["compiled_prompt"])
    return str(spec["compiled_prompt"])


# ---------------------------------------------------------------------------
# Stage 3: Pure-Stdlib Binary Image Mechanical Verifier (PNG / JPEG / WebP)
# ---------------------------------------------------------------------------


def inspect_image_header(data: bytes) -> dict[str, Any]:
    """Extract MIME type and exact pixel dimensions from PNG, JPEG, or WebP bytes."""
    size = len(data)
    if size < 16:
        raise ValueError(f"Image file is empty or truncated ({size} bytes).")

    # 1. PNG: 8-byte signature + 4-byte length (13) + 'IHDR' + 13-byte payload + 4-byte CRC32
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if size < 33:
            raise ValueError("Truncated PNG header: fewer than 33 bytes for IHDR.")
        ihdr_len = struct.unpack(">I", data[8:12])[0]
        chunk_type = data[12:16]
        if chunk_type != b"IHDR" or ihdr_len != 13:
            raise ValueError(f"Invalid PNG IHDR chunk header (type={chunk_type!r}, len={ihdr_len}).")
        expected_crc = struct.unpack(">I", data[29:33])[0]
        actual_crc = zlib.crc32(data[12:29]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("Corrupt PNG IHDR CRC32 checksum.")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid PNG dimensions ({width}x{height}).")
        return {"mime_type": "image/png", "width": width, "height": height, "size_bytes": size}

    # 2. JPEG: SOI (FF D8) followed by marker segments including SOF0..SOF3+
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos < size:
            if data[pos] != 0xFF:
                raise ValueError(f"Corrupt JPEG marker framing at byte offset {pos}.")
            while pos < size and data[pos] == 0xFF:
                pos += 1
            if pos >= size:
                break
            marker = data[pos]
            pos += 1
            if marker in (0xD9, 0xDA):  # EOI or SOS
                break
            if marker == 0x00 or marker == 0x01 or (0xD0 <= marker <= 0xD8):
                continue
            if pos + 2 > size:
                raise ValueError("Truncated JPEG segment length.")
            seg_len = struct.unpack(">H", data[pos : pos + 2])[0]
            if seg_len < 2 or pos + seg_len > size:
                raise ValueError("Truncated or malformed JPEG marker segment.")
            if marker in JPEG_SOF_MARKERS:
                if seg_len < 7:
                    raise ValueError("Truncated JPEG SOF header.")
                height, width = struct.unpack(">HH", data[pos + 3 : pos + 7])
                if width <= 0 or height <= 0:
                    raise ValueError(f"Invalid JPEG SOF dimensions ({width}x{height}).")
                return {"mime_type": "image/jpeg", "width": width, "height": height, "size_bytes": size}
            pos += seg_len
        raise ValueError("JPEG stream contains no recognizable SOF dimension header.")

    # 3. WebP: RIFF + <size_le32> + WEBP + ('VP8X' | 'VP8 ' | 'VP8L')
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if size < 20:
            raise ValueError("Truncated RIFF/WebP container header.")
        riff_payload_size = struct.unpack("<I", data[4:8])[0]
        if size < riff_payload_size + 8:
            raise ValueError(
                f"Truncated WebP RIFF payload: header declares {riff_payload_size + 8} bytes, got {size}."
            )
        fourcc = data[12:16]
        chunk_size = struct.unpack("<I", data[16:20])[0]
        if 20 + chunk_size > size:
            raise ValueError("Truncated WebP first chunk payload.")
        if fourcc == b"VP8X":
            if chunk_size < 10 or size < 30:
                raise ValueError("Truncated WebP VP8X header.")
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return {"mime_type": "image/webp", "width": width, "height": height, "size_bytes": size}
        if fourcc == b"VP8 ":
            if chunk_size < 10 or size < 30:
                raise ValueError("Truncated WebP VP8 keyframe header.")
            if (data[20] & 0x01) != 0 or data[23:26] != b"\x9d\x01\x2a":
                raise ValueError("Invalid WebP VP8 keyframe sync code.")
            raw_w, raw_h = struct.unpack("<HH", data[26:30])
            width = raw_w & 0x3FFF
            height = raw_h & 0x3FFF
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid WebP VP8 dimensions ({width}x{height}).")
            return {"mime_type": "image/webp", "width": width, "height": height, "size_bytes": size}
        if fourcc == b"VP8L":
            if chunk_size < 5 or size < 25 or data[20] != 0x2F:
                raise ValueError("Invalid or truncated WebP VP8L lossless header.")
            bits = struct.unpack("<I", data[21:25])[0]
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return {"mime_type": "image/webp", "width": width, "height": height, "size_bytes": size}
        raise ValueError(f"Unsupported WebP chunk type {fourcc!r}.")

    raise ValueError("Unrecognized or corrupt image magic header (expected PNG, JPEG, or WebP).")


def verify_image_mechanical(
    image_path: Path, *, target_ar: str, target_size: str
) -> dict[str, Any]:
    """Run Stage 3 deterministic header, aspect-ratio, and pixel-floor checks."""
    target_ratio = parse_aspect_ratio_value(target_ar)
    min_long_edge = MIN_LONG_EDGE_BY_SIZE.get(target_size, 512)

    if not image_path.is_file():
        return {
            "passed": False,
            "mime_type": None,
            "width": 0,
            "height": 0,
            "size_bytes": 0,
            "actual_ratio": 0.0,
            "target_ratio": round(target_ratio, 5),
            "ratio_error_pct": 100.0,
            "min_long_edge": min_long_edge,
            "errors": [f"Candidate image file does not exist: {image_path}"],
        }

    raw_bytes = image_path.read_bytes()
    try:
        header = inspect_image_header(raw_bytes)
    except ValueError as exc:
        return {
            "passed": False,
            "mime_type": None,
            "width": 0,
            "height": 0,
            "size_bytes": len(raw_bytes),
            "actual_ratio": 0.0,
            "target_ratio": round(target_ratio, 5),
            "ratio_error_pct": 100.0,
            "min_long_edge": min_long_edge,
            "errors": [str(exc)],
        }

    width = int(header["width"])
    height = int(header["height"])
    actual_ratio = width / height
    rel_error = abs(actual_ratio - target_ratio) / target_ratio
    long_edge = max(width, height)

    errors: list[str] = []
    if rel_error > ASPECT_RATIO_TOLERANCE:
        errors.append(
            f"Aspect ratio mismatch: image is {width}x{height} ({actual_ratio:.4f}), "
            f"target '{target_ar}' is {target_ratio:.4f} ({rel_error * 100:.2f}% > {ASPECT_RATIO_TOLERANCE * 100:.1f}% tolerance)."
        )
    if long_edge < min_long_edge:
        errors.append(
            f"Undersized image resolution: long edge is {long_edge}px ({width}x{height}), "
            f"minimum floor for size '{target_size}' is {min_long_edge}px."
        )

    return {
        "passed": len(errors) == 0,
        "mime_type": header["mime_type"],
        "width": width,
        "height": height,
        "size_bytes": header["size_bytes"],
        "actual_ratio": round(actual_ratio, 5),
        "target_ratio": round(target_ratio, 5),
        "ratio_error_pct": round(rel_error * 100.0, 3),
        "min_long_edge": min_long_edge,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Stage 4: Blinded Multimodal Rubric Judge & Provenance Consistency Validator
# ---------------------------------------------------------------------------


def build_judge_cli_command(
    *,
    spec: Mapping[str, Any],
    verifier_model: str,
    candidate_ref: str,
    reference_uris: Sequence[str],
) -> list[str]:
    """Build stateless blinded `gemini-api generate` command for Stage 4 judging."""
    ac_json = json.dumps(spec["acceptance_criteria"], separators=(",", ":"))
    judge_prompt = (
        "You are an independent, blinded visual quality auditor. "
        "Inspect the candidate image (first attached image) and any reference images (subsequent attached images). "
        "Evaluate EVERY acceptance criterion strictly on visible evidence in the candidate image. "
        "Cite concrete observed visual evidence for each criterion, and provide surgical fix instructions for any failure.\n"
        f"MODE: {spec['mode']}\n"
        f"TARGET_ASPECT_RATIO: {spec['aspect_ratio']}\n"
        f"ACCEPTANCE_CRITERIA_JSON:\n{ac_json}"
    )
    body = {
        "store": False,
        "generation_config": {"thinking_level": "high"},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": RUBRIC_VERDICT_SCHEMA,
        },
    }
    cmd = [
        "gemini-api",
        "generate",
        normalize_cli_positional_prompt(judge_prompt),
        "-m",
        verifier_model,
        "-i",
        str(candidate_ref),
    ]
    for ref_uri in reference_uris:
        cmd.extend(["-i", str(ref_uri)])
    cmd.extend(["--stream=false", "-o", "json", "--body", json.dumps(body, separators=(",", ":"))])
    return cmd


def validate_rubric_verdict(
    verdict_payload: Mapping[str, Any], spec: Mapping[str, Any]
) -> dict[str, Any]:
    """Deterministically enforce AC completeness, evidence provenance, and non-contradiction."""
    expected_acs = list(spec.get("acceptance_criteria", []))
    expected_by_id = {str(item["id"]): item for item in expected_acs}
    raw_results = verdict_payload.get("criteria_results")

    errors: list[str] = []
    if not isinstance(raw_results, list) or not raw_results:
        return {
            "passed": False,
            "pass_ratio": 0.0,
            "failed_ids": list(expected_by_id.keys()),
            "geometry_failed": True,
            "core_style_failed": False,
            "contradiction_detected": False,
            "structural_error": True,
            "errors": ["Judge payload missing non-empty 'criteria_results' list."],
            "fix_instructions": [],
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
            "criteria_results": [],
        }

    seen_ids: dict[str, dict[str, Any]] = {}
    for entry in raw_results:
        if not isinstance(entry, dict):
            errors.append("Malformed non-object item in 'criteria_results'.")
            continue
        ac_id = str(entry.get("id", "")).strip()
        if not ac_id or ac_id not in expected_by_id:
            errors.append(f"Unexpected or empty criterion ID '{ac_id}' in judge output.")
            continue
        if ac_id in seen_ids:
            errors.append(f"Duplicate criterion ID '{ac_id}' in judge output.")
            continue
        passed_val = entry.get("passed")
        evidence = str(entry.get("observed_evidence", "")).strip()
        fix_inst = str(entry.get("fix_instruction", "")).strip()
        if not isinstance(passed_val, bool):
            errors.append(f"Criterion '{ac_id}' has non-boolean 'passed' field.")
            continue
        if not evidence:
            errors.append(f"Criterion '{ac_id}' lacks required 'observed_evidence' provenance.")
            continue
        seen_ids[ac_id] = {
            "id": ac_id,
            "category": expected_by_id[ac_id].get("category", "general"),
            "mandatory": bool(expected_by_id[ac_id].get("mandatory", True)),
            "passed": passed_val,
            "observed_evidence": evidence,
            "fix_instruction": fix_inst,
        }

    missing_ids = [ac_id for ac_id in expected_by_id if ac_id not in seen_ids]
    if missing_ids:
        errors.append(f"Judge omitted mandatory acceptance criteria: {', '.join(missing_ids)}")

    mandatory_items = [item for item in expected_acs if item.get("mandatory", True)]
    if not mandatory_items:
        errors.append("Spec defines zero mandatory acceptance criteria; failing closed (S9).")
        return {
            "passed": False,
            "pass_ratio": 0.0,
            "failed_ids": list(expected_by_id.keys()),
            "geometry_failed": False,
            "core_style_failed": False,
            "contradiction_detected": False,
            "structural_error": True,
            "errors": errors,
            "fix_instructions": [],
            "edit_delta_prompt": "",
            "regenerated_prompt": "",
            "criteria_results": [seen_ids[ac_id] for ac_id in expected_by_id if ac_id in seen_ids],
        }

    mandatory_total = len(mandatory_items)
    passed_mandatory = sum(
        1 for item in mandatory_items if seen_ids.get(str(item["id"]), {}).get("passed") is True
    )
    pass_ratio = round(passed_mandatory / mandatory_total, 4)

    failed_ids = [
        str(item["id"])
        for item in mandatory_items
        if seen_ids.get(str(item["id"]), {}).get("passed") is not True
    ]
    geometry_failed = any(
        expected_by_id[ac_id].get("category") == "geometry" for ac_id in failed_ids if ac_id in expected_by_id
    )
    core_style_failed = any(
        expected_by_id[ac_id].get("category") in ("style", "subject")
        for ac_id in failed_ids
        if ac_id in expected_by_id
    )
    fix_instructions = [
        seen_ids[ac_id]["fix_instruction"] or f"Satisfy {ac_id}: {expected_by_id[ac_id]['requirement']}"
        for ac_id in failed_ids
        if ac_id in seen_ids
    ]

    computed_all_passed = len(errors) == 0 and len(failed_ids) == 0
    claimed_overall = verdict_payload.get("overall_pass")
    contradiction_detected = False
    if isinstance(claimed_overall, bool) and claimed_overall != computed_all_passed:
        contradiction_detected = True
        errors.append(
            f"Self-contradictory judge verdict: model claimed overall_pass={claimed_overall} "
            f"while per-criterion pass computation is {computed_all_passed}."
        )

    final_passed = computed_all_passed and not contradiction_detected
    return {
        "passed": final_passed,
        "pass_ratio": pass_ratio,
        "failed_ids": failed_ids,
        "geometry_failed": geometry_failed,
        "core_style_failed": core_style_failed,
        "contradiction_detected": contradiction_detected,
        "structural_error": len(errors) > 0,
        "errors": errors,
        "fix_instructions": fix_instructions,
        "edit_delta_prompt": str(verdict_payload.get("edit_delta_prompt") or "").strip(),
        "regenerated_prompt": str(verdict_payload.get("regenerated_prompt") or "").strip(),
        "criteria_results": [seen_ids[ac_id] for ac_id in expected_by_id if ac_id in seen_ids],
    }


def select_remediation_mode(
    *,
    mechanical_passed: bool,
    rubric_validation: Mapping[str, Any] | None,
    response_id: str | None,
) -> str:
    """Choose `edit_turn` (--previous-interaction-id) vs full `regenerate`."""
    if not mechanical_passed or not response_id or rubric_validation is None:
        return "regenerate"
    if (
        rubric_validation.get("structural_error")
        or rubric_validation.get("geometry_failed")
        or rubric_validation.get("core_style_failed")
    ):
        return "regenerate"
    if float(rubric_validation.get("pass_ratio", 0.0)) >= 0.70:
        return "edit_turn"
    return "regenerate"


# ---------------------------------------------------------------------------
# End-to-End Closed-Loop Frame Execution & Sequential Manifest Orchestration
# ---------------------------------------------------------------------------


def _run_generation_attempt(
    *,
    prompt: str,
    model_chain: Sequence[str],
    aspect_ratio: str,
    image_size: str,
    staged_out: Path,
    reference_uris: Sequence[str],
    previous_interaction_id: str | None,
    mode: str,
    has_quoted_text: bool,
    target_mime: str,
    runner: Callable[..., Any],
) -> tuple[dict[str, Any] | None, str]:
    """Try each model in `model_chain` until `gemini-api image -o json` succeeds."""
    last_err = "No models available in chain."
    staged_dir = staged_out.parent.resolve()
    for model_id in model_chain:
        cmd = build_image_cli_command(
            prompt=prompt,
            model=model_id,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            out_path=staged_out,
            references=reference_uris,
            previous_interaction_id=previous_interaction_id,
            mode=mode,
            has_quoted_text=has_quoted_text,
            target_mime=target_mime,
        )
        proc = runner(cmd, timeout=240)
        if proc.returncode != 0:
            err_msg = redact_secrets((proc.stderr or "").strip() or (proc.stdout or "").strip())
            last_err = f"{model_id} exited {proc.returncode}: {err_msg}"
            continue
        try:
            payload = json.loads(proc.stdout)
        except ValueError as exc:
            last_err = f"{model_id} emitted non-JSON output: {redact_secrets(str(exc))}"
            continue
        written_path_str = payload.get("path") if isinstance(payload, dict) else None
        candidate: Path | None = None
        if isinstance(written_path_str, str) and written_path_str.strip():
            raw_written = Path(written_path_str.strip())
            if raw_written.is_absolute():
                resolved_written = raw_written.resolve()
            else:
                cwd_candidate = (Path.cwd() / raw_written).resolve()
                dir_candidate = (staged_dir / raw_written).resolve()
                resolved_written = (
                    cwd_candidate
                    if cwd_candidate.is_relative_to(staged_dir) and cwd_candidate.is_file()
                    else dir_candidate
                )
            if (
                resolved_written.is_relative_to(staged_dir)
                and (
                    resolved_written.stem == staged_out.stem
                    or resolved_written.stem.startswith(f"{staged_out.stem}_")
                )
                and resolved_written.is_file()
            ):
                candidate = resolved_written
            else:
                last_err = (
                    f"{model_id} returned output path outside staged target "
                    f"('{written_path_str}'); refusing untrusted move/unlink."
                )
                continue
        else:
            matches = sorted(
                p
                for p in staged_dir.glob(f"{glob.escape(staged_out.stem)}.*")
                if p.is_file() and p.resolve().is_relative_to(staged_dir)
            )
            if matches:
                candidate = matches[0].resolve()
            else:
                last_err = f"{model_id} JSON missing 'path' field and no staged output file found."
                continue
        return {
            "model": model_id,
            "path": candidate,
            "mime_type": payload.get("mime_type"),
            "size_bytes": payload.get("size_bytes"),
            "response_id": payload.get("response_id"),
            "status": payload.get("status", "completed"),
        }, ""
    return None, last_err


def _run_blinded_judge_with_fallback(
    *,
    spec: Mapping[str, Any],
    verifier_chain: Sequence[str],
    candidate_path: Path,
    reference_uris: Sequence[str],
    runner: Callable[..., Any],
) -> tuple[dict[str, Any] | None, str, str]:
    """Run Stage 4 blinded rubric judge with verifier model quota failover."""
    last_err = "No verifier models available."
    for verifier_model in verifier_chain:
        if verifier_model == "gemini-3.8-flash":
            print(
                "[image-gen] WARNING: Primary Argon/Carbon verifiers unavailable; "
                "falling back to emergency 'gemini-3.8-flash' verifier.",
                file=sys.stderr,
            )
        cmd = build_judge_cli_command(
            spec=spec,
            verifier_model=verifier_model,
            candidate_ref=str(candidate_path),
            reference_uris=reference_uris,
        )
        proc = runner(cmd, timeout=180)
        if proc.returncode != 0:
            err_msg = redact_secrets((proc.stderr or "").strip() or (proc.stdout or "").strip())
            last_err = f"{verifier_model} exited {proc.returncode}: {err_msg}"
            continue
        try:
            raw_verdict_text = extract_generate_text(proc.stdout)
            verdict_json = json.loads(raw_verdict_text)
        except ValueError as exc:
            last_err = f"{verifier_model} returned unparseable rubric JSON: {redact_secrets(str(exc))}"
            continue
        if not isinstance(verdict_json, dict):
            last_err = f"{verifier_model} rubric verdict is not a JSON object."
            continue
        return validate_rubric_verdict(verdict_json, spec), verifier_model, ""
    return None, "", last_err


def _finalize_verified_image(
    candidate_path: Path,
    output_path: Path,
    actual_mime: str | None,
) -> tuple[Path, str | None]:
    """Move `candidate_path` to `output_path`, rewriting extension if binary MIME differs (P1 #3)."""
    requested_mime = target_mime_for_output(output_path)
    final_path = output_path
    if actual_mime and actual_mime != requested_mime and actual_mime in MIME_TO_EXT:
        target_ext = MIME_TO_EXT[actual_mime]
        final_path = output_path.with_suffix(target_ext)
        if final_path != output_path:
            print(
                f"[image-gen] NOTE: Candidate binary header is '{actual_mime}' (requested '{requested_mime}'); "
                f"writing output to {final_path} instead of {output_path}.",
                file=sys.stderr,
            )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(candidate_path), str(final_path))
    if final_path != output_path:
        if output_path.is_file():
            output_path.unlink()
        stale_req_prov = Path(f"{output_path}.provenance.json")
        if stale_req_prov.is_file():
            stale_req_prov.unlink()
        stale_req_rep = Path(f"{output_path}.report.json")
        if stale_req_rep.is_file():
            stale_req_rep.unlink()
    requested_out = str(output_path) if final_path != output_path else None
    return final_path, requested_out


def execute_single_asset(
    *,
    frozen_spec: Mapping[str, Any],
    output_path: Path,
    model_chain: Sequence[str],
    verifier_chain: Sequence[str],
    asset_cache: AssetCache,
    runner: Callable[..., Any],
    max_attempts: int,
    raw_prompt: bool,
    no_verify: bool,
    allow_unverified: bool,
    override_reason: str | None = None,
    initial_interaction_id: str | None = None,
    reused_refs: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Run the 4-stage generate -> mechanical -> blinded judge -> retry loop for one image."""
    clean_override_reason = redact_secrets((override_reason or "").strip())
    if allow_unverified and not clean_override_reason:
        raise ConfigError(
            '--allow-unverified requires a non-empty --override-reason "<why>" '
            "(ENGINEERING_STANDARD §9 loud-override rule)."
        )
    spec = copy.deepcopy(dict(frozen_spec))
    initial_digest = compute_spec_digest(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_mime = target_mime_for_output(output_path)

    ref_specs = list(spec.get("explicit_constraints", {}).get("references", []))
    for ref_item in ref_specs:
        validate_image_reference_asset(ref_item["path"], label="Reference image")

    base_prompt = (
        str(spec["compiled_prompt"])
        if raw_prompt
        else expand_prompt_via_cli(spec, verifier_chain, runner)
    )
    active_prompt = base_prompt
    active_prev_id = initial_interaction_id

    has_quoted = bool(spec.get("explicit_constraints", {}).get("quoted_literals"))

    attempt_history: list[dict[str, Any]] = []
    last_candidate_path: Path | None = None
    last_mechanical: dict[str, Any] | None = None
    last_rubric: dict[str, Any] | None = None
    last_gen_meta: dict[str, Any] | None = None

    for attempt in range(1, max_attempts + 1):
        # Enforce immutable spec invariant across every retry attempt
        if compute_spec_digest(spec) != initial_digest:
            raise RuntimeError("Frozen VisualRequirementSpec mutated across retry attempts.")

        use_upload = reused_refs or attempt > 1
        resolved_refs = [asset_cache.resolve(item["path"], reused=use_upload) for item in ref_specs]
        staged_target = output_path.parent / f".{output_path.stem}.attempt{attempt}{output_path.suffix or '.png'}"

        gen_meta, gen_err = _run_generation_attempt(
            prompt=active_prompt,
            model_chain=model_chain,
            aspect_ratio=spec["aspect_ratio"],
            image_size=spec["image_size"],
            staged_out=staged_target,
            reference_uris=resolved_refs,
            previous_interaction_id=active_prev_id,
            mode=spec["mode"],
            has_quoted_text=has_quoted,
            target_mime=target_mime,
            runner=runner,
        )
        if gen_meta is None:
            attempt_history.append({"attempt": attempt, "generation_error": gen_err})
            active_prev_id = initial_interaction_id
            active_prompt = base_prompt
            continue

        candidate_path = Path(gen_meta["path"])
        if last_candidate_path and last_candidate_path != candidate_path and last_candidate_path.is_file():
            last_candidate_path.unlink()
        last_candidate_path = candidate_path
        last_gen_meta = gen_meta

        mech = verify_image_mechanical(
            candidate_path,
            target_ar=spec["aspect_ratio"],
            target_size=spec["image_size"],
        )
        last_mechanical = mech

        if not mech["passed"]:
            attempt_history.append(
                {
                    "attempt": attempt,
                    "model": gen_meta["model"],
                    "response_id": gen_meta.get("response_id"),
                    "mechanical": mech,
                    "remediation_mode": "regenerate",
                }
            )
            if attempt < max_attempts:
                active_prev_id = initial_interaction_id
                active_prompt = (
                    f"{base_prompt} Corrective requirement: strictly output {spec['aspect_ratio']} "
                    f"aspect ratio at {spec['image_size']} resolution ({'; '.join(mech['errors'])})."
                )
            continue

        if no_verify:
            final_path, requested_out = _finalize_verified_image(
                candidate_path, output_path, mech.get("mime_type")
            )
            provenance = {
                "schema_version": 1,
                "status": "MECHANICALLY_VERIFIED_ONLY",
                "output": str(final_path),
                "model": gen_meta["model"],
                "verifier_model": None,
                "response_id": gen_meta.get("response_id"),
                "attempts_used": attempt,
                "spec_sha256": initial_digest,
                "mechanical": mech,
                "rubric": None,
                "unchecked_surfaces": [
                    "stage4_multimodal_rubric_judge (--no-verify)",
                    "full_pixel_scanline_decode",
                ],
            }
            if requested_out:
                provenance["requested_output"] = requested_out
            Path(f"{final_path}.provenance.json").write_text(
                json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
            )
            stale_final_rep = Path(f"{final_path}.report.json")
            if stale_final_rep.is_file():
                stale_final_rep.unlink()
            return 0, provenance

        rubric_eval, used_verifier, judge_err = _run_blinded_judge_with_fallback(
            spec=spec,
            verifier_chain=verifier_chain,
            candidate_path=candidate_path,
            reference_uris=resolved_refs,
            runner=runner,
        )
        if rubric_eval is None:
            attempt_history.append(
                {
                    "attempt": attempt,
                    "model": gen_meta["model"],
                    "mechanical": mech,
                    "judge_error": judge_err,
                }
            )
            active_prev_id = initial_interaction_id
            active_prompt = base_prompt
            continue

        last_rubric = rubric_eval
        if rubric_eval["passed"]:
            final_path, requested_out = _finalize_verified_image(
                candidate_path, output_path, mech.get("mime_type")
            )
            provenance = {
                "schema_version": 1,
                "status": "VERIFIED",
                "output": str(final_path),
                "model": gen_meta["model"],
                "verifier_model": used_verifier,
                "response_id": gen_meta.get("response_id"),
                "attempts_used": attempt,
                "spec_sha256": initial_digest,
                "mechanical": mech,
                "rubric": rubric_eval,
                "unchecked_surfaces": ["full_pixel_scanline_decode"],
            }
            if requested_out:
                provenance["requested_output"] = requested_out
            Path(f"{final_path}.provenance.json").write_text(
                json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
            )
            stale_final_rep = Path(f"{final_path}.report.json")
            if stale_final_rep.is_file():
                stale_final_rep.unlink()
            return 0, provenance

        remediation = select_remediation_mode(
            mechanical_passed=True,
            rubric_validation=rubric_eval,
            response_id=gen_meta.get("response_id"),
        )
        attempt_history.append(
            {
                "attempt": attempt,
                "model": gen_meta["model"],
                "verifier_model": used_verifier,
                "response_id": gen_meta.get("response_id"),
                "mechanical": mech,
                "rubric": rubric_eval,
                "remediation_mode": remediation,
            }
        )
        if attempt < max_attempts:
            fixes = " ".join(rubric_eval["fix_instructions"])
            if remediation == "edit_turn":
                active_prev_id = str(gen_meta["response_id"])
                delta = rubric_eval.get("edit_delta_prompt") or f"Keep everything else the same. {fixes}"
                if "keep everything else" not in delta.lower():
                    delta = f"Keep everything else the same. {delta}"
                active_prompt = delta
            else:
                active_prev_id = initial_interaction_id
                regen_text = rubric_eval.get("regenerated_prompt")
                if regen_text and validate_expanded_prompt(
                    spec["raw_prompt"], regen_text, spec["explicit_constraints"]["quoted_literals"]
                )[0]:
                    active_prompt = f"{regen_text} Mandatory corrections: {fixes}"
                else:
                    active_prompt = f"{base_prompt} Mandatory corrections: {fixes}"

    # Retries exhausted
    if allow_unverified and last_candidate_path and last_candidate_path.is_file():
        actual_mime = last_mechanical.get("mime_type") if isinstance(last_mechanical, dict) else None
        final_path, requested_out = _finalize_verified_image(
            last_candidate_path, output_path, actual_mime
        )
        print(
            f"[image-gen] WARNING: UNVERIFIED_OVERRIDE after {max_attempts} attempt(s) without passing "
            f"verification; writing unverified output to {final_path} "
            f"(--override-reason: {clean_override_reason}).",
            file=sys.stderr,
        )
        override_prov = {
            "schema_version": 1,
            "status": "UNVERIFIED_OVERRIDE",
            "override_reason": clean_override_reason,
            "output": str(final_path),
            "model": last_gen_meta["model"] if last_gen_meta else None,
            "response_id": last_gen_meta.get("response_id") if last_gen_meta else None,
            "attempts_used": max_attempts,
            "spec_sha256": initial_digest,
            "last_mechanical": last_mechanical,
            "last_rubric": last_rubric,
            "history": attempt_history,
        }
        if requested_out:
            override_prov["requested_output"] = requested_out
        Path(f"{final_path}.provenance.json").write_text(
            json.dumps(override_prov, indent=2) + "\n", encoding="utf-8"
        )
        override_report = {
            "schema_version": 1,
            "status": "UNVERIFIED_OVERRIDE",
            "override_reason": clean_override_reason,
            "intended_output": str(output_path),
            "output": str(final_path),
            "attempts_used": max_attempts,
            "spec_sha256": initial_digest,
            "last_mechanical": last_mechanical,
            "last_rubric": last_rubric,
            "history": attempt_history,
        }
        if requested_out:
            override_report["requested_output"] = requested_out
        Path(f"{final_path}.report.json").write_text(
            json.dumps(override_report, indent=2) + "\n", encoding="utf-8"
        )
        return 0, override_prov

    # Hard failure contract (S3): never leave an unverified file or stale provenance at --output
    if output_path.is_file():
        output_path.unlink()
    stale_prov = Path(f"{output_path}.provenance.json")
    if stale_prov.is_file():
        stale_prov.unlink()
    rejected_path: Path | None = None
    if last_candidate_path and last_candidate_path.is_file():
        ext = last_candidate_path.suffix or output_path.suffix or ".png"
        rejected_path = output_path.parent / f"{output_path.stem}.rejected{ext}"
        shutil.move(str(last_candidate_path), str(rejected_path))

    report = {
        "schema_version": 1,
        "status": "REJECTED",
        "intended_output": str(output_path),
        "rejected_artifact": str(rejected_path) if rejected_path else None,
        "attempts_used": max_attempts,
        "spec_sha256": initial_digest,
        "last_mechanical": last_mechanical,
        "last_rubric": last_rubric,
        "history": attempt_history,
    }
    report_path = Path(f"{output_path}.report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"[image-gen] ERROR: Verification failed after {max_attempts} attempt(s). "
        f"Diagnostic report written to {report_path}.",
        file=sys.stderr,
    )
    return 1, report


def _load_and_validate_manifest(
    manifest_path: Path,
    cli_mode: str,
    cli_ar: str,
    cli_size: str,
) -> tuple[dict[str, Any], str, str, str, str | None]:
    """Load and deterministically validate an image sequence manifest (P1 #2, P2 #14)."""
    if not manifest_path.is_file():
        raise ConfigError(f"Manifest file not found: {manifest_path}")
    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"Invalid JSON in manifest {manifest_path}: {exc}") from exc

    if not isinstance(manifest_data, dict) or not isinstance(manifest_data.get("frames"), list):
        raise ConfigError("Manifest JSON must be an object containing a non-empty 'frames' list.")
    frames_in = manifest_data["frames"]
    if not frames_in:
        raise ConfigError("Manifest 'frames' list must contain at least one frame.")

    raw_mode = manifest_data.get("mode")
    if raw_mode is not None:
        if not isinstance(raw_mode, str) or raw_mode not in SUPPORTED_MODES:
            raise ConfigError(
                f"Manifest 'mode' must be one of {SUPPORTED_MODES}; got {raw_mode!r}."
            )
    seq_mode = str(raw_mode or (cli_mode if cli_mode != "auto" else "timeline"))
    if seq_mode not in ("comic-panels", "timeline"):
        seq_mode = "timeline"

    raw_ar = manifest_data.get("aspect_ratio")
    if raw_ar is not None and (not isinstance(raw_ar, str) or raw_ar not in SUPPORTED_ASPECT_RATIOS):
        raise ConfigError(f"Manifest 'aspect_ratio' invalid: {raw_ar!r}.")
    seq_ar = str(raw_ar or cli_ar)

    raw_size = manifest_data.get("size")
    if raw_size is not None and (not isinstance(raw_size, str) or raw_size not in SUPPORTED_SIZES):
        raise ConfigError(f"Manifest 'size' invalid: {raw_size!r}.")
    seq_size = str(raw_size or cli_size)

    for idx, frame_entry in enumerate(frames_in, start=1):
        if not isinstance(frame_entry, dict) or not isinstance(frame_entry.get("prompt"), str) or not frame_entry["prompt"].strip():
            raise ConfigError(f"Frame {idx} in manifest is missing a non-empty string 'prompt'.")
        dur_key = "duration_s" if "duration_s" in frame_entry else ("duration_hint_s" if "duration_hint_s" in frame_entry else None)
        if dur_key is not None:
            dur_val = frame_entry[dur_key]
            if isinstance(dur_val, bool) or not isinstance(dur_val, int) or dur_val < 1:
                raise ConfigError(f"Frame {idx} '{dur_key}' must be an integer >= 1; got {dur_val!r}.")

    anchor_ref: str | None = None
    if "anchor_image" in manifest_data and manifest_data["anchor_image"] is not None:
        anchor_cfg = manifest_data["anchor_image"]
        if not isinstance(anchor_cfg, str) or not anchor_cfg.strip():
            raise ConfigError("Manifest 'anchor_image' must be a non-empty path or files/ URI.")
        anchor_str = anchor_cfg.strip()
        if _FILES_URI_RE.fullmatch(anchor_str) and not (manifest_path.parent / anchor_str).exists():
            anchor_ref = anchor_str
        else:
            raw_anchor = Path(anchor_str)
            candidate_anchor = raw_anchor if raw_anchor.is_absolute() else (manifest_path.parent / raw_anchor)
            anchor_ref = validate_image_reference_asset(
                str(candidate_anchor),
                allowed_root=manifest_path.parent,
                label="Manifest anchor_image",
            )

    return manifest_data, seq_mode, seq_ar, seq_size, anchor_ref


def execute_manifest_sequence(
    *,
    manifest_path: Path,
    output_arg: str,
    manifest_out_arg: str | None,
    cli_mode: str,
    cli_style: str | None,
    cli_ar: str,
    cli_size: str,
    cli_refs: Sequence[dict[str, str]],
    explicit_model: str | None,
    verifier_chain: Sequence[str],
    runner: Callable[..., Any],
    max_attempts: int,
    raw_prompt: bool,
    no_verify: bool,
    allow_unverified: bool,
    override_reason: str | None = None,
) -> int:
    """Execute sequential `comic-panels` or `timeline` frames and write keyframes_manifest.json."""
    clean_override_reason = redact_secrets((override_reason or "").strip())
    if allow_unverified and not clean_override_reason:
        raise ConfigError(
            '--allow-unverified requires a non-empty --override-reason "<why>" '
            "(ENGINEERING_STANDARD §9 loud-override rule)."
        )
    for ref_item in cli_refs:
        validate_image_reference_asset(ref_item["path"], label="Reference image")

    manifest_data, seq_mode, seq_ar, seq_size, anchor_ref = _load_and_validate_manifest(
        manifest_path, cli_mode, cli_ar, cli_size
    )
    frames_in = manifest_data["frames"]
    seq_style_val = cli_style if cli_style is not None else manifest_data.get("style")
    if seq_style_val is not None and not isinstance(seq_style_val, str):
        raise ConfigError("Manifest 'style' must be a string.")
    seq_style = seq_style_val

    out_target = Path(output_arg)
    base_dir = out_target.parent if out_target.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else out_target
    frames_dir = base_dir / "frames"
    manifest_out = Path(manifest_out_arg) if manifest_out_arg else (base_dir / "keyframes_manifest.json")

    manifest_root = manifest_out.parent.resolve()
    frames_root = frames_dir.resolve()
    if not frames_root.is_relative_to(manifest_root):
        raise ConfigError(
            f"--manifest-out directory '{manifest_root}' must contain frames directory '{frames_root}' "
            "so emitted manifest paths never contain '../' traversal."
        )

    frames_dir.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    asset_cache = AssetCache(runner)
    anchor_source_resolved: Path | None = None
    if anchor_ref is None and cli_refs:
        anchor_ref = validate_image_reference_asset(cli_refs[0]["path"], label="Reference image")

    if anchor_ref is not None and not _FILES_URI_RE.fullmatch(anchor_ref):
        anchor_resolved = Path(anchor_ref).resolve()
        anchor_source_resolved = anchor_resolved
        if not anchor_resolved.is_relative_to(manifest_root):
            staged_anchor = frames_dir / f"anchor{anchor_resolved.suffix or '.png'}"
            if staged_anchor.resolve() != anchor_resolved:
                shutil.copy2(str(anchor_resolved), str(staged_anchor))
            anchor_ref = str(staged_anchor.resolve())

    if anchor_ref is None:
        anchor_prompt = str(
            manifest_data.get("anchor_prompt")
            or f"Canonical character and environment anchor reference for: {frames_in[0]['prompt']}"
        )
        anchor_out = frames_dir / "anchor.png"
        anchor_spec = compile_spec(
            prompt=anchor_prompt,
            mode="single",
            style=seq_style,
            aspect_ratio=seq_ar,
            image_size=seq_size,
            references=cli_refs,
        )
        anchor_chain = build_image_model_chain(
            explicit_model,
            mode="single",
            has_references=bool(cli_refs),
            has_quoted_text=bool(anchor_spec["explicit_constraints"]["quoted_literals"]),
            multi_panel=True,
        )
        rc_anchor, anchor_prov = execute_single_asset(
            frozen_spec=anchor_spec,
            output_path=anchor_out,
            model_chain=anchor_chain,
            verifier_chain=verifier_chain,
            asset_cache=asset_cache,
            runner=runner,
            max_attempts=max_attempts,
            raw_prompt=raw_prompt,
            no_verify=no_verify,
            allow_unverified=allow_unverified,
            override_reason=clean_override_reason or None,
            reused_refs=True,
        )
        if rc_anchor != 0:
            return rc_anchor
        anchor_ref = str(anchor_prov["output"])

    written_frames: list[dict[str, Any]] = []
    prev_frame_path: Path | None = None
    total_frames = len(frames_in)

    for idx, frame_entry in enumerate(frames_in, start=1):
        frame_prompt = frame_entry["prompt"].strip()
        caption = str(frame_entry.get("caption", f"Step {idx}"))
        duration_s = int(frame_entry.get("duration_s", frame_entry.get("duration_hint_s", 5)))

        frame_refs: list[dict[str, str]] = [{"role": "anchor", "path": anchor_ref}]
        if prev_frame_path is not None and str(prev_frame_path) != anchor_ref:
            frame_refs.append({"role": "ref", "path": str(prev_frame_path)})
        for extra in cli_refs:
            raw_extra = extra["path"].strip()
            if _FILES_URI_RE.fullmatch(raw_extra):
                if raw_extra == anchor_ref:
                    continue
            else:
                extra_resolved = Path(raw_extra).resolve()
                if (
                    str(extra_resolved) == anchor_ref
                    or (anchor_source_resolved is not None and extra_resolved == anchor_source_resolved)
                ):
                    continue
            if len(frame_refs) < MAX_REFERENCE_IMAGES:
                frame_refs.append(extra)

        frame_out = frames_dir / f"frame_{idx:02d}.png"
        frame_spec = compile_spec(
            prompt=frame_prompt,
            mode=seq_mode,
            style=seq_style,
            aspect_ratio=seq_ar,
            image_size=seq_size,
            references=frame_refs,
            panel_index=idx,
            total_panels=total_frames,
        )
        frame_chain = build_image_model_chain(
            explicit_model,
            mode=seq_mode,
            has_references=True,
            has_quoted_text=bool(frame_spec["explicit_constraints"]["quoted_literals"]),
            multi_panel=True,
        )
        rc_frame, prov = execute_single_asset(
            frozen_spec=frame_spec,
            output_path=frame_out,
            model_chain=frame_chain,
            verifier_chain=verifier_chain,
            asset_cache=asset_cache,
            runner=runner,
            max_attempts=max_attempts,
            raw_prompt=raw_prompt,
            no_verify=no_verify,
            allow_unverified=allow_unverified,
            override_reason=clean_override_reason or None,
            reused_refs=True,
        )
        if rc_frame != 0:
            return rc_frame
        actual_frame_out = Path(prov["output"])
        prev_frame_path = actual_frame_out
        try:
            manifest_frame_path = os.path.relpath(
                actual_frame_out.resolve(), manifest_out.parent.resolve()
            ).replace(os.sep, "/")
        except ValueError:
            manifest_frame_path = str(actual_frame_out.resolve())
        written_frames.append(
            {
                "index": idx,
                "path": manifest_frame_path,
                "response_id": prov.get("response_id") or "",
                "prompt": frame_prompt,
                "caption": caption,
                "duration_s": duration_s,
            }
        )

    if _FILES_URI_RE.fullmatch(anchor_ref):
        manifest_anchor_path = anchor_ref
    else:
        try:
            manifest_anchor_path = os.path.relpath(
                Path(anchor_ref).resolve(), manifest_out.parent.resolve()
            ).replace(os.sep, "/")
        except ValueError:
            manifest_anchor_path = str(Path(anchor_ref).resolve())

    out_manifest_payload = {
        "schema_version": 1,
        "mode": seq_mode,
        "style": seq_style or "",
        "aspect_ratio": seq_ar,
        "anchor_image": manifest_anchor_path,
        "frames": written_frames,
    }
    manifest_out.write_text(json.dumps(out_manifest_payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "VERIFIED_SEQUENCE", "manifest": str(manifest_out), "frame_count": len(written_frames)}))
    return 0


# ---------------------------------------------------------------------------
# Standalone Preflight Diagnostics (`--doctor`) & CLI Entrypoint
# ---------------------------------------------------------------------------


def _redact_json_strings(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_json_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_json_strings(item) for item in value]
    return value


def run_doctor(
    *,
    runner: Callable[..., Any] = default_runner,
    env: Mapping[str, str] | None = None,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    """Inspect `gemini-api` binary availability, version, auth status, and env shadowing."""
    active_env = dict(os.environ if env is None else env)
    binary_path = which_fn("gemini-api")
    env_key_set = bool(active_env.get("GEMINI_API_KEY", "").strip())

    if not binary_path:
        return {
            "ready": False,
            "binary_path": None,
            "version": None,
            "whoami": None,
            "env_api_key_set": env_key_set,
            "env_api_key_shadow_warning": False,
            "install_hint": (
                "Install `gemini-api` via `bash scripts/install.sh --with-media-tools` "
                "or follow https://aistudio.google.com/docs/cli"
            ),
        }

    ver_proc = runner(["gemini-api", "--version"], timeout=15)
    version_str = redact_secrets(ver_proc.stdout.strip()) if ver_proc.returncode == 0 else None

    who_proc = runner(["gemini-api", "whoami", "-o", "json"], timeout=15)
    whoami_data: dict[str, Any] | None = None
    if who_proc.returncode == 0 and who_proc.stdout.strip():
        try:
            parsed_who = json.loads(who_proc.stdout)
            if isinstance(parsed_who, dict):
                whoami_data = _redact_json_strings(parsed_who)
        except ValueError:
            whoami_data = {"raw": redact_secrets(who_proc.stdout.strip())}

    shadow_warning = env_key_set
    warnings: list[str] = []
    if shadow_warning:
        warnings.append(
            "GEMINI_API_KEY is set in the environment and may shadow OS keyring credentials "
            "stored by `gemini-api auth login` (see https://aistudio.google.com/docs/cli)."
        )

    return {
        "ready": ver_proc.returncode == 0,
        "binary_path": binary_path,
        "version": version_str,
        "whoami": whoami_data,
        "env_api_key_set": env_key_set,
        "env_api_key_shadow_warning": shadow_warning,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image_gen.py",
        description=(
            "Generate and verify diagrams, illustrations, comic grids, and sequential frames "
            "via the official `gemini-api` CLI (https://aistudio.google.com/docs/cli)."
        ),
    )
    parser.add_argument("--prompt", type=str, help="Image generation prompt.")
    parser.add_argument("--spec-file", type=str, help="Load a pre-compiled VisualRequirementSpec JSON file.")
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=list(SUPPORTED_MODES),
        help="Generation craft mode (default: auto).",
    )
    parser.add_argument("--style", type=str, help="Art-direction style string.")
    parser.add_argument(
        "-r",
        "--reference",
        "--references",
        dest="references",
        action="append",
        default=[],
        help="Reference image path or role:path (repeatable or comma-separated, max 14).",
    )
    parser.add_argument(
        "--ar",
        type=str,
        default="1:1",
        choices=list(SUPPORTED_ASPECT_RATIOS),
        help="Target aspect ratio (default: 1:1).",
    )
    parser.add_argument(
        "--size",
        type=str,
        default="1K",
        choices=list(SUPPORTED_SIZES),
        help="Target resolution tier (default: 1K; auto-upgraded to 2K for comic-grid or dense text).",
    )
    parser.add_argument("-o", "--output", type=str, default="output.png", help="Output file or directory path.")
    parser.add_argument("--manifest", type=str, help="Input JSON sequence spec for comic-panels or timeline.")
    parser.add_argument("--manifest-out", type=str, help="Output path for keyframes_manifest.json.")
    parser.add_argument("--previous-interaction-id", type=str, help="Prior gemini-api response_id for multi-turn edits.")
    parser.add_argument("--model", type=str, default=None, help=f"Override primary image model (default: {PRIMARY_IMAGE_MODEL}).")
    parser.add_argument(
        "--verifier-model",
        type=str,
        default=None,
        help=f"Override primary blinded verifier model (default: {DEFAULT_VERIFIER_MODEL}).",
    )
    parser.add_argument("--max-attempts", type=int, default=3, help="Max closed-loop generation attempts (default: 3).")
    parser.add_argument("--raw-prompt", action="store_true", help="Skip LLM prompt expansion and use deterministic compiled prompt.")
    parser.add_argument("--expand-prompt", action="store_true", help="Explicitly enable Argon prompt expansion (default when live).")
    parser.add_argument("--no-verify", action="store_true", help="Skip Stage 4 multimodal rubric judge (Stage 3 mechanical gate still runs).")
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Permit writing an unverified candidate on retry exhaustion with UNVERIFIED_OVERRIDE provenance (requires --override-reason).",
    )
    parser.add_argument(
        "--override-reason",
        type=str,
        default=None,
        help="Mandatory non-empty justification recorded in .report.json and provenance when --allow-unverified is used.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate spec and print planned gemini-api command JSON without network calls.")
    parser.add_argument("--doctor", action="store_true", help="Check gemini-api binary, version, and auth keyring status.")
    parser.add_argument("--verify-only", type=str, help="Run offline mechanical (+ optional --rubric-file) verification on an existing image.")
    parser.add_argument("--rubric-file", type=str, help="Rubric JSON file to validate alongside --verify-only and --spec-file.")
    return parser


def _validate_spec_dict(loaded: Any) -> dict[str, Any]:
    """Validate `--spec-file` schema and mandatory AC invariant (P1 #6, P2 #14)."""
    if not isinstance(loaded, dict):
        raise ConfigError("--spec-file must contain a JSON object.")
    spec = copy.deepcopy(loaded)

    has_raw = "raw_prompt" in spec
    has_compiled = "compiled_prompt" in spec
    if has_raw and (not isinstance(spec["raw_prompt"], str) or not spec["raw_prompt"].strip()):
        raise ConfigError("--spec-file 'raw_prompt' must be a non-empty string.")
    if has_compiled and (not isinstance(spec["compiled_prompt"], str) or not spec["compiled_prompt"].strip()):
        raise ConfigError("--spec-file 'compiled_prompt' must be a non-empty string.")
    if not has_raw and not has_compiled:
        raise ConfigError("--spec-file must contain 'raw_prompt' and/or 'compiled_prompt'.")
    if not has_raw:
        spec["raw_prompt"] = spec["compiled_prompt"]
    if not has_compiled:
        spec["compiled_prompt"] = spec["raw_prompt"]

    mode_val = spec.get("mode", "single")
    if not isinstance(mode_val, str) or mode_val not in SUPPORTED_MODES:
        raise ConfigError(f"--spec-file 'mode' invalid: {mode_val!r}.")
    spec["mode"] = mode_val

    ar_val = spec.get("aspect_ratio")
    if not isinstance(ar_val, str) or ar_val not in SUPPORTED_ASPECT_RATIOS:
        raise ConfigError(f"--spec-file 'aspect_ratio' invalid or missing: {ar_val!r}.")

    size_val = spec.get("image_size")
    if not isinstance(size_val, str) or size_val not in SUPPORTED_SIZES:
        raise ConfigError(f"--spec-file 'image_size' invalid or missing: {size_val!r}.")

    acs = spec.get("acceptance_criteria")
    if not isinstance(acs, list) or not acs:
        raise ConfigError("--spec-file must contain a non-empty 'acceptance_criteria' list.")
    mandatory_count = 0
    for idx, ac in enumerate(acs, start=1):
        if not isinstance(ac, dict):
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] must be an object.")
        if not isinstance(ac.get("id"), str) or not ac["id"].strip():
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] missing non-empty 'id'.")
        if not isinstance(ac.get("category"), str) or not ac["category"].strip():
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] missing non-empty 'category'.")
        if not isinstance(ac.get("requirement"), str) or not ac["requirement"].strip():
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] missing non-empty 'requirement'.")
        if "mandatory" in ac and not isinstance(ac["mandatory"], bool):
            raise ConfigError(f"--spec-file acceptance_criteria[{idx}] 'mandatory' must be boolean.")
        if ac.get("mandatory", True):
            mandatory_count += 1
    if mandatory_count == 0:
        raise ConfigError("--spec-file defines zero mandatory acceptance criteria (S9).")

    implicit = spec.get("implicit_constraints")
    if implicit is not None and (not isinstance(implicit, list) or not all(isinstance(x, str) for x in implicit)):
        raise ConfigError("--spec-file 'implicit_constraints' must be a list of strings.")

    explicit = spec.get("explicit_constraints")
    if explicit is None:
        explicit = {}
    elif not isinstance(explicit, dict):
        raise ConfigError("--spec-file 'explicit_constraints' must be an object.")
    quoted = explicit.get("quoted_literals")
    if quoted is None:
        explicit["quoted_literals"] = extract_quoted_literals(spec["raw_prompt"])
    elif not isinstance(quoted, list) or not all(isinstance(q, str) for q in quoted):
        raise ConfigError("--spec-file 'explicit_constraints.quoted_literals' must be a list of strings.")
    refs = explicit.get("references")
    if refs is None:
        explicit["references"] = []
    elif not isinstance(refs, list):
        raise ConfigError("--spec-file 'explicit_constraints.references' must be a list.")
    else:
        for idx, ref in enumerate(refs, start=1):
            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref["path"].strip():
                raise ConfigError(
                    f"--spec-file 'explicit_constraints.references[{idx}]' must be an object with non-empty 'path'."
                )
            if "role" in ref and (not isinstance(ref["role"], str) or not ref["role"].strip()):
                raise ConfigError(
                    f"--spec-file 'explicit_constraints.references[{idx}].role' must be a non-empty string."
                )
    spec["explicit_constraints"] = explicit
    return spec


def _load_or_compile_spec(args: argparse.Namespace, parsed_refs: Sequence[dict[str, str]]) -> dict[str, Any]:
    if args.spec_file:
        spec_path = Path(args.spec_file)
        if not spec_path.is_file():
            raise ConfigError(f"Spec file not found: {spec_path}")
        try:
            loaded = json.loads(spec_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ConfigError(f"Invalid JSON in --spec-file {spec_path}: {exc}") from exc
        return _validate_spec_dict(loaded)
    if not args.prompt:
        raise ConfigError("One of --prompt, --spec-file, --manifest, --verify-only, or --doctor is required.")
    return compile_spec(
        prompt=args.prompt,
        mode=args.mode,
        style=args.style,
        aspect_ratio=args.ar,
        image_size=args.size,
        references=parsed_refs,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    active_runner = runner or default_runner
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.doctor:
        doc = run_doctor(runner=active_runner, env=env)
        for warning in doc.get("warnings", []):
            print(f"[image-gen] WARNING: {warning}", file=sys.stderr)
        print(json.dumps(doc, indent=2))
        return 0 if doc["ready"] else 1

    try:
        if args.max_attempts < 1:
            raise ConfigError("--max-attempts must be >= 1.")
        override_reason = redact_secrets((args.override_reason or "").strip())
        if args.allow_unverified and not override_reason:
            raise ConfigError(
                '--allow-unverified requires a non-empty --override-reason "<why>" '
                "(ENGINEERING_STANDARD §9 loud-override rule)."
            )
        verifier_chain = build_verifier_model_chain(args.verifier_model)
        if args.model:
            validate_model_id(args.model, role="image")
        parsed_refs = parse_reference_arg(args.references)

        if args.verify_only:
            candidate = Path(args.verify_only)
            spec_for_verify = (
                _load_or_compile_spec(args, parsed_refs)
                if (args.spec_file or args.prompt)
                else {
                    "aspect_ratio": args.ar,
                    "image_size": args.size,
                    "acceptance_criteria": [],
                }
            )
            rubric_data: dict[str, Any] | None = None
            if args.rubric_file:
                rubric_path = Path(args.rubric_file)
                if not rubric_path.is_file():
                    raise ConfigError(f"Rubric file not found: {rubric_path}")
                try:
                    parsed_rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    raise ConfigError(f"Invalid JSON in --rubric-file {rubric_path}: {exc}") from exc
                if not isinstance(parsed_rubric, dict):
                    raise ConfigError("--rubric-file must contain a JSON object.")
                rubric_data = parsed_rubric

            mech = verify_image_mechanical(
                candidate,
                target_ar=str(spec_for_verify.get("aspect_ratio", args.ar)),
                target_size=str(spec_for_verify.get("image_size", args.size)),
            )
            if candidate.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and mech.get("mime_type"):
                expected_mime = target_mime_for_output(candidate)
                if mech["mime_type"] != expected_mime:
                    mech["passed"] = False
                    mech["errors"].append(
                        f"Extension mismatch: '{candidate.name}' expects '{expected_mime}' "
                        f"but binary header is '{mech['mime_type']}'."
                    )
            rubric_report = None
            passed = mech["passed"]
            if rubric_data is not None:
                rubric_report = validate_rubric_verdict(rubric_data, spec_for_verify)
                passed = passed and rubric_report["passed"]
            print(json.dumps({"passed": passed, "mechanical": mech, "rubric": rubric_report}, indent=2))
            return 0 if passed else 1

        if args.manifest and not args.dry_run:
            return execute_manifest_sequence(
                manifest_path=Path(args.manifest),
                output_arg=args.output,
                manifest_out_arg=args.manifest_out,
                cli_mode=args.mode,
                cli_style=args.style,
                cli_ar=args.ar,
                cli_size=args.size,
                cli_refs=parsed_refs,
                explicit_model=args.model,
                verifier_chain=verifier_chain,
                runner=active_runner,
                max_attempts=args.max_attempts,
                raw_prompt=bool(args.raw_prompt and not args.expand_prompt),
                no_verify=args.no_verify,
                allow_unverified=args.allow_unverified,
                override_reason=override_reason or None,
            )

        if args.manifest and args.dry_run:
            manifest_data, seq_mode, seq_ar, seq_size, _anchor_ref = _load_and_validate_manifest(
                Path(args.manifest), args.mode, args.ar, args.size
            )
            first_prompt = manifest_data["frames"][0]["prompt"].strip()
            spec = compile_spec(
                prompt=first_prompt,
                mode=seq_mode,
                style=args.style or manifest_data.get("style"),
                aspect_ratio=seq_ar,
                image_size=seq_size,
                references=parsed_refs,
                panel_index=1,
                total_panels=len(manifest_data["frames"]),
            )
        else:
            spec = _load_or_compile_spec(args, parsed_refs)

        model_chain = build_image_model_chain(
            args.model,
            mode=spec["mode"],
            has_references=bool(spec["explicit_constraints"]["references"]),
            has_quoted_text=bool(spec["explicit_constraints"]["quoted_literals"]),
            multi_panel=spec["mode"] in ("comic-grid", "comic-panels", "timeline"),
        )
    except ConfigError as exc:
        print(f"[image-gen] configuration error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"[image-gen] ERROR: {redact_secrets(str(exc))}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    if args.dry_run:
        planned_cmd = build_image_cli_command(
            prompt=spec["compiled_prompt"],
            model=model_chain[0],
            aspect_ratio=spec["aspect_ratio"],
            image_size=spec["image_size"],
            out_path=out_path,
            references=[r["path"] for r in spec["explicit_constraints"]["references"]],
            previous_interaction_id=args.previous_interaction_id,
            mode=spec["mode"],
            has_quoted_text=bool(spec["explicit_constraints"]["quoted_literals"]),
            target_mime=target_mime_for_output(out_path),
        )
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "spec": spec,
                    "spec_sha256": compute_spec_digest(spec),
                    "model_chain": model_chain,
                    "verifier_chain": verifier_chain,
                    "planned_command": planned_cmd,
                    "unchecked_surfaces": [
                        "live_gemini_api_execution (--dry-run)",
                        "stage3_mechanical_binary_verification (--dry-run)",
                        "stage4_multimodal_rubric_judge (--dry-run)",
                    ],
                },
                indent=2,
            )
        )
        return 0

    asset_cache = AssetCache(active_runner)
    try:
        rc, result_payload = execute_single_asset(
            frozen_spec=spec,
            output_path=out_path,
            model_chain=model_chain,
            verifier_chain=verifier_chain,
            asset_cache=asset_cache,
            runner=active_runner,
            max_attempts=args.max_attempts,
            raw_prompt=bool(args.raw_prompt and not args.expand_prompt),
            no_verify=args.no_verify,
            allow_unverified=args.allow_unverified,
            override_reason=override_reason or None,
            initial_interaction_id=args.previous_interaction_id,
        )
    except ConfigError as exc:
        print(f"[image-gen] configuration error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"[image-gen] ERROR: {redact_secrets(str(exc))}", file=sys.stderr)
        return 1

    if rc == 0:
        print(
            json.dumps(
                {
                    "status": result_payload["status"],
                    "output": str(result_payload.get("output", out_path)),
                    "model": result_payload.get("model"),
                    "response_id": result_payload.get("response_id"),
                    "attempts_used": result_payload.get("attempts_used"),
                }
            )
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
