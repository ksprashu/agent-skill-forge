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

"""Gate executor for the /work DAG.

Before this file existed, the Gate column of a DAG was a comment. Any agent
could run ``dag_validator.py --set-status task=PASSED`` and the word PASSED
would be written to disk whether or not the gate held. This module supplies the
missing predicate: every gate name in the Gate column now resolves to a
function that returns a verdict, and the validator refuses to write PASSED
when that function says no.

Three kinds of gate, and the difference between them is the whole design:

``mechanical``
    The executor can settle it by itself, right now, by running a command or
    reading the filesystem. ``exit_0``, ``zero_mock``, ``file_exists``,
    ``victory_cert``, and any gate cell that is literally a shell command.

``attested``
    The gate is a judgement — "is this design sound", "did review pass" — and
    no script can make it. What a script *can* do is refuse an attestation that
    is unsigned, self-signed, cites artifacts that do not exist, cites
    artifacts that are empty, or was written against a different revision of
    the code than the one on disk. That is the ceiling for a judgement gate and
    this module goes to it, no further. It does not, and cannot, check whether
    the reviewer was right.

``trivial``
    ``none``. Passes. Recorded as passing for nothing.

Unknown gate names fail closed. A typo in the Gate column must not read as
permission.

Freshness is enforced throughout by ``tree_digest``: a SHA-256 over the sorted
(path, content-hash) pairs of every source file under the project root. A green
test run or a reviewer's approval only counts if the digest recorded alongside
it still matches the tree. Evidence for code that has since changed is not
evidence.

Exit codes: 0 gate passed, 1 gate failed, 2 invocation error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent

AGENTS_DIRNAME = ".agents"
EVIDENCE_DIRNAME = "evidence"
ATTESTATION_DIRNAME = "attestations"

#: Directories never included in a tree digest and never scanned for evidence.
DIGEST_EXCLUDE_DIRS = {
    ".git", ".agents", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "node_modules", ".venv", "venv", "dist", "build",
    ".tox", ".idea", ".vscode", "htmlcov", ".DS_Store",
}

#: Extensions that make up "the code" for freshness purposes. Docs change
#: constantly and should not invalidate a green test run.
DIGEST_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb",
    ".sh", ".sql", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json",
}

#: An artifact smaller than this is a placeholder, not a deliverable.
MIN_EVIDENCE_BYTES = 200

#: Text that means the artifact was scaffolded and never filled in.
PLACEHOLDER_MARKERS = ("TBD", "TODO", "FIXME", "<!-- fill", "PLACEHOLDER", "XXX")

DEFAULT_TIMEOUT = 900

TRIVIAL_GATES = {"none", "n/a", "na", "-", "", "null"}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """The verdict on one gate for one task.

    ``not_checked`` is not decoration. A gate that reports only what it
    verified, and stays silent about the rest, reads as a stronger claim than
    it is; every predicate here states its own blind spots.
    """

    gate: str
    task: str
    kind: str
    passed: bool
    reason: str
    evidence: List[str] = field(default_factory=list)
    not_checked: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "task": self.task,
            "kind": self.kind,
            "passed": self.passed,
            "reason": self.reason,
            "evidence": self.evidence,
            "not_checked": self.not_checked,
            "details": self.details,
        }


@dataclass
class GateSpec:
    """One row of the registry."""

    kind: str
    summary: str
    predicate: Callable[["GateContext"], GateResult]


@dataclass
class GateContext:
    """Everything a predicate is allowed to look at."""

    gate: str
    task: str
    base_dir: Path
    outputs: List[str] = field(default_factory=list)
    command: Optional[str] = None
    all_statuses: Dict[str, str] = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT
    source_dir: Optional[str] = None

    def agents_dir(self) -> Path:
        return self.base_dir / AGENTS_DIRNAME

    def scan_root(self) -> Path:
        return (self.base_dir / self.source_dir) if self.source_dir else self.base_dir


# ---------------------------------------------------------------------------
# Tree digest — the freshness primitive
# ---------------------------------------------------------------------------

def iter_source_files(root: Path) -> List[Path]:
    """Every file that counts as code under ``root``, sorted for determinism."""
    found: List[Path] = []
    root = Path(root)
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in DIGEST_EXCLUDE_DIRS
                             and not d.startswith("."))
        for name in sorted(filenames):
            if Path(name).suffix.lower() in DIGEST_EXTENSIONS:
                found.append(Path(dirpath) / name)
    return sorted(found)


def tree_digest(root: str | Path) -> str:
    """SHA-256 over the code under ``root``.

    Two trees share a digest when every code file has the same relative path
    and the same bytes. Docs, images and build output are excluded so that
    editing a README does not invalidate an otherwise valid test run.
    """
    root = Path(root).resolve()
    hasher = hashlib.sha256()
    for path in iter_source_files(root):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        rel = path.resolve().relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(hashlib.sha256(data).hexdigest().encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    """Filesystem-safe form of a task or gate id."""
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in value) or "unnamed"


# ---------------------------------------------------------------------------
# Command execution and the run ledger
# ---------------------------------------------------------------------------

def run_command(command: str, cwd: str | Path, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Run ``command`` as argv. Never through a shell.

    Handing the cell to a shell would let a Gate cell in a Markdown file — a
    file an agent writes — become arbitrary shell. The cell is split with
    ``shlex`` and executed directly, so ``&&``, pipes and redirection are inert
    text rather than operators.
    """
    argv = shlex.split(command)
    if not argv:
        return {"command": command, "argv": [], "exit_code": 2,
                "stdout": "", "stderr": "empty command", "duration_s": 0.0}
    started = time.time()
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout, check=False,
        )
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        code, out, err = 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        code, out, err = 127, "", f"could not execute: {exc}"
    return {
        "command": command,
        "argv": argv,
        "exit_code": code,
        "stdout": out,
        "stderr": err,
        "duration_s": round(time.time() - started, 3),
    }


def evidence_dir(base_dir: str | Path, task: str) -> Path:
    return Path(base_dir) / AGENTS_DIRNAME / EVIDENCE_DIRNAME / _slug(task)


#: A run recorded by the auditor proves the auditor ran, not that the tests
#: pass. Keeping the two kinds apart stops a clean audit from laundering itself
#: into an ``exit_0``.
KIND_VERIFICATION = "verification"
KIND_AUDIT = "audit"


def record_run(base_dir: str | Path, task: str, gate: str, result: Dict[str, Any],
               source_dir: Optional[str] = None,
               kind: str = KIND_VERIFICATION) -> Path:
    """Persist one execution, stamped with the digest of the tree it ran against."""
    base = Path(base_dir)
    scan_root = (base / source_dir) if source_dir else base
    target = evidence_dir(base, task)
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task,
        "gate": gate,
        "kind": kind,
        "command": result["command"],
        "argv": result.get("argv", []),
        "exit_code": result["exit_code"],
        "duration_s": result.get("duration_s"),
        "recorded_at": _now_iso(),
        "tree_digest": tree_digest(scan_root),
        "stdout_tail": (result.get("stdout") or "")[-4000:],
        "stderr_tail": (result.get("stderr") or "")[-4000:],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = target / f"run-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_runs(base_dir: str | Path, task: str,
              kind: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every recorded run for a task, oldest first. Unreadable records are skipped."""
    target = evidence_dir(base_dir, task)
    if not target.is_dir():
        return []
    runs: List[Dict[str, Any]] = []
    for path in sorted(target.glob("run-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Records written before `kind` existed are verification runs.
        if kind is not None and record.get("kind", KIND_VERIFICATION) != kind:
            continue
        record["_path"] = str(path)
        runs.append(record)
    return runs


def latest_run(base_dir: str | Path, task: str,
               kind: Optional[str] = KIND_VERIFICATION) -> Optional[Dict[str, Any]]:
    runs = load_runs(base_dir, task, kind=kind)
    return runs[-1] if runs else None


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------

ATTESTATION_FIELDS = ("task", "gate", "verdict", "reviewer_role", "worker_role",
                      "evidence", "summary", "tree_digest", "attested_at")


def attestation_path(base_dir: str | Path, task: str, gate: str) -> Path:
    return (Path(base_dir) / AGENTS_DIRNAME / ATTESTATION_DIRNAME
            / f"{_slug(task)}.{_slug(gate)}.json")


def write_attestation(base_dir: str | Path, task: str, gate: str, verdict: str,
                      reviewer_role: str, worker_role: str, evidence: Sequence[str],
                      summary: str, source_dir: Optional[str] = None) -> Path:
    """Write an attestation with the tree digest computed here, not supplied.

    The digest is taken by this function rather than accepted as an argument so
    that an attestation cannot be back-dated to a revision the reviewer never
    saw.
    """
    base = Path(base_dir)
    scan_root = (base / source_dir) if source_dir else base
    path = attestation_path(base, task, gate)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task,
        "gate": gate,
        "verdict": verdict.upper(),
        "reviewer_role": reviewer_role,
        "worker_role": worker_role,
        "evidence": list(evidence),
        "summary": summary,
        "tree_digest": tree_digest(scan_root),
        "attested_at": _now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _artifact_problem(base_dir: Path, rel: str) -> Optional[str]:
    """Why this cited artifact does not count as evidence, or None if it does."""
    path = Path(rel)
    if not path.is_absolute():
        path = base_dir / rel
    if not path.exists():
        return f"cited evidence does not exist: {rel}"
    if path.is_dir():
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return f"cited evidence unreadable: {rel} ({exc})"
    if len(raw) < MIN_EVIDENCE_BYTES:
        return (f"cited evidence is {len(raw)} bytes, under the "
                f"{MIN_EVIDENCE_BYTES}-byte floor: {rel}")
    text = raw.decode("utf-8", errors="replace")
    stripped = text
    for marker in PLACEHOLDER_MARKERS:
        stripped = stripped.replace(marker, "")
    if len(stripped.strip()) < MIN_EVIDENCE_BYTES:
        return f"cited evidence is placeholder text: {rel}"
    return None


def validate_attestation(record: Dict[str, Any], ctx: GateContext) -> List[str]:
    """Every mechanical reason to reject this attestation. Empty list means accept."""
    problems: List[str] = []

    missing = [f for f in ATTESTATION_FIELDS if f not in record]
    if missing:
        problems.append(f"attestation missing required fields: {', '.join(missing)}")
        return problems

    if str(record["verdict"]).upper() != "PASS":
        problems.append(f"attestation verdict is {record['verdict']!r}, not PASS")

    if record.get("task") != ctx.task:
        problems.append(
            f"attestation is for task {record.get('task')!r}, not {ctx.task!r}")
    if record.get("gate") != ctx.gate:
        problems.append(
            f"attestation is for gate {record.get('gate')!r}, not {ctx.gate!r}")

    reviewer = str(record.get("reviewer_role") or "").strip().lower()
    worker = str(record.get("worker_role") or "").strip().lower()
    if not reviewer:
        problems.append("attestation has no reviewer_role")
    if not worker:
        problems.append("attestation has no worker_role")
    if reviewer and reviewer == worker:
        problems.append(
            f"self-attestation: reviewer_role and worker_role are both {reviewer!r}")

    evidence = record.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        problems.append("attestation cites no evidence")
    else:
        for rel in evidence:
            problem = _artifact_problem(ctx.base_dir, str(rel))
            if problem:
                problems.append(problem)

    summary = str(record.get("summary") or "").strip()
    if len(summary) < 40:
        problems.append("attestation summary is under 40 characters; say what was reviewed")

    recorded_digest = str(record.get("tree_digest") or "")
    current_digest = tree_digest(ctx.scan_root())
    if not recorded_digest:
        problems.append("attestation carries no tree_digest")
    elif recorded_digest != current_digest:
        problems.append(
            "attestation is stale: the code changed after it was written "
            f"(attested {recorded_digest[:12]}, now {current_digest[:12]})")

    try:
        attested_at = datetime.fromisoformat(str(record.get("attested_at")))
        if attested_at.tzinfo is None:
            attested_at = attested_at.replace(tzinfo=timezone.utc)
        if attested_at > datetime.now(timezone.utc):
            problems.append("attestation is dated in the future")
    except (TypeError, ValueError):
        problems.append("attestation timestamp is unparseable")

    return problems


ATTESTATION_BLIND_SPOTS = [
    "whether the reviewer's judgement was correct",
    "whether the review was thorough",
    "whether the cited evidence actually supports the verdict",
]


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def _gate_trivial(ctx: GateContext) -> GateResult:
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="trivial", passed=True,
        reason="No gate declared for this task.",
        not_checked=["everything; this task declared no gate"],
    )


def _gate_recorded_exit_zero(ctx: GateContext) -> GateResult:
    """A verification command ran against *this* tree and exited 0.

    If ``--cmd`` is supplied the command is run now and recorded. Otherwise the
    most recent recorded run for the task is consulted, and rejected if it was
    taken against a different revision of the code.
    """
    if ctx.command:
        result = run_command(ctx.command, ctx.base_dir, ctx.timeout)
        path = record_run(ctx.base_dir, ctx.task, ctx.gate, result, ctx.source_dir)
        passed = result["exit_code"] == 0
        tail = (result["stderr"] or result["stdout"] or "").strip().splitlines()[-1:]
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=passed,
            reason=(f"`{ctx.command}` exited {result['exit_code']}"
                    + (f": {tail[0][:200]}" if tail and not passed else "")),
            evidence=[str(path)],
            not_checked=["whether the command that was run is the right command",
                         "whether the tests it ran assert anything meaningful"],
            details={"exit_code": result["exit_code"]},
        )

    record = latest_run(ctx.base_dir, ctx.task)
    if record is None:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=(f"No recorded verification run for task {ctx.task!r}. Run "
                    f"`gate_executor.py check --task {ctx.task} --gate {ctx.gate} "
                    f"--cmd '<your test command>'` first."),
            not_checked=[],
        )

    current = tree_digest(ctx.scan_root())
    if record.get("tree_digest") != current:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=("The code changed after the last recorded run "
                    f"(`{record.get('command')}`). Re-run it."),
            evidence=[record.get("_path", "")],
        )
    if record.get("exit_code") != 0:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=f"Last recorded run `{record.get('command')}` exited "
                   f"{record.get('exit_code')}",
            evidence=[record.get("_path", "")],
        )
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="mechanical", passed=True,
        reason=f"`{record.get('command')}` exited 0 against the current tree.",
        evidence=[record.get("_path", "")],
        not_checked=["whether the command that was run is the right command",
                     "whether the tests it ran assert anything meaningful"],
    )


def _gate_zero_mock(ctx: GateContext) -> GateResult:
    """The forensic auditor clears the tree in strict mode."""
    auditor = SCRIPT_DIR / "forensic_audit.py"
    if not auditor.exists():
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=f"Auditor not found at {auditor}",
        )
    command = (f"{shlex.quote(sys.executable)} {shlex.quote(str(auditor))} "
               f"--target-dir {shlex.quote(str(ctx.scan_root()))} --strict --quiet")
    result = run_command(command, ctx.base_dir, ctx.timeout)
    path = record_run(ctx.base_dir, ctx.task, ctx.gate, result, ctx.source_dir,
                      kind=KIND_AUDIT)
    passed = result["exit_code"] == 0
    summary = (result["stdout"] or "").strip().splitlines()
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="mechanical", passed=passed,
        reason=("Forensic audit clean in strict mode." if passed
                else "Forensic audit vetoed: " + "; ".join(summary[:4])[:400]),
        evidence=[str(path)],
        not_checked=["semantic correctness of the code the auditor cleared"],
        details={"exit_code": result["exit_code"]},
    )


def _gate_file_exists(ctx: GateContext) -> GateResult:
    """Every declared output exists and is more than a placeholder."""
    if not ctx.outputs:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason="Gate is `file_exists` but the task declares no outputs.",
        )
    problems = [p for p in (_artifact_problem(ctx.base_dir, o) for o in ctx.outputs) if p]
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="mechanical", passed=not problems,
        reason=("All declared outputs exist and carry content."
                if not problems else "; ".join(problems)),
        evidence=list(ctx.outputs),
        not_checked=["whether the content of these files is correct or relevant"],
    )


def _gate_victory_cert(ctx: GateContext) -> GateResult:
    """Terminal gate. Composite, and deliberately the strictest thing here.

    Requires, in order: no unfinished task anywhere in the DAG, a strict
    forensic audit with nothing outstanding, and a verification run against the
    current tree that exited 0. Any one of them missing and there is no
    certificate.
    """
    unfinished = sorted(tid for tid, status in ctx.all_statuses.items()
                        if tid != ctx.task and str(status).upper() != "PASSED")
    if unfinished:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=f"{len(unfinished)} task(s) not PASSED: {', '.join(unfinished[:8])}"
                   + (" …" if len(unfinished) > 8 else ""),
        )

    audit = _gate_zero_mock(ctx)
    if not audit.passed:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=f"Forensic audit failed at certification: {audit.reason}",
            evidence=audit.evidence,
        )

    exec_result = _gate_recorded_exit_zero(ctx)
    if not exec_result.passed:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason=f"No clean verification run at certification: {exec_result.reason}",
            evidence=audit.evidence + exec_result.evidence,
        )

    missing_outputs = [p for p in (_artifact_problem(ctx.base_dir, o)
                                   for o in ctx.outputs) if p]
    if missing_outputs:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="mechanical", passed=False,
            reason="; ".join(missing_outputs),
            evidence=audit.evidence + exec_result.evidence,
        )

    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="mechanical", passed=True,
        reason="All tasks PASSED, strict forensic audit clean, verification run exited 0.",
        evidence=audit.evidence + exec_result.evidence,
        not_checked=["whether the delivered system does what the user asked for",
                     "whether the tests cover the requirement, not just the code"],
    )


def _attested(ctx: GateContext) -> GateResult:
    path = attestation_path(ctx.base_dir, ctx.task, ctx.gate)
    if not path.exists():
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="attested", passed=False,
            reason=(f"No attestation at {path}. A reviewer in a role other than the "
                    f"worker's must run `gate_executor.py attest --task {ctx.task} "
                    f"--gate {ctx.gate} ...`."),
            not_checked=ATTESTATION_BLIND_SPOTS,
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="attested", passed=False,
            reason=f"Attestation at {path} is unreadable: {exc}",
            not_checked=ATTESTATION_BLIND_SPOTS,
        )
    if not isinstance(record, dict):
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="attested", passed=False,
            reason=f"Attestation at {path} is not a JSON object",
            not_checked=ATTESTATION_BLIND_SPOTS,
        )

    problems = validate_attestation(record, ctx)
    evidence = [str(path)] + [str(e) for e in (record.get("evidence") or [])]
    if problems:
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind="attested", passed=False,
            reason="; ".join(problems), evidence=[str(path)],
            not_checked=ATTESTATION_BLIND_SPOTS,
        )
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="attested", passed=True,
        reason=(f"Attested PASS by {record.get('reviewer_role')} against the current "
                f"tree, citing {len(record.get('evidence') or [])} artifact(s)."),
        evidence=evidence,
        not_checked=ATTESTATION_BLIND_SPOTS,
    )


def _gate_command(ctx: GateContext) -> GateResult:
    """The Gate cell is itself the command. Run it; exit 0 is the gate."""
    result = run_command(ctx.gate, ctx.base_dir, ctx.timeout)
    path = record_run(ctx.base_dir, ctx.task, ctx.gate, result, ctx.source_dir)
    passed = result["exit_code"] == 0
    tail = (result["stderr"] or result["stdout"] or "").strip().splitlines()[-1:]
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="command", passed=passed,
        reason=(f"`{ctx.gate}` exited {result['exit_code']}"
                + (f": {tail[0][:200]}" if tail and not passed else "")),
        evidence=[str(path)],
        not_checked=["whether this command verifies what the task claims to deliver"],
        details={"exit_code": result["exit_code"]},
    )


def _gate_unknown(ctx: GateContext) -> GateResult:
    return GateResult(
        gate=ctx.gate, task=ctx.task, kind="unknown", passed=False,
        reason=(f"Unrecognised gate {ctx.gate!r}. Known gates: "
                f"{', '.join(sorted(GATE_REGISTRY))}. A gate the executor cannot "
                f"evaluate is not a gate; fix the DAG or add a predicate."),
    )


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

GATE_REGISTRY: Dict[str, GateSpec] = {
    "none": GateSpec("trivial", "No gate.", _gate_trivial),

    "exit_0": GateSpec(
        "mechanical", "A recorded verification command exited 0 against this tree.",
        _gate_recorded_exit_zero),
    "test_pass": GateSpec(
        "mechanical", "Alias of exit_0.", _gate_recorded_exit_zero),
    "all_passed": GateSpec(
        "mechanical", "Alias of exit_0, evaluated at a join.", _gate_recorded_exit_zero),

    "zero_mock": GateSpec(
        "mechanical", "forensic_audit.py --strict exits 0.", _gate_zero_mock),
    "file_exists": GateSpec(
        "mechanical", "Every declared output exists and is not a placeholder.",
        _gate_file_exists),
    "victory_cert": GateSpec(
        "mechanical", "All tasks PASSED + strict audit clean + verification run green.",
        _gate_victory_cert),

    "spec_approved": GateSpec(
        "attested", "A reviewer attested the spec is complete and unambiguous.", _attested),
    "design_pass": GateSpec(
        "attested", "A reviewer attested the design proposal is substantive.", _attested),
    "arbiter_pass": GateSpec(
        "attested", "The Arbiter attested a selection, citing evidence.", _attested),
    "spike_pass": GateSpec(
        "attested", "A reviewer attested the validation spike proved the risky assumption.",
        _attested),
    "review_pass": GateSpec(
        "attested", "A reviewer attested the code review passed.", _attested),
    "review_5axis_pass": GateSpec(
        "attested", "A reviewer attested the five-axis review passed.", _attested),
    "acceptance_pass": GateSpec(
        "attested", "A reviewer attested the deliverable meets the spec.", _attested),
    "committee_join": GateSpec(
        "attested", "Every committee member attested; recorded as one join attestation.",
        _attested),

    # Emitted by the `review` and `massive` topologies in scaffold_work.py.
    # Every one of these is a reading task: whether a claim checks out, whether
    # two documents contradict each other, whether prose is padded. No script
    # settles any of them, so they are attested like the rest.
    "survey_pass": GateSpec(
        "attested", "A reviewer attested the codebase survey is complete.", _attested),
    "fact_check_pass": GateSpec(
        "attested", "A reviewer attested each checked claim against its source.", _attested),
    "analysis_pass": GateSpec(
        "attested", "A reviewer attested the inconsistency analysis is complete.", _attested),
    "unslop_clean": GateSpec(
        "attested", "A reviewer attested the prose is free of filler per skills/unslop.",
        _attested),
}


def resolve_spec(gate: str) -> GateSpec:
    """Map a Gate cell to its spec. Command cells route to the command runner."""
    token = (gate or "").strip()
    if token.lower() in TRIVIAL_GATES:
        return GATE_REGISTRY["none"]
    if token in GATE_REGISTRY:
        return GATE_REGISTRY[token]
    lowered = token.lower()
    if lowered in GATE_REGISTRY:
        return GATE_REGISTRY[lowered]
    if _looks_like_command(token):
        return GateSpec("command", "Literal command in the Gate cell.", _gate_command)
    return GateSpec("unknown", "Unrecognised.", _gate_unknown)


def _looks_like_command(token: str) -> bool:
    """A Gate cell is a command when it has arguments and names a real runner.

    Deliberately narrow. Anything that merely *looks* shell-ish would let a
    typo'd gate name execute; requiring a known runner keeps an unrecognised
    single word failing closed.
    """
    if " " not in token:
        return False
    head = shlex.split(token)[0] if token.strip() else ""
    head = Path(head).name.lower()
    runners = {"pytest", "python", "python3", "python3.12", "python3.13", "npm",
               "npx", "node", "go", "cargo", "make", "ruff", "mypy", "jest",
               "vitest", "bash", "sh", "uv", "poetry", "tox"}
    return head in runners or head.startswith("python")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate_gate(gate: str, task: str, base_dir: str | Path = ".", *,
                  outputs: Optional[Sequence[str]] = None,
                  command: Optional[str] = None,
                  all_statuses: Optional[Dict[str, str]] = None,
                  timeout: int = DEFAULT_TIMEOUT,
                  source_dir: Optional[str] = None) -> GateResult:
    """Evaluate one gate for one task. The single entry point for callers."""
    ctx = GateContext(
        gate=(gate or "none").strip(),
        task=task,
        base_dir=Path(base_dir).resolve(),
        outputs=list(outputs or []),
        command=command,
        all_statuses=dict(all_statuses or {}),
        timeout=timeout,
        source_dir=source_dir,
    )
    spec = resolve_spec(ctx.gate)
    try:
        return spec.predicate(ctx)
    except Exception as exc:  # a crashing predicate must not read as a pass
        return GateResult(
            gate=ctx.gate, task=ctx.task, kind=spec.kind, passed=False,
            reason=f"Gate predicate raised {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_result(result: GateResult) -> None:
    icon = "PASS" if result.passed else "FAIL"
    print(f"[{icon}] gate={result.gate} task={result.task} ({result.kind})")
    print(f"  {result.reason}")
    if result.evidence:
        print("  Evidence:")
        for item in result.evidence:
            print(f"    - {item}")
    if result.not_checked:
        print("  Not checked by this gate:")
        for item in result.not_checked:
            print(f"    - {item}")


def _cmd_check(args: argparse.Namespace) -> int:
    result = evaluate_gate(
        args.gate, args.task, args.base_dir,
        outputs=args.output, command=args.cmd, timeout=args.timeout,
        source_dir=args.source_dir,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    elif not args.quiet:
        _print_result(result)
    return 0 if result.passed else 1


def _cmd_attest(args: argparse.Namespace) -> int:
    spec = GATE_REGISTRY.get(args.gate)
    if spec is None or spec.kind != "attested":
        attestable = sorted(g for g, s in GATE_REGISTRY.items() if s.kind == "attested")
        print(f"Error: {args.gate!r} is not an attested gate. Attested gates: "
              f"{', '.join(attestable)}", file=sys.stderr)
        return 2
    if args.reviewer_role.strip().lower() == args.worker_role.strip().lower():
        print("Error: reviewer_role and worker_role are identical; a worker cannot "
              "attest their own gate.", file=sys.stderr)
        return 2
    path = write_attestation(
        args.base_dir, args.task, args.gate, args.verdict, args.reviewer_role,
        args.worker_role, args.evidence, args.summary, args.source_dir,
    )
    # Written, now judged by the same rules any other caller faces.
    result = evaluate_gate(args.gate, args.task, args.base_dir,
                           source_dir=args.source_dir)
    if not args.quiet:
        print(f"Attestation written to {path}")
        _print_result(result)
    return 0 if result.passed else 1


def _cmd_record(args: argparse.Namespace) -> int:
    result = run_command(args.cmd, args.base_dir, args.timeout)
    path = record_run(args.base_dir, args.task, args.gate, result, args.source_dir)
    if not args.quiet:
        print(f"Recorded `{args.cmd}` -> exit {result['exit_code']} at {path}")
        if result["exit_code"] != 0:
            sys.stderr.write((result["stderr"] or result["stdout"])[-2000:])
    return 0 if result["exit_code"] == 0 else 1


def _cmd_list(args: argparse.Namespace) -> int:
    rows = [(name, spec.kind, spec.summary) for name, spec in sorted(GATE_REGISTRY.items())]
    if args.json:
        print(json.dumps([{"gate": n, "kind": k, "summary": s} for n, k, s in rows], indent=2))
        return 0
    width = max(len(n) for n, _, _ in rows)
    print("Gate registry\n")
    for name, kind, summary in rows:
        print(f"  {name.ljust(width)}  {kind:<10}  {summary}")
    print("\n  <command>".ljust(width + 4)
          + "  command     A Gate cell that is a literal test command is run as argv.")
    print("\nAnything else fails closed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate /work DAG barrier gates (skills/work)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--base-dir", default=".", help="Project root (default: .)")
        p.add_argument("--source-dir", default=None,
                       help="Subdirectory holding the code, for digest and audit scope")
        p.add_argument("--quiet", "-q", action="store_true")

    check = sub.add_parser("check", help="Evaluate one gate")
    check.add_argument("--gate", required=True)
    check.add_argument("--task", required=True)
    check.add_argument("--cmd", default=None,
                       help="Verification command to run and record for exit_0 gates")
    check.add_argument("--output", action="append", default=[],
                       help="Declared output path (repeatable), for file_exists")
    check.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    check.add_argument("--json", action="store_true")
    add_common(check)
    check.set_defaults(func=_cmd_check)

    attest = sub.add_parser("attest", help="Write a reviewer attestation for a judgement gate")
    attest.add_argument("--gate", required=True)
    attest.add_argument("--task", required=True)
    attest.add_argument("--verdict", required=True, choices=["PASS", "FAIL"])
    attest.add_argument("--reviewer-role", required=True,
                        help="Role of the attesting agent, e.g. code-reviewer")
    attest.add_argument("--worker-role", required=True,
                        help="Role that produced the work under review")
    attest.add_argument("--evidence", action="append", default=[], required=True,
                        help="Path to an artifact supporting the verdict (repeatable)")
    attest.add_argument("--summary", required=True,
                        help="What was reviewed and what was found (40+ chars)")
    add_common(attest)
    attest.set_defaults(func=_cmd_attest)

    record = sub.add_parser("record", help="Run a command and record the result as evidence")
    record.add_argument("--task", required=True)
    record.add_argument("--gate", default="exit_0")
    record.add_argument("--cmd", required=True)
    record.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_common(record)
    record.set_defaults(func=_cmd_record)

    listing = sub.add_parser("list", help="Print the gate registry")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=_cmd_list)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
