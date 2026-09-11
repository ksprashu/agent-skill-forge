#!/usr/bin/env python3
"""
Forensic Integrity Audit Engine for Multi-Agent Workflows
Part of the Google Antigravity Work Swarm Engine (skills/work).

Audits code and test suites for:
1. Synthetic mock facades (unittest.mock, jest.fn, vi.fn, patch)
2. Tautological assertions (assert True, expect(1).toBe(1))
3. Test tampering (deleted assertions, added skip markers via git diff)
4. Cryptographic proof verification and SHA-256 evidence logging
"""

import os
import sys
import io
import re
import ast
import hashlib
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

class ForensicViolation:
    def __init__(self, category: str, file_path: str, line_no: int, message: str, severity: str = "VETO"):
        self.category = category
        self.file_path = file_path
        self.line_no = line_no
        self.message = message
        self.severity = severity

    def __str__(self):
        return f"[{self.severity}] [{self.category}] {self.file_path}:{self.line_no} -> {self.message}"

class PythonASTAuditor(ast.NodeVisitor):
    def __init__(self, file_path: str, strict: bool = False):
        self.file_path = file_path
        self.strict = strict
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in ("unittest.mock", "mock"):
                sev = "VETO" if self.strict else "WARNING"
                self.violations.append(ForensicViolation(
                    category="MOCK_IMPORT",
                    file_path=self.file_path,
                    line_no=node.lineno,
                    message=f"Direct import of '{alias.name}'. Synthetic mocks isolate tests from physical runtime.",
                    severity=sev
                ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and ("unittest.mock" in node.module or node.module == "mock"):
            sev = "VETO" if self.strict else "WARNING"
            self.violations.append(ForensicViolation(
                category="MOCK_IMPORT",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Imported from '{node.module}'. Synthetic mocks isolate tests from physical runtime.",
                severity=sev
            ))
        self.generic_visit(node)

    def visit_Call(self, node):
        # Detect patch, patch.object, MagicMock, Mock calls
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("patch", "MagicMock", "Mock", "PropertyMock"):
            sev = "VETO" if self.strict else "WARNING"
            self.violations.append(ForensicViolation(
                category="MOCK_INVOCATION",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Invocation of mock factory '{func_name}()'.",
                severity=sev
            ))
        self.generic_visit(node)

    def visit_Assert(self, node):
        # Detect assert True or assert literal tautology
        is_tautology = False
        reason = ""

        # assert True, assert 1
        if isinstance(node.test, ast.Constant):
            if node.test.value is True or node.test.value == 1:
                is_tautology = True
                reason = f"Asserts constant literal '{node.test.value}'"
        elif isinstance(node.test, ast.Name) and node.test.id == "True":
            is_tautology = True
            reason = "Asserts variable 'True'"
        # assert x == x
        elif isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                left = ast.unparse(node.test.left) if hasattr(ast, "unparse") else ""
                right = ast.unparse(node.test.comparators[0]) if hasattr(ast, "unparse") else ""
                if left and left == right:
                    is_tautology = True
                    reason = f"Tautological self-comparison '{left} == {right}'"

        if is_tautology:
            self.violations.append(ForensicViolation(
                category="TAUTOLOGICAL_ASSERTION",
                file_path=self.file_path,
                line_no=node.lineno,
                message=f"Empty or tautological assertion detected: {reason}.",
                severity="VETO"
            ))

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Detect empty test functions (containing only pass or docstring)
        if node.name.startswith("test_"):
            statements = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
            if not statements or (len(statements) == 1 and isinstance(statements[0], ast.Pass)):
                self.violations.append(ForensicViolation(
                    category="EMPTY_TEST_BODY",
                    file_path=self.file_path,
                    line_no=node.lineno,
                    message=f"Test function '{node.name}' has an empty or no-op body.",
                    severity="VETO"
                ))
        self.generic_visit(node)

def audit_python_file(file_path: str, strict: bool) -> list[ForensicViolation]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=file_path)
        auditor = PythonASTAuditor(file_path, strict=strict)
        auditor.visit(tree)
        return auditor.violations
    except SyntaxError as e:
        return [ForensicViolation("SYNTAX_ERROR", file_path, e.lineno or 1, f"Failed to parse AST: {e.msg}")]
    except Exception as e:
        return [ForensicViolation("READ_ERROR", file_path, 1, f"Failed to read file: {e}")]

def audit_js_file(file_path: str, strict: bool) -> list[ForensicViolation]:
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            # Tautologies
            if re.search(r"expect\s*\(\s*true\s*\)\s*\.\s*to(?:Be|Equal)\s*\(\s*true\s*\)", stripped):
                violations.append(ForensicViolation("TAUTOLOGICAL_ASSERTION", file_path, idx, "Tautological assertion expect(true).toBe(true)", "VETO"))
            elif re.search(r"expect\s*\(\s*1\s*\)\s*\.\s*to(?:Be|Equal)\s*\(\s*1\s*\)", stripped):
                violations.append(ForensicViolation("TAUTOLOGICAL_ASSERTION", file_path, idx, "Tautological assertion expect(1).toBe(1)", "VETO"))
            elif re.search(r"assert\s*\(\s*true\s*\)", stripped):
                violations.append(ForensicViolation("TAUTOLOGICAL_ASSERTION", file_path, idx, "Tautological assert(true)", "VETO"))

            # Mocks
            if re.search(r"\b(jest\.fn|vi\.fn|sinon\.stub|jest\.mock)\b", stripped):
                sev = "VETO" if strict else "WARNING"
                violations.append(ForensicViolation("MOCK_INVOCATION", file_path, idx, f"JS/TS mock detected: '{stripped}'", sev))

    except Exception as e:
        violations.append(ForensicViolation("READ_ERROR", file_path, 1, f"Failed to read file: {e}"))
    return violations

def check_git_tampering(target_dir: str) -> list[ForensicViolation]:
    """Inspect git diff for deleted assertions or added skip markers."""
    violations = []
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", "tests", "test", "*test*"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0:
            return []

        diff_lines = result.stdout.splitlines()
        current_file = "unknown"
        for line in diff_lines:
            if line.startswith("--- a/"):
                current_file = line[6:]
            elif line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("-") and not line.startswith("---"):
                removed_content = line[1:].strip()
                if re.search(r"\b(assert|expect|self\.assert)\b", removed_content):
                    violations.append(ForensicViolation(
                        category="TAMPERING_ASSERTION_DELETED",
                        file_path=current_file,
                        line_no=0,
                        message=f"Assertion deleted from test suite: '{removed_content}'",
                        severity="VETO"
                    ))
            elif line.startswith("+") and not line.startswith("+++"):
                added_content = line[1:].strip()
                if re.search(r"(@pytest\.mark\.skip|it\.skip|describe\.skip|xit\(|fit\()", added_content):
                    violations.append(ForensicViolation(
                        category="TAMPERING_TEST_SKIPPED",
                        file_path=current_file,
                        line_no=0,
                        message=f"Test skip marker added: '{added_content}'",
                        severity="VETO"
                    ))
    except Exception:
        pass
    return violations

def record_evidence(target_dir: str, command: str, stdout: str, stderr: str, exit_code: int):
    """Write an immutable SHA-256 evidence record to .agents/EVIDENCE.md."""
    agents_dir = os.path.join(target_dir, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    evidence_file = os.path.join(agents_dir, "EVIDENCE.md")

    payload = f"{command}\n{stdout}\n{stderr}\n{exit_code}"
    sha256_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    status_icon = "✅" if exit_code == 0 else "❌"
    entry = f"""
### Evidence Record — {now_iso}
- **Status**: {status_icon} Exit Code {exit_code}
- **Command**: `{command}`
- **SHA-256 Proof**: `{sha256_hash}`
- **Output Sample**:
```text
{stdout[-500:] if len(stdout) > 500 else stdout}
```
---
"""
    if not os.path.exists(evidence_file):
        with open(evidence_file, "w", encoding="utf-8") as f:
            f.write("# 🛡️ Multi-Agent Forensic Evidence Ledger\n\nImmutable record of physical runtime verifications.\n\n")

    with open(evidence_file, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"🔒 Evidence recorded to {evidence_file} [SHA-256: {sha256_hash[:16]}...]")

def main():
    parser = argparse.ArgumentParser(description="Forensic Integrity Audit Engine for Multi-Agent Systems")
    parser.add_argument("--target-dir", default=".", help="Root directory to audit")
    parser.add_argument("--integrity-mode", choices=["development", "demo", "benchmark"], default="development",
                        help="Integrity mode: benchmark enforces zero-mock purity")
    parser.add_argument("--strict", action="store_true", help="Force benchmark-level zero mock tolerance")
    parser.add_argument("--exec-and-record", help="Run a verification command and record physical evidence")
    args = parser.parse_args()

    strict_mode = args.strict or (args.integrity_mode == "benchmark")

    print(f"=================================================================")
    print(f"🔍 Forensic Integrity Audit Engine — Mode: {args.integrity_mode.upper()}")
    print(f"=================================================================")

    violations = []

    # 1. Execute and record physical evidence if requested
    if args.exec_and_record:
        print(f"⚡ Executing physical process: {args.exec_and_record}")
        proc = subprocess.run(
            args.exec_and_record,
            shell=True,
            cwd=args.target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        record_evidence(args.target_dir, args.exec_and_record, proc.stdout, proc.stderr, proc.returncode)
        if proc.returncode != 0:
            violations.append(ForensicViolation(
                category="PROCESS_FAILURE",
                file_path="subshell",
                line_no=0,
                message=f"Command '{args.exec_and_record}' failed with exit code {proc.returncode}",
                severity="VETO"
            ))

    # 2. Scan test files
    target_path = Path(args.target_dir)
    test_files = []
    for pattern in ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py",
                    "**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts"]:
        for p in target_path.glob(pattern):
            if ".git" in p.parts or "node_modules" in p.parts or ".venv" in p.parts:
                continue
            test_files.append(p)

    test_files = list(set(test_files))
    print(f"📁 Discovered {len(test_files)} test suite files to audit.")

    for tf in test_files:
        filepath_str = str(tf)
        if tf.suffix == ".py":
            violations.extend(audit_python_file(filepath_str, strict=strict_mode))
        elif tf.suffix in (".js", ".ts"):
            violations.extend(audit_js_file(filepath_str, strict=strict_mode))

    # 3. Check git diff tampering
    violations.extend(check_git_tampering(args.target_dir))

    # 4. Synthesize Report
    vetos = [v for v in violations if v.severity == "VETO"]
    warnings = [v for v in violations if v.severity == "WARNING"]

    print("\n--- Forensic Audit Findings ---")
    if not violations:
        print("✅ ZERO forensic violations detected. Test suite displays high physical integrity.")
        sys.exit(0)

    for w in warnings:
        print(f"⚠️  {w}")

    for v in vetos:
        print(f"❌ {v}")

    print("-------------------------------")
    if vetos:
        print(f"\n🚨 VERDICT: VETO ({len(vetos)} blocking violations)")
        print("The Forensic Auditor has exercised Binary Veto. All cheats and circumventions must be remediated.")
        sys.exit(1)
    else:
        print(f"\n✅ VERDICT: CLEARED ({len(warnings)} non-blocking warnings)")
        sys.exit(0)

if __name__ == "__main__":
    main()
