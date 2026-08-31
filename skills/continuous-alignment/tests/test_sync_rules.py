import json
import os
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sync_agents_rules import (
    MAX_ROOT_LINES,
    build_root_agents_content,
    categorize_rules,
    load_active_memories,
    sync_rules,
)


class TestSyncAgentsRules(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir) / "workspace"
        self.workspace.mkdir(parents=True)
        self.memories_file = self.workspace / ".gemini" / "knowledge" / "memories.jsonl"
        self.memories_file.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sync_rules_creates_agents_md(self):
        sample_memories = [
            {
                "memory_id": "MEM-1111",
                "category": "command",
                "statement": "`pytest -v`: Run test suite",
                "status": "active"
            },
            {
                "memory_id": "MEM-2222",
                "category": "constraint",
                "statement": "Never commit unencrypted secrets",
                "status": "active"
            }
        ]
        with open(self.memories_file, "w", encoding="utf-8") as f:
            for item in sample_memories:
                f.write(json.dumps(item) + "\n")

        res = sync_rules(str(self.workspace))
        self.assertEqual(res["status"], "success")

        agents_file = self.workspace / "AGENTS.md"
        self.assertTrue(agents_file.exists())
        content = agents_file.read_text(encoding="utf-8")
        self.assertIn("Never commit unencrypted secrets", content)
        self.assertIn("pytest -v", content)
        self.assertLessEqual(len(content.splitlines()), MAX_ROOT_LINES)

    def test_path_scoped_rule_spillover(self):
        sample_memories = [
            {
                "memory_id": "MEM-3333",
                "category": "constraint",
                "scope": "path_scoped",
                "target_path_glob": "skills/docs/**",
                "statement": "Always compile HTML docs with compile_html_docs.py",
                "status": "active"
            }
        ]
        with open(self.memories_file, "w", encoding="utf-8") as f:
            for item in sample_memories:
                f.write(json.dumps(item) + "\n")

        res = sync_rules(str(self.workspace))
        self.assertEqual(res["overflow_rules"], 1)

        rule_file = self.workspace / ".agents" / "rules" / "skills_docs.md"
        self.assertTrue(rule_file.exists())
        content = rule_file.read_text(encoding="utf-8")
        self.assertIn("Always compile HTML docs with compile_html_docs.py", content)

    def test_superseded_rules_are_ignored(self):
        sample_memories = [
            {
                "memory_id": "MEM-OLD",
                "category": "constraint",
                "statement": "Use SQLite for metadata",
                "status": "active"
            },
            {
                "memory_id": "MEM-NEW",
                "category": "constraint",
                "statement": "Use flat-file JSONL for metadata",
                "status": "active",
                "supersedes": "MEM-OLD"
            }
        ]
        with open(self.memories_file, "w", encoding="utf-8") as f:
            for item in sample_memories:
                f.write(json.dumps(item) + "\n")

        active = load_active_memories(self.memories_file)
        active_ids = [m["memory_id"] for m in active]
        self.assertIn("MEM-NEW", active_ids)
        self.assertNotIn("MEM-OLD", active_ids)


if __name__ == "__main__":
    unittest.main()
