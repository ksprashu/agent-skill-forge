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
Agent Skill Forge - Design Gate (PreToolUse hook)

Makes the `brainstorm` skill's <HARD-GATE> mechanical instead of advisory.

Product-code edits are refused until an approved design artefact exists for the
current line of work. Reading, searching, docs, tests, and Markdown are never
blocked, so exploration and note-taking stay free.

  Spike         docs/design/<slug>-probe.md      approved  -> unblocked
  Bounded       docs/design/<slug>-design.md     approved  -> unblocked
  Architectural docs/design/<slug>-spec.md       approved
                docs/design/<slug>-plan.md       approved  -> unblocked
                (an approved spec alone does NOT unblock; that is the point)

An artefact counts only if it carries a `Status: approved` line and is newer
than this branch's merge-base. A design approved for last month's work does not
authorise today's. Freshness comes from git history, not filesystem mtime,
because a checkout or clone rewrites every mtime to now.

SECURITY MODEL — read this before trusting the gate
  This is a workflow guardrail, not a security boundary.

  It reliably stops an agent that is simply taking the shortest path to an
  edit: the Edit/Write/MultiEdit/NotebookEdit branch is path-scoped and exact,
  and the Bash branch catches the common shell mutations.

  The docs/tests/Markdown exemption holds on both branches, but by different
  means. The editor branch knows the exact path. The Bash branch tokenises the
  command and lets it through only when every path-shaped operand it can read
  is exempt; anything it cannot parse -- a pipeline, an interpreter one-liner,
  an extensionless target -- is blocked rather than guessed at. So the
  exemption is reliable for simple commands and conservative for the rest.

  It does not stop an agent that is actively trying to get around it. A shell
  is a general-purpose mutation engine, and BASH_MUTATORS is a pattern list;
  anything from an unusual interpreter invocation to a helper script defeats
  it. The agent can also call `design_gate.py --approve` itself, because
  writing under docs/ is deliberately never blocked.

  If you need an actual boundary, enforce it where the agent cannot reach:
  a pre-commit hook, a CI check, or branch protection. Those run outside the
  agent's tool surface. This hook runs inside it.

Usage
  design_gate.py                       read a PreToolUse event on stdin (hook mode)
  design_gate.py --approve <file>      stamp an artefact as approved
  design_gate.py --status              show what the gate currently sees
  design_gate.py --install             wire into ~/.claude/settings.json
  design_gate.py --uninstall           remove it again
  design_gate.py --self-test           run the built-in checks

Escape hatch: set FORGE_GATE=off to disable for one session.
"""

import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import time

BLOCKED_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}

# Editor tools are not the only way to change a file. A shell can do it too,
# so the same gate is applied to Bash commands that look like mutations.
#
# Read this for what it is: a speed bump wide enough to stop an agent that is
# simply taking the quickest route, not a sandbox. A shell is a general-purpose
# mutation engine and no pattern list closes it. See SECURITY MODEL in the
# module docstring.
BASH_TOOLS = {'Bash', 'BashOutput'}
BASH_MUTATORS = (
    # in-place editors and file writers
    re.compile(r'\bsed\b[^|;&]*\s-[a-zA-Z]*i'),
    re.compile(r'\bperl\b[^|;&]*\s-[a-zA-Z]*i'),
    re.compile(r'\b(?:tee|dd)\b'),
    re.compile(r'\b(?:cp|mv|install|rsync|patch|truncate|ln)\b'),
    re.compile(r'\b(?:rm|rmdir|shred)\b'),
    re.compile(r'\bgit\s+(?:apply|checkout|restore|revert|stash)\b'),
    # here-doc or redirection into a file
    re.compile(r'>>?\s*[^\s|&;<>]+'),
    # interpreter one-liners that open files for writing
    re.compile(r'\b(?:python3?|node|ruby)\b[^|;&]*-[ce]\b'),
)
# Commands that only read. Checked first, so `grep -r foo > /dev/null` and
# friends do not trip the redirection pattern for no reason.
BASH_SAFE_REDIRECT = re.compile(r'>\s*(?:/dev/null|/dev/stderr|&\d)\b')

# Never blocked. Exploration, notes, tests, and the artefacts themselves.
ALWAYS_ALLOWED_DIRS = (
    'docs/', 'doc/', 'tests/', 'test/', '__tests__/', 'spec/', 'specs/',
    '.forge/', '.upstream/', 'overlays/', '.agents/', '.github/',
)
ALWAYS_ALLOWED_GLOBS = (
    '*.md', '*.mdx', '*.txt', '*.rst', '.gitignore', '.gitattributes',
    'LICENSE*', 'CONSTRAINTS.md', 'ACCEPTANCE.md', 'AGENTS.md', 'CLAUDE.md',
    'GEMINI.md', '*.test.*', '*.spec.*', '*_test.py', 'test_*.py',
)

DESIGN_DIR = 'docs/design'
ARTEFACT_KINDS = {
    'probe': 'spike',
    'design': 'bounded',
    'spec': 'architectural',
    'plan': 'architectural',
}
APPROVED_RE = re.compile(r'^\s*(?:\*\*)?status(?:\*\*)?\s*:\s*approved\b', re.IGNORECASE | re.MULTILINE)

STALE_FALLBACK_SECONDS = 7 * 24 * 3600


# ----------------------------------------------------------------------------
# Repo helpers
# ----------------------------------------------------------------------------

def git(args, cwd):
    try:
        out = subprocess.run(
            ['git'] + args, cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def project_root(cwd):
    root = git(['rev-parse', '--show-toplevel'], cwd)
    # realpath both sides: /tmp is a symlink to /private/tmp on macOS, and a
    # mismatch there makes every path look like it is outside the project.
    return os.path.realpath(root or cwd)


def baseline_timestamp(root):
    """Epoch seconds of this branch's merge-base with the default branch.

    Artefacts older than this belong to earlier work and do not authorise
    today's edits. Falls back to a rolling window outside git.
    """
    for base in ('origin/main', 'origin/master', 'main', 'master'):
        mb = git(['merge-base', 'HEAD', base], root)
        if mb:
            ts = git(['show', '-s', '--format=%ct', mb], root)
            if ts and ts.isdigit():
                return int(ts)
    head_ts = git(['show', '-s', '--format=%ct', 'HEAD'], root)
    if head_ts and head_ts.isdigit():
        return min(int(head_ts), int(time.time()) - STALE_FALLBACK_SECONDS)
    return int(time.time()) - STALE_FALLBACK_SECONDS


# ----------------------------------------------------------------------------
# Path classification
# ----------------------------------------------------------------------------

def normalise_rel(rel_path):
    """Strip a leading './' without eating leading dots.

    str.lstrip('./') removes every leading '.' and '/' character, so
    '.github/workflows/ci.yml' became 'github/workflows/ci.yml' and stopped
    matching the '.github/' exemption. Only the prefix should go.
    """
    norm = rel_path.replace(os.sep, '/')
    while norm.startswith('./'):
        norm = norm[2:]
    return norm.lstrip('/')


def is_always_allowed(rel_path):
    norm = normalise_rel(rel_path)
    if any(norm.startswith(d) or f'/{d}' in f'/{norm}' for d in ALWAYS_ALLOWED_DIRS):
        return True
    base = os.path.basename(norm)
    return any(fnmatch.fnmatch(base, g) for g in ALWAYS_ALLOWED_GLOBS)


# ----------------------------------------------------------------------------
# Artefact scanning
# ----------------------------------------------------------------------------

def artefact_timestamp(root, rel):
    """When this artefact last genuinely changed, in epoch seconds.

    Filesystem mtime is not trustworthy here. `git checkout`, `git reset`, a
    fresh clone, or a stash pop all rewrite mtimes to now, which would make a
    long-superseded approved design look like current work and reopen the
    gate. So for anything git knows about, ask git.

    - Untracked, or tracked with uncommitted changes -> this is live work.
      Return now.
    - Otherwise -> the commit time of the last commit that touched it.
    - Not a git repo at all -> fall back to mtime, which is all we have.
    """
    full = os.path.join(root, rel)
    if not os.path.isdir(os.path.join(root, '.git')):
        try:
            return os.path.getmtime(full)
        except OSError:
            return 0

    tracked = git(['ls-files', '--error-unmatch', rel], root) is not None
    if not tracked:
        return time.time()

    # Tracked but dirty in the working tree means someone is editing it now.
    if git(['diff', '--quiet', 'HEAD', '--', rel], root) is None:
        return time.time()

    ts = git(['log', '-1', '--format=%ct', '--', rel], root)
    if ts and ts.isdigit():
        return int(ts)
    try:
        return os.path.getmtime(full)
    except OSError:
        return 0


def scan_artefacts(root):
    """Return {kind: [(path, slug, approved, fresh)]} for everything in docs/design.

    The slug is the stem with the `-<kind>` suffix removed, so
    `payment-retry-spec.md` yields slug `payment-retry`. evaluate() needs it to
    pair a spec with its own plan rather than with any plan lying around.
    """
    found = {k: [] for k in ARTEFACT_KINDS}
    ddir = os.path.join(root, DESIGN_DIR)
    if not os.path.isdir(ddir):
        return found
    baseline = baseline_timestamp(root)
    for name in sorted(os.listdir(ddir)):
        if not name.endswith('.md'):
            continue
        stem = name[:-3]
        kind = next((k for k in ARTEFACT_KINDS if stem.endswith(f'-{k}')), None)
        if not kind:
            continue
        slug = stem[:-(len(kind) + 1)]
        full = os.path.join(ddir, name)
        rel = f'{DESIGN_DIR}/{name}'
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            approved = bool(APPROVED_RE.search(text))
        except OSError:
            continue
        fresh = artefact_timestamp(root, rel) >= baseline
        found[kind].append((rel, slug, approved, fresh))
    return found


def evaluate(root):
    """Decide whether the gate is open. Returns (open: bool, reason, detail)."""
    found = scan_artefacts(root)

    def live(kind):
        return [(p, slug) for p, slug, ok, fresh in found[kind] if ok and fresh]

    probes, designs = live('probe'), live('design')
    specs, plans = live('spec'), live('plan')

    if specs:
        # Pair by slug. Combining the two lists independently meant an approved
        # `alpha-spec.md` plus an approved `beta-plan.md` opened the gate, so
        # work nobody planned could ride in on a plan written for something
        # else. The whole point of requiring both is that the plan is *this*
        # spec's plan.
        plan_slugs = {slug: p for p, slug in plans}
        paired = [(sp, plan_slugs[slug]) for sp, slug in specs if slug in plan_slugs]
        if paired:
            spec_path, plan_path = paired[0]
            return True, 'architectural', (
                f"spec {spec_path} and its plan {plan_path} are approved")

        orphans = ', '.join(sorted(slug for _, slug in specs))
        stray = ', '.join(sorted(slug for _, slug in plans))
        extra = ''
        if stray:
            extra = (f"\n  Approved plan(s) exist for a different slug ({stray}). "
                     f"A plan only\n  authorises the spec it belongs to.")
        return False, 'architectural-plan-missing', (
            f"An approved spec exists ({specs[0][0]}) but no approved plan with\n"
            f"  the matching slug. Approving a spec only permits writing the plan.\n"
            f"  Write {DESIGN_DIR}/{orphans.split(', ')[0]}-plan.md, get it approved,\n"
            f"  then edit.{extra}"
        )
    if designs:
        return True, 'bounded', f"design {designs[0][0]} is approved"
    if probes:
        return True, 'spike', f"probe {probes[0][0]} is approved"

    stale = [p for k in found for p, _slug, ok, fresh in found[k] if ok and not fresh]
    unapproved = [p for k in found for p, _slug, ok, _ in found[k] if not ok]
    detail = ''
    if stale:
        detail = (
            f"\n  Found approved but stale artefact(s): {', '.join(stale[:3])}\n"
            f"  These predate this branch's merge-base, so they do not authorise this work."
        )
    elif unapproved:
        detail = (
            f"\n  Found artefact(s) without a `Status: approved` line: {', '.join(unapproved[:3])}\n"
            f"  A human writes that line. Stamp one with:\n"
            f"    python3 hooks/design_gate.py --approve <file>"
        )
    return False, 'no-artefact', detail


def block_message(rel_path, reason, detail):
    if reason == 'architectural-plan-missing':
        body = detail
    else:
        body = (
            f"No approved design artefact for this line of work.{detail}\n\n"
            f"  Run the `brainstorm` skill, pick a path, and get its artefact approved:\n\n"
            f"    Spike          {DESIGN_DIR}/<slug>-probe.md\n"
            f"    Bounded        {DESIGN_DIR}/<slug>-design.md\n"
            f"    Architectural  {DESIGN_DIR}/<slug>-spec.md  then  <slug>-plan.md\n"
        )
    return (
        f"BLOCKED by Agent Skill Forge design gate: {rel_path}\n\n"
        f"  {body}\n"
        f"  Reading, searching, docs/, tests/, and Markdown are never blocked.\n"
        f"  To disable for this session: FORGE_GATE=off\n"
    )


# ----------------------------------------------------------------------------
# Hook mode
# ----------------------------------------------------------------------------

def looks_like_mutation(command):
    """Does this shell command look like it writes to the filesystem?"""
    if not command:
        return False
    stripped = BASH_SAFE_REDIRECT.sub('', command)
    return any(p.search(stripped) for p in BASH_MUTATORS)


# A token that looks like a path we could classify, and is not a flag, a URL,
# or a shell variable. It must end in a file extension: that is what separates
# `docs/notes.md` from a sed script like `s/a/b/`, which is full of slashes and
# is not a path at all. Extensionless operands (`rm -rf build`) simply are not
# classifiable here, so the caller falls through to blocking.
PATH_TOKEN_RE = re.compile(r'^[A-Za-z0-9._~@/\\-]+\.[A-Za-z0-9]{1,6}$')


def bash_path_operands(command):
    """Best-effort list of filesystem paths a shell command names.

    This exists only to honour one promise: docs/, tests/ and Markdown are
    never blocked. That promise was written for the editor branch and the Bash
    branch broke it, refusing `sed -i docs/notes.md` while the gate was shut.

    It is a tokeniser, not a shell. It is used in one direction only -- to let
    a command through when *every* path it names is exempt. If nothing
    path-shaped can be extracted, or one operand is not exempt, the caller
    falls through to blocking. Being wrong here can only ever be conservative.
    """
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        return []  # Unbalanced quotes. Cannot reason about it; do not try.

    paths = []
    for tok in tokens:
        if tok.startswith('-') or '://' in tok or '$' in tok or '*' in tok:
            continue
        if tok in ('>', '>>', '|', '&&', ';'):
            continue
        while tok.startswith('>'):
            tok = tok[1:]
        if tok and PATH_TOKEN_RE.match(tok):
            paths.append(tok)
    return paths


def bash_targets_only_allowed_paths(command, root):
    """True when the command names at least one path and all of them are exempt."""
    operands = bash_path_operands(command)
    checked = []
    for tok in operands:
        if os.path.isabs(tok):
            real = os.path.realpath(tok)
            try:
                rel = os.path.relpath(real, os.path.realpath(root))
            except ValueError:
                return False
            if rel.startswith('..'):
                return False  # Outside the project. Not ours to wave through.
            tok = rel
        checked.append(tok)

    return bool(checked) and all(is_always_allowed(t) for t in checked)


def run_hook_bash(tool_input, cwd):
    """Apply the gate to shell commands that look like they mutate files.

    Shell commands cannot be path-scoped the way the editor branch is -- the
    paths a command touches are not knowable without running it. So the check
    runs the other way round: if every path the command names is one the gate
    never blocks, let it through; otherwise, once the gate is shut, refuse and
    say what tripped it.
    """
    command = tool_input.get('command') or ''
    if not looks_like_mutation(command):
        return 0

    root = project_root(cwd)
    if bash_targets_only_allowed_paths(command, root):
        return 0

    is_open, reason, detail = evaluate(root)
    if is_open:
        return 0

    sys.stderr.write(
        "BLOCKED by the forge design gate.\n\n"
        f"  This shell command looks like it modifies files:\n    {command[:200]}\n\n"
        "  No approved design artefact covers this work yet, so the gate is shut\n"
        "  for writes of any kind, not just Edit and Write.\n"
        f"{detail}\n\n"
        "  docs/, tests/ and Markdown are exempt, but only when every path in\n"
        "  the command is one of those and the command is simple enough to read.\n"
        "  A pipeline or an interpreter one-liner cannot be checked that way.\n\n"
        "  If this command only reads, re-run it in a form that cannot write,\n"
        "  or set FORGE_GATE=off for this session if you know what you are doing.\n"
    )
    return 2


def run_hook():
    if os.environ.get('FORGE_GATE', '').lower() in ('off', '0', 'false', 'disabled'):
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Never break the harness on a malformed event.

    tool = event.get('tool_name', '')
    tool_input = event.get('tool_input') or {}
    cwd = event.get('cwd') or os.getcwd()

    if tool in BASH_TOOLS:
        return run_hook_bash(tool_input, cwd)

    if tool not in BLOCKED_TOOLS:
        return 0

    file_path = tool_input.get('file_path') or tool_input.get('notebook_path') or ''
    if not file_path:
        return 0

    root = project_root(cwd)

    try:
        rel = os.path.relpath(os.path.realpath(file_path), root)
    except ValueError:
        return 0
    if rel.startswith('..'):
        return 0  # Outside the project. Not ours to police.

    if is_always_allowed(rel):
        return 0

    is_open, reason, detail = evaluate(root)
    if is_open:
        return 0

    sys.stderr.write(block_message(rel, reason, detail))
    return 2  # Exit 2 blocks the tool call and shows stderr to the model.


# ----------------------------------------------------------------------------
# CLI modes
# ----------------------------------------------------------------------------

def cmd_approve(path):
    if not os.path.exists(path):
        print(f"  No such file: {path}")
        return 1
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    if APPROVED_RE.search(text):
        print(f"  Already approved: {path}")
        return 0
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    lines = text.split('\n')
    insert_at = 0
    if lines and lines[0].startswith('# '):
        insert_at = 1
    lines.insert(insert_at, f"\nStatus: approved\nApproved-at: {stamp}\n")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    os.utime(path, None)
    print(f"  Approved: {path}")

    # Say what actually happened. Approving a spec does not open the gate.
    is_open, reason, detail = evaluate(project_root(os.path.dirname(os.path.abspath(path)) or os.getcwd()))
    if is_open:
        print(f"  Gate is now OPEN for product-code edits on this branch.")
    else:
        print(f"  Gate is still CLOSED.")
        if detail:
            print(f"  {detail.strip()}")
    return 0


def cmd_status():
    root = project_root(os.getcwd())
    print("=" * 74)
    print(" 🚧 Agent Skill Forge — Design Gate Status")
    print("=" * 74)
    print()
    if os.environ.get('FORGE_GATE', '').lower() in ('off', '0', 'false', 'disabled'):
        print("  FORGE_GATE=off — the gate is disabled for this session.")
        print()
    print(f"  Project root : {root}")
    print(f"  Design dir   : {os.path.join(root, DESIGN_DIR)}")
    baseline = baseline_timestamp(root)
    print(f"  Baseline     : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(baseline))}"
          f"  (artefacts older than this do not count)")
    print()

    found = scan_artefacts(root)
    any_found = False
    for kind, entries in found.items():
        for path, approved, fresh in entries:
            any_found = True
            flag = 'approved' if approved else 'NOT approved'
            age = 'current' if fresh else 'STALE'
            print(f"  [{ARTEFACT_KINDS[kind]:<14}] {path:<44} {flag:<13} {age}")
    if not any_found:
        print("  No design artefacts found.")
    print()

    is_open, reason, detail = evaluate(root)
    if is_open:
        print(f"  GATE OPEN — {detail}")
    else:
        print(f"  GATE CLOSED — {reason}{detail}")
    return 0


CLAUDE_SETTINGS = os.path.expanduser('~/.claude/settings.json')


def hook_command(script_path):
    """The command line Claude Code will run for every matched tool call.

    It records the interpreter that is running this installer, not the literal
    string `python3`. install.ps1 deliberately searches for python3.12, py,
    python3 and python in that order, so on a Windows box where only `py`
    exists a hard-coded `python3` installs cleanly and then fails to start on
    every single tool call.
    """
    return f'"{sys.executable}" "{script_path}"'


def hook_entry(script_path):
    return {
        'matcher': 'Edit|Write|MultiEdit|NotebookEdit|Bash',
        'hooks': [{'type': 'command', 'command': hook_command(script_path)}],
    }


def cmd_install():
    script_path = os.path.abspath(__file__)
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS), exist_ok=True)
    settings = {}
    if os.path.exists(CLAUDE_SETTINGS):
        try:
            with open(CLAUDE_SETTINGS, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"  {CLAUDE_SETTINGS} is not valid JSON. Fix it first; nothing was changed.")
            return 1

    hooks = settings.setdefault('hooks', {})
    pre = hooks.setdefault('PreToolUse', [])
    for group in pre:
        for h in group.get('hooks', []):
            if 'design_gate.py' in h.get('command', ''):
                h['command'] = hook_command(script_path)
                _write_settings(settings)
                print(f"  Design gate already present; path refreshed in {CLAUDE_SETTINGS}")
                print(f"  Interpreter: {sys.executable}")
                return 0
    pre.append(hook_entry(script_path))
    _write_settings(settings)
    print(f"  Design gate installed into {CLAUDE_SETTINGS}")
    print(f"  Matches: Edit, Write, MultiEdit, NotebookEdit, Bash")
    print(f"  Interpreter: {sys.executable}")
    print(f"  Disable for one session with: FORGE_GATE=off")
    return 0


def cmd_uninstall():
    if not os.path.exists(CLAUDE_SETTINGS):
        print("  Nothing to remove.")
        return 0
    try:
        with open(CLAUDE_SETTINGS, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f"  {CLAUDE_SETTINGS} is not valid JSON. Nothing was changed.")
        return 1
    pre = settings.get('hooks', {}).get('PreToolUse', [])
    kept = []
    removed = 0
    for group in pre:
        inner = [h for h in group.get('hooks', []) if 'design_gate.py' not in h.get('command', '')]
        removed += len(group.get('hooks', [])) - len(inner)
        if inner:
            group['hooks'] = inner
            kept.append(group)
    if removed:
        settings['hooks']['PreToolUse'] = kept
        _write_settings(settings)
        print(f"  Removed the design gate from {CLAUDE_SETTINGS}")
    else:
        print("  Design gate was not installed.")
    return 0


def _write_settings(settings):
    with open(CLAUDE_SETTINGS, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')


# ----------------------------------------------------------------------------
# Self-test
# ----------------------------------------------------------------------------

def cmd_self_test():
    import tempfile
    failures = []

    def check(label, actual, expected):
        if actual == expected:
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}: got {actual!r}, expected {expected!r}")
            failures.append(label)

    check('docs/ allowed', is_always_allowed('docs/design/foo-spec.md'), True)
    check('tests/ allowed', is_always_allowed('tests/test_auth.py'), True)
    check('markdown allowed', is_always_allowed('notes.md'), True)
    check('README allowed', is_always_allowed('README.md'), True)
    check('test file allowed', is_always_allowed('src/auth.test.ts'), True)
    check('nested test dir allowed', is_always_allowed('pkg/tests/helper.py'), True)
    check('src blocked', is_always_allowed('src/auth.py'), False)
    check('scripts blocked', is_always_allowed('scripts/deploy.sh'), False)

    # Regression: lstrip('./') used to eat the leading dot of dotted dirs,
    # so these documented exemptions silently stopped matching.
    check('.github/ allowed', is_always_allowed('.github/workflows/ci.yml'), True)
    check('.forge/ allowed', is_always_allowed('.forge/state.json'), True)
    check('.upstream/ allowed', is_always_allowed('.upstream/grill/SKILL.md'), True)
    check('./ prefix stripped', is_always_allowed('./docs/x-spec.md'), True)
    check('./ prefix on src still blocked', is_always_allowed('./src/auth.py'), False)

    # Bash mutation detection
    check('sed -i is a mutation', looks_like_mutation("sed -i '' s/a/b/ src/x.py"), True)
    check('tee is a mutation', looks_like_mutation('echo hi | tee src/x.py'), True)
    check('redirect is a mutation', looks_like_mutation('echo hi > src/x.py'), True)
    check('append is a mutation', looks_like_mutation('echo hi >> src/x.py'), True)
    check('cp is a mutation', looks_like_mutation('cp a.py b.py'), True)
    check('rm is a mutation', looks_like_mutation('rm -rf build'), True)
    check('git checkout is a mutation', looks_like_mutation('git checkout -- src'), True)
    check('python -c is a mutation', looks_like_mutation('python3 -c "open(1,\'w\')"'), True)
    check('grep is not', looks_like_mutation('grep -rn foo src/'), False)
    check('ls is not', looks_like_mutation('ls -la'), False)
    check('cat is not', looks_like_mutation('cat README.md'), False)
    check('/dev/null redirect is not', looks_like_mutation('make test > /dev/null'), False)
    check('git status is not', looks_like_mutation('git status --short'), False)

    # The Bash branch must honour the same exemptions the editor branch does.
    # It used to block every detected write regardless of path, so a shut gate
    # refused `sed -i docs/notes.md` -- which the contract says is never
    # blocked.
    def only_allowed(cmd):
        return bash_targets_only_allowed_paths(cmd, '/tmp/forge-selftest')

    check('sed on docs is exempt', only_allowed("sed -i '' s/a/b/ docs/notes.md"), True)
    check('write into tests/ is exempt', only_allowed('echo x > tests/test_a.py'), True)
    check('cp between docs is exempt', only_allowed('cp docs/a.md docs/b.md'), True)
    check('markdown anywhere is exempt', only_allowed('rm CHANGELOG.md'), True)
    check('sed on src is not exempt', only_allowed("sed -i '' s/a/b/ src/auth.py"), False)
    check('mixed docs and src is not exempt',
          only_allowed('cp docs/a.md src/auth.py'), False)
    check('no readable operand is not exempt',
          only_allowed('python3 -c "open(\'src/x.py\',\'w\')"'), False)
    check('unbalanced quotes are not exempt', only_allowed('sed -i "docs/a.md'), False)
    check('path outside the project is not exempt',
          only_allowed('rm /etc/hosts.md'), False)

    # The installed hook must name the interpreter that installed it. A literal
    # 'python3' breaks on a Windows box where only `py` or python3.12 exists.
    check('hook records a real interpreter',
          hook_command('/x/design_gate.py').startswith(f'"{sys.executable}"'), True)
    check('hook does not hard-code python3',
          hook_command('/x/design_gate.py').startswith('python3 '), False)

    with tempfile.TemporaryDirectory() as tmp:
        ddir = os.path.join(tmp, DESIGN_DIR)
        os.makedirs(ddir)

        check('empty -> closed', evaluate(tmp)[0], False)

        probe = os.path.join(ddir, 'x-probe.md')
        with open(probe, 'w') as f:
            f.write('# Probe\n\nQuestion?\n')
        check('unapproved probe -> closed', evaluate(tmp)[0], False)

        with open(probe, 'w') as f:
            f.write('# Probe\n\nStatus: approved\n\nQuestion?\n')
        check('approved probe -> open', evaluate(tmp)[0], True)

        os.remove(probe)
        spec = os.path.join(ddir, 'y-spec.md')
        with open(spec, 'w') as f:
            f.write('# Spec\n\nStatus: approved\n')
        is_open, reason, _ = evaluate(tmp)
        check('approved spec alone -> closed', is_open, False)
        check('reason is plan-missing', reason, 'architectural-plan-missing')

        # A plan for a *different* slug must not authorise this spec. The two
        # lists used to be combined independently, so any approved plan opened
        # the gate for any approved spec.
        other_plan = os.path.join(ddir, 'unrelated-plan.md')
        with open(other_plan, 'w') as f:
            f.write('# Plan\n\nStatus: approved\n')
        is_open, reason, _ = evaluate(tmp)
        check('spec + mismatched plan -> closed', is_open, False)
        check('mismatched plan reason', reason, 'architectural-plan-missing')
        os.remove(other_plan)

        plan = os.path.join(ddir, 'y-plan.md')
        with open(plan, 'w') as f:
            f.write('# Plan\n\n**Status**: approved\n')
        check('spec + matching plan -> open', evaluate(tmp)[0], True)

        stale = os.path.join(tmp, DESIGN_DIR, 'z-design.md')
        os.remove(spec)
        os.remove(plan)
        with open(stale, 'w') as f:
            f.write('# Design\n\nStatus: approved\n')
        old = time.time() - (400 * 24 * 3600)
        os.utime(stale, (old, old))
        check('stale artefact -> closed', evaluate(tmp)[0], False)

    print()
    if failures:
        print(f"  {len(failures)} check(s) failed.")
        return 1
    print("  All design gate checks passed.")
    return 0


def main():
    p = argparse.ArgumentParser(description="Agent Skill Forge design gate (PreToolUse hook)")
    p.add_argument('--approve', metavar='FILE', help="Stamp a design artefact as approved")
    p.add_argument('--status', action='store_true', help="Show what the gate currently sees")
    p.add_argument('--install', action='store_true', help="Wire into ~/.claude/settings.json")
    p.add_argument('--uninstall', action='store_true', help="Remove from ~/.claude/settings.json")
    p.add_argument('--self-test', action='store_true', help="Run the built-in checks")
    args = p.parse_args()

    if args.approve:
        return cmd_approve(args.approve)
    if args.status:
        return cmd_status()
    if args.install:
        return cmd_install()
    if args.uninstall:
        return cmd_uninstall()
    if args.self_test:
        return cmd_self_test()
    return run_hook()


if __name__ == '__main__':
    sys.exit(main())
