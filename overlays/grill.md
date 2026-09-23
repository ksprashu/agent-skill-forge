## In the forge

`grill` is the first gate. Nothing downstream is trustworthy if the ask is still fuzzy.

**Stop condition.** The upstream rule is an empty frontier. Add one test to it: before you
declare the frontier empty, write down what you think the user wants in one sentence and a
confidence number. Under 95%, you have a question left. Say the number out loud.

**Write it down.** When the frontier empties, save the settled tree to
`docs/understand/<slug>.md`. A grilling that only lives in chat scroll is lost by tomorrow.

**Next.** Hand the settled tree to `done` to turn it into acceptance criteria. Do not go
straight to `brainstorm` — a design without written done criteria has nothing to be checked
against.

**Related:** `echo` if the ask arrived as a ramble. `doubt` if a single decision needs
attacking rather than the whole tree.
