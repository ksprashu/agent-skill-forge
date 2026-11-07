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

"""Normaliser and redaction tests for run_scanners.py, against canned output.

The canned files in fixtures/canned/ were captured from real runs of semgrep
1.182, gitleaks 8.30, osv-scanner 2.7, trivy 0.76, actionlint 1.7, zizmor 1.31,
pip-audit and npm 11, then trimmed. govulncheck and cargo-audit follow their
documented JSON formats. Secret slots hold the placeholder __SECRET__, which
the tests replace with a token generated at run time, so no secret-shaped
string is committed. None of these tests needs a scanner installed.
"""

from __future__ import annotations

import importlib.util
import json
import random
import string
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
CANNED = TESTS_DIR / "fixtures" / "canned"
_spec = importlib.util.spec_from_file_location(
    "run_scanners", TESTS_DIR.parent / "scripts" / "run_scanners.py")
RS = importlib.util.module_from_spec(_spec)
sys.modules["run_scanners"] = RS  # dataclasses resolve annotations via sys.modules
_spec.loader.exec_module(RS)

ROOT = Path("/REPO")


def fake_token(seed: int = 3) -> str:
    rng = random.Random(seed)
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(rng.choice(alphabet) for _ in range(36))


def canned(name: str, secret: str | None = None):
    text = (CANNED / name).read_text(encoding="utf-8")
    if secret is not None:
        text = text.replace("__SECRET__", secret)
    return json.loads(text) if not name.endswith(".jsonl") else RS._json_stream(text)


class NormaliserTest(unittest.TestCase):
    def assertLeadShape(self, leads):
        for ld in leads:
            self.assertEqual(set(ld), {"tool", "rule_id", "file", "line", "message",
                                       "severity", "cwe", "aliases"})
            self.assertFalse(ld["file"].startswith("/REPO"), ld)

    def test_semgrep(self):
        leads = RS.norm_semgrep(canned("semgrep.json", fake_token()), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual(len(leads), 10)
        sqli = [ld for ld in leads if ld["rule_id"].endswith("formatted-sql-query")]
        self.assertEqual(len(sqli), 1)
        self.assertEqual((sqli[0]["file"], sqli[0]["line"], sqli[0]["severity"]),
                         ("app.py", 12, "WARNING"))
        self.assertEqual(sqli[0]["cwe"], ["CWE-89"])
        mutable = next(ld for ld in leads if "mutable-action-tag" in ld["rule_id"])
        self.assertEqual(mutable["cwe"], ["CWE-1357", "CWE-353"])

    def test_gitleaks(self):
        leads = RS.norm_gitleaks(canned("gitleaks.json", fake_token()), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual([(ld["rule_id"], ld["file"], ld["line"]) for ld in leads],
                         [("github-pat", "config.py", 1),
                          ("github-pat", "old/settings.py", 7)])
        self.assertTrue(all(ld["cwe"] == ["CWE-798"] for ld in leads))
        self.assertIn("commit 0123456789ab", leads[1]["message"])
        # author identity is PII and is never copied
        self.assertNotIn("someone@example.invalid", json.dumps(leads))

    def test_osv_scanner_groups_aliases(self):
        leads = RS.norm_osv(canned("osv-scanner.json"), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual([ld["rule_id"] for ld in leads],
                         ["PYSEC-2018-66", "PYSEC-2019-179", "PYSEC-2023-62",
                          "PYSEC-2026-2151"])
        first = leads[0]
        self.assertEqual(first["file"], "requirements.txt")
        self.assertIn("CVE-2018-1000656", first["aliases"])
        self.assertNotIn("PYSEC-2018-66", first["aliases"])
        self.assertEqual(first["severity"], "8.7")
        self.assertEqual(first["cwe"], ["CWE-20"])
        self.assertIn("flask@0.12.2", first["message"])

    def test_trivy_skips_passing_checks(self):
        leads = RS.norm_trivy(canned("trivy.json", fake_token()), ROOT)
        self.assertLeadShape(leads)
        ids = [ld["rule_id"] for ld in leads]
        self.assertIn("DS-0002", ids)
        self.assertNotIn("DS-0001", ids)          # Status PASS
        self.assertIn("CVE-2023-30861", ids)
        secret = next(ld for ld in leads if ld["rule_id"] == "github-pat")
        self.assertEqual((secret["file"], secret["line"], secret["severity"]),
                         ("config.py", 1, "CRITICAL"))
        root_user = next(ld for ld in leads if ld["rule_id"] == "DS-0002")
        self.assertEqual(root_user["line"], 2)

    def test_actionlint(self):
        leads = RS.norm_actionlint(canned("actionlint.json"), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual([(ld["rule_id"], ld["file"], ld["line"]) for ld in leads],
                         [("actionlint:expression", ".github/workflows/ci.yml", 9)])
        self.assertIn("potentially untrusted", leads[0]["message"])

    def test_zizmor_rows_are_one_based_and_ignored_dropped(self):
        leads = RS.norm_zizmor(canned("zizmor.json"), ROOT)
        self.assertLeadShape(leads)
        by_rule = {ld["rule_id"]: ld for ld in leads}
        self.assertNotIn("zizmor:ignored-finding", by_rule)
        self.assertEqual(by_rule["zizmor:template-injection"]["line"], 9)
        self.assertEqual(by_rule["zizmor:dangerous-triggers"]["line"], 1)
        self.assertEqual(by_rule["zizmor:unpinned-uses"]["severity"], "High")
        self.assertEqual(len(leads), 5)

    def test_npm_audit_uses_ghsa_ids_and_skips_transitive_strings(self):
        leads = RS.norm_npm_audit(canned("npm-audit.json"), ROOT)
        self.assertLeadShape(leads)
        rules = {ld["rule_id"] for ld in leads}
        self.assertIn("GHSA-35jh-r3h4-6jhm", rules)
        cmd = next(ld for ld in leads if ld["rule_id"] == "GHSA-35jh-r3h4-6jhm")
        self.assertEqual((cmd["severity"], cmd["cwe"]), ("high", ["CWE-77", "CWE-94"]))
        self.assertTrue(all(r.startswith("GHSA-") for r in rules))

    def test_pip_audit(self):
        leads = RS.dedupe(RS.norm_pip_audit(canned("pip-audit.json"), ROOT))
        self.assertLeadShape(leads)
        rules = [ld["rule_id"] for ld in leads]
        self.assertEqual(len(rules), len(set(rules)))
        self.assertIn("PYSEC-2018-66", rules)
        lead = next(ld for ld in leads if ld["rule_id"] == "PYSEC-2018-66")
        self.assertIn("CVE-2018-1000656", lead["aliases"])
        self.assertIn("fixed in 0.12.3", lead["message"])

    def test_govulncheck_stream_dedupes_and_marks_reachability(self):
        leads = RS.norm_govulncheck(canned("govulncheck.jsonl"), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual(len(leads), 2)
        called = next(ld for ld in leads if ld["rule_id"] == "GO-2024-2687")
        self.assertIn("(called)", called["message"])
        self.assertEqual((called["file"], called["line"]), ("server.go", 120))
        self.assertIn("CVE-2023-45288", called["aliases"])
        required = next(ld for ld in leads if ld["rule_id"] == "GO-2023-2153")
        self.assertIn("(required)", required["message"])
        self.assertEqual(required["file"], "go.mod")

    def test_cargo_audit(self):
        leads = RS.norm_cargo_audit(canned("cargo-audit.json"), ROOT)
        self.assertLeadShape(leads)
        self.assertEqual([(ld["rule_id"], ld["file"]) for ld in leads],
                         [("RUSTSEC-2023-0071", "Cargo.lock")])
        self.assertIn("rsa@0.9.6", leads[0]["message"])
        self.assertIn("GHSA-c38w-74pg-36hr", leads[0]["aliases"])

    def test_empty_outputs_give_no_leads(self):
        # T1 at the normaliser level: the same functions on empty reports.
        self.assertEqual(RS.norm_semgrep({"results": []}, ROOT), [])
        self.assertEqual(RS.norm_gitleaks([], ROOT), [])
        self.assertEqual(RS.norm_osv({"results": []}, ROOT), [])
        self.assertEqual(RS.norm_trivy({"Results": None}, ROOT), [])
        self.assertEqual(RS.norm_zizmor([], ROOT), [])
        self.assertEqual(RS.norm_npm_audit({"vulnerabilities": {}}, ROOT), [])
        self.assertEqual(RS.norm_cargo_audit({"vulnerabilities": {"list": []}}, ROOT), [])


class RedactionTest(unittest.TestCase):
    """S8: secret values must not survive capture, whichever tool saw them."""

    def test_no_planted_secret_in_any_normalised_output(self):
        token = fake_token(11)
        leads = (RS.norm_semgrep(canned("semgrep.json", token), ROOT)
                 + RS.norm_gitleaks(canned("gitleaks.json", token), ROOT)
                 + RS.norm_trivy(canned("trivy.json", token), ROOT))
        blob = json.dumps(leads)
        self.assertNotIn(token, blob)
        self.assertNotIn(token[4:20], blob)
        # the semgrep message interpolated the secret; it must be masked
        msg = next(ld["message"] for ld in leads
                   if ld["rule_id"].endswith("detected-github-token"))
        self.assertIn("[REDACTED]", msg)

    def test_redact_masks_known_shapes(self):
        aws = "AKIA" + "ABCDEFGHIJKLMNOP"
        samples = [fake_token(5), aws, "xoxb-" + "1234567890-abcdefghij",
                   "sk_live_" + "a1b2c3d4e5f6g7h8", "https://bob:hunter2pass@host.example/x"]
        for s in samples:
            out = RS.redact(f"found {s} here")
            self.assertIn("[REDACTED]", out, s)
            self.assertNotIn(s, out)

    def test_redact_leaves_ordinary_messages_alone(self):
        msg = ("Detected possible formatted SQL query. Use parameterized queries "
               "instead. See CWE-89 and https://owasp.org/Top10/")
        self.assertEqual(RS.redact(msg), msg)

    def test_rel_shortens_absolute_paths_only_under_root(self):
        self.assertEqual(RS.rel("/REPO/a/b.py", ROOT), "a/b.py")
        self.assertEqual(RS.rel("./a/b.py", ROOT), "a/b.py")
        self.assertEqual(RS.rel("a/b.py", ROOT), "a/b.py")
        self.assertEqual(RS.rel(None, ROOT), "")

    def test_cwes_parses_strings_ints_and_lists(self):
        self.assertEqual(RS.cwes(["CWE-89: SQLi", "CWE-89", "CWE-20"]), ["CWE-89", "CWE-20"])
        self.assertEqual(RS.cwes("no weakness here"), [])
        self.assertEqual(RS.cwes(None), [])


if __name__ == "__main__":
    unittest.main()
