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

#: Imports that reach from one enforced root into another. Each is a script
#: that puts the other root on ``sys.path`` before importing, so the module is
#: local in fact even though it is not local to the importer's own directory.
#: Listed one by one, with the importer named, because the alternative —
#: pooling every root's module names into one allow-list — let a file in any
#: root vouch for an identically-named import in any other.
CROSS_ROOT_IMPORTS = {
    # validate_skills.py runs the DAG fixtures through the work skill's own
    # validator rather than reimplementing the parser.
    "scripts": frozenset({"dag_validator"}),
}

SKIP_DIR_NAMES = frozenset({"__pycache__", ".git", ".upstream", "node_modules", "fixtures"})


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if SKIP_DIR_NAMES & set(path.parts):
            continue
        yield path


def _modules_in(directory: Path) -> Set[str]:
    """What ``import x`` finds when ``directory`` is on ``sys.path``."""
    names: Set[str] = set()
    for child in directory.iterdir():
        if child.name in SKIP_DIR_NAMES:
            continue
        if child.is_file() and child.suffix == ".py":
            names.add(child.stem)
        elif child.is_dir() and (child / "__init__.py").exists():
            names.add(child.name)
    return names


def local_module_names(importer: Path) -> Set[str]:
    """Modules importable because they sit next to *this* importer.

    ``scaffold_work.py`` imports ``visual_engine`` from its own scripts
    directory. That is not a dependency; it is the same codebase.

    Computed per importer, not per root. A root-wide list let
    ``scripts/deep/helper.py`` vouch for ``import helper`` in ``scripts/a.py``,
    which cannot resolve it -- and let a nested file named after a third-party
    package hide that dependency everywhere in the root. Python puts the
    running script's directory on ``sys.path``, so that is what is local: the
    importer's siblings, and, for a module inside a package, the siblings of
    the directory the package was imported from.
    """
    names = _modules_in(importer.parent)
    base = importer.parent
    while (base / "__init__.py").exists():
        base = base.parent
    if base != importer.parent:
        names |= _modules_in(base)
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
    """Every non-stdlib import under ``roots``. One line per violation.

    The allow-list is computed per importer -- see ``local_module_names`` --
    and never as one union across roots. These trees are not mutually
    importable at runtime: nothing under ``hooks/`` can ``import`` a module
    that exists only in ``scripts/``. Pooling the names
    meant a file in one root vouched for an identically-named import in
    another, so a genuine missing dependency could hide behind a local module
    that merely shared its name.
    """
    stdlib = set(sys.stdlib_module_names) | {
        # Sibling trees these scripts legitimately add to sys.path.
        "tests",
    }
    violations: List[str] = []
    for rel in roots:
        root = repo_root / rel
        if not root.exists():
            violations.append(f"{root}: enforced root does not exist")
            continue
        shared = stdlib | CROSS_ROOT_IMPORTS.get(str(rel), frozenset())
        for path in iter_python_files(root):
            allowed = shared | local_module_names(path)
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
