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
render.py - Compile a validated profile into harness configuration files.

Everything in the output is derived from the profile. There is no default
persona hiding in the templates: an axis left 'unknown' produces no
instruction at all, rather than a plausible-sounding guess. Two different
profiles cannot render the same file, and a test enforces that.

Each generated file carries a provenance footer stating how many of its
claims were observed in logs, declared by the user, or merely inferred --
so the person living with these rules can see exactly how much of it was
actually earned.

CLI:
    render.py profile.json -o .                    # write all harnesses
    render.py profile.json -t claude -o ~/repo     # one harness
    render.py profile.json --dry-run               # print, write nothing
    render.py profile.json --check -o .            # CI: are files current?
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import profile_tool as profile_mod  # noqa: E402  (local module, path set above)

if sys.platform == "win32":  # pragma: no cover - platform guard
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Harness -> (output filename, template filename)
HARNESSES = {
    "claude": ("CLAUDE.md", "claude.md.tmpl"),
    "antigravity": ("GEMINI.md", "gemini.md.tmpl"),
    "gemini-cli": ("GEMINI.md", "gemini.md.tmpl"),
    "agents": ("AGENTS.md", "agents.md.tmpl"),
    "cursor": (".cursorrules", "cursorrules.tmpl"),
    "windsurf": (".windsurfrules", "cursorrules.tmpl"),
    "codex": ("AGENTS.md", "agents.md.tmpl"),
    "system": ("system_prompt.md", "system_prompt.md.tmpl"),
}

TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

# ---------------------------------------------------------------------------
# Band -> directive
#
# Deliberately opposed at the extremes. If 'low' and 'high' produced similar
# text, the dimension would not be worth measuring and the rendered configs
# would converge on one house style regardless of who they describe.
# ---------------------------------------------------------------------------

BAND_TEXT = {
    "visual_scaffolding": {
        "high": "Lead with structure. Any choice between options goes in a "
                "comparison table; any non-obvious system shape gets a diagram. "
                "Prose supports the visual, not the other way round.",
        "medium": "Use a table or diagram only where it genuinely compresses "
                  "the explanation. Default to prose and code.",
        "low": "Do not produce diagrams. Carry structure in code, data shapes, "
               "or a plain list. A flowchart of a linear process is noise.",
    },
    "text_density": {
        "high": "Break text up aggressively. Short paragraphs, lead-in bolding "
                "on list items, and a horizontal rule between major sections.",
        "medium": "Keep paragraphs tight, but continuous prose is fine where "
                  "the argument needs to flow.",
        "low": "Write in full paragraphs. Do not fragment an argument into "
               "bullet points just to shorten lines.",
    },
    "orientation_need": {
        "high": "Open with one line of context and one line naming the actual "
                "problem, before any detail or diagram.",
        "medium": "A brief framing sentence is welcome when the topic is new; "
                  "skip it on follow-ups.",
        "low": "Start at the answer. No restating the question, no summary of "
               "what you are about to do.",
    },
    "metaphor_affinity": {
        "high": "Ground abstractions in physical comparisons, and give opaque "
                "jargon a concrete nickname the first time it appears.",
        "medium": "Reach for an analogy when a concept is genuinely unfamiliar; "
                  "otherwise use the real terms.",
        "low": "No analogies. Name the real mechanism with its real vocabulary "
               "and assume the reader knows the field.",
    },
    "decision_directness": {
        "high": "Make the call. Give one recommendation up front and then "
                "defend it. Do not present a menu.",
        "medium": "Recommend one option, but show the runner-up and why it "
                  "lost.",
        "low": "Lay out the viable options with their trade-offs and let the "
               "decision stay with the reader.",
    },
    "evidence_depth": {
        "high": "Model the full picture: every cost line rather than one, plus "
                "second-order effects and the failure modes that bite later.",
        "medium": "Give the headline answer with the trade-offs that actually "
                  "change the decision.",
        "low": "Answer the question asked. Do not append exhaustive cost "
               "models or edge-case inventories unless requested.",
    },
}

LIMIT_TEXT = {
    "response_ceiling_words": "Keep responses under roughly {v} words unless "
                              "asked to go deeper.",
    "sentences_per_bullet": "At most {v} sentence(s) per list item.",
    "bullets_per_section": "At most {v} list items per section; split or cut "
                           "beyond that.",
    "code_fold_threshold": "Collapse code and diffs longer than {v} lines "
                           "behind a `<details>` block.",
}

SCOPE_HEADING = {
    "always": "Always",
    "architecture": "Architecture and design",
    "debugging": "Debugging and incident work",
    "learning": "Explanations and concept work",
    "review": "Code review",
    "cost": "Cost and capacity analysis",
    "writing": "Prose and documentation",
}


class RenderError(Exception):
    """Raised when a profile cannot be turned into a usable config."""


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------


def _band(prof, name):
    entry = prof.get("dimensions", {}).get(name, {})
    band = entry.get("band", "unknown")
    return band if band in ("low", "medium", "high") else None


def _line(prof, name):
    """One directive for a dimension, or None if the axis is unknown."""
    band = _band(prof, name)
    if band is None:
        return None
    text = BAND_TEXT[name][band]
    if prof["dimensions"][name].get("source") == "inferred":
        text += " *(inferred, not yet confirmed)*"
    return text


def _bullets(lines):
    return "\n".join(f"- {line}" for line in lines if line)


def build_tone_block(prof):
    lines = []
    tone = prof.get("tone", {})
    default = (tone.get("default") or "").strip()
    if default:
        lines.append(f"Default register: {default}")
    for context, text in sorted(tone.items()):
        if context == "default" or not str(text).strip():
            continue
        lines.append(f"{SCOPE_HEADING.get(context, context.title())}: {text.strip()}")
    metaphor = _line(prof, "metaphor_affinity")
    if metaphor:
        lines.append(metaphor)
    return _bullets(lines) or "_No tone preferences established yet._"


def build_formatting_block(prof):
    lines = [_line(prof, "text_density"), _line(prof, "orientation_need")]
    limits = prof.get("limits", {})
    for name, template in LIMIT_TEXT.items():
        value = limits.get(name)
        if value is not None:
            lines.append(template.format(v=value))
    return _bullets(lines) or "_No formatting preferences established yet._"


def build_visual_block(prof):
    return _bullets([_line(prof, "visual_scaffolding")]) or \
        "_No preference established for diagrams and tables._"


def build_analysis_block(prof):
    lines = [_line(prof, "decision_directness"), _line(prof, "evidence_depth")]
    return _bullets(lines) or "_No preference established for depth of analysis._"


def _rules_by_scope(items):
    """Render a rule list grouped under its scope headings.

    Shared by the rules and forbidden blocks. They used to be written out
    separately and the forbidden one dropped both the scope grouping and the
    *(inferred)* suffix -- so a guessed prohibition read as a hard rule, while
    the provenance footer below it promised that every inferred item was
    marked. The reader had no way to tell which prohibitions were earned.
    """
    by_scope = {}
    for rule in items:
        by_scope.setdefault(rule.get("scope", "always"), []).append(rule)

    parts = []
    for scope in profile_mod.SCOPES:
        bucket = by_scope.get(scope)
        if not bucket:
            continue
        parts.append(f"**{SCOPE_HEADING.get(scope, scope.title())}**")
        for rule in bucket:
            suffix = " *(inferred)*" if rule.get("source") == "inferred" else ""
            parts.append(f"- {rule['directive'].rstrip('.')}.{suffix}")
        parts.append("")
    return "\n".join(parts).strip()


def build_rules_block(prof):
    rules = prof.get("rules", [])
    if not rules:
        return "_No specific rules recorded._"
    return _rules_by_scope(rules)


def build_forbidden_block(prof):
    items = prof.get("forbidden", [])
    if not items:
        return "_Nothing recorded as off-limits yet._"
    return _rules_by_scope(items)


def build_provenance_block(prof):
    """The honesty footer. Anyone reading a generated config can see how much
    of it came from evidence and how much is still guesswork."""
    cov = profile_mod.coverage(prof)
    unknowns = prof.get("unknowns", [])
    lines = [
        f"Compiled from a profile of {cov['claims_total']} claims: "
        f"{cov['observed']} observed in logs, {cov['declared']} stated directly, "
        f"{cov['inferred']} inferred ({cov['grounded_pct']}% grounded in evidence)."
    ]
    if unknowns:
        readable = ", ".join(u.replace("_", " ") for u in sorted(unknowns))
        lines.append(f"Still unknown, so deliberately unconstrained: {readable}. "
                     f"Use your own judgement there and ask if it matters.")
    if cov["inferred"]:
        lines.append("Items marked *(inferred)* were reasoned about, not "
                     "observed. Correct them and they will be replaced.")
    if cov["unattributed"]:
        lines.append(
            f"{cov['unattributed']} of those are tone settings and numeric "
            f"limits. The profile format has nowhere to record where they came "
            f"from, so treat them as unsourced and say so if one is wrong.")
    return "\n\n".join(lines)


BLOCK_BUILDERS = {
    "TONE_BLOCK": build_tone_block,
    "FORMATTING_BLOCK": build_formatting_block,
    "VISUAL_BLOCK": build_visual_block,
    "ANALYSIS_BLOCK": build_analysis_block,
    "RULES_BLOCK": build_rules_block,
    "FORBIDDEN_BLOCK": build_forbidden_block,
    "PROVENANCE_BLOCK": build_provenance_block,
}


def build_tokens(prof):
    tokens = {name: fn(prof) for name, fn in BLOCK_BUILDERS.items()}
    tokens["SUBJECT"] = prof.get("subject", "the user")
    tokens["GENERATED"] = prof.get("generated", "")
    return tokens


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_one(prof, harness, tokens=None):
    if harness not in HARNESSES:
        raise RenderError(f"unknown harness {harness!r}; expected one of "
                          f"{', '.join(sorted(HARNESSES))}")
    filename, template_name = HARNESSES[harness]
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise RenderError(f"missing template: {template_path}")

    tokens = tokens or build_tokens(prof)
    text = template_path.read_text(encoding="utf-8")
    text = TOKEN_RE.sub(lambda m: tokens.get(m.group(1), m.group(0)), text)

    leftover = sorted(set(TOKEN_RE.findall(text)))
    if leftover:
        raise RenderError(f"{template_name} has tokens with no value: "
                          f"{', '.join(leftover)}")
    return filename, text


def render_all(prof, harnesses=None):
    """Return {filename: content}. Harnesses sharing a filename must agree."""
    tokens = build_tokens(prof)
    out = {}
    for harness in (harnesses or sorted(HARNESSES)):
        filename, text = render_one(prof, harness, tokens)
        out[filename] = text
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compile a validated profile into harness config files.")
    parser.add_argument("profile", help="path to profile.json")
    parser.add_argument("-t", "--harness", action="append",
                        choices=sorted(HARNESSES),
                        help="target harness; repeatable (default: all)")
    parser.add_argument("-o", "--output-dir", default=".")
    parser.add_argument("-e", "--evidence", help="evidence.json, to resolve quote IDs")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written")
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if files on disk are stale")
    parser.add_argument("--force", action="store_true",
                        help="render even if the profile fails validation")
    args = parser.parse_args(argv)

    try:
        prof = profile_mod.load(args.profile)
    except profile_mod.ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    evidence = None
    if args.evidence:
        try:
            evidence = profile_mod.load(args.evidence)
        except profile_mod.ProfileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    errors, warnings = profile_mod.validate(prof, evidence)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"error:   {e}", file=sys.stderr)
        if not args.force:
            print("\nRefusing to render an invalid profile. Fix the errors, or "
                  "pass --force if you know what you are doing.", file=sys.stderr)
            return 1

    try:
        outputs = render_all(prof, args.harness)
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir)

    if args.dry_run:
        for filename, text in sorted(outputs.items()):
            print(f"===== {out_dir / filename} " + "=" * 20)
            print(text)
        return 0

    if args.check:
        stale = []
        for filename, text in sorted(outputs.items()):
            target = out_dir / filename
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != text:
                stale.append(filename)
                diff = difflib.unified_diff(
                    current.splitlines(), text.splitlines(),
                    fromfile=f"{filename} (on disk)", tofile=f"{filename} (expected)",
                    lineterm="")
                print("\n".join(diff))
        if stale:
            print(f"\n{len(stale)} file(s) out of date: {', '.join(stale)}",
                  file=sys.stderr)
            return 1
        print("All harness configs are current")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in sorted(outputs.items()):
        (out_dir / filename).write_text(text, encoding="utf-8")
        print(f"Wrote {out_dir / filename}")

    cov = profile_mod.coverage(prof)
    if cov["inferred"] or cov["unknown_dimensions"]:
        print(f"\nNote: {cov['inferred']} inferred claim(s) and "
              f"{cov['unknown_dimensions']} unknown dimension(s) are marked as "
              f"such in the output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
