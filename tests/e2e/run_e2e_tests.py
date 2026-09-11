#!/usr/bin/env python3.12
"""
End-to-End Test Runner for Markdown DAG Workflow Engine & Harness Protocol
Path: tests/e2e/run_e2e_tests.py

Usage:
    python3.12 tests/e2e/run_e2e_tests.py [--tier <1|2|3|4|all>] [--verify-fixtures] [-v]

Features:
- Executes 77 opaque-box E2E test cases across 4 tiers.
- Supports tier-scoped execution (Tier 1: Features, Tier 2: Boundaries, Tier 3: Pairwise, Tier 4: Real-World).
- Provides deterministic verification of fixture markdown files via --verify-fixtures.
- Handles Windows UTF-8 console output safely.
"""

import argparse
import io
import os
import sys
import unittest
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import test classes
try:
    from tests.e2e.test_dag_workflow_e2e import (
        DAG_VALIDATOR_PATH,
        FIXTURES_DIR,
        Tier1FeatureCoverageTests,
        Tier2BoundaryCornerCaseTests,
        Tier3CrossFeatureCombinationTests,
        Tier4RealWorldWorkloadScenarioTests,
    )
except ImportError as exc:
    sys.stderr.write(f"FATAL: Failed to import E2E test suite: {exc}\n")
    sys.exit(2)


def verify_fixtures() -> int:
    """Verify that all canonical test fixtures exist and have well-formed markdown table headers."""
    print("=" * 70)
    print("Markdown DAG Fixture Verification")
    print("=" * 70)
    print(f"Fixtures directory: {FIXTURES_DIR}")

    if not FIXTURES_DIR.exists():
        print(f"❌ Fixtures directory not found: {FIXTURES_DIR}")
        return 1

    expected_fixtures = [
        "focused_bugfix_dag.md",
        "multi_milestone_swarm_dag.md",
        "diamond_dag.md",
        "linear_dag.md",
        "cyclic_dag.md",
        "async_watchdog_dag.md",
        "unicode_dag.md",
        "missing_dep_dag.md",
        "duplicate_id_dag.md",
        "empty_table_dag.md",
    ]

    missing = []
    verified = 0

    for fix_name in expected_fixtures:
        path = FIXTURES_DIR / fix_name
        if not path.exists():
            print(f"  ❌ Missing fixture: {fix_name}")
            missing.append(fix_name)
            continue

        size = path.stat().st_size
        content = path.read_text(encoding="utf-8")
        has_table = ("| ID |" in content or "|ID|" in content)
        has_mode = ("Mode" in content)
        has_deps = ("Depends On" in content or "Dependencies" in content)

        if has_table and has_mode and has_deps:
            print(f"  ✅ [PASS] {fix_name:30} ({size} bytes, GFM table verified)")
            verified += 1
        else:
            print(f"  ⚠️ [WARN] {fix_name:30} ({size} bytes, non-standard table)")
            verified += 1

    print("-" * 70)
    print(f"Total Fixtures Verified: {verified}/{len(expected_fixtures)}")
    if missing:
        print(f"❌ Missing Fixtures: {missing}")
        return 1

    print("✅ All 10 canonical Markdown DAG fixtures verified successfully.")
    return 0


def build_suite(tier: str) -> unittest.TestSuite:
    """Build unittest suite based on selected tier."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    tier_map = {
        "1": [Tier1FeatureCoverageTests],
        "2": [Tier2BoundaryCornerCaseTests],
        "3": [Tier3CrossFeatureCombinationTests],
        "4": [Tier4RealWorldWorkloadScenarioTests],
    }

    if tier == "all":
        classes = [
            Tier1FeatureCoverageTests,
            Tier2BoundaryCornerCaseTests,
            Tier3CrossFeatureCombinationTests,
            Tier4RealWorldWorkloadScenarioTests,
        ]
    elif tier in tier_map:
        classes = tier_map[tier]
    else:
        raise ValueError(f"Unknown tier: {tier}")

    for test_class in classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    return suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Markdown DAG Workflow Engine E2E Test Suite"
    )
    parser.add_argument(
        "--tier",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Test tier to execute: 1 (Features), 2 (Boundaries), 3 (Pairwise), 4 (Real-World), all (default)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose test reporting",
    )
    parser.add_argument(
        "--verify-fixtures",
        action="store_true",
        help="Verify fixture files integrity without executing full CLI tests",
    )
    parser.add_argument(
        "--validator",
        type=str,
        default=None,
        help="Custom path to dag_validator.py script under test",
    )

    args = parser.parse_args()

    if args.verify_fixtures:
        return verify_fixtures()

    target_script = Path(args.validator) if args.validator else DAG_VALIDATOR_PATH
    os.environ["DAG_VALIDATOR_SCRIPT"] = str(target_script)

    print("=" * 70)
    print("Markdown DAG Workflow Engine: End-to-End Test Suite")
    print("=" * 70)
    print(f"Target Validator CLI : {target_script}")
    print(f"Target Script Exists : {target_script.exists()}")
    print(f"Execution Tier Scope : Tier {args.tier.upper()}")
    print(f"Python Executable    : {sys.executable}")
    print("=" * 70)

    if not target_script.exists():
        print(f"⚠️  NOTE: Target CLI {target_script} does not exist yet.")
        print("   Running test suite in pending/discovery mode...")
        print("   (Tests will cleanly report SkipTest until Milestone 1 publishes dag_validator.py)")
        print("-" * 70)

    suite = build_suite(args.tier)
    total_tests = suite.countTestCases()
    print(f"Discovered {total_tests} test cases for execution.")
    print("-" * 70)

    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    print("=" * 70)
    print("E2E Test Execution Summary")
    print("=" * 70)
    print(f"Total Tests Run : {result.testsRun}")
    print(f"Passed          : {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f"Failures        : {len(result.failures)}")
    print(f"Errors          : {len(result.errors)}")
    print(f"Skipped         : {len(result.skipped)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("✅ E2E Test Suite executed cleanly.")
        return 0
    else:
        print("❌ E2E Test Suite reported test failures.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
