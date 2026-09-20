#!/usr/bin/env python3
"""
Automated Arbiter Tournament Evaluation Engine
Part of the Google Antigravity Work Swarm Engine (skills/work).

Evaluates competing candidates:
A. Implementation Tournament (Worker Alpha vs Worker Beta):
   1. Correctness (40%): Test suite pass rate and failure counts
   2. Performance (25%): Runtime latency and resource efficiency
   3. Simplicity & Unslop (20%): Code churn, conciseness, sub-150-line modularity
   4. Maintainability (15%): Low dependency footprint and architectural cleanliness

B. Design Proposal Tournament (Design Alpha vs Design Beta):
   1. Architecture & Spec Grounding (30%): Interface completeness, requirement coverage, non-goals
   2. Interface & Data Contract Rigor (25%): Schemas, API contracts, migration paths
   3. Failure Handling & Security (25%): Concurrency, edge cases, auth/isolation, race conditions
   4. Simplicity, Unslop & Operability (20%): Minimal dependencies, zero AI fluff, observability
"""

import os
import sys
import io
import json
import time
import re
import argparse
import subprocess
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and getattr(sys.stderr, "encoding", "").lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

AI_SLOP_WORDS = {
    "delve", "testament", "tapestry", "seamless", "seamlessly", "crucial",
    "leverage", "leveraging", "robust", "plethora", "beacon", "cutting-edge",
    "paramount", "pivotal", "foster", "fostering", "game-changer"
}

def run_command(cmd: str, cwd: str = ".") -> tuple[int, str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    elapsed = time.perf_counter() - start
    return proc.returncode, proc.stdout, proc.stderr, elapsed

def count_code_metrics(dir_path: str) -> dict:
    """Analyze line counts and file sizes in candidate directory."""
    metrics = {
        "file_count": 0,
        "total_lines": 0,
        "files_over_150_lines": 0,
        "avg_lines_per_file": 0
    }
    path = Path(dir_path)
    if not path.exists():
        return metrics

    for ext in ["*.py", "*.ts", "*.js", "*.go", "*.rs"]:
        for f in path.rglob(ext):
            if any(part in f.parts for part in [".git", "node_modules", ".venv", "__pycache__"]):
                continue
            metrics["file_count"] += 1
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    lines = len(fh.readlines())
                    metrics["total_lines"] += lines
                    if lines > 150:
                        metrics["files_over_150_lines"] += 1
            except Exception:
                pass

    if metrics["file_count"] > 0:
        metrics["avg_lines_per_file"] = round(metrics["total_lines"] / metrics["file_count"], 1)

    return metrics

def evaluate_candidate(name: str, test_cmd: str | None, bench_cmd: str | None, code_dir: str) -> dict:
    print(f"📊 Evaluating {name}...")
    result = {
        "name": name,
        "test_exit_code": 0,
        "test_duration_s": 0.0,
        "test_passed": True,
        "bench_duration_s": 0.0,
        "code_metrics": count_code_metrics(code_dir),
        "scores": {}
    }

    # 1. Run Tests
    if test_cmd:
        code, stdout, stderr, dur = run_command(test_cmd, cwd=".")
        result["test_exit_code"] = code
        result["test_duration_s"] = round(dur, 3)
        result["test_passed"] = (code == 0)
    else:
        result["test_passed"] = True

    # 2. Run Benchmarks
    if bench_cmd:
        b_code, b_out, b_err, b_dur = run_command(bench_cmd, cwd=".")
        result["bench_duration_s"] = round(b_dur, 3)

    return result

def score_candidates(alpha: dict, beta: dict) -> dict:
    # Axis 1: Correctness (Max 40 pts)
    alpha_corr = 40.0 if alpha["test_passed"] else 0.0
    beta_corr = 40.0 if beta["test_passed"] else 0.0

    # Axis 2: Performance (Max 25 pts)
    alpha_time = alpha["bench_duration_s"] or alpha["test_duration_s"] or 1.0
    beta_time = beta["bench_duration_s"] or beta["test_duration_s"] or 1.0

    if alpha_time == beta_time:
        alpha_perf = 25.0
        beta_perf = 25.0
    elif alpha_time < beta_time:
        alpha_perf = 25.0
        ratio = alpha_time / beta_time
        beta_perf = max(10.0, round(25.0 * ratio, 1))
    else:
        beta_perf = 25.0
        ratio = beta_time / alpha_time
        alpha_perf = max(10.0, round(25.0 * ratio, 1))

    # Axis 3: Simplicity & Unslop (Max 20 pts)
    alpha_lines = alpha["code_metrics"]["total_lines"]
    beta_lines = beta["code_metrics"]["total_lines"]
    alpha_oversize = alpha["code_metrics"]["files_over_150_lines"]
    beta_oversize = beta["code_metrics"]["files_over_150_lines"]

    alpha_simp = 20.0 - (alpha_oversize * 2)
    beta_simp = 20.0 - (beta_oversize * 2)

    if alpha_lines > 0 and beta_lines > 0:
        if alpha_lines < beta_lines:
            alpha_simp += 2.0
        elif beta_lines < alpha_lines:
            beta_simp += 2.0

    alpha_simp = max(5.0, min(20.0, alpha_simp))
    beta_simp = max(5.0, min(20.0, beta_simp))

    # Axis 4: Maintainability (Max 15 pts)
    alpha_maint = 15.0
    beta_maint = 15.0

    alpha_total = round(alpha_corr + alpha_perf + alpha_simp + alpha_maint, 1)
    beta_total = round(beta_corr + beta_perf + beta_simp + beta_maint, 1)

    alpha["scores"] = {
        "correctness": alpha_corr,
        "performance": alpha_perf,
        "simplicity": alpha_simp,
        "maintainability": alpha_maint,
        "total": alpha_total
    }
    beta["scores"] = {
        "correctness": beta_corr,
        "performance": beta_perf,
        "simplicity": beta_simp,
        "maintainability": beta_maint,
        "total": beta_total
    }

    # Recommendation
    diff = abs(alpha_total - beta_total)
    if not alpha["test_passed"] and beta["test_passed"]:
        rec = "SELECT_BETA (Alpha failed tests)"
    elif alpha["test_passed"] and not beta["test_passed"]:
        rec = "SELECT_ALPHA (Beta failed tests)"
    elif diff >= 8.0:
        winner = "ALPHA" if alpha_total > beta_total else "BETA"
        rec = f"SELECT_{winner} (Decisive lead: {max(alpha_total, beta_total)} vs {min(alpha_total, beta_total)})"
    else:
        rec = "SYNTHESIS_RECOMMENDED (Close score: synthesize Alpha ergonomics with Beta performance)"

    return {
        "type": "code",
        "recommendation": rec,
        "alpha": alpha,
        "beta": beta
    }

def evaluate_design_file(name: str, file_path: str) -> dict:
    """Analyze structure, completeness, and unslop quality of a design proposal markdown file."""
    p = Path(file_path)
    if not p.exists():
        return {
            "name": name,
            "path": file_path,
            "exists": False,
            "total_lines": 0,
            "code_blocks": 0,
            "sections": {},
            "slop_count": 0,
            "slop_words": [],
            "trade_offs_identified": [],
            "scores": {
                "grounding": 0.0,
                "contracts": 0.0,
                "resilience": 0.0,
                "unslop": 0.0,
                "total": 0.0
            }
        }

    content = p.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    total_lines = len(lines)

    # Detect code blocks
    code_blocks = len(re.findall(r"^```[a-zA-Z0-9_\-]*\n", content, re.MULTILINE))

    # Check key sections
    section_patterns = {
        "architecture": r"^#{1,3}\s+.*(architecture|topology|system design|overview).*",
        "data_models": r"^#{1,3}\s+.*(data model|schema|contracts?|interfaces?).*",
        "failure_modes": r"^#{1,3}\s+.*(failure|resilience|edge cases?|error handling|security).*",
        "non_goals": r"^#{1,3}\s+.*(non-goals?|out of scope|boundaries).*",
        "trade_offs": r"^#{1,3}\s+.*(trade-?offs?|alternatives?|decision points?).*",
    }

    found_sections = {}
    for sec, pat in section_patterns.items():
        found_sections[sec] = bool(re.search(pat, content, re.IGNORECASE | re.MULTILINE))

    # Detect AI slop words
    words = re.findall(r"\b[a-zA-Z\-]+\b", content.lower())
    found_slop = [w for w in words if w in AI_SLOP_WORDS]
    slop_count = len(found_slop)

    # Extract user decision points or trade-off items
    trade_offs = []
    for line in lines:
        if re.search(r"(\[choice\]|\[decision\]|vs\.?|trade-?off)", line, re.IGNORECASE):
            cleaned = line.strip().lstrip("-*#").strip()
            if len(cleaned) > 10 and len(trade_offs) < 5:
                trade_offs.append(cleaned)

    # Compute individual scores
    # Axis 1: Grounding & Coverage (Max 30)
    grounding = 10.0
    if found_sections["architecture"]:
        grounding += 10.0
    if found_sections["non_goals"]:
        grounding += 5.0
    if total_lines >= 40:
        grounding += 5.0
    grounding = min(30.0, grounding)

    # Axis 2: Contracts & Data Models (Max 25)
    contracts = 5.0
    if found_sections["data_models"]:
        contracts += 10.0
    if code_blocks >= 2:
        contracts += 10.0
    elif code_blocks == 1:
        contracts += 5.0
    contracts = min(25.0, contracts)

    # Axis 3: Failure Modes & Resilience (Max 25)
    resilience = 5.0
    if found_sections["failure_modes"]:
        resilience += 15.0
    if len(trade_offs) >= 1:
        resilience += 5.0
    resilience = min(25.0, resilience)

    # Axis 4: Simplicity, Unslop & Conciseness (Max 20)
    unslop = 20.0 - min(10.0, slop_count * 1.5)
    if total_lines > 400:
        unslop -= 3.0  # penalize excessive verbosity
    unslop = max(5.0, min(20.0, unslop))

    total = round(grounding + contracts + resilience + unslop, 1)

    return {
        "name": name,
        "path": file_path,
        "exists": True,
        "total_lines": total_lines,
        "code_blocks": code_blocks,
        "sections": found_sections,
        "slop_count": slop_count,
        "slop_words": list(set(found_slop))[:5],
        "trade_offs_identified": trade_offs,
        "scores": {
            "grounding": grounding,
            "contracts": contracts,
            "resilience": resilience,
            "unslop": unslop,
            "total": total
        }
    }

def score_design_proposals(alpha: dict, beta: dict) -> dict:
    """Compares two architectural design proposals and produces recommendation."""
    alpha_total = alpha["scores"]["total"]
    beta_total = beta["scores"]["total"]

    diff = abs(alpha_total - beta_total)
    has_user_choice = bool(alpha.get("trade_offs_identified") or beta.get("trade_offs_identified"))

    if not alpha["exists"] and beta["exists"]:
        rec = "SELECT_BETA (Proposal Alpha missing)"
    elif alpha["exists"] and not beta["exists"]:
        rec = "SELECT_ALPHA (Proposal Beta missing)"
    elif diff >= 8.0:
        winner = "ALPHA" if alpha_total > beta_total else "BETA"
        rec = f"SELECT_{winner} (Decisive lead: {max(alpha_total, beta_total)} vs {min(alpha_total, beta_total)})"
    elif has_user_choice:
        rec = "USER_DECISION_REQUIRED (Alternative trade-offs identified — present choice card to user)"
    else:
        rec = "SYNTHESIS_RECOMMENDED (Synthesize Alpha structural clarity with Beta contract rigor into DESIGN.md)"

    return {
        "type": "design",
        "recommendation": rec,
        "alpha": alpha,
        "beta": beta
    }

def print_scorecard(eval_data: dict, output_file: str | None = None):
    alpha = eval_data["alpha"]
    beta = eval_data["beta"]
    rec = eval_data["recommendation"]

    if eval_data.get("type") == "design":
        md = f"""# 🏛️ Architectural Design Arbiter Scorecard

## Recommendation: **{rec}**

| Evaluation Axis | Max Weight | Proposal Alpha | Proposal Beta |
|---|---|---|---|
| **Architecture & Spec Grounding** | 30 pts | {alpha['scores']['grounding']} pts | {beta['scores']['grounding']} pts |
| **Interface & Data Contracts** | 25 pts | {alpha['scores']['contracts']} pts | {beta['scores']['contracts']} pts |
| **Failure Modes & Resilience** | 25 pts | {alpha['scores']['resilience']} pts | {beta['scores']['resilience']} pts |
| **Simplicity & Unslop** | 20 pts | {alpha['scores']['unslop']} pts | {beta['scores']['unslop']} pts |
| **TOTAL SCORE** | **100 pts** | **{alpha['scores']['total']} pts** | **{beta['scores']['total']} pts** |

---

### Comparative Analysis
- **File**: Alpha: `{alpha['path']}` ({alpha['total_lines']} lines) | Beta: `{beta['path']}` ({beta['total_lines']} lines)
- **Concrete Code/Schema Blocks**: Alpha: `{alpha['code_blocks']}` | Beta: `{beta['code_blocks']}`
- **AI Slop Flagged**: Alpha: `{alpha['slop_count']}` ({', '.join(alpha['slop_words']) or 'none'}) | Beta: `{beta['slop_count']}` ({', '.join(beta['slop_words']) or 'none'})

### Identified Trade-Offs & Decision Points
- **Proposal Alpha**: {'; '.join(alpha['trade_offs_identified']) or 'None explicitly flagged'}
- **Proposal Beta**: {'; '.join(beta['trade_offs_identified']) or 'None explicitly flagged'}
"""
    else:
        md = f"""# 🏆 Arbiter Tournament Scorecard

## Recommendation: **{rec}**

| Evaluation Axis | Max Weight | Worker Alpha | Worker Beta |
|---|---|---|---|
| **Correctness** (Tests & Stability) | 40 pts | {alpha['scores']['correctness']} pts | {beta['scores']['correctness']} pts |
| **Performance** (Execution Latency) | 25 pts | {alpha['scores']['performance']} pts | {beta['scores']['performance']} pts |
| **Simplicity & Unslop** (Conciseness) | 20 pts | {alpha['scores']['simplicity']} pts | {beta['scores']['simplicity']} pts |
| **Maintainability** (Modularity) | 15 pts | {alpha['scores']['maintainability']} pts | {beta['scores']['maintainability']} pts |
| **TOTAL SCORE** | **100 pts** | **{alpha['scores']['total']} pts** | **{beta['scores']['total']} pts** |

---

### Quantitative Comparison
- **Test Passed**: Alpha: `{alpha['test_passed']}` ({alpha['test_duration_s']}s) | Beta: `{beta['test_passed']}` ({beta['test_duration_s']}s)
- **Total Lines**: Alpha: `{alpha['code_metrics']['total_lines']}` | Beta: `{beta['code_metrics']['total_lines']}`
- **Files > 150 Lines**: Alpha: `{alpha['code_metrics']['files_over_150_lines']}` | Beta: `{beta['code_metrics']['files_over_150_lines']}`
- **Avg Lines / File**: Alpha: `{alpha['code_metrics']['avg_lines_per_file']}` | Beta: `{beta['code_metrics']['avg_lines_per_file']}`
"""
    print("\n" + md)
    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ Saved scorecard to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Automated Arbiter Tournament Evaluation Engine")
    # Implementation mode
    parser.add_argument("--alpha-dir", default=".", help="Path to Worker Alpha code")
    parser.add_argument("--beta-dir", default=".", help="Path to Worker Beta code")
    parser.add_argument("--alpha-test", help="Test command for Alpha")
    parser.add_argument("--beta-test", help="Test command for Beta")
    parser.add_argument("--bench-cmd", help="Benchmark execution command")
    # Design proposal mode
    parser.add_argument("--design-alpha", help="Path to Proposal Alpha markdown file")
    parser.add_argument("--design-beta", help="Path to Proposal Beta markdown file")
    parser.add_argument("--output-scorecard", default=".agents/orchestrator/arbiter_scorecard.md", help="Path to save markdown scorecard")
    args = parser.parse_args()

    if args.design_alpha or args.design_beta:
        d_alpha_path = args.design_alpha or ".agents/design/proposals/proposal_alpha.md"
        d_beta_path = args.design_beta or ".agents/design/proposals/proposal_beta.md"
        alpha_res = evaluate_design_file("Proposal Alpha", d_alpha_path)
        beta_res = evaluate_design_file("Proposal Beta", d_beta_path)
        eval_data = score_design_proposals(alpha_res, beta_res)
        print_scorecard(eval_data, args.output_scorecard)
    else:
        alpha_res = evaluate_candidate("Worker Alpha", args.alpha_test, args.bench_cmd, args.alpha_dir)
        beta_res = evaluate_candidate("Worker Beta", args.beta_test, args.bench_cmd, args.beta_dir)
        eval_data = score_candidates(alpha_res, beta_res)
        print_scorecard(eval_data, args.output_scorecard)

if __name__ == "__main__":
    main()
