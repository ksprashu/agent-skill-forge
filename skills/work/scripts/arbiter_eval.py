#!/usr/bin/env python3
"""Arbiter evidence collector for the design and implementation tournaments.

Part of the Work Swarm Engine (``skills/work``).

This script **does not rank proposals and does not emit a score.** It collects
facts and hands them to the Arbiter agent, which judges. That split is the
repo's standing rule for judgement tasks (``docs/ENGINEERING_STANDARD.md`` §S9):
a script may count, quote, measure, and execute; deciding which architecture is
better is not one of those things.

The previous version scored design documents out of 100 from heading regexes,
fenced-block counts, and line count. On 2026-09-23 it was measured against two
real proposals and scored a content-free document **95** and a rigorous one
**40**, then recommended the content-free one. It was anti-correlated with
quality, and because the Design Architects can read this file, it taught them
to write headings instead of designs. See ``docs/review/2026-09-23-work-skill-review.md``
finding W-03.

Two modes:

* **Design evidence** (``--design-alpha/--design-beta``): structural and
  linguistic facts about two proposal documents. No verdict.
* **Implementation measurement** (``--alpha-test/--beta-test``): real measured
  quantities — exit codes, wall-clock, line counts. A verdict is emitted only
  where it is mechanically determined (one candidate's tests fail and the
  other's pass). Otherwise the comparison is handed back for judgement.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":  # pragma: no cover - platform specific
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

VERDICT_JUDGEMENT_REQUIRED = "JUDGEMENT_REQUIRED"

#: Words that signal generated filler rather than authored prose. Kept in sync
#: with skills/unslop by hand; see W-08 for why that is a known weakness.
AI_SLOP_WORDS = frozenset({
    "delve", "testament", "tapestry", "seamless", "seamlessly", "crucial",
    "leverage", "leveraging", "robust", "plethora", "beacon", "cutting-edge",
    "paramount", "pivotal", "foster", "fostering", "game-changer", "elevate",
    "underscore", "underscores", "myriad", "realm", "landscape",
})

#: Phrases that promise a decision without making one. A design document made
#: mostly of these has described the shape of a design, not a design.
HEDGE_PHRASES = (
    "will be defined", "will be determined", "to be determined", "will be added",
    "should be", "can be configured", "as needed", "as appropriate",
    "where applicable", "appropriately", "have been considered",
    "has been considered", "follows established patterns", "well-defined",
    "clear responsibilities", "solid foundation", "meets the requirements",
    "best practices", "industry standard", "handled gracefully",
    "degrades gracefully", "in a future phase", "out of scope for this iteration",
)

UNRESOLVED_MARKER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX|\?\?\?|<placeholder>)\b", re.IGNORECASE)

#: A number attached to a unit. The signature of a claim someone measured
#: rather than asserted.
MEASURED_CLAIM_RE = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:ms|µs|us|ns|sec|secs|seconds?|minutes?|hours?|days?"
    r"|%|x\b|×|kb|mb|gb|tb|kib|mib|gib"
    r"|qps|rps|tps|iops|ops|rows?|jobs?|requests?|connections?|workers?"
    r"|vcpus?|cores?|threads?|bytes?)"
    r"|\b(?:p50|p95|p99|p999)\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s*/\s*(?:sec|second|s|min|minute|hour|h)\b",
    re.IGNORECASE,
)

#: Language that names what was not chosen, and why.
ALTERNATIVE_RE = re.compile(
    r"\b(instead of|rather than|the alternative|alternatively|we rejected|"
    r"ruled out|loses because|wins because|migration path|not doing|"
    r"trade-?off|versus|\bvs\.?\b)", re.IGNORECASE,
)

PLACEHOLDER_BODIES = {"", "TBD", "TODO", "FIXME", "N/A", "NA", "PLACEHOLDER", "..."}

CODE_FENCE_RE = re.compile(r"^```([a-zA-Z0-9_+\-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Subprocess
# ---------------------------------------------------------------------------

def run_command(cmd: str, cwd: str = ".", timeout: int = 900) -> tuple[int, str, str, float]:
    """Run ``cmd`` as an argv list. Never through a shell (W-11).

    Commands originate in agent-authored Markdown; a shell here is a command
    injection path. If a pipeline is genuinely needed, put it in a script and
    invoke the script.
    """
    argv = shlex.split(cmd)
    if not argv:
        return 2, "", "empty command", 0.0
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s", float(timeout)
    except OSError as exc:
        return 127, "", f"could not execute {argv[0]!r}: {exc}", 0.0
    return proc.returncode, proc.stdout, proc.stderr, time.perf_counter() - start


# ---------------------------------------------------------------------------
# Design evidence
# ---------------------------------------------------------------------------

def _split_code_blocks(content: str) -> tuple[list[dict], str]:
    """Return (blocks, prose) — prose is the content with fences removed."""
    blocks: list[dict] = []
    prose_lines: list[str] = []
    current: dict | None = None
    buffer: list[str] = []

    for lineno, line in enumerate(content.splitlines(), 1):
        fence = CODE_FENCE_RE.match(line)
        if fence and current is None:
            current = {"lang": fence.group(1) or "none", "start_line": lineno}
            buffer = []
            continue
        if line.strip().startswith("```") and current is not None:
            body = [b for b in buffer if b.strip()]
            joined = "\n".join(body).strip()
            normalised = joined.strip().strip("`").strip().upper().rstrip(".")
            current["lines"] = len(body)
            if normalised in PLACEHOLDER_BODIES or not joined:
                current["kind"] = "placeholder"
            elif len(body) < 3:
                current["kind"] = "trivial"
            else:
                current["kind"] = "substantive"
            blocks.append(current)
            current = None
            continue
        if current is not None:
            buffer.append(line)
        else:
            prose_lines.append(line)

    if current is not None:  # unterminated fence
        current["lines"] = len([b for b in buffer if b.strip()])
        current["kind"] = "unterminated"
        blocks.append(current)

    return blocks, "\n".join(prose_lines)


def collect_design_evidence(name: str, file_path: str) -> dict:
    """Facts about a design proposal. No score, no ranking, no verdict."""
    path = Path(file_path)
    evidence: dict = {
        "name": name,
        "path": file_path,
        "exists": path.exists(),
        "headings": [],
        "total_lines": 0,
        "prose_words": 0,
        "code_blocks": {"substantive": 0, "trivial": 0, "placeholder": 0, "unterminated": 0},
        "code_block_detail": [],
        "measured_claims": [],
        "named_alternatives": [],
        "unresolved_markers": [],
        "hedge_phrases": [],
        "slop_words": [],
        "backticked_identifiers": 0,
        "distinct_identifiers": 0,
    }
    if not path.exists():
        return evidence

    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    evidence["total_lines"] = len(lines)
    evidence["headings"] = [m.group(2) for m in HEADING_RE.finditer(content)]

    blocks, prose = _split_code_blocks(content)
    evidence["code_block_detail"] = blocks
    for block in blocks:
        evidence["code_blocks"][block["kind"]] = evidence["code_blocks"].get(block["kind"], 0) + 1
    evidence["prose_words"] = len(re.findall(r"\b[\w'-]+\b", prose))

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        if MEASURED_CLAIM_RE.search(stripped):
            evidence["measured_claims"].append({"line": lineno, "text": stripped[:160]})
        if ALTERNATIVE_RE.search(stripped):
            evidence["named_alternatives"].append({"line": lineno, "text": stripped[:160]})
        for match in UNRESOLVED_MARKER_RE.finditer(stripped):
            evidence["unresolved_markers"].append({"line": lineno, "marker": match.group(0)})

    lowered = prose.lower()
    for phrase in HEDGE_PHRASES:
        count = lowered.count(phrase)
        if count:
            evidence["hedge_phrases"].append({"phrase": phrase, "count": count})
    evidence["hedge_phrases"].sort(key=lambda item: -item["count"])

    words = re.findall(r"\b[a-zA-Z][a-zA-Z\-]+\b", lowered)
    slop: dict[str, int] = {}
    for word in words:
        if word in AI_SLOP_WORDS:
            slop[word] = slop.get(word, 0) + 1
    evidence["slop_words"] = sorted(
        ({"word": w, "count": c} for w, c in slop.items()), key=lambda item: -item["count"])

    identifiers = re.findall(r"`([^`\n]{1,60})`", content)
    evidence["backticked_identifiers"] = len(identifiers)
    evidence["distinct_identifiers"] = len({i.strip() for i in identifiers})

    return evidence


#: (label, extractor, "higher is better?"). ``None`` means neither direction is
#: automatically better — that is exactly the judgement the Arbiter must make.
DESIGN_SIGNALS: tuple[tuple[str, str, bool | None], ...] = (
    ("Headings", "n_headings", None),
    ("Prose words", "prose_words", None),
    ("Substantive code/schema blocks", "n_substantive", True),
    ("Trivial code blocks (<3 lines)", "n_trivial", False),
    ("Placeholder blocks (TBD/empty)", "n_placeholder", False),
    ("Measured claims (number + unit)", "n_measured", True),
    ("Named alternatives & trade-offs", "n_alternatives", True),
    ("Unresolved markers (TBD/TODO/???)", "n_unresolved", False),
    ("Hedge phrases", "n_hedges", False),
    ("AI slop words", "n_slop", False),
    ("Distinct backticked identifiers", "distinct_identifiers", True),
)


def _signal_values(evidence: dict) -> dict[str, int]:
    blocks = evidence["code_blocks"]
    return {
        "n_headings": len(evidence["headings"]),
        "prose_words": evidence["prose_words"],
        "n_substantive": blocks.get("substantive", 0),
        "n_trivial": blocks.get("trivial", 0),
        "n_placeholder": blocks.get("placeholder", 0) + blocks.get("unterminated", 0),
        "n_measured": len(evidence["measured_claims"]),
        "n_alternatives": len(evidence["named_alternatives"]),
        "n_unresolved": len(evidence["unresolved_markers"]),
        "n_hedges": sum(h["count"] for h in evidence["hedge_phrases"]),
        "n_slop": sum(s["count"] for s in evidence["slop_words"]),
        "distinct_identifiers": evidence["distinct_identifiers"],
    }


def compare_design_evidence(alpha: dict, beta: dict) -> dict:
    """Lay the two evidence sets side by side. Emit no ranking."""
    missing = [e["name"] for e in (alpha, beta) if not e["exists"]]
    questions = [
        "Does each proposal commit to a specific mechanism, or describe the shape of one?",
        "Which measured claims are reproducible, and which are asserted?",
        "What does each proposal refuse to do, and is that refusal correct?",
        "Where the two differ, is the difference a trade-off for the user to decide, "
        "or a mistake by one of them?",
        "Does either proposal's failure analysis name a failure that is specific to "
        "this design, rather than a generic one?",
    ]
    return {
        "type": "design",
        "verdict": VERDICT_JUDGEMENT_REQUIRED,
        "missing_proposals": missing,
        "alpha": alpha,
        "beta": beta,
        "signals": {"alpha": _signal_values(alpha), "beta": _signal_values(beta)},
        "questions_for_the_arbiter": questions,
    }


# ---------------------------------------------------------------------------
# Implementation measurement
# ---------------------------------------------------------------------------

def count_code_metrics(dir_path: str) -> dict:
    metrics = {"file_count": 0, "total_lines": 0, "files_over_150_lines": 0,
               "median_lines_per_file": 0, "max_lines_in_a_file": 0}
    path = Path(dir_path)
    if not path.exists():
        return metrics

    sizes: list[int] = []
    for ext in ("*.py", "*.ts", "*.js", "*.go", "*.rs", "*.java", "*.rb"):
        for file in path.rglob(ext):
            if any(part in (".git", "node_modules", ".venv", "__pycache__", "dist", "build")
                   for part in file.parts):
                continue
            try:
                count = len(file.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
            sizes.append(count)

    if sizes:
        metrics["file_count"] = len(sizes)
        metrics["total_lines"] = sum(sizes)
        metrics["files_over_150_lines"] = sum(1 for s in sizes if s > 150)
        metrics["median_lines_per_file"] = int(statistics.median(sizes))
        metrics["max_lines_in_a_file"] = max(sizes)
    return metrics


def measure_candidate(name: str, test_cmd: str | None, bench_cmd: str | None,
                      code_dir: str, timeout: int = 900) -> dict:
    """Measure a candidate. Every field here is an observation, not a rating."""
    print(f"Measuring {name}...", file=sys.stderr)
    result = {
        "name": name,
        "code_dir": code_dir,
        "test_cmd": test_cmd,
        "test_run": False,
        "test_exit_code": None,
        "test_passed": None,
        "test_duration_s": None,
        "bench_run": False,
        "bench_duration_s": None,
        "code_metrics": count_code_metrics(code_dir),
    }
    if test_cmd:
        code, _out, _err, duration = run_command(test_cmd, cwd=".", timeout=timeout)
        result.update(test_run=True, test_exit_code=code, test_passed=(code == 0),
                      test_duration_s=round(duration, 3))
    if bench_cmd:
        _c, _o, _e, duration = run_command(bench_cmd, cwd=".", timeout=timeout)
        result.update(bench_run=True, bench_duration_s=round(duration, 3))
    return result


def compare_candidates(alpha: dict, beta: dict) -> dict:
    """Compare measurements. Decide only what the measurements decide."""
    verdict = VERDICT_JUDGEMENT_REQUIRED
    basis = ("Both candidates are viable on the measurements below. Which is better "
             "is a judgement about the code, not a number — read both diffs.")

    a_pass, b_pass = alpha["test_passed"], beta["test_passed"]
    if a_pass is False and b_pass is True:
        verdict, basis = "SELECT_BETA", f"Alpha's test command exited {alpha['test_exit_code']}; Beta's exited 0."
    elif a_pass is True and b_pass is False:
        verdict, basis = "SELECT_ALPHA", f"Beta's test command exited {beta['test_exit_code']}; Alpha's exited 0."
    elif a_pass is False and b_pass is False:
        verdict, basis = "BOTH_REJECTED", "Neither candidate's test command exits 0. There is nothing to choose between."
    elif not alpha["test_run"] or not beta["test_run"]:
        basis = ("No test command was supplied for at least one candidate, so correctness "
                 "is unmeasured. The line counts below say nothing about it.")

    return {
        "type": "implementation",
        "verdict": verdict,
        "basis": basis,
        "alpha": alpha,
        "beta": beta,
        "questions_for_the_arbiter": [
            "Do the two test suites actually constrain the same behaviour, or does one "
            "assert less? Run forensic_audit.py --mutate on each before trusting a green run.",
            "Is the faster candidate faster on the workload that matters, or on the benchmark?",
            "Which one will be easier to change in six months, and on what evidence?",
        ],
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_examples(items: list[dict], key: str, limit: int = 3) -> str:
    if not items:
        return "_none_"
    shown = [f"L{i['line']}: {i[key]}" for i in items[:limit]]
    suffix = f" _(+{len(items) - limit} more)_" if len(items) > limit else ""
    return "<br/>".join(f"`{s}`" for s in shown) + suffix


def render_design_report(data: dict) -> str:
    alpha, beta = data["alpha"], data["beta"]
    sa, sb = data["signals"]["alpha"], data["signals"]["beta"]

    rows = []
    for label, key, higher_better in DESIGN_SIGNALS:
        direction = {True: "more is better", False: "fewer is better", None: "neither"}[higher_better]
        rows.append(f"| {label} | {sa[key]} | {sb[key]} | {direction} |")

    missing = ""
    if data["missing_proposals"]:
        missing = f"\n> **Missing proposal(s)**: {', '.join(data['missing_proposals'])}\n"

    return f"""# Architectural Arbiter — Evidence Report

> **Verdict: {data['verdict']}.** This script collects evidence; it does not rank
> proposals and does not produce a score. The Arbiter agent reads the evidence
> below, reads both documents in full, and decides. A number here would be a
> guess wearing a uniform.
{missing}
- **Alpha**: `{alpha['path']}` ({alpha['total_lines']} lines, {'present' if alpha['exists'] else 'MISSING'})
- **Beta**: `{beta['path']}` ({beta['total_lines']} lines, {'present' if beta['exists'] else 'MISSING'})

## Discriminating signals

| Signal | Alpha | Beta | Direction |
|---|---|---|---|
{chr(10).join(rows)}

"Direction" says which way a signal usually points, not how much it is worth.
A proposal can have many measured claims and still be wrong.

## Measured claims

| | Alpha | Beta |
|---|---|---|
| Count | {sa['n_measured']} | {sb['n_measured']} |
| Examples | {_fmt_examples(alpha['measured_claims'], 'text')} | {_fmt_examples(beta['measured_claims'], 'text')} |

## Named alternatives and trade-offs

| | Alpha | Beta |
|---|---|---|
| Count | {sa['n_alternatives']} | {sb['n_alternatives']} |
| Examples | {_fmt_examples(alpha['named_alternatives'], 'text')} | {_fmt_examples(beta['named_alternatives'], 'text')} |

## Unresolved markers

| | Alpha | Beta |
|---|---|---|
| Count | {sa['n_unresolved']} | {sb['n_unresolved']} |
| Markers | {_fmt_examples(alpha['unresolved_markers'], 'marker')} | {_fmt_examples(beta['unresolved_markers'], 'marker')} |

## Language

| | Alpha | Beta |
|---|---|---|
| Hedge phrases | {', '.join(f"{h['phrase']} ({h['count']})" for h in alpha['hedge_phrases'][:4]) or '_none_'} | {', '.join(f"{h['phrase']} ({h['count']})" for h in beta['hedge_phrases'][:4]) or '_none_'} |
| AI slop | {', '.join(f"{s['word']} ({s['count']})" for s in alpha['slop_words'][:4]) or '_none_'} | {', '.join(f"{s['word']} ({s['count']})" for s in beta['slop_words'][:4]) or '_none_'} |

## Headings present

- **Alpha**: {', '.join(f'`{h}`' for h in alpha['headings'][:12]) or '_none_'}
- **Beta**: {', '.join(f'`{h}`' for h in beta['headings'][:12]) or '_none_'}

Headings are listed, not scored. A document with every expected heading and
nothing under them scores well on structure and badly on being a design.

## What this evidence cannot tell you

- Whether either design is **correct**, or will work at the required scale.
- Whether a measured claim was actually measured, or typed.
- Whether the omitted alternative was omitted deliberately or not considered.
- Whether the two proposals are genuinely different, or the same design twice.

## Questions the Arbiter must answer in `DESIGN.md`

{chr(10).join(f'{i}. {q}' for i, q in enumerate(data['questions_for_the_arbiter'], 1))}
"""


def render_implementation_report(data: dict) -> str:
    alpha, beta = data["alpha"], data["beta"]
    am, bm = alpha["code_metrics"], beta["code_metrics"]

    def cell(value, suffix=""):
        return "_not measured_" if value is None else f"{value}{suffix}"

    return f"""# Implementation Tournament — Measurement Report

> **Verdict: {data['verdict']}.** {data['basis']}

## Measurements

| Observation | Alpha | Beta |
|---|---|---|
| Test command | `{alpha['test_cmd'] or 'none supplied'}` | `{beta['test_cmd'] or 'none supplied'}` |
| Test exit code | {cell(alpha['test_exit_code'])} | {cell(beta['test_exit_code'])} |
| Test wall clock | {cell(alpha['test_duration_s'], 's')} | {cell(beta['test_duration_s'], 's')} |
| Benchmark wall clock | {cell(alpha['bench_duration_s'], 's')} | {cell(beta['bench_duration_s'], 's')} |
| Source files | {am['file_count']} | {bm['file_count']} |
| Total lines | {am['total_lines']} | {bm['total_lines']} |
| Median lines/file | {am['median_lines_per_file']} | {bm['median_lines_per_file']} |
| Largest file | {am['max_lines_in_a_file']} | {bm['max_lines_in_a_file']} |
| Files over 150 lines | {am['files_over_150_lines']} | {bm['files_over_150_lines']} |

Wall clock is one sample on a shared machine. Treat a difference under roughly
20% as noise unless it is reproduced.

## What these measurements cannot tell you

- **Maintainability.** There is no mechanical proxy for it, so none is offered.
  The previous version of this script awarded both candidates a fixed 15 points
  for it, which inflated both totals and discriminated nothing (W-03).
- Whether a green suite means correct code. Run
  `forensic_audit.py --mutate --test-cmd ...` against each candidate first.
- Whether fewer lines means simpler, or means less handled.

## Questions the Arbiter must answer

{chr(10).join(f'{i}. {q}' for i, q in enumerate(data['questions_for_the_arbiter'], 1))}
"""


def render_report(data: dict) -> str:
    return render_design_report(data) if data.get("type") == "design" else render_implementation_report(data)


def write_report(data: dict, output_file: str | None, quiet: bool = False) -> str:
    markdown = render_report(data)
    if not quiet:
        print("\n" + markdown)
    if output_file:
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        print(f"Saved report to {output_file}", file=sys.stderr)
    return markdown


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Arbiter evidence collector (skills/work). Collects facts; does not rank.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--alpha-dir", default=".", help="Path to Worker Alpha code")
    parser.add_argument("--beta-dir", default=".", help="Path to Worker Beta code")
    parser.add_argument("--alpha-test", help="Test command for Alpha (argv, not a shell line)")
    parser.add_argument("--beta-test", help="Test command for Beta (argv, not a shell line)")
    parser.add_argument("--bench-cmd", help="Benchmark command run against both candidates")
    parser.add_argument("--design-alpha", help="Path to Proposal Alpha markdown")
    parser.add_argument("--design-beta", help="Path to Proposal Beta markdown")
    parser.add_argument("--output-scorecard", "--output-report",
                        default=".agents/design/arbiter_evidence.md",
                        help="Where to write the markdown evidence report")
    parser.add_argument("--json", action="store_true", help="Emit the evidence as JSON on stdout")
    parser.add_argument("--quiet", "-q", action="store_true", help="Do not print the markdown report")
    parser.add_argument("--timeout", type=int, default=900, help="Per-command timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.design_alpha or args.design_beta:
        alpha_path = args.design_alpha or ".agents/design/proposals/proposal_alpha.md"
        beta_path = args.design_beta or ".agents/design/proposals/proposal_beta.md"
        data = compare_design_evidence(
            collect_design_evidence("Proposal Alpha", alpha_path),
            collect_design_evidence("Proposal Beta", beta_path),
        )
    else:
        data = compare_candidates(
            measure_candidate("Worker Alpha", args.alpha_test, args.bench_cmd,
                              args.alpha_dir, args.timeout),
            measure_candidate("Worker Beta", args.beta_test, args.bench_cmd,
                              args.beta_dir, args.timeout),
        )

    if args.json:
        print(json.dumps(data, indent=2))
        if args.output_scorecard:
            write_report(data, args.output_scorecard, quiet=True)
    else:
        write_report(data, args.output_scorecard, quiet=args.quiet)

    if data.get("missing_proposals"):
        return 2
    if data["verdict"] == "BOTH_REJECTED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
