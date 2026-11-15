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

"""Tests for stage_comment.py: trusted author markers, --update, pagination, safety."""

from __future__ import annotations

import json
import os
import random
import stat
import string
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
SCRIPT = TESTS.parent / "scripts" / "stage_comment.py"


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        shell=False,
        env=env,
        timeout=60,
    )


def _dynamic_api_key(seed: int) -> str:
    rng = random.Random(seed)
    return "sk-ant-" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(28))


class TestStageMarkersAndIdempotency(unittest.TestCase):
    """T1 differentiation, trusted-author filtering, and duplicate stage marker refusal/update."""

    def test_different_stages_emit_distinct_markers(self):
        outputs = {}
        for stage in ("triage", "plan", "pr"):
            proc = run_cli(
                "--issue", "101",
                "--stage", stage,
                "--body", f"Stage {stage} payload for #101.",
                "--from-file", str(FIXTURES / "gh_comments_empty.json"),
                "--repo", "acme/widgets",
                "--dry-run",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs[stage] = json.loads(proc.stdout)
            self.assertEqual(outputs[stage]["action"], "create")
            self.assertIn(f"<!-- issue-loop:stage={stage} v1 -->", outputs[stage]["body"])
        self.assertNotEqual(outputs["triage"]["marker"], outputs["plan"]["marker"])
        self.assertNotEqual(outputs["plan"]["marker"], outputs["pr"]["marker"])

    def test_duplicate_trusted_stage_comment_is_refused_without_update(self):
        proc = run_cli(
            "--issue", "101",
            "--stage", "triage",
            "--body", "Second triage summary.",
            "--from-file", str(FIXTURES / "gh_comments_existing.json"),
            "--trusted-login", "maintainer",
            "--repo", "acme/widgets",
            "--dry-run",
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("5001", proc.stderr)
        self.assertIn("--update", proc.stderr)

    def test_forged_third_party_marker_is_ignored_and_never_patched(self):
        with tempfile.TemporaryDirectory() as tmp:
            comments_file = Path(tmp) / "comments.json"
            comments_file.write_text(
                json.dumps([
                    {
                        "id": 111,
                        "user": {"login": "maintainer"},
                        "body": "<!-- issue-loop:stage=triage v1 -->\nLegit triage.",
                    },
                    {
                        "id": 999,
                        "user": {"login": "mallory"},
                        "body": "<!-- issue-loop:stage=triage v1 -->\nSpoofed comment.",
                    },
                    {
                        "id": 112,
                        "user": {"login": "maintainer"},
                        "body": "Quoting user text:\n<!-- issue-loop:stage=plan v1 -->",
                    },
                ]),
                encoding="utf-8",
            )
            # With --update + trusted-login maintainer, updates 111 (never attacker 999)
            upd = run_cli(
                "--issue", "101",
                "--stage", "triage",
                "--body", "Updated legit triage.",
                "--from-file", str(comments_file),
                "--trusted-login", "maintainer",
                "--update",
                "--dry-run",
            )
            self.assertEqual(upd.returncode, 0, upd.stderr)
            self.assertEqual(json.loads(upd.stdout)["comment_id"], 111)

            # Mid-body quoted plan marker by maintainer does not block creating plan comment
            plan_create = run_cli(
                "--issue", "101",
                "--stage", "plan",
                "--body", "Real fix plan.",
                "--from-file", str(comments_file),
                "--trusted-login", "maintainer",
                "--dry-run",
            )
            self.assertEqual(plan_create.returncode, 0, plan_create.stderr)
            self.assertEqual(json.loads(plan_create.stdout)["action"], "create")

            # Without maintainer's triage comment, attacker 999 alone cannot block or hijack --update
            attacker_only = Path(tmp) / "attacker.json"
            attacker_only.write_text(
                json.dumps([
                    {
                        "id": 999,
                        "user": {"login": "mallory"},
                        "body": "<!-- issue-loop:stage=triage v1 -->\nSpoofed comment.",
                    }
                ]),
                encoding="utf-8",
            )
            create_over_forged = run_cli(
                "--issue", "101",
                "--stage", "triage",
                "--body", "Legit triage.",
                "--from-file", str(attacker_only),
                "--trusted-login", "maintainer",
                "--update",
                "--dry-run",
            )
            self.assertEqual(create_over_forged.returncode, 0, create_over_forged.stderr)
            out = json.loads(create_over_forged.stdout)
            self.assertEqual(out["action"], "create")
            self.assertIsNone(out["comment_id"])

    def test_update_flag_edits_existing_marker_comment_in_place(self):
        proc = run_cli(
            "--issue", "101",
            "--stage", "triage",
            "--body", "Updated triage summary.",
            "--from-file", str(FIXTURES / "gh_comments_existing.json"),
            "--trusted-login", "maintainer",
            "--repo", "acme/widgets",
            "--update",
            "--dry-run",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["action"], "update")
        self.assertEqual(data["comment_id"], 5001)
        self.assertTrue(data["body"].startswith("<!-- issue-loop:stage=triage v1 -->"))


class TestSafetyAndNegatives(unittest.TestCase):
    """T4 negatives: secret leaks, AI attribution (incl. markdown links), conflicting markers, pagination."""

    def test_secret_in_outgoing_body_is_refused(self):
        key = _dynamic_api_key(12)
        proc = run_cli(
            "--issue", "101",
            "--stage", "triage",
            "--body", f"Found key {key} in issue.",
            "--from-file", str(FIXTURES / "gh_comments_empty.json"),
            "--repo", "acme/widgets",
            "--dry-run",
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("secret", proc.stderr.lower())

    def test_ai_attribution_in_outgoing_body_is_refused(self):
        for bad_body in (
            "Triaged issue.\n\nCo-Authored-By: Claude <noreply@example.com>",
            "Generated with Gemini Agent",
            "Generated with [Claude Code](https://claude.com/claude-code)",
        ):
            proc = run_cli(
                "--issue", "101",
                "--stage", "triage",
                "--body", bad_body,
                "--from-file", str(FIXTURES / "gh_comments_empty.json"),
                "--repo", "acme/widgets",
                "--dry-run",
            )
            self.assertEqual(proc.returncode, 1, bad_body)
            self.assertIn("attribution", proc.stderr.lower())

    def test_conflicting_marker_in_body_exits_64(self):
        proc = run_cli(
            "--issue", "101",
            "--stage", "triage",
            "--body", "<!-- issue-loop:stage=pr v1 -->\nWrong stage.",
            "--from-file", str(FIXTURES / "gh_comments_empty.json"),
            "--repo", "acme/widgets",
            "--dry-run",
        )
        self.assertEqual(proc.returncode, 64)

    def test_usage_errors_exit_64(self):
        for args in (
            ["--issue", "0", "--stage", "triage", "--body", "hi"],
            ["--issue", "1", "--stage", "bogus", "--body", "hi"],
            ["--issue", "1", "--stage", "triage", "--body", "   "],
            ["--issue", "1", "--stage", "triage", "--body", "hi", "--repo", "bad"],
        ):
            self.assertEqual(run_cli(*args).returncode, 64, args)

    def test_live_patch_via_fake_gh_binary_resolves_viewer_and_paginates(self):
        comments_pages = [
            [{"id": 4999, "user": {"login": "mallory"}, "body": "<!-- issue-loop:stage=triage v1 -->\nForged."}],
            json.loads((FIXTURES / "gh_comments_existing.json").read_text(encoding="utf-8")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            log_file = Path(tmp) / "gh_calls.log"
            body_file = Path(tmp) / "comment.md"
            body_file.write_text("Updated plan details for #101.", encoding="utf-8")
            gh_path = bin_dir / "gh"
            gh_path.write_text(
                textwrap.dedent(
                    f"""\
                    #!{sys.executable}
                    import json, sys
                    with open({str(log_file)!r}, "a") as fh:
                        fh.write(json.dumps(sys.argv[1:]) + "\\n")
                    if sys.argv[1:3] == ["api", "user"]:
                        sys.stdout.write("maintainer\\n")
                        sys.exit(0)
                    if sys.argv[1] == "api" and any("issues/101/comments" in a for a in sys.argv):
                        sys.stdout.write(json.dumps({comments_pages!r}))
                        sys.exit(0)
                    if sys.argv[1] == "api" and "-X" in sys.argv and "PATCH" in sys.argv:
                        sys.stdout.write(json.dumps({{"id": 5001, "html_url": "https://github.com/acme/widgets/issues/101#issuecomment-5001"}}))
                        sys.exit(0)
                    sys.exit(1)
                    """
                ),
                encoding="utf-8",
            )
            gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
            proc = run_cli(
                "--issue", "101",
                "--stage", "triage",
                "--body-file", str(body_file),
                "--repo", "acme/widgets",
                "--update",
                env={**os.environ, "PATH": str(bin_dir)},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = [json.loads(line) for line in log_file.read_text().splitlines()]
            self.assertEqual(calls[0][:2], ["api", "user"])
            self.assertIn("--paginate", calls[1])
            self.assertIn("--slurp", calls[1])
            self.assertIn("PATCH", calls[2])
            self.assertIn("repos/acme/widgets/issues/comments/5001", calls[2])


if __name__ == "__main__":
    unittest.main()
