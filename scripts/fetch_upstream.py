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
Agent Skill Forge - Reference-Only Upstream Skill Fetcher

Upstream skills are never vendored into this repository. They are resolved at
install time from a pinned commit SHA, cached, and materialised into
<repo>/.upstream/<name>/ where the symlink manager can reach them.

  fetch_upstream.py                 # fetch everything in the lock file
  fetch_upstream.py --skills grill,prove
  fetch_upstream.py --offline       # cache only; fail loudly on a miss
  fetch_upstream.py --non-interactive   # skip skills that need a live human
  fetch_upstream.py --verify        # check materialised trees against the manifest
  fetch_upstream.py --upgrade       # re-resolve to upstream HEAD and show the diff
  fetch_upstream.py --status        # what is pinned, cached, materialised

Requires only the Python standard library.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

if sys.platform == 'win32':
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
LOCK_FILE = os.path.join(REPO_ROOT, 'config', 'upstream.lock.json')
OVERLAY_DIR = os.path.join(REPO_ROOT, 'overlays')
MANIFEST_NAME = '.forge-manifest.json'
# Every overlay opens with this heading, so the provenance block can point at
# an exact line and say "forge text starts here" rather than claiming the whole
# body is upstream's.
OVERLAY_HEADING = '## In the forge'

API = 'https://api.github.com'
RAW = 'https://raw.githubusercontent.com'
UA = 'agent-skill-forge-fetcher'

# Upstream skills carry executable helpers. Only these extensions are written.
ALLOWED_SUFFIXES = {
    '.md', '.mdx', '.txt', '.rst', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini',
    '.py', '.sh', '.bash', '.zsh', '.ps1', '.rb', '.go',
    '.js', '.mjs', '.cjs', '.jsx', '.ts', '.mts', '.cts', '.tsx',
    '.css', '.html', '.svg', '.dot', '.csv', '',
}
MAX_FILE_BYTES = 2 * 1024 * 1024


class FetchError(Exception):
    pass


# ----------------------------------------------------------------------------
# Lock file
# ----------------------------------------------------------------------------

SHA_RE = re.compile(r'^[0-9a-f]{40}$')


def load_lock():
    if not os.path.exists(LOCK_FILE):
        raise FetchError(f"Lock file not found: {LOCK_FILE}")
    with open(LOCK_FILE, 'r', encoding='utf-8') as f:
        lock = json.load(f)

    # The whole reproducibility claim rests on every ref being a full commit
    # SHA. A branch name resolves to different content over time and a short
    # SHA can become ambiguous, so reject both here rather than discovering it
    # after the fetch. This runs before any network or cache access.
    skills = lock.get('skills') or {}
    bad = []
    for name, entry in sorted(skills.items()):
        ref = entry.get('ref')
        if not isinstance(ref, str) or not SHA_RE.match(ref):
            bad.append(f"    {name}: {ref!r}")
    if bad:
        raise FetchError(
            "Lock file has refs that are not 40-character commit SHAs:\n"
            + "\n".join(bad)
            + "\n  Branches and tags are not allowed: they move, and a force-push"
              "\n  would silently change what gets installed. Pin a commit."
        )
    return lock


def cache_root(lock):
    return os.path.expanduser(lock.get('cache_dir', '~/.cache/agent-skill-forge'))


def materialise_root(lock):
    return os.path.join(REPO_ROOT, lock.get('materialise_dir', '.upstream'))


def repo_slug(repo):
    return repo.replace('/', '__')


def cache_path(lock, entry):
    return os.path.join(cache_root(lock), f"{repo_slug(entry['repo'])}@{entry['ref']}", entry['path'])


# ----------------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------------

def github_token():
    for var in ('GITHUB_TOKEN', 'GH_TOKEN'):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(
            ['gh', 'auth', 'token'], capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def http_get(url, token=None, accept='application/vnd.github+json'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 403 and 'rate limit' in e.read().decode('utf-8', 'replace').lower():
            raise FetchError(
                f"GitHub rate limit hit on {url}\n"
                f"  Set GITHUB_TOKEN, or run `gh auth login`, then retry."
            )
        raise FetchError(f"HTTP {e.code} for {url}")
    except urllib.error.URLError as e:
        raise FetchError(f"Network error for {url}: {e.reason}")


def list_dir(repo, path, ref, token):
    """List one directory at a pinned ref. Returns [(name, type, path)]."""
    url = f"{API}/repos/{repo}/contents/{path}?ref={ref}"
    data = json.loads(http_get(url, token))
    if isinstance(data, dict):
        raise FetchError(f"{repo}/{path}@{ref[:8]} is a file, expected a directory")
    return [(e['name'], e['type'], e['path']) for e in data]


def download_blob(repo, path, ref, token):
    """Fetch one file's bytes. Raw host first; API fallback for private repos."""
    raw_url = f"{RAW}/{repo}/{ref}/{urllib.request.quote(path)}"
    try:
        return http_get(raw_url, token=None, accept='*/*')
    except FetchError:
        url = f"{API}/repos/{repo}/contents/{path}?ref={ref}"
        data = json.loads(http_get(url, token))
        return base64.b64decode(data['content'])


def fetch_tree(repo, path, ref, token, dest, depth=0):
    """Recursively download a directory at a pinned ref into dest."""
    if depth > 6:
        raise FetchError(f"{repo}/{path}: directory nesting deeper than 6 levels")
    os.makedirs(dest, exist_ok=True)
    count = 0
    for name, kind, full_path in list_dir(repo, path, ref, token):
        target = os.path.join(dest, name)
        if kind == 'dir':
            count += fetch_tree(repo, full_path, ref, token, target, depth + 1)
        elif kind == 'file':
            suffix = os.path.splitext(name)[1].lower()
            if suffix not in ALLOWED_SUFFIXES:
                print(f"      skipped {name} (extension not allowed)")
                continue
            blob = download_blob(repo, full_path, ref, token)
            if len(blob) > MAX_FILE_BYTES:
                print(f"      skipped {name} ({len(blob)} bytes, over limit)")
                continue
            with open(target, 'wb') as f:
                f.write(blob)
            count += 1
        else:
            print(f"      skipped {name} (type {kind})")
    return count


# ----------------------------------------------------------------------------
# Overlay + materialise
# ----------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r'\A---\r?\n(.*?)\r?\n---\r?\n', re.DOTALL)


def split_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def set_frontmatter_name(front, new_name):
    """Replace the top-level `name:` value, preserving everything else."""
    lines = front.split('\n')
    for i, line in enumerate(lines):
        if re.match(r'^name\s*:', line):
            lines[i] = f'name: {new_name}'
            return '\n'.join(lines)
    return f'name: {new_name}\n' + '\n'.join(lines)


def load_overlay(entry):
    fname = entry.get('overlay')
    if not fname:
        return None
    path = os.path.join(OVERLAY_DIR, fname)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def provenance_block(name, entry):
    lic = entry.get('license', 'unknown')
    note = entry.get('license_note')
    lines = [
        '',
        '---',
        '',
        '## Provenance',
        '',
        f"Installed by Agent Skill Forge as `{name}`. Not authored here, and not",
        'vendored into the forge repository.',
        '',
        f"- Upstream: `{entry['repo']}` at `{entry['path']}`",
        f"- Pinned commit: `{entry['ref']}`",
        f"- Author: {entry.get('attribution', 'unknown')}",
        f"- Licence: {lic}",
    ]
    if note:
        lines.append(f"- Licence note: {note}")
    lines += [
        '',
        'What is whose, exactly:',
        '',
        f"- Everything above the `{OVERLAY_HEADING}` heading is the upstream author's",
        '  text at that commit, unchanged.',
        f"- The `{OVERLAY_HEADING}` section below it is written by the forge, not by",
        '  the upstream author. It describes how this skill wires into the forge spine.',
        f"- One upstream field is rewritten: frontmatter `name:` becomes `{name}`, so the",
        "  skill installs under the forge naming scheme. Every other field is upstream's.",
        '',
        'Do not edit this file. It is regenerated on every fetch. Change `overlays/` in',
        'the forge repository instead.',
        '',
    ]
    return '\n'.join(lines)


def apply_overlay(skill_dir, name, entry):
    """Rename the skill and append the forge overlay + provenance to SKILL.md."""
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    if not os.path.exists(skill_md):
        raise FetchError(f"{name}: upstream has no SKILL.md at {entry['path']}")

    with open(skill_md, 'r', encoding='utf-8') as f:
        text = f.read()

    front, body = split_frontmatter(text)
    if front is None:
        raise FetchError(f"{name}: upstream SKILL.md has no YAML frontmatter")

    upstream_name = 'unknown'
    m = re.search(r'^name\s*:\s*(.+)$', front, re.MULTILINE)
    if m:
        upstream_name = m.group(1).strip()

    front = set_frontmatter_name(front, name)

    overlay = load_overlay(entry)
    out = f"---\n{front}\n---\n{body.rstrip()}\n"
    if overlay:
        # Guarantee the boundary marker the provenance block refers to, even
        # if an overlay author forgets it.
        text = overlay.strip()
        if not text.startswith(OVERLAY_HEADING):
            text = f"{OVERLAY_HEADING}\n\n{text}"
        out += '\n---\n\n' + text + '\n'
    out += provenance_block(name, entry)

    with open(skill_md, 'w', encoding='utf-8') as f:
        f.write(out)

    return upstream_name


def tree_hash(root):
    """Stable sha256 over relative paths and contents."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn == MANIFEST_NAME:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            h.update(rel.encode('utf-8'))
            with open(full, 'rb') as f:
                h.update(f.read())
    return h.hexdigest()


def materialise(lock, name, entry, cached):
    dest = os.path.join(materialise_root(lock), name)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(cached, dest)
    upstream_name = apply_overlay(dest, name, entry)

    manifest = {
        'name': name,
        'upstream_name': upstream_name,
        'repo': entry['repo'],
        'path': entry['path'],
        'ref': entry['ref'],
        'license': entry.get('license'),
        'attribution': entry.get('attribution'),
        'gate': entry.get('gate'),
        'interactive': entry.get('interactive', False),
        'tree_sha256': None,
    }
    manifest['tree_sha256'] = tree_hash(dest)
    with open(os.path.join(dest, MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    return dest, manifest


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def select(lock, only, non_interactive):
    """Names to fetch, plus the ones excluded for needing a human.

    The two exclusions are not the same thing and must not be conflated.
    `--skills X` narrows this run; everything else stays installed. A
    non-interactive environment genuinely cannot host an interactive skill, so
    those must not remain installed either.

    Returns (names, needs_human).
    """
    skills = lock['skills']
    names = list(skills.keys())
    if only:
        wanted = [s.strip() for s in only.split(',') if s.strip()]
        unknown = [w for w in wanted if w not in skills]
        if unknown:
            raise FetchError(f"Not in the lock file: {', '.join(unknown)}")
        names = wanted

    needs_human = []
    if non_interactive:
        kept = [n for n in names if not skills[n].get('interactive')]
        needs_human = [n for n in names if n not in kept]
        for n in needs_human:
            print(f"  [SKIP] {n} needs a live human; excluded from a non-interactive install")
        names = kept
    return names, needs_human


def demote_excluded(lock, needs_human):
    """Remove materialised skills that cannot run in this environment.

    Dropping a name from the fetch loop is not enough. A previously
    materialised skill stays in .upstream/, and the sync pass discovers
    directories rather than reading this selection, so an excluded skill would
    still get installed. The cache is left alone: only the working copy goes,
    so re-including it later stays an offline operation.
    """
    root = materialise_root(lock)
    if not os.path.isdir(root):
        return []
    dropped = []
    for name in needs_human:
        dest = os.path.join(root, name)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
            dropped.append(name)
    return dropped


def cmd_fetch(args, lock):
    names, needs_human = select(lock, args.skills, args.non_interactive)
    token = None if args.offline else github_token()
    if not args.offline and not token:
        print("  [NOTE] No GitHub token found. Unauthenticated requests are limited to 60/hour.")
        print("         Run `gh auth login` or set GITHUB_TOKEN if you hit a limit.\n")

    os.makedirs(materialise_root(lock), exist_ok=True)
    ok, failed = [], []

    for name in names:
        entry = lock['skills'][name]
        cached = cache_path(lock, entry)
        short = entry['ref'][:8]
        print(f"  {name:11} {entry['repo']}/{entry['path']} @ {short}")

        try:
            if os.path.isdir(cached) and os.listdir(cached):
                print(f"      cache hit")
            elif args.offline:
                raise FetchError(
                    f"not cached and --offline was requested.\n"
                    f"      Expected at {cached}\n"
                    f"      Run without --offline once on a networked machine to populate the cache."
                )
            else:
                n = fetch_tree(entry['repo'], entry['path'], entry['ref'], token, cached)
                print(f"      fetched {n} file(s) -> cache")

            dest, manifest = materialise(lock, name, entry, cached)
            rel = os.path.relpath(dest, REPO_ROOT)
            print(f"      materialised -> {rel}  [{manifest['tree_sha256'][:12]}]")
            ok.append(name)
        except FetchError as e:
            print(f"      FAILED: {e}")
            failed.append((name, str(e)))
            if os.path.isdir(cached) and not os.listdir(cached):
                shutil.rmtree(cached, ignore_errors=True)

    dropped = demote_excluded(lock, needs_human)
    for name in dropped:
        print(f"  [REMOVED] {name} was excluded from this run; "
              f"removed a previously installed copy (cache kept)")

    print()
    print(f"  {len(ok)} of {len(names)} upstream skills ready.")
    if failed:
        print()
        print("  These skills are NOT installed:")
        for name, err in failed:
            print(f"    - {name}: {err.splitlines()[0]}")
        return 1
    return 0


def cmd_verify(args, lock):
    root = materialise_root(lock)
    bad = 0
    absent = 0
    names, _ = select(lock, args.skills, args.non_interactive)
    for name in names:
        entry = lock['skills'][name]
        dest = os.path.join(root, name)
        mpath = os.path.join(dest, MANIFEST_NAME)
        if not os.path.exists(mpath):
            # An absent skill is a verification failure, not a note. Treating
            # it as skippable meant --verify exited 0 on an empty .upstream/,
            # so CI could report every pin verified with nothing installed.
            print(f"  [ABSENT]   {name}  not installed")
            absent += 1
            continue
        with open(mpath, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        actual = tree_hash(dest)
        if actual != manifest.get('tree_sha256'):
            print(f"  [MODIFIED] {name}  manifest {manifest.get('tree_sha256','?')[:12]} != actual {actual[:12]}")
            bad += 1
        elif manifest.get('ref') != entry['ref']:
            print(f"  [STALE]    {name}  installed {manifest.get('ref','?')[:8]}, lock says {entry['ref'][:8]}")
            bad += 1
        else:
            print(f"  [OK]       {name}  {entry['ref'][:8]}")
    if bad or absent:
        parts = []
        if bad:
            parts.append(f"{bad} modified or stale")
        if absent:
            parts.append(f"{absent} not installed")
        print(f"\n  Verification failed: {', '.join(parts)}.")
        print("  Run: python3 scripts/fetch_upstream.py")
    return 1 if (bad or absent) else 0


def cmd_upgrade(args, lock):
    token = github_token()
    repos = sorted({e['repo'] for e in lock['skills'].values()})
    heads = {}
    print("  Resolving upstream HEADs...\n")
    for repo in repos:
        try:
            data = json.loads(http_get(f"{API}/repos/{repo}/commits?per_page=1", token))
            heads[repo] = data[0]['sha']
        except (FetchError, KeyError, IndexError) as e:
            print(f"    {repo}: could not resolve ({e})")

    changed = []
    for name, entry in lock['skills'].items():
        head = heads.get(entry['repo'])
        if not head:
            continue
        if head != entry['ref']:
            changed.append((name, entry, head))

    if not changed:
        print("  Every pin is already at upstream HEAD. Nothing to do.")
        return 0

    print(f"  {len(changed)} pin(s) behind HEAD:\n")
    for name, entry, head in changed:
        print(f"    {name:11} {entry['repo']}")
        print(f"                {entry['ref'][:12]} -> {head[:12]}")
        print(f"                https://github.com/{entry['repo']}/compare/{entry['ref']}...{head}")
    print()

    if not args.write:
        print("  Review the compare links above, then re-run with --write to bump the lock file.")
        print("  Nothing has been changed.")
        return 0

    with open(LOCK_FILE, 'r', encoding='utf-8') as f:
        raw = f.read()
    for _, entry, head in changed:
        raw = raw.replace(f'"{entry["ref"]}"', f'"{head}"')
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(raw)
    print(f"  Lock file bumped. Run `python3 scripts/fetch_upstream.py` to fetch the new pins.")
    return 0


def cmd_status(args, lock):
    root = materialise_root(lock)
    print(f"  {'skill':<12}{'gate':<12}{'pinned':<10}{'cache':<8}{'installed':<11}source")
    print(f"  {'-'*12}{'-'*12}{'-'*10}{'-'*8}{'-'*11}{'-'*30}")
    for name, entry in lock['skills'].items():
        cached = 'yes' if os.path.isdir(cache_path(lock, entry)) else 'no'
        inst = 'yes' if os.path.exists(os.path.join(root, name, 'SKILL.md')) else 'no'
        print(f"  {name:<12}{entry.get('gate',''):<12}{entry['ref'][:8]:<10}{cached:<8}{inst:<11}{entry['repo']}")
    print()
    print(f"  cache:  {cache_root(lock)}")
    print(f"  target: {root}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Fetch reference-only upstream skills at pinned commits.")
    p.add_argument('--skills', type=str, help="Comma-separated subset of lock-file skill names")
    p.add_argument('--offline', action='store_true', help="Use the cache only; fail loudly on a miss")
    p.add_argument('--non-interactive', action='store_true', help="Skip skills that need a live human")
    p.add_argument('--verify', action='store_true', help="Check installed trees against their manifests")
    p.add_argument('--upgrade', action='store_true', help="Show pins behind upstream HEAD")
    p.add_argument('--write', action='store_true', help="With --upgrade, bump the lock file")
    p.add_argument('--status', action='store_true', help="Show pin, cache, and install state")
    args = p.parse_args()

    print("=" * 74)
    print(" 📦 Agent Skill Forge — Upstream Skill Fetcher (reference-only)")
    print("=" * 74)
    print()

    try:
        lock = load_lock()
        if args.status:
            return cmd_status(args, lock)
        if args.verify:
            return cmd_verify(args, lock)
        if args.upgrade:
            return cmd_upgrade(args, lock)
        return cmd_fetch(args, lock)
    except FetchError as e:
        print(f"  ERROR: {e}")
        return 2


if __name__ == '__main__':
    sys.exit(main())
