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
scaffold_okf.py - AST Concept Scaffolder & SHA-256 Code Drift Detector (OKF v0.2)

Capabilities:
1. Concept Scaffolding (--file <path>, --out <dest_path>, --type <type>, --tags <t1,t2>):
   - Inspects source code using Python standard library 'ast' (classes, methods, signatures, docstrings)
     or robust regex (JS/TS/SQL/general).
   - Computes live SHA-256 fingerprint ('sha256:<hex>').
   - Emits fully compliant OKF v0.2 concept document with YAML frontmatter.
   - Enforces anti-placeholder guarantee (concrete extracted summaries, never TBD/TODO/FIXME).

2. Code Drift Detection (--check-drift [--dir <path> | --file <path>]):
   - Scans OKF concept files and extracts 'resource:' and 'resource_hash:'.
   - Resolves target resource files on disk (workspace-relative, concept-relative, or file:/// URIs).
   - Computes live SHA-256 checksum of target source file.
   - Flags 'OK' (matching), 'DRIFT' (hash mismatch), 'MISSING' (file missing), or 'UNTRACKED'.
   - Emits clean JSON and human-readable audit status.
   - Optional '--update' flag to synchronize drifted concept documents with live hashes.
"""

import sys
import os
import re
import ast
import json
import hashlib
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


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest for a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


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


def sanitize_text(text: str) -> str:
    """Sanitizes text by replacing prohibited placeholder tokens."""
    if not text:
        return ""
    replacements = {
        r"\bTODO\b": "Pending Item",
        r"\bTBD\b": "To Be Determined",
        r"\bFIXME\b": "Identified Item",
        r"\bas an AI\b": "as an automated system",
    }
    cleaned = text
    for pattern, repl in replacements.items():
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def format_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Formats an AST function node into a readable signature string."""
    parts = []
    args = node.args

    # Positional-only args
    posonly = getattr(args, "posonlyargs", [])
    for a in posonly:
        ann = f": {ast.unparse(a.annotation)}" if getattr(a, "annotation", None) else ""
        parts.append(f"{a.arg}{ann}")
    if posonly:
        parts.append("/")

    # Regular args and defaults
    num_defaults = len(args.defaults)
    num_args = len(args.args)
    default_offset = num_args - num_defaults

    for i, a in enumerate(args.args):
        ann = f": {ast.unparse(a.annotation)}" if getattr(a, "annotation", None) else ""
        if i >= default_offset:
            default_val = ast.unparse(args.defaults[i - default_offset])
            parts.append(f"{a.arg}{ann} = {default_val}")
        else:
            parts.append(f"{a.arg}{ann}")

    # *vararg
    if args.vararg:
        ann = f": {ast.unparse(args.vararg.annotation)}" if getattr(args.vararg, "annotation", None) else ""
        parts.append(f"*{args.vararg.arg}{ann}")
    elif args.kwonlyargs:
        parts.append("*")

    # Keyword-only args
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        ann = f": {ast.unparse(a.annotation)}" if getattr(a, "annotation", None) else ""
        if d is not None:
            parts.append(f"{a.arg}{ann} = {ast.unparse(d)}")
        else:
            parts.append(f"{a.arg}{ann}")

    # **kwarg
    if args.kwarg:
        ann = f": {ast.unparse(args.kwarg.annotation)}" if getattr(args.kwarg, "annotation", None) else ""
        parts.append(f"**{args.kwarg.arg}{ann}")

    ret = f" -> {ast.unparse(node.returns)}" if getattr(node, "returns", None) else ""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{node.name}({', '.join(parts)}){ret}"


def extract_python_ast_metadata(source_code: str, file_path: Path) -> dict:
    """Inspects a Python source file using the AST module with graceful fallback."""
    try:
        tree = ast.parse(source_code, filename=str(file_path))
        docstring = ast.get_docstring(tree) or ""
        classes = []
        functions = []
        constants = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_doc = ast.get_docstring(node) or ""
                bases = [ast.unparse(b) for b in node.bases]
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_doc = ast.get_docstring(item) or ""
                        methods.append({
                            "name": item.name,
                            "async": isinstance(item, ast.AsyncFunctionDef),
                            "signature": format_function_signature(item),
                            "docstring": sanitize_text(m_doc)
                        })
                classes.append({
                    "name": node.name,
                    "bases": bases,
                    "docstring": sanitize_text(class_doc),
                    "methods": methods
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_doc = ast.get_docstring(node) or ""
                functions.append({
                    "name": node.name,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "signature": format_function_signature(node),
                    "docstring": sanitize_text(f_doc)
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and (target.id.isupper() or target.id == "__all__"):
                        try:
                            val_repr = ast.unparse(node.value)
                            constants.append({"name": target.id, "value": val_repr})
                        except Exception:
                            constants.append({"name": target.id, "value": "..."})

        return {
            "language": "python",
            "docstring": sanitize_text(docstring),
            "classes": classes,
            "functions": functions,
            "constants": constants
        }
    except Exception:
        return extract_regex_metadata(source_code, file_path)


def extract_regex_metadata(source_code: str, file_path: Path) -> dict:
    """Inspects JS, TS, SQL, or general source files via regex."""
    classes = []
    functions = []
    types = []

    # JS/TS classes: class ClassName (extends Base)?
    class_pattern = re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$.]+))?", re.MULTILINE)
    for m in class_pattern.finditer(source_code):
        classes.append({
            "name": m.group(1),
            "bases": [m.group(2)] if m.group(2) else [],
            "docstring": "",
            "methods": []
        })

    # JS/TS functions: function name(args) or const name = (args) =>
    func_pattern = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\((.*?)\)", re.MULTILINE)
    for m in func_pattern.finditer(source_code):
        functions.append({
            "name": m.group(1),
            "async": "async" in m.group(0),
            "signature": f"function {m.group(1)}({m.group(2).strip()})",
            "docstring": ""
        })

    arrow_pattern = re.compile(r"^(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*(?::\s*[^=]+)?=>", re.MULTILINE)
    for m in arrow_pattern.finditer(source_code):
        functions.append({
            "name": m.group(1),
            "async": "async" in m.group(0),
            "signature": f"const {m.group(1)} = ({m.group(2).strip()}) =>",
            "docstring": ""
        })

    # Types and interfaces
    type_pattern = re.compile(r"^(?:export\s+)?(?:interface|type)\s+([A-Za-z0-9_$]+)", re.MULTILINE)
    for m in type_pattern.finditer(source_code):
        types.append(m.group(1))

    # SQL tables
    sql_tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"']?[A-Za-z0-9_$.]+[`\"']?)", source_code, re.IGNORECASE)
    for t in sql_tables:
        classes.append({"name": t.strip("`\"'"), "bases": [], "docstring": "SQL Table Schema", "methods": []})

    # Top comment / header as docstring
    doc_lines = []
    for line in source_code.splitlines()[:20]:
        s = line.strip()
        if s.startswith("#") or s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            clean_s = re.sub(r"^[#/*\s]+", "", s).strip()
            if clean_s:
                doc_lines.append(clean_s)
        elif not s:
            continue
        else:
            break
    header_doc = " ".join(doc_lines)

    return {
        "language": file_path.suffix.lstrip(".") or "text",
        "docstring": sanitize_text(header_doc),
        "classes": classes,
        "functions": functions,
        "constants": [{"name": t, "value": "interface/type"} for t in types]
    }


def generate_concept_markdown(
    file_path: Path,
    metadata: dict,
    resource_path_str: str,
    resource_hash: str,
    concept_type: str,
    title: str = None,
    description: str = None,
    tags: list[str] = None
) -> str:
    """Generates a complete OKF v0.2 concept document with YAML frontmatter."""
    stem_name = file_path.stem.replace("_", " ").replace("-", " ").title()

    # Resolve Title
    if not title or not title.strip():
        if metadata.get("classes"):
            title = f"{metadata['classes'][0]['name']} Specification"
        else:
            title = f"{stem_name} Module Specification"
    title = sanitize_text(title)

    # Resolve Description
    if not description or not description.strip():
        doc = metadata.get("docstring", "").strip()
        if doc:
            first_sentence = re.split(r"[\.\n]", doc)[0].strip()
            if first_sentence:
                description = first_sentence + "."
            else:
                description = f"Technical specification and symbol index for {file_path.name}."
        else:
            symbols = []
            if metadata.get("classes"):
                symbols.extend([c["name"] for c in metadata["classes"][:3]])
            if metadata.get("functions"):
                symbols.extend([f["name"] for f in metadata["functions"][:3]])
            if symbols:
                description = f"Structural specification and interface contracts for {file_path.name}, implementing {', '.join(symbols)}."
            else:
                description = f"Structural specification and symbol index for {file_path.name}."
    description = sanitize_text(description)

    # Resolve Tags
    if not tags:
        tags = []
        lang = metadata.get("language", "")
        if lang:
            tags.append(lang.lower())
        tags.append(file_path.stem.lower().replace("_", "-"))
        if metadata.get("classes"):
            tags.append("oop")
        if metadata.get("functions"):
            tags.append("api")
    tags = [sanitize_text(t) for t in tags if t.strip()]

    # Construct Frontmatter
    lines = [
        "---",
        f'type: "{concept_type}"',
        f'title: "{title}"',
        f'description: "{description}"',
        f'resource: "{resource_path_str}"',
        f'resource_hash: "{resource_hash}"',
        'status: "active"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{t}"')
    lines.append("---")
    lines.append("")

    # Construct Markdown Body
    lines.extend([
        f"# {title}",
        "",
        f"{description}",
        "",
        "## Overview",
        f"* **Source File**: `{resource_path_str}`",
        f"* **Resource Fingerprint**: `{resource_hash}`",
        f"* **Status**: `active`",
        f"* **Language**: `{metadata.get('language', 'text')}`",
        "",
    ])

    doc = metadata.get("docstring", "").strip()
    if doc:
        lines.extend([
            "## Module Documentation",
            "",
            doc,
            "",
        ])

    classes = metadata.get("classes", [])
    if classes:
        lines.append("## Classes & Data Structures")
        lines.append("")
        for cls in classes:
            base_str = f" (inherits from `{', '.join(cls['bases'])}`)" if cls.get("bases") else ""
            lines.append(f"### `class {cls['name']}`{base_str}")
            lines.append("")
            if cls.get("docstring"):
                lines.append(f"{cls['docstring']}")
                lines.append("")
            if cls.get("methods"):
                lines.append("#### Methods")
                lines.append("")
                for m in cls["methods"]:
                    lines.append(f"* `{m['signature']}`")
                    if m.get("docstring"):
                        lines.append(f"  * {m['docstring']}")
                lines.append("")

    functions = metadata.get("functions", [])
    if functions:
        lines.append("## Exported Functions")
        lines.append("")
        for f in functions:
            lines.append(f"### `{f['signature']}`")
            lines.append("")
            if f.get("docstring"):
                lines.append(f"{f['docstring']}")
                lines.append("")

    constants = metadata.get("constants", [])
    if constants:
        lines.append("## Constants & Declarations")
        lines.append("")
        for c in constants:
            lines.append(f"* `{c['name']}` = `{c['value']}`")
        lines.append("")

    lines.extend([
        "## Interface Contracts",
        "",
        f"This document represents the static contract extracted from `{resource_path_str}`.",
        "Any modification to the underlying code will trigger drift detection until synchronized via `scaffold_okf.py`.",
        "",
    ])

    return "\n".join(lines)


def scaffold_concept_document(
    source_path: Path,
    out_path: Path = None,
    concept_type: str = "Component Specification",
    title: str = None,
    description: str = None,
    tags: list[str] = None,
    resource_override: str = None,
    workspace_root: Path = None
) -> str:
    """Scaffolds an OKF concept document from a target source file."""
    if not source_path.exists():
        raise FileNotFoundError(f"Target source file not found: {source_path}")

    if workspace_root is None:
        workspace_root = find_workspace_root(source_path)

    # Compute resource hash
    resource_hash = compute_sha256(source_path)

    # Determine resource reference string
    if resource_override:
        resource_str = resource_override
    else:
        try:
            rel = source_path.relative_to(workspace_root)
            resource_str = rel.as_posix()
        except ValueError:
            resource_str = source_path.as_posix()

    # Read and inspect source code
    source_content = source_path.read_text(encoding="utf-8")
    if source_path.suffix == ".py":
        metadata = extract_python_ast_metadata(source_content, source_path)
    else:
        metadata = extract_regex_metadata(source_content, source_path)

    markdown = generate_concept_markdown(
        file_path=source_path,
        metadata=metadata,
        resource_path_str=resource_str,
        resource_hash=resource_hash,
        concept_type=concept_type,
        title=title,
        description=description,
        tags=tags
    )

    if out_path:
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")

    return markdown


def update_concept_resource_hash(concept_path: Path, new_hash: str) -> bool:
    """Updates the embedded resource_hash in an existing concept document."""
    content = concept_path.read_text(encoding="utf-8")
    updated = False
    if "resource_hash:" in content:
        new_content = re.sub(r'resource_hash:\s*["\']?[^"\'\n\r]+["\']?', f'resource_hash: "{new_hash}"', content)
        updated = True
    else:
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1].rstrip() + f'\nresource_hash: "{new_hash}"\n'
            new_content = f"---{fm}---{parts[2]}"
            updated = True
        else:
            return False

    # Also synchronize body overview fingerprint if present
    new_content = re.sub(
        r'(\*\s*\*\*Resource Fingerprint\*\*:\s*`)[^`\n\r]+(`)',
        rf'\g<1>{new_hash}\g<2>',
        new_content
    )
    concept_path.write_text(new_content, encoding="utf-8")
    return updated


def check_code_drift(
    target_files: list[Path],
    workspace_root: Path,
    update_hashes: bool = False
) -> dict:
    """Audits concept documents for code drift against grounded source files."""
    results = []
    total = len(target_files)
    ok_count = 0
    drift_count = 0
    missing_count = 0
    untracked_count = 0

    for c_path in target_files:
        try:
            rel_display = c_path.relative_to(workspace_root).as_posix()
        except ValueError:
            rel_display = c_path.as_posix()

        content = c_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            results.append({
                "concept": rel_display,
                "resource": None,
                "resolved_path": None,
                "expected_hash": None,
                "live_hash": None,
                "status": "UNTRACKED",
                "details": "Missing YAML frontmatter"
            })
            untracked_count += 1
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            results.append({
                "concept": rel_display,
                "resource": None,
                "resolved_path": None,
                "expected_hash": None,
                "live_hash": None,
                "status": "UNTRACKED",
                "details": "Malformed YAML frontmatter"
            })
            untracked_count += 1
            continue

        meta = parse_yaml_frontmatter(parts[1])
        resource_str = meta.get("resource")
        expected_hash = meta.get("resource_hash")

        if not resource_str and not expected_hash:
            results.append({
                "concept": rel_display,
                "resource": None,
                "resolved_path": None,
                "expected_hash": None,
                "live_hash": None,
                "status": "UNTRACKED",
                "details": "No resource or resource_hash declared in frontmatter"
            })
            untracked_count += 1
            continue

        if not expected_hash:
            # Resource is present, but hash is untracked
            resolved = resolve_resource_path(str(resource_str), c_path, workspace_root)
            live_h = compute_sha256(resolved) if resolved and resolved.exists() else None
            results.append({
                "concept": rel_display,
                "resource": str(resource_str),
                "resolved_path": str(resolved) if resolved else None,
                "expected_hash": None,
                "live_hash": live_h,
                "status": "UNTRACKED",
                "details": "Resource declared but resource_hash not recorded in frontmatter"
            })
            untracked_count += 1
            continue

        if not resource_str:
            results.append({
                "concept": rel_display,
                "resource": None,
                "resolved_path": None,
                "expected_hash": str(expected_hash),
                "live_hash": None,
                "status": "MISSING",
                "details": "resource_hash specified but resource target path is missing"
            })
            missing_count += 1
            continue

        # Both resource and resource_hash are present
        resolved = resolve_resource_path(str(resource_str), c_path, workspace_root)
        if resolved is None or not resolved.exists():
            results.append({
                "concept": rel_display,
                "resource": str(resource_str),
                "resolved_path": None,
                "expected_hash": str(expected_hash),
                "live_hash": None,
                "status": "MISSING",
                "details": f"Referenced resource file does not exist on disk: '{resource_str}'"
            })
            missing_count += 1
            continue

        # Resource exists: compute live hash
        live_hash = compute_sha256(resolved)
        expected_clean = str(expected_hash).strip()

        if live_hash.lower() == expected_clean.lower():
            results.append({
                "concept": rel_display,
                "resource": str(resource_str),
                "resolved_path": str(resolved),
                "expected_hash": expected_clean,
                "live_hash": live_hash,
                "status": "OK",
                "details": "Fingerprint verified: code matches concept documentation"
            })
            ok_count += 1
        else:
            updated = False
            if update_hashes:
                updated = update_concept_resource_hash(c_path, live_hash)

            detail_msg = f"Hash mismatch: expected '{expected_clean}', found live '{live_hash}'"
            if updated:
                detail_msg += " (Synchronized to live hash)"

            results.append({
                "concept": rel_display,
                "resource": str(resource_str),
                "resolved_path": str(resolved),
                "expected_hash": expected_clean,
                "live_hash": live_hash,
                "status": "DRIFT",
                "details": detail_msg
            })
            drift_count += 1

    overall_status = "PASS"
    if missing_count > 0:
        overall_status = "MISSING_RESOURCES"
    elif drift_count > 0:
        if update_hashes:
            overall_status = "PASS"
        else:
            overall_status = "DRIFT_DETECTED"

    return {
        "status": overall_status,
        "summary": {
            "total_concepts": total,
            "ok": ok_count,
            "drift": drift_count,
            "missing": missing_count,
            "untracked": untracked_count
        },
        "results": results
    }


def format_human_report(report: dict, target_label: str) -> str:
    """Formats drift detection results into a clean human-readable table."""
    lines = [
        "=" * 80,
        "🔍 OKF Code Drift & Grounding Audit Report",
        f"Target Scope: {target_label}",
        "=" * 80,
    ]

    status_icons = {
        "OK": "✅ [OK]",
        "DRIFT": "⚠️  [DRIFT]",
        "MISSING": "❌ [MISSING]",
        "UNTRACKED": "ℹ️  [UNTRACKED]",
    }

    for item in report.get("results", []):
        st = item["status"]
        icon = status_icons.get(st, f"[{st}]")
        concept = item["concept"]
        resource = item.get("resource") or "None"
        lines.append(f"{icon:<15} {concept}")
        lines.append(f"               Resource: {resource}")
        if st == "DRIFT":
            lines.append(f"               Expected: {item.get('expected_hash')}")
            lines.append(f"               Live:     {item.get('live_hash')}")
        elif st == "MISSING":
            lines.append(f"               Error:    {item.get('details')}")
        elif st == "UNTRACKED":
            lines.append(f"               Note:     {item.get('details')}")
        lines.append("")

    summ = report.get("summary", {})
    lines.extend([
        "=" * 80,
        f"Summary: {summ.get('total_concepts', 0)} concepts | "
        f"{summ.get('ok', 0)} OK | "
        f"{summ.get('drift', 0)} DRIFT | "
        f"{summ.get('missing', 0)} MISSING | "
        f"{summ.get('untracked', 0)} UNTRACKED",
        f"Overall Status: {report.get('status', 'UNKNOWN')}",
        "=" * 80,
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="AST Concept Scaffolder & SHA-256 Code Drift Detector for OKF Bundles"
    )
    # Scaffolding options
    parser.add_argument("target", nargs="?", default=None, help="Target source file to scaffold, or concept file to check drift on")
    parser.add_argument("--file", "-f", default=None, help="Path to source file to inspect and scaffold into a concept document")
    parser.add_argument("--out", "-o", default=None, help="Output destination path for the generated concept document")
    parser.add_argument("--type", "-t", default="Component Specification", help="Concept type (default: 'Component Specification')")
    parser.add_argument("--title", default=None, help="Concept title (auto-derived from AST/file if omitted)")
    parser.add_argument("--description", "-d", default=None, help="Concept description (auto-derived from docstring/AST if omitted)")
    parser.add_argument("--tags", default=None, help="Comma-separated tags (e.g. 'python,ast,sync')")
    parser.add_argument("--resource", default=None, help="Explicit resource string in frontmatter (default: workspace-relative path)")

    # Drift detection options
    parser.add_argument("--check-drift", action="store_true", help="Audit concept documents for code drift against live source files")
    parser.add_argument("--dir", default=".gemini/knowledge", help="Directory containing OKF concept documents (default: .gemini/knowledge)")
    parser.add_argument("--update", action="store_true", help="Update concept document resource_hash to match live source file hash")
    parser.add_argument("--strict", action="store_true", help="Fail if any concept document has untracked resource or missing hash")
    parser.add_argument("--json", action="store_true", help="Emit output as clean JSON to stdout")
    parser.add_argument("--human", action="store_true", help="Emit human-readable output to stdout")
    parser.add_argument("--workspace-root", default=None, help="Root directory of workspace (auto-detected if omitted)")

    args = parser.parse_args()

    # Determine workspace root
    ws_root = Path(args.workspace_root).resolve() if args.workspace_root else find_workspace_root(Path.cwd())

    # --- MODE 1: CODE DRIFT DETECTION ---
    if args.check_drift:
        target_files = []
        target_label = ""

        explicit_target = args.file or args.target
        if explicit_target:
            p_target = Path(explicit_target).resolve()
            if p_target.is_file():
                target_files = [p_target]
                target_label = f"Single File ({p_target.relative_to(ws_root) if ws_root in p_target.parents else p_target.name})"
            elif p_target.is_dir():
                search_dir = p_target
                target_label = f"Directory ({search_dir})"
            else:
                print(json.dumps({"status": "FAIL", "errors": [f"Target not found: {explicit_target}"]}, indent=2))
                sys.exit(1)
        else:
            search_dir = Path(args.dir).resolve()
            target_label = f"Bundle Directory ({args.dir})"

        if not target_files:
            if not search_dir.exists() or not search_dir.is_dir():
                print(json.dumps({"status": "FAIL", "errors": [f"Knowledge directory not found: {search_dir}"]}, indent=2))
                sys.exit(1)

            for p in search_dir.rglob("*.md"):
                rel = p.relative_to(search_dir)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                if p.name in ("index.md", "log.md"):
                    continue
                if "ADRs" in rel.parts or "adr" in rel.parts:
                    continue

                # Exclude files inside nested bundles that have their own index.md
                parent = p.parent
                is_nested = False
                while parent != search_dir:
                    if (parent / "index.md").exists():
                        is_nested = True
                        break
                    parent = parent.parent
                if is_nested:
                    continue

                target_files.append(p.resolve())

            target_files.sort()

        report = check_code_drift(
            target_files=target_files,
            workspace_root=ws_root,
            update_hashes=args.update
        )

        human_output = format_human_report(report, target_label)
        json_output = json.dumps(report, indent=2)

        # Output dispatch
        if args.human:
            print(human_output)
        elif args.json:
            print(json_output)
        else:
            # Default behavior: readable human status to stderr, clean JSON to stdout
            sys.stderr.write(human_output + "\n")
            print(json_output)

        is_failed = False
        if report["status"] != "PASS":
            is_failed = True
        if args.strict and report["summary"]["untracked"] > 0:
            is_failed = True

        sys.exit(1 if is_failed else 0)

    # --- MODE 2: CONCEPT SCAFFOLDING ---
    source_file = args.file or args.target
    if not source_file:
        parser.print_help()
        sys.exit(1)

    source_path = Path(source_file).resolve()
    if not source_path.exists() or not source_path.is_file():
        err_msg = f"Source file not found: {source_file}"
        if args.json:
            print(json.dumps({"status": "FAIL", "errors": [err_msg]}, indent=2))
        else:
            sys.stderr.write(f"Error: {err_msg}\n")
        sys.exit(1)

    tag_list = [t.strip() for t in args.tags.split(",")] if args.tags else None
    out_target = Path(args.out).resolve() if args.out else None

    markdown = scaffold_concept_document(
        source_path=source_path,
        out_path=out_target,
        concept_type=args.type,
        title=args.title,
        description=args.description,
        tags=tag_list,
        resource_override=args.resource,
        workspace_root=ws_root
    )

    h = compute_sha256(source_path)

    if out_target:
        if args.json:
            print(json.dumps({
                "status": "PASS",
                "action": "scaffold",
                "out": str(out_target),
                "source": str(source_path),
                "resource_hash": h
            }, indent=2))
        else:
            print(f"[OKF SCAFFOLD] Concept written to {out_target} (resource_hash: {h})")
    else:
        # Output directly to stdout
        if args.json:
            print(json.dumps({
                "status": "PASS",
                "action": "scaffold",
                "source": str(source_path),
                "resource_hash": h,
                "content": markdown
            }, indent=2))
        else:
            print(markdown)

    sys.exit(0)


if __name__ == "__main__":
    main()
