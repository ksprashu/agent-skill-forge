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
Review Collector (S9 Evidence Collector) for the Review Skill.

Collects objective mechanical facts about a git diff and/or repository topology:
- Git diff stats: modified file paths, lines added/deleted, diff size (>500 lines check).
- Manifest discovery: package.json, pyproject.toml, Cargo.toml, go.mod, etc.
- Static tool detection: linters, formatters, typecheckers, test runners, CI configurations.
- Repository topology: file extensions, top-level directories, file counts.

In strict compliance with docs/ENGINEERING_STANDARD.md:
- S1: Python 3.12, stdlib only.
- S2: Never shadow stdlib module names.
- S3: Exit non-zero on failure.
- S4: subprocess with argv and shell=False.
- S5: No hardcoded absolute paths.
- S9: Evidence/judgement split - collects counts and facts, never scores or judges.
- V5: Explicitly reports what was NOT inspected.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Strict console UTF-8 safety
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".tox",
    "dist",
    "build",
    ".next",
    ".cache",
    "target",
    ".turbo",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

MANIFEST_MAP: Dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java/gradle",
    "build.gradle.kts": "kotlin/gradle",
    "Gemfile": "ruby",
    "composer.json": "php",
    "flake.nix": "nix",
}

UNINSPECTED_SURFACE: List[str] = [
    "runtime execution dynamics and memory allocation profiles",
    "live production traffic logs and telemetry streams",
    "subjective architectural elegance and semantic business intent",
    "third-party cloud service permissions and remote state",
]


class ReviewCollector:
    """Collects empirical repository and diff facts without qualitative judgement."""

    def __init__(self, target_path: Path | str = "."):
        self.target_path = Path(target_path).resolve()
        if not self.target_path.exists():
            raise FileNotFoundError(f"Target path does not exist: {self.target_path}")

    def is_git_repo(self) -> bool:
        """Check if target_path is within a git working tree."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.target_path),
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            return False

    def get_git_root(self) -> Optional[Path]:
        """Return the root path of the git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(self.target_path),
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
            if res.returncode == 0:
                return Path(res.stdout.strip()).resolve()
        except Exception:
            pass
        return None

    def collect_diff(
        self,
        base_ref: Optional[str] = None,
        staged_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Collect git diff statistics.

        Returns a dictionary containing files changed, lines inserted/deleted,
        and boolean flags indicating whether diff exceeds 500 lines.
        """
        if not self.is_git_repo():
            raise RuntimeError(
                f"Cannot inspect diff: {self.target_path} is not inside a git repository."
            )

        # Determine git diff arguments
        if staged_only:
            ref_args = ["--cached"]
            effective_ref = "--cached (staged)"
        elif base_ref:
            ref_args = [base_ref]
            effective_ref = base_ref
        else:
            # Check if HEAD exists
            head_check = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=str(self.target_path),
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
            if head_check.returncode == 0:
                ref_args = ["HEAD"]
                effective_ref = "HEAD"
            else:
                ref_args = ["--cached"]
                effective_ref = "--cached (initial commit)"

        # Run git diff --numstat
        cmd_numstat = ["git", "diff", *ref_args, "--numstat"]
        res_numstat = subprocess.run(
            cmd_numstat,
            cwd=str(self.target_path),
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        if res_numstat.returncode != 0:
            raise RuntimeError(
                f"git diff --numstat failed (exit {res_numstat.returncode}): {res_numstat.stderr.strip()}"
            )

        # Run git diff --name-status
        cmd_name_status = ["git", "diff", *ref_args, "--name-status"]
        res_name_status = subprocess.run(
            cmd_name_status,
            cwd=str(self.target_path),
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        if res_name_status.returncode != 0:
            raise RuntimeError(
                f"git diff --name-status failed (exit {res_name_status.returncode}): {res_name_status.stderr.strip()}"
            )

        # Parse name-status: map file path to status
        status_map: Dict[str, str] = {}
        for line in res_name_status.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                status_code, fpath = parts[0], parts[1]
                # If renamed, fpath has "old -> new" or tab separation
                if "\t" in fpath:
                    fpath = fpath.split("\t")[-1]
                status_map[fpath] = status_code

        # Parse numstat: lines inserted, lines deleted, file path
        insertions = 0
        deletions = 0
        file_stats: List[Dict[str, Any]] = []
        modified_files: List[str] = []

        for line in res_numstat.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            ins_str, del_str, fpath = parts[0], parts[1], parts[2]
            if "\t" in fpath:
                fpath = fpath.split("\t")[-1]

            is_binary = ins_str == "-" and del_str == "-"
            ins = 0 if is_binary else int(ins_str)
            dels = 0 if is_binary else int(del_str)

            insertions += ins
            deletions += dels
            modified_files.append(fpath)

            file_stats.append({
                "path": fpath,
                "status": status_map.get(fpath, "M"),
                "insertions": ins,
                "deletions": dels,
                "binary": is_binary,
            })

        total_lines_changed = insertions + deletions
        diff_exceeds_500_lines = total_lines_changed > 500

        return {
            "base_ref": effective_ref,
            "files_changed_count": len(modified_files),
            "modified_files": modified_files,
            "insertions": insertions,
            "deletions": deletions,
            "total_lines_changed": total_lines_changed,
            "diff_exceeds_500_lines": diff_exceeds_500_lines,
            "is_large_diff": diff_exceeds_500_lines,
            "file_stats": file_stats,
        }

    def collect_manifests(self) -> List[Dict[str, str]]:
        """Discover package, build, and dependency manifests across the repository."""
        manifests: List[Dict[str, str]] = []

        for root, dirs, files in os.walk(self.target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            root_path = Path(root)

            for fname in files:
                if fname in MANIFEST_MAP:
                    rel_path = (root_path / fname).relative_to(self.target_path).as_posix()
                    manifests.append({
                        "name": fname,
                        "path": rel_path,
                        "ecosystem": MANIFEST_MAP[fname],
                    })

        # Sort for deterministic output
        manifests.sort(key=lambda m: m["path"])
        return manifests

    def collect_static_tools(self) -> List[Dict[str, str]]:
        """Detect static analyzers, linters, typecheckers, test runners, and CI tools."""
        tools: List[Dict[str, str]] = []
        found_names: Set[str] = set()

        def add_tool(name: str, category: str, config_file: str) -> None:
            if name not in found_names:
                found_names.add(name)
                tools.append({
                    "name": name,
                    "category": category,
                    "config_file": config_file,
                })

        # 1. Linters & Formatters
        # ESLint
        for pat in [".eslintrc*", "eslint.config.*"]:
            for match in self.target_path.glob(pat):
                if match.is_file():
                    add_tool("eslint", "linter", match.relative_to(self.target_path).as_posix())
                    break

        # Prettier
        for pat in [".prettierrc*", "prettier.config.*"]:
            for match in self.target_path.glob(pat):
                if match.is_file():
                    add_tool("prettier", "formatter", match.relative_to(self.target_path).as_posix())
                    break

        # Ruff
        for fname in ["ruff.toml", ".ruff.toml"]:
            f = self.target_path / fname
            if f.is_file():
                add_tool("ruff", "linter_formatter", fname)
                break
        pyproject = self.target_path / "pyproject.toml"
        if pyproject.is_file() and "ruff" not in found_names:
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.ruff]" in content:
                    add_tool("ruff", "linter_formatter", "pyproject.toml")
            except Exception:
                pass

        # Black
        if pyproject.is_file() and "black" not in found_names:
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.black]" in content:
                    add_tool("black", "formatter", "pyproject.toml")
            except Exception:
                pass

        # Flake8
        if (self.target_path / ".flake8").is_file():
            add_tool("flake8", "linter", ".flake8")

        # Rustfmt & Clippy
        if (self.target_path / "rustfmt.toml").is_file():
            add_tool("rustfmt", "formatter", "rustfmt.toml")
        if (self.target_path / "clippy.toml").is_file():
            add_tool("clippy", "linter", "clippy.toml")

        # Biome
        for fname in ["biome.json", "biome.jsonc"]:
            if (self.target_path / fname).is_file():
                add_tool("biome", "linter_formatter", fname)
                break

        # Golangci-lint
        for pat in [".golangci.*"]:
            for match in self.target_path.glob(pat):
                if match.is_file():
                    add_tool("golangci-lint", "linter", match.relative_to(self.target_path).as_posix())
                    break

        # 2. Typecheckers
        # TypeScript
        if (self.target_path / "tsconfig.json").is_file():
            add_tool("typescript", "typechecker", "tsconfig.json")

        # Mypy
        for fname in ["mypy.ini", ".mypy.ini"]:
            if (self.target_path / fname).is_file():
                add_tool("mypy", "typechecker", fname)
                break
        if pyproject.is_file() and "mypy" not in found_names:
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.mypy]" in content:
                    add_tool("mypy", "typechecker", "pyproject.toml")
            except Exception:
                pass

        # Pyright
        if (self.target_path / "pyrightconfig.json").is_file():
            add_tool("pyright", "typechecker", "pyrightconfig.json")
        elif pyproject.is_file() and "pyright" not in found_names:
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.pyright]" in content:
                    add_tool("pyright", "typechecker", "pyproject.toml")
            except Exception:
                pass

        # 3. Test Runners
        # Vitest
        for pat in ["vitest.config.*"]:
            for match in self.target_path.glob(pat):
                if match.is_file():
                    add_tool("vitest", "test_runner", match.relative_to(self.target_path).as_posix())
                    break

        # Jest
        for pat in ["jest.config.*"]:
            for match in self.target_path.glob(pat):
                if match.is_file():
                    add_tool("jest", "test_runner", match.relative_to(self.target_path).as_posix())
                    break

        # Pytest
        for fname in ["pytest.ini", "conftest.py"]:
            if (self.target_path / fname).is_file():
                add_tool("pytest", "test_runner", fname)
                break
        if pyproject.is_file() and "pytest" not in found_names:
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.pytest]" in content or "[tool.pytest.ini_options]" in content:
                    add_tool("pytest", "test_runner", "pyproject.toml")
            except Exception:
                pass

        # Cargo test
        if (self.target_path / "Cargo.toml").is_file():
            add_tool("cargo-test", "test_runner", "Cargo.toml")

        # Go test
        if (self.target_path / "go.mod").is_file():
            add_tool("go-test", "test_runner", "go.mod")

        # 4. CI/CD & Automation
        gh_workflows = self.target_path / ".github" / "workflows"
        if gh_workflows.is_dir():
            wf_files = list(gh_workflows.glob("*.yml")) + list(gh_workflows.glob("*.yaml"))
            if wf_files:
                add_tool("github-actions", "ci_cd", ".github/workflows")

        if (self.target_path / ".gitlab-ci.yml").is_file():
            add_tool("gitlab-ci", "ci_cd", ".gitlab-ci.yml")

        # Sort for deterministic output
        tools.sort(key=lambda t: (t["category"], t["name"]))
        return tools

    def collect_topology(self) -> Dict[str, Any]:
        """Map repository topology: total files, extension counts, and top directories."""
        extensions: Dict[str, int] = {}
        total_files = 0
        top_directories: List[str] = []

        # Find top directories
        for entry in self.target_path.iterdir():
            if entry.is_dir() and entry.name not in IGNORE_DIRS and not entry.name.startswith("."):
                top_directories.append(entry.name)

        top_directories.sort()

        # Walk files
        for root, dirs, files in os.walk(self.target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in files:
                total_files += 1
                suffix = Path(fname).suffix.lower()
                ext = suffix if suffix else "(none)"
                extensions[ext] = extensions.get(ext, 0) + 1

        # Sort extensions by count descending, then name
        sorted_exts = dict(sorted(extensions.items(), key=lambda item: (-item[1], item[0])))

        return {
            "total_files": total_files,
            "extensions": sorted_exts,
            "top_directories": top_directories,
        }

    def collect_all(
        self,
        include_diff: bool = True,
        include_repo: bool = True,
        base_ref: Optional[str] = None,
        staged_only: bool = False,
    ) -> Dict[str, Any]:
        """Synthesize all empirical evidence into a single structured report."""
        now_iso = datetime.now(timezone.utc).isoformat()
        report: Dict[str, Any] = {
            "collector_version": "1.0.0",
            "timestamp": now_iso,
            "target_path": str(self.target_path),
            "is_git_repo": self.is_git_repo(),
            "uninspected": UNINSPECTED_SURFACE,
        }

        diff_data = None
        if include_diff:
            if self.is_git_repo():
                diff_data = self.collect_diff(base_ref=base_ref, staged_only=staged_only)
                report["diff"] = diff_data
                # Expose root convenience fields
                report["total_lines_changed"] = diff_data["total_lines_changed"]
                report["diff_exceeds_500_lines"] = diff_data["diff_exceeds_500_lines"]
                report["is_large_diff"] = diff_data["is_large_diff"]
                report["modified_files"] = diff_data["modified_files"]
            else:
                report["diff"] = None
                report["total_lines_changed"] = 0
                report["diff_exceeds_500_lines"] = False
                report["is_large_diff"] = False
                report["modified_files"] = []

        if include_repo:
            manifests = self.collect_manifests()
            tools = self.collect_static_tools()
            topology = self.collect_topology()

            report["repo"] = {
                "manifests": manifests,
                "tools": tools,
                "topology": topology,
            }
            # Expose root convenience fields
            report["manifests"] = manifests
            report["tools"] = tools
            report["detected_linters"] = [t["name"] for t in tools if "linter" in t["category"]]
            report["detected_test_runners"] = [t["name"] for t in tools if t["category"] == "test_runner"]

        return report


def collect_evidence(
    target_path: Path | str = ".",
    include_diff: bool = True,
    include_repo: bool = True,
    base_ref: Optional[str] = None,
    staged_only: bool = False,
) -> Dict[str, Any]:
    """Helper entrypoint for programmatic evidence collection."""
    collector = ReviewCollector(target_path=target_path)
    return collector.collect_all(
        include_diff=include_diff,
        include_repo=include_repo,
        base_ref=base_ref,
        staged_only=staged_only,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build accurate command line interface parser (S6 compliant)."""
    parser = argparse.ArgumentParser(
        description="Review Collector: Collects mechanical facts on git diffs, manifests, and static tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help="Inspect git diff (lines changed, modified files, >500 lines threshold).",
    )
    parser.add_argument(
        "--repo",
        action="store_true",
        default=False,
        help="Inspect repository-wide topology, package manifests, and static tools.",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Target repository or workspace directory path (default: current working directory).",
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help="Git base reference for diff comparison (e.g. HEAD~1, origin/main).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        default=False,
        help="Inspect only staged git changes (--cached).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output file path to write evidence JSON (e.g. evidence.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print structured evidence JSON directly to standard output.",
    )
    return parser


def main() -> int:
    """CLI execution entrypoint. Returns exit code (0 on success, non-zero on failure)."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # Determine mode: if neither --diff nor --repo is explicitly specified, collect both
    do_diff = args.diff
    do_repo = args.repo
    if not do_diff and not do_repo:
        do_diff = True
        do_repo = True

    try:
        collector = ReviewCollector(target_path=args.path)

        # If --diff was explicitly requested but not a git repo, fail closed (S3)
        if args.diff and not collector.is_git_repo():
            sys.stderr.write(f"Error: Target path '{args.path}' is not inside a git repository.\n")
            return 1

        evidence = collector.collect_all(
            include_diff=do_diff,
            include_repo=do_repo,
            base_ref=args.base,
            staged_only=args.staged,
        )

        formatted_json = json.dumps(evidence, indent=2, ensure_ascii=False)

        # Write to file if --out is specified
        if args.out:
            out_path = Path(args.out).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(formatted_json + "\n", encoding="utf-8")
            if not args.json:
                sys.stdout.write(f"✓ Evidence written to {out_path}\n")

        # Print to stdout if --json is specified, or if neither --out nor --json was given
        if args.json or not args.out:
            sys.stdout.write(formatted_json + "\n")

        return 0

    except Exception as exc:
        sys.stderr.write(f"Error during evidence collection: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
