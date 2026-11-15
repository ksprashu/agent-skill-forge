# pr-guardian command and marker grammar

Read this before posting your first reply on a PR that pr-guardian reviews, or
before running `restack.py` / `merge_pr.py`.

## Commands you post

Commands are matched at the **start of a line**, case-insensitive, and
everything after the colon up to the end of that line is the argument. One
command per comment. Put any extra explanation on later lines.

| Command | Where | Who | Effect |
|---|---|---|---|
| `/ai-review wontfix: <reason>` | Reply **inside the finding's thread** | PR author | Next round the reviewer weighs the reason. It either accepts (replies "Pushback accepted" with status `accepted_pushback`; you then resolve the thread, and it is never re-raised) or rejects with a counter-argument and the thread stays open. |
| `/ai-review escalate: <why>` | **PR comment** (conversation tab), not a thread | PR author | The bot adds the `needs-human` label. `pr-guardian/verdict` stays failing until the owner applies `human-override`. |
| `/ai-review` (alone) | PR comment | Repo owner only | Forces a re-review without a push. Coming from anyone else it does nothing, so don't post it. |

### Grammar

```
wontfix   := "/ai-review" WS "wontfix:" WS? reason
escalate  := "/ai-review" WS "escalate:" WS? why
rerun     := "/ai-review" EOL
reason    := non-empty text on the same line
```

An empty `reason` gives the reviewer nothing to weigh. `reply.py` refuses it.

### Good wontfix reasons

```
/ai-review wontfix: False positive. `user_id` comes from the verified session (middleware/auth.py:52), never from the request body, so this is not an IDOR.
/ai-review wontfix: Out of scope for this PR (dependency bump only). Tracked in #418 with the repro.
/ai-review wontfix: Intentional. The O(n^2) loop runs on at most 8 shards (config/limits.py:12); rationale recorded in docs/adr/0007-shard-merge.md.
```

### Bad wontfix reasons (expect rejection, and don't post these)

```
/ai-review wontfix: I disagree.
/ai-review wontfix: This is fine.
/ai-review wontfix: Will fix later.           (no linked issue)
/ai-review wontfix: Tests pass.               (passing tests don't refute a finding)
```

### Fixed replies

Not a command. A plain reply so the reviewer and humans can trace the fix:

```
Fixed in a1b2c3d. Cache key now includes tenant_id; test_cache_isolation covers it.
```

`reply.py --fixed <sha> --note "<what changed>"` writes exactly this.

### Escalation comment

```
/ai-review escalate: R-004 re-raised for the 3rd round with the same argument after
wontfix citing keys.py:3 (bounded Enum). No new evidence in rounds 2-3. Requesting
an owner decision.
```

Name the finding ids, the rounds, and what was already argued.

## Markers pr-guardian writes (read by `review_state.py`)

Hidden HTML comments. Don't write them yourself. A forged marker is gaming
the reviewer.

| Marker | Where |
|---|---|
| `<!-- pr-guardian:finding id=R-001 severity=P1 -->` | First line of a finding thread's first comment. `id` matches `^[A-Z][A-Z0-9]*-[0-9]{3,}$`; `severity` is `P0`-`P3` (or `nit`). Fields may be in any order. |
| `<!-- pr-guardian:status id=R-001 status=reopened -->` | In a pr-guardian reply. `status` is one of `new`, `still_open`, `reopened`, `fixed`, `accepted_pushback`. `fixed` comes with "Verified fixed" and `accepted_pushback` with "Pushback accepted": once the **latest** pr-guardian reply in a thread carries one of those two, the PR author resolves the thread (`resolve.py`). pr-guardian itself never resolves. |
| `<!-- pr-guardian:nits -->` | The single nits summary PR comment. |

A thread whose first comment has a pr-guardian marker that is not well-formed
on the first line is reported under `threads.unparsed` with a reason. It still
blocks the merge. Read it by hand.

## Helper invocations

### Review state, replies, and thread resolution

```bash
python3 <skill-dir>/scripts/review_state.py --pr 42 [--repo owner/name]
python3 <skill-dir>/scripts/review_state.py --pr 42 --check-name "pr-guardian/verdict" --bot-login my-app
python3 <skill-dir>/scripts/review_state.py --from-file response.json --allow-unknown-mergeable
python3 <skill-dir>/scripts/reply.py --thread-id PRRT_kwDO... --fixed a1b2c3d --note "..."
python3 <skill-dir>/scripts/reply.py --thread-id PRRT_kwDO... --wontfix "..." --dry-run
python3 <skill-dir>/scripts/resolve.py --pr 42 --thread-id PRRT_kwDO...   # only after status=fixed|accepted_pushback
gh pr comment 42 --body "/ai-review escalate: ..."
gh pr checks 42 --watch
```

Thread ids (`PRRT_...`) come from `threads.open[].thread_id` in the
`review_state.py` output; the ones you may resolve are in
`threads.ready_to_resolve[].thread_id`.

### Stack restacking (`restack.py`)

```bash
# Single PR: dry-run (default) vs apply
python3 <skill-dir>/scripts/restack.py --pr 42 [--repo owner/name] --dry-run
python3 <skill-dir>/scripts/restack.py --pr 42 [--repo owner/name] --apply
python3 <skill-dir>/scripts/restack.py --pr 42 --strategy rebase --apply --push --force-with-lease

# Offline / fixture-backed single-PR restack
python3 <skill-dir>/scripts/restack.py --pr 42 --from-file context.json --repo-dir . --remote origin --no-fetch --apply

# Post-merge topological cascade across open same-repo PRs (isCrossRepository == false)
python3 <skill-dir>/scripts/restack.py --cascade --merged-pr 40 [--repo owner/name] --dry-run
python3 <skill-dir>/scripts/restack.py --cascade --merged-pr 40 [--repo owner/name] --apply
```

Flags: `--pr`, `--cascade`, `--merged-pr`, `--repo`, `--repo-dir`, `--remote`,
`--from-file`, `--strategy` (`merge` | `rebase`), `--no-fetch`, `--push`,
`--force-with-lease` (only with `--strategy rebase`), `--dry-run`, `--apply`.
Exit codes: `0` clean / applied, `1` conflict (aborted cleanly; `conflicting_files`
in stdout) / dirty tree / branch mismatch / cycle / unsafe ref, `2` git/gh/file
error, `64` usage error.

### Pre-merge L3 gate and squash merge (`merge_pr.py`)

```bash
python3 <skill-dir>/scripts/merge_pr.py --pr 42 [--repo owner/name] --dry-run
python3 <skill-dir>/scripts/merge_pr.py --pr 42 [--repo owner/name] --execute
python3 <skill-dir>/scripts/merge_pr.py --pr 42 [--repo owner/name] --auto --execute
python3 <skill-dir>/scripts/merge_pr.py --from-file response.json --no-delete-branch --dry-run
```

Flags: `--pr`, `--repo`, `--from-file`, `--check-name`, `--bot-login`, `--auto`,
`--no-delete-branch`, `--dry-run` (default), `--execute`.
Exit codes: `0` ready / merged, `1` refused (open threads, `CONFLICTING`,
`DIRTY`, `BLOCKED`, `UNKNOWN`, non-passing check, or `needs-human`), `2` gh/API
error, `64` usage error.
