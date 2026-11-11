#!/usr/bin/env python3
"""Deterministic validator for Atelier HTML reports.

Always-on checks:
1. 100% balanced HTML tags (via HTMLParser).
2. Zero overlapping <text> bounding boxes inside any inline <svg> diagram.

Opt-in / persona-driven check:
3. Zero typographic em-dashes or en-dashes (including &mdash; / &ndash;),
   enabled when --forbid-dashes is passed, when persona.json sets
   "forbid_dashes": true, or when the active voice_and_tone.md bans em-dashes
   (unless --allow-dashes is passed).
"""

import argparse
import json
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class HTMLTagValidator(HTMLParser):
    VOID = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(
                f"Tag mismatch: closing </{tag}> when stack top is "
                f"{self.stack[-1] if self.stack else None}"
            )
        else:
            self.stack.pop()


def _persona_dir() -> pathlib.Path:
    override = os.environ.get("AGENT_PERSONA_DIR")
    if override:
        return pathlib.Path(override).expanduser()
    env_home = os.environ.get("HOME")
    home = pathlib.Path(env_home) if env_home else pathlib.Path.home()
    return home / ".gemini" / "personas"


def detect_persona_forbids_dashes(pdir: pathlib.Path | None = None) -> bool:
    """Return True if persona.json or default/voice_and_tone.md forbids em-dashes."""
    root = pdir if pdir is not None else _persona_dir()
    persona_json = root / "persona.json"
    if persona_json.is_file():
        try:
            data = json.loads(persona_json.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "forbid_dashes" in data:
                return bool(data["forbid_dashes"])
        except (OSError, ValueError):
            pass

    voice_md = root / "default" / "voice_and_tone.md"
    if voice_md.is_file():
        try:
            vtxt = voice_md.read_text(encoding="utf-8")
            if re.search(
                r"(no\s+typographic\s+em-dashes|never\s+use\s+[`'\"]?\u2014|forbid[_\s-]dashes)",
                vtxt,
                flags=re.I,
            ):
                return True
        except OSError:
            pass
    return False


def check_svg_text_collisions(html_text: str) -> list[str]:
    """Detect overlapping <text> bounding boxes inside inline <svg> elements."""
    collisions = []
    svg_blocks = re.findall(r"(<svg\b.*?</svg>)", html_text, flags=re.S | re.I)
    for idx, svg_raw in enumerate(svg_blocks, 1):
        clean_svg = re.sub(r"&[a-zA-Z0-9#]+;", "X", svg_raw)
        try:
            root = ET.fromstring(clean_svg)
        except ET.ParseError as exc:
            collisions.append(f"SVG #{idx}: XML parse error: {exc}")
            continue

        boxes = []
        for elem in root.iter():
            tag_name = elem.tag.split("}")[-1]
            if tag_name != "text":
                continue
            transform = elem.attrib.get("transform", "")
            if "rotate" in transform:
                continue
            try:
                x = float(elem.attrib.get("x", "0"))
                y = float(elem.attrib.get("y", "0"))
            except ValueError:
                continue
            fs_str = elem.attrib.get("font-size", "12").replace("px", "")
            try:
                fs = float(fs_str)
            except ValueError:
                fs = 12.0
            anchor = elem.attrib.get("text-anchor", "start")
            text_content = "".join(elem.itertext()).strip()
            if not text_content:
                continue
            est_width = len(text_content) * fs * 0.56
            if anchor == "middle":
                x0, x1 = x - est_width / 2.0, x + est_width / 2.0
            elif anchor == "end":
                x0, x1 = x - est_width, x
            else:
                x0, x1 = x, x + est_width
            y0, y1 = y - fs * 0.85, y + fs * 0.2
            boxes.append((x0, y0, x1, y1, text_content, x, y))

        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ax0, ay0, ax1, ay1, atxt, ax, ay = boxes[i]
                bx0, by0, bx1, by1, btxt, bx, by = boxes[j]
                horiz_overlap = min(ax1, bx1) - max(ax0, bx0)
                vert_overlap = min(ay1, by1) - max(ay0, by0)
                if horiz_overlap > 6.0 and vert_overlap > 1.5:
                    collisions.append(
                        f"SVG #{idx} text collision: '{atxt[:35]}' (x={ax}, y={ay}) "
                        f"overlaps '{btxt[:35]}' (x={bx}, y={by})"
                    )
    return collisions


def validate_file(path: pathlib.Path, forbid_dashes: bool | None = None) -> list[str]:
    if forbid_dashes is None:
        forbid_dashes = detect_persona_forbids_dashes()

    errors = []
    text = path.read_text(encoding="utf-8")

    if forbid_dashes:
        em_count = text.count("\u2014") + text.count("&mdash;") + text.count("&#8212;")
        en_count = text.count("\u2013") + text.count("&ndash;") + text.count("&#8211;")
        if em_count > 0 or en_count > 0:
            errors.append(f"Dash check failed: {em_count} em-dashes, {en_count} en-dashes")

    parser = HTMLTagValidator()
    parser.feed(text)
    if parser.errors or parser.stack:
        errors.extend(parser.errors)
        if parser.stack:
            errors.append(f"Unclosed HTML tags: {parser.stack}")

    errors.extend(check_svg_text_collisions(text))
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate Atelier HTML reports.")
    dash_group = ap.add_mutually_exclusive_group()
    dash_group.add_argument(
        "--forbid-dashes",
        action="store_true",
        help="Fail on typographic em-dashes or en-dashes.",
    )
    dash_group.add_argument(
        "--allow-dashes",
        action="store_true",
        help="Skip typographic dash checks even if an active persona forbids them.",
    )
    ap.add_argument("files", nargs="+", help="HTML report file(s) to validate.")
    args = ap.parse_args(argv)

    if args.forbid_dashes:
        forbid_dashes = True
    elif args.allow_dashes:
        forbid_dashes = False
    else:
        forbid_dashes = detect_persona_forbids_dashes()

    any_err = False
    for raw_file in args.files:
        p = pathlib.Path(raw_file)
        errs = validate_file(p, forbid_dashes=forbid_dashes)
        if errs:
            any_err = True
            print(f"FAIL {p.name}:")
            for e in errs:
                print(f"  - {e}")
        else:
            dash_note = "0 dash violations, " if forbid_dashes else ""
            print(f"PASS {p.name}: {dash_note}100% balanced HTML, 0 SVG text collisions")
    return 1 if any_err else 0


if __name__ == "__main__":
    sys.exit(main())
