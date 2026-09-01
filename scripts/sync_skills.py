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

"""
Agent Skill Forge - Canonical Skill Symlink Manager & On-Demand Bootstrapper

Synchronizes curated core global skills across AI developer tools:
- Antigravity IDE (~/.gemini/config/skills)
- Antigravity CLI (~/.gemini/antigravity-cli/skills)
- Gemini CLI (~/.gemini/skills)
- Claude Code (~/.claude/skills)
- Universal Agent Hub (~/.agents/skills)

Also bootstraps project-scoped domain skills into:
- <project>/.gemini/skills
- <project>/.agents/skills
"""

import os
import sys
import argparse
import shutil
import json

if sys.platform == 'win32':
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CORE_SKILLS_DIR = os.path.join(REPO_ROOT, 'skills')
PREFERRED_SKILLS_DIR = os.path.join(REPO_ROOT, 'preferred')

AGENTS_SKILLS_DIR = os.path.expanduser('~/.agents/skills')
GEMINI_SKILLS_DIR = os.path.expanduser('~/.gemini/skills')
GEMINI_CONFIG_SKILLS_DIR = os.path.expanduser('~/.gemini/config/skills')
CLAUDE_SKILLS_DIR = os.path.expanduser('~/.claude/skills')
ANTIGRAVITY_CLI_SKILLS_DIR = os.path.expanduser('~/.gemini/antigravity-cli/skills')

# 15 Core Global Skills (1-Word Primary Action Verbs)
CORE_SKILLS = {
    'prompt': os.path.join(CORE_SKILLS_DIR, 'prompt'),
    'grill': os.path.join(CORE_SKILLS_DIR, 'grill'),
    'spec': os.path.join(CORE_SKILLS_DIR, 'spec'),
    'plan': os.path.join(CORE_SKILLS_DIR, 'plan'),
    'test': os.path.join(CORE_SKILLS_DIR, 'test'),
    'verify': os.path.join(CORE_SKILLS_DIR, 'verify'),
    'review': os.path.join(CORE_SKILLS_DIR, 'review'),
    'unslop': os.path.join(CORE_SKILLS_DIR, 'unslop'),
    'docs': os.path.join(CORE_SKILLS_DIR, 'docs'),
    'catalog': os.path.join(CORE_SKILLS_DIR, 'catalog'),
    'sync': os.path.join(CORE_SKILLS_DIR, 'sync'),
    'google-oss': os.path.join(CORE_SKILLS_DIR, 'google-oss'),
    'codelab': os.path.join(CORE_SKILLS_DIR, 'codelab'),
    'voice': os.path.join(CORE_SKILLS_DIR, 'voice'),
    'copy-write': os.path.join(CORE_SKILLS_DIR, 'copy-write'),
    'image-gen': os.path.join(CORE_SKILLS_DIR, 'image-gen'),
    'continuous-alignment': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
    'align': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
}

# Backward-Compatible Aliases
ALIASES = {
    'prompt-writer': 'prompt',
    'grill-me': 'grill',
    'planning': 'plan',
    'expectation-harness': 'verify',
    'documentation': 'docs',
    'compile-docs': 'docs',
    'knowledge-catalog': 'catalog',
    'skill-sync': 'sync',
    'make-google-oss': 'google-oss',
    'codelab-creator': 'codelab',
    'copy-write-bara': 'copy-write',
    'image-gen-expert': 'image-gen',
    'extract-human-voice': 'voice',
    'evolve': 'align',
}


def is_link(path):
    """Check if path is a symlink or Windows junction."""
    if os.path.islink(path):
        return True
    if sys.platform == 'win32' and hasattr(os.path, 'isjunction') and os.path.isjunction(path):
        return True
    return False


def remove_link(path):
    """Remove a symlink or junction safely without deleting target contents."""
    os.unlink(path)


def remove_path_or_link(path):
    """Safely remove a file, symlink, junction, or directory."""
    if is_link(path):
        remove_link(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def create_link(src_path, target_link, copy_mode=False):
    """Create a directory symlink, Windows junction, or physical copy."""
    if copy_mode:
        if os.path.exists(target_link) or is_link(target_link):
            remove_path_or_link(target_link)
        shutil.copytree(src_path, target_link)
        return

    if sys.platform == 'win32':
        try:
            os.symlink(src_path, target_link, target_is_directory=True)
        except OSError:
            import _winapi
            _winapi.CreateJunction(src_path, target_link)
    else:
        os.symlink(src_path, target_link)


def is_same_link_target(target_link, src_path):
    """Check if target_link resolves or points to src_path."""
    try:
        if os.path.exists(target_link) and os.path.exists(src_path):
            if os.path.samefile(target_link, src_path):
                return True
    except OSError:
        pass
    try:
        dst = os.readlink(target_link)
        if sys.platform == 'win32' and dst.startswith('\\\\?\\'):
            dst = dst[4:]
        return os.path.abspath(dst) == os.path.abspath(src_path)
    except OSError:
        return False


def discover_all_skills():
    """Discover all core and preferred skills in the monorepo."""
    all_skills = {}
    if os.path.exists(CORE_SKILLS_DIR):
        for name in sorted(os.listdir(CORE_SKILLS_DIR)):
            path = os.path.join(CORE_SKILLS_DIR, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, 'SKILL.md')):
                all_skills[name] = {'path': path, 'type': 'global'}
    
    if os.path.exists(PREFERRED_SKILLS_DIR):
        for name in sorted(os.listdir(PREFERRED_SKILLS_DIR)):
            path = os.path.join(PREFERRED_SKILLS_DIR, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, 'SKILL.md')):
                all_skills[name] = {'path': path, 'type': 'preferred'}

    return all_skills


def clean_stale_and_orphan_links(skills_dir, allowed_skills, prune=False):
    """Remove broken symlinks or symlinks not in allowed list."""
    if not os.path.exists(skills_dir):
        return

    for item in sorted(os.listdir(skills_dir)):
        item_path = os.path.join(skills_dir, item)
        if is_link(item_path):
            target_exists = os.path.exists(item_path)
            is_allowed = item in allowed_skills or item in ALIASES
            if not target_exists or not is_allowed:
                reason = "BROKEN" if not target_exists else "NON-GLOBAL / STALE"
                print(f"  [{reason}] {item} in {skills_dir}")
                if prune:
                    remove_link(item_path)
                    print(f"    -> Removed: {item_path}")
        elif os.path.isdir(item_path) and item not in allowed_skills and item not in ALIASES:
            print(f"  [NON-GLOBAL DIR] {item} in {skills_dir}")
            if prune:
                shutil.rmtree(item_path)
                print(f"    -> Removed directory: {item_path}")


def sync_skills_json(fix=False):
    """Register canonical skills directories in global skills.json configs."""
    configs = [
        os.path.expanduser('~/.gemini/config/skills.json'),
        os.path.expanduser('~/.agents/skills.json'),
    ]
    data = {
        "entries": [
            {"path": CORE_SKILLS_DIR.replace('\\', '/')},
            {"path": PREFERRED_SKILLS_DIR.replace('\\', '/')}
        ]
    }
    for cfg in configs:
        cfg_dir = os.path.dirname(cfg)
        os.makedirs(cfg_dir, exist_ok=True)
        if fix:
            with open(cfg, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"  [JSON CONFIG] Generated {cfg}")


def sync_global_skills(prune=False, fix=False, copy_mode=False):
    """Synchronize core global skills into global agent directories."""
    print("=" * 65)
    print("🚀 Agent Skill Forge — Global Symlink Synchronizer")
    print("=" * 65)
    print(f"Core Skills ({len(CORE_SKILLS)} primary verbs):")
    for name, path in CORE_SKILLS.items():
        exists = os.path.exists(os.path.join(path, 'SKILL.md'))
        status = "EXISTS" if exists else "MISSING CANONICAL SOURCE"
        print(f"  - {name:20} -> {path} [{status}]")

    target_dirs = [
        ("~/.agents/skills", AGENTS_SKILLS_DIR),
        ("~/.gemini/skills", GEMINI_SKILLS_DIR),
        ("~/.gemini/config/skills", GEMINI_CONFIG_SKILLS_DIR),
        ("~/.claude/skills", CLAUDE_SKILLS_DIR),
        ("~/.gemini/antigravity-cli/skills", ANTIGRAVITY_CLI_SKILLS_DIR),
    ]

    all_targets = dict(CORE_SKILLS)
    for alias, target in ALIASES.items():
        if target in CORE_SKILLS:
            all_targets[alias] = CORE_SKILLS[target]

    for label, target_dir in target_dirs:
        os.makedirs(target_dir, exist_ok=True)
        print(f"\n--- Auditing {label} ---")
        clean_stale_and_orphan_links(target_dir, all_targets, prune=prune)

        for name, src_path in all_targets.items():
            if not os.path.exists(src_path):
                continue
            target_link = os.path.join(target_dir, name)
            if not os.path.exists(target_link) and not is_link(target_link):
                print(f"  [MISSING] {name}")
                if fix:
                    create_link(src_path, target_link, copy_mode=copy_mode)
                    action = "Copied" if copy_mode else "Linked"
                    print(f"    -> {action} {target_link} -> {src_path}")
            elif is_link(target_link):
                if copy_mode:
                    if fix:
                        remove_link(target_link)
                        create_link(src_path, target_link, copy_mode=True)
                        print(f"    -> Converted junction to physical copy: {target_link}")
                elif not is_same_link_target(target_link, src_path):
                    try:
                        link_dst = os.readlink(target_link)
                    except OSError:
                        link_dst = "unknown"
                    print(f"  [REPOINT LINK] {name} ({link_dst}) -> {src_path}")
                    if fix:
                        remove_link(target_link)
                        create_link(src_path, target_link, copy_mode=False)
                        print(f"    -> Repointed link to {src_path}")
                else:
                    print(f"  [OK] {name}")
            elif os.path.isdir(target_link):
                if not copy_mode and fix:
                    shutil.rmtree(target_link)
                    create_link(src_path, target_link, copy_mode=False)
                    print(f"    -> Replaced directory with symlink {target_link} -> {src_path}")
                else:
                    print(f"  [OK] {name} (directory)")

    print("\n--- Auditing JSON Configuration Registries ---")
    sync_skills_json(fix=fix)


def bootstrap_project_skills(project_dir, skill_names, fix=False, copy_mode=False):
    """Bootstrap specific preferred or core skills into a project directory."""
    project_dir = os.path.abspath(os.path.expanduser(project_dir))
    if not os.path.exists(project_dir):
        print(f"Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    all_skills = discover_all_skills()
    print(f"\n📦 Bootstrapping skills into project: {project_dir}")
    print(f"Requested skills: {', '.join(skill_names)}")

    project_gemini_skills = os.path.join(project_dir, '.gemini', 'skills')
    project_agents_skills = os.path.join(project_dir, '.agents', 'skills')
    os.makedirs(project_gemini_skills, exist_ok=True)
    os.makedirs(project_agents_skills, exist_ok=True)

    for skill in skill_names:
        skill = skill.strip()
        if not skill:
            continue

        skill_info = all_skills.get(skill)
        if not skill_info:
            print(f"  [NOT FOUND LOCALLY] {skill} — Try pulling via: npx skills add <package> --skill {skill}")
            continue

        src_path = skill_info['path']
        for target_dir in [project_gemini_skills, project_agents_skills]:
            target_link = os.path.join(target_dir, skill)
            if not os.path.exists(target_link) and not is_link(target_link):
                print(f"  [BOOTSTRAP] {skill} ({skill_info['type']}) -> {target_link}")
                if fix:
                    create_link(src_path, target_link, copy_mode=copy_mode)
                    print(f"    -> Created entry to {src_path}")
            else:
                print(f"  [ALREADY PRESENT] {skill} in {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Agent Skill Forge - Symlink Manager & On-Demand Bootstrapper")
    parser.add_argument('--fix', action='store_true', help="Automatically create or repoint missing symlinks")
    parser.add_argument('--prune', action='store_true', help="Remove stale, broken, or non-global symlinks")
    parser.add_argument('--copy', action='store_true', help="Use physical directory copying instead of symlinks/junctions")
    parser.add_argument('--project', type=str, help="Target project workspace for JIT skill bootstrapping")
    parser.add_argument('--skills', type=str, help="Comma-separated skill names to bootstrap into the project")
    parser.add_argument('--list-available', action='store_true', help="List all core and preferred skills in the forge")

    args = parser.parse_args()

    if args.list_available:
        all_skills = discover_all_skills()
        print(f"Agent Skill Forge Catalog ({len(all_skills)} total skills):")
        print("\n🌟 Core Global Skills (15 Action Verbs):")
        for name in sorted(CORE_SKILLS.keys()):
            path = CORE_SKILLS[name]
            print(f"  - {name:20} -> {path}")
        print("\n🛠️ Preferred Domain Skills (On-Demand JIT):")
        for name, info in sorted(all_skills.items()):
            if info['type'] == 'preferred':
                print(f"  - {name:32} -> {info['path']}")
        return

    if args.project:
        if not args.skills:
            print("Error: --skills must be provided when using --project (e.g. --skills frontend-ui-engineering,security-and-hardening)")
            sys.exit(1)
        skill_names = [s.strip() for s in args.skills.split(',')]
        bootstrap_project_skills(args.project, skill_names, fix=args.fix, copy_mode=args.copy)
        return

    sync_global_skills(prune=args.prune, fix=args.fix, copy_mode=args.copy)


if __name__ == '__main__':
    main()
