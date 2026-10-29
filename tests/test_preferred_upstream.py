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

"""Domain skills that come from addyosmani/agent-skills are fetched, not vendored.

The bug these were written against: ten of the preferred domain skills were
full copies of addyosmani/agent-skills sitting in ``preferred/``, while the
README said "nothing is vendored, nothing is forked". The copies had drifted
from upstream and nothing pinned which upstream commit they came from.

They are now lock entries in ``config/upstream.lock.json`` and materialise into
``.upstream/`` like the spine. Two properties matter:

* a domain cluster name resolves either to a local ``preferred/`` skill or to a
  lock entry, never to nothing and never to both;
* when the fetch has not run, the installers say so and carry on. A missing
  ``.upstream/`` must not crash discovery or read as a typo.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK = REPO_ROOT / "config" / "upstream.lock.json"
PREFERRED = REPO_ROOT / "preferred"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_upstream  # noqa: E402
import sync_skills  # noqa: E402

ADDY_DOMAIN_SKILLS = (
    "api-and-interface-design",
    "browser-testing-with-devtools",
    "ci-cd-and-automation",
    "context-engineering",
    "debugging-and-error-recovery",
    "deprecation-and-migration",
    "frontend-ui-engineering",
    "git-workflow-and-versioning",
    "observability-and-instrumentation",
    "performance-optimization",
)

SHA = re.compile(r"^[0-9a-f]{40}$")


def lock_skills() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))["skills"]


def domain_names() -> list[str]:
    return [n for c in sync_skills.DOMAIN_CLUSTERS.values() for n in c["skills"]]


class TestNothingIsVendored(unittest.TestCase):
    def test_each_addy_skill_is_a_pinned_lock_entry(self):
        lock = lock_skills()
        for name in ADDY_DOMAIN_SKILLS:
            with self.subTest(name=name):
                self.assertIn(name, lock)
                entry = lock[name]
                self.assertEqual(entry["repo"], "addyosmani/agent-skills")
                self.assertEqual(entry["path"], f"skills/{name}")
                self.assertRegex(entry["ref"], SHA)
                self.assertEqual(entry["license"], "MIT")

    def test_no_preferred_directory_shadows_a_lock_entry(self):
        lock = lock_skills()
        vendored = sorted(
            p.name for p in PREFERRED.iterdir() if p.is_dir() and p.name in lock
        )
        self.assertEqual(vendored, [], "these are fetched; delete the local copies")

    def test_every_domain_cluster_name_resolves_somewhere(self):
        lock = lock_skills()
        for name in domain_names():
            with self.subTest(name=name):
                local = (PREFERRED / name / "SKILL.md").is_file()
                self.assertTrue(
                    local or name in lock,
                    f"{name} is in DOMAIN_CLUSTERS but is neither in preferred/ nor in the lock",
                )

    def test_dropped_skills_are_gone_from_the_clusters(self):
        for name in ("benchmark-harness", "security-and-hardening"):
            with self.subTest(name=name):
                self.assertNotIn(name, domain_names())
                self.assertFalse((PREFERRED / name).exists())


class TestUpstreamDiscovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.upstream = Path(self._tmp.name) / ".upstream"

    def _patch(self):
        return mock.patch.object(sync_skills, "UPSTREAM_SKILLS_DIR", str(self.upstream))

    def test_a_materialised_domain_skill_is_discovered_as_upstream(self):
        skill = self.upstream / "performance-optimization"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: performance-optimization\n---\n")
        with self._patch():
            found = sync_skills.discover_all_skills()
        self.assertEqual(found["performance-optimization"]["type"], "upstream")
        self.assertEqual(found["performance-optimization"]["path"], str(skill))

    def test_no_upstream_directory_does_not_crash_discovery(self):
        with self._patch():
            found = sync_skills.discover_all_skills()
        self.assertNotIn("performance-optimization", found)
        self.assertIn("agent-security-posture", found)

    def test_bootstrap_names_the_fetch_step_for_an_unfetched_lock_entry(self):
        project = Path(self._tmp.name) / "project"
        project.mkdir()
        out = io.StringIO()
        with self._patch(), contextlib.redirect_stdout(out):
            sync_skills.bootstrap_project_skills(str(project), ["performance-optimization"])
        text = out.getvalue()
        self.assertIn("NOT FETCHED", text)
        self.assertIn("fetch_upstream.py", text)
        self.assertFalse((project / ".gemini").exists())

    def test_a_real_typo_still_gets_the_generic_message(self):
        project = Path(self._tmp.name) / "project"
        project.mkdir()
        out = io.StringIO()
        with self._patch(), contextlib.redirect_stdout(out):
            sync_skills.bootstrap_project_skills(str(project), ["performance-optimisation"])
        self.assertIn("NOT FOUND LOCALLY", out.getvalue())


class TestProvenanceWithoutOverlay(unittest.TestCase):
    """The domain entries carry no overlay, so there is no forge section to point at."""

    def _materialise(self, entry):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        skill = Path(tmp.name)
        (skill / "SKILL.md").write_text("---\nname: upstream-name\n---\n\n# Body\n")
        fetch_upstream.apply_overlay(str(skill), "performance-optimization", entry)
        return (skill / "SKILL.md").read_text()

    def test_no_overlay_means_no_claim_of_a_forge_section(self):
        entry = dict(lock_skills()["performance-optimization"])
        text = self._materialise(entry)
        self.assertNotIn(fetch_upstream.OVERLAY_HEADING, text)
        self.assertIn("Provenance", text)
        self.assertIn(entry["ref"], text)

    def test_an_overlay_still_gets_the_boundary_explanation(self):
        entry = dict(lock_skills()["doubt"])
        text = self._materialise(entry)
        self.assertIn(fetch_upstream.OVERLAY_HEADING, text)


if __name__ == "__main__":
    unittest.main()
