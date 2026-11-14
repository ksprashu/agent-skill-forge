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

"""Validate Stage 2 issue triage plans and file-disjoint swarm execution tracks.

  plan_tracks.py --plan plan.json [--from-evidence evidence.json] [--check-disjoint]
                 [--max-shard-size 8]

Verifier (ENGINEERING_STANDARD V1-V6): enforces structural integrity of Stage 2
fix plans, file-disjoint ownership across concurrent tracks (exact matches and
directory-prefix overlap), partial-issue tracking (`Refs` vs `Fixes`), and
optional parity against Stage 1 `issue_state.py` evidence.

Surface (V3): plan JSON schema, triage classification enums, file-path safety,
inter-track file/directory disjointness, partial-issue marking, and open-issue
coverage against `--from-evidence`.
Not checked (V5): whether planned fixes are semantically correct, or whether
files exist on disk on the target repo branch.

Exit codes:
  0   plan valid and all concurrent tracks are file-disjoint
  1   validation failure (overlapping files, missing track mapping, unsafe path, etc.)
  2   input file unreadable or invalid JSON
  64  usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_common as IC  # noqa: E402


def _paths_collide(a: str, b: str) -> bool:
    ac, bc = a.casefold(), b.casefold()
    return ac == bc or ac.startswith(bc + "/") or bc.startswith(ac + "/")


def compute_triage_shards(issue_numbers: list[int], max_shard_size: int) -> list[list[int]]:
    """Partition open issue numbers into deterministic shards of <= max_shard_size."""
    return [
        issue_numbers[i:i + max_shard_size]
        for i in range(0, len(issue_numbers), max_shard_size)
    ]


def validate_plan(
    plan: Any,
    evidence: dict[str, Any] | None = None,
    check_disjoint: bool = False,
    max_shard_size: int = 8,
) -> dict[str, Any]:
    """Validate Stage 2 plan JSON and return structured results."""
    errors: list[str] = []
    collisions: list[dict[str, Any]] = []
    issue_link_modes: dict[str, str] = {}
    triage_shards: list[list[int]] = []

    if not isinstance(plan, dict):
        return {
            "valid": False,
            "mode": None,
            "tracks_count": 0,
            "issues_count": 0,
            "collisions": [],
            "errors": ["$: plan must be a JSON object"],
            "triage_shards": [],
            "issue_link_modes": {},
            "not_checked": ["semantic correctness of proposed fixes", "on-disk file existence"],
        }

    if plan.get("schema_version") != IC.SCHEMA_VERSION:
        errors.append(f"$.schema_version: expected {IC.SCHEMA_VERSION!r}")

    mode = plan.get("mode")
    if mode not in ("standalone", "swarm"):
        errors.append("$.mode: must be 'standalone' or 'swarm'")

    issues_raw = plan.get("issues")
    tracks_raw = plan.get("tracks")
    if not isinstance(issues_raw, list) or not issues_raw:
        errors.append("$.issues: must be a non-empty list")
        issues_raw = []
    if not isinstance(tracks_raw, list):
        errors.append("$.tracks: must be a list")
        tracks_raw = []

    issue_map: dict[int, dict[str, Any]] = {}
    for idx, entry in enumerate(issues_raw):
        where = f"$.issues[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: must be an object")
            continue
        num = entry.get("issue")
        if not isinstance(num, int) or isinstance(num, bool) or num < 1:
            errors.append(f"{where}.issue: must be a positive integer")
            continue
        if num in issue_map:
            errors.append(f"{where}: duplicate issue #{num}")
            continue

        cls = entry.get("classification")
        if cls not in IC.TRIAGE_CLASSIFICATIONS:
            errors.append(f"{where}.classification: invalid {cls!r}")

        ev = entry.get("evidence")
        if not isinstance(ev, list) or not ev or not all(isinstance(x, str) and x.strip() for x in ev):
            errors.append(f"{where}.evidence: must be a non-empty list of evidence strings")

        tid = entry.get("track_id")
        if tid is not None and (not isinstance(tid, str) or not tid.strip()):
            errors.append(f"{where}.track_id: must be null or a non-empty string")

        if cls in IC.FIXABLE_CLASSIFICATIONS and not tid:
            errors.append(f"{where}: fixable issue #{num} ({cls}) must name a track_id")
        if cls not in IC.FIXABLE_CLASSIFICATIONS and tid:
            errors.append(f"{where}: non-fixable issue #{num} ({cls}) must have track_id=null")

        issue_map[num] = entry

    track_map: dict[str, dict[str, Any]] = {}
    track_paths: dict[str, list[str]] = {}
    assigned_issues: dict[int, str] = {}
    all_partial_issues: set[int] = set()

    for idx, tr in enumerate(tracks_raw):
        where = f"$.tracks[{idx}]"
        if not isinstance(tr, dict):
            errors.append(f"{where}: must be an object")
            continue

        tid = tr.get("track_id")
        if not isinstance(tid, str) or not tid.strip():
            errors.append(f"{where}.track_id: must be a non-empty string")
            continue
        if tid in track_map:
            errors.append(f"{where}: duplicate track_id {tid!r}")
            continue
        track_map[tid] = tr

        summary = tr.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            errors.append(f"{where}.summary: must be a non-empty string")

        t_issues = tr.get("issues")
        if not isinstance(t_issues, list) or not t_issues:
            errors.append(f"{where}.issues: must be a non-empty list of issue numbers")
            t_issues = []
        for num in t_issues:
            if not isinstance(num, int) or isinstance(num, bool) or num < 1:
                errors.append(f"{where}.issues: invalid issue number {num!r}")
                continue
            if num in assigned_issues:
                errors.append(f"{where}.issues: issue #{num} already assigned to track {assigned_issues[num]!r}")
            else:
                assigned_issues[num] = tid
            if num not in issue_map:
                errors.append(f"{where}.issues: issue #{num} missing from $.issues")
            else:
                cls = issue_map[num].get("classification")
                if cls not in IC.FIXABLE_CLASSIFICATIONS:
                    errors.append(f"{where}.issues: non-fixable issue #{num} ({cls}) cannot be in a track")
                elif issue_map[num].get("track_id") != tid:
                    errors.append(f"{where}.issues: issue #{num} declares track_id={issue_map[num].get('track_id')!r}, not {tid!r}")

        p_issues = tr.get("partial_issues", [])
        if not isinstance(p_issues, list):
            errors.append(f"{where}.partial_issues: must be a list")
            p_issues = []
        for pnum in p_issues:
            if pnum not in t_issues:
                errors.append(f"{where}.partial_issues: #{pnum} is not listed in track issues")
            else:
                all_partial_issues.add(pnum)

        owned = tr.get("owned_files")
        if not isinstance(owned, list) or not owned:
            errors.append(f"{where}.owned_files: must be a non-empty list of repo-relative file paths")
            owned = []
        tests = tr.get("test_files", [])
        if not isinstance(tests, list):
            errors.append(f"{where}.test_files: must be a list of repo-relative file paths")
            tests = []

        acc = tr.get("acceptance_tests")
        if not isinstance(acc, list) or not acc or not all(isinstance(x, str) and x.strip() for x in acc):
            errors.append(f"{where}.acceptance_tests: must be a non-empty list of test criteria")

        norm_paths: list[str] = []
        for field_name, raw_list in (("owned_files", owned), ("test_files", tests)):
            for raw_path in raw_list:
                ok, result = IC.is_safe_repo_rel_path(raw_path)
                if not ok:
                    errors.append(f"{where}.{field_name}: {result}")
                else:
                    norm_paths.append(result)
        track_paths[tid] = sorted(set(norm_paths))

    for num, entry in sorted(issue_map.items()):
        cls = entry.get("classification")
        tid = entry.get("track_id")
        if cls in IC.FIXABLE_CLASSIFICATIONS:
            if num not in assigned_issues:
                errors.append(f"$.issues: fixable issue #{num} ({cls}) is not assigned to any track")
            if cls == "partially_addressed" and num not in all_partial_issues:
                errors.append(
                    f"$.issues: issue #{num} is classified 'partially_addressed' and must appear in "
                    "its track's partial_issues so Stage 5 uses Refs rather than Fixes"
                )
            issue_link_modes[str(num)] = "Refs" if num in all_partial_issues else "Fixes"
        elif tid and tid in track_map:
            errors.append(f"$.issues: non-fixable issue #{num} must not reference track {tid!r}")

    enforce_disjoint = check_disjoint or mode == "swarm"
    if enforce_disjoint and len(track_paths) > 1:
        tids = sorted(track_paths)
        for i, tid_a in enumerate(tids):
            for tid_b in tids[i + 1:]:
                overlaps: list[dict[str, str]] = []
                for pa in track_paths[tid_a]:
                    for pb in track_paths[tid_b]:
                        if _paths_collide(pa, pb):
                            overlaps.append({"track_a_path": pa, "track_b_path": pb})
                if overlaps:
                    collisions.append({
                        "track_a": tid_a,
                        "track_b": tid_b,
                        "overlaps": overlaps,
                    })
                    errors.append(
                        f"file ownership collision between {tid_a!r} and {tid_b!r}: "
                        + ", ".join(f"{o['track_a_path']} <-> {o['track_b_path']}" for o in overlaps)
                    )

    if evidence is not None:
        if not isinstance(evidence, dict) or not isinstance(evidence.get("issues"), list):
            errors.append("$.evidence: --from-evidence file must contain an 'issues' list from issue_state.py")
        else:
            open_nums = [
                item["number"]
                for item in evidence["issues"]
                if isinstance(item, dict) and isinstance(item.get("number"), int)
                and item.get("state", "OPEN") == "OPEN"
            ]
            for num in open_nums:
                if num not in issue_map:
                    errors.append(f"$.evidence: open issue #{num} from Stage 1 evidence is missing from plan.issues")
            triage_shards = compute_triage_shards(open_nums, max_shard_size)

    return {
        "valid": not errors and not collisions,
        "mode": mode,
        "tracks_count": len(track_map),
        "issues_count": len(issue_map),
        "collisions": collisions,
        "errors": errors,
        "triage_shards": triage_shards,
        "issue_link_modes": issue_link_modes,
        "not_checked": [
            "semantic correctness of proposed fixes",
            "whether owned_files exist on disk on the target branch",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plan", required=True, help="Stage 2 plan JSON path ('-' for stdin)")
    parser.add_argument("--from-evidence", help="optional Stage 1 issue_state.py JSON to verify coverage")
    parser.add_argument("--check-disjoint", action="store_true", help="enforce file-disjoint ownership across tracks")
    parser.add_argument("--max-shard-size", type=int, default=8, help="max issues per triage shard (1..25)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    if args.max_shard_size < 1 or args.max_shard_size > 25:
        print("plan_tracks: --max-shard-size must be between 1 and 25", file=sys.stderr)
        return 64

    try:
        raw_plan = sys.stdin.read() if args.plan == "-" else Path(args.plan).read_text(encoding="utf-8")
        plan = json.loads(raw_plan)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plan_tracks: cannot read plan {args.plan}: {exc}", file=sys.stderr)
        return 2

    evidence = None
    if args.from_evidence:
        try:
            evidence = json.loads(Path(args.from_evidence).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"plan_tracks: cannot read evidence {args.from_evidence}: {exc}", file=sys.stderr)
            return 2

    result = validate_plan(
        plan,
        evidence=evidence,
        check_disjoint=args.check_disjoint,
        max_shard_size=args.max_shard_size,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
