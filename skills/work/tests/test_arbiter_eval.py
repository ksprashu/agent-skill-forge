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

"""Tests for skills/work/scripts/arbiter_eval.py.

The headline test is ``TestAntiCorrelationRegression``. On 2026-09-23 the
previous version of this script scored a content-free proposal 95 and a
rigorous one 40, and recommended the content-free one. Those two documents are
committed as fixtures; every signal that discriminates between them must now
point the right way, and no total score may be emitted at all.
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
DESIGNS = SKILL_DIR / "fixtures" / "designs"
sys.path.insert(0, str(SCRIPTS_DIR))

from arbiter_eval import (  # noqa: E402
    DESIGN_SIGNALS,
    VERDICT_JUDGEMENT_REQUIRED,
    collect_design_evidence,
    compare_candidates,
    compare_design_evidence,
    count_code_metrics,
    measure_candidate,
    render_report,
    run_command,
    _signal_values,
)

SCRIPT = str(SCRIPTS_DIR / "arbiter_eval.py")
HOLLOW = DESIGNS / "hollow_proposal.md"
SUBSTANTIVE = DESIGNS / "substantive_proposal.md"


def run_cli(*args, timeout=120):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
    )


def write_doc(tmp: str, name: str, body: str) -> str:
    path = Path(tmp) / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# The regression this rewrite exists for
# ---------------------------------------------------------------------------

class TestAntiCorrelationRegression(unittest.TestCase):
    """W-03: the old scorer preferred the hollow document 95 to 40."""

    @classmethod
    def setUpClass(cls):
        cls.sub = collect_design_evidence("Substantive", str(SUBSTANTIVE))
        cls.hol = collect_design_evidence("Hollow", str(HOLLOW))
        cls.s_sub = _signal_values(cls.sub)
        cls.s_hol = _signal_values(cls.hol)

    def test_every_directional_signal_favours_the_substantive_proposal(self):
        wrong = []
        for label, key, higher_better in DESIGN_SIGNALS:
            if higher_better is None:
                continue
            sub, hol = self.s_sub[key], self.s_hol[key]
            better = sub > hol if higher_better else sub < hol
            if not (better or sub == hol):
                wrong.append(f"{label}: substantive={sub} hollow={hol}")
        self.assertEqual([], wrong, f"signals point at the hollow proposal: {wrong}")

    def test_the_hollow_proposal_wins_only_on_heading_count(self):
        """Headings were 30 of the old 100 points. They are now undirected."""
        self.assertGreater(self.s_hol["n_headings"], self.s_sub["n_headings"])
        directions = {key: hb for _label, key, hb in DESIGN_SIGNALS}
        self.assertIsNone(directions["n_headings"])

    def test_placeholder_fences_are_not_counted_as_contract_evidence(self):
        """```TBD``` scored 10 of 25 on the Contracts axis in the old version."""
        self.assertGreaterEqual(self.s_hol["n_placeholder"], 4)
        self.assertEqual(self.s_hol["n_substantive"], 0)
        self.assertGreater(self.s_sub["n_substantive"], 0)

    def test_measured_claims_separate_the_two_documents(self):
        self.assertGreaterEqual(self.s_sub["n_measured"], 5)
        self.assertEqual(self.s_hol["n_measured"], 0)

    def test_hedging_is_detected_in_the_hollow_proposal(self):
        self.assertGreater(self.s_hol["n_hedges"], 5)
        self.assertEqual(self.s_sub["n_hedges"], 0)


class TestNoScoringSurvives(unittest.TestCase):
    """S9: a script may count; it may not judge."""

    BANNED = ("total_score", '"total"', "pts |", "Decisive lead", "SELECT_ALPHA (", "SELECT_BETA (")

    def test_design_evidence_contains_no_score_field(self):
        evidence = collect_design_evidence("x", str(SUBSTANTIVE))
        self.assertNotIn("scores", evidence)
        self.assertNotIn("total", evidence)
        for value in evidence.values():
            self.assertNotIsInstance(value, float)

    def test_design_report_emits_no_total_and_no_ranking(self):
        data = compare_design_evidence(
            collect_design_evidence("A", str(SUBSTANTIVE)),
            collect_design_evidence("B", str(HOLLOW)),
        )
        report = render_report(data)
        for banned in self.BANNED:
            self.assertNotIn(banned, report, f"scoring vocabulary returned: {banned}")
        self.assertEqual(data["verdict"], VERDICT_JUDGEMENT_REQUIRED)

    def test_the_source_file_no_longer_contains_a_points_table(self):
        source = Path(SCRIPT).read_text(encoding="utf-8")
        self.assertNotIn("alpha_maint = 15.0", source)
        self.assertNotIn("Max 15 pts", source)
        self.assertNotIn("30 pts", source)

    def test_report_states_what_it_cannot_tell_you(self):
        data = compare_design_evidence(
            collect_design_evidence("A", str(SUBSTANTIVE)),
            collect_design_evidence("B", str(HOLLOW)),
        )
        report = render_report(data)
        self.assertIn("cannot tell you", report)
        self.assertIn("Questions the Arbiter must answer", report)


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------

class TestCodeBlockClassification(unittest.TestCase):
    def _blocks(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            return collect_design_evidence("x", write_doc(tmp, "d.md", body))["code_blocks"]

    def test_tbd_fence_is_a_placeholder(self):
        self.assertEqual(1, self._blocks("# D\n\n```\nTBD\n```\n")["placeholder"])

    def test_empty_fence_is_a_placeholder(self):
        self.assertEqual(1, self._blocks("# D\n\n```\n\n```\n")["placeholder"])

    def test_two_line_fence_is_trivial(self):
        self.assertEqual(1, self._blocks("# D\n\n```mermaid\nflowchart TD\n    A --> B\n```\n")["trivial"])

    def test_real_schema_is_substantive(self):
        body = """
        # D

        ```sql
        CREATE TABLE jobs (
          id bigserial PRIMARY KEY,
          state text NOT NULL,
          payload jsonb NOT NULL
        );
        ```
        """
        self.assertEqual(1, self._blocks(body)["substantive"])

    def test_unterminated_fence_is_reported_not_swallowed(self):
        self.assertEqual(1, self._blocks("# D\n\n```python\nx = 1\ny = 2\nz = 3\n")["unterminated"])


class TestMeasuredClaims(unittest.TestCase):
    def _count(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            return len(collect_design_evidence("x", write_doc(tmp, "d.md", body))["measured_claims"])

    def test_latency_with_units_counts(self):
        self.assertEqual(1, self._count("p99 claim latency is 11 ms under load\n"))

    def test_throughput_counts(self):
        self.assertEqual(1, self._count("Sustains 4,100 jobs/sec on the staging box\n"))

    def test_percentage_counts(self):
        self.assertEqual(1, self._count("Cuts allocation by 40% in the hot path\n"))

    def test_bare_prose_does_not_count(self):
        self.assertEqual(0, self._count("The system is fast and scales well under load\n"))

    def test_a_bare_number_without_a_unit_does_not_count(self):
        self.assertEqual(0, self._count("There are 3 components in the diagram above\n"))


class TestNamedAlternatives(unittest.TestCase):
    def _count(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            return len(collect_design_evidence("x", write_doc(tmp, "d.md", body))["named_alternatives"])

    def test_rejection_with_a_reason_counts(self):
        self.assertEqual(1, self._count("We rejected Redis Streams because of the second source of truth\n"))

    def test_migration_path_counts(self):
        self.assertEqual(1, self._count("The migration path is to move only the claim path\n"))

    def test_generic_prose_does_not_count(self):
        self.assertEqual(0, self._count("The design is modular and extensible\n"))


class TestMissingFiles(unittest.TestCase):
    def test_missing_proposal_is_recorded_not_scored_zero(self):
        evidence = collect_design_evidence("Gone", "/nonexistent/proposal.md")
        self.assertFalse(evidence["exists"])
        self.assertNotIn("scores", evidence)

    def test_comparison_names_the_missing_proposal(self):
        data = compare_design_evidence(
            collect_design_evidence("A", str(SUBSTANTIVE)),
            collect_design_evidence("B", "/nonexistent/x.md"),
        )
        self.assertEqual(["B"], data["missing_proposals"])
        self.assertIn("MISSING", render_report(data))

    def test_cli_exits_2_when_a_proposal_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--design-alpha", str(SUBSTANTIVE), "--design-beta", "/nope.md",
                             "--output-scorecard", str(Path(tmp) / "r.md"), "-q")
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# Implementation tournament
# ---------------------------------------------------------------------------

class TestImplementationMeasurement(unittest.TestCase):
    PASS = f"{sys.executable} -c pass"
    FAIL = f'{sys.executable} -c "import sys; sys.exit(1)"'

    def test_failing_candidate_loses_and_the_basis_is_the_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            alpha = measure_candidate("A", self.FAIL, None, tmp)
            beta = measure_candidate("B", self.PASS, None, tmp)
        data = compare_candidates(alpha, beta)
        self.assertEqual(data["verdict"], "SELECT_BETA")
        self.assertIn("exited 1", data["basis"])

    def test_two_passing_candidates_are_handed_back_for_judgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            alpha = measure_candidate("A", self.PASS, None, tmp)
            beta = measure_candidate("B", self.PASS, None, tmp)
        self.assertEqual(compare_candidates(alpha, beta)["verdict"], VERDICT_JUDGEMENT_REQUIRED)

    def test_two_failing_candidates_reject_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            alpha = measure_candidate("A", self.FAIL, None, tmp)
            beta = measure_candidate("B", self.FAIL, None, tmp)
        self.assertEqual(compare_candidates(alpha, beta)["verdict"], "BOTH_REJECTED")

    def test_unmeasured_correctness_is_stated_not_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            alpha = measure_candidate("A", None, None, tmp)
            beta = measure_candidate("B", None, None, tmp)
        data = compare_candidates(alpha, beta)
        self.assertIsNone(alpha["test_passed"])
        self.assertIn("unmeasured", data["basis"])

    def test_report_names_the_removed_constant_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = compare_candidates(
                measure_candidate("A", None, None, tmp),
                measure_candidate("B", None, None, tmp))
        report = render_report(data)
        self.assertIn("Maintainability", report)
        self.assertIn("no mechanical proxy", report)
        self.assertNotIn("15 pts", report)


class TestCodeMetrics(unittest.TestCase):
    def test_metrics_are_measured_from_real_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("x = 1\n" * 200, encoding="utf-8")
            (Path(tmp) / "b.py").write_text("y = 2\n" * 10, encoding="utf-8")
            metrics = count_code_metrics(tmp)
        self.assertEqual(metrics["file_count"], 2)
        self.assertEqual(metrics["total_lines"], 210)
        self.assertEqual(metrics["files_over_150_lines"], 1)
        self.assertEqual(metrics["max_lines_in_a_file"], 200)

    def test_vendored_directories_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "node_modules").mkdir()
            (Path(tmp) / "node_modules" / "dep.js").write_text("a\n" * 500, encoding="utf-8")
            (Path(tmp) / "a.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(count_code_metrics(tmp)["file_count"], 1)

    def test_absent_directory_yields_zeros_not_an_exception(self):
        self.assertEqual(count_code_metrics("/nonexistent/dir")["file_count"], 0)


# ---------------------------------------------------------------------------
# Safety and CLI contract
# ---------------------------------------------------------------------------

class TestExecutionSafety(unittest.TestCase):
    def test_run_command_does_not_use_a_shell(self):
        """W-11: commands come from agent-authored Markdown."""
        with tempfile.TemporaryDirectory() as tmp:
            canary = Path(tmp) / "pwned.txt"
            run_command(f'{sys.executable} -c pass ; touch {canary}', cwd=tmp)
            self.assertFalse(canary.exists(), "shell metacharacter executed")

    def test_unknown_binary_is_reported_not_raised(self):
        code, _out, err, _dur = run_command("definitely-not-a-real-binary-xyz")
        self.assertEqual(code, 127)
        self.assertIn("could not execute", err)

    def test_empty_command_is_an_invocation_error(self):
        self.assertEqual(2, run_command("   ")[0])

    def test_timeout_is_enforced(self):
        code, _out, err, _dur = run_command(
            f'{sys.executable} -c "import time; time.sleep(30)"', timeout=1)
        self.assertEqual(code, 124)
        self.assertIn("timed out", err)


class TestCliContract(unittest.TestCase):
    def test_json_mode_emits_parseable_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--design-alpha", str(SUBSTANTIVE), "--design-beta", str(HOLLOW),
                             "--json", "--output-scorecard", str(Path(tmp) / "r.md"))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["type"], "design")
        self.assertEqual(payload["verdict"], VERDICT_JUDGEMENT_REQUIRED)
        self.assertIn("signals", payload)

    def test_report_is_written_to_the_requested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "evidence.md"
            run_cli("--design-alpha", str(SUBSTANTIVE), "--design-beta", str(HOLLOW),
                    "--output-scorecard", str(out), "-q")
            self.assertTrue(out.exists())
            self.assertIn("Evidence Report", out.read_text(encoding="utf-8"))

    def test_reports_for_the_two_fixtures_differ(self):
        """Differentiation (T1)."""
        swapped = compare_design_evidence(
            collect_design_evidence("A", str(HOLLOW)),
            collect_design_evidence("B", str(SUBSTANTIVE)))
        normal = compare_design_evidence(
            collect_design_evidence("A", str(SUBSTANTIVE)),
            collect_design_evidence("B", str(HOLLOW)))
        self.assertNotEqual(render_report(swapped), render_report(normal))


if __name__ == "__main__":
    unittest.main()
