# When to escalate

Read this before posting `/ai-review escalate:`. Escalation pulls a human in and
holds the PR red until they act. It's the right move when the automated loop
can't converge. It's the wrong move when it's a way to skip a fix.

`review_state.py` gives you `escalation_signals`: facts such as "R-001
reopened 2 times" or "2 wontfix replies each answered without
accepted_pushback". A signal is a reason to look, not a reason to escalate.
You decide, using the tests below.

## Legitimate: the loop is stuck

Escalate when at least one of these holds **and** you have already done your
part (a real fix attempt, or a wontfix with concrete evidence):

1. **Repeated rejection with no new argument.** You posted a wontfix with
   evidence. The reviewer rejected it, you answered the rejection with more
   evidence, and the next round repeats the original claim without engaging.
   *Example:* you cite `keys.py:3` showing the dict is bounded by a 16-member
   Enum. The reviewer says "still unbounded" twice and never mentions the Enum.
2. **Self-contradiction across rounds.** Round 2 asks for X, round 3 flags X as
   a defect. *Example:* R-007 asks you to catch `ValueError` at the call site.
   After you do, R-011 flags "broad exception handling at the call site".
3. **Out-of-scope rewrite.** The finding demands a redesign unrelated to the
   PR's purpose, and you have already offered a follow-up issue. *Example:* a
   one-line dependency bump gets a P1 asking to migrate the ORM.
4. **Three or more rounds on the same point** (`open_across_rounds`,
   `finding_reopened_repeatedly`) where each round you changed something
   material and the reviewer's objection did not move.
5. **Factual impossibility.** The finding cites code or a file that doesn't
   exist at the head SHA, and pushback pointing this out was rejected.

## Lazy: don't escalate

- **First rejection.** One counter-argument from the reviewer is normal. Read
  it. It may be right. Reply to the substance or fix.
- **The fix is just tedious.** Size of work is not a disagreement.
- **Your wontfix had no evidence.** "I disagree" rejected twice is your
  problem, not the reviewer's. Write a real reason first (see
  `references/commands.md`).
- **The reopen was earned.** If the reviewer reopened a thread because your fix
  didn't land (wrong branch, not pushed, fixed a different line), fix it.
- **To beat the clock.** Escalating to merge faster defeats the point of the
  check.
- **Nits.** Nits never block, so there is nothing to escalate.
- **P0/P1 security findings you haven't disproved.** Fix them, or show with
  evidence why they're false. Don't hand an unexamined vulnerability to a
  human as a "disagreement".

## Writing the escalation

One PR comment. Include:

- The finding ids involved.
- The rounds (from `rounds` and the thread history).
- What you argued and what evidence you gave, with links to the thread replies.
- What the reviewer said in response, and why it doesn't engage.
- The decision you're asking the owner to make.

```
/ai-review escalate: R-004 (P2) open 3 rounds. Round 1 wontfix cited keys.py:3
(Enum with 16 members bounds the dict). Rounds 2 and 3 repeat "unbounded cache"
without addressing the Enum. Asking the owner to accept the pushback or name the
case where the dict grows past 16.
```

After escalating, **stop pushing changes aimed at that finding.** Keep fixing
other open findings if any remain, then report and wait. The owner either
applies `human-override` or tells you what to change.
