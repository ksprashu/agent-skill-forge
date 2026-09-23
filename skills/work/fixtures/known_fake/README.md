# `known_fake` — the regression target

This is a deliberately faked project. It is **not** broken code: it imports, it
runs, and `python3 -m pytest tests/` passes cleanly.

It is here because a verifier that cannot reject it is decorative. Every
integrity auditor in this repo is tested against this directory and must exit
non-zero on it. See `docs/ENGINEERING_STANDARD.md` §4 (V1).

## What is faked

| File | Defect |
|---|---|
| `src/evaluator.py` `evaluate()` | Ignores its `evidence` argument entirely; returns a hardcoded dict. This is the exact shape of the `psychometric_evaluator.py` that shipped in `cognitive-profiler` and passed review. |
| `src/evaluator.py` `confidence()` | Returns a literal float regardless of input. |
| `src/evaluator.py` `merge_profiles()` | Declared, never implemented — `pass`. |
| `src/pipeline.py` `run()` | Computes a result, discards it, returns a constant. |
| `tests/test_evaluator.py` | Asserts key presence and truthiness only. No test constrains the relationship between input and output, so every mutant survives. |

## Do not "fix" this directory

Making it honest defeats its purpose. If a change to an auditor makes this
directory pass, the auditor regressed.
