# Overlays

Upstream skills are fetched at a pinned commit and never edited in place. Each
file here is appended to its skill's `SKILL.md` at fetch time, below the
upstream content and above the provenance block.

An overlay has one job: say how this skill connects to the rest of the forge
spine. It does not restate, correct, or argue with the upstream skill. If you
find yourself rewriting upstream behaviour in an overlay, the right move is
usually to stop referencing that skill and write your own.

| Overlay | Skill | Gate |
| :--- | :--- | :--- |
| `grill.md` | `grill` | understand |
| `echo.md` | `echo` | understand |
| `done.md` | `done` | understand |
| `brainstorm.md` | `brainstorm` | think |
| `research.md` | `research` | think |
| `doubt.md` | `doubt` | think |
| `prove.md` | `prove` | verify |
| `bar.md` | `bar` | verify |
| `scope.md` | `scope` | verify |
| `land.md` | `land` | human |
| `nudge.md` | `nudge` | human |

Overlays are regenerated on every `fetch_upstream.py` run. Editing
`.upstream/<name>/SKILL.md` directly will be overwritten; edit the overlay.
