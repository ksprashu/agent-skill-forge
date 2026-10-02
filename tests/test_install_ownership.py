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

"""Tests that ``--prune`` only ever deletes things this repo installed.

The five global hubs are shared. creative-stack registers its own source
directory in the same ``skills.json`` files and installs into the same
``~/.agents/skills``, so an entry whose name we do not recognise means another
owner, not a stale install of ours. Pruning by name deleted creative-stack's
skills; pruning by destination does not.

The guard that was in place tested ``is_link(p) and os.path.exists(p)``, which
reads as if it covers this and does not. Three cases walked straight past it
into ``shutil.rmtree``, and each has a test here:

* a foreign skill stored as a real directory rather than a link
* a foreign link whose target is temporarily unreachable (an unmounted volume,
  a repo on an external disk) — indistinguishable from one of our own broken
  links once ``os.path.exists`` is the only question asked
* a Windows junction on Python < 3.12, where ``os.path.islink`` returns False
  and ``shutil.rmtree`` follows the junction into the source repo

The third is the expensive one: it does not leave a wrong directory behind, it
deletes somebody's checkout.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC = str(REPO_ROOT / "scripts" / "sync_skills.py")

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_skills  # noqa: E402


def isolated_env(home: Path) -> dict:
    """Environment for a sync_skills.py subprocess that cannot reach the real hubs.

    Every hub path is ``~``-relative and expanded at run time, so pointing both
    variables at a scratch directory confines the whole run — links, copies,
    prunes and the skills.json registries — to it. A run without this installs
    into, and with --prune deletes from, the contributor's own home.
    """
    return dict(os.environ, HOME=str(home), USERPROFILE=str(home))


def write_skill(directory: Path, name: str) -> Path:
    """Create a plausible skill directory, the way another repo would."""
    path = directory / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")
    return path


class ForeignEntriesSurvivePrune(unittest.TestCase):
    """Anything we cannot prove we installed is left alone."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="forge_ownership_"))
        self.hub = self.tmp / "hub"
        self.hub.mkdir()
        self.foreign_src = self.tmp / "creative-stack"
        self.foreign_src.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def prune(self):
        sync_skills.clean_stale_and_orphan_links(str(self.hub), allowed_skills={}, prune=True)

    def test_foreign_real_directory_is_not_deleted(self):
        """A --copy install belonging to another repo carries no marker of ours."""
        victim = write_skill(self.hub, "unfamiliar-skill")
        self.prune()
        self.assertTrue(
            victim.is_dir(),
            "a real directory we did not install was deleted by --prune",
        )
        self.assertTrue((victim / "SKILL.md").exists())

    def test_foreign_symlink_with_unreachable_target_is_not_deleted(self):
        """Reads as BROKEN under a link-only check; readlink still names the owner."""
        link = self.hub / "offline-skill"
        unreachable = self.tmp / "not-mounted" / "offline-skill"
        os.symlink(unreachable, link)
        self.assertFalse(os.path.exists(link), "precondition: target must be unreachable")

        self.prune()
        self.assertTrue(
            os.path.lexists(link),
            "a dangling link pointing outside this repo was pruned as one of ours",
        )

    def test_our_own_dangling_link_is_still_pruned(self):
        """The guard must not become a blanket amnesty for broken links."""
        gone = REPO_ROOT / "skills" / "definitely-not-a-real-skill"
        link = self.hub / "definitely-not-a-real-skill"
        os.symlink(gone, link)
        self.assertFalse(os.path.exists(link), "precondition: target must not exist")

        self.prune()
        self.assertFalse(
            os.path.lexists(link),
            "a dangling link into our own repo should still be cleaned up",
        )

    def test_link_into_this_repo_is_recognised_as_ours(self):
        real = REPO_ROOT / "skills"
        link = self.hub / "ours"
        os.symlink(real, link)
        self.assertTrue(sync_skills.is_forge_owned(str(link)))

    def test_our_link_through_a_symlinked_parent_is_still_ours(self):
        """Ownership compares canonical paths, not the spelling of the link.

        The destination we write is whatever path the installer was invoked
        with, which need not be canonical — /tmp is a symlink to /private/tmp
        on macOS, and a checkout reached through any symlinked parent has the
        same shape. Comparing the unresolved destination alone would read our
        own link as foreign, never prune it, and let stale links accumulate
        forever.
        """
        indirect = Path(tempfile.mkdtemp(dir=self.tmp, prefix="alias_")) / "repo"
        os.symlink(REPO_ROOT, indirect)
        link = self.hub / "ours-via-alias"
        os.symlink(indirect / "skills", link)

        self.assertNotEqual(
            str(sync_skills.link_destination(str(link))),
            str(REPO_ROOT / "skills"),
            "precondition: the destination must be a non-canonical spelling",
        )
        self.assertTrue(
            sync_skills.is_forge_owned(str(link)),
            "a link into this repo by a non-canonical path read as foreign",
        )

    def test_copy_install_is_marked_and_recognised(self):
        """--copy leaves no link to read, so create_link stamps a marker instead."""
        copied = write_skill(self.hub, "copied-skill")
        (copied / sync_skills.OWNER_MARKER).write_text("x\n", encoding="utf-8")
        self.assertTrue(sync_skills.is_forge_owned(str(copied)))

    def test_entries_we_did_not_install_are_not_claimed(self):
        """The counterpart the positive assertions need.

        `is_forge_owned` returning True unconditionally satisfies every
        positive case above, so on their own they cannot distinguish working
        detection from a degenerate yes. These are the cases that must come
        back False, stated at the same level rather than only implied by the
        prune behaviour further up.
        """
        unmarked = write_skill(self.hub, "someone-elses")
        self.assertFalse(sync_skills.is_forge_owned(str(unmarked)),
                         "an unmarked directory was claimed as ours")

        outward = self.hub / "points-away"
        os.symlink(self.foreign_src / "skill", outward)
        self.assertFalse(sync_skills.is_forge_owned(str(outward)),
                         "a link out of this repo was claimed as ours")

        loose = self.hub / "loose-file.md"
        loose.write_text("not a skill\n", encoding="utf-8")
        self.assertFalse(sync_skills.is_forge_owned(str(loose)),
                         "a plain file is neither a link nor a marked install")

    def test_reserved_names_are_purged_even_when_foreign(self):
        """Deliberate exception: a reserved name is broken for whoever owns it."""
        victim = write_skill(self.hub, "grill-me")
        self.prune()
        self.assertFalse(
            victim.exists(),
            "reserved-namespace entries are purged regardless of owner",
        )

    @unittest.skipUnless(sys.platform == "win32", "junctions are Windows-only")
    def test_junction_is_detected_without_isjunction(self):
        """os.path.isjunction is 3.12+; the reparse-point attribute is not.

        Without this, rmtree follows the junction and deletes the source repo
        it points at, not just the entry in the hub.
        """
        target = self.foreign_src / "linked"
        target.mkdir()
        (target / "keepme.txt").write_text("evidence", encoding="utf-8")
        junction = self.hub / "linked"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
            check=True, capture_output=True,
        )
        self.assertFalse(os.path.islink(str(junction)), "precondition: islink misses junctions")
        self.assertTrue(sync_skills.is_reparse_point(str(junction)))

        self.prune()
        self.assertTrue(
            (target / "keepme.txt").exists(),
            "prune followed a junction into the source repo and deleted its contents",
        )


class ReparseAttributeDecoding(unittest.TestCase):
    """The one part of the junction fix that does not need a Windows kernel.

    ``test_junction_is_detected_without_isjunction`` above is skipped off
    Windows, and the Tests CI matrix is ubuntu+macos, so today it runs
    nowhere. Rather than leave the whole fix resting on that, the fix is split
    where the platform dependency actually is.

    Whether ``shutil.rmtree`` follows a junction, and whether ``lstat`` sets
    the reparse bit on one, are Windows behaviours and are not tested here.
    Whether we *read* that bit correctly is arithmetic on an integer, and that
    is what ``has_reparse_attribute`` isolates — the test that decides, on
    Python 3.8-3.11 where ``os.path.isjunction`` does not exist, whether a
    junction is recognised before rmtree is reached.

    These cases use real stat results where one exists and a plain carrier
    object where the field cannot occur on this platform. That is not a
    substitute for the Windows test; it narrows what the Windows test is
    still the only evidence for.
    """

    class StatWithAttributes:
        """Carries st_file_attributes, which POSIX stat results never have."""

        def __init__(self, attributes):
            self.st_file_attributes = attributes

    def test_reparse_bit_is_recognised(self):
        """A junction's attributes: a directory that is also a reparse point."""
        st = self.StatWithAttributes(
            stat.FILE_ATTRIBUTE_DIRECTORY | stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
        self.assertTrue(
            sync_skills.has_reparse_attribute(st),
            "a junction read as an ordinary directory; rmtree would follow it",
        )

    def test_plain_directory_is_not_a_reparse_point(self):
        st = self.StatWithAttributes(stat.FILE_ATTRIBUTE_DIRECTORY)
        self.assertFalse(sync_skills.has_reparse_attribute(st))

    def test_other_attributes_do_not_trigger_it(self):
        """The mask must select one bit, not test the field for truthiness."""
        st = self.StatWithAttributes(
            stat.FILE_ATTRIBUTE_ARCHIVE | stat.FILE_ATTRIBUTE_READONLY
            | stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
        )
        self.assertFalse(sync_skills.has_reparse_attribute(st))

    @unittest.skipIf(sys.platform == "win32", "Windows stat results carry st_file_attributes")
    def test_a_real_posix_stat_result_is_handled(self):
        """st_file_attributes is absent here; that must not raise."""
        st = os.lstat(str(REPO_ROOT))
        self.assertFalse(hasattr(st, "st_file_attributes"),
                         "precondition: POSIX stat results lack the field")
        self.assertFalse(sync_skills.has_reparse_attribute(st))

    def test_posix_directories_and_links_classify_correctly(self):
        """End to end on this platform, through the real stdlib."""
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain"
            plain.mkdir()
            link = Path(tmp) / "link"
            os.symlink(plain, link)

            self.assertFalse(sync_skills.is_reparse_point(str(plain)))
            self.assertTrue(sync_skills.is_reparse_point(str(link)))

    def test_a_missing_path_is_not_a_reparse_point(self):
        self.assertFalse(sync_skills.is_reparse_point("/nonexistent/path/xyzzy"))


class UnresolvedSelectorsDoNotArmPrune(unittest.TestCase):
    """A typo must not turn --prune into "delete everything".

    strict_prune is armed by has_explicit_selection and scoped by the resolved
    allow-list. An unrecognised token used to set the flag while contributing
    nothing to the list, so ``--skills brainstrom --prune`` pruned against an
    allow-list matching nothing. It stays non-fatal — the installers already
    report unplaceable names — but it no longer counts as a selection.
    """

    def test_unknown_skill_name_is_reported_not_resolved(self):
        names, unknown = sync_skills.validate_skill_names("no-such-skill")
        self.assertEqual(unknown, ["no-such-skill"])
        self.assertEqual(names, ["no-such-skill"], "the name still reaches the reporter")

    def test_unknown_cluster_token_resolves_to_nothing(self):
        resolved, unknown = sync_skills.resolve_clusters_arg("c99")
        self.assertEqual(resolved, [])
        self.assertEqual(unknown, ["c99"])

    def test_known_selectors_still_resolve(self):
        resolved, unknown = sync_skills.resolve_clusters_arg("c3")
        self.assertEqual(unknown, [])
        self.assertTrue(resolved)

    def test_aliases_resolve_to_their_canonical_skill(self):
        """The sync installs an alias only alongside its canonical skill, so an
        alias left as-is selected nothing and still armed strict pruning."""
        names, unknown = sync_skills.validate_skill_names("prompt-writer")
        self.assertEqual(unknown, [])
        self.assertEqual(names, ["prompt"])

    def test_an_alias_and_its_canonical_name_select_once(self):
        names, _ = sync_skills.validate_skill_names("prompt, prompt-writer")
        self.assertEqual(names, ["prompt"])

    def test_typo_with_prune_exits_zero_and_warns(self):
        with tempfile.TemporaryDirectory() as home:
            proc = subprocess.run(
                [sys.executable, SYNC, "--skills", "brainstrom", "--prune"],
                capture_output=True, text=True, env=isolated_env(Path(home)),
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("brainstrom", proc.stderr)
        self.assertIn("default sweep", proc.stderr,
                      "an all-unresolved selection must say it is not pruning to empty")


class SyncAgainstAScratchHome(unittest.TestCase):
    """End to end through the CLI, with every hub under a temporary HOME."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="forge_home_"))
        self.hub = self.home / ".claude" / "skills"
        self.hub.mkdir(parents=True)
        self.elsewhere = self.home / "other-repo"

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def sync(self, *args):
        proc = subprocess.run([sys.executable, SYNC, *args], capture_output=True,
                              text=True, env=isolated_env(self.home))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def test_an_alias_selection_does_not_prune_its_own_skill(self):
        self.sync("--skills", "prompt", "--fix")
        installed = self.hub / "prompt"
        self.assertTrue(os.path.lexists(installed), "precondition: prompt was installed")

        self.sync("--skills", "prompt-writer", "--prune", "--fix")
        self.assertTrue(os.path.lexists(installed),
                        "selecting an alias pruned the skill it names")
        self.assertTrue(os.path.lexists(self.hub / "prompt-writer"),
                        "the alias itself should be installed alongside it")

    def test_a_foreign_directory_at_a_selected_name_survives_fix(self):
        for mode in ((), ("--copy",)):
            with self.subTest(mode=mode or "link"):
                victim = write_skill(self.hub, "prompt")
                out = self.sync("--skills", "prompt", "--fix", *mode)
                self.assertFalse(sync_skills.is_reparse_point(str(victim)),
                                 "a foreign directory was replaced with our link")
                self.assertFalse((victim / sync_skills.OWNER_MARKER).exists(),
                                 "a foreign directory was replaced with our copy")
                self.assertTrue((victim / "SKILL.md").exists())
                self.assertIn("[FOREIGN CONFLICT] prompt", out)
                shutil.rmtree(victim)

    def test_a_foreign_link_at_a_selected_name_is_not_repointed(self):
        foreign = write_skill(self.elsewhere, "prompt")
        for mode in ((), ("--copy",)):
            with self.subTest(mode=mode or "link"):
                link = self.hub / "prompt"
                os.symlink(foreign, link)
                self.sync("--skills", "prompt", "--fix", *mode)
                self.assertEqual(sync_skills.link_destination(str(link)), str(foreign),
                                 "a link owned by another repo was repointed or replaced")
                link.unlink()

    def test_our_own_misdirected_link_is_still_repointed(self):
        """The control: the guard must not freeze links this repo wrote."""
        link = self.hub / "prompt"
        os.symlink(REPO_ROOT / "skills" / "plan", link)
        self.assertTrue(sync_skills.is_forge_owned(str(link)), "precondition: ours")

        self.sync("--skills", "prompt", "--fix")
        self.assertTrue(os.path.realpath(link).endswith(os.sep + "prompt"),
                        f"our own link was left pointing at {os.path.realpath(link)}")


class CopiesAndLinksPruneAlike(unittest.TestCase):
    """A --copy install is the same skill stored differently; prune must agree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="forge_copies_"))
        self.hub = self.tmp / "hub"
        self.hub.mkdir()
        self.available = sync_skills.discover_all_skills()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, name, copy):
        target = self.hub / name
        canonical = sync_skills.ALIASES.get(name, name)
        sync_skills.create_link(self.available[canonical]["path"], str(target), copy_mode=copy)
        self.assertTrue(sync_skills.is_forge_owned(str(target)), "precondition: ours")
        self.assertEqual(sync_skills.is_reparse_point(str(target)), not copy,
                         "precondition: installed in the requested form")
        return target

    def prune(self, allowed, strict):
        sync_skills.clean_stale_and_orphan_links(
            str(self.hub), {n: self.available[n]["path"] for n in allowed},
            prune=True, strict_prune=strict)

    def test_an_explicitly_deselected_alias_is_removed(self):
        for copy in (False, True):
            with self.subTest(copy=copy):
                alias = self.install("prompt-writer", copy)
                self.prune(["plan"], strict=True)
                self.assertFalse(os.path.lexists(alias),
                                 "an alias survived an explicit selection that excludes it")

    def test_an_alias_of_a_selected_skill_is_kept(self):
        for copy in (False, True):
            with self.subTest(copy=copy):
                alias = self.install("prompt-writer", copy)
                self.prune(["prompt"], strict=True)
                self.assertTrue(os.path.lexists(alias))
                sync_skills.remove_path_or_link(str(alias))

    def test_plain_prune_keeps_an_available_skill_outside_the_selection(self):
        name = "performance-optimization"
        self.assertNotIn(name, sync_skills.CORE_SKILLS, "precondition: not a default skill")
        for copy in (False, True):
            with self.subTest(copy=copy):
                kept = self.install(name, copy)
                self.prune([], strict=False)
                self.assertTrue(os.path.lexists(kept),
                                "plain --prune removed an available skill it should keep")
                sync_skills.remove_path_or_link(str(kept))

    def test_plain_prune_still_removes_a_copy_of_a_retired_skill(self):
        """The control: the default sweep must not keep every marked copy."""
        retired = write_skill(self.hub, "a-skill-this-repo-retired")
        (retired / sync_skills.OWNER_MARKER).write_text("x\n", encoding="utf-8")
        self.prune([], strict=False)
        self.assertFalse(retired.exists())


@unittest.skipIf(sys.platform == "win32", "install.sh is the POSIX entry point")
class NonInteractiveInstallDoesNotPrune(unittest.TestCase):
    """The curl-pipe-bash and CI path must not delete on a flag nobody typed.

    Both installers passed --prune whenever stdin was not a tty. That is
    exactly the unattended path — the documented one-liner, and CI — so the
    removal ran where nobody was watching and nobody had consented to it.
    Combined with pruning by name, the advertised install command deleted
    skills the hub already held.

    This runs install.sh for real and intercepts at the python3 boundary with
    a recording shim on PATH, so the assertion is about the argv the script
    actually builds, not about its source text. Nothing touches the real home
    directory: the shim never executes sync_skills.py.
    """

    SHIM = "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$ARGV_LOG\"\nexit 0\n"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="forge_installer_"))
        self.log = self.tmp / "argv.log"
        shim = self.tmp / "python3"
        shim.write_text(self.SHIM, encoding="utf-8")
        shim.chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_installer(self, *args, stdin=subprocess.DEVNULL):
        env = dict(os.environ, PATH=f"{self.tmp}{os.pathsep}{os.environ['PATH']}",
                   ARGV_LOG=str(self.log))
        proc = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "install.sh"), "--no-fetch", *args],
            capture_output=True, text=True, env=env, stdin=stdin,
        )
        recorded = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        return proc, recorded

    def test_the_sync_is_invoked_at_all(self):
        """Guards the rest: an install that never calls sync trivially passes."""
        proc, recorded = self.run_installer()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("sync_skills.py", recorded)
        self.assertIn("--fix", recorded)

    def test_prune_is_not_passed_when_stdin_is_not_a_tty(self):
        _, recorded = self.run_installer()
        self.assertNotIn(
            "--prune", recorded,
            "the unattended install path armed pruning on its own",
        )

    def test_prune_is_still_honoured_when_asked_for(self):
        """Removing the default must not remove the capability."""
        _, recorded = self.run_installer("--prune")
        self.assertIn("--prune", recorded)

    def test_the_powershell_installer_matches(self):
        """install.ps1 has the same change and no equivalent test.

        There is no PowerShell on the machines that run this suite, and CI's
        Windows job only parse-checks the script — it never reaches the
        branch. So the behaviour cannot be asserted the way install.sh's is
        above, and this reads the source instead.

        That is a weaker check and is named as one: it would not catch the
        two scripts diverging in behaviour, only this flag reappearing. It is
        here because silence would read as coverage.
        """
        source = (REPO_ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
        non_interactive = source.split("} else {")[-1]
        self.assertIn("sync_skills.py", non_interactive,
                      "the branch this reads is no longer the one that syncs")
        self.assertNotIn("--prune", non_interactive)


class ClosureEngineUsesNoShell(unittest.TestCase):
    """Goal summaries are task-derived text and reached a shell string verbatim."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "skills" / "verify" / "scripts"))
        import ega_closure_engine  # noqa: E402
        self.engine = ega_closure_engine
        self.tmp = Path(tempfile.mkdtemp(prefix="forge_closure_"))
        # Nothing is inherited from the contributor's git config: signing is
        # off locally (a global commit.gpgsign with no usable key fails the
        # seed commit), and the branch is set rather than left to
        # init.defaultBranch, which the protected-branch test depends on.
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        for setting in (["symbolic-ref", "HEAD", "refs/heads/main"],
                        ["config", "user.email", "t@example.com"],
                        ["config", "user.name", "Test"],
                        ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git", "-C", str(self.tmp), *setting], check=True)
        (self.tmp / "seed.txt").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.tmp), "add", "seed.txt"], check=True)
        subprocess.run(["git", "-C", str(self.tmp), "commit", "-qm", "seed"], check=True)

        # A real remote, so "nothing was pushed" cannot pass merely because
        # there was nowhere to push to. Without this the protected-branch
        # refusal and the no-remote path return the same value, and a test
        # asserting on it holds even with the refusal deleted.
        self.remote = self.tmp.parent / (self.tmp.name + "-remote.git")
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(
            ["git", "-C", str(self.tmp), "remote", "add", "origin", str(self.remote)],
            check=True,
        )

    def remote_commit_count(self):
        out, _, _ = self.engine.run_cmd(
            ["git", "-C", str(self.remote), "rev-list", "--all", "--count"]
        )
        return int(out or 0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.remote, ignore_errors=True)

    def assert_payload_is_inert(self, payload, literal):
        """Run a closure whose goal summary is a shell payload, and prove inertness.

        Two things here are load-bearing, both learned by reverting the fix
        and watching how the test died.

        The canary is checked before the return value. A payload that merely
        breaks quoting also fails the commit, and asserting success first
        reports that as if it were the injection being stopped — a death for
        the wrong reason. Together the two assertions say what is meant:
        nothing executed, and the commit still worked.

        The payload is relative, and short. ``clean_goal`` truncates at 60
        characters, so an absolute canary path under a tempdir pushed the
        closing delimiter off the end and the payload became a syntax error
        rather than an exploit. run_cmd runs with cwd=repo_dir, so a bare
        filename lands in the repo either way.
        """
        canary = self.tmp / "pwned.txt"
        self.assertLess(len(payload), 60, "precondition: clean_goal must not truncate it")
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")

        ok, detail = self.engine.execute_git_closure(
            "EGA-1", payload, "python", str(self.tmp)
        )
        self.assertFalse(canary.exists(), "the goal summary was executed by a shell")
        self.assertTrue(ok, f"the commit itself failed: {detail}")

        subject, _, _ = self.engine.run_cmd(
            ["git", "log", "-1", "--pretty=%s"], cwd=str(self.tmp)
        )
        self.assertIn(literal, subject, "the literal text belongs in the commit subject")

    def test_dollar_paren_substitution_is_not_executed(self):
        """Verified live: under shell=True this commits cleanly and fires."""
        self.assert_payload_is_inert("add $(touch pwned.txt)", "$(touch")

    def test_backtick_substitution_is_not_executed(self):
        """Also fires on its own. Combining the two instead breaks quoting,
        which fails the commit without executing anything — so they have to
        be separate tests to mean anything."""
        self.assert_payload_is_inert("add `touch pwned.txt`", "`touch")

    def test_no_shell_invocation_anywhere_in_the_module(self):
        """A lint, kept deliberately alongside the behavioural tests above.

        A shape assertion is worth having when it covers a surface behaviour
        cannot reach, and worth deleting when it stands in for a behavioural
        test that should exist. This is the former: the two canary tests
        prove the commit path is inert, but they only reach the call sites
        they exercise, and a future subprocess call added elsewhere in this
        module would be covered by neither.
        """
        source = (REPO_ROOT / "skills" / "verify" / "scripts"
                  / "ega_closure_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertIn("shell=False", source,
                      "the guard is worthless if the call it guards is gone")

    def test_a_quote_in_the_goal_survives_into_the_message(self):
        """The old code stripped quotes to make its shell string safe.

        With argv there is no shell to protect, and the stripping only
        corrupted summaries that legitimately contained one.
        """
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")
        self.engine.execute_git_closure(
            "EGA-6", 'fix the "obvious" bug', "python", str(self.tmp)
        )
        subject, _, _ = self.engine.run_cmd(
            ["git", "log", "-1", "--pretty=%s"], cwd=str(self.tmp)
        )
        self.assertIn('"obvious"', subject)

    def test_untracked_files_are_not_swept_into_the_commit(self):
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")
        scratch = self.tmp / "scratch.txt"
        scratch.write_text("unrelated experiment\n", encoding="utf-8")

        self.engine.execute_git_closure("EGA-2", "tidy up", "python", str(self.tmp))

        files, _, _ = self.engine.run_cmd(
            ["git", "show", "--name-only", "--pretty=", "HEAD"], cwd=str(self.tmp)
        )
        self.assertIn("seed.txt", files)
        self.assertNotIn("scratch.txt", files, "git add -A swept up untracked work")

    def test_only_untracked_files_is_a_clean_tree(self):
        """git add -u stages nothing here, so the old status check led to an
        empty commit and reported a closure with nothing to do as a failure."""
        (self.tmp / "scratch.txt").write_text("unrelated experiment\n", encoding="utf-8")
        ok, detail = self.engine.execute_git_closure("EGA-7", "tidy up", "python", str(self.tmp))
        self.assertTrue(ok, detail)
        self.assertEqual(detail, "Clean working tree")

    def test_protected_branch_is_never_pushed(self):
        """A reachable remote, so refusing is the only reason nothing arrives."""
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")
        branch, _, _ = self.engine.run_cmd(["git", "branch", "--show-current"], cwd=str(self.tmp))
        self.assertIn(branch, self.engine.PROTECTED_BRANCHES,
                      "precondition: git init should land on a protected branch name")
        self.assertEqual(self.remote_commit_count(), 0, "precondition: remote is empty")

        ok, _ = self.engine.execute_git_closure(
            "EGA-3", "tidy up", "python", str(self.tmp), push=True
        )
        self.assertTrue(ok)
        self.assertEqual(
            self.remote_commit_count(), 0,
            "a protected branch was pushed to the remote",
        )

    def test_an_unprotected_branch_is_pushed_when_asked(self):
        """The negative control: refusing must not mean push never works."""
        self.engine.run_cmd(["git", "checkout", "-q", "-b", "feature/x"], cwd=str(self.tmp))
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")

        ok, _ = self.engine.execute_git_closure(
            "EGA-4", "tidy up", "python", str(self.tmp), push=True
        )
        self.assertTrue(ok)
        self.assertEqual(
            self.remote_commit_count(), 2,
            "push=True on an unprotected branch should reach the remote",
        )

    def test_nothing_is_pushed_without_push(self):
        """The default path, with a reachable remote available to push to."""
        self.engine.run_cmd(["git", "checkout", "-q", "-b", "feature/y"], cwd=str(self.tmp))
        (self.tmp / "seed.txt").write_text("changed\n", encoding="utf-8")

        self.engine.execute_git_closure("EGA-5", "tidy up", "python", str(self.tmp))
        self.assertEqual(
            self.remote_commit_count(), 0,
            "closure published without being asked to",
        )


if __name__ == "__main__":
    unittest.main()
