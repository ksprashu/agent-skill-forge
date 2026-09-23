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

"""Domain skill autowiring for /work subagent dispatch.

``domain_autowiring.md`` said the Orchestrator "dynamically scans the local
``skills/`` and ``preferred/`` catalogs and injects specialized domain skills
directly into subagent prompt briefs". Nothing scanned anything. The matrix in
that document was a table an agent was trusted to read and apply from memory,
which meant the paths in it drifted from the filesystem and nobody found out.

This module does the scanning. It walks ``skills/*/SKILL.md`` and
``preferred/*/SKILL.md``, reads their frontmatter, folds in the tags from
``preferred/catalog.json`` when present, matches a task description against a
declared domain matrix, and emits the exact injection lines for the dispatch
payload.

What it does and does not claim:

    It reports which skills matched and **which terms caused the match**. It
    does not rank skills by usefulness and it does not decide which one the
    subagent actually needs — a keyword hit is a candidate, not a judgement.
    The dispatching agent reads the candidates and picks.

The one thing here that is a hard verdict is ``--check``: every skill path
named in the matrix must resolve to a real ``SKILL.md`` on disk. A matrix row
pointing at a skill that was renamed or deleted is a broken brief, and that is
mechanically decidable, so it exits non-zero.

Exit codes: 0 success, 1 check failed, 2 invocation error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SKILL_ROOTS = ("skills", "preferred")
SKILL_FILENAME = "SKILL.md"
CATALOG_RELPATH = Path("preferred") / "catalog.json"

# Words that match everything and therefore discriminate nothing.
STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have in into is it its of on or over
    that the their then there these this to under up was were will with your
    add build create ensure implement make need should use using write
    """.split()
)


@dataclass(frozen=True)
class SkillEntry:
    """A skill discovered on disk."""

    name: str
    relpath: str
    description: str
    tags: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": self.relpath,
            "description": self.description,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class Domain:
    """One row of the skill mapping matrix."""

    label: str
    skills: Tuple[str, ...]
    roles: Tuple[str, ...]
    instructions: str
    triggers: Tuple[str, ...]


@dataclass
class Match:
    """A domain that matched, and the terms that made it match."""

    domain: Domain
    terms: List[str] = field(default_factory=list)
    resolved: List[SkillEntry] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "domain": self.domain.label,
            "matched_terms": sorted(self.terms),
            "roles": list(self.domain.roles),
            "instructions": self.domain.instructions,
            "skills": [entry.to_dict() for entry in self.resolved],
            "missing_skills": list(self.missing),
        }


# The matrix is duplicated in ``references/domain_autowiring.md`` for humans.
# ``tests/test_autowire.py`` parses that table and asserts it agrees with this
# structure row for row, so the prose cannot drift away from the code again.
DOMAIN_MATRIX: Tuple[Domain, ...] = (
    Domain(
        label="Database, Schema & API Contracts",
        skills=("preferred/api-and-interface-design",),
        roles=("Explorer", "Worker"),
        instructions="Relational normalization, migration immutability, zero dummy seeds.",
        triggers=(
            "database", "schema", "migration", "sql", "postgres", "sqlite",
            "mysql", "orm", "table", "index", "query", "normalization",
            "seed data", "primary key", "foreign key", "api", "endpoint",
            "rest", "graphql", "contract", "interface",
        ),
    ),
    Domain(
        label="Observability & Logging",
        skills=("preferred/observability-and-instrumentation",),
        roles=("Explorer", "Worker"),
        instructions="Structured JSON logs, sensitive data scrubbing, /api/health.",
        triggers=(
            "logging", "log", "observability", "telemetry", "tracing", "trace",
            "metric", "prometheus", "opentelemetry", "monitoring", "dashboard",
            "alerting", "health", "health check", "health endpoint",
            "instrumentation",
        ),
    ),
    Domain(
        label="Security & RBAC",
        skills=("preferred/security-and-hardening",),
        roles=("Challenger", "Auditor"),
        instructions="OWASP Top 10, constant-time token comparison, brute-force mitigation.",
        triggers=(
            "security", "auth", "authentication", "authorization", "rbac",
            "permission", "token", "secret", "credential", "password",
            "encryption", "owasp", "injection", "xss", "csrf", "vulnerability",
            "hardening", "rate limit",
        ),
    ),
    Domain(
        label="CI/CD & Workflows",
        skills=("preferred/ci-cd-and-automation",),
        roles=("Worker", "Reviewer"),
        instructions="Deterministic caching, GitHub Actions, zero-secret hygiene.",
        triggers=(
            "ci", "cd", "pipeline", "github actions", "workflow", "deploy",
            "deployment", "release", "build cache", "automation", "runner",
        ),
    ),
    Domain(
        label="Testing & TDD",
        skills=("skills/test", "skills/verify"),
        roles=("Challenger", "Worker"),
        instructions="Red-Green-Refactor, static verifier scripts, blinded rubrics.",
        triggers=(
            "test", "tdd", "coverage", "fixture", "regression", "assertion",
            "pytest", "unit test", "integration test", "red-green",
        ),
    ),
    Domain(
        label="Code Review & Standards",
        skills=("skills/review", "skills/unslop"),
        roles=("Reviewer",),
        instructions="5-axis review, boilerplate stripping, zero AI fluff.",
        triggers=(
            "review", "refactor", "readability", "lint", "code smell",
            "boilerplate", "style", "cleanup", "naming",
        ),
    ),
    Domain(
        label="Performance & Benchmarking",
        skills=("preferred/performance-optimization", "preferred/benchmark-harness"),
        roles=("Challenger", "Worker"),
        instructions="Latency budgets, p99 regression gates, memory leak detection.",
        triggers=(
            "performance", "latency", "throughput", "benchmark", "profiling",
            "memory leak", "p99", "optimization", "slow", "cache hit",
            "hot path", "allocation",
        ),
    ),
)


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


def parse_frontmatter(text: str) -> Dict[str, str]:
    """Pull the top-level scalar keys out of a SKILL.md frontmatter block.

    Deliberately not a YAML parser. Skill frontmatter is two or three
    ``key: value`` lines; pulling in a parser for that would be a dependency
    bought with nothing.
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


def load_catalog_tags(repo_root: Path) -> Dict[str, Tuple[str, ...]]:
    """Read ``preferred/catalog.json`` tags, keyed by skill name."""
    catalog = repo_root / CATALOG_RELPATH
    try:
        payload = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    tags: Dict[str, Tuple[str, ...]] = {}
    for record in payload.get("skills", []):
        if not isinstance(record, dict):
            continue
        name = str(record.get("name", "")).strip()
        if not name:
            continue
        raw = record.get("tags", [])
        if isinstance(raw, list):
            tags[name] = tuple(str(tag).strip().lower() for tag in raw if str(tag).strip())
    return tags


def discover_skills(repo_root: Path) -> List[SkillEntry]:
    """Scan ``skills/`` and ``preferred/`` for installed skills."""
    tags = load_catalog_tags(repo_root)
    entries: List[SkillEntry] = []
    for root_name in SKILL_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            skill_file = child / SKILL_FILENAME
            if not skill_file.is_file():
                continue
            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError:
                continue
            front = parse_frontmatter(text)
            name = front.get("name") or child.name
            entries.append(
                SkillEntry(
                    name=name,
                    relpath=f"{root_name}/{child.name}",
                    description=front.get("description", ""),
                    tags=tags.get(child.name, tags.get(name, ())),
                )
            )
    return entries


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lowercase and reduce to space-separated alphanumeric runs."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def tokenize(text: str) -> frozenset:
    """Content tokens of ``text``, with a naive plural fold.

    ``metrics`` and ``metric`` are the same trigger as far as a task
    description is concerned; ``logs`` and ``log`` likewise. Stemming beyond
    the trailing ``s`` is guesswork that would make matches hard to predict.
    """
    tokens = set()
    for token in normalize(text).split():
        if token in STOPWORDS:
            continue
        tokens.add(token)
        if len(token) > 3 and token.endswith("s"):
            tokens.add(token[:-1])
        else:
            tokens.add(token + "s")
    return frozenset(tokens)


def trigger_hits(trigger: str, normalized: str, tokens: frozenset) -> bool:
    """Does ``trigger`` appear in the task text?

    Multi-word triggers match as a phrase; single words match whole tokens, so
    ``ci`` does not fire on ``specific``.
    """
    trigger_norm = normalize(trigger)
    if not trigger_norm:
        return False
    if " " in trigger_norm:
        return f" {trigger_norm} " in f" {normalized} "
    return trigger_norm in tokens


def match_domains(
    task: str,
    *,
    role: Optional[str] = None,
    matrix: Sequence[Domain] = DOMAIN_MATRIX,
) -> List[Match]:
    """Domains whose triggers appear in ``task``, most terms matched first.

    ``role`` narrows to the domains the matrix assigns to that role. Ties break
    on the domain label so two runs on the same task give the same brief.
    """
    normalized = normalize(task)
    tokens = tokenize(task)
    wanted_role = role.strip().lower() if role else None

    matches: List[Match] = []
    for domain in matrix:
        if wanted_role and wanted_role not in {r.lower() for r in domain.roles}:
            continue
        hits = [t for t in domain.triggers if trigger_hits(t, normalized, tokens)]
        if hits:
            matches.append(Match(domain=domain, terms=hits))
    matches.sort(key=lambda m: (-len(m.terms), m.domain.label))
    return matches


def resolve(matches: Iterable[Match], entries: Sequence[SkillEntry]) -> List[Match]:
    """Attach the on-disk skill for each matched path; note the ones missing."""
    by_path = {entry.relpath: entry for entry in entries}
    resolved: List[Match] = []
    for match in matches:
        match.resolved = []
        match.missing = []
        for relpath in match.domain.skills:
            entry = by_path.get(relpath)
            if entry is None:
                match.missing.append(relpath)
            else:
                match.resolved.append(entry)
        resolved.append(match)
    return resolved


def autowire(
    task: str,
    repo_root: Path,
    *,
    role: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Match]:
    """Full pipeline: scan the catalogs, match the task, resolve the paths."""
    entries = discover_skills(repo_root)
    matches = resolve(match_domains(task, role=role), entries)
    if limit is not None and limit >= 0:
        matches = matches[:limit]
    return matches


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render_brief(matches: Sequence[Match], *, role: Optional[str] = None) -> str:
    """The block to paste into a dispatch payload's Prompt field."""
    if not matches:
        return (
            "Domain Skills: none matched. Work from the task description and the "
            "grounding in .gemini/knowledge/."
        )
    header = "Domain Skills (read each with view_file before you start"
    header += f"; matched for role {role}):" if role else "):"
    lines = [header]
    for match in matches:
        terms = ", ".join(sorted(match.terms)[:6])
        for entry in match.resolved:
            lines.append(
                f"- {entry.relpath}/{SKILL_FILENAME} — {match.domain.label} "
                f"(matched: {terms})"
            )
        for missing in match.missing:
            lines.append(f"- MISSING: {missing} — declared in the matrix, absent on disk")
    lines.append(
        "These are keyword matches against the task text, not a judgement about "
        "what the task needs. Read them and apply the ones that apply."
    )
    return "\n".join(lines)


def render_listing(entries: Sequence[SkillEntry], matrix: Sequence[Domain]) -> str:
    """Human-readable dump of the matrix and its resolution status."""
    by_path = {entry.relpath: entry for entry in entries}
    lines = [f"Discovered {len(entries)} skills under {'/, '.join(SKILL_ROOTS)}/", ""]
    for domain in matrix:
        lines.append(f"{domain.label}  [roles: {', '.join(domain.roles)}]")
        for relpath in domain.skills:
            entry = by_path.get(relpath)
            status = "ok" if entry else "MISSING"
            detail = f" — {entry.description}" if entry and entry.description else ""
            lines.append(f"  [{status}] {relpath}{detail}")
        lines.append(f"  triggers: {', '.join(domain.triggers)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def check_matrix(repo_root: Path, matrix: Sequence[Domain] = DOMAIN_MATRIX) -> List[str]:
    """Every skill named in the matrix must exist. Returns the failures."""
    entries = {entry.relpath for entry in discover_skills(repo_root)}
    problems: List[str] = []
    for domain in matrix:
        if not domain.skills:
            problems.append(f"{domain.label}: maps to no skill at all")
        if not domain.triggers:
            problems.append(f"{domain.label}: has no triggers, so it can never match")
        for relpath in domain.skills:
            if relpath not in entries:
                problems.append(
                    f"{domain.label}: {relpath}/{SKILL_FILENAME} does not exist"
                )
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autowire.py",
        description="Resolve domain skills for a /work subagent dispatch brief.",
    )
    parser.add_argument("--task", help="Task description to match against the matrix")
    parser.add_argument("--role", help="Narrow to one role (Worker, Reviewer, ...)")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root holding skills/ and preferred/"
    )
    parser.add_argument("--max", type=int, default=None, help="Cap the number of domains")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a brief")
    parser.add_argument("--list", action="store_true", help="Print the matrix and exit")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify every matrix path resolves on disk; exit 1 if not",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    if not repo_root.is_dir():
        print(f"error: --repo-root {repo_root} is not a directory", file=sys.stderr)
        return 2

    if args.check:
        problems = check_matrix(repo_root)
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
        print(f"autowire matrix ok: {len(DOMAIN_MATRIX)} domains resolve on disk")
        return 0

    if args.list:
        print(render_listing(discover_skills(repo_root), DOMAIN_MATRIX), end="")
        return 0

    if not args.task:
        print("error: --task is required unless --list or --check is given", file=sys.stderr)
        return 2

    matches = autowire(args.task, repo_root, role=args.role, limit=args.max)
    if args.json:
        print(
            json.dumps(
                {
                    "task": args.task,
                    "role": args.role,
                    "matches": [m.to_dict() for m in matches],
                },
                indent=2,
            )
        )
    else:
        print(render_brief(matches, role=args.role))
    return 0


if __name__ == "__main__":
    sys.exit(main())
