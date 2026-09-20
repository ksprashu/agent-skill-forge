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
import re

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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
    'human-voice': os.path.join(CORE_SKILLS_DIR, 'human-voice'),
    'copy-write': os.path.join(CORE_SKILLS_DIR, 'copy-write'),
    'image-gen': os.path.join(CORE_SKILLS_DIR, 'image-gen'),
    'continuous-alignment': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
    'align': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
    'work': os.path.join(CORE_SKILLS_DIR, 'work'),
}

# Backward-Compatible Aliases
ALIASES = {
    'prompt-writer': 'prompt',
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
    'extract-human-voice': 'human-voice',
    'evolve': 'align',
    'teamwork': 'work',
    'team': 'work',
    'swarm': 'work',
}

ANTIGRAVITY_RESERVED_COMMANDS = {'goal', 'schedule', 'browser', 'grill-me', 'teamwork-preview', 'learn', 'boost', 'agents', 'config', 'settings', 'clear', 'resume', 'rewind', 'undo', 'fork', 'add-dir', 'keybindings', 'codesearch', 'credits', 'diff', 'permissions', 'statusline', 'title', 'voice', 'help'}
ANTIGRAVITY_BUILTIN_SKILLS = {'agy-customizations', 'antigravity_guide', 'antigravity-guide', 'generative_ui', 'migrate-workflows', 'permissioned-github'}
ALL_RESERVED = ANTIGRAVITY_RESERVED_COMMANDS | ANTIGRAVITY_BUILTIN_SKILLS

# ==============================================================================
# Skill Clusters Taxonomy (Core Action Verbs & Preferred Domain Skills)
# ==============================================================================

CORE_CLUSTERS = {
    'c1': {
        'id': 'plan-spec',
        'name': 'Planning, Specification & Swarm Execution',
        'description': 'Requirements gathering, Socratic grilling, spec design, task DAG planning, and autonomous swarm execution.',
        'skills': ['spec', 'plan', 'grill', 'prompt', 'work'],
    },
    'c2': {
        'id': 'test-review',
        'name': 'Quality & Verification',
        'description': 'TDD prove-it reproduction, static verification rubrics, code reviews, and slop stripping.',
        'skills': ['test', 'verify', 'review', 'unslop'],
    },
    'c3': {
        'id': 'content-creative',
        'name': 'Content, Creative & Authoring',
        'description': 'Step-by-step Google codelabs, human voice profiling, technical copywriting, and image generation.',
        'skills': ['codelab', 'human-voice', 'copy-write', 'image-gen'],
    },
    'c4': {
        'id': 'docs-governance',
        'name': 'Knowledge & Governance',
        'description': 'Documentation compilation, OKF knowledge catalog, Google OSS hygiene, and continuous alignment.',
        'skills': ['docs', 'catalog', 'google-oss', 'continuous-alignment', 'sync'],
    },
}

DOMAIN_CLUSTERS = {
    'd1': {
        'id': 'fullstack',
        'name': 'Full-Stack & Quality',
        'description': 'Frontend UI engineering, Core Web Vitals optimization, Chrome DevTools testing, and resilient API contract design.',
        'skills': [
            'frontend-ui-engineering',
            'performance-optimization',
            'browser-testing-with-devtools',
            'api-and-interface-design',
        ],
    },
    'd2': {
        'id': 'security',
        'name': 'Security, Diagnostics & Reliability',
        'description': 'OWASP threat modeling & hardening, root-cause debugging checklist, OpenTelemetry & structured logging.',
        'skills': [
            'security-and-hardening',
            'debugging-and-error-recovery',
            'observability-and-instrumentation',
        ],
    },
    'd3': {
        'id': 'devops',
        'name': 'DevOps & Workflows',
        'description': 'GitHub Actions matrix CI/CD automation, trunk-based Git workflows, and zero-downtime schema deprecations.',
        'skills': [
            'ci-cd-and-automation',
            'git-workflow-and-versioning',
            'deprecation-and-migration',
        ],
    },
    'd4': {
        'id': 'ai',
        'name': 'AI & Evaluation',
        'description': 'Context window token management and universal AI assistant benchmark evaluation harness.',
        'skills': [
            'context-engineering',
            'benchmark-harness',
        ],
    },
}

ALL_CLUSTERS = {**CORE_CLUSTERS, **DOMAIN_CLUSTERS}


def resolve_clusters_arg(cluster_arg):
    """Resolve comma-separated cluster codes, IDs, presets, or skill names into a list of skill names."""
    skills = []
    if not cluster_arg:
        return skills
    parts = [p.strip().lower() for p in cluster_arg.split(',') if p.strip()]
    for p in parts:
        if p in ('all', 'complete'):
            for c in ALL_CLUSTERS.values():
                skills.extend(c['skills'])
            break
        elif p == 'core':
            for c in CORE_CLUSTERS.values():
                skills.extend(c['skills'])
        elif p in ('domain', 'preferred'):
            for c in DOMAIN_CLUSTERS.values():
                skills.extend(c['skills'])
        elif p in ('content', 'creative', 'c3'):
            skills.extend(CORE_CLUSTERS['c3']['skills'])
        elif p in ('plan', 'spec', 'planning', 'c1'):
            skills.extend(CORE_CLUSTERS['c1']['skills'])
        elif p in ('test', 'qa', 'quality', 'c2'):
            skills.extend(CORE_CLUSTERS['c2']['skills'])
        elif p in ('docs', 'gov', 'governance', 'c4'):
            skills.extend(CORE_CLUSTERS['c4']['skills'])
        elif p in ALL_CLUSTERS:
            skills.extend(ALL_CLUSTERS[p]['skills'])
        else:
            matched = False
            for c in ALL_CLUSTERS.values():
                if p == c['id'].lower():
                    skills.extend(c['skills'])
                    matched = True
                    break
                elif p in [s.lower() for s in c['skills']]:
                    skills.append(p)
                    matched = True
                    break
            if not matched:
                skills.append(p)
    return list(dict.fromkeys(skills))


def interactive_wizard():
    """Interactive CLI wizard to select clusters and installation scope."""
    print("=" * 74)
    print(" 🔨 AGENT SKILL FORGE — Interactive Cluster & Skill Installer")
    print("=" * 74)

    print("\n📦 CORE SKILL CLUSTERS:")
    for key, info in sorted(CORE_CLUSTERS.items()):
        skills_str = ", ".join(info['skills'])
        print(f"  [{key}] {info['name']}")
        print(f"       Description : {info['description']}")
        print(f"       Skills      : {skills_str}")

    print("\n🛠️  DOMAIN SKILL CLUSTERS:")
    for key, info in sorted(DOMAIN_CLUSTERS.items()):
        skills_str = ", ".join(info['skills'])
        print(f"  [{key}] {info['name']}")
        print(f"       Description : {info['description']}")
        print(f"       Skills      : {skills_str}")

    print("\n⚡ QUICK PRESETS:")
    print("  [content] Content & Creative only (codelab, human-voice, copy-write, image-gen)")
    print("  [core]    All 18 Core Action Skills (c1, c2, c3, c4)")
    print("  [domain]  All 12 Preferred Domain Skills (d1, d2, d3, d4)")
    print("  [all]     Complete Forge (All 30 Core & Domain Skills)")
    print("  [custom]  Enter comma-separated skill names")
    print("-" * 74)

    try:
        choice = input("Enter choice(s) [e.g. c3, or c3,d1, or content] (default: all): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)

    if not choice:
        choice = 'all'

    if choice.lower() == 'custom':
        try:
            custom_input = input("Enter comma-separated skill names: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)
        chosen_skills = [s.strip() for s in custom_input.split(',') if s.strip()]
    else:
        chosen_skills = resolve_clusters_arg(choice)

    print(f"\n  -> Selected ({len(chosen_skills)} skills): {', '.join(chosen_skills)}")

    print("\nInstallation Scope:")
    print("  [1] Global across all AI tools (~/.gemini, ~/.agents, ~/.claude, etc.)")
    print("  [2] Project-scoped (Install into a specific repository workspace)")
    try:
        scope_choice = input("Select scope [1-2] (default: 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)

    if scope_choice == '2':
        try:
            project_dir = input("Enter project workspace directory (default: .): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)
        if not project_dir:
            project_dir = "."
        return 'project', project_dir, chosen_skills, False
    else:
        try:
            prune_input = input("\nPrune unselected skills from global directories? [y/N]: ").strip().lower()
            strict_prune = (prune_input == 'y')
        except (EOFError, KeyboardInterrupt):
            strict_prune = False
        return 'global', None, chosen_skills, strict_prune


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


def clean_stale_and_orphan_links(skills_dir, allowed_skills, prune=False, strict_prune=False):
    """Remove broken symlinks, items matching Antigravity reserved namespace, or symlinks not in allowed list."""
    if not os.path.exists(skills_dir):
        return

    all_available = discover_all_skills()

    for item in sorted(os.listdir(skills_dir)):
        item_path = os.path.join(skills_dir, item)
        if item.lower() in ALL_RESERVED:
            reason = "RESERVED ANTIGRAVITY NAMESPACE"
            print(f"  [{reason}] {item} in {skills_dir}")
            if prune:
                remove_path_or_link(item_path)
                print(f"    -> Removed: {item_path}")
            continue

        if is_link(item_path):
            target_exists = os.path.exists(item_path)
            if strict_prune:
                is_allowed = item in allowed_skills or (item in ALIASES and ALIASES[item] in allowed_skills)
            else:
                is_allowed = item in allowed_skills or item in ALIASES or (item in all_available and target_exists)

            if not target_exists or not is_allowed:
                reason = "BROKEN" if not target_exists else "STALE / NOT SELECTED"
                print(f"  [{reason}] {item} in {skills_dir}")
                if prune:
                    remove_link(item_path)
                    print(f"    -> Removed: {item_path}")
        elif os.path.isdir(item_path) and item not in allowed_skills and item not in ALIASES and item not in all_available:
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


def sync_global_skills(prune=False, fix=False, copy_mode=False, selected_skills=None, strict_prune=False):
    """Synchronize selected core and/or domain skills into global agent directories."""
    print("=" * 65)
    print("🚀 Agent Skill Forge — Global Symlink Synchronizer")
    print("=" * 65)

    all_available = discover_all_skills()

    if selected_skills is None:
        target_skill_names = list(CORE_SKILLS.keys())
        print(f"Default Core Skills ({len(target_skill_names)} primary verbs):")
    else:
        target_skill_names = selected_skills
        print(f"Target Selected Skills ({len(target_skill_names)}):")

    all_targets = {}
    for name in target_skill_names:
        if name.lower() in ALL_RESERVED:
            print(f"  [RESERVED SKIPPED] '{name}' collides with Antigravity reserved namespace and cannot be linked.")
            continue
        if name in all_available:
            path = all_available[name]['path']
            all_targets[name] = path
            exists = os.path.exists(os.path.join(path, 'SKILL.md'))
            status = "EXISTS" if exists else "MISSING CANONICAL SOURCE"
            print(f"  - {name:32} -> {path} [{status}]")
        elif name in CORE_SKILLS:
            path = CORE_SKILLS[name]
            all_targets[name] = path
            exists = os.path.exists(os.path.join(path, 'SKILL.md'))
            status = "EXISTS" if exists else "MISSING CANONICAL SOURCE"
            print(f"  - {name:32} -> {path} [{status}]")
        else:
            print(f"  ! {name:32} [NOT FOUND IN FORGE]")

    for alias, target in ALIASES.items():
        if alias.lower() in ALL_RESERVED:
            continue
        if target in all_targets:
            all_targets[alias] = all_targets[target]

    target_dirs = [
        ("~/.agents/skills", AGENTS_SKILLS_DIR),
        ("~/.gemini/skills", GEMINI_SKILLS_DIR),
        ("~/.gemini/config/skills", GEMINI_CONFIG_SKILLS_DIR),
        ("~/.claude/skills", CLAUDE_SKILLS_DIR),
        ("~/.gemini/antigravity-cli/skills", ANTIGRAVITY_CLI_SKILLS_DIR),
    ]

    for label, target_dir in target_dirs:
        os.makedirs(target_dir, exist_ok=True)
        print(f"\n--- Auditing {label} ---")
        clean_stale_and_orphan_links(target_dir, all_targets, prune=prune, strict_prune=strict_prune)

        for name, src_path in all_targets.items():
            if name.lower() in ALL_RESERVED:
                print(f"  [BLOCKED RESERVED] Refusing to link reserved name: {name}")
                continue
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

        if skill.lower() in ALL_RESERVED:
            print(f"  [RESERVED SKIPPED] '{skill}' collides with Antigravity reserved namespace and cannot be bootstrapped.")
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
    parser.add_argument('--prune', action='store_true', help="Remove stale, broken, or non-selected symlinks")
    parser.add_argument('--copy', action='store_true', help="Use physical directory copying instead of symlinks/junctions")
    parser.add_argument('--project', type=str, help="Target project workspace for JIT skill bootstrapping")
    parser.add_argument('--skills', type=str, help="Comma-separated skill names to install/bootstrap")
    parser.add_argument('--clusters', type=str, help="Comma-separated cluster codes or presets (c1, c2, c3, c4, d1, d2, d3, d4, content, core, domain, all)")
    parser.add_argument('--all', action='store_true', help="Install all 30 core and domain skills")
    parser.add_argument('--core', action='store_true', help="Install all 18 core action skills (c1, c2, c3, c4)")
    parser.add_argument('--domain', action='store_true', help="Install all 12 preferred domain skills (d1, d2, d3, d4)")
    parser.add_argument('--content', action='store_true', help="Install content & creative skills only (c3: codelab, human-voice, copy-write, image-gen)")
    parser.add_argument('--interactive', '-i', action='store_true', help="Launch interactive skill cluster installer")
    parser.add_argument('--list-available', action='store_true', help="List all core and preferred skills in the forge")
    parser.add_argument('--list-clusters', action='store_true', help="List all core and domain clusters with member skills")

    args = parser.parse_args()

    if args.list_clusters:
        print("=" * 70)
        print("🛠️  Agent Skill Forge — Skill Clusters")
        print("=" * 70)
        print("\n📦 CORE SKILL CLUSTERS:")
        for key, info in sorted(CORE_CLUSTERS.items()):
            print(f"\nCluster {key.upper()}: {info['name']} ({info['id']})")
            print(f"  Description: {info['description']}")
            print("  Skills:")
            for s in info['skills']:
                print(f"    - {s}")
        print("\n🛠️  DOMAIN SKILL CLUSTERS:")
        for key, info in sorted(DOMAIN_CLUSTERS.items()):
            print(f"\nCluster {key.upper()}: {info['name']} ({info['id']})")
            print(f"  Description: {info['description']}")
            print("  Skills:")
            for s in info['skills']:
                print(f"    - {s}")
        return

    if args.list_available:
        all_skills = discover_all_skills()
        print(f"Agent Skill Forge Catalog ({len(all_skills)} total skills):")
        print("\n🌟 Core Global Skills (18 Action Verbs):")
        for name in sorted(CORE_SKILLS.keys()):
            path = CORE_SKILLS[name]
            print(f"  - {name:22} -> {path}")
        print("\n🛠️ Preferred Domain Skills (On-Demand JIT):")
        for name, info in sorted(all_skills.items()):
            if info['type'] == 'preferred':
                print(f"  - {name:32} -> {info['path']}")
        return

    if args.interactive:
        scope, project_dir, chosen_skills, strict_prune = interactive_wizard()
        if scope == 'project':
            bootstrap_project_skills(project_dir, chosen_skills, fix=True, copy_mode=args.copy)
        else:
            sync_global_skills(prune=args.prune or strict_prune, fix=True, copy_mode=args.copy, selected_skills=chosen_skills, strict_prune=strict_prune)
        return

    # Resolve selected skills from CLI flags
    requested_skills = []
    has_explicit_selection = False

    if args.all:
        has_explicit_selection = True
        for c in ALL_CLUSTERS.values():
            requested_skills.extend(c['skills'])
    if args.core:
        has_explicit_selection = True
        for c in CORE_CLUSTERS.values():
            requested_skills.extend(c['skills'])
    if args.domain:
        has_explicit_selection = True
        for c in DOMAIN_CLUSTERS.values():
            requested_skills.extend(c['skills'])
    if args.content:
        has_explicit_selection = True
        requested_skills.extend(CORE_CLUSTERS['c3']['skills'])
    if args.clusters:
        has_explicit_selection = True
        requested_skills.extend(resolve_clusters_arg(args.clusters))
    if args.skills:
        has_explicit_selection = True
        requested_skills.extend([s.strip() for s in args.skills.split(',') if s.strip()])

    requested_skills = list(dict.fromkeys(requested_skills))

    if args.project:
        if not requested_skills:
            print("Error: --skills, --clusters, --content, --core, or --all must be provided with --project")
            sys.exit(1)
        bootstrap_project_skills(args.project, requested_skills, fix=args.fix, copy_mode=args.copy)
        return

    strict_prune = has_explicit_selection and args.prune
    selected = requested_skills if has_explicit_selection else None
    sync_global_skills(prune=args.prune, fix=args.fix, copy_mode=args.copy, selected_skills=selected, strict_prune=strict_prune)


if __name__ == '__main__':
    main()
