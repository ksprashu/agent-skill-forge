#!/usr/bin/env python3
"""Forensic Integrity Audit Engine for multi-agent workflows.

Part of the Work Swarm Engine (``skills/work``). Backs the ``zero_mock``
barrier gate.

What this audits
----------------
1. **Production source** (the point of the thing): functions whose output
   cannot depend on their input, unimplemented stubs, discarded computation.
2. **Test suites**: synthetic mock facades, tautological assertions, empty
   bodies, tests whose only assertions are existence checks.
3. **Test tampering**: assertions deleted or skip markers added, via git diff.
4. **Mutation smoke** (opt-in, ``--mutate``): stub each function in turn and
   require the suite to go red. A surviving mutant is an unconstrained function.

What this does NOT audit — stated here and printed in every report, because a
verifier that overstates its coverage is worse than none:

* Semantic correctness. A wrong-but-input-dependent function passes.
* JavaScript/TypeScript source. Only pattern-scanned, and only for mocks and
  tautologies; no JS AST is parsed.
* Anything outside ``--target-dir``, or matched by ``--exclude``.

Exit codes: ``0`` clean (warnings allowed), ``1`` VETO, ``2`` invocation error.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

if sys.platform == "win32":  # pragma: no cover - platform specific
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

VETO = "VETO"
WARNING = "WARNING"

PRUNE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".tox", "dist", "build", ".eggs",
    "site-packages", ".next", ".nuxt", "target",
}

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs"}

#: Decorators that legitimise an empty or constant body.
STUB_EXEMPT_DECORATORS = {
    "abstractmethod", "abstractproperty", "overload", "singledispatch",
    "singledispatchmethod", "abstractclassmethod", "abstractstaticmethod",
}

#: Base classes whose methods are declarations, not implementations.
DECLARATION_BASES = {"Protocol", "ABC", "ABCMeta", "TypedDict", "NamedTuple"}

#: Calls that make an assertion about existence rather than about behaviour.
WEAK_ASSERT_CALLS = {"exists", "is_file", "is_dir", "hasattr", "isinstance", "callable"}


@dataclass
class ForensicViolation:
    category: str
    file_path: str
    line_no: int
    message: str
    severity: str = VETO

    def __str__(self) -> str:
        return f"[{self.severity}] [{self.category}] {self.file_path}:{self.line_no} -> {self.message}"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "file": self.file_path,
            "line": self.line_no,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ScanCoverage:
    """What was actually examined. Printed verbatim in every report."""

    source_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    js_files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)
    mutation_ran: bool = False
    mutants_total: int = 0
    mutants_survived: int = 0

    def to_dict(self) -> dict:
        return {
            "source_files_audited": len(self.source_files),
            "test_files_audited": len(self.test_files),
            "js_files_pattern_scanned": len(self.js_files),
            "files_skipped": len(self.skipped),
            "files_unparseable": len(self.unparseable),
            "mutation_smoke_ran": self.mutation_ran,
            "mutants_total": self.mutants_total,
            "mutants_survived": self.mutants_survived,
        }


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------

def _decorator_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    a = node.args
    names = [p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return [n for n in names if n not in ("self", "cls")]


def _loaded_names(node: ast.AST) -> set[str]:
    return {
        n.id for n in ast.walk(node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }


def _is_constant_expr(node: ast.AST | None) -> bool:
    """True if the expression's value is fixed at parse time.

    Literals, and containers built only from literals. A call, name, attribute,
    comprehension, f-string with a substitution, or operator on a name is not.
    """
    if node is None:
        return True  # bare `return`
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_constant_expr(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(_is_constant_expr(k) for k in node.keys) and all(
            _is_constant_expr(v) for v in node.values
        )
    if isinstance(node, ast.UnaryOp):
        return _is_constant_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return _is_constant_expr(node.left) and _is_constant_expr(node.right)
    if isinstance(node, ast.JoinedStr):
        return all(isinstance(v, ast.Constant) for v in node.values)
    return False


def _body_statements(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    """Function body minus its docstring."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return body


def _returns_in(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Return]:
    """Return statements belonging to this function, not to nested ones."""
    found: list[ast.Return] = []

    def walk(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, ast.Return):
                found.append(child)
            walk(child)

    walk(node)
    return found


# --------------------------------------------------------------------------
# Production source auditor — the part that was missing
# --------------------------------------------------------------------------

class SourceIntegrityAuditor(ast.NodeVisitor):
    """Finds functions whose output cannot depend on their input.

    This is the detector for the failure that shipped twice in this repo: an
    ``evaluate(evidence)`` that ignores ``evidence`` and returns a fixed dict,
    under a docstring claiming it computes something.
    """

    def __init__(self, file_path: str, strict: bool = False) -> None:
        self.file_path = file_path
        self.strict = strict
        self.violations: list[ForensicViolation] = []
        self._class_stack: list[ast.ClassDef] = []

    # -- traversal ---------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._audit_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._audit_function(node)
        self.generic_visit(node)

    # -- checks ------------------------------------------------------------

    def _in_declaration_class(self) -> bool:
        for cls in self._class_stack:
            for base in cls.bases:
                name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                if name in DECLARATION_BASES:
                    return True
        return False

    def _audit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if _decorator_names(node) & STUB_EXEMPT_DECORATORS:
            return
        if self._in_declaration_class():
            return

        body = _body_statements(node)
        params = _parameter_names(node)

        if self._check_stub(node, body):
            return
        if self._check_hardcoded_return(node, body, params):
            return
        self._check_ignored_parameters(node, body, params)
        self._check_dead_computation(node, body)

    def _check_stub(self, node, body) -> bool:
        """Empty body, ``...``, or a bare NotImplementedError."""
        if not body:
            reason = "body is empty"
        elif len(body) == 1 and isinstance(body[0], ast.Pass):
            reason = "body is a bare `pass`"
        elif len(body) == 1 and isinstance(body[0], ast.Expr) and \
                isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis:
            reason = "body is a bare `...`"
        elif len(body) == 1 and isinstance(body[0], ast.Raise):
            exc = body[0].exc
            target = exc.func if isinstance(exc, ast.Call) else exc
            name = getattr(target, "id", getattr(target, "attr", ""))
            if name != "NotImplementedError":
                return False
            reason = "body raises NotImplementedError"
        else:
            return False

        self.violations.append(ForensicViolation(
            category="UNIMPLEMENTED_STUB",
            file_path=self.file_path,
            line_no=node.lineno,
            message=(f"Production function '{node.name}' is declared but not implemented "
                     f"({reason}). Shipping a stub behind a docstring is the cheapest "
                     f"way to fake a deliverable."),
            severity=VETO if self.strict else WARNING,
        ))
        return True

    def _check_hardcoded_return(self, node, body, params) -> bool:
        """The core check: a function that takes input and cannot use it."""
        if not params:
            return False
        returns = _returns_in(node)
        if not returns:
            return False
        if not all(_is_constant_expr(r.value) for r in returns):
            return False
        # If a return is reached conditionally on a parameter, the output does
        # depend on the input (e.g. a predicate). Only flag when no parameter
        # is referenced anywhere in the body at all.
        referenced = _loaded_names(ast.Module(body=body, type_ignores=[]))
        if referenced & set(params):
            return False

        values = ", ".join(ast.unparse(r.value) if r.value is not None else "None" for r in returns[:3])
        self.violations.append(ForensicViolation(
            category="HARDCODED_RETURN",
            file_path=self.file_path,
            line_no=node.lineno,
            message=(f"Function '{node.name}({', '.join(params)})' returns only literal "
                     f"values ({values}) and never references any parameter. Its output "
                     f"cannot depend on its input — this is a hardcoded facade."),
            severity=VETO,
        ))
        return True

    def _check_ignored_parameters(self, node, body, params) -> None:
        """Non-trivial function that never reads any of its parameters."""
        if not params or len(body) < 2:
            return
        if node.name.startswith("__") and node.name.endswith("__"):
            return
        referenced = _loaded_names(ast.Module(body=body, type_ignores=[]))
        if referenced & set(params):
            return
        self.violations.append(ForensicViolation(
            category="IGNORED_PARAMETERS",
            file_path=self.file_path,
            line_no=node.lineno,
            message=(f"Function '{node.name}' accepts {params} and reads none of them. "
                     f"Either the parameters are dead or the implementation is a facade."),
            severity=VETO if self.strict else WARNING,
        ))

    def _check_dead_computation(self, node, body) -> None:
        """A call result assigned to a local that is then never read."""
        assigned: dict[str, int] = {}
        for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        assigned[target.id] = stmt.lineno
        if not assigned:
            return
        read = _loaded_names(ast.Module(body=body, type_ignores=[]))
        for name, lineno in assigned.items():
            if name in read or name.startswith("_"):
                continue
            self.violations.append(ForensicViolation(
                category="DEAD_COMPUTATION",
                file_path=self.file_path,
                line_no=lineno,
                message=(f"In '{node.name}', the result of a call is assigned to '{name}' "
                         f"and never read. Computation performed and discarded is the "
                         f"signature of a function that only looks like it works."),
                severity=VETO if self.strict else WARNING,
            ))


# --------------------------------------------------------------------------
# Test suite auditor
# --------------------------------------------------------------------------

class TestSuiteAuditor(ast.NodeVisitor):
    """Finds mock facades, tautologies, empty tests, and existence-only tests."""

    def __init__(self, file_path: str, strict: bool = False) -> None:
        self.file_path = file_path
        self.strict = strict
        self.violations: list[ForensicViolation] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in ("unittest.mock", "mock"):
                self.violations.append(ForensicViolation(
                    category="MOCK_IMPORT",
                    file_path=self.file_path,
                    line_no=node.lineno,
                    message=f"Direct import of '{alias.name}'. Synthetic mocks isolate tests from physical runtime.",
                    severity=VETO if self.strict else WARNING,
                ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and ("unittest.mock" in node.module or node.module == "mock"):
            self.violations.append(ForensicViolation(
                category="MOCK_IMPORT",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Imported from '{node.module}'. Synthetic mocks isolate tests from physical runtime.",
                severity=VETO if self.strict else WARNING,
            ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name in ("patch", "MagicMock", "Mock", "PropertyMock", "AsyncMock"):
            self.violations.append(ForensicViolation(
                category="MOCK_INVOCATION",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Invocation of mock factory '{func_name}()'.",
                severity=VETO if self.strict else WARNING,
            ))
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        reason = self._tautology_reason(node.test)
        if reason:
            self.violations.append(ForensicViolation(
                category="TAUTOLOGICAL_ASSERTION",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Empty or tautological assertion detected: {reason}.",
                severity=VETO,
            ))
        self.generic_visit(node)

    @staticmethod
    def _tautology_reason(test: ast.expr) -> str:
        if isinstance(test, ast.Constant) and (test.value is True or test.value == 1):
            return f"Asserts constant literal '{test.value}'"
        if isinstance(test, ast.Name) and test.id == "True":
            return "Asserts variable 'True'"
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            left = ast.unparse(test.left)
            right = ast.unparse(test.comparators[0])
            if left == right:
                return f"Tautological self-comparison '{left} == {right}'"
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test_"):
            self._audit_test_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("test_"):
            self._audit_test_function(node)
        self.generic_visit(node)

    def _audit_test_function(self, node) -> None:
        body = _body_statements(node)
        if not body or (len(body) == 1 and isinstance(body[0], ast.Pass)):
            self.violations.append(ForensicViolation(
                category="EMPTY_TEST_BODY",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Test function '{node.name}' has an empty or no-op body.",
                severity=VETO,
            ))
            return

        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        has_raises = any(
            isinstance(n, ast.Attribute) and n.attr in ("raises", "warns", "deprecated_call")
            for n in ast.walk(node)
        )
        # A call to an assertion helper counts: `self.assertEqual(...)`, and also
        # `self._assert_rejected(...)`, which is how parameterised negative tests
        # are usually factored.
        has_assert_call = any(
            "assert" in getattr(n, "attr", getattr(n, "id", "")).lower()
            for n in ast.walk(node)
            if isinstance(n, (ast.Attribute, ast.Name))
        )
        if not asserts and not has_raises and not has_assert_call:
            self.violations.append(ForensicViolation(
                category="NO_ASSERTION",
                file_path=self.file_path,
                line_no=node.lineno,
                message=(f"Test '{node.name}' executes code but asserts nothing. It can "
                         f"only fail on an exception."),
                severity=VETO if self.strict else WARNING,
            ))
            return

        if asserts and not has_raises and all(self._is_weak_assert(a.test) for a in asserts):
            self.violations.append(ForensicViolation(
                category="WEAK_ASSERTION_ONLY",
                file_path=self.file_path,
                line_no=node.lineno,
                message=(f"Every assertion in '{node.name}' is an existence or type check. "
                         f"The test confirms something was produced, not that it is right — "
                         f"a hardcoded implementation passes it."),
                severity=VETO if self.strict else WARNING,
            ))

    @staticmethod
    def _is_weak_assert(test: ast.expr) -> bool:
        if isinstance(test, ast.Name):
            return True  # bare truthiness
        if isinstance(test, ast.Call):
            target = test.func
            name = getattr(target, "attr", getattr(target, "id", ""))
            return name in WEAK_ASSERT_CALLS
        if isinstance(test, ast.Compare):
            ops = test.ops
            if len(ops) == 1 and isinstance(ops[0], (ast.In, ast.NotIn)):
                return True
            if len(ops) == 1 and isinstance(ops[0], (ast.Is, ast.IsNot)):
                comp = test.comparators[0]
                return isinstance(comp, ast.Constant) and comp.value is None
            # len(x) > 0 and friends
            if len(ops) == 1 and isinstance(ops[0], (ast.Gt, ast.GtE, ast.NotEq)):
                left, right = test.left, test.comparators[0]
                is_len = isinstance(left, ast.Call) and getattr(left.func, "id", "") == "len"
                is_zero = isinstance(right, ast.Constant) and right.value == 0
                return is_len and is_zero
        return False


# --------------------------------------------------------------------------
# File-level drivers
# --------------------------------------------------------------------------

def _parse(file_path: str, coverage: ScanCoverage) -> ast.Module | None:
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ast.parse(source, filename=file_path)
    except SyntaxError:
        coverage.unparseable.append(file_path)
        return None
    except OSError:
        coverage.unparseable.append(file_path)
        return None


def audit_python_source(file_path: str, strict: bool, coverage: ScanCoverage) -> list[ForensicViolation]:
    tree = _parse(file_path, coverage)
    if tree is None:
        return []
    auditor = SourceIntegrityAuditor(file_path, strict=strict)
    auditor.visit(tree)
    return auditor.violations


def audit_python_test(file_path: str, strict: bool, coverage: ScanCoverage) -> list[ForensicViolation]:
    tree = _parse(file_path, coverage)
    if tree is None:
        return []
    auditor = TestSuiteAuditor(file_path, strict=strict)
    auditor.visit(tree)
    return auditor.violations


JS_TAUTOLOGIES = (
    (r"expect\s*\(\s*true\s*\)\s*\.\s*to(?:Be|Equal)\s*\(\s*true\s*\)", "expect(true).toBe(true)"),
    (r"expect\s*\(\s*1\s*\)\s*\.\s*to(?:Be|Equal)\s*\(\s*1\s*\)", "expect(1).toBe(1)"),
    (r"assert\s*\(\s*true\s*\)", "assert(true)"),
)
JS_MOCKS = r"\b(jest\.fn|vi\.fn|sinon\.stub|jest\.mock|vi\.mock)\b"


def audit_js_file(file_path: str, strict: bool) -> list[ForensicViolation]:
    violations: list[ForensicViolation] = []
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [ForensicViolation("READ_ERROR", file_path, 1, f"Failed to read file: {exc}")]

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        for pattern, label in JS_TAUTOLOGIES:
            if re.search(pattern, stripped):
                violations.append(ForensicViolation(
                    "TAUTOLOGICAL_ASSERTION", file_path, idx, f"Tautological assertion {label}", VETO))
                break
        if re.search(JS_MOCKS, stripped):
            violations.append(ForensicViolation(
                "MOCK_INVOCATION", file_path, idx, f"JS/TS mock detected: '{stripped[:80]}'",
                VETO if strict else WARNING))
    return violations


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def is_test_path(path: Path) -> bool:
    if any(part in TEST_DIR_NAMES for part in path.parts):
        return True
    name = path.name
    if name.startswith("test_") or name.startswith("conftest"):
        return True
    return bool(re.search(r"(_test|\.test|\.spec)\.(py|js|ts|tsx|jsx|mjs)$", name))


def discover(target: Path, excludes: Iterable[str], coverage: ScanCoverage) -> None:
    exclude_patterns = list(excludes)

    def excluded(path: Path) -> bool:
        rel = path.relative_to(target).as_posix() if path.is_relative_to(target) else path.as_posix()
        return any(re.search(pat, rel) for pat in exclude_patterns)

    for root, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for filename in sorted(filenames):
            path = root_path / filename
            if path.suffix not in (".py", ".js", ".ts", ".tsx", ".jsx", ".mjs"):
                continue
            if excluded(path):
                coverage.skipped.append(str(path))
                continue
            if path.suffix == ".py":
                (coverage.test_files if is_test_path(path) else coverage.source_files).append(str(path))
            else:
                coverage.js_files.append(str(path))


# --------------------------------------------------------------------------
# Git tampering
# --------------------------------------------------------------------------

#: An assertion *statement*, not the word "assert" in a comment or a string.
ASSERTION_STMT_RE = re.compile(
    r"^(?:assert\b|self\.assert\w*\s*\(|expect\s*\(|cy\.\w+\s*\(.*should|"
    r"\w+\.assert\w*\s*\(|assert_\w+\s*\()")
COMMENT_PREFIXES = ("#", "//", "/*", "*", '"""', "'''", "<!--")


def check_git_tampering(target_dir: str) -> list[ForensicViolation]:
    """Look for assertions removed, or skip markers added, since HEAD.

    Only meaningful when the diff is a single agent's work against a known-good
    baseline — inside a ``/work`` milestone. Off by default, because against an
    ordinary working tree an honest test refactor is indistinguishable from
    tampering, and a verifier that cries wolf gets switched off.
    """
    violations: list[ForensicViolation] = []
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", "tests", "test", "*test*"],
            cwd=target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []

    current_file = "unknown"
    for line in result.stdout.splitlines():
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("-") and not line.startswith("---"):
            removed = line[1:].strip()
            if removed.startswith(COMMENT_PREFIXES):
                continue
            if ASSERTION_STMT_RE.match(removed):
                violations.append(ForensicViolation(
                    "TAMPERING_ASSERTION_DELETED", current_file, 0,
                    f"Assertion deleted from test suite: '{removed[:100]}'", VETO))
        elif line.startswith("+") and not line.startswith("+++"):
            added = line[1:].strip()
            if added.startswith(COMMENT_PREFIXES):
                continue
            if re.search(r"(@pytest\.mark\.skip|@unittest\.skip|it\.skip|describe\.skip|xit\(|fit\()", added):
                violations.append(ForensicViolation(
                    "TAMPERING_TEST_SKIPPED", current_file, 0,
                    f"Test skip marker added: '{added[:100]}'", VETO))
    return violations


# --------------------------------------------------------------------------
# Mutation smoke
# --------------------------------------------------------------------------

@dataclass
class Mutant:
    file: str
    function: str
    line: int
    killed: bool = False
    detail: str = ""


def _mutation_targets(path: Path) -> list[tuple[str, int, int, int, int]]:
    """(name, def_lineno, body_start_lineno, body_end_lineno, indent) per function."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except (SyntaxError, OSError):
        return []
    targets = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _decorator_names(node) & STUB_EXEMPT_DECORATORS:
            continue
        body = _body_statements(node)
        if not body:
            continue
        # Skip already-trivial bodies: mutating them changes nothing.
        if len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Return)) and \
                _is_constant_expr(getattr(body[0], "value", None)):
            continue
        end = max(getattr(s, "end_lineno", s.lineno) or s.lineno for s in body)
        targets.append((node.name, node.lineno, body[0].lineno, end, body[0].col_offset))
    return targets


def run_mutation_smoke(target: Path, source_files: list[str], test_cmd: str,
                       limit: int, timeout: int) -> tuple[list[Mutant], str]:
    """Stub each function in turn; the suite must go red. Survivors are findings."""
    argv = shlex.split(test_cmd)
    if not argv:
        return [], "empty --test-cmd"

    baseline = subprocess.run(
        argv, cwd=str(target), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if baseline.returncode != 0:
        return [], (f"baseline test command exited {baseline.returncode}; mutation smoke needs a "
                    f"green suite to start from")

    candidates: list[tuple[str, tuple]] = []
    for rel in source_files:
        for spec in _mutation_targets(Path(rel)):
            candidates.append((rel, spec))
    candidates = candidates[:limit]

    mutants: list[Mutant] = []
    for rel, (name, def_line, body_start, body_end, indent) in candidates:
        with tempfile.TemporaryDirectory(prefix="forensic-mutate-") as tmp:
            work = Path(tmp) / target.name
            shutil.copytree(target, work, ignore=shutil.ignore_patterns(*PRUNE_DIRS))
            mutated_path = work / Path(rel).relative_to(target)
            lines = mutated_path.read_text(encoding="utf-8", errors="replace").splitlines()
            replacement = " " * indent + "return None"
            lines[body_start - 1:body_end] = [replacement]
            mutated_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            mutant = Mutant(file=rel, function=name, line=def_line)
            try:
                proc = subprocess.run(
                    argv, cwd=str(work), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", timeout=timeout,
                )
                mutant.killed = proc.returncode != 0
                mutant.detail = f"exit {proc.returncode}"
            except subprocess.TimeoutExpired:
                mutant.killed = True
                mutant.detail = "timeout (treated as killed)"
            except OSError as exc:
                mutant.killed = True
                mutant.detail = f"could not run: {exc}"
            mutants.append(mutant)

    return mutants, ""


# --------------------------------------------------------------------------
# Evidence ledger
# --------------------------------------------------------------------------

def record_evidence(target_dir: str, command: str, stdout: str, stderr: str, exit_code: int) -> str:
    agents_dir = Path(target_dir) / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = agents_dir / "EVIDENCE.md"

    payload = f"{command}\n{stdout}\n{stderr}\n{exit_code}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status_icon = "PASS" if exit_code == 0 else "FAIL"

    entry = (
        f"\n### Evidence Record — {now_iso}\n"
        f"- **Status**: {status_icon} (exit code {exit_code})\n"
        f"- **Command**: `{command}`\n"
        f"- **SHA-256 Proof**: `{digest}`\n"
        f"- **Output Sample**:\n\n"
        f"```text\n{stdout[-1500:]}\n```\n\n---\n"
    )
    if not evidence_file.exists():
        evidence_file.write_text(
            "# Multi-Agent Forensic Evidence Ledger\n\n"
            "Immutable record of physical runtime verifications.\n\n",
            encoding="utf-8",
        )
    with evidence_file.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    print(f"Evidence recorded to {evidence_file} [SHA-256: {digest[:16]}...]")
    return digest


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _relative(file_path: str, target: Path) -> str:
    """Render a path relative to the audit root, so reports are portable."""
    try:
        return Path(file_path).resolve().relative_to(target).as_posix()
    except ValueError:
        return file_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forensic Integrity Audit Engine (skills/work). Backs the zero_mock gate.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--target-dir", "--project-dir", default=".", help="Root directory to audit")
    parser.add_argument("--integrity-mode", choices=["development", "demo", "benchmark"],
                        default="development",
                        help="benchmark escalates every warning to a blocking veto")
    parser.add_argument("--strict", action="store_true", help="Same as --integrity-mode benchmark")
    parser.add_argument("--exclude", action="append", default=[], metavar="REGEX",
                        help="Regex matched against repo-relative paths; repeatable")
    parser.add_argument("--check-tampering", action="store_true",
                        help="Scan `git diff HEAD` for deleted assertions and added skip "
                             "markers. Only meaningful against a known-good baseline, e.g. "
                             "inside a /work milestone; off by default.")
    parser.add_argument("--exec-and-record", metavar="CMD",
                        help="Run a verification command (argv, not a shell line) and record evidence")
    parser.add_argument("--mutate", action="store_true",
                        help="Run mutation smoke: stub each function and require the suite to go red")
    parser.add_argument("--test-cmd", metavar="CMD",
                        help="Test command for --mutate, e.g. 'python3 -m pytest -q'")
    parser.add_argument("--mutate-limit", type=int, default=25,
                        help="Maximum number of mutants to generate (default: 25)")
    parser.add_argument("--timeout", type=int, default=300, help="Per-subprocess timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report on stdout")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress the human report")
    return parser


def _print_human_report(violations: list[ForensicViolation], coverage: ScanCoverage,
                        mode: str, strict: bool, notes: list[str]) -> None:
    label = f"{mode.upper()} (strict: warnings escalated to veto)" if strict else mode.upper()
    print("=" * 72)
    print(f"Forensic Integrity Audit — mode: {label}")
    print("=" * 72)
    print(f"  production source files audited : {len(coverage.source_files)}")
    print(f"  test suite files audited        : {len(coverage.test_files)}")
    print(f"  JS/TS files pattern-scanned     : {len(coverage.js_files)}")
    if coverage.skipped:
        print(f"  files skipped by --exclude      : {len(coverage.skipped)}")
    if coverage.unparseable:
        print(f"  files that failed to parse      : {len(coverage.unparseable)}")
    if coverage.mutation_ran:
        killed = coverage.mutants_total - coverage.mutants_survived
        print(f"  mutation smoke                  : {killed}/{coverage.mutants_total} mutants killed")
    else:
        print("  mutation smoke                  : NOT RUN (pass --mutate --test-cmd)")

    print("\nNot checked by this tool: semantic correctness; JS/TS source logic "
          "(pattern scan only); anything outside --target-dir or matched by --exclude.")

    for note in notes:
        print(f"\nNOTE: {note}")

    warnings = [v for v in violations if v.severity == WARNING]
    vetos = [v for v in violations if v.severity == VETO]

    print("\n--- Findings ---")
    if not violations:
        print("No forensic violations in the surface described above.")
        return
    for violation in warnings:
        print(f"  WARN  {violation}")
    for violation in vetos:
        print(f"  VETO  {violation}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    target = Path(args.target_dir).resolve()
    if not target.is_dir():
        print(f"Error: --target-dir '{args.target_dir}' is not a directory", file=sys.stderr)
        return 2
    if args.mutate and not args.test_cmd:
        print("Error: --mutate requires --test-cmd", file=sys.stderr)
        return 2

    strict = args.strict or args.integrity_mode == "benchmark"
    violations: list[ForensicViolation] = []
    coverage = ScanCoverage()
    notes: list[str] = []

    # 1. Physical execution evidence -------------------------------------
    if args.exec_and_record:
        argv_exec = shlex.split(args.exec_and_record)
        if not argv_exec:
            print("Error: --exec-and-record is empty", file=sys.stderr)
            return 2
        try:
            proc = subprocess.run(
                argv_exec, cwd=str(target), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", timeout=args.timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Error: could not execute {argv_exec!r}: {exc}", file=sys.stderr)
            return 2
        record_evidence(args.target_dir, args.exec_and_record, proc.stdout, proc.stderr, proc.returncode)
        if proc.returncode != 0:
            violations.append(ForensicViolation(
                "PROCESS_FAILURE", "subprocess", 0,
                f"Command '{args.exec_and_record}' exited {proc.returncode}", VETO))

    # 2. Static audit ------------------------------------------------------
    discover(target, args.exclude, coverage)
    for path in coverage.source_files:
        violations.extend(audit_python_source(path, strict, coverage))
    for path in coverage.test_files:
        violations.extend(audit_python_test(path, strict, coverage))
    for path in coverage.js_files:
        violations.extend(audit_js_file(path, strict))

    if not coverage.source_files:
        notes.append("No production source files were found. This audit says nothing about "
                     "implementation integrity — only about the test suite.")
    if not coverage.test_files:
        notes.append("No test files were found. Nothing constrains the implementation.")

    # 3. Tampering ---------------------------------------------------------
    if args.check_tampering:
        violations.extend(check_git_tampering(str(target)))
    else:
        notes.append("Test tampering was not checked (pass --check-tampering, and only "
                     "against a known-good baseline).")

    # 4. Mutation smoke ----------------------------------------------------
    if args.mutate:
        mutants, error = run_mutation_smoke(
            target, coverage.source_files, args.test_cmd, args.mutate_limit, args.timeout)
        if error:
            notes.append(f"Mutation smoke did not run: {error}")
        else:
            coverage.mutation_ran = True
            coverage.mutants_total = len(mutants)
            survivors = [m for m in mutants if not m.killed]
            coverage.mutants_survived = len(survivors)
            for mutant in survivors:
                violations.append(ForensicViolation(
                    "SURVIVING_MUTANT", mutant.file, mutant.line,
                    f"Replacing the body of '{mutant.function}' with 'return None' left the "
                    f"suite green. Nothing tests what this function actually does.",
                    VETO if strict else WARNING))

    # 5. Report ------------------------------------------------------------
    for violation in violations:
        violation.file_path = _relative(violation.file_path, target)

    vetos = [v for v in violations if v.severity == VETO]
    warnings = [v for v in violations if v.severity == WARNING]

    if args.json:
        print(json.dumps({
            "mode": args.integrity_mode,
            "strict": strict,
            "verdict": "VETO" if vetos else "CLEARED",
            "veto_count": len(vetos),
            "warning_count": len(warnings),
            "coverage": coverage.to_dict(),
            "notes": notes,
            "violations": [v.to_dict() for v in violations],
        }, indent=2))
    elif not args.quiet:
        _print_human_report(violations, coverage, args.integrity_mode, strict, notes)

    if vetos:
        if not args.json and not args.quiet:
            print(f"\nVERDICT: VETO ({len(vetos)} blocking, {len(warnings)} advisory)")
            print("The Forensic Auditor has exercised Binary Veto.")
        return 1

    if not args.json and not args.quiet:
        print(f"\nVERDICT: CLEARED ({len(warnings)} advisory warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
