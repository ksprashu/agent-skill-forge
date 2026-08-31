import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from compile_roadmap import (
    compile_vision_and_roadmap,
    create_madr_record,
    generate_roadmap_svg,
    load_active_adrs,
)


class TestCompileRoadmap(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir) / "workspace"
        self.workspace.mkdir(parents=True)
        self.adr_dir = self.workspace / ".gemini" / "knowledge" / "ADRs"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_and_load_madr_record(self):
        file_path = create_madr_record(
            adr_dir=self.adr_dir,
            adr_id=2,
            title="Adopt SVG Visualizer for Roadmaps",
            context="Need visual clarity on active milestones",
            decision="Embed dynamic SVG diagrams into ROADMAP.md",
            positives=["Zero client-side JS dependency", "High aesthetic quality"],
            negatives=["Slightly larger markdown size"]
        )
        self.assertTrue(file_path.exists())
        adrs = load_active_adrs(self.adr_dir)
        self.assertEqual(len(adrs), 1)
        self.assertEqual(adrs[0]["title"], "ADR-002: Adopt SVG Visualizer for Roadmaps")
        self.assertEqual(adrs[0]["status"], "Accepted")

    def test_generate_roadmap_svg(self):
        milestones = [
            {"name": "Step 1", "desc": "Setup", "status": "completed"},
            {"name": "Step 2", "desc": "Execution", "status": "in_progress"}
        ]
        svg = generate_roadmap_svg(milestones)
        self.assertIn("<svg", svg)
        self.assertIn("DONE", svg)
        self.assertIn("ACTIVE", svg)

    def test_compile_vision_and_roadmap_end_to_end(self):
        res = compile_vision_and_roadmap(str(self.workspace))
        self.assertEqual(res["status"], "success")
        self.assertTrue((self.workspace / "docs" / "ROADMAP.md").exists())
        self.assertTrue((self.workspace / "docs" / "VISION.md").exists())


if __name__ == "__main__":
    unittest.main()
