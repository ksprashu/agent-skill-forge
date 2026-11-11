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
persona.py - Find, fetch, refresh and activate a personal voice & overlay pack.

The skill is public; a person's profile is not. Profiles live in a persona
directory (default ~/.gemini/personas), which is usually a clone of the
owner's private repo. This script resolves which profile applies, keeps that
clone current, and links optional rules/ or skills/ overlays so a fresh
machine picks up the full persona with one setting:

    AGENT_PERSONA_REPO   owner/name (cloned with gh if present, else https)
                         or any git URL or local path. Unset => nothing is
                         fetched and the skill stays neutral.
    AGENT_PERSONA_DIR    override the persona directory.

CLI:
    persona.py status [--name NAME]
    persona.py pull [--force] [--name NAME]
    persona.py activate [--name NAME]

Exit codes: 0 a personal profile resolves, 1 neutral (template only),
2 error (fetch failed, named profile missing, bad arguments).

Standard library only. Needs git (and optionally gh) on PATH for pull.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROFILE = "voice_and_tone.md"
SAMPLES = "voice-samples.md"
STAMP = "persona-last-pull"
PULL_INTERVAL = 24 * 60 * 60
TIMEOUT = 30
# Neither part may start with "-", so it can never be read as an option.
OWNER_NAME = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.-]*/[A-Za-z0-9_.][A-Za-z0-9_.-]*$")


def _home_dir():
    env_home = os.environ.get("HOME")
    if env_home:
        return Path(env_home)
    return Path.home()


def persona_dir():
    override = os.environ.get("AGENT_PERSONA_DIR")
    if override:
        return Path(override).expanduser()
    return _home_dir() / ".gemini" / "personas"


def resolve(skill_dir, pdir, name="default"):
    """Return (tier, profile_path, samples_path_or_None).

    A named profile is tier 2 or nothing: falling back to someone's default
    voice when they asked for a specific one would be the wrong voice.
    """
    if name == "default":
        local = skill_dir / "references" / "voice_and_tone.local.md"
        if local.is_file():
            return 1, local, None
    profile = pdir / name / PROFILE
    if profile.is_file():
        samples = profile.parent / SAMPLES
        return 2, profile, samples if samples.is_file() else None
    if name != "default":
        return None, None, None
    return 3, skill_dir / "references" / "voice_and_tone.template.md", None


def _resolve_characters_pack(chars_root):
    """Locate characters.json directly under chars_root or in a pack subfolder."""
    if not chars_root.is_dir():
        return None
    direct = chars_root / "characters.json"
    if direct.is_file():
        return direct
    for sub in sorted(chars_root.iterdir()):
        if sub.is_dir() and not sub.name.startswith("."):
            candidate = sub / "characters.json"
            if candidate.is_file():
                return candidate
    return None


def _points_within(link_path, root_dir):
    try:
        raw = os.readlink(link_path)
        resolved = (link_path.parent / raw).resolve()
        resolved.relative_to(root_dir.resolve())
        return True
    except (OSError, ValueError):
        return False


def _link_or_copy_file(src, dst, owner_root):
    src_resolved = src.resolve()
    if dst.is_symlink():
        if dst.exists() and dst.resolve() == src_resolved:
            return dst
        if _points_within(dst, owner_root):
            dst.unlink()
        else:
            return None
    elif dst.exists():
        return None
    try:
        dst.symlink_to(src_resolved)
    except OSError:
        shutil.copy2(src_resolved, dst)
    return dst


def _link_or_junction_dir(src, dst, owner_root):
    src_resolved = src.resolve()
    if dst.is_symlink():
        if dst.exists() and dst.resolve() == src_resolved:
            return dst
        if _points_within(dst, owner_root):
            dst.unlink()
        else:
            return None
    elif dst.exists():
        return None
    try:
        os.symlink(str(src_resolved), str(dst), target_is_directory=True)
        return dst
    except OSError:
        if os.name == "nt":
            try:
                proc = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(dst), str(src_resolved)],
                    capture_output=True, text=True, timeout=TIMEOUT
                )
                if proc.returncode == 0 and dst.exists():
                    return dst
            except (OSError, subprocess.TimeoutExpired):
                pass
        shutil.copytree(src_resolved, dst)
        return dst


def activate_overlays(pdir, home=None):
    """Link/copy rules/*.md and skills/*/SKILL.md from pdir into user harnesses."""
    pdir = Path(pdir)
    if not pdir.is_dir():
        return []
    home_root = Path(home) if home is not None else _home_dir()
    activated = []

    rules_dir = pdir / "rules"
    if rules_dir.is_dir():
        rule_files = sorted(p for p in rules_dir.glob("*.md") if p.is_file())
        if rule_files:
            rule_targets = [home_root / ".gemini" / "config" / "rules"]
            agy_cli_parent = home_root / ".gemini" / "antigravity-cli"
            if agy_cli_parent.exists():
                rule_targets.append(agy_cli_parent / "rules")
            for target_dir in rule_targets:
                target_dir.mkdir(parents=True, exist_ok=True)
                for rf in rule_files:
                    linked = _link_or_copy_file(rf, target_dir / rf.name, pdir)
                    if linked is not None:
                        activated.append(linked)

    skills_dir = pdir / "skills"
    if skills_dir.is_dir():
        skill_subdirs = sorted(
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").is_file()
        )
        if skill_subdirs:
            skill_targets = [
                home_root / ".gemini" / "config" / "skills",
                home_root / ".gemini" / "skills",
                home_root / ".claude" / "skills",
                home_root / ".agents" / "skills",
            ]
            for target_dir in skill_targets:
                target_dir.mkdir(parents=True, exist_ok=True)
                for sd in skill_subdirs:
                    linked = _link_or_junction_dir(sd, target_dir / sd.name, pdir)
                    if linked is not None:
                        activated.append(linked)

    return activated


def _git_env():
    env = dict(os.environ)
    # Never block on a credential prompt; an agent can't answer it.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GH_PROMPT_DISABLED", "1")
    return env


def _run(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=TIMEOUT, env=_git_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return proc.returncode == 0, (proc.stderr or proc.stdout).strip()


def _clone_cmd(source, dest):
    """The clone command, or None if source could be read as an option."""
    if source.startswith("-"):
        return None
    # An absolute destination can't start with "-" either.
    dest = str(Path(dest).absolute())
    if OWNER_NAME.match(source) and not Path(source).exists():
        if shutil.which("gh"):
            return ["gh", "repo", "clone", source, dest, "--", "--quiet"]
        source = "https://github.com/%s.git" % source
    return ["git", "clone", "--quiet", "--", source, dest]


def _is_git(pdir):
    return (pdir / ".git").exists()


def _origin(pdir):
    ok, out = _run(["git", "-C", str(pdir), "remote", "get-url", "origin"])
    return out if ok else None


def pull(pdir, source, force=False, now=None):
    """Clone or refresh the persona directory. Returns (ok, message)."""
    now = time.time() if now is None else now
    if _is_git(pdir):
        stamp = pdir / ".git" / STAMP
        if not force and stamp.is_file() and now - stamp.stat().st_mtime < PULL_INTERVAL:
            return True, "up to date (pulled within the last 24h; use --force)"
        ok, out = _run(["git", "-C", str(pdir), "pull", "--ff-only", "--quiet"])
        if ok:
            # Stamp only on success, so a failed pull is retried next run.
            stamp.touch()
            return True, "pulled"
        # The working copy is still usable; a stale voice beats no voice.
        return True, "pull failed, using the local copy: %s" % out
    if not source:
        return True, "AGENT_PERSONA_REPO is not set; nothing to fetch"
    if pdir.exists() and any(pdir.iterdir()):
        return True, ("%s exists and is not a git clone; leaving it alone. "
                      "Move it aside to clone %s there." % (pdir, source))
    cmd = _clone_cmd(source, pdir)
    if cmd is None:
        return False, "AGENT_PERSONA_REPO must not start with '-': %s" % source
    pdir.parent.mkdir(parents=True, exist_ok=True)
    ok, out = _run(cmd)
    if not ok:
        return False, "clone of %s failed: %s" % (source, out)
    (pdir / ".git" / STAMP).touch()
    return True, "cloned %s" % source


def report(pdir, name):
    tier, profile, samples = resolve(SKILL_DIR, pdir, name)
    source = os.environ.get("AGENT_PERSONA_REPO") or "(unset)"
    lines = ["persona_dir: %s" % pdir,
             "persona_repo: %s" % source]
    if _is_git(pdir):
        lines.append("clone_of: %s" % (_origin(pdir) or "(no origin)"))
    if tier is None:
        lines.append("profile: named profile '%s' not found at %s"
                     % (name, pdir / name / PROFILE))
        print("\n".join(lines))
        return 2
    reader_file = pdir / name / "reader" / "profile.json"
    chars_file = _resolve_characters_pack(pdir / name / "characters")
    labels = {1: "tier 1 (local override)", 2: "tier 2 (persona directory)",
              3: "tier 3 (neutral template; no personal profile found)"}
    lines += ["tier: %s" % labels[tier],
              "profile: %s" % profile,
              "samples: %s" % (samples or "(none)"),
              "reader_pack: %s" % (reader_file if reader_file.is_file() else "(none)"),
              "characters_pack: %s" % (chars_file or "(none)")]
    print("\n".join(lines))
    return 0 if tier in (1, 2) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("status", "pull", "activate"):
        p = sub.add_parser(cmd)
        p.add_argument("--name", default="default",
                       help="named profile under the persona directory")
        if cmd == "pull":
            p.add_argument("--force", action="store_true",
                           help="pull now, ignoring the once-a-day throttle")
    args = parser.parse_args(argv)
    if not re.match(r"^[A-Za-z0-9_.-]+$", args.name) or args.name in (".", ".."):
        print("invalid profile name: %r" % args.name, file=sys.stderr)
        return 2

    pdir = persona_dir()
    if args.cmd == "pull":
        ok, msg = pull(pdir, os.environ.get("AGENT_PERSONA_REPO"), args.force)
        print("pull: %s" % msg)
        if not ok:
            report(pdir, args.name)
            return 2
        if pdir.is_dir():
            activated = activate_overlays(pdir)
            if activated:
                print("activated: %d overlay item(s)" % len(activated))
    elif args.cmd == "activate":
        activated = activate_overlays(pdir)
        print("activated: %d overlay item(s)" % len(activated))
        rc = report(pdir, args.name)
        return 0 if (rc == 0 or len(activated) > 0) else rc
    return report(pdir, args.name)


if __name__ == "__main__":
    sys.exit(main())
