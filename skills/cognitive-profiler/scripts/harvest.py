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
harvest.py - Collect evidence about how someone reacts to AI output.

This script observes and counts. It does not score, rank, classify, or
conclude. Every signal it emits is anchored to a redacted verbatim quote
with a source, so that a later judgement can cite it and a human can check
it. Interpretation happens one layer up, by an agent reading
references/rubric.md -- not here in regex.

That split is deliberate. "This person dislikes diagrams" is a judgement
that needs context. "On 2026-04-03 they wrote 'the flowchart didn't help,
just show me the table'" is a fact. This script only produces facts.

CLI:
    harvest.py -o evidence.json
    harvest.py --sources claude-code,antigravity --since 2026-01-01
    harvest.py --list-sources
    harvest.py --check-redaction evidence.json
"""

import argparse
import glob
import json
import os
import platform
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import profile_tool  # noqa: E402  (local module, path set above)

if sys.platform == "win32":  # pragma: no cover - platform guard
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

EVIDENCE_VERSION = "1.0"
MAX_QUOTE_CHARS = 320

# ---------------------------------------------------------------------------
# Redaction
#
# Applied to every string before it reaches the output file. The evidence
# file is meant to be readable, diffable, and safe to hand to a model.
# ---------------------------------------------------------------------------

HOME = Path.home()

# Same table the profile validator rejects against, so a pattern added on one
# side is never missing from the other. See profile_tool.SENSITIVE_PATTERNS.
REDACTIONS = [(pattern, replacement)
              for pattern, _label, replacement in profile_tool.SENSITIVE_PATTERNS]


def redact(text):
    """Strip credentials and personal paths. Order matters: keys before paths."""
    if not isinstance(text, str):
        return ""
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Signals
#
# Each signal names a thing the user *did*, not a trait they *have*. Phrases
# are multi-word wherever a single word would fire on ordinary conversation:
# an earlier version of this tool counted the word "stop" and the word
# "hello" as evidence of cognitive fatigue, which is how you end up with a
# confident profile built from noise.
# ---------------------------------------------------------------------------

SIGNALS = {
    "length_complaint": {
        "means": "Reacted to a response being too long.",
        "phrases": [
            "too long", "too verbose", "wall of text", "shorten", "make it shorter",
            "be concise", "more concise", "tl;dr", "tldr", "cut it down",
            "trim this down", "too much text", "shorter please", "less verbose",
            "you're rambling", "get to the point",
        ],
    },
    "structure_request": {
        "means": "Asked for information to be reshaped into explicit structure.",
        "phrases": [
            "as a table", "in a table", "use a table", "make a table",
            "bullet points", "as bullets", "decision tree", "checklist",
            "summary first", "summarise first", "summarize first",
            "tabulate", "side by side", "comparison table",
        ],
    },
    "structure_rejection": {
        "means": "Rejected structure in favour of prose or raw output.",
        "phrases": [
            "stop with the bullet", "no bullet points", "just write it out",
            "in prose", "plain paragraphs", "too many headings",
            "stop formatting", "drop the tables",
        ],
    },
    "diagram_request": {
        "means": "Asked for a visual representation.",
        "phrases": [
            "draw a diagram", "show me a diagram", "a flowchart", "mermaid",
            "architecture diagram", "sequence diagram", "visualise this",
            "visualize this", "show it visually",
        ],
    },
    "diagram_rejection": {
        "means": "Rejected a diagram as unhelpful or decorative.",
        "phrases": [
            "useless diagram", "pointless diagram", "the diagram didn't help",
            "the diagram doesn't help", "no diagram", "skip the diagram",
            "don't need a diagram", "the flowchart was", "lose the flowchart",
            "delete the diagram", "no mermaid", "redundant diagram",
        ],
    },
    "analogy_rejection": {
        "means": "Rejected analogies, simplification, or a patronising register.",
        "phrases": [
            "patronising", "patronizing", "condescending", "don't dumb it down",
            "stop dumbing", "no analogies", "skip the analogy", "i know what",
            "i'm not a beginner", "explain it like i'm five", "too simplistic",
            "silly analogy",
        ],
    },
    "analogy_request": {
        "means": "Asked for an intuitive or concrete explanation.",
        "phrases": [
            "explain it simply", "in plain english", "what does that mean",
            "give me an analogy", "like what", "intuitively",
            "help me understand", "walk me through it",
        ],
    },
    "directness_request": {
        "means": "Asked for a single recommendation instead of options.",
        "phrases": [
            "just tell me", "pick one", "which one should i", "your recommendation",
            "what would you do", "stop hedging", "make a decision", "just do it",
            "don't give me options", "your opinion",
        ],
    },
    "depth_request": {
        "means": "Asked for more rigour: costs, edge cases, or failure modes.",
        "phrases": [
            "what about the cost", "total cost", "what did you miss", "you missed",
            "edge case", "failure mode", "what breaks", "what's the catch",
            "blind spot", "blindspot", "second order", "what else",
            "gotcha", "trade-off", "tradeoff",
        ],
    },
    "preamble_complaint": {
        "means": "Objected to throat-clearing before the answer.",
        "phrases": [
            "skip the preamble", "no preamble", "stop explaining what you're",
            "don't tell me what you're about to", "get straight to",
            "cut the intro", "stop apologising", "stop apologizing",
        ],
    },
    "repetition_complaint": {
        "means": "Pointed out the assistant repeated or ignored prior instruction.",
        "phrases": [
            "i already said", "i said that", "you already", "as i said",
            "i told you", "you keep", "same mistake", "read what i wrote",
            "stop repeating",
        ],
    },
}

# Compiled once. Multi-word phrases match literally; single-word phrases get
# word boundaries so "again" cannot match "against".
_COMPILED = {
    name: [(p, re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE))
           for p in spec["phrases"]]
    for name, spec in SIGNALS.items()
}


def find_signals(text):
    """Return [(signal, matched_phrase)] for a single utterance, one hit per signal."""
    hits = []
    for name, patterns in _COMPILED.items():
        for phrase, pattern in patterns:
            if pattern.search(text):
                hits.append((name, phrase))
                break
    return hits


# ---------------------------------------------------------------------------
# Source discovery
# ---------------------------------------------------------------------------


def _app_support():
    system = platform.system()
    if system == "Darwin":
        return HOME / "Library" / "Application Support"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
    return Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))


def source_roots():
    """Candidate directories per harness. Layouts differ by version, so each
    harness lists every location we have seen in the wild."""
    app = _app_support()
    return {
        "claude-code": [HOME / ".claude" / "projects"],
        "antigravity": [
            HOME / ".gemini" / "antigravity-cli" / "brain",
            HOME / ".gemini" / "antigravity-ide",
            HOME / ".gemini" / "antigravity" / "brain",
        ],
        "gemini-cli": [HOME / ".gemini" / "tmp"],
        "cline": [app / "Code" / "User" / "globalStorage" /
                  "saoudrizwan.claude-dev" / "tasks"],
        "roo-code": [app / "Code" / "User" / "globalStorage" /
                     "rooveterinaryinc.roo-cline" / "tasks"],
        "cursor": [app / "Cursor" / "User"],
    }


def _words(text):
    return len(text.split())


class Harvest:
    """Accumulates turns and signals across every harness."""

    def __init__(self, since=None, max_quotes_per_signal=8):
        self.since = since
        self.max_quotes_per_signal = max_quotes_per_signal
        self.quotes = []
        self.signal_counts = Counter()
        self.user_word_counts = []
        self.assistant_word_counts = []
        self.response_words_at_complaint = []
        self.sources = {}
        self._next_id = 1

    # -- recording ----------------------------------------------------------

    def _in_window(self, when):
        if not self.since or not when:
            return True
        return when[:10] >= self.since

    def add_user_turn(self, harness, text, when=None, prior_response_words=None):
        text = redact(text).strip()
        if not text:
            return
        if not self._in_window(when):
            return

        self.user_word_counts.append(_words(text))

        for signal, phrase in find_signals(text):
            self.signal_counts[signal] += 1
            if signal == "length_complaint" and prior_response_words:
                self.response_words_at_complaint.append(prior_response_words)
            # Cap quotes per signal: the count carries the frequency, the
            # quotes only need to carry enough texture to judge from.
            kept = sum(1 for q in self.quotes if q["signal"] == signal)
            if kept < self.max_quotes_per_signal:
                snippet = text if len(text) <= MAX_QUOTE_CHARS else (
                    text[:MAX_QUOTE_CHARS].rstrip() + "…")
                quote = {
                    "id": f"q{self._next_id}",
                    "signal": signal,
                    "matched": phrase,
                    "harness": harness,
                    "text": snippet,
                }
                if when:
                    quote["when"] = when[:10]
                if prior_response_words:
                    quote["prior_response_words"] = prior_response_words
                self.quotes.append(quote)
                self._next_id += 1

    def add_assistant_turn(self, text, when=None):
        text = (text or "").strip()
        if not text or not self._in_window(when):
            return
        self.assistant_word_counts.append(_words(text))

    # -- parsers ------------------------------------------------------------

    def _iter_jsonl(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return

    def parse_claude_code(self, root):
        """~/.claude/projects/<slug>/<session>.jsonl

        A record with type "user" is not necessarily a human turn: tool
        results and injected meta-prompts wear the same type. Counting those
        as speech is how you end up profiling the harness instead of the
        person."""
        files = sorted(Path(root).glob("**/*.jsonl"))
        sessions = 0
        for path in files:
            sessions += 1
            last_assistant_words = None
            for rec in self._iter_jsonl(path):
                rtype = rec.get("type")
                when = rec.get("timestamp")

                if rtype == "assistant":
                    message = rec.get("message") or {}
                    content = message.get("content")
                    visible = []
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                visible.append(block.get("text", ""))
                    elif isinstance(content, str):
                        visible.append(content)
                    text = "\n".join(visible).strip()
                    if text:
                        last_assistant_words = _words(text)
                        self.add_assistant_turn(text, when)

                elif rtype == "user":
                    if rec.get("isMeta") or rec.get("isSidechain"):
                        continue
                    message = rec.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        # Any tool_result block means this is the harness
                        # feeding output back, not the user typing.
                        if any(isinstance(b, dict) and b.get("type") == "tool_result"
                               for b in content):
                            continue
                        text = "\n".join(
                            b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
                    else:
                        continue
                    # Slash commands and pasted stdout are not prose.
                    if text.lstrip().startswith(("<command-", "<local-command",
                                                 "<bash-", "Caveat:")):
                        continue
                    self.add_user_turn("claude-code", text, when, last_assistant_words)
        return sessions

    def parse_antigravity(self, root):
        """transcript.jsonl anywhere beneath the brain/session directory."""
        sessions = 0
        for path in sorted(Path(root).glob("**/transcript.jsonl")):
            sessions += 1
            last_assistant_words = None
            for rec in self._iter_jsonl(path):
                when = rec.get("created_at")
                rtype = rec.get("type")

                if rtype == "PLANNER_RESPONSE":
                    text = rec.get("content") or ""
                    if isinstance(text, str) and text.strip():
                        last_assistant_words = _words(text)
                        self.add_assistant_turn(text, when)

                elif rtype == "USER_INPUT" and rec.get("source") == "USER_EXPLICIT":
                    text = rec.get("content")
                    if not isinstance(text, str):
                        continue
                    # Antigravity wraps the typed text in a request envelope.
                    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>",
                                      text, re.DOTALL)
                    if match:
                        text = match.group(1)
                    self.add_user_turn("antigravity", text, when, last_assistant_words)
        return sessions

    def parse_gemini_cli(self, root):
        sessions = 0
        for path in sorted(Path(root).glob("**/*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            messages = data if isinstance(data, list) else data.get("messages")
            if not isinstance(messages, list):
                continue
            sessions += 1
            last_assistant_words = None
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role") or msg.get("type")
                text = msg.get("content") or msg.get("text") or ""
                if not isinstance(text, str) or not text.strip():
                    continue
                if role in ("user", "human"):
                    self.add_user_turn("gemini-cli", text, None, last_assistant_words)
                elif role in ("model", "assistant"):
                    last_assistant_words = _words(text)
                    self.add_assistant_turn(text)
        return sessions

    def parse_cline(self, root, harness):
        """Cline and Roo store one directory per task with ui_messages.json."""
        sessions = 0
        for path in sorted(Path(root).glob("**/ui_messages.json")):
            try:
                messages = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(messages, list):
                continue
            sessions += 1
            last_assistant_words = None
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                text = msg.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                if msg.get("type") == "say" and msg.get("say") == "text":
                    last_assistant_words = _words(text)
                    self.add_assistant_turn(text)
                elif msg.get("type") == "ask" and msg.get("ask") == "followup":
                    continue
                elif msg.get("say") in ("user_feedback", "task"):
                    self.add_user_turn(harness, text, None, last_assistant_words)
        return sessions

    def parse_cursor(self, root):
        """Cursor keeps chat state in a SQLite key-value blob store."""
        sessions = 0
        for db_path in sorted(Path(root).glob("**/state.vscdb")):
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            except sqlite3.Error:
                continue
            try:
                rows = conn.execute(
                    "SELECT value FROM ItemTable WHERE key LIKE '%chat%'"
                ).fetchall()
            except sqlite3.Error:
                conn.close()
                continue
            conn.close()
            sessions += 1
            for (value,) in rows:
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode("utf-8", errors="ignore")
                try:
                    blob = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    continue
                for text, is_user in _walk_cursor_bubbles(blob):
                    if is_user:
                        self.add_user_turn("cursor", text)
                    else:
                        self.add_assistant_turn(text)
        return sessions

    # -- driver -------------------------------------------------------------

    def run(self, wanted=None):
        roots = source_roots()
        for harness, candidates in roots.items():
            if wanted and harness not in wanted:
                continue
            found = [p for p in candidates if p.exists()]
            if not found:
                self.sources[harness] = {"status": "not-found", "sessions": 0}
                continue
            sessions = 0
            for root in found:
                try:
                    if harness == "claude-code":
                        sessions += self.parse_claude_code(root)
                    elif harness == "antigravity":
                        sessions += self.parse_antigravity(root)
                    elif harness == "gemini-cli":
                        sessions += self.parse_gemini_cli(root)
                    elif harness in ("cline", "roo-code"):
                        sessions += self.parse_cline(root, harness)
                    elif harness == "cursor":
                        sessions += self.parse_cursor(root)
                except (OSError, RecursionError) as exc:
                    self.sources[harness] = {"status": f"error: {exc}", "sessions": 0}
                    break
            else:
                self.sources[harness] = {
                    "status": "read" if sessions else "empty",
                    "sessions": sessions,
                }
        return self

    # -- output -------------------------------------------------------------

    def report(self):
        user_turns = len(self.user_word_counts)
        total_signals = sum(self.signal_counts.values())

        # Coverage decides whether the agent may judge from logs at all.
        if user_turns < 40 or total_signals < 5:
            level, advice = "thin", (
                "Not enough signal to judge from logs. Run the calibration "
                "questions in references/calibration.md instead, and mark the "
                "resulting claims as 'declared'.")
        elif total_signals < 20:
            level, advice = "partial", (
                "Enough to ground some dimensions. Leave the rest 'unknown' "
                "and close the gaps with calibration questions.")
        else:
            level, advice = "adequate", (
                "Enough signal to ground most dimensions as 'observed'. Still "
                "confirm the result with the user before rendering.")

        return {
            "evidence_version": EVIDENCE_VERSION,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_start": self.since,
            "sources": self.sources,
            "coverage": {
                "level": level,
                "advice": advice,
                "user_turns": user_turns,
                "assistant_turns": len(self.assistant_word_counts),
                "sessions": sum(s.get("sessions", 0) for s in self.sources.values()),
                "signal_hits": total_signals,
            },
            "stats": {
                "user_words": _distribution(self.user_word_counts),
                "assistant_words": _distribution(self.assistant_word_counts),
                "assistant_words_when_length_complained": _distribution(
                    self.response_words_at_complaint),
            },
            "signals": {
                name: {
                    "count": self.signal_counts.get(name, 0),
                    "means": spec["means"],
                    "quotes": [q["id"] for q in self.quotes if q["signal"] == name],
                }
                for name, spec in SIGNALS.items()
                if self.signal_counts.get(name, 0)
            },
            "quotes": self.quotes,
        }


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


def _distribution(values):
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    n = len(ordered)

    def pct(p):
        return ordered[min(n - 1, int(round((p / 100.0) * (n - 1))))]

    return {
        "n": n,
        "median": pct(50),
        "p75": pct(75),
        "p90": pct(90),
        "max": ordered[-1],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_list_sources():
    print("Harness log locations on this machine:\n")
    for harness, candidates in source_roots().items():
        for path in candidates:
            mark = "found  " if path.exists() else "missing"
            display = str(path).replace(str(HOME), "~")
            print(f"  [{mark}] {harness:<14} {display}")
    return 0


def _cmd_check_redaction(path):
    """Re-scan a written evidence file. Belt and braces: the file is meant to
    be safe to share, so verify rather than trust."""
    text = Path(path).read_text(encoding="utf-8")
    leaks = []
    for pattern, label in REDACTIONS:
        for match in pattern.finditer(text):
            if match.group(0) not in ("<email>", "<api-key>", "<token>", "~"):
                leaks.append((label, match.group(0)[:60]))
    if leaks:
        print(f"{len(leaks)} possible leak(s) survived redaction:", file=sys.stderr)
        for label, sample in leaks[:20]:
            print(f"  {label}: {sample}", file=sys.stderr)
        return 1
    print(f"{path}: clean")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Harvest redacted evidence about AI-output preferences. "
                    "Counts and quotes only; no scoring.")
    parser.add_argument("-o", "--output", default="evidence.json")
    parser.add_argument("--sources", help="comma-separated subset, e.g. "
                                          "claude-code,antigravity")
    parser.add_argument("--since", help="ISO date; ignore turns before it")
    parser.add_argument("--max-quotes", type=int, default=8,
                        help="quotes kept per signal (default 8)")
    parser.add_argument("--stdout", action="store_true",
                        help="print the report instead of writing a file")
    parser.add_argument("--list-sources", action="store_true",
                        help="show which harness logs exist here, then exit")
    parser.add_argument("--check-redaction", metavar="FILE",
                        help="re-scan an evidence file for leaked secrets")
    args = parser.parse_args(argv)

    if args.list_sources:
        return _cmd_list_sources()
    if args.check_redaction:
        return _cmd_check_redaction(args.check_redaction)

    wanted = None
    if args.sources:
        wanted = {s.strip() for s in args.sources.split(",") if s.strip()}
        unknown = wanted - set(source_roots())
        if unknown:
            print(f"error: unknown source(s): {', '.join(sorted(unknown))}",
                  file=sys.stderr)
            return 2

    harvest = Harvest(since=args.since, max_quotes_per_signal=args.max_quotes)
    harvest.run(wanted)
    report = harvest.report()

    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.stdout:
        print(payload)
    else:
        Path(args.output).write_text(payload, encoding="utf-8")

    cov = report["coverage"]
    print(f"Read {cov['sessions']} session(s) across "
          f"{sum(1 for s in report['sources'].values() if s['status'] == 'read')} "
          f"harness(es).", file=sys.stderr)
    print(f"{cov['user_turns']} user turns, {cov['signal_hits']} signal hits, "
          f"{len(report['quotes'])} quotes retained.", file=sys.stderr)
    print(f"Coverage: {cov['level']} -- {cov['advice']}", file=sys.stderr)
    if not args.stdout:
        print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
