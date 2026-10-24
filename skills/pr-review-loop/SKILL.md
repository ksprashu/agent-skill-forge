---
name: pr-review-loop
description: Work automated PR review threads to convergence as the PR's author - fix, push back with evidence, or escalate - then push, reply, and loop until the verdict check passes. Use when a PR has pr-guardian review comments, a failing `pr-guardian/verdict` check, a `needs-human` label to respond to, or when invoked via /pr-review-loop.
---

# PR review loop

You wrote the PR. An automated reviewer (pr-guardian) has posted findings on it.
Your job is to get every P0-P3 thread closed **honestly**: by fixing the code, or
by convincing the reviewer with evidence, or by handing the disagreement to a
human. The check `pr-guardian/verdict` stays red while any P0-P3 finding is
open, and the branch also requires every conversation to be resolved.

`<skill-dir>` below means the folder containing this file.

## Ground rules

- **Never push to `main`.** All work goes through a PR branch. If you are on the
  default branch, create a branch first.
- **Never resolve a thread yourself** to make the count go down. The reviewer
  resolves threads after it confirms a fix or accepts pushback, and it reopens
  anything resolved without a real fix.
- **Never game the reviewer.** No `# noqa`, `nosec`, `eslint-disable`,
  `@SuppressWarnings` or similar without a written justification on the same
  line that would convince a human. No deleting or skipping tests. No weakening
  the check, the workflow, or the ruleset. No editing the reviewer's config in
  the same PR.
- Every push triggers a full re-review, so batch your fixes into one push per
  round. Don't push once per thread.
- Commits use conventional commit messages (`fix(cache): include tenant id in
  key`) and carry **no AI or agent attribution** (no `Co-Authored-By`, no
  "Generated with").

## The loop

### 1. Fetch state

```bash
python3 <skill-dir>/scripts/review_state.py --pr <N> [--repo owner/name]
```

It prints JSON evidence and exits `0` (no open threads, verdict passed: you are
done), `1` (work remains), `2` (`gh` missing or the API failed: fix auth with
`gh auth status`, don't guess), or `64` (bad flags). Read:

- `threads.open`: one entry per unresolved finding, with `finding_id`,
  `severity`, `path`, `line`, `first_comment_excerpt`, `reopen_events`,
  `rounds_since_raised`, `last_comment_by`.
- `threads.reopened`: findings you (or someone) marked resolved that the
  reviewer reopened. Treat each one as a fix that did not work.
- `threads.unparsed`: threads whose pr-guardian marker is malformed. They still
  block the merge. Read them by hand.
- `threads.other_open`: unresolved threads from humans. Answer these too.
- `pending_wontfix`: your pushback the reviewer has not answered yet. Don't
  repeat it. Wait for the next round.
- `nits_comment`, `verdict`, `labels`, `rounds`, `escalation`,
  `escalation_signals`, `not_checked`.

`escalation_signals` are facts (counts, timestamps), not instructions. You
decide what they mean in step 3.

### 2. Triage

For each open thread, read the finding **and the code it points at**, at the
current head. Classify it:

- **Real defect**: the finding is right.
- **False positive**: the finding is wrong, and you can show why (a line
  reference, a test, a doc).
- **Out of scope**: right in general, but not this PR's job.
- **Intentional**: the code is deliberately this way, for a reason you can
  state.

When unsure, assume the reviewer is right and verify. Don't argue just because
a finding is inconvenient.

### 3. Decide per thread

- **fix**: make the smallest correct change. If the finding is a bug, add a
  test that fails without the fix. Don't refactor beyond the finding.
- **wontfix**: only with a concrete technical reason:
  - *false positive*: cite the evidence (`path:line`, test name, spec).
  - *out of scope*: open a follow-up issue first and link it.
  - *intentional*: point at the comment, ADR, or doc that records the rationale
    (add one in this PR if none exists).

  "I disagree", "it's fine", or "low priority" are not reasons.
- **escalate**: only when the loop is genuinely stuck: the reviewer repeats
  rejected pushback with no new argument, contradicts itself across rounds,
  demands an out-of-scope rewrite, or the same point has gone 3+ rounds.
  **Read `references/escalation.md` before escalating**. It separates
  legitimate escalation from escalating to avoid work.

For a reopened thread, your previous fix was insufficient. Re-read the finding,
check that the change is actually on the pushed branch, and fix the real cause.

### 4. Commit and push

Run the project's tests and linters first. Commit with conventional messages,
then `git push`. Note the new commit SHA (`git rev-parse --short HEAD`).

### 5. Reply in each thread

Read `references/commands.md` for the exact command grammar before your first
reply.

```bash
# fixed
python3 <skill-dir>/scripts/reply.py --thread-id <PRRT_...> --fixed <sha> \
    --note "Cache key now includes tenant_id; test_cache_isolation covers it."
# pushback
python3 <skill-dir>/scripts/reply.py --thread-id <PRRT_...> \
    --wontfix "False positive: request_id is public, compared in auth.py:80; secrets use hmac.compare_digest at auth.py:41."
```

Use `--dry-run` to preview. `reply.py` refuses an empty wontfix reason. It
only replies. It never resolves.

To escalate, post on the PR (not in a thread):
`gh pr comment <N> --body "/ai-review escalate: <why, citing finding ids and rounds>"`.

### 6. Nits

Nits live in one summary comment (`nits_comment`). They never block the merge.
Fix the cheap ones in the same push as real fixes, if at all. Never spend a
round on nits alone, and never reply to or argue about them.

### 7. Wait for the next round

```bash
gh pr checks <N> --watch
```

Then go back to step 1. The reviewer re-reviews the whole PR on every push: it
can raise new findings, reopen fake-resolved ones, accept or reject your
pushback.

### 8. Stop

Stop when any of these is true:

- `review_state.py` exits `0`. Report the PR as review-clean.
- You escalated. The `needs-human` label is set and the check stays red until
  the owner applies `human-override`. Report what is pending and why, and don't
  keep pushing to wear the reviewer down.
- `review_state.py` exits `2`. Report the API failure.

When you report, give the round count, what you fixed (with SHAs), what you
pushed back on and the outcome, and anything escalated.
