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
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SLASH_COMMAND_SKILLS = {'prompt', 'grill', 'docs', 'sync', 'google-oss', 'codelab', 'human-voice', 'copy-write', 'image-gen', 'work', 'cognitive-profiler'}
ANTIGRAVITY_RESERVED_COMMANDS = {'goal', 'schedule', 'browser', 'grill-me', 'teamwork-preview', 'learn', 'boost', 'agents', 'config', 'settings', 'clear', 'resume', 'rewind', 'undo', 'fork', 'add-dir', 'keybindings', 'codesearch', 'credits', 'diff', 'permissions', 'statusline', 'title', 'voice', 'help'}
ANTIGRAVITY_BUILTIN_SKILLS = {'agy-customizations', 'antigravity_guide', 'antigravity-guide', 'generative_ui', 'migrate-workflows', 'permissioned-github'}
ALL_RESERVED = ANTIGRAVITY_RESERVED_COMMANDS | ANTIGRAVITY_BUILTIN_SKILLS

sys.path.insert(0, SCRIPT_DIR)
try:
    from sync_skills import ALIASES
except ImportError:
    ALIASES = {}

PII_PATTERNS = [
    re.compile(r'ksprashanth@', re.IGNORECASE),
    re.compile(r'ksprashu@', re.IGNORECASE),
    re.compile(r'Prashanth Subrahmanyam', re.IGNORECASE),
]

# A home directory in a tracked file is two defects at once: it leaks the
# author's username, and the link or command is broken for everyone else. The
# 2026-09-18 review counted 49 such files while the README advertised "Zero-PII";
# the patterns below are what would have caught them.
HOST_PATH_PATTERNS = [
    re.compile(r'/Users/(?!<)[A-Za-z0-9._-]+'),
    re.compile(r'[Cc]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+'),
    re.compile(r'/home/(?!<)[A-Za-z0-9._-]+'),
]

#: Reviews and standards that quote the pattern throughout. Whole-file
#: exemptions are a blunt instrument; prefer the inline marker below, which
#: keeps the justification next to the line it excuses.
HOST_PATH_EXEMPT = {
    'docs/ENGINEERING_STANDARD.md',
    'docs/review/2026-09-23-work-skill-review.md',
    'docs/review/2026-09-18-asis-tobe.md',
    'TEST_INFRA.md',
    'scripts/validate_skills.py',
}

#: A line carrying this marker is exempt. Used by redaction code, by tests that
#: feed the scanner a bad path on purpose, and by docs showing what not to do.
HOST_PATH_INLINE_MARKER = 'host-path-ok'

HOST_PATH_SKIP_DIRS = {'.git', '.upstream', 'node_modules', '__pycache__',
                       '.pytest_cache', '.venv', 'venv', '.agents', 'output',
                       'dist', 'build'}

#: ``.html`` earns its place: the generated walkthroughs and implementation
#: plans carry `file:///Users/...` links, and leaving the suffix off meant the
#: scan reported a clean repository while 27 such links sat in tracked docs.
HOST_PATH_SUFFIXES = ('.md', '.py', '.sh', '.json', '.jsonl', '.yaml', '.yml',
                      '.cjs', '.js', '.ts', '.toml', '.cfg', '.ini', '.txt',
                      '.html')


def scan_host_paths(repo_root):
    """Fail on any machine-specific absolute path in a tracked file."""
    errors = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in HOST_PATH_SKIP_DIRS]
        for name in filenames:
            if not name.endswith(HOST_PATH_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, repo_root).replace(os.sep, '/')
            if rel in HOST_PATH_EXEMPT:
                continue
            try:
                with open(full, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            # Every hit is reported, one per line. Capping at the first match
            # turns fixing a file into whack-a-mole across repeated runs.
            for index, line in enumerate(content.splitlines()):
                if HOST_PATH_INLINE_MARKER in line:
                    continue
                for pattern in HOST_PATH_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        errors.append(
                            f"[host-path] {rel}:{index + 1} contains a machine-specific "
                            f"absolute path '{match.group(0)}'. Use a repo-relative "
                            f"path, ~, or an environment variable. If the path is "
                            f"deliberate, mark the line `{HOST_PATH_INLINE_MARKER}`.")
                        break
    return errors


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

        # Check reserved Antigravity namespace collision
        if item.lower() in ALL_RESERVED:
            errors.append(f"[{item}] Skill directory name collides with Antigravity reserved namespace: '{item}'")
        skill_name = fm.get('name')
        if skill_name and skill_name.strip().lower() in ALL_RESERVED:
            errors.append(f"[{item}] Skill frontmatter name '{skill_name}' collides with Antigravity reserved namespace")

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


def validate_aliases():
    """Verify that no backward-compatible aliases collide with reserved Antigravity names."""
    errors = []
    for alias, target in ALIASES.items():
        if alias.lower() in ALL_RESERVED:
            errors.append(f"[Alias: '{alias}'] Collides with Antigravity reserved namespace (points to '{target}')")
    return errors


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


#: Where the work skill's dispatch briefs live. Each ```json block in these
#: files is a payload the Orchestrator copies into ``invoke_subagent``.
DISPATCH_BRIEF_FILES = ('skills/work/SKILL.md', 'skills/work/references/*.md')

#: The grounding path every judging or building subagent is pointed at (W-07).
KNOWLEDGE_GROUNDING = '.gemini/knowledge/'

#: What each dispatch brief must point its subagent at, keyed by exact Role.
#: ``knowledge`` is W-07: read the project's knowledge catalog before working.
#: ``skills`` is W-08: sibling skills cited by path, so the brief delegates to
#: them instead of restating a rubric that then drifts. Both were closed in
#: prose, and prose is L1 -- nothing failed when a brief lost its grounding
#: line. A role missing from this table fails too, so a new role has to decide
#: its grounding on purpose rather than inherit none by default.
BRIEF_CONTRACTS = {
    'Design Architect Alpha': {'knowledge': True, 'skills': ()},
    'Design Architect Beta': {'knowledge': True, 'skills': ()},
    'Architectural Arbiter': {'knowledge': True, 'skills': ()},
    'Architectural Design Reviewer': {'knowledge': True,
                                      'skills': ('skills/review/SKILL.md',)},
    '5-Axis Code Reviewer': {'knowledge': True,
                             'skills': ('skills/review/SKILL.md', 'skills/unslop/SKILL.md')},
    'Adversarial Challenger': {'knowledge': True, 'skills': ('skills/test/SKILL.md',)},
    'Acceptance Reviewer': {'knowledge': True, 'skills': ()},
    'Worker Alpha — Approach A': {'knowledge': True, 'skills': ()},
    'Worker Beta — Approach B': {'knowledge': True, 'skills': ()},
    'Observability & Audit Specialist': {'knowledge': True, 'skills': ()},
    # Runs a deterministic script over the tree; there is nothing to ground.
    'Forensic Integrity Auditor': {'knowledge': False, 'skills': ()},
    # Executes cold from a clean checkout. Prior context is what it must not have.
    'Victory Auditor': {'knowledge': False, 'skills': ()},
}

_JSON_FENCE = re.compile(r'^([ \t]*)```json[ \t]*\n(.*?)^\1```', re.M | re.S)
_CITED_SKILL_PATH = re.compile(r'skills/[\w./-]+?\.md')


def iter_dispatch_briefs(repo_root):
    """Yield ``(relpath, line, payload_or_error)`` for every ```json block.

    A block that does not parse is yielded as the error string: a brief the
    linter cannot read is a brief it cannot vouch for.
    """
    import glob
    import json
    import textwrap

    for pattern in DISPATCH_BRIEF_FILES:
        for path in sorted(glob.glob(os.path.join(repo_root, pattern))):
            rel = os.path.relpath(path, repo_root).replace(os.sep, '/')
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
            for m in _JSON_FENCE.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                try:
                    data = json.loads(textwrap.dedent(m.group(2)))
                except ValueError as ex:
                    yield rel, line, f"unparseable dispatch payload: {ex}"
                    continue
                payloads = data.get('Subagents', [data]) if isinstance(data, dict) else []
                for payload in payloads:
                    if isinstance(payload, dict) and 'Prompt' in payload:
                        yield rel, line, payload


def validate_dispatch_briefs(repo_root):
    """Check every dispatch brief against ``BRIEF_CONTRACTS``. Returns errors."""
    errors = []
    for rel, line, payload in iter_dispatch_briefs(repo_root):
        where = f"[Brief: {rel}:{line}]"
        if isinstance(payload, str):
            errors.append(f"{where} {payload}")
            continue
        prompt = str(payload.get('Prompt', ''))
        role = payload.get('Role')
        for cited in sorted(set(_CITED_SKILL_PATH.findall(prompt))):
            if not os.path.isfile(os.path.join(repo_root, cited)):
                errors.append(f"{where} {role or 'payload'!s} cites {cited}, which does not exist")
        if role is None:
            # The heartbeat tick goes to the Orchestrator itself, not a subagent.
            if not prompt.startswith('Heartbeat tick'):
                errors.append(f"{where} dispatch payload has no Role, so no grounding contract applies")
            continue
        contract = BRIEF_CONTRACTS.get(role)
        if contract is None:
            errors.append(f"{where} no grounding contract for role {role!r}; "
                          f"add it to BRIEF_CONTRACTS in scripts/validate_skills.py")
            continue
        if contract['knowledge'] and KNOWLEDGE_GROUNDING not in prompt:
            errors.append(f"{where} {role} is not pointed at {KNOWLEDGE_GROUNDING} (W-07)")
        for skill in contract['skills']:
            if skill not in prompt:
                errors.append(f"{where} {role} does not cite {skill} (W-08)")
    return errors


def main():
    print("=" * 65)
    print("🔍 Agent Skill Forge — Skill Validation & PII Audit")
    print("=" * 65)

    core_dir = os.path.join(REPO_ROOT, 'skills')
    pref_dir = os.path.join(REPO_ROOT, 'preferred')

    core_count, core_errs, core_warns = validate_skill_dir(core_dir, 'core')
    pref_count, pref_errs, pref_warns = validate_skill_dir(pref_dir, 'preferred')
    dag_count, dag_errs, dag_warns = validate_dag_harness(REPO_ROOT)
    alias_errs = validate_aliases()
    path_errs = scan_host_paths(REPO_ROOT)
    brief_errs = validate_dispatch_briefs(REPO_ROOT)

    print(f"Validated {core_count} Core Skills and {pref_count} Preferred Skills.")
    print(f"Validated {dag_count} Markdown DAG Workflow Specifications.")
    print(f"Validated {len(ALIASES)} Skill Aliases against reserved namespaces.")
    print(f"Scanned the tree for machine-specific absolute paths "
          f"({len(HOST_PATH_EXEMPT)} documented exemptions).")
    print(f"Checked /work dispatch briefs against {len(BRIEF_CONTRACTS)} role grounding contracts.")
    print(f"Total Skills: {core_count + pref_count}\n")

    all_warnings = core_warns + pref_warns + dag_warns
    all_errors = core_errs + pref_errs + dag_errs + alias_errs + path_errs + brief_errs

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

