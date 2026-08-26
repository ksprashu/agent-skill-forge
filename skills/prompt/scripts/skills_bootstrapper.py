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
Prompt-Writer Skill Bootstrapper (Plumbing Utility)
Executes physical project-level bootstrapping (symlinking local canonical skills
and installing remote packages from skills.sh) based on LLM decision-making.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional

GITHUB_DIR = os.path.expanduser('~/code/github')
REFERENCES_CATALOG = os.path.expanduser('~/code/github/skills-prompt-writer/skills/prompt-writer/references/PREFERRED_SKILLS.md')


def discover_canonical_skills() -> Dict[str, str]:
    """Discovers all local canonical skills available in ~/code/github."""
    skills = {}
    if not os.path.exists(GITHUB_DIR):
        return skills

    for repo in sorted(os.listdir(GITHUB_DIR)):
        repo_path = os.path.join(GITHUB_DIR, repo)
        if not os.path.isdir(repo_path):
            continue

        inner_skills = os.path.join(repo_path, 'skills')
        if os.path.isdir(inner_skills):
            for sk in sorted(os.listdir(inner_skills)):
                sk_path = os.path.join(inner_skills, sk)
                if os.path.isdir(sk_path) and os.path.exists(os.path.join(sk_path, 'SKILL.md')):
                    skills[sk] = sk_path
        elif os.path.exists(os.path.join(repo_path, 'SKILL.md')):
            sk_name = repo.replace('skills-', '').replace('gcx-', '').replace('agent-', '')
            skills[sk_name] = repo_path

    # Also check ~/.gemini/config/plugins for built-in plugin skills
    plugins_dir = os.path.expanduser('~/.gemini/config/plugins')
    if os.path.isdir(plugins_dir):
        for plugin in sorted(os.listdir(plugins_dir)):
            p_skills = os.path.join(plugins_dir, plugin, 'skills')
            if os.path.isdir(p_skills):
                for sk in sorted(os.listdir(p_skills)):
                    sk_path = os.path.join(p_skills, sk)
                    if os.path.isdir(sk_path) and os.path.exists(os.path.join(sk_path, 'SKILL.md')):
                        if sk not in skills:
                            skills[sk] = sk_path

    return skills


def install_project_skills(
    project_dir: str,
    skill_names: List[str],
    install_remote: bool = True
) -> Dict:
    """
    Installs the specified skills into <project>/.gemini/skills/ and <project>/.agents/skills/.
    Handles both local canonical skill names and remote package identifiers (e.g. vercel-labs/agent-skills).
    """
    project_path = os.path.abspath(os.path.expanduser(project_dir))
    os.makedirs(project_path, exist_ok=True)

    gemini_skills_dir = os.path.join(project_path, '.gemini', 'skills')
    agents_skills_dir = os.path.join(project_path, '.agents', 'skills')
    os.makedirs(gemini_skills_dir, exist_ok=True)
    os.makedirs(agents_skills_dir, exist_ok=True)

    canonical = discover_canonical_skills()
    installed = []
    remote_installed = []
    skipped = []
    not_found = []

    for skill in skill_names:
        skill = skill.strip()
        if not skill:
            continue

        # Check if it's a remote package identifier (contains '/')
        if '/' in skill:
            # Format: 'package/skill' or 'package'
            parts = skill.split('/')
            pkg = parts[0] + '/' + parts[1].split('@')[0] if len(parts) >= 2 else skill
            sub_skill = parts[2] if len(parts) > 2 else ""

            if install_remote and shutil.which("npx"):
                cmd = ["npx", "skills", "add", pkg]
                if sub_skill:
                    cmd.extend(["--skill", sub_skill])
                cmd.append("--project")
                try:
                    res = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, check=False)
                    remote_installed.append({
                        "name": skill,
                        "command": " ".join(cmd),
                        "status": "SUCCESS" if res.returncode == 0 else "FAILED",
                        "output": res.stdout.strip() or res.stderr.strip()
                    })
                except Exception as e:
                    remote_installed.append({"name": skill, "status": "ERROR", "error": str(e)})
            else:
                remote_installed.append({
                    "name": skill,
                    "command": f"npx skills add {pkg} --project",
                    "status": "QUEUED_MANUAL"
                })
            continue

        # Local canonical skill lookup
        if skill in canonical:
            src_path = canonical[skill]
            target_gemini = os.path.join(gemini_skills_dir, skill)
            target_agents = os.path.join(agents_skills_dir, skill)

            already_present = True
            for target in [target_gemini, target_agents]:
                if not os.path.exists(target) and not os.path.islink(target):
                    os.symlink(src_path, target)
                    already_present = False

            if already_present:
                skipped.append(skill)
            else:
                installed.append({
                    "name": skill,
                    "source": src_path,
                    "gemini_link": target_gemini,
                    "agents_link": target_agents
                })
        else:
            not_found.append(skill)

    return {
        "project_dir": project_path,
        "installed_local": installed,
        "remote_installed": remote_installed,
        "already_present": skipped,
        "not_found": not_found,
        "catalog_reference": REFERENCES_CATALOG if os.path.exists(REFERENCES_CATALOG) else None
    }


def main():
    parser = argparse.ArgumentParser(description="Prompt-Writer Skill Bootstrapper (Plumbing Utility)")
    parser.add_argument('--project', type=str, default=".", help="Project workspace directory")
    parser.add_argument('--skills', type=str, required=False, help="Comma-separated skills to install")
    parser.add_argument('--no-remote', action='store_true', help="Do not run npx skills add for remote packages")
    parser.add_argument('--catalog', action='store_true', help="Print location of PREFERRED_SKILLS.md catalog")
    parser.add_argument('--json', action='store_true', help="Output results in JSON format")

    args = parser.parse_args()

    if args.catalog:
        if os.path.exists(REFERENCES_CATALOG):
            print(REFERENCES_CATALOG)
        else:
            print("Catalog not found at default location.")
        return

    if not args.skills:
        parser.print_help()
        sys.exit(1)

    skill_list = [s.strip() for s in args.skills.split(',') if s.strip()]
    result = install_project_skills(
        project_dir=args.project,
        skill_names=skill_list,
        install_remote=not args.no_remote
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("Skill Bootstrapper Result")
        print("=" * 60)
        print(f"Project Target : {result['project_dir']}")

        if result['installed_local']:
            print("\n[Installed Local Skills]:")
            for item in result['installed_local']:
                print(f"  + {item['name']:25} -> {item['source']}")

        if result['already_present']:
            print("\n[Already Present in Project]:")
            for name in result['already_present']:
                print(f"  * {name}")

        if result['remote_installed']:
            print("\n[Remote skills.sh Packages]:")
            for rem in result['remote_installed']:
                status = rem.get('status', 'OK')
                cmd = rem.get('command', rem.get('name'))
                print(f"  [{status}] {cmd}")

        if result['not_found']:
            print("\n[Not Found in Local Repos]:")
            for name in result['not_found']:
                print(f"  ? {name} (Try searching via: npx skills find {name})")


if __name__ == '__main__':
    main()
