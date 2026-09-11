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

if sys.platform == 'win32':
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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


def validate_dag_harness(repo_root):
    """
    Validates canonical Markdown DAG specifications and templates across skills/
    fixtures and references using skills/work/scripts/dag_validator.py.
    """
    errors = []
    warnings = []
    dag_script = os.path.join(repo_root, 'skills', 'work', 'scripts', 'dag_validator.py')
    if not os.path.exists(dag_script):
        return 0, [f"Missing DAG validator harness: {dag_script}"], []

    sys.path.insert(0, os.path.join(repo_root, 'skills', 'work', 'scripts'))
    try:
        from dag_validator import DAGValidator
    except Exception as ex:
        return 0, [f"Failed to import DAGValidator: {ex}"], []

    validator = DAGValidator(check_artifacts=False, base_dir=repo_root)

    fixture_dirs = [
        os.path.join(repo_root, 'skills', 'work', 'fixtures'),
        os.path.join(repo_root, 'skills', 'work', 'references'),
        os.path.join(repo_root, 'skills', 'plan', 'references'),
    ]

    valid_count = 0
    for d in fixture_dirs:
        if not os.path.exists(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith('.md'):
                fpath = os.path.join(d, f)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        content = fh.read()
                    if '|' in content and re.search(r'\|\s*(id|#|task\s*id)\s*\|', content, re.IGNORECASE):
                        report = validator.validate(content)
                        if not report.valid:
                            errors.append(f"[DAG: {f}] Validation failed in {fpath}: {'; '.join(report.errors)}")
                        else:
                            valid_count += 1
                except Exception as ex:
                    errors.append(f"[DAG: {f}] Exception during validation: {ex}")

    return valid_count, errors, warnings


def main():
    print("=" * 65)
    print("🔍 Agent Skill Forge — Skill Validation & PII Audit")
    print("=" * 65)

    core_dir = os.path.join(REPO_ROOT, 'skills')
    pref_dir = os.path.join(REPO_ROOT, 'preferred')

    core_count, core_errs, core_warns = validate_skill_dir(core_dir, 'core')
    pref_count, pref_errs, pref_warns = validate_skill_dir(pref_dir, 'preferred')
    dag_count, dag_errs, dag_warns = validate_dag_harness(REPO_ROOT)

    print(f"Validated {core_count} Core Skills and {pref_count} Preferred Skills.")
    print(f"Validated {dag_count} Markdown DAG Workflow Specifications.")
    print(f"Total Skills: {core_count + pref_count}\n")

    all_warnings = core_warns + pref_warns + dag_warns
    all_errors = core_errs + pref_errs + dag_errs

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

    print("✅ All skills and DAG workflow specifications passed validation with 0 PII leaks and clean frontmatter!\n")


if __name__ == '__main__':
    main()

