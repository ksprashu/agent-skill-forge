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

"""Collect vulnerability evidence for an agent to triage.

Two modes:

  check_vulns.py lockfile PATH [PATH ...]
      Parse resolved dependency versions from lockfiles and ask OSV.dev which
      advisories affect them (one querybatch per 1,000 packages). Only the
      ecosystem, package name and version leave the machine.

  check_vulns.py recent [--days N] [--severity LEVEL]
      List CVEs NVD published in the last N days (default 7, max 120). NVD
      needs pubStartDate and pubEndDate together; both are built from the
      clock.

The script collects and counts. It does not judge exploitability or decide
what to fix; the agent does that with the evidence printed here.

Output is one JSON object on stdout. Diagnostics go to stderr.

Exit codes:
  0   checked, no advisories found in what was checked
  1   checked, advisories found (listed in "advisories")
  2   unavailable or partial: a source failed, a response was unusable, or
      some dependencies could not be resolved. Unchecked is not safe.
  64  usage error

Environment (optional):
  ASP_OSV_URL   OSV base URL (default https://api.osv.dev)
  ASP_NVD_URL   NVD CVE endpoint (default
                https://services.nvd.nist.gov/rest/json/cves/2.0)
  NVD_API_KEY   sent as the apiKey header for higher NVD rate limits
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_UNAVAILABLE = 2
EXIT_USAGE = 64

DEFAULT_OSV = "https://api.osv.dev"
DEFAULT_NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"
TIMEOUT_S = 20
MAX_RETRY_WAIT_S = 10
OSV_BATCH = 1000
NVD_MAX_DAYS = 120
NVD_PAGE = 2000  # NVD's maximum page size
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

# Lockfile basename -> parser name. Only files that pin resolved versions.
SUPPORTED = {
    "package-lock.json": "npm",
    "requirements.txt": "pypi_requirements",
    "poetry.lock": "poetry",
    "Cargo.lock": "cargo",
    "go.sum": "gosum",
}


class UsageError(Exception):
    pass


class SourceError(Exception):
    pass


# ---------------------------------------------------------------- parsing

# A registry release version: 1.2.3, 1.2.3-beta.1, 1.2.3+build. Anything else
# (git URLs, file: paths, tarball URLs, aliases) is not sent anywhere, because
# it can carry credentials or local paths and doesn't name a registry release.
_REGISTRY_VERSION = re.compile(r"^v?\d+(\.\d+){0,3}([-+][0-9A-Za-z.+-]+)?$")


def _npm_record(name: str, version: str | None,
                pkgs: list[dict], unresolved: list[str]) -> None:
    if version and _REGISTRY_VERSION.match(version):
        pkgs.append({"ecosystem": "npm", "name": name, "version": version})
    else:
        unresolved.append(f"{name} (no registry version)")


def parse_npm(text: str) -> tuple[list[dict], list[str]]:
    data = json.loads(text)
    pkgs, unresolved = [], []
    for key, meta in (data.get("packages") or {}).items():
        if not key:  # "" is the root project itself
            continue
        name = meta.get("name") or key.split("node_modules/")[-1]
        if meta.get("link"):
            continue
        _npm_record(name, meta.get("version"), pkgs, unresolved)
    if not data.get("packages"):  # lockfileVersion 1
        def walk(deps: dict) -> None:
            for name, meta in deps.items():
                _npm_record(name, meta.get("version"), pkgs, unresolved)
                walk(meta.get("dependencies") or {})
        walk(data.get("dependencies") or {})
    return pkgs, unresolved


_REQ_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*===?\s*([^\s;#]+)")
_REQ_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
# Options that add dependencies from elsewhere. They aren't followed, so the
# result is incomplete. Their arguments are never copied into the report.
_REQ_INCLUDES = ("-r", "--requirement", "-c", "--constraint",
                 "-e", "--editable")


def parse_requirements(text: str) -> tuple[list[dict], list[str]]:
    """Pinned lines become packages. Everything else that adds a dependency
    is reported as unresolved by line number and package name only, never by
    its text, which can hold URLs with credentials or local paths."""
    pkgs, unresolved = [], []
    continued = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        is_continuation, continued = continued, raw.rstrip().endswith("\\")
        line = raw.split(" #", 1)[0].strip().rstrip("\\").strip()
        if not line or line.startswith("#") or is_continuation:
            continue
        if line.startswith("-"):
            option = re.split(r"[\s=]", line, maxsplit=1)[0]
            if not option.startswith("--") and len(option) > 2:
                option = option[:2]  # pip accepts -rbase.txt, -e./pkg
            if option in _REQ_INCLUDES:
                unresolved.append(f"line {lineno}: {option} directive not "
                                  "followed")
            continue  # index URLs, hashes and other global options
        m = _REQ_PIN.match(line)
        if m:
            pkgs.append({"ecosystem": "PyPI", "name": m.group(1),
                         "version": m.group(3)})
            continue
        name = _REQ_NAME.match(line)
        label = name.group(1) if name else "unnamed requirement"
        unresolved.append(f"line {lineno}: {label} (not pinned with ==)")
    return pkgs, unresolved


# Cargo.lock source strings that mean the public crates.io registry.
_CRATES_IO_SOURCES = (
    "registry+https://github.com/rust-lang/crates.io-index",
    "sparse+https://index.crates.io/",
)


def parse_poetry(text: str) -> tuple[list[dict], list[str]]:
    """Only packages without a [package.source] table come from PyPI. Git,
    URL, path and alternate-index sources can carry the same name and version
    as a PyPI release while being different code, so they are unresolved."""
    pkgs, unresolved = [], []
    for p in tomllib.loads(text).get("package") or []:
        name, version = p.get("name"), p.get("version")
        if not name:
            unresolved.append("unnamed package")
        elif p.get("source"):
            unresolved.append(f"{name} (non-PyPI source)")
        elif not version:
            unresolved.append(f"{name} (no version)")
        else:
            pkgs.append({"ecosystem": "PyPI", "name": name, "version": version})
    return pkgs, unresolved


def parse_cargo(text: str) -> tuple[list[dict], list[str]]:
    """Entries with no source are local workspace or path crates, not
    third-party releases, and are skipped. Git and alternate-registry sources
    are unresolved; only crates.io sources are sent."""
    pkgs, unresolved = [], []
    for p in tomllib.loads(text).get("package") or []:
        name, version, source = p.get("name"), p.get("version"), p.get("source")
        if not source:
            continue
        if not name:
            unresolved.append("unnamed package")
        elif source not in _CRATES_IO_SOURCES:
            unresolved.append(f"{name} (non-crates.io source)")
        elif not version:
            unresolved.append(f"{name} (no version)")
        else:
            pkgs.append({"ecosystem": "crates.io", "name": name,
                         "version": version})
    return pkgs, unresolved


def parse_gosum(text: str) -> tuple[list[dict], list[str]]:
    seen, pkgs = set(), []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        module, version = parts[0], parts[1].removesuffix("/go.mod")
        if (module, version) in seen:
            continue
        seen.add((module, version))
        pkgs.append({"ecosystem": "Go", "name": module,
                     "version": version.lstrip("v")})
    return pkgs, []


PARSERS = {
    "npm": parse_npm,
    "pypi_requirements": parse_requirements,
    "poetry": parse_poetry,
    "cargo": parse_cargo,
    "gosum": parse_gosum,
}


def read_lockfile(path: Path) -> tuple[list[dict], list[str]]:
    kind = SUPPORTED.get(path.name)
    if kind is None:
        raise UsageError(
            f"unsupported lockfile {path.name!r}; supported: "
            + ", ".join(sorted(SUPPORTED)))
    if not path.is_file():
        raise UsageError(f"not a file: {path}")
    try:
        return PARSERS[kind](path.read_text(encoding="utf-8"))
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        raise UsageError(f"could not parse {path.name}: {exc}") from exc


# ---------------------------------------------------------------- network


def _request(url: str, *, body: dict | None = None,
             headers: dict | None = None) -> dict:
    """GET or POST JSON with a timeout and one bounded retry on 429/5xx."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    for attempt in (1, 2):
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if retryable and attempt == 1:
                wait = exc.headers.get("Retry-After", "2")
                try:
                    wait_s = min(float(wait), MAX_RETRY_WAIT_S)
                except ValueError:
                    wait_s = 2.0
                time.sleep(wait_s)
                continue
            raise SourceError(f"HTTP {exc.code} from {_host(url)}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"cannot reach {_host(url)}: {exc}") from exc
        try:
            decoded = json.loads(raw)
        except ValueError as exc:
            raise SourceError(f"unparseable JSON from {_host(url)}") from exc
        if not isinstance(decoded, dict):
            raise SourceError(f"unexpected JSON shape from {_host(url)}")
        return decoded
    raise SourceError(f"no response from {_host(url)}")


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc or url


def _valid_osv_result(result: object) -> bool:
    """One querybatch entry: an object whose optional vulns list holds
    objects with string IDs. Anything else is unusable, not clean."""
    if not isinstance(result, dict):
        return False
    vulns = result.get("vulns", [])
    return isinstance(vulns, list) and all(
        isinstance(v, dict) and isinstance(v.get("id"), str) and v["id"]
        for v in vulns)


def osv_check(pkgs: list[dict]) -> tuple[list[dict], list[str], int]:
    """Return (advisories, problems, packages_checked).

    Sends ecosystem, name and version only; never paths or file contents.
    """
    base = os.environ.get("ASP_OSV_URL", DEFAULT_OSV).rstrip("/")
    advisories, problems, checked = [], [], 0
    for start in range(0, len(pkgs), OSV_BATCH):
        chunk = pkgs[start:start + OSV_BATCH]
        queries = [{"package": {"ecosystem": p["ecosystem"], "name": p["name"]},
                    "version": p["version"]} for p in chunk]
        try:
            resp = _request(f"{base}/v1/querybatch", body={"queries": queries})
        except SourceError as exc:
            problems.append(str(exc))
            continue
        results = resp.get("results")
        if not isinstance(results, list) or len(results) != len(chunk):
            problems.append("OSV returned a result list that does not match "
                            "the query list")
            continue
        if not all(_valid_osv_result(r) for r in results):
            problems.append("OSV returned malformed result entries")
            continue
        checked += len(chunk)
        for pkg, result in zip(chunk, results):
            ids = [v["id"] for v in result.get("vulns") or []]
            if result.get("next_page_token"):
                problems.append(f"OSV has more advisories for {pkg['name']} "
                                "than one page; listed IDs are incomplete")
            if ids:
                advisories.append({**pkg, "ids": ids})
    return advisories, problems, checked


def nvd_window(days: int, now: dt.datetime) -> tuple[str, str]:
    if not 1 <= days <= NVD_MAX_DAYS:
        raise UsageError(f"--days must be 1 to {NVD_MAX_DAYS}")
    end = now.astimezone(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
    start = end - dt.timedelta(days=days)
    fmt = "%Y-%m-%dT%H:%M:%S.000"
    return start.strftime(fmt), end.strftime(fmt)


def nvd_recent(days: int, severity: str,
               now: dt.datetime | None = None) -> tuple[dict, list[str]]:
    start, end = nvd_window(days, now or dt.datetime.now(dt.timezone.utc))
    params = {"cvssV3Severity": severity, "pubStartDate": start,
              "pubEndDate": end, "resultsPerPage": str(NVD_PAGE)}
    url = os.environ.get("ASP_NVD_URL", DEFAULT_NVD) + "?" + \
        urllib.parse.urlencode(params)
    headers = {}
    if os.environ.get("NVD_API_KEY"):
        headers["apiKey"] = os.environ["NVD_API_KEY"]
    try:
        resp = _request(url, headers=headers)
    except SourceError as exc:
        return {"window": [start, end]}, [str(exc)]
    vulns = resp.get("vulnerabilities")
    total = resp.get("totalResults")
    if not isinstance(vulns, list) or not isinstance(total, int):
        return {"window": [start, end]}, ["NVD response missing "
                                          "vulnerabilities or totalResults"]
    ids = [v.get("cve", {}).get("id") for v in vulns
           if isinstance(v, dict) and v.get("cve", {}).get("id")]
    problems = []
    if total > len(ids):
        problems.append(f"NVD reports {total} CVEs but returned {len(ids)}; "
                        "the list is incomplete")
    return {"window": [start, end], "severity": severity,
            "total": total, "listed": ids}, problems


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_vulns.py",
        description="Collect vulnerability evidence from OSV.dev and NVD.",
        epilog="Exit 0 clean, 1 advisories found, 2 unavailable or partial, "
               "64 usage error.")
    sub = p.add_subparsers(dest="mode", required=True)
    lock = sub.add_parser("lockfile", help="check resolved dependencies "
                          "against OSV.dev")
    lock.add_argument("paths", nargs="+", type=Path,
                      help="lockfiles: " + ", ".join(sorted(SUPPORTED)))
    rec = sub.add_parser("recent", help="list recent CVEs from NVD")
    rec.add_argument("--days", type=int, default=7,
                     help=f"window in days, 1 to {NVD_MAX_DAYS} (default 7)")
    rec.add_argument("--severity", default="CRITICAL",
                     choices=SEVERITIES, help="CVSS v3 severity "
                     "(default CRITICAL)")
    return p


def run(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_CLEAN if exc.code == 0 else EXIT_USAGE

    report: dict = {"mode": args.mode}
    try:
        if args.mode == "lockfile":
            pkgs, unresolved = [], []
            for path in args.paths:
                found, missing = read_lockfile(path)
                pkgs.extend(found)
                unresolved.extend(missing)
            advisories, problems, checked = (osv_check(pkgs) if pkgs
                                             else ([], [], 0))
            report.update(packages_found=len(pkgs), packages_checked=checked,
                          unresolved=unresolved, advisories=advisories)
            if unresolved:
                problems.append(f"{len(unresolved)} dependencies have no "
                                "pinned version and were not checked")
        else:
            nvd, problems = nvd_recent(args.days, args.severity)
            report.update(nvd=nvd)
            advisories = nvd.get("listed") or []
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    report["problems"] = problems
    if problems:
        some_checked = bool(report.get("packages_checked")) or bool(
            report.get("nvd", {}).get("listed") is not None
            and "total" in report.get("nvd", {}))
        report["status"] = "partial" if some_checked else "unavailable"
        code = EXIT_UNAVAILABLE
    elif advisories:
        report["status"] = "finding"
        code = EXIT_FINDINGS
    else:
        report["status"] = "checked"
        code = EXIT_CLEAN
    print(json.dumps(report, indent=2))
    for msg in problems:
        print(f"warning: {msg}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
