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

"""Run the security scanners that are installed and relevant; emit leads.

A scanner hit is a *lead*, not a finding. This script collects and normalises
leads; it does not decide which are real (S9). The model triages each lead
with the six-element test and records confirmed / needs_validation / rejected.

Modes:
  (default)      scan the working tree as it is now
  --diff BASE    scan what changed since BASE (a commit-ish). semgrep uses
                 --baseline-commit; gitleaks scans the commits BASE..HEAD plus a
                 copy of changed-but-uncommitted files; the other tools run only
                 when files they understand changed, and their file-located
                 leads are filtered to changed files
  --audit        whole tree, and gitleaks scans the full git history

Tools, each run only when on PATH and relevant to the repository:
  semgrep        p/default, p/owasp-top-ten, p/secrets + language packs
  gitleaks       git history / commit range / directory; --redact always
  osv-scanner    scan source -r, when a lockfile or manifest exists
  trivy          fs --scanners vuln,misconfig,secret, when IaC, Dockerfiles or
                 Kubernetes manifests exist (the misconfig scanner is what
                 `trivy config` runs, so one pass covers both)
  actionlint     when .github/workflows has workflow files
  zizmor         when .github/workflows has workflow files (offline audits)
  npm-audit      npm audit --json --package-lock-only, root package-lock.json
  pip-audit      root requirements*.txt, --no-deps --disable-pip (never
                 installs anything, so unpinned files fail and are reported)
  govulncheck    root go.mod
  cargo-audit    root Cargo.lock

The native audits send dependency names and versions to their registry or
database (that is how they work); osv-scanner does the same with OSV.dev.

Secrets (S8): gitleaks runs with --redact, its report lives in a temporary
directory, and every normaliser copies only whitelisted fields (never
gitleaks' Secret/Match, trivy's Match/Code or semgrep's lines). Messages are
passed through a token redactor at capture.

What this does not check (V5): reachability, exploitability, business logic,
authorisation design, anything no installed tool covers. A relevant tool that
is missing, times out or errors is listed in not_inspected and makes the run
partial (exit 2); it never counts as clean. A relevant tool left out with
--tools is listed in not_inspected too, but does not force exit 2.

Output: one JSON object on stdout ("leads" plus per-tool status).
Diagnostics on stderr.

Exit codes:
  0   every relevant selected tool ran and reported no leads
  1   leads present and every relevant selected tool ran
  2   partial: a relevant selected tool was missing, timed out or failed
      (leads found by the others are still listed)
  64  usage error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

EXIT_CLEAN = 0
EXIT_LEADS = 1
EXIT_PARTIAL = 2
EXIT_USAGE = 64

LEADS_SCHEMA = "security-review/leads@1"
DEFAULT_TIMEOUT_S = 600
MAX_WALK_FILES = 50_000
MAX_MESSAGE = 500

SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "venv", "__pycache__",
             "dist", "build", "target", ".tox", ".mypy_cache", ".pytest_cache",
             ".terraform", ".next", ".gradle"}

# extension -> semgrep language pack. Packs verified to exist in the registry.
LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".go": "golang", ".java": "java", ".kt": "kotlin",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".rs": "rust",
    ".scala": "scala", ".swift": "swift", ".c": "c", ".h": "c",
    ".tf": "terraform",
}
SEMGREP_BASE_CONFIGS = ("p/default", "p/owasp-top-ten", "p/secrets")
SEMGREP_PACKS = {"python": "p/python", "javascript": "p/javascript",
                 "typescript": "p/typescript", "golang": "p/golang",
                 "java": "p/java", "kotlin": "p/kotlin", "ruby": "p/ruby",
                 "php": "p/php", "csharp": "p/csharp", "rust": "p/rust",
                 "scala": "p/scala", "swift": "p/swift", "c": "p/c",
                 "terraform": "p/terraform", "dockerfile": "p/dockerfile",
                 "kubernetes": "p/kubernetes"}

LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
             "pnpm-lock.yaml", "bun.lock", "requirements.txt", "poetry.lock",
             "Pipfile.lock", "uv.lock", "pdm.lock", "Cargo.lock", "go.mod",
             "Gemfile.lock", "composer.lock", "pom.xml", "gradle.lockfile",
             "packages.lock.json", "mix.lock", "pubspec.lock"}

TOOL_ORDER = ("semgrep", "gitleaks", "osv-scanner", "trivy", "actionlint",
              "zizmor", "npm-audit", "pip-audit", "govulncheck", "cargo-audit")


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- redaction

_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)",
               re.DOTALL),
    re.compile(r"\b(gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\b(sk|rk|pk)_(live|test)_[A-Za-z0-9]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),          # credentials in a URL
]
# A long token mixing letters and digits: almost never prose, often a secret.
_GENERIC_TOKEN = re.compile(r"[A-Za-z0-9+=_-]{32,}")


def redact(text: object) -> str:
    """Mask secret-shaped substrings. Applied to every captured message."""
    s = "" if text is None else str(text)
    for pat in _SECRET_PATTERNS:
        s = pat.sub(lambda m: "://[REDACTED]@" if m.group(0).startswith("://")
                    else "[REDACTED]", s)
    s = _GENERIC_TOKEN.sub(
        lambda m: "[REDACTED]" if (re.search(r"\d", m.group(0))
                                   and re.search(r"[A-Za-z]", m.group(0)))
        else m.group(0), s)
    return s[:MAX_MESSAGE]


# ---------------------------------------------------------------- leads

_CWE = re.compile(r"CWE-(\d+)")


def cwes(value: object) -> list[str]:
    """Collect CWE ids from a string, a list of strings, or nested values."""
    found: list[str] = []
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, (list, tuple)):
            stack.extend(reversed(v))
        elif isinstance(v, (str, int)):
            text = f"CWE-{v}" if isinstance(v, int) else v
            for m in _CWE.finditer(text):
                cid = f"CWE-{m.group(1)}"
                if cid not in found:
                    found.append(cid)
    return found


def rel(path: object, root: Path) -> str:
    """Repo-relative POSIX path; absolute paths under root are shortened."""
    if not isinstance(path, str) or not path:
        return ""
    p = path.replace("\\", "/")
    for base in (str(root), str(root.resolve())):
        prefix = base.replace("\\", "/").rstrip("/") + "/"
        if p.startswith(prefix):
            return p[len(prefix):]
    if os.path.isabs(p):   # e.g. /tmp vs /private/tmp on macOS
        try:
            return Path(os.path.realpath(p)).relative_to(root.resolve()).as_posix()
        except ValueError:
            return p
    return p[2:] if p.startswith("./") else p


def lead(tool: str, rule_id: object, file: str, line: object, message: object,
         severity: object, cwe: list[str] | None = None,
         aliases: list[str] | None = None) -> dict[str, Any]:
    return {
        "tool": tool,
        "rule_id": str(rule_id or "unknown"),
        "file": file,
        "line": line if isinstance(line, int) and not isinstance(line, bool)
        and line > 0 else None,
        "message": redact(message),
        "severity": str(severity) if severity not in (None, "") else None,
        "cwe": cwe or [],
        "aliases": aliases or [],
    }


# ---------------------------------------------------------------- normalisers
# Each takes the tool's parsed output and the repo root, and returns leads.
# They read whitelisted fields only: that is where redaction happens (S8).


def norm_semgrep(data: Any, root: Path) -> list[dict]:
    out = []
    for r in (data or {}).get("results") or []:
        extra = r.get("extra") or {}
        out.append(lead("semgrep", r.get("check_id"), rel(r.get("path"), root),
                        (r.get("start") or {}).get("line"), extra.get("message"),
                        extra.get("severity"),
                        cwes((extra.get("metadata") or {}).get("cwe"))))
    return out


def norm_gitleaks(data: Any, root: Path) -> list[dict]:
    out = []
    for r in data or []:
        if not isinstance(r, dict):
            continue
        msg = r.get("Description") or r.get("RuleID")
        commit = r.get("Commit") or ""
        if commit:
            msg = f"{msg} (commit {str(commit)[:12]})"
        out.append(lead("gitleaks", r.get("RuleID"), rel(r.get("File"), root),
                        r.get("StartLine"), msg, None, ["CWE-798"]))
    return out


def norm_osv(data: Any, root: Path) -> list[dict]:
    out = []
    for res in (data or {}).get("results") or []:
        src = rel((res.get("source") or {}).get("path"), root)
        for pkg in res.get("packages") or []:
            p = pkg.get("package") or {}
            vulns = {v.get("id"): v for v in pkg.get("vulnerabilities") or []}
            groups = pkg.get("groups") or [{"ids": [i]} for i in vulns]
            for g in groups:
                ids = g.get("ids") or []
                if not ids:
                    continue
                v = next((vulns[i] for i in ids if i in vulns), {})
                db = v.get("database_specific") or {}
                aliases = sorted(set(g.get("aliases") or v.get("aliases") or []) - {ids[0]})
                summary = v.get("summary") or ""
                msg = f"{p.get('ecosystem', '?')} {p.get('name', '?')}@{p.get('version', '?')}"
                msg += f": {summary}" if summary else ""
                out.append(lead("osv-scanner", ids[0], src, None, msg,
                                g.get("max_severity") or db.get("severity"),
                                cwes(db.get("cwe_ids")), aliases))
    return out


def norm_trivy(data: Any, root: Path) -> list[dict]:
    out = []
    for res in (data or {}).get("Results") or []:
        target = rel(res.get("Target"), root)
        for v in res.get("Vulnerabilities") or []:
            msg = f"{v.get('PkgName')}@{v.get('InstalledVersion')}: {v.get('Title') or ''}"
            if v.get("FixedVersion"):
                msg += f" (fixed in {v['FixedVersion']})"
            out.append(lead("trivy", v.get("VulnerabilityID"), target, None, msg,
                            v.get("Severity"), cwes(v.get("CweIDs"))))
        for m in res.get("Misconfigurations") or []:
            if m.get("Status", "FAIL") != "FAIL":
                continue
            out.append(lead("trivy", m.get("ID") or m.get("AVDID"), target,
                            (m.get("CauseMetadata") or {}).get("StartLine"),
                            m.get("Message") or m.get("Title"), m.get("Severity")))
        for s in res.get("Secrets") or []:
            out.append(lead("trivy", s.get("RuleID"), target, s.get("StartLine"),
                            s.get("Title"), s.get("Severity"), ["CWE-798"]))
    return out


def norm_actionlint(data: Any, root: Path) -> list[dict]:
    return [lead("actionlint", f"actionlint:{e.get('kind', 'error')}",
                 rel(e.get("filepath"), root), e.get("line"), e.get("message"),
                 "error")
            for e in data or [] if isinstance(e, dict)]


def norm_zizmor(data: Any, root: Path) -> list[dict]:
    out = []
    for f in data or []:
        if not isinstance(f, dict) or f.get("ignored"):
            continue
        locs = f.get("locations") or [{}]
        primary = next((loc for loc in locs
                        if (loc.get("symbolic") or {}).get("kind") == "Primary"), locs[0])
        key = ((primary.get("symbolic") or {}).get("key") or {}).get("Local") or {}
        path = key.get("verbatim_path") or key.get("given_path") or ""
        row = (((primary.get("concrete") or {}).get("location") or {})
               .get("start_point") or {}).get("row")
        det = f.get("determinations") or {}
        out.append(lead("zizmor", f"zizmor:{f.get('ident')}", rel(path, root),
                        row + 1 if isinstance(row, int) else None,
                        f"{f.get('desc')} (confidence {det.get('confidence')})",
                        det.get("severity")))
    return out


def norm_npm_audit(data: Any, root: Path) -> list[dict]:
    out, seen = [], set()
    for name, v in ((data or {}).get("vulnerabilities") or {}).items():
        for via in v.get("via") or []:
            if not isinstance(via, dict):
                continue  # a string means "vulnerable through another package"
            url = via.get("url") or ""
            ghsa = url.rsplit("/", 1)[-1] if "GHSA-" in url else ""
            rule = ghsa or f"npm-advisory-{via.get('source')}"
            if (rule, name) in seen:
                continue
            seen.add((rule, name))
            out.append(lead("npm-audit", rule, "package-lock.json", None,
                            f"{via.get('name', name)} {via.get('range', '')}: "
                            f"{via.get('title', '')}", via.get("severity"),
                            cwes(via.get("cwe"))))
    return out


def norm_pip_audit(data: Any, root: Path, source: str = "requirements.txt") -> list[dict]:
    out = []
    deps = data.get("dependencies") if isinstance(data, dict) else data
    for d in deps or []:
        for v in d.get("vulns") or []:
            fixes = ", ".join(v.get("fix_versions") or [])
            msg = f"PyPI {d.get('name')}@{d.get('version')}"
            msg += f" (fixed in {fixes})" if fixes else ""
            out.append(lead("pip-audit", v.get("id"), source, None, msg, None,
                            [], list(v.get("aliases") or [])))
    return out


def _json_stream(text: str) -> list[Any]:
    """govulncheck -json prints a stream of JSON objects, not one document."""
    dec, i, objs = json.JSONDecoder(), 0, []
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        obj, i = dec.raw_decode(text, i)
        objs.append(obj)
    return objs


def norm_govulncheck(data: Any, root: Path) -> list[dict]:
    objs = data if isinstance(data, list) else [data]
    osv_meta = {}
    for o in objs:
        if isinstance(o, dict) and isinstance(o.get("osv"), dict):
            osv_meta[o["osv"].get("id")] = o["osv"]
    out, seen = [], set()
    for o in objs:
        f = o.get("finding") if isinstance(o, dict) else None
        if not isinstance(f, dict):
            continue
        trace = f.get("trace") or [{}]
        # A finding with a function in its trace is a reachable call; module-
        # or package-level findings are imports only. Keep only the deepest.
        frame = trace[0]
        pos = frame.get("position") or {}
        level = "called" if frame.get("function") else (
            "imported" if frame.get("package") else "required")
        key = (f.get("osv"), pos.get("filename"), pos.get("line"), level)
        if key in seen:
            continue
        seen.add(key)
        meta = osv_meta.get(f.get("osv")) or {}
        msg = f"{frame.get('module', '?')}@{frame.get('version', '?')} ({level})"
        if meta.get("summary"):
            msg += f": {meta['summary']}"
        out.append(lead("govulncheck", f.get("osv"),
                        rel(pos.get("filename"), root) or "go.mod",
                        pos.get("line"), msg, None, [],
                        list(meta.get("aliases") or [])))
    return out


def norm_cargo_audit(data: Any, root: Path) -> list[dict]:
    out = []
    for v in ((data or {}).get("vulnerabilities") or {}).get("list") or []:
        adv, pkg = v.get("advisory") or {}, v.get("package") or {}
        out.append(lead("cargo-audit", adv.get("id"), "Cargo.lock", None,
                        f"crates.io {pkg.get('name')}@{pkg.get('version')}: "
                        f"{adv.get('title', '')}", adv.get("cvss"), [],
                        list(adv.get("aliases") or [])))
    return out


# ---------------------------------------------------------------- repo facts


@dataclass
class Repo:
    root: Path
    files: list[str]                 # repo-relative POSIX paths
    truncated: bool
    is_git: bool
    changed: set[str] | None = None  # diff mode only
    uncommitted: list[str] = field(default_factory=list)

    def has(self, pred: Callable[[str], bool]) -> bool:
        pool = self.files if self.changed is None else sorted(self.changed)
        return any(pred(f) for f in pool)

    def exists(self, pred: Callable[[str], bool]) -> bool:
        return any(pred(f) for f in self.files)


def walk(root: Path) -> tuple[list[str], bool]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            files.append(Path(dirpath, name).relative_to(root).as_posix())
            if len(files) >= MAX_WALK_FILES:
                return files, True
    return files, False


def git(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, timeout=timeout, shell=False)


def resolve_base(root: Path, base: str) -> str:
    if base.startswith("-") or not base.strip():
        raise UsageError(f"--diff needs a commit-ish, got {base!r}")
    if not shutil.which("git"):
        raise UsageError("--diff needs git on PATH")
    proc = git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if proc.returncode != 0:
        raise UsageError(f"--diff {base!r} does not name a commit in {root}")
    return proc.stdout.strip()


def changed_files(root: Path, base_sha: str) -> tuple[set[str], list[str]]:
    """Files changed since base (committed or not) and the uncommitted subset."""
    diff = git(root, "diff", "--name-only", "--diff-filter=d", base_sha)
    dirty = git(root, "diff", "--name-only", "--diff-filter=d", "HEAD")
    untracked = git(root, "ls-files", "--others", "--exclude-standard")
    for proc in (diff, dirty, untracked):
        if proc.returncode != 0:
            raise UsageError(f"git failed: {proc.stderr.strip()[:200]}")
    split = lambda p: {x for x in p.stdout.splitlines() if x}  # noqa: E731
    uncommitted = sorted(split(dirty) | split(untracked))
    return split(diff) | set(uncommitted), uncommitted


def load_repo(root: Path, base_sha: str | None) -> Repo:
    files, truncated = walk(root)
    is_git = bool(shutil.which("git")) and git(root, "rev-parse", "--git-dir").returncode == 0
    repo = Repo(root, files, truncated, is_git)
    if base_sha:
        repo.changed, repo.uncommitted = changed_files(root, base_sha)
    return repo


def languages(repo: Repo) -> list[str]:
    langs = {LANG_BY_EXT[Path(f).suffix] for f in repo.files if Path(f).suffix in LANG_BY_EXT}
    if repo.exists(_is_dockerfile):
        langs.add("dockerfile")
    if repo.exists(lambda f: _is_k8s(repo.root, f)):
        langs.add("kubernetes")
    return sorted(langs)


def _is_dockerfile(f: str) -> bool:
    name = Path(f).name.lower()
    return name == "dockerfile" or name.startswith("dockerfile.") or name.endswith(".dockerfile")


_K8S = re.compile(r"^apiVersion:\s*\S+.*^kind:\s*\S+", re.MULTILINE | re.DOTALL)


def _is_k8s(root: Path, f: str) -> bool:
    if not f.endswith((".yaml", ".yml")) or f.startswith(".github/"):
        return False
    try:
        with open(root / f, encoding="utf-8", errors="replace") as fh:
            return bool(_K8S.search(fh.read(4096)))
    except OSError:
        return False


def _is_iac(root: Path, f: str) -> bool:
    name = Path(f).name.lower()
    return (_is_dockerfile(f) or f.endswith((".tf", ".tfvars", ".bicep"))
            or name in ("chart.yaml", "docker-compose.yml", "docker-compose.yaml",
                        "compose.yml", "compose.yaml")
            or _is_k8s(root, f))


def _is_workflow(f: str) -> bool:
    return f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))


def _is_lockfile(f: str) -> bool:
    name = Path(f).name
    return name in LOCKFILES or (name.startswith("requirements") and name.endswith(".txt"))


def _is_root_requirements(f: str) -> bool:
    return "/" not in f and f.startswith("requirements") and f.endswith(".txt")


# ---------------------------------------------------------------- tool specs


@dataclass
class Invocation:
    argv: list[str]
    parse: Callable[[str], Any]
    normalise: Callable[[Any, Path], list[dict]]
    ok_codes: tuple[int, ...] = (0,)
    report: Path | None = None        # read this file instead of stdout
    path_root: Path | None = None     # where reported paths are relative to
    cwd: Path | None = None
    empty_ok_codes: tuple[int, ...] = ()   # exit codes meaning "nothing to scan"


@dataclass
class ToolSpec:
    name: str
    binary: str
    relevant: Callable[[Repo], str | None]      # None = relevant, else reason
    build: Callable[["Ctx"], list[Invocation]]
    filter_to_diff: bool = False


@dataclass
class Ctx:
    repo: Repo
    mode: str
    base_sha: str | None
    tmp: Path
    binary: str
    langs: list[str]


def _json(text: str) -> Any:
    return json.loads(text) if text.strip() else None


def _rel_root(repo: Repo, need: Callable[[str], bool], what: str) -> str | None:
    if not repo.exists(need):
        return f"not relevant: no {what}"
    if repo.changed is not None and not repo.has(need):
        return f"not relevant: no {what} changed since base"
    return None


def build_semgrep(c: Ctx) -> list[Invocation]:
    argv = [c.binary, "scan", "--json", "--metrics", "off", "--quiet",
            "--disable-version-check"]
    for cfg in (*SEMGREP_BASE_CONFIGS,
                *(SEMGREP_PACKS[l] for l in c.langs if l in SEMGREP_PACKS)):
        argv += ["--config", cfg]
    if c.base_sha:
        argv += ["--baseline-commit", c.base_sha]
    argv.append(str(c.repo.root))
    return [Invocation(argv, _json, norm_semgrep, ok_codes=(0, 1),
                       cwd=c.repo.root)]


def build_gitleaks(c: Ctx) -> list[Invocation]:
    common = ["--report-format", "json", "--redact", "--no-banner",
              "--exit-code", "0", "--log-level", "error"]
    out = []
    if c.mode == "diff":
        rep = c.tmp / "gitleaks-range.json"
        out.append(Invocation([c.binary, "git", f"--log-opts={c.base_sha}..HEAD",
                               *common, "--report-path", str(rep), str(c.repo.root)],
                              _json, norm_gitleaks, report=rep))
        if c.repo.uncommitted:
            stage = c.tmp / "uncommitted"
            for f in c.repo.uncommitted:
                src = c.repo.root / f
                if src.is_file():
                    (stage / f).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, stage / f)
            rep2 = c.tmp / "gitleaks-uncommitted.json"
            out.append(Invocation([c.binary, "dir", *common, "--report-path",
                                   str(rep2), str(stage)], _json, norm_gitleaks,
                                  report=rep2, path_root=stage))
    elif c.mode == "audit" and c.repo.is_git:
        rep = c.tmp / "gitleaks-history.json"
        out.append(Invocation([c.binary, "git", *common, "--report-path", str(rep),
                               str(c.repo.root)], _json, norm_gitleaks, report=rep))
    else:
        rep = c.tmp / "gitleaks-dir.json"
        out.append(Invocation([c.binary, "dir", *common, "--report-path", str(rep),
                               str(c.repo.root)], _json, norm_gitleaks, report=rep))
    return out


def build_osv(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "scan", "source", "-r", "--format", "json",
                        str(c.repo.root)], _json, norm_osv, ok_codes=(0, 1),
                       empty_ok_codes=(128,))]


def build_trivy(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "fs", "--scanners", "vuln,misconfig,secret",
                        "--format", "json", "--quiet", "--exit-code", "0",
                        str(c.repo.root)], _json, norm_trivy, cwd=c.repo.root)]


def build_actionlint(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "-format", "{{json .}}"], _json, norm_actionlint,
                       ok_codes=(0, 1), cwd=c.repo.root)]


def build_zizmor(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "--format", "json", "--offline",
                        ".github/workflows"], _json, norm_zizmor,
                       ok_codes=(0, 10, 11, 12, 13, 14), cwd=c.repo.root)]


def build_npm(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "audit", "--json", "--package-lock-only"],
                       _json, norm_npm_audit, ok_codes=(0, 1), cwd=c.repo.root)]


def build_pip_audit(c: Ctx) -> list[Invocation]:
    out = []
    for f in sorted(x for x in c.repo.files if _is_root_requirements(x)):
        out.append(Invocation(
            [c.binary, "-f", "json", "--progress-spinner", "off", "--no-deps",
             "--disable-pip", "-r", f],
            _json, lambda d, r, src=f: norm_pip_audit(d, r, src), ok_codes=(0, 1),
            cwd=c.repo.root))
    return out


def build_govulncheck(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "-json", "./..."], _json_stream, norm_govulncheck,
                       ok_codes=(0, 3), cwd=c.repo.root)]


def build_cargo_audit(c: Ctx) -> list[Invocation]:
    return [Invocation([c.binary, "audit", "--json"], _json, norm_cargo_audit,
                       ok_codes=(0, 1), cwd=c.repo.root)]


TOOLS: dict[str, ToolSpec] = {
    "semgrep": ToolSpec(
        "semgrep", "semgrep",
        lambda r: _rel_root(r, lambda f: Path(f).suffix in LANG_BY_EXT
                            or _is_iac(r.root, f) or _is_workflow(f),
                            "source, IaC or workflow files"),
        build_semgrep),
    "gitleaks": ToolSpec(
        "gitleaks", "gitleaks",
        lambda r: (None if r.changed is None or r.changed
                   else "not relevant: nothing changed since base"),
        build_gitleaks),
    "osv-scanner": ToolSpec(
        "osv-scanner", "osv-scanner",
        lambda r: _rel_root(r, _is_lockfile, "lockfiles or manifests"), build_osv),
    "trivy": ToolSpec(
        "trivy", "trivy",
        lambda r: _rel_root(r, lambda f: _is_iac(r.root, f),
                            "Dockerfiles, IaC or Kubernetes manifests"),
        build_trivy, filter_to_diff=True),
    "actionlint": ToolSpec(
        "actionlint", "actionlint",
        lambda r: _rel_root(r, _is_workflow, ".github/workflows files"),
        build_actionlint, filter_to_diff=True),
    "zizmor": ToolSpec(
        "zizmor", "zizmor",
        lambda r: _rel_root(r, _is_workflow, ".github/workflows files"),
        build_zizmor, filter_to_diff=True),
    "npm-audit": ToolSpec(
        "npm-audit", "npm",
        lambda r: _rel_root(r, lambda f: f in ("package-lock.json",
                                               "npm-shrinkwrap.json"),
                            "root package-lock.json"), build_npm),
    "pip-audit": ToolSpec(
        "pip-audit", "pip-audit",
        lambda r: _rel_root(r, _is_root_requirements, "root requirements*.txt"),
        build_pip_audit),
    "govulncheck": ToolSpec(
        "govulncheck", "govulncheck",
        lambda r: _rel_root(r, lambda f: f in ("go.mod", "go.sum"), "root go.mod"),
        build_govulncheck),
    "cargo-audit": ToolSpec(
        "cargo-audit", "cargo-audit",
        lambda r: _rel_root(r, lambda f: f == "Cargo.lock", "root Cargo.lock"),
        build_cargo_audit),
}


# ---------------------------------------------------------------- running


def _tail(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return redact(" | ".join(lines[-3:]))[:300]


def run_invocation(inv: Invocation, timeout: int,
                   repo_root: Path) -> tuple[str, list[dict], str, int | None]:
    """Return (status, leads, reason, exit_code). Status: ran|timed_out|error."""
    try:
        proc = subprocess.run(inv.argv, capture_output=True, text=True,
                              timeout=timeout, shell=False, cwd=inv.cwd,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "timed_out", [], f"no result within {timeout}s", None
    except OSError as exc:
        return "error", [], f"could not start: {exc.strerror or exc}", None
    if proc.returncode in inv.empty_ok_codes:
        return "ran", [], "", proc.returncode
    if proc.returncode not in inv.ok_codes:
        return "error", [], f"exit {proc.returncode}: {_tail(proc.stderr)}", proc.returncode
    try:
        if inv.report is not None:
            text = inv.report.read_text(encoding="utf-8") if inv.report.exists() else ""
            if not text.strip():
                return "error", [], "no report written", proc.returncode
        else:
            text = proc.stdout
        data = inv.parse(text)
    except (ValueError, OSError) as exc:
        return "error", [], f"unparseable output: {type(exc).__name__}", proc.returncode
    finally:
        if inv.report is not None and inv.report.exists():
            inv.report.unlink()   # the raw report never outlives the run
    try:
        leads = inv.normalise(data, inv.path_root or repo_root)
    except (AttributeError, TypeError, KeyError) as exc:
        return "error", [], f"unexpected output shape: {type(exc).__name__}", proc.returncode
    return "ran", leads, "", proc.returncode


def scan(root: Path, mode: str, base: str | None, selected: list[str] | None,
         timeout: int) -> dict[str, Any]:
    root = root.resolve()
    base_sha = resolve_base(root, base) if base else None
    repo = load_repo(root, base_sha)
    langs = languages(repo)
    report: dict[str, Any] = {
        "schema": LEADS_SCHEMA, "mode": mode, "base": base_sha,
        "languages": langs, "tools": {}, "leads": [], "not_inspected": [],
    }
    partial = False
    with tempfile.TemporaryDirectory(prefix="security-review-") as tmpd:
        for name in TOOL_ORDER:
            spec = TOOLS[name]
            entry: dict[str, Any] = {"status": "skipped", "reason": "", "leads": 0}
            report["tools"][name] = entry
            why_not = spec.relevant(repo)
            if why_not:
                entry["reason"] = why_not
                continue
            if selected is not None and name not in selected:
                entry["reason"] = "not selected via --tools"
                report["not_inspected"].append({"what": name, "reason":
                                                "relevant but not selected via --tools"})
                continue
            binary = shutil.which(spec.binary)
            if not binary:
                entry["reason"] = f"not installed ({spec.binary} not on PATH)"
                report["not_inspected"].append({"what": name, "reason": entry["reason"]})
                partial = True
                continue
            ctx = Ctx(repo, mode, base_sha, Path(tmpd), binary, langs)
            tool_leads, problems = [], []
            entry["status"] = "ran"
            for inv in spec.build(ctx):
                status, leads, reason, code = run_invocation(inv, timeout, repo.root)
                entry.setdefault("exit_codes", []).append(code)
                if status != "ran":
                    entry["status"] = status
                    problems.append(reason)
                tool_leads.extend(leads)
            tool_leads = dedupe(tool_leads)
            if spec.filter_to_diff and repo.changed is not None:
                kept = [ld for ld in tool_leads if not ld["file"] or ld["file"] in repo.changed]
                entry["filtered_unchanged"] = len(tool_leads) - len(kept)
                tool_leads = kept
            if problems:
                entry["reason"] = "; ".join(problems)
                report["not_inspected"].append({"what": name, "reason": entry["reason"]})
                partial = True
            entry["leads"] = len(tool_leads)
            report["leads"].extend(tool_leads)
    if repo.truncated:
        report["not_inspected"].append({"what": "file walk", "reason":
                                        f"stopped at {MAX_WALK_FILES} files; relevance "
                                        "detection may have missed some"})
    report["status"] = "partial" if partial else ("leads" if report["leads"] else "clean")
    return report


def dedupe(leads: list[dict]) -> list[dict]:
    seen, out = set(), []
    for ld in leads:
        key = (ld["rule_id"], ld["file"], ld["line"], ld["message"])
        if key not in seen:
            seen.add(key)
            out.append(ld)
    return out


def to_sarif(report: dict[str, Any]) -> dict[str, Any]:
    """Raw leads as SARIF 2.1.0. These are unreviewed scanner hits."""
    rules: dict[str, dict] = {}
    results = []
    for ld in report["leads"]:
        rid = f"{ld['tool']}/{ld['rule_id']}"
        rules.setdefault(rid, {"id": rid, "shortDescription": {"text": rid},
                               "properties": {"tags": ["security", "lead", *ld["cwe"]]}})
        loc: dict[str, Any] = {"artifactLocation": {"uri": ld["file"] or "."}}
        if ld["line"]:
            loc["region"] = {"startLine": ld["line"]}
        results.append({"ruleId": rid, "level": "warning",
                        "message": {"text": ld["message"] or rid},
                        "locations": [{"physicalLocation": loc}],
                        "properties": {"reported_severity": ld["severity"],
                                       "review_status": "unreviewed lead"}})
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "security-review/run_scanners",
                                          "rules": list(rules.values())}},
                      "results": results}]}


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_scanners.py",
        description="Run installed, relevant security scanners and print "
                    "normalised leads (unreviewed scanner hits) as JSON.",
        epilog="Exit 0 all relevant tools ran with no leads, 1 leads present, "
               "2 partial (a relevant tool missing, timed out or failed), "
               "64 usage error. Tools: " + ", ".join(TOOL_ORDER) + ".")
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--diff", metavar="BASE",
                       help="scan only what changed since commit-ish BASE")
    scope.add_argument("--audit", action="store_true",
                       help="whole tree plus full git history for gitleaks")
    p.add_argument("--repo-root", type=Path, default=Path("."),
                   help="repository to scan (default: current directory)")
    p.add_argument("--tools", metavar="A,B",
                   help="comma-separated subset of tools to run")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                   help=f"per-invocation timeout in seconds (default {DEFAULT_TIMEOUT_S})")
    p.add_argument("--json-out", type=Path, metavar="FILE",
                   help="also write the leads JSON to FILE")
    p.add_argument("--sarif-out", type=Path, metavar="FILE",
                   help="also write raw leads as SARIF 2.1.0 to FILE")
    return p


def run(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_CLEAN if exc.code == 0 else EXIT_USAGE
    try:
        root = args.repo_root
        if not root.is_dir():
            raise UsageError(f"--repo-root is not a directory: {root}")
        if args.timeout < 1:
            raise UsageError("--timeout must be at least 1")
        selected = None
        if args.tools:
            selected = [t.strip() for t in args.tools.split(",") if t.strip()]
            unknown = sorted(set(selected) - set(TOOLS))
            if unknown or not selected:
                raise UsageError(f"unknown tool(s) {unknown}; choose from "
                                 + ", ".join(TOOL_ORDER))
        mode = "diff" if args.diff else ("audit" if args.audit else "repo")
        report = scan(root, mode, args.diff, selected, args.timeout)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    text = json.dumps(report, indent=2)
    print(text)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    if args.sarif_out:
        args.sarif_out.write_text(json.dumps(to_sarif(report), indent=2) + "\n",
                                  encoding="utf-8")
    for item in report["not_inspected"]:
        print(f"not inspected: {item['what']}: {item['reason']}", file=sys.stderr)
    return {"partial": EXIT_PARTIAL, "leads": EXIT_LEADS}.get(report["status"], EXIT_CLEAN)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
