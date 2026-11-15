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

"""Pure-stdlib mechanical probe collectors and S8 secret redactor for skills/horizon.

Engineering Standard contract (S1-S9, V5):
  - S1: 100% Python 3.12 standard library.
  - S2: Module name ``horizon_probes`` does not shadow any stdlib module.
  - S4: Every subprocess invocation passes an argument list with ``shell=False``,
        an explicit timeout, and CWE-88 positional ``-`` argument guards.
  - S8: Secrets are redacted at capture time inside subprocess and HTTP runners,
        while preserving valid JSON literals (``null``, ``true``, ``false``, numbers).
  - S9: Probes record purely factual observations (hashes, exit codes, HTTP
        statuses, release tags, token presence, file anchor existence) and NEVER
        emit subjective scores or verdicts.
  - V5: Unavailable tools, failed remote fetches, and ``agent_query`` probes are
        recorded explicitly in ``not_inspected`` rather than omitted or passed.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Constants & Allowlists
# ---------------------------------------------------------------------------

CLI_HELP_ALLOWLIST: frozenset[str] = frozenset(
    {"gemini-api", "gh", "ffmpeg", "ffprobe", "python3", "git"}
)
ALLOWED_CLI_FLAGS: frozenset[str] = frozenset({"--help", "-h", "--version"})
SAFE_CLI_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GITHUB_PR_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)/?$"
)

MAX_HTTP_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_S = 30
DEFAULT_GITHUB_API_BASE = "https://api.github.com"

LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})
BLOCKED_METADATA_HOSTS: frozenset[str] = frozenset(
    {"169.254.169.254", "metadata.google.internal", "metadata.goog", "100.100.100.200"}
)

PROBE_KINDS: frozenset[str] = frozenset(
    {"cli_help", "github_release", "http_digest", "file_anchor", "gh_pr_status", "agent_query"}
)
FILE_ANCHOR_SCOPES: frozenset[str] = frozenset({"repo", "global_config"})

# Aligned with skills/image-gen/scripts/image_gen.py so quoted and unquoted keys
# redact cleanly while JSON literals (null/true/false/numbers) stay parseable.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35,}\b")),
    ("Google OAuth token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Secret key", re.compile(r"\bsk-(?!ant-)(?:live-|test-|proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b")),
    (
        "Env API key assignment",
        re.compile(
            r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_API_KEY|'
            r'GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY)["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'
        ),
    ),
    (
        "Env API key assignment",
        re.compile(
            r"(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_API_KEY|"
            r"GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY)[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')",
        ),
    ),
    (
        "Env API key assignment",
        re.compile(
            r'(?i)(\b(?:GEMINI_API_KEY|GOOGLE_API_KEY|GOOGLE_CLOUD_API_KEY|'
            r'GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY)["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
    ),
    (
        "API key field",
        re.compile(r'(?i)(\bapi_key["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]+(?=")'),
    ),
    (
        "API key field",
        re.compile(r"(?i)(\bapi_key[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]+(?=')"),
    ),
    (
        "API key field",
        re.compile(
            r'(?i)(\bapi_key["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]+)'
        ),
    ),
    (
        "URL query credential",
        re.compile(r"(?i)([?&](?:key|api_key|access_token|token)=)(?!\[REDACTED\b)[^&\s\"']+"),
    ),
    (
        "Credential key assignment",
        re.compile(r'(?i)(\bkey["\']?\s*[:=]\s*")(?!\[REDACTED\b)[^"\n]{16,}(?=")'),
    ),
    (
        "Credential key assignment",
        re.compile(r"(?i)(\bkey[\"']?\s*[:=]\s*')(?!\[REDACTED\b)[^'\n]{16,}(?=')"),
    ),
    (
        "Credential key assignment",
        re.compile(
            r'(?i)(\bkey["\']?\s*[:=]\s*)'
            r'(?!["\'\[\{]|\[REDACTED\b|(?:null|true|false|-?\d+(?:\.\d+)?)(?=[\s,}\]]|$))'
            r'([^\s"\'&,;{}]{16,})'
        ),
    ),
    (
        "PEM private key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
            r"(?:[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----)?"
        ),
    ),
)


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result with S8-redacted stdout and stderr."""

    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]
    not_found: bool = False
    timed_out: bool = False


@dataclass(frozen=True)
class HttpResult:
    """Captured HTTP response bytes with status and truncation flag."""

    status: int
    body: bytes
    truncated: bool
    final_url: str


RunnerCallable = Callable[[Sequence[str], int], CommandResult]
HttpFetchCallable = Callable[[str, Mapping[str, str], int, int], HttpResult]


# ---------------------------------------------------------------------------
# Capture-Time Secret Redaction & Leak Scanning (S8)
# ---------------------------------------------------------------------------


def redact_secrets(text: str) -> str:
    """Redact credentials, API keys, tokens, and PEM blocks at capture time (S8)."""
    if not text:
        return ""
    cleaned = text
    for label, pattern in SECRET_PATTERNS:
        if label == "URL query credential":
            cleaned = pattern.sub(r"\1[REDACTED]", cleaned)
        elif pattern.groups >= 1:
            cleaned = pattern.sub(rf"\1[REDACTED:{label}]", cleaned)
        else:
            cleaned = pattern.sub(f"[REDACTED:{label}]", cleaned)
    return cleaned


def redact_value(obj: Any) -> Any:
    """Recursively apply S8 secret redaction across nested JSON-compatible values."""
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, list):
        return [redact_value(item) for item in obj]
    if isinstance(obj, dict):
        return {redact_secrets(str(k)): redact_value(v) for k, v in obj.items()}
    return obj


def find_secret_leaks(obj: Any, path_prefix: str = "$") -> list[str]:
    """Scan nested JSON values for unredacted secret patterns."""
    hits: list[str] = []
    if isinstance(obj, str):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(obj):
                hits.append(f"{path_prefix}: matched {label}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(find_secret_leaks(item, f"{path_prefix}[{idx}]"))
    elif isinstance(obj, dict):
        for key, val in obj.items():
            hits.extend(find_secret_leaks(val, f"{path_prefix}.{key}"))
    return hits


def contract_home(path: Path | str) -> str:
    """Replace the active user's home prefix with ``~`` so paths stay portable (K7)."""
    resolved = str(Path(os.path.expanduser(str(path))).resolve())
    home = str(Path.home().resolve())
    if resolved == home:
        return "~"
    if resolved.startswith(home + os.sep):
        return "~/" + resolved[len(home) + 1 :].replace("\\", "/")
    return resolved.replace("\\", "/")


# ---------------------------------------------------------------------------
# URL, Repo, Token, and Path Confinement Validation
# ---------------------------------------------------------------------------


def _is_blocked_host(host: str, *, allow_loopback: bool) -> bool:
    raw = host.strip().lower().rstrip(".")
    if "%" in raw:
        return True
    bare = raw.strip("[]")
    if not bare or bare in BLOCKED_METADATA_HOSTS:
        return True
    if bare == "localhost" or bare.endswith(".localhost"):
        return not (allow_loopback and bare == "localhost")
    if bare.isdigit() or re.fullmatch(r"0x[0-9a-f]+", bare):
        return True
    try:
        ip_obj = ipaddress.ip_address(bare)
    except ValueError:
        if re.fullmatch(
            r"(?:0x[0-9a-f]+|0[0-7]*|[1-9]\d*)(?:\.(?:0x[0-9a-f]+|0[0-7]*|[1-9]\d*)){0,3}",
            bare,
        ):
            return True
        return False
    mapped = getattr(ip_obj, "ipv4_mapped", None)
    if mapped is not None:
        ip_obj = mapped
    if ip_obj.is_loopback:
        return not allow_loopback
    return (
        ip_obj.is_private
        or ip_obj.is_reserved
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_unspecified
        or ip_obj.is_multicast
        or not ip_obj.is_global
    )


def validate_http_digest_url(raw_url: str, *, allow_loopback: bool = True) -> str:
    """Validate an ``http_digest`` URL, blocking ``file://``, internal IPs, and external ``http://``."""
    raw_str = str(raw_url)
    if any(ord(ch) < 32 for ch in raw_str):
        raise ValueError("URL must be a single-line string without control characters.")
    cleaned = raw_str.strip()
    if not cleaned:
        raise ValueError("URL must be a non-empty string.")
    parsed = urllib.parse.urlsplit(cleaned)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not embed user credentials.")
    scheme = parsed.scheme.lower()
    raw_host = (parsed.hostname or "").lower()
    norm_host = raw_host.rstrip(".")
    if scheme == "https":
        if not norm_host or _is_blocked_host(raw_host, allow_loopback=allow_loopback):
            raise ValueError(f"Blocked or invalid HTTPS host in URL: {redact_secrets(cleaned)!r}")
        return cleaned
    if scheme == "http" and allow_loopback and norm_host in LOOPBACK_HOSTS:
        return cleaned
    raise ValueError(
        f"Insecure or disallowed URL scheme/host for http_digest ({redact_secrets(cleaned)!r}): "
        f"only https:// or loopback http://127.0.0.1 / http://localhost is permitted."
    )


def resolve_github_api_base(env: Mapping[str, str] | None = None) -> str:
    """Resolve ``FORGE_HORIZON_GITHUB_API_BASE`` allowing https, loopback http, or file://."""
    active_env = env if env is not None else os.environ
    raw_val = str(active_env.get("FORGE_HORIZON_GITHUB_API_BASE", ""))
    if any(ord(ch) < 32 for ch in raw_val):
        raise ValueError("FORGE_HORIZON_GITHUB_API_BASE contains control characters.")
    raw = raw_val.strip()
    if not raw:
        return DEFAULT_GITHUB_API_BASE
    parsed = urllib.parse.urlsplit(raw)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("FORGE_HORIZON_GITHUB_API_BASE must not embed credentials.")
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme == "https" and host and not _is_blocked_host(host, allow_loopback=True):
        return raw.rstrip("/")
    if scheme == "http" and host in LOOPBACK_HOSTS:
        return raw.rstrip("/")
    if scheme == "file" and parsed.path:
        return raw.rstrip("/")
    raise ValueError(
        f"Insecure FORGE_HORIZON_GITHUB_API_BASE={redact_secrets(raw)!r}: "
        f"only https://, loopback http://127.0.0.1 / http://localhost, or file:// is permitted."
    )


def validate_github_repo(repo: str) -> str:
    """Validate ``<owner>/<repo>`` slug."""
    cleaned = str(repo).strip()
    if not GITHUB_REPO_RE.fullmatch(cleaned):
        raise ValueError(f"Invalid GitHub repository slug {cleaned!r}; expected 'owner/repo'.")
    owner, name = cleaned.split("/", 1)
    if owner in (".", "..") or name in (".", ".."):
        raise ValueError(f"Invalid GitHub repository slug {cleaned!r}.")
    return cleaned


def validate_gh_pr_url(pr_url: str) -> str:
    """Validate canonical GitHub pull request URL ``https://github.com/<owner>/<repo>/pull/<n>``."""
    cleaned = str(pr_url).strip()
    match = GITHUB_PR_URL_RE.fullmatch(cleaned)
    if not match:
        raise ValueError(
            f"Invalid PR URL {redact_secrets(cleaned)!r}; expected "
            f"'https://github.com/<owner>/<repo>/pull/<number>'."
        )
    owner, repo, _num = match.groups()
    if owner in (".", "..") or repo in (".", ".."):
        raise ValueError(f"Invalid repository path in PR URL {redact_secrets(cleaned)!r}.")
    return cleaned.rstrip("/")


def validate_cli_help_tokens(binary: str, tokens: Sequence[str]) -> list[str]:
    """Validate allowlisted binary and safe ``cli_help`` subcommand/help tokens."""
    bin_clean = str(binary).strip()
    if bin_clean not in CLI_HELP_ALLOWLIST or "/" in bin_clean or "\\" in bin_clean:
        raise ValueError(
            f"Disallowed cli_help binary {bin_clean!r}; allowed: {sorted(CLI_HELP_ALLOWLIST)}"
        )
    validated: list[str] = []
    for raw_tok in tokens:
        tok = str(raw_tok).strip()
        if not tok or not SAFE_CLI_TOKEN_RE.fullmatch(tok):
            raise ValueError(f"Unsafe cli_help token {tok!r}; must match {SAFE_CLI_TOKEN_RE.pattern}")
        if tok.startswith("-") and tok not in ALLOWED_CLI_FLAGS:
            raise ValueError(
                f"Disallowed option flag {tok!r} in cli_help; only {sorted(ALLOWED_CLI_FLAGS)} allowed."
            )
        validated.append(tok)
    if not any(tok in ("--help", "-h") for tok in validated):
        validated.append("--help")
    return validated


def resolve_repo_relative_path(repo_root: Path, relpath: str) -> Path:
    """Resolve ``relpath`` strictly inside ``repo_root`` (CWE-22 / symlink confinement)."""
    raw = str(relpath).strip()
    if not raw or "\x00" in raw:
        raise ValueError("Empty or null-byte file_anchor path.")
    candidate_rel = Path(raw)
    if candidate_rel.is_absolute() or raw.startswith("~"):
        raise ValueError(f"Repo-scoped file_anchor path must be relative, got {raw!r}.")
    root_resolved = repo_root.resolve()
    resolved = (root_resolved / candidate_rel).resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"Path traversal or symlink escape blocked for {raw!r}.")
    return resolved


def resolve_global_config_path(
    raw_path: str,
    allowed_roots: Sequence[Path],
    *,
    must_exist: bool = True,
) -> Path:
    """Confine a global config file path to ``allowed_roots`` (default ``~/.gemini``)."""
    cleaned = str(raw_path).strip()
    if not cleaned or "\x00" in cleaned:
        raise ValueError("Target path must be non-empty and free of null bytes.")
    expanded = Path(os.path.expanduser(cleaned))
    try:
        resolved = expanded.resolve(strict=must_exist)
    except OSError as exc:
        raise ValueError(f"Target path {contract_home(expanded)!r} does not exist or is unreadable: {exc}") from None

    roots_resolved = [Path(os.path.expanduser(str(r))).resolve() for r in allowed_roots]
    if not any(resolved.is_relative_to(root) for root in roots_resolved):
        raise ValueError(
            f"Target path {contract_home(resolved)!r} escapes allowed root(s) "
            f"{[contract_home(r) for r in roots_resolved]}."
        )
    if must_exist and not resolved.is_file():
        raise ValueError(f"Target path {contract_home(resolved)!r} is not a regular file.")
    return resolved


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Probe field '{field_name}' must be a list of strings.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"Probe field '{field_name}' entries must be non-empty strings.")
        result.append(item)
    return result


def validate_probe_spec(probe: Any, index: int = 0) -> dict[str, Any]:
    """Validate and normalize one probe definition from a ledger item."""
    if not isinstance(probe, dict):
        raise ValueError(f"probes[{index}] must be a JSON object.")
    kind = str(probe.get("kind", "")).strip()
    if kind not in PROBE_KINDS:
        raise ValueError(f"probes[{index}].kind={kind!r} invalid; expected one of {sorted(PROBE_KINDS)}.")

    if kind == "cli_help":
        binary = str(probe.get("binary", "")).strip()
        raw_tokens: list[str] = []
        if "args" in probe and probe["args"] is not None:
            if not isinstance(probe["args"], list):
                raise ValueError(f"probes[{index}].args must be a list of tokens.")
            raw_tokens = [str(x) for x in probe["args"]]
        elif "subcommand" in probe and probe["subcommand"] is not None:
            sub = probe["subcommand"]
            if isinstance(sub, list):
                raw_tokens = [str(x) for x in sub]
            elif isinstance(sub, str):
                raw_tokens = [part for part in sub.split() if part]
            else:
                raise ValueError(f"probes[{index}].subcommand must be a string or list.")
        tokens = validate_cli_help_tokens(binary, raw_tokens)
        expect_tokens = _normalize_string_list(probe.get("expect_tokens"), "expect_tokens")
        out: dict[str, Any] = {
            "kind": "cli_help",
            "binary": binary,
            "args": tokens,
            "expect_tokens": expect_tokens,
        }
        if probe.get("baseline_output_sha256"):
            out["baseline_output_sha256"] = str(probe["baseline_output_sha256"]).strip()
        return out

    if kind == "github_release":
        repo = validate_github_repo(str(probe.get("repo", "")))
        out = {"kind": "github_release", "repo": repo}
        if probe.get("baseline_tag") is not None:
            out["baseline_tag"] = str(probe["baseline_tag"]).strip()
        return out

    if kind == "http_digest":
        url = validate_http_digest_url(str(probe.get("url", "")))
        expect_tokens = _normalize_string_list(probe.get("expect_tokens"), "expect_tokens")
        out = {"kind": "http_digest", "url": url, "expect_tokens": expect_tokens}
        if probe.get("baseline_sha256") is not None:
            out["baseline_sha256"] = str(probe["baseline_sha256"]).strip()
        return out

    if kind == "file_anchor":
        raw_path = str(probe.get("path") or probe.get("relpath") or "").strip()
        anchor_literal = str(probe.get("anchor_literal", ""))
        if not raw_path or "\x00" in raw_path:
            raise ValueError(f"probes[{index}].path must be a non-empty string.")
        if not anchor_literal:
            raise ValueError(f"probes[{index}].anchor_literal must be a non-empty string.")
        default_scope = "global_config" if raw_path.startswith("~") else "repo"
        scope = str(probe.get("scope") or default_scope).strip()
        if scope not in FILE_ANCHOR_SCOPES:
            raise ValueError(
                f"probes[{index}].scope={scope!r} invalid; expected {sorted(FILE_ANCHOR_SCOPES)}."
            )
        if scope == "repo":
            parts = Path(raw_path).parts
            if Path(raw_path).is_absolute() or raw_path.startswith("~") or ".." in parts:
                raise ValueError(f"probes[{index}].path={raw_path!r} must stay confined inside repo_root.")
        elif ".." in Path(raw_path).parts:
            raise ValueError(f"probes[{index}].path={raw_path!r} must not contain '..' traversal.")
        out = {
            "kind": "file_anchor",
            "scope": scope,
            "path": raw_path,
            "anchor_literal": anchor_literal,
        }
        if probe.get("baseline_sha256") is not None:
            out["baseline_sha256"] = str(probe["baseline_sha256"]).strip()
        return out

    if kind == "gh_pr_status":
        pr_url = validate_gh_pr_url(str(probe.get("pr_url", "")))
        return {"kind": "gh_pr_status", "pr_url": pr_url}

    # kind == "agent_query"
    source = str(probe.get("source", "")).strip()
    query = str(probe.get("query", "")).strip()
    if not source or not query:
        raise ValueError(f"probes[{index}] agent_query requires non-empty 'source' and 'query'.")
    return {"kind": "agent_query", "source": source, "query": query}


# ---------------------------------------------------------------------------
# Subprocess & HTTP Runners (S4, S8)
# ---------------------------------------------------------------------------


def default_runner(
    argv: Sequence[str],
    timeout: int = DEFAULT_TIMEOUT_S,
    *,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run ``argv`` with ``shell=False``, timeout, and capture-time S8 redaction."""
    if isinstance(argv, (str, bytes)) or not argv:
        raise ValueError("Subprocess argv must be a non-empty list/tuple of strings (S4).")
    cmd_tuple = tuple(str(part) for part in argv)
    try:
        proc = subprocess.run(
            list(cmd_tuple),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=dict(env) if env is not None else None,
        )
        return CommandResult(
            returncode=proc.returncode,
            stdout=redact_secrets(proc.stdout or ""),
            stderr=redact_secrets(proc.stderr or ""),
            argv=cmd_tuple,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            returncode=127,
            stdout="",
            stderr=redact_secrets(f"Command not found: {cmd_tuple[0]} ({exc})"),
            argv=cmd_tuple,
            not_found=True,
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = (
            exc.stdout.decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else str(exc.stdout or "")
        )
        return CommandResult(
            returncode=124,
            stdout=redact_secrets(raw_out),
            stderr=redact_secrets(f"Command timed out after {timeout}s: {cmd_tuple[0]}"),
            argv=cmd_tuple,
            timed_out=True,
        )


def _validate_redirect_target(
    abs_url: str,
    *,
    allow_loopback: bool,
    addrinfo_fn: Callable[..., list[Any]] | None = None,
) -> str:
    """Validate redirect URL scheme, host literal, and DNS-resolved IP addresses."""
    validated = validate_http_digest_url(abs_url, allow_loopback=allow_loopback)
    parsed = urllib.parse.urlsplit(validated)
    host = (parsed.hostname or "").strip().rstrip(".")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    resolver = addrinfo_fn if addrinfo_fn is not None else socket.getaddrinfo
    try:
        resolved_entries = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return validated
    for entry in resolved_entries:
        sockaddr = entry[4]
        resolved_ip = str(sockaddr[0]).split("%", 1)[0]
        if _is_blocked_host(resolved_ip, allow_loopback=allow_loopback):
            raise ValueError(
                f"Blocked redirect target resolving to disallowed address {resolved_ip!r}: "
                f"{redact_secrets(validated)!r}"
            )
    return validated


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects to disallowed schemes, internal IPs, or blocked DNS targets."""

    def __init__(
        self,
        *,
        allow_loopback: bool,
        addrinfo_fn: Callable[..., list[Any]] | None = None,
    ) -> None:
        self.allow_loopback = allow_loopback
        self.addrinfo_fn = addrinfo_fn

    def http_error_302(self, req, fp, code, msg, headers):
        target = headers.get("location") or headers.get("uri")
        if target:
            abs_url = urllib.parse.urljoin(req.full_url, target)
            _validate_redirect_target(
                abs_url, allow_loopback=self.allow_loopback, addrinfo_fn=self.addrinfo_fn
            )
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        abs_url = urllib.parse.urljoin(req.full_url, newurl)
        _validate_redirect_target(
            abs_url, allow_loopback=self.allow_loopback, addrinfo_fn=self.addrinfo_fn
        )
        return super().redirect_request(req, fp, code, msg, headers, abs_url)


def default_http_fetch(
    url: str,
    headers: Mapping[str, str],
    timeout: int = DEFAULT_TIMEOUT_S,
    max_bytes: int = MAX_HTTP_BYTES,
    *,
    extra_handlers: Sequence[urllib.request.BaseHandler] = (),
) -> HttpResult:
    """Fetch ``url`` with safe redirect validation and bounded byte read."""
    validated_url = validate_http_digest_url(url)
    host = (urllib.parse.urlsplit(validated_url).hostname or "").lower().rstrip(".")
    is_loopback = host in LOOPBACK_HOSTS
    req = urllib.request.Request(url=validated_url, method="GET")
    for key, val in headers.items():
        req.add_header(key, val)
    handlers: list[urllib.request.BaseHandler] = [_SafeRedirectHandler(allow_loopback=is_loopback)]
    if is_loopback:
        handlers.append(urllib.request.ProxyHandler({}))
    handlers.extend(extra_handlers)
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            status = int(getattr(resp, "status", None) or resp.getcode() or 200)
            final_url = redact_secrets(str(resp.geturl() or validated_url))
            return HttpResult(
                status=status,
                body=raw[:max_bytes],
                truncated=truncated,
                final_url=final_url,
            )
    except urllib.error.HTTPError as exc:
        err_bytes = exc.read(4096) if hasattr(exc, "read") else b""
        err_text = redact_secrets(err_bytes.decode("utf-8", errors="replace"))
        raise RuntimeError(
            f"HTTP {exc.code} from {redact_secrets(validated_url)}: "
            f"{err_text[:400] or redact_secrets(str(exc))}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error fetching {redact_secrets(validated_url)}: "
            f"{redact_secrets(str(exc.reason))}"
        ) from exc


# ---------------------------------------------------------------------------
# Individual Mechanical Probe Collectors (S9, V5)
# ---------------------------------------------------------------------------


def collect_cli_help(
    item_id: str,
    probe: Mapping[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
    runner: RunnerCallable | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Execute allowlisted CLI ``--help`` and collect digest + token presence."""
    binary = str(probe["binary"]).strip()
    tokens = validate_cli_help_tokens(binary, probe.get("args", []))
    expect_tokens = [str(t) for t in probe.get("expect_tokens", [])]
    baseline_sha = str(probe.get("baseline_output_sha256") or "").strip() or None
    argv = [binary, *tokens]

    path_var = (env or os.environ).get("PATH")
    if runner is None and shutil.which(binary, path=path_var) is None:
        result = {
            "kind": "cli_help",
            "binary": binary,
            "argv": argv,
            "available": False,
            "returncode": None,
            "output_sha256": None,
            "matched_tokens": [],
            "missing_tokens": list(expect_tokens),
            "changed_vs_baseline": None,
            "error": f"Binary '{binary}' not found on PATH.",
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "cli_help",
            "what": f"cli_help:{binary}",
            "reason": f"Binary '{binary}' not installed on PATH.",
        }
        return result, not_inspected

    exec_fn = runner if runner is not None else (lambda cmd, t: default_runner(cmd, timeout=t, env=env))
    proc = exec_fn(argv, timeout)
    if proc.not_found or proc.timed_out:
        reason = proc.stderr or ("Timed out" if proc.timed_out else "Command not found")
        result = {
            "kind": "cli_help",
            "binary": binary,
            "argv": argv,
            "available": False,
            "returncode": proc.returncode,
            "output_sha256": None,
            "matched_tokens": [],
            "missing_tokens": list(expect_tokens),
            "changed_vs_baseline": None,
            "error": redact_secrets(reason),
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "cli_help",
            "what": f"cli_help:{binary}",
            "reason": redact_secrets(reason),
        }
        return result, not_inspected

    combined = redact_secrets(f"{proc.stdout}\n{proc.stderr}".strip())
    output_sha256 = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    matched = [tok for tok in expect_tokens if tok in combined]
    missing = [tok for tok in expect_tokens if tok not in combined]
    changed = (output_sha256 != baseline_sha) if baseline_sha else None
    result = {
        "kind": "cli_help",
        "binary": binary,
        "argv": argv,
        "available": True,
        "returncode": proc.returncode,
        "output_sha256": output_sha256,
        "matched_tokens": matched,
        "missing_tokens": missing,
        "changed_vs_baseline": changed,
        "error": None,
    }
    return result, None


def _read_local_github_release(api_base: str, repo: str, max_bytes: int) -> HttpResult:
    parsed = urllib.parse.urlsplit(api_base)
    base_dir = Path(urllib.request.url2pathname(parsed.path)).resolve()
    rel_candidates = (
        Path("repos") / repo / "releases" / "latest",
        Path("repos") / repo / "releases" / "latest.json",
    )
    target_file: Path | None = None
    for rel in rel_candidates:
        cand = (base_dir / rel).resolve()
        if not cand.is_relative_to(base_dir):
            raise ValueError(f"Path escape blocked in file:// GitHub API base: {cand}")
        if cand.is_file():
            target_file = cand
            break
    if target_file is None:
        raise RuntimeError(f"Fixture release file not found under {base_dir} for {repo}.")
    raw = target_file.read_bytes()[: max_bytes + 1]
    return HttpResult(
        status=200,
        body=raw[:max_bytes],
        truncated=len(raw) > max_bytes,
        final_url=f"{api_base}/repos/{repo}/releases/latest",
    )


def collect_github_release(
    item_id: str,
    probe: Mapping[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
    http_fetcher: HttpFetchCallable | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Query latest GitHub release metadata (or ``FORGE_HORIZON_GITHUB_API_BASE``)."""
    repo = validate_github_repo(str(probe["repo"]))
    baseline_tag = str(probe.get("baseline_tag") or "").strip() or None
    api_base = resolve_github_api_base(env)
    url = f"{api_base}/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agent-skill-forge-horizon/1.0",
    }

    try:
        if api_base.startswith("file://"):
            resp = _read_local_github_release(api_base, repo, MAX_HTTP_BYTES)
        else:
            fetcher = http_fetcher if http_fetcher is not None else default_http_fetch
            resp = fetcher(url, headers, timeout, MAX_HTTP_BYTES)
        payload = json.loads(resp.body.decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            raise ValueError("GitHub release response is not a JSON object.")
    except ValueError:
        raise
    except Exception as exc:
        err_msg = redact_secrets(str(exc))
        status_match = re.search(r"\bHTTP (\d{3})\b", err_msg)
        http_status = int(status_match.group(1)) if status_match else None
        result = {
            "kind": "github_release",
            "repo": repo,
            "url": redact_secrets(url),
            "available": False,
            "http_status": http_status,
            "tag_name": None,
            "published_at": None,
            "asset_names": [],
            "baseline_tag": baseline_tag,
            "tag_changed_vs_baseline": False,
            "error": err_msg,
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "github_release",
            "what": f"github_release:{repo}",
            "reason": err_msg,
        }
        return result, not_inspected

    tag_name = redact_secrets(str(payload.get("tag_name") or "").strip()) or None
    published_at = redact_secrets(str(payload.get("published_at") or "").strip()) or None
    raw_assets = payload.get("assets") or []
    asset_names = [
        redact_secrets(str(asset["name"]))
        for asset in raw_assets
        if isinstance(asset, dict) and asset.get("name")
    ]
    tag_changed = bool(baseline_tag and tag_name and tag_name != baseline_tag)
    result = {
        "kind": "github_release",
        "repo": repo,
        "url": redact_secrets(resp.final_url),
        "available": True,
        "http_status": resp.status,
        "tag_name": tag_name,
        "published_at": published_at,
        "asset_names": asset_names,
        "baseline_tag": baseline_tag,
        "tag_changed_vs_baseline": tag_changed,
        "error": None,
    }
    return result, None


def collect_http_digest(
    item_id: str,
    probe: Mapping[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
    http_fetcher: HttpFetchCallable | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Fetch bounded HTTPS (or loopback HTTP) page and record SHA-256 + token presence."""
    url = validate_http_digest_url(str(probe["url"]))
    expect_tokens = [str(t) for t in probe.get("expect_tokens", [])]
    baseline_sha = str(probe.get("baseline_sha256") or "").strip() or None
    headers = {"User-Agent": "agent-skill-forge-horizon/1.0"}

    try:
        fetcher = http_fetcher if http_fetcher is not None else default_http_fetch
        resp = fetcher(url, headers, timeout, MAX_HTTP_BYTES)
    except ValueError:
        raise
    except Exception as exc:
        err_msg = redact_secrets(str(exc))
        status_match = re.search(r"\bHTTP (\d{3})\b", err_msg)
        http_status = int(status_match.group(1)) if status_match else None
        result = {
            "kind": "http_digest",
            "url": redact_secrets(url),
            "available": False,
            "http_status": http_status,
            "content_sha256": None,
            "bytes_read": 0,
            "truncated": False,
            "baseline_sha256": baseline_sha,
            "changed_vs_baseline": False,
            "matched_tokens": [],
            "missing_tokens": list(expect_tokens),
            "error": err_msg,
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "http_digest",
            "what": f"http_digest:{redact_secrets(url)}",
            "reason": err_msg,
        }
        return result, not_inspected

    content_sha256 = hashlib.sha256(resp.body).hexdigest()
    text = redact_secrets(resp.body.decode("utf-8", errors="replace"))
    matched = [tok for tok in expect_tokens if tok in text]
    missing = [tok for tok in expect_tokens if tok not in text]
    changed = bool(baseline_sha and content_sha256 != baseline_sha)
    result = {
        "kind": "http_digest",
        "url": redact_secrets(resp.final_url),
        "available": True,
        "http_status": resp.status,
        "content_sha256": content_sha256,
        "bytes_read": len(resp.body),
        "truncated": resp.truncated,
        "baseline_sha256": baseline_sha,
        "changed_vs_baseline": changed,
        "matched_tokens": matched,
        "missing_tokens": missing,
        "error": None,
    }
    return result, None


def collect_file_anchor(
    probe: Mapping[str, Any],
    *,
    repo_root: Path,
    allow_roots: Sequence[Path],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Inspect a confined repo or global_config file for SHA-256 and substring anchor."""
    raw_path = str(probe.get("path") or probe.get("relpath") or "").strip()
    anchor_literal = str(probe.get("anchor_literal", ""))
    scope = str(probe.get("scope") or ("global_config" if raw_path.startswith("~") else "repo")).strip()
    baseline_sha = str(probe.get("baseline_sha256") or "").strip() or None

    if scope == "repo":
        resolved = resolve_repo_relative_path(repo_root, raw_path)
        display_path = raw_path
    elif scope == "global_config":
        resolved = resolve_global_config_path(raw_path, allow_roots, must_exist=False)
        display_path = contract_home(resolved)
    else:
        raise ValueError(f"Unsupported file_anchor scope: {scope!r}")

    if not resolved.exists() or not resolved.is_file():
        return {
            "kind": "file_anchor",
            "scope": scope,
            "path": display_path,
            "exists": False,
            "file_sha256": None,
            "truncated": False,
            "anchor_literal": anchor_literal,
            "anchor_found": False,
            "changed_vs_baseline": False,
            "error": None,
        }, None

    with resolved.open("rb") as fh:
        raw_read = fh.read(MAX_HTTP_BYTES + 1)
    truncated = len(raw_read) > MAX_HTTP_BYTES
    raw_bytes = raw_read[:MAX_HTTP_BYTES]
    file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8", errors="replace")
    anchor_found = anchor_literal in text
    changed = bool(baseline_sha and file_sha256 != baseline_sha)
    return {
        "kind": "file_anchor",
        "scope": scope,
        "path": display_path,
        "exists": True,
        "file_sha256": file_sha256,
        "truncated": truncated,
        "anchor_literal": anchor_literal,
        "anchor_found": anchor_found,
        "changed_vs_baseline": changed,
        "error": None,
    }, None


def collect_gh_pr_status(
    item_id: str,
    pr_url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
    runner: RunnerCallable | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Inspect GitHub PR merge state via ``gh pr view --json state,mergedAt,url -- <pr_url>``."""
    canonical_url = validate_gh_pr_url(pr_url)
    argv = ["gh", "pr", "view", "--json", "state,mergedAt,url", "--", canonical_url]
    path_var = (env or os.environ).get("PATH")
    if runner is None and shutil.which("gh", path=path_var) is None:
        result = {
            "kind": "gh_pr_status",
            "pr_url": canonical_url,
            "available": False,
            "state": None,
            "merged_at": None,
            "url": canonical_url,
            "error": "gh CLI not found on PATH.",
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "gh_pr_status",
            "what": f"gh_pr_status:{canonical_url}",
            "reason": "gh CLI not installed on PATH.",
        }
        return result, not_inspected

    exec_fn = runner if runner is not None else (lambda cmd, t: default_runner(cmd, timeout=t, env=env))
    proc = exec_fn(argv, timeout)
    if proc.returncode != 0 or proc.not_found or proc.timed_out:
        err_msg = redact_secrets(proc.stderr or proc.stdout or f"gh pr view exited {proc.returncode}")
        result = {
            "kind": "gh_pr_status",
            "pr_url": canonical_url,
            "available": False,
            "state": None,
            "merged_at": None,
            "url": canonical_url,
            "error": err_msg,
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "gh_pr_status",
            "what": f"gh_pr_status:{canonical_url}",
            "reason": err_msg,
        }
        return result, not_inspected

    try:
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            raise ValueError("gh pr view output was not a JSON object.")
    except (json.JSONDecodeError, ValueError) as exc:
        err_msg = redact_secrets(f"Invalid JSON from gh pr view: {exc}")
        result = {
            "kind": "gh_pr_status",
            "pr_url": canonical_url,
            "available": False,
            "state": None,
            "merged_at": None,
            "url": canonical_url,
            "error": err_msg,
        }
        not_inspected = {
            "item_id": item_id,
            "probe_kind": "gh_pr_status",
            "what": f"gh_pr_status:{canonical_url}",
            "reason": err_msg,
        }
        return result, not_inspected

    return {
        "kind": "gh_pr_status",
        "pr_url": canonical_url,
        "available": True,
        "state": str(payload.get("state") or "").upper() or None,
        "merged_at": payload.get("mergedAt"),
        "url": redact_secrets(str(payload.get("url") or canonical_url)),
        "error": None,
    }, None


def collect_agent_query(
    item_id: str,
    probe: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Record metadata for MCP/model-catalogue probes requiring agent evaluation (V5)."""
    source = redact_secrets(str(probe.get("source", "")).strip())
    query = redact_secrets(str(probe.get("query", "")).strip())
    if not source or not query:
        raise ValueError("agent_query requires non-empty 'source' and 'query'.")
    result = {
        "kind": "agent_query",
        "source": source,
        "query": query,
        "status": "requires_agent_eval",
        "available": False,
    }
    not_inspected = {
        "item_id": item_id,
        "probe_kind": "agent_query",
        "what": f"agent_query:{source}",
        "reason": "requires_agent_eval (cannot execute MCP or model-catalogue query mechanically)",
    }
    return result, not_inspected


def run_probe(
    item_id: str,
    probe: Mapping[str, Any],
    *,
    repo_root: Path,
    allow_roots: Sequence[Path],
    timeout: int = DEFAULT_TIMEOUT_S,
    runner: RunnerCallable | None = None,
    http_fetcher: HttpFetchCallable | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Dispatch one validated probe spec to its factual collector."""
    kind = str(probe.get("kind", "")).strip()
    if kind == "cli_help":
        return collect_cli_help(item_id, probe, timeout=timeout, runner=runner, env=env)
    if kind == "github_release":
        return collect_github_release(item_id, probe, timeout=timeout, http_fetcher=http_fetcher, env=env)
    if kind == "http_digest":
        return collect_http_digest(item_id, probe, timeout=timeout, http_fetcher=http_fetcher)
    if kind == "file_anchor":
        return collect_file_anchor(probe, repo_root=repo_root, allow_roots=allow_roots)
    if kind == "gh_pr_status":
        return collect_gh_pr_status(
            item_id, str(probe.get("pr_url", "")), timeout=timeout, runner=runner, env=env
        )
    if kind == "agent_query":
        return collect_agent_query(item_id, probe)
    raise ValueError(f"Unknown probe kind: {kind!r}")
