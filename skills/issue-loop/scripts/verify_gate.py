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

"""Stage 4 deterministic verification, 8-axis review, security scan, and cross-family gate.

  verify_gate.py --bundle gate_bundle.json [--repo-root .] [--swarm]
                 [--allow-intra-family-fallback]

Verifier (ENGINEERING_STANDARD V1-V6): enforces branch protection, SHA-bound fresh
test evidence (with TDD red-green flag), owned-file scope confinement, `review`
and `security-review` findings contracts (0 open P0-P3), honest scanner coverage,
and cross-family review separation in swarm mode.

Surface (V3): bundle schema, protected-branch check, HEAD SHA binding across
tests/review/security (and live git HEAD when `--repo-root` is given), scope
subset check, findings contract validation, scanner status/not_inspected parity,
secret-leak check, and author vs verifier model-family separation.
Not checked (V5): semantic accuracy of tests or reviewer prose, or live GitHub
checks/branch protection rules.

Exit codes:
  0   VERDICT: PASS
  1   VERDICT: FAIL (one or more gate checks failed)
  2   bundle or findings file unreadable, malformed JSON, or git error
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


def _sha_matches(expected: Any, actual: Any) -> bool:
    if not isinstance(expected, str) or not isinstance(actual, str):
        return False
    a, b = expected.strip().lower(), actual.strip().lower()
    if not IC.SHA_PATTERN.match(a) or not IC.SHA_PATTERN.match(b):
        return False
    return a.startswith(b) or b.startswith(a)


def _resolve_findings_doc(section: dict[str, Any], label: str, base_dir: Path, failures: list[str]) -> dict[str, Any] | None:
    if "findings_doc" in section:
        doc = section.get("findings_doc")
        if not isinstance(doc, dict):
            failures.append(f"{label}.findings_doc must be a JSON object")
            return None
        return doc
    fpath = section.get("findings_file")
    if not isinstance(fpath, str) or not fpath.strip():
        failures.append(f"{label} must provide 'findings_doc' or 'findings_file'")
        return None
    ok, norm = IC.is_safe_repo_rel_path(fpath)
    if not ok:
        failures.append(f"{label}.findings_file: {norm}")
        return None
    target = (base_dir / norm).resolve()
    try:
        target.relative_to(base_dir.resolve())
    except ValueError:
        failures.append(f"{label}.findings_file escapes workspace root")
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{label}.findings_file unreadable: {exc}")
        return None


def _check_findings_section(
    section: Any,
    label: str,
    bundle_sha: str,
    expected_producers: tuple[str, ...],
    base_dir: Path,
    failures: list[str],
) -> dict[str, Any] | None:
    if not isinstance(section, dict):
        failures.append(f"{label} section must be a JSON object")
        return None
    if not _sha_matches(bundle_sha, section.get("head_sha")):
        failures.append(f"{label}.head_sha {section.get('head_sha')!r} does not match bundle head_sha {bundle_sha!r}")
    doc = _resolve_findings_doc(section, label, base_dir, failures)
    if doc is None:
        return None
    doc_errors = IC.validate_findings_doc(doc)
    for err in doc_errors:
        failures.append(f"{label} findings invalid: {err}")
    if doc.get("producer") not in expected_producers:
        failures.append(f"{label} findings producer {doc.get('producer')!r} not in {list(expected_producers)}")
    open_blocking = [
        f for f in doc.get("findings", [])
        if isinstance(f, dict)
        and f.get("severity") in IC.FINDINGS_BLOCKING_SEVERITIES
        and f.get("status") not in IC.FINDINGS_CLOSED_STATUSES
    ]
    if open_blocking:
        ids = ", ".join(str(f.get("id", "?")) for f in open_blocking)
        failures.append(f"{label} has {len(open_blocking)} open blocking P0-P3 finding(s): {ids}")
    return doc


def evaluate_bundle(
    bundle: Any,
    base_dir: Path,
    repo_root: Path | None = None,
    force_swarm: bool = False,
    allow_intra_family_fallback: bool = False,
) -> dict[str, Any]:
    """Run every deterministic Stage 4 gate on the bundle and return a structured verdict."""
    failures: list[str] = []
    checked: list[str] = []
    cross_family: dict[str, Any] = {}

    if not isinstance(bundle, dict):
        return {
            "verdict": "FAIL",
            "failures": ["$: gate bundle must be a JSON object"],
            "checked": [],
            "not_checked": ["semantic accuracy of tests or reviewer prose", "live GitHub check status"],
            "cross_family": {},
        }

    if bundle.get("schema_version") != IC.SCHEMA_VERSION:
        failures.append(f"$.schema_version: expected {IC.SCHEMA_VERSION!r}")

    mode = bundle.get("mode")
    if mode not in ("standalone", "swarm"):
        failures.append("$.mode: must be 'standalone' or 'swarm'")

    branch = bundle.get("branch")
    if not isinstance(branch, str) or not IC.SAFE_BRANCH_PATTERN.match(branch) or ".." in branch:
        failures.append(f"$.branch: invalid feature branch name {branch!r}")
    elif branch in IC.PROTECTED_BRANCHES:
        failures.append(f"$.branch: refusing protected branch {branch!r}")
    checked.append("branch_protection")

    head_sha = bundle.get("head_sha")
    if not isinstance(head_sha, str) or not IC.SHA_PATTERN.match(head_sha):
        failures.append(f"$.head_sha: expected 7..40 char git commit SHA, got {head_sha!r}")
        head_sha = ""
    checked.append("head_sha_format")

    secret_hits = IC.find_secret_leaks(bundle)
    if secret_hits:
        failures.append(f"secret pattern detected in bundle: {secret_hits[0]}")
    checked.append("bundle_secret_scan")

    # 1. Tests & red-green verification
    tests = bundle.get("tests")
    if not isinstance(tests, dict):
        failures.append("$.tests: must be a JSON object")
    else:
        if head_sha and not _sha_matches(head_sha, tests.get("head_sha")):
            failures.append(f"tests.head_sha {tests.get('head_sha')!r} does not match bundle head_sha {head_sha!r}")
        if not isinstance(tests.get("command"), str) or not tests["command"].strip():
            failures.append("tests.command: must be a non-empty string")
        if tests.get("exit_code") != 0:
            failures.append(f"tests.exit_code: expected 0, got {tests.get('exit_code')!r}")
        passed = tests.get("passed")
        if not isinstance(passed, int) or isinstance(passed, bool) or passed < 1:
            failures.append("tests.passed: must be integer >= 1")
        failed = tests.get("failed")
        if not isinstance(failed, int) or isinstance(failed, bool) or failed != 0:
            failures.append(f"tests.failed: must be 0, got {failed!r}")
        skipped = tests.get("skipped", 0)
        if not isinstance(skipped, int) or isinstance(skipped, bool) or skipped < 0:
            failures.append("tests.skipped: must be integer >= 0")
        elif skipped > 0:
            just = tests.get("skip_justification", "")
            if not isinstance(just, str) or len(just.strip()) < 20:
                failures.append("tests.skipped > 0 requires skip_justification (>= 20 chars)")
        if tests.get("red_green_verified") is not True:
            failures.append("tests.red_green_verified must be true (TDD prove-it cycle required)")
    checked.append("tests_and_tdd")

    # 2. Scope / owned-file confinement
    scope = bundle.get("scope")
    changed_paths: list[str] = []
    if not isinstance(scope, dict):
        failures.append("$.scope: must be a JSON object")
    else:
        allowed_raw = scope.get("allowed_files")
        changed_raw = scope.get("changed_files")
        allowed_set: set[str] = set()
        if not isinstance(allowed_raw, list) or not allowed_raw:
            failures.append("scope.allowed_files: must be a non-empty list")
        else:
            for item in allowed_raw:
                ok, norm = IC.is_safe_repo_rel_path(item)
                if not ok:
                    failures.append(f"scope.allowed_files: {norm}")
                else:
                    allowed_set.add(norm)
        if not isinstance(changed_raw, list) or not changed_raw:
            failures.append("scope.changed_files: must be a non-empty list")
        else:
            for item in changed_raw:
                ok, norm = IC.is_safe_repo_rel_path(item)
                if not ok:
                    failures.append(f"scope.changed_files: {norm}")
                else:
                    changed_paths.append(norm)
                    if allowed_set and norm not in allowed_set:
                        failures.append(f"scope violation: changed file {norm!r} is outside allowed_files")
    checked.append("scope_confinement")

    # 3. 8-axis code review contract
    _check_findings_section(
        bundle.get("review"),
        "review",
        head_sha,
        ("review",),
        repo_root or base_dir,
        failures,
    )
    checked.append("review_findings_gate")

    # 4. Security review & static scanner honesty
    sec = bundle.get("security")
    sec_doc = _check_findings_section(
        sec,
        "security",
        head_sha,
        ("security-review",),
        repo_root or base_dir,
        failures,
    )
    if isinstance(sec, dict):
        if sec.get("secrets_found") != 0:
            failures.append(f"security.secrets_found must be 0, got {sec.get('secrets_found')!r}")
        scanners = sec.get("scanners")
        if not isinstance(scanners, dict) or not scanners:
            failures.append("security.scanners must be a non-empty map of tool -> status")
        else:
            not_inspected_blob = json.dumps((sec_doc or {}).get("not_inspected", [])).lower()
            for tool, status in sorted(scanners.items()):
                if status not in IC.SCANNER_ALLOWED_STATUSES:
                    failures.append(f"security.scanners[{tool!r}]: invalid status {status!r}")
                elif status in IC.SCANNER_FAILING_STATUSES:
                    failures.append(f"security.scanners[{tool!r}] reported {status!r}")
                elif status == "not_installed" and str(tool).lower() not in not_inspected_blob:
                    failures.append(
                        f"security.scanners[{tool!r}] is 'not_installed' but missing from "
                        "security findings not_inspected (missing is never clean)"
                    )
            present_lower = {str(k).lower() for k in scanners}
            for expected_tool in IC.EXPECTED_SECURITY_SCANNERS:
                if expected_tool not in present_lower and expected_tool not in not_inspected_blob:
                    failures.append(
                        f"security.scanners omitted {expected_tool!r} and it is missing from "
                        "security findings not_inspected (missing is never clean)"
                    )
    checked.append("security_scan_gate")

    # 5. Swarm cross-family review invariant
    is_swarm = force_swarm or mode == "swarm"
    if is_swarm:
        author_model = bundle.get("author_model", "")
        review_model = bundle.get("review_model") or bundle.get("verifier_model", "")
        security_model = bundle.get("security_model") or review_model
        author_fam = IC.model_family(author_model)
        review_fam = IC.model_family(review_model)
        security_fam = IC.model_family(security_model)
        cross_family = {
            "author_model": author_model,
            "author_family": author_fam,
            "review_model": review_model,
            "review_family": review_fam,
            "security_model": security_model,
            "security_family": security_fam,
        }
        if author_fam == "unknown":
            failures.append(f"swarm cross-family gate: unknown author_model family for {author_model!r}")
        if review_fam == "unknown":
            failures.append(f"swarm cross-family gate: unknown review_model family for {review_model!r}")
        if security_fam == "unknown":
            failures.append(f"swarm cross-family gate: unknown security_model family for {security_model!r}")

        same_family = (
            (author_fam != "unknown" and author_fam == review_fam)
            or (author_fam != "unknown" and author_fam == security_fam)
        )
        if same_family:
            reason = bundle.get("intra_family_fallback_reason", "")
            if allow_intra_family_fallback and isinstance(reason, str) and len(reason.strip()) >= 20:
                cross_family["intra_family_fallback"] = True
            else:
                failures.append(
                    f"swarm cross-family gate: verifier family ({review_fam}/{security_fam}) must differ "
                    f"from author_family ({author_fam})"
                )
        checked.append("swarm_cross_family")

    # 6. Optional live git repo verification
    if repo_root is not None:
        head_proc = IC.run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root)
        if head_proc.returncode != 0:
            raise IC.GhError(f"git rev-parse HEAD failed in {repo_root}: {head_proc.stderr.strip()}")
        live_head = head_proc.stdout.strip()
        if head_sha and not _sha_matches(live_head, head_sha):
            failures.append(f"stale evidence: bundle head_sha {head_sha!r} does not match live git HEAD {live_head!r}")

        branch_proc = IC.run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
        if branch_proc.returncode == 0:
            live_branch = branch_proc.stdout.strip()
            if live_branch in IC.PROTECTED_BRANCHES:
                failures.append(f"live git branch is protected branch {live_branch!r}")

        root_resolved = repo_root.resolve()
        for rel in changed_paths:
            try:
                (root_resolved / rel).resolve().relative_to(root_resolved)
            except ValueError:
                failures.append(f"changed file {rel!r} escapes --repo-root")
        checked.append("live_git_head")

    return {
        "verdict": "PASS" if not failures else "FAIL",
        "head_sha": head_sha,
        "branch": branch if isinstance(branch, str) else "",
        "failures": failures,
        "checked": checked,
        "not_checked": [
            "semantic accuracy of tests or reviewer prose",
            "live GitHub branch protection or PR status checks",
        ],
        "cross_family": cross_family,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bundle", required=True, help="Stage 4 verification bundle JSON ('-' for stdin)")
    parser.add_argument("--repo-root", help="optional git repository root to verify live HEAD SHA")
    parser.add_argument("--swarm", action="store_true", help="enforce cross-family author vs verifier check")
    parser.add_argument(
        "--allow-intra-family-fallback",
        action="store_true",
        help="permit disclosed same-family verification when intra_family_fallback_reason (>=20 chars) is present",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0

    bundle_path = None if args.bundle == "-" else Path(args.bundle)
    try:
        raw = sys.stdin.read() if bundle_path is None else bundle_path.read_text(encoding="utf-8")
        bundle = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"verify_gate: cannot read bundle {args.bundle}: {exc}", file=sys.stderr)
        return 2

    repo_root: Path | None = None
    if args.repo_root:
        repo_root = Path(args.repo_root)
        if not repo_root.is_dir():
            print(f"verify_gate: --repo-root {args.repo_root} is not a directory", file=sys.stderr)
            return 2

    base_dir = bundle_path.resolve().parent if bundle_path is not None else Path.cwd()
    try:
        result = evaluate_bundle(
            bundle,
            base_dir=base_dir,
            repo_root=repo_root,
            force_swarm=args.swarm,
            allow_intra_family_fallback=args.allow_intra_family_fallback,
        )
    except IC.GhError as exc:
        print(f"verify_gate: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
