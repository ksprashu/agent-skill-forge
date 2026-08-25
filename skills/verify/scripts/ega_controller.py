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

"""
ega_controller.py - Expectation-Grounded Alignment (EGA) Controller Orchestrator

Serves as the top-level hard-enforced controller layer that:
1. Ingests full user prompts + multimodal image attachments.
2. Runs Phase 1 Expectation Synthesis (compiles expectations.json, verify_static.py, rubric.json).
3. Dispatches worker execution (if worker command provided).
4. Enforces Phase 2 Dual-Verification Gate (Static Verifier + Dynamic LLM Judge) via ega_loop_runner.py.
5. Manages delta feedback retries automatically until zero defects or circuit breaker.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="EGA Controller Orchestrator")
    parser.add_argument("--prompt", help="Verbatim user prompt text")
    parser.add_argument("--prompt-file", help="Path to file containing raw user prompt")
    parser.add_argument("--images", nargs="*", default=[], help="Image file paths attached to prompt")
    parser.add_argument("--domain", "-d", default="web", choices=["web", "html", "ui", "python", "node", "javascript", "markdown", "general"], help="Domain type")
    parser.add_argument("--persona", "-p", default="Builder-Coder", help="Persona role")
    parser.add_argument("--worker-cmd", help="Optional shell command line to run worker implementation pass")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts")

    args = parser.parse_args()

    full_prompt = args.prompt
    if not full_prompt and args.prompt_file and Path(args.prompt_file).exists():
        full_prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    if not full_prompt:
        full_prompt = "Execute Expectation-Grounded Implementation Pass"

    print("============================================================")
    print("🚀 EGA CONTROLLER ORCHESTRATOR INITIALIZED")
    print("============================================================")

    # 1. Compile Harness (Phase 1)
    scripts_dir = Path(__file__).parent
    compiler = scripts_dir / "compile_ega_harness.py"

    compile_cmd = [
        sys.executable, str(compiler),
        full_prompt[:100],
        args.persona,
        "--domain", args.domain,
        "--prompt", full_prompt
    ]
    if args.images:
        compile_cmd.extend(["--images"] + args.images)

    res = subprocess.run(compile_cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(f"❌ Harness compilation failed: {res.stderr}")
        sys.exit(1)

    # Extract Short ID from compiler output
    short_id = None
    for line in res.stdout.splitlines():
        if "Compiled EGA Harness" in line:
            parts = line.split()
            for p in parts:
                if p.startswith("EGA-"):
                    short_id = p
                    break

    if not short_id:
        print("❌ Could not determine compiled harness short ID")
        sys.exit(1)

    harness_dir = Path.cwd() / ".gemini" / "harness" / short_id
    print(f"📦 Active Harness Workspace: {harness_dir}")

    # 2. Loop Execution (Phase 2 Dual Gate)
    loop_runner = scripts_dir / "ega_loop_runner.py"

    attempt = 0
    gate_passed = False

    while attempt < args.max_retries:
        attempt += 1
        print(f"\n🔄 --- CONTROL LOOP ATTEMPT {attempt}/{args.max_retries} ---")

        # Run Worker Command if provided
        if args.worker_cmd:
            print(f"⚡ Executing worker command: {args.worker_cmd}")
            w_res = subprocess.run(args.worker_cmd, shell=True, capture_output=True, text=True)
            print(f"Worker Output:\n{w_res.stdout}")
            if w_res.stderr:
                print(f"Worker Warnings/Errors:\n{w_res.stderr}")

        # Run Dual Verification Gate
        gate_res = subprocess.run([sys.executable, str(loop_runner), short_id], capture_output=True, text=True)
        print(gate_res.stdout)

        if gate_res.returncode == 0:
            gate_passed = True
            print("\n✅ CONTROLLER GATE PASSED WITH ZERO DEFECTS!")
            break
        else:
            delta_file = harness_dir / "node_01_delta_report.md"
            if delta_file.exists():
                print(f"⚠️ Gate rejected. Delta report generated at {delta_file}")

    if not gate_passed:
        print(f"\n❌ CIRCUIT BREAKER TRIGGERED: Failed after {args.max_retries} attempts.")
        sys.exit(1)

    print("============================================================")
    print("🎉 EGA CONTROLLER COMPLETED SUCCESSFULLY")
    print("============================================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
