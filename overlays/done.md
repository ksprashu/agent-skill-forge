## In the forge

`done` produces the artefact the rest of the spine checks against. Without it, `prove` has
nothing to prove and `scope` has no intent to compare a diff to.

**Where it lands.** `docs/understand/<slug>-acceptance.md`, or `ACCEPTANCE.md` at the repo
root for whole-project criteria. One file, versioned, not a chat message.

**The hard gate reads this.** If `hooks/design_gate.py` is enabled, an architectural change
with no acceptance file will be blocked before the first edit. That is deliberate.

**Split of duties.**

| Question | Skill |
| :--- | :--- |
| What does this specific change have to do? | `done` |
| What bar does *all* code in this project clear? | `bar` |
| Did we actually hit it? | `prove` |

**Next.** `bar` for project-wide thresholds, then `brainstorm` to design against both.
