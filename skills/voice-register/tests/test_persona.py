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

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

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

    def test_missing_named_profile_exits_2(self):
        self.cli("pull", repo=str(self.bare))
        r = self.cli("status", "--name", "work")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stdout)

    def test_name_cannot_escape_the_persona_dir(self):
        r = self.cli("status", "--name", "..")
        self.assertEqual(r.returncode, 2)


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


if __name__ == "__main__":
    unittest.main()
