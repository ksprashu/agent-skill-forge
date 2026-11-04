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
import json
import glob
import sqlite3
import platform
import argparse
import getpass
from collections import Counter

# Set up paths relative to user's home directory
HOME = os.path.expanduser('~')

def get_tool_paths():
    """Dynamically resolves AI tool storage directories across macOS, Linux, and Windows."""
    system = platform.system()
    if system == "Darwin":
        app_support = os.path.join(HOME, "Library", "Application Support")
    elif system == "Windows":
        app_support = os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming"))
    else:  # Linux / Unix
        app_support = os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))

    return {
        "antigravity-cli": os.path.join(HOME, ".gemini", "antigravity-cli", "brain"),
        "antigravity-ide": os.path.join(HOME, ".gemini", "antigravity", "brain"),
        "gemini-cli": os.path.join(HOME, ".gemini", "tmp"),
        "claude-code": os.path.join(HOME, ".claude", "projects"),
        "cline": os.path.join(app_support, "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "tasks"),
        "roo-code": os.path.join(app_support, "Code", "User", "globalStorage", "rooveterinaryinc.roo-cline", "tasks"),
        "aider": HOME,  # Checked for .aider.history and .aider.chat.history.md
        "cursor": os.path.join(app_support, "Cursor", "User")
    }

# Standard storage paths for AI coding tools
PATHS = get_tool_paths()

# A hostname label that marks a host as internal wherever it sits in the name
# (foo.corp, ci.corp.example.com). The whole hostname is consumed, so no
# suffix such as an employer's domain survives.
_INTERNAL_LABEL = r'(?:internal|corp|intranet)(?![a-z0-9-])'
_INTERNAL_URL_LABEL = r'(?:internal|corp|intranet|lan|local)(?![a-z0-9-])'
_MORE_LABELS = r'(?:\.[a-z0-9-]+)*'
_URL_TAIL = r'(?::[0-9]+)?(?:[/?#][a-z0-9./?=&_%#:~+-]*)?(?<![.,;:])'

# Regex and lists for PII / Sensitive data scrubbing
PII_PATTERNS = [
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '<EMAIL>'),  # Email addresses
    (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '<IP_ADDRESS>'),  # IPv4 addresses
    (r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:|\b::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b', '<IP_ADDRESS>'),  # IPv6 addresses
    (r'https?://(?:[a-z0-9-]+\.)*' + _INTERNAL_URL_LABEL + _MORE_LABELS + _URL_TAIL, '<INTERNAL_URL>'),
    # bare internal hostnames: a label before it (foo.corp), or two after it (corp.example.com)
    (r'\b(?:[a-z0-9-]+\.)+' + _INTERNAL_LABEL + _MORE_LABELS
     + r'|\b' + _INTERNAL_LABEL + r'(?:\.[a-z0-9-]+){2,}', '<COMPANY_DOMAIN>'),
    (r'AI_SHA_KEY_[a-zA-Z0-9]{16,}', '<REDACTED_API_KEY>'),  # Key structures
    (r'AIzaSy[a-zA-Z0-9_-]{33}', '<REDACTED_API_KEY>'),  # Google Cloud API Keys
    (r'ghp_[a-zA-Z0-9]{36}', '<REDACTED_GITHUB_TOKEN>'),  # GitHub token
    (r'github_pat_[a-zA-Z0-9_]{80,}', '<REDACTED_GITHUB_PAT>'),  # GitHub Fine-Grained PAT
    (r'sk-ant-api03-[a-zA-Z0-9_-]{40,}', '<REDACTED_ANTHROPIC_KEY>'),  # Anthropic API Keys
    (r'sk-[a-zA-Z0-9]{32,}', '<REDACTED_OPENAI_KEY>'),  # OpenAI API Keys
    (r'AKIA[0-9A-Z]{16}', '<REDACTED_AWS_ACCESS_KEY>'),  # AWS Access Key ID
    (r'glpat-[a-zA-Z0-9_-]{20,}', '<REDACTED_GITLAB_PAT>'),  # GitLab Personal Access Token
    (r'ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9._-]{10,}', '<REDACTED_JWT_TOKEN>'),  # JWTs
]


def add_internal_domains(domains):
    """Redact URLs and hostnames under the given domains (e.g. an employer's intranet).

    Nothing employer-specific ships in this file; pass yours with --internal-domain.
    """
    # These go first, so a generic pattern can't consume part of the hostname
    # and leave the supplied domain behind.
    rows = []
    for domain in domains or ():
        domain = domain.strip().lstrip(".")
        if domain:
            escaped = re.escape(domain) + r'(?![a-z0-9-])'
            rows.append((r'https?://(?:[a-z0-9-]+\.)*' + escaped + _MORE_LABELS + _URL_TAIL, '<INTERNAL_URL>'))
            rows.append((r'(?<![a-z0-9-])(?:[a-z0-9-]+\.)*' + escaped + _MORE_LABELS, '<COMPANY_DOMAIN>'))
    PII_PATTERNS[:0] = rows

_current_system_user = getpass.getuser()
NAME_PATTERNS = [
    (r'\b' + re.escape(_current_system_user) + r'\b', '<USER_ID>'),
    (r'/Users/' + re.escape(_current_system_user), '/Users/<USER_ID>'),  # host-path-ok
    (r'/home/' + re.escape(_current_system_user), '/home/<USER_ID>'),  # host-path-ok
]

COMMONWEALTH_WORDS = [
    "colour", "behaviour", "customisation", "optimise", "prioritise", "organisation",
    "modelling", "visualise", "customise"
]

def sanitize_text(text, extra_names=None):
    """Scrubs sensitive information, PII, and specific personal ids/domains from raw text."""
    if not isinstance(text, str):
        return ""
    
    # Run generic PII scrubbers
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
    # Run user name and home path scrubbers
    for pattern, replacement in NAME_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    if extra_names:
        for name, tag in extra_names:
            if name:
                text = re.sub(r'\b' + re.escape(name) + r'\b', tag, text, flags=re.IGNORECASE)
        
    return text

def extract_antigravity(extra_names=None, surfaces=("antigravity-ide", "antigravity-cli")):
    """Extracts from Antigravity transcript.jsonl files.

    ``surfaces`` names which of the two brains to read. It defaults to both,
    which is what ``--tool antigravity`` means; ``--tool antigravity-cli`` asks
    for the CLI only, and a filter that silently widens is not a filter.
    """
    prompts = []
    dirs_to_check = [PATHS.get(name) for name in surfaces]
    for base_dir in dirs_to_check:
        if not base_dir or not os.path.exists(base_dir):
            continue

        # Traverse all directories including hidden (.system_generated)
        for root, _, files in os.walk(base_dir):
            if "transcript.jsonl" in files:
                log_file = os.path.join(root, "transcript.jsonl")
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            data = json.loads(line)
                            # Extract from PLANNER_RESPONSE or user interactions
                            if data.get("type") == "USER_INPUT" and data.get("content"):
                                prompts.append(sanitize_text(data["content"], extra_names=extra_names))
                            elif data.get("source") == "USER_EXPLICIT" and data.get("content"):
                                prompts.append(sanitize_text(data["content"], extra_names=extra_names))
                except Exception:
                    continue
    return prompts

def extract_antigravity_cli(extra_names=None):
    return extract_antigravity(extra_names=extra_names, surfaces=("antigravity-cli",))


def extract_antigravity_ide(extra_names=None):
    return extract_antigravity(extra_names=extra_names, surfaces=("antigravity-ide",))

def extract_gemini_cli(extra_names=None):
    """Extracts from gemini-cli session JSONL files."""
    prompts = []
    base_dir = PATHS["gemini-cli"]
    if not os.path.exists(base_dir):
        return prompts

    log_files = glob.glob(os.path.join(base_dir, "**", "chats", "*.jsonl"), recursive=True)
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    # Support multiple formats in gemini-cli
                    if data.get("role") == "user" and data.get("content"):
                        prompts.append(sanitize_text(data["content"], extra_names=extra_names))
                    elif "user_input" in data:
                        prompts.append(sanitize_text(data["user_input"], extra_names=extra_names))
                    elif "content" in data and isinstance(data["content"], str) and data.get("sender") == "user":
                        prompts.append(sanitize_text(data["content"], extra_names=extra_names))
        except Exception:
            continue
    return prompts

def extract_claude_code(extra_names=None):
    """Extracts from Claude Code jsonl files."""
    prompts = []
    base_dir = PATHS["claude-code"]
    if not os.path.exists(base_dir):
        return prompts

    log_files = glob.glob(os.path.join(base_dir, "**", "chat_*.jsonl"), recursive=True)
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    # Claude Code schema checks
                    if data.get("role") == "user" and data.get("content"):
                        content = data["content"]
                        if isinstance(content, list):
                            text = " ".join([part.get("text", "") for part in content if part.get("type") == "text"])
                            prompts.append(sanitize_text(text, extra_names=extra_names))
                        elif isinstance(content, str):
                            prompts.append(sanitize_text(content, extra_names=extra_names))
        except Exception:
            continue
    return prompts

def extract_cline_and_roo_code(extra_names=None):
    """Extracts from Cline and Roo Code ui_messages.json files."""
    prompts = []
    for tool_name in ["cline", "roo-code"]:
        base_dir = PATHS[tool_name]
        if not os.path.exists(base_dir):
            continue

        log_files = glob.glob(os.path.join(base_dir, "**", "ui_messages.json"), recursive=True)
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
                    for msg in messages:
                        # Extracted user prompts
                        if msg.get("type") == "say" and msg.get("say") == "user_feedback":
                            if msg.get("text"):
                                prompts.append(sanitize_text(msg["text"], extra_names=extra_names))
                        elif msg.get("role") == "user" and msg.get("content"):
                            prompts.append(sanitize_text(msg["content"], extra_names=extra_names))
            except Exception:
                continue
    return prompts

def extract_aider(extra_names=None):
    """Extracts from Aider session logs."""
    prompts = []
    # Check ~/.aider.history (plain command history file)
    history_file = os.path.join(PATHS["aider"], ".aider.history")
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line and not clean_line.startswith("#"):
                        prompts.append(sanitize_text(clean_line, extra_names=extra_names))
        except Exception:
            pass
            
    # Check for .aider.chat.history.md files in common directories instead of recursive scanning
    search_paths = [
        os.path.join(HOME, ".aider.chat.history.md"),
        os.path.join(HOME, "*", ".aider.chat.history.md"),
        os.path.join(HOME, "code", "*", ".aider.chat.history.md"),
        os.path.join(HOME, "git", "*", ".aider.chat.history.md")
    ]
    chat_files = []
    for sp in search_paths:
        chat_files.extend(glob.glob(sp))

    for chat_file in chat_files:
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                # Simple extraction of blockquotes or lines starting with >
                for line in f:
                    if line.startswith("> ") or line.startswith("  > "):
                        text = line.replace("> ", "").strip()
                        if text:
                            prompts.append(sanitize_text(text, extra_names=extra_names))
        except Exception:
            continue
    return prompts

def extract_cursor(extra_names=None):
    """Extracts from Cursor global state.vscdb SQLite DB if accessible."""
    prompts = []
    base_dir = PATHS["cursor"]
    if not os.path.exists(base_dir):
        return prompts
        
    db_file = os.path.join(base_dir, "globalStorage", "state.vscdb")
    if os.path.exists(db_file):
        try:
            # Use read-only URI mode to prevent database locking errors when Cursor is open
            db_uri = f"file:{db_file}?mode=ro&immutable=1"
            conn = sqlite3.connect(db_uri, uri=True)
            cursor = conn.cursor()
            # Try finding chat/composer keys in state table
            cursor.execute("SELECT key, value FROM globalState WHERE key LIKE '%chat%' OR key LIKE '%composer%'")
            rows = cursor.fetchall()
            for key, value in rows:
                try:
                    # Parse values which are JSON strings
                    val_data = json.loads(value)
                    # Extract any strings/contents inside state trees
                    val_str = json.dumps(val_data)
                    # Simple regex extraction of text inputs inside state tree
                    found_prompts = re.findall(r'"text"\s*:\s*"([^"]+)"', val_str)
                    for fp in found_prompts:
                        # Unescape unicode and sanitize
                        text = bytes(fp, "utf-8").decode("unicode_escape", errors="ignore")
                        prompts.append(sanitize_text(text, extra_names=extra_names))
                except Exception:
                    continue
            conn.close()
        except Exception:
            pass
    return prompts

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
        n = stats["commonwealth_count"]
        spelling += " by default; %d Commonwealth spelling%s seen (%s)" % (
            n, "" if n == 1 else "s", words)

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
        for tool, path in PATHS.items():
            status = "EXISTS" if os.path.exists(path) else "NOT FOUND"
            print(f"  - {tool}: {path} [{status}]")

    add_internal_domains(args.internal_domain)

    extra_names = []
    if args.user_name:
        extra_names.append((args.user_name, "<USER_NAME>"))
    if args.user_nickname:
        extra_names.append((args.user_nickname, "<USER_NICKNAME>"))

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
    
    # 4. Cline and Roo Code
    if target_tool in ["all", "cline", "roo-code"]:
        print("Checking Cline & Roo Code files...")
        cline_prompts = extract_cline_and_roo_code(extra_names=extra_names)
        print(f"-> Extracted {len(cline_prompts)} prompts from Cline & Roo Code.")
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
