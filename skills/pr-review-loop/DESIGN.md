# Design notes (`pr-review-loop`)

Why `pr-review-loop` is structured around deterministic L3 scripts, exact-tree
squash detection, and fail-closed merge gates. Read `SKILL.md` for usage.

---

## 1. Why review-clean is not merge-ready

`review_state.py` previously reported only review threads and `pr-guardian/verdict`.
A PR with zero open threads and a green `pr-guardian/verdict` could still exit
`0` while carrying `mergeable=CONFLICTING` or `mergeStateStatus=DIRTY`, causing
agents to declare the PR done when GitHub refused to merge it.

Now:

- `review_state.py` fetches `mergeable`, `mergeStateStatus`, `headRefOid`, and
  `baseRefOid`, surfaces them under `"merge"`, and exits `1` whenever
  `mergeable == "CONFLICTING"`, `mergeStateStatus == "DIRTY"`, or `mergeable`
  is `"UNKNOWN"` (unless `--allow-unknown-mergeable` is explicitly passed for
  legacy offline JSON responses).
- `merge_pr.py` separates review cleanliness from full merge readiness: even
  when `review_state.py` exits `0`, `merge_pr.py` still refuses (`exit 1`)
  unless `state == "OPEN"`, `mergeable == "MERGEABLE"`, `mergeStateStatus` is
  `CLEAN` or `HAS_HOOKS` (rejecting `BLOCKED`, `BEHIND`, `UNSTABLE`, `DRAFT`),
  and every check in `statusCheckRollup` is `COMPLETED` with a passing
  conclusion (`SUCCESS`, `NEUTRAL`, or `SKIPPED`). Passing `--auto` preserves
  those exact L3 preconditions and only forwards `--auto` to `gh pr merge`.

## 2. Why squash-merge stacks conflict — and why `-s ours` is guarded by tree OIDs

When PR `#1` (`H1`) is squash-merged into `main`, GitHub creates a new squash
commit `S1` whose tree equals `H1^{tree}` but whose parent is `main`, not `H1`.
Stacked PR `#2` (`H2`, branched from `H1`) still contains `H1` in its ancestry.
Running a plain `git merge origin/main` compares `M0..H2` against `M0..S1` and
frequently triggers false conflicts on lines touched in `#1` and `#2`.

Blindly running `git merge -s ours origin/main` would silently discard unrelated
commits that landed on `main` after `S1`. To make `-s ours` mathematically safe:

1. `restack.py` checks `git merge-base --is-ancestor <merged_head_oid> HEAD`.
2. It runs `-s ours` against `origin/<base>` **only** when
   `<merged_head_oid>^{tree} == origin/<base>^{tree}`.
3. If `origin/<base>` moved further ahead, it checks whether `mergeCommit.oid`
   has `<merged_head_oid>^{tree} == <mergeCommit>^{tree}` and is an ancestor of
   `origin/<base>`; if so, it records `-s ours` up to `mergeCommit.oid` and then
   runs a real `git merge --no-edit origin/<base>`, rolling back `HEAD`
   atomically on conflict.
4. In all other cases it runs normal `git merge --no-edit` (or `git rebase`),
   aborting cleanly on conflict and outputting `conflicting_files` as JSON with
   exit `1` so the author resolves semantic conflicts explicitly.

## 3. Security boundaries (`S4`, `S8`, `CWE-88`, fork isolation)

- Every `git` and `gh` command runs with `shell=False` and list `argv`.
- Branch/remote refs (`headRefName`, `baseRefName`, `--remote`) are validated
  with `validate_ref` before hitting `git` or `gh`, rejecting `-`-prefixed refs
  (`CWE-88` flag injection), control characters, `..`, `@{`, and `.lock`.
- `--cascade` filters strictly for `isCrossRepository is False`, recording fork
  PRs in `skipped_forks` rather than attempting cross-repo restacks.
- Secret/token redaction (`S8`) runs at ingest in `_run_cmd` and `load_json_file`.
- Rebase pushes require explicit `--force-with-lease` under `--strategy rebase`;
  bare `git push --force` is never emitted.
