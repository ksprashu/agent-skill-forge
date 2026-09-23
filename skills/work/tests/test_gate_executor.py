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

"""Tests for skills/work/scripts/gate_executor.py and its use by the validator.

The load-bearing pair is ``test_failing_gate_blocks_passed`` and
``test_passing_gate_allows_passed``. A gate executor that always refuses is as
useless as one that always agrees; these two pin it between the failure modes.
Everything else tests one predicate.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gate_executor as GE  # noqa: E402

EXECUTOR = str(SCRIPTS_DIR / "gate_executor.py")
VALIDATOR = str(SCRIPTS_DIR / "dag_validator.py")

PASSING_TEST = "def test_ok():\n    assert 1 + 1 == 2\n"
FAILING_TEST = "def test_bad():\n    assert 1 + 1 == 3\n"

HONEST_SOURCE = textwrap.dedent('''
    """A small honest module."""


    def add(left, right):
        """Sum two numbers."""
        return left + right
''')

DAG_TEMPLATE = textwrap.dedent("""\
    # Test DAG

    ## Task Graph
    | ID | Title | Mode | Depends On | Inputs | Outputs | Gate | Status |
    |---|---|---|---|---|---|---|---|
    | worker | Build it | series | none | SPEC.md | src/mod.py | {gate} | PENDING |
""")


def run_executor(*args, cwd=None, timeout=300):
    return subprocess.run([sys.executable, EXECUTOR, *args], cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, timeout=timeout)


def run_validator(*args, timeout=300):
    return subprocess.run([sys.executable, VALIDATOR, *args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, timeout=timeout)


class ProjectFixture:
    """A throwaway project tree with source and a test suite."""

    def __init__(self, source=HONEST_SOURCE, test=PASSING_TEST):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src" / "mod.py").write_text(source, encoding="utf-8")
        (self.root / "tests" / "test_mod.py").write_text(test, encoding="utf-8")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()
        return False


def substantial(label):
    """Text long enough to clear the placeholder floor."""
    return (f"# {label}\n\n" + f"Findings recorded for {label}. " * 20)


class FixtureCopy:
    """A throwaway copy of a committed fixture corpus.

    Gates write evidence into ``.agents/`` under whatever directory they are
    pointed at. Pointing them at the committed corpus would have the test suite
    silently edit its own fixtures, so every gate that touches one works on a
    copy.
    """

    def __init__(self, name):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / name
        shutil.copytree(SKILL_DIR / "fixtures" / name, self.root)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()
        return False


# ---------------------------------------------------------------------------
# The pin: a gate must be able to both block and allow
# ---------------------------------------------------------------------------

class TestGateEnforcementPin(unittest.TestCase):

    def test_failing_gate_blocks_passed(self):
        with ProjectFixture(test=FAILING_TEST) as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="exit_0"))
            GE.evaluate_gate("exit_0", "worker", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(3, proc.returncode, proc.stderr)
            self.assertIn("Gate check failed", proc.stderr)
            self.assertIn("PENDING", dag.read_text(encoding="utf-8"))
            self.assertNotIn("| PASSED |", dag.read_text(encoding="utf-8"))

    def test_passing_gate_allows_passed(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="exit_0"))
            GE.evaluate_gate("exit_0", "worker", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertIn("| PASSED |", dag.read_text(encoding="utf-8"))

    def test_non_passed_transitions_are_not_gated(self):
        """RUNNING is reporting, not a claim. It needs no evidence."""
        with ProjectFixture(test=FAILING_TEST) as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="exit_0"))
            proc = run_validator(str(dag), "--set-status", "worker=RUNNING",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertIn("| RUNNING |", dag.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# exit_0 and the freshness rule
# ---------------------------------------------------------------------------

class TestExitZeroGate(unittest.TestCase):

    def test_green_command_passes(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("exit_0", "worker", fx.root,
                                      command=f"{sys.executable} -m pytest tests -q")
            self.assertTrue(result.passed, result.reason)

    def test_red_command_fails(self):
        with ProjectFixture(test=FAILING_TEST) as fx:
            result = GE.evaluate_gate("exit_0", "worker", fx.root,
                                      command=f"{sys.executable} -m pytest tests -q")
            self.assertFalse(result.passed)

    def test_no_recorded_run_fails(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("exit_0", "worker", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("No recorded verification run", result.reason)

    def test_recorded_run_satisfies_the_gate_later(self):
        with ProjectFixture() as fx:
            GE.evaluate_gate("exit_0", "worker", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            self.assertTrue(GE.evaluate_gate("exit_0", "worker", fx.root).passed)

    def test_stale_run_does_not_satisfy_the_gate(self):
        """A green run against code that has since changed is not evidence."""
        with ProjectFixture() as fx:
            GE.evaluate_gate("exit_0", "worker", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            fx.write("src/mod.py", HONEST_SOURCE + "\n\ndef sub(a, b):\n    return a - b\n")
            result = GE.evaluate_gate("exit_0", "worker", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("changed after", result.reason)

    def test_editing_documentation_does_not_invalidate_a_run(self):
        with ProjectFixture() as fx:
            GE.evaluate_gate("exit_0", "worker", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            fx.write("README.md", "# totally different prose\n")
            self.assertTrue(GE.evaluate_gate("exit_0", "worker", fx.root).passed)

    def test_an_audit_run_does_not_launder_itself_into_a_test_run(self):
        """A clean forensic audit exits 0. That is not the test suite passing."""
        with ProjectFixture(test=FAILING_TEST) as fx:
            self.assertTrue(GE.evaluate_gate("zero_mock", "worker", fx.root).passed)
            result = GE.evaluate_gate("exit_0", "worker", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("No recorded verification run", result.reason)

    def test_aliases_route_to_the_same_predicate(self):
        for alias in ("test_pass", "all_passed"):
            self.assertIs(GE.GATE_REGISTRY[alias].predicate,
                          GE.GATE_REGISTRY["exit_0"].predicate)


# ---------------------------------------------------------------------------
# zero_mock
# ---------------------------------------------------------------------------

class TestZeroMockGate(unittest.TestCase):

    def test_known_good_fixture_passes(self):
        with FixtureCopy("known_good") as fx:
            result = GE.evaluate_gate("zero_mock", "worker", fx.root)
            self.assertTrue(result.passed, result.reason)

    def test_known_fake_fixture_fails(self):
        with FixtureCopy("known_fake") as fx:
            result = GE.evaluate_gate("zero_mock", "worker", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("vetoed", result.reason)


# ---------------------------------------------------------------------------
# file_exists
# ---------------------------------------------------------------------------

class TestFileExistsGate(unittest.TestCase):

    def test_existing_substantial_output_passes(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Report"))
            result = GE.evaluate_gate("file_exists", "worker", fx.root,
                                      outputs=["report.md"])
            self.assertTrue(result.passed, result.reason)

    def test_missing_output_fails(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("file_exists", "worker", fx.root,
                                      outputs=["report.md"])
            self.assertFalse(result.passed)
            self.assertIn("does not exist", result.reason)

    def test_empty_output_fails(self):
        with ProjectFixture() as fx:
            fx.write("report.md", "")
            result = GE.evaluate_gate("file_exists", "worker", fx.root,
                                      outputs=["report.md"])
            self.assertFalse(result.passed)

    def test_placeholder_output_fails(self):
        with ProjectFixture() as fx:
            fx.write("report.md", "# Report\n\n" + "TBD\n" * 200)
            result = GE.evaluate_gate("file_exists", "worker", fx.root,
                                      outputs=["report.md"])
            self.assertFalse(result.passed)
            self.assertIn("placeholder", result.reason)

    def test_gate_without_declared_outputs_fails(self):
        with ProjectFixture() as fx:
            self.assertFalse(GE.evaluate_gate("file_exists", "worker", fx.root).passed)


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------

class TestAttestedGates(unittest.TestCase):

    def _attest(self, fx, **overrides):
        kwargs = dict(task="review", gate="review_pass", verdict="PASS",
                      reviewer_role="code-reviewer", worker_role="implementer",
                      evidence=["report.md"],
                      summary="Reviewed the diff against the spec and found no blocking issues.")
        kwargs.update(overrides)
        return GE.write_attestation(fx.root, **kwargs)

    def test_missing_attestation_fails(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("No attestation", result.reason)

    def test_valid_attestation_passes(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx)
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertTrue(result.passed, result.reason)

    def test_self_attestation_fails(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx, reviewer_role="implementer")
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("self-attestation", result.reason)

    def test_fail_verdict_does_not_open_the_gate(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx, verdict="FAIL")
            self.assertFalse(GE.evaluate_gate("review_pass", "review", fx.root).passed)

    def test_attestation_citing_a_missing_artifact_fails(self):
        with ProjectFixture() as fx:
            self._attest(fx, evidence=["nowhere.md"])
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("does not exist", result.reason)

    def test_attestation_citing_an_empty_artifact_fails(self):
        with ProjectFixture() as fx:
            fx.write("report.md", "ok\n")
            self._attest(fx)
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("byte floor", result.reason)

    def test_attestation_with_no_evidence_fails(self):
        with ProjectFixture() as fx:
            self._attest(fx, evidence=[])
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("cites no evidence", result.reason)

    def test_terse_summary_fails(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx, summary="lgtm")
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("summary", result.reason)

    def test_attestation_goes_stale_when_the_code_changes(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx)
            self.assertTrue(GE.evaluate_gate("review_pass", "review", fx.root).passed)
            fx.write("src/mod.py", HONEST_SOURCE + "\n\ndef mul(a, b):\n    return a * b\n")
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("stale", result.reason)

    def test_attestation_for_a_different_task_does_not_transfer(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx)
            path = GE.attestation_path(fx.root, "review", "review_pass")
            other = GE.attestation_path(fx.root, "other", "review_pass")
            other.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            result = GE.evaluate_gate("review_pass", "other", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("is for task", result.reason)

    def test_corrupt_attestation_fails(self):
        with ProjectFixture() as fx:
            path = GE.attestation_path(fx.root, "review", "review_pass")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not json", encoding="utf-8")
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertFalse(result.passed)
            self.assertIn("unreadable", result.reason)

    def test_attestation_reports_what_it_cannot_check(self):
        with ProjectFixture() as fx:
            fx.write("report.md", substantial("Code review"))
            self._attest(fx)
            result = GE.evaluate_gate("review_pass", "review", fx.root)
            self.assertTrue(any("judgement was correct" in n for n in result.not_checked))

    def test_every_judgement_gate_is_attested_not_mechanical(self):
        for gate in ("spec_approved", "design_pass", "arbiter_pass", "spike_pass",
                     "review_pass", "acceptance_pass"):
            self.assertEqual("attested", GE.GATE_REGISTRY[gate].kind, gate)


# ---------------------------------------------------------------------------
# victory_cert
# ---------------------------------------------------------------------------

class TestVictoryCertGate(unittest.TestCase):

    def test_unfinished_tasks_block_certification(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate(
                "victory_cert", "victory", fx.root,
                all_statuses={"worker": "PASSED", "reviewer": "PENDING"})
            self.assertFalse(result.passed)
            self.assertIn("reviewer", result.reason)

    def test_certification_requires_a_verification_run(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("victory_cert", "victory", fx.root,
                                      all_statuses={"worker": "PASSED"})
            self.assertFalse(result.passed)
            self.assertIn("verification run", result.reason)

    def test_faked_code_cannot_be_certified(self):
        with FixtureCopy("known_fake") as fx:
            result = GE.evaluate_gate("victory_cert", "victory", fx.root,
                                      all_statuses={"worker": "PASSED"})
            self.assertFalse(result.passed)
            self.assertIn("Forensic audit failed", result.reason)

    def test_full_certification_passes_when_everything_holds(self):
        with ProjectFixture() as fx:
            fx.write("VICTORY.md", substantial("Victory certificate"))
            GE.evaluate_gate("exit_0", "victory", fx.root,
                             command=f"{sys.executable} -m pytest tests -q")
            result = GE.evaluate_gate("victory_cert", "victory", fx.root,
                                      outputs=["VICTORY.md"],
                                      all_statuses={"worker": "PASSED", "victory": "PASSED"})
            self.assertTrue(result.passed, result.reason)


# ---------------------------------------------------------------------------
# Gate resolution: unknown names fail closed
# ---------------------------------------------------------------------------

class TestScaffoldedGatesAreExecutable(unittest.TestCase):
    """Every gate the scaffolder writes must resolve to a predicate.

    Gates fail closed, so a topology template naming a gate the registry has
    never heard of produces a DAG whose tasks can never reach PASSED — and the
    failure surfaces only when someone runs that topology. Four gates
    (``survey_pass``, ``fact_check_pass``, ``analysis_pass``, ``unslop_clean``)
    were in exactly that state when this test was written.
    """

    GATE_CELL = re.compile(
        r"\|\s*([A-Za-z0-9_. /-]+?)\s*\|\s*(?:PENDING|BLOCKED|RUNNING|PASSED|FAILED)\s*\|"
    )

    def _gates_in(self, path):
        text = Path(path).read_text(encoding="utf-8")
        return {m.group(1).strip() for m in self.GATE_CELL.finditer(text)}

    def test_every_gate_in_the_scaffolder_resolves(self):
        scaffolder = SCRIPTS_DIR / "scaffold_work.py"
        gates = self._gates_in(scaffolder)
        self.assertGreater(len(gates), 5, "gate extraction found almost nothing")
        for gate in sorted(gates):
            with self.subTest(gate=gate):
                spec = GE.resolve_spec(gate)
                self.assertNotEqual(
                    "unknown", spec.kind,
                    f"scaffold_work.py emits gate '{gate}' but GATE_REGISTRY has no "
                    f"predicate for it, so that topology can never pass",
                )

    def test_every_gate_in_the_committed_fixtures_resolves(self):
        fixtures = sorted((SCRIPTS_DIR.parent / "fixtures").glob("*.md"))
        self.assertTrue(fixtures, "no fixture DAGs found")
        for fixture in fixtures:
            for gate in sorted(self._gates_in(fixture)):
                with self.subTest(fixture=fixture.name, gate=gate):
                    self.assertNotEqual("unknown", GE.resolve_spec(gate).kind)

    def test_each_scaffolded_topology_produces_resolvable_gates(self):
        import subprocess

        topologies = ["full", "focused", "review", "proof", "massive", "lifecycle"]
        for topology in topologies:
            with self.subTest(topology=topology), tempfile.TemporaryDirectory() as tmp:
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS_DIR / "scaffold_work.py"),
                     "--project-dir", tmp, "--name", "GateProbe",
                     "--topology", topology],
                    capture_output=True, text=True,
                )
                self.assertEqual(0, proc.returncode, proc.stderr)
                dag = Path(tmp) / ".agents" / "DAG.md"
                self.assertTrue(dag.is_file(), f"{topology} scaffolded no DAG.md")
                gates = self._gates_in(dag)
                self.assertTrue(gates, f"{topology} DAG has no gate cells")
                for gate in sorted(gates):
                    self.assertNotEqual(
                        "unknown", GE.resolve_spec(gate).kind,
                        f"topology '{topology}' emits unresolvable gate '{gate}'",
                    )


class TestGateResolution(unittest.TestCase):

    def test_unknown_gate_fails_closed(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("looks_fine_to_me", "worker", fx.root)
            self.assertFalse(result.passed)
            self.assertEqual("unknown", result.kind)

    def test_typo_of_a_real_gate_fails_closed(self):
        with ProjectFixture() as fx:
            self.assertFalse(GE.evaluate_gate("exit0", "worker", fx.root).passed)

    def test_none_passes_trivially(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate("none", "worker", fx.root)
            self.assertTrue(result.passed)
            self.assertEqual("trivial", result.kind)
            self.assertTrue(result.not_checked)

    def test_blank_gate_is_treated_as_none(self):
        with ProjectFixture() as fx:
            self.assertTrue(GE.evaluate_gate("", "worker", fx.root).passed)

    def test_command_cell_is_executed(self):
        with ProjectFixture() as fx:
            result = GE.evaluate_gate(f"{sys.executable} -m pytest tests -q",
                                      "worker", fx.root)
            self.assertEqual("command", result.kind)
            self.assertTrue(result.passed, result.reason)

    def test_failing_command_cell_fails(self):
        with ProjectFixture(test=FAILING_TEST) as fx:
            result = GE.evaluate_gate(f"{sys.executable} -m pytest tests -q",
                                      "worker", fx.root)
            self.assertFalse(result.passed)

    def test_a_crashing_predicate_does_not_read_as_a_pass(self):
        original = GE.GATE_REGISTRY["none"].predicate

        def boom(ctx):
            raise RuntimeError("detonated")

        GE.GATE_REGISTRY["none"].predicate = boom
        try:
            with ProjectFixture() as fx:
                result = GE.evaluate_gate("none", "worker", fx.root)
                self.assertFalse(result.passed)
                self.assertIn("RuntimeError", result.reason)
        finally:
            GE.GATE_REGISTRY["none"].predicate = original


# ---------------------------------------------------------------------------
# Execution safety
# ---------------------------------------------------------------------------

class TestExecutionSafety(unittest.TestCase):

    def test_gate_commands_do_not_run_through_a_shell(self):
        """A Gate cell is agent-written text. Shell metacharacters must be inert."""
        with ProjectFixture() as fx:
            canary = fx.root / "pwned.txt"
            GE.run_command(f"{sys.executable} -c pass && touch {canary}", fx.root)
            self.assertFalse(canary.exists())

    def test_source_does_not_use_shell_true(self):
        source = Path(GE.__file__).read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)

    def test_timeout_is_reported_not_raised(self):
        with ProjectFixture() as fx:
            result = GE.run_command(f"{sys.executable} -c import~time", fx.root, timeout=1)
            self.assertIn(result["exit_code"], (1, 2, 124, 127))

    def test_unrunnable_command_returns_127(self):
        with ProjectFixture() as fx:
            result = GE.run_command("definitely-not-a-real-binary-xyz --go", fx.root)
            self.assertEqual(127, result["exit_code"])


# ---------------------------------------------------------------------------
# Tree digest
# ---------------------------------------------------------------------------

class TestTreeDigest(unittest.TestCase):

    def test_identical_trees_share_a_digest(self):
        with ProjectFixture() as a, ProjectFixture() as b:
            self.assertEqual(GE.tree_digest(a.root), GE.tree_digest(b.root))

    def test_changed_content_changes_the_digest(self):
        with ProjectFixture() as fx:
            before = GE.tree_digest(fx.root)
            fx.write("src/mod.py", HONEST_SOURCE + "\n# a change\n")
            self.assertNotEqual(before, GE.tree_digest(fx.root))

    def test_renamed_file_changes_the_digest(self):
        with ProjectFixture() as fx:
            before = GE.tree_digest(fx.root)
            os.rename(fx.root / "src" / "mod.py", fx.root / "src" / "other.py")
            self.assertNotEqual(before, GE.tree_digest(fx.root))

    def test_evidence_directory_is_excluded(self):
        with ProjectFixture() as fx:
            before = GE.tree_digest(fx.root)
            GE.record_run(fx.root, "worker", "exit_0",
                          {"command": "x", "exit_code": 0, "stdout": "", "stderr": ""})
            self.assertEqual(before, GE.tree_digest(fx.root))

    def test_missing_directory_digests_without_crashing(self):
        self.assertTrue(GE.tree_digest("/nonexistent/path/xyz"))


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):

    def test_list_names_every_registered_gate(self):
        proc = run_executor("list")
        self.assertEqual(0, proc.returncode)
        for gate in GE.GATE_REGISTRY:
            self.assertIn(gate, proc.stdout)

    def test_check_exit_code_reflects_the_verdict(self):
        with ProjectFixture() as fx:
            ok = run_executor("check", "--gate", "none", "--task", "t",
                              "--base-dir", str(fx.root))
            self.assertEqual(0, ok.returncode)
            bad = run_executor("check", "--gate", "review_pass", "--task", "t",
                               "--base-dir", str(fx.root))
            self.assertEqual(1, bad.returncode)

    def test_json_output_is_parseable(self):
        with ProjectFixture() as fx:
            proc = run_executor("check", "--gate", "none", "--task", "t",
                                "--base-dir", str(fx.root), "--json")
            payload = json.loads(proc.stdout)
            self.assertEqual({"gate", "task", "kind", "passed", "reason",
                              "evidence", "not_checked", "details"}, set(payload))

    def test_attest_refuses_a_mechanical_gate(self):
        with ProjectFixture() as fx:
            proc = run_executor("attest", "--gate", "exit_0", "--task", "t",
                                "--verdict", "PASS", "--reviewer-role", "r",
                                "--worker-role", "w", "--evidence", "x.md",
                                "--summary", "a" * 50, "--base-dir", str(fx.root))
            self.assertEqual(2, proc.returncode)
            self.assertIn("not an attested gate", proc.stderr)

    def test_attest_refuses_matching_roles(self):
        with ProjectFixture() as fx:
            proc = run_executor("attest", "--gate", "review_pass", "--task", "t",
                                "--verdict", "PASS", "--reviewer-role", "dev",
                                "--worker-role", "dev", "--evidence", "x.md",
                                "--summary", "a" * 50, "--base-dir", str(fx.root))
            self.assertEqual(2, proc.returncode)

    def test_record_writes_evidence_and_reflects_exit_code(self):
        with ProjectFixture(test=FAILING_TEST) as fx:
            proc = run_executor("record", "--task", "worker", "--cmd",
                                f"{sys.executable} -m pytest tests -q",
                                "--base-dir", str(fx.root))
            self.assertEqual(1, proc.returncode)
            self.assertTrue(GE.load_runs(fx.root, "worker"))


# ---------------------------------------------------------------------------
# Validator integration
# ---------------------------------------------------------------------------

class TestValidatorIntegration(unittest.TestCase):

    def test_unknown_gate_blocks_the_write(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="looks_done"))
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(3, proc.returncode)
            self.assertIn("PENDING", dag.read_text(encoding="utf-8"))

    def test_force_status_requires_a_reason(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="review_pass"))
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--force-status",
                                 "--base-dir", str(fx.root))
            self.assertEqual(2, proc.returncode)
            self.assertIn("requires --reason", proc.stderr)

    def test_force_status_writes_the_override_into_the_dag(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="review_pass"))
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--force-status", "--reason",
                                 "reviewer unavailable; tracked in ticket 41",
                                 "--base-dir", str(fx.root))
            self.assertEqual(0, proc.returncode, proc.stderr)
            text = dag.read_text(encoding="utf-8")
            self.assertIn("| PASSED |", text)
            self.assertIn("Gate Overrides", text)
            self.assertIn("ticket 41", text)

    def test_gate_failure_leaves_the_file_untouched(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="review_pass"))
            before = dag.read_text(encoding="utf-8")
            run_validator(str(dag), "--set-status", "worker=PASSED",
                          "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(before, dag.read_text(encoding="utf-8"))

    def test_status_for_an_undeclared_task_is_refused(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="none"))
            proc = run_validator(str(dag), "--set-status", "ghost=PASSED",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(3, proc.returncode)
            self.assertIn("not declared", proc.stderr)

    def test_none_gate_still_allows_progress(self):
        with ProjectFixture() as fx:
            dag = fx.write("DAG.md", DAG_TEMPLATE.format(gate="none"))
            proc = run_validator(str(dag), "--set-status", "worker=PASSED",
                                 "--update-file", "--base-dir", str(fx.root))
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertIn("| PASSED |", dag.read_text(encoding="utf-8"))


class TestFixturesStayClean(unittest.TestCase):
    """The corpus is an input. Nothing in this suite may write to it.

    Added after the first version of these tests pointed gates straight at
    ``fixtures/known_good`` and left four evidence files inside the committed
    corpus.
    """

    def test_no_gate_artifacts_are_left_in_the_committed_fixtures(self):
        for name in ("known_fake", "known_good"):
            agents = SKILL_DIR / "fixtures" / name / GE.AGENTS_DIRNAME
            self.assertFalse(
                agents.exists(),
                f"{agents} exists: a test wrote gate evidence into the fixture "
                f"corpus. Use FixtureCopy instead of the committed path.")


if __name__ == "__main__":
    unittest.main()
