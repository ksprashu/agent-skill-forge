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
Test suite for Defect Validator (skills/review/scripts/defect_validator.py).

Implements required testing patterns from docs/ENGINEERING_STANDARD.md:
- Pattern T4 (Mandatory Negative Tests): Asserts validator rejects malformed defect
  fixtures and pinpointed missing schema elements with non-zero exit codes.
- Asserts valid defect fixture passes cleanly with exit code 0.
- Asserts accurate CLI flag contracts, JSON output schema, and V5 uninspected surface.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = TESTS_DIR / "fixtures"

sys.path.insert(0, str(SCRIPTS_DIR))
import defect_validator as DV  # noqa: E402

VALIDATOR_SCRIPT = SCRIPTS_DIR / "defect_validator.py"
VALID_FIXTURE = FIXTURES_DIR / "valid_defect.md"
MALFORMED_FIXTURE = FIXTURES_DIR / "malformed_defect.md"


class TestDefectValidatorFixtures(unittest.TestCase):
    """Test validation of committed known-good and known-bad fixtures."""

    def test_valid_defect_fixture_cli_passes(self) -> None:
        """Assert that running defect_validator.py on valid_defect.md exits 0."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", str(VALID_FIXTURE)],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Expected exit code 0 for valid_defect.md, got {res.returncode}. Stderr: {res.stderr}",
        )
        self.assertIn("valid", res.stdout.lower())
        self.assertIn("0 error", res.stdout.lower())

    def test_malformed_defect_fixture_cli_fails_t4(self) -> None:
        """Pattern T4: Assert that running defect_validator.py on malformed_defect.md exits 1."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", str(MALFORMED_FIXTURE)],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(
            res.returncode,
            1,
            f"Expected exit code 1 for malformed_defect.md, got {res.returncode}. Stdout: {res.stdout}",
        )
        # Verify specific schema violations are reported in stderr
        stderr_lower = res.stderr.lower()
        self.assertIn("file:line", stderr_lower, "Expected missing file:line error in diagnostics")
        self.assertTrue(
            "empirical proof" in stderr_lower or "reproduction" in stderr_lower,
            "Expected missing empirical proof/reproduction error in diagnostics",
        )
        self.assertTrue(
            "verification gate" in stderr_lower or "verification command" in stderr_lower,
            "Expected missing verification gate error in diagnostics",
        )


class TestDefectValidatorSchemaRules(unittest.TestCase):
    """Test schema enforcement: missing required sections or bad coordinates trigger exit 1."""

    BASE_VALID_TEMPLATE = """# [DEFECT-001] [P0: Critical] Memory leak in cache

- **Location**: [`src/cache/store.ts:L88`](file:///src/cache/store.ts#L88)

## Description
Unbounded cache growth causes memory exhaustion.

## Blast Radius
Node process crashes with out-of-memory error.

## Empirical Proof
Run cache population loop for 100,000 iterations: heap size exceeds 2GB.

## Drop-in Remediation
```typescript
// Before:
// cache.set(k, v);
// After:
cache.setWithEviction(k, v, 1000);
```

## Verification Gate
`npm run test:cache`
"""

    def test_missing_id_and_badge_triggers_exit_1(self) -> None:
        """Pattern T4: Missing defect ID or badge triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "# [DEFECT-001] [P0: Critical] Memory leak in cache",
            "# Memory leak in cache",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("badge", res.stderr.lower())

    def test_missing_location_triggers_exit_1(self) -> None:
        """Pattern T4: Missing file:line coordinate triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "- **Location**: [`src/cache/store.ts:L88`](file:///src/cache/store.ts#L88)",
            "- **Location**: src/cache/store.ts",  # Missing line number
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("file:line", res.stderr.lower())

    def test_unparseable_location_triggers_exit_1(self) -> None:
        """Pattern T4: Non-coordinate location triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "- **Location**: [`src/cache/store.ts:L88`](file:///src/cache/store.ts#L88)",
            "- **Location**: somewhere in the cache subsystem",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("file:line", res.stderr.lower())

    def test_missing_description_triggers_exit_1(self) -> None:
        """Pattern T4: Missing Description section triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "## Description\nUnbounded cache growth causes memory exhaustion.\n\n",
            "",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("description", res.stderr.lower())

    def test_missing_blast_radius_triggers_exit_1(self) -> None:
        """Pattern T4: Missing Blast Radius section triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "## Blast Radius\nNode process crashes with out-of-memory error.\n\n",
            "",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertTrue(
            "blast radius" in res.stderr.lower() or "impact" in res.stderr.lower()
        )

    def test_missing_empirical_proof_triggers_exit_1(self) -> None:
        """Pattern T4: Missing Empirical Proof section triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "## Empirical Proof\nRun cache population loop for 100,000 iterations: heap size exceeds 2GB.\n\n",
            "",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertTrue(
            "empirical proof" in res.stderr.lower() or "reproduction" in res.stderr.lower()
        )

    def test_missing_drop_in_remediation_triggers_exit_1(self) -> None:
        """Pattern T4: Missing Drop-in Remediation section triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "## Drop-in Remediation\n```typescript\n// Before:\n// cache.set(k, v);\n// After:\ncache.setWithEviction(k, v, 1000);\n```\n\n",
            "",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertTrue(
            "drop-in remediation" in res.stderr.lower() or "proposed fix" in res.stderr.lower()
        )

    def test_remediation_without_code_block_triggers_exit_1(self) -> None:
        """Pattern T4: Drop-in Remediation without a fenced code block triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "```typescript\n// Before:\n// cache.set(k, v);\n// After:\ncache.setWithEviction(k, v, 1000);\n```",
            "Please rewrite cache.set to evict old items when limit is reached.",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("code block", res.stderr.lower())

    def test_remediation_with_empty_code_block_triggers_exit_1(self) -> None:
        """Pattern T4: Drop-in Remediation with empty code block triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "```typescript\n// Before:\n// cache.set(k, v);\n// After:\ncache.setWithEviction(k, v, 1000);\n```",
            "```typescript\n\n```",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("empty", res.stderr.lower())

    def test_missing_verification_gate_triggers_exit_1(self) -> None:
        """Pattern T4: Missing Verification Gate section triggers validation failure."""
        bad_text = self.BASE_VALID_TEMPLATE.replace(
            "## Verification Gate\n`npm run test:cache`\n",
            "",
        )
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--text", bad_text],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertTrue(
            "verification gate" in res.stderr.lower() or "verification command" in res.stderr.lower()
        )


class TestDefectValidatorCLI(unittest.TestCase):
    """Test CLI flags and outputs: --json, --quiet, --file, --text, and diagnostics."""

    def test_cli_json_mode_valid_fixture(self) -> None:
        """Verify --json produces parseable structured output matching schema."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", str(VALID_FIXTURE), "--json"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        parsed = json.loads(res.stdout)
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["defects_count"], 1)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(len(parsed["findings"]), 1)
        finding = parsed["findings"][0]
        self.assertEqual(finding["id"], "DEFECT-001")
        self.assertEqual(finding["badge"], "P0: Critical")
        self.assertTrue(len(finding["locations"]) > 0)
        # V5: Uninspected surface explicitly accounted for
        self.assertIn("uninspected", parsed)
        self.assertTrue(len(parsed["uninspected"]) > 0)

    def test_cli_json_mode_malformed_fixture(self) -> None:
        """Pattern T4: Verify --json on malformed defect outputs valid=False and error list."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", str(MALFORMED_FIXTURE), "--json"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        parsed = json.loads(res.stdout)
        self.assertFalse(parsed["valid"])
        self.assertGreaterEqual(len(parsed["errors"]), 3)

    def test_cli_quiet_flag_suppresses_stdout(self) -> None:
        """Verify --quiet suppresses informational output on success."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", str(VALID_FIXTURE), "--quiet"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "")

    def test_cli_nonexistent_file_exits_1(self) -> None:
        """Pattern T4: Non-existent file path exits 1 with diagnostic."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--file", "does_not_exist_defect.md"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("file not found", res.stderr.lower())

    def test_cli_missing_input_flags_exits_1(self) -> None:
        """Pattern T4: Invocation without --file or --text exits 1 with diagnostic."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT)],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("either --file or --text", res.stderr.lower())


class TestDefectValidatorProgrammatic(unittest.TestCase):
    """Test programmatic API and variations of badges, locations, and aliases."""

    def test_badge_variations(self) -> None:
        """Verify standard badge patterns: [P0..P3], [Critical], [Important], [DEFECT-###]."""
        badges = [
            "[DEFECT-042]",
            "[P0: Blocker]",
            "[P1: High]",
            "[P2: Medium]",
            "[P3: Low]",
            "[Critical]",
            "[Important]",
            "[Suggestion]",
            "[Question]",
        ]
        validator = DV.DefectValidator()
        for badge in badges:
            sample = TestDefectValidatorSchemaRules.BASE_VALID_TEMPLATE.replace(
                "# [DEFECT-001] [P0: Critical] Memory leak in cache",
                f"# {badge} Memory leak in cache",
            )
            result = validator.validate(sample)
            self.assertTrue(
                result["valid"],
                f"Badge '{badge}' failed validation: {result['errors']}",
            )

    def test_location_variations(self) -> None:
        """Verify acceptable location shapes: URI, path:L#, path:#, file:#."""
        locations = [
            "file:///src/api/auth.ts#L42",
            "src/api/auth.ts:L42",
            "src/api/auth.ts:42",
            "auth.ts:42",
            "[`auth.ts:L15`](file:///src/auth.ts#L15)",
        ]
        validator = DV.DefectValidator()
        for loc in locations:
            sample = TestDefectValidatorSchemaRules.BASE_VALID_TEMPLATE.replace(
                "- **Location**: [`src/cache/store.ts:L88`](file:///src/cache/store.ts#L88)",
                f"- **Location**: {loc}",
            )
            result = validator.validate(sample)
            self.assertTrue(
                result["valid"],
                f"Location '{loc}' failed validation: {result['errors']}",
            )

    def test_section_alias_variations(self) -> None:
        """Verify recognized section aliases: Vulnerability Description, Impact, Reproduction, Proposed Fix."""
        sample = """# [Critical] Insecure Deserialization in Session Store

- **Location**: `src/session.py:L12`

### Vulnerability Description
Pickle loads untrusted input.

### Impact
Remote code execution on application container.

### Reproduction
Execute exploit payload via cookie injection.

### Proposed Fix
```python
# Before:
# data = pickle.loads(cookie)
# After:
data = json.loads(cookie)
```

### Verification Command
`python3.12 -m pytest tests/test_session.py`
"""
        validator = DV.DefectValidator()
        result = validator.validate(sample)
        self.assertTrue(
            result["valid"],
            f"Aliases failed validation: {result['errors']}",
        )



# The long-form report shapes that references/schemas.md documented before the
# findings JSON became the primary output; the validator still checks them.
LEGACY_EXEMPLAR = FIXTURES_DIR / "legacy_defect_exemplar.md"
LEGACY_MODE_A_REPORT = FIXTURES_DIR / "legacy_mode_a_report.md"


class TestDefectValidatorRegressions(unittest.TestCase):
    """Regressions from pr-guardian review R-001, R-002 and R-003."""

    def setUp(self) -> None:
        self.validator = DV.DefectValidator()
        self.base = TestDefectValidatorSchemaRules.BASE_VALID_TEMPLATE

    def test_long_form_exemplar_passes(self) -> None:
        """R-001: the long-form exemplar ("Vulnerability / Defect Description") validates."""
        result = self.validator.validate(LEGACY_EXEMPLAR.read_text(encoding="utf-8"))
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["defects_count"], 1)

    def test_long_form_pr_report_passes(self) -> None:
        """R-003: the long-form PR report (a defect plus summary sections) validates."""
        result = self.validator.validate(LEGACY_MODE_A_REPORT.read_text(encoding="utf-8"))
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["defects_count"], 1)

    def test_headingless_prose_is_rejected(self) -> None:
        """R-001 T4: lines that merely start with section words are not section headings."""
        text = ("# [DEFECT-001] [P1: High] a.py:1\nDescription x\nImpact x\nRepro x\n"
                "Fix x\n```\ncode\n```\nVerification x\n")
        result = self.validator.validate(text)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Missing required section 'Description'" in e for e in result["errors"]))

    def test_fix_word_in_description_does_not_bind_remediation(self) -> None:
        """R-001: a prose line starting with "Fix" no longer stands in for the remediation."""
        text = self.base.replace(
            "Unbounded cache growth causes memory exhaustion.",
            "Unbounded cache growth causes memory exhaustion.\nFix this soon.",
        ).replace("## Drop-in Remediation\n", "")
        result = self.validator.validate(text)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Drop-in Remediation" in e for e in result["errors"]))

    def test_hash_comments_inside_remediation_fence(self) -> None:
        """R-002: '# Gate' / '# Verification' comments in the code block do not end the section."""
        text = self.base.replace(
            "```typescript\n// Before:\n// cache.set(k, v);\n// After:\ncache.setWithEviction(k, v, 1000);\n```",
            "```python\n# Gate: ensure caller is authenticated\n# Verification: see below\n"
            "cache.set_with_eviction(k, v, 1000)\n```",
        )
        result = self.validator.validate(text)
        self.assertTrue(result["valid"], result["errors"])

    def test_remediation_ends_at_next_heading(self) -> None:
        """R-002 T4: a code block in a later section does not satisfy the remediation."""
        text = self.base.replace(
            "```typescript\n// Before:\n// cache.set(k, v);\n// After:\ncache.setWithEviction(k, v, 1000);\n```",
            "Use an LRU.\n\n## Notes\n```\nunrelated\n```",
        )
        result = self.validator.validate(text)
        self.assertFalse(result["valid"])
        self.assertTrue(any("fenced code block" in e for e in result["errors"]))

    def test_zero_defect_report_passes(self) -> None:
        """R-003: an APPROVED review with no defects is valid with zero defects."""
        text = ("# Pull Request Quality Engineering Review\n\n**Review Status:** APPROVED\n\n"
                "## 1. Executive Summary & Macro Intent\nClean change.\n\n"
                "## 2. Findings Summary\n- 🔴 **P0 (Critical):** 0\n")
        result = self.validator.validate(text)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["defects_count"], 0)

    def test_question_and_p3_entries_are_non_blocking(self) -> None:
        """R-003: [Question] and [P3: ...] entries need a badge and location only."""
        text = (self.base
                + "\n### [Question] Max retries\n`src/config/limits.py:L14`: does 5 match the gateway timeout?\n"
                + "\n### [P3: Low - Suggestion/Nit] Rename helper\n`src/util.py:9`: `do_it` could be `flush`.\n")
        result = self.validator.validate(text)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual([f["tier"] for f in result["findings"]],
                         ["blocking", "non-blocking", "non-blocking"])

    def test_question_without_location_is_rejected(self) -> None:
        """R-003 T4: non-blocking entries still need a file:line location."""
        result = self.validator.validate(self.base + "\n### [Question] Why polling?\nNo location here.\n")
        self.assertFalse(result["valid"])
        self.assertTrue(any("Defect 2: Missing valid file:line" in e for e in result["errors"]))

    def test_unbadged_second_defect_is_detected(self) -> None:
        """R-003 T4: a second defect without a badge heading is not silently merged."""
        second = self.base.replace("# [DEFECT-001] [P0: Critical] Memory leak in cache",
                                   "## Second leak in store")
        result = self.validator.validate(self.base + "\n" + second)
        self.assertFalse(result["valid"])
        self.assertTrue(any("2 Description sections" in e for e in result["errors"]))

    def test_unbadged_defect_at_same_level_is_detected(self) -> None:
        """R-025: a badgeless defect at the first defect's heading level is not dropped."""
        second = self.base.replace("# [DEFECT-001] [P0: Critical] Memory leak in cache",
                                   "# Second leak in store")
        result = self.validator.validate(self.base + "\n" + second)
        self.assertFalse(result["valid"])
        self.assertTrue(any("outside a defect heading" in e for e in result["errors"]),
                        result["errors"])

    def test_summary_section_after_defect_still_passes(self) -> None:
        """R-025 T4: a same-level heading without defect sections is not an error."""
        result = self.validator.validate(self.base + "\n# Summary\n\nOne defect found.\n")
        self.assertTrue(result["valid"], result["errors"])

    def test_unbadged_defect_before_first_heading_is_detected(self) -> None:
        """R-003 T4: defect sections before the first badged heading are reported."""
        first = self.base.replace("# [DEFECT-001] [P0: Critical] Memory leak in cache",
                                  "# Leak without badge")
        result = self.validator.validate(first + "\n" + self.base)
        self.assertFalse(result["valid"])
        self.assertTrue(any("before the first defect heading" in e for e in result["errors"]))


class TestDefectValidatorVerdictGate(unittest.TestCase):
    """R-004: the report verdict is checked against its defects, not self-certified."""

    def setUp(self) -> None:
        self.validator = DV.DefectValidator()
        self.p0 = TestDefectValidatorSchemaRules.BASE_VALID_TEMPLATE

    def _report(self, status_line: str, body: str) -> str:
        defect = body.replace("\n## ", "\n#### ").replace("# [DEFECT", "### [DEFECT")
        return f"# Review\n\n{status_line}\n\n## Findings\n\n" + defect

    def test_approved_with_open_p0_is_rejected(self) -> None:
        result = self.validator.validate(self._report("**Review Status:** APPROVED", self.p0))
        self.assertFalse(result["valid"])
        self.assertTrue(any("open P0/P1" in e for e in result["errors"]), result["errors"])

    def test_changes_requested_with_open_p0_passes(self) -> None:
        result = self.validator.validate(self._report("**Review Status:** CHANGES REQUESTED", self.p0))
        self.assertTrue(result["valid"], result["errors"])

    def test_certified_with_open_p2_is_rejected(self) -> None:
        p2 = self.p0.replace("[P0: Critical]", "[P2: Medium]")
        result = self.validator.validate(self._report("**Certification Verdict:** CERTIFIED", p2))
        self.assertFalse(result["valid"])
        self.assertTrue(any("CERTIFIED" in e for e in result["errors"]), result["errors"])

    def test_defect_id_heading_takes_severity_from_metadata(self) -> None:
        """R-026: [DEFECT-###] without a badge uses its '- **Severity:** P0' line."""
        body = self.p0.replace("[DEFECT-001] [P0: Critical]", "[DEFECT-001]").replace(
            "- **Location**", "- **Severity:** P0: Critical\n- **Location**")
        result = self.validator.validate(self._report("**Review Status:** APPROVED", body))
        self.assertFalse(result["valid"])
        self.assertTrue(any("open P0/P1" in e for e in result["errors"]), result["errors"])

    def test_defect_id_heading_without_severity_counts_as_blocking(self) -> None:
        """R-026: a [DEFECT-###] with no stated severity blocks APPROVED rather than passing."""
        body = self.p0.replace("[DEFECT-001] [P0: Critical]", "[DEFECT-001]")
        result = self.validator.validate(self._report("**Review Status:** APPROVED", body))
        self.assertFalse(result["valid"])
        self.assertTrue(any("open P0/P1" in e for e in result["errors"]), result["errors"])

    def test_metadata_p3_on_defect_id_heading_allows_approved(self) -> None:
        """R-026 T4: a metadata P3 is not blocking, so APPROVED stands."""
        body = self.p0.replace("[DEFECT-001] [P0: Critical]", "[DEFECT-001]").replace(
            "- **Location**", "- **Severity:** P3: Low\n- **Location**")
        result = self.validator.validate(self._report("**Review Status:** APPROVED", body))
        self.assertFalse(any("open P0/P1" in e for e in result["errors"]), result["errors"])

    def test_conditionally_approved_with_p2_passes(self) -> None:
        p2 = self.p0.replace("[P0: Critical]", "[P2: Medium]")
        result = self.validator.validate(
            self._report("**Certification Verdict:** CONDITIONALLY APPROVED", p2))
        self.assertTrue(result["valid"], result["errors"])

    def test_template_option_list_is_not_a_verdict(self) -> None:
        result = self.validator.validate(
            self._report("**Review Status:** [ CHANGES REQUESTED | APPROVED ]", self.p0))
        self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
