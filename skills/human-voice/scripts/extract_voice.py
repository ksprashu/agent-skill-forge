#!/usr/bin/env python3
# Copyright 2026 Google LLC
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

import os
import re
import sys
import platform
import argparse
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import log_sources  # noqa: E402  (bundled beside this script; shared with cognitive-profiler)

HOME = os.path.expanduser('~')

# Log locations per tool, from log_sources. Each value is a list of paths.
PATHS = log_sources.tool_paths()

# Redaction rows added for this run (--internal-domain). The built-in table is
# log_sources.SENSITIVE_PATTERNS, shared with cognitive-profiler.
EXTRA_PATTERNS = []


def add_internal_domains(domains):
    """Redact URLs and hostnames under the given domains (e.g. an employer's intranet).

    Nothing employer-specific ships with this skill; pass yours with --internal-domain.
    """
    EXTRA_PATTERNS.extend(log_sources.internal_domain_patterns(domains))


COMMONWEALTH_WORDS = [
    "colour", "behaviour", "customisation", "optimise", "prioritise", "organisation",
    "modelling", "visualise", "customise"
]


def sanitize_text(text, extra_names=None):
    """Scrubs secrets, PII, internal hosts, your login name, and any supplied names."""
    names = [(log_sources.login_name(), log_sources.USER_ID)] + list(extra_names or [])
    return log_sources.redact(text, log_sources.name_patterns(names), domains=EXTRA_PATTERNS)


def _roots(tool):
    value = PATHS.get(tool)
    if not value:
        return []
    if isinstance(value, (str, os.PathLike)):
        value = [value]
    return [Path(v) for v in value]


def _user_prompts(tools, extra_names=None):
    """Redacted user turns from every existing location of the named tools."""
    prompts = []
    for tool in tools:
        reader = log_sources.READERS[tool]
        for root in _roots(tool):
            if not root.exists():
                continue
            for session in reader(root):
                for turn in session.turns:
                    if turn.role != "user":
                        continue
                    text = sanitize_text(turn.text, extra_names=extra_names).strip()
                    if text:
                        prompts.append(text)
    return prompts


def extract_antigravity(extra_names=None, surfaces=("antigravity-ide", "antigravity-cli")):
    """Extracts from Antigravity transcript.jsonl files.

    ``surfaces`` names which of the two brains to read. It defaults to both,
    which is what ``--tool antigravity`` means; ``--tool antigravity-cli`` asks
    for the CLI only, and a filter that silently widens is not a filter.
    """
    return _user_prompts(surfaces, extra_names)


def extract_antigravity_cli(extra_names=None):
    return extract_antigravity(extra_names=extra_names, surfaces=("antigravity-cli",))


def extract_antigravity_ide(extra_names=None):
    return extract_antigravity(extra_names=extra_names, surfaces=("antigravity-ide",))


def extract_gemini_cli(extra_names=None):
    """Extracts from gemini-cli chat files under ~/.gemini/tmp."""
    return _user_prompts(("gemini-cli",), extra_names)


def extract_claude_code(extra_names=None):
    """Extracts from Claude Code sessions: ~/.claude/projects/<slug>/<session>.jsonl."""
    return _user_prompts(("claude-code",), extra_names)


def extract_cline_and_roo_code(extra_names=None, tools=("cline", "roo-code")):
    """Extracts from Cline and Roo Code ui_messages.json files."""
    return _user_prompts(tools, extra_names)


def extract_aider(extra_names=None):
    """Extracts from aider chat transcripts and input histories."""
    return _user_prompts(("aider",), extra_names)


def extract_cursor(extra_names=None):
    """Extracts from Cursor's state.vscdb SQLite store, opened read-only."""
    return _user_prompts(("cursor",), extra_names)


def _rate(hits, total):
    return f"{int(hits / total * 100)}%" if total else "0%"


def analyze_linguistics(prompts):
    """Counts spelling, punctuation and length habits. Measures only; draws no persona.

    How someone reacts to AI output is cognitive-profiler's job, not this script's.
    """
    stats = {
        "total_prompts": len(prompts),
        "spelling": "US-English",
        "commonwealth_count": 0,
        "commonwealth_words": [],
        "punctuation_habits": {},
        "average_word_count": 0
    }

    if not prompts:
        return stats

    total_words = 0
    commonwealth_hits = Counter()
    counts = Counter()

    for p in prompts:
        total_words += len(p.split())

        for word in COMMONWEALTH_WORDS:
            if re.search(r'\b' + word + r'\b', p, re.IGNORECASE):
                stats["commonwealth_count"] += 1
                commonwealth_hits[word] += 1

        if "..." in p:
            counts["ellipsis"] += 1
        if "??" in p or "? !" in p:
            counts["double_question"] += 1
        if "—" in p or " -- " in p:
            counts["em_dash"] += 1
        if "->" in p or "=>" in p:
            counts["arrow"] += 1
        if re.search(r"\b\w+'(?:s|t|re|ll|ve|d|m)\b", p):
            counts["contraction"] += 1

    n = len(prompts)
    stats["average_word_count"] = int(total_words / n)
    if stats["commonwealth_count"] > 3:
        stats["spelling"] = "British/Commonwealth"
    stats["commonwealth_words"] = [w for w, _ in commonwealth_hits.most_common(5)]

    stats["punctuation_habits"] = {
        "ellipsis_frequency": _rate(counts["ellipsis"], n),
        "double_question_frequency": _rate(counts["double_question"], n),
        "em_dash_frequency": _rate(counts["em_dash"], n),
        "arrow_frequency": _rate(counts["arrow"], n),
        "contraction_frequency": _rate(counts["contraction"], n),
    }
    return stats


def default_output_dir():
    """The persona directory voice-register reads (AGENT_PERSONA_DIR overrides it)."""
    base = os.environ.get("AGENT_PERSONA_DIR") or os.path.join(HOME, ".gemini", "personas")
    return os.path.join(os.path.expanduser(base), "default")


PROFILE_DRAFT = "voice_and_tone.draft.md"
SAMPLES_DRAFT = "voice-samples.draft.md"


def write_canonical_files(prompts, stats, output_dir):
    """Writes a draft profile and raw excerpts in voice-register's template layout.

    Only measured facts are filled in; everything a script can't know is left as
    a <...> placeholder for the person to complete. The files are drafts, so the
    live voice_and_tone.md is never overwritten.
    """
    os.makedirs(output_dir, exist_ok=True)
    habits = stats["punctuation_habits"] or {}
    n = stats["total_prompts"]
    spelling = stats["spelling"]
    words = ", ".join(stats.get("commonwealth_words") or [])
    if words and stats["commonwealth_count"] > 3:
        spelling += " (seen: " + words + ")"
    elif words:
        # Too few to call it British, but worth showing.
        seen = stats["commonwealth_count"]
        spelling += " by default; %d Commonwealth spelling%s seen (%s)" % (
            seen, "" if seen == 1 else "s", words)

    with open(os.path.join(output_dir, PROFILE_DRAFT), 'w', encoding='utf-8') as f:
        f.write(f"""# Voice and Tone — <Your Name> (draft)

Drafted by human-voice from {n} redacted prompts. The measured lines below come from your prompts to AI tools, which are terser than the email or docs you send, so treat them as hints. Replace every `<...>`, delete what doesn't fit, then rename this file to `voice_and_tone.md`. See voice-register's `references/voice_and_tone.template.md` for the layout.

## Core Persona
<One or two sentences: role, stance, what you value in writing.>

## Linguistic & Punctuation Fingerprints
- **Openings**: <How you start: the answer first, the problem first, context first?>
- **Spelling**: {spelling}. <Confirm, and list words you always spell a particular way.>
- **Dashes**: em-dashes in {habits.get("em_dash_frequency", "0%")} of prompts. <Keep, or ban?>
- **Arrows and slashes**: `->` or `=>` in {habits.get("arrow_frequency", "0%")} of prompts. <Which form, with spaces?>
- **Contractions**: in {habits.get("contraction_frequency", "0%")} of prompts. <Natural, or avoided?>
- **Questions**: double question marks in {habits.get("double_question_frequency", "0%")} of prompts. <Do you soften asks?>
- **Transitions you actually use**: <...>
- **Lexicon**: <Domain terms you favour, and ones you never use.>
- **Live-only shorthand**: ellipses in {habits.get("ellipsis_frequency", "0%")} of prompts; average prompt is {stats["average_word_count"]} words. <Shorthand fine in chat but cleaned in polished docs.>

## Channel Registers
Fill in only the registers you write in.

### R1: Quick Internal / Team Email
- **Greeting**: <...>
- **Body**: <...>
- **Sign-off**: <...>

### R2: Cross-Functional / Stakeholder / External Email
- **Greeting**: <...>
- **Body shape**: <...>
- **Sign-off**: <...>

### R3: Technical Blog / Long-Form
- **Voice**: <...>
- **Structure**: <...>

### R4: Strategy Docs & Proposals
- **Voice**: <...>
- **Structure**: <...>

### R5: Working Notes & Comments
- **Structure**: <...>
""")

    with open(os.path.join(output_dir, SAMPLES_DRAFT), 'w', encoding='utf-8') as f:
        f.write("# Raw Excerpts (draft)\n\n")
        f.write("Redacted excerpts of your own prompts, for spotting habits. They are not "
                "before/after samples: write those in voice-register's "
                "`examples/voice-samples.template.md` layout and save them as "
                "`voice-samples.md`. Check this file for anything private before you "
                "commit it anywhere.\n\n")
        excerpts = [p for p in prompts if 15 < len(p.split()) < 80]
        if not excerpts:
            f.write("No prompts of a usable length were found.\n")
        for idx, ex in enumerate(excerpts[:5], 1):
            f.write(f"## Excerpt {idx}\n> {ex.strip()}\n\n")


def main():
    parser = argparse.ArgumentParser(description="Extract human writing voice and tone from local AI coding tool logs.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose diagnostic output")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Where to write the drafts (default: ~/.gemini/personas/default, or $AGENT_PERSONA_DIR/default)")
    parser.add_argument("--internal-domain", action="append", default=[], metavar="DOMAIN", help="Also redact URLs and hosts under this domain (repeatable), e.g. your employer's intranet")
    parser.add_argument("-t", "--tool", type=str, default="all", choices=["all", "antigravity", "antigravity-ide", "antigravity-cli", "gemini-cli", "claude-code", "cline", "roo-code", "aider", "cursor"], help="Target a specific AI coding tool for extraction")
    parser.add_argument("-u", "--user-name", type=str, default=None, help="Custom user name to scrub from prompts")
    parser.add_argument("-n", "--user-nickname", type=str, default=None, help="Custom user nickname to scrub from prompts")
    args = parser.parse_args()

    print("Initializing Voice Extraction across AI coding tools...")
    if args.verbose:
        print(f"Platform: {platform.system()} ({platform.release()})")
        print(f"Home Directory: {HOME}")
        print("Resolved tool storage paths:")
        for tool in PATHS:
            for path in _roots(tool):
                status = "EXISTS" if path.exists() else "NOT FOUND"
                print(f"  - {tool}: {path} [{status}]")

    add_internal_domains(args.internal_domain)

    extra_names = []
    if args.user_name:
        extra_names.append((args.user_name, log_sources.USER_NAME))
    if args.user_nickname:
        extra_names.append((args.user_nickname, log_sources.USER_NICKNAME))

    all_prompts = []
    target_tool = args.tool.lower()
    
    # 1. Antigravity IDE & CLI. Each surface has its own brain directory, and
    # naming one on --tool has to mean that one.
    ANTIGRAVITY_SURFACES = {
        "all": ("antigravity-ide", "antigravity-cli"),
        "antigravity": ("antigravity-ide", "antigravity-cli"),
        "antigravity-ide": ("antigravity-ide",),
        "antigravity-cli": ("antigravity-cli",),
    }
    if target_tool in ANTIGRAVITY_SURFACES:
        surfaces = ANTIGRAVITY_SURFACES[target_tool]
        label = " & ".join("IDE" if s.endswith("ide") else "CLI" for s in surfaces)
        print(f"Checking Antigravity {label} files...")
        ag_prompts = extract_antigravity(extra_names=extra_names, surfaces=surfaces)
        print(f"-> Extracted {len(ag_prompts)} prompts from Antigravity {label}.")
        all_prompts.extend(ag_prompts)
    
    # 2. Gemini CLI
    if target_tool in ["all", "gemini-cli"]:
        print("Checking Gemini CLI files...")
        gem_prompts = extract_gemini_cli(extra_names=extra_names)
        print(f"-> Extracted {len(gem_prompts)} prompts from Gemini CLI.")
        all_prompts.extend(gem_prompts)
    
    # 3. Claude Code
    if target_tool in ["all", "claude-code"]:
        print("Checking Claude Code files...")
        claude_prompts = extract_claude_code(extra_names=extra_names)
        print(f"-> Extracted {len(claude_prompts)} prompts from Claude Code.")
        all_prompts.extend(claude_prompts)
    
    # 4. Cline and Roo Code. Like Antigravity, naming one reads only that one.
    CLINE_TOOLS = {
        "all": ("cline", "roo-code"),
        "cline": ("cline",),
        "roo-code": ("roo-code",),
    }
    if target_tool in CLINE_TOOLS:
        tools = CLINE_TOOLS[target_tool]
        label = " & ".join("Cline" if t == "cline" else "Roo Code" for t in tools)
        print(f"Checking {label} files...")
        cline_prompts = extract_cline_and_roo_code(extra_names=extra_names, tools=tools)
        print(f"-> Extracted {len(cline_prompts)} prompts from {label}.")
        all_prompts.extend(cline_prompts)
    
    # 5. Aider
    if target_tool in ["all", "aider"]:
        print("Checking Aider files...")
        aider_prompts = extract_aider(extra_names=extra_names)
        print(f"-> Extracted {len(aider_prompts)} prompts from Aider.")
        all_prompts.extend(aider_prompts)
    
    # 6. Cursor
    if target_tool in ["all", "cursor"]:
        print("Checking Cursor SQLite databases...")
        cursor_prompts = extract_cursor(extra_names=extra_names)
        print(f"-> Extracted {len(cursor_prompts)} prompts from Cursor.")
        all_prompts.extend(cursor_prompts)
    
    # Remove duplicates
    unique_prompts = list(set(all_prompts))
    print(f"\nTotal unique prompts extracted: {len(unique_prompts)}")
    
    # Analyze linguistics
    print("Analyzing linguistic patterns...")
    stats = analyze_linguistics(unique_prompts)
    print(f"-> Detected primary spelling habit: {stats['spelling']}")
    print(f"-> Average word count per prompt: {stats['average_word_count']}")
    
    # Write drafts next to the live profile, never over it
    output_dir = args.output_dir or default_output_dir()
    print(f"Writing drafts to: {output_dir}")
    write_canonical_files(unique_prompts, stats, output_dir)
    print(f"Done. Edit {PROFILE_DRAFT}, then rename it to voice_and_tone.md for voice-register to use it.")

if __name__ == "__main__":
    main()
