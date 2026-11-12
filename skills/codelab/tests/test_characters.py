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

"""characters.cjs is a validator. Node runs its suite; pytest runs Node."""

import shutil
import subprocess
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
NODE_TEST = Path(__file__).resolve().parent / "characters.test.cjs"


class CharactersCjsTest(unittest.TestCase):
    def test_node_suite_rejects_bad_packs_and_accepts_good_ones(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required to test characters.cjs")
        proc = subprocess.run(
            [node, "--test", str(NODE_TEST)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_mandatory_frontmatter_template_omits_the_credits_banner(self):
        """The banner is conditional. The scaffold and the template must agree."""
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        schema = (SKILL / "references" / "metadata-schemas.md").read_text(encoding="utf-8")

        def fenced(text, lang):
            marker = f"```{lang}"
            start = text.index(marker) + len(marker)
            end = text.index("```", start)
            return text[start:end]

        self.assertNotIn("Enable_GDP_Credits_Banner", fenced(skill, "yaml"))
        self.assertNotIn("Enable_GDP_Credits_Banner", fenced(schema, "md"))
        self.assertIn("only when the lab offers Google Cloud", skill)
        self.assertIn("Add this key only when", schema)


if __name__ == "__main__":
    unittest.main()
