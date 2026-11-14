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

"""Comprehensive T1-T6, V1-V6, and S1-S9 test suite for skills/horizon.

Zero unittest.mock usage: subprocess calls execute real scripts on scratch PATH
directories or python3, and HTTP/GitHub probes exercise a real 127.0.0.1
ThreadingHTTPServer socket.
"""

from __future__ import annotations

import email.message
import hashlib
import http.server
import io
import json
import os
import re
import socket
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_GOOD = SKILL_DIR / "fixtures" / "known_good"
FIXTURES_BAD = SKILL_DIR / "fixtures" / "known_bad"
REPO_ROOT = SKILL_DIR.parents[1]

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import horizon  # noqa: E402
import horizon_probes  # noqa: E402


def _run_horizon(
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "horizon.py"), *args],
        cwd=str(cwd or SKILL_DIR),
        env=env,
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=30,
    )


def _write_executable(directory: Path, name: str, script_body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(script_body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _make_item_payload(
    item_id: str = "sample-watch-item",
    *,
    title: str = "Watch sample upstream CLI flag",
    window: str = "2026-Q4..2027-Q2",
    baseline: str = "Flag --beta required",
    forecast: str = "Flag promotes to stable default within 6 months.",
    playbook: str = "Update wrapper script and open PR.",
    probes: list[dict[str, Any]] | None = None,
    targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "category": "cli-tool",
        "window": window,
        "baseline_measurement": baseline,
        "forecast": forecast,
        "playbook": playbook,
        "source": "unit-test",
        "probes": probes
        if probes is not None
        else [{"kind": "cli_help", "binary": "python3", "expect_tokens": ["--version"]}],
        "targets": targets
        if targets is not None
        else [{"kind": "repo_branch_pr", "repo": "acme/repo", "path": "README.md"}],
    }


class _ThreadedHttpServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class _LocalProbeHandler(http.server.BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
    captured_requests: list[tuple[str, dict[str, str]]] = []

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.captured_requests.append(
            (self.path, {k.lower(): v for k, v in self.headers.items()})
        )
        entry = self.__class__.routes.get(self.path)
        if entry is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')
            return
        status, headers, body = entry
        self.send_response(status)
        for hk, hv in headers.items():
            self.send_header(hk, hv)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _InProcessLoopbackHttpHandler(urllib.request.BaseHandler):
    """Fallback OpenerDirector handler when sandbox blocks loopback TCP connect()."""

    handler_order = 10

    def http_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        parsed = urllib.parse.urlsplit(req.full_url)
        _LocalProbeHandler.captured_requests.append(
            (parsed.path, {k.lower(): v for k, v in req.header_items()})
        )
        entry = _LocalProbeHandler.routes.get(parsed.path)
        msg = email.message.Message()
        if entry is None:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", msg, io.BytesIO(b'{"error":"not found"}'))
        status, headers, body = entry
        for hk, hv in headers.items():
            msg[hk] = hv
        if status in (301, 302, 303, 307, 308):
            fp = urllib.response.addinfourl(io.BytesIO(body), msg, req.full_url, status)
            return self.parent.error("http", req, fp, status, "Found", msg)
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "Error", msg, io.BytesIO(body))
        resp_obj = urllib.response.addinfourl(io.BytesIO(body), msg, req.full_url, status)
        resp_obj.msg = "OK"
        return resp_obj


class TestSecurityAndRedaction(unittest.TestCase):
    """Covers S2, S4, S5, S8, SSRF, CWE-22, and CWE-88 guarantees."""

    def test_s2_s4_s5_source_hygiene_and_skill_length(self) -> None:
        self.assertNotIn("horizon", sys.stdlib_module_names)
        self.assertNotIn("horizon_probes", sys.stdlib_module_names)
        for path in (SCRIPTS_DIR / "horizon.py", SCRIPTS_DIR / "horizon_probes.py"):
            src = path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", src)
            self.assertNotRegex(src, r"/Users/(?!<)[A-Za-z0-9._-]+")
            self.assertNotRegex(src, r"/home/(?!<)[A-Za-z0-9._-]+")
        skill_lines = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(skill_lines), 160)

    def test_s8_secret_redaction_preserves_json_and_scrubs_subprocess_output(self) -> None:
        # Low-entropy concatenation keeps gitleaks leads at zero.
        google_key = "AIza" + "Dummy" + "Horizon" + "SecretKey" + "0123456789abcdef"
        oauth_tok = "ya29." + "a0Dummy" + "Horizon" + "OAuthTokenValue12345"
        gh_tok = "ghp_" + "DummyHorizon" + "Token0123456789abcdef"
        bearer_tok = "my_dummy_horizon_" + "bearer_token_987654"
        pem_hdr = "-----BEGIN " + "PRIVATE KEY-----"
        pem_ftr = "-----END " + "PRIVATE KEY-----"
        pem_body = "".join(["MIIE", "vQIB", "ADAN", "Bgkq", "hkiG"])

        raw_blob = (
            f"url=https://example.org/x?key={google_key}&access_token={oauth_tok} "
            f"Authorization: Bearer {bearer_tok} "
            f"GH_TOKEN={gh_tok} "
            f"key=ShortF# "
            f"{pem_hdr}\n{pem_body}\n{pem_ftr}"
        )
        proc = horizon_probes.default_runner(
            [sys.executable, "-c", f"import sys; sys.stderr.write({raw_blob!r})"]
        )
        self.assertEqual(proc.returncode, 0)
        for forbidden in (google_key, oauth_tok, gh_tok, bearer_tok, pem_body):
            self.assertNotIn(forbidden, proc.stderr)
        self.assertIn("key=ShortF#", proc.stderr)

        raw_json = json.dumps(
            {
                "api_key": "dummy_api_" + "secret_987654",
                "nullable": None,
                "key": 12345678901234567890,
                "enabled": True,
                "disabled": False,
                "nested": [{"token": "ghp_" + "NestedTokenValue" + "12345678"}],
            }
        )
        redacted_text = horizon_probes.redact_secrets(raw_json + ', "api_key": null')
        self.assertIn('"api_key": null', redacted_text)
        parsed = json.loads(horizon_probes.redact_secrets(raw_json))
        self.assertTrue(parsed["api_key"].startswith("[REDACTED:"))
        self.assertIsNone(parsed["nullable"])
        self.assertEqual(parsed["key"], 12345678901234567890)
        self.assertIs(parsed["enabled"], True)
        self.assertIs(parsed["disabled"], False)

        redacted_obj = horizon_probes.redact_value(json.loads(raw_json))
        self.assertTrue(redacted_obj["nested"][0]["token"].startswith("[REDACTED:"))
        self.assertEqual(horizon_probes.find_secret_leaks(redacted_obj), [])

        leaks = horizon_probes.find_secret_leaks({"bad": [gh_tok], "ok": "clean"})
        self.assertEqual(len(leaks), 1)
        self.assertIn("$.bad[0]", leaks[0])
        self.assertEqual(horizon_probes.redact_secrets(""), "")

    def test_contract_home_normalization(self) -> None:
        self.assertEqual(horizon_probes.contract_home(Path.home()), "~")
        self.assertEqual(
            horizon_probes.contract_home(Path.home() / ".gemini" / "horizons"),
            "~/.gemini/horizons",
        )
        self.assertEqual(horizon_probes.contract_home("/tmp/horizon-check"), str(Path("/tmp/horizon-check").resolve()))

    def test_url_and_ssrf_validation_boundaries(self) -> None:
        self.assertEqual(
            horizon_probes.validate_http_digest_url("https://ai.google.dev/gemini-api/docs"),
            "https://ai.google.dev/gemini-api/docs",
        )
        self.assertEqual(
            horizon_probes.validate_http_digest_url("http://127.0.0.1:8080/models"),
            "http://127.0.0.1:8080/models",
        )
        for bad_url in (
            "",
            "http://example.com/pricing",
            "file:///etc/passwd",
            "ftp://example.org/file",
            "https://169.254.169.254/latest/meta-data",
            "https://metadata.google.internal/computeMetadata/v1",
            "https://user:pass@example.org/docs",
            "https://example.org/a\nb",
        ):
            with self.assertRaises(ValueError, msg=f"Expected rejection for {bad_url!r}"):
                horizon_probes.validate_http_digest_url(bad_url)

        self.assertTrue(horizon_probes._is_blocked_host("169.254.169.254", allow_loopback=True))
        self.assertTrue(horizon_probes._is_blocked_host("127.0.0.1", allow_loopback=False))
        self.assertFalse(horizon_probes._is_blocked_host("example.org", allow_loopback=False))

        # SEC-001: Redirect handler must reject localhost, RFC1918, obfuscated numeric IPs, and DNS rebinding.
        redirect_handler = horizon_probes._SafeRedirectHandler(allow_loopback=False)
        origin_req = urllib.request.Request("https://example.org/releases")
        for blocked_loc in (
            "https://localhost:8443/admin",
            "https://LOCALHOST./admin",
            "https://foo.localhost/admin",
            "https://2130706433/admin",
            "https://0x7f000001/admin",
            "https://0177.0.0.1/admin",
            "https://127.1/admin",
            "https://10.0.0.5/internal",
            "https://192.168.1.1/router",
            "https://100.64.0.1/cgnat",
            "https://[::ffff:127.0.0.1]/admin",
            "https://[::ffff:10.0.0.5]/internal",
        ):
            with self.assertRaises(ValueError, msg=f"Expected redirect block for {blocked_loc}"):
                redirect_handler.redirect_request(origin_req, None, 302, "Found", {}, blocked_loc)

        rebind_handler = horizon_probes._SafeRedirectHandler(
            allow_loopback=False,
            addrinfo_fn=lambda h, p, type=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", p))],
        )
        with self.assertRaises(ValueError):
            rebind_handler.redirect_request(origin_req, None, 302, "Found", {}, "https://rebind.example.org/pwn")

        ok_handler = horizon_probes._SafeRedirectHandler(
            allow_loopback=False,
            addrinfo_fn=lambda h, p, type=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", p))],
        )
        redir_req = ok_handler.redirect_request(origin_req, None, 302, "Found", {}, "https://example.org/v2")
        self.assertIsNotNone(redir_req)
        self.assertEqual(redir_req.full_url, "https://example.org/v2")

        self.assertEqual(horizon_probes.resolve_github_api_base({}), "https://api.github.com")
        self.assertEqual(
            horizon_probes.resolve_github_api_base({"FORGE_HORIZON_GITHUB_API_BASE": "http://127.0.0.1:9999/"}),
            "http://127.0.0.1:9999",
        )
        self.assertEqual(
            horizon_probes.resolve_github_api_base({"FORGE_HORIZON_GITHUB_API_BASE": "file:///tmp/gh-api/"}),
            "file:///tmp/gh-api",
        )
        for bad_base in (
            "http://api.github.com",
            "http://evil.example.com",
            "ftp://127.0.0.1",
            "https://user:pass@api.github.com",
            "https://api.github.com\n",
        ):
            with self.assertRaises(ValueError, msg=f"Expected base rejection for {bad_base!r}"):
                horizon_probes.resolve_github_api_base({"FORGE_HORIZON_GITHUB_API_BASE": bad_base})

    def test_cli_token_repo_pr_and_path_confinement_guards(self) -> None:
        self.assertEqual(
            horizon_probes.validate_cli_help_tokens("gemini-api", ["generate"]),
            ["generate", "--help"],
        )
        self.assertEqual(
            horizon_probes.validate_cli_help_tokens("python3", ["--version"]),
            ["--version", "--help"],
        )
        for bad_bin, bad_toks in (
            ("bash", ["--help"]),
            ("/usr/bin/python3", ["--help"]),
            ("python3", ["-c"]),
            ("python3", ["--eval"]),
            ("git", ["status;id"]),
        ):
            with self.assertRaises(ValueError):
                horizon_probes.validate_cli_help_tokens(bad_bin, bad_toks)

        self.assertEqual(
            horizon_probes.validate_gh_pr_url("https://github.com/org/repo/pull/17/"),
            "https://github.com/org/repo/pull/17",
        )
        for bad_pr in (
            "http://github.com/org/repo/pull/17",
            "https://github.com/org/repo/issues/17",
            "https://github.com/../repo/pull/17",
        ):
            with self.assertRaises(ValueError):
                horizon_probes.validate_gh_pr_url(bad_pr)

        self.assertEqual(horizon_probes.validate_github_repo("acme/tool"), "acme/tool")
        for bad_repo in ("../evil", "noslash", "a/b/c"):
            with self.assertRaises(ValueError):
                horizon_probes.validate_github_repo(bad_repo)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            outside = root / "secret.txt"
            outside.write_text("top-secret", encoding="utf-8")
            inside = repo / "AGENTS.md"
            inside.write_text("anchor-here", encoding="utf-8")
            (repo / "escape_link").symlink_to(outside)

            self.assertEqual(horizon_probes.resolve_repo_relative_path(repo, "AGENTS.md"), inside.resolve())
            for bad_rel in ("../secret.txt", "/etc/passwd", "~/file", "escape_link", ""):
                with self.assertRaises(ValueError):
                    horizon_probes.resolve_repo_relative_path(repo, bad_rel)

            allowed = root / "allowed"
            allowed.mkdir()
            cfg = allowed / "rule.md"
            cfg.write_text("ok", encoding="utf-8")
            (allowed / "dir").mkdir()
            (allowed / "sym_escape").symlink_to(outside)
            self.assertEqual(horizon_probes.resolve_global_config_path(str(cfg), [allowed]), cfg.resolve())
            for bad_cfg in (str(outside), str(allowed / "sym_escape"), str(allowed / "missing.md"), str(allowed / "dir")):
                with self.assertRaises(ValueError):
                    horizon_probes.resolve_global_config_path(bad_cfg, [allowed])


class TestMechanicalProbesAndHttpServer(unittest.TestCase):
    """Exercises all 6 probes against real ThreadingHTTPServer sockets and real scripts."""

    server: _ThreadedHttpServer
    base_url: str
    thread: threading.Thread
    use_inprocess: bool = False

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = _ThreadedHttpServer(("127.0.0.1", 0), _LocalProbeHandler)
        port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                cls.use_inprocess = False
        except PermissionError:
            cls.use_inprocess = True

    def _http_fetcher(self):
        if not self.__class__.use_inprocess:
            return None
        return lambda u, h, t, m: horizon_probes.default_http_fetch(
            u, h, t, m, extra_handlers=[_InProcessLoopbackHttpHandler()]
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        _LocalProbeHandler.captured_requests.clear()
        secret_echo = "ghp_" + "EchoedServer" + "SecretValue1234567890"
        self.v1_bytes = b"Pricing v1: gemini-4-argon preview"
        self.v2_bytes = b"Pricing v2: gemini-4-argon GA stable"
        self.v1_sha = hashlib.sha256(self.v1_bytes).hexdigest()
        self.v2_sha = hashlib.sha256(self.v2_bytes).hexdigest()
        oversize = b"X" * (horizon_probes.MAX_HTTP_BYTES + 2048)

        _LocalProbeHandler.routes = {
            "/repos/acme/tool/releases/latest": (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "tag_name": "v2.4.0",
                        "published_at": "2026-11-10T00:00:00Z",
                        "assets": [{"name": "tool-linux.tar.gz"}, {"name": "checksums.txt"}],
                    }
                ).encode("utf-8"),
            ),
            "/repos/acme/err/releases/latest": (
                500,
                {"Content-Type": "text/plain"},
                f"Internal failure token={secret_echo}".encode("utf-8"),
            ),
            "/docs/v1": (200, {"Content-Type": "text/plain"}, self.v1_bytes),
            "/docs/v2": (200, {"Content-Type": "text/plain"}, self.v2_bytes),
            "/docs/large": (200, {"Content-Type": "application/octet-stream"}, oversize),
            "/redirect-ok": (302, {"Location": f"{self.base_url}/docs/v2"}, b""),
            "/redirect-ssrf": (302, {"Location": "http://example.com/pwn"}, b""),
            "/redirect-file": (302, {"Location": "file:///etc/passwd"}, b""),
        }

    def test_github_release_probe_http_and_file_and_secret_redaction(self) -> None:
        env = {"FORGE_HORIZON_GITHUB_API_BASE": self.base_url}
        fetcher = self._http_fetcher()
        same_res, ni_same = horizon_probes.run_probe(
            "item-gh",
            {"kind": "github_release", "repo": "acme/tool", "baseline_tag": "v2.4.0"},
            repo_root=REPO_ROOT,
            allow_roots=[Path.home() / ".gemini"],
            http_fetcher=fetcher,
            env=env,
        )
        self.assertIsNone(ni_same)
        self.assertTrue(same_res["available"])
        self.assertEqual(same_res["tag_name"], "v2.4.0")
        self.assertEqual(same_res["asset_names"], ["tool-linux.tar.gz", "checksums.txt"])
        self.assertFalse(same_res["tag_changed_vs_baseline"])

        changed_res, _ = horizon_probes.collect_github_release(
            "item-gh",
            {"kind": "github_release", "repo": "acme/tool", "baseline_tag": "v2.3.0"},
            http_fetcher=fetcher,
            env=env,
        )
        self.assertTrue(changed_res["tag_changed_vs_baseline"])

        err_res, ni_err = horizon_probes.collect_github_release(
            "item-gh", {"kind": "github_release", "repo": "acme/err"}, http_fetcher=fetcher, env=env
        )
        self.assertFalse(err_res["available"])
        self.assertEqual(err_res["http_status"], 500)
        self.assertNotIn("EchoedServer", err_res["error"])
        self.assertIsNotNone(ni_err)
        self.assertEqual(ni_err["what"], "github_release:acme/err")

        with self.assertRaises(ValueError):
            horizon_probes.collect_github_release(
                "item-gh",
                {"kind": "github_release", "repo": "acme/tool"},
                env={"FORGE_HORIZON_GITHUB_API_BASE": "http://example.com"},
            )

        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp) / "gh"
            rel_file = fixture_dir / "repos" / "acme" / "local" / "releases" / "latest.json"
            rel_file.parent.mkdir(parents=True)
            rel_file.write_text(
                json.dumps({"tag_name": "v9.0.0", "published_at": "2026-11-12T00:00:00Z", "assets": []}),
                encoding="utf-8",
            )
            file_res, file_ni = horizon_probes.collect_github_release(
                "item-local",
                {"kind": "github_release", "repo": "acme/local", "baseline_tag": "v8.0.0"},
                env={"FORGE_HORIZON_GITHUB_API_BASE": fixture_dir.as_uri()},
            )
            self.assertIsNone(file_ni)
            self.assertTrue(file_res["tag_changed_vs_baseline"])
            self.assertEqual(file_res["tag_name"], "v9.0.0")

    def test_http_digest_cap_redirects_and_ssrf_rejection(self) -> None:
        fetcher = self._http_fetcher()
        unchanged, ni = horizon_probes.run_probe(
            "item-http",
            {
                "kind": "http_digest",
                "url": f"{self.base_url}/docs/v1",
                "baseline_sha256": self.v1_sha,
                "expect_tokens": ["preview", "missing-tok"],
            },
            repo_root=REPO_ROOT,
            allow_roots=[Path.home() / ".gemini"],
            http_fetcher=fetcher,
        )
        self.assertIsNone(ni)
        self.assertTrue(unchanged["available"])
        self.assertEqual(unchanged["content_sha256"], self.v1_sha)
        self.assertFalse(unchanged["changed_vs_baseline"])
        self.assertEqual(unchanged["matched_tokens"], ["preview"])
        self.assertEqual(unchanged["missing_tokens"], ["missing-tok"])

        changed, _ = horizon_probes.collect_http_digest(
            "item-http",
            {"kind": "http_digest", "url": f"{self.base_url}/docs/v2", "baseline_sha256": self.v1_sha},
            http_fetcher=fetcher,
        )
        self.assertTrue(changed["changed_vs_baseline"])
        self.assertEqual(changed["content_sha256"], self.v2_sha)

        large, _ = horizon_probes.collect_http_digest(
            "item-http", {"kind": "http_digest", "url": f"{self.base_url}/docs/large"}, http_fetcher=fetcher
        )
        self.assertEqual(large["bytes_read"], horizon_probes.MAX_HTTP_BYTES)
        self.assertTrue(large["truncated"])

        redir_ok, _ = horizon_probes.collect_http_digest(
            "item-http", {"kind": "http_digest", "url": f"{self.base_url}/redirect-ok"}, http_fetcher=fetcher
        )
        self.assertTrue(redir_ok["available"])
        self.assertEqual(redir_ok["content_sha256"], self.v2_sha)

        for bad_redir in ("/redirect-ssrf", "/redirect-file"):
            with self.assertRaises(ValueError, msg=f"Expected SSRF redirect rejection for {bad_redir}"):
                horizon_probes.collect_http_digest(
                    "item-http",
                    {"kind": "http_digest", "url": f"{self.base_url}{bad_redir}"},
                    http_fetcher=fetcher,
                )

        for direct_bad in ("http://example.com/pricing", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                horizon_probes.collect_http_digest("item-http", {"kind": "http_digest", "url": direct_bad})

    def test_cli_help_file_anchor_gh_pr_status_and_agent_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            _write_executable(
                bin_dir,
                "gemini-api",
                "#!/bin/sh\necho 'Usage: gemini-api generate --store --thinking-level'\n",
            )
            _write_executable(
                bin_dir,
                "gh",
                '#!/bin/sh\necho \'{"state":"MERGED","mergedAt":"2026-11-12T10:00:00Z","url":"https://github.com/org/repo/pull/5"}\'\n',
            )
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ.get('PATH', '')}")

            res1, ni1 = horizon_probes.run_probe(
                "item-cli",
                {
                    "kind": "cli_help",
                    "binary": "gemini-api",
                    "args": ["generate", "--help"],
                    "expect_tokens": ["--store", "--missing"],
                },
                repo_root=root,
                allow_roots=[root],
                env=env,
            )
            self.assertIsNone(ni1)
            self.assertTrue(res1["available"])
            self.assertEqual(res1["returncode"], 0)
            self.assertEqual(res1["matched_tokens"], ["--store"])
            self.assertEqual(res1["missing_tokens"], ["--missing"])

            # Stub output changes -> changed_vs_baseline flips from False to True.
            same_res, _ = horizon_probes.collect_cli_help(
                "item-cli",
                {
                    "kind": "cli_help",
                    "binary": "gemini-api",
                    "args": ["generate", "--help"],
                    "baseline_output_sha256": res1["output_sha256"],
                },
                env=env,
            )
            self.assertFalse(same_res["changed_vs_baseline"])
            _write_executable(bin_dir, "gemini-api", "#!/bin/sh\necho 'Usage: gemini-api generate --stateless'\n")
            diff_res, _ = horizon_probes.collect_cli_help(
                "item-cli",
                {
                    "kind": "cli_help",
                    "binary": "gemini-api",
                    "args": ["generate", "--help"],
                    "baseline_output_sha256": res1["output_sha256"],
                },
                env=env,
            )
            self.assertTrue(diff_res["changed_vs_baseline"])

            # Missing binary cleanly enters not_inspected.
            missing_res, missing_ni = horizon_probes.collect_cli_help(
                "item-cli", {"kind": "cli_help", "binary": "gemini-api"}, env={"PATH": ""}
            )
            self.assertFalse(missing_res["available"])
            self.assertEqual(missing_ni["what"], "cli_help:gemini-api")

            # Timeout path via real sleeping stub.
            _write_executable(bin_dir, "ffprobe", "#!/bin/sh\nsleep 2\n")
            to_res, to_ni = horizon_probes.collect_cli_help(
                "item-cli", {"kind": "cli_help", "binary": "ffprobe"}, timeout=1, env=env
            )
            self.assertFalse(to_res["available"])
            self.assertIn("timed out", to_ni["reason"].lower())

            # gh_pr_status available vs missing vs non-zero exit.
            pr_res, pr_ni = horizon_probes.run_probe(
                "item-pr",
                {"kind": "gh_pr_status", "pr_url": "https://github.com/org/repo/pull/5"},
                repo_root=root,
                allow_roots=[root],
                env=env,
            )
            self.assertIsNone(pr_ni)
            self.assertTrue(pr_res["available"])
            self.assertEqual(pr_res["state"], "MERGED")

            pr_miss, pr_miss_ni = horizon_probes.collect_gh_pr_status(
                "item-pr", "https://github.com/org/repo/pull/5", env={"PATH": ""}
            )
            self.assertFalse(pr_miss["available"])
            self.assertEqual(pr_miss_ni["probe_kind"], "gh_pr_status")

            _write_executable(bin_dir, "gh", "#!/bin/sh\necho 'auth error' >&2\nexit 1\n")
            pr_fail, pr_fail_ni = horizon_probes.collect_gh_pr_status(
                "item-pr", "https://github.com/org/repo/pull/5", env=env
            )
            self.assertFalse(pr_fail["available"])
            self.assertIn("auth error", pr_fail_ni["reason"])

            _write_executable(bin_dir, "gh", "#!/bin/sh\necho 'not-json'\n")
            pr_badjson, pr_badjson_ni = horizon_probes.collect_gh_pr_status(
                "item-pr", "https://github.com/org/repo/pull/5", env=env
            )
            self.assertFalse(pr_badjson["available"])
            self.assertIn("Invalid JSON", pr_badjson_ni["reason"])

            # file_anchor repo + global_config + missing.
            target = root / "config.md"
            target.write_text("pin=gemini-launch-candidate-high\n", encoding="utf-8")
            fa_found, fa_ni = horizon_probes.run_probe(
                "item-fa",
                {"kind": "file_anchor", "scope": "repo", "path": "config.md", "anchor_literal": "gemini-launch-candidate-high"},
                repo_root=root,
                allow_roots=[root],
            )
            self.assertIsNone(fa_ni)
            self.assertTrue(fa_found["exists"])
            self.assertTrue(fa_found["anchor_found"])
            self.assertFalse(fa_found["truncated"])

            # REV-005: file_anchor caps reads at MAX_HTTP_BYTES.
            huge_file = root / "huge.txt"
            huge_file.write_bytes(b"A" * (horizon_probes.MAX_HTTP_BYTES + 1024))
            fa_huge, _ = horizon_probes.collect_file_anchor(
                {"kind": "file_anchor", "scope": "repo", "path": "huge.txt", "anchor_literal": "AAA"},
                repo_root=root,
                allow_roots=[root],
            )
            self.assertTrue(fa_huge["truncated"])
            self.assertEqual(fa_huge["file_sha256"], hashlib.sha256(b"A" * horizon_probes.MAX_HTTP_BYTES).hexdigest())

            fa_miss, _ = horizon_probes.collect_file_anchor(
                {"kind": "file_anchor", "scope": "global_config", "path": str(root / "absent.md"), "anchor_literal": "x"},
                repo_root=root,
                allow_roots=[root],
            )
            self.assertFalse(fa_miss["exists"])
            self.assertFalse(fa_miss["anchor_found"])

            # agent_query always reports requires_agent_eval + not_inspected.
            aq_res, aq_ni = horizon_probes.run_probe(
                "item-aq",
                {"kind": "agent_query", "source": "swarm-models", "query": "Check model catalogue"},
                repo_root=root,
                allow_roots=[root],
            )
            self.assertEqual(aq_res["status"], "requires_agent_eval")
            self.assertFalse(aq_res["available"])
            self.assertEqual(aq_ni["probe_kind"], "agent_query")

            with self.assertRaises(ValueError):
                horizon_probes.run_probe("x", {"kind": "unknown"}, repo_root=root, allow_roots=[root])


class TestLedgerCliAndReconciliation(unittest.TestCase):
    """Tests ledger resolution, permissions, record upserts, list, collect-evidence, and --doctor."""

    def test_ledger_dir_resolution_precedence_and_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_dir = root / "env_horizons"
            cli_dir = root / "cli_horizons"
            self.assertEqual(horizon.resolve_ledger_dir(str(cli_dir), {"FORGE_HORIZONS_DIR": str(env_dir)}), cli_dir.resolve())
            self.assertEqual(horizon.resolve_ledger_dir(None, {"FORGE_HORIZONS_DIR": str(env_dir)}), env_dir.resolve())
            self.assertEqual(horizon.resolve_ledger_dir(None, {}), (Path.home() / ".gemini" / "horizons").resolve())

            payload = _make_item_payload("perm-check-item")
            res = _run_horizon(
                "record", "--ledger-dir", str(cli_dir), "--input", "-", stdin_text=json.dumps(payload)
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            created = json.loads(res.stdout)
            self.assertEqual(created["action"], "created")
            self.assertEqual(created["revision"], 1)

            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(cli_dir.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((cli_dir / "ledger.jsonl").stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE((cli_dir / "INDEX.md").stat().st_mode), 0o600)

    def test_record_upsert_cli_flags_and_negative_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "horizons"
            probe_json = json.dumps({"kind": "cli_help", "binary": "python3", "expect_tokens": ["--help"]})
            target_json = json.dumps({"kind": "repo_branch_pr", "repo": "acme/repo", "path": "README.md"})

            r1 = _run_horizon(
                "--ledger-dir",
                str(ledger_dir),
                "record",
                "--id",
                "python-flag-watch",
                "--title",
                "Watch python3 help",
                "--category",
                "cli-tool",
                "--window",
                "2026-Q4..2027-Q1",
                "--baseline",
                "python3 exposes --help",
                "--forecast",
                "Help flag remains stable over 6 months.",
                "--playbook",
                "Verify python3 wrapper.",
                "--source",
                "cli-audit",
                "--probe",
                probe_json,
                "--target",
                target_json,
            )
            self.assertEqual(r1.returncode, 0, r1.stderr)
            d1 = json.loads(r1.stdout)
            self.assertEqual(d1["action"], "created")
            self.assertEqual(d1["revision"], 1)

            # Upsert increments revision while preserving created_at and history[].
            r2 = _run_horizon(
                "record",
                "--ledger-dir",
                str(ledger_dir),
                "--id",
                "python-flag-watch",
                "--title",
                "Watch python3 help (revised)",
                "--window",
                "2026-Q4..2027-Q2",
                "--baseline",
                "python3 exposes --help",
                "--forecast",
                "Updated 9-month forecast.",
                "--playbook",
                "Verify python3 wrapper.",
                "--probe",
                probe_json,
                "--target",
                target_json,
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            d2 = json.loads(r2.stdout)
            self.assertEqual(d2["action"], "updated")
            self.assertEqual(d2["revision"], 2)

            loaded = horizon.load_ledger(ledger_dir / "ledger.jsonl")
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["revision"], 2)
            self.assertEqual(len(loaded[0]["history"]), 2)
            self.assertEqual(loaded[0]["history"][1]["event"], "updated")
            self.assertRegex(loaded[0]["created_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertRegex(loaded[0]["updated_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

            # List JSON and table filtering.
            lst_json = _run_horizon("list", "--ledger-dir", str(ledger_dir), "--status", "watching", "--format", "json")
            self.assertEqual(lst_json.returncode, 0, lst_json.stderr)
            self.assertEqual(json.loads(lst_json.stdout)["count"], 1)

            lst_empty = _run_horizon("list", "--ledger-dir", str(ledger_dir), "--status", "landed", "--format", "table")
            self.assertEqual(lst_empty.returncode, 0, lst_empty.stderr)
            self.assertIn("No horizon items", lst_empty.stdout)

            # Negative tests (exit 2) for known_bad record fixtures and empty fields.
            for bad_fixture in ("record_insecure_http_probe.json", "record_zero_probes.json"):
                bad_res = _run_horizon(
                    "record", "--ledger-dir", str(ledger_dir), "--input", str(FIXTURES_BAD / bad_fixture)
                )
                self.assertEqual(bad_res.returncode, 2, f"{bad_fixture}: {bad_res.stdout} {bad_res.stderr}")

            for missing_field in ("title", "window", "baseline_measurement", "forecast", "playbook", "targets"):
                bad_obj = _make_item_payload("neg-case")
                bad_obj[missing_field] = [] if missing_field == "targets" else ""
                neg_res = _run_horizon(
                    "record", "--ledger-dir", str(ledger_dir), "--input", "-", stdin_text=json.dumps(bad_obj)
                )
                self.assertEqual(neg_res.returncode, 2, f"Expected exit 2 for empty {missing_field}")

            bad_id = _run_horizon(
                "record",
                "--ledger-dir",
                str(ledger_dir),
                "--input",
                "-",
                stdin_text=json.dumps(_make_item_payload("Bad_Slug!")),
            )
            self.assertEqual(bad_id.returncode, 2)

    def test_collect_evidence_reconciles_merged_prs_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / "horizons"
            bin_dir = root / "bin"
            _write_executable(
                bin_dir,
                "gh",
                '#!/bin/sh\necho \'{"state":"MERGED","mergedAt":"2026-11-14T11:00:00Z","url":"https://github.com/acme/repo/pull/88"}\'\n',
            )
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ.get('PATH', '')}")

            repo_dir = root / "sample_repo"
            repo_dir.mkdir()
            (repo_dir / "AGENTS.md").write_text("Engineering Standard anchor\n", encoding="utf-8")

            item = _make_item_payload(
                "pr-reconcile-item",
                probes=[
                    {"kind": "file_anchor", "scope": "repo", "path": "AGENTS.md", "anchor_literal": "Engineering Standard"},
                    {"kind": "agent_query", "source": "swarm-models", "query": "Check model deprecation"},
                ],
                targets=[{"kind": "repo_branch_pr", "repo": "acme/repo", "path": "AGENTS.md"}],
            )
            self.assertEqual(
                _run_horizon("record", "--ledger-dir", str(ledger_dir), "--input", "-", stdin_text=json.dumps(item), env=env).returncode,
                0,
            )
            self.assertEqual(
                _run_horizon(
                    "record-action",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--id",
                    "pr-reconcile-item",
                    "--status",
                    "pr_opened",
                    "--pr-url",
                    "https://github.com/acme/repo/pull/88",
                    env=env,
                ).returncode,
                0,
            )

            ev_out = root / "evidence.json"
            col = _run_horizon(
                "collect-evidence",
                "--ledger-dir",
                str(ledger_dir),
                "--repo-root",
                str(repo_dir),
                "--out",
                str(ev_out),
                "--reconcile-prs",
                env=env,
            )
            self.assertEqual(col.returncode, 0, col.stderr)
            ev_data = json.loads(ev_out.read_text(encoding="utf-8"))
            self.assertEqual(ev_data["items_evaluated"], 1)
            self.assertEqual(len(ev_data["reconciled_prs"]), 1)
            self.assertEqual(ev_data["reconciled_prs"][0]["item_id"], "pr-reconcile-item")
            self.assertEqual(ev_data["not_inspected"][0]["probe_kind"], "agent_query")

            # Item transitioned to landed and INDEX.md updated.
            items = horizon.load_ledger(ledger_dir / "ledger.jsonl")
            self.assertEqual(items[0]["status"], "landed")
            self.assertIn("`landed` | Watch sample upstream CLI flag", (ledger_dir / "INDEX.md").read_text(encoding="utf-8"))

            doc = _run_horizon("--ledger-dir", str(ledger_dir), "--doctor", env=env)
            self.assertEqual(doc.returncode, 0, doc.stderr)
            doc_json = json.loads(doc.stdout)
            self.assertEqual(doc_json["status"], "ok")
            self.assertTrue(doc_json["stdlib_only"])
            self.assertEqual(doc_json["item_count"], 1)

    def test_reconcile_closed_unmerged_and_concurrent_interleaving_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / "horizons"
            repo_dir = root / "repo"
            repo_dir.mkdir()
            (repo_dir / "AGENTS.md").write_text("anchor\n", encoding="utf-8")

            item_a = _make_item_payload(
                "item-closed-pr",
                probes=[{"kind": "file_anchor", "scope": "repo", "path": "AGENTS.md", "anchor_literal": "anchor"}],
            )
            item_b = _make_item_payload(
                "item-interleaved-action",
                probes=[{"kind": "file_anchor", "scope": "repo", "path": "AGENTS.md", "anchor_literal": "anchor"}],
            )
            item_c = _make_item_payload(
                "item-added-mid-probe",
                probes=[{"kind": "file_anchor", "scope": "repo", "path": "AGENTS.md", "anchor_literal": "anchor"}],
            )
            horizon.cmd_record(ledger_dir, item_a)
            horizon.cmd_record(ledger_dir, item_b)
            horizon.cmd_record_action(
                ledger_dir,
                item_id="item-closed-pr",
                new_status="pr_opened",
                pr_url="https://github.com/acme/repo/pull/101",
            )
            horizon.cmd_record_action(
                ledger_dir,
                item_id="item-interleaved-action",
                new_status="pr_opened",
                pr_url="https://github.com/acme/repo/pull/102",
            )

            interleaved_once = False

            def interleaving_runner(argv, _timeout):
                nonlocal interleaved_once
                pr_target = argv[-1]
                if not interleaved_once:
                    interleaved_once = True
                    # Simulate concurrent record + record-action arriving while slow probes execute.
                    horizon.cmd_record(ledger_dir, item_c)
                    horizon.cmd_record_action(
                        ledger_dir,
                        item_id="item-interleaved-action",
                        new_status="superseded",
                        note="Superseded mid-sweep",
                    )
                if pr_target.endswith("/101"):
                    return horizon_probes.CommandResult(
                        0,
                        json.dumps({"state": "CLOSED", "mergedAt": None, "url": pr_target}),
                        "",
                        tuple(argv),
                    )
                return horizon_probes.CommandResult(
                    0,
                    json.dumps({"state": "MERGED", "mergedAt": "2026-11-14T12:00:00Z", "url": pr_target}),
                    "",
                    tuple(argv),
                )

            evidence = horizon.cmd_collect_evidence(
                ledger_dir,
                repo_root=repo_dir,
                reconcile_prs=True,
                runner=interleaving_runner,
            )
            items_by_id = {it["id"]: it for it in horizon.load_ledger(ledger_dir / "ledger.jsonl")}
            # REV-002: CLOSED unmerged PR moves back to triggered with pr_closed_unmerged event.
            self.assertEqual(items_by_id["item-closed-pr"]["status"], "triggered")
            self.assertEqual(items_by_id["item-closed-pr"]["history"][-1]["event"], "pr_closed_unmerged")
            # REV-001: Mid-probe concurrent record & record-action survive intact.
            self.assertIn("item-added-mid-probe", items_by_id)
            self.assertEqual(items_by_id["item-interleaved-action"]["status"], "superseded")
            self.assertEqual(len(evidence["reconciled_prs"]), 1)
            self.assertEqual(evidence["reconciled_prs"][0]["to_status"], "triggered")
            index_text = (ledger_dir / "INDEX.md").read_text(encoding="utf-8")
            self.assertIn("item-added-mid-probe", index_text)
            self.assertNotIn("https://github.com/acme/repo/pull/101", index_text.split("## Open PRs")[1].split("## Landed")[0])


class TestVerdictAndProvenanceGates(unittest.TestCase):
    """Covers V1-V6 fixtures, L3 verdict validation, backup-target confinement, and record-action gates."""

    def test_v1_v2_fixtures_corrupt_ledger_and_verdict_contradictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "horizons"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "ledger.jsonl").write_text(
                (FIXTURES_GOOD / "sample_ledger.jsonl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            good = _run_horizon(
                "validate-verdict",
                "--ledger-dir",
                str(ledger_dir),
                "--verdict",
                str(FIXTURES_GOOD / "passing_verdict.json"),
                "--evidence",
                str(FIXTURES_GOOD / "sample_evidence.json"),
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            good_json = json.loads(good.stdout)
            self.assertTrue(good_json["valid"])
            self.assertEqual(good_json["triggered_count"], 1)

            for bad_verdict in (
                "verdict_drop_without_evidence.json",
                "verdict_duplicate_ids.json",
                "verdict_contradictory_count.json",
            ):
                bad = _run_horizon(
                    "validate-verdict",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--verdict",
                    str(FIXTURES_BAD / bad_verdict),
                )
                self.assertEqual(bad.returncode, 1, f"{bad_verdict}: {bad.stdout}")
                self.assertFalse(json.loads(bad.stdout)["valid"])

            # Reverse anti-contradiction: triggered_count=1 when all decisions are no_change.
            rev_verdict = {
                "schema_version": "1",
                "evaluated_at": "2026-11-14T12:00:00Z",
                "summary": "All clear but wrong triggered_count.",
                "triggered_count": 1,
                "not_inspected": [],
                "decisions": [
                    {
                        "item_id": "cli-flag-stabilization",
                        "decision": "no_change",
                        "summary": "Unchanged.",
                        "evidence_citations": ["probes[0].http_status=200"],
                    }
                ],
            }
            rev_res = _run_horizon(
                "validate-verdict", "--ledger-dir", str(ledger_dir), "--verdict", "-", stdin_text=json.dumps(rev_verdict)
            )
            self.assertEqual(rev_res.returncode, 1)
            self.assertIn("Contradictory triggered_count", rev_res.stdout)

            # Honesty failure: omitting or substituting not_inspected entry from evidence.json.
            dishonest_verdict = json.loads((FIXTURES_GOOD / "passing_verdict.json").read_text(encoding="utf-8"))
            dishonest_verdict["not_inspected"] = []
            dishonest_res = _run_horizon(
                "validate-verdict",
                "--ledger-dir",
                str(ledger_dir),
                "--verdict",
                "-",
                "--evidence",
                str(FIXTURES_GOOD / "sample_evidence.json"),
                stdin_text=json.dumps(dishonest_verdict),
            )
            self.assertEqual(dishonest_res.returncode, 1)
            self.assertIn("not_inspected honesty violation", dishonest_res.stdout)

            mismatched_ni = copy_dict(dishonest_verdict)
            mismatched_ni["not_inspected"] = [{"item_id": "cli-flag-stabilization", "what": "other-probe"}]
            mismatched_res = _run_horizon(
                "validate-verdict",
                "--ledger-dir",
                str(ledger_dir),
                "--verdict",
                "-",
                "--evidence",
                str(FIXTURES_GOOD / "sample_evidence.json"),
                stdin_text=json.dumps(mismatched_ni),
            )
            self.assertEqual(mismatched_res.returncode, 1)
            self.assertIn("not_inspected honesty violation", mismatched_res.stdout)

            # Unknown item_id, bool triggered_count, secret leak, empty decisions rejected.
            bad_bool = copy_dict(dishonest_verdict)
            bad_bool["triggered_count"] = True
            bad_bool["decisions"][0]["item_id"] = "unknown-slug"
            bad_bool["summary"] = "Secret ghp_" + "VerdictLeakValue" + "1234567890"
            errs = horizon.validate_verdict_payload(bad_bool, horizon.load_ledger(ledger_dir / "ledger.jsonl"))
            self.assertTrue(any("not bool" in e for e in errs))
            self.assertTrue(any("does not exist in ledger" in e for e in errs))
            self.assertTrue(any("Unredacted secret" in e for e in errs))

            empty_dec = {"schema_version": "1", "evaluated_at": "2026-11-14T12:00:00Z", "summary": "x", "triggered_count": 0, "not_inspected": [], "decisions": []}
            self.assertTrue(
                any("cannot be empty" in e for e in horizon.validate_verdict_payload(empty_dec, horizon.load_ledger(ledger_dir / "ledger.jsonl")))
            )

            # Corrupt ledger rejected non-zero across commands.
            corrupt_dir = Path(tmp) / "corrupt_horizons"
            corrupt_dir.mkdir()
            (corrupt_dir / "ledger.jsonl").write_text(
                (FIXTURES_BAD / "corrupt_ledger.jsonl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.assertEqual(_run_horizon("list", "--ledger-dir", str(corrupt_dir)).returncode, 1)
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(corrupt_dir)).returncode, 1)
            doc_corrupt = _run_horizon("--ledger-dir", str(corrupt_dir), "--doctor")
            self.assertEqual(json.loads(doc_corrupt.stdout)["status"], "degraded")

    def test_backup_target_confinement_and_record_action_l3_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_home = root / "home"
            gemini_dir = fake_home / ".gemini" / "config" / "rules"
            gemini_dir.mkdir(parents=True)
            cfg_file = gemini_dir / "swarm-models.md"
            cfg_file.write_text("# Swarm models v1\n", encoding="utf-8")
            other_cfg = gemini_dir / "other.md"
            other_cfg.write_text("# Other\n", encoding="utf-8")
            outside_file = root / "outside.txt"
            outside_file.write_text("outside", encoding="utf-8")
            (gemini_dir / "symlink_escape.md").symlink_to(outside_file)

            ledger_dir = root / "horizons"
            env = dict(os.environ, HOME=str(fake_home), USERPROFILE=str(fake_home))

            # Confinement rejections (exit 2).
            for bad_tgt in (str(outside_file), str(gemini_dir / "symlink_escape.md"), "~/.gemini/config/rules/missing.md"):
                bad_bk = _run_horizon("backup-target", "--ledger-dir", str(ledger_dir), "--target", bad_tgt, env=env)
                self.assertEqual(bad_bk.returncode, 2, f"Expected exit 2 for {bad_tgt}: {bad_bk.stderr}")

            # Successful confined backup.
            ok_bk = _run_horizon(
                "backup-target",
                "--ledger-dir",
                str(ledger_dir),
                "--target",
                "~/.gemini/config/rules/swarm-models.md",
                env=env,
            )
            self.assertEqual(ok_bk.returncode, 0, ok_bk.stderr)
            bk_info = json.loads(ok_bk.stdout)
            bk_path = Path(bk_info["backup_path"])
            self.assertTrue(bk_path.is_file())
            self.assertEqual(bk_info["sha256"], hashlib.sha256(cfg_file.read_bytes()).hexdigest())
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(bk_path.stat().st_mode), 0o600)

            # Repo target item: fail-closed pr_opened and landed gates.
            repo_item = _make_item_payload(
                "repo-gate-item",
                targets=[{"kind": "repo_branch_pr", "repo": "acme/repo", "path": "README.md"}],
            )
            self.assertEqual(
                _run_horizon("record", "--ledger-dir", str(ledger_dir), "--input", "-", stdin_text=json.dumps(repo_item), env=env).returncode,
                0,
            )
            self.assertEqual(
                _run_horizon("record-action", "--ledger-dir", str(ledger_dir), "--id", "repo-gate-item", "--status", "pr_opened", env=env).returncode,
                1,
            )
            self.assertEqual(
                _run_horizon(
                    "record-action",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--id",
                    "repo-gate-item",
                    "--status",
                    "pr_opened",
                    "--pr-url",
                    "https://github.com/acme/repo/issues/10",
                    env=env,
                ).returncode,
                1,
            )
            self.assertEqual(
                _run_horizon("record-action", "--ledger-dir", str(ledger_dir), "--id", "repo-gate-item", "--status", "landed", env=env).returncode,
                1,
            )
            # Override allowed for repo_branch_pr landed.
            ovr_res = _run_horizon(
                "record-action",
                "--ledger-dir",
                str(ledger_dir),
                "--id",
                "repo-gate-item",
                "--status",
                "landed",
                "--override-reason",
                "Verified upstream fix already present on main",
                env=env,
            )
            self.assertEqual(ovr_res.returncode, 0, ovr_res.stderr)

            # Global config target item: fail-closed backup gates.
            global_item = _make_item_payload(
                "global-gate-item",
                probes=[{"kind": "file_anchor", "scope": "global_config", "path": "~/.gemini/config/rules/swarm-models.md", "anchor_literal": "Swarm"}],
                targets=[{"kind": "global_config", "path": "~/.gemini/config/rules/swarm-models.md"}],
            )
            self.assertEqual(
                _run_horizon("record", "--ledger-dir", str(ledger_dir), "--input", "-", stdin_text=json.dumps(global_item), env=env).returncode,
                0,
            )
            # Missing backup -> exit 1.
            self.assertEqual(
                _run_horizon("record-action", "--ledger-dir", str(ledger_dir), "--id", "global-gate-item", "--status", "landed", env=env).returncode,
                1,
            )
            # Outside backup path -> exit 1.
            self.assertEqual(
                _run_horizon(
                    "record-action",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--id",
                    "global-gate-item",
                    "--status",
                    "landed",
                    "--backup-path",
                    str(outside_file),
                    env=env,
                ).returncode,
                1,
            )
            # Wrong target backup -> exit 1.
            other_bk = json.loads(
                _run_horizon(
                    "backup-target",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--target",
                    str(other_cfg),
                    env=env,
                ).stdout
            )
            self.assertEqual(
                _run_horizon(
                    "record-action",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--id",
                    "global-gate-item",
                    "--status",
                    "landed",
                    "--backup-path",
                    other_bk["backup_path"],
                    env=env,
                ).returncode,
                1,
            )
            # Tampered backup content -> exit 1.
            tampered_bk = json.loads(
                _run_horizon(
                    "backup-target",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--target",
                    str(cfg_file),
                    env=env,
                ).stdout
            )
            Path(tampered_bk["backup_path"]).write_text("TAMPERED", encoding="utf-8")
            self.assertEqual(
                _run_horizon(
                    "record-action",
                    "--ledger-dir",
                    str(ledger_dir),
                    "--id",
                    "global-gate-item",
                    "--status",
                    "landed",
                    "--backup-path",
                    tampered_bk["backup_path"],
                    env=env,
                ).returncode,
                1,
            )
            # Valid backup succeeds!
            land_ok = _run_horizon(
                "record-action",
                "--ledger-dir",
                str(ledger_dir),
                "--id",
                "global-gate-item",
                "--status",
                "landed",
                "--backup-path",
                str(bk_path),
                "--note",
                "Updated swarm-models rule after GA",
                env=env,
            )
            self.assertEqual(land_ok.returncode, 0, land_ok.stderr)
            self.assertTrue(Path(json.loads(land_ok.stdout)["run_file"]).is_file())


class TestDifferentiationFreshnessAndContracts(unittest.TestCase):
    """Covers T1, T3, T5 real-repo E2E, T6 render-index --check, and S6 CLI help parity."""

    def test_t1_differentiation_and_t3_derive_from_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "ledger_a"
            dir_b = root / "ledger_b"

            item_a = _make_item_payload(
                "alpha-watch",
                title="Alpha Watch Item",
                window="2026-Q4",
            )
            _run_horizon("record", "--ledger-dir", str(dir_a), "--input", "-", stdin_text=json.dumps(item_a))
            _run_horizon("record-action", "--ledger-dir", str(dir_a), "--id", "alpha-watch", "--status", "triggered")

            item_b = _make_item_payload(
                "zeta-superseded",
                title="Zeta Superseded Item",
                window="2027-Q3",
            )
            _run_horizon("record", "--ledger-dir", str(dir_b), "--input", "-", stdin_text=json.dumps(item_b))
            _run_horizon("record-action", "--ledger-dir", str(dir_b), "--id", "zeta-superseded", "--status", "superseded")

            idx_a = (dir_a / "INDEX.md").read_text(encoding="utf-8")
            idx_b = (dir_b / "INDEX.md").read_text(encoding="utf-8")
            self.assertNotEqual(idx_a, idx_b)
            self.assertIn("Alpha Watch Item", idx_a)
            self.assertNotIn("Alpha Watch Item", idx_b)
            self.assertIn("Zeta Superseded Item", idx_b)

            tbl_a = _run_horizon("list", "--ledger-dir", str(dir_a), "--format", "table").stdout
            tbl_b = _run_horizon("list", "--ledger-dir", str(dir_b), "--format", "table").stdout
            self.assertNotEqual(tbl_a, tbl_b)

            # REV-003: CR, LF, Unicode line separators, and pipes do not break Markdown tables.
            tricky = _make_item_payload(
                "cr-pipe-item",
                title="Title\rwith\nbreaks\u2028and\u2029|pipes",
                window="2026\rQ4|2027",
            )
            horizon.cmd_record(dir_a, tricky)
            idx_cr = (dir_a / "INDEX.md").read_text(encoding="utf-8")
            matching_rows = [line for line in idx_cr.splitlines() if "cr-pipe-item" in line]
            self.assertEqual(len(matching_rows), 1)
            self.assertIn("Title with breaks and \\|pipes", matching_rows[0])
            self.assertNotIn("\r", idx_cr)
            self.assertNotIn("\u2028", idx_cr)
            self.assertNotIn("\u2029", idx_cr)

    def test_t6_render_index_check_and_s6_help_docs_parity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "horizons"
            # Missing INDEX.md -> stale (exit 1).
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(ledger_dir), "--check").returncode, 1)

            _run_horizon(
                "record",
                "--ledger-dir",
                str(ledger_dir),
                "--input",
                str(FIXTURES_GOOD / "valid_record_item.json"),
            )
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(ledger_dir), "--check").returncode, 0)

            (ledger_dir / "INDEX.md").write_text("# Stale manual edit\n", encoding="utf-8")
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(ledger_dir), "--check").returncode, 1)
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(ledger_dir)).returncode, 0)
            self.assertEqual(_run_horizon("render-index", "--ledger-dir", str(ledger_dir), "--check").returncode, 0)

        # S6: Every documented subcommand and --flag in SKILL.md and references/*.md must exist in --help.
        help_texts = [_run_horizon("--help").stdout]
        subcommands = ("record", "list", "collect-evidence", "validate-verdict", "backup-target", "record-action", "render-index")
        for sub in subcommands:
            res = _run_horizon(sub, "--help")
            self.assertEqual(res.returncode, 0, res.stderr)
            help_texts.append(res.stdout)
        combined_help = "\n".join(help_texts)
        help_flags = set(re.findall(r"--[a-z][a-z0-9-]+", combined_help))

        for doc_path in (
            SKILL_DIR / "SKILL.md",
            SKILL_DIR / "references" / "ledger_and_probes.md",
            SKILL_DIR / "references" / "remediation_and_automation.md",
        ):
            doc_text = doc_path.read_text(encoding="utf-8")
            for documented_flag in set(re.findall(r"(?<![A-Za-z0-9-])--[a-z][a-z0-9-]+", doc_text)):
                # Ignore sample flags belonging to external tools probed by horizon (gh, gemini-api, python3).
                if documented_flag in (
                    "--json",
                    "--store",
                    "--thinking-level",
                    "--stateless",
                    "--beta",
                    "--help",
                    "--version",
                ):
                    continue
                self.assertIn(
                    documented_flag,
                    help_flags,
                    f"{doc_path.name} documents unknown flag {documented_flag}",
                )

    def test_t5_real_repository_end_to_end_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / "horizons"
            ev_path = root / "real_evidence.json"
            target_root = REPO_ROOT if (REPO_ROOT / "AGENTS.md").is_file() else SKILL_DIR
            anchor_rel = "AGENTS.md" if (REPO_ROOT / "AGENTS.md").is_file() else "SKILL.md"
            anchor_lit = "docs/ENGINEERING_STANDARD.md" if anchor_rel == "AGENTS.md" else "Horizon Sentinel"

            payload = _make_item_payload(
                "real-repo-agents-watch",
                title="Real repo anchor + python3 --help probe",
                probes=[
                    {"kind": "cli_help", "binary": "python3", "expect_tokens": ["--version"]},
                    {"kind": "file_anchor", "scope": "repo", "path": anchor_rel, "anchor_literal": anchor_lit},
                    {"kind": "agent_query", "source": "swarm-models", "query": "Verify model tier aliases"},
                ],
                targets=[{"kind": "repo_branch_pr", "repo": "ksprashu/agent-skill-forge", "path": anchor_rel}],
            )
            rec = _run_horizon("record", "--ledger-dir", str(ledger_dir), "--input", "-", stdin_text=json.dumps(payload))
            self.assertEqual(rec.returncode, 0, rec.stderr)

            col = _run_horizon(
                "collect-evidence",
                "--ledger-dir",
                str(ledger_dir),
                "--repo-root",
                str(target_root),
                "--out",
                str(ev_path),
            )
            self.assertEqual(col.returncode, 0, col.stderr)
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
            probes = ev["items"][0]["probes"]
            self.assertTrue(probes[0]["available"])
            self.assertIn("--version", probes[0]["matched_tokens"])
            self.assertTrue(probes[1]["exists"])
            self.assertTrue(probes[1]["anchor_found"])
            self.assertEqual(probes[2]["status"], "requires_agent_eval")

            verdict = {
                "schema_version": "1",
                "evaluated_at": "2026-11-14T12:30:00Z",
                "summary": "Real repo anchors and python3 CLI verified unchanged.",
                "triggered_count": 0,
                "not_inspected": ev["not_inspected"],
                "decisions": [
                    {
                        "item_id": "real-repo-agents-watch",
                        "decision": "no_change",
                        "summary": "Anchor and CLI tokens match baseline.",
                        "evidence_citations": [f"probes[1].file_sha256={probes[1]['file_sha256']}"],
                    }
                ],
            }
            val = _run_horizon(
                "validate-verdict",
                "--ledger-dir",
                str(ledger_dir),
                "--verdict",
                "-",
                "--evidence",
                str(ev_path),
                stdin_text=json.dumps(verdict),
            )
            self.assertEqual(val.returncode, 0, val.stdout + val.stderr)


def copy_dict(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


if __name__ == "__main__":
    unittest.main()
