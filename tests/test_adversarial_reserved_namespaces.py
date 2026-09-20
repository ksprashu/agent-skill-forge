#!/usr/bin/env python3.12
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

"""
Adversarial Test Suite: Reserved Antigravity Namespaces & Runtime Defense
Path: tests/test_adversarial_reserved_namespaces.py

Asserts that:
1. Attempting to add a skill named after any reserved Antigravity slash command
   (e.g., grill-me, teamwork-preview, voice, boost, goal) triggers a hard validation error.
2. Attempting to add an alias matching any reserved Antigravity slash command fails validation.
3. Attempting to sneak a reserved name via frontmatter 'name' field triggers a hard validation error.
4. Attempting to inject reserved names into sync_skills.py triggers prune/rejection.
5. Standard validation script (python3.12 scripts/validate_skills.py) passes with exit code 0.
6. Standard sync script (python3.12 scripts/sync_skills.py --prune --fix) passes with exit code 0.
7. grill-me, teamwork-preview, and voice are physically absent from ~/.gemini/config/skills
   and other global agent directories.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.validate_skills import (
    ALL_RESERVED,
    ANTIGRAVITY_BUILTIN_SKILLS,
    ANTIGRAVITY_RESERVED_COMMANDS,
    parse_frontmatter,
    validate_aliases,
    validate_skill_dir,
)
from scripts.sync_skills import (
    ALIASES,
    CORE_SKILLS,
    clean_stale_and_orphan_links,
)


class TestReservedNamespaceValidation(unittest.TestCase):
    """Hostile test cases attempting to bypass validation with reserved slash commands."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="adv_test_skills_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reserved_slash_command_directory_names_trigger_hard_errors(self):
        """Hostile test: creating directories named after reserved slash commands MUST fail validation."""
        hostile_names = ["grill-me", "teamwork-preview", "voice", "boost", "goal", "schedule", "browser", "help"]
        for name in hostile_names:
            skill_dir = os.path.join(self.temp_dir, name)
            os.makedirs(skill_dir, exist_ok=True)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {name}\ndescription: Hostile collision test for {name}\n---\n# {name}\nContent\n")

        count, errors, warnings = validate_skill_dir(self.temp_dir, "test")
        self.assertEqual(count, len(hostile_names), "All hostile skills should be parsed")
        
        # Every single hostile name must have triggered an error
        for name in hostile_names:
            matching_errors = [e for e in errors if name in e and "collides with Antigravity reserved namespace" in e]
            self.assertTrue(
                len(matching_errors) >= 1,
                f"Expected hard collision error for reserved slash command '{name}', got errors: {errors}"
            )

    def test_reserved_builtin_skills_directory_names_trigger_hard_errors(self):
        """Hostile test: creating directories named after Antigravity builtin skills MUST fail validation."""
        hostile_names = ["agy-customizations", "antigravity_guide", "generative_ui", "migrate-workflows", "permissioned-github"]
        for name in hostile_names:
            skill_dir = os.path.join(self.temp_dir, name)
            os.makedirs(skill_dir, exist_ok=True)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {name}\ndescription: Hostile builtin test for {name}\n---\n# {name}\nContent\n")

        count, errors, warnings = validate_skill_dir(self.temp_dir, "test")
        for name in hostile_names:
            matching_errors = [e for e in errors if name in e and "collides with Antigravity reserved namespace" in e]
            self.assertTrue(
                len(matching_errors) >= 1,
                f"Expected hard collision error for builtin skill '{name}', got errors: {errors}"
            )

    def test_frontmatter_name_collision_with_innocent_directory_name(self):
        """Hostile test: innocent folder name with reserved name in frontmatter MUST trigger hard error."""
        innocent_dir = os.path.join(self.temp_dir, "my-innocent-helper")
        os.makedirs(innocent_dir, exist_ok=True)
        skill_md = os.path.join(innocent_dir, "SKILL.md")

        # Infiltrate with reserved name in frontmatter
        for reserved in ["grill-me", "teamwork-preview", "voice", "boost", "goal"]:
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {reserved}\ndescription: Trojan skill infiltrating reserved namespace\n---\n# Trojan\n")

            count, errors, warnings = validate_skill_dir(self.temp_dir, "test")
            self.assertEqual(count, 1)
            matching = [e for e in errors if f"Skill frontmatter name '{reserved}' collides" in e]
            self.assertTrue(
                len(matching) >= 1,
                f"Frontmatter reserved name '{reserved}' failed to trigger validation error! Errors: {errors}"
            )

    def test_case_insensitive_directory_collision_triggers_hard_error(self):
        """Hostile test: uppercase/mixed-case directory names (Voice, GRILL-ME) MUST fail validation."""
        cased_names = ["Voice", "Grill-Me", "TEAMWORK-PREVIEW", "Boost", "Goal"]
        for name in cased_names:
            skill_dir = os.path.join(self.temp_dir, name)
            os.makedirs(skill_dir, exist_ok=True)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {name.lower()}\ndescription: Cased evasion test for {name}\n---\n# {name}\nContent\n")

            count, errors, warnings = validate_skill_dir(self.temp_dir, "test")
            matching = [e for e in errors if "collides with Antigravity reserved namespace" in e]
            self.assertTrue(
                len(matching) >= 1,
                f"Cased evasion directory '{name}' failed to trigger collision error! Errors: {errors}"
            )
            shutil.rmtree(skill_dir)

    def test_case_insensitive_frontmatter_collision_triggers_hard_error(self):
        """Hostile test: uppercase/mixed-case frontmatter names (Voice, Grill-Me) MUST fail validation."""
        innocent_dir = os.path.join(self.temp_dir, "clean-module")
        os.makedirs(innocent_dir, exist_ok=True)
        skill_md = os.path.join(innocent_dir, "SKILL.md")

        for cased_name in ["Voice", "Grill-Me", "TEAMWORK-PREVIEW", "Boost", "Goal"]:
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {cased_name}\ndescription: Cased frontmatter test\n---\n# Cased\n")

            count, errors, warnings = validate_skill_dir(self.temp_dir, "test")
            matching = [e for e in errors if "collides with Antigravity reserved namespace" in e]
            self.assertTrue(
                len(matching) >= 1,
                f"Cased frontmatter name '{cased_name}' failed to trigger collision error! Errors: {errors}"
            )
        shutil.rmtree(innocent_dir)


class TestReservedAliasValidation(unittest.TestCase):
    """Hostile test cases attempting to add reserved slash command names to ALIASES."""

    def test_active_aliases_have_zero_reserved_collisions(self):
        """Assert that current codebase ALIASES dictionary contains no reserved Antigravity collisions."""
        errors = validate_aliases()
        self.assertEqual(errors, [], f"Active ALIASES must contain 0 collisions, found: {errors}")

    def test_hostile_alias_injection_fails_validation(self):
        """Hostile test: dynamically injecting reserved commands into ALIASES MUST be caught by validate_aliases()."""
        import scripts.validate_skills as vs_mod
        original_aliases = dict(vs_mod.ALIASES)

        hostile_injections = {
            "grill-me": "grill",
            "teamwork-preview": "work",
            "voice": "human-voice",
            "boost": "work",
            "goal": "plan",
            "help": "docs",
            "agy-customizations": "catalog",
            "settings": "sync",
        }

        try:
            vs_mod.ALIASES = {**original_aliases, **hostile_injections}
            errors = vs_mod.validate_aliases()
            
            for hostile_alias, target in hostile_injections.items():
                found = any(f"[Alias: '{hostile_alias}']" in err for err in errors)
                self.assertTrue(
                    found,
                    f"Injected hostile alias '{hostile_alias}' pointing to '{target}' was NOT caught by validate_aliases()!"
                )
        finally:
            vs_mod.ALIASES = original_aliases

    def test_case_insensitive_hostile_alias_injection_fails_validation(self):
        """Hostile test: uppercase/mixed-case injected aliases (Voice, Grill-Me) MUST be caught."""
        import scripts.validate_skills as vs_mod
        original_aliases = dict(vs_mod.ALIASES)

        hostile_injections = {
            "Voice": "human-voice",
            "Grill-Me": "grill",
            "TEAMWORK-PREVIEW": "work",
            "Boost": "work",
            "Goal": "plan",
        }

        try:
            vs_mod.ALIASES = {**original_aliases, **hostile_injections}
            errors = vs_mod.validate_aliases()
            for hostile_alias, target in hostile_injections.items():
                found = any(f"[Alias: '{hostile_alias}']" in err for err in errors)
                self.assertTrue(
                    found,
                    f"Cased hostile alias '{hostile_alias}' was NOT caught by validate_aliases()!"
                )
        finally:
            vs_mod.ALIASES = original_aliases


class TestSyncSkillsReservedDefense(unittest.TestCase):
    """Hostile test cases asserting sync_skills refuses to link and aggressively prunes reserved entries."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="adv_test_sync_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_stale_prunes_reserved_directories_and_symlinks(self):
        """Hostile test: any reserved items appearing in agent skills directories are purged when pruning."""
        reserved_targets = ["grill-me", "teamwork-preview", "voice", "boost", "goal"]

        for item in reserved_targets:
            item_path = os.path.join(self.temp_dir, item)
            os.makedirs(item_path, exist_ok=True)
            marker_file = os.path.join(item_path, "SKILL.md")
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write(f"---\nname: {item}\n---\n# Hostile")

        # Verify items exist before prune
        for item in reserved_targets:
            self.assertTrue(os.path.exists(os.path.join(self.temp_dir, item)))

        # Run prune
        clean_stale_and_orphan_links(self.temp_dir, allowed_skills={}, prune=True)

        # Verify all reserved targets have been physically purged
        for item in reserved_targets:
            item_path = os.path.join(self.temp_dir, item)
            self.assertFalse(
                os.path.exists(item_path),
                f"Reserved namespace item '{item}' was NOT purged from skills directory during prune!"
            )


class TestPhysicalAbsenceInGlobalRuntime(unittest.TestCase):
    """Hostile test asserting that reserved commands are physically absent from actual user runtime dirs."""

    def test_reserved_commands_absent_from_gemini_config_skills(self):
        """Assert that grill-me, teamwork-preview, and voice are physically absent from ~/.gemini/config/skills."""
        runtime_dir = Path(os.path.expanduser("~/.gemini/config/skills"))
        reserved_forbidden = ["grill-me", "teamwork-preview", "voice"]

        if runtime_dir.exists():
            entries = os.listdir(runtime_dir)
            for forbidden in reserved_forbidden:
                self.assertNotIn(
                    forbidden,
                    entries,
                    f"CRITICAL: Forbidden reserved command '{forbidden}' was found physically in {runtime_dir}!"
                )

    def test_all_reserved_commands_absent_from_all_global_agent_skill_dirs(self):
        """Assert that all reserved names are absent across all 5 global agent skill directories."""
        dirs_to_check = [
            Path(os.path.expanduser("~/.gemini/config/skills")),
            Path(os.path.expanduser("~/.agents/skills")),
            Path(os.path.expanduser("~/.gemini/skills")),
            Path(os.path.expanduser("~/.claude/skills")),
            Path(os.path.expanduser("~/.gemini/antigravity-cli/skills")),
        ]

        for adir in dirs_to_check:
            if not adir.exists():
                continue
            entries = set(os.listdir(adir))
            collisions = entries & ALL_RESERVED
            self.assertEqual(
                collisions,
                set(),
                f"CRITICAL: Global directory '{adir}' contains forbidden reserved collisions: {collisions}"
            )


class TestScriptExecutionSubprocess(unittest.TestCase):
    """End-to-end execution of validation and sync scripts in real subprocesses."""

    def test_validate_skills_script_exit_code_0(self):
        """Run python3.12 scripts/validate_skills.py and assert exit code 0."""
        script_path = REPO_ROOT / "scripts" / "validate_skills.py"
        res = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            res.returncode,
            0,
            f"scripts/validate_skills.py failed with returncode {res.returncode}.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
        self.assertIn("0 PII leaks and clean frontmatter", res.stdout)

    def test_sync_skills_prune_fix_script_exit_code_0(self):
        """Run python3.12 scripts/sync_skills.py --prune --fix and assert exit code 0."""
        script_path = REPO_ROOT / "scripts" / "sync_skills.py"
        res = subprocess.run(
            [sys.executable, str(script_path), "--prune", "--fix"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            res.returncode,
            0,
            f"scripts/sync_skills.py --prune --fix failed with returncode {res.returncode}.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
