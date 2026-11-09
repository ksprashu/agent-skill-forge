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

"""Cross-Harness Automagic Session Handoff Engine.

Subcommands:
  capture   Collect mechanical workspace/git facts and SHA-256 file digests (.handoff/manifest.json).
  validate  Audit .handoff/state.json against schema, secret-leak patterns, and optional path checks.
  render    Compile manifest.json + validated state.json into .handoff/HANDOFF.md.
  arm       Install reversible auto-pickup beacons for Antigravity, Claude Code, Gemini CLI, Codex, and Cursor.
  status    Compare current workspace state against manifest.json to surface post-handoff drift (or --inject).
  disarm    Cleanly remove all auto-pickup beacons (restoring tracked files byte-for-byte) and optionally archive.

Audit scope (Engineering Standard V3/V5):
  `validate` audits JSON schema structure, non-empty required sections, secret/token regex patterns across all
  string leaves, and (with `--check-paths`) on-disk existence of referenced artifacts across captured workspaces.
  `validate` does NOT judge the semantic accuracy of architectural prose or whether next_actions are optimal.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = 1
MANAGED_TAG = "agent-skill-forge/handoff"

BEACON_START = "<!-- HANDOFF:AUTO:START -->"
BEACON_END = "<!-- HANDOFF:AUTO:END -->"
EXCLUDE_START = "# HANDOFF:AUTO:START"
EXCLUDE_END = "# HANDOFF:AUTO:END"

CURSOR_RULE_REL = ".cursor/rules/00-active-handoff.mdc"
CLAUDE_LOCAL_REL = ".claude/settings.local.json"

MAX_DIRTY_LIST = 60
MAX_WATCHED_FILES = 60

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI/Stripe-style secret key", re.compile(r"\bsk-(?:live-|test-|proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Google OAuth access token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("PEM private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def contract_home(path: Path | str) -> str:
    """Replace the current user's home prefix with `~` so stored paths stay portable and PII-free."""
    raw = str(Path(path).resolve())
    home = str(Path.home().resolve())
    if raw == home:
        return "~"
    sep = os.sep
    if raw.startswith(home + sep):
        return "~/" + raw[len(home) + 1 :].replace("\\", "/")
    return raw.replace("\\", "/")


def expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


def redact_secrets(text: str) -> str:
    """Redact credential/token patterns at capture time (Engineering Standard S8)."""
    cleaned = text
    for label, pattern in SECRET_PATTERNS:
        cleaned = pattern.sub(f"[REDACTED:{label}]", cleaned)
    return cleaned


def find_secret_leaks(obj: Any, path_prefix: str = "$") -> list[str]:
    """Recursively scan all string values in a JSON object for unredacted secret patterns."""
    hits: list[str] = []
    if isinstance(obj, str):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(obj):
                hits.append(f"{path_prefix}: matched {label} pattern")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(find_secret_leaks(item, f"{path_prefix}[{idx}]"))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(find_secret_leaks(v, f"{path_prefix}.{k}"))
    return hits


def sha256_file(path: Path) -> str:
    if path.name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        try:
            raw_text = path.read_text(encoding="utf-8")
            body = strip_delimited_block(raw_text, BEACON_START, BEACON_END)
            return hashlib.sha256(body.encode("utf-8")).hexdigest()
        except (OSError, UnicodeDecodeError):
            pass
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def ensure_git_exclude(repo: Path, extra_entries: list[str] | None = None) -> bool:
    """Add .handoff and local beacon files to .git/info/exclude without touching tracked .gitignore."""
    git_dir = repo / ".git"
    if not git_dir.is_dir():
        return False
    info_dir = git_dir / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    exclude_file = info_dir / "exclude"
    existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
    existing = strip_delimited_block(existing, EXCLUDE_START, EXCLUDE_END)

    entries = [".handoff/", CURSOR_RULE_REL, CLAUDE_LOCAL_REL]
    if extra_entries:
        for item in extra_entries:
            if item not in entries:
                entries.append(item)

    block = "\n".join([EXCLUDE_START, *entries, EXCLUDE_END]) + "\n"
    sep = "" if (not existing or existing.endswith("\n")) else "\n"
    exclude_file.write_text(existing + sep + block, encoding="utf-8")
    return True


def remove_git_exclude(repo: Path) -> None:
    exclude_file = repo / ".git" / "info" / "exclude"
    if not exclude_file.exists():
        return
    cleaned = strip_delimited_block(exclude_file.read_text(encoding="utf-8"), EXCLUDE_START, EXCLUDE_END)
    exclude_file.write_text(cleaned, encoding="utf-8")


def strip_delimited_block(content: str, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker) + r"(?:\r?\n){0,2}",
        re.DOTALL,
    )
    return pattern.sub("", content)


def prepend_beacon_block(file_path: Path, block_body: str) -> bool:
    """Prepend a reversible beacon block to file_path. Returns True if the file was newly created."""
    full_block = f"{BEACON_START}\n{block_body.rstrip()}\n{BEACON_END}"
    created = not file_path.exists()
    if created:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(full_block + "\n", encoding="utf-8")
        return True

    original = file_path.read_text(encoding="utf-8")
    stripped = strip_delimited_block(original, BEACON_START, BEACON_END)
    file_path.write_text(f"{full_block}\n\n{stripped}", encoding="utf-8")
    return False


def collect_workspace(repo: Path, watch_files: list[str]) -> dict[str, Any]:
    """Collect purely factual git and file-digest metadata for one workspace."""
    repo = repo.resolve()
    ensure_git_exclude(repo)
    code, inside = _run_git(repo, "rev-parse", "--is-inside-work-tree")
    is_git = code == 0 and inside == "true"

    branch: str | None = None
    head_sha: str | None = None
    head_subject: str | None = None
    recent_commits: list[str] = []
    dirty_files: list[dict[str, str]] = []
    dirty_total = 0
    candidate_watch: list[str] = list(watch_files)

    if is_git:
        _, branch_out = _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        branch = branch_out or None
        rc_sha, sha_out = _run_git(repo, "rev-parse", "HEAD")
        if rc_sha == 0 and sha_out:
            head_sha = sha_out
            _, subj_out = _run_git(repo, "log", "-1", "--format=%s")
            head_subject = redact_secrets(subj_out) if subj_out else None
            _, log_out = _run_git(repo, "log", "-5", "--format=%h %s")
            if log_out:
                recent_commits = [redact_secrets(line) for line in log_out.splitlines() if line.strip()]

        _, status_out = _run_git(repo, "status", "--porcelain")
        if status_out:
            all_lines = [ln for ln in status_out.splitlines() if ln.strip()]
            for ln in all_lines:
                st = ln[:2].strip() or "?"
                rel_p = redact_secrets(ln[3:].strip().strip('"'))
                if rel_p.startswith(".handoff") or rel_p in (CURSOR_RULE_REL, CLAUDE_LOCAL_REL):
                    continue
                dirty_total += 1
                if len(dirty_files) < MAX_DIRTY_LIST:
                    dirty_files.append({"status": st, "path": rel_p})
                if st != "D" and len(candidate_watch) < MAX_WATCHED_FILES:
                    candidate_watch.append(rel_p)

    watched_digests: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for rel in candidate_watch:
        norm = rel.replace("\\", "/").lstrip("./")
        if not norm or norm in seen or norm.startswith(".handoff"):
            continue
        seen.add(norm)
        full = (repo / norm).resolve()
        try:
            full.relative_to(repo)
        except ValueError:
            continue
        if full.is_file():
            watched_digests[norm] = {
                "sha256": sha256_file(full),
                "size": full.stat().st_size,
            }
        if len(watched_digests) >= MAX_WATCHED_FILES:
            break

    return {
        "name": repo.name,
        "path": contract_home(repo),
        "is_git": is_git,
        "branch": branch,
        "head_sha": head_sha,
        "head_subject": head_subject,
        "recent_commits": recent_commits,
        "dirty_files": dirty_files,
        "dirty_total": dirty_total,
        "watched_digests": watched_digests,
    }


def cmd_capture(args: argparse.Namespace) -> int:
    root = expand_path(args.root)
    if not root.is_dir():
        print(f"error: root directory does not exist: {args.root}", file=sys.stderr)
        return 1

    handoff_dir = root / ".handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    repos = [root]
    for extra in args.extra_repo or []:
        ep = expand_path(extra)
        if not ep.is_dir():
            print(f"error: extra repo directory does not exist: {extra}", file=sys.stderr)
            return 1
        if ep not in repos:
            repos.append(ep)

    workspaces = [collect_workspace(r, args.watch_file or []) for r in repos]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": utc_now_iso(),
        "primary_workspace": root.name,
        "workspaces": workspaces,
    }

    out_path = expand_path(args.out) if args.out else (handoff_dir / "manifest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Captured mechanical snapshot for {len(workspaces)} workspace(s) -> {contract_home(out_path)}"
    )
    return 0


def validate_state_dict(
    state: Any,
    manifest: dict[str, Any] | None = None,
    check_paths: bool = False,
    fallback_root: Path | None = None,
) -> tuple[list[str], str]:
    """Validate state.json structure, secrets, and optional artifact paths."""
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["state root must be a JSON object"], "Audited root type only."

    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}, got {state.get('schema_version')!r}")

    for str_key in ("title", "mission"):
        val = state.get(str_key)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"'{str_key}' must be a non-empty string")

    focus = state.get("active_focus")
    if not isinstance(focus, dict):
        errors.append("'active_focus' must be an object")
    else:
        if not isinstance(focus.get("summary"), str) or not focus["summary"].strip():
            errors.append("'active_focus.summary' must be a non-empty string")
        if not isinstance(focus.get("primary_workspace"), str) or not focus["primary_workspace"].strip():
            errors.append("'active_focus.primary_workspace' must be a non-empty string")
        af = focus.get("active_files")
        if not isinstance(af, list) or not af or not all(isinstance(x, str) and x.strip() for x in af):
            errors.append("'active_focus.active_files' must be a non-empty list of file paths")

    next_actions = state.get("next_actions")
    if not isinstance(next_actions, list) or not next_actions:
        errors.append("'next_actions' must be a non-empty list of action objects")
    else:
        for idx, act in enumerate(next_actions):
            if not isinstance(act, dict):
                errors.append(f"'next_actions[{idx}]' must be an object")
                continue
            for req in ("step", "command_or_prompt", "expected_outcome"):
                if not isinstance(act.get(req), str) or not act[req].strip():
                    errors.append(f"'next_actions[{idx}].{req}' must be a non-empty string")

    for list_key in ("completed", "locked_decisions", "open_questions", "suggested_skills", "resume_verification"):
        if not isinstance(state.get(list_key), list):
            errors.append(f"'{list_key}' must be a list")

    rv = state.get("resume_verification")
    if isinstance(rv, list) and not rv:
        errors.append("'resume_verification' must contain at least one verification command")

    secret_hits = find_secret_leaks(state)
    for hit in secret_hits:
        errors.append(f"secret/token leak detected at {hit}")

    checked_paths_count = 0
    if check_paths and not errors:
        roots: list[Path] = []
        if manifest and isinstance(manifest.get("workspaces"), list):
            for ws in manifest["workspaces"]:
                if isinstance(ws, dict) and isinstance(ws.get("path"), str):
                    roots.append(expand_path(ws["path"]))
        if fallback_root and fallback_root not in roots:
            roots.append(fallback_root)

        paths_to_verify: list[str] = []
        if isinstance(focus, dict) and isinstance(focus.get("active_files"), list):
            paths_to_verify.extend(focus["active_files"])
        for comp in state.get("completed", []):
            if isinstance(comp, dict) and isinstance(comp.get("artifacts"), list):
                paths_to_verify.extend(comp["artifacts"])

        for rel_or_tilde in paths_to_verify:
            if not isinstance(rel_or_tilde, str):
                continue
            checked_paths_count += 1
            if rel_or_tilde.startswith("~"):
                if not expand_path(rel_or_tilde).exists():
                    errors.append(f"referenced artifact does not exist: {rel_or_tilde}")
                continue
            # Allow `workspace_name/rel/path` or `rel/path` inside any captured workspace
            found = False
            for r in roots:
                if (r / rel_or_tilde).exists():
                    found = True
                    break
                if "/" in rel_or_tilde:
                    prefix, rest = rel_or_tilde.split("/", 1)
                    if prefix == r.name and (r / rest).exists():
                        found = True
                        break
            if not found:
                errors.append(f"referenced artifact does not exist in captured workspaces: {rel_or_tilde}")

    scope_note = (
        f"Audited state schema (10 top-level fields), scanned all string leaves against "
        f"{len(SECRET_PATTERNS)} secret/token patterns, and verified {checked_paths_count} artifact path(s) "
        f"({'enabled' if check_paths else 'disabled'}); did not judge prose accuracy of locked_decisions or next_actions."
    )
    return errors, scope_note


def cmd_validate(args: argparse.Namespace) -> int:
    state_path = expand_path(args.state)
    if not state_path.is_file():
        print(f"error: state file not found: {args.state}", file=sys.stderr)
        return 1
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in state file: {exc}", file=sys.stderr)
        return 1

    manifest: dict[str, Any] | None = None
    if args.manifest:
        mp = expand_path(args.manifest)
        if not mp.is_file():
            print(f"error: manifest file not found: {args.manifest}", file=sys.stderr)
            return 1
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON in manifest file: {exc}", file=sys.stderr)
            return 1

    errors, scope_note = validate_state_dict(
        state,
        manifest=manifest,
        check_paths=bool(args.check_paths),
        fallback_root=state_path.parent.parent,
    )
    print(scope_note)
    if errors:
        for err in errors:
            print(f"violation: {err}")
        return 1
    print("State validation clean.")
    return 0


def render_handoff_markdown(manifest: dict[str, Any], state: dict[str, Any]) -> str:
    captured_at = manifest.get("captured_at", "unknown")
    focus = state["active_focus"]
    lines: list[str] = [
        f"# 🤝 Active Session Handoff: {state['title']}",
        "",
        f"- **Captured (UTC):** `{captured_at}`",
        f"- **Primary Workspace:** `{focus['primary_workspace']}`",
        f"- **Schema:** `agent-skill-forge/handoff@v{SCHEMA_VERSION}`",
        "",
        "## ⚡ Automagic Resume Protocol (Incoming Agent — Execute First)",
        "",
        "1. **Check Post-Handoff Drift:** Run `python3 ~/.agents/skills/handoff/scripts/handoff_ops.py status --root .` (or inspect the Git snapshot below) to see if any files changed after this handoff was saved.",
        "2. **Load Suggested Skills:** Read the `SKILL.md` instructions for the skills listed in **Suggested Skills** below before modifying artifacts.",
        "3. **Acknowledge & Continue Seamlessly:** Greet the user in 3-5 concise lines confirming the loaded mission, drift status, and **Next Immediate Action #1** — then proceed directly (or ask if an Open Question blocks execution).",
        "4. **Disarm When Consumed:** Once you have resumed steady-state work and no longer need new sessions to replay this handoff, run `python3 ~/.agents/skills/handoff/scripts/handoff_ops.py disarm --root . --archive`.",
        "",
        "---",
        "",
        "## 🎯 Mission & Active Focus",
        "",
        f"**Mission:** {state['mission']}",
        "",
        f"**Active Focus:** {focus['summary']}",
        "",
        "**Active Files in Flight:**",
    ]
    for af in focus["active_files"]:
        lines.append(f"- `{af}`")

    if state.get("locked_decisions"):
        lines.extend(
            [
                "",
                "---",
                "",
                "## 🔒 Locked Decisions, User Preferences & Hard Guardrails",
                "",
                "| Decision / Invariant | Rationale (Why This Matters) |",
                "| :--- | :--- |",
            ]
        )
        for item in state["locked_decisions"]:
            dec = str(item.get("decision", "")).replace("|", "\\|")
            rat = str(item.get("rationale", "")).replace("|", "\\|")
            lines.append(f"| **{dec}** | {rat} |")

    if state.get("completed"):
        lines.extend(
            [
                "",
                "---",
                "",
                "## ✅ Completed & Verified Milestones (Do Not Redo)",
                "",
            ]
        )
        for comp in state["completed"]:
            art_list = ", ".join(f"`{a}`" for a in comp.get("artifacts", []))
            ver = comp.get("verification", "n/a")
            lines.append(f"- **{comp.get('item', '')}**")
            if art_list:
                lines.append(f"  - *Artifacts:* {art_list}")
            lines.append(f"  - *Verification:* {ver}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 🗺️ Multi-Workspace Git & Working-Tree Snapshot",
            "",
        ]
    )
    for ws in manifest.get("workspaces", []):
        name = ws.get("name", "workspace")
        wpath = ws.get("path", ".")
        if ws.get("is_git"):
            sha_short = (ws.get("head_sha") or "uncommitted")[:10]
            subj = ws.get("head_subject") or ""
            lines.append(
                f"### `{name}` (`{wpath}`) — branch `{ws.get('branch')}` @ `{sha_short}` ({subj})"
            )
            dirty = ws.get("dirty_files", [])
            dirty_total = ws.get("dirty_total", 0)
            if dirty:
                lines.append(f"- **Uncommitted / Untracked Files ({dirty_total} total):**")
                for df in dirty[:25]:
                    lines.append(f"  - `{df['status']}` `{df['path']}`")
                if dirty_total > 25:
                    lines.append(f"  - *(+{dirty_total - 25} more files recorded in `.handoff/manifest.json`)*")
            else:
                lines.append("- **Working Tree:** Clean (`0` modified/untracked files)")
        else:
            lines.append(f"### `{name}` (`{wpath}`) — non-git directory")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 🚀 Next Immediate Actions (Ordered)",
            "",
        ]
    )
    for idx, act in enumerate(state["next_actions"], start=1):
        lines.append(f"{idx}. **{act['step']}**")
        lines.append(f"   - *Command / Prompt:* `{act['command_or_prompt']}`")
        lines.append(f"   - *Expected Outcome:* {act['expected_outcome']}")

    if state.get("open_questions"):
        lines.extend(
            [
                "",
                "---",
                "",
                "## ❓ Open Questions / Pending User Input",
                "",
            ]
        )
        for q in state["open_questions"]:
            lines.append(f"- {q}")

    if state.get("suggested_skills"):
        lines.extend(
            [
                "",
                "---",
                "",
                "## 🧰 Suggested Skills to Activate",
                "",
            ]
        )
        for sk in state["suggested_skills"]:
            lines.append(f"- **`{sk.get('skill', '')}`** — {sk.get('why', '')}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 🧪 Baseline Resume Verification Commands",
            "",
            "```bash",
            *state.get("resume_verification", []),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def cmd_render(args: argparse.Namespace) -> int:
    manifest_path = expand_path(args.manifest)
    state_path = expand_path(args.state)
    if not manifest_path.is_file() or not state_path.is_file():
        print("error: both --manifest and --state files must exist", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    errors, _ = validate_state_dict(
        state,
        manifest=manifest,
        check_paths=bool(args.check_paths),
        fallback_root=manifest_path.parent.parent,
    )
    if errors:
        for err in errors:
            print(f"violation: {err}", file=sys.stderr)
        return 1

    out_path = expand_path(args.out) if args.out else (manifest_path.parent / "HANDOFF.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_handoff_markdown(manifest, state), encoding="utf-8")
    print(f"Rendered handoff document -> {contract_home(out_path)}")
    return 0


def _arm_single_repo(
    target_repo: Path,
    title: str,
    mission: str,
    first_step: str,
    captured_at: str,
    no_tracked_edits: bool = False,
) -> dict[str, Any]:
    """Install reversible auto-pickup beacons across all supported AI harnesses in target_repo."""
    script_portable = contract_home(Path(__file__).resolve())
    created_files: list[str] = []
    modified_files: list[str] = []

    beacon_text = "\n".join(
        [
            f"> **⚡ ACTIVE SESSION HANDOFF (`{captured_at}`) — {title}**",
            f"> **Mission:** {mission}",
            f"> **First Next Step:** {first_step}",
            "> **MANDATORY ON SESSION START:** Read `.handoff/HANDOFF.md` immediately before taking action, run "
            f"`python3 {script_portable} status --root .` to check for post-handoff file drift, briefly confirm the "
            "loaded state to the user, and continue from **Next Immediate Actions**.",
        ]
    )

    # 1. Universal AGENTS.md beacon (Antigravity IDE/CLI, OpenAI Codex, Windsurf, Amp)
    agents_md = target_repo / "AGENTS.md"
    if not (no_tracked_edits and agents_md.exists()):
        if prepend_beacon_block(agents_md, beacon_text):
            created_files.append("AGENTS.md")
        else:
            modified_files.append("AGENTS.md")

    # 2. CLAUDE.md @import beacon + .claude/settings.local.json SessionStart deterministic hook
    claude_md = target_repo / "CLAUDE.md"
    claude_imports = "@AGENTS.md\n@.handoff/HANDOFF.md" if agents_md.exists() else "@.handoff/HANDOFF.md"
    claude_beacon = beacon_text + f"\n\n{claude_imports}"
    if not (no_tracked_edits and claude_md.exists()):
        if prepend_beacon_block(claude_md, claude_beacon):
            created_files.append("CLAUDE.md")
        else:
            modified_files.append("CLAUDE.md")

    claude_local = target_repo / CLAUDE_LOCAL_REL
    claude_existed = claude_local.exists()
    settings_data: dict[str, Any] = {}
    if claude_existed:
        try:
            settings_data = json.loads(claude_local.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings_data = {}
    hooks_obj = settings_data.setdefault("hooks", {})
    session_start_list: list[dict[str, Any]] = [
        entry
        for entry in hooks_obj.get("SessionStart", [])
        if not (isinstance(entry, dict) and entry.get("_managed_by") == MANAGED_TAG)
    ]
    session_start_list.append(
        {
            "_managed_by": MANAGED_TAG,
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f"python3 {os.path.expanduser(script_portable)} status --root . --inject",
                }
            ],
        }
    )
    hooks_obj["SessionStart"] = session_start_list
    claude_local.parent.mkdir(parents=True, exist_ok=True)
    claude_local.write_text(json.dumps(settings_data, indent=2) + "\n", encoding="utf-8")

    # 3. GEMINI.md beacon + @import (Gemini CLI)
    gemini_md = target_repo / "GEMINI.md"
    gemini_beacon = beacon_text + "\n>\n@.handoff/HANDOFF.md"
    if not (no_tracked_edits and gemini_md.exists()):
        if prepend_beacon_block(gemini_md, gemini_beacon):
            created_files.append("GEMINI.md")
        else:
            modified_files.append("GEMINI.md")

    # 4. Cursor rule (.cursor/rules/00-active-handoff.mdc with alwaysApply: true)
    cursor_rule = target_repo / CURSOR_RULE_REL
    cursor_rule.parent.mkdir(parents=True, exist_ok=True)
    cursor_content = "\n".join(
        [
            "---",
            f"description: Active cross-tool session handoff ({title})",
            "globs:",
            "alwaysApply: true",
            "---",
            "",
            beacon_text,
            "",
            "Read `.handoff/HANDOFF.md` in full before executing any edits.",
            "",
        ]
    )
    cursor_rule.write_text(cursor_content, encoding="utf-8")

    ensure_git_exclude(target_repo, extra_entries=created_files)

    record = {
        "schema_version": SCHEMA_VERSION,
        "armed_at": utc_now_iso(),
        "created_files": created_files,
        "modified_files": modified_files,
        "claude_settings_existed": claude_existed,
    }
    return record


def cmd_arm(args: argparse.Namespace) -> int:
    root = expand_path(args.root)
    handoff_dir = root / ".handoff"
    manifest_path = handoff_dir / "manifest.json"
    state_path = handoff_dir / "state.json"
    handoff_md_path = handoff_dir / "HANDOFF.md"

    if not (manifest_path.is_file() and state_path.is_file() and handoff_md_path.is_file()):
        print(
            "error: .handoff/{manifest.json,state.json,HANDOFF.md} must all exist before arming",
            file=sys.stderr,
        )
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    first_step = state["next_actions"][0]["step"]
    captured_at = manifest.get("captured_at", utc_now_iso())

    primary_record = _arm_single_repo(
        root,
        title=state["title"],
        mission=state["mission"],
        first_step=first_step,
        captured_at=captured_at,
        no_tracked_edits=bool(args.no_tracked_edits),
    )

    linked_repos: list[str] = []
    for raw_link in args.link_repo or []:
        lp = expand_path(raw_link)
        if not lp.is_dir() or lp == root:
            continue
        lh = lp / ".handoff"
        lh.mkdir(parents=True, exist_ok=True)
        for fname in ("manifest.json", "state.json", "HANDOFF.md"):
            shutil.copy2(handoff_dir / fname, lh / fname)
        sub_rec = _arm_single_repo(
            lp,
            title=state["title"],
            mission=state["mission"],
            first_step=first_step,
            captured_at=captured_at,
            no_tracked_edits=bool(args.no_tracked_edits),
        )
        sub_rec["linked_from"] = contract_home(root)
        (lh / "armed.json").write_text(json.dumps(sub_rec, indent=2) + "\n", encoding="utf-8")
        linked_repos.append(contract_home(lp))

    primary_record["linked_repos"] = linked_repos
    (handoff_dir / "armed.json").write_text(json.dumps(primary_record, indent=2) + "\n", encoding="utf-8")
    print(
        f"Armed automagic pickup beacons in {contract_home(root)}"
        + (f" (+ {len(linked_repos)} linked repo(s))" if linked_repos else "")
    )
    return 0


def compute_drift(manifest: dict[str, Any]) -> list[str]:
    """Compare live workspaces against manifest.json SHA-256 digests and git HEADs."""
    drifted: list[str] = []
    for ws in manifest.get("workspaces", []):
        wname = ws.get("name", "workspace")
        wpath = expand_path(ws.get("path", "."))
        if not wpath.is_dir():
            drifted.append(f"[{wname}] workspace directory missing at {ws.get('path')}")
            continue
        if ws.get("is_git") and ws.get("head_sha"):
            rc, live_sha = _run_git(wpath, "rev-parse", "HEAD")
            if rc == 0 and live_sha and live_sha != ws["head_sha"]:
                drifted.append(
                    f"[{wname}] git HEAD moved from {ws['head_sha'][:10]} to {live_sha[:10]}"
                )
        for rel, meta in ws.get("watched_digests", {}).items():
            fp = wpath / rel
            if not fp.is_file():
                drifted.append(f"[{wname}] watched file deleted: {rel}")
            else:
                live_hash = sha256_file(fp)
                if live_hash != meta.get("sha256"):
                    drifted.append(f"[{wname}] file modified since handoff: {rel}")
    return drifted


def cmd_status(args: argparse.Namespace) -> int:
    root = expand_path(args.root)
    handoff_dir = root / ".handoff"
    manifest_path = handoff_dir / "manifest.json"
    handoff_md_path = handoff_dir / "HANDOFF.md"
    armed_path = handoff_dir / "armed.json"

    if not (manifest_path.is_file() and handoff_md_path.is_file()):
        if args.json:
            print(json.dumps({"active": False, "armed": False, "drift_detected": False, "drifted_items": []}))
        elif not args.inject:
            print("No active handoff in this workspace.")
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drifted = compute_drift(manifest)
    payload = {
        "active": True,
        "armed": armed_path.is_file(),
        "captured_at": manifest.get("captured_at"),
        "primary_workspace": manifest.get("primary_workspace"),
        "drift_detected": bool(drifted),
        "drifted_items": drifted,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    if args.inject:
        print("=== ACTIVE CROSS-TOOL SESSION HANDOFF (AUTO-LOADED) ===")
        if drifted:
            print("⚠️ POST-HANDOFF DRIFT DETECTED — RE-READ THESE ITEMS BEFORE EDITING:")
            for item in drifted:
                print(f"  - {item}")
        else:
            print("✅ DRIFT CHECK CLEAN: Working tree matches handoff snapshot.")
        print("")
        print(handoff_md_path.read_text(encoding="utf-8"))
        return 0

    print(f"Active handoff: YES (captured {payload['captured_at']}, armed={payload['armed']})")
    if drifted:
        print(f"Drift detected ({len(drifted)} item(s)):")
        for item in drifted:
            print(f"  - {item}")
    else:
        print("Drift check: CLEAN (0 files drifted since handoff)")
    return 0


def _disarm_single_repo(target_repo: Path, archive: bool = False, is_linked: bool = False) -> None:
    handoff_dir = target_repo / ".handoff"
    armed_path = handoff_dir / "armed.json"
    armed: dict[str, Any] = {}
    if armed_path.is_file():
        try:
            armed = json.loads(armed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            armed = {}

    created_set = set(armed.get("created_files", []))
    for doc_name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        doc_path = target_repo / doc_name
        if not doc_path.exists():
            continue
        if doc_name in created_set:
            doc_path.unlink()
        else:
            cleaned = strip_delimited_block(doc_path.read_text(encoding="utf-8"), BEACON_START, BEACON_END)
            doc_path.write_text(cleaned, encoding="utf-8")

    cursor_rule = target_repo / CURSOR_RULE_REL
    if cursor_rule.exists():
        cursor_rule.unlink()
        # Clean empty .cursor/rules and .cursor directories if we left nothing else behind
        for parent in (cursor_rule.parent, cursor_rule.parent.parent):
            try:
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass

    claude_local = target_repo / CLAUDE_LOCAL_REL
    if claude_local.exists():
        existed_before = armed.get("claude_settings_existed", True)
        try:
            sdata = json.loads(claude_local.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sdata = {}
        hooks_obj = sdata.get("hooks")
        if isinstance(hooks_obj, dict) and "SessionStart" in hooks_obj:
            kept = [
                e
                for e in hooks_obj.get("SessionStart", [])
                if not (isinstance(e, dict) and e.get("_managed_by") == MANAGED_TAG)
            ]
            if kept:
                hooks_obj["SessionStart"] = kept
            else:
                hooks_obj.pop("SessionStart", None)
            if not hooks_obj:
                sdata.pop("hooks", None)
        if not sdata and not existed_before:
            claude_local.unlink()
            try:
                if claude_local.parent.is_dir() and not any(claude_local.parent.iterdir()):
                    claude_local.parent.rmdir()
            except OSError:
                pass
        else:
            claude_local.write_text(json.dumps(sdata, indent=2) + "\n", encoding="utf-8")

    remove_git_exclude(target_repo)

    if armed_path.exists():
        armed_path.unlink()

    if is_linked and handoff_dir.is_dir():
        shutil.rmtree(handoff_dir, ignore_errors=True)
    elif archive and handoff_dir.is_dir():
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = handoff_dir / "archive" / stamp
        dest.mkdir(parents=True, exist_ok=True)
        for fname in ("manifest.json", "state.json", "HANDOFF.md"):
            src = handoff_dir / fname
            if src.is_file():
                shutil.move(str(src), str(dest / fname))


def cmd_disarm(args: argparse.Namespace) -> int:
    root = expand_path(args.root)
    armed_path = root / ".handoff" / "armed.json"
    linked_repos: list[str] = []
    if armed_path.is_file():
        try:
            linked_repos = json.loads(armed_path.read_text(encoding="utf-8")).get("linked_repos", [])
        except json.JSONDecodeError:
            linked_repos = []

    for lr in linked_repos:
        lp = expand_path(lr)
        if lp.is_dir():
            _disarm_single_repo(lp, archive=False, is_linked=True)

    _disarm_single_repo(root, archive=bool(args.archive), is_linked=False)
    print(f"Disarmed handoff beacons in {contract_home(root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff_ops.py",
        description="Deterministic cross-harness session handoff capture, verifier, renderer, and auto-pickup beacon manager.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_cap = sub.add_parser("capture", help="Capture mechanical workspace & git snapshot to .handoff/manifest.json")
    p_cap.add_argument("--root", default=".", help="Primary workspace root directory")
    p_cap.add_argument("--extra-repo", action="append", default=[], help="Additional participating repo path (repeatable)")
    p_cap.add_argument("--watch-file", action="append", default=[], help="Relative file path to SHA-256 hash for drift checks (repeatable)")
    p_cap.add_argument("--out", help="Custom output path for manifest.json (defaults to <root>/.handoff/manifest.json)")
    p_cap.set_defaults(func=cmd_capture)

    p_val = sub.add_parser("validate", help="Validate state.json schema, secret hygiene, and optional file existence")
    p_val.add_argument("--state", required=True, help="Path to .handoff/state.json")
    p_val.add_argument("--manifest", help="Optional path to .handoff/manifest.json")
    p_val.add_argument("--check-paths", action="store_true", help="Verify all referenced active/completed artifact paths exist on disk")
    p_val.set_defaults(func=cmd_validate)

    p_ren = sub.add_parser("render", help="Render validated state.json + manifest.json into .handoff/HANDOFF.md")
    p_ren.add_argument("--manifest", required=True, help="Path to .handoff/manifest.json")
    p_ren.add_argument("--state", required=True, help="Path to .handoff/state.json")
    p_ren.add_argument("--out", help="Output Markdown path (defaults to <root>/.handoff/HANDOFF.md)")
    p_ren.add_argument("--check-paths", action="store_true", help="Enforce artifact existence check before rendering")
    p_ren.set_defaults(func=cmd_render)

    p_arm = sub.add_parser("arm", help="Install reversible auto-pickup beacons across all AI coding harnesses")
    p_arm.add_argument("--root", default=".", help="Primary workspace directory containing .handoff/")
    p_arm.add_argument("--link-repo", action="append", default=[], help="Mirror .handoff/ and arm beacons in sibling repo (repeatable)")
    p_arm.add_argument("--no-tracked-edits", action="store_true", help="Skip editing existing AGENTS.md/CLAUDE.md/GEMINI.md; use only git-excluded local hooks/rules")
    p_arm.set_defaults(func=cmd_arm)

    p_sta = sub.add_parser("status", help="Check active handoff status and post-handoff file/git drift")
    p_sta.add_argument("--root", default=".", help="Workspace directory")
    p_sta.add_argument("--json", action="store_true", help="Emit machine-readable JSON status")
    p_sta.add_argument("--inject", action="store_true", help="Print live drift banner + full HANDOFF.md for SessionStart hooks")
    p_sta.set_defaults(func=cmd_status)

    p_dis = sub.add_parser("disarm", help="Remove all auto-pickup beacons (restoring files byte-for-byte) and optionally archive")
    p_dis.add_argument("--root", default=".", help="Primary workspace directory")
    p_dis.add_argument("--archive", action="store_true", help="Move manifest.json, state.json, and HANDOFF.md into .handoff/archive/<timestamp>/")
    p_dis.set_defaults(func=cmd_disarm)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
