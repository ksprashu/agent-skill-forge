#!/usr/bin/env python3
"""Deterministic checks behind the H2O swarm's gates.

Audits:
  verdict       a reviewer's verdict post has one VERDICT line, real evidence
                (a code span, a "$ command" line, or a file:line reference) and,
                for NOT GOOD, at least one numbered finding.
  freeze        records SHA-256 hashes of the approved criteria and acceptance
                tests into <state-dir>/state.json.
  check-frozen  fails if any frozen file changed or disappeared.
  record        counts NOT GOOD verdicts per gate against the cap in
                swarm.config.json and prints where the loop goes next.
  grant         extends one gate's cap after the user chooses to continue.
  status        prints the loop state.
  diff-guard    fails a unified diff that deletes test files, adds skip
                markers or lint/type suppressions, or removes more assertions
                from test files than it adds.

Does NOT judge: whether findings are correct, whether evidence is genuine
output, or whether code, plans or tests are good. Those are reviewer judgement.

Gates, routing and caps are read from swarm.config.json next to this skill, so
this script never restates them.

Exit codes: 0 pass, 1 fail, 2 invocation error, 3 loop cap reached (ask the user).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_CAP = 0, 1, 2, 3
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "swarm.config.json"
STATE_FILE = "state.json"

VERDICT_RE = re.compile(r"VERDICT:\s*(GOOD|NOT GOOD \(DESIGN\)|NOT GOOD)(?!\w)")
EVIDENCE_TOKEN_RE = re.compile(r"`[^`]+`|^\s*\$ \S|\S+\.\w+:\d+", re.MULTILINE)
PLACEHOLDERS = {"", "none", "n/a", "na", "-", "tbd", "todo", "see above"}
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)

TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec)/"
    r"|(^|/)test_[^/]+\.py$|_test\.(py|go)$"
    r"|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(java|kt|cs)$"
)
SKIP_RE = re.compile(
    r"@pytest\.mark\.(skip|xfail)|\bpytest\.skip\(|@unittest\.skip"
    r"|\b(it|test|describe)\.skip\(|\bx(it|describe|test)\("
    r"|@Disabled\b|@Ignore\b|\bt\.Skip(Now)?\(|#\[ignore\]"
)
SUPPRESS_RE = re.compile(
    r"#\s*noqa\b|#\s*type:\s*ignore|eslint-disable|@ts-(ignore|nocheck|expect-error)"
    r"|//\s*nolint|#\s*pylint:\s*disable|NOSONAR|#\s*nosec\b"
)
ASSERT_RE = re.compile(r"\bassert\w*\b|\bexpect\(|\bself\.assert|\bt\.(Error|Fatal)")


# ---------------------------------------------------------------- helpers

def fail_usage(message: str) -> int:
    print(f"h2o_gate: {message}", file=sys.stderr)
    return EXIT_USAGE


def emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def gates_of(config: dict) -> dict:
    return {stage["id"]: stage for stage in config["stages"] if stage.get("gate")}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_state(config: dict) -> dict:
    gates = gates_of(config)
    return {
        "frozen": {},
        "not_good": {gate: 0 for gate in gates},
        "grants": {gate: 0 for gate in gates},
        "implementation_not_good": 0,
    }


def read_state(state_dir: Path) -> dict:
    path = state_dir / STATE_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `freeze` or `record` first")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with open(state_dir / STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def section(text: str, name: str) -> str:
    """Text after `<name>:` up to the next Evidence/Findings/VERDICT header or the end."""
    match = re.search(rf"^{name}:(.*?)(?=^(?:Evidence|Findings):|^.*VERDICT:|\Z)",
                      text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------- verdict

def check_verdict(text: str) -> dict:
    reasons = []
    found = VERDICT_RE.findall(text)
    if len(found) != 1:
        reasons.append(f"expected exactly one VERDICT line, found {len(found)}")
        return {"verdict": "MALFORMED", "evidence": False, "findings": 0, "reasons": reasons}

    raw = found[0]
    verdict = {"GOOD": "GOOD", "NOT GOOD": "NOT_GOOD", "NOT GOOD (DESIGN)": "DESIGN"}[raw]
    evidence = section(text, "Evidence")
    findings = section(text, "Findings")
    has_evidence = (evidence.lower() not in PLACEHOLDERS
                    and bool(EVIDENCE_TOKEN_RE.search(evidence)))
    n_findings = len(NUMBERED_RE.findall(findings))

    if not has_evidence:
        reasons.append("no evidence: paste commands run and output, or file:line references")
    if verdict != "GOOD" and n_findings == 0:
        reasons.append("NOT GOOD needs at least one numbered finding")
    if reasons:
        verdict = "MALFORMED"
    return {"verdict": verdict, "evidence": has_evidence, "findings": n_findings, "reasons": reasons}


def cmd_verdict(args: argparse.Namespace) -> int:
    if args.file == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.file)
        if not path.is_file():
            return fail_usage(f"verdict file not found: {path}")
        text = path.read_text(encoding="utf-8")
    result = check_verdict(text)
    emit(result)
    return EXIT_PASS if result["verdict"] == "GOOD" else EXIT_FAIL


# ---------------------------------------------------------------- freeze

def cmd_freeze(args: argparse.Namespace, config: dict) -> int:
    state_dir = Path(args.state_dir)
    existing = state_dir / STATE_FILE
    if existing.exists():
        state = read_state(state_dir)
        if state.get("frozen") and not args.force:
            print(f"h2o_gate: {existing} already frozen; pass --force to re-freeze", file=sys.stderr)
            return EXIT_FAIL
    else:
        state = fresh_state(config)

    frozen = {}
    for name in args.file:
        path = Path(name)
        if not path.is_file():
            return fail_usage(f"cannot freeze missing file: {path}")
        frozen[name] = sha256_of(path)
    state["frozen"] = frozen
    if args.force:
        gates = gates_of(config)
        state["not_good"] = {gate: 0 for gate in gates}
        state["grants"] = {gate: 0 for gate in gates}
        state["implementation_not_good"] = 0
    write_state(state_dir, state)
    emit({"frozen": sorted(frozen), "gates": sorted(gates_of(config))})
    return EXIT_PASS


def cmd_check_frozen(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    try:
        state = read_state(state_dir)
    except FileNotFoundError:
        state = fresh_state(config)
    if not state.get("frozen"):
        emit({"changed": [], "missing": [], "ok": False, "reason": "nothing frozen yet"})
        return EXIT_FAIL
    changed, missing = [], []
    for name, digest in sorted(state["frozen"].items()):
        path = Path(name)
        if not path.is_file():
            missing.append(name)
        elif sha256_of(path) != digest:
            changed.append(name)
    emit({"changed": changed, "missing": missing, "ok": not (changed or missing)})
    return EXIT_FAIL if changed or missing else EXIT_PASS


# ---------------------------------------------------------------- loop counters

def cap_for(config: dict, state: dict, gate: str) -> int:
    return config["loop_policy"]["max_not_good_per_gate"] + state["grants"].get(gate, 0)


def cmd_record(args: argparse.Namespace, config: dict) -> int:
    gates = gates_of(config)
    if args.gate not in gates:
        return fail_usage(f"unknown gate {args.gate!r}; gates are {sorted(gates)}")
    stage = gates[args.gate]
    if args.verdict == "DESIGN" and "on_design_defect" not in stage:
        return fail_usage(f"gate {args.gate!r} has no DESIGN route")
    state_dir = Path(args.state_dir)
    try:
        state = read_state(state_dir)
    except FileNotFoundError:
        state = fresh_state(config)

    route = {"GOOD": "on_good", "NOT_GOOD": "on_not_good", "DESIGN": "on_design_defect"}[args.verdict]
    next_stage = stage[route]
    charged = None
    if args.verdict == "NOT_GOOD":
        charged = args.gate
    elif args.verdict == "DESIGN":
        charged = config["loop_policy"]["design_defect_counts_against"]

    escalate = None
    if charged:
        state["not_good"][charged] = state["not_good"].get(charged, 0) + 1
        if args.verdict == "NOT_GOOD" and next_stage == "implement":
            state["implementation_not_good"] += 1
            implementer = config["roles"]["implementer"]
            if state["implementation_not_good"] == implementer.get("escalate_after_not_good"):
                escalate = implementer.get("escalate_to")
    write_state(Path(args.state_dir), state)

    cap_reached = bool(charged) and state["not_good"][charged] >= cap_for(config, state, charged)
    emit({
        "gate": args.gate,
        "verdict": args.verdict,
        "charged_gate": charged,
        "not_good": state["not_good"].get(charged) if charged else None,
        "cap": cap_for(config, state, charged) if charged else None,
        "next_stage": "ask_user" if cap_reached else next_stage,
        "escalate_implementer_to": escalate,
    })
    return EXIT_CAP if cap_reached else EXIT_PASS


def cmd_grant(args: argparse.Namespace, config: dict) -> int:
    gates = gates_of(config)
    if args.gate not in gates:
        return fail_usage(f"unknown gate {args.gate!r}; gates are {sorted(gates)}")
    state_dir = Path(args.state_dir)
    try:
        state = read_state(state_dir)
    except FileNotFoundError:
        state = fresh_state(config)
    attempts = args.attempts or config["loop_policy"]["continue_grants_attempts"]
    state["grants"][args.gate] = state["grants"].get(args.gate, 0) + attempts
    write_state(Path(args.state_dir), state)
    emit({"gate": args.gate, "granted": attempts, "cap": cap_for(config, state, args.gate)})
    return EXIT_PASS


def cmd_status(args: argparse.Namespace) -> int:
    try:
        emit(read_state(Path(args.state_dir)))
    except FileNotFoundError as exc:
        return fail_usage(str(exc))
    return EXIT_PASS


# ---------------------------------------------------------------- diff guard

def scan_diff(diff: str) -> list:
    violations = []
    current, deleted = None, False
    removed_asserts, added_asserts = {}, {}

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/", 1)
            current, deleted = (parts[1] if len(parts) == 2 else None), False
            continue
        if line.startswith("deleted file mode"):
            deleted = True
            if current and TEST_PATH_RE.search(current):
                violations.append({"file": current, "kind": "deleted_test_file", "line": ""})
            continue
        if current is None or line.startswith(("+++", "---")):
            continue
        is_test = bool(TEST_PATH_RE.search(current))
        if line.startswith("+"):
            body = line[1:]
            if SKIP_RE.search(body):
                violations.append({"file": current, "kind": "added_skip", "line": body.strip()})
            if SUPPRESS_RE.search(body):
                violations.append({"file": current, "kind": "added_suppression", "line": body.strip()})
            if is_test and ASSERT_RE.search(body):
                added_asserts[current] = added_asserts.get(current, 0) + 1
        elif line.startswith("-") and is_test and not deleted and ASSERT_RE.search(line[1:]):
            removed_asserts[current] = removed_asserts.get(current, 0) + 1

    for path, removed in sorted(removed_asserts.items()):
        net = removed - added_asserts.get(path, 0)
        if net > 0:
            violations.append({"file": path, "kind": "assertions_removed", "line": f"net -{net}"})
    return violations


def cmd_diff_guard(args: argparse.Namespace) -> int:
    if args.diff_file:
        path = Path(args.diff_file)
        if not path.is_file():
            return fail_usage(f"diff file not found: {path}")
        diff = path.read_text(encoding="utf-8")
    else:
        proc = subprocess.run(
            ["git", "-C", args.repo, "diff", "--no-color", "-M", args.base],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            return fail_usage(f"git diff failed: {proc.stderr.strip()}")
        diff = proc.stdout
    violations = scan_diff(diff)
    emit({"ok": not violations, "violations": violations})
    return EXIT_FAIL if violations else EXIT_PASS


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="path to swarm.config.json (default: the skill's own)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verdict", help="check a reviewer verdict post")
    p.add_argument("--file", required=True, help="verdict text file, or - for stdin")

    p = sub.add_parser("freeze", help="hash the approved criteria and acceptance tests")
    p.add_argument("--state-dir", required=True)
    p.add_argument("--file", action="append", required=True, help="file to freeze (repeatable)")
    p.add_argument("--force", action="store_true", help="overwrite an existing freeze")

    p = sub.add_parser("check-frozen", help="fail if a frozen file changed")
    p.add_argument("--state-dir", required=True)

    p = sub.add_parser("record", help="record a gate verdict and print the next stage")
    p.add_argument("--state-dir", required=True)
    p.add_argument("--gate", required=True)
    p.add_argument("--verdict", required=True, choices=["GOOD", "NOT_GOOD", "DESIGN"])

    p = sub.add_parser("grant", help="extend a gate's cap after the user says continue")
    p.add_argument("--state-dir", required=True)
    p.add_argument("--gate", required=True)
    p.add_argument("--attempts", type=int, default=0,
                   help="attempts to add (default: loop_policy.continue_grants_attempts)")

    p = sub.add_parser("status", help="print the loop state")
    p.add_argument("--state-dir", required=True)

    p = sub.add_parser("diff-guard", help="fail a diff that weakens tests")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff-file", help="unified diff to scan")
    source.add_argument("--base", help="git ref to diff the working tree against")
    p.add_argument("--repo", default=".", help="repository for --base (default: .)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verdict":
        return cmd_verdict(args)
    if args.command == "check-frozen":
        return cmd_check_frozen(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "diff-guard":
        return cmd_diff_guard(args)
    try:
        config = load_config(Path(args.config))
    except (OSError, ValueError) as exc:
        return fail_usage(f"cannot read config {args.config}: {exc}")
    handlers = {"freeze": cmd_freeze, "record": cmd_record, "grant": cmd_grant}
    return handlers[args.command](args, config)


if __name__ == "__main__":
    sys.exit(main())
