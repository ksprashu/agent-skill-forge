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

"""persona.py tests.

The properties that matter: an unconfigured machine stays neutral and fetches
nothing; a configured one clones once and refreshes at most daily; and the
script never overwrites a persona directory it didn't create. A local bare
repo stands in for the private GitHub repo, so no network is needed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "persona.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import persona as P  # noqa: E402

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
       "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]


def git(*args, cwd=None):
    subprocess.run(GIT + list(args), cwd=cwd, check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git is required")
class PersonaCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pdir = self.tmp / "personas"
        self.bare = self.tmp / "remote.git"
        self.work = self.tmp / "work"
        git("init", "--bare", "-q", str(self.bare))
        git("init", "-q", str(self.work))
        self.commit("Voice v1")
        git("push", "-q", str(self.bare), "HEAD:main", cwd=self.work)
        git("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.bare)

    def commit(self, text):
        (self.work / "default").mkdir(exist_ok=True)
        (self.work / "default" / P.PROFILE).write_text("# %s\n" % text)
        (self.work / "default" / P.SAMPLES).write_text("# samples\n")
        git("add", "-A", cwd=self.work)
        git("commit", "-q", "-m", text, cwd=self.work)

    def cli(self, *args, repo=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AGENT_PERSONA_REPO", "AGENT_PERSONA_DIR")}
        env["AGENT_PERSONA_DIR"] = str(self.pdir)
        env["HOME"] = str(self.tmp)
        if repo:
            env["AGENT_PERSONA_REPO"] = repo
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                              capture_output=True, text=True, env=env, timeout=60)

    def profile_text(self):
        return (self.pdir / "default" / P.PROFILE).read_text()

    def test_unconfigured_machine_stays_neutral_and_fetches_nothing(self):
        r = self.cli("pull")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("AGENT_PERSONA_REPO is not set", r.stdout)
        self.assertIn("tier 3", r.stdout)
        self.assertFalse(self.pdir.exists())

    def test_pull_clones_then_resolves_tier_2_with_samples(self):
        r = self.cli("pull", repo=str(self.bare))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("cloned", r.stdout)
        self.assertIn("tier 2", r.stdout)
        self.assertIn(P.SAMPLES, r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v1\n")

    def test_pull_is_throttled_to_once_a_day_unless_forced(self):
        self.cli("pull", repo=str(self.bare))
        self.commit("Voice v2")
        git("push", "-q", str(self.bare), "HEAD:main", cwd=self.work)

        r = self.cli("pull", repo=str(self.bare))
        self.assertIn("up to date", r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v1\n")

        r = self.cli("pull", "--force", repo=str(self.bare))
        self.assertIn("pulled", r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v2\n")

    def test_stale_stamp_triggers_a_pull(self):
        self.cli("pull", repo=str(self.bare))
        self.commit("Voice v2")
        git("push", "-q", str(self.bare), "HEAD:main", cwd=self.work)
        stamp = self.pdir / ".git" / P.STAMP
        old = time.time() - P.PULL_INTERVAL - 60
        os.utime(stamp, (old, old))
        r = self.cli("pull", repo=str(self.bare))
        self.assertIn("pulled", r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v2\n")

    def test_never_clobbers_a_hand_made_persona_dir(self):
        (self.pdir / "default").mkdir(parents=True)
        (self.pdir / "default" / P.PROFILE).write_text("# mine\n")
        r = self.cli("pull", repo=str(self.bare))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("leaving it alone", r.stdout)
        self.assertFalse((self.pdir / ".git").exists())
        self.assertEqual(self.profile_text(), "# mine\n")

    def test_failed_clone_exits_2(self):
        r = self.cli("pull", repo=str(self.tmp / "missing.git"))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("clone of", r.stdout)

    def test_failed_pull_keeps_the_local_copy(self):
        self.cli("pull", repo=str(self.bare))
        shutil.rmtree(self.bare)
        r = self.cli("pull", "--force", repo=str(self.bare))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("using the local copy", r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v1\n")

    def test_failed_pull_is_retried_on_the_next_run(self):
        self.cli("pull", repo=str(self.bare))
        stamp = self.pdir / ".git" / P.STAMP
        old = time.time() - P.PULL_INTERVAL - 60
        os.utime(stamp, (old, old))
        moved = self.tmp / "moved.git"
        self.bare.rename(moved)
        r = self.cli("pull", repo=str(self.bare))
        self.assertIn("using the local copy", r.stdout)
        self.assertLess(stamp.stat().st_mtime, time.time() - P.PULL_INTERVAL)
        moved.rename(self.bare)
        self.commit("Voice v2")
        git("push", "-q", str(self.bare), "HEAD:main", cwd=self.work)
        r = self.cli("pull", repo=str(self.bare))
        self.assertIn("pulled", r.stdout)
        self.assertEqual(self.profile_text(), "# Voice v2\n")

    def test_option_like_repo_is_refused(self):
        r = self.cli("pull", repo="--upload-pack=touch /tmp/x")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("must not start with '-'", r.stdout)
        self.assertFalse(self.pdir.exists())

    def test_missing_named_profile_exits_2(self):
        self.cli("pull", repo=str(self.bare))
        r = self.cli("status", "--name", "work")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stdout)

    def test_name_cannot_escape_the_persona_dir(self):
        r = self.cli("status", "--name", "..")
        self.assertEqual(r.returncode, 2)

    def test_status_reports_reader_and_characters_packs_when_present(self):
        self.cli("pull", repo=str(self.bare))
        r0 = self.cli("status")
        self.assertIn("reader_pack: (none)", r0.stdout)
        self.assertIn("characters_pack: (none)", r0.stdout)

        reader_file = self.pdir / "default" / "reader" / "profile.json"
        chars_file = self.pdir / "default" / "characters" / "characters.json"
        reader_file.parent.mkdir(parents=True, exist_ok=True)
        chars_file.parent.mkdir(parents=True, exist_ok=True)
        reader_file.write_text('{"schema_version": 1}\n')
        chars_file.write_text('{"companion_theme": "Pip", "characters": []}\n')

        r1 = self.cli("status")
        self.assertEqual(r1.returncode, 0)
        self.assertIn(f"reader_pack: {reader_file}", r1.stdout)
        self.assertIn(f"characters_pack: {chars_file}", r1.stdout)

    def test_activate_links_rules_and_skills_overlays(self):
        (self.work / "rules").mkdir(exist_ok=True)
        (self.work / "rules" / "persona-response.md").write_text("# reader rule\n")
        (self.work / "skills" / "custom-helper").mkdir(parents=True, exist_ok=True)
        (self.work / "skills" / "custom-helper" / "SKILL.md").write_text("---\nname: custom-helper\ndescription: x\n---\n")
        git("add", "-A", cwd=self.work)
        git("commit", "-q", "-m", "Add overlays", cwd=self.work)
        git("push", "-q", str(self.bare), "HEAD:main", cwd=self.work)

        for parent in (
            self.tmp / ".gemini" / "config",
            self.tmp / ".gemini" / "antigravity-cli",
            self.tmp / ".claude",
            self.tmp / ".agents",
            self.tmp / ".codex",
        ):
            parent.mkdir(parents=True, exist_ok=True)
        r = self.cli("pull", repo=str(self.bare))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.tmp / ".gemini" / "config" / "rules" / "persona-response.md").is_file())
        self.assertTrue((self.tmp / ".gemini" / "antigravity-cli" / "rules" / "persona-response.md").is_file())
        for sroot in (
            self.tmp / ".gemini" / "config" / "skills",
            self.tmp / ".gemini" / "skills",
            self.tmp / ".gemini" / "antigravity-cli" / "skills",
            self.tmp / ".claude" / "skills",
            self.tmp / ".agents" / "skills",
            self.tmp / ".codex" / "skills",
        ):
            self.assertTrue((sroot / "custom-helper" / "SKILL.md").is_file(), str(sroot))

        r_act = self.cli("activate")
        self.assertEqual(r_act.returncode, 0, r_act.stdout + r_act.stderr)
        self.assertRegex(r_act.stdout, r"activated: [1-9]")


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = self.tmp / "skill"
        (self.skill / "references").mkdir(parents=True)
        (self.skill / "references" / "voice_and_tone.template.md").write_text("t")
        self.pdir = self.tmp / "personas"
        (self.pdir / "default").mkdir(parents=True)
        (self.pdir / "default" / P.PROFILE).write_text("p")

    def test_local_override_wins_for_default_only(self):
        local = self.skill / "references" / "voice_and_tone.local.md"
        local.write_text("l")
        self.assertEqual(P.resolve(self.skill, self.pdir)[:2], (1, local))
        (self.pdir / "work").mkdir()
        (self.pdir / "work" / P.PROFILE).write_text("w")
        self.assertEqual(P.resolve(self.skill, self.pdir, "work")[0], 2)

    def test_samples_only_when_present(self):
        self.assertIsNone(P.resolve(self.skill, self.pdir)[2])
        (self.pdir / "default" / P.SAMPLES).write_text("s")
        self.assertEqual(P.resolve(self.skill, self.pdir)[2],
                         self.pdir / "default" / P.SAMPLES)

    def test_owner_name_uses_github(self):
        cmd = P._clone_cmd("someone/persona", self.tmp / "x")
        self.assertTrue(cmd[0] == "gh" or "https://github.com/someone/persona.git" in cmd)

    def test_git_clone_ends_options_before_the_source(self):
        cmd = P._clone_cmd(str(self.tmp / "remote.git"), "-dest")
        self.assertEqual(cmd[:4], ["git", "clone", "--quiet", "--"])
        self.assertTrue(Path(cmd[-1]).is_absolute())

    def test_owner_name_cannot_start_with_a_hyphen(self):
        self.assertIsNone(P.OWNER_NAME.match("-o/persona"))
        self.assertIsNone(P.OWNER_NAME.match("someone/-persona"))
        self.assertIsNone(P._clone_cmd("-o/persona", self.tmp / "x"))

    def test_harness_skill_dirs_match_harnesses_json(self):
        repo = SKILL_ROOT.parents[1]
        data = json.loads((repo / "config" / "harnesses.json").read_text(encoding="utf-8"))
        expected = []
        for harness in data["harnesses"].values():
            for raw in harness.get("skills_dirs", []):
                if raw.startswith("~/"):
                    expected.append(raw[2:])
        self.assertCountEqual(P.HARNESS_SKILL_DIRS, expected)

    def test_activate_skips_harnesses_that_are_not_installed(self):
        home = self.tmp / "home"
        pdir = self.tmp / "persona"
        skill = pdir / "skills" / "custom-helper"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("v1\n", encoding="utf-8")
        (home / ".claude").mkdir(parents=True)
        linked = P.activate_overlays(pdir, home=home)
        self.assertTrue((home / ".claude" / "skills" / "custom-helper" / "SKILL.md").is_file())
        self.assertTrue(linked)
        for absent in (".codex", ".agents", ".gemini"):
            self.assertFalse((home / absent).exists(), absent)

    def test_copy_fallback_refreshes_and_does_not_clobber_foreign_files(self):
        home = self.tmp / "home"
        pdir = self.tmp / "persona"
        rule = pdir / "rules" / "persona-response.md"
        rule.parent.mkdir(parents=True)
        rule.write_text("# v1\n", encoding="utf-8")
        skill = pdir / "skills" / "custom-helper"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("v1\n", encoding="utf-8")
        (home / ".gemini").mkdir(parents=True)
        foreign_skill = home / ".claude" / "skills" / "kept"
        foreign_skill.mkdir(parents=True)
        (foreign_skill / "SKILL.md").write_text("mine\n", encoding="utf-8")
        (pdir / "skills" / "kept").mkdir()
        (pdir / "skills" / "kept" / "SKILL.md").write_text("theirs\n", encoding="utf-8")

        def no_symlink(*_args, **_kwargs):
            raise OSError("symlinks disabled")

        with mock.patch.object(P.os, "symlink", no_symlink):
            first = P.activate_overlays(pdir, home=home)
            self.assertTrue(first)
            copied = home / ".claude" / "skills" / "custom-helper" / "SKILL.md"
            self.assertEqual(copied.read_text(encoding="utf-8"), "v1\n")
            self.assertTrue((copied.parent / P.OWNED_DIR_MARKER).is_file())
            self.assertEqual((foreign_skill / "SKILL.md").read_text(encoding="utf-8"), "mine\n")
            rule_copy = home / ".gemini" / "config" / "rules" / "persona-response.md"
            self.assertEqual(rule_copy.read_text(encoding="utf-8"), "# v1\n")

            (skill / "SKILL.md").write_text("v2\n", encoding="utf-8")
            rule.write_text("# v2\n", encoding="utf-8")
            second = P.activate_overlays(pdir, home=home)
            self.assertTrue(any(p.name == "custom-helper" for p in second))
            self.assertEqual(copied.read_text(encoding="utf-8"), "v2\n")
            self.assertEqual(rule_copy.read_text(encoding="utf-8"), "# v2\n")
            self.assertEqual((foreign_skill / "SKILL.md").read_text(encoding="utf-8"), "mine\n")
            self.assertFalse((home / ".codex").exists())
            self.assertFalse((home / ".agents").exists())

    def test_rules_are_not_written_into_a_harness_that_is_not_installed(self):
        home = self.tmp / "home"
        pdir = self.tmp / "persona"
        rule = pdir / "rules" / "persona-response.md"
        rule.parent.mkdir(parents=True)
        rule.write_text("# rule\n", encoding="utf-8")
        P.activate_overlays(pdir, home=home)
        self.assertFalse((home / ".gemini").exists())
        self.assertFalse(home.exists())

    def test_activate_without_a_voice_profile_still_exits_0(self):
        pdir = self.tmp / "overlays-only"
        (pdir / "skills" / "helper").mkdir(parents=True)
        (pdir / "skills" / "helper" / "SKILL.md").write_text("hi\n", encoding="utf-8")
        (self.tmp / ".claude").mkdir()
        env = {k: v for k, v in os.environ.items()
               if k not in ("AGENT_PERSONA_REPO", "AGENT_PERSONA_DIR")}
        env["AGENT_PERSONA_DIR"] = str(pdir)
        env["HOME"] = str(self.tmp)
        run = lambda: subprocess.run(
            [sys.executable, str(SCRIPT), "activate"],
            capture_output=True, text=True, env=env, timeout=30)
        first = run()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("tier 3", first.stdout)
        self.assertRegex(first.stdout, r"activated: [1-9]")
        second = run()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertRegex(second.stdout, r"activated: [1-9]")

    def test_directory_links_use_createjunction_not_mklink(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("mklink", source)
        self.assertIn("CreateJunction", source)


if __name__ == "__main__":
    unittest.main()
