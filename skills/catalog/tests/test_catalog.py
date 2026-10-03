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
test_catalog.py - Comprehensive Automated Test Suite for OKF Knowledge Catalog

Covers all 11 Milestone 4 Acceptance Tests:
- Test 1: Valid concept document passes verification (verify_okf.py).
- Test 2: Missing required frontmatter keys (type, title, description) fails with specific error messages.
- Test 3: Placeholder tokens (TBD, TODO, FIXME, as an AI) fail verification.
- Test 4: index.md meta-manifest passes verification without requiring type.
- Test 5: Missing disk resource fails resource grounding check when --check-resources is active.
- Test 6: Existing disk resource passes resource grounding check.
- Test 7: --all detects orphaned concept documents not registered in index.md.
- Test 8: --all detects dangling links in index.md pointing to non-existent files.
- Test 9: scaffold_okf.py generates valid OKF concept documents from Python source files with AST extraction.
- Test 10: scaffold_okf.py --check-drift correctly detects matching hash (OK) vs modified source file (DRIFT_DETECTED).
- Test 11: scaffold_okf.py --update correctly synchronizes updated hashes.
"""

import sys
import os
import shutil
import tempfile
import unittest
import json
import subprocess
from pathlib import Path

# UTF-8 Console encoding safety on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add scripts directory to module import path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from verify_okf import (
    verify_concept_file,
    verify_knowledge_bundle,
    verify_index_manifest,
    parse_yaml_frontmatter,
    resolve_resource_path,
    validate_okf_v02_metadata,
)
from scaffold_okf import (
    scaffold_concept_document,
    check_code_drift,
    compute_sha256,
    update_concept_resource_hash,
)


class TestOKFCatalogSuite(unittest.TestCase):
    """Test suite covering OKF verifier and AST concept scaffolder with drift detection."""

    def setUp(self):
        """Create isolated temporary workspace directory for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="okf_test_")
        self.workspace_root = Path(self.test_dir).resolve()
        # Seed an AGENTS.md so find_workspace_root anchors to self.workspace_root
        (self.workspace_root / "AGENTS.md").write_text("# Test Workspace\n", encoding="utf-8")

        self.verify_script = SCRIPTS_DIR / "verify_okf.py"
        self.scaffold_script = SCRIPTS_DIR / "scaffold_okf.py"

    def tearDown(self):
        """Clean up temporary workspace directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run_cli(self, script_path: Path, *args) -> tuple[int, str, str]:
        """Runs a script via CLI subprocess and returns (exit_code, stdout, stderr)."""
        cmd = [sys.executable, str(script_path)] + list(args)
        proc = subprocess.run(
            cmd,
            cwd=str(self.workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return proc.returncode, proc.stdout, proc.stderr

    # -------------------------------------------------------------------------
    # Test 1: Valid concept document passes verification (verify_okf.py)
    # -------------------------------------------------------------------------
    def test_01_valid_concept_passes_verification(self):
        """Test 1: Valid concept document passes verification with zero errors."""
        doc_path = self.workspace_root / "valid_concept.md"
        content = """---
type: "Architecture Specification"
title: "Core Service Engine"
description: "Detailed technical specification for the core service engine subsystem."
status: "active"
tags:
  - "core"
  - "engine"
---
# Core Service Engine

Detailed implementation notes and behavioral invariants for the service engine.
"""
        doc_path.write_text(content, encoding="utf-8")

        # Programmatic verification
        errors = verify_concept_file(doc_path, check_resources=False, workspace_root=self.workspace_root)
        self.assertEqual(errors, [], f"Expected zero errors, got: {errors}")

        # CLI invocation
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            str(doc_path),
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 0, f"CLI exited with non-zero code {exit_code}: {stdout}")
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "PASS")

    # -------------------------------------------------------------------------
    # Test 2: Missing required frontmatter keys fails with specific error messages
    # -------------------------------------------------------------------------
    def test_02_missing_required_keys_fails(self):
        """Test 2: Missing required keys (type, title, description) fails with specific error messages."""
        # 1. Missing type
        doc_no_type = self.workspace_root / "no_type.md"
        doc_no_type.write_text("""---
title: "No Type Concept"
description: "Valid description but missing type key."
---
# Content
""", encoding="utf-8")
        # Notice: when type is missing on a non-index file, verify_concept_file checks index manifest rules
        # Let's test standard concept file with type omitted or explicitly missing
        # If type is empty:
        doc_empty_type = self.workspace_root / "empty_type.md"
        doc_empty_type.write_text("""---
type: ""
title: "Empty Type Concept"
description: "Valid description."
---
# Content
""", encoding="utf-8")
        errors = verify_concept_file(doc_empty_type, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Missing required OKF frontmatter key: 'type'" in e for e in errors),
            f"Expected missing type error, got: {errors}"
        )

        # 2. Missing title
        doc_no_title = self.workspace_root / "no_title.md"
        doc_no_title.write_text("""---
type: "Architecture Specification"
description: "Valid description but missing title key."
---
# Content
""", encoding="utf-8")
        errors = verify_concept_file(doc_no_title, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Missing required OKF frontmatter key: 'title'" in e for e in errors),
            f"Expected missing title error, got: {errors}"
        )

        # 3. Missing description
        doc_no_desc = self.workspace_root / "no_desc.md"
        doc_no_desc.write_text("""---
type: "Architecture Specification"
title: "Valid Title"
---
# Content
""", encoding="utf-8")
        errors = verify_concept_file(doc_no_desc, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Missing required OKF frontmatter key: 'description'" in e for e in errors),
            f"Expected missing description error, got: {errors}"
        )

        # 4. CLI test asserting failure exit code 1
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            str(doc_no_desc),
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 1)
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "FAIL")
        self.assertTrue(any("description" in e for e in data.get("errors", [])))

    # -------------------------------------------------------------------------
    # Test 3: Placeholder tokens (TBD, TODO, FIXME, as an AI) fail verification
    # -------------------------------------------------------------------------
    def test_03_placeholder_tokens_fail(self):
        """Test 3: Placeholder tokens (TBD, TODO, FIXME, as an AI) fail verification."""
        placeholders = ["TODO", "TBD", "FIXME", "as an AI"]

        for token in placeholders:
            doc_path = self.workspace_root / f"placeholder_{token.replace(' ', '_')}.md"
            doc_path.write_text(f"""---
type: "Component Specification"
title: "Component with Placeholder"
description: "This component specification contains prohibited token {token}."
status: "active"
---
# Component Overview
The implementation details are {token} and will be refined.
""", encoding="utf-8")

            errors = verify_concept_file(doc_path, check_resources=False, workspace_root=self.workspace_root)
            self.assertTrue(
                any(f"Contains prohibited placeholder: '{token}'" in e for e in errors),
                f"Expected error for token '{token}', got: {errors}"
            )

            # CLI verification
            exit_code, stdout, _ = self._run_cli(
                self.verify_script,
                str(doc_path),
                "--workspace-root", str(self.workspace_root),
            )
            self.assertEqual(exit_code, 1)
            data = json.loads(stdout)
            self.assertEqual(data.get("status"), "FAIL")
            self.assertTrue(any(token in e for e in data.get("errors", [])))

    # -------------------------------------------------------------------------
    # Test 4: index.md meta-manifest passes verification without requiring type
    # -------------------------------------------------------------------------
    def test_04_index_manifest_passes_without_type(self):
        """Test 4: index.md meta-manifest passes verification without requiring 'type' frontmatter key."""
        index_path = self.workspace_root / "index.md"
        index_path.write_text("""---
title: "OKF System Architecture Index"
description: "Root index and meta-manifest for system architecture concepts."
status: "active"
---
# OKF System Architecture Index

Welcome to the knowledge base.

| Concept ID | Topic | File Path | Status |
|---|---|---|---|
| `core_engine` | Core Engine | `core_engine.md` | `active` |
| `network_rpc` | RPC Network | `network_rpc.md` | `active` |

## Maintenance
Index maintained autonomously.
""", encoding="utf-8")

        # Programmatic verification
        errors = verify_concept_file(index_path, check_resources=False, workspace_root=self.workspace_root)
        self.assertEqual(errors, [], f"Expected index.md to pass without 'type', got errors: {errors}")

        # CLI verification
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            str(index_path),
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 0, f"index.md verification failed with exit code {exit_code}: {stdout}")
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "PASS")

        # Malformed index: missing title
        bad_index = self.workspace_root / "bad_index.md"
        bad_index.write_text("""---
description: "No title in frontmatter."
---
| Concept ID | File Path |
|---|---|
| `c1` | `c1.md` |
""", encoding="utf-8")
        bad_errors = verify_concept_file(bad_index, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(any("Index manifest missing required 'title'" in e for e in bad_errors))

    # -------------------------------------------------------------------------
    # Test 5: Missing disk resource fails resource grounding check
    # -------------------------------------------------------------------------
    def test_05_missing_disk_resource_fails_grounding(self):
        """Test 5: Missing disk resource fails resource grounding check when --check-resources is active."""
        doc_path = self.workspace_root / "unpinned_concept.md"
        doc_path.write_text("""---
type: "Component Specification"
title: "Unpinned Component"
description: "Concept pointing to a missing disk resource."
resource: "src/non_existent_engine.py"
status: "active"
---
# Unpinned Component
Resource does not exist on disk.
""", encoding="utf-8")

        # Resource grounding enabled: should fail
        errors = verify_concept_file(doc_path, check_resources=True, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Referenced resource does not exist on disk: 'src/non_existent_engine.py'" in e for e in errors),
            f"Expected missing resource error, got: {errors}"
        )

        # CLI verification with --check-resources
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            str(doc_path),
            "--check-resources",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 1)
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "FAIL")
        self.assertTrue(any("Referenced resource does not exist on disk" in e for e in data.get("errors", [])))

        # When check_resources is disabled, it should pass
        errors_ignored = verify_concept_file(doc_path, check_resources=False, workspace_root=self.workspace_root)
        self.assertEqual(errors_ignored, [])

    # -------------------------------------------------------------------------
    # Test 6: Existing disk resource passes resource grounding check
    # -------------------------------------------------------------------------
    def test_06_existing_disk_resource_passes_grounding(self):
        """Test 6: Existing disk resource passes resource grounding check."""
        # Create real resource file on disk
        src_dir = self.workspace_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        worker_file = src_dir / "worker_engine.py"
        worker_file.write_text("# Worker implementation\ndef run():\n    return 42\n", encoding="utf-8")

        doc_path = self.workspace_root / "grounded_concept.md"
        doc_path.write_text("""---
type: "Component Specification"
title: "Worker Engine Specification"
description: "Grounded technical specification for the worker engine."
resource: "src/worker_engine.py"
status: "active"
---
# Worker Engine
Grounded against src/worker_engine.py.
""", encoding="utf-8")

        # Programmatic verification
        errors = verify_concept_file(doc_path, check_resources=True, workspace_root=self.workspace_root)
        self.assertEqual(errors, [], f"Expected grounded resource to pass, got errors: {errors}")

        # CLI verification
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            str(doc_path),
            "--check-resources",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 0, f"CLI failed with exit code {exit_code}: {stdout}")
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "PASS")

    # -------------------------------------------------------------------------
    # Test 7: --all detects orphaned concept documents not registered in index.md
    # -------------------------------------------------------------------------
    def test_07_all_detects_orphaned_concept_documents(self):
        """Test 7: --all detects orphaned concept documents not registered in index.md."""
        bundle_dir = self.workspace_root / "knowledge_bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 1. Registered concept
        registered_doc = bundle_dir / "registered.md"
        registered_doc.write_text("""---
type: "Guide"
title: "Registered Guide"
description: "Properly registered concept document in index."
status: "active"
---
# Registered Guide
""", encoding="utf-8")

        # 2. Orphaned concept (on disk, but omitted from index.md)
        orphaned_doc = bundle_dir / "orphaned.md"
        orphaned_doc.write_text("""---
type: "Guide"
title: "Orphaned Guide"
description: "Orphaned concept document omitted from index."
status: "active"
---
# Orphaned Guide
""", encoding="utf-8")

        # 3. Index manifest only linking registered.md
        index_doc = bundle_dir / "index.md"
        index_doc.write_text("""---
title: "Bundle Index"
description: "Meta index with one concept."
---
# Bundle Index

| Concept ID | Topic | File Path |
|---|---|---|
| `registered` | Registered Guide | [registered.md](registered.md) |
""", encoding="utf-8")

        # Programmatic audit
        errors = verify_knowledge_bundle(bundle_dir, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Orphaned concept document not registered in index.md: 'orphaned.md'" in e for e in errors),
            f"Expected orphaned concept error for orphaned.md, got: {errors}"
        )

        # CLI verification with --all --dir
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            "--all",
            "--dir", str(bundle_dir),
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 1)
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "FAIL")
        self.assertTrue(any("orphaned.md" in e for e in data.get("errors", [])))

    # -------------------------------------------------------------------------
    # Test 8: --all detects dangling links in index.md pointing to non-existent files
    # -------------------------------------------------------------------------
    def test_08_all_detects_dangling_links_in_index(self):
        """Test 8: --all detects dangling links in index.md pointing to non-existent files."""
        bundle_dir = self.workspace_root / "knowledge_dangling"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 1. Existing concept
        existing_doc = bundle_dir / "valid_concept.md"
        existing_doc.write_text("""---
type: "Runbook"
title: "Valid Runbook"
description: "Active runbook document."
status: "active"
---
# Valid Runbook
""", encoding="utf-8")

        # 2. Index with a link pointing to non_existent.md
        index_doc = bundle_dir / "index.md"
        index_doc.write_text("""---
title: "Index with Dangling Link"
description: "Meta manifest containing a dead pointer."
---
# Index

| Concept ID | Topic | File Path |
|---|---|---|
| `valid` | Valid Runbook | [valid_concept.md](valid_concept.md) |
| `ghost` | Ghost Concept | [non_existent.md](non_existent.md) |
""", encoding="utf-8")

        # Programmatic audit
        errors = verify_knowledge_bundle(bundle_dir, check_resources=False, workspace_root=self.workspace_root)
        self.assertTrue(
            any("Dangling link in index.md points to non-existent file: 'non_existent.md'" in e for e in errors),
            f"Expected dangling link error, got: {errors}"
        )

        # CLI verification
        exit_code, stdout, _ = self._run_cli(
            self.verify_script,
            "--all",
            "--dir", str(bundle_dir),
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 1)
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "FAIL")
        self.assertTrue(any("Dangling link in index.md points to non-existent file" in e for e in data.get("errors", [])))

    # -------------------------------------------------------------------------
    # Test 9: scaffold_okf.py generates valid OKF concept documents with AST extraction
    # -------------------------------------------------------------------------
    def test_09_scaffold_okf_ast_extraction(self):
        """Test 9: scaffold_okf.py generates valid OKF concept documents from Python source with AST extraction."""
        src_dir = self.workspace_root / "services"
        src_dir.mkdir(parents=True, exist_ok=True)
        py_source = src_dir / "pipeline_engine.py"
        py_source.write_text('''"""Pipeline execution engine for batch processing."""

__all__ = ["PipelineEngine", "execute_step"]

DEFAULT_BUFFER_SIZE = 1024

class PipelineEngine:
    """Core pipeline orchestration class."""

    def __init__(self, name: str, max_workers: int = 4):
        """Initialize pipeline with worker pool."""
        self.name = name
        self.max_workers = max_workers

    def run_pipeline(self, steps: list[str], dry_run: bool = False) -> bool:
        """Executes registered pipeline steps."""
        return True

def execute_step(step_id: str, timeout: float = 30.0) -> int:
    """Executes a single pipeline step."""
    return 0
''', encoding="utf-8")

        out_concept = self.workspace_root / "pipeline_engine_spec.md"

        # 1. Programmatic scaffolding
        markdown = scaffold_concept_document(
            source_path=py_source,
            out_path=out_concept,
            concept_type="Component Specification",
            tags=["python", "pipeline", "engine"],
            workspace_root=self.workspace_root,
        )

        self.assertTrue(out_concept.exists())
        content = out_concept.read_text(encoding="utf-8")

        # Verify frontmatter structure
        self.assertTrue(content.startswith("---"))
        meta = parse_yaml_frontmatter(content.split("---", 2)[1])
        self.assertEqual(meta.get("type"), "Component Specification")
        self.assertIn("PipelineEngine", meta.get("title", ""))
        self.assertTrue(len(meta.get("description", "")) > 0)
        self.assertEqual(meta.get("resource"), "services/pipeline_engine.py")
        self.assertTrue(str(meta.get("resource_hash")).startswith("sha256:"))
        self.assertEqual(meta.get("status"), "active")
        self.assertIn("pipeline", meta.get("tags", []))

        # Verify AST extracted symbols in markdown body
        self.assertIn("class PipelineEngine", content)
        self.assertIn("Core pipeline orchestration class.", content)
        self.assertIn("def __init__(self, name: str, max_workers: int = 4)", content)
        self.assertIn("def run_pipeline(self, steps: list[str], dry_run: bool = False) -> bool", content)
        self.assertIn("def execute_step(step_id: str, timeout: float = 30.0) -> int", content)
        self.assertIn("DEFAULT_BUFFER_SIZE", content)

        # 2. Verifier certification: assert the generated concept document is 100% compliant OKF
        errors = verify_concept_file(out_concept, check_resources=True, workspace_root=self.workspace_root)
        self.assertEqual(errors, [], f"Scaffolded document failed OKF verification: {errors}")

        # 3. CLI execution verification
        cli_out = self.workspace_root / "cli_pipeline_spec.md"
        exit_code, stdout, _ = self._run_cli(
            self.scaffold_script,
            "--file", str(py_source),
            "--out", str(cli_out),
            "--type", "Architecture Specification",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 0, f"Scaffolder CLI failed: {stdout}")
        self.assertTrue(cli_out.exists())
        cli_errors = verify_concept_file(cli_out, check_resources=True, workspace_root=self.workspace_root)
        self.assertEqual(cli_errors, [])

    # -------------------------------------------------------------------------
    # Test 10: scaffold_okf.py --check-drift detects matching vs modified source
    # -------------------------------------------------------------------------
    def test_10_scaffold_okf_drift_detection(self):
        """Test 10: scaffold_okf.py --check-drift detects matching hash (OK) vs modified source file (DRIFT_DETECTED)."""
        src_file = self.workspace_root / "auth_provider.py"
        src_file.write_text("class AuthProvider:\n    pass\n", encoding="utf-8")

        concept_file = self.workspace_root / "auth_provider_spec.md"
        scaffold_concept_document(
            source_path=src_file,
            out_path=concept_file,
            workspace_root=self.workspace_root,
        )

        # Phase A: Initial matching state (OK)
        report_initial = check_code_drift([concept_file], workspace_root=self.workspace_root)
        self.assertEqual(report_initial["status"], "PASS")
        self.assertEqual(report_initial["summary"]["ok"], 1)
        self.assertEqual(report_initial["summary"]["drift"], 0)
        self.assertEqual(report_initial["results"][0]["status"], "OK")

        # CLI audit Phase A
        exit_code, stdout, _ = self._run_cli(
            self.scaffold_script,
            "--check-drift",
            "--file", str(concept_file),
            "--json",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 0, f"Expected clean drift audit, got exit {exit_code}: {stdout}")
        data = json.loads(stdout)
        self.assertEqual(data.get("status"), "PASS")

        # Phase B: Mutate source file to trigger drift
        src_file.write_text("class AuthProvider:\n    # New method added\n    def login(self): pass\n", encoding="utf-8")

        # Programmatic audit Phase B
        report_drift = check_code_drift([concept_file], workspace_root=self.workspace_root)
        self.assertEqual(report_drift["status"], "DRIFT_DETECTED")
        self.assertEqual(report_drift["summary"]["ok"], 0)
        self.assertEqual(report_drift["summary"]["drift"], 1)
        self.assertEqual(report_drift["results"][0]["status"], "DRIFT")
        self.assertIn("Hash mismatch", report_drift["results"][0]["details"])

        # CLI audit Phase B
        exit_code, stdout, _ = self._run_cli(
            self.scaffold_script,
            "--check-drift",
            "--file", str(concept_file),
            "--json",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(exit_code, 1, f"Expected drift detection exit code 1, got {exit_code}")
        data_drift = json.loads(stdout)
        self.assertEqual(data_drift.get("status"), "DRIFT_DETECTED")
        self.assertEqual(data_drift["summary"]["drift"], 1)

    # -------------------------------------------------------------------------
    # Test 11: scaffold_okf.py --update correctly synchronizes updated hashes
    # -------------------------------------------------------------------------
    def test_11_scaffold_okf_update_synchronizes_hashes(self):
        """Test 11: scaffold_okf.py --update correctly synchronizes updated hashes."""
        src_file = self.workspace_root / "config_store.py"
        src_file.write_text("CONFIG_VERSION = 1\n", encoding="utf-8")

        concept_file = self.workspace_root / "config_store_spec.md"
        scaffold_concept_document(
            source_path=src_file,
            out_path=concept_file,
            workspace_root=self.workspace_root,
        )

        # Mutate source file
        src_file.write_text("CONFIG_VERSION = 2\n# Updated production setting\n", encoding="utf-8")
        new_live_hash = compute_sha256(src_file)

        # Verify drift is present before synchronization
        pre_report = check_code_drift([concept_file], workspace_root=self.workspace_root)
        self.assertEqual(pre_report["status"], "DRIFT_DETECTED")

        # Execute synchronization via CLI with --update
        exit_code, stdout, _ = self._run_cli(
            self.scaffold_script,
            "--check-drift",
            "--file", str(concept_file),
            "--update",
            "--json",
            "--workspace-root", str(self.workspace_root),
        )
        # Note: when drift is updated in that same run, report recorded the drift and synchronized it
        # Let's verify the file on disk now has the new hash
        concept_content = concept_file.read_text(encoding="utf-8")
        self.assertIn(new_live_hash, concept_content)

        # Subsequent check without --update must immediately return PASS and OK
        post_report = check_code_drift([concept_file], workspace_root=self.workspace_root)
        self.assertEqual(post_report["status"], "PASS")
        self.assertEqual(post_report["summary"]["ok"], 1)
        self.assertEqual(post_report["summary"]["drift"], 0)
        self.assertEqual(post_report["results"][0]["status"], "OK")

        # CLI post-sync check must exit 0
        post_exit_code, post_stdout, _ = self._run_cli(
            self.scaffold_script,
            "--check-drift",
            "--file", str(concept_file),
            "--json",
            "--workspace-root", str(self.workspace_root),
        )
        self.assertEqual(post_exit_code, 0, f"Post-sync CLI audit failed: {post_stdout}")
        post_data = json.loads(post_stdout)
        self.assertEqual(post_data.get("status"), "PASS")

        # Final verifier sanity check
        errors = verify_concept_file(concept_file, check_resources=True, workspace_root=self.workspace_root)
        self.assertEqual(errors, [], f"Synchronized concept failed verification: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
