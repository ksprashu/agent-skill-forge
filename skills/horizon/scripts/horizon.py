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

"""Stdlib-only Horizon Sentinel CLI engine for skills/horizon.

Turns 6-12 month technical and AI forecasts into a central machine-wide ledger
(``~/.gemini/horizons/`` by default, overridable via ``--ledger-dir`` or
``$FORGE_HORIZONS_DIR``), executes mechanical upstream/anchor probes into
``evidence.json`` (S9), validates LLM/MCP sweep verdicts (``verdict.json``,
V1-V6), enforces SHA-256 pre-edit backups for ``global_config`` targets and PR
URL provenance for ``repo_branch_pr`` targets, and renders deterministic
``INDEX.md`` tables.

What ``validate-verdict`` audits (V3):
  Schema version, known unique item IDs, allowed decision enums, non-empty
  ``evidence_citations`` + ``summary`` on triggered/supersede decisions,
  two-way ``triggered_count`` consistency, absence of unredacted secret leaks,
  and ``not_inspected`` parity against ``evidence.json``.

What ``validate-verdict`` does NOT audit (V5):
  Whether an agent's semantic interpretation of a release note or forecast
  prose is true in the real world.

Exit codes:
  0  Success / valid / up-to-date
  1  Verification failure, gate refusal, corrupt ledger, or stale INDEX.md
  2  Invalid CLI usage, bad payload schema, insecure URL, or confined path escape
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]

try:  # pragma: no cover - POSIX omits msvcrt
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

if sys.platform == "win32":  # pragma: no cover - Windows console encoding guard
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import horizon_probes  # noqa: E402

# ---------------------------------------------------------------------------
# Constants & Schemas
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1"
DEFAULT_LEDGER_SUBDIR = Path(".gemini") / "horizons"

ITEM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
BACKUP_FILENAME_RE = re.compile(r"^(\d{8}T\d{6,12}Z)_([0-9a-f]{12})_(.+)$")

VALID_STATUSES: tuple[str, ...] = (
    "watching",
    "triggered",
    "pr_opened",
    "landed",
    "superseded",
)
ACTION_TRANSITION_STATUSES: tuple[str, ...] = (
    "triggered",
    "pr_opened",
    "landed",
    "superseded",
)
ACTIVE_PROBE_STATUSES: frozenset[str] = frozenset({"watching", "pr_opened"})

VALID_TARGET_KINDS: frozenset[str] = frozenset({"repo_branch_pr", "global_config"})
VALID_DECISIONS: frozenset[str] = frozenset(
    {"no_change", "drop_confirmed", "target_drifted", "supersede"}
)
TRIGGERED_DECISIONS: frozenset[str] = frozenset(
    {"drop_confirmed", "target_drifted", "supersede"}
)

REQUIRED_ITEM_TEXT_FIELDS: tuple[str, ...] = (
    "title",
    "window",
    "baseline_measurement",
    "forecast",
    "playbook",
)


class CliUsageError(ValueError):
    """Raised on invalid CLI arguments, schemas, or unsafe paths (exit 2)."""


class ValidationFailure(RuntimeError):
    """Raised on corrupt ledger, failing verdict checks, or closed L3 gates (exit 1)."""


# ---------------------------------------------------------------------------
# Time, Directory, and Atomic File Helpers
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Return current UTC timestamp in canonical ISO-8601 ``Z`` format."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_timestamp_slug() -> str:
    """Return filename-safe UTC timestamp slug including microseconds."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def resolve_ledger_dir(
    cli_dir: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve central ledger directory: ``--ledger-dir`` -> ``$FORGE_HORIZONS_DIR`` -> ``~/.gemini/horizons``."""
    active_env = env if env is not None else os.environ
    raw = (cli_dir or "").strip() or str(active_env.get("FORGE_HORIZONS_DIR", "")).strip()
    if raw:
        return Path(os.path.expanduser(raw)).resolve()
    return (Path.home() / DEFAULT_LEDGER_SUBDIR).resolve()


def ensure_secure_dir(path: Path) -> Path:
    """Create directory if missing and enforce ``0o700`` permissions on POSIX."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Atomically write ``data`` to ``path`` via sibling temp file and ``os.replace``."""
    ensure_secure_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        if os.name == "posix":
            os.chmod(path, mode)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    """Atomically write UTF-8 text to ``path`` with ``0o600`` permissions."""
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


@contextlib.contextmanager
def ledger_lock(ledger_dir: Path) -> Iterator[None]:
    """Serialize read-modify-write transitions on ``<ledger_dir>/.ledger.lock``."""
    ensure_secure_dir(ledger_dir)
    lock_path = ledger_dir / ".ledger.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    if os.name == "posix":
        os.chmod(lock_path, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows locking
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        yield
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows locking
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


# ---------------------------------------------------------------------------
# Ledger & Target Validation
# ---------------------------------------------------------------------------


def validate_item_id(raw_id: Any) -> str:
    """Validate slug ``^[a-z0-9][a-z0-9-]{2,63}$``."""
    slug = str(raw_id or "").strip()
    if not ITEM_ID_RE.fullmatch(slug):
        raise CliUsageError(
            f"Invalid item id {slug!r}; must match {ITEM_ID_RE.pattern} (3-64 lowercase chars/digits/hyphens)."
        )
    return slug


def validate_target_spec(target: Any, index: int = 0) -> dict[str, Any]:
    """Validate and normalize one target dictionary (``repo_branch_pr`` or ``global_config``)."""
    if not isinstance(target, dict):
        raise CliUsageError(f"targets[{index}] must be a JSON object.")
    kind = str(target.get("kind", "")).strip()
    if kind not in VALID_TARGET_KINDS:
        raise CliUsageError(
            f"targets[{index}].kind={kind!r} invalid; expected one of {sorted(VALID_TARGET_KINDS)}."
        )
    if kind == "repo_branch_pr":
        repo = str(target.get("repo", "")).strip()
        rel_path = str(target.get("path", "")).strip()
        if not repo and not rel_path:
            raise CliUsageError(f"targets[{index}] repo_branch_pr requires 'repo' or 'path'.")
        if rel_path and ("\x00" in rel_path or ".." in Path(rel_path).parts):
            raise CliUsageError(f"targets[{index}].path={rel_path!r} contains unsafe traversal.")
        out: dict[str, Any] = {"kind": "repo_branch_pr"}
        if repo:
            out["repo"] = horizon_probes.redact_secrets(repo)
        if rel_path:
            out["path"] = horizon_probes.redact_secrets(rel_path)
        if target.get("branch"):
            out["branch"] = horizon_probes.redact_secrets(str(target["branch"]).strip())
        return out

    raw_path = str(target.get("path", "")).strip()
    if not raw_path or "\x00" in raw_path or ".." in Path(raw_path).parts:
        raise CliUsageError(f"targets[{index}] global_config requires a safe non-empty 'path'.")
    return {"kind": "global_config", "path": horizon_probes.redact_secrets(raw_path)}


def validate_record_payload(raw: Any) -> dict[str, Any]:
    """Validate a ``record`` payload and enforce probe/target/S8 contracts (exit 2 on error)."""
    if not isinstance(raw, dict):
        raise CliUsageError("Record payload must be a JSON object.")
    item_id = validate_item_id(raw.get("id"))
    cleaned: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "id": item_id}

    for field in REQUIRED_ITEM_TEXT_FIELDS:
        val = raw.get(field)
        if not isinstance(val, str) or not val.strip():
            raise CliUsageError(f"Missing or empty required field '{field}'.")
        cleaned[field] = horizon_probes.redact_secrets(val.strip())

    category = raw.get("category", "general")
    if not isinstance(category, str) or not category.strip():
        raise CliUsageError("Field 'category' must be a non-empty string.")
    cleaned["category"] = horizon_probes.redact_secrets(category.strip())

    source = raw.get("source", "manual")
    if not isinstance(source, str) or not source.strip():
        raise CliUsageError("Field 'source' must be a non-empty string.")
    cleaned["source"] = horizon_probes.redact_secrets(source.strip())

    raw_probes = raw.get("probes")
    if not isinstance(raw_probes, list) or not raw_probes:
        raise CliUsageError("Field 'probes' must be a non-empty array of probe objects.")
    validated_probes: list[dict[str, Any]] = []
    for idx, probe in enumerate(raw_probes):
        try:
            validated_probes.append(horizon_probes.validate_probe_spec(probe, idx))
        except ValueError as exc:
            raise CliUsageError(str(exc)) from exc
    cleaned["probes"] = horizon_probes.redact_value(validated_probes)

    raw_targets = raw.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise CliUsageError("Field 'targets' must be a non-empty array of target objects.")
    cleaned["targets"] = [validate_target_spec(t, idx) for idx, t in enumerate(raw_targets)]
    return cleaned


def validate_ledger_item(obj: Any, line_no: int = 1) -> dict[str, Any]:
    """Validate a single line parsed from ``ledger.jsonl`` (fail-closed)."""
    if not isinstance(obj, dict):
        raise ValidationFailure(f"ledger.jsonl line {line_no}: expected JSON object.")
    try:
        item_id = validate_item_id(obj.get("id"))
    except CliUsageError as exc:
        raise ValidationFailure(f"ledger.jsonl line {line_no}: {exc}") from exc

    status = str(obj.get("status", "")).strip()
    if status not in VALID_STATUSES:
        raise ValidationFailure(
            f"ledger.jsonl line {line_no} ({item_id}): invalid status {status!r}."
        )
    revision = obj.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValidationFailure(
            f"ledger.jsonl line {line_no} ({item_id}): revision must be an integer >= 1."
        )
    for field in REQUIRED_ITEM_TEXT_FIELDS:
        val = obj.get(field)
        if not isinstance(val, str) or not val.strip():
            raise ValidationFailure(
                f"ledger.jsonl line {line_no} ({item_id}): missing/empty '{field}'."
            )

    raw_probes = obj.get("probes")
    if not isinstance(raw_probes, list) or not raw_probes:
        raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): empty or invalid 'probes'.")
    for idx, probe in enumerate(raw_probes):
        try:
            horizon_probes.validate_probe_spec(probe, idx)
        except ValueError as exc:
            raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): {exc}") from exc

    raw_targets = obj.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): empty or invalid 'targets'.")
    for idx, tgt in enumerate(raw_targets):
        try:
            validate_target_spec(tgt, idx)
        except CliUsageError as exc:
            raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): {exc}") from exc

    if not isinstance(obj.get("history", []), list):
        raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): 'history' must be a list.")
    if obj.get("pr_url"):
        try:
            horizon_probes.validate_gh_pr_url(str(obj["pr_url"]))
        except ValueError as exc:
            raise ValidationFailure(f"ledger.jsonl line {line_no} ({item_id}): {exc}") from exc
    return obj


def load_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    """Load and strictly validate ``ledger.jsonl``. Fails closed on corruption or duplicate IDs."""
    if not ledger_path.exists():
        return []
    try:
        raw_text = ledger_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationFailure(f"Cannot read ledger {ledger_path}: {exc}") from exc

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_no, raw_line in enumerate(raw_text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValidationFailure(f"ledger.jsonl line {line_no}: corrupt JSON ({exc}).") from exc
        validated = validate_ledger_item(parsed, line_no=line_no)
        item_id = validated["id"]
        if item_id in seen_ids:
            raise ValidationFailure(f"ledger.jsonl line {line_no}: duplicate item id {item_id!r}.")
        seen_ids.add(item_id)
        items.append(validated)
    return items


def save_ledger(ledger_dir: Path, items: Sequence[Mapping[str, Any]]) -> Path:
    """Persist ``items`` atomically into ``<ledger_dir>/ledger.jsonl`` with ``0o600`` mode."""
    ensure_secure_dir(ledger_dir)
    ledger_path = ledger_dir / "ledger.jsonl"
    body = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    atomic_write_text(ledger_path, body, mode=0o600)
    return ledger_path


# ---------------------------------------------------------------------------
# Deterministic INDEX.md Renderer (T1, T3, T6)
# ---------------------------------------------------------------------------


def _md_cell(value: Any) -> str:
    text = re.sub(r"[\r\n\u2028\u2029]+", " ", str(value or "-")).strip()
    return text.replace("|", "\\|") or "-"


def render_index_markdown(items: Sequence[Mapping[str, Any]]) -> str:
    """Render deterministic Markdown ``INDEX.md`` from validated ledger items."""
    counts: dict[str, int] = {status: 0 for status in VALID_STATUSES}
    for item in items:
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1

    lines: list[str] = [
        "# Tech Horizon Ledger Index",
        "",
        "Generated deterministically from `ledger.jsonl`. Do not edit by hand; run `horizon.py render-index`.",
        "",
        "## Summary Counts",
        "",
        "| Status | Count |",
        "| :--- | ---: |",
    ]
    for status in VALID_STATUSES:
        lines.append(f"| `{status}` | {counts[status]} |")
    lines.append(f"| **Total** | **{len(items)}** |")
    lines.append("")

    active_priority = {"triggered": 0, "watching": 1}
    active = sorted(
        (it for it in items if it.get("status") in ("watching", "triggered")),
        key=lambda it: (active_priority.get(str(it.get("status")), 9), str(it.get("id", ""))),
    )
    lines.extend(
        [
            "## Active Watchlist",
            "",
            "| ID | Rev | Status | Category | Window | Title | Updated |",
            "| :--- | ---: | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    if active:
        for it in active:
            lines.append(
                f"| `{_md_cell(it['id'])}` | {it.get('revision', 1)} | `{_md_cell(it['status'])}` | "
                f"{_md_cell(it.get('category', 'general'))} | {_md_cell(it.get('window'))} | "
                f"{_md_cell(it.get('title'))} | {_md_cell(it.get('updated_at'))} |"
            )
    else:
        lines.append("| _none_ | 0 | - | - | - | No active watching or triggered items | - |")
    lines.append("")

    open_prs = sorted(
        (it for it in items if it.get("status") == "pr_opened"),
        key=lambda it: str(it.get("id", "")),
    )
    lines.extend(
        [
            "## Open PRs",
            "",
            "| ID | Rev | Title | PR URL | Updated |",
            "| :--- | ---: | :--- | :--- | :--- |",
        ]
    )
    if open_prs:
        for it in open_prs:
            lines.append(
                f"| `{_md_cell(it['id'])}` | {it.get('revision', 1)} | {_md_cell(it.get('title'))} | "
                f"{_md_cell(it.get('pr_url') or '-')} | {_md_cell(it.get('updated_at'))} |"
            )
    else:
        lines.append("| _none_ | 0 | No open remediation PRs | - | - |")
    lines.append("")

    history_items = sorted(
        (it for it in items if it.get("status") in ("landed", "superseded")),
        key=lambda it: str(it.get("id", "")),
    )
    lines.extend(
        [
            "## Landed & Superseded History",
            "",
            "| ID | Status | Title | Provenance | Updated |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    if history_items:
        for it in history_items:
            provenance_parts: list[str] = []
            if it.get("pr_url"):
                provenance_parts.append(f"PR: {it['pr_url']}")
            if it.get("backup_path"):
                provenance_parts.append(f"Backup: {Path(str(it['backup_path'])).name}")
            if it.get("override_reason"):
                provenance_parts.append(f"Override: {it['override_reason']}")
            provenance = "; ".join(provenance_parts) if provenance_parts else "-"
            lines.append(
                f"| `{_md_cell(it['id'])}` | `{_md_cell(it['status'])}` | {_md_cell(it.get('title'))} | "
                f"{_md_cell(provenance)} | {_md_cell(it.get('updated_at'))} |"
            )
    else:
        lines.append("| _none_ | - | No landed or superseded items | - | - |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subcommand Handlers
# ---------------------------------------------------------------------------


def _load_json_input(path_arg: str) -> Any:
    if path_arg == "-":
        raw = sys.stdin.read()
    else:
        path = Path(os.path.expanduser(path_arg))
        if not path.is_file():
            raise CliUsageError(f"Input file not found: {path}")
        raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliUsageError(f"Invalid JSON input ({path_arg}): {exc}") from exc


def cmd_record(ledger_dir: Path, raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and upsert a forecast item into ``ledger.jsonl``, then render ``INDEX.md``."""
    validated = validate_record_payload(raw_payload)
    ledger_path = ledger_dir / "ledger.jsonl"
    now = utc_now_iso()

    with ledger_lock(ledger_dir):
        items = load_ledger(ledger_path)
        existing_idx = next((idx for idx, it in enumerate(items) if it["id"] == validated["id"]), None)
        if existing_idx is None:
            item = {
                **validated,
                "status": "watching",
                "revision": 1,
                "created_at": now,
                "updated_at": now,
                "pr_url": None,
                "backup_path": None,
                "override_reason": None,
                "history": [
                    {
                        "timestamp": now,
                        "event": "created",
                        "revision": 1,
                        "status": "watching",
                        "summary": "Initial forecast recorded.",
                    }
                ],
            }
            items.append(item)
            action = "created"
        else:
            prev = items[existing_idx]
            new_rev = int(prev.get("revision", 1)) + 1
            history = list(prev.get("history", []))
            history.append(
                {
                    "timestamp": now,
                    "event": "updated",
                    "revision": new_rev,
                    "status": prev["status"],
                    "previous_revision": prev.get("revision", 1),
                    "previous_forecast": prev.get("forecast"),
                    "previous_baseline": prev.get("baseline_measurement"),
                }
            )
            item = {
                **validated,
                "status": prev["status"],
                "revision": new_rev,
                "created_at": prev.get("created_at", now),
                "updated_at": now,
                "pr_url": prev.get("pr_url"),
                "backup_path": prev.get("backup_path"),
                "override_reason": prev.get("override_reason"),
                "history": history,
            }
            items[existing_idx] = item
            action = "updated"

        saved_ledger = save_ledger(ledger_dir, items)
        index_path = ledger_dir / "INDEX.md"
        atomic_write_text(index_path, render_index_markdown(items), mode=0o600)
    return {
        "action": action,
        "id": item["id"],
        "revision": item["revision"],
        "status": item["status"],
        "ledger_path": str(saved_ledger),
        "index_path": str(index_path),
    }


def cmd_list(
    ledger_dir: Path,
    *,
    status_filter: str = "all",
    output_format: str = "table",
) -> tuple[list[dict[str, Any]], str]:
    """Load ledger items, filter by status, and render JSON or tabular view."""
    items = load_ledger(ledger_dir / "ledger.jsonl")
    if status_filter != "all":
        items = [it for it in items if it.get("status") == status_filter]
    if output_format == "json":
        return items, json.dumps({"count": len(items), "items": items}, indent=2)

    if not items:
        return items, f"No horizon items matching status={status_filter!r}."
    rows = ["ID | Rev | Status | Category | Window | Title", "--- | ---: | --- | --- | --- | ---"]
    for it in items:
        rows.append(
            f"{_md_cell(it['id'])} | {it.get('revision', 1)} | {_md_cell(it['status'])} | "
            f"{_md_cell(it.get('category', 'general'))} | {_md_cell(it.get('window'))} | "
            f"{_md_cell(it.get('title'))}"
        )
    return items, "\n".join(rows)


def cmd_collect_evidence(
    ledger_dir: Path,
    *,
    out_path: Path | None = None,
    repo_root: Path | None = None,
    allow_roots: Sequence[str] = (),
    item_id_filter: str | None = None,
    reconcile_prs: bool = False,
    timeout: int = horizon_probes.DEFAULT_TIMEOUT_S,
    runner: horizon_probes.RunnerCallable | None = None,
    http_fetcher: horizon_probes.HttpFetchCallable | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run mechanical probes across active items and optionally reconcile merged/closed PRs."""
    ledger_path = ledger_dir / "ledger.jsonl"
    if item_id_filter:
        validate_item_id(item_id_filter)
    if ledger_path.exists():
        with ledger_lock(ledger_dir):
            items = load_ledger(ledger_path)
    else:
        items = []

    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_allow_roots = [
        (Path.home() / ".gemini").resolve(),
        *(Path(os.path.expanduser(r)).resolve() for r in allow_roots),
    ]

    if item_id_filter and not any(it["id"] == item_id_filter for it in items):
        raise ValidationFailure(f"Item id {item_id_filter!r} not found in ledger.")

    evaluated_items: list[dict[str, Any]] = []
    not_inspected: list[dict[str, Any]] = []
    skipped_items: list[dict[str, Any]] = []
    reconciled_prs: list[dict[str, Any]] = []
    pending_reconciliations: dict[str, dict[str, Any]] = {}
    now = utc_now_iso()

    for item in items:
        item_id = item["id"]
        if item_id_filter and item_id != item_id_filter:
            continue
        if item["status"] not in ACTIVE_PROBE_STATUSES:
            skipped_items.append({"item_id": item_id, "status": item["status"]})
            continue

        probe_results: list[dict[str, Any]] = []
        pr_status_result: dict[str, Any] | None = None
        checked_pr_urls: set[str] = set()

        for probe in item["probes"]:
            result, uninspected = horizon_probes.run_probe(
                item_id,
                probe,
                repo_root=resolved_repo_root,
                allow_roots=resolved_allow_roots,
                timeout=timeout,
                runner=runner,
                http_fetcher=http_fetcher,
                env=env,
            )
            probe_results.append(result)
            if uninspected is not None:
                not_inspected.append(uninspected)
            if result.get("kind") == "gh_pr_status":
                checked_pr_urls.add(str(result.get("pr_url", "")))
                if item.get("pr_url") and str(result.get("pr_url")) == str(item["pr_url"]).rstrip("/"):
                    pr_status_result = result

        if item["status"] == "pr_opened" and item.get("pr_url"):
            norm_pr = horizon_probes.validate_gh_pr_url(str(item["pr_url"]))
            if norm_pr not in checked_pr_urls:
                pr_status_result, pr_uninspected = horizon_probes.collect_gh_pr_status(
                    item_id, norm_pr, timeout=timeout, runner=runner, env=env
                )
                probe_results.append(pr_status_result)
                if pr_uninspected is not None:
                    not_inspected.append(pr_uninspected)

        observed_status = item["status"]
        if (
            reconcile_prs
            and item["status"] == "pr_opened"
            and item.get("pr_url")
            and pr_status_result is not None
            and pr_status_result.get("available") is True
        ):
            pr_state = str(pr_status_result.get("state") or "").upper()
            expected_pr_url = str(item["pr_url"]).rstrip("/")
            if pr_state == "MERGED":
                pending_reconciliations[item_id] = {
                    "expected_pr_url": expected_pr_url,
                    "to_status": "landed",
                    "event": "pr_reconciled",
                    "pr_state": "MERGED",
                    "merged_at": pr_status_result.get("merged_at"),
                }
                observed_status = "landed"
            elif pr_state == "CLOSED":
                pending_reconciliations[item_id] = {
                    "expected_pr_url": expected_pr_url,
                    "to_status": "triggered",
                    "event": "pr_closed_unmerged",
                    "pr_state": "CLOSED",
                    "merged_at": None,
                }
                observed_status = "triggered"

        entry: dict[str, Any] = {
            "item_id": item_id,
            "revision": item["revision"],
            "status": observed_status,
            "probes": probe_results,
        }
        if pr_status_result is not None:
            entry["pr_status"] = pr_status_result
        evaluated_items.append(entry)

    if pending_reconciliations:
        with ledger_lock(ledger_dir):
            fresh_items = load_ledger(ledger_path)
            ledger_dirty = False
            reconciled_ids: set[str] = set()
            for fresh in fresh_items:
                rec = pending_reconciliations.get(fresh["id"])
                if not rec:
                    continue
                fresh_pr = str(fresh.get("pr_url") or "").rstrip("/")
                if fresh["status"] != "pr_opened" or fresh_pr != rec["expected_pr_url"]:
                    continue
                fresh["status"] = rec["to_status"]
                fresh["updated_at"] = now
                history = list(fresh.get("history", []))
                hist_event: dict[str, Any] = {
                    "timestamp": now,
                    "event": rec["event"],
                    "from_status": "pr_opened",
                    "to_status": rec["to_status"],
                    "pr_url": fresh.get("pr_url"),
                }
                if rec["merged_at"] is not None:
                    hist_event["merged_at"] = rec["merged_at"]
                history.append(hist_event)
                fresh["history"] = history
                reconcile_entry: dict[str, Any] = {
                    "item_id": fresh["id"],
                    "pr_url": fresh.get("pr_url"),
                    "state": rec["pr_state"],
                    "from_status": "pr_opened",
                    "to_status": rec["to_status"],
                }
                if rec["merged_at"] is not None:
                    reconcile_entry["merged_at"] = rec["merged_at"]
                reconciled_prs.append(reconcile_entry)
                reconciled_ids.add(fresh["id"])
                ledger_dirty = True

            if ledger_dirty:
                save_ledger(ledger_dir, fresh_items)
                atomic_write_text(
                    ledger_dir / "INDEX.md", render_index_markdown(fresh_items), mode=0o600
                )
            fresh_status_by_id = {it["id"]: it["status"] for it in fresh_items}
            for ev_entry in evaluated_items:
                if ev_entry["item_id"] in pending_reconciliations and ev_entry["item_id"] not in reconciled_ids:
                    ev_entry["status"] = fresh_status_by_id.get(ev_entry["item_id"], ev_entry["status"])

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": now,
        "ledger_dir": horizon_probes.contract_home(ledger_dir),
        "items_evaluated": len(evaluated_items),
        "items": evaluated_items,
        "skipped_items": skipped_items,
        "not_inspected": not_inspected,
        "reconciled_prs": reconciled_prs,
    }
    runs_dir = ensure_secure_dir(ledger_dir / "runs")
    run_file = runs_dir / f"{utc_timestamp_slug()}-evidence.json"
    serialized = json.dumps(evidence, indent=2) + "\n"
    atomic_write_text(run_file, serialized, mode=0o600)
    if out_path is not None:
        atomic_write_text(out_path, serialized, mode=0o600)
    evidence["run_file"] = str(run_file)
    return evidence


def _not_inspected_key(entry: Any) -> str:
    if isinstance(entry, dict):
        item_id = str(entry.get("item_id", "")).strip()
        what = str(entry.get("what", "")).strip()
        if item_id or what:
            return f"{item_id}|{what}"
        return json.dumps(entry, sort_keys=True)
    return str(entry).strip()


def validate_verdict_payload(
    verdict: Any,
    ledger_items: Sequence[Mapping[str, Any]],
    evidence: Any = None,
) -> list[str]:
    """Validate LLM/MCP verdict JSON against ledger items and optional evidence (V1-V6, S9)."""
    errors: list[str] = []
    if not isinstance(verdict, dict):
        return ["Verdict document must be a JSON object."]

    if verdict.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got {verdict.get('schema_version')!r}."
        )
    if not isinstance(verdict.get("evaluated_at"), str) or not verdict["evaluated_at"].strip():
        errors.append("Missing or empty 'evaluated_at' timestamp string.")
    if not isinstance(verdict.get("summary"), str) or not verdict["summary"].strip():
        errors.append("Missing or empty top-level 'summary'.")

    triggered_count = verdict.get("triggered_count")
    if not isinstance(triggered_count, int) or isinstance(triggered_count, bool) or triggered_count < 0:
        errors.append("'triggered_count' must be a non-negative integer (not bool).")

    not_inspected = verdict.get("not_inspected")
    if not isinstance(not_inspected, list):
        errors.append("'not_inspected' must be a list.")

    leaks = horizon_probes.find_secret_leaks(verdict)
    for hit in leaks:
        errors.append(f"Unredacted secret pattern detected at {hit}.")

    decisions = verdict.get("decisions")
    if not isinstance(decisions, list):
        errors.append("'decisions' must be a list.")
        return errors

    if not decisions and any(it.get("status") in ACTIVE_PROBE_STATUSES for it in ledger_items):
        errors.append(
            "Verdict 'decisions' cannot be empty while active watching/pr_opened items exist in ledger.jsonl."
        )

    known_by_id = {str(it["id"]): it for it in ledger_items}
    seen_ids: set[str] = set()
    actual_triggered = 0

    for idx, dec in enumerate(decisions):
        prefix = f"decisions[{idx}]"
        if not isinstance(dec, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        item_id = dec.get("item_id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{prefix}.item_id must be a non-empty string.")
            continue
        if item_id in seen_ids:
            errors.append(f"{prefix}.item_id={item_id!r} is duplicated.")
        seen_ids.add(item_id)
        if item_id not in known_by_id:
            errors.append(f"{prefix}.item_id={item_id!r} does not exist in ledger.jsonl.")

        decision_val = dec.get("decision")
        if decision_val not in VALID_DECISIONS:
            errors.append(
                f"{prefix}.decision={decision_val!r} invalid; expected one of {sorted(VALID_DECISIONS)}."
            )
            continue

        cites = dec.get("evidence_citations")
        if not isinstance(cites, list) or any(not isinstance(c, str) or not c.strip() for c in cites):
            errors.append(f"{prefix}.evidence_citations must be a list of non-empty strings.")
            cites = []

        item_summary = dec.get("summary")
        if not isinstance(item_summary, str):
            errors.append(f"{prefix}.summary must be a string.")
            item_summary = ""

        if decision_val in TRIGGERED_DECISIONS:
            actual_triggered += 1
            if not cites:
                errors.append(
                    f"{prefix} ({item_id}): decision={decision_val!r} requires non-empty evidence_citations."
                )
            if not item_summary.strip():
                errors.append(
                    f"{prefix} ({item_id}): decision={decision_val!r} requires non-empty summary."
                )

    if isinstance(triggered_count, int) and not isinstance(triggered_count, bool):
        if triggered_count != actual_triggered:
            errors.append(
                f"Contradictory triggered_count={triggered_count}: decisions contain "
                f"{actual_triggered} triggered/supersede item(s) ({sorted(TRIGGERED_DECISIONS)})."
            )

    if evidence is not None:
        if not isinstance(evidence, dict):
            errors.append("Evidence document must be a JSON object.")
        else:
            ev_items = evidence.get("items", [])
            if isinstance(ev_items, list):
                for ev_it in ev_items:
                    if isinstance(ev_it, dict) and ev_it.get("item_id"):
                        ev_id = str(ev_it["item_id"])
                        if ev_id not in seen_ids:
                            errors.append(
                                f"Evidence evaluated item {ev_id!r}, which is missing from verdict decisions."
                            )
            ev_not_inspected = evidence.get("not_inspected", [])
            if isinstance(ev_not_inspected, list) and isinstance(not_inspected, list):
                verdict_keys = {_not_inspected_key(entry) for entry in not_inspected}
                for ev_ni in ev_not_inspected:
                    key = _not_inspected_key(ev_ni)
                    if not isinstance(key, str) or not key or key not in verdict_keys:
                        errors.append(
                            f"not_inspected honesty violation: verdict omitted unchecked surface {key!r} from evidence.json."
                        )

    return errors


def cmd_backup_target(
    ledger_dir: Path,
    target_arg: str,
    allow_roots: Sequence[str] = (),
) -> dict[str, Any]:
    """Snapshot a confined global config target with SHA-256 verification and ``0o600`` mode."""
    allowed_roots = [
        (Path.home() / ".gemini").resolve(),
        *(Path(os.path.expanduser(r)).resolve() for r in allow_roots),
    ]
    try:
        resolved_target = horizon_probes.resolve_global_config_path(
            target_arg, allowed_roots, must_exist=True
        )
    except ValueError as exc:
        raise CliUsageError(str(exc)) from exc

    open_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(resolved_target, open_flags)
    except OSError as exc:
        raise CliUsageError(
            f"Cannot safely open target {horizon_probes.contract_home(resolved_target)!r}: {exc}"
        ) from exc
    with os.fdopen(fd, "rb") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise CliUsageError(
                f"Target path {horizon_probes.contract_home(resolved_target)!r} is not a regular file."
            )
        data = fh.read()
    digest = hashlib.sha256(data).hexdigest()
    safe_name = resolved_target.name
    if not safe_name or "/" in safe_name or "\\" in safe_name or safe_name in (".", ".."):
        raise CliUsageError(f"Unsafe target filename: {safe_name!r}")

    backups_dir = ensure_secure_dir(ledger_dir / "backups")
    backup_path = backups_dir / f"{utc_timestamp_slug()}_{digest[:12]}_{safe_name}"
    atomic_write_bytes(backup_path, data, mode=0o600)

    verified_digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    if verified_digest != digest:
        raise ValidationFailure("Backup write failed post-write SHA-256 verification.")

    meta_path = backups_dir / f"{backup_path.name}.sha256.json"
    meta = {
        "backup_path": str(backup_path),
        "target_path": str(resolved_target),
        "sha256": digest,
        "bytes": len(data),
        "created_at": utc_now_iso(),
    }
    atomic_write_text(meta_path, json.dumps(meta, indent=2) + "\n", mode=0o600)
    return {
        "backup_path": str(backup_path),
        "target_path": str(resolved_target),
        "sha256": digest,
        "bytes": len(data),
    }


def _verify_backup_for_item(
    ledger_dir: Path,
    backup_arg: str,
    item: Mapping[str, Any],
) -> Path:
    """Verify backup location inside ``<ledger_dir>/backups/``, SHA-256 digest, and target existence."""
    backups_dir = (ledger_dir / "backups").resolve()
    raw_backup = Path(os.path.expanduser(backup_arg.strip()))
    try:
        resolved_backup = raw_backup.resolve(strict=True)
    except OSError as exc:
        raise ValidationFailure(f"Backup path {backup_arg!r} does not exist: {exc}") from exc

    if not resolved_backup.is_relative_to(backups_dir):
        raise ValidationFailure(
            f"Backup path {resolved_backup} must reside inside {backups_dir}."
        )
    if not resolved_backup.is_file():
        raise ValidationFailure(f"Backup path {resolved_backup} is not a regular file.")

    name_match = BACKUP_FILENAME_RE.fullmatch(resolved_backup.name)
    if not name_match:
        raise ValidationFailure(
            f"Backup filename {resolved_backup.name!r} does not match '<utc_ts>_<sha12>_<basename>'."
        )
    expected_sha12 = name_match.group(2)
    actual_sha = hashlib.sha256(resolved_backup.read_bytes()).hexdigest()
    if actual_sha[:12] != expected_sha12:
        raise ValidationFailure(
            f"Backup digest mismatch: filename carries {expected_sha12}, actual SHA-256 starts with {actual_sha[:12]}."
        )

    meta_path = resolved_backup.parent / f"{resolved_backup.name}.sha256.json"
    if not meta_path.is_file():
        raise ValidationFailure(f"Missing backup digest sidecar {meta_path.name}.")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"Unreadable backup digest sidecar {meta_path.name}: {exc}") from exc
    if not isinstance(meta, dict) or meta.get("sha256") != actual_sha:
        raise ValidationFailure("Backup sidecar SHA-256 does not match backup contents.")

    target_str = str(meta.get("target_path", "")).strip()
    if not target_str:
        raise ValidationFailure("Backup sidecar is missing 'target_path'.")
    recorded_target = Path(os.path.expanduser(target_str)).resolve()
    if not recorded_target.is_file():
        raise ValidationFailure(f"Backed-up target file no longer exists on disk: {recorded_target}.")

    global_targets = [t for t in item.get("targets", []) if t.get("kind") == "global_config"]
    resolved_item_targets: list[Path] = []
    for tgt in global_targets:
        t_path = Path(os.path.expanduser(str(tgt["path"]))).resolve()
        if not t_path.is_file():
            raise ValidationFailure(f"Item global_config target does not exist on disk: {t_path}.")
        resolved_item_targets.append(t_path)

    if resolved_item_targets and recorded_target not in resolved_item_targets:
        raise ValidationFailure(
            f"Backup target {recorded_target} does not match item global_config target(s)."
        )
    return resolved_backup


def cmd_record_action(
    ledger_dir: Path,
    *,
    item_id: str,
    new_status: str,
    pr_url: str | None = None,
    backup_path: str | None = None,
    override_reason: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Transition an item status through fail-closed L3 provenance gates."""
    validate_item_id(item_id)
    if new_status not in ACTION_TRANSITION_STATUSES:
        raise CliUsageError(
            f"Invalid target status {new_status!r}; expected {ACTION_TRANSITION_STATUSES}."
        )

    ledger_path = ledger_dir / "ledger.jsonl"
    now = utc_now_iso()
    with ledger_lock(ledger_dir):
        items = load_ledger(ledger_path)
        target_idx = next((idx for idx, it in enumerate(items) if it["id"] == item_id), None)
        if target_idx is None:
            raise ValidationFailure(f"Item {item_id!r} not found in ledger.")

        item = copy.deepcopy(items[target_idx])
        targets = item.get("targets", [])
        has_repo = any(t.get("kind") == "repo_branch_pr" for t in targets)
        has_global = any(t.get("kind") == "global_config" for t in targets)

        clean_pr_url: str | None = None
        if pr_url is not None and pr_url.strip():
            try:
                clean_pr_url = horizon_probes.validate_gh_pr_url(pr_url)
            except ValueError as exc:
                raise ValidationFailure(str(exc)) from exc
        elif item.get("pr_url"):
            clean_pr_url = str(item["pr_url"])

        clean_override = (
            horizon_probes.redact_secrets(override_reason.strip())
            if override_reason and override_reason.strip()
            else None
        )

        if has_repo and new_status == "pr_opened":
            if not pr_url or not pr_url.strip() or not clean_pr_url:
                raise ValidationFailure(
                    f"Gate refused transition to 'pr_opened' for {item_id!r}: "
                    f"repo_branch_pr target requires a valid --pr-url (https://github.com/<owner>/<repo>/pull/<n>)."
                )

        if has_repo and new_status == "landed":
            if not clean_pr_url and not clean_override:
                raise ValidationFailure(
                    f"Gate refused transition to 'landed' for {item_id!r}: "
                    f"repo_branch_pr target requires --pr-url or an explicit --override-reason."
                )

        verified_backup: Path | None = None
        if has_global and new_status == "landed":
            if not backup_path or not backup_path.strip():
                raise ValidationFailure(
                    f"Gate refused transition to 'landed' for {item_id!r}: "
                    f"global_config target requires --backup-path inside <ledger-dir>/backups/."
                )
            verified_backup = _verify_backup_for_item(ledger_dir, backup_path, item)
        elif backup_path and backup_path.strip():
            verified_backup = _verify_backup_for_item(ledger_dir, backup_path, item)

        old_status = item["status"]
        item["status"] = new_status
        item["updated_at"] = now
        if clean_pr_url:
            item["pr_url"] = clean_pr_url
        if verified_backup is not None:
            item["backup_path"] = str(verified_backup)
        if clean_override:
            item["override_reason"] = clean_override

        event_record = {
            "timestamp": now,
            "event": "status_transition",
            "from_status": old_status,
            "to_status": new_status,
            "pr_url": clean_pr_url,
            "backup_path": str(verified_backup) if verified_backup else None,
            "override_reason": clean_override,
            "note": horizon_probes.redact_secrets(note.strip()) if note and note.strip() else None,
        }
        history = list(item.get("history", []))
        history.append(event_record)
        item["history"] = history
        items[target_idx] = item

        save_ledger(ledger_dir, items)
        index_path = ledger_dir / "INDEX.md"
        atomic_write_text(index_path, render_index_markdown(items), mode=0o600)

    runs_dir = ensure_secure_dir(ledger_dir / "runs")
    action_log = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": now,
        "item_id": item_id,
        **event_record,
    }
    run_file = runs_dir / f"{utc_timestamp_slug()}-action-{item_id}.json"
    atomic_write_text(run_file, json.dumps(action_log, indent=2) + "\n", mode=0o600)
    return {
        "item_id": item_id,
        "from_status": old_status,
        "status": new_status,
        "pr_url": item.get("pr_url"),
        "backup_path": item.get("backup_path"),
        "override_reason": item.get("override_reason"),
        "run_file": str(run_file),
        "index_path": str(index_path),
    }


def cmd_render_index(ledger_dir: Path, *, check: bool = False) -> tuple[int, dict[str, Any]]:
    """Render ``<ledger-dir>/INDEX.md`` or check freshness against ``ledger.jsonl``."""
    index_path = ledger_dir / "INDEX.md"
    if check:
        if ledger_dir.exists():
            with ledger_lock(ledger_dir):
                items = load_ledger(ledger_dir / "ledger.jsonl")
                expected = render_index_markdown(items)
                if not index_path.is_file():
                    return 1, {"status": "stale", "reason": "INDEX.md missing", "index_path": str(index_path)}
                current = index_path.read_text(encoding="utf-8")
        else:
            items = []
            expected = render_index_markdown(items)
            return 1, {"status": "stale", "reason": "INDEX.md missing", "index_path": str(index_path)}
        if current != expected:
            return 1, {"status": "stale", "reason": "INDEX.md differs from ledger.jsonl", "index_path": str(index_path)}
        return 0, {"status": "ok", "index_path": str(index_path), "item_count": len(items)}

    with ledger_lock(ledger_dir):
        items = load_ledger(ledger_dir / "ledger.jsonl")
        expected = render_index_markdown(items)
        atomic_write_text(index_path, expected, mode=0o600)
    return 0, {"status": "rendered", "index_path": str(index_path), "item_count": len(items)}


def cmd_doctor(ledger_dir: Path) -> dict[str, Any]:
    """Report Python stdlib, ledger directory, and external CLI readiness."""
    ledger_path = ledger_dir / "ledger.jsonl"
    item_count = 0
    ledger_valid = True
    ledger_error: str | None = None
    if ledger_path.exists():
        try:
            item_count = len(load_ledger(ledger_path))
        except ValidationFailure as exc:
            ledger_valid = False
            ledger_error = str(exc)

    tools = {
        binary: (shutil.which(binary) is not None)
        for binary in sorted(horizon_probes.CLI_HELP_ALLOWLIST)
    }
    return {
        "status": "ok" if ledger_valid else "degraded",
        "python_version": sys.version.split()[0],
        "stdlib_only": True,
        "ledger_dir": horizon_probes.contract_home(ledger_dir),
        "ledger_exists": ledger_path.exists(),
        "ledger_valid": ledger_valid,
        "ledger_error": ledger_error,
        "item_count": item_count,
        "tools": tools,
    }


# ---------------------------------------------------------------------------
# CLI Argument Parser & Entrypoint (S6)
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build Horizon CLI parser whose flags stay synced 1:1 with SKILL.md and references."""
    shared_ledger = argparse.ArgumentParser(add_help=False)
    shared_ledger.add_argument(
        "--ledger-dir",
        dest="sub_ledger_dir",
        default=argparse.SUPPRESS,
        help="Override ledger directory (default: $FORGE_HORIZONS_DIR or ~/.gemini/horizons).",
    )

    parser = argparse.ArgumentParser(
        prog="horizon.py",
        description="Horizon Sentinel CLI: central 6-12 month forecast ledger, probes, verdict validation, and provenance gates.",
    )
    parser.add_argument(
        "--ledger-dir",
        dest="top_ledger_dir",
        default=None,
        help="Override ledger directory (default: $FORGE_HORIZONS_DIR or ~/.gemini/horizons).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Report environment, tool availability, and ledger readiness as JSON.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", title="subcommands")

    p_record = subparsers.add_parser(
        "record",
        parents=[shared_ledger],
        help="Validate and upsert a forecast item into ledger.jsonl and regenerate INDEX.md.",
    )
    p_record.add_argument("--input", help="JSON file containing forecast item payload (or '-' for stdin).")
    p_record.add_argument("--id", help="Unique kebab-case item slug (3-64 chars).")
    p_record.add_argument("--title", help="Human-readable forecast title.")
    p_record.add_argument("--category", help="Forecast category label (default: general).")
    p_record.add_argument("--window", help="Expected time window (e.g. '6-12 months' or '2026-Q4..2027-Q2').")
    p_record.add_argument("--baseline", help="Current baseline measurement observed today.")
    p_record.add_argument("--forecast", help="Explicit 6-12 month forecast statement.")
    p_record.add_argument("--playbook", help="Remediation steps to execute when forecast drops or drifts.")
    p_record.add_argument("--probe", action="append", default=[], help="JSON probe object (repeatable).")
    p_record.add_argument("--target", action="append", default=[], help="JSON target object (repeatable).")
    p_record.add_argument("--source", help="Provenance source label for this forecast.")

    p_list = subparsers.add_parser(
        "list",
        parents=[shared_ledger],
        help="List horizon items filtered by status.",
    )
    p_list.add_argument(
        "--status",
        choices=("all", *VALID_STATUSES),
        default="all",
        help="Filter items by lifecycle status (default: all).",
    )
    p_list.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format (default: table).",
    )

    p_collect = subparsers.add_parser(
        "collect-evidence",
        parents=[shared_ledger],
        help="Execute mechanical probes across watching/pr_opened items into evidence.json.",
    )
    p_collect.add_argument("--out", help="Write evidence JSON to this path in addition to runs/ archive.")
    p_collect.add_argument("--repo-root", help="Repository root for confining repo-scoped file_anchor probes.")
    p_collect.add_argument(
        "--allow-root",
        action="append",
        default=[],
        help="Additional allowed root directory for global_config file_anchor probes (repeatable).",
    )
    p_collect.add_argument("--id", help="Restrict probe collection to a single item slug.")
    p_collect.add_argument(
        "--reconcile-prs",
        action="store_true",
        help="Transition pr_opened items whose gh_pr_status reports MERGED to landed and update INDEX.md.",
    )
    p_collect.add_argument(
        "--timeout",
        type=int,
        default=horizon_probes.DEFAULT_TIMEOUT_S,
        help="Per-probe subprocess/HTTP timeout in seconds (default: 30).",
    )

    p_validate = subparsers.add_parser(
        "validate-verdict",
        parents=[shared_ledger],
        help="L3 verifier validating agent-authored verdict.json against ledger.jsonl and optional evidence.json.",
    )
    p_validate.add_argument("--verdict", required=True, help="Path to verdict.json (or '-' for stdin).")
    p_validate.add_argument("--evidence", help="Optional path to evidence.json for not_inspected honesty verification.")

    p_backup = subparsers.add_parser(
        "backup-target",
        parents=[shared_ledger],
        help="Create a SHA-256-verified backup snapshot of a confined local target file.",
    )
    p_backup.add_argument("--target", required=True, help="Local target file path (confined to ~/.gemini or --allow-root).")
    p_backup.add_argument(
        "--allow-root",
        action="append",
        default=[],
        help="Additional allowed root directory for target confinement (repeatable).",
    )

    p_action = subparsers.add_parser(
        "record-action",
        parents=[shared_ledger],
        help="Transition an item status through fail-closed PR URL and SHA-256 backup L3 gates.",
    )
    p_action.add_argument("--id", required=True, help="Target item slug.")
    p_action.add_argument(
        "--status",
        required=True,
        choices=ACTION_TRANSITION_STATUSES,
        help="New lifecycle status.",
    )
    p_action.add_argument("--pr-url", help="Canonical GitHub PR URL (https://github.com/<owner>/<repo>/pull/<n>).")
    p_action.add_argument("--backup-path", help="Verified backup path inside <ledger-dir>/backups/.")
    p_action.add_argument("--override-reason", help="Explicit justification bypassing repo PR URL requirement on landed.")
    p_action.add_argument("--note", help="Optional transition note recorded in history[].")

    p_render = subparsers.add_parser(
        "render-index",
        parents=[shared_ledger],
        help="Deterministically render <ledger-dir>/INDEX.md from ledger.jsonl.",
    )
    p_render.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if INDEX.md is missing or out of date vs ledger.jsonl.",
    )
    return parser


def _build_record_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.input:
        loaded = _load_json_input(args.input)
        if not isinstance(loaded, dict):
            raise CliUsageError("Record --input JSON must be an object.")
        payload.update(loaded)

    cli_str_map = {
        "id": args.id,
        "title": args.title,
        "category": args.category,
        "window": args.window,
        "baseline_measurement": args.baseline,
        "forecast": args.forecast,
        "playbook": args.playbook,
        "source": args.source,
    }
    for key, val in cli_str_map.items():
        if val is not None:
            payload[key] = val

    if args.probe:
        parsed_probes: list[Any] = []
        for idx, raw_probe in enumerate(args.probe):
            try:
                parsed_probes.append(json.loads(raw_probe))
            except json.JSONDecodeError as exc:
                raise CliUsageError(f"Invalid JSON in --probe[{idx}]: {exc}") from exc
        payload["probes"] = parsed_probes

    if args.target:
        parsed_targets: list[Any] = []
        for idx, raw_target in enumerate(args.target):
            try:
                parsed_targets.append(json.loads(raw_target))
            except json.JSONDecodeError as exc:
                raise CliUsageError(f"Invalid JSON in --target[{idx}]: {exc}") from exc
        payload["targets"] = parsed_targets
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for ``skills/horizon/scripts/horizon.py``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    cli_ledger = getattr(args, "sub_ledger_dir", None) or getattr(args, "top_ledger_dir", None)
    ledger_dir = resolve_ledger_dir(cli_ledger)

    try:
        if args.doctor:
            print(json.dumps(cmd_doctor(ledger_dir), indent=2))
            return 0
        if not args.subcommand:
            parser.print_help(sys.stderr)
            return 2

        if args.subcommand == "record":
            payload = _build_record_payload_from_args(args)
            print(json.dumps(cmd_record(ledger_dir, payload), indent=2))
            return 0

        if args.subcommand == "list":
            _items, rendered = cmd_list(
                ledger_dir, status_filter=args.status, output_format=args.format
            )
            print(rendered)
            return 0

        if args.subcommand == "collect-evidence":
            if args.timeout < 1:
                raise CliUsageError("--timeout must be >= 1 second.")
            out_path = Path(os.path.expanduser(args.out)).resolve() if args.out else None
            repo_root = Path(os.path.expanduser(args.repo_root)).resolve() if args.repo_root else None
            evidence = cmd_collect_evidence(
                ledger_dir,
                out_path=out_path,
                repo_root=repo_root,
                allow_roots=args.allow_root,
                item_id_filter=args.id,
                reconcile_prs=args.reconcile_prs,
                timeout=args.timeout,
            )
            print(json.dumps(evidence, indent=2))
            return 0

        if args.subcommand == "validate-verdict":
            verdict_path_arg = args.verdict
            if verdict_path_arg != "-" and not Path(os.path.expanduser(verdict_path_arg)).is_file():
                raise CliUsageError(f"Verdict file not found: {verdict_path_arg}")
            try:
                verdict_obj = _load_json_input(verdict_path_arg)
            except CliUsageError as exc:
                raise ValidationFailure(str(exc)) from exc

            evidence_obj: Any = None
            if args.evidence:
                if not Path(os.path.expanduser(args.evidence)).is_file():
                    raise CliUsageError(f"Evidence file not found: {args.evidence}")
                try:
                    evidence_obj = _load_json_input(args.evidence)
                except CliUsageError as exc:
                    raise ValidationFailure(str(exc)) from exc

            ledger_items = load_ledger(ledger_dir / "ledger.jsonl")
            errs = validate_verdict_payload(verdict_obj, ledger_items, evidence=evidence_obj)
            if errs:
                print(
                    json.dumps(
                        {
                            "valid": False,
                            "errors": errs,
                            "scope_note": (
                                "Checked schema, unique known item_id values, evidence_citations, "
                                "triggered_count consistency, secret patterns, and not_inspected parity; "
                                "did not judge semantic accuracy of forecast prose."
                            ),
                        },
                        indent=2,
                    )
                )
                return 1
            print(
                json.dumps(
                    {
                        "valid": True,
                        "decisions_checked": len(verdict_obj.get("decisions", [])),
                        "triggered_count": verdict_obj.get("triggered_count"),
                        "not_inspected_count": len(verdict_obj.get("not_inspected", [])),
                        "scope_note": (
                            "Checked schema, unique known item_id values, evidence_citations, "
                            "triggered_count consistency, secret patterns, and not_inspected parity; "
                            "did not judge semantic accuracy of forecast prose."
                        ),
                    },
                    indent=2,
                )
            )
            return 0

        if args.subcommand == "backup-target":
            result = cmd_backup_target(ledger_dir, args.target, allow_roots=args.allow_root)
            print(json.dumps(result, indent=2))
            return 0

        if args.subcommand == "record-action":
            result = cmd_record_action(
                ledger_dir,
                item_id=args.id,
                new_status=args.status,
                pr_url=args.pr_url,
                backup_path=args.backup_path,
                override_reason=args.override_reason,
                note=args.note,
            )
            print(json.dumps(result, indent=2))
            return 0

        if args.subcommand == "render-index":
            rc, info = cmd_render_index(ledger_dir, check=args.check)
            print(json.dumps(info, indent=2))
            return rc

        raise CliUsageError(f"Unknown subcommand: {args.subcommand}")
    except CliUsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValidationFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
