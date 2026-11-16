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

"""Verification suite for ``horizon_mcp.py`` and cross-process ledger access."""

from __future__ import annotations

import concurrent.futures
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import horizon  # noqa: E402
import horizon_mcp  # noqa: E402


def _sample_record(slug: str, title: str, forecast_text: str) -> dict[str, Any]:
    return {
        "id": slug,
        "title": title,
        "category": "macos-sdk",
        "window": "2027-Q2..2027-Q3",
        "baseline_measurement": "Baseline observed today.",
        "forecast": forecast_text,
        "playbook": "Open a branch and update the adapter.",
        "probes": [
            {
                "kind": "cli_help",
                "binary": "python3",
                "expect_tokens": ["--version"],
            }
        ],
        "targets": [
            {
                "kind": "repo_branch_pr",
                "repo": "ksprashu/agent-skill-forge",
                "path": "skills/horizon/SKILL.md",
            }
        ],
    }


def _record_via_cli_worker(args: tuple[str, str, str]) -> int:
    ledger_dir_str, slug, title = args
    payload = _sample_record(slug, title, f"Forecast for {slug}")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "horizon.py"),
            "record",
            "--ledger-dir",
            ledger_dir_str,
            "--input",
            "-",
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode


class TestHorizonMcpAndPermissions(unittest.TestCase):
    """Tests T1-T6 for MCP server parity, security confinement, and concurrent writes."""

    def test_t3_tool_definitions_derive_from_horizon_constants(self) -> None:
        defs = {t["name"]: t for t in horizon_mcp.build_tool_definitions()}
        expected_names = {
            "horizon_doctor",
            "horizon_list",
            "horizon_record",
            "horizon_collect_evidence",
            "horizon_validate_verdict",
            "horizon_backup_target",
            "horizon_record_action",
            "horizon_render_index",
        }
        self.assertEqual(set(defs.keys()), expected_names)
        self.assertEqual(
            defs["horizon_list"]["inputSchema"]["properties"]["status"]["enum"],
            ["all", *horizon.VALID_STATUSES],
        )
        self.assertEqual(
            defs["horizon_record_action"]["inputSchema"]["properties"]["status"]["enum"],
            list(horizon.ACTION_TRANSITION_STATUSES),
        )

    def test_t1_differentiation_and_lifecycle_via_mcp_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = Path(tmp) / "ledger_a"
            dir_b = Path(tmp) / "ledger_b"

            err_a, res_a = horizon_mcp.dispatch_tool(
                dir_a,
                "horizon_record",
                _sample_record("alpha-mcp-item", "Alpha MCP Forecast", "Alpha drops in Q2"),
            )
            err_b, res_b = horizon_mcp.dispatch_tool(
                dir_b,
                "horizon_record",
                _sample_record("beta-mcp-item", "Beta MCP Forecast", "Beta drops in Q3"),
            )
            self.assertFalse(err_a, res_a)
            self.assertFalse(err_b, res_b)
            self.assertNotEqual(res_a["id"], res_b["id"])

            idx_a = (dir_a / "INDEX.md").read_text(encoding="utf-8")
            idx_b = (dir_b / "INDEX.md").read_text(encoding="utf-8")
            self.assertNotEqual(idx_a, idx_b)
            self.assertIn("Alpha MCP Forecast", idx_a)
            self.assertNotIn("Beta MCP Forecast", idx_a)

            # Collect evidence & validate inline verdict object without scratch files.
            err_ev, ev = horizon_mcp.dispatch_tool(dir_a, "horizon_collect_evidence", {})
            self.assertFalse(err_ev, ev)
            self.assertEqual(ev["items_evaluated"], 1)

            verdict = {
                "schema_version": "1",
                "evaluated_at": "2026-11-15T18:00:00Z",
                "summary": "Verified unchanged via MCP.",
                "triggered_count": 0,
                "not_inspected": ev["not_inspected"],
                "decisions": [
                    {
                        "item_id": "alpha-mcp-item",
                        "decision": "no_change",
                        "summary": "CLI tokens match.",
                        "evidence_citations": ["probes[0].available=True"],
                    }
                ],
            }
            err_val, val_res = horizon_mcp.dispatch_tool(
                dir_a,
                "horizon_validate_verdict",
                {
                    "verdict": verdict,
                    "evidence": ev,
                    "save_out": str(dir_a / "runs" / "latest-verdict.json"),
                },
            )
            self.assertFalse(err_val, val_res)
            self.assertTrue(val_res["valid"])
            self.assertTrue((dir_a / "runs" / "latest-verdict.json").is_file())

    def test_t4_negative_security_confinement_and_l3_gate_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / "horizons"
            outside_file = root / "outside_escape.json"

            horizon_mcp.dispatch_tool(
                ledger_dir,
                "horizon_record",
                _sample_record("neg-check-item", "Negative Check", "Forecast body"),
            )

            # 1. Confine collect_evidence 'out' against writing outside ledger_dir / system temp:
            #    Create a directory outside system temp if possible, or test '..' traversal rejection.
            is_err, payload = horizon_mcp.dispatch_tool(
                ledger_dir,
                "horizon_collect_evidence",
                {"out": str(ledger_dir / ".." / "escape.json")},
            )
            self.assertTrue(is_err)
            self.assertIn("traversal", payload["message"])
            self.assertFalse(outside_file.exists())

            # 2. Bad verdict (contradictory triggered_count) MUST return isError=True.
            bad_verdict = {
                "schema_version": "1",
                "evaluated_at": "2026-11-15T18:00:00Z",
                "summary": "Contradictory verdict.",
                "triggered_count": 5,
                "not_inspected": [],
                "decisions": [
                    {
                        "item_id": "neg-check-item",
                        "decision": "no_change",
                        "summary": "No change.",
                        "evidence_citations": ["probes[0]"],
                    }
                ],
            }
            is_err_v, val_payload = horizon_mcp.dispatch_tool(
                ledger_dir, "horizon_validate_verdict", {"verdict": bad_verdict}
            )
            self.assertTrue(is_err_v)
            self.assertFalse(val_payload["valid"])

            # 3. Unprovenanced pr_opened transition MUST fail closed (isError=True).
            is_err_act, act_payload = horizon_mcp.dispatch_tool(
                ledger_dir,
                "horizon_record_action",
                {"id": "neg-check-item", "status": "pr_opened"},
            )
            self.assertTrue(is_err_act)
            self.assertIn("requires a valid --pr-url", act_payload["message"])

    def test_conditional_chmod_skips_redundant_call_but_fixes_loose_perms(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX permission check")
        with tempfile.TemporaryDirectory() as tmp:
            secure_dir = Path(tmp) / "already_secure"
            secure_dir.mkdir(mode=0o700)
            os.chmod(secure_dir, 0o700)

            with mock.patch("os.chmod", wraps=os.chmod) as spy_chmod:
                horizon.ensure_secure_dir(secure_dir)
                spy_chmod.assert_not_called()

            loose_dir = Path(tmp) / "loose_dir"
            loose_dir.mkdir(mode=0o755)
            os.chmod(loose_dir, 0o755)
            with mock.patch("os.chmod", wraps=os.chmod) as spy_chmod_fix:
                horizon.ensure_secure_dir(loose_dir)
                spy_chmod_fix.assert_called_once_with(loose_dir, 0o700)

    def test_stdio_framing_both_newline_and_content_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "horizons"

            # 1. Newline-delimited JSON-RPC (MCP 2024-11-05 / 2025-03-26 standard)
            req_init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            req_doc = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "horizon_doctor", "arguments": {}}}
            in_bytes = (
                json.dumps(req_init) + "\n" + json.dumps(notif) + "\n" + json.dumps(req_doc) + "\n"
            ).encode("utf-8")
            out_buf = io.BytesIO()
            rc = horizon_mcp.serve_stdio(ledger_dir, instream=io.BytesIO(in_bytes), outstream=out_buf)
            self.assertEqual(rc, 0)
            lines = [json.loads(line) for line in out_buf.getvalue().decode("utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["result"]["protocolVersion"], "2025-03-26")
            doc_payload = json.loads(lines[1]["result"]["content"][0]["text"])
            self.assertEqual(doc_payload["status"], "ok")

            # 2. Content-Length framed JSON-RPC
            body = json.dumps({"jsonrpc": "2.0", "id": 99, "method": "tools/list", "params": {}}).encode("utf-8")
            cl_in = io.BytesIO(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
            cl_out = io.BytesIO()
            self.assertEqual(horizon_mcp.serve_stdio(ledger_dir, instream=cl_in, outstream=cl_out), 0)
            raw_reply = cl_out.getvalue()
            self.assertTrue(raw_reply.startswith(b"Content-Length: "))
            _, reply_body = raw_reply.split(b"\r\n\r\n", 1)
            parsed_reply = json.loads(reply_body.decode("utf-8"))
            self.assertEqual(parsed_reply["id"], 99)
            self.assertEqual(len(parsed_reply["result"]["tools"]), 8)

    def test_t5_live_mcp_subprocess_and_concurrent_cli_processes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "shared_horizons"
            env = {**os.environ, "FORGE_HORIZONS_DIR": str(ledger_dir)}
            mcp_proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / "horizon.py"), "mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            assert mcp_proc.stdin is not None and mcp_proc.stdout is not None
            try:
                # Initialize MCP subprocess
                init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
                mcp_proc.stdin.write((json.dumps(init_msg) + "\n").encode("utf-8"))
                mcp_proc.stdin.flush()
                init_resp = json.loads(mcp_proc.stdout.readline().decode("utf-8"))
                self.assertEqual(init_resp["result"]["serverInfo"]["name"], "horizon")

                # Fire 6 concurrent CLI processes while interleaving 4 MCP record calls on the SAME ledger!
                cli_tasks = [(str(ledger_dir), f"cli-proc-item-{idx}", f"CLI Item {idx}") for idx in range(6)]
                with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
                    futs = [pool.submit(_record_via_cli_worker, t) for t in cli_tasks]
                    for m_idx in range(4):
                        call_msg = {
                            "jsonrpc": "2.0",
                            "id": 10 + m_idx,
                            "method": "tools/call",
                            "params": {
                                "name": "horizon_record",
                                "arguments": _sample_record(
                                    f"mcp-conv-item-{m_idx}",
                                    f"MCP Conversation {m_idx}",
                                    f"MCP forecast {m_idx}",
                                ),
                            },
                        }
                        mcp_proc.stdin.write((json.dumps(call_msg) + "\n").encode("utf-8"))
                        mcp_proc.stdin.flush()
                        call_resp = json.loads(mcp_proc.stdout.readline().decode("utf-8"))
                        self.assertFalse(call_resp["result"]["isError"], call_resp)

                    for fut in futs:
                        self.assertEqual(fut.result(), 0)

                # Verify all 10 concurrent items persisted cleanly and INDEX.md is byte-fresh!
                chk_msg = {
                    "jsonrpc": "2.0",
                    "id": 99,
                    "method": "tools/call",
                    "params": {"name": "horizon_render_index", "arguments": {"check": True}},
                }
                mcp_proc.stdin.write((json.dumps(chk_msg) + "\n").encode("utf-8"))
                mcp_proc.stdin.flush()
                chk_resp = json.loads(mcp_proc.stdout.readline().decode("utf-8"))
                self.assertFalse(chk_resp["result"]["isError"], chk_resp)
                chk_info = json.loads(chk_resp["result"]["content"][0]["text"])
                self.assertEqual(chk_info["item_count"], 10)
            finally:
                mcp_proc.stdin.close()
                mcp_proc.wait(timeout=5)
                if mcp_proc.stderr:
                    mcp_proc.stderr.close()
                mcp_proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
