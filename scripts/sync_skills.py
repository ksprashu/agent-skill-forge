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
import difflib
import shutil
import json
import re
import stat

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CORE_SKILLS_DIR = os.path.join(REPO_ROOT, 'skills')
PREFERRED_SKILLS_DIR = os.path.join(REPO_ROOT, 'preferred')
UPSTREAM_SKILLS_DIR = os.path.join(REPO_ROOT, '.upstream')
HARNESSES_FILE = os.path.join(REPO_ROOT, 'config', 'harnesses.json')
UPSTREAM_LOCK_FILE = os.path.join(REPO_ROOT, 'config', 'upstream.lock.json')

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
    'cognitive-profiler': os.path.join(CORE_SKILLS_DIR, 'cognitive-profiler'),
    'copy-write': os.path.join(CORE_SKILLS_DIR, 'copy-write'),
    'image-gen': os.path.join(CORE_SKILLS_DIR, 'image-gen'),
    'continuous-alignment': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
    'align': os.path.join(CORE_SKILLS_DIR, 'continuous-alignment'),
    'work': os.path.join(CORE_SKILLS_DIR, 'work'),
    'profile': os.path.join(CORE_SKILLS_DIR, 'cognitive-profiler'),
    'cognitive-profiler': os.path.join(CORE_SKILLS_DIR, 'cognitive-profiler'),
}

# The four-gate spine. These live in .upstream/ and are fetched at install time
# from pinned commits by scripts/fetch_upstream.py — never vendored here.
SPINE_SKILLS = {
    'understand': ['echo', 'grill', 'done'],
    'think': ['brainstorm', 'research', 'doubt'],
    'verify': ['prove', 'bar', 'scope'],
    'human': ['profile', 'land', 'nudge'],
}
UPSTREAM_SPINE = {'echo', 'grill', 'done', 'brainstorm', 'research', 'doubt',
                  'prove', 'bar', 'scope', 'land', 'nudge'}

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
    'profile-me': 'cognitive-profiler',
    'cognitive-profile': 'cognitive-profiler',
    'evolve': 'align',
    'teamwork': 'work',
    'team': 'work',
    'swarm': 'work',
}

ANTIGRAVITY_RESERVED_COMMANDS = {'goal', 'schedule', 'browser', 'grill-me', 'teamwork-preview', 'learn', 'boost', 'agents', 'config', 'settings', 'clear', 'resume', 'rewind', 'undo', 'fork', 'add-dir', 'keybindings', 'codesearch', 'credits', 'diff', 'permissions', 'statusline', 'title', 'voice', 'help'}
ANTIGRAVITY_BUILTIN_SKILLS = {'agy-customizations', 'antigravity_guide', 'antigravity-guide', 'generative_ui', 'migrate-workflows', 'permissioned-github'}
ALL_RESERVED = ANTIGRAVITY_RESERVED_COMMANDS | ANTIGRAVITY_BUILTIN_SKILLS


# ==============================================================================
# Harness Capability Matrix
# ==============================================================================

_HARNESS_CACHE = None


def load_harnesses():
    """Load config/harnesses.json. Returns None if absent, so older flows still run."""
    global _HARNESS_CACHE
    if _HARNESS_CACHE is not None:
        return _HARNESS_CACHE
    if not os.path.exists(HARNESSES_FILE):
        print(f"  [WARN] {HARNESSES_FILE} not found. Falling back to installing every skill everywhere.")
        _HARNESS_CACHE = False
        return None
    try:
        with open(HARNESSES_FILE, 'r', encoding='utf-8') as f:
            _HARNESS_CACHE = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [ERROR] {HARNESSES_FILE} is not valid JSON: {e}")
        _HARNESS_CACHE = False
        return None
    return _HARNESS_CACHE


def harness_targets():
    """Resolve installation targets from the capability matrix.

    Returns [(key, label, expanded_dir, harness_config)].
    """
    matrix = load_harnesses()
    if not matrix:
        return [
            ('agents-hub', '~/.agents/skills', AGENTS_SKILLS_DIR, {}),
            ('gemini-cli', '~/.gemini/skills', GEMINI_SKILLS_DIR, {}),
            ('antigravity-ide', '~/.gemini/config/skills', GEMINI_CONFIG_SKILLS_DIR, {}),
            ('claude-code', '~/.claude/skills', CLAUDE_SKILLS_DIR, {}),
            ('antigravity-cli', '~/.gemini/antigravity-cli/skills', ANTIGRAVITY_CLI_SKILLS_DIR, {}),
        ]
    targets = []
    for key, cfg in matrix.get('harnesses', {}).items():
        for raw in cfg.get('skills_dirs', []):
            targets.append((key, raw, os.path.expanduser(raw), cfg))
    return targets


def harness_reserved(harness_cfg):
    """Reserved names for one harness, falling back to the Antigravity set."""
    reserved = harness_cfg.get('reserved')
    if reserved is None:
        return set(ALL_RESERVED)
    return {r.lower() for r in reserved}


def local_commands(harness_cfg, project_dir=None):
    """Slash commands the user has defined themselves for this harness.

    These are not harness capabilities. `~/.claude/commands/plan.md` is one
    person's config, not something Claude Code ships, so it must never be
    written into harnesses.json. It is still a real collision for that person,
    so we detect it at runtime and let it subtract locally.

    Returns {command_name: path}.
    """
    found = {}
    dirs = list(harness_cfg.get('commands_dirs', []))
    if project_dir:
        dirs += [os.path.join(project_dir, d)
                 for d in harness_cfg.get('project_commands_dirs', [])]
    for raw in dirs:
        d = os.path.expanduser(raw)
        if not os.path.isdir(d):
            continue
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for fn in entries:
            if fn.endswith('.md') and not fn.startswith('.'):
                found.setdefault(fn[:-3].lower(), os.path.join(d, fn))
    return found


def native_conflicts(skill_names, harness_cfg, strict_native=False, ignore_native=False,
                     project_dir=None, include_local=True):
    """Which of these skills the harness already covers.

    Returns {skill_name: {'provider', 'coverage', 'capability', 'note', 'source'}}.
    'source' is 'native' for a capability the harness ships, or 'local' for a
    same-named slash command the user wrote themselves.

    Only 'full' coverage is subtracted by default; --strict-native also drops
    'partial'. A local command always subtracts, because two things answering
    to the same name is a collision no coverage level can soften.
    """
    if ignore_native:
        return {}
    matrix = load_harnesses()
    if not matrix:
        return {}
    skill_caps = matrix.get('skill_capabilities', {})
    native = harness_cfg.get('native', {})

    skipped = {}
    for name in skill_names:
        cap = skill_caps.get(name)
        if not cap or cap not in native:
            continue
        entry = native[cap]
        coverage = entry.get('coverage', 'full')
        if coverage == 'full' or (strict_native and coverage == 'partial'):
            skipped[name] = {
                'provider': entry.get('provider', '?'),
                'coverage': coverage,
                'capability': cap,
                'note': entry.get('note', ''),
                'source': 'native',
            }

    if include_local:
        user_cmds = local_commands(harness_cfg, project_dir=project_dir)
        for name in skill_names:
            if name in skipped or name.lower() not in user_cmds:
                continue
            skipped[name] = {
                'provider': '/' + name.lower(),
                'coverage': 'local',
                'capability': skill_caps.get(name, '?'),
                'note': 'Your own command at %s. Delete it to use the forge skill instead.'
                        % user_cmds[name.lower()].replace(os.path.expanduser('~'), '~'),
                'source': 'local',
            }
    return skipped

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
        'description': 'Step-by-step Google codelabs, human voice profiling, agent communication profiling, technical copywriting, and image generation.',
        'skills': ['codelab', 'human-voice', 'cognitive-profiler', 'copy-write', 'image-gen'],
    },
    'c4': {
        'id': 'docs-governance',
        'name': 'Knowledge & Governance',
        'description': 'Documentation compilation, OKF knowledge catalog, Google OSS hygiene, and continuous alignment.',
        'skills': ['docs', 'catalog', 'google-oss', 'continuous-alignment', 'sync'],
    },
    'c5': {
        'id': 'spine',
        'name': 'The Four-Gate Spine',
        'description': 'Understand the ask, think before building, prove the result, and make it land with a human. Eleven of these twelve are referenced from upstream at a pinned commit, not vendored.',
        'skills': ['echo', 'grill', 'done', 'brainstorm', 'research', 'doubt',
                   'prove', 'bar', 'scope', 'profile', 'land', 'nudge'],
    },
}

# What `--core` and the wizard's [core] preset mean. c5 is deliberately not in
# here: it is the spine, eleven twelfths of which is fetched from upstream at
# install time, and --core must stay a local, offline-capable selection.
CORE_AGGREGATE = ('c1', 'c2', 'c3', 'c4')

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


class UnknownSelector(ValueError):
    """Raised when a --clusters/--skills token matches nothing known."""

    def __init__(self, unknown, vocabulary):
        self.unknown = unknown
        self.vocabulary = vocabulary
        super().__init__(self.format())

    def format(self):
        lines = []
        for token in self.unknown:
            hint = difflib.get_close_matches(token, sorted(self.vocabulary), n=3, cutoff=0.6)
            suffix = f"  Did you mean: {', '.join(hint)}?" if hint else ""
            lines.append(f"  unknown selector '{token}'.{suffix}")
        lines.append("\nRun with --list-clusters to see every valid cluster, preset, and skill name.")
        return "Unrecognised selector(s):\n" + "\n".join(lines)


def _selector_vocabulary():
    """Every token resolve_clusters_arg accepts, for suggestions and listings."""
    vocab = {'all', 'complete', 'core', 'domain', 'preferred', 'content', 'creative',
             'planning', 'qa', 'quality', 'gov', 'governance'}
    vocab.update(ALL_CLUSTERS.keys())
    vocab.update(ALIASES.keys())
    for c in ALL_CLUSTERS.values():
        vocab.add(c['id'].lower())
        vocab.update(s.lower() for s in c['skills'])
    vocab.update(discover_all_skills().keys())
    return vocab


def validate_skill_names(skills_arg):
    """Split a --skills list into (names, unknown).

    Every name is returned, including the unrecognised ones: the installers
    already report those as NOT FOUND LOCALLY or RESERVED SKIPPED and carry on,
    and a typo should not be fatal. `unknown` is reported separately so callers
    can keep an unresolved name from counting as an explicit selection, which
    is the part that was actually dangerous — see main().

    Aliases come back as their canonical skill. Counting an alias as resolved
    while passing it through unchanged armed strict pruning with an allow-list
    the sync never matched — it installs an alias only alongside its canonical
    skill — so `--skills prompt-writer --prune` deleted `prompt` itself.
    """
    names = [s.strip() for s in skills_arg.split(',') if s.strip()]
    names = list(dict.fromkeys(ALIASES.get(n, n) for n in names))
    known = discover_all_skills()
    unknown = [n for n in names if n not in known]
    return names, unknown


def resolve_clusters_arg(cluster_arg):
    """Resolve cluster codes, IDs, presets, or skill names into (skills, unknown).

    Tokens that resolve to nothing are returned in `unknown` rather than raised
    on, so the caller picks the policy: the wizard stops, the CLI warns.
    """
    skills = []
    unknown = []
    if not cluster_arg:
        return skills
    parts = [p.strip().lower() for p in cluster_arg.split(',') if p.strip()]
    for p in parts:
        if p in ('all', 'complete'):
            for c in ALL_CLUSTERS.values():
                skills.extend(c['skills'])
            break
        elif p == 'core':
            # c1-c4 only. c5 (the spine) is mostly upstream, so folding it in
            # here would quietly turn a local core install into a networked
            # one. Ask for it with --spine or --clusters c5.
            for key in CORE_AGGREGATE:
                skills.extend(CORE_CLUSTERS[key]['skills'])
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
                unknown.append(p)

    return list(dict.fromkeys(skills)), unknown


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
    print("  [content] Content & Creative only (codelab, human-voice, cognitive-profiler, copy-write, image-gen)")
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
        chosen_skills, unknown = validate_skill_names(custom_input)
        vocabulary = set(discover_all_skills()) | set(ALIASES)
    else:
        chosen_skills, unknown = resolve_clusters_arg(choice)
        vocabulary = _selector_vocabulary()

    # The wizard stops where the CLI only warns: the user is sitting here and
    # can retype, and the next prompt offers to prune.
    if unknown:
        print(f"\n❌ {UnknownSelector(unknown, vocabulary)}", file=sys.stderr)
        sys.exit(2)

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


# Dropped into every --copy install so a physical copy can later be told
# apart from a directory the user wrote by hand. Copies made before this
# marker existed have none, so they read as foreign and are left alone:
# a stale copy lingering is a far cheaper failure than deleting real work.
OWNER_MARKER = '.forge-owned'


def is_link(path):
    """Check if path is a symlink or Windows junction."""
    if os.path.islink(path):
        return True
    if sys.platform == 'win32' and hasattr(os.path, 'isjunction') and os.path.isjunction(path):
        return True
    return False


def has_reparse_attribute(st):
    """True when an lstat result carries FILE_ATTRIBUTE_REPARSE_POINT.

    Split out of is_reparse_point so this much is checkable off Windows. The
    rest of that function is platform dispatch and a stdlib call, but this is
    the test that decides whether a junction is seen at all on Python
    3.8-3.11 — and being wrong here is what lets rmtree walk into the source
    repo. st_file_attributes is absent on non-Windows stat results, hence the
    default rather than an AttributeError handler around the whole lookup.
    """
    return bool(getattr(st, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def is_reparse_point(path):
    """True for a symlink or any Windows reparse point, including junctions.

    os.path.isjunction landed in 3.12 but the installers probe plain `python`,
    so on 3.8-3.11 a junction we created ourselves is invisible to is_link and
    gets handled as an ordinary directory. That matters because shutil.rmtree
    follows junctions on Windows: the "delete the link" path would instead
    walk into the canonical repo and delete the source. Fall back to the
    reparse-point attribute, which has been available on every supported
    Python.
    """
    if os.path.islink(path):
        return True
    if sys.platform != 'win32':
        return False
    if hasattr(os.path, 'isjunction'):
        try:
            if os.path.isjunction(path):
                return True
        except OSError:
            pass
    try:
        return has_reparse_attribute(os.lstat(path))
    except OSError:
        return False


def link_destination(path):
    """Absolute destination of a link or junction, or None if not one.

    Reports the destination whether or not it currently resolves, so a foreign
    link to an unmounted volume or a moved checkout still names its owner
    instead of reading as one of our own broken links. That is the property
    the prune path depends on.

    readlink is used rather than realpath to report the entry's own immediate
    destination — the one we would have written — rather than the end of a
    chain some other repo may have introduced. Both agree on dangling links,
    so the two are interchangeable for the common case; is_forge_owned tests
    the resolved form as well, which is what makes a link through a symlinked
    parent (/tmp -> /private/tmp) still read as ours.

    Relative destinations resolve against the link's own directory, not the
    process working directory.
    """
    if not is_reparse_point(path):
        return None
    try:
        dest = os.readlink(path)
    except OSError:
        # Junctions on older Pythons are not readable via readlink.
        try:
            dest = os.path.realpath(path)
        except OSError:
            return None
    if sys.platform == 'win32' and dest.startswith('\\\\?\\'):
        dest = dest[4:]
    if not os.path.isabs(dest):
        dest = os.path.join(os.path.dirname(os.path.abspath(path)), dest)
    return os.path.normpath(os.path.abspath(dest))


def _is_within(child, parent):
    """True if `child` is `parent` or sits underneath it."""
    try:
        return os.path.commonpath([os.path.abspath(child), os.path.abspath(parent)]) == os.path.abspath(parent)
    except (ValueError, OSError):
        # Different drives on Windows, or an unresolvable path.
        return False


def is_forge_owned(path):
    """True only for entries this repo actually put here.

    Ownership is decided by where an entry points, never by what it is called.
    These hub directories are shared — creative-stack and any other skill repo
    link into the same ~/.claude/skills — so an unrecognised name is evidence
    of another owner, not of staleness. Deciding on name alone is what silently
    deleted eight working creative-stack skills on every --prune run.

    Anything we cannot positively attribute to this repo returns False, so the
    caller leaves it alone. Guessing wrong in that direction costs a stale
    entry; guessing wrong in the other direction costs the user their work.
    """
    root = os.path.realpath(REPO_ROOT)

    dest = link_destination(path)
    if dest is not None:
        return _is_within(dest, root) or _is_within(os.path.realpath(dest), root)

    if os.path.isdir(path):
        return os.path.isfile(os.path.join(path, OWNER_MARKER))

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
        # Stamp the copy so a later --prune can tell it apart from a directory
        # the user wrote themselves. Without this, a physical install and
        # somebody else's work are indistinguishable on disk.
        try:
            with open(os.path.join(target_link, OWNER_MARKER), 'w', encoding='utf-8') as f:
                f.write(os.path.realpath(src_path) + "\n")
        except OSError as e:
            print(f"  [WARN] could not mark {target_link} as forge-owned: {e}")
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

    # Reference-only upstream skills, materialised by scripts/fetch_upstream.py.
    # These deliberately win over a local skill of the same name: `grill` is the
    # upstream engine plus an overlay, not the older local copy.
    if os.path.exists(UPSTREAM_SKILLS_DIR):
        for name in sorted(os.listdir(UPSTREAM_SKILLS_DIR)):
            path = os.path.join(UPSTREAM_SKILLS_DIR, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, 'SKILL.md')):
                if name in all_skills:
                    print(f"  [UPSTREAM WINS] {name}: using .upstream/{name}, "
                          f"shadowing {os.path.relpath(all_skills[name]['path'], REPO_ROOT)}")
                all_skills[name] = {'path': path, 'type': 'upstream'}

    return all_skills


def clean_stale_and_orphan_links(skills_dir, allowed_skills, prune=False, strict_prune=False,
                                 reserved=None, excluded=None):
    """Remove broken symlinks, reserved-namespace items, or links not allowed here.

    `excluded` is the set this harness must not have: capabilities it already
    covers natively, plus same-named commands the user wrote. Those are removed
    unconditionally. Without that, the lenient branch below would keep any link
    whose target merely exists, so flipping a capability to `full` (or adding a
    local command) left the superseded skill installed forever.
    """
    if not os.path.exists(skills_dir):
        return

    all_available = discover_all_skills()
    if reserved is None:
        reserved = ALL_RESERVED
    excluded = excluded or set()

    for item in sorted(os.listdir(skills_dir)):
        item_path = os.path.join(skills_dir, item)

        # Reserved names are purged whoever owns them. A harness reserves these
        # for itself, so anything sitting on one is already broken for every
        # repo on the machine, not just ours — leaving a foreign one in place
        # would leave the collision it causes in place too. The set is a fixed,
        # known list, which is what makes claiming authority over it defensible
        # where the open-ended rules below are not.
        if item.lower() in reserved:
            reason = "RESERVED HARNESS NAMESPACE"
            print(f"  [{reason}] {item} in {skills_dir}")
            if prune:
                remove_path_or_link(item_path)
                print(f"    -> Removed: {item_path}")
            continue

        # Past this point every branch can delete something we did not install,
        # so ownership is settled first. Three cases used to slip past the
        # link-only check and reach shutil.rmtree: a foreign skill stored as a
        # real directory, a foreign link whose target was temporarily
        # unreachable (it read as one of our own broken links), and a Windows
        # junction on Python <3.12 that is invisible to islink — where rmtree
        # follows the junction and takes the source repo with it.
        if not is_forge_owned(item_path):
            dest = link_destination(item_path)
            where = f" -> {dest}" if dest else ""
            print(f"  [FOREIGN] {item}{where} in {skills_dir} (owned elsewhere, left alone)")
            continue

        # Superseded stays downstream of the ownership check, unlike reserved.
        # `excluded` is open-ended — it grows with every capability a harness
        # declares native and every command the user writes — so a name landing
        # in it says this harness covers that capability, not that whatever
        # holds the name is ours to delete.
        if item in excluded or ALIASES.get(item) in excluded:
            print(f"  [SUPERSEDED] {item} in {skills_dir}")
            if prune:
                remove_path_or_link(item_path)
                print(f"    -> Removed: {item_path}")
            continue

        # Everything from here down is ours, confirmed by destination or by
        # the ownership marker. Links and marked copies answer to the same
        # allow-list: a --copy install is the same skill stored differently,
        # and giving copies their own rule meant plain --prune deleted copied
        # skills an equivalent link kept, while copied aliases survived an
        # explicit deselection.
        linked = is_reparse_point(item_path)
        target_exists = os.path.exists(item_path)
        if strict_prune:
            is_allowed = item in allowed_skills or ALIASES.get(item) in allowed_skills
        else:
            is_allowed = item in allowed_skills or item in ALIASES or (item in all_available and target_exists)

        if not target_exists or not is_allowed:
            if not linked:
                reason = "STALE COPY / NOT SELECTED"
            else:
                reason = "BROKEN" if not target_exists else "STALE / NOT SELECTED"
            print(f"  [{reason}] {item} in {skills_dir}")
            if prune:
                if linked:
                    remove_link(item_path)
                else:
                    shutil.rmtree(item_path)
                print(f"    -> Removed: {item_path}")


def sync_skills_json(fix=False):
    """Register canonical skills directories in global skills.json configs.

    Merged, not rewritten. These files are shared with every other skill repo
    on the machine — creative-stack registers its own source directory in the
    same two files — and writing only our entries unregistered theirs on every
    sync.
    """
    configs = [
        os.path.expanduser('~/.gemini/config/skills.json'),
        os.path.expanduser('~/.agents/skills.json'),
    ]
    ours = [CORE_SKILLS_DIR.replace('\\', '/'),
            PREFERRED_SKILLS_DIR.replace('\\', '/')]

    for cfg in configs:
        os.makedirs(os.path.dirname(cfg), exist_ok=True)
        data, entries = {}, []
        if os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                entries = data.get('entries', [])
            except (json.JSONDecodeError, ValueError):
                print(f"  [WARN] {cfg} is not valid JSON — rewriting")
                data, entries = {}, []

        known = {os.path.abspath(os.path.expanduser(e.get('path', '')))
                 for e in entries}
        added = [{"path": p} for p in ours if os.path.abspath(p) not in known]
        if not added:
            print(f"  [JSON CONFIG] {cfg} already registered")
            continue
        if fix:
            data['entries'] = entries + added
            with open(cfg, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"  [JSON CONFIG] Updated {cfg} "
                  f"(+{len(added)}, {len(entries)} existing kept)")


def clean_skills_json():
    """Remove forge entries from global skills.json configs or delete file if empty."""
    configs = [
        os.path.expanduser('~/.gemini/config/skills.json'),
        os.path.expanduser('~/.agents/skills.json'),
    ]
    for cfg in configs:
        if not os.path.exists(cfg):
            continue
        try:
            with open(cfg, 'r', encoding='utf-8') as f:
                data = json.load(f)
            entries = data.get('entries', [])
            remaining_entries = []
            for entry in entries:
                entry_path = os.path.abspath(os.path.expanduser(entry.get('path', '')))
                if not entry_path.startswith(REPO_ROOT):
                    remaining_entries.append(entry)
            if not remaining_entries and not data.get('inherits'):
                os.remove(cfg)
                print(f"  [REMOVED CONFIG] {cfg}")
            elif len(remaining_entries) != len(entries):
                data['entries'] = remaining_entries
                with open(cfg, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f"  [UPDATED CONFIG] Removed forge entries from {cfg}")
            else:
                print(f"  [OK] No forge entries in {cfg}")
        except Exception as e:
            print(f"  [ERROR] Failed to clean {cfg}: {e}")


def uninstall_skills(project_dir=None):
    """Remove all installed skills and configs associated with Agent Skill Forge."""
    print("=" * 65)
    print("🧹 Agent Skill Forge — Skill Uninstaller")
    print("=" * 65)

    all_skills = discover_all_skills()
    all_names = set(all_skills.keys()) | set(CORE_SKILLS.keys()) | set(ALIASES.keys())

    if project_dir:
        project_dir = os.path.abspath(os.path.expanduser(project_dir))
        target_dirs = [
            (f"{project_dir}/.gemini/skills", os.path.join(project_dir, '.gemini', 'skills')),
            (f"{project_dir}/.agents/skills", os.path.join(project_dir, '.agents', 'skills')),
        ]
    else:
        target_dirs = [(label, path) for _k, label, path, _c in harness_targets()]

    for label, target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
        print(f"\n--- Cleaning {label} ---")
        removed_count = 0
        for item in sorted(os.listdir(target_dir)):
            item_path = os.path.join(target_dir, item)
            if is_link(item_path):
                try:
                    dst = os.readlink(item_path)
                    if sys.platform == 'win32' and dst.startswith('\\\\?\\'):
                        dst = dst[4:]
                    abs_dst = os.path.abspath(os.path.join(target_dir, dst))
                    if abs_dst.startswith(REPO_ROOT) or item in all_names:
                        remove_link(item_path)
                        print(f"  [UNLINKED] {item} -> {dst}")
                        removed_count += 1
                except OSError as e:
                    print(f"  [ERROR] {item}: {e}")
            elif os.path.isdir(item_path) and item in all_names:
                shutil.rmtree(item_path)
                print(f"  [REMOVED DIR] {item}")
                removed_count += 1
        if removed_count == 0:
            print("  (no installed forge skills found)")

    if not project_dir:
        print("\n--- Cleaning JSON Configuration Registries ---")
        clean_skills_json()

    print("\n✅ All Agent Skill Forge skills have been completely removed.")



def sync_global_skills(prune=False, fix=False, copy_mode=False, selected_skills=None, strict_prune=False,
                       strict_native=False, ignore_native=False):
    """Synchronize selected skills into each harness, minus what that harness ships natively."""
    print("=" * 65)
    print("🚀 Agent Skill Forge — Global Symlink Synchronizer")
    print("=" * 65)

    all_available = discover_all_skills()

    if selected_skills is None:
        # The default is the legacy verb set plus the four-gate spine. The spine
        # has to be in here: `install.sh` with no arguments prints a banner that
        # advertises /echo, /brainstorm, /prove and the rest, and a banner that
        # names skills the run did not install is just a lie. Spine names that
        # were never fetched are reported as NOT FOUND below and skipped.
        target_skill_names = list(CORE_SKILLS.keys())
        for gate in SPINE_SKILLS.values():
            target_skill_names.extend(n for n in gate if n not in target_skill_names)
        print(f"Default Core Skills + spine ({len(target_skill_names)} entries):")
    else:
        target_skill_names = selected_skills
        print(f"Target Selected Skills ({len(target_skill_names)}):")

    # Reserved-name filtering is per harness now, not global: a name Antigravity
    # reserves may be perfectly installable under Claude Code.
    all_targets = {}
    for name in target_skill_names:
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
        if target in all_targets:
            all_targets[alias] = all_targets[target]

    for hkey, label, target_dir, hcfg in harness_targets():
        os.makedirs(target_dir, exist_ok=True)
        hlabel = hcfg.get('label', hkey)
        print(f"\n--- Auditing {hlabel}: {label} ---")

        reserved = harness_reserved(hcfg)
        skipped = native_conflicts(all_targets.keys(), hcfg,
                                   strict_native=strict_native, ignore_native=ignore_native)

        # Subtract what this harness already ships, so the forge does not shadow it.
        harness_targets_map = {n: p for n, p in all_targets.items() if n not in skipped}
        for name, info in sorted(skipped.items()):
            tag = 'YOURS' if info['source'] == 'local' else 'NATIVE'
            owner = 'your own' if info['source'] == 'local' else hlabel
            print(f"  [{tag} {info['coverage'].upper():<6}] {name:<22} covered by {owner} {info['provider']}")
            if info['note']:
                print(f"                      {info['note']}")

        clean_stale_and_orphan_links(target_dir, harness_targets_map, prune=prune,
                                     strict_prune=strict_prune, reserved=reserved,
                                     excluded=set(skipped))

        for name, src_path in harness_targets_map.items():
            if name.lower() in reserved:
                print(f"  [BLOCKED RESERVED] {name} collides with a {hlabel} reserved name")
                continue
            if not os.path.exists(src_path):
                continue
            target_link = os.path.join(target_dir, name)
            # Cleanup above leaves foreign entries alone; so must this. Every
            # branch below that finds something already here replaces it, and
            # an entry that merely shares a skill's name belongs to whoever put
            # it there — a foreign directory was rmtree'd and a foreign link
            # repointed on every --fix, the step the installers always run.
            if (os.path.lexists(target_link) or is_link(target_link)) and not is_forge_owned(target_link):
                dest = link_destination(target_link)
                where = f" -> {dest}" if dest else ""
                print(f"  [FOREIGN CONFLICT] {name}{where} is owned elsewhere; not replaced")
                continue
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
    if fix:
        # Deferred until --fix. Creating these unconditionally made the dry run
        # leave two empty directories in someone else's project, which is both
        # a write the caller did not ask for and the exact "it looked like it
        # installed" confusion the [WOULD BOOTSTRAP] wording exists to end.
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
                if fix:
                    print(f"  [BOOTSTRAP] {skill} ({skill_info['type']}) -> {target_link}")
                    create_link(src_path, target_link, copy_mode=copy_mode)
                    print(f"    -> Created entry to {src_path}")
                else:
                    # Without --fix nothing is written. Saying BOOTSTRAP here
                    # read as a completed install, and the empty directory it
                    # left behind was only noticed downstream.
                    print(f"  [WOULD BOOTSTRAP] {skill} ({skill_info['type']}) -> "
                          f"{target_link}  (dry run; re-run with --fix to create it)")
            else:
                print(f"  [ALREADY PRESENT] {skill} in {target_dir}")


def list_harnesses(strict_native=False):
    """Print each harness, where it installs, and what the forge will skip there."""
    matrix = load_harnesses()
    print("=" * 78)
    print(" 🧭 Agent Skill Forge — Harness Capability Matrix")
    print("=" * 78)
    if not matrix:
        print("\n  No capability matrix found. Every skill installs into every harness.")
        return 0

    skill_caps = matrix.get('skill_capabilities', {})
    all_forge_skills = sorted(skill_caps.keys())

    for key, cfg in matrix.get('harnesses', {}).items():
        label = cfg.get('label', key)
        dirs = ', '.join(cfg.get('skills_dirs', []))
        hooks = cfg.get('hook_support', 'none')
        print(f"\n  {label}  ({key})")
        print(f"    Installs to   : {dirs}")
        print(f"    Hook support  : {hooks}"
              + ("   <- the design gate can be enforced here" if hooks != 'none' else "   <- design gate is advisory only"))

        reserved = cfg.get('reserved', [])
        if reserved:
            print(f"    Reserved names: {len(reserved)} built-in command(s) the forge will never shadow")

        covered = cfg.get('native', {})
        if covered:
            print(f"    Natively covers: {len(covered)} capability(ies)")
            for cap, entry in sorted(covered.items()):
                print(f"        {cap:<24} {entry.get('coverage','full'):<8} {entry.get('provider','?')}")
                if entry.get('note'):
                    print(f"        {'':<24} note: {entry['note']}")

        skipped = native_conflicts(all_forge_skills, cfg, strict_native=strict_native)
        if not skipped:
            print(f"    Skipped here  : nothing — the forge installs its full selection")
            continue

        native_hits = {n: i for n, i in skipped.items() if i['source'] == 'native'}
        local_hits = {n: i for n, i in skipped.items() if i['source'] == 'local'}
        if native_hits:
            print(f"    Skipped here  : {len(native_hits)} skill(s) the harness already ships")
            for name, info in sorted(native_hits.items()):
                print(f"        {name:<16} {info['coverage']:<8} {info['provider']}")
        if local_hits:
            print(f"    Your commands : {len(local_hits)} skill(s) you already defined yourself")
            for name, info in sorted(local_hits.items()):
                print(f"        {name:<16} {'local':<8} {info['provider']}")
                print(f"        {'':<16} {info['note']}")

    print("\n  Coverage 'full' is skipped by default. 'partial' is installed unless --strict-native.")
    print("  Override everything with --ignore-native.")
    return 0


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
    parser.add_argument('--content', action='store_true', help="Install content & creative skills only (c3: codelab, human-voice, cognitive-profiler, copy-write, image-gen)")
    parser.add_argument('--interactive', '-i', action='store_true', help="Launch interactive skill cluster installer")
    parser.add_argument('--list-available', action='store_true', help="List all core and preferred skills in the forge")
    parser.add_argument('--list-clusters', action='store_true', help="List all core and domain clusters with member skills")
    parser.add_argument('--uninstall', action='store_true', help="Uninstall and remove all installed skills and configs")
    parser.add_argument('--spine', action='store_true', help="Install the four-gate spine only (c5)")
    parser.add_argument('--strict-native', action='store_true', help="Also skip skills a harness covers only partially")
    parser.add_argument('--ignore-native', action='store_true', help="Install everything everywhere, even where the harness has a native")
    parser.add_argument('--list-harnesses', action='store_true', help="Show each harness, its skills dir, and what it covers natively")

    args = parser.parse_args()

    if args.list_harnesses:
        return list_harnesses(strict_native=args.strict_native)

    if args.uninstall:
        uninstall_skills(project_dir=args.project)
        return

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
        for key in CORE_AGGREGATE:
            requested_skills.extend(CORE_CLUSTERS[key]['skills'])
    if args.domain:
        has_explicit_selection = True
        for c in DOMAIN_CLUSTERS.values():
            requested_skills.extend(c['skills'])
    if args.content:
        has_explicit_selection = True
        requested_skills.extend(CORE_CLUSTERS['c3']['skills'])
    if args.spine:
        has_explicit_selection = True
        requested_skills.extend(CORE_CLUSTERS['c5']['skills'])
    # An unresolved selector is reported but not fatal — the installers already
    # print NOT FOUND LOCALLY / RESERVED SKIPPED for names they cannot place,
    # and a typo should not stop the names that did resolve from installing.
    #
    # What it must not do is count as an explicit selection. strict_prune is
    # armed by has_explicit_selection and scoped by requested_skills, so a
    # single mistyped name used to arm prune against an allow-list that matched
    # nothing — and the whole installed set went. Unresolved names therefore
    # ride along in requested_skills (so they get reported) without ever
    # setting the flag that arms pruning.
    unresolved = []
    if args.clusters:
        resolved, unknown = resolve_clusters_arg(args.clusters)
        requested_skills.extend(resolved)
        unresolved.extend(unknown)
        if resolved:
            has_explicit_selection = True
    if args.skills:
        names, unknown = validate_skill_names(args.skills)
        requested_skills.extend(names)
        unresolved.extend(unknown)
        if len(names) > len(unknown):
            has_explicit_selection = True

    if unresolved:
        print(f"\n⚠️  {UnknownSelector(unresolved, _selector_vocabulary())}", file=sys.stderr)
        if args.prune and not has_explicit_selection:
            print("    Nothing in this selection resolved, so --prune is limited to its "
                  "default sweep rather than pruning to an empty allow-list.", file=sys.stderr)

    requested_skills = list(dict.fromkeys(requested_skills))

    if args.project:
        if not requested_skills:
            print("Error: --skills, --clusters, --content, --core, or --all must be provided with --project")
            sys.exit(1)
        bootstrap_project_skills(args.project, requested_skills, fix=args.fix, copy_mode=args.copy)
        return

    strict_prune = has_explicit_selection and args.prune
    selected = requested_skills if has_explicit_selection else None
    sync_global_skills(prune=args.prune, fix=args.fix, copy_mode=args.copy, selected_skills=selected,
                       strict_prune=strict_prune, strict_native=args.strict_native,
                       ignore_native=args.ignore_native)


if __name__ == '__main__':
    main()
