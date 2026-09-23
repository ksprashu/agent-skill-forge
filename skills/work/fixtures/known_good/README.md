# `known_good` — the acceptance target

An honest implementation of the same surface as `../known_fake`. Every integrity
auditor in this repo must exit **0** on this directory.

Without this fixture, the cheapest way to pass the `known_fake` test is
`sys.exit(1)` unconditionally. See `docs/ENGINEERING_STANDARD.md` §4 (V2).

## What makes it honest

- Every function's return value is derived from its parameters.
- `merge_profiles` is implemented, not stubbed.
- The tests include **negative** cases (invalid band, empty evidence, conflicting
  merge) and a **differentiation** case asserting that opposite inputs produce
  different output — so a hardcoded reimplementation would fail the suite.
