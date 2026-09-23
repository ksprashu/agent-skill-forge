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

"""
profile_tool.py - The communication-profile contract.

This module is the single source of truth for what a profile is. The JSON
Schema in references/profile.schema.json is *generated* from the constants
here, so the two can never drift.

The load-bearing invariant is the evidence rule:

    A claim with source "observed" must cite at least one quote ID that
    resolves against a harvested evidence file. A claim with source
    "declared" must cite what the user actually said or chose. Only
    "inferred" claims may stand on reasoning alone, and those are counted,
    surfaced, and stamped into every rendered config.

That rule is what stops this tool from inventing a personality for someone
and presenting it back to them as measurement.

CLI:
    profile_tool.py init      -o profile.json [--subject NAME]
    profile_tool.py validate  profile.json [-e evidence.json] [--strict]
    profile_tool.py amend     profile.json --directive TEXT --scope SCOPE
                         --source SOURCE [--evidence ITEM ...]
    profile_tool.py schema    [-o references/profile.schema.json] [--check]
"""

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":  # pragma: no cover - platform guard
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Dimensions
#
# Six axes, each of which must change at least one block of rendered output.
# If an axis cannot change what the agent does, it does not belong here.
# ---------------------------------------------------------------------------

DIMENSIONS = {
    "visual_scaffolding": {
        "question": "Should structure (diagrams, tables) carry the explanation, or prose?",
        "low": "Prose and code. Diagrams are noise.",
        "high": "Tables and diagrams first; prose supports them.",
        "drives": "visual",
    },
    "text_density": {
        "question": "How much unbroken prose can land before attention drops?",
        "low": "Comfortable with long-form prose.",
        "high": "Long paragraphs are not read. Chunk aggressively.",
        "drives": "formatting",
    },
    "orientation_need": {
        "question": "Is framing needed before detail, or is it throat-clearing?",
        "low": "Start at the payload. Framing wastes a screen.",
        "high": "State context and the problem before any detail.",
        "drives": "formatting",
    },
    "metaphor_affinity": {
        "question": "Do physical analogies help, or patronise?",
        "low": "No analogies. Use precise names for real things.",
        "high": "Ground abstractions in tangible, physical comparisons.",
        "drives": "tone",
    },
    "decision_directness": {
        "question": "One recommendation, or the option space?",
        "low": "Lay out options with trade-offs; the call is mine.",
        "high": "Make the call, then justify it. No committee buffet.",
        "drives": "analysis",
    },
    "evidence_depth": {
        "question": "Headline answer, or the full cost and failure model?",
        "low": "Headline plus the reasoning. Skip exhaustive modelling.",
        "high": "Full totals, second-order effects, and failure modes.",
        "drives": "analysis",
    },
}

BANDS = ("low", "medium", "high", "unknown")
SOURCES = ("observed", "declared", "inferred")
SCOPES = (
    "always",
    "architecture",
    "debugging",
    "learning",
    "review",
    "cost",
    "writing",
)

# Numeric knobs. None means "not established" -- the renderer omits the line
# entirely rather than inventing a threshold.
LIMITS = {
    "response_ceiling_words": (50, 5000),
    "sentences_per_bullet": (1, 10),
    "bullets_per_section": (2, 20),
    "code_fold_threshold": (3, 200),
}

TONE_CONTEXTS = ("default",) + tuple(s for s in SCOPES if s != "always")

# Top-level keys validate() refuses to do without. build_schema() reads the same
# tuple, so the advertised schema and the CLI cannot disagree about what a
# profile must contain. They did: `forbidden` was absent here and required
# there, so a profile that passed the published schema was rejected on load.
# test_schema_required_matches_validator deletes each of these in turn and
# fails if the validator stays quiet.
REQUIRED_TOP_LEVEL = ("schema_version", "subject", "dimensions", "rules",
                      "forbidden", "limits", "tone", "unknowns")

QUOTE_ID_RE = re.compile(r"^q\d+$")

# ---------------------------------------------------------------------------
# Sensitive data — one table, two consumers
#
# harvest.py redacts these out of evidence; this module rejects a profile that
# still contains one. Those two lists used to be maintained separately and
# drifted: harvest caught `ghp_`/`gho_`/`sk-proj-`/Slack/JWT/bearer tokens and
# assignment-style secrets, while the profile validator knew about five
# patterns and waved the rest through. A secret that survives harvesting has to
# be caught here, so both sides now read the same table.
#
# Columns: regex, human label (for the validator's error), replacement (for
# the redactor). Order matters — credentials before home paths, because a key
# embedded in a path must be masked as a key.
#
# The assignment-style pattern is deliberately broad. It will fire on a
# directive phrased "password: never log it", which is a false positive. Being
# noisy about a literal secret in a file destined for `git commit` is the
# trade we want; reword the directive.
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
     "email address", "<email>"),
    (re.compile(r"\bAIzaSy[A-Za-z0-9_-]{33}\b"),
     "Google API key", "<api-key>"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
     "OpenAI-style API key", "<api-key>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
     "GitHub token", "<token>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
     "Slack token", "<token>"),
    (re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "JSON Web Token", "<jwt>"),
    (re.compile(r"(?i)\b(?:bearer|authorization:)\s+\S+"),
     "authorization header", "<auth>"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+"),
     "assigned secret", "<secret>"),
    (re.compile(r"C:\\Users\\[A-Za-z0-9._-]+", re.IGNORECASE),
     "home directory path", "~"),
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+"),
     "home directory path", "~"),
]

# A profile is compiled into files that get committed to repositories and
# pasted into system prompts. Anything personally identifying that leaks in
# here leaks everywhere downstream, so it is rejected at the contract layer.
LEAK_PATTERNS = [(p, label) for p, label, _ in SENSITIVE_PATTERNS]


class ProfileError(Exception):
    """Raised when a profile cannot be loaded or is structurally unusable."""


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_profile(subject: str = "the user") -> dict:
    """An honest empty profile: every axis unknown, nothing claimed."""
    return {
        "schema_version": SCHEMA_VERSION,
        "subject": subject,
        "generated": _now(),
        "evidence_ref": None,
        "dimensions": {
            name: {
                "band": "unknown",
                "source": "inferred",
                "evidence": [],
                "rationale": "",
            }
            for name in DIMENSIONS
        },
        "tone": {"default": ""},
        "limits": {name: None for name in LIMITS},
        "rules": [],
        "forbidden": [],
        "unknowns": sorted(DIMENSIONS),
    }


def next_rule_id(profile: dict) -> str:
    used = set()
    for rule in profile.get("rules", []) + profile.get("forbidden", []):
        rid = rule.get("id", "")
        if rid.startswith("R") and rid[1:].isdigit():
            used.add(int(rid[1:]))
    n = 1
    while n in used:
        n += 1
    return f"R{n}"


def add_rule(profile, directive, scope="always", source="declared",
             evidence=None, forbidden=False):
    """Append a rule and return it. Does not validate; call validate() after."""
    if scope not in SCOPES:
        raise ProfileError(f"unknown scope {scope!r}; expected one of {', '.join(SCOPES)}")
    if source not in SOURCES:
        raise ProfileError(f"unknown source {source!r}; expected one of {', '.join(SOURCES)}")
    rule = {
        "id": next_rule_id(profile),
        "scope": scope,
        "directive": directive.strip(),
        "source": source,
        "evidence": list(evidence or []),
    }
    profile.setdefault("forbidden" if forbidden else "rules", []).append(rule)
    return rule


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _check_leaks(node, path, errors):
    if isinstance(node, dict):
        for key, value in node.items():
            _check_leaks(value, f"{path}.{key}", errors)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _check_leaks(value, f"{path}[{i}]", errors)
    elif isinstance(node, str):
        for pattern, label in LEAK_PATTERNS:
            if pattern.search(node):
                errors.append(f"{path}: contains a {label}; profiles are compiled "
                              f"into committed files and must stay clean")
                break


def _validate_claim(claim, path, quote_ids, errors, warnings, require_evidence):
    """Shared checks for a dimension entry or a rule -- both carry evidence."""
    source = claim.get("source")
    if source not in SOURCES:
        errors.append(f"{path}.source: {source!r} is not one of {', '.join(SOURCES)}")
        return

    evidence = claim.get("evidence")
    if not isinstance(evidence, list):
        errors.append(f"{path}.evidence: must be a list")
        return

    if source == "observed":
        if not evidence:
            errors.append(f"{path}: source is 'observed' but cites no evidence. "
                          f"Downgrade to 'inferred' or cite a quote ID.")
        for item in evidence:
            if not isinstance(item, str) or not QUOTE_ID_RE.match(item):
                errors.append(f"{path}.evidence: 'observed' claims cite quote IDs "
                              f"like 'q7', got {item!r}")
            elif quote_ids is not None and item not in quote_ids:
                errors.append(f"{path}.evidence: quote {item!r} is not in the "
                              f"evidence file")
    elif source == "declared":
        if not evidence:
            errors.append(f"{path}: source is 'declared' but does not record what "
                          f"the user said or chose")
        for item in evidence:
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{path}.evidence: 'declared' claims need a note, "
                              f"got {item!r}")
    else:  # inferred
        if require_evidence:
            errors.append(f"{path}: source is 'inferred', which --strict rejects")
        else:
            warnings.append(f"{path}: inferred, not grounded in evidence")


def validate(profile, evidence=None, strict=False):
    """Return (errors, warnings). An empty errors list means the profile is usable."""
    errors, warnings = [], []

    if not isinstance(profile, dict):
        return ([f"profile must be a JSON object, got {type(profile).__name__}"], [])

    version = profile.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(f"schema_version: expected {SCHEMA_VERSION!r}, got {version!r}")

    # `str(x or "")` would happily accept 42 or ["a"] and stringify it. The
    # renderer then runs re.sub over profile["subject"] and raises TypeError on
    # a non-string, so the type has to be checked here, not coerced.
    subject = profile.get("subject")
    if not isinstance(subject, str):
        errors.append(f"subject: must be a string, got {type(subject).__name__}")
    elif not subject.strip():
        errors.append("subject: must name who this profile describes")

    # Checked early because the dimensions pass below reads it.
    unknowns = profile.get("unknowns")
    if not isinstance(unknowns, list):
        errors.append("unknowns: must be a list")
        unknowns = []
    elif any(not isinstance(u, str) for u in unknowns):
        errors.append("unknowns: every entry must be a dimension name string")
        unknowns = [u for u in unknowns if isinstance(u, str)]

    quote_ids = None
    if evidence is not None:
        quote_ids = {q["id"] for q in evidence.get("quotes", []) if "id" in q}

    # -- dimensions ---------------------------------------------------------
    dims = profile.get("dimensions")
    if not isinstance(dims, dict):
        errors.append("dimensions: must be an object")
    else:
        for name in DIMENSIONS:
            if name not in dims:
                errors.append(f"dimensions.{name}: missing")
        for name, entry in dims.items():
            path = f"dimensions.{name}"
            if name not in DIMENSIONS:
                errors.append(f"{path}: unknown dimension")
                continue
            if not isinstance(entry, dict):
                errors.append(f"{path}: must be an object")
                continue
            band = entry.get("band")
            if band not in BANDS:
                errors.append(f"{path}.band: {band!r} is not one of {', '.join(BANDS)}")
                continue
            if band == "unknown":
                # An unknown axis makes no claim, so it needs no evidence --
                # but it must be declared unknown out loud.
                if entry.get("evidence"):
                    warnings.append(f"{path}: band is 'unknown' but evidence is cited")
                if name not in unknowns:
                    errors.append(f"{path}: band is 'unknown' but {name!r} is not "
                                  f"listed in profile.unknowns")
            else:
                _validate_claim(entry, path, quote_ids, errors, warnings, strict)
                if not str(entry.get("rationale") or "").strip():
                    errors.append(f"{path}.rationale: required once a band is set")
                # The other direction of the unknowns invariant. Without this,
                # a profile can band an axis 'high' and still advertise it as
                # unknown, so the rendered config claims a measurement it then
                # tells the reader it never took.
                if name in unknowns:
                    errors.append(f"{path}: band is {band!r} but {name!r} is still "
                                  f"listed in profile.unknowns")

        for name in unknowns:
            if name not in DIMENSIONS:
                errors.append(f"unknowns: {name!r} is not a dimension")

    # -- rules --------------------------------------------------------------
    seen_ids = set()
    for bucket in ("rules", "forbidden"):
        items = profile.get(bucket)
        if not isinstance(items, list):
            errors.append(f"{bucket}: must be a list")
            continue
        for i, rule in enumerate(items):
            path = f"{bucket}[{i}]"
            if not isinstance(rule, dict):
                errors.append(f"{path}: must be an object")
                continue
            rid = rule.get("id")
            if not rid:
                errors.append(f"{path}.id: missing")
            elif rid in seen_ids:
                errors.append(f"{path}.id: duplicate id {rid!r}")
            else:
                seen_ids.add(rid)
            if rule.get("scope") not in SCOPES:
                errors.append(f"{path}.scope: {rule.get('scope')!r} is not one of "
                              f"{', '.join(SCOPES)}")
            if not str(rule.get("directive") or "").strip():
                errors.append(f"{path}.directive: must not be empty")
            _validate_claim(rule, path, quote_ids, errors, warnings, strict)

    if not profile.get("rules"):
        errors.append("rules: a profile with no rules renders an empty config; "
                      "run a calibration pass first")

    # -- limits -------------------------------------------------------------
    limits = profile.get("limits")
    if not isinstance(limits, dict):
        errors.append("limits: must be an object")
    else:
        for name, value in limits.items():
            if name not in LIMITS:
                errors.append(f"limits.{name}: unknown limit")
                continue
            if value is None:
                continue
            lo, hi = LIMITS[name]
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"limits.{name}: must be an integer or null, got {value!r}")
            elif not lo <= value <= hi:
                errors.append(f"limits.{name}: {value} is outside the sane range {lo}-{hi}")

    # -- tone ---------------------------------------------------------------
    tone = profile.get("tone")
    if not isinstance(tone, dict):
        errors.append("tone: must be an object")
    else:
        for key, value in tone.items():
            if key not in TONE_CONTEXTS:
                errors.append(f"tone.{key}: unknown context; expected one of "
                              f"{', '.join(TONE_CONTEXTS)}")
            # render.build_tone_block calls .strip() on these. Only the keys
            # were ever checked, so a tone value of null or 12 got through
            # validate() clean and blew up in the renderer instead.
            if not isinstance(value, str):
                errors.append(f"tone.{key}: must be a string, got "
                              f"{type(value).__name__}")

    _check_leaks(profile, "profile", errors)

    return errors, warnings


def coverage(profile):
    """How much of this profile was earned rather than guessed.

    Dimensions and rules each carry a `source`, so they can be sorted into
    observed / declared / inferred. Tone strings and numeric limits do not:
    the schema has no place to put one. They still render as directives, so
    they are counted as `unattributed` and included in the denominator.

    That last part matters. Counting them only in the numerator's absence --
    i.e. leaving them out of `claims_total` entirely, as this function used to
    -- meant a profile of two observed rules and six invented limits reported
    100% grounded. The footer in every generated config quotes this number, so
    the number has to cover everything the config actually tells the agent to
    do.
    """
    counts = {s: 0 for s in SOURCES}
    counts["unknown"] = 0
    for entry in profile.get("dimensions", {}).values():
        if entry.get("band") == "unknown":
            counts["unknown"] += 1
        else:
            counts[entry.get("source", "inferred")] += 1
    for rule in profile.get("rules", []) + profile.get("forbidden", []):
        counts[rule.get("source", "inferred")] += 1

    tone = profile.get("tone") or {}
    limits = profile.get("limits") or {}
    unattributed = 0
    if isinstance(tone, dict):
        unattributed += sum(1 for v in tone.values()
                            if isinstance(v, str) and v.strip())
    if isinstance(limits, dict):
        unattributed += sum(1 for v in limits.values() if v is not None)

    total = sum(counts.values()) + unattributed
    grounded = counts["observed"] + counts["declared"]
    return {
        "claims_total": total,
        "observed": counts["observed"],
        "declared": counts["declared"],
        "inferred": counts["inferred"],
        "unattributed": unattributed,
        "unknown_dimensions": counts["unknown"],
        "grounded_pct": round(100.0 * grounded / total, 1) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load(path):
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"no such file: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"{p} is not valid JSON: {exc}") from exc


def save(profile, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Schema generation -- derived, never hand-edited
# ---------------------------------------------------------------------------


def build_schema():
    claim_props = {
        "source": {"enum": list(SOURCES)},
        "evidence": {"type": "array", "items": {"type": "string"}},
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://github.com/ksprashu/agent-skill-forge/"
               "skills/cognitive-profiler/references/profile.schema.json",
        "title": "Communication Profile",
        "description": (
            "Generated by scripts/profile_tool.py -- do not hand-edit. "
            "Run `profile_tool.py schema --check` to verify this file is current. "
            "JSON Schema cannot express the evidence invariant (observed claims "
            "must cite resolvable quote IDs); scripts/profile_tool.py validate does."
        ),
        "type": "object",
        "required": list(REQUIRED_TOP_LEVEL),
        "additionalProperties": False,
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "subject": {"type": "string", "minLength": 1},
            "generated": {"type": "string"},
            "evidence_ref": {"type": ["string", "null"]},
            "dimensions": {
                "type": "object",
                "required": list(DIMENSIONS),
                "additionalProperties": False,
                "properties": {
                    name: {
                        "type": "object",
                        "description": meta["question"],
                        "required": ["band", "source", "evidence", "rationale"],
                        "additionalProperties": False,
                        "properties": dict(
                            claim_props,
                            band={"enum": list(BANDS)},
                            rationale={"type": "string"},
                        ),
                    }
                    for name, meta in DIMENSIONS.items()
                },
            },
            "tone": {
                "type": "object",
                "additionalProperties": False,
                "properties": {c: {"type": "string"} for c in TONE_CONTEXTS},
            },
            "limits": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    name: {"type": ["integer", "null"], "minimum": lo, "maximum": hi}
                    for name, (lo, hi) in LIMITS.items()
                },
            },
            "rules": {"type": "array", "items": {"$ref": "#/definitions/rule"}},
            "forbidden": {"type": "array", "items": {"$ref": "#/definitions/rule"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
        },
        "definitions": {
            "rule": {
                "type": "object",
                "required": ["id", "scope", "directive", "source", "evidence"],
                "additionalProperties": False,
                "properties": dict(
                    claim_props,
                    id={"type": "string", "pattern": r"^R\d+$"},
                    scope={"enum": list(SCOPES)},
                    directive={"type": "string", "minLength": 1},
                ),
            }
        },
    }


def schema_path():
    return Path(__file__).resolve().parent.parent / "references" / "profile.schema.json"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_init(args):
    profile = new_profile(args.subject)
    save(profile, args.output)
    print(f"Wrote empty profile to {args.output}")
    print("Every dimension is 'unknown'. Fill it via a calibration pass -- see "
          "references/calibration.md.")
    return 0


def _cmd_validate(args):
    profile = load(args.profile)
    evidence = load(args.evidence) if args.evidence else None
    errors, warnings = validate(profile, evidence, strict=args.strict)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error:   {e}", file=sys.stderr)

    cov = coverage(profile)
    print(f"\n{cov['claims_total']} claims: {cov['observed']} observed, "
          f"{cov['declared']} declared, {cov['inferred']} inferred, "
          f"{cov['unattributed']} unattributed (tone/limits), "
          f"{cov['unknown_dimensions']} dimensions left unknown "
          f"({cov['grounded_pct']}% grounded)")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("OK")
    return 0


def _cmd_amend(args):
    profile = load(args.profile)
    rule = add_rule(
        profile,
        directive=args.directive,
        scope=args.scope,
        source=args.source,
        evidence=args.evidence,
        forbidden=args.forbidden,
    )
    profile["generated"] = _now()

    errors, _ = validate(profile)
    if errors:
        print("Refusing to write; the amended profile does not validate:",
              file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    save(profile, args.profile)
    bucket = "forbidden" if args.forbidden else "rules"
    print(f"Added {bucket} {rule['id']} ({args.scope}/{args.source}): {rule['directive']}")
    print("Re-run render.py to push this into your harness configs.")
    return 0


def _cmd_schema(args):
    schema = build_schema()
    text = json.dumps(schema, indent=2) + "\n"
    target = Path(args.output) if args.output else schema_path()

    if args.check:
        if not target.exists():
            print(f"error: {target} does not exist; run without --check to "
                  f"generate it", file=sys.stderr)
            return 1
        if target.read_text(encoding="utf-8") != text:
            print(f"error: {target} is stale. Regenerate with: "
                  f"profile_tool.py schema", file=sys.stderr)
            return 1
        print(f"{target} is current")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"Wrote schema to {target}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create, validate and amend a communication profile.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="write an empty, honest profile")
    p_init.add_argument("-o", "--output", default="profile.json")
    p_init.add_argument("--subject", default="the user")
    p_init.set_defaults(func=_cmd_init)

    p_val = sub.add_parser("validate", help="check a profile against the contract")
    p_val.add_argument("profile")
    p_val.add_argument("-e", "--evidence", help="evidence.json, to resolve quote IDs")
    p_val.add_argument("--strict", action="store_true",
                       help="reject inferred claims outright")
    p_val.set_defaults(func=_cmd_validate)

    p_am = sub.add_parser("amend", help="append one rule, validate, and save")
    p_am.add_argument("profile")
    p_am.add_argument("--directive", required=True)
    p_am.add_argument("--scope", default="always", choices=SCOPES)
    p_am.add_argument("--source", default="declared", choices=SOURCES)
    p_am.add_argument("--evidence", action="append", default=[],
                      help="quote ID (observed) or a note (declared); repeatable")
    p_am.add_argument("--forbidden", action="store_true",
                      help="record as a prohibition rather than an instruction")
    p_am.set_defaults(func=_cmd_amend)

    p_sc = sub.add_parser("schema", help="regenerate or verify the JSON Schema")
    p_sc.add_argument("-o", "--output")
    p_sc.add_argument("--check", action="store_true",
                      help="exit non-zero if the committed schema is stale")
    p_sc.set_defaults(func=_cmd_schema)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
