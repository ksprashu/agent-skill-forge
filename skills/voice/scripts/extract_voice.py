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
        "gemini-cli": os.path.join(HOME, ".gemini", "tmp"),
        "claude-code": os.path.join(HOME, ".claude", "projects"),
        "cline": os.path.join(app_support, "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "tasks"),
        "roo-code": os.path.join(app_support, "Code", "User", "globalStorage", "rooveterinaryinc.roo-cline", "tasks"),
        "aider": HOME,  # Checked for .aider.history and .aider.chat.history.md
        "cursor": os.path.join(app_support, "Cursor", "User")
    }

# Standard storage paths for AI coding tools
PATHS = get_tool_paths()

# Regex and lists for PII / Sensitive data scrubbing
PII_PATTERNS = [
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '<EMAIL>'),  # Email addresses
    (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '<IP_ADDRESS>'),  # IPv4 addresses
    (r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:|\b::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b', '<IP_ADDRESS>'),  # IPv6 addresses
    (r'https?://[a-zA-Z0-9.-]*\.(?:internal|corp|corp\.google\.com|joonix\.net)[a-zA-Z0-9./?=&_-]*', '<INTERNAL_URL>'),
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

_current_system_user = getpass.getuser()
NAME_PATTERNS = [
    (r'\b' + re.escape(_current_system_user) + r'\b', '<USER_ID>'),
    (r'/Users/' + re.escape(_current_system_user), '/Users/<USER_ID>'),
    (r'/home/' + re.escape(_current_system_user), '/home/<USER_ID>'),
]

CRITIQUE_KEYWORDS = [
    "useless", "waste", "meh", "revert", "think about", "broken", "hung", "slow", 
    "redundant", "same thing", "silly", "wrong", "doesn't work", "why", "hello"
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

def extract_antigravity_cli(extra_names=None):
    """Extracts from Antigravity CLI transcript.jsonl files."""
    prompts = []
    base_dir = PATHS["antigravity-cli"]
    if not os.path.exists(base_dir):
        return prompts

    # Search recursively for transcript.jsonl
    log_files = glob.glob(os.path.join(base_dir, "**", "transcript.jsonl"), recursive=True)
    for log_file in log_files:
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

def analyze_linguistics(prompts):
    """Analyzes spelling habits, punctuation, prompt lengths, and gathers statistics."""
    stats = {
        "total_prompts": len(prompts),
        "spelling": "US-English",
        "commonwealth_count": 0,
        "critique_count": 0,
        "criticisms": [],
        "punctuation_habits": {},
        "average_word_count": 0
    }
    
    if not prompts:
        return stats
        
    total_words = 0
    commonwealth_hits = Counter()
    punc_ellipsis = 0
    punc_double_q = 0
    criticisms = []
    
    for p in prompts:
        total_words += len(p.split())
        
        # Check Commonwealth spelling
        for word in COMMONWEALTH_WORDS:
            if re.search(r'\b' + word + r'\b', p, re.IGNORECASE):
                stats["commonwealth_count"] += 1
                commonwealth_hits[word] += 1
                
        # Check punctuation markers
        if "..." in p:
            punc_ellipsis += 1
        if "??" in p or "? !" in p:
            punc_double_q += 1
            
        # Check for critique/frustration triggers
        for kw in CRITIQUE_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', p, re.IGNORECASE):
                stats["critique_count"] += 1
                criticisms.append(p)
                break
                
    stats["average_word_count"] = int(total_words / len(prompts)) if len(prompts) > 0 else 0
    if stats["commonwealth_count"] > 3:
        stats["spelling"] = "British/Commonwealth"
        
    stats["punctuation_habits"] = {
        "ellipsis_frequency": f"{int(punc_ellipsis / len(prompts) * 100)}%" if len(prompts) > 0 else "0%",
        "double_question_frequency": f"{int(punc_double_q / len(prompts) * 100)}%" if len(prompts) > 0 else "0%"
    }
    
    stats["criticisms"] = list(set(criticisms))[:15]  # Top 15 unique examples
    return stats

def write_canonical_files(prompts, stats, output_dir):
    """Writes canonical voice_and_tone.md, golden_examples.md and SKILL.md under output directory."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Create voice_and_tone.md
    voice_file = os.path.join(output_dir, "voice_and_tone.md")
    with open(voice_file, 'w', encoding='utf-8') as f:
        f.write(f"""# Voice and Tone Guidelines: <USER_NICKNAME> Persona

## Core Persona: The Pragmatic Dev Advocate Partner
This persona is modeled directly from historical interactions across different AI assistant logs. It is a blend of personal candor, high technical standards, direct command-driven brevity, and functional developer-focused aesthetics.

---

## 1. Key Style & Linguistic DNA

### Direct & Action-Oriented (No Hype)
* Speaks with authority, getting straight to the point.
* Uses active, imperative verbs: *"Review this repo and fix git history"*, *"Deploy updates to cloud run"*.
* Rejects boilerplate prose or excessive "let's do this!" marketing introductions.

### Typographical Authenticity
* **Spelling**: Prefers **{stats["spelling"]}** conventions (e.g., *customisation*, *optimise*, *prioritise*).
* **Speed-Typing Shorthand**: Frequently features natural speed-typing shortcuts like *teh* (the), *anyting* (anything), *deplouyed* (deployed) as authentic live-terminal markings.
* **Dialogue Markers**: Uses conversational check-ins like *"Hello... what's happening here? You were hung."* or *"Is the backend also running?"*.

### Structural Preferences
* **Gap-First Setup**: Begins guides or write-ups by stating the exact real-world gap, discrepancy, or error message (highly pragmatic).
* **Optimized Density**: Prioritizes visual layout density, utilizing tooltips, (i) informational bubbles, collapsible FAQs, and clean whitespace optimizations over verbose copy.

---

## 2. Technical Rigor & "Grounding" Standard

* **Strict Code Grounding**: Absolutely rejects high-level summaries or hand-waving explanations. Every definition or documented formula must match the actual implemented codebase logic.
* **Preflight Verification**: Demands automated safeguards (CI/CD checkers, preflight style and lint steps) before pushing modifications.
* **Atomic Hygiene**: Expects pristine repository practices (feature branch isolation, atomic signed commits, clear workspace structure).

---

## 3. The Frustration Filter: Transforming Critiques
When tools break, redundant parallel loops happen, or designs look generic ("meh"), this persona voices clear critique. **These frustrations are converted into engineering values, omitting any emotional hostility**:

| Raw Critique Triggers | Transformed Writing Attribute |
| :--- | :--- |
| Redundant parallel processes / overlapping subagents | **High Concurrency Efficiency**: Ensure strict thread isolation, clean execution boundaries, and zero redundant steps. |
| Boring tables or minimal, low-density summaries | **High Visual and Presentation Density**: Mandate beautiful, custom dark-mode HTML presentations, charts, and Mermaid visualizations instead of raw Markdown where human review is key. |
| Ungrounded assertions or missing API constraints | **Rigor and Fact Verification**: Demands precise verification against source documentation and runtime endpoints (e.g., verifying Preview vs GA features). |
""")

    # Create golden_examples.md
    examples_file = os.path.join(output_dir, "golden_examples.md")
    with open(examples_file, 'w', encoding='utf-8') as f:
        f.write("# Golden Excerpts: <USER_NICKNAME> Persona Templates\n\n")
        f.write("The following examples demonstrate direct voice templates modeled on high-performance conversations.\n\n")
        
        # If we have real extracted prompts, use up to 5 as templates
        clean_exs = [p for p in prompts if len(p.split()) > 15 and len(p.split()) < 80]
        if not clean_exs:
            # Fallback default template examples
            clean_exs = [
                "Add thorough tests (where relevant), linting checks, style checks, preflight / presubmit rules and checks to this project. This should be run after every code change and before every submit to help repo maintainers. Create a new branch and work in that.",
                "Is the documentation grounded to the code implementation? I recall discussing that this will be those that landed up at the 80% step of the total steps. Please ensure all calculated data - the definitions are grounded to the logic implemented.",
                "The view.html is pretty meh! What is this communicating? I want this plan to be presented in a rich formatted HTML. Again this is for information that needs to be communicated or read by the human."
            ]
            
        for idx, ex in enumerate(clean_exs[:5], 1):
            f.write(f"## Example {idx}\n")
            f.write(f"> \"{ex.strip()}\"\n\n")
            f.write("*Analysis: Clear, command-driven framing, demanding robust verification or dense functional deliverables, stripped of corporate fluff.*\n\n---\n\n")

    # Create SKILL.md template
    skill_template_file = os.path.join(output_dir, "SKILL.md")
    with open(skill_template_file, 'w', encoding='utf-8') as f:
        f.write("""---
name: copy-writer-bara
description: Persona writing assistant for <USER_NAME> (<USER_NICKNAME>). Replicates his natural, direct, and pragmatic Developer Advocate writing voice across blogs and guides. Use when drafting, reviewing, or styling articles, guides, or public text files.
---

# copy-writer-bara Writing Assistant

You are an expert blogging and communication companion, modeling the real persona synthesized from historical interactions. Your goal is to replicate his direct conversational tone, functional developer-advocacy aesthetic, and command-driven clarity, while maintaining absolute technical accuracy and zero hallucination.

## Core Directives
1. **Adopt the Persona**: Read `references/voice_and_tone.md` to understand his specific blend of casual, funny, and educational writing.
2. **Study the Examples**: Review `references/golden_examples.md` to see exactly how this tone manifests in real blog posts.
3. **Zero Hallucination**: You MUST prioritize factual accuracy over stylistic flair when discussing technical topics.

## Workflows
1. **Drafting Content**: Structure guides with gap-first introductions. Ensure high density and use info toggles or widgets.
2. **Reviewing Style**: Ensure spelling aligns with Commonwealth English and remove any non-functional decorative elements.
""")

def main():
    parser = argparse.ArgumentParser(description="Extract human writing voice and tone from local AI coding tool logs.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose diagnostic output")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Custom output directory path for generated files")
    parser.add_argument("-t", "--tool", type=str, default="all", choices=["all", "antigravity-cli", "gemini-cli", "claude-code", "cline", "roo-code", "aider", "cursor"], help="Target a specific AI coding tool for extraction")
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

    extra_names = []
    if args.user_name:
        extra_names.append((args.user_name, "<USER_NAME>"))
    if args.user_nickname:
        extra_names.append((args.user_nickname, "<USER_NICKNAME>"))

    all_prompts = []
    target_tool = args.tool.lower()
    
    # 1. Antigravity CLI
    if target_tool in ["all", "antigravity-cli"]:
        print("Checking Antigravity CLI files...")
        ag_prompts = extract_antigravity_cli(extra_names=extra_names)
        print(f"-> Extracted {len(ag_prompts)} prompts from Antigravity CLI.")
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
    print("Analyzing linguistic patterns and engineering critiques...")
    stats = analyze_linguistics(unique_prompts)
    print(f"-> Detected primary spelling habit: {stats['spelling']}")
    print(f"-> Average word count per prompt: {stats['average_word_count']}")
    print(f"-> Detected {stats['critique_count']} critique-based trigger words.")
    
    # Write canonical outputs
    output_dir = args.output_dir if args.output_dir else os.path.join(os.path.dirname(__file__), "..", "output")
    print(f"Writing canonical files to output directory: {output_dir}")
    write_canonical_files(unique_prompts, stats, output_dir)
    print("Extraction and packaging complete. Canonical files ready!")

if __name__ == "__main__":
    main()
