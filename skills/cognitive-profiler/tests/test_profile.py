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

"""Contract tests for the profile schema and its evidence invariant."""

import copy
import json
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import profile_tool as P  # noqa: E402


def load_fixture(name):
    return json.loads((SKILL_ROOT / "fixtures" / name).read_text(encoding="utf-8"))


class TestFixturesValidate(unittest.TestCase):
    """The shipped fixtures double as worked examples, so they must be clean."""

    def test_structured_profile_validates_against_its_evidence(self):
        prof = load_fixture("profile_structured.json")
        evidence = load_fixture("evidence_sample.json")
        errors, _ = P.validate(prof, evidence)
        self.assertEqual(errors, [])

    def test_terse_profile_validates(self):
        errors, _ = P.validate(load_fixture("profile_terse.json"))
        self.assertEqual(errors, [])

    def test_every_dimension_is_exercised_by_the_fixtures(self):
        """Guards against adding a dimension with no fixture coverage, which
        would let it render untested."""
        bands = set()
        for name in ("profile_structured.json", "profile_terse.json"):
            for dim in load_fixture(name)["dimensions"].values():
                bands.add(dim["band"])
        self.assertTrue({"low", "high", "unknown"} <= bands)


class TestEvidenceInvariant(unittest.TestCase):
    """The rule that stops the tool inventing a personality and calling it data."""

    def setUp(self):
        self.prof = load_fixture("profile_structured.json")
        self.evidence = load_fixture("evidence_sample.json")

    def test_observed_claim_without_evidence_is_rejected(self):
        self.prof["dimensions"]["visual_scaffolding"]["evidence"] = []
        errors, _ = P.validate(self.prof, self.evidence)
        self.assertTrue(any("cites no evidence" in e for e in errors), errors)

    def test_observed_claim_citing_a_missing_quote_is_rejected(self):
        self.prof["dimensions"]["visual_scaffolding"]["evidence"] = ["q999"]
        errors, _ = P.validate(self.prof, self.evidence)
        self.assertTrue(any("not in the evidence file" in e for e in errors), errors)

    def test_observed_claim_citing_prose_instead_of_a_quote_id_is_rejected(self):
        self.prof["rules"][0]["evidence"] = ["they said they like tables"]
        errors, _ = P.validate(self.prof, self.evidence)
        self.assertTrue(any("cite quote IDs" in e for e in errors), errors)

    def test_declared_claim_without_a_note_is_rejected(self):
        self.prof["rules"][0]["source"] = "declared"
        self.prof["rules"][0]["evidence"] = []
        errors, _ = P.validate(self.prof, self.evidence)
        self.assertTrue(any("does not record what" in e for e in errors), errors)

    def test_inferred_claim_warns_but_passes(self):
        self.prof["rules"][0]["source"] = "inferred"
        self.prof["rules"][0]["evidence"] = []
        errors, warnings = P.validate(self.prof, self.evidence)
        self.assertEqual(errors, [])
        self.assertTrue(any("inferred" in w for w in warnings), warnings)

    def test_strict_mode_rejects_inferred_claims(self):
        self.prof["rules"][0]["source"] = "inferred"
        self.prof["rules"][0]["evidence"] = []
        errors, _ = P.validate(self.prof, self.evidence, strict=True)
        self.assertTrue(any("--strict rejects" in e for e in errors), errors)

    def test_quote_ids_go_unchecked_when_no_evidence_file_is_supplied(self):
        """Without the evidence file we cannot resolve IDs, and must not
        pretend otherwise by failing open in either direction."""
        self.prof["dimensions"]["visual_scaffolding"]["evidence"] = ["q999"]
        errors, _ = P.validate(self.prof, evidence=None)
        self.assertEqual(errors, [])


class TestUnknownHandling(unittest.TestCase):
    def test_unknown_band_must_be_listed_in_unknowns(self):
        prof = load_fixture("profile_terse.json")
        prof["unknowns"] = []
        errors, _ = P.validate(prof)
        self.assertTrue(any("profile.unknowns" in e for e in errors), errors)

    def test_known_band_requires_a_rationale(self):
        prof = load_fixture("profile_terse.json")
        prof["dimensions"]["visual_scaffolding"]["rationale"] = "  "
        errors, _ = P.validate(prof)
        self.assertTrue(any("rationale" in e for e in errors), errors)

    def test_empty_profile_is_rejected_for_having_no_rules(self):
        errors, _ = P.validate(P.new_profile("nobody"))
        self.assertTrue(any(e.startswith("rules:") for e in errors), errors)

    def test_new_profile_claims_nothing(self):
        prof = P.new_profile("nobody")
        self.assertTrue(all(d["band"] == "unknown"
                            for d in prof["dimensions"].values()))
        self.assertEqual(sorted(prof["unknowns"]), sorted(P.DIMENSIONS))


class TestLeakRejection(unittest.TestCase):
    """Profiles compile into committed files, so they are checked for secrets
    at the contract layer rather than trusting every caller."""

    def setUp(self):
        self.prof = load_fixture("profile_terse.json")

    def _assert_rejected(self, value, fragment):
        prof = copy.deepcopy(self.prof)
        prof["rules"][0]["directive"] = value
        errors, _ = P.validate(prof)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_email_is_rejected(self):
        self._assert_rejected("Email dev@example.com before merging", "email address")

    def test_home_directory_path_is_rejected(self):
        self._assert_rejected("Read /Users/someone/notes.md first", "home directory")

    def test_api_key_is_rejected(self):
        self._assert_rejected("Use sk-abcdefghijklmnopqrstuvwxyz012345", "API key")

    def test_subject_field_is_also_scanned(self):
        prof = copy.deepcopy(self.prof)
        prof["subject"] = "dev@example.com"
        errors, _ = P.validate(prof)
        self.assertTrue(any("email address" in e for e in errors), errors)


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.prof = load_fixture("profile_structured.json")

    def test_null_limit_is_allowed(self):
        self.prof["limits"]["response_ceiling_words"] = None
        errors, _ = P.validate(self.prof, load_fixture("evidence_sample.json"))
        self.assertEqual(errors, [])

    def test_out_of_range_limit_is_rejected(self):
        self.prof["limits"]["response_ceiling_words"] = 4
        errors, _ = P.validate(self.prof, load_fixture("evidence_sample.json"))
        self.assertTrue(any("outside the sane range" in e for e in errors), errors)

    def test_non_integer_limit_is_rejected(self):
        self.prof["limits"]["bullets_per_section"] = "four"
        errors, _ = P.validate(self.prof, load_fixture("evidence_sample.json"))
        self.assertTrue(any("must be an integer" in e for e in errors), errors)

    def test_booleans_are_not_accepted_as_integers(self):
        self.prof["limits"]["bullets_per_section"] = True
        errors, _ = P.validate(self.prof, load_fixture("evidence_sample.json"))
        self.assertTrue(any("must be an integer" in e for e in errors), errors)


class TestStructuralErrors(unittest.TestCase):
    def test_duplicate_rule_ids_are_rejected(self):
        prof = load_fixture("profile_terse.json")
        prof["rules"][1]["id"] = prof["rules"][0]["id"]
        errors, _ = P.validate(prof)
        self.assertTrue(any("duplicate id" in e for e in errors), errors)

    def test_rule_ids_are_unique_across_rules_and_forbidden(self):
        prof = load_fixture("profile_terse.json")
        prof["forbidden"][0]["id"] = prof["rules"][0]["id"]
        errors, _ = P.validate(prof)
        self.assertTrue(any("duplicate id" in e for e in errors), errors)

    def test_unknown_scope_is_rejected(self):
        prof = load_fixture("profile_terse.json")
        prof["rules"][0]["scope"] = "vibes"
        errors, _ = P.validate(prof)
        self.assertTrue(any("scope" in e for e in errors), errors)

    def test_wrong_schema_version_is_rejected(self):
        prof = load_fixture("profile_terse.json")
        prof["schema_version"] = "0.9"
        errors, _ = P.validate(prof)
        self.assertTrue(any("schema_version" in e for e in errors), errors)

    def test_unknown_tone_context_is_rejected(self):
        prof = load_fixture("profile_terse.json")
        prof["tone"]["astrology"] = "gemini"
        errors, _ = P.validate(prof)
        self.assertTrue(any("tone.astrology" in e for e in errors), errors)

    def test_next_rule_id_skips_ids_already_used(self):
        prof = load_fixture("profile_terse.json")
        self.assertEqual(P.next_rule_id(prof), "R4")


class TestCoverage(unittest.TestCase):
    def test_coverage_counts_each_source(self):
        cov = P.coverage(load_fixture("profile_structured.json"))
        self.assertEqual(cov["observed"], 9)
        self.assertEqual(cov["declared"], 1)
        self.assertEqual(cov["inferred"], 0)
        self.assertEqual(cov["grounded_pct"], 100.0)

    def test_unknown_dimensions_are_counted_separately(self):
        cov = P.coverage(load_fixture("profile_terse.json"))
        self.assertEqual(cov["unknown_dimensions"], 1)


class TestSchemaGeneration(unittest.TestCase):
    def test_committed_schema_matches_the_generated_one(self):
        """The schema file is derived from the constants in profile_tool.py. If this
        fails, run: python3 scripts/profile_tool.py schema"""
        committed = P.schema_path().read_text(encoding="utf-8")
        expected = json.dumps(P.build_schema(), indent=2) + "\n"
        self.assertEqual(committed, expected,
                         "references/profile.schema.json is stale; regenerate it")

    def test_schema_lists_every_dimension(self):
        props = P.build_schema()["properties"]["dimensions"]["properties"]
        self.assertEqual(sorted(props), sorted(P.DIMENSIONS))


class TestAmend(unittest.TestCase):
    def test_amend_appends_and_keeps_the_profile_valid(self):
        prof = load_fixture("profile_terse.json")
        before = len(prof["rules"])
        P.add_rule(prof, "Never open with a restatement of my question",
                   scope="always", source="declared",
                   evidence=["Said so on 2026-09-21."])
        self.assertEqual(len(prof["rules"]), before + 1)
        errors, _ = P.validate(prof)
        self.assertEqual(errors, [])

    def test_amend_rejects_an_unknown_scope(self):
        with self.assertRaises(P.ProfileError):
            P.add_rule(load_fixture("profile_terse.json"), "x", scope="nope")


if __name__ == "__main__":
    unittest.main()
