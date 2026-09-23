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

"""Rendering tests.

The load-bearing one is TestDifferentiation: if two opposite profiles can
render the same file, the profile is decorative and the whole tool is a
static template with extra steps. The previous version of this skill failed
exactly that way, and had a passing test suite throughout.
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import profile_tool as P  # noqa: E402
import render as R  # noqa: E402


def load_fixture(name):
    return json.loads((SKILL_ROOT / "fixtures" / name).read_text(encoding="utf-8"))


class TestDifferentiation(unittest.TestCase):
    """Output must be a function of the profile."""

    def setUp(self):
        self.structured = R.render_all(load_fixture("profile_structured.json"))
        self.terse = R.render_all(load_fixture("profile_terse.json"))

    def test_every_rendered_file_differs_between_opposite_profiles(self):
        self.assertEqual(set(self.structured), set(self.terse))
        for filename in self.structured:
            self.assertNotEqual(
                self.structured[filename], self.terse[filename],
                f"{filename} is identical for two opposite profiles, so the "
                f"profile is not driving the output")

    def test_opposite_bands_produce_opposing_instructions(self):
        for filename, text in self.structured.items():
            self.assertIn("comparison table", text.lower(), filename)
        for filename, text in self.terse.items():
            self.assertIn("do not produce diagrams", text.lower(), filename)
            self.assertNotIn("lead with structure", text.lower(), filename)

    def test_a_profile_that_bans_analogies_does_not_recommend_them(self):
        for filename, text in self.terse.items():
            self.assertIn("no analogies", text.lower(), filename)
            self.assertNotIn("ground abstractions", text.lower(), filename)

    def test_subject_reaches_every_output(self):
        for filename, text in self.structured.items():
            self.assertIn("a structured reader", text, filename)

    def test_bands_alone_change_the_output(self):
        """The dimensions must be load-bearing, independently of everything else.

        The two fixtures also differ in subject, timestamp and claim counts, so
        the test above would still pass if render_all ignored every band. This
        one starts from one fixture and flips nothing but the bands, holding
        subject, rules, tone, limits and provenance identical -- the only thing
        left that can move the output is the dimensions.
        """
        base = load_fixture("profile_structured.json")
        flipped = copy.deepcopy(base)
        swap = {"low": "high", "high": "low"}
        moved = []
        for name, entry in flipped["dimensions"].items():
            if entry["band"] in swap:
                entry["band"] = swap[entry["band"]]
                moved.append(name)
        self.assertTrue(moved, "fixture has no banded dimension left to flip")

        before = R.render_all(base)
        after = R.render_all(flipped)
        for filename in before:
            self.assertNotEqual(
                before[filename], after[filename],
                f"{filename} is unchanged after flipping {len(moved)} band(s) "
                f"({', '.join(moved)}), so the dimensions do not drive it")

    def test_each_dimension_individually_moves_the_output(self):
        """No axis is allowed to be decorative. One at a time, flip it alone."""
        base = load_fixture("profile_structured.json")
        rendered = R.render_one(base, "claude")[1]
        swap = {"low": "high", "high": "low", "medium": "high"}
        for name, entry in base["dimensions"].items():
            if entry["band"] not in swap:
                continue
            with self.subTest(dimension=name):
                one = copy.deepcopy(base)
                one["dimensions"][name]["band"] = swap[entry["band"]]
                self.assertNotEqual(
                    rendered, R.render_one(one, "claude")[1],
                    f"{name} can be flipped without changing the config, so it "
                    f"is not wired to any rendered block")


class TestUnknownsRenderNothing(unittest.TestCase):
    """An unestablished axis must produce silence, not a plausible default.

    This is the anti-fabrication guarantee: the user should never find a rule
    in their config that nobody ever decided."""

    def test_unknown_dimension_emits_no_directive(self):
        prof = load_fixture("profile_terse.json")
        text = R.render_one(prof, "claude")[1]
        for band_text in R.BAND_TEXT["evidence_depth"].values():
            self.assertNotIn(band_text, text)

    def test_unknown_dimension_is_named_in_the_provenance_footer(self):
        text = R.render_one(load_fixture("profile_terse.json"), "claude")[1]
        self.assertIn("evidence depth", text)

    def test_null_limits_emit_no_numbers(self):
        text = R.render_one(load_fixture("profile_terse.json"), "claude")[1]
        self.assertNotIn("words unless", text)
        self.assertNotIn("per list item", text)

    def test_a_profile_with_all_axes_unknown_carries_no_house_style(self):
        prof = P.new_profile("nobody")
        P.add_rule(prof, "Say hello", source="declared", evidence=["asked"])
        text = R.render_one(prof, "claude")[1]
        for dimension in R.BAND_TEXT.values():
            for band_text in dimension.values():
                self.assertNotIn(band_text, text)


class TestProvenance(unittest.TestCase):
    def test_footer_reports_the_real_counts(self):
        prof = load_fixture("profile_structured.json")
        cov = P.coverage(prof)
        text = R.render_one(prof, "claude")[1]
        self.assertIn("9 observed in logs", text)
        self.assertIn(f"{cov['grounded_pct']}% grounded", text)

    def test_footer_names_the_unsourced_tone_and_limit_settings(self):
        prof = load_fixture("profile_structured.json")
        text = R.render_one(prof, "claude")[1]
        self.assertIn("tone settings and numeric limits", text)
        self.assertIn(str(P.coverage(prof)["unattributed"]), text)

    def test_inferred_prohibitions_are_marked_too(self):
        """The footer promises that every inferred item is marked *(inferred)*.
        The forbidden block did not honour that, so a guessed prohibition read
        as a hard rule."""
        prof = load_fixture("profile_structured.json")
        self.assertTrue(prof["forbidden"], "fixture no longer exercises this")
        prof["forbidden"][0]["source"] = "inferred"
        prof["forbidden"][0]["evidence"] = []
        block = R.build_forbidden_block(prof)
        self.assertIn("*(inferred)*", block)

    def test_prohibitions_are_grouped_under_their_scope(self):
        prof = load_fixture("profile_structured.json")
        prof["forbidden"] = [
            dict(prof["forbidden"][0], id="R90", scope="cost",
                 directive="Never quote a bare list price"),
        ]
        block = R.build_forbidden_block(prof)
        self.assertIn(R.SCOPE_HEADING["cost"], block)

    def test_inferred_claims_are_marked_inline(self):
        prof = load_fixture("profile_structured.json")
        prof["dimensions"]["visual_scaffolding"]["source"] = "inferred"
        prof["dimensions"]["visual_scaffolding"]["evidence"] = []
        text = R.render_one(prof, "claude")[1]
        self.assertIn("*(inferred, not yet confirmed)*", text)

    def test_inferred_rules_are_marked_inline(self):
        prof = load_fixture("profile_terse.json")
        prof["rules"][0]["source"] = "inferred"
        prof["rules"][0]["evidence"] = []
        text = R.render_one(prof, "claude")[1]
        self.assertIn("*(inferred)*", text)


class TestTemplates(unittest.TestCase):
    def test_no_template_leaves_an_unfilled_token(self):
        prof = load_fixture("profile_structured.json")
        for harness in R.HARNESSES:
            _, text = R.render_one(prof, harness)
            self.assertEqual(R.TOKEN_RE.findall(text), [], harness)

    def test_a_template_with_an_unknown_token_fails_loudly(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        original = R.TEMPLATES_DIR
        try:
            shutil.copytree(original, tmp / "templates")
            (tmp / "templates" / "claude.md.tmpl").write_text(
                "{{TONE_BLOCK}} {{NOT_A_REAL_TOKEN}}", encoding="utf-8")
            R.TEMPLATES_DIR = tmp / "templates"
            with self.assertRaises(R.RenderError) as ctx:
                R.render_one(load_fixture("profile_terse.json"), "claude")
            self.assertIn("NOT_A_REAL_TOKEN", str(ctx.exception))
        finally:
            R.TEMPLATES_DIR = original

    def test_no_template_hardcodes_a_persona(self):
        """Templates must carry structure only. Any directive baked into a
        template applies to everyone regardless of their profile."""
        banned = ["rule of 3", "adhd", "orientation anchor", "decision tree",
                  "scratchpad", "college", "blindspot audit", "tco"]
        for path in R.TEMPLATES_DIR.glob("*.tmpl"):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in banned:
                self.assertNotIn(phrase, text,
                                 f"{path.name} hardcodes '{phrase}'")

    def test_every_harness_maps_to_an_existing_template(self):
        for harness, (_, template) in R.HARNESSES.items():
            self.assertTrue((R.TEMPLATES_DIR / template).exists(), harness)

    def test_harnesses_sharing_a_filename_agree(self):
        prof = load_fixture("profile_structured.json")
        by_name = {}
        for harness in R.HARNESSES:
            filename, text = R.render_one(prof, harness)
            if filename in by_name:
                self.assertEqual(by_name[filename], text,
                                 f"{filename} rendered differently by two harnesses")
            by_name[filename] = text

    def test_unknown_harness_is_rejected(self):
        with self.assertRaises(R.RenderError):
            R.render_one(load_fixture("profile_terse.json"), "notepad")


class TestBandCoverage(unittest.TestCase):
    def test_every_dimension_has_text_for_every_real_band(self):
        self.assertEqual(sorted(R.BAND_TEXT), sorted(P.DIMENSIONS))
        for name, bands in R.BAND_TEXT.items():
            self.assertEqual(sorted(bands), ["high", "low", "medium"], name)

    def test_low_and_high_are_genuinely_opposed(self):
        """A dimension whose extremes read the same is not worth measuring."""
        for name, bands in R.BAND_TEXT.items():
            low = set(bands["low"].lower().split())
            high = set(bands["high"].lower().split())
            overlap = len(low & high) / max(len(low | high), 1)
            self.assertLess(overlap, 0.4,
                            f"{name}: low and high bands are {overlap:.0%} similar")

    def test_every_dimension_drives_a_block_that_exists(self):
        drives = {meta["drives"] for meta in P.DIMENSIONS.values()}
        blocks = {b.replace("_BLOCK", "").lower() for b in R.BLOCK_BUILDERS}
        self.assertTrue(drives <= blocks, f"{drives - blocks} drive no block")


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_writes_files_and_check_then_passes(self):
        prof_path = SKILL_ROOT / "fixtures" / "profile_structured.json"
        ev_path = SKILL_ROOT / "fixtures" / "evidence_sample.json"
        rc = R.main([str(prof_path), "-o", str(self.tmp), "-e", str(ev_path)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.tmp / "CLAUDE.md").exists())
        self.assertTrue((self.tmp / ".cursorrules").exists())
        self.assertEqual(
            R.main([str(prof_path), "-o", str(self.tmp), "--check"]), 0)

    def test_check_fails_when_a_file_is_stale(self):
        prof_path = SKILL_ROOT / "fixtures" / "profile_structured.json"
        R.main([str(prof_path), "-o", str(self.tmp)])
        (self.tmp / "CLAUDE.md").write_text("edited by hand", encoding="utf-8")
        self.assertEqual(
            R.main([str(prof_path), "-o", str(self.tmp), "--check"]), 1)

    def test_an_invalid_profile_is_refused(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps(P.new_profile("nobody")), encoding="utf-8")
        self.assertEqual(R.main([str(bad), "-o", str(self.tmp)]), 1)
        self.assertFalse((self.tmp / "CLAUDE.md").exists())

    def test_force_renders_an_invalid_profile(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps(P.new_profile("nobody")), encoding="utf-8")
        self.assertEqual(R.main([str(bad), "-o", str(self.tmp), "--force"]), 0)

    def test_missing_profile_exits_two(self):
        self.assertEqual(R.main([str(self.tmp / "nope.json")]), 2)


if __name__ == "__main__":
    unittest.main()
