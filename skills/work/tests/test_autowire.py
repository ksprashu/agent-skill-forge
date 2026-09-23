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

"""Tests for the domain skill autowiring resolver.

The load-bearing tests here are ``TestMatrixMatchesDocumentation`` and
``TestMatrixResolvesOnDisk``: the failure this module exists to prevent is a
dispatch brief telling a subagent to read a skill that was renamed two commits
ago, and a reference document describing a mapping the code does not implement.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = Path(__file__).resolve().parents[1] / "references" / "domain_autowiring.md"

sys.path.insert(0, str(SCRIPTS_DIR))

import autowire  # noqa: E402


def run_cli(args, cwd=REPO_ROOT):
    """Invoke the script the way the Orchestrator does."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "autowire.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_skill(root: Path, namespace: str, name: str, description: str) -> Path:
    directory = root / namespace / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            description: {description}
            ---

            # {name}
            """
        ),
        encoding="utf-8",
    )
    return directory


class TestMatrixMatchesDocumentation(unittest.TestCase):
    """The reference table and DOMAIN_MATRIX must say the same thing."""

    @staticmethod
    def parse_doc_rows():
        text = DOC_PATH.read_text(encoding="utf-8")
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 4 or cells[0].startswith("Technical Domain"):
                continue
            if set(cells[0]) <= {"-", ":"}:
                continue
            label = cells[0].strip("*").strip()
            skills = tuple(re.findall(r"`([^`]+)`", cells[1]))
            roles = tuple(r.strip() for r in cells[2].split(",") if r.strip())
            rows.append((label, skills, roles, cells[3]))
        return rows

    def test_documentation_table_is_parseable(self):
        rows = self.parse_doc_rows()
        self.assertEqual(len(rows), len(autowire.DOMAIN_MATRIX))

    def test_every_documented_row_exists_in_code(self):
        by_label = {d.label: d for d in autowire.DOMAIN_MATRIX}
        for label, skills, roles, instructions in self.parse_doc_rows():
            with self.subTest(domain=label):
                self.assertIn(label, by_label, f"{label} documented but not implemented")
                domain = by_label[label]
                self.assertEqual(domain.skills, skills)
                self.assertEqual(domain.roles, roles)
                self.assertEqual(domain.instructions, instructions)

    def test_every_code_row_exists_in_documentation(self):
        documented = {row[0] for row in self.parse_doc_rows()}
        for domain in autowire.DOMAIN_MATRIX:
            with self.subTest(domain=domain.label):
                self.assertIn(domain.label, documented)

    def test_documentation_does_not_dispatch_on_flash(self):
        # The committee and the workers run on the same model as the code they
        # are checking; a flash example invites the opposite.
        self.assertNotIn('"Model": "flash"', DOC_PATH.read_text(encoding="utf-8"))


class TestMatrixResolvesOnDisk(unittest.TestCase):
    def test_check_passes_against_this_repository(self):
        problems = autowire.check_matrix(REPO_ROOT)
        self.assertEqual(problems, [], f"unresolved matrix entries: {problems}")

    def test_check_cli_exits_zero(self):
        code, out, err = run_cli(["--check"])
        self.assertEqual(code, 0, err)
        self.assertIn("matrix ok", out)

    def test_check_fails_when_a_skill_is_missing(self):
        ghost = autowire.Domain(
            label="Ghost",
            skills=("preferred/does-not-exist",),
            roles=("Worker",),
            instructions="",
            triggers=("ghost",),
        )
        problems = autowire.check_matrix(REPO_ROOT, matrix=(ghost,))
        self.assertTrue(any("does-not-exist" in p for p in problems))

    def test_check_fails_on_a_domain_with_no_triggers(self):
        dead = autowire.Domain(
            label="Unreachable",
            skills=("skills/test",),
            roles=("Worker",),
            instructions="",
            triggers=(),
        )
        problems = autowire.check_matrix(REPO_ROOT, matrix=(dead,))
        self.assertTrue(any("never match" in p for p in problems))

    def test_check_fails_on_a_domain_with_no_skills(self):
        empty = autowire.Domain(
            label="Empty",
            skills=(),
            roles=("Worker",),
            instructions="",
            triggers=("empty",),
        )
        problems = autowire.check_matrix(REPO_ROOT, matrix=(empty,))
        self.assertTrue(any("no skill" in p for p in problems))

    def test_check_cli_exits_one_on_an_empty_tree(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(["--check", "--repo-root", tmp])
            self.assertEqual(code, 1)
            self.assertIn("does not exist", err)


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_discovers_skills_from_both_roots(self):
        make_skill(self.root, "skills", "alpha", "Alpha skill.")
        make_skill(self.root, "preferred", "beta", "Beta skill.")
        paths = {e.relpath for e in autowire.discover_skills(self.root)}
        self.assertEqual(paths, {"skills/alpha", "preferred/beta"})

    def test_ignores_directories_without_a_skill_file(self):
        (self.root / "skills" / "not-a-skill").mkdir(parents=True)
        self.assertEqual(autowire.discover_skills(self.root), [])

    def test_reads_name_and_description_from_frontmatter(self):
        make_skill(self.root, "skills", "gamma", "Does a specific thing.")
        entry = autowire.discover_skills(self.root)[0]
        self.assertEqual(entry.name, "gamma")
        self.assertEqual(entry.description, "Does a specific thing.")

    def test_falls_back_to_the_directory_name_without_frontmatter(self):
        directory = self.root / "skills" / "bare"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("# Bare\n", encoding="utf-8")
        entry = autowire.discover_skills(self.root)[0]
        self.assertEqual(entry.name, "bare")
        self.assertEqual(entry.description, "")

    def test_folds_in_catalog_tags(self):
        make_skill(self.root, "preferred", "tagged", "Tagged skill.")
        (self.root / "preferred" / "catalog.json").write_text(
            json.dumps({"skills": [{"name": "tagged", "tags": ["one", "TWO"]}]}),
            encoding="utf-8",
        )
        entry = autowire.discover_skills(self.root)[0]
        self.assertEqual(entry.tags, ("one", "two"))

    def test_a_corrupt_catalog_does_not_break_discovery(self):
        make_skill(self.root, "preferred", "tagged", "Tagged skill.")
        (self.root / "preferred" / "catalog.json").write_text("{not json", encoding="utf-8")
        entries = autowire.discover_skills(self.root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].tags, ())

    def test_discovery_is_sorted_and_therefore_deterministic(self):
        for name in ("zulu", "alpha", "mike"):
            make_skill(self.root, "skills", name, "x")
        names = [e.name for e in autowire.discover_skills(self.root)]
        self.assertEqual(names, sorted(names))

    def test_discovers_the_real_repository_catalog(self):
        entries = autowire.discover_skills(REPO_ROOT)
        paths = {e.relpath for e in entries}
        self.assertIn("skills/work", paths)
        self.assertIn("preferred/security-and-hardening", paths)


class TestFrontmatterParsing(unittest.TestCase):
    def test_returns_empty_without_a_frontmatter_block(self):
        self.assertEqual(autowire.parse_frontmatter("# Just a heading\n"), {})

    def test_stops_at_the_closing_delimiter(self):
        text = "---\nname: a\n---\nname: not-this\n"
        self.assertEqual(autowire.parse_frontmatter(text)["name"], "a")

    def test_strips_surrounding_quotes(self):
        text = "---\ndescription: \"quoted value\"\n---\n"
        self.assertEqual(autowire.parse_frontmatter(text)["description"], "quoted value")

    def test_ignores_nested_keys(self):
        text = "---\nname: a\nmetadata:\n  nested: b\n---\n"
        fields = autowire.parse_frontmatter(text)
        self.assertNotIn("nested", fields)


class TestMatching(unittest.TestCase):
    def test_matches_an_observability_task(self):
        matches = autowire.match_domains("Add structured logging and traces")
        self.assertEqual(matches[0].domain.label, "Observability & Logging")

    def test_reports_the_terms_that_caused_the_match(self):
        matches = autowire.match_domains("Fix the SQL migration schema")
        terms = set(matches[0].terms)
        self.assertTrue({"sql", "migration", "schema"} <= terms)

    def test_returns_nothing_for_an_unrelated_task(self):
        self.assertEqual(autowire.match_domains("Rename the mascot"), [])

    def test_ranks_the_domain_with_more_hits_first(self):
        task = "Profile the slow hot path, measure p99 latency, and log the result"
        labels = [m.domain.label for m in autowire.match_domains(task)]
        self.assertEqual(labels[0], "Performance & Benchmarking")

    def test_ordering_is_stable_across_runs(self):
        task = "Review the test coverage of the deployment pipeline"
        first = [m.domain.label for m in autowire.match_domains(task)]
        second = [m.domain.label for m in autowire.match_domains(task)]
        self.assertEqual(first, second)

    def test_role_filter_narrows_the_result(self):
        task = "Harden token comparison and add a regression test"
        auditor = {m.domain.label for m in autowire.match_domains(task, role="Auditor")}
        self.assertIn("Security & RBAC", auditor)
        self.assertNotIn("Testing & TDD", auditor)

    def test_role_filter_is_case_insensitive(self):
        task = "Harden the RBAC layer"
        lower = autowire.match_domains(task, role="auditor")
        upper = autowire.match_domains(task, role="AUDITOR")
        self.assertEqual([m.domain.label for m in lower], [m.domain.label for m in upper])

    def test_an_unknown_role_matches_nothing(self):
        self.assertEqual(autowire.match_domains("Add logging", role="Sentinel"), [])

    def test_a_short_token_does_not_match_inside_a_word(self):
        # "ci" must not fire on "specific" or "decision".
        labels = [m.domain.label for m in autowire.match_domains("A specific decision")]
        self.assertNotIn("CI/CD & Workflows", labels)

    def test_a_multiword_trigger_needs_the_whole_phrase(self):
        self.assertEqual(autowire.match_domains("check the memory"), [])
        labels = [m.domain.label for m in autowire.match_domains("plug the memory leak")]
        self.assertIn("Performance & Benchmarking", labels)

    def test_plural_and_singular_are_the_same_trigger(self):
        singular = autowire.match_domains("emit a metric")
        plural = autowire.match_domains("emit metrics")
        self.assertEqual(
            [m.domain.label for m in singular], [m.domain.label for m in plural]
        )

    def test_stopwords_alone_match_nothing(self):
        self.assertEqual(autowire.match_domains("Build and create the thing"), [])

    def test_punctuation_does_not_block_a_match(self):
        labels = [m.domain.label for m in autowire.match_domains("expose /api/health!")]
        self.assertIn("Observability & Logging", labels)


class TestResolution(unittest.TestCase):
    def test_resolution_attaches_the_discovered_entry(self):
        matches = autowire.autowire("add structured logging", REPO_ROOT)
        entry = matches[0].resolved[0]
        self.assertEqual(entry.relpath, "preferred/observability-and-instrumentation")
        self.assertTrue(entry.description)

    def test_a_missing_skill_is_reported_not_silently_dropped(self):
        ghost = autowire.Domain(
            label="Ghost",
            skills=("preferred/vanished",),
            roles=("Worker",),
            instructions="",
            triggers=("ghost",),
        )
        matches = autowire.resolve(
            autowire.match_domains("a ghost appears", matrix=(ghost,)),
            autowire.discover_skills(REPO_ROOT),
        )
        self.assertEqual(matches[0].missing, ["preferred/vanished"])
        self.assertEqual(matches[0].resolved, [])

    def test_limit_caps_the_number_of_domains(self):
        task = "Review the slow deployment pipeline logging and test coverage"
        self.assertEqual(len(autowire.autowire(task, REPO_ROOT, limit=2)), 2)


class TestRendering(unittest.TestCase):
    def test_brief_lists_a_full_skill_file_path(self):
        brief = autowire.render_brief(autowire.autowire("add tracing", REPO_ROOT))
        self.assertIn("preferred/observability-and-instrumentation/SKILL.md", brief)

    def test_brief_states_that_matches_are_not_a_judgement(self):
        brief = autowire.render_brief(autowire.autowire("add tracing", REPO_ROOT))
        self.assertIn("not a judgement", brief)

    def test_brief_on_no_match_points_at_the_knowledge_catalog(self):
        brief = autowire.render_brief([])
        self.assertIn(".gemini/knowledge/", brief)

    def test_brief_flags_a_missing_skill_loudly(self):
        ghost = autowire.Domain(
            label="Ghost",
            skills=("preferred/vanished",),
            roles=("Worker",),
            instructions="",
            triggers=("ghost",),
        )
        matches = autowire.resolve(
            autowire.match_domains("a ghost appears", matrix=(ghost,)), []
        )
        self.assertIn("MISSING: preferred/vanished", autowire.render_brief(matches))

    def test_listing_marks_resolution_status(self):
        listing = autowire.render_listing(
            autowire.discover_skills(REPO_ROOT), autowire.DOMAIN_MATRIX
        )
        self.assertIn("[ok] skills/test", listing)
        self.assertNotIn("[MISSING]", listing)


class TestCli(unittest.TestCase):
    def test_task_emits_a_brief(self):
        code, out, err = run_cli(["--task", "add structured logging"])
        self.assertEqual(code, 0, err)
        self.assertIn("Domain Skills", out)

    def test_json_output_is_valid_json(self):
        code, out, err = run_cli(["--task", "harden the RBAC layer", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["matches"][0]["domain"], "Security & RBAC")

    def test_list_prints_every_domain(self):
        code, out, err = run_cli(["--list"])
        self.assertEqual(code, 0, err)
        for domain in autowire.DOMAIN_MATRIX:
            self.assertIn(domain.label, out)

    def test_missing_task_is_an_invocation_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("--task is required", err)

    def test_a_bad_repo_root_is_an_invocation_error(self):
        code, _, err = run_cli(["--task", "x", "--repo-root", "/nonexistent/path/xyz"])
        self.assertEqual(code, 2)
        self.assertIn("not a directory", err)

    def test_role_flag_reaches_the_output(self):
        code, out, err = run_cli(["--task", "add structured logging", "--role", "Worker"])
        self.assertEqual(code, 0, err)
        self.assertIn("for role Worker", out)


class TestSourceDiscipline(unittest.TestCase):
    """Repo-wide invariants this script must not be the one to break."""

    SOURCE = (SCRIPTS_DIR / "autowire.py").read_text(encoding="utf-8")

    def test_no_shell_true(self):
        self.assertNotIn("shell=True", self.SOURCE)

    def test_no_third_party_imports(self):
        for line in self.SOURCE.splitlines():
            if line.startswith(("import ", "from ")):
                module = line.split()[1].split(".")[0]
                self.assertIn(
                    module,
                    {
                        "__future__", "argparse", "dataclasses", "json", "pathlib",
                        "re", "sys", "typing",
                    },
                    f"non-stdlib import: {line}",
                )

    def test_the_script_does_not_score_or_rank_by_quality(self):
        # Ordering by hit count is a count. Any word implying a quality verdict
        # here would mean the script had started making the judgement it hands
        # to the agent.
        for banned in ("score", "grade", "best_skill", "winner"):
            self.assertNotIn(banned, self.SOURCE.lower())


if __name__ == "__main__":
    unittest.main()
