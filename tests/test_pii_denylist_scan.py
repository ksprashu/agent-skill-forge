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

"""PII and --denylist scanning in scripts/validate_skills.py.

An attribution line in a skill README may carry the repository author's
display name. It may not carry an email address, and a caller-supplied
denylist term is never skipped because the line is an attribution.
"""

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_skills import scan_skills_pii_and_denylist  # noqa: E402


AUTHOR = "Prashanth Subrahmanyam"


class PiiDenylistScanTest(unittest.TestCase):
    def scan(self, files, terms=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return scan_skills_pii_and_denylist(str(root), terms)

    def test_readme_attribution_may_name_the_author(self):
        text = f"*   **Original Author & Architect**: {AUTHOR} ([@ksprashu](https://github.com/ksprashu))\n"
        self.assertEqual([], self.scan({"skills/demo/README.md": text}))

    def test_readme_attribution_still_rejects_an_email(self):
        text = f"*   **Author**: {AUTHOR} <ksprashu@example.com>\n"
        found = self.scan({"skills/demo/README.md": text})
        self.assertTrue(any("ksprashu@" in item for item in found), found)
        self.assertFalse(any(AUTHOR in item for item in found), found)

    def test_readme_attribution_still_rejects_a_denylist_term(self):
        text = "*   **Curated by**: internal-codename stays on this line\n"
        found = self.scan(
            {"skills/demo/README.md": text},
            terms=["internal-codename"],
        )
        self.assertTrue(any("internal-codename" in item and "[denylist]" in item for item in found), found)

    def test_display_name_outside_an_attribution_line_is_rejected(self):
        text = f"Contact {AUTHOR} for the design.\n"
        found = self.scan({"skills/demo/README.md": text})
        self.assertTrue(found, found)
        skill = self.scan({"skills/demo/SKILL.md": textwrap.dedent(f"""\
            ---
            name: demo
            description: x
            ---
            Written by {AUTHOR}.
        """)})
        self.assertTrue(skill, skill)

    def test_clean_skill_text_passes(self):
        self.assertEqual([], self.scan({
            "skills/demo/SKILL.md": "---\nname: demo\ndescription: x\n---\nHello.\n",
            "skills/demo/README.md": "*   **Author**: A. N. Other\n",
        }))


if __name__ == "__main__":
    unittest.main()
