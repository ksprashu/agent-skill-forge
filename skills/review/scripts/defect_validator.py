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
  Section headings must be markdown headings or bold labels; fenced code is ignored when
  looking for them.
- Non-blocking entries ([P3: ...], [Suggestion], [Question]) need only the badge and a location.
- Accepts a single defect or a whole Mode A / Mode B report; a report with zero defect
  entries is valid.
- A stated Review Status / Certification Verdict must match the defects: APPROVED or
  CONDITIONALLY APPROVED with an open P0/P1, or CERTIFIED with an open P0-P2, fails.

In strict compliance with docs/ENGINEERING_STANDARD.md:
- S1: Python 3.12, stdlib only (sys, argparse, re, pathlib, typing, json).
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

# A section heading is a markdown heading (optionally numbered, e.g. "#### 2. ") or a bold /
# underscored label at the start of a line ("**Impact**", "- **Fix:**"). The prefix is
# mandatory: plain prose that happens to start with "Description" or "Fix" is not a heading.
_HEADING_PREFIX = r'(?m)^[ \t]*(?:#{1,6}[ \t]+(?:\d+[.)][ \t]*)?|(?:[-*][ \t]+)?(?:\*{1,2}|_{1,2}))'


def _section_pattern(alternatives: str) -> re.Pattern[str]:
    return re.compile(_HEADING_PREFIX + r'(?:' + alternatives + r')\b', re.IGNORECASE)


# Required sections definition
REQUIRED_SECTIONS: List[Dict[str, Any]] = [
    {
        "name": "Description",
        "pattern": _section_pattern(
            r'Vulnerability\s*/\s*Defect\s+Description|Vulnerability\s+Description'
            r'|Defect\s+Description|Description'
        ),
        "aliases": ["Description", "Vulnerability Description", "Vulnerability / Defect Description"],
    },
    {
        "name": "Blast Radius",
        "pattern": _section_pattern(r'Blast\s+Radius|Impact'),
        "aliases": ["Blast Radius", "Impact"],
    },
    {
        "name": "Empirical Proof",
        "pattern": _section_pattern(r'Empirical\s+Proof|Reproduction|Proof\s+of\s+Concept|PoC|Repro'),
        "aliases": ["Empirical Proof", "Reproduction"],
    },
    {
        "name": "Drop-in Remediation",
        "pattern": _section_pattern(
            r'Drop-in\s+Remediation|Proposed\s+Fix|Proposed\s+Remediation|Remediation|Fix'
        ),
        "aliases": ["Drop-in Remediation", "Proposed Fix"],
    },
    {
        "name": "Verification Gate",
        "pattern": _section_pattern(r'Verification\s+Gate|Verification\s+Command|Verification'),
        "aliases": ["Verification Gate", "Verification command"],
    },
]

# Headings that open a defect entry. Searched on fence-masked text, so a "# [DEFECT-1]"
# comment inside a code block never opens an entry.
DEFECT_HEADING_PATTERN = re.compile(
    r'(?m)^(#{1,6})[ \t]+.*?(?:\[DEFECT-\d+\]|\[P[0-3]:|\[(?:Critical|Important|Suggestion|Question))',
    re.IGNORECASE,
)
ANY_HEADING_PATTERN = re.compile(r'(?m)^(#{1,6})[ \t]')

# Non-blocking entries (schemas.md severity table, conduct.md Rule 6 and 3.1) carry a badge
# and a location but no Blast Radius / Proof / Remediation / Verification Gate.
LIGHT_BADGE_PATTERN = re.compile(r'\[(?:P3:[^\]]*|Suggestion[^\]]*|Question[^\]]*)\]', re.IGNORECASE)
BLOCKING_BADGE_PATTERN = re.compile(r'\[(?:P[0-2]:[^\]]*|Critical[^\]]*|Important[^\]]*)\]', re.IGNORECASE)

# Report verdict lines (schemas.md Mode A / Mode B templates). A template line that still
# lists the options ("[ A | B ]") is not a verdict.
VERDICT_PATTERN = re.compile(
    r'(?im)^[ \t]*[-*]?[ \t]*\**[ \t]*(Review\s+Status|Certification\s+Verdict|Overall\s+Verdict)'
    r'[ \t]*:?\**[ \t]*:?[ \t]*(.+)$'
)


def severity_rank(heading: str) -> Optional[int]:
    """0-3 from a defect heading's badge ([P0:] .. [P3:], [Critical]=0, [Important]=2)."""
    m = re.search(r'\[P([0-3]):', heading, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if re.search(r'\[Critical', heading, re.IGNORECASE):
        return 0
    if re.search(r'\[Important', heading, re.IGNORECASE):
        return 2
    if re.search(r'\[(?:Suggestion|Question)', heading, re.IGNORECASE):
        return 3
    return None


def verdict_errors(text: str, ranks: List[Optional[int]]) -> List[str]:
    """A stated verdict must agree with the defects in the report (schemas.md section 1,
    workflows.md Pass 4): APPROVED / CONDITIONALLY APPROVED need zero P0/P1, CERTIFIED
    needs zero P0-P2."""
    errors: List[str] = []
    p01 = sum(1 for r in ranks if r is not None and r <= 1)
    p2 = sum(1 for r in ranks if r == 2)
    for m in VERDICT_PATTERN.finditer(mask_fences(text)):
        label, value = m.group(1), m.group(2).strip("*` []").upper()
        if "|" in value:
            continue
        if "CERTIFIED" in value and (p01 or p2):
            errors.append(f"{label} is CERTIFIED but the report has {p01} P0/P1 and {p2} P2 defect(s).")
        elif "APPROVED" in value and p01:
            errors.append(f"{label} is {value} but the report has {p01} open P0/P1 defect(s).")
    return errors


_FENCE_OPEN = re.compile(r'^[ \t]{0,3}(`{3,}|~{3,})')


def fenced_blocks(text: str) -> List[Tuple[int, int, int, bool]]:
    """Return (block_start, content_start, content_end, closed) for each fenced code block.

    Follows CommonMark: a fence closes on a line of the same character, at least as long
    as the opener; an unclosed fence runs to the end of the text.
    """
    blocks: List[Tuple[int, int, int, bool]] = []
    offset = 0
    fence: Optional[str] = None
    block_start = content_start = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if fence is None:
            m = _FENCE_OPEN.match(bare)
            if m:
                fence = m.group(1)
                block_start, content_start = offset, offset + len(line)
        else:
            stripped = bare.strip()
            if (len(bare) - len(bare.lstrip(" \t")) <= 3 and stripped
                    and set(stripped) == {fence[0]} and len(stripped) >= len(fence)):
                blocks.append((block_start, content_start, offset, True))
                fence = None
        offset += len(line)
    if fence is not None:
        blocks.append((block_start, content_start, len(text), False))
    return blocks


def mask_fences(text: str) -> str:
    """Blank out fenced code content (keeping offsets and newlines) so headings are found
    only in prose. Fence lines themselves are kept."""
    chars = list(text)
    for _, content_start, content_end, _ in fenced_blocks(text):
        for i in range(content_start, content_end):
            if chars[i] not in "\r\n":
                chars[i] = " "
    return "".join(chars)


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
        masked = mask_fences(chunk)
        heading_line = masked.lstrip().split("\n", 1)[0]
        light = bool(LIGHT_BADGE_PATTERN.search(heading_line)) and not BLOCKING_BADGE_PATTERN.search(heading_line)

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

        # A second Description heading means a following defect lost its ID/badge heading
        # and was merged into this one.
        descriptions = len(REQUIRED_SECTIONS[0]["pattern"].findall(masked))
        if descriptions > 1:
            errors.append(
                f"Defect {defect_index}: contains {descriptions} Description sections; "
                "each defect needs its own heading with a Defect ID or badge."
            )

        # 3. Required sections (P3 / Suggestion / Question entries are non-blocking: badge
        # and location only)
        rem_match: Optional[re.Match[str]] = None
        section_starts: List[int] = []
        for sec in REQUIRED_SECTIONS if not light else []:
            sec_name = sec["name"]
            match = sec["pattern"].search(masked)
            if not match:
                aliases_str = " / ".join(sec["aliases"])
                errors.append(
                    f"Defect {defect_index}: Missing required section '{sec_name}'. "
                    f"Expected heading matching '{aliases_str}'."
                )
            elif sec_name == "Drop-in Remediation":
                rem_match = match
            else:
                section_starts.extend(m.start() for m in sec["pattern"].finditer(masked))

        # 4. Code block in Drop-in Remediation. The section ends at the next markdown
        # heading or the next required-section label, found in prose only.
        if rem_match is not None:
            rem_start = rem_match.end()
            ends = [s for s in section_starts if s > rem_start]
            next_heading = ANY_HEADING_PATTERN.search(masked, rem_start)
            if next_heading:
                ends.append(next_heading.start())
            rem_end = min(ends) if ends else len(chunk)
            code_blocks = [
                chunk[cs:ce] for bs, cs, ce, closed in fenced_blocks(chunk)
                if closed and rem_start <= bs < rem_end
            ]
            if not code_blocks:
                errors.append(
                    f"Defect {defect_index}: 'Drop-in Remediation / Proposed Fix' section must contain "
                    "a fenced code block (``` ... ```) with proposed code or before/after comparison."
                )
            elif not any(b.strip() for b in code_blocks):
                errors.append(
                    f"Defect {defect_index}: 'Drop-in Remediation' code block is empty."
                )

        is_valid = len(errors) == 0
        return {
            "index": defect_index,
            "id": defect_id or f"DEFECT-{defect_index:03d}" if is_valid else (defect_id or "UNKNOWN"),
            "badge": badge,
            "tier": "non-blocking" if light else "blocking",
            "locations": locations,
            "valid": is_valid,
            "errors": errors,
        }

    def split_defects(self, text: str) -> Tuple[List[str], List[str]]:
        """Split a defect file or a whole review report into defect chunks.

        Returns (chunks, errors). A chunk runs from a defect heading to the next defect
        heading or the next heading at the same or a higher level. Text with no defect
        heading is one chunk if it contains defect sections, else it is a report with
        zero defects.
        """
        masked = mask_fences(text)
        heads = list(DEFECT_HEADING_PATTERN.finditer(masked))
        has_sections = any(sec["pattern"].search(masked) for sec in REQUIRED_SECTIONS)
        if not heads:
            return ([text] if has_sections else []), []

        errors: List[str] = []
        preamble = masked[:heads[0].start()]
        if REQUIRED_SECTIONS[0]["pattern"].search(preamble):
            errors.append(
                "Defect sections appear before the first defect heading; "
                "that defect is missing its Defect ID or badge heading."
            )
        chunks: List[str] = []
        for i, head in enumerate(heads):
            level = len(head.group(1))
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            for h in ANY_HEADING_PATTERN.finditer(masked, head.end(), end):
                if len(h.group(1)) <= level:
                    end = h.start()
                    break
            chunks.append(text[head.start():end])
        return chunks, errors

    def validate(self, text: str, source_name: str = "<input>") -> Dict[str, Any]:
        """Validate markdown text: one defect, several, or a whole review/audit report."""
        if not text or not text.strip():
            return {
                "source": source_name,
                "valid": False,
                "defects_count": 0,
                "errors": ["Input defect markdown is empty."],
                "findings": [],
                "uninspected": UNINSPECTED_SURFACE,
            }

        chunks, all_errors = self.split_defects(text)
        findings: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks, start=1):
            finding = self.validate_defect_chunk(chunk, defect_index=idx)
            findings.append(finding)
            all_errors.extend(finding["errors"])
        all_errors.extend(verdict_errors(
            text, [severity_rank(mask_fences(c).lstrip().split("\n", 1)[0]) for c in chunks]))

        return {
            "source": source_name,
            "valid": not all_errors,
            "defects_count": len(chunks),
            "errors": all_errors,
            "findings": findings,
            "uninspected": UNINSPECTED_SURFACE,
        }


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
