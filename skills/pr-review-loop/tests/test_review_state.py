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

"""Tests for review_state.py against canned GraphQL responses.

T1 differentiation (all-resolved vs open P1), marker parsing including
malformed markers, escalation-signal facts, and T4 negatives (bad usage,
gh missing, GraphQL errors, open work that must not exit 0).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures"
SCRIPT = SKILL / "scripts" / "review_state.py"
FINDINGS = SKILL.parent / "review" / "scripts" / "findings.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RS = _load(SCRIPT, "pr_review_loop_review_state")


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, shell=False, env=env)


def run_fixture(name: str) -> tuple[int, dict]:
    proc = run("--from-file", str(FIXTURES / f"{name}.json"))
    return proc.returncode, json.loads(proc.stdout)


class TestDifferentiation(unittest.TestCase):
    """T1: opposite inputs give different exits and different evidence."""

    def test_resolved_vs_open_p1(self):
        code_a, a = run_fixture("all_resolved")
        code_b, b = run_fixture("open_p1")
        self.assertEqual(code_a, 0)
        self.assertEqual(code_b, 1)
        self.assertEqual(a["open_blocking"], 0)
        self.assertEqual(b["open_blocking"], 2)
        self.assertEqual(b["by_severity"]["P1"], 2)
        self.assertEqual(a["threads"]["open"], [])
        self.assertEqual(sorted(e["finding_id"] for e in b["threads"]["open"]), ["R-001", "S-001"])
        self.assertEqual(sorted(e["finding_id"] for e in a["threads"]["resolved"]), ["R-001", "R-002"])
        self.assertEqual(a["verdict"]["conclusion"], "SUCCESS")
        self.assertEqual(b["verdict"]["conclusion"], "FAILURE")
        self.assertEqual((a["rounds"], b["rounds"]), (2, 1))
        self.assertIsNotNone(a["nits_comment"])
        self.assertIsNone(b["nits_comment"])
        # Same PR metadata and labels in both fixtures; every review-derived
        # field must differ.
        for key in ("verdict", "rounds", "open_blocking", "by_severity", "threads",
                    "pending_wontfix", "nits_comment"):
            self.assertNotEqual(a[key], b[key], f"{key} is input-independent")

    def test_pending_wontfix_is_quoted_from_input(self):
        _, b = run_fixture("open_p1")
        self.assertEqual(len(b["pending_wontfix"]), 1)
        pending = b["pending_wontfix"][0]
        self.assertEqual(pending["thread_id"], "PRRT_o2")
        self.assertIn("public request id", pending["reason"])
        _, a = run_fixture("all_resolved")
        self.assertEqual(a["pending_wontfix"], [])


class TestMarkerParsing(unittest.TestCase):

    def test_valid_marker(self):
        kind, fields, _ = RS.parse_finding_marker(
            "<!-- pr-guardian:finding id=R-001 severity=P1 -->\nbody")
        self.assertEqual(kind, "finding")
        self.assertEqual(fields, {"id": "R-001", "severity": "P1"})

    def test_field_order_and_spacing_tolerated(self):
        kind, fields, _ = RS.parse_finding_marker(
            "  <!--pr-guardian:finding severity=P0   id=SEC-012 -->")
        self.assertEqual((kind, fields), ("finding", {"id": "SEC-012", "severity": "P0"}))

    def test_no_marker_is_not_pr_guardian(self):
        self.assertEqual(RS.parse_finding_marker("Looks good to me")[0], "none")
        self.assertEqual(RS.parse_finding_marker("")[0], "none")

    def test_malformed_markers_are_unparsed_with_reason(self):
        cases = {
            "<!-- pr-guardian:finding id=bad severity=P1 -->": "id",
            "<!-- pr-guardian:finding id=R-001 severity=P9 -->": "severity",
            "<!-- pr-guardian:finding id=R-001 severity=P1": "well-formed",
            "<!-- pr-guardian:status id=R-001 status=fixed -->": "kind",
            "<!-- pr-guardian:finding severity=P1 -->": "id",
            "intro\n<!-- pr-guardian:finding id=R-001 severity=P1 -->": "well-formed",
        }
        for body, needle in cases.items():
            kind, fields, reason = RS.parse_finding_marker(body)
            self.assertEqual(kind, "unparsed", body)
            self.assertIsNone(fields, body)
            self.assertIn(needle, reason, body)

    def test_malformed_fixture_does_not_crash_and_fails_closed(self):
        code, doc = run_fixture("malformed_marker")
        self.assertEqual(code, 1)
        unparsed = {u["thread_id"]: u for u in doc["threads"]["unparsed"]}
        self.assertEqual(set(unparsed), {"PRRT_m1", "PRRT_m2", "PRRT_m3"})
        self.assertTrue(unparsed["PRRT_m3"]["is_resolved"])
        self.assertEqual([e["finding_id"] for e in doc["threads"]["open"]], ["R-004"])
        self.assertEqual(doc["by_severity"]["P0"], 1)

    def test_unparsed_open_thread_alone_blocks_exit_zero(self):
        doc = fixture("malformed_marker")
        pr = doc["data"]["repository"]["pullRequest"]
        pr["reviewThreads"]["nodes"] = [t for t in pr["reviewThreads"]["nodes"]
                                        if t["id"] == "PRRT_m1"]
        pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][1][
            "state"] = "SUCCESS"
        state = RS.build_state(doc)
        self.assertEqual(state["open_blocking"], 0)
        self.assertEqual(RS.exit_code(state), 1)

    def test_status_markers(self):
        body = ("<!-- pr-guardian:status id=R-001 status=reopened -->\n"
                "<!-- pr-guardian:status id=R-001 status=bogus -->")
        self.assertEqual([s["status"] for s in RS.parse_status_markers(body)], ["reopened"])

    def test_constants_match_shared_findings_contract(self):
        if not FINDINGS.exists():
            self.skipTest("findings.py not present (standalone install)")
        findings = _load(FINDINGS, "pr_review_loop_findings_contract")
        self.assertEqual(RS.ID_PATTERN, findings.ID_PATTERN)
        self.assertEqual(RS.SEVERITIES, findings.SEVERITIES)
        self.assertEqual(RS.BLOCKING_SEVERITIES, findings.BLOCKING_SEVERITIES)
        self.assertEqual(RS.STATUSES, findings.STATUSES)


class TestEscalationSignals(unittest.TestCase):

    def setUp(self):
        self.code, self.doc = run_fixture("escalation")
        self.kinds = {(s["kind"], s["finding_id"]) for s in self.doc["escalation_signals"]}

    def test_reopened_twice(self):
        self.assertIn(("finding_reopened_repeatedly", "R-001"), self.kinds)
        self.assertEqual([e["finding_id"] for e in self.doc["threads"]["reopened"]], ["R-001"])
        self.assertEqual(self.doc["threads"]["open"][0]["reopen_events"], 2)

    def test_pushback_answered_without_status_change(self):
        self.assertIn(("pushback_answered_thread_still_open", "R-001"), self.kinds)
        self.assertIn(("pushback_rejected_repeatedly", "R-001"), self.kinds)

    def test_rounds(self):
        self.assertEqual(self.doc["rounds"], 4)
        self.assertIn(("open_across_rounds", "R-001"), self.kinds)

    def test_accepted_pushback_raises_no_signal(self):
        self.assertFalse(any(fid == "R-002" for _, fid in self.kinds))

    def test_escalation_state_and_exit(self):
        self.assertEqual(self.code, 1)
        self.assertTrue(self.doc["escalation"]["needs_human_label"])
        self.assertFalse(self.doc["escalation"]["human_override_label"])
        self.assertEqual(len(self.doc["escalation"]["requested"]), 1)

    def test_signals_are_facts_not_judgements(self):
        banned = ("should", "recommend", "escalate now", "lazy", "legitimate", "score")
        for sig in self.doc["escalation_signals"]:
            self.assertEqual(set(sig), {"kind", "finding_id", "thread_id", "fact"})
            for word in banned:
                self.assertNotIn(word, sig["fact"].lower())

    def test_clean_pr_has_no_signals(self):
        _, a = run_fixture("all_resolved")
        self.assertEqual(a["escalation_signals"], [])

    def test_single_reopen_is_below_threshold(self):
        doc = fixture("escalation")
        thread = doc["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"][0]
        thread["comments"]["nodes"].pop()  # drop the second reopen
        kinds = {s["kind"] for s in RS.build_state(doc)["escalation_signals"]}
        self.assertNotIn("finding_reopened_repeatedly", kinds)


class TestNegatives(unittest.TestCase):
    """T4: things that must not exit 0, and usage that must be refused."""

    def _mutate(self, fn) -> int:
        doc = copy.deepcopy(fixture("all_resolved"))
        fn(doc["data"]["repository"]["pullRequest"])
        return RS.exit_code(RS.build_state(doc))

    def test_baseline_clean(self):
        self.assertEqual(self._mutate(lambda pr: None), 0)

    def test_verdict_pending_is_not_clean(self):
        def f(pr):
            ctx = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][1]
            ctx.update(state="PENDING")
        self.assertEqual(self._mutate(f), 1)

    def test_verdict_missing_is_not_clean(self):
        def f(pr):
            pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"].pop()
        self.assertEqual(self._mutate(f), 1)

    def test_other_check_named_verdict_does_not_count(self):
        def f(pr):
            ctx = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][1]
            ctx["context"] = "lint/verdict"
        self.assertEqual(self._mutate(f), 1)

    def test_unresolved_finding_with_passing_verdict_is_not_clean(self):
        self.assertEqual(self._mutate(
            lambda pr: pr["reviewThreads"]["nodes"][0].update(isResolved=False)), 1)

    def test_unresolved_human_thread_is_not_clean(self):
        def f(pr):
            pr["reviewThreads"]["nodes"].append({
                "id": "PRRT_h1", "isResolved": False, "isOutdated": False, "path": "a.py",
                "line": 1, "comments": {"nodes": [{"author": {"login": "owner"},
                                                   "body": "why this?", "createdAt": "x"}]}})
        self.assertEqual(self._mutate(f), 1)

    def test_status_context_verdict_supported(self):
        def f(pr):
            nodes = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
            nodes[1] = {"__typename": "StatusContext", "context": "pr-guardian/verdict",
                        "state": "FAILURE"}
        self.assertEqual(self._mutate(f), 1)

    def test_graphql_error_exits_2(self):
        proc = run("--from-file", str(FIXTURES / "graphql_error.json"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Could not resolve", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_unreadable_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not json", encoding="utf-8")
            self.assertEqual(run("--from-file", str(bad)).returncode, 2)
            self.assertEqual(run("--from-file", str(Path(tmp) / "missing.json")).returncode, 2)

    def test_gh_missing_exits_2(self):
        with tempfile.TemporaryDirectory() as empty:
            env = {**os.environ, "PATH": empty}
            proc = run("--pr", "7", "--repo", "acme/widgets", env=env)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("gh CLI not found", proc.stderr)

    def test_usage_errors_exit_64(self):
        for args in ([], ["--pr", "0"], ["--pr", "x"], ["--pr", "7", "--repo", "acme"],
                     ["--pr", "7", "--repo", "a/b;rm -rf"], ["--bogus"]):
            self.assertEqual(run(*args).returncode, 64, args)

    def test_help_documents_flags(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        for flag in ("--pr", "--repo", "--from-file", "--check-name", "--bot-login"):
            self.assertIn(flag, proc.stdout)


if __name__ == "__main__":
    unittest.main()
