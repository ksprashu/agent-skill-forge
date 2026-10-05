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
Defect Validator (S9 Validator & Schema Enforcer) for the Review Skill.

Validates that agent-authored markdown defect reports adhere to the Atomic Defect Schema:
- Valid Defect ID or standard badge: matches r'\\[DEFECT-\\d+\\]', r'\\[P[0-3]:\\s*[^\\]]+\\]',
  or r'\\[(Critical|Important|Suggestion|Question)[^\\]]*\\]'.
- Valid file:line location: matches 'file:///path/to/file#L\\d+', 'path/to/file:L\\d+',
  or 'path/to/file:\\d+'.
- Required sections:
  1. Description / Vulnerability Description
  2. Blast Radius / Impact
  3. Empirical Proof / Reproduction
  4. Drop-in Remediation / Proposed Fix (with code block containing Before/After or proposed code)
  5. Verification Gate / Verification command

In strict compliance with docs/ENGINEERING_STANDARD.md:
- S1: Python 3.12, stdlib only (sys, os, argparse, re, pathlib, typing, json).
- S2: Never shadow stdlib module names.
- S3: Exit non-zero on failure. Print findings to stdout, diagnostics to stderr.
- S4: subprocess with argument list and shell=False (if invoked).
- S5: No hardcoded absolute paths.
- S6: Accurate --help matching all documented flags.
- S9: Evidence/judgement split - validates mechanical schema conformance, never scores.
- V5: Explicitly reports what was NOT inspected.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Strict console UTF-8 safety
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# V5 compliance: Honest accounting of surface this validator does not audit
UNINSPECTED_SURFACE: List[str] = [
    "semantic correctness and security of proposed remediation code",
    "empirical reproduction execution against live repository state",
    "factual accuracy of stated blast radius and business impact",
    "git history and authorship provenance of referenced file lines",
]

# ID / Badge patterns
ID_BADGE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r'\[DEFECT-\d+\]', re.IGNORECASE),
    re.compile(r'\[P[0-3]:\s*[^\]]+\]', re.IGNORECASE),
    re.compile(r'\[(Critical|Important|Suggestion|Question)[^\]]*\]', re.IGNORECASE),
]

# File:line location patterns
LOCATION_PATTERNS: List[re.Pattern[str]] = [
    # URI format: file:///path/to/file#L42
    re.compile(r'file:///[^\s\)\]>#]+#L\d+'),
    # Path with directory prefix: path/to/file:L42 or path/to/file:42 or /path/to/file:42
    re.compile(r'(?:^|[\s\(`\'"\[<])((?:/|\\)?(?:[a-zA-Z0-9_\-\.]+[/\\])+[a-zA-Z0-9_\-\.]+:(?:L)?\d+)'),
    # Single filename with extension: file.ext:L42 or file.ext:42
    re.compile(r'(?:^|[\s\(`\'"\[<])([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9_\-]+:(?:L)?\d+)'),
]

# Required sections definition
REQUIRED_SECTIONS: List[Dict[str, Any]] = [
    {
        "name": "Description",
        "pattern": re.compile(
            r'(?:^|\n)\s*(?:#{1,6}\s*(?:\d+[\.\)]\s*)?|\*{1,2}|-\s+\*{1,2}|_\s*)?'
            r'(?:Vulnerability\s+Description|Description)\b',
            re.IGNORECASE,
        ),
        "aliases": ["Description", "Vulnerability Description"],
    },
    {
        "name": "Blast Radius",
        "pattern": re.compile(
            r'(?:^|\n)\s*(?:#{1,6}\s*(?:\d+[\.\)]\s*)?|\*{1,2}|-\s+\*{1,2}|_\s*)?'
            r'(?:Blast\s+Radius|Impact)\b',
            re.IGNORECASE,
        ),
        "aliases": ["Blast Radius", "Impact"],
    },
    {
        "name": "Empirical Proof",
        "pattern": re.compile(
            r'(?:^|\n)\s*(?:#{1,6}\s*(?:\d+[\.\)]\s*)?|\*{1,2}|-\s+\*{1,2}|_\s*)?'
            r'(?:Empirical\s+Proof|Reproduction|Proof\s+of\s+Concept|PoC|Repro)\b',
            re.IGNORECASE,
        ),
        "aliases": ["Empirical Proof", "Reproduction"],
    },
    {
        "name": "Drop-in Remediation",
        "pattern": re.compile(
            r'(?:^|\n)\s*(?:#{1,6}\s*(?:\d+[\.\)]\s*)?|\*{1,2}|-\s+\*{1,2}|_\s*)?'
            r'(?:Drop-in\s+Remediation|Proposed\s+Fix|Remediation|Proposed\s+Remediation|Fix)\b',
            re.IGNORECASE,
        ),
        "aliases": ["Drop-in Remediation", "Proposed Fix"],
    },
    {
        "name": "Verification Gate",
        "pattern": re.compile(
            r'(?:^|\n)\s*(?:#{1,6}\s*(?:\d+[\.\)]\s*)?|\*{1,2}|-\s+\*{1,2}|_\s*)?'
            r'(?:Verification\s+Gate|Verification\s+Command|Verification)\b',
            re.IGNORECASE,
        ),
        "aliases": ["Verification Gate", "Verification command"],
    },
]


def extract_locations(text: str) -> List[str]:
    """Find all valid file:line locations in the given text."""
    locations: List[str] = []
    # 1. file:///path/to/file#L42
    for match in LOCATION_PATTERNS[0].finditer(text):
        locations.append(match.group(0))

    # 2. path/to/file:L42 or path/to/file:42
    for match in LOCATION_PATTERNS[1].finditer(text):
        loc = match.group(1).strip()
        if loc and loc not in locations:
            locations.append(loc)

    # 3. single_file.ext:L42 or single_file.ext:42
    for match in LOCATION_PATTERNS[2].finditer(text):
        loc = match.group(1).strip()
        if loc and loc not in locations:
            locations.append(loc)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for loc in locations:
        if loc not in seen:
            seen.add(loc)
            deduped.append(loc)
    return deduped


def extract_id_and_badge(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract defect ID and/or severity badge if present."""
    defect_id = None
    badge = None

    id_match = re.search(r'\[DEFECT-\d+\]', text, re.IGNORECASE)
    if id_match:
        defect_id = id_match.group(0).strip('[]')

    badge_match = re.search(r'\[P[0-3]:\s*[^\]]+\]', text, re.IGNORECASE)
    if badge_match:
        badge = badge_match.group(0).strip('[]')
    else:
        badge_match2 = re.search(r'\[(Critical|Important|Suggestion|Question)[^\]]*\]', text, re.IGNORECASE)
        if badge_match2:
            badge = badge_match2.group(0).strip('[]')

    return defect_id, badge


class DefectValidator:
    """Enforces Atomic Defect Schema on markdown defect documentation."""

    def __init__(self) -> None:
        self.uninspected: List[str] = list(UNINSPECTED_SURFACE)

    def validate_defect_chunk(self, chunk: str, defect_index: int = 1) -> Dict[str, Any]:
        """Validate a single defect block against the Atomic Defect Schema."""
        errors: List[str] = []
        defect_id, badge = extract_id_and_badge(chunk)

        # 1. Valid Defect ID or standard badge
        has_id_or_badge = any(pat.search(chunk) for pat in ID_BADGE_PATTERNS)
        if not has_id_or_badge:
            errors.append(
                f"Defect {defect_index}: Missing valid Defect ID or standard badge. "
                "Must match r'\\[DEFECT-\\d+\\]', r'\\[P[0-3]:\\s*[^\\]]+\\]', "
                "or r'\\[(Critical|Important|Suggestion|Question)[^\\]]*\\]'."
            )

        # 2. Valid file:line location
        locations = extract_locations(chunk)
        if not locations:
            errors.append(
                f"Defect {defect_index}: Missing valid file:line location. "
                "Must match 'file:///path/to/file#L<line>', 'path/to/file:L<line>', "
                "or 'path/to/file:<line>'."
            )

        # 3. Required sections
        rem_match: Optional[re.Match[str]] = None
        for sec in REQUIRED_SECTIONS:
            sec_name = sec["name"]
            sec_pattern: re.Pattern[str] = sec["pattern"]
            match = sec_pattern.search(chunk)
            if not match:
                aliases_str = " / ".join(sec["aliases"])
                errors.append(
                    f"Defect {defect_index}: Missing required section '{sec_name}'. "
                    f"Expected heading matching '{aliases_str}'."
                )
            elif sec_name == "Drop-in Remediation":
                rem_match = match

        # 4. Code block in Drop-in Remediation
        if rem_match is not None:
            rem_start = rem_match.end()
            rem_rest = chunk[rem_start:]
            # Next section starts at next header or bold label (excluding code comments)
            next_heading = re.search(
                r'(?m)(?:^#{1,6}\s*(?:\d+[\.\)]\s*)?(?:Verification|Gate|Command|Next\s+Actions?|Sign-off|\[?DEFECT)|^[-*]?\s*\*{1,2}(?:Verification|Gate|Command))',
                rem_rest,
                re.IGNORECASE,
            )
            rem_content = rem_rest[:next_heading.start()] if next_heading else rem_rest

            # Check for fenced code blocks (3 or more backticks)
            code_blocks = re.findall(r'`{3,}(?:[a-zA-Z0-9_\-\+]*\n)?([\s\S]*?)`{3,}', rem_content)
            if not code_blocks:
                errors.append(
                    f"Defect {defect_index}: 'Drop-in Remediation / Proposed Fix' section must contain "
                    "a fenced code block (``` ... ```) with proposed code or before/after comparison."
                )
            else:
                non_empty = [b for b in code_blocks if b.strip()]
                if not non_empty:
                    errors.append(
                        f"Defect {defect_index}: 'Drop-in Remediation' code block is empty."
                    )

        is_valid = len(errors) == 0
        return {
            "index": defect_index,
            "id": defect_id or f"DEFECT-{defect_index:03d}" if is_valid else (defect_id or "UNKNOWN"),
            "badge": badge,
            "locations": locations,
            "valid": is_valid,
            "errors": errors,
        }

    def validate(self, text: str, source_name: str = "<input>") -> Dict[str, Any]:
        """Validate markdown text which may contain one or more defect entries."""
        if not text or not text.strip():
            return {
                "source": source_name,
                "valid": False,
                "defects_count": 0,
                "errors": ["Input defect markdown is empty."],
                "findings": [],
                "uninspected": UNINSPECTED_SURFACE,
            }

        # Check if text contains multiple defect headings
        defect_heading_pat = re.compile(
            r'(?m)^(#{1,4}\s+.*(?:\[DEFECT-\d+\]|\[P[0-3]:|\[(?:Critical|Important|Suggestion|Question)))',
            re.IGNORECASE,
        )
        matches = list(defect_heading_pat.finditer(text))

        chunks: List[str] = []
        if len(matches) > 1:
            for i in range(len(matches)):
                start = matches[i].start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                chunks.append(text[start:end])
        else:
            chunks = [text]

        findings: List[Dict[str, Any]] = []
        all_errors: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            finding = self.validate_defect_chunk(chunk, defect_index=idx)
            findings.append(finding)
            all_errors.extend(finding["errors"])

        is_valid = len(all_errors) == 0

        return {
            "source": source_name,
            "valid": is_valid,
            "defects_count": len(chunks),
            "errors": all_errors,
            "findings": findings,
            "uninspected": UNINSPECTED_SURFACE,
        }


def validate_defect(
    text: Optional[str] = None,
    file_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Programmatic helper to validate a defect markdown file or string."""
    validator = DefectValidator()
    if file_path is not None:
        p = Path(file_path).resolve()
        if not p.exists():
            return {
                "source": str(p),
                "valid": False,
                "defects_count": 0,
                "errors": [f"File not found: {p}"],
                "findings": [],
                "uninspected": UNINSPECTED_SURFACE,
            }
        content = p.read_text(encoding="utf-8")
        return validator.validate(content, source_name=str(p))
    elif text is not None:
        return validator.validate(text, source_name="<inline_text>")
    else:
        raise ValueError("Either 'text' or 'file_path' must be provided.")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build accurate command line interface parser (S6 compliant)."""
    parser = argparse.ArgumentParser(
        description="Defect Validator: Validates agent-authored markdown defect reports against Atomic Defect Schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to markdown defect file to validate.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Direct markdown text of defect report to validate.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress informational stdout output on success.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output validation results as structured JSON.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI execution entrypoint. Returns 0 if valid, 1 if malformed."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.file and args.text is None:
        sys.stderr.write("Error: Either --file or --text must be specified.\n")
        return 1

    validator = DefectValidator()

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"Error: File not found: {args.file}\n")
            return 1
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            sys.stderr.write(f"Error reading file '{args.file}': {exc}\n")
            return 1
        source_name = str(file_path)
    else:
        content = args.text
        source_name = "<inline_text>"

    result = validator.validate(content, source_name=source_name)

    if args.json:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    else:
        if result["valid"]:
            if not args.quiet:
                sys.stdout.write(
                    f"✓ Defect schema valid: {result['defects_count']} defect(s) checked. 0 errors.\n"
                )
                for f in result["findings"]:
                    loc_str = ", ".join(f.get("locations", [])) or "N/A"
                    sys.stdout.write(f"  • {f.get('id', 'DEFECT')}: {loc_str}\n")
                sys.stdout.write(f"  Uninspected: {', '.join(result['uninspected'])}\n")
        else:
            sys.stderr.write(
                f"✗ Defect schema validation failed ({len(result['errors'])} error(s)):\n"
            )
            for err in result["errors"]:
                sys.stderr.write(f"  - {err}\n")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
