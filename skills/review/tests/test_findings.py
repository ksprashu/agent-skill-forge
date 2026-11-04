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

"""Tests for scripts/findings.py, the shared findings contract.

Patterns (docs/ENGINEERING_STANDARD.md):
- V1/V2: committed known-bad fixture is rejected, known-good fixtures accepted.
- T4: one negative test per semantic rule and per structural constraint, each
  asserting the specific error, not just a non-zero exit.
- T6: the committed schema is byte-identical to a fresh `findings.py schema`.
- Gate: exit 1 on open P0-P3, exit 0 when all are closed or nit-only, and
  refusal (exit 1) on an invalid document.
- SARIF: output shape is a 2.1.0 log whose results mirror the open findings.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPT = SKILL_DIR / "scripts" / "findings.py"
SCHEMA_FILE = SKILL_DIR / "references" / "findings.schema.json"
FIX = TESTS_DIR / "fixtures" / "findings"

sys.path.insert(0, str(SCRIPT.parent))
import findings as F  # noqa: E402


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True, shell=False, check=False)


def run_on(cmd: str, doc: object) -> subprocess.CompletedProcess:
    return run_cli(cmd, "-", stdin=json.dumps(doc))


class TestFixtures(unittest.TestCase):
    """V1 / V2: committed fixtures."""

    def test_known_good_fixtures_validate(self) -> None:
        for name in ("known_good_open.json", "known_good_closed.json",
                     "known_good_nits_only.json"):
            with self.subTest(name=name):
                res = run_cli("validate", str(FIX / name))
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertEqual(json.loads(res.stdout), {"valid": True, "errors": []})

    def test_known_bad_fixture_is_rejected(self) -> None:
        res = run_cli("validate", str(FIX / "known_bad.json"))
        self.assertEqual(res.returncode, 1)
        out = json.loads(res.stdout)
        self.assertFalse(out["valid"])
        # Every planted defect must be caught, not just one of them.
        for fragment in ("end_line 14 before start_line 15", "repo-relative",
                         "needs concrete evidence", "cannot be low confidence",
                         "CWE/CVE", "security_verdict", "needs the prior_id",
                         "duplicate id", "must cite a guide"):
            self.assertTrue(any(fragment in e for e in out["errors"]),
                            f"known_bad.json: no error mentioning {fragment!r}")


class TestSemanticRules(unittest.TestCase):
    """T4: each semantic rule rejects on its own, with its own message."""

    def setUp(self) -> None:
        self.doc = load("known_good_open.json")
        self.assertEqual(F.validate(self.doc), [])

    def assertRejects(self, doc: dict, fragment: str) -> None:
        errors = F.validate(doc)
        self.assertTrue(any(fragment in e for e in errors),
                        f"expected an error containing {fragment!r}, got {errors}")

    def finding(self, i: int = 0) -> dict:
        return self.doc["findings"][i]

    def test_duplicate_id(self) -> None:
        self.doc["findings"][1]["id"] = "REV-001"
        self.assertRejects(self.doc, "duplicate id REV-001")

    def test_end_before_start(self) -> None:
        self.finding().update(start_line=20, end_line=10)
        self.assertRejects(self.doc, "end_line 10 before start_line 20")

    def test_paths_must_be_repo_relative_posix(self) -> None:
        for bad in ("/etc/passwd", "C:/repo/a.py", "../outside.py", "app\\search.py",
                    "app/../../x.py"):
            with self.subTest(path=bad):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0]["file"] = bad
                self.assertRejects(doc, "repo-relative POSIX path")

    def test_p0_p1_need_evidence(self) -> None:
        for sev in ("P0", "P1"):
            with self.subTest(sev=sev):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0].update(severity=sev, evidence="   short    ")
                self.assertRejects(doc, f"{sev} needs concrete evidence")

    def test_p2_does_not_need_long_evidence(self) -> None:
        self.finding().update(severity="P2", evidence="")
        self.assertEqual(F.validate(self.doc), [])

    def test_p0_p1_cannot_be_low_confidence(self) -> None:
        for sev in ("P0", "P1"):
            with self.subTest(sev=sev):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0].update(severity=sev, confidence="low")
                self.assertRejects(doc, f"{sev} cannot be low confidence")

    def test_style_needs_reference(self) -> None:
        self.finding(1)["references"] = []
        self.assertRejects(self.doc, "style findings must cite")

    def test_reference_must_be_https(self) -> None:
        self.finding(1)["references"][0]["url"] = "http://google.github.io/styleguide/pyguide.html"
        self.assertRejects(self.doc, "does not match ^https://")

    def test_security_needs_weakness_rule(self) -> None:
        for bad in ("", "sql-injection", "cwe-89", "OWASP-A03"):
            with self.subTest(rule=bad):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0]["rule"] = bad
                self.assertRejects(doc, "security findings need a CWE")

    def test_security_rule_forms_accepted(self) -> None:
        for good in ("CWE-79", "CVE-2024-3094", "GHSA-jfh8-c2jp-5v3q", "OSV-2023-1",
                     "ASI01", "LLM01", "API1"):
            with self.subTest(rule=good):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0]["rule"] = good
                self.assertEqual(F.validate(doc), [])

    def test_security_needs_verdict(self) -> None:
        self.finding()["security_verdict"] = "n/a"
        self.assertRejects(self.doc, "need security_verdict confirmed or needs_validation")

    def test_needs_validation_cannot_be_blocking_high(self) -> None:
        for sev in ("P0", "P1"):
            with self.subTest(sev=sev):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0].update(severity=sev, security_verdict="needs_validation")
                self.assertRejects(doc, f"needs_validation cannot be {sev}")
        self.finding().update(severity="P2", security_verdict="needs_validation")
        self.assertEqual(F.validate(self.doc), [])

    def test_continuing_status_needs_prior_id(self) -> None:
        for status in ("still_open", "reopened", "fixed", "accepted_pushback"):
            with self.subTest(status=status):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0].update(status=status, prior_id="")
                self.assertRejects(doc, f"status {status} needs the prior_id")
                doc["findings"][0]["prior_id"] = "REV-001"
                self.assertEqual(F.validate(doc), [])


class TestStructuralRules(unittest.TestCase):
    """T4: the schema half of validate()."""

    def setUp(self) -> None:
        self.doc = load("known_good_open.json")

    def assertRejects(self, doc: object, fragment: str) -> None:
        errors = F.validate(doc)
        self.assertTrue(any(fragment in e for e in errors),
                        f"expected an error containing {fragment!r}, got {errors}")

    def test_missing_top_level_field(self) -> None:
        del self.doc["not_inspected"]
        self.assertRejects(self.doc, "$: missing not_inspected")

    def test_missing_finding_field(self) -> None:
        del self.doc["findings"][0]["evidence"]
        self.assertRejects(self.doc, "$.findings[0]: missing evidence")

    def test_unexpected_field(self) -> None:
        self.doc["score"] = 95
        self.assertRejects(self.doc, "unexpected field score")
        self.doc["findings"][0]["verdict"] = "approve"
        self.assertRejects(self.doc, "unexpected field verdict")

    def test_enums(self) -> None:
        cases = [("severity", "critical"), ("axis", "readability"),
                 ("confidence", "certain"), ("status", "resolved"),
                 ("security_verdict", "rejected")]
        for field, bad in cases:
            with self.subTest(field=field):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0][field] = bad
                self.assertRejects(doc, f"$.findings[0].{field}: {bad!r} not one of")
        for field, bad in (("schema_version", "2"), ("producer", "pr-guardian"),
                           ("mode", "audit")):
            with self.subTest(field=field):
                doc = copy.deepcopy(self.doc)
                doc[field] = bad
                self.assertRejects(doc, f"$.{field}: {bad!r} not one of")

    def test_types(self) -> None:
        self.doc["findings"][0]["start_line"] = True
        self.assertRejects(self.doc, "start_line: expected integer")
        doc = load("known_good_open.json")
        doc["findings"][0]["end_line"] = "15"
        self.assertRejects(doc, "end_line: expected integer")

    def test_line_minimum(self) -> None:
        self.doc["findings"][0]["start_line"] = 0
        self.assertRejects(self.doc, "start_line: below 1")

    def test_id_pattern(self) -> None:
        for bad in ("REV-1", "rev-001", "001", "REV_001"):
            with self.subTest(id=bad):
                doc = copy.deepcopy(self.doc)
                doc["findings"][0]["id"] = bad
                self.assertRejects(doc, "id: does not match")

    def test_title_length(self) -> None:
        self.doc["findings"][0]["title"] = "x" * (F.TITLE_MAX + 1)
        self.assertRejects(self.doc, f"longer than {F.TITLE_MAX}")

    def test_empty_required_strings(self) -> None:
        self.doc["summary"] = ""
        self.assertRejects(self.doc, "$.summary: empty")

    def test_not_an_object(self) -> None:
        self.assertRejects([], "$: expected object")

    def test_non_list_findings_reported_not_crashing(self) -> None:
        for bad in (5, None, "REV-001"):
            with self.subTest(findings=bad):
                doc = copy.deepcopy(self.doc)
                doc["findings"] = bad
                self.assertRejects(doc, "$.findings: expected array")

    def test_non_string_id_reported_not_crashing(self) -> None:
        self.doc["findings"][0]["id"] = ["REV-001"]
        self.assertRejects(self.doc, "id: expected string")


class TestSchemaFreshness(unittest.TestCase):
    """T6: committed schema == generated schema, byte for byte."""

    def test_committed_schema_is_fresh(self) -> None:
        res = run_cli("schema")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.encode("utf-8"), SCHEMA_FILE.read_bytes(),
                         "references/findings.schema.json is stale; regenerate with "
                         "`python3 scripts/findings.py schema > references/findings.schema.json`")

    def test_schema_enums_derive_from_constants(self) -> None:
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        props = schema["properties"]["findings"]["items"]["properties"]
        self.assertEqual(props["severity"]["enum"], list(F.SEVERITIES))
        self.assertEqual(props["axis"]["enum"], list(F.AXES))
        self.assertEqual(props["status"]["enum"], list(F.STATUSES))
        self.assertIn("style", F.AXES)


class TestGate(unittest.TestCase):

    def test_open_blocking_exits_1(self) -> None:
        res = run_cli("gate", str(FIX / "known_good_open.json"))
        self.assertEqual(res.returncode, 1, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["open_blocking"], 2)
        self.assertEqual(out["ids"], ["REV-001", "REV-002"])
        self.assertEqual(out["by_severity"], {"P0": 1, "P1": 0, "P2": 0, "P3": 1})
        self.assertEqual(out["not_inspected"], [{"what": "mypy", "reason": "binary not on PATH"}])

    def test_each_blocking_severity_blocks_and_nit_does_not(self) -> None:
        base = load("known_good_nits_only.json")
        for sev in ("P0", "P1", "P2", "P3"):
            with self.subTest(sev=sev):
                doc = copy.deepcopy(base)
                doc["findings"][0].update(severity=sev, confidence="high",
                                          evidence="x = items[len(items)]  # IndexError")
                self.assertEqual(run_on("gate", doc).returncode, 1)
        self.assertEqual(run_on("gate", base).returncode, 0)

    def test_still_open_and_reopened_block(self) -> None:
        for status in ("still_open", "reopened", "new"):
            with self.subTest(status=status):
                doc = load("known_good_closed.json")
                doc["findings"][0]["status"] = status
                self.assertEqual(run_on("gate", doc).returncode, 1)

    def test_all_closed_exits_0(self) -> None:
        res = run_cli("gate", str(FIX / "known_good_closed.json"))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(json.loads(res.stdout)["open_blocking"], 0)

    def test_nit_only_exits_0(self) -> None:
        self.assertEqual(run_cli("gate", str(FIX / "known_good_nits_only.json")).returncode, 0)

    def test_empty_findings_exits_0(self) -> None:
        doc = load("known_good_nits_only.json")
        doc["findings"] = []
        self.assertEqual(run_on("gate", doc).returncode, 0)

    def test_gate_refuses_invalid_document(self) -> None:
        res = run_cli("gate", str(FIX / "known_bad.json"))
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout, "", "an invalid document must not produce a gate verdict")
        self.assertIn("refusing to gate an invalid document", res.stderr)

    def test_gate_refuses_invalid_even_with_no_open_findings(self) -> None:
        doc = load("known_good_closed.json")
        doc["findings"][0]["prior_id"] = ""   # fixed without prior_id: invalid
        res = run_on("gate", doc)
        self.assertEqual(res.returncode, 1)
        self.assertIn("refusing", res.stderr)

    def test_unreadable_input_exits_2(self) -> None:
        self.assertEqual(run_cli("gate", "-", stdin="{not json").returncode, 2)
        self.assertEqual(run_cli("gate", str(FIX / "does-not-exist.json")).returncode, 2)

    def test_usage_error_exits_64(self) -> None:
        self.assertEqual(run_cli("frobnicate").returncode, 64)
        self.assertEqual(run_cli().returncode, 64)

    def test_open_blocking_function(self) -> None:
        self.assertEqual([f["id"] for f in F.open_blocking(load("known_good_open.json"))],
                         ["REV-001", "REV-002"])
        self.assertEqual(F.open_blocking(load("known_good_closed.json")), [])


class TestSarif(unittest.TestCase):

    def test_sarif_shape(self) -> None:
        res = run_cli("sarif", str(FIX / "known_good_open.json"))
        self.assertEqual(res.returncode, 0, res.stderr)
        log = json.loads(res.stdout)
        self.assertEqual(log["version"], "2.1.0")
        self.assertIn("sarif", log["$schema"])
        self.assertEqual(len(log["runs"]), 1)
        run = log["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "agent-skill-forge/review")
        rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
        self.assertEqual(rule_ids, {"CWE-89", "google-pystyle-2.12", "observability"})

        by_id = {r["partialFingerprints"]["findingId"]: r for r in run["results"]}
        self.assertEqual(set(by_id), {"REV-001", "REV-002", "REV-003"})
        r1 = by_id["REV-001"]
        self.assertEqual(r1["ruleId"], "CWE-89")
        self.assertEqual(r1["level"], "error")
        loc = r1["locations"][0]["physicalLocation"]
        self.assertEqual(loc["artifactLocation"]["uri"], "app/search.py")
        self.assertEqual(loc["region"], {"startLine": 14, "endLine": 15})
        self.assertTrue(r1["message"]["text"].startswith("[P0] "))
        self.assertEqual(by_id["REV-002"]["level"], "note")
        # A rule with a reference carries it as helpUri.
        rules = {r["id"]: r for r in run["tool"]["driver"]["rules"]}
        self.assertTrue(rules["CWE-89"]["helpUri"].startswith("https://cwe.mitre.org"))

    def test_sarif_level_follows_severity(self) -> None:
        doc = load("known_good_open.json")
        doc["findings"][0]["severity"] = "P2"
        doc["findings"][0]["security_verdict"] = "needs_validation"
        log = json.loads(run_on("sarif", doc).stdout)
        levels = {r["partialFingerprints"]["findingId"]: r["level"]
                  for r in log["runs"][0]["results"]}
        self.assertEqual(levels["REV-001"], "warning")

    def test_sarif_omits_closed_findings(self) -> None:
        log = json.loads(run_cli("sarif", str(FIX / "known_good_closed.json")).stdout)
        ids = [r["partialFingerprints"]["findingId"] for r in log["runs"][0]["results"]]
        self.assertEqual(ids, ["REV-103"])

    def test_sarif_refuses_invalid(self) -> None:
        res = run_cli("sarif", str(FIX / "known_bad.json"))
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout, "")


if __name__ == "__main__":
    unittest.main()
