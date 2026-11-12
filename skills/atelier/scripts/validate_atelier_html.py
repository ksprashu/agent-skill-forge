#!/usr/bin/env python3
"""Deterministic validator for Atelier HTML reports.

Always-on checks:
1. 100% balanced HTML tags (via HTMLParser).
2. SVG <text> clearance. When two labels' horizontal boxes come within 6px,
   their baselines must be at least 1.2x the larger font-size apart
   (design-principles.md). Ancestor translate() groups, px units, and
   per-line <tspan> positions are included. A coordinate this check cannot
   place is an error, not a skip.

Opt-in / persona-driven check:
3. Zero typographic em-dashes (—, &mdash;, &#8212;), enabled when
   --forbid-dashes is passed, when persona.json sets "forbid_dashes": true,
   or when the active voice_and_tone.md bans em-dashes (unless --allow-dashes
   is passed). En-dashes are ranges (18–30, R1–R6) and are allowed.
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


# design-principles.md: horizontal boxes within this gap must clear vertically.
_HORIZ_CLEARANCE_PX = 6.0
_VERT_BASELINE_FACTOR = 1.2
_CHAR_WIDTH_FACTOR = 0.56
_LENGTH_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")
_TRANSLATE_RE = re.compile(
    r"translate\(\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:px)?)"
    r"(?:\s*[, ]\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:px)?))?\s*\)",
    re.IGNORECASE,
)
_UNPLACEABLE_TRANSFORM_RE = re.compile(
    r"\b(?:matrix|rotate|scale|skewX|skewY)\s*\(",
    re.IGNORECASE,
)


def _local(elem) -> str:
    return elem.tag.split("}")[-1].lower()


def _style_map(elem) -> dict[str, str]:
    style = elem.attrib.get("style", "")
    parsed = {}
    for part in style.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        parsed[key.strip().lower()] = value.strip()
    return parsed


def _optional_unit(raw):
    """Return ``(value_or_None, ok)``. A missing value is ``(None, True)``."""
    if raw is None or str(raw).strip() == "":
        return None, True
    return _parse_user_unit(raw, None)


def _parse_user_unit(raw, default=None):
    """Parse an SVG user unit. ``px`` is accepted; ``%`` and other units are not.

    Returns ``(value, ok)``. A missing value uses ``default`` and is ok.
    """
    if raw is None or str(raw).strip() == "":
        if default is None:
            return 0.0, False
        return float(default), True
    text = str(raw).strip()
    if text.endswith("%"):
        return None, False
    if text.lower().endswith("px"):
        text = text[:-2].strip()
    if not _LENGTH_RE.match(text):
        return None, False
    return float(text), True


def _translation(transform: str):
    """Return ``(dx, dy, placeable)`` for a transform attribute.

    ``translate()`` is accumulated. rotate, scale, matrix, and skew cannot
    be placed by this axis-aligned check, so they are reported rather than
    treated as the identity (which would both false-pass and false-fail).
    """
    if not transform or not transform.strip():
        return 0.0, 0.0, True
    if _UNPLACEABLE_TRANSFORM_RE.search(transform):
        return 0.0, 0.0, False
    dx = dy = 0.0
    for match in _TRANSLATE_RE.finditer(transform):
        x_val, ok_x = _parse_user_unit(match.group(1), 0.0)
        if match.group(2) is None:
            y_val, ok_y = 0.0, True
        else:
            y_val, ok_y = _parse_user_unit(match.group(2), 0.0)
        if not (ok_x and ok_y):
            return 0.0, 0.0, False
        dx += x_val
        dy += y_val
    leftover = _TRANSLATE_RE.sub(" ", transform)
    if re.search(r"[A-Za-z]", leftover):
        return 0.0, 0.0, False
    return dx, dy, True


def _presentation(elem, name: str, default: str) -> str:
    style = _style_map(elem)
    raw = elem.attrib.get(name)
    if raw is None or raw == "":
        raw = style.get(name, default)
    return raw


def _font_size(elem):
    raw = _presentation(elem, "font-size", "12")
    return _parse_user_unit(raw, None)


def _anchor(elem) -> str:
    raw = _presentation(elem, "text-anchor", "start").strip().lower()
    if raw in ("middle", "end", "start"):
        return raw
    return "start"


class _Label:
    __slots__ = ("x0", "x1", "baseline", "fs", "text")

    def __init__(self, x, baseline, text, fs, anchor):
        width = len(text) * fs * _CHAR_WIDTH_FACTOR
        if anchor == "middle":
            self.x0, self.x1 = x - width / 2.0, x + width / 2.0
        elif anchor == "end":
            self.x0, self.x1 = x - width, x
        else:
            self.x0, self.x1 = x, x + width
        self.baseline = baseline
        self.fs = fs
        self.text = text


def _too_close(a: _Label, b: _Label) -> bool:
    """True when horizontal boxes are within 6px and baselines are under 1.2x."""
    gap = max(a.x0, b.x0) - min(a.x1, b.x1)
    if gap > _HORIZ_CLEARANCE_PX:
        return False
    need = _VERT_BASELINE_FACTOR * max(a.fs, b.fs)
    return abs(a.baseline - b.baseline) + 1e-9 < need


def _place_text(elem, origin_x, origin_y, placeable, labels, errors, svg_idx):
    preview = "".join(elem.itertext()).strip()[:35] or "(empty)"
    if not placeable:
        errors.append(
            f"SVG #{svg_idx}: cannot place text '{preview}' "
            f"(transform is not an axis-aligned translate)"
        )
        return
    own_x, ok_x = _parse_user_unit(elem.attrib.get("x"), 0.0)
    own_y, ok_y = _parse_user_unit(elem.attrib.get("y"), 0.0)
    if not (ok_x and ok_y):
        errors.append(
            f"SVG #{svg_idx}: text '{preview}' coordinate is not an absolute "
            f"user unit (x={elem.attrib.get('x')!r}, y={elem.attrib.get('y')!r})"
        )
        return
    fs, ok_fs = _font_size(elem)
    if not ok_fs or fs <= 0:
        errors.append(
            f"SVG #{svg_idx}: text '{preview}' font-size is not an absolute user unit"
        )
        return
    anchor = _anchor(elem)
    cursor_x = origin_x + own_x
    cursor_y = origin_y + own_y

    def add(text, x, y, line_fs, line_anchor):
        cleaned = text.strip()
        if cleaned:
            labels.append(_Label(x, y, cleaned, line_fs, line_anchor))

    if elem.text:
        add(elem.text, cursor_x, cursor_y, fs, anchor)
    for child in list(elem):
        if _local(child) != "tspan":
            if child.tail:
                add(child.tail, cursor_x, cursor_y, fs, anchor)
            continue
        line_fs, ok_line_fs = _font_size(child) if (
            child.attrib.get("font-size") or _style_map(child).get("font-size")
        ) else (fs, True)
        if not ok_line_fs or line_fs <= 0:
            errors.append(
                f"SVG #{svg_idx}: tspan font-size is not an absolute user unit"
            )
            return
        line_anchor = _anchor(child) if (
            child.attrib.get("text-anchor") or _style_map(child).get("text-anchor")
        ) else anchor
        sx, ok_sx = _optional_unit(child.attrib.get("x"))
        sy, ok_sy = _optional_unit(child.attrib.get("y"))
        sdx, ok_sdx = _parse_user_unit(child.attrib.get("dx"), 0.0)
        sdy, ok_sdy = _parse_user_unit(child.attrib.get("dy"), 0.0)
        if not (ok_sx and ok_sy and ok_sdx and ok_sdy):
            snippet = "".join(child.itertext()).strip()[:35] or "(empty)"
            errors.append(
                f"SVG #{svg_idx}: tspan '{snippet}' coordinate is not an absolute user unit"
            )
            return
        if sx is not None:
            cursor_x = origin_x + sx
        cursor_x += sdx
        if sy is not None:
            cursor_y = origin_y + sy
        cursor_y += sdy
        add(child.text or "", cursor_x, cursor_y, line_fs, line_anchor)
        if child.tail:
            add(child.tail, cursor_x, cursor_y, fs, anchor)


def _walk_svg(elem, anc_x, anc_y, anc_ok, labels, errors, svg_idx):
    if _local(elem) == "text":
        dx, dy, ok = _translation(elem.attrib.get("transform", ""))
        _place_text(elem, anc_x + dx, anc_y + dy, anc_ok and ok, labels, errors, svg_idx)
        return
    dx, dy, ok = _translation(elem.attrib.get("transform", ""))
    for child in list(elem):
        _walk_svg(child, anc_x + dx, anc_y + dy, anc_ok and ok, labels, errors, svg_idx)


def check_svg_text_collisions(html_text: str) -> list[str]:
    """Report SVG text labels that violate the 1.2x / 6px clearance rule."""
    collisions = []
    svg_blocks = re.findall(r"(<svg\b.*?</svg>)", html_text, flags=re.S | re.I)
    for idx, svg_raw in enumerate(svg_blocks, 1):
        # Named entities are not XML. Collapse them so the tree still parses;
        # width then uses the replacement length, which is conservative for "&amp;".
        clean_svg = re.sub(r"&[a-zA-Z0-9#]+;", "X", svg_raw)
        try:
            root = ET.fromstring(clean_svg)
        except ET.ParseError as exc:
            collisions.append(f"SVG #{idx}: XML parse error: {exc}")
            continue

        labels = []
        _walk_svg(root, 0.0, 0.0, True, labels, collisions, idx)
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = labels[i], labels[j]
                if _too_close(a, b):
                    collisions.append(
                        f"SVG #{idx} text collision: '{a.text[:35]}' "
                        f"(baseline={a.baseline:g}) overlaps '{b.text[:35]}' "
                        f"(baseline={b.baseline:g}); need "
                        f"{_VERT_BASELINE_FACTOR:g}x font-size vertical separation "
                        f"when horizontal boxes are within {_HORIZ_CLEARANCE_PX:g}px"
                    )
    return collisions


def validate_file(path: pathlib.Path, forbid_dashes: bool | None = None) -> list[str]:
    if forbid_dashes is None:
        forbid_dashes = detect_persona_forbids_dashes()

    errors = []
    text = path.read_text(encoding="utf-8")

    if forbid_dashes:
        em_count = text.count("\u2014") + text.count("&mdash;") + text.count("&#8212;")
        if em_count > 0:
            errors.append(f"Dash check failed: {em_count} em-dashes")

    parser = HTMLTagValidator()
    parser.feed(text)
    if parser.errors or parser.stack:
        errors.extend(parser.errors)
        if parser.stack:
            errors.append(f"Unclosed HTML tags: {parser.stack}")

    errors.extend(check_svg_text_collisions(text))
    return errors


def configure_stdio() -> None:
    """UTF-8 stdout/stderr on Windows so SVG excerpts do not crash cp1252."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    ap = argparse.ArgumentParser(description="Validate Atelier HTML reports.")
    dash_group = ap.add_mutually_exclusive_group()
    dash_group.add_argument(
        "--forbid-dashes",
        action="store_true",
        help="Fail on typographic em-dashes (en-dashes in ranges are allowed).",
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
        try:
            errs = validate_file(p, forbid_dashes=forbid_dashes)
        except OSError as exc:
            any_err = True
            print(f"FAIL {p}: {exc.strerror or exc}", file=sys.stderr)
            continue
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
