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

"""The findings contract shared by `review`, `security-review` and pr-guardian.

A review is judgement; this module does not judge. It owns the *shape* of the
judgement so that a machine can act on it:

  findings.py schema               print the JSON Schema (generated from the
                                   constants below; references/findings.schema.json
                                   is a committed copy, kept fresh by a test)
  findings.py validate FILE        structural + semantic validation
  findings.py gate FILE            exit 1 if any finding is still open at P0-P3
  findings.py sarif FILE           convert to SARIF 2.1.0 for code scanning

FILE may be "-" for stdin. Findings and results go to stdout, diagnostics to
stderr.

Exit codes:
  0   validate: document is valid.  gate: no open blocking findings.
  1   validate: document is invalid. gate: open blocking findings exist.
  2   input unreadable or not JSON
  64  usage error

What `validate` checks (V3): every field's type and enum, line ranges, path
safety, id uniqueness, and the evidence rules in EVIDENCE_RULES. What it does
not check (V5): whether a finding is *true*. That needs a reviewer, and a
validator that pretended otherwise would be decorative verification.

`gate` refuses to run on an invalid document: an unparseable review is not a
clean review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

PRODUCERS = ("review", "security-review")
MODES = ("pr", "diff", "repo")

# One severity scale for every skill. security-review's Critical/High/Medium/Low
# map onto P0/P1/P2/P3 (see SECURITY_SEVERITY_MAP).
SEVERITIES = ("P0", "P1", "P2", "P3", "nit")
BLOCKING_SEVERITIES = ("P0", "P1", "P2", "P3")
SECURITY_SEVERITY_MAP = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3",
                         "informational": "nit"}

AXES = (
    "scope-architecture",
    "correctness",
    "security",
    "reliability",
    "performance",
    "data-integrity",
    "tests",
    "observability",
    "style",
)
CONFIDENCE = ("high", "medium", "low")

# Lifecycle across review rounds. A finding is open unless its status says the
# author dealt with it and the reviewer agreed.
STATUSES = ("new", "still_open", "reopened", "fixed", "accepted_pushback")
CLOSED_STATUSES = ("fixed", "accepted_pushback")

# From agent-security-posture's audit method. "rejected" leads never become
# findings, so it is not a legal value here.
SECURITY_VERDICTS = ("confirmed", "needs_validation", "n/a")

ID_PATTERN = r"^[A-Z][A-Z0-9]*-[0-9]{3,}$"
SECURITY_RULE_PATTERN = r"^(CWE-[0-9]+|CVE-[0-9]{4}-[0-9]+|GHSA(-[23456789cfghjmpqrvwx]{4}){3}|OSV-.+|ASI[0-9]{2}|LLM[0-9]{2}|API[0-9]{1,2})"
TITLE_MAX = 120

EVIDENCE_RULES = (
    "P0/P1 need evidence of at least 20 characters and medium or high confidence.",
    "Style findings cite at least one https reference (the guide or config rule).",
    "Security-axis findings name a CWE, CVE, GHSA, OSV, ASI, LLM or API rule id "
    "and carry a security_verdict of confirmed or needs_validation.",
    "needs_validation security findings cannot be P0/P1; only confirmed ones can.",
    "fixed / accepted_pushback / still_open / reopened findings carry the prior_id "
    "they continue.",
)


def build_schema() -> dict[str, Any]:
    """The JSON Schema for a review document, derived from the constants."""
    reference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "url"],
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "url": {"type": "string", "pattern": "^https://"},
        },
    }
    finding = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id", "severity", "axis", "rule", "title", "file", "start_line",
            "end_line", "rationale", "evidence", "suggestion", "references",
            "confidence", "status", "prior_id", "security_verdict",
        ],
        "properties": {
            "id": {"type": "string", "pattern": ID_PATTERN},
            "severity": {"type": "string", "enum": list(SEVERITIES)},
            "axis": {"type": "string", "enum": list(AXES)},
            "rule": {"type": "string",
                     "description": "Rule or weakness id: CWE-89, PEP8-E501, "
                                    "google-pystyle-3.8, eslint:no-eval, ..."},
            "title": {"type": "string", "minLength": 1, "maxLength": TITLE_MAX},
            "file": {"type": "string", "minLength": 1,
                     "description": "Repo-relative path."},
            "start_line": {"type": "integer", "minimum": 1},
            "end_line": {"type": "integer", "minimum": 1},
            "rationale": {"type": "string", "minLength": 1,
                          "description": "Why this is a defect and what breaks."},
            "evidence": {"type": "string",
                         "description": "Quoted code, tool output, or repro."},
            "suggestion": {"type": "string",
                           "description": "Replacement for lines start..end, "
                                          "or empty when no drop-in fix exists."},
            "references": {"type": "array", "items": reference},
            "confidence": {"type": "string", "enum": list(CONFIDENCE)},
            "status": {"type": "string", "enum": list(STATUSES)},
            "prior_id": {"type": "string",
                         "description": "Id from the previous round, or empty."},
            "security_verdict": {"type": "string", "enum": list(SECURITY_VERDICTS)},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://github.com/ksprashu/agent-skill-forge/skills/review/references/findings.schema.json",
        "title": "Review findings",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "producer", "mode", "summary", "inspected",
                     "not_inspected", "findings"],
        "properties": {
            "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
            "producer": {"type": "string", "enum": list(PRODUCERS)},
            "mode": {"type": "string", "enum": list(MODES)},
            "summary": {"type": "string", "minLength": 1},
            "inspected": {"type": "array", "items": {"type": "string"}},
            "not_inspected": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["what", "reason"],
                    "properties": {"what": {"type": "string", "minLength": 1},
                                   "reason": {"type": "string", "minLength": 1}},
                },
            },
            "findings": {"type": "array", "items": finding},
        },
    }


# --- a small draft-07 subset validator (stdlib only, S1) ---------------------

_TYPES = {"object": dict, "array": list, "string": str, "integer": int}


def _check(node: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected:
        py = _TYPES[expected]
        if not isinstance(node, py) or (expected == "integer" and isinstance(node, bool)):
            errors.append(f"{path}: expected {expected}")
            return
    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{path}: {node!r} not one of {schema['enum']}")
    if isinstance(node, str):
        if len(node) < schema.get("minLength", 0):
            errors.append(f"{path}: empty")
        if "maxLength" in schema and len(node) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], node):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(node, int) and "minimum" in schema and node < schema["minimum"]:
        errors.append(f"{path}: below {schema['minimum']}")
    if isinstance(node, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in node:
                errors.append(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in props:
                    errors.append(f"{path}: unexpected field {key}")
        for key, sub in props.items():
            if key in node:
                _check(node[key], sub, f"{path}.{key}", errors)
    if isinstance(node, list) and "items" in schema:
        for i, item in enumerate(node):
            _check(item, schema["items"], f"{path}[{i}]", errors)


def _semantic(doc: dict[str, Any], errors: list[str]) -> None:
    seen: set[str] = set()
    findings = doc.get("findings", [])
    if not isinstance(findings, list):  # already reported by _check
        return
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        where = f"$.findings[{i}]"
        fid = f.get("id", "")
        if isinstance(fid, str):  # a non-string id is already a type error
            if fid in seen:
                errors.append(f"{where}: duplicate id {fid}")
            seen.add(fid)

        start, end = f.get("start_line"), f.get("end_line")
        if isinstance(start, int) and isinstance(end, int) and end < start:
            errors.append(f"{where}: end_line {end} before start_line {start}")

        path = f.get("file", "")
        if isinstance(path, str) and (path.startswith("/") or re.match(r"^[A-Za-z]:", path)
                                      or ".." in Path(path).parts or "\\" in path):
            errors.append(f"{where}: file must be a repo-relative POSIX path")

        sev, axis = f.get("severity"), f.get("axis")
        evidence = f.get("evidence", "")
        if sev in ("P0", "P1"):
            if not isinstance(evidence, str) or len(evidence.strip()) < 20:
                errors.append(f"{where}: {sev} needs concrete evidence (>= 20 chars)")
            if f.get("confidence") == "low":
                errors.append(f"{where}: {sev} cannot be low confidence")

        refs = f.get("references", [])
        if axis == "style" and not refs:
            errors.append(f"{where}: style findings must cite a guide or config rule")

        verdict = f.get("security_verdict")
        if axis == "security":
            if not re.match(SECURITY_RULE_PATTERN, str(f.get("rule", ""))):
                errors.append(f"{where}: security findings need a CWE/CVE/GHSA/OSV/ASI/LLM/API rule")
            if verdict not in ("confirmed", "needs_validation"):
                errors.append(f"{where}: security findings need security_verdict "
                              "confirmed or needs_validation")
            if verdict == "needs_validation" and sev in ("P0", "P1"):
                errors.append(f"{where}: needs_validation cannot be {sev}; confirm it or lower it")

        status, prior = f.get("status"), f.get("prior_id", "")
        if status in ("still_open", "reopened", "fixed", "accepted_pushback") and not prior:
            errors.append(f"{where}: status {status} needs the prior_id it continues")


def validate(doc: Any) -> list[str]:
    """Return every error found; an empty list means valid."""
    errors: list[str] = []
    _check(doc, build_schema(), "$", errors)
    if isinstance(doc, dict):
        _semantic(doc, errors)
    return errors


def open_blocking(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Findings that should hold a merge: P0-P3 and not closed."""
    return [f for f in doc.get("findings", [])
            if f.get("severity") in BLOCKING_SEVERITIES
            and f.get("status") not in CLOSED_STATUSES]


_SARIF_LEVEL = {"P0": "error", "P1": "error", "P2": "warning", "P3": "note", "nit": "note"}


def to_sarif(doc: dict[str, Any]) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    results = []
    for f in doc.get("findings", []):
        if f.get("status") in CLOSED_STATUSES:
            continue
        rule_id = f.get("rule") or f.get("axis", "review")
        rule = rules.setdefault(rule_id, {
            "id": rule_id,
            "shortDescription": {"text": f["title"]},
            "properties": {"tags": [f["axis"]]},
        })
        if f.get("references"):
            rule.setdefault("helpUri", f["references"][0]["url"])
        results.append({
            "ruleId": rule_id,
            "level": _SARIF_LEVEL[f["severity"]],
            "message": {"text": f"[{f['severity']}] {f['title']}: {f['rationale']}"},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f["file"]},
                "region": {"startLine": f["start_line"], "endLine": f["end_line"]},
            }}],
            "partialFingerprints": {"findingId": f["id"]},
            "properties": {"severity": f["severity"], "confidence": f["confidence"]},
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": f"agent-skill-forge/{doc.get('producer', 'review')}",
                                "informationUri": "https://github.com/ksprashu/agent-skill-forge",
                                "rules": list(rules.values())}},
            "results": results,
        }],
    }


def _load(arg: str) -> Any:
    text = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema", help="print the JSON Schema")
    for name, helptext in (("validate", "validate a findings document"),
                           ("gate", "exit 1 if open P0-P3 findings remain"),
                           ("sarif", "convert a findings document to SARIF 2.1.0")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("file", help="findings JSON path, or - for stdin")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if args.cmd == "schema":
        print(json.dumps(build_schema(), indent=2))
        return 0

    try:
        doc = _load(args.file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"findings: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    errors = validate(doc)
    if args.cmd == "validate":
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 1 if errors else 0
    if errors:
        print(f"findings: refusing to {args.cmd} an invalid document:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    if args.cmd == "gate":
        blocking = open_blocking(doc)
        print(json.dumps({
            "open_blocking": len(blocking),
            "by_severity": {s: sum(1 for f in blocking if f["severity"] == s)
                            for s in BLOCKING_SEVERITIES},
            "ids": [f["id"] for f in blocking],
            "not_inspected": doc.get("not_inspected", []),
        }, indent=2))
        return 1 if blocking else 0
    print(json.dumps(to_sarif(doc), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
