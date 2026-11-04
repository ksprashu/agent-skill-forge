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

"""The shared log harvester ships as byte-identical copies in two skills.

human-voice and cognitive-profiler both read the user's own turns out of local
AI-tool logs and redact them. A skill installed with `npx skills add` is only
its own folder, so neither can import the other's code; each bundles
log_sources.py instead. Separate copies of this logic drifted once already (one
skill read Claude Code's real format, the other found zero prompts), so this
test fails the moment the copies differ.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COPIES = [
    REPO_ROOT / "skills" / "cognitive-profiler" / "scripts" / "log_sources.py",
    REPO_ROOT / "skills" / "human-voice" / "scripts" / "log_sources.py",
]


class TestLogSourcesParity(unittest.TestCase):

    def test_every_copy_exists(self):
        for path in COPIES:
            self.assertTrue(path.is_file(), f"missing {path.relative_to(REPO_ROOT)}")

    def test_copies_are_byte_identical(self):
        first, *rest = COPIES
        reference = first.read_bytes()
        for path in rest:
            self.assertEqual(
                reference, path.read_bytes(),
                f"{path.relative_to(REPO_ROOT)} differs from "
                f"{first.relative_to(REPO_ROOT)}. Edit one copy, then copy it "
                f"over the other.")


if __name__ == "__main__":
    unittest.main()
