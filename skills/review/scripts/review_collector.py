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

"""Review evidence collector (S9): gathers facts, runs the repo's own tools.

What it does:
  - diff facts: changed files, insertions/deletions, the 500-line flag
    (working tree vs HEAD, --staged, --base REF, or --pr N via `gh`)
  - repo facts: manifests, detected tool configs, topology
  - EXECUTES the linters, formatters (check mode) and type checkers whose
    config or ecosystem is present and whose binary is on PATH (or in
    node_modules/.bin), with a timeout, shell=False, scoped to the changed
    files in diff/PR mode; `gh pr checks` when --pr is given
  - records per tool: status ran / skipped (with reason) / timed_out, argv,
    exit code, duration, and truncated output (parsed JSON where the tool
    supports a JSON format, with an issue count)

What it does not do (V5): judge. There is no score, verdict or "passed" in
the output. Exit codes are reported as facts. A tool that did not run is
listed under `not_inspected` with the reason; it is never treated as clean.

Security note: running a repo's linters executes repo-controlled code
(eslint.config.js, prettier.config.js, conftest/plugins, build.rs for
clippy). Use --no-exec on code you do not trust, e.g. a fork's PR.

Exit codes:
  0   evidence collected (whatever the tools reported)
  1   collection failed (not a git repo in diff mode, gh unavailable or
      failing in --pr mode, unreadable path)
  2   usage error (argparse)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

COLLECTOR_VERSION = "2.0.0"
DEFAULT_TIMEOUT = 120
OUTPUT_CHAR_LIMIT = 20_000
ISSUE_LIMIT = 200
REPO_FILE_LIMIT = 2_000
PR_BODY_LIMIT = 4_000

IGNORE_DIRS: set[str] = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build",
    ".next", ".cache", "target", ".turbo", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

MANIFEST_MAP: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java/gradle",
    "build.gradle.kts": "kotlin/gradle",
    "Gemfile": "ruby",
    "composer.json": "php",
    "flake.nix": "nix",
}

UNINSPECTED_SURFACE: list[str] = [
    "runtime behaviour, memory and latency profiles",
    "production traffic, logs and telemetry",
    "design intent and business correctness (the reviewer's job)",
    "third-party cloud permissions and remote state",
    "test suites (not run by the collector; run them in the challenger phase)",
]

PR_FIELDS = ("number,title,body,author,url,state,isDraft,baseRefName,headRefName,"
             "headRefOid,additions,deletions,changedFiles,files,labels,reviewDecision")
PR_CHECK_FIELDS = "name,state,bucket,link,workflow"

PY = (".py", ".pyi")
JS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte")
PRETTIER = JS + (".json", ".jsonc", ".css", ".scss", ".less", ".html", ".md", ".mdx",
                 ".yaml", ".yml", ".graphql")
SHELL = (".sh", ".bash")
MD = (".md", ".markdown")


# --- small helpers -----------------------------------------------------------

def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          shell=False, check=False)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _truncate(text: str, limit: int = OUTPUT_CHAR_LIMIT) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n... [{len(text) - limit} more characters truncated]", True


def _first_glob(root: Path, patterns: tuple[str, ...]) -> str | None:
    for pat in patterns:
        for match in sorted(root.glob(pat)):
            if match.is_file():
                return match.relative_to(root).as_posix()
    return None


def _pyproject_has(root: Path, table: str) -> bool:
    return f"[{table}]" in _read(root / "pyproject.toml") or \
        f"[{table}." in _read(root / "pyproject.toml")


def _package_json(root: Path) -> dict[str, Any]:
    try:
        data = json.loads(_read(root / "package.json") or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


# --- tool registry -------------------------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    """How to find, trigger, scope and run one tool.

    trigger(root) returns the config file or ecosystem marker that makes the
    tool applicable, or None. build(files) returns argv after the binary;
    files is None for an unscoped (whole repo) run.
    """
    name: str
    category: str
    binary: str
    trigger: Callable[[Path], str | None]
    build: Callable[[list[str] | None], list[str]]
    extensions: tuple[str, ...] = ()
    file_scoped: bool = True          # False: tool runs on the project, not files
    needs_files: bool = False         # True: unscoped run needs an explicit file list
    parse: str = "text"               # json | jsonlines | text
    node_local: bool = False          # also look in node_modules/.bin
    name_filter: Callable[[str], bool] | None = None


def _ruff_trigger(root: Path) -> str | None:
    return _first_glob(root, ("ruff.toml", ".ruff.toml")) or \
        ("pyproject.toml [tool.ruff]" if _pyproject_has(root, "tool.ruff") else None)


def _eslint_trigger(root: Path) -> str | None:
    return _first_glob(root, (".eslintrc", ".eslintrc.*", "eslint.config.*")) or \
        ("package.json eslintConfig" if "eslintConfig" in _package_json(root) else None)


def _prettier_trigger(root: Path) -> str | None:
    return _first_glob(root, (".prettierrc", ".prettierrc.*", "prettier.config.*")) or \
        ("package.json prettier" if "prettier" in _package_json(root) else None)


def _mypy_trigger(root: Path) -> str | None:
    found = _first_glob(root, ("mypy.ini", ".mypy.ini"))
    if found:
        return found
    if _pyproject_has(root, "tool.mypy"):
        return "pyproject.toml [tool.mypy]"
    if "[mypy]" in _read(root / "setup.cfg"):
        return "setup.cfg [mypy]"
    return None


def _pyright_trigger(root: Path) -> str | None:
    return _first_glob(root, ("pyrightconfig.json",)) or \
        ("pyproject.toml [tool.pyright]" if _pyproject_has(root, "tool.pyright") else None)


def _has_files(exts: tuple[str, ...], label: str) -> Callable[[Path], str | None]:
    def trigger(root: Path) -> str | None:
        return label if _walk(root, exts, None, limit=1) else None
    return trigger


def _is_dockerfile(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    return base == "Dockerfile" or base.startswith("Dockerfile.") or base.endswith(".Dockerfile")


def _dockerfile_trigger(root: Path) -> str | None:
    return "Dockerfile present" if _walk(root, (), _is_dockerfile, limit=1) else None


def _go_pkg(path: str) -> str:
    parent = Path(path).parent.as_posix()
    return "." if parent == "." else "./" + parent


def _files_or(default: list[str]) -> Callable[[list[str] | None], list[str]]:
    return lambda files: files if files is not None else default


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("ruff-check", "linter", "ruff", _ruff_trigger,
             lambda f: ["check", "--output-format", "json", "--no-fix", *_files_or(["."])(f)],
             PY, parse="json"),
    ToolSpec("ruff-format", "formatter", "ruff", _ruff_trigger,
             lambda f: ["format", "--check", *_files_or(["."])(f)], PY),
    ToolSpec("black", "formatter", "black",
             lambda r: "pyproject.toml [tool.black]" if _pyproject_has(r, "tool.black") else None,
             lambda f: ["--check", *_files_or(["."])(f)], PY),
    ToolSpec("mypy", "typechecker", "mypy", _mypy_trigger,
             lambda f: ["--no-color-output", "--no-error-summary", *_files_or(["."])(f)], PY),
    ToolSpec("pyright", "typechecker", "pyright", _pyright_trigger,
             lambda f: ["--outputjson", *_files_or([])(f)], PY, parse="json"),
    ToolSpec("python-compile", "syntax", "python",
             _has_files(PY[:1], "*.py files present"),
             lambda f: ["-m", "py_compile", *(f or [])], PY[:1], needs_files=True),
    ToolSpec("eslint", "linter", "eslint", _eslint_trigger,
             lambda f: ["--format", "json", *_files_or(["."])(f)], JS, parse="json",
             node_local=True),
    ToolSpec("biome", "linter", "biome",
             lambda r: _first_glob(r, ("biome.json", "biome.jsonc")),
             lambda f: ["check", "--reporter=json", *_files_or(["."])(f)], JS + (".json", ".css"),
             parse="json", node_local=True),
    ToolSpec("prettier", "formatter", "prettier", _prettier_trigger,
             lambda f: ["--check", *_files_or(["."])(f)], PRETTIER, node_local=True),
    ToolSpec("tsc", "typechecker", "tsc",
             lambda r: _first_glob(r, ("tsconfig.json",)),
             lambda f: ["--noEmit", "--pretty", "false", "-p", "tsconfig.json"], JS,
             file_scoped=False, node_local=True),
    ToolSpec("golangci-lint", "linter", "golangci-lint",
             lambda r: _first_glob(r, (".golangci.yml", ".golangci.yaml", ".golangci.toml",
                                       ".golangci.json", "go.mod")),
             lambda f: ["run", *(sorted({_go_pkg(p) for p in f}) if f is not None
                                 else ["./..."])],
             (".go",)),
    ToolSpec("cargo-clippy", "linter", "cargo",
             lambda r: _first_glob(r, ("Cargo.toml",)),
             lambda f: ["clippy", "--quiet", "--message-format=json"], (".rs",),
             file_scoped=False, parse="jsonlines"),
    ToolSpec("shellcheck", "linter", "shellcheck", _has_files(SHELL, "shell scripts present"),
             lambda f: ["-f", "json1", *(f or [])], SHELL, needs_files=True, parse="json"),
    ToolSpec("hadolint", "linter", "hadolint", _dockerfile_trigger,
             lambda f: ["-f", "json", *(f or [])], (), needs_files=True, parse="json",
             name_filter=_is_dockerfile),
    ToolSpec("markdownlint", "linter", "markdownlint",
             lambda r: _first_glob(r, (".markdownlint.json", ".markdownlint.jsonc",
                                       ".markdownlint.yaml", ".markdownlint.yml",
                                       ".markdownlintrc")),
             lambda f: ["--json", *_files_or(["."])(f)], MD, parse="json", node_local=True),
)


def _walk(root: Path, exts: tuple[str, ...], name_filter: Callable[[str], bool] | None,
          limit: int = REPO_FILE_LIMIT) -> list[str]:
    found: list[str] = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
        for fname in sorted(files):
            rel = (Path(dirpath) / fname).relative_to(root).as_posix()
            if (exts and fname.lower().endswith(exts)) or (name_filter and name_filter(rel)):
                found.append(rel)
                if len(found) >= limit:
                    return found
    return found


def _matches(spec: ToolSpec, path: str) -> bool:
    if spec.name_filter is not None:
        return spec.name_filter(path)
    return path.lower().endswith(spec.extensions)


def _resolve_binary(spec: ToolSpec, root: Path) -> str | None:
    if spec.name == "python-compile":
        return sys.executable
    if spec.node_local:
        local = root / "node_modules" / ".bin" / spec.binary
        if local.is_file() and os.access(local, os.X_OK):
            return str(local)
    return shutil.which(spec.binary)


# --- process execution ---------------------------------------------------------

def run_command(argv: list[str], cwd: Path, timeout: float,
                env: dict[str, str] | None = None) -> dict[str, Any]:
    """Run argv with shell=False; kill the whole process group on timeout."""
    started = time.monotonic()
    popen_kw: dict[str, Any] = {}
    if os.name == "posix":
        popen_kw["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                                encoding="utf-8", errors="replace", shell=False,
                                env=env, **popen_kw)
    except OSError as exc:
        return {"status": "skipped", "reason": f"could not start: {exc}", "exit_code": None,
                "stdout": "", "stderr": "", "duration_s": 0.0}
    try:
        out, err = proc.communicate(timeout=timeout)
        status, code = "ran", proc.returncode
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
        else:
            proc.kill()
        out, err = proc.communicate()
        status, code = "timed_out", None
    return {"status": status, "reason": f"exceeded {timeout:g}s" if code is None else "",
            "exit_code": code, "stdout": out or "", "stderr": err or "",
            "duration_s": round(time.monotonic() - started, 3)}


def _relpath(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return path


def parse_output(spec: ToolSpec, stdout: str, root: Path) -> dict[str, Any] | None:
    """Turn JSON tool output into a list of issues; None if it does not parse.

    Counting is the only aggregation (S9): nothing here ranks or judges.
    """
    issues: list[dict[str, Any]] = []
    try:
        if spec.parse == "json":
            data = json.loads(stdout) if stdout.strip() else []
        elif spec.parse == "jsonlines":
            data = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        else:
            return None
    except json.JSONDecodeError:
        return None

    if spec.name == "ruff-check" and isinstance(data, list):
        for d in data:
            issues.append({"file": _relpath(d.get("filename", ""), root),
                           "line": (d.get("location") or {}).get("row"),
                           "rule": d.get("code"), "message": d.get("message")})
    elif spec.name == "eslint" and isinstance(data, list):
        for f in data:
            for m in f.get("messages", []):
                issues.append({"file": _relpath(f.get("filePath", ""), root),
                               "line": m.get("line"), "rule": m.get("ruleId"),
                               "severity": m.get("severity"), "message": m.get("message")})
    elif spec.name == "pyright" and isinstance(data, dict):
        for d in data.get("generalDiagnostics", []):
            issues.append({"file": _relpath(d.get("file", ""), root),
                           "line": ((d.get("range") or {}).get("start") or {}).get("line", -1) + 1,
                           "rule": d.get("rule"), "severity": d.get("severity"),
                           "message": d.get("message")})
    elif spec.name == "shellcheck" and isinstance(data, dict):
        for c in data.get("comments", []):
            issues.append({"file": c.get("file"), "line": c.get("line"),
                           "rule": f"SC{c.get('code')}", "severity": c.get("level"),
                           "message": c.get("message")})
    elif spec.name == "hadolint" and isinstance(data, list):
        for c in data:
            issues.append({"file": c.get("file"), "line": c.get("line"), "rule": c.get("code"),
                           "severity": c.get("level"), "message": c.get("message")})
    elif spec.name == "markdownlint" and isinstance(data, list):
        for c in data:
            names = c.get("ruleNames") or [""]
            issues.append({"file": c.get("fileName"), "line": c.get("lineNumber"),
                           "rule": names[0], "message": c.get("ruleDescription")})
    elif spec.name == "biome" and isinstance(data, dict):
        for d in data.get("diagnostics", []):
            loc = d.get("location") or {}
            issues.append({"file": (loc.get("path") or {}).get("file") if isinstance(
                               loc.get("path"), dict) else loc.get("path"),
                           "rule": d.get("category"), "severity": d.get("severity"),
                           "message": d.get("description")})
    elif spec.name == "cargo-clippy" and isinstance(data, list):
        for d in data:
            if not isinstance(d, dict) or d.get("reason") != "compiler-message":
                continue
            msg = d.get("message") or {}
            spans = [s for s in msg.get("spans", []) if s.get("is_primary")]
            issues.append({"file": spans[0].get("file_name") if spans else None,
                           "line": spans[0].get("line_start") if spans else None,
                           "rule": (msg.get("code") or {}).get("code"),
                           "severity": msg.get("level"), "message": msg.get("message")})
    else:
        return None
    return {"issue_count": len(issues), "issues": issues[:ISSUE_LIMIT],
            "issues_truncated": len(issues) > ISSUE_LIMIT}


_TEXT_COUNTERS: dict[str, re.Pattern[str]] = {
    "ruff-format": re.compile(r"^Would reformat", re.M),
    "black": re.compile(r"^would reformat", re.M),
    "prettier": re.compile(r"^\[warn\] (?!Code style issues)", re.M),
    "mypy": re.compile(r"^[^:\n]+:\d+: error:", re.M),
    "tsc": re.compile(r"^[^(\n]+\(\d+,\d+\): error TS\d+", re.M),
    "golangci-lint": re.compile(r"^[^:\n]+\.go:\d+:\d+: ", re.M),
    "python-compile": re.compile(r"^\s*File \"[^\"]+\", line \d+", re.M),
}


def _empty_result(spec: ToolSpec, trigger: str | None, status: str, reason: str,
                  argv: list[str] | None = None) -> dict[str, Any]:
    return {"name": spec.name, "category": spec.category, "trigger": trigger,
            "status": status, "reason": reason, "argv": argv, "scope": None,
            "files": [], "exit_code": None, "duration_s": None, "output": None}


def run_tool(spec: ToolSpec, root: Path, changed: list[str] | None,
             exec_enabled: bool, timeout: float, exec_block: str = "") -> dict[str, Any] | None:
    """Detect, scope and (maybe) run one tool. None means: not applicable here."""
    trigger = spec.trigger(root)
    if trigger is None:
        return None
    if not exec_enabled:
        return _empty_result(spec, trigger, "skipped", "--no-exec: detection only")
    if exec_block:
        return _empty_result(spec, trigger, "skipped", exec_block)

    binary = _resolve_binary(spec, root)
    if binary is None:
        where = "PATH or node_modules/.bin" if spec.node_local else "PATH"
        return _empty_result(spec, trigger, "skipped", f"{spec.binary} not found on {where}")

    files: list[str] | None
    if changed is not None:
        relevant = [p for p in changed if _matches(spec, p) and (root / p).is_file()]
        if not relevant:
            what = ", ".join(spec.extensions) or "matching"
            return _empty_result(spec, trigger, "skipped",
                                 f"no changed files match ({what})")
        files = relevant if spec.file_scoped else None
        run_scope = "changed_files" if spec.file_scoped else "project (tool cannot be file-scoped)"
    elif spec.needs_files:
        files = _walk(root, spec.extensions, spec.name_filter)
        run_scope = "repo_files"
        if len(files) >= REPO_FILE_LIMIT:
            run_scope += f" (first {REPO_FILE_LIMIT})"
    else:
        files, run_scope = None, "repo"

    argv = [binary, *spec.build(files)]
    env = dict(os.environ, NO_COLOR="1", FORCE_COLOR="0", CLICOLOR="0")
    with tempfile.TemporaryDirectory(prefix="review-collector-") as cache:
        env["PYTHONPYCACHEPREFIX"] = cache   # py_compile must not litter the repo
        proc = run_command(argv, root, timeout, env)

    result = _empty_result(spec, trigger, proc["status"], proc["reason"], argv)
    result.update(scope=run_scope, files=files or [], exit_code=proc["exit_code"],
                  duration_s=proc["duration_s"])
    if proc["status"] == "skipped":
        return result
    stdout, out_trunc = _truncate(proc["stdout"])
    stderr, err_trunc = _truncate(proc["stderr"], OUTPUT_CHAR_LIMIT // 4)
    output: dict[str, Any] = {"stdout": stdout, "stderr": stderr,
                              "truncated": out_trunc or err_trunc, "format": "text"}
    parsed = parse_output(spec, proc["stdout"], root) if proc["status"] == "ran" else None
    if parsed is not None:
        output.update(format="json", **parsed)
        output["stdout"] = ""   # the parsed issues carry the content
    elif spec.name in _TEXT_COUNTERS and proc["status"] == "ran":
        output["issue_count"] = len(_TEXT_COUNTERS[spec.name].findall(
            proc["stdout"] + "\n" + proc["stderr"]))
    result["output"] = output
    return result


# --- evidence collection -------------------------------------------------------

class CollectionError(RuntimeError):
    pass


class ReviewCollector:
    """Collects repository and diff facts and tool runs, without judgement."""

    def __init__(self, target_path: Path | str = "."):
        self.target_path = Path(target_path).resolve()
        if not self.target_path.exists():
            raise FileNotFoundError(f"Target path does not exist: {self.target_path}")

    def is_git_repo(self) -> bool:
        try:
            res = _git(["rev-parse", "--is-inside-work-tree"], self.target_path)
        except OSError:
            return False
        return res.returncode == 0 and res.stdout.strip() == "true"

    # -- diff --------------------------------------------------------------

    def collect_diff(self, base_ref: str | None = None,
                     staged_only: bool = False) -> dict[str, Any]:
        """Diff facts for the working tree vs HEAD, the index, or a base ref."""
        if not self.is_git_repo():
            raise CollectionError(f"{self.target_path} is not inside a git repository")

        if staged_only:
            ref_args, effective = ["--cached"], "--cached (staged)"
        elif base_ref:
            mb = _git(["merge-base", base_ref, "HEAD"], self.target_path)
            if mb.returncode == 0 and mb.stdout.strip():
                ref_args, effective = [mb.stdout.strip()], f"merge-base({base_ref}, HEAD)"
            else:
                ref_args, effective = [base_ref], base_ref
        elif _git(["rev-parse", "--verify", "HEAD"], self.target_path).returncode == 0:
            ref_args, effective = ["HEAD"], "HEAD"
        else:
            ref_args, effective = ["--cached"], "--cached (initial commit)"

        numstat = _git(["diff", "--relative", *ref_args, "--numstat", "-z"], self.target_path)
        names = _git(["diff", "--relative", *ref_args, "--name-status", "-z"], self.target_path)
        for res, what in ((numstat, "--numstat"), (names, "--name-status")):
            if res.returncode != 0:
                raise CollectionError(f"git diff {what} failed: {res.stderr.strip()}")

        status_map: dict[str, str] = {}
        tokens = names.stdout.split("\0")
        i = 0
        while i < len(tokens) - 1:
            code = tokens[i]
            if not code:
                i += 1
                continue
            if code[0] in "RC":
                status_map[tokens[i + 2]] = code[0]
                i += 3
            else:
                status_map[tokens[i + 1]] = code[0]
                i += 2

        stats: list[dict[str, Any]] = []
        tokens = numstat.stdout.split("\0")
        i = 0
        while i < len(tokens):
            rec = tokens[i]
            if not rec:
                i += 1
                continue
            parts = rec.split("\t")
            if len(parts) == 3 and parts[2] == "":   # rename: paths follow
                path = tokens[i + 2] if i + 2 < len(tokens) else ""
                i += 3
            else:
                path = parts[2] if len(parts) > 2 else ""
                i += 1
            binary = parts[0] == "-" and parts[1] == "-"
            stats.append({"path": path, "status": status_map.get(path, "M"),
                          "insertions": 0 if binary else int(parts[0]),
                          "deletions": 0 if binary else int(parts[1]), "binary": binary})
        if not staged_only:
            stats.extend(self._untracked())
        return self._diff_summary(effective, stats)

    def _untracked(self) -> list[dict[str, Any]]:
        """New files `git diff` cannot see: untracked and not ignored."""
        res = _git(["ls-files", "--others", "--exclude-standard", "-z"], self.target_path)
        out: list[dict[str, Any]] = []
        for path in filter(None, res.stdout.split("\0") if res.returncode == 0 else []):
            try:
                data = (self.target_path / path).read_bytes()
            except OSError:
                continue
            binary = b"\0" in data[:8192]
            out.append({"path": path, "status": "?", "insertions": 0 if binary else
                        len(data.splitlines()), "deletions": 0, "binary": binary,
                        "untracked": True})
        return out

    @staticmethod
    def _diff_summary(effective: str, stats: list[dict[str, Any]]) -> dict[str, Any]:
        ins = sum(s["insertions"] for s in stats)
        dels = sum(s["deletions"] for s in stats)
        return {
            "base_ref": effective,
            "files_changed_count": len(stats),
            "modified_files": [s["path"] for s in stats],
            "insertions": ins,
            "deletions": dels,
            "total_lines_changed": ins + dels,
            "diff_exceeds_500_lines": ins + dels > 500,
            "is_large_diff": ins + dels > 500,
            "file_stats": stats,
        }

    # -- pull request -----------------------------------------------------

    def collect_pr(self, number: int, timeout: float) -> dict[str, Any]:
        """PR metadata and per-file diff stats via `gh pr view --json`."""
        gh = shutil.which("gh")
        if gh is None:
            raise CollectionError("--pr needs the GitHub CLI (gh) on PATH")
        res = run_command([gh, "pr", "view", str(number), "--json", PR_FIELDS],
                          self.target_path, timeout)
        if res["status"] != "ran" or res["exit_code"] != 0:
            raise CollectionError(f"gh pr view {number} failed: "
                                  f"{(res['stderr'] or res['reason']).strip()}")
        try:
            meta = json.loads(res["stdout"])
        except json.JSONDecodeError as exc:
            raise CollectionError(f"gh pr view returned non-JSON: {exc}") from exc

        stats = [{"path": f.get("path", ""), "status": f.get("changeType", "M")[:1] or "M",
                  "insertions": int(f.get("additions", 0)), "deletions": int(f.get("deletions", 0)),
                  "binary": False} for f in meta.get("files") or []]
        body, body_trunc = _truncate(meta.get("body") or "", PR_BODY_LIMIT)
        head = _git(["rev-parse", "HEAD"], self.target_path) if self.is_git_repo() else None
        local_head = head.stdout.strip() if head is not None and head.returncode == 0 else None
        pr = {
            "number": meta.get("number", number),
            "url": meta.get("url"),
            "title": meta.get("title"),
            "author": (meta.get("author") or {}).get("login"),
            "state": meta.get("state"),
            "is_draft": meta.get("isDraft"),
            "base_ref": meta.get("baseRefName"),
            "head_ref": meta.get("headRefName"),
            "head_sha": meta.get("headRefOid"),
            "local_head_sha": local_head,
            "local_head_matches_pr": bool(local_head) and local_head == meta.get("headRefOid"),
            "labels": [lbl.get("name") for lbl in meta.get("labels") or []],
            "review_decision": meta.get("reviewDecision"),
            "body": body,
            "body_truncated": body_trunc,
            "body_is_untrusted_input": True,
        }
        return {"pr": pr, "diff": self._diff_summary(f"PR #{number} ({pr['base_ref']})", stats)}

    def collect_pr_checks(self, number: int, timeout: float) -> dict[str, Any]:
        """`gh pr checks` as a recorded tool run (exit 8 = pending, 1 = failing)."""
        gh = shutil.which("gh")
        base = {"name": "gh-pr-checks", "category": "ci", "trigger": f"--pr {number}",
                "scope": "pr", "files": []}
        if gh is None:
            return {**base, "status": "skipped", "reason": "gh not found on PATH", "argv": None,
                    "exit_code": None, "duration_s": None, "output": None}
        argv = [gh, "pr", "checks", str(number), "--json", PR_CHECK_FIELDS]
        res = run_command(argv, self.target_path, timeout)
        output: dict[str, Any] | None = None
        if res["status"] != "skipped":
            stderr, trunc = _truncate(res["stderr"], OUTPUT_CHAR_LIMIT // 4)
            output = {"format": "text", "stdout": "", "stderr": stderr, "truncated": trunc}
            try:
                checks = json.loads(res["stdout"]) if res["stdout"].strip() else []
                buckets: dict[str, int] = {}
                for c in checks:
                    buckets[c.get("bucket", "unknown")] = buckets.get(c.get("bucket", "unknown"), 0) + 1
                output.update(format="json", checks=checks[:ISSUE_LIMIT], by_bucket=buckets,
                              issue_count=buckets.get("fail", 0))
            except (json.JSONDecodeError, AttributeError):
                output["stdout"], output["truncated"] = _truncate(res["stdout"])
        return {**base, "status": res["status"], "reason": res["reason"], "argv": argv,
                "exit_code": res["exit_code"], "duration_s": res["duration_s"], "output": output}

    # -- repo facts -------------------------------------------------------

    def collect_manifests(self) -> list[dict[str, str]]:
        manifests: list[dict[str, str]] = []
        for root, dirs, files in os.walk(self.target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in files:
                if fname in MANIFEST_MAP:
                    rel = (Path(root) / fname).relative_to(self.target_path).as_posix()
                    manifests.append({"name": fname, "path": rel,
                                      "ecosystem": MANIFEST_MAP[fname]})
        manifests.sort(key=lambda m: m["path"])
        return manifests

    def collect_static_tools(self) -> list[dict[str, str]]:
        """Detected tool configs (detection only; see collect_tool_runs for execution)."""
        root = self.target_path
        tools: dict[str, dict[str, str]] = {}

        def add(name: str, category: str, config: str | None) -> None:
            if config and name not in tools:
                tools[name] = {"name": name, "category": category, "config_file": config}

        add("eslint", "linter", _eslint_trigger(root))
        add("prettier", "formatter", _prettier_trigger(root))
        add("ruff", "linter_formatter", _ruff_trigger(root))
        add("black", "formatter",
            "pyproject.toml" if _pyproject_has(root, "tool.black") else None)
        add("flake8", "linter", _first_glob(root, (".flake8",)))
        add("rustfmt", "formatter", _first_glob(root, ("rustfmt.toml", ".rustfmt.toml")))
        add("clippy", "linter", _first_glob(root, ("clippy.toml", ".clippy.toml")))
        add("biome", "linter_formatter", _first_glob(root, ("biome.json", "biome.jsonc")))
        add("golangci-lint", "linter", _first_glob(root, (".golangci.*",)))
        add("markdownlint", "linter", _first_glob(root, (".markdownlint*",)))
        add("editorconfig", "convention", _first_glob(root, (".editorconfig",)))
        add("typescript", "typechecker", _first_glob(root, ("tsconfig.json",)))
        add("mypy", "typechecker", _mypy_trigger(root))
        add("pyright", "typechecker", _pyright_trigger(root))
        add("vitest", "test_runner", _first_glob(root, ("vitest.config.*",)))
        add("jest", "test_runner", _first_glob(root, ("jest.config.*",)))
        pytest_cfg = _first_glob(root, ("pytest.ini", "conftest.py"))
        if not pytest_cfg and (_pyproject_has(root, "tool.pytest")):
            pytest_cfg = "pyproject.toml"
        add("pytest", "test_runner", pytest_cfg)
        add("cargo-test", "test_runner", _first_glob(root, ("Cargo.toml",)))
        add("go-test", "test_runner", _first_glob(root, ("go.mod",)))
        wf = root / ".github" / "workflows"
        if wf.is_dir() and (list(wf.glob("*.yml")) + list(wf.glob("*.yaml"))):
            add("github-actions", "ci_cd", ".github/workflows")
        add("gitlab-ci", "ci_cd", _first_glob(root, (".gitlab-ci.yml",)))
        add("contributing", "convention", _first_glob(root, ("CONTRIBUTING.md", ".github/CONTRIBUTING.md")))
        add("agents-md", "convention", _first_glob(root, ("AGENTS.md", "CLAUDE.md")))
        return sorted(tools.values(), key=lambda t: (t["category"], t["name"]))

    def collect_topology(self) -> dict[str, Any]:
        extensions: dict[str, int] = {}
        total = 0
        top = sorted(e.name for e in self.target_path.iterdir()
                     if e.is_dir() and e.name not in IGNORE_DIRS and not e.name.startswith("."))
        for _root, dirs, files in os.walk(self.target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in files:
                total += 1
                ext = Path(fname).suffix.lower() or "(none)"
                extensions[ext] = extensions.get(ext, 0) + 1
        return {"total_files": total,
                "extensions": dict(sorted(extensions.items(), key=lambda kv: (-kv[1], kv[0]))),
                "top_directories": top}

    def collect_tool_runs(self, changed: list[str] | None, exec_enabled: bool = True,
                          timeout: float = DEFAULT_TIMEOUT,
                          exec_block: str = "") -> list[dict[str, Any]]:
        """Run every applicable tool. changed=None means whole-repo scope."""
        runs = []
        for spec in TOOLS:
            res = run_tool(spec, self.target_path, changed, exec_enabled, timeout,
                           exec_block)
            if res is not None:
                runs.append(res)
        return runs

    # -- everything -------------------------------------------------------

    def collect_all(self, include_diff: bool = True, include_repo: bool = True,
                    base_ref: str | None = None, staged_only: bool = False,
                    pr_number: int | None = None, exec_enabled: bool = True,
                    timeout: float = DEFAULT_TIMEOUT, tool_scope: str | None = None,
                    ) -> dict[str, Any]:
        """Assemble evidence. tool_scope: 'diff', 'repo', or None (no tool runs)."""
        report: dict[str, Any] = {
            "collector_version": COLLECTOR_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_path": str(self.target_path),
            "is_git_repo": self.is_git_repo(),
            "mode": "pr" if pr_number is not None else ("diff" if include_diff else "repo"),
            "uninspected": UNINSPECTED_SURFACE,
        }
        not_inspected: list[dict[str, str]] = []

        exec_block = ""
        if pr_number is not None:
            pr_data = self.collect_pr(pr_number, timeout)
            report["pr"] = pr_data["pr"]
            report["diff"] = pr_data["diff"]
            if not pr_data["pr"]["local_head_matches_pr"]:
                exec_block = ("local HEAD is not the PR head; check it out "
                              f"(gh pr checkout {pr_number}) to run tools on the PR's code")
        elif include_diff:
            if self.is_git_repo():
                report["diff"] = self.collect_diff(base_ref=base_ref, staged_only=staged_only)
            else:
                report["diff"] = None
                not_inspected.append({"what": "diff", "reason": "not a git repository"})

        diff = report.get("diff")
        if "diff" in report:
            report["total_lines_changed"] = diff["total_lines_changed"] if diff else 0
            report["diff_exceeds_500_lines"] = diff["diff_exceeds_500_lines"] if diff else False
            report["is_large_diff"] = report["diff_exceeds_500_lines"]
            report["modified_files"] = diff["modified_files"] if diff else []

        if include_repo:
            manifests = self.collect_manifests()
            tools = self.collect_static_tools()
            report["repo"] = {"manifests": manifests, "tools": tools,
                              "topology": self.collect_topology()}
            report["manifests"] = manifests
            report["tools"] = tools
            report["detected_linters"] = [t["name"] for t in tools if "linter" in t["category"]]
            report["detected_test_runners"] = [t["name"] for t in tools
                                               if t["category"] == "test_runner"]

        if tool_scope is not None:
            changed = None if tool_scope == "repo" else list(report.get("modified_files", []))
            runs = self.collect_tool_runs(changed, exec_enabled, timeout, exec_block)
            if pr_number is not None:
                runs.append(self.collect_pr_checks(pr_number, timeout))
            report["tool_scope"] = tool_scope
            report["tool_runs"] = runs
            for r in runs:
                if r["status"] != "ran":
                    not_inspected.append({"what": r["name"],
                                          "reason": f"{r['status']}: {r['reason']}"})
            if not runs:
                not_inspected.append({"what": "linters/type checkers",
                                      "reason": "no supported tool config or ecosystem found"})
        report["not_inspected"] = not_inspected
        return report


def collect_evidence(target_path: Path | str = ".", **kwargs: Any) -> dict[str, Any]:
    """Programmatic entry point; kwargs as for ReviewCollector.collect_all."""
    return ReviewCollector(target_path=target_path).collect_all(**kwargs)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review_collector.py",
        description="Collect review evidence: diff facts, repo facts, and the results of "
                    "running the repo's own linters, formatters and type checkers. "
                    "Facts only: no scores or verdicts. A tool that did not run is listed "
                    "under not_inspected.",
        epilog="Default (no mode flag): diff of the working tree vs HEAD plus repo facts, "
               "with tools scoped to the changed files.",
    )
    mode = parser.add_argument_group("scope")
    mode.add_argument("--diff", action="store_true",
                      help="diff facts only (working tree vs HEAD unless --staged/--base); "
                           "tools scoped to changed files")
    mode.add_argument("--repo", action="store_true",
                      help="whole-repository facts (manifests, tool configs, topology); "
                           "tools run on the whole repo unless --diff/--pr/--staged/--base "
                           "is also given")
    mode.add_argument("--pr", type=int, metavar="N",
                      help="pull request N via `gh pr view --json` and `gh pr checks`; tools "
                           "run only if the local HEAD is the PR head")
    mode.add_argument("--base", metavar="REF",
                      help="diff against merge-base(REF, HEAD), e.g. origin/main")
    mode.add_argument("--staged", action="store_true", help="diff the index (git diff --cached)")
    parser.add_argument("--path", default=".",
                        help="repository directory to inspect (default: current directory)")
    parser.add_argument("--no-exec", action="store_true",
                        help="detect tools but run none of them (use on untrusted code)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS",
                        help=f"per-tool timeout (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--out", metavar="FILE", help="write the evidence JSON to FILE")
    parser.add_argument("--json", action="store_true",
                        help="print the evidence JSON to stdout (default when --out is absent)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.staged and (args.base or args.pr is not None):
        print("review_collector: --staged cannot be combined with --base or --pr",
              file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("review_collector: --timeout must be positive", file=sys.stderr)
        return 2

    wants_diff = args.diff or args.staged or bool(args.base)
    if args.pr is not None:
        include_diff, include_repo, scope = False, args.repo, "diff"
    elif wants_diff:
        include_diff, include_repo, scope = True, args.repo, "diff"
    elif args.repo:
        include_diff, include_repo, scope = False, True, "repo"
    else:
        include_diff, include_repo, scope = True, True, "diff"

    try:
        collector = ReviewCollector(target_path=args.path)
        if not collector.is_git_repo():
            if wants_diff:
                print(f"review_collector: {args.path} is not inside a git repository",
                      file=sys.stderr)
                return 1
            if args.pr is None:
                scope = "repo"   # default mode outside git: nothing to scope to
        evidence = collector.collect_all(
            include_diff=include_diff, include_repo=include_repo, base_ref=args.base,
            staged_only=args.staged, pr_number=args.pr, exec_enabled=not args.no_exec,
            timeout=args.timeout, tool_scope=scope)
    except (CollectionError, FileNotFoundError, OSError) as exc:
        print(f"review_collector: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(evidence, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"review_collector: evidence written to {out}", file=sys.stderr)
    if args.json or not args.out:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
