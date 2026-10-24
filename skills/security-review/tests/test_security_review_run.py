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

"""End-to-end tests for run_scanners.py, run as a subprocess.

Two kinds:

* Fake tools. PATH is replaced by a directory of small Python executables
  named like the real scanners, which print canned output. These pin the exit
  code contract (0 / 1 / 2 / 64), missing-tool honesty, timeouts, redaction of
  a report that arrives *unredacted*, and diff-mode filtering, without any
  scanner installed.
* Live differentiation (T1). fixtures/repos/vulnerable (SQL injection plus a
  secret generated at run time) against fixtures/repos/clean, using whichever
  of semgrep and gitleaks is installed. Skipped, with the reason, otherwise.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPT = TESTS_DIR.parent / "scripts" / "run_scanners.py"
FIXTURES = TESTS_DIR / "fixtures"
CANNED = FIXTURES / "canned"

FAKE_TOOL = textwrap.dedent("""\
    #!{python}
    import json, os, sys, time
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, os.path.basename(__file__) + ".spec.json")) as fh:
        spec = json.load(fh)
    with open(os.path.join(here, os.path.basename(__file__) + ".argv"), "a") as fh:
        fh.write(json.dumps(sys.argv[1:]) + "\\n")
    time.sleep(spec.get("sleep", 0))
    if "--report-path" in sys.argv:
        with open(sys.argv[sys.argv.index("--report-path") + 1], "w") as fh:
            fh.write(spec.get("report", ""))
    sys.stdout.write(spec.get("stdout", ""))
    sys.stderr.write(spec.get("stderr", ""))
    sys.exit(spec.get("code", 0))
    """)


def fake_token(seed: int) -> str:
    rng = random.Random(seed)
    return "ghp_" + "".join(rng.choice(string.ascii_letters + string.digits)
                            for _ in range(36))


class Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def add_tool(self, name: str, **spec) -> None:
        path = self.bin / name
        path.write_text(FAKE_TOOL.format(python=sys.executable), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (self.bin / f"{name}.spec.json").write_text(json.dumps(spec), encoding="utf-8")

    def argv_of(self, name: str) -> list[list[str]]:
        f = self.bin / f"{name}.argv"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def add_git(self) -> None:
        git = shutil.which("git")
        if not git:
            self.skipTest("git not installed")
        (self.bin / "git").symlink_to(git)

    def write(self, rel: str, text: str) -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_tool(self, *args: str, path: str | None = None):
        env = {k: v for k, v in os.environ.items() if k not in ("PATH",)}
        env["PATH"] = path if path is not None else str(self.bin)
        proc = subprocess.run([sys.executable, str(SCRIPT), "--repo-root",
                               str(self.repo), *args],
                              capture_output=True, text=True, env=env,
                              timeout=120, shell=False)
        report = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
        return proc.returncode, report, proc.stderr


class ExitContractTest(Harness):
    def test_missing_tools_are_partial_never_clean(self):
        self.write("app.py", "print('hi')\n")
        code, report, err = self.run_tool()
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")
        missing = {i["what"] for i in report["not_inspected"]}
        self.assertEqual(missing, {"semgrep", "gitleaks"})
        self.assertEqual(report["tools"]["semgrep"]["status"], "skipped")
        self.assertIn("not installed", report["tools"]["semgrep"]["reason"])
        self.assertIn("not inspected: semgrep", err)
        # irrelevant tools are skipped without making the run partial
        self.assertIn("not relevant", report["tools"]["trivy"]["reason"])

    def test_all_relevant_tools_clean_exits_zero(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout=json.dumps({"results": [], "errors": []}))
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["not_inspected"], [])
        self.assertEqual(report["languages"], ["python"])
        semgrep_argv = self.argv_of("semgrep")[0]
        for cfg in ("p/default", "p/owasp-top-ten", "p/secrets", "p/python"):
            self.assertIn(cfg, semgrep_argv)
        self.assertIn("--redact", self.argv_of("gitleaks")[0])

    def test_leads_exit_one(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout=(CANNED / "semgrep.json").read_text())
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "leads")
        self.assertEqual(report["tools"]["semgrep"]["leads"], len(report["leads"]))
        self.assertTrue(any("CWE-89" in ld["cwe"] for ld in report["leads"]))

    def test_leads_with_a_missing_tool_is_still_partial(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout=(CANNED / "semgrep.json").read_text())
        code, report, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertTrue(report["leads"])
        self.assertEqual([i["what"] for i in report["not_inspected"]], ["gitleaks"])

    def test_tool_error_is_partial(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", code=7, stderr="rule fetch failed\n")
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertEqual(report["tools"]["semgrep"]["status"], "error")
        self.assertIn("exit 7", report["tools"]["semgrep"]["reason"])

    def test_unparseable_output_is_partial(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout="{not json")
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("unparseable", report["tools"]["semgrep"]["reason"])

    def test_missing_report_file_is_partial(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout=json.dumps({"results": []}))
        self.add_tool("gitleaks", report="")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertEqual(report["tools"]["gitleaks"]["status"], "error")

    def test_timeout_is_partial(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", sleep=5, stdout=json.dumps({"results": []}))
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool("--timeout", "1")
        self.assertEqual(code, 2)
        self.assertEqual(report["tools"]["semgrep"]["status"], "timed_out")

    def test_deselected_relevant_tool_is_reported_not_inspected(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool("--tools", "gitleaks")
        self.assertEqual(code, 0)
        self.assertEqual(report["not_inspected"],
                         [{"what": "semgrep",
                           "reason": "relevant but not selected via --tools"}])

    def test_workflows_and_lockfiles_bring_in_their_tools(self):
        self.write("app.py", "print('hi')\n")
        self.write(".github/workflows/ci.yml", "on: push\n")
        self.write("requirements.txt", "flask==0.12.2\n")
        code, report, _ = self.run_tool()
        self.assertEqual(code, 2)
        missing = {i["what"] for i in report["not_inspected"]}
        self.assertEqual(missing, {"semgrep", "gitleaks", "osv-scanner",
                                   "actionlint", "zizmor", "pip-audit"})


class RedactionEndToEndTest(Harness):
    def test_unredacted_report_never_reaches_any_output(self):
        # Simulate a gitleaks that ignored --redact: its report carries the
        # raw secret in Secret and Match. Nothing downstream may contain it.
        token = fake_token(21)
        self.write("app.py", "print('hi')\n")
        report = (CANNED / "gitleaks.json").read_text().replace("__SECRET__", token)
        semgrep = (CANNED / "semgrep.json").read_text().replace("__SECRET__", token)
        self.add_tool("gitleaks", report=report, stderr=f"debug: saw {token}\n")
        self.add_tool("semgrep", stdout=semgrep)
        json_out, sarif_out = self.tmp / "leads.json", self.tmp / "leads.sarif"
        code, parsed, err = self.run_tool("--json-out", str(json_out),
                                          "--sarif-out", str(sarif_out))
        self.assertEqual(code, 1)
        blobs = [json.dumps(parsed), err, json_out.read_text(), sarif_out.read_text()]
        for blob in blobs:
            self.assertNotIn(token, blob)
            self.assertNotIn(token[4:24], blob)
        self.assertTrue(any(ld["tool"] == "gitleaks" for ld in parsed["leads"]))

    def test_raw_report_is_deleted(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("gitleaks", report="[]")
        self.add_tool("semgrep", stdout=json.dumps({"results": []}))
        self.run_tool()
        report_path = self.argv_of("gitleaks")[0]
        rp = Path(report_path[report_path.index("--report-path") + 1])
        self.assertFalse(rp.exists())


class OutputsTest(Harness):
    def test_sarif_mirrors_leads(self):
        self.write("app.py", "print('hi')\n")
        self.add_tool("semgrep", stdout=(CANNED / "semgrep.json").read_text())
        self.add_tool("gitleaks", report="[]")
        sarif_out = self.tmp / "out.sarif"
        _, report, _ = self.run_tool("--sarif-out", str(sarif_out))
        sarif = json.loads(sarif_out.read_text())
        self.assertEqual(sarif["version"], "2.1.0")
        results = sarif["runs"][0]["results"]
        self.assertEqual(len(results), len(report["leads"]))
        self.assertTrue(all(r["ruleId"].startswith("semgrep/") for r in results))

    def test_help_documents_every_flag(self):
        code, _, _ = self.run_tool("--help")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                              capture_output=True, text=True, shell=False, timeout=30)
        self.assertEqual(proc.returncode, 0)
        for flag in ("--diff", "--audit", "--repo-root", "--tools", "--json-out",
                     "--sarif-out", "--timeout"):
            self.assertIn(flag, proc.stdout)


class UsageTest(Harness):
    def test_unknown_tool(self):
        code, _, err = self.run_tool("--tools", "semgrep,nmap")
        self.assertEqual(code, 64)
        self.assertIn("nmap", err)

    def test_diff_and_audit_are_exclusive(self):
        code, _, _ = self.run_tool("--diff", "HEAD", "--audit")
        self.assertEqual(code, 64)

    def test_diff_base_must_be_a_commit(self):
        self.add_git()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, shell=False)
        code, _, err = self.run_tool("--diff", "no-such-ref")
        self.assertEqual(code, 64)
        self.assertIn("does not name a commit", err)

    def test_diff_base_cannot_be_an_option(self):
        code, _, _ = self.run_tool("--diff=--output=/tmp/x")
        self.assertEqual(code, 64)

    def test_repo_root_must_exist(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--repo-root",
                               str(self.tmp / "nope")], capture_output=True,
                              text=True, shell=False, timeout=30)
        self.assertEqual(proc.returncode, 64)


class DiffModeTest(Harness):
    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.email=t@example.invalid",
                        "-c", "user.name=t", *args], check=True, capture_output=True,
                       shell=False)

    def test_diff_mode_scopes_tools_and_filters_unchanged_files(self):
        self.add_git()
        self.git("init", "-q")
        self.write("app.py", "print('hi')\n")
        self.write(".github/workflows/old.yml", "on: push\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.write(".github/workflows/new.yml", "on: pull_request_target\n")
        self.write("dirty.py", "print('uncommitted')\n")
        al = [{"message": "old", "filepath": ".github/workflows/old.yml", "line": 1,
               "column": 1, "kind": "syntax-check"},
              {"message": "new", "filepath": ".github/workflows/new.yml", "line": 1,
               "column": 1, "kind": "expression"}]
        self.add_tool("actionlint", stdout=json.dumps(al), code=1)
        self.add_tool("zizmor", stdout="[]")
        self.add_tool("semgrep", stdout=json.dumps({"results": []}))
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool("--diff", "HEAD")
        self.assertEqual(code, 1, report)
        self.assertEqual(report["mode"], "diff")
        self.assertEqual([ld["file"] for ld in report["leads"]],
                         [".github/workflows/new.yml"])
        self.assertEqual(report["tools"]["actionlint"]["filtered_unchanged"], 1)
        semgrep_argv = self.argv_of("semgrep")[0]
        self.assertIn("--baseline-commit", semgrep_argv)
        gl = self.argv_of("gitleaks")
        self.assertEqual(len(gl), 2)                  # commit range + uncommitted copy
        self.assertTrue(any(a.startswith("--log-opts=") and a.endswith("..HEAD")
                            for a in gl[0]))
        self.assertEqual(gl[1][0], "dir")

    def test_diff_mode_skips_tools_whose_files_did_not_change(self):
        self.add_git()
        self.git("init", "-q")
        self.write("app.py", "print('hi')\n")
        self.write("requirements.txt", "flask==3.0.0\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.write("app.py", "print('changed')\n")
        self.add_tool("semgrep", stdout=json.dumps({"results": []}))
        self.add_tool("gitleaks", report="[]")
        code, report, _ = self.run_tool("--diff", "HEAD")
        self.assertEqual(code, 0, report)
        self.assertIn("changed since base", report["tools"]["osv-scanner"]["reason"])


@unittest.skipUnless(shutil.which("semgrep") or shutil.which("gitleaks"),
                     "neither semgrep nor gitleaks is installed")
class LiveDifferentiationTest(unittest.TestCase):
    """T1 with real scanners: vulnerable fixture gives leads, clean gives none."""

    def scan(self, name: str, tools: list[str]):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = Path(tmp) / name
        shutil.copytree(FIXTURES / "repos" / name, repo)
        if name == "vulnerable":
            (repo / "config.py").write_text(f'GITHUB_TOKEN = "{fake_token(7)}"\n',
                                            encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(repo),
                               "--tools", ",".join(tools), "--timeout", "300"],
                              capture_output=True, text=True, shell=False, timeout=900)
        return proc.returncode, json.loads(proc.stdout), proc.stderr

    def test_vulnerable_and_clean_fixtures_differ(self):
        tools = [t for t in ("semgrep", "gitleaks") if shutil.which(t)]
        bad_code, bad, _ = self.scan("vulnerable", tools)
        good_code, good, _ = self.scan("clean", tools)
        for name in tools:
            if bad["tools"][name]["status"] != "ran" or good["tools"][name]["status"] != "ran":
                self.skipTest(f"{name} did not run: {bad['tools'][name]['reason']}"
                              " (semgrep needs network for registry rules)")
        self.assertEqual(bad_code, 1)
        self.assertEqual(good_code, 0, good["leads"])
        self.assertEqual(good["leads"], [])
        found = {c for ld in bad["leads"] for c in ld["cwe"]}
        if "semgrep" in tools:
            self.assertIn("CWE-89", found)
        if "gitleaks" in tools:
            self.assertIn("CWE-798", found)
            self.assertTrue(any(ld["tool"] == "gitleaks" and ld["file"] == "config.py"
                                for ld in bad["leads"]))
        self.assertNotIn(fake_token(7), json.dumps(bad))


if __name__ == "__main__":
    unittest.main()
