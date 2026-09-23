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
authorise today's.

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
import subprocess
import sys
import time

BLOCKED_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}

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

def is_always_allowed(rel_path):
    norm = rel_path.replace(os.sep, '/').lstrip('./')
    if any(norm.startswith(d) or f'/{d}' in f'/{norm}' for d in ALWAYS_ALLOWED_DIRS):
        return True
    base = os.path.basename(norm)
    return any(fnmatch.fnmatch(base, g) for g in ALWAYS_ALLOWED_GLOBS)


# ----------------------------------------------------------------------------
# Artefact scanning
# ----------------------------------------------------------------------------

def scan_artefacts(root):
    """Return {kind: [(path, approved, fresh)]} for everything in docs/design."""
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
        full = os.path.join(ddir, name)
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            approved = bool(APPROVED_RE.search(text))
            fresh = os.path.getmtime(full) >= baseline
        except OSError:
            continue
        found[kind].append((os.path.join(DESIGN_DIR, name), approved, fresh))
    return found


def evaluate(root):
    """Decide whether the gate is open. Returns (open: bool, reason, detail)."""
    found = scan_artefacts(root)

    def live(kind):
        return [p for p, ok, fresh in found[kind] if ok and fresh]

    probes, designs, specs, plans = live('probe'), live('design'), live('spec'), live('plan')

    if specs:
        if plans:
            return True, 'architectural', f"spec {specs[0]} and plan {plans[0]} are approved"
        return False, 'architectural-plan-missing', (
            f"An approved spec exists ({specs[0]}) but no approved plan.\n"
            f"  Approving a spec only permits writing the plan. Write\n"
            f"  {DESIGN_DIR}/<slug>-plan.md, get it approved, then edit."
        )
    if designs:
        return True, 'bounded', f"design {designs[0]} is approved"
    if probes:
        return True, 'spike', f"probe {probes[0]} is approved"

    stale = [p for k in found for p, ok, fresh in found[k] if ok and not fresh]
    unapproved = [p for k in found for p, ok, _ in found[k] if not ok]
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

def run_hook():
    if os.environ.get('FORGE_GATE', '').lower() in ('off', '0', 'false', 'disabled'):
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Never break the harness on a malformed event.

    tool = event.get('tool_name', '')
    if tool not in BLOCKED_TOOLS:
        return 0

    tool_input = event.get('tool_input') or {}
    file_path = tool_input.get('file_path') or tool_input.get('notebook_path') or ''
    if not file_path:
        return 0

    cwd = event.get('cwd') or os.getcwd()
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


def hook_entry(script_path):
    return {
        'matcher': 'Edit|Write|MultiEdit|NotebookEdit',
        'hooks': [{'type': 'command', 'command': f'python3 "{script_path}"'}],
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
                h['command'] = f'python3 "{script_path}"'
                _write_settings(settings)
                print(f"  Design gate already present; path refreshed in {CLAUDE_SETTINGS}")
                return 0
    pre.append(hook_entry(script_path))
    _write_settings(settings)
    print(f"  Design gate installed into {CLAUDE_SETTINGS}")
    print(f"  Matches: Edit, Write, MultiEdit, NotebookEdit")
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

        plan = os.path.join(ddir, 'y-plan.md')
        with open(plan, 'w') as f:
            f.write('# Plan\n\n**Status**: approved\n')
        check('spec + plan -> open', evaluate(tmp)[0], True)

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
