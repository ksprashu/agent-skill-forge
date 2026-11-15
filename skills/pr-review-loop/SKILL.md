---
name: pr-review-loop
description: Work automated PR review threads, merge conflicts, squash-merged stacks, and pre-merge checks to `--squash` / `--auto --squash` convergence as the PR's author. Use when a PR has pr-guardian review comments, a failing `pr-guardian/verdict` check, `CONFLICTING`/`DIRTY` squash-stack conflicts, a `needs-human` label, or when invoked via /pr-review-loop.
---

# PR review loop

You wrote the PR. An automated reviewer (pr-guardian) has posted findings on it,
or an upstream PR in your stack merged and left this branch behind or
conflicting. Your job is to get every P0-P3 thread closed **honestly** and
converge to a conflict-free, green merge state (`--squash` or `--auto --squash`).
The check `pr-guardian/verdict` stays red while any P0-P3 finding is open, and
branch rules require resolved conversations and zero conflicts.

`<skill-dir>` below means the folder containing this file.

## Ground rules

- **Never push to `main`.** All work goes through a PR branch. If you are on the
  default branch, create a branch first.
- **Never resolve a thread the reviewer hasn't verified.** pr-guardian replies
  `pr-guardian:status ... status=fixed|accepted_pushback` when verified; only
  then resolve with `resolve.py`. Resolving earlier marks it `reopened`.
- **Never game the reviewer.** No `# noqa`, `nosec`, `eslint-disable`, or
  `@SuppressWarnings` without inline justification. No skipped tests or rule
  weakening.
- **Never guess `-s ours` or force-push blindly.** Use `restack.py` (uses
  `-s ours` only when `headRefOid^{tree} == origin/<base>^{tree}`); use
  `--force-with-lease` only under explicit `--strategy rebase`.
- **Batch fixes into one push per round**, with conventional commits (`fix(cache):
  ...`) and **zero AI or agent attribution** (`Co-Authored-By`, etc.).

## The loop

### 1. Fetch state and merge readiness

```bash
python3 <skill-dir>/scripts/review_state.py --pr <N> [--repo owner/name]
```

It prints JSON evidence and exits `0` (no open threads, `mergeable` clean,
verdict `SUCCESS`), `1` (work, conflicts, or `UNKNOWN` mergeability remains), `2`
(`gh`/API failure), or `64` (bad flags). Read:

- `merge`: `mergeable` (`MERGEABLE|CONFLICTING|UNKNOWN`), `merge_state`
  (`CLEAN|DIRTY|BLOCKED|BEHIND|UNSTABLE|UNKNOWN`), `head_oid`, `base_oid`.
  Exits `1` if `CONFLICTING`, `DIRTY`, or `UNKNOWN` (unless
  `--allow-unknown-mergeable` is passed for legacy offline fixtures).
- `threads.open`, `threads.reopened`, `threads.ready_to_resolve`,
  `threads.unparsed`, `threads.other_open`, `pending_wontfix`.
- `nits_comment`, `verdict`, `labels`, `rounds`, `escalation`,
  `escalation_signals` (facts only), `not_checked`.

### 1a. Resolve what the reviewer verified

For each entry in `threads.ready_to_resolve`:

```bash
python3 <skill-dir>/scripts/resolve.py --pr <N> --thread-id <PRRT_...> [--repo owner/name]
```

`resolve.py` refuses (exit `1`) unless pr-guardian's latest reply in the thread
is `status=fixed` or `status=accepted_pushback`.

### 1b. Restack behind or conflicting PRs (squash-stack aware)

Read `references/commands.md` before running `restack.py` or `merge_pr.py`.
When `merge.mergeable == "CONFLICTING"` or `merge.merge_state` is `DIRTY`/`BEHIND`:

```bash
python3 <skill-dir>/scripts/restack.py --pr <N> [--repo owner/name] --dry-run
python3 <skill-dir>/scripts/restack.py --pr <N> [--repo owner/name] --apply
```

- If a recently merged PR's `headRefOid` is already an ancestor of `HEAD` and
  `headRefOid^{tree} == origin/<base>^{tree}`, `--apply` runs
  `merge -s ours` cleanly without replaying squashed hunks.
- Otherwise it runs `git merge --no-edit origin/<base>` (or `rebase` with
  `--strategy rebase`). On conflict it aborts cleanly, prints `conflicting_files`
  as JSON, and exits `1` so you resolve the conflicts semantically and test.
- After merging a lower PR `#M` in a stack, preview or run cascade restack in
  topological order for same-repo PRs (`isCrossRepository == false`):
  `python3 <skill-dir>/scripts/restack.py --cascade --merged-pr <M> --dry-run`.

### 2. Triage

For each open thread, read the finding and code at `HEAD`. Classify as **Real
defect**, **False positive**, **Out of scope**, or **Intentional**. When unsure,
verify assuming the reviewer is right.

### 3. Decide per thread

- **fix**: smallest correct change plus a regression test.
- **wontfix**: concrete technical evidence (`path:line`, test, ADR, or follow-up
  issue for out-of-scope). Never argue "I disagree" or "tests pass".
- **escalate**: only when genuinely stuck (repeated rejection without new
  argument, contradiction, out-of-scope rewrite, 3+ rounds). **Read
  `references/escalation.md` before escalating.**

### 4. Commit and push

Run the repo's tests and linters first. Commit with conventional messages, then
`git push` (or `--force-with-lease` only after an explicit rebase).

### 5. Reply in each thread

Read `references/commands.md` for exact reply and marker grammar before posting:

```bash
python3 <skill-dir>/scripts/reply.py --thread-id <PRRT_...> --fixed <sha> \
    --note "Cache key now includes tenant_id; test_cache_isolation covers it."
python3 <skill-dir>/scripts/reply.py --thread-id <PRRT_...> \
    --wontfix "False positive: request_id is public at auth.py:80."
```

To escalate, comment on the PR:
`gh pr comment <N> --body "/ai-review escalate: <why, citing ids and rounds>"`.

### 6. Nits

Nits (`nits_comment`) never block merge. Bundle cheap ones into real-fix pushes;
never spend a round on nits alone or argue about them.

### 7. Wait for the next round

```bash
gh pr checks <N> --watch
```

Return to step 1 after checks finish.

### 8. Pre-merge gate and stop

When `review_state.py` exits `0`, verify deterministic merge readiness with
`merge_pr.py` (refuses if any thread, conflict, `BLOCKED`/`DIRTY` state, or check
is non-passing):

```bash
python3 <skill-dir>/scripts/merge_pr.py --pr <N> [--repo owner/name] [--auto] --dry-run
python3 <skill-dir>/scripts/merge_pr.py --pr <N> [--repo owner/name] [--auto] --execute
```

Stop when:
- `merge_pr.py` passes (or merges via `--squash` / `--auto --squash`), or
  `review_state.py` exits `0` when you were asked only to get review-clean.
- You escalated (`needs-human` active): stop pushing until `human-override`.
- A script exits `2` (`gh`/API error) or `restack.py` exits `1` on semantic
  conflicts requiring author edits.

Report round count, fixed SHAs, restacks/cascade results, pushback outcomes, and
merge readiness or escalation status.
