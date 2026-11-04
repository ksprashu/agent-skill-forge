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
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertTrue((out / EV.PROFILE_DRAFT).is_file())
        self.assertTrue((out / EV.SAMPLES_DRAFT).is_file())
        self.assertIn("US-English", (out / EV.PROFILE_DRAFT).read_text(encoding="utf-8"))
        self.assertIn(
            "Please make sure the docs are grounded to the code",
            (out / EV.SAMPLES_DRAFT).read_text(encoding="utf-8"),
        )

    def test_never_overwrites_the_live_profile(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        live = Path(tmp.name) / "voice_and_tone.md"
        live.write_text("# mine\n", encoding="utf-8")
        EV.write_canonical_files([], EV.analyze_linguistics([]), tmp.name)
        self.assertEqual(live.read_text(encoding="utf-8"), "# mine\n")

    def test_draft_uses_the_voice_register_layout(self):
        text = (self._write() / EV.PROFILE_DRAFT).read_text(encoding="utf-8")
        for heading in ("## Core Persona", "## Linguistic & Punctuation Fingerprints",
                        "### R1:", "### R2:", "### R3:", "### R4:", "### R5:"):
            self.assertIn(heading, text)
        self.assertIn("<Your Name>", text)

    def test_carries_no_built_in_persona_or_samples(self):
        """It once wrote its author's persona whatever the logs said, and fell
        back to real-looking prompts when none were found."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        EV.write_canonical_files([], EV.analyze_linguistics([]), tmp.name)
        out = Path(tmp.name)
        profile = (out / EV.PROFILE_DRAFT).read_text(encoding="utf-8")
        samples = (out / EV.SAMPLES_DRAFT).read_text(encoding="utf-8")
        self.assertIn("No prompts of a usable length", samples)
        self.assertNotIn("## Excerpt", samples)
        for phrase in ("Frustration", "Dev Advocate", "teh", "meh"):
            self.assertNotIn(phrase, profile + samples)

    def test_default_output_is_the_persona_directory(self):
        with mock.patch.dict(os.environ, {"AGENT_PERSONA_DIR": "/tmp/p"}):
            self.assertEqual(EV.default_output_dir(), os.path.join("/tmp/p", "default"))


    def test_does_not_scaffold_a_skill(self):
        out = self._write()
        self.assertFalse((out / "SKILL.md").exists())
        self.assertFalse((out / "golden_examples.md").exists())


class TestRedactionHasNoBuiltInEmployer(unittest.TestCase):
    def test_source_names_no_employer_domain(self):
        for module in (EV, EV.log_sources):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for domain in ("google" + ".com", "joonix"):
                self.assertNotIn(domain, source, module.__name__)

    def test_generic_internal_hosts_are_redacted(self):
        """The documented examples in EXAMPLES.md, verbatim."""
        self.assertEqual(
            "Deploy this microservice under the <COMPANY_DOMAIN> cloud project and "
            "verify the webhook at <INTERNAL_URL>.",
            EV.sanitize_text(
                "Deploy this microservice under the microservice.corp.internal cloud project "
                "and verify the webhook at https://subdomain.corp.internal/receiver/v1."))

    def test_a_supplied_internal_domain_is_redacted(self):
        saved = list(EV.EXTRA_PATTERNS)
        self.addCleanup(lambda: EV.EXTRA_PATTERNS.__setitem__(slice(None), saved))
        EV.add_internal_domains(["example-corp.net"])
        out = EV.sanitize_text("deploy to https://build.example-corp.net/job/7 and ci.example-corp.net.")
        self.assertEqual("deploy to <INTERNAL_URL> and <COMPANY_DOMAIN>.", out)

    def test_an_internal_label_mid_hostname_redacts_the_whole_name(self):
        out = EV.sanitize_text(
            "clone git.internal.acme.example, open https://ci.corp.acme.example:8443/job/7. "
            "Also corp.acme.example and build.intranet.")
        self.assertEqual(
            "clone <COMPANY_DOMAIN>, open <INTERNAL_URL>. Also <COMPANY_DOMAIN> and <COMPANY_DOMAIN>.",
            out)
        self.assertNotIn("acme", out)

    def test_a_supplied_domain_under_an_internal_label_leaves_no_suffix(self):
        saved = list(EV.EXTRA_PATTERNS)
        self.addCleanup(lambda: EV.EXTRA_PATTERNS.__setitem__(slice(None), saved))
        EV.add_internal_domains(["acme.example"])
        out = EV.sanitize_text("ssh git.internal.acme.example or https://x.corp.acme.example/a")
        self.assertEqual("ssh <COMPANY_DOMAIN> or <INTERNAL_URL>", out)

    def test_an_email_under_a_supplied_domain_is_redacted_whole(self):
        saved = list(EV.EXTRA_PATTERNS)
        self.addCleanup(lambda: EV.EXTRA_PATTERNS.__setitem__(slice(None), saved))
        EV.add_internal_domains(["acme.example"])
        out = EV.sanitize_text("ask alice.smith@acme.example or oncall@corp.acme.example")
        self.assertEqual("ask <EMAIL> or <EMAIL>", out)

    def test_ordinary_words_are_not_hostnames(self):
        text = "The internal API and corporate docs live in internal-tools.md and localhost."
        self.assertEqual(text, EV.sanitize_text(text))


class TestMeasuredHabits(unittest.TestCase):
    """Different writing must produce different measurements and drafts."""

    def _draft(self, prompts):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        EV.write_canonical_files(prompts, EV.analyze_linguistics(prompts), tmp.name)
        return (Path(tmp.name) / EV.PROFILE_DRAFT).read_text(encoding="utf-8")

    def test_rates_follow_the_input(self):
        plain = EV.analyze_linguistics(["Ship it today.", "Run the tests first."])
        marked = EV.analyze_linguistics(["It's done — ship it -> prod.", "Don't merge yet..."])
        rates = lambda s: s["punctuation_habits"]
        self.assertEqual(rates(plain)["em_dash_frequency"], "0%")
        self.assertEqual(rates(marked)["em_dash_frequency"], "50%")
        self.assertEqual(rates(plain)["arrow_frequency"], "0%")
        self.assertEqual(rates(marked)["arrow_frequency"], "50%")
        self.assertEqual(rates(plain)["contraction_frequency"], "0%")
        self.assertEqual(rates(marked)["contraction_frequency"], "100%")
        self.assertEqual(rates(marked)["ellipsis_frequency"], "50%")

    def test_rates_reach_the_draft(self):
        text = self._draft(["It's done — ship it -> prod.", "Run the tests first."])
        self.assertIn("em-dashes in 50% of prompts", text)
        self.assertIn("`=>` in 50% of prompts", text)
        self.assertIn("**Contractions**: in 50% of prompts", text)

    def test_a_few_commonwealth_words_do_not_contradict_the_spelling(self):
        stats = EV.analyze_linguistics(["Change the colour of the button please."])
        self.assertEqual(stats["spelling"], "US-English")
        self.assertEqual(stats["commonwealth_words"], ["colour"])
        text = self._draft(["Change the colour of the button please."])
        self.assertIn("US-English by default; 1 Commonwealth spelling seen (colour)", text)
        self.assertNotIn("(seen: colour)", text)
        self.assertIn("Drafted by human-voice from 1 redacted prompts", text)

    def test_the_header_counts_prompts_not_spellings(self):
        prompts = ["Change the colour of the button.", "Ship it.", "Run the tests."]
        self.assertIn("Drafted by human-voice from 3 redacted prompts", self._draft(prompts))

    def test_more_than_three_commonwealth_words_switch_the_spelling(self):
        prompts = ["colour it", "optimise it", "prioritise it", "visualise it"]
        stats = EV.analyze_linguistics(prompts)
        self.assertEqual(stats["spelling"], "British/Commonwealth")
        self.assertIn("British/Commonwealth (seen: ", self._draft(prompts))
        self.assertEqual(EV.analyze_linguistics(prompts[:3])["spelling"], "US-English")


class TestExamplesAreVerbatim(unittest.TestCase):
    """The scrubbing examples in EXAMPLES.md, input and output verbatim."""

    def test_example_a_email_host_and_name(self):
        self.assertEqual(
            "Set up standard OAuth restrictions so that only <EMAIL> and anyone from "
            "<COMPANY_DOMAIN> can authenticate. Ask <USER_NAME> if we need other domains.",
            EV.sanitize_text(
                "Set up standard OAuth restrictions so that only developer@example.com and "
                "anyone from corp.internal can authenticate. Ask Alex if we need other domains.",
                extra_names=[("Alex", "<USER_NAME>")]))

    def test_example_c_home_path_and_token(self):
        raw = ("I have cloned the repo in /Users/developer/code/github/project. "  # host-path-ok
               "My GitHub Token is ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8. "
               "Can you push the feature branch?")
        self.assertEqual(
            "I have cloned the repo in ~/code/github/project. My GitHub Token is <TOKEN>. "
            "Can you push the feature branch?",
            EV.sanitize_text(raw))


class TestSharedRedactionTable(unittest.TestCase):
    """human-voice redacts with the same table cognitive-profiler does."""

    def test_patterns_human_voice_never_had_are_now_caught(self):
        for secret in ("xoxb-1234567890-abcdef", "Bearer abcdef123456",
                       "password = hunter2correcthorse",
                       "sk-proj-abcdefghijklmnopqrstuvwx"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, EV.sanitize_text(f"use {secret} here"))

    def test_patterns_cognitive_profiler_never_had_are_still_caught(self):
        for secret, placeholder in (("10.1.2.3", "<IP_ADDRESS>"),
                                    ("fe80::1ff:fe23:4567:890a", "<IP_ADDRESS>"),
                                    ("AKIAABCDEFGHIJKLMNOP", "<API_KEY>"),
                                    ("glpat-abcdefghijklmnopqrst", "<TOKEN>"),
                                    ("github_pat_" + "a" * 30, "<TOKEN>")):
            with self.subTest(secret=secret):
                out = EV.sanitize_text(f"use {secret} here")
                self.assertNotIn(secret, out)
                self.assertIn(placeholder, out)

    def test_code_with_double_colons_is_not_an_ip_address(self):
        self.assertEqual("call std::add and Vec::new",
                         EV.sanitize_text("call std::add and Vec::new"))

    def test_the_login_name_is_scrubbed(self):
        with mock.patch.object(EV.log_sources, "login_name", return_value="jdoe"):
            self.assertEqual("ask <USER_ID> about it", EV.sanitize_text("ask jdoe about it"))

    def test_a_login_name_that_is_a_placeholder_word_does_not_mangle_it(self):
        with mock.patch.object(EV.log_sources, "login_name", return_value="email"):
            self.assertEqual("mail <EMAIL>", EV.sanitize_text("mail a@b.com"))


def _jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


class ToolFixture:
    """Point one tool at a temporary directory for the duration of a test."""

    def __init__(self, tool):
        self.tool = tool
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def __enter__(self):
        self._saved = dict(EV.PATHS)
        EV.PATHS[self.tool] = [self.root]
        return self.root

    def __exit__(self, *exc):
        EV.PATHS.clear()
        EV.PATHS.update(self._saved)
        self.tmp.cleanup()
        return False


class TestClaudeCodeSessions(unittest.TestCase):
    """Claude Code writes ~/.claude/projects/<slug>/<session>.jsonl with the
    turn under `message`. The old extractor globbed chat_*.jsonl and read a
    top-level `role`, so it found nothing on a real machine."""

    def _extract(self, records):
        with ToolFixture("claude-code") as root:
            _jsonl(root / "-home-dev-project" / "0b5c3c1e-session.jsonl", records)
            return EV.extract_claude_code()

    def test_string_content_is_read(self):
        self.assertEqual(["fix the failing test"], self._extract([
            {"type": "user", "timestamp": "2026-09-20T10:00:00Z",
             "message": {"role": "user", "content": "fix the failing test"}}]))

    def test_text_parts_are_read(self):
        self.assertEqual(["first part\nsecond part"], self._extract([
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": "first part"},
                {"type": "text", "text": "second part"}]}}]))

    def test_tool_result_records_are_not_prompts(self):
        self.assertEqual([], self._extract([
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "42 passed"}]}}]))

    def test_assistant_meta_sidechain_and_commands_are_not_prompts(self):
        self.assertEqual([], self._extract([
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Here is the fix."}]}},
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "meta"}},
            {"type": "user", "isSidechain": True,
             "message": {"role": "user", "content": "subagent prompt"}},
            {"type": "user", "isCompactSummary": True,
             "message": {"role": "user", "content": "This session is being continued"}},
            {"type": "user", "message": {"role": "user",
                                         "content": "<command-name>/clear</command-name>"}}]))

    def test_prompts_are_redacted(self):
        out = self._extract([{"type": "user", "message": {
            "role": "user", "content": "mail ops@example.com from /Users/dev/x"}}])  # host-path-ok
        self.assertEqual(["mail <EMAIL> from ~/x"], out)


class TestOtherTools(unittest.TestCase):

    def test_cline_and_roo_code_are_read_separately(self):
        with ToolFixture("cline") as cline_root, ToolFixture("roo-code") as roo_root:
            for root, word in ((cline_root, "cline"), (roo_root, "roo")):
                (root / "1700000000000").mkdir()
                (root / "1700000000000" / "ui_messages.json").write_text(json.dumps([
                    {"type": "say", "say": "text", "text": "assistant reply"},
                    {"type": "say", "say": "user_feedback", "text": f"typed into {word}"},
                ]), encoding="utf-8")
            self.assertEqual(["typed into cline"],
                             EV.extract_cline_and_roo_code(tools=("cline",)))
            self.assertEqual(2, len(EV.extract_cline_and_roo_code()))

    def test_aider_chat_history_reads_user_lines_not_tool_output(self):
        """aider writes your input as `#### ` lines and its own output as `> `
        blockquotes; the old extractor read the blockquotes."""
        with ToolFixture("aider") as root:
            chat = root / ".aider.chat.history.md"
            chat.write_text(
                "# aider chat started at 2026-09-20 10:00:00\n\n"
                "> Aider v0.60.0\n> Added app.py to the chat.\n\n"
                "#### add a retry to the upload call\n\n"
                "Here is the change.\n", encoding="utf-8")
            EV.PATHS["aider"] = [chat]
            self.assertEqual(["add a retry to the upload call"], EV.extract_aider())

    def test_aider_input_history_strips_the_plus_prefix(self):
        with ToolFixture("aider") as root:
            history = root / ".aider.input.history"
            history.write_text("\n# 2026-09-20 10:00:01.123\n+rename the helper\n",
                               encoding="utf-8")
            EV.PATHS["aider"] = [history]
            self.assertEqual(["rename the helper"], EV.extract_aider())

    def test_gemini_cli_session_json_is_read(self):
        with ToolFixture("gemini-cli") as root:
            chats = root / "abc123" / "chats"
            chats.mkdir(parents=True)
            (chats / "session-1.json").write_text(json.dumps({"messages": [
                {"type": "user", "content": "explain the cache"},
                {"type": "gemini", "content": "The cache..."},
            ]}), encoding="utf-8")
            _jsonl(chats / "older.jsonl", [{"role": "user", "content": "older format"}])
            self.assertEqual(sorted(["explain the cache", "older format"]),
                             sorted(EV.extract_gemini_cli()))


if __name__ == "__main__":
    unittest.main()
