#!/usr/bin/env python3
# Copyright 2026 Google LLC
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
verify_okf.py - Deterministic Static Verifier for Open Knowledge Format (OKF) Bundles

Validates:
1. File existence on disk.
2. YAML Frontmatter presence and syntax.
3. Required OKF keys ('type', 'title', 'description').
4. Meta-document support for 'index.md' (valid title, table columns; no 'type' requirement).
5. Resource grounding check (referenced 'resource:' files must exist on disk).
6. Recursive directory & bidirectional bundle audit (--all, --dir):
   - Every concept document must be linked in index.md (no orphaned concepts).
   - Every link in index.md must point to an existing file on disk (no dangling links).
7. OKF v0.2 metadata validation ('sources', 'verified', 'stale_after', 'status', 'resource_hash').
8. Anti-placeholder defense (TBD, TODO, FIXME, as an AI).
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path

# UTF-8 Console encoding safety on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    yaml = None


def find_workspace_root(start_path: Path) -> Path:
    """Finds the workspace root by looking for .git or AGENTS.md."""
    p = start_path.resolve()
    if p.is_file():
        p = p.parent
    for parent in [p] + list(p.parents):
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            return parent
    return p


def parse_yaml_frontmatter(yaml_block: str) -> dict:
    """Zero-dependency parser for OKF YAML frontmatter with PyYAML fallback."""
    if yaml is not None:
        try:
            res = yaml.safe_load(yaml_block)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    meta = {}
    lines = yaml_block.splitlines()
    i = 0
    current_key = None

    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()
        i += 1
        if not line or line.startswith("#"):
            continue

        # Check for block list item (e.g. "  - item")
        if current_key and (raw_line.startswith("  -") or raw_line.startswith("\t-") or line.startswith("- ")):
            val = line.lstrip("- ").strip().strip('"').strip("'")
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(val)
            continue

        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            current_key = key

            if not val:
                meta[key] = []
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                if not inner:
                    meta[key] = []
                else:
                    items = [item.strip().strip('"').strip("'") for item in re.split(r",\s*", inner) if item.strip()]
                    meta[key] = items
            else:
                meta[key] = val.strip('"').strip("'")
        else:
            current_key = None

    return meta


def resolve_resource_path(resource_str: str, file_path: Path, workspace_root: Path) -> Path | None:
    """Resolves resource paths handling relative paths, file:/// URIs, and cross-platform paths."""
    clean = str(resource_str).strip().strip('"').strip("'")
    if clean.startswith("file://"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        clean_path = url2pathname(urlparse(clean).path)
    else:
        clean_path = clean

    # 1. Direct path check
    p = Path(clean_path)
    if p.is_absolute() and p.exists():
        return p.resolve()

    # 2. Check relative to workspace_root
    p_ws = (workspace_root / clean_path).resolve()
    if p_ws.exists():
        return p_ws

    # 3. Check relative to file_path.parent
    p_rel = (file_path.parent / clean_path).resolve()
    if p_rel.exists():
        return p_rel

    # 4. Check if URI contains workspace_root.name
    norm = clean_path.replace("\\", "/")
    ws_name = workspace_root.name
    if ws_name in norm:
        parts = norm.split(ws_name + "/", 1)
        if len(parts) > 1:
            candidate = (workspace_root / parts[1]).resolve()
            if candidate.exists():
                return candidate

    return None


def resolve_concept_link(target: str, bundle_dir: Path, workspace_root: Path) -> Path | None:
    """Resolves markdown link targets from index.md to canonical files on disk."""
    clean = target.strip().strip("<>").strip()
    if clean.startswith("file://"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        clean_path = url2pathname(urlparse(clean).path)
    else:
        clean_path = clean

    # Strip URL anchor/fragment if present
    clean_path = clean_path.split("#")[0].strip()
    if not clean_path:
        return None

    # Direct absolute path
    p = Path(clean_path)
    if p.is_absolute() and p.exists():
        return p.resolve()

    # Relative to bundle_dir
    p_bundle = (bundle_dir / clean_path).resolve()
    if p_bundle.exists():
        return p_bundle

    # Relative to workspace_root
    p_ws = (workspace_root / clean_path).resolve()
    if p_ws.exists():
        return p_ws

    # Check if target contains bundle_dir name or workspace_root name
    norm = clean_path.replace("\\", "/")
    b_name = bundle_dir.name
    if b_name in norm:
        parts = norm.split(b_name + "/", 1)
        if len(parts) > 1:
            candidate = (bundle_dir / parts[1]).resolve()
            if candidate.exists():
                return candidate

    ws_name = workspace_root.name
    if ws_name in norm:
        parts = norm.split(ws_name + "/", 1)
        if len(parts) > 1:
            candidate = (workspace_root / parts[1]).resolve()
            if candidate.exists():
                return candidate

    return None


def validate_okf_v02_metadata(meta: dict) -> list[str]:
    """Validates optional OKF v0.2 metadata fields when present."""
    errors = []

    if "resource_hash" in meta and meta["resource_hash"]:
        val = str(meta["resource_hash"]).strip()
        if not re.match(r"^sha256:[a-fA-F0-9]{64}$", val):
            errors.append(f"Invalid 'resource_hash' format: '{val}'. Expected 'sha256:<64-char hex>'")

    if "sources" in meta and meta["sources"] is not None:
        val = meta["sources"]
        if not isinstance(val, list) or any(not isinstance(s, str) for s in val):
            errors.append("Field 'sources' must be a list of strings")

    if "verified" in meta and meta["verified"] is not None:
        val = str(meta["verified"]).strip()
        if not val:
            errors.append("Field 'verified' must be a valid non-empty string or timestamp")

    if "stale_after" in meta and meta["stale_after"] is not None:
        val = str(meta["stale_after"]).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            errors.append(f"Invalid 'stale_after' format: '{val}'. Expected 'YYYY-MM-DD'")

    if "status" in meta and meta["status"] is not None:
        val = str(meta["status"]).strip().lower()
        if val not in ("draft", "active", "deprecated"):
            errors.append(f"Invalid 'status': '{meta['status']}'. Expected 'draft', 'active', or 'deprecated'")

    if "tags" in meta and meta["tags"] is not None:
        val = meta["tags"]
        if not isinstance(val, list) or any(not isinstance(t, str) for t in val):
            errors.append("Field 'tags' must be a list of strings")

    return errors


def verify_index_manifest(path: Path, content: str, meta: dict) -> list[str]:
    """Verifies index.md meta-manifest structure."""
    errors = []

    # 1. Title is required in frontmatter
    title = meta.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        errors.append("Index manifest missing required 'title' in frontmatter")

    # 2. Markdown table check
    table_pattern = re.compile(r"^\s*\|(.+)\|\s*\n\s*\|(\s*:?-+:?\s*\|)+\s*$", re.MULTILINE)
    match = table_pattern.search(content)
    if not match:
        errors.append("Index manifest missing valid Markdown table with column headers")
    else:
        header_line = match.group(1)
        headers = [h.strip().lower() for h in header_line.split("|")]
        has_concept = any("concept" in h for h in headers)
        has_path = any("path" in h or "file" in h or "target" in h or "link" in h for h in headers)
        if not (has_concept and has_path):
            errors.append(f"Index manifest Markdown table missing required columns (expected 'Concept ID' and 'File Path', found: {[h.strip() for h in header_line.split('|')]})")

    return errors


def verify_concept_file(file_path, check_resources=False, workspace_root=None):
    """Verifies a single concept document or index manifest file."""
    errors = []
    path = Path(file_path)

    if not path.exists():
        return [f"Concept file missing: {file_path}"]
    if not path.is_file():
        return [f"Target path is not a regular file: {file_path}"]

    if workspace_root is None:
        workspace_root = find_workspace_root(path)

    content = path.read_text(encoding="utf-8")

    # 1. Check YAML frontmatter opening
    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter opening '---'")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("Malformed YAML frontmatter block (missing closing '---')")
        return errors

    yaml_block = parts[1]
    meta = parse_yaml_frontmatter(yaml_block)

    if not isinstance(meta, dict) or not meta:
        errors.append("Frontmatter is empty or not a valid YAML dictionary")
        return errors

    # 2. Check if file is index meta-manifest
    is_index = (path.name.lower() == "index.md") or path.name.lower().endswith("index.md")

    if is_index:
        errors.extend(verify_index_manifest(path, content, meta))
    else:
        # Standard concept document schema (R1.1)
        required_keys = ["type", "title", "description"]
        for key in required_keys:
            val = meta.get(key)
            if val is None or not isinstance(val, str) or not val.strip():
                errors.append(f"Missing required OKF frontmatter key: '{key}'")

        # Resource grounding validation (R1.3)
        if check_resources and "resource" in meta and meta["resource"]:
            resolved = resolve_resource_path(str(meta["resource"]), path, workspace_root)
            if resolved is None or not resolved.exists():
                errors.append(f"Referenced resource does not exist on disk: '{meta['resource']}'")

    # 3. OKF v0.2 metadata validation (R1.5)
    errors.extend(validate_okf_v02_metadata(meta))

    # 4. Check for prohibited placeholder markers (R1.6)
    prohibited = ["TBD", "TODO", "FIXME", "as an AI"]
    for term in prohibited:
        if re.search(rf"\b{re.escape(term)}\b", content, re.IGNORECASE):
            errors.append(f"Contains prohibited placeholder: '{term}'")

    return errors


def verify_knowledge_bundle(bundle_dir: Path, check_resources: bool = False, workspace_root: Path = None) -> list[str]:
    """Performs recursive schema verification and bidirectional audit across an OKF bundle."""
    errors = []
    bundle_dir = bundle_dir.resolve()
    if workspace_root is None:
        workspace_root = find_workspace_root(bundle_dir)

    index_path = bundle_dir / "index.md"
    if not index_path.exists():
        return [f"Index manifest missing in bundle: {index_path}"]

    # 1. Verify index.md
    index_errors = verify_concept_file(index_path, check_resources=check_resources, workspace_root=workspace_root)
    for err in index_errors:
        errors.append(f"[index.md] {err}")

    # 2. Collect all concept files (excluding index.md, log.md, ADRs, and nested bundles)
    concept_files = []
    for p in bundle_dir.rglob("*.md"):
        rel = p.relative_to(bundle_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p.name in ("index.md", "log.md"):
            continue
        if "ADRs" in rel.parts or "adr" in rel.parts:
            continue

        # Exclude files inside nested bundles that have their own index.md
        parent = p.parent
        is_nested = False
        while parent != bundle_dir:
            if (parent / "index.md").exists():
                is_nested = True
                break
            parent = parent.parent
        if is_nested:
            continue

        concept_files.append(p.resolve())

    # 3. Verify each concept file against schema
    for c_file in sorted(concept_files):
        rel_display = c_file.relative_to(bundle_dir).as_posix()
        c_errors = verify_concept_file(c_file, check_resources=check_resources, workspace_root=workspace_root)
        for err in c_errors:
            errors.append(f"[{rel_display}] {err}")

    # 4. Bidirectional audit (R1.4 / Fix Defect 5)
    index_content = index_path.read_text(encoding="utf-8")
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", index_content)

    linked_paths = set()
    for text, target in links:
        target_str = target.strip()
        if target_str.startswith("#") or target_str.startswith("http://") or target_str.startswith("https://"):
            continue

        resolved = resolve_concept_link(target_str, bundle_dir, workspace_root)
        if resolved is None or not resolved.exists():
            errors.append(f"Dangling link in index.md points to non-existent file: '{target_str}'")
        else:
            linked_paths.add(resolved.resolve())

    # Assert no orphaned concept documents
    for c_file in sorted(concept_files):
        if c_file not in linked_paths:
            rel_display = c_file.relative_to(bundle_dir).as_posix()
            errors.append(f"Orphaned concept document not registered in index.md: '{rel_display}'")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Static Verifier for Open Knowledge Format (OKF) Bundles and Concepts"
    )
    parser.add_argument("file_path", nargs="?", default=None, help="Path to a single concept document or index.md")
    parser.add_argument("--all", action="store_true", help="Recursively scan and audit an entire OKF knowledge bundle")
    parser.add_argument("--dir", default=None, help="Directory path to audit (default: .gemini/knowledge)")
    parser.add_argument("--check-resources", action="store_true", default=None, help="Enforce disk existence for referenced 'resource:' files")
    parser.add_argument("--no-check-resources", dest="check_resources", action="store_false", help="Disable disk existence check for resources")
    parser.add_argument("--workspace-root", default=None, help="Root directory of workspace (auto-detected if omitted)")

    args = parser.parse_args()

    ws_root = Path(args.workspace_root).resolve() if args.workspace_root else None

    if args.all or (args.dir is not None and not args.file_path):
        target_dir = args.dir or ".gemini/knowledge"
        bundle_dir = Path(target_dir).resolve()
        if not bundle_dir.exists() or not bundle_dir.is_dir():
            print(json.dumps({"status": "FAIL", "errors": [f"Directory not found: {target_dir}"]}, indent=2))
            sys.exit(1)

        # Default check_resources is False for --all unless explicitly requested
        check_res = True if args.check_resources is True else False
        errors = verify_knowledge_bundle(bundle_dir, check_resources=check_res, workspace_root=ws_root)

        if errors:
            print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
            sys.exit(1)

        print(json.dumps({"status": "PASS"}, indent=2))
        sys.exit(0)

    elif args.file_path:
        target_path = Path(args.file_path).resolve()
        if not target_path.exists():
            print(json.dumps({"status": "FAIL", "errors": [f"Concept file missing: {args.file_path}"]}, indent=2))
            sys.exit(1)

        if target_path.is_dir():
            check_res = True if args.check_resources is True else False
            errors = verify_knowledge_bundle(target_path, check_resources=check_res, workspace_root=ws_root)
            if errors:
                print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
                sys.exit(1)
            print(json.dumps({"status": "PASS"}, indent=2))
            sys.exit(0)

        # Default check_resources is True for single-file unless --no-check-resources passed
        check_res = False if args.check_resources is False else True
        errors = verify_concept_file(target_path, check_resources=check_res, workspace_root=ws_root)

        if errors:
            print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
            sys.exit(1)

        print(json.dumps({"status": "PASS"}, indent=2))
        sys.exit(0)

    else:
        print(json.dumps({"status": "FAIL", "errors": ["Usage: verify_okf.py <CONCEPT_FILE_PATH> or verify_okf.py --all [--dir <PATH>]"]}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
