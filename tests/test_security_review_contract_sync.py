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

"""T6: security-review bundles its own copy of the shared findings contract.

`npx skills add` installs a skill as its folder alone, so security-review
cannot import from skills/review at run time. It carries byte-identical copies
of findings.py and findings.schema.json instead. These tests fail the moment
the copies drift; the fix is to copy the review versions across again.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAIRS = (
    ("skills/review/scripts/findings.py", "skills/security-review/scripts/findings.py"),
    ("skills/review/references/findings.schema.json",
     "skills/security-review/references/findings.schema.json"),
)


class ContractSyncTest(unittest.TestCase):
    def test_copies_are_byte_identical(self):
        for source, copy in PAIRS:
            with self.subTest(copy=copy):
                a, b = REPO_ROOT / source, REPO_ROOT / copy
                self.assertTrue(b.is_file(), f"{copy} is missing; copy it from {source}")
                self.assertEqual(a.read_bytes(), b.read_bytes(),
                                 f"{copy} has drifted from {source}; copy it again")

    def test_bundled_schema_matches_bundled_generator(self):
        script = REPO_ROOT / "skills/security-review/scripts/findings.py"
        out = subprocess.run([sys.executable, str(script), "schema"], capture_output=True,
                             text=True, shell=False, timeout=60, check=True).stdout
        committed = (REPO_ROOT / "skills/security-review/references/findings.schema.json")
        self.assertEqual(json.loads(out), json.loads(committed.read_text(encoding="utf-8")))

    def test_contract_accepts_security_review_producer(self):
        script = REPO_ROOT / "skills/security-review/scripts/findings.py"
        doc = {
            "schema_version": "1", "producer": "security-review", "mode": "diff",
            "summary": "No confirmed issues.", "inspected": ["app.py"],
            "not_inspected": [{"what": "trivy", "reason": "not installed"}],
            "findings": [],
        }
        proc = subprocess.run([sys.executable, str(script), "validate", "-"],
                              input=json.dumps(doc), capture_output=True, text=True,
                              shell=False, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
