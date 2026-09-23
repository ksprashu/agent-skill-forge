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

"""Tests for skills/work/scripts/forensic_audit.py.

The two load-bearing tests are ``test_known_fake_is_rejected`` and
``test_known_good_is_accepted``. Together they pin the auditor between two
committed fixtures, so it can neither become a rubber stamp nor an
unconditional ``exit(1)``. Everything else is detector-level detail.

Written after the 2026-09-23 review, where the previous auditor cleared a
hardcoded implementation with "ZERO forensic violations" in its strictest mode.
"""

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES = SKILL_DIR / "fixtures"
sys.path.insert(0, str(SCRIPTS_DIR))

import forensic_audit as FA  # noqa: E402

SCRIPT = str(SCRIPTS_DIR / "forensic_audit.py")
KNOWN_FAKE = FIXTURES / "known_fake"
KNOWN_GOOD = FIXTURES / "known_good"


def run_cli(*args, timeout=120):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout,
    )


def audit_source(code, strict=True):
    """Audit a snippet as production source; return violation categories."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "module.py"
        path.write_text(textwrap.dedent(code), encoding="utf-8")
        coverage = FA.ScanCoverage()
        found = FA.audit_python_source(str(path), strict, coverage)
    return [v.category for v in found]


def audit_test(code, strict=True):
    """Audit a snippet as a test suite; return violation categories."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test_module.py"
        path.write_text(textwrap.dedent(code), encoding="utf-8")
        coverage = FA.ScanCoverage()
        found = FA.audit_python_test(str(path), strict, coverage)
    return [v.category for v in found]


# ---------------------------------------------------------------------------
# The contract: pinned between two fixtures
# ---------------------------------------------------------------------------

class TestFixtureContract(unittest.TestCase):
    """V1 and V2 from docs/ENGINEERING_STANDARD.md §4."""

    def test_known_fake_is_rejected(self):
        result = run_cli("--target-dir", str(KNOWN_FAKE), "--strict")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VETO", result.stdout)

    def test_known_good_is_accepted(self):
        result = run_cli("--target-dir", str(KNOWN_GOOD), "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CLEARED", result.stdout)

    def test_the_fake_fixtures_own_tests_pass(self):
        """The fake is green. That is the whole point of it."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
            cwd=str(KNOWN_FAKE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_reports_for_fake_and_good_differ(self):
        """Differentiation (T1): opposite inputs, different output."""
        fake = run_cli("--target-dir", str(KNOWN_FAKE), "--json").stdout
        good = run_cli("--target-dir", str(KNOWN_GOOD), "--json").stdout
        self.assertNotEqual(fake, good)
        self.assertNotEqual(json.loads(fake)["verdict"], json.loads(good)["verdict"])

    def test_the_specific_regression_is_named(self):
        """The hardcoded evaluate() that shipped must be caught by name."""
        payload = json.loads(run_cli("--target-dir", str(KNOWN_FAKE), "--json").stdout)
        hardcoded = [v for v in payload["violations"] if v["category"] == "HARDCODED_RETURN"]
        self.assertTrue(any(v["file"].endswith("src/evaluator.py") for v in hardcoded))
        self.assertTrue(any("evaluate" in v["message"] for v in hardcoded))


# ---------------------------------------------------------------------------
# Production source detectors — the surface the old auditor never looked at
# ---------------------------------------------------------------------------

class TestHardcodedReturn(unittest.TestCase):
    def test_function_ignoring_its_argument_is_vetoed(self):
        self.assertIn("HARDCODED_RETURN", audit_source("""
            def evaluate(evidence):
                return {"score": 87}
        """))

    def test_function_using_its_argument_is_clean(self):
        self.assertEqual([], audit_source("""
            def evaluate(evidence):
                return {"score": len(evidence)}
        """))

    def test_constant_return_behind_a_parameter_branch_is_clean(self):
        """A predicate returns literals, but the branch depends on the input."""
        self.assertEqual([], audit_source("""
            def is_ready(state):
                if state == "done":
                    return True
                return False
        """))

    def test_zero_argument_constant_function_is_clean(self):
        """No parameters means no input to ignore."""
        self.assertEqual([], audit_source("""
            def schema_version():
                return "1.0"
        """))

    def test_nested_literal_container_is_still_hardcoded(self):
        self.assertIn("HARDCODED_RETURN", audit_source("""
            def profile(evidence, harness):
                return {"dims": [1, 2, 3], "band": ("high", "low")}
        """))

    def test_method_using_self_but_not_its_argument_is_vetoed(self):
        self.assertIn("HARDCODED_RETURN", audit_source("""
            class Scorer:
                def score(self, candidate):
                    return 95.0
        """))

    def test_nested_function_returns_do_not_leak_to_the_parent(self):
        self.assertEqual([], audit_source("""
            def outer(items):
                def inner():
                    return 7
                return [inner() for _ in items]
        """))

    def test_fstring_with_a_parameter_is_not_constant(self):
        self.assertEqual([], audit_source("""
            def label(name):
                return f"task-{name}"
        """))


class TestStubDetection(unittest.TestCase):
    def test_bare_pass_body_is_flagged(self):
        self.assertIn("UNIMPLEMENTED_STUB", audit_source("""
            def merge(a, b):
                '''Merge two profiles.'''
                pass
        """))

    def test_not_implemented_error_is_flagged(self):
        self.assertIn("UNIMPLEMENTED_STUB", audit_source("""
            def merge(a, b):
                raise NotImplementedError
        """))

    def test_abstract_method_is_exempt(self):
        self.assertEqual([], audit_source("""
            from abc import abstractmethod
            class Base:
                @abstractmethod
                def merge(self, a, b):
                    ...
        """))

    def test_protocol_members_are_exempt(self):
        self.assertEqual([], audit_source("""
            from typing import Protocol
            class Merger(Protocol):
                def merge(self, a, b) -> dict:
                    ...
        """))

    def test_raising_a_real_error_is_not_a_stub(self):
        self.assertEqual([], audit_source("""
            def merge(a, b):
                raise ValueError(f"cannot merge {a} and {b}")
        """))


class TestDeadComputation(unittest.TestCase):
    def test_discarded_call_result_is_flagged(self):
        self.assertIn("DEAD_COMPUTATION", audit_source("""
            def run(turns):
                cleaned = normalise(turns)
                scored = evaluate(cleaned)
                return {"status": "complete", "n": len(cleaned)}
        """))

    def test_used_call_result_is_clean(self):
        self.assertEqual([], audit_source("""
            def run(turns):
                cleaned = normalise(turns)
                return evaluate(cleaned)
        """))

    def test_underscore_prefixed_discard_is_tolerated(self):
        self.assertEqual([], audit_source("""
            def run(turns):
                _unused = warm_cache(turns)
                return len(turns)
        """))


class TestIgnoredParameters(unittest.TestCase):
    def test_multi_statement_function_reading_no_parameter_is_flagged(self):
        self.assertIn("IGNORED_PARAMETERS", audit_source("""
            def persist(record, path):
                registry = build_registry()
                registry.flush()
                emit_metric("persisted")
        """))

    def test_dunder_methods_are_exempt(self):
        self.assertEqual([], audit_source("""
            class Thing:
                def __eq__(self, other):
                    calls.append(1)
                    return NotImplemented
        """))


# ---------------------------------------------------------------------------
# Test-suite detectors
# ---------------------------------------------------------------------------

class TestSuiteDetectors(unittest.TestCase):
    def test_tautological_assertion(self):
        self.assertIn("TAUTOLOGICAL_ASSERTION", audit_test("""
            def test_thing():
                assert True
        """))

    def test_self_comparison(self):
        self.assertIn("TAUTOLOGICAL_ASSERTION", audit_test("""
            def test_thing():
                x = compute()
                assert x == x
        """))

    def test_empty_body(self):
        self.assertIn("EMPTY_TEST_BODY", audit_test("""
            def test_thing():
                pass
        """))

    def test_no_assertion_at_all(self):
        self.assertIn("NO_ASSERTION", audit_test("""
            def test_thing():
                result = compute(1, 2)
                print(result)
        """))

    def test_delegating_to_an_assertion_helper_counts_as_asserting(self):
        """Parameterised negative tests factor the assert into a helper."""
        categories = audit_test("""
            class T:
                def _assert_rejected(self, value):
                    assert value not in allowed
                def test_email(self):
                    self._assert_rejected("a@b.com")
        """)
        self.assertNotIn("NO_ASSERTION", categories)

    def test_existence_only_assertions_are_flagged(self):
        self.assertIn("WEAK_ASSERTION_ONLY", audit_test("""
            def test_evaluate():
                result = evaluate({})
                assert "score" in result
                assert result is not None
        """))

    def test_value_assertions_are_not_flagged(self):
        categories = audit_test("""
            def test_evaluate():
                assert evaluate({"n": 2}) == {"score": 4}
        """)
        self.assertNotIn("WEAK_ASSERTION_ONLY", categories)

    def test_pytest_raises_is_a_real_assertion(self):
        categories = audit_test("""
            import pytest
            def test_rejects():
                with pytest.raises(ValueError):
                    merge({}, {"band": "extreme"})
        """)
        self.assertNotIn("NO_ASSERTION", categories)
        self.assertNotIn("WEAK_ASSERTION_ONLY", categories)

    def test_mock_import_is_flagged(self):
        self.assertIn("MOCK_IMPORT", audit_test("""
            from unittest.mock import patch
            def test_thing():
                assert compute() == 3
        """))

    def test_mock_invocation_is_flagged(self):
        self.assertIn("MOCK_INVOCATION", audit_test("""
            def test_thing():
                client = MagicMock()
                assert client.call() is not None
        """))


class TestJavaScriptScan(unittest.TestCase):
    def _scan(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.test.js"
            path.write_text(textwrap.dedent(code), encoding="utf-8")
            return [v.category for v in FA.audit_js_file(str(path), True)]

    def test_tautology(self):
        self.assertIn("TAUTOLOGICAL_ASSERTION", self._scan("it('x', () => { expect(true).toBe(true) })"))

    def test_mock(self):
        self.assertIn("MOCK_INVOCATION", self._scan("const f = jest.fn();"))

    def test_real_assertion_is_clean(self):
        self.assertEqual([], self._scan("it('x', () => { expect(add(1,2)).toBe(3) })"))


# ---------------------------------------------------------------------------
# Discovery, severity, and honest reporting
# ---------------------------------------------------------------------------

class TestDiscovery(unittest.TestCase):
    def test_source_and_tests_are_classified_apart(self):
        coverage = FA.ScanCoverage()
        FA.discover(KNOWN_FAKE, [], coverage)
        self.assertTrue(any(p.endswith("src/evaluator.py") for p in coverage.source_files))
        self.assertTrue(any(p.endswith("tests/test_evaluator.py") for p in coverage.test_files))
        self.assertFalse(any("test_" in Path(p).name for p in coverage.source_files))

    def test_production_source_is_actually_audited(self):
        """W-02: the old auditor globbed only test files."""
        coverage = FA.ScanCoverage()
        FA.discover(KNOWN_FAKE, [], coverage)
        self.assertGreater(len(coverage.source_files), 0)

    def test_is_test_path_recognises_the_usual_shapes(self):
        for name in ("tests/foo.py", "test_x.py", "x_test.py", "a.spec.ts", "b.test.js"):
            self.assertTrue(FA.is_test_path(Path(name)), name)
        for name in ("src/evaluator.py", "lib/latest.py", "contest.py"):
            self.assertFalse(FA.is_test_path(Path(name)), name)

    def test_exclude_pattern_removes_files_and_says_so(self):
        payload = json.loads(run_cli(
            "--target-dir", str(KNOWN_FAKE), "--exclude", "src/", "--json").stdout)
        self.assertEqual(payload["coverage"]["source_files_audited"], 0)
        self.assertGreater(payload["coverage"]["files_skipped"], 0)


class TestSeverityLadder(unittest.TestCase):
    def test_strict_escalates_advisory_findings(self):
        lenient = audit_source("def f(a, b):\n    pass\n", strict=False)
        self.assertEqual(["UNIMPLEMENTED_STUB"], lenient)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.py"
            path.write_text("def f(a, b):\n    pass\n", encoding="utf-8")
            cov = FA.ScanCoverage()
            soft = FA.audit_python_source(str(path), False, cov)[0].severity
            hard = FA.audit_python_source(str(path), True, cov)[0].severity
        self.assertEqual(soft, FA.WARNING)
        self.assertEqual(hard, FA.VETO)

    def test_hardcoded_return_vetoes_even_in_development_mode(self):
        result = run_cli("--target-dir", str(KNOWN_FAKE), "--integrity-mode", "development")
        self.assertEqual(result.returncode, 1)

    def test_benchmark_mode_implies_strict(self):
        result = run_cli("--target-dir", str(KNOWN_FAKE), "--integrity-mode", "benchmark")
        self.assertIn("strict", result.stdout)


class TestHonestReporting(unittest.TestCase):
    """V5: a verifier must say what it did not check."""

    def test_report_states_what_was_not_checked(self):
        out = run_cli("--target-dir", str(KNOWN_GOOD)).stdout
        self.assertIn("Not checked by this tool", out)
        self.assertIn("semantic correctness", out)

    def test_report_states_the_audited_counts(self):
        out = run_cli("--target-dir", str(KNOWN_GOOD)).stdout
        self.assertIn("production source files audited", out)
        self.assertIn("test suite files audited", out)

    def test_clean_verdict_does_not_claim_zero_violations_overall(self):
        """'ZERO forensic violations detected' was the false claim in W-02."""
        out = run_cli("--target-dir", str(KNOWN_GOOD)).stdout
        self.assertNotIn("ZERO forensic violations", out)
        self.assertIn("surface described above", out)

    def test_a_directory_with_no_source_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            (Path(tmp) / "tests" / "test_x.py").write_text(
                "def test_x():\n    assert 1 + 1 == 2\n", encoding="utf-8")
            payload = json.loads(run_cli("--target-dir", tmp, "--json").stdout)
        self.assertTrue(any("No production source files" in n for n in payload["notes"]))

    def test_mutation_not_run_is_reported_not_implied(self):
        out = run_cli("--target-dir", str(KNOWN_GOOD)).stdout
        self.assertIn("mutation smoke", out.lower())
        self.assertIn("NOT RUN", out)


class TestJsonContract(unittest.TestCase):
    def test_json_payload_shape(self):
        payload = json.loads(run_cli("--target-dir", str(KNOWN_FAKE), "--json").stdout)
        for key in ("mode", "strict", "verdict", "veto_count", "warning_count",
                    "coverage", "notes", "violations"):
            self.assertIn(key, payload)
        self.assertEqual(payload["verdict"], "VETO")

    def test_violation_paths_are_relative_to_the_target(self):
        payload = json.loads(run_cli("--target-dir", str(KNOWN_FAKE), "--json").stdout)
        for violation in payload["violations"]:
            self.assertFalse(Path(violation["file"]).is_absolute(), violation["file"])


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestExecutionSafety(unittest.TestCase):
    def test_exec_and_record_does_not_use_a_shell(self):
        """W-11: shell=True on agent-authored strings is an injection path."""
        with tempfile.TemporaryDirectory() as tmp:
            canary = Path(tmp) / "pwned.txt"
            result = run_cli(
                "--target-dir", tmp,
                "--exec-and-record", f"{sys.executable} -c pass ; touch {canary}")
            self.assertFalse(canary.exists(),
                             "the shell metacharacter executed; shell=True has returned")
            self.assertIn(result.returncode, (0, 1, 2))

    def test_exec_and_record_writes_a_hashed_evidence_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli("--target-dir", tmp, "--exec-and-record", f"{sys.executable} -c pass")
            ledger = Path(tmp) / ".agents" / "EVIDENCE.md"
            self.assertTrue(ledger.exists())
            body = ledger.read_text(encoding="utf-8")
            self.assertIn("SHA-256 Proof", body)
            self.assertIn("exit code 0", body)

    def test_failed_command_vetoes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "--target-dir", tmp,
                "--exec-and-record", f"{sys.executable} -c \"import sys; sys.exit(3)\"")
            self.assertEqual(result.returncode, 1)

    def test_mutate_without_test_cmd_is_an_invocation_error(self):
        result = run_cli("--target-dir", str(KNOWN_GOOD), "--mutate")
        self.assertEqual(result.returncode, 2)

    def test_missing_target_dir_is_an_invocation_error(self):
        result = run_cli("--target-dir", "/nonexistent/path/xyz")
        self.assertEqual(result.returncode, 2)


class TestMutationSmoke(unittest.TestCase):
    """T2 as a first-class feature rather than a manual step."""

    CMD = f"{sys.executable} -m pytest tests -q -p no:cacheprovider"

    def test_honest_fixture_kills_every_mutant(self):
        payload = json.loads(run_cli(
            "--target-dir", str(KNOWN_GOOD), "--mutate", "--test-cmd", self.CMD,
            "--json", timeout=300).stdout)
        cov = payload["coverage"]
        self.assertTrue(cov["mutation_smoke_ran"])
        self.assertGreater(cov["mutants_total"], 0)
        self.assertEqual(cov["mutants_survived"], 0,
                         [v for v in payload["violations"] if v["category"] == "SURVIVING_MUTANT"])

    def test_fake_fixture_leaves_a_mutant_alive(self):
        payload = json.loads(run_cli(
            "--target-dir", str(KNOWN_FAKE), "--mutate", "--test-cmd", self.CMD,
            "--json", timeout=300).stdout)
        self.assertGreater(payload["coverage"]["mutants_survived"], 0)
        self.assertTrue(any(v["category"] == "SURVIVING_MUTANT" for v in payload["violations"]))

    def test_red_baseline_is_reported_not_silently_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            (Path(tmp) / "m.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
            (Path(tmp) / "tests" / "test_m.py").write_text(
                "def test_f():\n    assert 1 == 2\n", encoding="utf-8")
            payload = json.loads(run_cli(
                "--target-dir", tmp, "--mutate", "--test-cmd", self.CMD, "--json",
                timeout=300).stdout)
        self.assertFalse(payload["coverage"]["mutation_smoke_ran"])
        self.assertTrue(any("baseline" in n for n in payload["notes"]))


class TestTamperingDetection(unittest.TestCase):
    """Precise enough to be left on, off by default because it cannot tell an
    honest refactor from tampering without a known-good baseline."""

    def _repo_with_change(self, original, changed):
        tmp = tempfile.mkdtemp()
        root = Path(tmp)
        (root / "tests").mkdir()
        target = root / "tests" / "test_x.py"
        # Identity and signing are both set locally: a contributor with
        # `commit.gpgsign = true` globally cannot sign inside a throwaway repo
        # in a non-interactive test run, and the commit fails with an error
        # about the signing agent rather than anything to do with tampering.
        for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"],
                    ["git", "config", "user.name", "t"],
                    ["git", "config", "commit.gpgsign", "false"]):
            subprocess.run(cmd, cwd=tmp, check=True, capture_output=True)
        target.write_text(original, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp, check=True, capture_output=True)
        target.write_text(changed, encoding="utf-8")
        return tmp

    def test_deleted_assertion_is_caught(self):
        tmp = self._repo_with_change(
            "def test_x():\n    assert add(1, 2) == 3\n    assert add(0, 0) == 0\n",
            "def test_x():\n    assert add(1, 2) == 3\n")
        categories = [v.category for v in FA.check_git_tampering(tmp)]
        self.assertIn("TAMPERING_ASSERTION_DELETED", categories)

    def test_deleted_comment_mentioning_assert_is_not_tampering(self):
        tmp = self._repo_with_change(
            "def test_x():\n    # assert disk file creation\n    assert add(1, 2) == 3\n",
            "def test_x():\n    assert add(1, 2) == 3\n")
        self.assertEqual([], FA.check_git_tampering(tmp))

    def test_added_skip_marker_is_caught(self):
        tmp = self._repo_with_change(
            "def test_x():\n    assert add(1, 2) == 3\n",
            "import pytest\n\n@pytest.mark.skip\ndef test_x():\n    assert add(1, 2) == 3\n")
        categories = [v.category for v in FA.check_git_tampering(tmp)]
        self.assertIn("TAMPERING_TEST_SKIPPED", categories)

    def test_tampering_is_off_unless_requested(self):
        out = run_cli("--target-dir", str(KNOWN_GOOD)).stdout
        self.assertIn("Test tampering was not checked", out)

    def test_non_git_directory_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], FA.check_git_tampering(tmp))


# ---------------------------------------------------------------------------
# The auditor audits itself
# ---------------------------------------------------------------------------

class TestSelfAudit(unittest.TestCase):
    def test_the_repository_passes_its_own_strict_audit(self):
        """L4 candidate: this is the job CI runs."""
        repo_root = SKILL_DIR.parent.parent
        result = run_cli("--target-dir", str(repo_root), "--strict",
                         "--exclude", "fixtures/known_", timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])


if __name__ == "__main__":
    unittest.main()
