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
Agent Skill Forge - Skill Linter & Security Verifier
"""

import os
import sys
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SLASH_COMMAND_SKILLS = {'prompt', 'grill', 'docs', 'sync', 'google-oss', 'codelab', 'voice', 'copy-write', 'image-gen'}
PII_PATTERNS = [
    re.compile(r'ksprashanth@', re.IGNORECASE),
    re.compile(r'ksprashu@', re.IGNORECASE),
    re.compile(r'Prashanth Subrahmanyam', re.IGNORECASE),
]


def parse_frontmatter(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None, content

    fm_raw = match.group(1)
    fm = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            fm[key.strip()] = val.strip()

    return fm, content


def validate_skill_dir(base_dir, skill_type):
    errors = []
    warnings = []
    count = 0

    if not os.path.exists(base_dir):
        return 0, [f"Directory missing: {base_dir}"], []

    for item in sorted(os.listdir(base_dir)):
        skill_path = os.path.join(base_dir, item)
        if not os.path.isdir(skill_path):
            continue

        skill_md = os.path.join(skill_path, 'SKILL.md')
        if not os.path.exists(skill_md):
            errors.append(f"[{item}] Missing SKILL.md in {skill_path}")
            continue

        count += 1
        fm, body = parse_frontmatter(skill_md)
        if not fm:
            errors.append(f"[{item}] Missing or malformed YAML frontmatter in {skill_md}")
            continue

        if 'name' not in fm:
            errors.append(f"[{item}] Frontmatter missing 'name'")
        if 'description' not in fm:
            errors.append(f"[{item}] Frontmatter missing 'description'")

        # Check slash command gating
        if item in SLASH_COMMAND_SKILLS:
            dmi = fm.get('disable-model-invocation', '').lower()
            if dmi != 'true':
                warnings.append(f"[{item}] Slash command skill should have 'disable-model-invocation: true'")

        # PII Check
        for pat in PII_PATTERNS:
            if pat.search(body) or pat.search(str(fm)):
                # Ignore .local.md references
                errors.append(f"[{item}] Potential PII match found in {skill_md}: {pat.pattern}")

    return count, errors, warnings


def main():
    print("=" * 65)
    print("🔍 Agent Skill Forge — Skill Validation & PII Audit")
    print("=" * 65)

    core_dir = os.path.join(REPO_ROOT, 'skills')
    pref_dir = os.path.join(REPO_ROOT, 'preferred')

    core_count, core_errs, core_warns = validate_skill_dir(core_dir, 'core')
    pref_count, pref_errs, pref_warns = validate_skill_dir(pref_dir, 'preferred')

    print(f"Validated {core_count} Core Skills and {pref_count} Preferred Skills.")
    print(f"Total Skills: {core_count + pref_count}\n")

    all_warnings = core_warns + pref_warns
    all_errors = core_errs + pref_errs

    if all_warnings:
        print("⚠️  Warnings:")
        for w in all_warnings:
            print(f"   {w}")
        print()

    if all_errors:
        print("❌ Errors Found:")
        for e in all_errors:
            print(f"   {e}")
        print()
        sys.exit(1)

    print("✅ All skills passed validation with 0 PII leaks and clean frontmatter!\n")


if __name__ == '__main__':
    main()
