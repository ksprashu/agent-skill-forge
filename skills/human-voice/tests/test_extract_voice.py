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

"""Tests for the transcript extractors in skills/human-voice.

The surface filter is the part worth pinning. `--tool antigravity-cli` once
read the IDE brain as well, so a user who asked for one surface silently got
both — and this script exists to pull a person's own words out of their
machine, where reading more than was asked for is exactly the wrong failure.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import extract_voice as EV  # noqa: E402


class SurfaceFixture:
    """Two Antigravity brain directories, each with one distinguishable prompt."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {}
        for surface in ("antigravity-ide", "antigravity-cli"):
            session = root / surface / "brain" / "session-1"
            session.mkdir(parents=True)
            (session / "transcript.jsonl").write_text(
                json.dumps({"type": "USER_INPUT", "content": f"spoken into the {surface}"}) + "\n",
                encoding="utf-8")
            self.paths[surface] = str(root / surface / "brain")

    def __enter__(self):
        self._saved = dict(EV.PATHS)
        EV.PATHS.update(self.paths)
        return self

    def __exit__(self, *exc):
        EV.PATHS.clear()
        EV.PATHS.update(self._saved)
        self.tmp.cleanup()
        return False


class TestAntigravitySurfaceFilter(unittest.TestCase):

    def test_the_cli_extractor_reads_only_the_cli_brain(self):
        with SurfaceFixture():
            self.assertEqual(["spoken into the antigravity-cli"],
                             EV.extract_antigravity_cli())

    def test_the_ide_extractor_reads_only_the_ide_brain(self):
        with SurfaceFixture():
            self.assertEqual(["spoken into the antigravity-ide"],
                             EV.extract_antigravity_ide())

    def test_the_unfiltered_extractor_reads_both(self):
        with SurfaceFixture():
            self.assertEqual(2, len(EV.extract_antigravity()))

    def test_an_absent_brain_directory_is_not_an_error(self):
        with SurfaceFixture():
            EV.PATHS["antigravity-cli"] = "/nonexistent/brain/xyz"
            self.assertEqual([], EV.extract_antigravity_cli())


class TestSanitisation(unittest.TestCase):

    def test_an_email_address_does_not_survive_extraction(self):
        with SurfaceFixture() as fx:
            session = Path(fx.paths["antigravity-cli"]) / "session-2"
            session.mkdir(parents=True)
            (session / "transcript.jsonl").write_text(
                json.dumps({"type": "USER_INPUT",
                            "content": "mail me at someone@example.com"}) + "\n",
                encoding="utf-8")
            joined = "\n".join(EV.extract_antigravity_cli())
            self.assertNotIn("someone@example.com", joined)
            self.assertIn("<EMAIL>", joined)

    def test_a_supplied_name_is_replaced_wherever_it_appears(self):
        self.assertEqual(
            "<USER_NAME> wrote this",
            EV.sanitize_text("Alex wrote this", extra_names=[("Alex", "<USER_NAME>")]))


if __name__ == "__main__":
    unittest.main()


class TestOutputsFeedVoiceRegister(unittest.TestCase):
    """The extractor's outputs are a voice-register profile, not a new skill.

    It used to emit a SKILL.md for a `copy-writer-bara` skill that no longer
    exists, and a golden_examples.md that nothing reads.
    """

    def _write(self):
        prompts = ["Please make sure the docs are grounded to the code and the tests pass before merging this change."]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        EV.write_canonical_files(prompts, EV.analyze_linguistics(prompts), tmp.name)
        return Path(tmp.name)

    def test_writes_a_profile_and_samples(self):
        out = self._write()
        self.assertTrue((out / "voice_and_tone.md").is_file())
        self.assertTrue((out / "voice-samples.md").is_file())

    def test_does_not_scaffold_a_skill(self):
        out = self._write()
        self.assertFalse((out / "SKILL.md").exists())
        self.assertFalse((out / "golden_examples.md").exists())
