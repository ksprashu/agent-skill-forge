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
log_sources.py - Find local AI-tool logs, read your turns out of them, redact.

Shared by two skills: human-voice (how you write) and cognitive-profiler (how
you react to AI output). Both read the same logs and must scrub the same
secrets, and they used to carry separate copies of this code that drifted:
one read Claude Code's real session format and the other found nothing.

A skill installed with `npx skills add` is only its own folder, so it cannot
import from a sibling skill. Each skill therefore ships an identical copy of
this file in its scripts/ directory, and tests/test_log_sources_parity.py at
the repo root fails if the copies differ. Edit one, then copy it over the
other.

Three parts:

1. Where each tool keeps its logs, per OS (`tool_paths`, `source_roots`).
2. One reader per log format. Each yields a `Session` of `Turn`s with the raw,
   unredacted text; callers redact. A reader never raises on a corrupt file;
   it skips it.
3. One redaction table (`SENSITIVE_PATTERNS`) plus helpers for names and
   internal domains a user supplies at run time.

Stdlib only.
"""

import getpass
import glob
import json
import os
import platform
import re
import sqlite3
from pathlib import Path
from typing import List, NamedTuple, Optional

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class Turn(NamedTuple):
    """One utterance. ``role`` is "user" or "assistant"; ``text`` is raw."""

    role: str
    text: str
    when: Optional[str] = None


class Session(NamedTuple):
    """One conversation: a file, or one chat inside a file."""

    path: Path
    turns: List[Turn]


# ---------------------------------------------------------------------------
# Where the logs live
# ---------------------------------------------------------------------------


def _home():
    return Path.home()


def app_support_dir(home=None):
    """The per-user application data directory for VS Code-style apps."""
    home = Path(home) if home else _home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Application Support"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))


#: Directories searched for aider history files, relative to home. Aider
#: writes its history into whichever directory it was started in, so there
#: is no single location; these are the common ones, searched one level deep
#: rather than walking the whole home directory.
AIDER_SEARCH_DIRS = ("", "*", os.path.join("code", "*"), os.path.join("git", "*"))
AIDER_CHAT_FILE = ".aider.chat.history.md"
AIDER_INPUT_FILES = (".aider.input.history", ".aider.history")


def aider_files(home=None):
    """Aider history files under the usual directories.

    The chat transcript and the input history record the same prompts, so an
    input history is used only where no chat transcript sits beside it.
    """
    home = Path(home) if home else _home()
    found = []
    for rel in AIDER_SEARCH_DIRS:
        for directory in sorted(glob.glob(os.path.join(str(home), rel))):
            directory = Path(directory)
            chat = directory / AIDER_CHAT_FILE
            if chat.is_file():
                found.append(chat)
                continue
            for name in AIDER_INPUT_FILES:
                candidate = directory / name
                if candidate.is_file():
                    found.append(candidate)
                    break
    return found


def tool_paths(home=None):
    """Candidate log locations per tool, as lists of absolute paths.

    Antigravity's two surfaces are listed separately so a caller can read one
    without the other. Layouts move between releases, so each entry lists
    every location seen in the wild.
    """
    home = Path(home) if home else _home()
    app = app_support_dir(home)
    vscode_storage = app / "Code" / "User" / "globalStorage"
    return {
        "antigravity-cli": [home / ".gemini" / "antigravity-cli" / "brain"],
        "antigravity-ide": [
            home / ".gemini" / "antigravity-ide",
            home / ".gemini" / "antigravity" / "brain",
        ],
        "gemini-cli": [home / ".gemini" / "tmp"],
        "claude-code": [home / ".claude" / "projects"],
        "cline": [vscode_storage / "saoudrizwan.claude-dev" / "tasks"],
        "roo-code": [vscode_storage / "rooveterinaryinc.roo-cline" / "tasks"],
        "cursor": [app / "Cursor" / "User"],
        "aider": aider_files(home) or [home / AIDER_CHAT_FILE],
    }


def source_roots(home=None):
    """Candidate locations per harness, with Antigravity's surfaces merged."""
    paths = tool_paths(home)
    return {
        "claude-code": paths["claude-code"],
        "antigravity": paths["antigravity-cli"] + paths["antigravity-ide"],
        "gemini-cli": paths["gemini-cli"],
        "cline": paths["cline"],
        "roo-code": paths["roo-code"],
        "cursor": paths["cursor"],
        "aider": paths["aider"],
    }


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def _iter_jsonl(path):
    """JSON objects from a JSONL file. Malformed lines are skipped."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    yield record
    except OSError:
        return


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def _text_of(content):
    """A string, or the text parts of a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


#: Claude Code user records that start like this are slash commands, pasted
#: shell output, or harness caveats, not prose the person wrote.
CLAUDE_NON_PROSE_PREFIXES = ("<command-", "<local-command", "<bash-", "Caveat:")


def read_claude_code(root):
    """~/.claude/projects/<slug>/<session>.jsonl

    A record with type "user" is not necessarily a human turn: tool results,
    injected meta-prompts, compaction summaries, and subagent traffic wear the
    same type. Counting those as speech profiles the harness, not the person.
    """
    for path in sorted(Path(root).glob("**/*.jsonl")):
        turns = []
        for rec in _iter_jsonl(path):
            rtype = rec.get("type")
            when = rec.get("timestamp")
            message = rec.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")

            if rtype == "assistant":
                text = _text_of(content).strip()
                if text:
                    turns.append(Turn("assistant", text, when))

            elif rtype == "user":
                if rec.get("isMeta") or rec.get("isSidechain") or rec.get("isCompactSummary"):
                    continue
                if isinstance(content, list):
                    # Any tool_result block means this is the harness feeding
                    # output back, not the user typing.
                    if any(isinstance(b, dict) and b.get("type") == "tool_result"
                           for b in content):
                        continue
                elif not isinstance(content, str):
                    continue
                text = _text_of(content)
                if text.lstrip().startswith(CLAUDE_NON_PROSE_PREFIXES):
                    continue
                if text.strip():
                    turns.append(Turn("user", text, when))
        yield Session(path, turns)


_USER_REQUEST_RE = re.compile(r"<USER_REQUEST>(.*?)</USER_REQUEST>", re.DOTALL)


def read_antigravity(root):
    """transcript.jsonl anywhere beneath a brain or session directory.

    Only USER_EXPLICIT input is a person typing; other sources are the harness
    talking to itself. Older transcripts carry no source field at all, and a
    USER_INPUT record without one is taken as typed.
    """
    for path in sorted(Path(root).glob("**/transcript.jsonl")):
        turns = []
        for rec in _iter_jsonl(path):
            when = rec.get("created_at")
            rtype = rec.get("type")
            text = rec.get("content")
            if not isinstance(text, str) or not text.strip():
                continue
            if rtype == "PLANNER_RESPONSE":
                turns.append(Turn("assistant", text, when))
                continue
            source = rec.get("source")
            if source == "USER_EXPLICIT" or (rtype == "USER_INPUT" and source is None):
                # Antigravity wraps the typed text in a request envelope.
                match = _USER_REQUEST_RE.search(text)
                if match:
                    text = match.group(1)
                turns.append(Turn("user", text, when))
        yield Session(path, turns)


_GEMINI_USER_ROLES = ("user", "human")
_GEMINI_ASSISTANT_ROLES = ("model", "assistant", "gemini")


def _gemini_turn(msg):
    role = msg.get("role") or msg.get("type") or msg.get("sender")
    when = msg.get("timestamp")
    if "user_input" in msg and isinstance(msg["user_input"], str):
        return Turn("user", msg["user_input"], when)
    content = msg.get("content")
    if content is None:
        content = msg.get("text")
    text = _text_of(content)
    if not text.strip():
        return None
    if role in _GEMINI_USER_ROLES:
        return Turn("user", text, when)
    if role in _GEMINI_ASSISTANT_ROLES:
        return Turn("assistant", text, when)
    return None


def read_gemini_cli(root):
    """~/.gemini/tmp/<project>/: chat JSON files and JSONL chat logs.

    A JSON file counts as a session only if it holds a message list, so
    settings files and the like are ignored.
    """
    root = Path(root)
    for path in sorted(root.glob("**/*.json")):
        data = _load_json(path)
        messages = data if isinstance(data, list) else (
            data.get("messages") if isinstance(data, dict) else None)
        if not isinstance(messages, list):
            continue
        turns = [t for t in (_gemini_turn(m) for m in messages if isinstance(m, dict)) if t]
        yield Session(path, turns)
    for path in sorted(root.glob("**/*.jsonl")):
        turns = [t for t in (_gemini_turn(r) for r in _iter_jsonl(path)) if t]
        if turns:
            yield Session(path, turns)


def read_cline(root):
    """Cline and Roo Code: one directory per task, each with ui_messages.json."""
    for path in sorted(Path(root).glob("**/ui_messages.json")):
        messages = _load_json(path)
        if not isinstance(messages, list):
            continue
        turns = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            text = msg.get("text")
            if isinstance(text, str) and text.strip():
                if msg.get("type") == "say" and msg.get("say") == "text":
                    turns.append(Turn("assistant", text))
                    continue
                if msg.get("type") == "ask" and msg.get("ask") == "followup":
                    continue
                if msg.get("say") in ("user_feedback", "task"):
                    turns.append(Turn("user", text))
                    continue
            if msg.get("role") == "user":
                content = _text_of(msg.get("content"))
                if content.strip():
                    turns.append(Turn("user", content))
        yield Session(path, turns)


def _walk_cursor_bubbles(node, depth=0):
    """Cursor nests chat bubbles at varying depths across versions; walk for
    any dict carrying text plus a role-ish discriminator."""
    if depth > 8:
        return
    if isinstance(node, dict):
        text = node.get("text")
        if isinstance(text, str) and len(text.strip()) > 15:
            rtype = node.get("type")
            role = node.get("role")
            is_user = (rtype == 1 or role == "user")
            is_assistant = (rtype == 2 or role in ("assistant", "ai"))
            if is_user or is_assistant:
                yield text, is_user
        for value in node.values():
            yield from _walk_cursor_bubbles(value, depth + 1)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_cursor_bubbles(value, depth + 1)


def _cursor_rows(db_path):
    """Chat rows from a Cursor state.vscdb, opened read-only.

    If Cursor holds a lock, retry as immutable, which reads the file as it
    stands on disk without touching the lock.
    """
    query = "SELECT value FROM ItemTable WHERE key LIKE '%chat%'"
    for suffix in ("?mode=ro", "?mode=ro&immutable=1"):
        try:
            conn = sqlite3.connect(f"file:{db_path}{suffix}", uri=True)
        except sqlite3.Error:
            continue
        try:
            return conn.execute(query).fetchall()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                return None
        except sqlite3.Error:
            return None
        finally:
            conn.close()
    return None


def read_cursor(root):
    """Cursor keeps chat state in a SQLite key-value store (state.vscdb)."""
    for db_path in sorted(Path(root).glob("**/state.vscdb")):
        rows = _cursor_rows(db_path)
        if rows is None:
            continue
        turns = []
        for (value,) in rows:
            if isinstance(value, (bytes, bytearray)):
                value = value.decode("utf-8", errors="ignore")
            try:
                blob = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                continue
            for text, is_user in _walk_cursor_bubbles(blob):
                turns.append(Turn("user" if is_user else "assistant", text))
        yield Session(db_path, turns)


_AIDER_SESSION_RE = re.compile(r"^# aider chat started at (.+?)\s*$")


def _read_aider_chat(path):
    """.aider.chat.history.md: user input is written as `#### ` lines, tool
    output as `> ` blockquotes, and the model's reply as plain lines."""
    sessions = []
    turns, when = [], None
    user_lines, reply_lines = [], []

    def flush_user():
        if user_lines:
            turns.append(Turn("user", "\n".join(user_lines), when))
            user_lines.clear()

    def flush_reply():
        text = "\n".join(reply_lines).strip()
        if text:
            turns.append(Turn("assistant", text, when))
        reply_lines.clear()

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return sessions

    for line in lines:
        started = _AIDER_SESSION_RE.match(line)
        if started:
            flush_user()
            flush_reply()
            if turns:
                sessions.append(Session(path, turns))
            turns, when = [], started.group(1)
            continue
        if line.startswith("#### "):
            flush_reply()
            user_lines.append(line[5:])
            continue
        if line.strip() == "####":
            flush_reply()
            user_lines.append("")
            continue
        flush_user()
        if line.startswith(">"):
            continue
        reply_lines.append(line)
    flush_user()
    flush_reply()
    if turns:
        sessions.append(Session(path, turns))
    return sessions


def _read_aider_input(path):
    """.aider.input.history: `# <timestamp>` then one `+`-prefixed line per
    line of input. Older plain histories have no prefix; take the line as is."""
    turns, when, lines = [], None, []

    def flush():
        text = "\n".join(lines).strip()
        if text:
            turns.append(Turn("user", text, when))
        lines.clear()

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return []
    for line in raw:
        if line.startswith("#"):
            flush()
            when = line.lstrip("#").strip() or None
            continue
        lines.append(line[1:] if line.startswith("+") else line)
    flush()
    return [Session(path, turns)] if turns else []


def read_aider(path):
    """One aider history file: a chat transcript or an input history."""
    path = Path(path)
    if path.is_dir():
        files = aider_files(path)
    else:
        files = [path]
    for item in files:
        if item.name == AIDER_CHAT_FILE:
            yield from _read_aider_chat(item)
        else:
            yield from _read_aider_input(item)


#: Reader per tool name, for callers that dispatch on the names above.
READERS = {
    "antigravity": read_antigravity,
    "antigravity-cli": read_antigravity,
    "antigravity-ide": read_antigravity,
    "gemini-cli": read_gemini_cli,
    "claude-code": read_claude_code,
    "cline": read_cline,
    "roo-code": read_cline,
    "cursor": read_cursor,
    "aider": read_aider,
}


# ---------------------------------------------------------------------------
# Redaction
#
# One table, three consumers: human-voice scrubs prompts with it,
# cognitive-profiler's harvest.py scrubs evidence with it, and
# cognitive-profiler's profile_tool.py rejects a profile that still matches
# it. Separate tables drifted before; a secret one side knew about sailed
# through the other.
#
# Columns: compiled regex, human label (for a validator's error message),
# replacement. Order matters: credentials first, so a key embedded in a URL
# or path is masked as a key; home paths last.
#
# Placeholders are upper-case words in angle brackets, which no pattern here
# matches, so redaction is idempotent and a placeholder is easy to tell from
# anything a person typed. Home directories become `~`, which keeps the rest
# of the path readable.
#
# The assignment-style pattern is deliberately broad. It fires on "password:
# never log it", a false positive. Being noisy about a literal secret in a
# file headed for `git commit` is the trade we want.
#
# Nothing employer-specific belongs here. Users pass their own domains at run
# time (internal_domain_patterns).
# ---------------------------------------------------------------------------

_IPV6 = (
    r"(?<![\w:])(?=[0-9a-f:]*\d)"
    r"(?:(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}"
    r"|(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){0,6})?::"
    r"(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){0,6})?)"
    r"(?![\w:])"
)

#: Hostname suffixes that are internal by convention on any network.
INTERNAL_URL_SUFFIXES = ("internal", "corp", "intranet", "lan", "local")
INTERNAL_HOST_SUFFIXES = ("internal", "corp", "intranet")

# The label can sit anywhere in the name (foo.corp, ci.corp.example.com). The
# whole hostname is consumed, so no suffix such as an employer's domain is left.
_INTERNAL_URL_LABEL = r"(?:" + "|".join(INTERNAL_URL_SUFFIXES) + r")(?![a-z0-9-])"
_INTERNAL_HOST_LABEL = r"(?:" + "|".join(INTERNAL_HOST_SUFFIXES) + r")(?![a-z0-9-])"
_MORE_LABELS = r"(?:\.[a-z0-9-]+)*"
_URL_TAIL = r"(?::[0-9]+)?(?:[/?#][a-z0-9./?=&_%#:~+-]*)?(?<![.,;:])"

SENSITIVE_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
     "email address", "<EMAIL>"),
    (re.compile(r"\bAIzaSy[A-Za-z0-9_-]{33}\b"),
     "Google API key", "<API_KEY>"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
     "Anthropic API key", "<API_KEY>"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
     "OpenAI-style API key", "<API_KEY>"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
     "AWS access key ID", "<API_KEY>"),
    (re.compile(r"\bAI_SHA_KEY_[A-Za-z0-9]{16,}"),
     "prefixed API key", "<API_KEY>"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"),
     "GitHub fine-grained token", "<TOKEN>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
     "GitHub token", "<TOKEN>"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"),
     "GitLab token", "<TOKEN>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
     "Slack token", "<TOKEN>"),
    (re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "JSON Web Token", "<JWT>"),
    (re.compile(r"(?i)\b(?:bearer|authorization:)\s+\S+"),
     "authorization header", "<AUTH>"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+"),
     "assigned secret", "<SECRET>"),
    (re.compile(r"(?i)https?://(?:[a-z0-9-]+\.)*" + _INTERNAL_URL_LABEL
                + _MORE_LABELS + _URL_TAIL),
     "internal URL", "<INTERNAL_URL>"),
    # A label before it (foo.corp), or two after it (corp.example.com).
    (re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+" + _INTERNAL_HOST_LABEL + _MORE_LABELS
                + r"|\b" + _INTERNAL_HOST_LABEL + r"(?:\.[a-z0-9-]+){2,}"),
     "internal hostname", "<COMPANY_DOMAIN>"),
    (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
     "IP address", "<IP_ADDRESS>"),
    (re.compile(_IPV6, re.IGNORECASE),
     "IP address", "<IP_ADDRESS>"),
    (re.compile(r"\b[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+", re.IGNORECASE),  # host-path-ok
     "home directory path", "~"),
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+"),  # host-path-ok
     "home directory path", "~"),
]

#: Placeholders for names a caller supplies.
USER_ID = "<USER_ID>"
USER_NAME = "<USER_NAME>"
USER_NICKNAME = "<USER_NICKNAME>"

#: Every string redaction can emit. A scanner re-checking redacted output can
#: ignore these.
PLACEHOLDERS = frozenset(
    [replacement for _, _, replacement in SENSITIVE_PATTERNS]
    + [USER_ID, USER_NAME, USER_NICKNAME])


def internal_domain_patterns(domains):
    """Rows that redact URLs and hostnames under the given domains, such as an
    employer's intranet. Same shape as SENSITIVE_PATTERNS."""
    rows = []
    for domain in domains or ():
        domain = (domain or "").strip().lstrip(".")
        if not domain:
            continue
        escaped = re.escape(domain) + r"(?![a-z0-9-])"
        rows.append((re.compile(r"(?i)https?://(?:[a-z0-9-]+\.)*" + escaped
                                + _MORE_LABELS + _URL_TAIL),
                     "internal URL", "<INTERNAL_URL>"))
        rows.append((re.compile(r"(?i)(?<![a-z0-9-])(?:[a-z0-9-]+\.)*" + escaped
                                + _MORE_LABELS),
                     "internal hostname", "<COMPANY_DOMAIN>"))
    return rows


def name_patterns(names):
    """Rows that replace each (name, placeholder) pair wherever the name
    appears as a whole word, ignoring case. Text already inside a placeholder
    is left alone, so a login name like "user" cannot mangle "<USER_ID>"."""
    rows = []
    for name, placeholder in names or ():
        name = (name or "").strip()
        if not name:
            continue
        pattern = re.compile(r"(?<![\w<])" + re.escape(name) + r"(?![\w>])",
                             re.IGNORECASE)
        rows.append((pattern, "personal name", placeholder))
    return rows


def login_name():
    """The OS account name, or None if it cannot be determined."""
    try:
        return getpass.getuser() or None
    except Exception:  # getpass raises a platform-specific mix
        return None


def redact(text, extra=(), domains=()):
    """Apply ``domains``, then SENSITIVE_PATTERNS, then ``extra``, to ``text``.

    ``domains`` takes rows from internal_domain_patterns(). They run after the
    email pattern, so an address under the domain is redacted whole, and before
    the built-in internal-host patterns, so those can't consume part of a
    hostname and leave the supplied domain behind. ``extra`` takes rows from
    name_patterns(). Non-strings come back as "".
    """
    if not isinstance(text, str):
        return ""
    at = next(i for i, row in enumerate(SENSITIVE_PATTERNS) if row[1] == "internal URL")
    rows = SENSITIVE_PATTERNS[:at] + list(domains) + SENSITIVE_PATTERNS[at:]
    for pattern, _label, replacement in rows:
        text = pattern.sub(replacement, text)
    for pattern, _label, replacement in extra:
        text = pattern.sub(replacement, text)
    return text
