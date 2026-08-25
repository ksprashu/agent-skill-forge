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
mine_brain_transcripts.py - Cross-Session Brain Trajectory & Memory Mining Engine

Scans Antigravity CLI and UI brain files (~/.gemini/antigravity-cli/brain/ and ~/.gemini/antigravity/brain/)
to search, extract, and harness past context, user feedback, error recoveries, and task trajectories.
"""

import os
import sys
import json
import argparse
from pathlib import Path

def find_brain_directories():
    """Locates all Antigravity CLI and UI brain directories."""
    home = Path.home()
    candidates = [
        home / ".gemini" / "antigravity-cli" / "brain",
        home / ".gemini" / "antigravity" / "brain",
        home / ".gemini" / "antigravity-ide" / "brain",
        home / ".config" / "antigravity" / "brain"
    ]
    valid = [c for c in candidates if c.exists()]
    return valid

def search_transcripts(query, max_results=10):
    """Searches transcript.jsonl across all brain directories for matching text."""
    brain_dirs = find_brain_directories()
    results = []

    print(f"[Brain Miner] Searching across {len(brain_dirs)} brain locations for: '{query}'")

    for bdir in brain_dirs:
        for conv_dir in bdir.iterdir():
            if not conv_dir.is_dir():
                continue

            transcript_path = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
            if not transcript_path.exists():
                continue

            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            try:
                                data = json.loads(line)
                                results.append({
                                    "conversation_id": conv_dir.name,
                                    "brain_source": bdir.parent.name,
                                    "line_number": line_no,
                                    "step_type": data.get("type"),
                                    "source": data.get("source"),
                                    "content_snippet": str(data.get("content", ""))[:200]
                                })
                                if len(results) >= max_results:
                                    return results
                            except json.JSONDecodeError:
                                pass
            except Exception:
                continue

    return results

def main():
    parser = argparse.ArgumentParser(description="Mine Antigravity Brain Files")
    parser.add_argument("query", help="Search query or keyword (e.g. 'error', 'user_guide', 'theme')")
    parser.add_argument("--max", "-m", type=int, default=10, help="Maximum results to return")

    args = parser.parse_args()
    results = search_transcripts(args.query, max_results=args.max)

    print(f"\n=======================================================")
    print(f"🧠 ANTIGRAVITY BRAIN TRANSCRIPT MINER RESULTS")
    print(f"Query: '{args.query}' | Found: {len(results)} matches")
    print(f"=======================================================\n")

    for r in results:
        print(f"• [{r['brain_source']}] ConvID: {r['conversation_id']} (Line {r['line_number']})")
        print(f"  Type: {r['step_type']} | Source: {r['source']}")
        print(f"  Snippet: {r['content_snippet']}\n")

if __name__ == "__main__":
    main()
