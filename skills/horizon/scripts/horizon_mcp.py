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

"""Stdlib-only stdio MCP server for Horizon Sentinel (``horizon.py mcp``).

Exposes the central forecast ledger (``~/.gemini/horizons/`` by default, or
``$FORGE_HORIZONS_DIR``) as structured MCP tools so any conversation, subagent,
or swarm worker can read and update ``ledger.jsonl`` across workspace sandboxes
without weakening host isolation or bypassing ``horizon.py`` L3 gates.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, BinaryIO, Mapping

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import horizon  # noqa: E402
import horizon_probes  # noqa: E402

SERVER_NAME = "horizon"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"2024-11-05", "2025-03-26", "2025-06-18"})
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


def build_tool_definitions() -> list[dict[str, Any]]:
    """Build MCP tool definitions derived from ``horizon.py`` constants (S7)."""
    list_statuses = ["all", *horizon.VALID_STATUSES]
    transition_statuses = list(horizon.ACTION_TRANSITION_STATUSES)
    return [
        {
            "name": "horizon_doctor",
            "description": "Report Python stdlib, central ledger health, item count, and external CLI availability.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_list",
            "description": "List forecasts in the central Horizon ledger filtered by lifecycle status.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": list_statuses,
                        "description": "Lifecycle status filter (default: all).",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "table"],
                        "description": "Output format (default: json).",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_record",
            "description": "Validate and upsert a 6-12 month forecast item into ledger.jsonl and regenerate INDEX.md.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique kebab-case item slug matching ^[a-z0-9][a-z0-9-]{2,63}$.",
                    },
                    "title": {"type": "string", "description": "Human-readable forecast title."},
                    "category": {
                        "type": "string",
                        "description": "Forecast category label (default: general).",
                    },
                    "window": {
                        "type": "string",
                        "description": "Expected forecast horizon window (e.g. 2026-Q4..2027-Q2).",
                    },
                    "baseline_measurement": {
                        "type": "string",
                        "description": "Current baseline measurement observed today.",
                    },
                    "baseline": {
                        "type": "string",
                        "description": "Alias for baseline_measurement.",
                    },
                    "forecast": {
                        "type": "string",
                        "description": "Explicit 6-12 month forecast statement.",
                    },
                    "playbook": {
                        "type": "string",
                        "description": "Actionable remediation playbook when the forecast triggers.",
                    },
                    "source": {
                        "type": "string",
                        "description": "Origin provenance label (default: mcp).",
                    },
                    "probes": {
                        "type": "array",
                        "items": {"type": "object"},
                        "minItems": 1,
                        "description": "Non-empty array of validated probe objects.",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "object"},
                        "minItems": 1,
                        "description": "Non-empty array of repo_branch_pr or global_config target objects.",
                    },
                },
                "required": ["id", "title", "window", "forecast", "playbook", "probes", "targets"],
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_collect_evidence",
            "description": "Execute mechanical probes across active items and archive factual evidence under runs/.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo_root": {
                        "type": "string",
                        "description": "Repository root for confining repo-scoped file_anchor probes.",
                    },
                    "allow_roots": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional allowed roots for global_config file_anchor probes.",
                    },
                    "id": {
                        "type": "string",
                        "description": "Optional single item slug filter.",
                    },
                    "reconcile_prs": {
                        "type": "boolean",
                        "description": "Auto-reconcile MERGED/CLOSED PRs on pr_opened items.",
                    },
                    "timeout": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 120,
                        "description": "Per-probe timeout in seconds (default: 30).",
                    },
                    "out": {
                        "type": "string",
                        "description": "Optional output file path (must reside inside ledger_dir or system temp dir).",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_validate_verdict",
            "description": "L3 verifier checking a sweep verdict object or confined JSON path against ledger.jsonl and evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "verdict": {
                        "description": "Verdict JSON object or file path inside ledger_dir/temp dir.",
                    },
                    "evidence": {
                        "description": "Optional evidence JSON object or file path inside ledger_dir/temp dir.",
                    },
                    "save_out": {
                        "type": "string",
                        "description": "Optional path inside ledger_dir/temp dir to persist a valid verdict.",
                    },
                },
                "required": ["verdict"],
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_backup_target",
            "description": "Create a SHA-256-verified snapshot of a confined global_config target inside backups/.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target file path confined to ~/.gemini or allow_roots.",
                    },
                    "allow_roots": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional allowed root directories for target confinement.",
                    },
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_record_action",
            "description": "Transition an item status through fail-closed PR URL and SHA-256 backup L3 gates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Target item slug."},
                    "status": {
                        "type": "string",
                        "enum": transition_statuses,
                        "description": "New lifecycle status.",
                    },
                    "pr_url": {
                        "type": "string",
                        "description": "Canonical GitHub PR URL for repo_branch_pr targets.",
                    },
                    "backup_path": {
                        "type": "string",
                        "description": "Verified backup path inside <ledger-dir>/backups/ for global_config targets.",
                    },
                    "override_reason": {
                        "type": "string",
                        "description": "Explicit justification bypassing repo PR URL requirement on landed.",
                    },
                    "note": {"type": "string", "description": "Optional transition note."},
                },
                "required": ["id", "status"],
                "additionalProperties": False,
            },
        },
        {
            "name": "horizon_render_index",
            "description": "Deterministically render or freshness-check <ledger-dir>/INDEX.md from ledger.jsonl.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "check": {
                        "type": "boolean",
                        "description": "Return error if INDEX.md is missing or stale vs ledger.jsonl.",
                    },
                },
                "additionalProperties": False,
            },
        },
    ]


def _allowed_scratch_roots(ledger_dir: Path) -> list[Path]:
    roots = [ledger_dir.resolve(), Path(tempfile.gettempdir()).resolve()]
    for candidate in ("/tmp", "/private/tmp"):
        p = Path(candidate)
        if p.exists():
            roots.append(p.resolve())
    return roots


def _confine_scratch_or_ledger_path(raw_path: str, ledger_dir: Path, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        raise horizon.CliUsageError(f"{label} must be a non-empty path string.")
    expanded = Path(os.path.expanduser(raw_path.strip()))
    if ".." in expanded.parts:
        raise horizon.CliUsageError(f"{label} may not contain '..' path traversal.")
    resolved = expanded.resolve()
    allowed = _allowed_scratch_roots(ledger_dir)
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise horizon.CliUsageError(
            f"{label} must reside inside ledger directory ({horizon_probes.contract_home(ledger_dir)}) or system temp dir."
        )
    return resolved


def _coerce_doc_or_path(val: Any, ledger_dir: Path, label: str) -> Any:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        confined = _confine_scratch_or_ledger_path(val, ledger_dir, label)
        if not confined.is_file():
            raise horizon.CliUsageError(f"{label} file not found: {horizon_probes.contract_home(confined)}")
        try:
            return json.loads(confined.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise horizon.ValidationFailure(f"Invalid JSON in {label}: {exc}") from exc
    raise horizon.CliUsageError(f"{label} must be a JSON object or file path string.")


def dispatch_tool(
    ledger_dir: Path,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
) -> tuple[bool, Any]:
    """Execute one MCP tool against ``ledger_dir``. Returns ``(is_error, payload)``."""
    args = dict(arguments or {})
    try:
        if tool_name == "horizon_doctor":
            return False, horizon.cmd_doctor(ledger_dir)

        if tool_name == "horizon_list":
            status_filter = str(args.get("status", "all"))
            if status_filter not in ("all", *horizon.VALID_STATUSES):
                raise horizon.CliUsageError(f"Invalid status filter: {status_filter!r}")
            output_format = str(args.get("format", "json"))
            if output_format not in ("json", "table"):
                raise horizon.CliUsageError(f"Invalid format: {output_format!r}")
            items, rendered = horizon.cmd_list(
                ledger_dir, status_filter=status_filter, output_format=output_format
            )
            if output_format == "json":
                return False, {"count": len(items), "items": items}
            return False, {"count": len(items), "table": rendered}

        if tool_name == "horizon_record":
            payload = dict(args)
            if "baseline_measurement" not in payload and "baseline" in payload:
                payload["baseline_measurement"] = payload.pop("baseline")
            else:
                payload.pop("baseline", None)
            payload.setdefault("source", "mcp")
            return False, horizon.cmd_record(ledger_dir, payload)

        if tool_name == "horizon_collect_evidence":
            timeout = int(args.get("timeout", horizon_probes.DEFAULT_TIMEOUT_S))
            if timeout < 1 or timeout > 120:
                raise horizon.CliUsageError("timeout must be between 1 and 120 seconds.")
            out_path = (
                _confine_scratch_or_ledger_path(str(args["out"]), ledger_dir, "out")
                if args.get("out")
                else None
            )
            repo_root = (
                Path(os.path.expanduser(str(args["repo_root"]))).resolve()
                if args.get("repo_root")
                else None
            )
            allow_roots_raw = args.get("allow_roots") or []
            if not isinstance(allow_roots_raw, list) or any(not isinstance(x, str) for x in allow_roots_raw):
                raise horizon.CliUsageError("allow_roots must be a list of path strings.")
            return False, horizon.cmd_collect_evidence(
                ledger_dir,
                out_path=out_path,
                repo_root=repo_root,
                allow_roots=allow_roots_raw,
                item_id_filter=str(args["id"]) if args.get("id") else None,
                reconcile_prs=bool(args.get("reconcile_prs", False)),
                timeout=timeout,
            )

        if tool_name == "horizon_validate_verdict":
            if "verdict" not in args:
                raise horizon.CliUsageError("Missing required 'verdict' argument.")
            verdict_obj = _coerce_doc_or_path(args["verdict"], ledger_dir, "verdict")
            evidence_obj = (
                _coerce_doc_or_path(args["evidence"], ledger_dir, "evidence")
                if args.get("evidence") is not None
                else None
            )
            ledger_items = horizon.load_ledger(ledger_dir / "ledger.jsonl")
            errs = horizon.validate_verdict_payload(verdict_obj, ledger_items, evidence=evidence_obj)
            scope_note = (
                "Checked schema, unique known item_id values, evidence_citations, "
                "triggered_count consistency, secret patterns, and not_inspected parity; "
                "did not judge semantic accuracy of forecast prose."
            )
            if errs:
                return True, {"valid": False, "errors": errs, "scope_note": scope_note}

            saved_to: str | None = None
            if args.get("save_out"):
                save_path = _confine_scratch_or_ledger_path(str(args["save_out"]), ledger_dir, "save_out")
                horizon.atomic_write_text(save_path, json.dumps(verdict_obj, indent=2) + "\n", mode=0o600)
                saved_to = str(save_path)
            result: dict[str, Any] = {
                "valid": True,
                "decisions_checked": len(verdict_obj.get("decisions", [])),
                "triggered_count": verdict_obj.get("triggered_count"),
                "not_inspected_count": len(verdict_obj.get("not_inspected", [])),
                "scope_note": scope_note,
            }
            if saved_to:
                result["saved_out"] = saved_to
            return False, result

        if tool_name == "horizon_backup_target":
            target = args.get("target")
            if not isinstance(target, str) or not target.strip():
                raise horizon.CliUsageError("Missing required 'target' path.")
            allow_roots_raw = args.get("allow_roots") or []
            if not isinstance(allow_roots_raw, list) or any(not isinstance(x, str) for x in allow_roots_raw):
                raise horizon.CliUsageError("allow_roots must be a list of path strings.")
            return False, horizon.cmd_backup_target(ledger_dir, target, allow_roots=allow_roots_raw)

        if tool_name == "horizon_record_action":
            return False, horizon.cmd_record_action(
                ledger_dir,
                item_id=str(args.get("id", "")),
                new_status=str(args.get("status", "")),
                pr_url=args.get("pr_url"),
                backup_path=args.get("backup_path"),
                override_reason=args.get("override_reason"),
                note=args.get("note"),
            )

        if tool_name == "horizon_render_index":
            rc, info = horizon.cmd_render_index(ledger_dir, check=bool(args.get("check", False)))
            return (rc != 0), info

        raise horizon.CliUsageError(f"Unknown Horizon MCP tool: {tool_name!r}")
    except (horizon.CliUsageError, horizon.ValidationFailure, ValueError) as exc:
        return True, {"error": type(exc).__name__, "message": str(exc)}


def handle_rpc_message(ledger_dir: Path, msg: Any) -> dict[str, Any] | None:
    """Process a single JSON-RPC 2.0 message and return a response dict (or ``None`` for notifications)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id") if isinstance(msg, dict) else None,
            "error": {"code": -32600, "message": "Invalid JSON-RPC 2.0 request."},
        }

    method = msg.get("method")
    has_id = "id" in msg
    req_id = msg.get("id")

    if not isinstance(method, str):
        if not has_id:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32600, "message": "Missing string 'method'."},
        }

    if not has_id:
        return None

    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": "'params' must be an object."},
        }

    if method == "initialize":
        requested = str(params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION))
        negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": build_tool_definitions()}}

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    if method == "tools/call":
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Missing tool 'name'."},
            }
        tool_args = params.get("arguments") or {}
        if not isinstance(tool_args, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Tool 'arguments' must be an object."},
            }
        is_error, payload = dispatch_tool(ledger_dir, tool_name, tool_args)
        text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _read_next_message(stream: BinaryIO) -> tuple[Any, str] | tuple[None, None]:
    """Read one MCP message from ``stream``. Supports newline JSON and ``Content-Length`` headers."""
    while True:
        first_line = stream.readline(MAX_MESSAGE_BYTES + 1)
        if not first_line:
            return None, None
        if len(first_line) > MAX_MESSAGE_BYTES:
            raise ValueError("MCP message exceeded maximum size.")
        stripped = first_line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith(b"content-length:"):
            content_length = int(stripped.split(b":", 1)[1].strip())
            if content_length < 0 or content_length > MAX_MESSAGE_BYTES:
                raise ValueError(f"Invalid Content-Length: {content_length}")
            while True:
                hdr = stream.readline(4096)
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            body = stream.read(content_length)
            if len(body) < content_length:
                return None, None
            return json.loads(body.decode("utf-8")), "content-length"

        return json.loads(stripped.decode("utf-8")), "newline"


def _write_message(stream: BinaryIO, payload: Mapping[str, Any], framing: str) -> None:
    if framing == "content-length":
        encoded = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
        stream.write(header + encoded)
    else:
        encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        stream.write(encoded)
    stream.flush()


def serve_stdio(
    ledger_dir: Path,
    *,
    instream: BinaryIO | None = None,
    outstream: BinaryIO | None = None,
) -> int:
    """Run the synchronous JSON-RPC 2.0 MCP server loop over ``stdin``/``stdout``."""
    reader = instream if instream is not None else sys.stdin.buffer
    writer = outstream if outstream is not None else sys.stdout.buffer
    last_framing = "newline"

    while True:
        try:
            msg, framing = _read_next_message(reader)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            _write_message(writer, err_resp, last_framing)
            continue

        if msg is None or framing is None:
            return 0
        last_framing = framing
        response = handle_rpc_message(ledger_dir, msg)
        if response is not None:
            _write_message(writer, response, framing)


def main(argv: list[str] | None = None) -> int:
    ledger_dir = horizon.resolve_ledger_dir(None)
    if argv:
        return horizon.main(["mcp", *argv])
    return serve_stdio(ledger_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
