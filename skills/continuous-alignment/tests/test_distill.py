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

from distill_session import (
    compute_memory_id,
    distill_session,
    extract_command_invariants,
    extract_tool_troubleshooting,
    extract_user_constraints,
    parse_transcript_lines,
    sanitize_text,
)


class TestDistillSession(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir) / "workspace"
        self.workspace.mkdir(parents=True)
        self.transcript_file = Path(self.test_dir) / "transcript.jsonl"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_text_redacts_keys_and_pii(self):
        raw = "My key is AIzaSyD948f938hf_2398hdsf and email is engineer@example.com."
        sanitized = sanitize_text(raw)
        self.assertNotIn("AIzaSyD948f938hf_2398hdsf", sanitized)
        self.assertNotIn("engineer@example.com", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)

    def test_compute_memory_id_deterministic(self):
        id1 = compute_memory_id("Always run pytest before committing", "constraint")
        id2 = compute_memory_id("Always run pytest before committing", "constraint")
        id3 = compute_memory_id("Different rule", "constraint")
        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertTrue(id1.startswith("MEM-"))

    def test_extract_user_constraints(self):
        entry = {
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "content": "You must always run pytest -v before opening a PR. Do not touch production databases directly."
        }
        constraints = extract_user_constraints(entry)
        self.assertGreaterEqual(len(constraints), 1)
        statements = [c["statement"] for c in constraints]
        self.assertTrue(any("pytest" in s for s in statements))

    def test_extract_command_invariants(self):
        entries = [
            {
                "type": "PLANNER_RESPONSE",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "pytest -v tests/"}
                    }
                ]
            }
        ]
        cmds = extract_command_invariants(entries)
        self.assertEqual(len(cmds), 1)
        self.assertIn("pytest -v tests/", cmds[0]["statement"])

    def test_distill_session_end_to_end(self):
        # Create a sample transcript
        sample_transcript = [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Always enforce strict typing in python files. Never use bare except blocks."
            },
            {
                "type": "PLANNER_RESPONSE",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "python scripts/validate_skills.py"}
                    }
                ]
            }
        ]
        with open(self.transcript_file, "w", encoding="utf-8") as f:
            for item in sample_transcript:
                f.write(json.dumps(item) + "\n")

        res = distill_session(
            workspace_path=str(self.workspace),
            transcript_path=str(self.transcript_file),
            conversation_id="test-conv-123"
        )
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["added"], 0)

        # Verify memories.jsonl was created
        memories_path = self.workspace / ".gemini" / "knowledge" / "memories.jsonl"
        self.assertTrue(memories_path.exists())

        # Test deduplication on re-run
        res_repeat = distill_session(
            workspace_path=str(self.workspace),
            transcript_path=str(self.transcript_file),
            conversation_id="test-conv-123"
        )
        self.assertEqual(res_repeat["added"], 0)


if __name__ == "__main__":
    unittest.main()
