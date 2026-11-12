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

"""Known-good and known-bad coverage for validate_atelier_html.py.

The script is the delivery gate for Atelier HTML. These tests are what make
that gate reject unclosed tags, colliding SVG labels, and em-dashes, and
accept a clean report that uses en-dashes for ranges.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "validate_atelier_html.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import validate_atelier_html as V  # noqa: E402


def _run(argv):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True, text=True, timeout=30,
    )


class ValidatorCliTest(unittest.TestCase):
    def test_known_good_fixture_exits_0_with_en_dash_and_forbid_flag(self):
        proc = _run(["--forbid-dashes", str(FIXTURES / "known_good.html")])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS", proc.stdout)

    def test_known_bad_overlap_exits_nonzero(self):
        proc = _run(["--allow-dashes", str(FIXTURES / "known_bad_overlap.html")])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("text collision", proc.stdout)

    def test_known_bad_unclosed_exits_nonzero(self):
        proc = _run(["--allow-dashes", str(FIXTURES / "known_bad_unclosed.html")])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(
            "Unclosed" in proc.stdout or "Tag mismatch" in proc.stdout,
            proc.stdout,
        )

    def test_em_dash_fails_only_when_forbidden_and_en_dash_does_not(self):
        em = FIXTURES / "known_bad_emdash.html"
        allowed = _run(["--allow-dashes", str(em)])
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        forbidden = _run(["--forbid-dashes", str(em)])
        self.assertEqual(forbidden.returncode, 1, forbidden.stdout + forbidden.stderr)
        self.assertIn("em-dashes", forbidden.stdout)
        self.assertNotIn("en-dashes", forbidden.stdout)

    def test_en_dash_range_passes_when_em_dashes_are_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "range.html"
            path.write_text(
                "<html><body><p>Range 18\u201330 stays.</p></body></html>",
                encoding="utf-8",
            )
            self.assertEqual(V.validate_file(path, forbid_dashes=True), [])

    def test_help_exits_0(self):
        proc = _run(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("--forbid-dashes", proc.stdout)
        self.assertIn("--allow-dashes", proc.stdout)

    def test_missing_file_is_a_clean_failure(self):
        proc = _run(["--allow-dashes", "no-such-atelier-report.html"])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("FAIL", proc.stderr)

    def test_win32_stdio_is_reconfigured_to_utf8(self):
        class Stream:
            def __init__(self):
                self.kwargs = None

            def reconfigure(self, **kwargs):
                self.kwargs = kwargs

        stdout, stderr = Stream(), Stream()
        saved = (V.sys.platform, V.sys.stdout, V.sys.stderr)
        V.sys.platform, V.sys.stdout, V.sys.stderr = "win32", stdout, stderr
        try:
            V.configure_stdio()
        finally:
            V.sys.platform, V.sys.stdout, V.sys.stderr = saved
        self.assertEqual(stdout.kwargs, {"encoding": "utf-8", "errors": "replace"})
        self.assertEqual(stderr.kwargs, {"encoding": "utf-8", "errors": "replace"})


class SvgClearanceTest(unittest.TestCase):
    def test_translate_groups_on_separate_rows_do_not_collide(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
          <g transform="translate(0, 0)"><text x="8" y="12" font-size="12">Row A label</text></g>
          <g transform="translate(0, 36)"><text x="8" y="12" font-size="12">Row B label</text></g>
        </svg>"""
        self.assertEqual(V.check_svg_text_collisions(svg), [])

    def test_labels_within_6px_horizontally_on_one_baseline_collide(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="0" y="20" font-size="12">Hi</text>
          <text x="16" y="20" font-size="12">Yo</text>
        </svg>"""
        found = V.check_svg_text_collisions(svg)
        self.assertTrue(found, "gap under 6px on one baseline must fail")
        self.assertIn("Hi", found[0])

    def test_baselines_closer_than_1_2x_font_size_collide(self):
        # 11px apart is about 0.92x of 12px, which the old box-overlap
        # threshold treated as clear. The contract requires 1.2x.
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="10" y="20" font-size="12">RowLabel</text>
          <text x="12" y="31" font-size="12">RowLabel</text>
        </svg>"""
        self.assertTrue(V.check_svg_text_collisions(svg))

    def test_px_coordinates_and_style_font_size_are_placed(self):
        far = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="10px" y="20px" style="font-size:12px;text-anchor:start">Alpha</text>
          <text x="400px" y="20px" style="font-size:12px">Beta</text>
        </svg>"""
        self.assertEqual(V.check_svg_text_collisions(far), [])
        piled = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="10px" y="20px" style="font-size:12px">Same</text>
          <text x="12px" y="22px" style="font-size:12px">Spot</text>
        </svg>"""
        self.assertTrue(V.check_svg_text_collisions(piled))

    def test_percent_coordinate_is_an_error_not_a_skip(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="50%" y="10">Hi</text>
          <text x="50%" y="10">Hi</text>
        </svg>"""
        found = V.check_svg_text_collisions(svg)
        self.assertTrue(any("not an absolute user unit" in item for item in found))

    def test_tspan_dy_is_its_own_line(self):
        tight = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="8" y="20" font-size="12"><tspan x="8" dy="0">Hello</tspan><tspan x="8" dy="10">World</tspan></text>
        </svg>"""
        clear = """<svg xmlns="http://www.w3.org/2000/svg">
          <text x="8" y="20" font-size="12"><tspan x="8" dy="0">Hello</tspan><tspan x="8" dy="18">World</tspan></text>
        </svg>"""
        self.assertTrue(V.check_svg_text_collisions(tight))
        self.assertEqual(V.check_svg_text_collisions(clear), [])

    def test_opposite_layouts_do_not_produce_the_same_verdict(self):
        """T1: a colliding diagram and a cleared one must not share a result."""
        bad = (FIXTURES / "known_bad_overlap.html").read_text(encoding="utf-8")
        good = (FIXTURES / "known_good.html").read_text(encoding="utf-8")
        self.assertNotEqual(
            V.check_svg_text_collisions(bad),
            V.check_svg_text_collisions(good),
        )


if __name__ == "__main__":
    unittest.main()
