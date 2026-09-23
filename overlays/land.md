## In the forge

`land` is the gate for anything a human has to read: docs, a README, a design write-up, a
release note, an analysis.

**It reports, it does not rewrite.** That is the point. `unslop` edits the text; `land` tells
you where the reading broke. Run `unslop` first, then `land` to find out whether it worked.

**Read it with `profile`.** If a cognitive profile exists, the quit points matter more than
the aggregate verdict — they tell you where *this* reader would have left, not where a
generic one would.

**Needs a live human and time.** It is excluded from non-interactive installs, and it is not
a pre-commit check. Use it before publishing, not on every save.
