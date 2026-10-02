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

"""Tests for the dispatch-brief grounding lint in scripts/validate_skills.py.

W-07 and W-08 were closed in prose, and the remediation log said every brief
named ``.gemini/knowledge/``. When the lint first ran, nine of fourteen did not.
These tests are what keeps the next edit from quietly undoing the fix.
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_skills import (  # noqa: E402
    BRIEF_CONTRACTS,
    KNOWLEDGE_GROUNDING,
    iter_dispatch_briefs,
    validate_dispatch_briefs,
)

GROUNDED = f"Grounding: read {KNOWLEDGE_GROUNDING} first.\n"


def fence(*payloads, indent=""):
    body = json.dumps({"Subagents": list(payloads)}, indent=2, ensure_ascii=False)
    block = f"```json\n{body}\n```\n"
    return textwrap.indent(block, indent) if indent else block


class BriefCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for skill in ("review", "unslop", "test", "catalog"):
            self.write(f"skills/{skill}/SKILL.md", "# skill\n")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def lint(self, text, rel="skills/work/SKILL.md"):
        self.write(rel, text)
        return validate_dispatch_briefs(str(self.root))


class TestCompliantBriefsPass(BriefCase):
    """The positive control. A lint that flags everything passes every test below."""

    def test_a_grounded_code_reviewer_citing_its_skills_passes(self):
        brief = {"Role": "5-Axis Code Reviewer",
                 "Prompt": GROUNDED + "Read skills/review/SKILL.md and skills/unslop/SKILL.md."}
        self.assertEqual([], self.lint(fence(brief)))

    def test_an_exempt_role_needs_no_grounding(self):
        brief = {"Role": "Victory Auditor", "Prompt": "Run the gate cold."}
        self.assertEqual([], self.lint(fence(brief)))

    def test_the_heartbeat_tick_has_no_role_and_needs_none(self):
        payload = {"Prompt": "Heartbeat tick: inspect subagent progress."}
        self.assertEqual([], self.lint(f"```json\n{json.dumps(payload)}\n```\n"))

    def test_other_fenced_languages_are_not_payloads(self):
        self.assertEqual([], self.lint('```bash\necho \'{"Role": "Nobody", "Prompt": "x"}\'\n```\n'))


class TestGroundingIsRequired(BriefCase):
    def test_a_judging_role_without_the_knowledge_path_fails(self):
        brief = {"Role": "Acceptance Reviewer", "Prompt": "Audit SPEC.md."}
        errors = self.lint(fence(brief))
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Acceptance Reviewer is not pointed at .gemini/knowledge/ (W-07)", errors[0])

    def test_a_reviewer_that_drops_a_sibling_skill_fails(self):
        brief = {"Role": "5-Axis Code Reviewer",
                 "Prompt": GROUNDED + "Read skills/review/SKILL.md."}
        errors = self.lint(fence(brief))
        self.assertEqual(1, len(errors), errors)
        self.assertIn("does not cite skills/unslop/SKILL.md (W-08)", errors[0])

    def test_the_error_names_the_file_and_line_of_the_block(self):
        brief = {"Role": "Acceptance Reviewer", "Prompt": "Audit SPEC.md."}
        errors = self.lint("# Title\n\nprose\n\n" + fence(brief))
        self.assertIn("[Brief: skills/work/SKILL.md:5]", errors[0])


class TestUnknownsFailClosed(BriefCase):
    def test_a_role_without_a_contract_fails(self):
        brief = {"Role": "Brand New Role", "Prompt": GROUNDED}
        errors = self.lint(fence(brief))
        self.assertEqual(1, len(errors), errors)
        self.assertIn("no grounding contract for role 'Brand New Role'", errors[0])

    def test_a_roleless_payload_that_is_not_the_heartbeat_fails(self):
        payload = {"Prompt": "Implement the feature."}
        errors = self.lint(f"```json\n{json.dumps(payload)}\n```\n")
        self.assertEqual(1, len(errors), errors)
        self.assertIn("has no Role", errors[0])

    def test_an_unparseable_payload_fails(self):
        errors = self.lint('```json\n{"Role": "Victory Auditor", "Prompt": "x",}\n```\n')
        self.assertEqual(1, len(errors), errors)
        self.assertIn("unparseable dispatch payload", errors[0])

    def test_a_cited_skill_path_that_does_not_exist_fails(self):
        brief = {"Role": "Victory Auditor", "Prompt": "Follow skills/nope/SKILL.md."}
        errors = self.lint(fence(brief))
        self.assertEqual(1, len(errors), errors)
        self.assertIn("cites skills/nope/SKILL.md, which does not exist", errors[0])


class TestEveryBriefFileIsScanned(BriefCase):
    def test_briefs_in_references_are_checked(self):
        brief = {"Role": "Acceptance Reviewer", "Prompt": "Audit SPEC.md."}
        errors = self.lint(fence(brief), rel="skills/work/references/protocol.md")
        self.assertTrue(any("references/protocol.md" in e and "W-07" in e for e in errors), errors)

    def test_a_block_indented_under_a_list_item_is_checked(self):
        """orchestrator_protocol.md nests its payloads inside a numbered list."""
        brief = {"Role": "Acceptance Reviewer", "Prompt": "Audit SPEC.md."}
        errors = self.lint("1. Dispatch:\n" + fence(brief, indent="   "))
        self.assertTrue(any("W-07" in e for e in errors), errors)

    def test_every_payload_in_a_block_is_checked_not_just_the_first(self):
        ok = {"Role": "Victory Auditor", "Prompt": "Run cold."}
        bad = {"Role": "Acceptance Reviewer", "Prompt": "Audit SPEC.md."}
        self.assertTrue(any("Acceptance Reviewer" in e for e in self.lint(fence(ok, bad))))


class TestRepositoryBriefs(unittest.TestCase):
    def test_every_shipped_brief_meets_its_contract(self):
        self.assertEqual([], validate_dispatch_briefs(str(REPO_ROOT)))

    def test_the_shipped_briefs_were_actually_found(self):
        """A lint that finds no briefs reports a clean repository too."""
        roles = {p.get("Role") for _, _, p in iter_dispatch_briefs(str(REPO_ROOT))
                 if isinstance(p, dict)}
        self.assertTrue({"Architectural Arbiter", "5-Axis Code Reviewer",
                         "Victory Auditor"} <= roles, roles)

    def test_every_contract_is_used_by_a_shipped_brief(self):
        """A contract with no brief is dead weight, or a brief was renamed."""
        roles = {p.get("Role") for _, _, p in iter_dispatch_briefs(str(REPO_ROOT))
                 if isinstance(p, dict)}
        self.assertEqual(set(), set(BRIEF_CONTRACTS) - roles)


if __name__ == "__main__":
    unittest.main()
