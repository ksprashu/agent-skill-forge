#!/usr/bin/env python3
"""
Skill Sync - Canonical Skill Symlink Manager & On-Demand Bootstrapper
Scans canonical skill source repositories in ~/code/github and manages symlinks
across global agent directories (~/.agents/skills, ~/.gemini/skills, ~/.gemini/config/skills, ~/.claude/skills)
and project-scoped directories (<project>/.gemini/skills, <project>/.agents/skills).
"""

import os
import sys
import argparse
import shutil

GITHUB_DIR = os.path.expanduser('~/code/github')
AGENTS_SKILLS_DIR = os.path.expanduser('~/.agents/skills')
GEMINI_SKILLS_DIR = os.path.expanduser('~/.gemini/skills')
GEMINI_CONFIG_SKILLS_DIR = os.path.expanduser('~/.gemini/config/skills')
CLAUDE_SKILLS_DIR = os.path.expanduser('~/.claude/skills')

# Curated Core Global Skills (Universal OS & Personal Toolkit)
CURATED_GLOBAL_SKILLS = {
    # 15 Primary 1-Word Action Slugs
    'prompt': os.path.join(GITHUB_DIR, 'skills-prompt-writer/skills/prompt-writer'),
    'grill': os.path.join(GITHUB_DIR, 'agent-skills/skills/grill'),
    'spec': os.path.join(GITHUB_DIR, 'agent-skills/skills/spec'),
    'plan': os.path.join(GITHUB_DIR, 'agent-skills/skills/planning'),
    'test': os.path.join(GITHUB_DIR, 'agent-skills/skills/test'),
    'verify': os.path.join(GITHUB_DIR, 'skills-expectation-harness/skills/expectation-harness'),
    'review': os.path.join(GITHUB_DIR, 'agent-skills/skills/review'),
    'unslop': os.path.join(GITHUB_DIR, 'agent-skills/skills/unslop'),
    'docs': os.path.join(GITHUB_DIR, 'skills-documentation/skills/documentation'),
    'catalog': os.path.join(GITHUB_DIR, 'skills-knowledge-catalog/skills/knowledge-catalog'),
    'sync': os.path.join(GITHUB_DIR, 'agent-skill-sync/skills/skill-sync'),
    'google-oss': os.path.join(GITHUB_DIR, 'gcx-make-google-oss/skills/make-google-oss'),
    'codelab': os.path.join(GITHUB_DIR, 'skills-codelab-creator/skills/codelab-creator'),
    'voice': os.path.join(GITHUB_DIR, 'skills-extract-human-voice/skills/extract-human-voice'),
    'copy-write': os.path.join(GITHUB_DIR, 'copy-write-bara'),
    'image-gen': os.path.join(GITHUB_DIR, 'skills-image-gen-expert/skills/image-gen-expert'),

    # Backward-compatible Aliases
    'prompt-writer': os.path.join(GITHUB_DIR, 'skills-prompt-writer/skills/prompt-writer'),
    'grill-me': os.path.join(GITHUB_DIR, 'agent-skills/skills/grill'),
    'planning': os.path.join(GITHUB_DIR, 'agent-skills/skills/planning'),
    'expectation-harness': os.path.join(GITHUB_DIR, 'skills-expectation-harness/skills/expectation-harness'),
    'documentation': os.path.join(GITHUB_DIR, 'skills-documentation/skills/documentation'),
    'compile-docs': os.path.join(GITHUB_DIR, 'skills-documentation/skills/documentation'),
    'knowledge-catalog': os.path.join(GITHUB_DIR, 'skills-knowledge-catalog/skills/knowledge-catalog'),
    'skill-sync': os.path.join(GITHUB_DIR, 'agent-skill-sync/skills/skill-sync'),
    'make-google-oss': os.path.join(GITHUB_DIR, 'gcx-make-google-oss/skills/make-google-oss'),
    'codelab-creator': os.path.join(GITHUB_DIR, 'skills-codelab-creator/skills/codelab-creator'),
    'copy-write-bara': os.path.join(GITHUB_DIR, 'copy-write-bara'),
    'image-gen-expert': os.path.join(GITHUB_DIR, 'skills-image-gen-expert/skills/image-gen-expert'),
    'using-agent-skills': os.path.join(GITHUB_DIR, 'agent-skills/skills/using-agent-skills'),
}


def discover_canonical_skills():
    """Find all canonical skills across all repositories in ~/code/github."""
    skills = {}
    if not os.path.exists(GITHUB_DIR):
        return skills

    for repo in sorted(os.listdir(GITHUB_DIR)):
        repo_path = os.path.join(GITHUB_DIR, repo)
        if not os.path.isdir(repo_path):
            continue

        # Check for skills/<skill-name>/SKILL.md
        inner_skills = os.path.join(repo_path, 'skills')
        if os.path.isdir(inner_skills):
            for sk in sorted(os.listdir(inner_skills)):
                sk_path = os.path.join(inner_skills, sk)
                if os.path.isdir(sk_path) and os.path.exists(os.path.join(sk_path, 'SKILL.md')):
                    skills[sk] = sk_path
        
        # Check direct SKILL.md in repo root
        elif os.path.exists(os.path.join(repo_path, 'SKILL.md')):
            sk_name = repo.replace('skills-', '').replace('gcx-', '').replace('agent-', '')
            skills[sk_name] = repo_path

    return skills


def clean_stale_and_orphan_links(skills_dir, allowed_skills, prune=False):
    """Remove broken symlinks or symlinks not in the allowed set."""
    if not os.path.exists(skills_dir):
        return

    for item in sorted(os.listdir(skills_dir)):
        item_path = os.path.join(skills_dir, item)
        if os.path.islink(item_path):
            target_exists = os.path.exists(item_path)
            is_allowed = item in allowed_skills
            if not target_exists or not is_allowed:
                reason = "BROKEN" if not target_exists else "NON-GLOBAL / STALE"
                print(f"  [{reason}] {item} in {skills_dir}")
                if prune:
                    os.unlink(item_path)
                    print(f"    -> Removed: {item_path}")
        elif os.path.isdir(item_path) and item not in allowed_skills:
            # Check if it's a regular directory not allowed in global
            print(f"  [NON-GLOBAL DIR] {item} in {skills_dir}")
            if prune:
                shutil.rmtree(item_path)
                print(f"    -> Removed dir: {item_path}")


def sync_global_skills(prune=False, fix=False):
    """Ensure only curated global skills exist in global agent directories."""
    print("=" * 60)
    print("Curated Global Skills Synchronization")
    print("=" * 60)
    print(f"Curated list ({len(CURATED_GLOBAL_SKILLS)} core skills):")
    for name, path in CURATED_GLOBAL_SKILLS.items():
        exists = os.path.exists(os.path.join(path, 'SKILL.md'))
        status = "EXISTS" if exists else "MISSING CANONICAL SOURCE"
        print(f"  - {name:26} -> {path} [{status}]")

    target_dirs = [
        ("~/.agents/skills", AGENTS_SKILLS_DIR),
        ("~/.gemini/skills", GEMINI_SKILLS_DIR),
        ("~/.gemini/config/skills", GEMINI_CONFIG_SKILLS_DIR),
        ("~/.claude/skills", CLAUDE_SKILLS_DIR),
        ("~/.gemini/antigravity-cli/skills", os.path.expanduser('~/.gemini/antigravity-cli/skills')),
    ]

    for label, target_dir in target_dirs:
        os.makedirs(target_dir, exist_ok=True)
        print(f"\n--- Auditing {label} ---")
        clean_stale_and_orphan_links(target_dir, CURATED_GLOBAL_SKILLS, prune=prune)

        for name, src_path in CURATED_GLOBAL_SKILLS.items():
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
                    if not os.path.exists(target_link):
                        print(f"  [BROKEN LINK] {name} ({link_dst})")
                        if fix:
                            os.unlink(target_link)
                            os.symlink(src_path, target_link)
                            print(f"    -> Repaired link to {src_path}")
                    else:
                        print(f"  [OK] {name}")
                except OSError:
                    pass
            elif os.path.isdir(target_link):
                if os.path.exists(os.path.join(target_link, 'SKILL.md')):
                    print(f"  [OK (DIR)] {name}")
                elif fix:
                    shutil.rmtree(target_link)
                    os.symlink(src_path, target_link)
                    print(f"    -> Replaced directory with symlink {target_link} -> {src_path}")
                else:
                    print(f"  [DIR (EMPTY/INVALID)] {name}")


def bootstrap_project_skills(project_dir, skill_names, fix=False):
    """Bootstrap specific skills into a project directory (.gemini/skills and .agents/skills)."""
    project_dir = os.path.abspath(os.path.expanduser(project_dir))
    if not os.path.exists(project_dir):
        print(f"Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    all_canonical = discover_canonical_skills()
    print(f"\nBootstrapping skills for project: {project_dir}")
    print(f"Requested skills: {', '.join(skill_names)}")

    project_gemini_skills = os.path.join(project_dir, '.gemini', 'skills')
    project_agents_skills = os.path.join(project_dir, '.agents', 'skills')
    os.makedirs(project_gemini_skills, exist_ok=True)
    os.makedirs(project_agents_skills, exist_ok=True)

    for skill in skill_names:
        skill = skill.strip()
        if not skill:
            continue

        src_path = all_canonical.get(skill)
        if not src_path:
            # Check CURATED_GLOBAL_SKILLS
            src_path = CURATED_GLOBAL_SKILLS.get(skill)

        if not src_path or not os.path.exists(src_path):
            print(f"  [NOT FOUND LOCALLY] {skill} - Try pulling via: npx skills add <package> --skill {skill}")
            continue

        for target_dir in [project_gemini_skills, project_agents_skills]:
            target_link = os.path.join(target_dir, skill)
            if not os.path.exists(target_link) and not os.path.islink(target_link):
                print(f"  [BOOTSTRAP] {skill} -> {target_link}")
                if fix:
                    os.symlink(src_path, target_link)
                    print(f"    -> Created symlink to {src_path}")
            else:
                print(f"  [ALREADY PRESENT] {skill} in {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Skill Sync & On-Demand Bootstrapper")
    parser.add_argument('--fix', action='store_true', help="Automatically create/repair missing symlinks")
    parser.add_argument('--prune', action='store_true', help="Remove stale, duplicate, or non-global symlinks")
    parser.add_argument('--project', type=str, help="Target project directory for on-demand skill bootstrapping")
    parser.add_argument('--skills', type=str, help="Comma-separated skill names to bootstrap into the project")
    parser.add_argument('--list-available', action='store_true', help="List all discovered canonical skills in ~/code/github")

    args = parser.parse_args()

    if args.list_available:
        canonical = discover_canonical_skills()
        print(f"Discovered {len(canonical)} canonical skills in {GITHUB_DIR}:")
        for name, path in sorted(canonical.items()):
            is_global = name in CURATED_GLOBAL_SKILLS
            tag = "[GLOBAL]" if is_global else "[ON-DEMAND]"
            print(f"  {tag:12} {name:32} -> {path}")
        return

    if args.project:
        if not args.skills:
            print("Error: --skills must be provided when using --project (e.g. --skills cloud-run-basics,bigquery-basics)")
            sys.exit(1)
        skill_names = [s.strip() for s in args.skills.split(',')]
        bootstrap_project_skills(args.project, skill_names, fix=args.fix)
        return

    sync_global_skills(prune=args.prune, fix=args.fix)


if __name__ == '__main__':
    main()
