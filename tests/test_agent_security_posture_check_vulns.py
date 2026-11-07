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
    # Enrichment fakes: OSV advisory aliases, KEV listing, EPSS rows, and
    # which enrichment sources should fail ("osvvuln", "kev", "epss").
    vuln_aliases: dict = {}
    kev_cves: list = []
    enrich_fail: set = set()

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
        route = urllib.parse.urlsplit(self.path).path
        if route.startswith("/v1/vulns/"):
            if "osvvuln" in FakeServer.enrich_fail:
                return self._send(500, {})
            vid = urllib.parse.unquote(route.rsplit("/", 1)[-1])
            return self._send(200, {"id": vid,
                                    "aliases": FakeServer.vuln_aliases.get(vid, [])})
        if route == "/kev.json":
            if "kev" in FakeServer.enrich_fail:
                return self._send(200, b"{broken")
            return self._send(200, {"vulnerabilities": [
                {"cveID": c, "dateAdded": "2024-01-02"} for c in FakeServer.kev_cves]})
        if route == "/epss":
            if "epss" in FakeServer.enrich_fail:
                return self._send(500, {})
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            cves = qs.get("cve", [""])[0].split(",")
            return self._send(200, {"data": [{"cve": c, "epss": "0.42",
                                              "percentile": "0.97",
                                              "date": "2026-10-23"} for c in cves if c]})
        if FakeServer.mode == "error500":
            return self._send(500, {})
        if FakeServer.mode == "nullcve":
            return self._send(200, {"totalResults": 1, "vulnerabilities": [{"cve": None}]})
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
        FakeServer.vuln_aliases = {}
        FakeServer.kev_cves = []
        FakeServer.enrich_fail = set()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args: str, env_extra: dict | None = None):
        env = {**os.environ, "ASP_OSV_URL": self.base,
               "ASP_NVD_URL": self.base + "/rest/json/cves/2.0",
               "ASP_KEV_URL": self.base + "/kev.json",
               "ASP_EPSS_URL": self.base + "/epss",
               "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
        env.pop("NVD_API_KEY", None)
        env.pop("ASP_GH_BIN", None)
        env.update(env_extra or {})
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
                "node_modules/lodash": {"version": "4.17.20",
                                        "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz"},
                "node_modules/express": {"version": "4.19.2",
                                         "resolved": "https://registry.npmjs.org/express/-/express-4.19.2.tgz"},
            }}))

    # --- usage errors (T4: negative tests) ---------------------------------

    def test_no_arguments_is_usage_error(self):
        code, _, _ = self.run_script()
        self.assertEqual(code, 64)

    def test_unsupported_lockfile_is_usage_error(self):
        path = self.write("composer.lock", "{}\n")
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

    def test_npm_git_resolved_and_workspace_entries_are_not_sent(self):
        # PR #5 review (ChatGPT, Grok Bot): a registry-looking version with a
        # git source, and a workspace path, were both sent as public packages.
        secret = "ws-t0ken"
        path = self.write("package-lock.json", json.dumps({
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "app", "version": "1.0.0"},
                "packages/internal-lib": {"name": "internal-lib", "version": "1.0.0"},
                "node_modules/internal-lib": {"resolved": "packages/internal-lib", "link": True},
                "node_modules/forked": {"version": "1.2.3",
                                        "resolved": f"git+ssh://git@github.example/o/forked.git#{secret}"},
                "node_modules/mirrored": {"version": "2.0.0",
                                          "resolved": "https://npm.private.example/mirrored-2.0.0.tgz"},
                "node_modules/express": {"version": "4.19.2",
                                         "resolved": "https://registry.npmjs.org/express/-/express-4.19.2.tgz"},
            }}))
        code, report, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["packages_checked"], 1)
        self.assertEqual(sorted(report["unresolved"]),
                         ["forked (not from the public npm registry)",
                          "mirrored (not from the public npm registry)"])
        sent = json.dumps(FakeServer.seen_bodies)
        self.assertNotIn("internal-lib", sent)
        self.assertNotIn("forked", sent)
        self.assertNotIn(secret, sent + json.dumps(report) + err)

    def test_non_exact_python_pins_are_unresolved(self):
        # PR #5 review: ==2.* and compound specifiers were reported as checked.
        path = self.write("requirements.txt",
                          "requests==2.*\nurllib3==2.2.1,!=2.2.0\nidna==3.7\n")
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["packages_checked"], 1)
        self.assertEqual(report["unresolved"],
                         ["line 1: requests (not one exact version)",
                          "line 2: urllib3 (not one exact version)"])

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
                "express": {"version": "4.19.2",
                            "resolved": "https://registry.npmjs.org/express/-/express-4.19.2.tgz"},
            }}))
        code, report, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        sent = json.dumps(FakeServer.seen_bodies)
        self.assertNotIn(secret, sent)
        self.assertNotIn(secret, json.dumps(report) + err)
        self.assertEqual(report["packages_checked"], 1)
        self.assertEqual(report["unresolved"], ["private-lib (no registry version)"])

    # --- recent mode -------------------------------------------------------

    def test_recent_null_cve_entry_is_unavailable(self):
        # PR #5 review: {"cve": null} raised AttributeError instead of exit 2.
        FakeServer.mode = "nullcve"
        code, report, _ = self.run_script("recent")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "unavailable")

    def test_nvd_validation_in_process(self):
        original = check_vulns._request
        try:
            check_vulns._request = lambda *a, **k: {"totalResults": 1,
                                                    "vulnerabilities": [{"cve": None}]}
            nvd, problems = check_vulns.nvd_recent(7, "HIGH")
        finally:
            check_vulns._request = original
        self.assertTrue(problems)
        self.assertNotIn("listed", nvd)

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

    # --- new lockfile formats (T1/T3/T4) ------------------------------------

    def test_pnpm_lock_versions_v5_v6_v9_and_non_registry(self):
        secret = "pn-t0ken"
        v6 = ("lockfileVersion: '6.0'\n\npackages:\n\n"
              "  /lodash@4.17.20:\n    resolution: {integrity: sha512-x}\n    dev: false\n\n"
              "  /@babel/core@7.24.0(supports-color@8.1.1):\n    resolution: {integrity: sha512-y}\n\n"
              f"  /github.com/o/forked/abc123:\n    resolution: {{tarball: https://u:{secret}@codeload.example/x}}\n"
              "    name: forked\n    version: 1.0.0\n")
        pkgs, unresolved = check_vulns.parse_pnpm(v6)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("lodash", "4.17.20"), ("@babel/core", "7.24.0")})
        self.assertEqual(unresolved, ["forked (not from the public npm registry)"])
        self.assertNotIn(secret, json.dumps([pkgs, unresolved]))
        v9 = ("lockfileVersion: '9.0'\n\nimporters:\n  .:\n    dependencies:\n"
              "      lodash:\n        specifier: ^4\n\npackages:\n\n"
              "  lodash@4.17.21:\n    resolution: {integrity: sha512-x}\n\n"
              "  '@types/node@20.1.0':\n    resolution: {integrity: sha512-z}\n\n"
              "  local-lib@file:../local-lib:\n    resolution: {directory: ../local-lib, type: directory}\n\n"
              "snapshots:\n\n  lodash@4.17.21: {}\n")
        pkgs, unresolved = check_vulns.parse_pnpm(v9)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("lodash", "4.17.21"), ("@types/node", "20.1.0")})
        self.assertEqual(unresolved, ["local-lib (not from the public npm registry)"])
        v5 = ("lockfileVersion: 5.4\npackages:\n  /left-pad/1.3.0:\n    resolution: {integrity: x}\n"
              "  /@scope/pkg/2.0.0_react@18.2.0:\n    resolution: {integrity: y}\n")
        pkgs, _ = check_vulns.parse_pnpm(v5)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("left-pad", "1.3.0"), ("@scope/pkg", "2.0.0")})

    def test_yarn_classic_lock(self):
        secret = "yarn-t0ken"
        text = ('# yarn lockfile v1\n\n'
                '"lodash@^4.17.0", lodash@~4.17.20:\n  version "4.17.20"\n'
                '  resolved "https://registry.yarnpkg.com/lodash/-/lodash-4.17.20.tgz#abc"\n\n'
                '"@babel/core@^7":\n  version "7.24.0"\n'
                '  resolved "https://registry.npmjs.org/@babel/core/-/core-7.24.0.tgz"\n\n'
                f'"forked@git+https://u:{secret}@git.example/forked.git":\n  version "1.0.0"\n'
                f'  resolved "git+https://u:{secret}@git.example/forked.git#abc"\n\n'
                'mirrored@^2:\n  version "2.0.0"\n'
                '  resolved "https://npm.private.example/mirrored-2.0.0.tgz"\n')
        pkgs, unresolved = check_vulns.parse_yarn(text)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("lodash", "4.17.20"), ("@babel/core", "7.24.0")})
        self.assertEqual(sorted(unresolved),
                         ["forked (not from the public npm registry)",
                          "mirrored (not from the public npm registry)"])
        self.assertNotIn(secret, json.dumps([pkgs, unresolved]))

    def test_yarn_berry_lock(self):
        text = ('__metadata:\n  version: 8\n  cacheKey: 10\n\n'
                '"lodash@npm:^4.17.0":\n  version: 4.17.21\n'
                '  resolution: "lodash@npm:4.17.21"\n  languageName: node\n  linkType: hard\n\n'
                '"app@workspace:.":\n  version: 0.0.0-use.local\n'
                '  resolution: "app@workspace:."\n  linkType: soft\n\n'
                '"forked@https://github.com/o/forked.git#commit=abc":\n  version: 1.0.0\n'
                '  resolution: "forked@https://github.com/o/forked.git#commit=abc"\n\n'
                '"resolve@patch:resolve@npm%3A^1#~builtin<compat/resolve>":\n  version: 1.22.8\n'
                '  resolution: "resolve@patch:resolve@npm%3A1.22.8#~builtin<compat/resolve>::version=1.22.8"\n')
        pkgs, unresolved = check_vulns.parse_yarn(text)
        self.assertEqual(pkgs, [{"ecosystem": "npm", "name": "lodash", "version": "4.17.21"}])
        self.assertEqual(unresolved, ["forked (non-npm source)"])

    def test_uv_lock(self):
        text = ('version = 1\n\n'
                '[[package]]\nname = "requests"\nversion = "2.32.3"\n'
                'source = { registry = "https://pypi.org/simple" }\n\n'
                '[[package]]\nname = "app"\nversion = "0.1.0"\nsource = { editable = "." }\n\n'
                '[[package]]\nname = "inhouse"\nversion = "1.0.0"\n'
                'source = { git = "https://u:uvtok@git.example/x.git" }\n\n'
                '[[package]]\nname = "mirrored"\nversion = "2.0.0"\n'
                'source = { registry = "https://pkgs.private.example/simple" }\n')
        pkgs, unresolved = check_vulns.parse_uvlock(text)
        self.assertEqual(pkgs, [{"ecosystem": "PyPI", "name": "requests", "version": "2.32.3"}])
        self.assertEqual(unresolved, ["inhouse (non-PyPI source)", "mirrored (non-PyPI source)"])
        self.assertNotIn("uvtok", json.dumps(unresolved))

    def test_pipfile_lock(self):
        text = json.dumps({
            "_meta": {"sources": [{"name": "pypi", "url": "https://pypi.org/simple"},
                                  {"name": "corp", "url": "https://pkgs.private.example/simple"}]},
            "default": {"requests": {"version": "==2.32.3", "index": "pypi"},
                        "inhouse": {"git": "https://u:piptok@git.example/x.git", "ref": "abc"},
                        "private": {"version": "==1.0.0", "index": "corp"}},
            "develop": {"pytest": {"version": "==8.3.2"},
                        "local": {"path": ".", "editable": True}}})
        pkgs, unresolved = check_vulns.parse_pipfile_lock(text)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("requests", "2.32.3"), ("pytest", "8.3.2")})
        self.assertEqual(sorted(unresolved), ["inhouse (non-PyPI source)",
                                              "local (non-PyPI source)",
                                              "private (non-PyPI index)"])
        self.assertNotIn("piptok", json.dumps(unresolved))

    def test_gemfile_lock(self):
        text = ("GIT\n  remote: https://u:gemtok@git.example/forked.git\n  revision: abc\n"
                "  specs:\n    forked (1.0.0)\n\n"
                "PATH\n  remote: ../local\n  specs:\n    localgem (0.1.0)\n\n"
                "GEM\n  remote: https://rubygems.org/\n  specs:\n"
                "    nokogiri (1.15.4-x86_64-linux)\n      racc (~> 1.4)\n"
                "    rails (7.1.3)\n    racc (1.7.3)\n\n"
                "PLATFORMS\n  x86_64-linux\n\nDEPENDENCIES\n  rails (= 7.1.3)\n\n"
                "BUNDLED WITH\n   2.5.6\n")
        pkgs, unresolved = check_vulns.parse_gemfile_lock(text)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("nokogiri", "1.15.4"), ("rails", "7.1.3"), ("racc", "1.7.3")})
        self.assertEqual({p["ecosystem"] for p in pkgs}, {"RubyGems"})
        self.assertEqual(unresolved, ["forked (non-rubygems.org source)",
                                      "localgem (non-rubygems.org source)"])
        self.assertNotIn("gemtok", json.dumps(unresolved))

    def test_gradle_lockfile(self):
        text = ("# This is a Gradle generated file for dependency locking.\n"
                "com.google.guava:guava:33.0.0-jre=compileClasspath,runtimeClasspath\n"
                "org.slf4j:slf4j-api:2.0.9=runtimeClasspath\n"
                "empty=annotationProcessor\n")
        pkgs, unresolved = check_vulns.parse_gradle_lockfile(text)
        self.assertEqual(pkgs, [
            {"ecosystem": "Maven", "name": "com.google.guava:guava", "version": "33.0.0-jre"},
            {"ecosystem": "Maven", "name": "org.slf4j:slf4j-api", "version": "2.0.9"}])
        self.assertEqual(unresolved, [])

    POM = ('<?xml version="1.0"?>\n'
           '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
           '  <groupId>com.example</groupId><artifactId>app</artifactId><version>1.0</version>\n'
           '  <properties><jackson.version>2.15.2</jackson.version></properties>\n'
           '  <dependencyManagement><dependencies>\n'
           '    <dependency><groupId>org.springframework</groupId>'
           '<artifactId>spring-core</artifactId><version>6.1.0</version></dependency>\n'
           '  </dependencies></dependencyManagement>\n'
           '  <dependencies>\n'
           '    <dependency><groupId>com.fasterxml.jackson.core</groupId>'
           '<artifactId>jackson-databind</artifactId><version>${jackson.version}</version></dependency>\n'
           '    <dependency><groupId>${project.groupId}</groupId>'
           '<artifactId>sibling</artifactId><version>${project.version}</version></dependency>\n'
           '    <dependency><groupId>org.apache.commons</groupId>'
           '<artifactId>commons-text</artifactId><version>${commons.version}</version></dependency>\n'
           '    <dependency><groupId>junit</groupId><artifactId>junit</artifactId>'
           '<version>[4.0,5.0)</version></dependency>\n'
           '    <dependency><groupId>org.springframework</groupId>'
           '<artifactId>spring-core</artifactId></dependency>\n'
           '  </dependencies>\n</project>\n')

    def test_pom_explicit_versions_and_unresolved(self):
        pkgs, unresolved = check_vulns.parse_pom(self.POM)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("org.springframework:spring-core", "6.1.0"),
                          ("com.fasterxml.jackson.core:jackson-databind", "2.15.2"),
                          ("com.example:sibling", "1.0")})
        self.assertEqual(unresolved, [
            "org.apache.commons:commons-text (unresolved property ${commons.version})",
            "junit:junit (version range)",
            "org.springframework:spring-core (version managed elsewhere)"])

    def test_pom_unresolved_property_is_partial_with_coverage_note(self):
        path = self.write("pom.xml", self.POM)
        code, report, _ = self.run_script("lockfile", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["packages_checked"], 3)
        self.assertIn("transitive", report["coverage_notes"][0])

    def test_pom_with_doctype_is_refused(self):
        path = self.write("pom.xml", '<?xml version="1.0"?>\n<!DOCTYPE p [<!ENTITY x "y">]>\n'
                                     '<project>&x;</project>\n')
        code, _, err = self.run_script("lockfile", str(path))
        self.assertEqual(code, 64)
        self.assertIn("DOCTYPE", err)
        self.assertEqual(FakeServer.seen_bodies, [])

    def test_gosum_go_mod_only_lines_are_not_counted(self):
        gosum = ("golang.org/x/net v0.23.0 h1:abc=\n"
                 "golang.org/x/net v0.23.0/go.mod h1:def=\n"
                 "golang.org/x/net v0.10.0/go.mod h1:old=\n"
                 "golang.org/x/text v0.14.0/go.mod h1:ghi=\n")
        pkgs, _ = check_vulns.parse_gosum(gosum)
        self.assertEqual(pkgs, [{"ecosystem": "Go", "name": "golang.org/x/net",
                                 "version": "0.23.0"}])

    GOMOD = ("module example.com/app\n\ngo 1.22\n\n"
             "require github.com/pkg/errors v0.9.1\n\n"
             "require (\n\tgolang.org/x/net v0.23.0\n"
             "\tgolang.org/x/text v0.14.0 // indirect\n"
             "\texample.com/forked v1.0.0\n\texample.com/local v0.0.0\n)\n\n"
             "replace example.com/local => ../local\n"
             "replace example.com/forked v1.0.0 => example.com/fork2 v1.0.1\n")

    def test_gomod_require_and_replace(self):
        pkgs, unresolved = check_vulns.parse_gomod(self.GOMOD)
        self.assertEqual({(p["name"], p["version"]) for p in pkgs},
                         {("github.com/pkg/errors", "0.9.1"), ("golang.org/x/net", "0.23.0"),
                          ("golang.org/x/text", "0.14.0"), ("example.com/fork2", "1.0.1")})
        self.assertEqual(unresolved, ["example.com/local (replaced by a local path)"])

    def test_gomod_and_gosum_together_do_not_double_count(self):
        mod = self.write("go.mod", "module m\n\ngo 1.22\n\nrequire golang.org/x/net v0.23.0\n")
        gosum = self.write("go.sum", "golang.org/x/net v0.23.0 h1:a=\n"
                                     "golang.org/x/net v0.23.0/go.mod h1:b=\n"
                                     "golang.org/x/crypto v0.1.0 h1:c=\n")
        code, report, _ = self.run_script("lockfile", str(mod), str(gosum))
        self.assertEqual(code, 0)
        self.assertEqual(report["packages_checked"], 1)
        self.assertEqual(len(FakeServer.seen_bodies[0]["queries"]), 1)

    def test_new_formats_send_no_credentials(self):
        secret = "cred-t0ken"
        yarn = self.write("yarn.lock",
                          f'"forked@git+https://u:{secret}@git.example/f.git":\n  version "1.0.0"\n'
                          f'  resolved "git+https://u:{secret}@git.example/f.git#abc"\n'
                          'lodash@^4:\n  version "4.17.20"\n'
                          '  resolved "https://registry.yarnpkg.com/lodash/-/lodash-4.17.20.tgz"\n')
        code, report, err = self.run_script("lockfile", str(yarn))
        self.assertEqual(code, 2)
        self.assertEqual(report["packages_checked"], 1)
        self.assertNotIn(secret, json.dumps(FakeServer.seen_bodies) + json.dumps(report) + err)

    # --- enrichment (T1: KEV-listed vs not listed) -------------------------

    def fake_gh(self, payload: dict, exit_code: int = 0) -> str:
        path = self.dir / "fake_gh.py"
        path.write_text(f"#!{sys.executable}\nimport json, sys\n"
                        f"sys.stdout.write(json.dumps({payload!r}))\n"
                        f"sys.exit({exit_code})\n", encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    GH_PAYLOAD = {"ghsa_id": "GHSA-35jh-r3h4-6jhm", "severity": "high",
                  "summary": "Command injection in lodash",
                  "html_url": "https://github.com/advisories/GHSA-35jh-r3h4-6jhm",
                  "cvss": {"score": 7.2, "vector_string": "CVSS:3.1/x"},
                  "cwes": [{"cwe_id": "CWE-94", "name": "Code injection"}]}

    def enrich_run(self, kev: list):
        FakeServer.mode = "vulns"
        FakeServer.vuln_aliases = {"GHSA-test-0001": ["CVE-2021-23337", "GHSA-35jh-r3h4-6jhm"]}
        FakeServer.kev_cves = kev
        gh = self.fake_gh(self.GH_PAYLOAD)
        return self.run_script("lockfile", "--enrich", str(self.npm_lock()),
                               env_extra={"ASP_GH_BIN": gh})

    def test_enrich_kev_listed_vs_not_listed_differ(self):
        code_a, listed, _ = self.enrich_run(["CVE-2021-23337"])
        code_b, unlisted, _ = self.enrich_run(["CVE-1999-0001"])
        self.assertEqual((code_a, code_b), (1, 1))
        ea = listed["advisories"][0]["enrichment"]
        eb = unlisted["advisories"][0]["enrichment"]
        self.assertTrue(ea["kev"])
        self.assertEqual(ea["kev_date_added"], {"CVE-2021-23337": "2024-01-02"})
        self.assertFalse(eb["kev"])
        self.assertEqual(eb["kev_date_added"], {})
        self.assertNotEqual(ea, eb)
        self.assertEqual(ea["aliases"], ["CVE-2021-23337", "GHSA-35jh-r3h4-6jhm"])
        self.assertEqual(ea["epss"]["CVE-2021-23337"]["percentile"], "0.97")
        ghsa = ea["ghsa"]["GHSA-35jh-r3h4-6jhm"]
        self.assertEqual((ghsa["severity"], ghsa["cvss_score"], ghsa["cwes"]),
                         ("high", 7.2, ["CWE-94"]))

    def test_enrich_sends_only_advisory_ids(self):
        self.enrich_run([])
        epss = [p for p in FakeServer.seen_paths if p.startswith("/epss")]
        self.assertEqual(len(epss), 1)
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(epss[0]).query)
        self.assertEqual(qs["cve"], ["CVE-2021-23337"])
        self.assertNotIn(str(self.dir), json.dumps(FakeServer.seen_paths))

    def test_enrich_without_gh_is_partial(self):
        FakeServer.mode = "vulns"
        FakeServer.vuln_aliases = {"GHSA-test-0001": ["GHSA-35jh-r3h4-6jhm"]}
        empty = self.dir / "empty-bin"
        empty.mkdir()
        code, report, _ = self.run_script("lockfile", "--enrich", str(self.npm_lock()),
                                          env_extra={"PATH": str(empty)})
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")
        self.assertIn("GHSA enrichment not run: gh not on PATH", report["problems"])
        self.assertIsNone(report["advisories"][0]["enrichment"]["ghsa"])

    def test_enrich_source_failures_are_partial_and_null(self):
        for source, needle in (("kev", "CISA KEV"), ("epss", "FIRST EPSS"),
                               ("osvvuln", "OSV advisory details")):
            with self.subTest(source=source):
                FakeServer.enrich_fail = {source}
                code, report, _ = self.enrich_run(["CVE-2021-23337"])
                self.assertEqual(code, 2)
                self.assertEqual(report["status"], "partial")
                self.assertTrue(any(needle in p for p in report["problems"]))
                if source in ("kev", "epss"):
                    self.assertIsNone(report["advisories"][0]["enrichment"][source])

    def test_enrich_gh_error_is_partial(self):
        FakeServer.mode = "vulns"
        FakeServer.vuln_aliases = {"GHSA-test-0001": ["GHSA-35jh-r3h4-6jhm"]}
        gh = self.fake_gh({}, exit_code=1)
        code, report, _ = self.run_script("lockfile", "--enrich", str(self.npm_lock()),
                                          env_extra={"ASP_GH_BIN": gh})
        self.assertEqual(code, 2)
        self.assertIn("GHSA GHSA-35jh-r3h4-6jhm: gh exited 1", report["problems"])

    def test_without_enrich_flag_no_enrichment_calls(self):
        FakeServer.mode = "vulns"
        code, report, _ = self.run_script("lockfile", str(self.npm_lock()))
        self.assertEqual(code, 1)
        self.assertNotIn("enrichment", report["advisories"][0])
        self.assertEqual(FakeServer.seen_paths, [])

    def test_ghsa_id_regex_rejects_injection(self):
        self.assertTrue(check_vulns.GHSA_ID.match("GHSA-35jh-r3h4-6jhm"))
        for bad in ("GHSA-test-0001", "GHSA-35jh-r3h4-6jhm/../../user", "--paginate",
                    "GHSA-35jh-r3h4-6jhm;id"):
            self.assertIsNone(check_vulns.GHSA_ID.match(bad), bad)


if __name__ == "__main__":
    unittest.main()
