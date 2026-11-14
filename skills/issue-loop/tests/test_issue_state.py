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

"""Tests for issue_state.py: differentiation, trusted markers, redaction, injection framing."""

from __future__ import annotations

import json
import os
import random
import stat
import string
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures"
SCRIPT = SKILL / "scripts" / "issue_state.py"


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        env=env,
        timeout=60,
    )


def run_fixture(name: str, *extra: str) -> tuple[int, dict]:
    proc = run_cli("--from-file", str(FIXTURES / f"{name}.json"), "--repo", "acme/widgets", *extra)
    return proc.returncode, json.loads(proc.stdout)


def _dynamic_gh_token(seed: int) -> str:
    rng = random.Random(seed)
    return "ghp_" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(32))


class TestDifferentiation(unittest.TestCase):
    """T1: opposite fixtures produce different exits and distinct derived fields."""

    def test_open_vs_empty_vs_truncated(self):
        code_open, open_doc = run_fixture("gh_issues_open")
        code_empty, empty_doc = run_fixture("gh_issues_empty")
        code_trunc, trunc_doc = run_fixture("gh_issues_truncated")

        self.assertEqual(code_open, 0)
        self.assertEqual(code_empty, 1)
        self.assertEqual(code_trunc, 1)

        self.assertEqual(open_doc["status"], "work_available")
        self.assertEqual(empty_doc["status"], "empty")
        self.assertEqual(trunc_doc["status"], "partial_truncated")

        self.assertEqual([i["number"] for i in open_doc["issues"]], [101, 102, 103])
        self.assertEqual(empty_doc["issues"], [])
        self.assertEqual(len(trunc_doc["not_checked"]), 2)
        self.assertEqual(open_doc["not_checked"], [])

        for key in ("status", "issues", "open_prs", "summary"):
            self.assertNotEqual(open_doc[key], empty_doc[key], f"{key} is input-independent")

    def test_trusted_vs_untrusted_stage_markers_and_open_pr_links(self):
        code, doc = run_fixture("gh_issues_open")
        self.assertEqual(code, 0)
        by_num = {item["number"]: item for item in doc["issues"]}

        # #101 has a forged marker from mallory -> recorded as trusted=False, not already_triaged
        self.assertEqual(len(by_num[101]["stage_markers"]["triage"]), 1)
        self.assertFalse(by_num[101]["stage_markers"]["triage"][0]["trusted"])
        self.assertEqual(by_num[101]["stage_markers"]["triage"][0]["author"], "mallory")

        # #102 has a marker from viewer ("maintainer") -> trusted=True
        self.assertEqual(len(by_num[102]["stage_markers"]["triage"]), 1)
        self.assertTrue(by_num[102]["stage_markers"]["triage"][0]["trusted"])
        self.assertEqual(by_num[102]["stage_markers"]["triage"][0]["comment_id"], 7001)
        self.assertEqual(by_num[102]["stage_markers"]["triage"][0]["author"], "maintainer")

        links_103 = by_num[103]["linked_open_prs"]
        self.assertEqual(len(links_103), 1)
        self.assertEqual(links_103[0]["number"], 205)
        self.assertEqual(doc["summary"]["with_open_pr"], 1)
        self.assertEqual(doc["summary"]["already_triaged"], 1)


class TestRedactionAndInjectionFraming(unittest.TestCase):
    """S8 redaction at capture and prompt-injection framing for untrusted text."""

    def test_secrets_pii_and_injections_are_redacted_and_framed(self):
        code, doc = run_fixture("gh_issue_with_injection_and_secret", "--issue", "404")
        self.assertEqual(code, 0)
        raw_out = json.dumps(doc)

        for leaked in ("alice@example.com", "reporter@example.org", "hunter2pass", "topsecrettokenvalue123456"):
            self.assertNotIn(leaked, raw_out)

        issue = doc["issues"][0]
        self.assertTrue(issue["title"]["untrusted"])
        self.assertTrue(issue["body"]["untrusted"])
        self.assertIn("UNTRUSTED ISSUE DATA", issue["body"]["instruction_warning"])
        self.assertGreaterEqual(issue["injection_signals_count"], 4)

        directives = set(issue["body"]["suspicious_directives"])
        self.assertIn("instruction_override", directives)
        self.assertIn("xml_role_tag", directives)
        self.assertIn("forged_stage_marker", directives)
        self.assertIn("shell_pipe_exec", directives)

        self.assertNotIn("<!-- issue-loop:stage=pr v1 -->", issue["body"]["text"])
        self.assertEqual(issue["stage_markers"]["pr"], [])
        self.assertFalse(issue["stage_markers"]["triage"][0]["trusted"])

    def test_dynamic_token_and_host_path_scrubbed_before_output(self):
        raw = json.loads((FIXTURES / "gh_issue_with_injection_and_secret.json").read_text(encoding="utf-8"))
        tok = _dynamic_gh_token(77)
        host_home = "/Users/" + "alice/projects/app"  # host-path-ok: dynamic redaction probe
        raw["data"]["repository"]["issue"]["body"] += f"\nToken: {tok}\nPath: {host_home}\n"

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "issue.json"
            out = Path(tmp) / "evidence.json"
            src.write_text(json.dumps(raw), encoding="utf-8")
            proc = run_cli("--from-file", str(src), "--repo", "acme/widgets", "--issue", "404", "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(tok, proc.stdout)
            self.assertNotIn("alice/projects", proc.stdout)
            written = out.read_text(encoding="utf-8")
            self.assertNotIn(tok, written)
            self.assertIn("[REDACTED:github-token]", written)
            self.assertIn("~/projects/app", written)


class TestNegativeAndLiveCli(unittest.TestCase):
    """T4 negatives: bad flags, missing gh, malformed input, and live fake gh CLI."""

    def test_usage_errors_exit_64(self):
        for args in (
            ["--issue", "0", "--from-file", str(FIXTURES / "gh_issues_open.json")],
            ["--repo", "not-a-repo", "--from-file", str(FIXTURES / "gh_issues_open.json")],
            ["--limit", "0", "--from-file", str(FIXTURES / "gh_issues_open.json")],
            ["--limit", "101", "--from-file", str(FIXTURES / "gh_issues_open.json")],
            ["--bogus-flag"],
        ):
            proc = run_cli(*args)
            self.assertEqual(proc.returncode, 64, (args, proc.stderr))

    def test_missing_gh_exits_2(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run_cli("--repo", "acme/widgets", env={**os.environ, "PATH": empty})
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("gh", proc.stderr)

    def test_unreadable_or_error_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            self.assertEqual(run_cli("--from-file", str(bad)).returncode, 2)
            self.assertEqual(run_cli("--from-file", str(Path(tmp) / "missing.json")).returncode, 2)

            gql_err = Path(tmp) / "err.json"
            gql_err.write_text(json.dumps({"errors": [{"message": "Not found"}]}), encoding="utf-8")
            proc = run_cli("--from-file", str(gql_err), "--repo", "acme/widgets")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Not found", proc.stderr)

    def test_fake_gh_binary_invocation_and_include_closed_query(self):
        fixture_text = (FIXTURES / "gh_issues_open.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            calls_log = Path(tmp) / "gh_calls.json"
            gh_path = bin_dir / "gh"
            gh_path.write_text(
                textwrap.dedent(
                    f"""\
                    #!{sys.executable}
                    import json, sys
                    if sys.argv[1:3] == ["api", "graphql"]:
                        with open({str(calls_log)!r}, "a") as fh:
                            fh.write(json.dumps(sys.argv[1:]) + "\\n")
                        sys.stdout.write({fixture_text!r})
                        sys.exit(0)
                    sys.stderr.write("unexpected gh call: " + repr(sys.argv[1:]))
                    sys.exit(1)
                    """
                ),
                encoding="utf-8",
            )
            gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

            proc_open = run_cli("--repo", "acme/widgets", env={**os.environ, "PATH": str(bin_dir)})
            self.assertEqual(proc_open.returncode, 0, proc_open.stderr)

            proc_all = run_cli("--repo", "acme/widgets", "--include-closed", env={**os.environ, "PATH": str(bin_dir)})
            self.assertEqual(proc_all.returncode, 0, proc_all.stderr)

            calls = [json.loads(line) for line in calls_log.read_text().splitlines()]
            self.assertTrue(any("states: [OPEN]" in arg for arg in calls[0]))
            self.assertTrue(any("states: [OPEN, CLOSED]" in arg for arg in calls[1]))


if __name__ == "__main__":
    unittest.main()
