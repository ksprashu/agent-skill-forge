#!/usr/bin/env python3
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
}


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
        if os.path.islink(item_path):
            target_exists = os.path.exists(item_path)
            is_allowed = item in allowed_skills or item in ALIASES
            if not target_exists or not is_allowed:
                reason = "BROKEN" if not target_exists else "NON-GLOBAL / STALE"
                print(f"  [{reason}] {item} in {skills_dir}")
                if prune:
                    os.unlink(item_path)
                    print(f"    -> Removed: {item_path}")
        elif os.path.isdir(item_path) and item not in allowed_skills and item not in ALIASES:
            print(f"  [NON-GLOBAL DIR] {item} in {skills_dir}")
            if prune:
                shutil.rmtree(item_path)
                print(f"    -> Removed directory: {item_path}")


def sync_global_skills(prune=False, fix=False):
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
            if not os.path.exists(target_link) and not os.path.islink(target_link):
                print(f"  [MISSING] {name}")
                if fix:
                    os.symlink(src_path, target_link)
                    print(f"    -> Linked {target_link} -> {src_path}")
            elif os.path.islink(target_link):
                try:
                    link_dst = os.readlink(target_link)
                    if not os.path.exists(target_link) or link_dst != src_path:
                        print(f"  [REPOINT LINK] {name} ({link_dst}) -> {src_path}")
                        if fix:
                            os.unlink(target_link)
                            os.symlink(src_path, target_link)
                            print(f"    -> Repointed link to {src_path}")
                    else:
                        print(f"  [OK] {name}")
                except OSError:
                    pass
            elif os.path.isdir(target_link):
                if fix:
                    shutil.rmtree(target_link)
                    os.symlink(src_path, target_link)
                    print(f"    -> Replaced directory with symlink {target_link} -> {src_path}")
                else:
                    print(f"  [DIR (NEEDS SYMLINK)] {name}")


def bootstrap_project_skills(project_dir, skill_names, fix=False):
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
            if not os.path.exists(target_link) and not os.path.islink(target_link):
                print(f"  [BOOTSTRAP] {skill} ({skill_info['type']}) -> {target_link}")
                if fix:
                    os.symlink(src_path, target_link)
                    print(f"    -> Created symlink to {src_path}")
            else:
                print(f"  [ALREADY PRESENT] {skill} in {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Agent Skill Forge - Symlink Manager & On-Demand Bootstrapper")
    parser.add_argument('--fix', action='store_true', help="Automatically create or repoint missing symlinks")
    parser.add_argument('--prune', action='store_true', help="Remove stale, broken, or non-global symlinks")
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
        bootstrap_project_skills(args.project, skill_names, fix=args.fix)
        return

    sync_global_skills(prune=args.prune, fix=args.fix)


if __name__ == '__main__':
    main()
