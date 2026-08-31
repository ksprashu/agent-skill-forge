# Task 06: Build Deterministic Test Suite & Run Validation

## Objective
Implement pytest unit test suites to verify transcript parsing, rule extraction, line capping, and hook protocol execution.

## Files to Create
- `skills/continuous-alignment/tests/test_distill.py`
- `skills/continuous-alignment/tests/test_sync_rules.py`

## Validation Steps
- Run `pytest skills/continuous-alignment/tests/`.
- Run `python scripts/validate_skills.py` to ensure zero frontmatter or PII lint errors.
- Test simulated hook invocation with sample JSON payloads via stdin.
