"""Keeps the docs and evals honest.

- The JSON example in references/schemas.md passes findings.py validate.
- Every URL in references/style-guides.md is https.
- Every eval that targets a seeded fixture points at a file that exists and
  carries a SEEDED marker; the known-good control carries none.
- Eval axes and rules are values findings.py accepts.
- SKILL.md stays within the progressive-disclosure budget (K3).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import unittest

SKILL_DIR = Path(__file__).resolve().parent.parent
REFS = SKILL_DIR / "references"
EVALS = SKILL_DIR / "evals"
SEEDED = EVALS / "fixtures" / "seeded"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import findings as F  # noqa: E402


def _expected(case: dict) -> list[dict]:
    exp = case.get("expected")
    if exp is None:
        return []
    return exp if isinstance(exp, list) else [exp]


class TestDocs(unittest.TestCase):
    def test_schemas_md_example_validates(self) -> None:
        text = (REFS / "schemas.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
        self.assertTrue(blocks, "schemas.md lost its JSON example")
        doc = json.loads(blocks[0])
        self.assertEqual(F.validate(doc), [])
        self.assertTrue(F.open_blocking(doc), "example should show an open blocker")

    def test_style_guide_urls_are_https(self) -> None:
        text = (REFS / "style-guides.md").read_text(encoding="utf-8")
        urls = re.findall(r"\bhttps?://[^\s|)>]+", text)
        self.assertGreater(len(urls), 30)
        self.assertEqual([u for u in urls if not u.startswith("https://")], [])

    def test_skill_md_budget_and_portable_paths(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 200)
        self.assertNotIn("python3.12", text)
        self.assertNotRegex(text, r"(?<!<skill-dir>/)scripts/\w+\.py --")


class TestEvals(unittest.TestCase):
    def setUp(self) -> None:
        self.evals = json.loads((EVALS / "evals.json").read_text(encoding="utf-8"))
        self.triggers = json.loads((EVALS / "triggers.json").read_text(encoding="utf-8"))

    def test_shape(self) -> None:
        self.assertEqual(self.evals["skill"], "review")
        self.assertEqual(self.triggers["skill"], "review")
        for case in self.evals["test_cases"]:
            self.assertTrue(case["name"] and case["input"] and case["assertions"], case)
        flags = {c["should_trigger"] for c in self.triggers["test_cases"]}
        self.assertEqual(flags, {True, False}, "need positive and negative triggers")

    def test_seeded_targets_exist_and_are_marked(self) -> None:
        seen = 0
        for case in self.evals["test_cases"]:
            for exp in _expected(case):
                path = SEEDED / exp["file"]
                self.assertTrue(path.is_file(), path)
                body = path.read_text(encoding="utf-8")
                if exp.get("count") == 0:
                    self.assertNotIn("SEEDED", body)
                    continue
                seen += 1
                self.assertIn("SEEDED", body, path)
                self.assertIn(exp["axis"], F.AXES)
                self.assertIn(exp["severity_floor"], F.SEVERITIES)
                if exp["axis"] == "security":
                    self.assertRegex(exp["rule"], r"^CWE-\d+$")
        self.assertGreaterEqual(seen, 5)

    def test_every_seeded_file_has_an_eval(self) -> None:
        targeted = {e["file"] for c in self.evals["test_cases"] for e in _expected(c)}
        on_disk = {p.relative_to(SEEDED).as_posix() for p in SEEDED.rglob("*") if p.is_file()}
        self.assertEqual(on_disk - targeted, set())


if __name__ == "__main__":
    unittest.main()
