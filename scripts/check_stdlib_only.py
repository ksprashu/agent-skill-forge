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

"""Enforce the stdlib-only rule where the repository actually claims it.

The forge's engine scripts run inside agent harnesses on machines the authors
do not control, with no install step. A single ``import requests`` turns a
working skill into a traceback on someone else's laptop, and the traceback
arrives mid-task.

The rule is not repository-wide, and pretending otherwise would be a lie this
script then had to carry exceptions for: ``skills/image-gen`` needs Pillow and
the Google SDK, and the OKF verifiers need PyYAML. Those skills declare their
dependencies and bootstrap them. ``ENFORCED_ROOTS`` lists the trees where no
such declaration exists and none is wanted.

Exit codes: 0 clean, 1 violations found, 2 invocation error.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple

#: Trees that must run on a bare interpreter. Everything the /work DAG engine
#: executes, plus the installer-side scripts and hooks.
ENFORCED_ROOTS = ("scripts", "hooks", "skills/work/scripts")

# sys.stdlib_module_names arrived in 3.10 and there is no honest way to fake the
# list on an older runtime. Everything this repo actually installs runs on 3.9;
# only this developer check does not. Say so plainly, because the alternative is
# an AttributeError sixteen frames deep in a test run.
MIN_PYTHON = (3, 10)
if sys.version_info < MIN_PYTHON:
    raise SystemExit(
        f"check_stdlib_only.py needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer "
        f"(running {sys.version_info.major}.{sys.version_info.minor}); it reads "
        f"sys.stdlib_module_names to decide what counts as stdlib.\n"
        f"The installer and the skills themselves have no such floor -- this is a "
        f"lint, so run it with a newer interpreter."
    )

#: Test-only dependency. The engine scripts themselves may not import it.
TEST_ONLY_MODULES = frozenset({"pytest"})

SKIP_DIR_NAMES = frozenset({"__pycache__", ".git", ".upstream", "node_modules", "fixtures"})


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if SKIP_DIR_NAMES & set(path.parts):
            continue
        yield path


def local_module_names(roots: Sequence[Path]) -> Set[str]:
    """Modules importable because they sit next to the importer.

    ``scaffold_work.py`` imports ``visual_engine`` from its own scripts
    directory. That is not a dependency; it is the same codebase.
    """
    names: Set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in iter_python_files(root):
            names.add(path.stem)
            names.add(path.parent.name)
        for child in root.rglob("*"):
            if child.is_dir() and (child / "__init__.py").exists():
                names.add(child.name)
    return names


def imported_modules(tree: ast.AST) -> Iterable[Tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # explicit relative import, always local
                continue
            if node.module:
                yield node.lineno, node.module.split(".")[0]


def scan(repo_root: Path, roots: Sequence[str] = ENFORCED_ROOTS) -> List[str]:
    """Every non-stdlib import under ``roots``. One line per violation."""
    root_paths = [repo_root / r for r in roots]
    allowed = set(sys.stdlib_module_names) | local_module_names(root_paths) | {
        # Sibling trees these scripts legitimately add to sys.path.
        "tests",
    }
    violations: List[str] = []
    for root in root_paths:
        if not root.exists():
            violations.append(f"{root}: enforced root does not exist")
            continue
        for path in iter_python_files(root):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                violations.append(f"{path.relative_to(repo_root)}:{exc.lineno}: syntax error: {exc.msg}")
                continue
            for lineno, module in imported_modules(tree):
                if not module or module in allowed:
                    continue
                note = " (test-only dependency)" if module in TEST_ONLY_MODULES else ""
                violations.append(
                    f"{path.relative_to(repo_root)}:{lineno}: non-stdlib import "
                    f"'{module}'{note}"
                )
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_stdlib_only.py",
        description="Fail if an engine script imports something the stdlib does not provide.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--root", action="append", default=None,
                        help="Override the enforced roots (repeatable)")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"error: --repo-root {repo_root} is not a directory", file=sys.stderr)
        return 2

    roots = tuple(args.root) if args.root else ENFORCED_ROOTS
    violations = scan(repo_root, roots)
    if violations:
        for violation in violations:
            print(f"error: {violation}", file=sys.stderr)
        print(f"\n{len(violations)} non-stdlib import(s) under: {', '.join(roots)}",
              file=sys.stderr)
        return 1

    print(f"stdlib-only: clean across {', '.join(roots)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
