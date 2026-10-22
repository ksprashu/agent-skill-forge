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

"""Tests for preferred/agent-security-posture/scripts/check_vulns.py.

The script is run as a subprocess against a local fake OSV/NVD server, so
exit codes are tested the way an agent or CI would read them. The fake NVD
mirrors the real API's rule that pubStartDate without pubEndDate is a 404.
"""

from __future__ import annotations

import datetime as dt
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "preferred" / "agent-security-posture" / "scripts" / "check_vulns.py"

sys.path.insert(0, str(SCRIPT.parent))
import check_vulns  # noqa: E402


class FakeServer(http.server.BaseHTTPRequestHandler):
    """Behaviour is set per test through class attributes."""

    mode = "ok"           # ok | vulns | error500 | badjson | listjson | short
    nvd_total = 0
    nvd_returned = None   # None means return all nvd_total entries
    seen_bodies: list = []
    seen_paths: list = []

    def log_message(self, *args):  # keep test output clean
        pass

    def _send(self, code: int, payload) -> None:
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", "0")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServer.seen_bodies.append(body)
        if FakeServer.mode == "error500":
            return self._send(500, {"error": "boom"})
        if FakeServer.mode == "badjson":
            return self._send(200, b"{not json")
        if FakeServer.mode == "listjson":
            return self._send(200, [])
        if FakeServer.mode == "nullresults":
            return self._send(200, {"results": [None] * len(body["queries"])})
        if FakeServer.mode == "badvulns":
            return self._send(200, {"results": [{"vulns": ["GHSA-x"]}] * len(body["queries"])})
        queries = body["queries"]
        if FakeServer.mode == "short":
            return self._send(200, {"results": [{}]})
        results = []
        for q in queries:
            if FakeServer.mode == "vulns" and q["package"]["name"] == "lodash":
                results.append({"vulns": [{"id": "GHSA-test-0001"}]})
            else:
                results.append({})
        return self._send(200, {"results": results})

    def do_GET(self):
        FakeServer.seen_paths.append(self.path)
        if FakeServer.mode == "error500":
            return self._send(500, {})
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        if "pubStartDate" in qs and "pubEndDate" not in qs:
            return self._send(404, {})
        count = FakeServer.nvd_total if FakeServer.nvd_returned is None else FakeServer.nvd_returned
        vulns = [{"cve": {"id": f"CVE-2026-{i:05d}"}} for i in range(count)]
        return self._send(200, {"totalResults": FakeServer.nvd_total,
                                "vulnerabilities": vulns})


class CheckVulnsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeServer.mode = "ok"
        FakeServer.nvd_total = 0
        FakeServer.nvd_returned = None
        FakeServer.seen_bodies = []
        FakeServer.seen_paths = []
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args: str):
        env = {**os.environ, "ASP_OSV_URL": self.base,
               "ASP_NVD_URL": self.base + "/rest/json/cves/2.0",
               "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
        env.pop("NVD_API_KEY", None)
        proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env,
                              timeout=60, shell=False)
        report = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
        return proc.returncode, report, proc.stderr

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def npm_lock(self) -> Path:
        return self.write("package-lock.json", json.dumps({
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "app", "version": "1.0.0"},
                "node_modules/lodash": {"version": "4.17.20"},
                "node_modules/express": {"version": "4.19.2"},
            }}))

    # --- usage errors (T4: negative tests) ---------------------------------

    def test_no_arguments_is_usage_error(self):
        code, _, _ = self.run_script()
        self.assertEqual(code, 64)

    def test_unsupported_lockfile_is_usage_error(self):
        path = self.write("Gemfile.lock", "GEM\n")
        code, _, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 64)
        self.assertIn("unsupported lockfile", err)

    def test_days_over_nvd_limit_is_usage_error(self):
        code, _, _ = self.run_script("recent", "--days", "121")
        self.assertEqual(code, 64)

    # --- lockfile mode (T1: differentiation) -------------------------------

    def test_clean_lockfile_exits_zero(self):
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "checked")
        self.assertEqual(report["packages_checked"], 2)

    def test_advisory_exits_one_and_names_it(self):
        FakeServer.mode = "vulns"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "finding")
        self.assertEqual(report["advisories"][0]["name"], "lodash")
        self.assertEqual(report["advisories"][0]["ids"], ["GHSA-test-0001"])

    def test_only_identifiers_leave_the_machine(self):
        path = self.npm_lock()
        self.run_script("lockfile", str(path))
        sent = json.dumps(FakeServer.seen_bodies)
        self.assertNotIn(str(self.dir), sent)
        query = FakeServer.seen_bodies[0]["queries"][0]
        self.assertEqual(set(query), {"package", "version"})
        self.assertEqual(set(query["package"]), {"ecosystem", "name"})

    def test_unpinned_requirement_makes_result_partial(self):
        path = self.write("requirements.txt", "requests==2.32.3\nflask>=3\n")
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["unresolved"], ["line 2: flask (not pinned with ==)"])

    def test_server_error_is_unavailable_not_clean(self):
        FakeServer.mode = "error500"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["packages_checked"], 0)

    def test_malformed_json_is_unavailable(self):
        FakeServer.mode = "badjson"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")

    def test_mismatched_result_count_is_unavailable(self):
        FakeServer.mode = "short"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)

    def test_wrong_shape_json_is_unavailable(self):
        FakeServer.mode = "listjson"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")

    def test_credentials_in_requirements_never_reach_output(self):
        secret = "s3cr3t-t0ken-value"
        path = self.write("requirements.txt",
                          "requests==2.32.3\n"
                          f"private-client @ https://user:{secret}@pkgs.example.invalid/c.whl\n")
        code, report, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn(secret, err)
        self.assertNotIn(secret, json.dumps(FakeServer.seen_bodies))
        self.assertEqual(report["unresolved"],
                         ["line 2: private-client (not pinned with ==)"])

    def test_include_directive_makes_result_partial(self):
        path = self.write("requirements.txt", "-r base.txt\n")
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["unresolved"], ["line 1: -r directive not followed"])

    def test_attached_short_option_makes_result_partial(self):
        path = self.write("requirements.txt", "-rbase.txt\n-e./local-pkg\n")
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["unresolved"], ["line 1: -r directive not followed",
                                                "line 2: -e directive not followed"])
        self.assertNotIn("base.txt", json.dumps(report))

    def test_null_result_entries_are_unavailable(self):
        FakeServer.mode = "nullresults"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)
        self.assertEqual(report["packages_checked"], 0)

    def test_malformed_vuln_entries_are_unavailable(self):
        FakeServer.mode = "badvulns"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")

    def test_poetry_and_cargo_non_registry_sources_are_unresolved(self):
        poetry = self.write("poetry.lock",
                            '[[package]]\nname = "requests"\nversion = "2.32.3"\n\n'
                            '[[package]]\nname = "inhouse"\nversion = "1.0.0"\n'
                            '[package.source]\ntype = "git"\nurl = "https://u:tok@git.example/x.git"\n')
        cargo_dir = self.dir / "c"
        cargo_dir.mkdir()
        cargo = cargo_dir / "Cargo.lock"
        cargo.write_text(
            '[[package]]\nname = "app"\nversion = "0.1.0"\n\n'
            '[[package]]\nname = "serde"\nversion = "1.0.200"\n'
            'source = "registry+https://github.com/rust-lang/crates.io-index"\n\n'
            '[[package]]\nname = "forked"\nversion = "1.0.0"\n'
            'source = "git+https://u:tok@git.example/forked#abc"\n', encoding="utf-8")
        code, report, err = self.run_script("lockfile", str(poetry), str(cargo))
        self.assertEqual(code, 2)
        self.assertEqual(report["packages_checked"], 2)
        self.assertEqual(sorted(report["unresolved"]),
                         ["forked (non-crates.io source)", "inhouse (non-PyPI source)"])
        self.assertNotIn("tok", json.dumps(report) + err + json.dumps(FakeServer.seen_bodies))

    def test_hash_continuation_lines_are_not_unresolved(self):
        path = self.write("requirements.txt",
                          "requests==2.32.3 \\\n    --hash=sha256:abc\n"
                          "--index-url https://pypi.org/simple\n")
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 0)
        self.assertEqual(report["unresolved"], [])

    def test_npm_git_source_is_not_sent(self):
        secret = "gh-t0ken-value"
        path = self.write("package-lock.json", json.dumps({
            "lockfileVersion": 1,
            "dependencies": {
                "private-lib": {"version": f"git+https://u:{secret}@github.example/x.git"},
                "express": {"version": "4.19.2"},
            }}))
        code, report, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        sent = json.dumps(FakeServer.seen_bodies)
        self.assertNotIn(secret, sent)
        self.assertNotIn(secret, json.dumps(report) + err)
        self.assertEqual(report["packages_checked"], 1)
        self.assertEqual(report["unresolved"], ["private-lib (no registry version)"])

    # --- recent mode -------------------------------------------------------

    def test_recent_incomplete_page_is_partial(self):
        FakeServer.nvd_total = 51
        FakeServer.nvd_returned = 50
        code, report, _ = self.run_script("recent")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")

    def test_recent_sends_both_dates(self):
        FakeServer.nvd_total = 3
        code, report, _ = self.run_script("recent", "--days", "7")
        self.assertEqual(code, 1)
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(FakeServer.seen_paths[0]).query)
        self.assertIn("pubStartDate", qs)
        self.assertIn("pubEndDate", qs)
        self.assertEqual(report["nvd"]["total"], 3)

    def test_recent_with_no_cves_exits_zero(self):
        code, report, _ = self.run_script("recent")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "checked")

    def test_recent_unreachable_is_unavailable(self):
        FakeServer.mode = "error500"
        code, report, _ = self.run_script("recent")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")

    # --- parsers, in process (T3: derive from fixtures) --------------------

    def test_window_is_exact_days_apart(self):
        now = dt.datetime(2026, 10, 22, 12, 0, tzinfo=dt.timezone.utc)
        start, end = check_vulns.nvd_window(7, now)
        self.assertEqual(start, "2026-10-15T12:00:00.000")
        self.assertEqual(end, "2026-10-22T12:00:00.000")

    def test_parsers_read_each_supported_format(self):
        cargo = ('[[package]]\nname = "serde"\nversion = "1.0.200"\n'
                 'source = "registry+https://github.com/rust-lang/crates.io-index"\n')
        poetry = '[[package]]\nname = "requests"\nversion = "2.32.3"\n'
        gosum = ("golang.org/x/net v0.23.0 h1:abc=\n"
                 "golang.org/x/net v0.23.0/go.mod h1:def=\n")
        self.assertEqual(check_vulns.parse_cargo(cargo)[0][0]["ecosystem"], "crates.io")
        self.assertEqual(check_vulns.parse_poetry(poetry)[0][0]["version"], "2.32.3")
        go = check_vulns.parse_gosum(gosum)[0]
        self.assertEqual(len(go), 1)
        self.assertEqual(go[0]["version"], "0.23.0")


if __name__ == "__main__":
    unittest.main()
