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
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_sources  # noqa: E402  (local module, path set above)

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

# The shared table in log_sources.py, which the profile validator also rejects
# against, so a pattern added for one is never missing from the other.
REDACTIONS = [(pattern, replacement)
              for pattern, _label, replacement in log_sources.SENSITIVE_PATTERNS]


#: The OS login name, which also turns up in paths and project names.
_LOGIN = log_sources.name_patterns([(log_sources.login_name(), log_sources.USER_ID)])


def redact(text):
    """Strip credentials, internal hosts, personal paths, and the login name."""
    return log_sources.redact(text, _LOGIN)


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
#
# Locations and log formats live in log_sources.py, shared with human-voice.
# ---------------------------------------------------------------------------


def source_roots():
    """Candidate log locations per harness. Layouts differ by version, so each
    harness lists every location we have seen in the wild."""
    return log_sources.source_roots()


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
    #
    # Reading each format is log_sources' job. Here, each session's turns are
    # replayed in order so a user turn can be paired with the length of the
    # response it reacted to.

    def _consume(self, harness, sessions):
        count = 0
        for session in sessions:
            count += 1
            last_assistant_words = None
            for turn in session.turns:
                if turn.role == "assistant":
                    text = turn.text.strip()
                    if text:
                        last_assistant_words = _words(text)
                        self.add_assistant_turn(text, turn.when)
                else:
                    self.add_user_turn(harness, turn.text, turn.when,
                                       last_assistant_words)
        return count

    def parse_claude_code(self, root):
        """~/.claude/projects/<slug>/<session>.jsonl; see log_sources."""
        return self._consume("claude-code", log_sources.read_claude_code(root))

    def parse_antigravity(self, root):
        """transcript.jsonl anywhere beneath the brain/session directory."""
        return self._consume("antigravity", log_sources.read_antigravity(root))

    def parse_gemini_cli(self, root):
        return self._consume("gemini-cli", log_sources.read_gemini_cli(root))

    def parse_cline(self, root, harness):
        """Cline and Roo store one directory per task with ui_messages.json."""
        return self._consume(harness, log_sources.read_cline(root))

    def parse_cursor(self, root):
        """Cursor keeps chat state in a SQLite key-value blob store."""
        return self._consume("cursor", log_sources.read_cursor(root))

    def parse_aider(self, path):
        """An aider chat transcript or input history file."""
        return self._consume("aider", log_sources.read_aider(path))

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
                    elif harness == "aider":
                        sessions += self.parse_aider(root)
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
    for pattern, label, _replacement in log_sources.SENSITIVE_PATTERNS:
        for match in pattern.finditer(text):
            if match.group(0) not in log_sources.PLACEHOLDERS:
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
