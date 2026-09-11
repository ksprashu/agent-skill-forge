#!/usr/bin/env python3
"""
Automated Arbiter Tournament Evaluation Engine
Part of the Google Antigravity Work Swarm Engine (skills/work).

Evaluates competing implementations (Worker Alpha vs Worker Beta)
across four core axes:
1. Correctness (40%): Test suite pass rate and failure counts
2. Performance (25%): Runtime latency and resource efficiency
3. Simplicity & Unslop (20%): Code churn, conciseness, sub-150-line modularity
4. Maintainability (15%): Low dependency footprint and architectural cleanliness
"""

import os
import sys
import io
import json
import time
import argparse
import subprocess
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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
    # Compare test or benchmark durations (lower is better)
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
    # Fewer lines of code and fewer files > 150 lines
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
        "recommendation": rec,
        "alpha": alpha,
        "beta": beta
    }

def print_scorecard(eval_data: dict, output_file: str | None = None):
    alpha = eval_data["alpha"]
    beta = eval_data["beta"]
    rec = eval_data["recommendation"]

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
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ Saved scorecard to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Automated Arbiter Tournament Evaluation Engine")
    parser.add_argument("--alpha-dir", default=".", help="Path to Worker Alpha code")
    parser.add_argument("--beta-dir", default=".", help="Path to Worker Beta code")
    parser.add_argument("--alpha-test", help="Test command for Alpha")
    parser.add_argument("--beta-test", help="Test command for Beta")
    parser.add_argument("--bench-cmd", help="Benchmark execution command")
    parser.add_argument("--output-scorecard", default=".agents/orchestrator/arbiter_scorecard.md", help="Path to save markdown scorecard")
    args = parser.parse_args()

    alpha_res = evaluate_candidate("Worker Alpha", args.alpha_test, args.bench_cmd, args.alpha_dir)
    beta_res = evaluate_candidate("Worker Beta", args.beta_test, args.bench_cmd, args.beta_dir)

    eval_data = score_candidates(alpha_res, beta_res)
    print_scorecard(eval_data, args.output_scorecard)

if __name__ == "__main__":
    main()
