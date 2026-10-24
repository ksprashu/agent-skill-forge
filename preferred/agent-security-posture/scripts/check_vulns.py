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

  check_vulns.py lockfile [--enrich] PATH [PATH ...]
      Parse resolved dependency versions from lockfiles and ask OSV.dev which
      advisories affect them (one querybatch per 1,000 packages). Only the
      ecosystem, package name and version leave the machine.

      Supported: package-lock.json, pnpm-lock.yaml, yarn.lock (classic and
      berry), requirements.txt (== pins), poetry.lock, uv.lock, Pipfile.lock,
      Cargo.lock, go.mod, go.sum, Gemfile.lock, gradle.lockfile and pom.xml
      (explicit versions only; unresolved ${properties} are unchecked).
      Git, path, tarball and alternate-registry entries are reported as
      unresolved by name and never transmitted. go.sum counts only module
      versions whose code hash is present; with go.mod from the same
      directory, go.mod is read instead.

      --enrich adds, per advisory: OSV aliases, CISA KEV membership and date
      added, FIRST EPSS score and percentile for CVE aliases, and GHSA
      severity, CVSS score, CWEs, summary and URL via `gh api` when gh is on
      PATH. Only advisory ids leave the machine. A failed enrichment source
      is a problem: the result becomes partial (exit 2).

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
  ASP_KEV_URL   CISA KEV feed (default https://www.cisa.gov/sites/default/
                files/feeds/known_exploited_vulnerabilities.json)
  ASP_EPSS_URL  FIRST EPSS endpoint (default
                https://api.first.org/data/v1/epss)
  ASP_GH_BIN    gh executable to use for GHSA details (default: gh on PATH)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
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
DEFAULT_KEV = ("https://www.cisa.gov/sites/default/files/feeds/"
               "known_exploited_vulnerabilities.json")
DEFAULT_EPSS = "https://api.first.org/data/v1/epss"
EPSS_BATCH = 50
GH_TIMEOUT_S = 30
CVE_ID = re.compile(r"^CVE-\d{4}-\d{4,}$")
# GHSA ids use a restricted alphabet; anything else is never passed to gh.
GHSA_ID = re.compile(r"^GHSA(-[23456789cfghjmpqrvwx]{4}){3}$")
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
    "go.mod": "gomod",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "uv.lock": "uv",
    "Pipfile.lock": "pipfile",
    "Gemfile.lock": "gemfile",
    "gradle.lockfile": "gradle",
    "pom.xml": "pom",
}

# What a lockfile cannot show. Reported under "coverage_notes" so a clean
# result is read with its limits; these do not change the exit code.
COVERAGE_NOTES = {
    "pom": "pom.xml lists direct dependencies only; transitive dependencies "
           "need a resolved tree (gradle.lockfile, or a resolved dependency "
           "list) and were not checked",
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


# Hosts whose tarballs are the public npm registry. A version string alone
# doesn't prove the source: a git, file or private-registry entry can carry
# "1.2.3" too, and OSV would then vouch for code it never saw.
_NPM_PUBLIC_HOSTS = ("registry.npmjs.org", "registry.yarnpkg.com")


def _npm_public(resolved: object) -> bool:
    if not isinstance(resolved, str):
        return False
    parts = urllib.parse.urlsplit(resolved)
    return parts.scheme == "https" and parts.hostname in _NPM_PUBLIC_HOSTS


def _npm_record(name: str, meta: dict,
                pkgs: list[dict], unresolved: list[str]) -> None:
    """Send only entries resolved from the public registry with a release
    version. Everything else is unresolved by name; its URL or path is never
    kept."""
    version = meta.get("version")
    if not (isinstance(version, str) and _REGISTRY_VERSION.match(version)):
        unresolved.append(f"{name} (no registry version)")
    elif not _npm_public(meta.get("resolved")):
        unresolved.append(f"{name} (not from the public npm registry)")
    else:
        pkgs.append({"ecosystem": "npm", "name": name, "version": version})


def parse_npm(text: str) -> tuple[list[dict], list[str]]:
    data = json.loads(text)
    pkgs, unresolved = [], []
    for key, meta in (data.get("packages") or {}).items():
        if not key:  # "" is the root project itself
            continue
        if "node_modules/" not in key:
            continue  # a workspace package: the project's own code
        if not isinstance(meta, dict) or meta.get("link"):
            continue  # a symlink to a workspace package
        name = meta.get("name") or key.rsplit("node_modules/", 1)[-1]
        _npm_record(name, meta, pkgs, unresolved)
    if not data.get("packages"):  # lockfileVersion 1
        def walk(deps: dict) -> None:
            for name, meta in deps.items():
                if not isinstance(meta, dict):
                    unresolved.append(f"{name} (unreadable entry)")
                    continue
                _npm_record(name, meta, pkgs, unresolved)
                walk(meta.get("dependencies") or {})
        walk(data.get("dependencies") or {})
    return pkgs, unresolved


_REQ_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*===?\s*([^;#]+)")
# One exact release, e.g. 2.32.3, 1.0.0rc1, 2.0.post1. Wildcards (2.*) and
# compound specifiers (==2.32.3,!=2.32.2) name a range, not a version.
_EXACT_PY_VERSION = re.compile(r"^v?\d+(\.\d+)*([._-]?(a|b|rc|post|dev)\d*)*(\+[0-9A-Za-z.]+)?$",
                               re.IGNORECASE)
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
            version = m.group(3).strip()
            if _EXACT_PY_VERSION.match(version):
                pkgs.append({"ecosystem": "PyPI", "name": m.group(1),
                             "version": version})
            else:
                unresolved.append(f"line {lineno}: {m.group(1)} "
                                  "(not one exact version)")
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
    """go.sum lists every module version in the build graph, including
    versions whose go.mod was read during resolution but whose code was never
    built. Those appear only as "<module> <version>/go.mod" lines. Count a
    module version only when go.sum holds the hash of its zip (a line without
    the /go.mod suffix), so pruned versions are not reported."""
    seen, pkgs = set(), []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1].endswith("/go.mod"):
            continue
        module, version = parts[0], parts[1]
        if (module, version) in seen:
            continue
        seen.add((module, version))
        pkgs.append({"ecosystem": "Go", "name": module,
                     "version": version.lstrip("v")})
    return pkgs, []


_GO_LOCAL = re.compile(r"^(\.{1,2}/|/|[A-Za-z]:[\\/])")


def parse_gomod(text: str) -> tuple[list[dict], list[str]]:
    """require lines (single and block form, // indirect included). A module
    replaced by a local path is unresolved; one replaced by another module
    version is checked as the replacement."""
    requires: list[tuple[str, str]] = []
    replaces: dict[tuple[str, str | None], tuple[str, str | None]] = {}
    block = None
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if block:
            if line == ")":
                block = None
                continue
            body = line
            _go_directive(block, body, requires, replaces)
            continue
        word, _, body = line.partition(" ")
        body = body.strip()
        if word not in ("require", "replace"):
            continue
        if body == "(":
            block = word
        else:
            _go_directive(word, body, requires, replaces)
    pkgs, unresolved = [], []
    for module, version in requires:
        target = replaces.get((module, version)) or replaces.get((module, None))
        if target is not None:
            new_mod, new_ver = target
            if new_ver is None:
                unresolved.append(f"{module} (replaced by a local path)")
                continue
            module, version = new_mod, new_ver
        pkgs.append({"ecosystem": "Go", "name": module,
                     "version": version.lstrip("v")})
    return pkgs, unresolved


def _go_directive(word: str, body: str, requires: list,
                  replaces: dict) -> None:
    if word == "require":
        parts = body.split()
        if len(parts) >= 2:
            requires.append((parts[0], parts[1]))
        return
    left, sep, right = body.partition("=>")
    if not sep:
        return
    lparts, rparts = left.split(), right.split()
    if not lparts or not rparts:
        return
    key = (lparts[0], lparts[1] if len(lparts) > 1 else None)
    if _GO_LOCAL.match(rparts[0]) or len(rparts) < 2:
        replaces[key] = (rparts[0], None)
    else:
        replaces[key] = (rparts[0], rparts[1])


# An npm package name, optionally scoped. Used to decide whether a lockfile
# key is safe to echo as a label; anything else (URLs, paths) is never copied.
_NPM_NAME = re.compile(r"^(@[A-Za-z0-9._~-]+/)?[A-Za-z0-9._~-]+$")


def _npm_label(name: str) -> str:
    return name if _NPM_NAME.match(name or "") else "unnamed entry"


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def _split_name_version(spec: str) -> tuple[str, str]:
    """"name@1.2.3" or "@scope/name@1.2.3" -> (name, rest)."""
    idx = spec.find("@", 1)
    if idx < 0:
        return spec, ""
    return spec[:idx], spec[idx + 1:]


def parse_pnpm(text: str) -> tuple[list[dict], list[str]]:
    """pnpm-lock.yaml, read line by line (no YAML library). Only the
    top-level packages: map is read. Keys:
      v5   /name/1.2.3_peer:        /@scope/name/1.2.3:
      v6   /name@1.2.3(peer@1):     /@scope/name@1.2.3:
      v9   name@1.2.3:              '@scope/name@1.2.3':
    An entry with a tarball, repo, commit or directory resolution, or whose
    version is not a registry release (git, file:, link:), is unresolved by
    name; its URL or path is never kept."""
    entries: list[tuple[str, dict]] = []
    in_packages = False
    current: dict | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            in_packages = line == "packages:"
            current = None
            continue
        if not in_packages:
            continue
        if indent == 2 and line.endswith(":"):
            current = {}
            entries.append((_unquote(line[:-1]), current))
        elif indent == 4 and current is not None and ":" in line:
            key, _, value = line.partition(":")
            current[key.strip()] = value.strip()
    pkgs, unresolved, seen = [], [], set()
    for key, attrs in entries:
        spec = key.lstrip("/").split("(", 1)[0]
        name, version = _split_name_version(spec)
        if (not version or not _NPM_NAME.match(name)) and "/" in spec:
            # v5: /name/1.2.3 or /@s/name/1.2.3_peer@1 (peers after "_")
            v5_name, _, v5_version = spec.split("_", 1)[0].rpartition("/")
            if _NPM_NAME.match(v5_name):
                name, version = v5_name, v5_version
        label = _npm_label(_unquote(attrs.get("name", "")) or name)
        if attrs.get("version"):  # v6 non-registry entries carry name/version
            version = _unquote(attrs["version"]) if not version else version
        resolution = attrs.get("resolution", "")
        if any(k in resolution for k in ("tarball:", "repo:", "commit:",
                                         "directory:")):
            unresolved.append(f"{label} (not from the public npm registry)")
        elif not (_REGISTRY_VERSION.match(version)
                  and _NPM_NAME.match(name)):
            unresolved.append(f"{label} (no registry version)")
        elif (name, version) not in seen:
            seen.add((name, version))
            pkgs.append({"ecosystem": "npm", "name": name,
                         "version": version.lstrip("v")})
    return pkgs, list(dict.fromkeys(unresolved))


def parse_yarn(text: str) -> tuple[list[dict], list[str]]:
    """yarn.lock, classic (v1) and berry (v2+). Classic entries are sent only
    when resolved from the public registry. Berry entries are sent when the
    resolution uses the npm: protocol; workspace: entries are the project's
    own code and patch: entries repeat a base npm: entry, so both are skipped.
    Other protocols (git, file, link, portal, exec, URLs) are unresolved by
    name. Berry does not record the registry host, so a custom
    npmRegistryServer cannot be told apart from the public registry."""
    berry = "__metadata:" in text
    entries: list[tuple[str, dict]] = []
    current: dict | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            current = {}
            entries.append((line[:-1], current))
        elif indent == 2 and current is not None:
            if berry:
                key, _, value = line.partition(":")
            else:
                key, _, value = line.partition(" ")
            current[key.strip()] = _unquote(value.strip())
    pkgs, unresolved, seen = [], [], set()
    for header, attrs in entries:
        first = _unquote(_unquote(header).split(",")[0])
        name, _ = _split_name_version(first)
        if name == "__metadata":
            continue
        if berry:
            res_name, proto = _split_name_version(attrs.get("resolution", ""))
            name = res_name or name
            label = _npm_label(name)
            if proto.startswith(("workspace:", "patch:")):
                continue
            version = attrs.get("version", "")
            if not proto.startswith("npm:"):
                unresolved.append(f"{label} (non-npm source)")
            elif not (_REGISTRY_VERSION.match(version) and
                      _NPM_NAME.match(name)):
                unresolved.append(f"{label} (no registry version)")
            elif (name, version) not in seen:
                seen.add((name, version))
                pkgs.append({"ecosystem": "npm", "name": name,
                             "version": version})
            continue
        if _npm_label(name) != name:
            unresolved.append("unnamed entry (no registry version)")
            continue
        found, missing = [], []
        _npm_record(name, attrs, found, missing)
        unresolved.extend(missing)
        for p in found:
            if (p["name"], p["version"]) not in seen:
                seen.add((p["name"], p["version"]))
                pkgs.append(p)
    return pkgs, list(dict.fromkeys(unresolved))


_PYPI_HOSTS = ("pypi.org", "files.pythonhosted.org")


def parse_uvlock(text: str) -> tuple[list[dict], list[str]]:
    """uv.lock. Packages from the PyPI registry are sent; editable and
    virtual sources are the project itself and are skipped; git, url, path,
    directory and other-registry sources are unresolved by name."""
    pkgs, unresolved = [], []
    for p in tomllib.loads(text).get("package") or []:
        name, version = p.get("name"), p.get("version")
        source = p.get("source") or {}
        if not name:
            unresolved.append("unnamed package")
            continue
        if not isinstance(source, dict):
            unresolved.append(f"{name} (unreadable source)")
            continue
        if "editable" in source or "virtual" in source:
            continue
        registry = source.get("registry")
        host = urllib.parse.urlsplit(registry).hostname if isinstance(
            registry, str) else None
        if host not in _PYPI_HOSTS:
            unresolved.append(f"{name} (non-PyPI source)")
        elif not (isinstance(version, str) and
                  _EXACT_PY_VERSION.match(version)):
            unresolved.append(f"{name} (no exact version)")
        else:
            pkgs.append({"ecosystem": "PyPI", "name": name,
                         "version": version})
    return pkgs, unresolved


def parse_pipfile_lock(text: str) -> tuple[list[dict], list[str]]:
    """Pipfile.lock "default" and "develop". git, path, file and editable
    entries, and entries from an index that is not PyPI, are unresolved."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Pipfile.lock is not a JSON object")
    sources = {}
    for src in (data.get("_meta") or {}).get("sources") or []:
        if isinstance(src, dict) and isinstance(src.get("name"), str):
            sources[src["name"]] = urllib.parse.urlsplit(
                str(src.get("url", ""))).hostname
    pkgs, unresolved, seen = [], [], set()
    for section in ("default", "develop"):
        for name, meta in (data.get(section) or {}).items():
            if not isinstance(meta, dict):
                unresolved.append(f"{name} (unreadable entry)")
                continue
            if any(k in meta for k in ("git", "path", "file", "editable")):
                unresolved.append(f"{name} (non-PyPI source)")
                continue
            index = meta.get("index")
            if index is not None and sources.get(index) not in _PYPI_HOSTS:
                unresolved.append(f"{name} (non-PyPI index)")
                continue
            version = str(meta.get("version", ""))
            exact = version[2:] if version.startswith("==") else ""
            if not _EXACT_PY_VERSION.match(exact):
                unresolved.append(f"{name} (not one exact version)")
            elif (name, exact) not in seen:
                seen.add((name, exact))
                pkgs.append({"ecosystem": "PyPI", "name": name,
                             "version": exact})
    return pkgs, unresolved


_GEM_SPEC = re.compile(r"^    ([A-Za-z0-9._-]+) \(([^)]+)\)$")
_GEM_VERSION = re.compile(r"^\d+(\.[0-9A-Za-z]+)*$")


def parse_gemfile_lock(text: str) -> tuple[list[dict], list[str]]:
    """Gemfile.lock. Specs under a GEM section whose remote is rubygems.org
    are sent (a platform suffix such as -x86_64-linux is dropped). Specs
    under GIT, PATH or a GEM section with another remote are unresolved by
    name."""
    pkgs, unresolved, seen = [], [], set()
    section, remote_public = None, False
    for raw in text.splitlines():
        if raw and not raw.startswith(" "):
            section = raw.strip()
            remote_public = False
            continue
        stripped = raw.strip()
        if stripped.startswith("remote:"):
            host = urllib.parse.urlsplit(
                stripped.split(":", 1)[1].strip()).hostname
            remote_public = section == "GEM" and host == "rubygems.org"
            continue
        if section not in ("GEM", "GIT", "PATH"):
            continue
        m = _GEM_SPEC.match(raw)
        if not m:
            continue
        name, version = m.group(1), m.group(2).split("-", 1)[0]
        if not remote_public:
            unresolved.append(f"{name} (non-rubygems.org source)")
        elif not _GEM_VERSION.match(version):
            unresolved.append(f"{name} (no exact version)")
        elif (name, version) not in seen:
            seen.add((name, version))
            pkgs.append({"ecosystem": "RubyGems", "name": name,
                         "version": version})
    return pkgs, list(dict.fromkeys(unresolved))


_MAVEN_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")


def parse_gradle_lockfile(text: str) -> tuple[list[dict], list[str]]:
    """gradle.lockfile: group:artifact:version=configurations."""
    pkgs, unresolved = [], []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("empty="):
            continue
        coords = line.split("=", 1)[0].split(":")
        if len(coords) != 3:
            unresolved.append(f"line {lineno}: unreadable coordinate")
            continue
        group, artifact, version = coords
        if not _MAVEN_VERSION.match(version):
            unresolved.append(f"{group}:{artifact} (no exact version)")
            continue
        pkgs.append({"ecosystem": "Maven", "name": f"{group}:{artifact}",
                     "version": version})
    return pkgs, unresolved


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(elem, name: str):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _text(elem, name: str) -> str:
    c = _child(elem, name)
    return (c.text or "").strip() if c is not None else ""


_PROP_REF = re.compile(r"\$\{([^}]+)\}")


def parse_pom(text: str) -> tuple[list[dict], list[str]]:
    """Maven pom.xml: <dependencies> and <dependencyManagement>. Only
    explicit versions are sent. ${prop} is substituted when the property is
    defined literally in the same file; otherwise the dependency is
    unresolved. Ranges and missing versions (managed by a parent or a BOM)
    are unresolved. Transitive dependencies are not in a pom at all.

    defusedxml is not stdlib, so documents with a DOCTYPE or ENTITY
    declaration are refused rather than parsed (entity-expansion guard)."""
    import xml.etree.ElementTree as ET
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ValueError("pom.xml declares a DOCTYPE or ENTITY; refusing to "
                         "parse it")
    root = ET.fromstring(text)
    props: dict[str, str] = {}
    for key in ("version", "groupId", "artifactId"):
        value = _text(root, key)
        if value and "${" not in value:
            props[f"project.{key}"] = value
    props_el = _child(root, "properties")
    if props_el is not None:
        for c in props_el:
            value = (c.text or "").strip()
            if value and "${" not in value:
                props[_local(c.tag)] = value

    def subst(value: str) -> str:
        return _PROP_REF.sub(lambda m: props.get(m.group(1), m.group(0)),
                             value)

    deps = []
    for container in (root, _child(root, "dependencyManagement")):
        if container is None:
            continue
        deps_el = _child(container, "dependencies")
        if deps_el is not None:
            deps.extend(d for d in deps_el if _local(d.tag) == "dependency")
    pkgs, unresolved = [], []
    for dep in deps:
        group, artifact = subst(_text(dep, "groupId")), subst(
            _text(dep, "artifactId"))
        raw_version = _text(dep, "version")
        name = f"{group}:{artifact}"
        if not group or not artifact or "${" in name:
            unresolved.append(f"{name} (unresolved coordinates)")
            continue
        if not raw_version:
            unresolved.append(f"{name} (version managed elsewhere)")
            continue
        version = subst(raw_version)
        missing = _PROP_REF.search(version)
        if missing:
            unresolved.append(f"{name} (unresolved property "
                              f"${{{missing.group(1)}}})")
        elif version[:1] in "[(" or "," in version or not \
                _MAVEN_VERSION.match(version):
            unresolved.append(f"{name} (version range)")
        else:
            pkgs.append({"ecosystem": "Maven", "name": name,
                         "version": version})
    return pkgs, unresolved


PARSERS = {
    "npm": parse_npm,
    "pypi_requirements": parse_requirements,
    "poetry": parse_poetry,
    "cargo": parse_cargo,
    "gosum": parse_gosum,
    "gomod": parse_gomod,
    "pnpm": parse_pnpm,
    "yarn": parse_yarn,
    "uv": parse_uvlock,
    "pipfile": parse_pipfile_lock,
    "gemfile": parse_gemfile_lock,
    "gradle": parse_gradle_lockfile,
    "pom": parse_pom,
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
    except (ValueError, tomllib.TOMLDecodeError, SyntaxError) as exc:
        # xml.etree.ElementTree.ParseError is a SyntaxError subclass.
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


# ---------------------------------------------------------------- enrichment
#
# Only advisory identifiers leave the machine here: OSV advisory ids, CVE ids
# for EPSS, and GHSA ids for gh. The KEV feed is downloaded whole, so nothing
# is sent to CISA at all.


def _osv_aliases(ids: list[str], problems: list[str]) -> dict[str, list[str]]:
    base = os.environ.get("ASP_OSV_URL", DEFAULT_OSV).rstrip("/")
    aliases: dict[str, list[str]] = {}
    for vid in ids:
        try:
            data = _request(f"{base}/v1/vulns/{urllib.parse.quote(vid, safe='')}")
        except SourceError as exc:
            problems.append(f"OSV advisory details for {vid}: {exc}")
            continue
        found = data.get("aliases", [])
        if not isinstance(found, list) or not all(isinstance(a, str)
                                                   for a in found):
            problems.append(f"OSV advisory details for {vid}: malformed "
                            "aliases")
            continue
        aliases[vid] = found
    return aliases


def _kev(cves: set[str], problems: list[str]) -> dict[str, str] | None:
    """CVE -> dateAdded for listed CVEs; None when the feed is unusable."""
    url = os.environ.get("ASP_KEV_URL", DEFAULT_KEV)
    try:
        data = _request(url)
    except SourceError as exc:
        problems.append(f"CISA KEV: {exc}")
        return None
    vulns = data.get("vulnerabilities")
    if not isinstance(vulns, list) or not all(
            isinstance(v, dict) and isinstance(v.get("cveID"), str)
            for v in vulns):
        problems.append("CISA KEV: feed missing a vulnerabilities list")
        return None
    return {v["cveID"]: str(v.get("dateAdded", "")) for v in vulns
            if v["cveID"] in cves}


def _epss(cves: list[str], problems: list[str]) -> dict[str, dict] | None:
    base = os.environ.get("ASP_EPSS_URL", DEFAULT_EPSS)
    scores: dict[str, dict] = {}
    for start in range(0, len(cves), EPSS_BATCH):
        chunk = cves[start:start + EPSS_BATCH]
        url = base + "?" + urllib.parse.urlencode({"cve": ",".join(chunk)})
        try:
            data = _request(url)
        except SourceError as exc:
            problems.append(f"FIRST EPSS: {exc}")
            return None
        rows = data.get("data")
        if not isinstance(rows, list) or not all(
                isinstance(r, dict) and isinstance(r.get("cve"), str)
                for r in rows):
            problems.append("FIRST EPSS: response missing a data list")
            return None
        for r in rows:
            scores[r["cve"]] = {"epss": r.get("epss"),
                                "percentile": r.get("percentile"),
                                "date": r.get("date")}
    return scores


def _ghsa(ids: list[str], problems: list[str]) -> dict[str, dict] | None:
    gh = os.environ.get("ASP_GH_BIN") or shutil.which("gh")
    if not gh or not (os.path.isfile(gh) and os.access(gh, os.X_OK)):
        problems.append("GHSA enrichment not run: gh not on PATH")
        return None
    out: dict[str, dict] = {}
    for gid in ids:
        if not GHSA_ID.match(gid):
            continue
        try:
            proc = subprocess.run([gh, "api", f"/advisories/{gid}"],
                                  capture_output=True, text=True,
                                  timeout=GH_TIMEOUT_S, shell=False,
                                  check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            problems.append(f"GHSA {gid}: gh failed ({type(exc).__name__})")
            continue
        if proc.returncode != 0:
            problems.append(f"GHSA {gid}: gh exited {proc.returncode}")
            continue
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            problems.append(f"GHSA {gid}: gh returned unparseable JSON")
            continue
        if not isinstance(data, dict):
            problems.append(f"GHSA {gid}: gh returned an unexpected shape")
            continue
        cvss = data.get("cvss") if isinstance(data.get("cvss"), dict) else {}
        cwes = [c.get("cwe_id") for c in data.get("cwes") or []
                if isinstance(c, dict) and isinstance(c.get("cwe_id"), str)]
        out[gid] = {"severity": data.get("severity"),
                    "cvss_score": cvss.get("score"),
                    "cwes": cwes,
                    "summary": data.get("summary"),
                    "html_url": data.get("html_url")}
    return out


def enrich(advisories: list[dict]) -> list[str]:
    """Add an "enrichment" object to each advisory. Returns problems; any
    problem means enrichment was asked for and not fully obtained. A source
    that failed is reported as null under its key, never as false."""
    problems: list[str] = []
    ids = sorted({i for a in advisories for i in a["ids"]})
    aliases = _osv_aliases(ids, problems)
    known = {i: sorted(set([i, *aliases.get(i, [])])) for i in ids}
    cves = sorted({x for group in known.values() for x in group
                   if CVE_ID.match(x)})
    ghsas = sorted({x for group in known.values() for x in group
                    if GHSA_ID.match(x)})
    kev = _kev(set(cves), problems) if cves else {}
    epss = _epss(cves, problems) if cves else {}
    ghsa = _ghsa(ghsas, problems) if ghsas else {}
    for adv in advisories:
        names = sorted({x for i in adv["ids"] for x in known[i]})
        adv_cves = [x for x in names if CVE_ID.match(x)]
        adv_ghsa = [x for x in names if GHSA_ID.match(x)]
        adv["enrichment"] = {
            "aliases": [x for x in names if x not in adv["ids"]],
            "kev": None if kev is None else any(c in kev for c in adv_cves),
            "kev_date_added": None if kev is None else
            {c: kev[c] for c in adv_cves if c in kev},
            "epss": None if epss is None else
            {c: epss[c] for c in adv_cves if c in epss},
            "ghsa": None if ghsa is None else
            {g: ghsa[g] for g in adv_ghsa if g in ghsa},
        }
    return problems


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
    if not all(isinstance(v, dict) and isinstance(v.get("cve"), dict)
               and isinstance(v["cve"].get("id"), str) and v["cve"]["id"]
               for v in vulns):
        return {"window": [start, end]}, ["NVD returned malformed "
                                          "vulnerability entries"]
    ids = [v["cve"]["id"] for v in vulns]
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
               "64 usage error. Environment: ASP_OSV_URL, ASP_NVD_URL, "
               "NVD_API_KEY, ASP_KEV_URL, ASP_EPSS_URL, ASP_GH_BIN.")
    sub = p.add_subparsers(dest="mode", required=True)
    lock = sub.add_parser("lockfile", help="check resolved dependencies "
                          "against OSV.dev")
    lock.add_argument("paths", nargs="+", type=Path,
                      help="lockfiles: " + ", ".join(sorted(SUPPORTED)))
    lock.add_argument("--enrich", action="store_true",
                      help="add OSV aliases, CISA KEV membership, FIRST EPSS "
                      "scores and GHSA details (via gh) to each advisory; a "
                      "failed enrichment source makes the result partial")
    rec = sub.add_parser("recent", help="list recent CVEs from NVD")
    rec.add_argument("--days", type=int, default=7,
                     help=f"window in days, 1 to {NVD_MAX_DAYS} (default 7)")
    rec.add_argument("--severity", default="CRITICAL",
                     choices=SEVERITIES, help="CVSS v3 severity "
                     "(default CRITICAL)")
    return p


def _prefer_gomod(paths: list[Path]) -> list[Path]:
    """When go.mod and go.sum from one directory are both given, read only
    go.mod: go.sum also hashes versions that were never selected."""
    mod_dirs = {p.resolve().parent for p in paths if p.name == "go.mod"}
    return [p for p in paths
            if not (p.name == "go.sum" and p.resolve().parent in mod_dirs)]


def run(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_CLEAN if exc.code == 0 else EXIT_USAGE

    report: dict = {"mode": args.mode}
    try:
        if args.mode == "lockfile":
            pkgs, unresolved, notes = [], [], []
            paths = _prefer_gomod(args.paths)
            for path in paths:
                found, missing = read_lockfile(path)
                pkgs.extend(found)
                unresolved.extend(missing)
                note = COVERAGE_NOTES.get(SUPPORTED[path.name])
                if note and note not in notes:
                    notes.append(note)
            pkgs = list({(p["ecosystem"], p["name"], p["version"]): p
                         for p in pkgs}.values())
            advisories, problems, checked = (osv_check(pkgs) if pkgs
                                             else ([], [], 0))
            if args.enrich and advisories:
                problems.extend(enrich(advisories))
            report.update(packages_found=len(pkgs), packages_checked=checked,
                          unresolved=unresolved, advisories=advisories)
            if notes:
                report["coverage_notes"] = notes
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
