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

"""Evidence-collection tests.

Two properties matter more than the parsing details:

1. Nothing leaves this machine unredacted. The evidence file is written to
   disk and handed to a model, so every credential pattern is tested.
2. harvest.py draws no conclusions. It emits counts and quotes; the moment it
   starts emitting bands or scores, the judgement moves out of the reviewable
   layer and back into keyword arithmetic.
"""

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import harvest as H  # noqa: E402
import profile_tool as P  # noqa: E402


def jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def claude_user(text, **extra):
    rec = {"type": "user", "timestamp": "2026-09-20T10:00:00Z",
           "message": {"content": text}}
    rec.update(extra)
    return rec


class TestRedaction(unittest.TestCase):
    """Every pattern here has shipped in someone's transcript at some point."""

    def test_email_is_replaced(self):
        self.assertEqual(H.redact("ping alice@example.com now"),
                         "ping <EMAIL> now")

    def test_google_api_key_is_replaced(self):
        key = "AIzaSy" + "A" * 33
        self.assertNotIn(key, H.redact(f"key is {key}"))

    def test_openai_style_key_is_replaced(self):
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz",
                         H.redact("export OPENAI=sk-abcdefghijklmnopqrstuvwxyz"))

    def test_an_internal_label_mid_hostname_redacts_the_whole_name(self):
        out = H.redact("see git.internal.acme.example and https://ci.corp.acme.example/job/7")
        self.assertEqual(out, "see <COMPANY_DOMAIN> and <INTERNAL_URL>")

    def test_authorization_header_token_is_replaced(self):
        for header in ("Authorization: Bearer abc.def-123", "authorization: Basic dXNlcjpwYXNz",
                       "Authorization: abc123secret", "curl -H 'bearer abc123secret'"):
            out = H.redact(header)
            self.assertIn("<AUTH>", out, header)
            for secret in ("abc.def-123", "dXNlcjpwYXNz", "abc123secret"):
                self.assertNotIn(secret, out, header)

    def test_github_token_is_replaced(self):
        self.assertNotIn("ghp_", H.redact("use ghp_" + "b" * 36))

    def test_jwt_is_replaced(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K"
        self.assertIn("<JWT>", H.redact(f"Authorization {jwt}"))

    def test_assignment_style_secret_is_replaced(self):
        self.assertIn("<SECRET>", H.redact("password = hunter2correcthorse"))

    def test_json_quoted_secret_assignment_is_replaced(self):
        secret = "hunter2" + "correcthorse"
        raw = '{"password": "' + secret + '", "user": "alice"}'
        out = H.redact(raw)
        self.assertNotIn(secret, out)
        self.assertIn("<SECRET>", out)
        self.assertIn('"user": "alice"', out)
        self.assertEqual(H.redact(out), out)

    def test_credentialed_uri_is_replaced(self):
        pw1 = "myS3cret" + "Pass"
        pw2 = "myS3cret!" + "Pass"
        pw3 = "redis" + "Secret99"
        for uri, pw in (
            (f"postgres://admin:{pw1}@10.0.1.5:5432/prod", pw1),
            (f"https://admin:{pw2}@api.example.com/v1", pw2),
            (f"redis://:{pw3}@cache.internal:6379/0", pw3),
        ):
            out = H.redact(f"connect to ({uri}).")
            self.assertNotIn(pw, out, uri)
            self.assertEqual(out, "connect to (<SECRET>).")
            self.assertEqual(H.redact(out), out)

    def test_authorization_apikey_and_oauth_schemes_redact_the_credential(self):
        tok = "secret_tok_" + "999"
        for scheme in ("ApiKey", "Api-Key", "OAuth", "Bot"):
            out = H.redact(f"Authorization: {scheme} {tok}")
            self.assertIn("<AUTH>", out, scheme)
            self.assertNotIn(tok, out, scheme)

    def test_posix_home_directory_becomes_tilde(self):
        self.assertEqual(H.redact("/Users/someone/code/x.py"), "~/code/x.py")  # host-path-ok

    def test_windows_home_directory_becomes_tilde(self):
        self.assertEqual(H.redact(r"C:\Users\Someone\notes.md"), r"~\notes.md")  # host-path-ok

    def test_home_directory_in_a_claude_project_slug_becomes_tilde(self):
        self.assertEqual(H.redact("tasks/-Users-someone-code-repo/a.output"),  # host-path-ok
                         "tasks/~-code-repo/a.output")
        self.assertEqual(H.redact("tasks/-Users-alice.smith-code-repo/a.output"),  # host-path-ok
                         "tasks/~-code-repo/a.output")
        self.assertEqual(H.redact("projects/C--Users-alice.smith-code/s.jsonl"),  # host-path-ok
                         "projects/~-code/s.jsonl")
        self.assertEqual(H.redact("pass --home-dir /tmp/work"),
                         "pass --home-dir /tmp/work")

    def test_login_name_is_replaced(self):
        name = H.log_sources.login_name()
        if not name:
            self.skipTest("no login name on this host")
        self.assertNotIn(name, H.redact(f"cd /srv/{name}-work"))

    def test_redaction_happens_on_the_way_in(self):
        """Quotes are redacted at capture, not at write, so an exception
        between the two cannot leak anything."""
        h = H.Harvest()
        h.add_user_turn("claude-code", "this is too long, mail me at a@b.com")
        self.assertIn("<EMAIL>", h.quotes[0]["text"])
        self.assertNotIn("a@b.com", json.dumps(h.report()))

    def test_redaction_is_idempotent(self):
        once = H.redact("a@b.com and /Users/x/f")  # host-path-ok
        self.assertEqual(H.redact(once), once)

    def test_check_redaction_flags_a_dirty_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        dirty = tmp / "evidence.json"
        dirty.write_text('{"quotes": ["mail me at leak@example.com"]}',
                         encoding="utf-8")
        self.assertEqual(H.main(["--check-redaction", str(dirty)]), 1)

    def test_check_redaction_passes_a_clean_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        clean = tmp / "evidence.json"
        clean.write_text('{"quotes": ["that was too long"]}', encoding="utf-8")
        self.assertEqual(H.main(["--check-redaction", str(clean)]), 0)


class TestSignalMatching(unittest.TestCase):
    """The previous version of this skill counted bare words like "stop" and
    "hello". These tests exist so that cannot come back."""

    def test_a_real_complaint_is_matched(self):
        hits = dict(H.find_signals("that was way too long, cut it down"))
        self.assertIn("length_complaint", hits)

    def test_ordinary_prose_matches_nothing(self):
        benign = [
            "hello, can you look at the auth module",
            "stop the container and restart it",
            "the build failed again",
            "I think the table in postgres needs an index",
            "run it against staging first",
        ]
        for text in benign:
            self.assertEqual(H.find_signals(text), [],
                             f"false positive on: {text}")

    def test_table_talk_is_not_a_structure_request(self):
        """'table' alone is a database word in this corpus far more often than
        a formatting request."""
        self.assertEqual(H.find_signals("drop the users table"), [])
        self.assertIn("structure_request",
                      dict(H.find_signals("show me that as a table")))

    def test_every_signal_phrase_matches_its_own_signal(self):
        for name, spec in H.SIGNALS.items():
            for phrase in spec["phrases"]:
                hits = dict(H.find_signals(f"well, {phrase}, please"))
                self.assertIn(name, hits, f"{name}: {phrase!r} does not match")

    def test_matching_is_case_insensitive(self):
        self.assertIn("length_complaint",
                      dict(H.find_signals("TOO VERBOSE")))

    def test_every_signal_documents_what_it_means(self):
        for name, spec in H.SIGNALS.items():
            self.assertTrue(spec["means"].strip(), name)
            self.assertTrue(spec["phrases"], name)


class TestNoJudgement(unittest.TestCase):
    """harvest.py collects; it does not conclude. If a scoring key ever shows
    up in the report, the judgement has silently moved back into Python."""

    def setUp(self):
        h = H.Harvest()
        for _ in range(60):
            h.add_user_turn("claude-code", "too long, be concise")
        self.report = h.report()

    def test_report_contains_no_bands_or_scores(self):
        blob = json.dumps(self.report).lower()
        for word in ("band", "score", "rating", "percentile", "profile",
                     "recommend", "personality"):
            self.assertNotIn(f'"{word}"', blob, f"report emits a '{word}' key")

    def test_report_names_no_profile_dimension(self):
        blob = json.dumps(self.report).lower()
        for dimension in P.DIMENSIONS:
            self.assertNotIn(dimension, blob,
                             f"harvest.py is pre-judging '{dimension}'")

    def test_signals_carry_counts_and_quote_ids_only(self):
        for name, entry in self.report["signals"].items():
            self.assertEqual(sorted(entry), ["count", "means", "quotes"], name)


class TestCoverageHonesty(unittest.TestCase):
    """Coverage gates how much the agent is entitled to conclude, so the
    thresholds are part of the contract, not an implementation detail."""

    def _harvest(self, turns, complaints):
        h = H.Harvest()
        for _ in range(complaints):
            h.add_user_turn("claude-code", "that was too long")
        for i in range(turns - complaints):
            h.add_user_turn("claude-code", f"please look at module {i}")
        return h.report()["coverage"]

    def test_no_data_is_thin(self):
        self.assertEqual(H.Harvest().report()["coverage"]["level"], "thin")

    def test_many_turns_but_no_signal_is_still_thin(self):
        self.assertEqual(self._harvest(200, 2)["level"], "thin")

    def test_few_turns_with_signal_is_still_thin(self):
        """A 100% complaint rate over 10 turns is not a personality."""
        self.assertEqual(self._harvest(10, 10)["level"], "thin")

    def test_moderate_signal_is_partial(self):
        self.assertEqual(self._harvest(100, 10)["level"], "partial")

    def test_strong_signal_is_adequate(self):
        self.assertEqual(self._harvest(200, 40)["level"], "adequate")

    def test_every_level_carries_actionable_advice(self):
        for turns, complaints in ((0, 0), (100, 10), (200, 40)):
            cov = self._harvest(turns, complaints) if turns else \
                H.Harvest().report()["coverage"]
            self.assertGreater(len(cov["advice"]), 40, cov["level"])


class TestQuotes(unittest.TestCase):
    def test_quote_ids_are_the_form_the_profile_validator_accepts(self):
        h = H.Harvest()
        h.add_user_turn("claude-code", "too long")
        for quote in h.report()["quotes"]:
            self.assertRegex(quote["id"], P.QUOTE_ID_RE)

    def test_quote_ids_are_unique(self):
        h = H.Harvest()
        for _ in range(30):
            h.add_user_turn("claude-code", "too long")
            h.add_user_turn("claude-code", "just tell me")
        ids = [q["id"] for q in h.quotes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_quotes_are_capped_per_signal_but_counts_are_not(self):
        h = H.Harvest(max_quotes_per_signal=3)
        for _ in range(25):
            h.add_user_turn("claude-code", "too long")
        report = h.report()
        self.assertEqual(len(report["quotes"]), 3)
        self.assertEqual(report["signals"]["length_complaint"]["count"], 25)

    def test_long_turns_are_truncated(self):
        h = H.Harvest()
        h.add_user_turn("claude-code", "too long " + "x" * 2000)
        self.assertLessEqual(len(h.quotes[0]["text"]), H.MAX_QUOTE_CHARS + 1)

    def test_every_signal_quote_id_resolves_in_the_quote_list(self):
        h = H.Harvest()
        h.add_user_turn("claude-code", "too long")
        h.add_user_turn("claude-code", "pick one")
        report = h.report()
        known = {q["id"] for q in report["quotes"]}
        for entry in report["signals"].values():
            self.assertTrue(set(entry["quotes"]) <= known)

    def test_since_window_drops_older_turns(self):
        h = H.Harvest(since="2026-09-01")
        h.add_user_turn("claude-code", "too long", when="2026-08-30T00:00:00Z")
        h.add_user_turn("claude-code", "too long", when="2026-09-15T00:00:00Z")
        self.assertEqual(h.report()["coverage"]["user_turns"], 1)

    def test_empty_turns_are_not_counted(self):
        h = H.Harvest()
        h.add_user_turn("claude-code", "   ")
        h.add_user_turn("claude-code", "")
        self.assertEqual(h.report()["coverage"]["user_turns"], 0)


class TestClaudeCodeParser(unittest.TestCase):
    """type=="user" in a Claude Code transcript does not mean a human spoke.
    Counting harness chatter as speech profiles the tool, not the person."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.h = H.Harvest()

    def _parse(self, records):
        jsonl(self.tmp / "proj" / "session.jsonl", records)
        return self.h.parse_claude_code(self.tmp)

    def test_a_plain_user_turn_is_counted(self):
        self._parse([claude_user("that was too long")])
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)

    def test_meta_records_are_skipped(self):
        self._parse([claude_user("too long", isMeta=True)])
        self.assertEqual(self.h.report()["coverage"]["user_turns"], 0)

    def test_subagent_records_are_skipped(self):
        """Sidechain turns are written by an agent, not the user."""
        self._parse([claude_user("too long", isSidechain=True)])
        self.assertEqual(self.h.report()["coverage"]["user_turns"], 0)

    def test_sidechain_and_meta_assistant_turns_do_not_pollute_word_counts(self):
        count = self._parse([
            {"type": "assistant", "timestamp": "2026-09-20T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "w " * 400}]}},
            {"type": "assistant", "isSidechain": True,
             "timestamp": "2026-09-20T10:00:01Z",
             "message": {"content": [{"type": "text", "text": "w " * 900}]}},
            {"type": "assistant", "isMeta": True,
             "timestamp": "2026-09-20T10:00:02Z",
             "message": {"content": [{"type": "text", "text": "w " * 700}]}},
            claude_user("too long"),
        ])
        self.assertEqual(count, 1)
        self.assertEqual(self.h.assistant_word_counts, [400])
        self.assertEqual(self.h.response_words_at_complaint, [400])

    def test_sidechain_only_file_counts_zero_sessions(self):
        count = self._parse([
            {"type": "assistant", "isSidechain": True,
             "message": {"content": [{"type": "text", "text": "subagent reply"}]}},
            claude_user("subagent prompt", isSidechain=True),
        ])
        self.assertEqual(count, 0)

    def test_tool_results_are_skipped(self):
        self._parse([{
            "type": "user", "timestamp": "2026-09-20T10:00:00Z",
            "message": {"content": [
                {"type": "tool_result", "content": "too long"}]}}])
        self.assertEqual(self.h.report()["coverage"]["user_turns"], 0)

    def test_slash_commands_and_pasted_output_are_skipped(self):
        for prefix in ("<command-name>x", "<local-command-stdout>too long",
                       "<bash-input>ls", "Caveat: the messages below",
                       "<task-notification>\n<status>too long</status>",
                       "<system-reminder>too long</system-reminder>"):
            h = H.Harvest()
            jsonl(self.tmp / "p" / "s.jsonl", [claude_user(prefix)])
            h.parse_claude_code(self.tmp)
            self.assertEqual(h.report()["coverage"]["user_turns"], 0, prefix)

    def test_assistant_text_blocks_are_measured(self):
        self._parse([{
            "type": "assistant", "timestamp": "2026-09-20T10:00:00Z",
            "message": {"content": [{"type": "text", "text": "one two three"}]}}])
        self.assertEqual(self.h.assistant_word_counts, [3])

    def test_a_length_complaint_records_the_response_it_was_about(self):
        """This pairing is what makes response_ceiling_words a measurement
        rather than a guess."""
        self._parse([
            {"type": "assistant", "timestamp": "2026-09-20T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "w " * 500}]}},
            claude_user("too long"),
        ])
        self.assertEqual(self.h.response_words_at_complaint, [500])
        self.assertEqual(
            self.h.report()["stats"][
                "assistant_words_when_length_complained"]["n"], 1)

    def test_malformed_lines_do_not_abort_the_file(self):
        path = self.tmp / "p" / "s.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"broken\n' + json.dumps(claude_user("too long")) + "\n",
                        encoding="utf-8")
        self.h.parse_claude_code(self.tmp)
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)

    def test_a_missing_directory_is_not_an_error(self):
        self.assertEqual(self.h.parse_claude_code(self.tmp / "nope"), 0)


class TestAntigravityParser(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.h = H.Harvest()

    def _parse(self, records):
        jsonl(self.tmp / "sess" / "transcript.jsonl", records)
        return self.h.parse_antigravity(self.tmp)

    def test_the_request_envelope_is_unwrapped(self):
        self._parse([{"type": "USER_INPUT", "source": "USER_EXPLICIT",
                      "created_at": "2026-09-20T10:00:00Z",
                      "content": "<USER_REQUEST>that was too long"
                                 "</USER_REQUEST>"}])
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)
        self.assertNotIn("USER_REQUEST", self.h.quotes[0]["text"])

    def test_synthetic_input_is_skipped(self):
        """Only USER_EXPLICIT is a person typing; the rest is the harness
        talking to itself."""
        self._parse([{"type": "USER_INPUT", "source": "SYSTEM",
                      "content": "too long"}])
        self.assertEqual(self.h.report()["coverage"]["user_turns"], 0)

    def test_planner_responses_are_measured_as_assistant_output(self):
        self._parse([{"type": "PLANNER_RESPONSE", "content": "a b c d"}])
        self.assertEqual(self.h.assistant_word_counts, [4])

    def test_harness_is_recorded_on_the_quote(self):
        self._parse([{"type": "USER_INPUT", "source": "USER_EXPLICIT",
                      "content": "too long"}])
        self.assertEqual(self.h.quotes[0]["harness"], "antigravity")


class TestOtherParsers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.h = H.Harvest()

    def test_gemini_cli_reads_a_message_list(self):
        (self.tmp / "s").mkdir(parents=True)
        (self.tmp / "s" / "chat.json").write_text(json.dumps({"messages": [
            {"role": "model", "content": "a b c"},
            {"role": "user", "content": "too long"},
        ]}), encoding="utf-8")
        self.h.parse_gemini_cli(self.tmp)
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)
        self.assertEqual(self.h.response_words_at_complaint, [3])

    def test_gemini_cli_ignores_unrelated_json(self):
        (self.tmp / "settings.json").write_text('{"theme": "dark"}',
                                                encoding="utf-8")
        self.assertEqual(self.h.parse_gemini_cli(self.tmp), 0)

    def test_cline_reads_user_feedback_only(self):
        task = self.tmp / "1700000000000"
        task.mkdir(parents=True)
        task.joinpath("ui_messages.json").write_text(json.dumps([
            {"type": "say", "say": "text", "text": "one two"},
            {"type": "say", "say": "user_feedback", "text": "too long"},
            {"type": "ask", "ask": "followup", "text": "shorten this?"},
        ]), encoding="utf-8")
        self.h.parse_cline(self.tmp, "cline")
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)
        self.assertEqual(self.h.report()["coverage"]["user_turns"], 1)

    def test_aider_chat_transcript_pairs_input_with_the_reply(self):
        chat = self.tmp / ".aider.chat.history.md"
        chat.write_text(
            "# aider chat started at 2026-09-20 10:00:00\n"
            "> Added app.py to the chat.\n"
            "#### refactor the upload call\n"
            "one two three four\n"
            "#### that was too long\n", encoding="utf-8")
        self.assertEqual(self.h.parse_aider(chat), 1)
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)
        self.assertEqual(self.h.response_words_at_complaint, [4])
        self.assertEqual(self.h.quotes[0]["harness"], "aider")

    def test_a_corrupt_file_is_skipped_rather_than_fatal(self):
        task = self.tmp / "t"
        task.mkdir(parents=True)
        task.joinpath("ui_messages.json").write_text("{not json",
                                                     encoding="utf-8")
        self.assertEqual(self.h.parse_cline(self.tmp, "cline"), 0)

    def test_cursor_db_in_hash_directory_is_read_without_creating_stray_files(self):
        db_dir = self.tmp / "c#" / "globalStorage"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "state.vscdb"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
            conn.execute(
                "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                ("workbench.panel.aichat.view", json.dumps({
                    "tabs": [{"bubbles": [
                        {"type": 1, "text": "that response was way too long, shorten it"}
                    ]}]
                })),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(self.h.parse_cursor(self.tmp), 1)
        self.assertEqual(self.h.signal_counts["length_complaint"], 1)
        self.assertFalse((self.tmp / "c").exists())

    def test_cursor_db_with_only_layout_keys_counts_zero_sessions(self):
        db_path = self.tmp / "globalStorage" / "state.vscdb"
        db_path.parent.mkdir(parents=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
            conn.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                         ("workbench.panel.chat.hidden", "{}"))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.h.parse_cursor(self.tmp), 0)

    def test_aider_input_comments_do_not_leak_into_when(self):
        hist = self.tmp / ".aider.history"
        hist.write_text(
            "# leak@example.com\n"
            "that was too long\n"
            "# 2026-09-20 10:00:01.123456\n"
            "+cut it down\n",
            encoding="utf-8",
        )
        self.assertEqual(self.h.parse_aider(hist), 1)
        quotes = self.h.report()["quotes"]
        self.assertEqual(len(quotes), 2)
        self.assertNotIn("when", quotes[0])
        self.assertEqual(quotes[1].get("when"), "2026-09-20")
        self.assertNotIn("leak", json.dumps(self.h.report()))

    def test_numeric_epoch_and_gemini_session_timestamps_work_with_since(self):
        chats = self.tmp / "proj" / "chats"
        chats.mkdir(parents=True)
        (chats / "old-session.json").write_text(json.dumps({
            "startTime": "2025-08-01T10:00:00Z",
            "messages": [{"role": "user", "content": "too long"}],
        }), encoding="utf-8")
        (chats / "new-session.json").write_text(json.dumps({
            "startTime": "2026-09-15T10:00:00Z",
            "messages": [{"role": "user", "content": "too long"}],
        }), encoding="utf-8")
        jsonl(chats / "epochs.jsonl", [
            {"role": "user", "timestamp": 1755734400, "content": "too long"},
            {"role": "user", "timestamp": 1789900800000, "content": "cut it down"},
        ])
        h = H.Harvest(since="2026-09-01")
        self.assertEqual(h.parse_gemini_cli(self.tmp), 3)
        self.assertEqual(h.report()["coverage"]["user_turns"], 2)

    def test_empty_transcripts_yield_zero_sessions(self):
        jsonl(self.tmp / "ag" / "transcript.jsonl", [
            {"type": "USER_INPUT", "source": "SYSTEM", "content": "ignored"},
            {"type": "USER_INPUT", "source": "USER_EXPLICIT",
             "content": "<USER_REQUEST>   </USER_REQUEST>"},
        ])
        self.assertEqual(self.h.parse_antigravity(self.tmp / "ag"), 0)

        (self.tmp / "gem").mkdir()
        (self.tmp / "gem" / "empty.json").write_text('{"messages": []}', encoding="utf-8")
        self.assertEqual(self.h.parse_gemini_cli(self.tmp / "gem"), 0)

        (self.tmp / "cline" / "t1").mkdir(parents=True)
        (self.tmp / "cline" / "t1" / "ui_messages.json").write_text("[]", encoding="utf-8")
        self.assertEqual(self.h.parse_cline(self.tmp / "cline", "cline"), 0)


class TestSourceRoots(unittest.TestCase):
    def test_every_harness_lists_at_least_one_candidate(self):
        for harness, paths in H.source_roots().items():
            self.assertTrue(paths, harness)
            for path in paths:
                self.assertTrue(path.is_absolute(), f"{harness}: {path}")

    def test_antigravity_layouts_are_all_probed(self):
        """The directory moved between releases; missing one silently yields
        an empty harvest that looks like 'this user has no opinions'."""
        self.assertGreaterEqual(len(H.source_roots()["antigravity"]), 3)

    def test_run_records_a_status_for_every_harness(self):
        h = H.Harvest().run(wanted={"cline"})
        self.assertEqual(set(h.sources), {"cline"})
        self.assertIn(h.sources["cline"]["status"],
                      ("read", "empty", "not-found"))


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_unknown_source_is_rejected(self):
        self.assertEqual(H.main(["--sources", "notepad"]), 2)

    def test_list_sources_succeeds(self):
        self.assertEqual(H.main(["--list-sources"]), 0)

    def test_output_is_valid_json_with_the_expected_shape(self):
        out = self.tmp / "evidence.json"
        self.assertEqual(H.main(["--sources", "cline", "-o", str(out)]), 0)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(sorted(report),
                         ["coverage", "evidence_version", "generated",
                          "quotes", "signals", "sources", "stats",
                          "window_start"])

    def test_shipped_fixture_matches_the_live_report_shape(self):
        """The fixture is what the rubric and tests are written against; if
        the real output drifts from it, the documentation is now wrong."""
        out = self.tmp / "evidence.json"
        H.main(["--sources", "cline", "-o", str(out)])
        live = json.loads(out.read_text(encoding="utf-8"))
        fixture = json.loads(
            (SKILL_ROOT / "fixtures" / "evidence_sample.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(sorted(live), sorted(fixture))
        self.assertEqual(sorted(live["coverage"]), sorted(fixture["coverage"]))
        self.assertEqual(sorted(live["stats"]), sorted(fixture["stats"]))


if __name__ == "__main__":
    unittest.main()
