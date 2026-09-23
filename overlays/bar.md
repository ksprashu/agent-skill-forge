## In the forge

`bar` writes the project's quality floor down once, with numbers, so it stops being
re-argued per pull request.

**Where it lands.** `CONSTRAINTS.md` at the repo root.

**Scope split.** `bar` is project-wide and durable. `done` is per-change and specific. Both
feed `prove`; neither replaces the other.

**The watch matters more than the write.** The second half of this skill — spotting a new
`@ts-ignore`, a skipped test, a deleted assertion, a threshold edited down — is the part that
earns its place. A CONSTRAINTS.md nobody enforces is decoration.

**Pairs with `scope`:** `bar` catches the quality bar dropping, `scope` catches the change
growing. Different failures, both invisible in a green build.
