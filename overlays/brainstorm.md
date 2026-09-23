## In the forge

`brainstorm` is the hard gate for the whole forge. Every other think-gate skill is optional;
this one is the wall.

**Enforcement.** On Claude Code, `hooks/design_gate.py` makes the `<HARD-GATE>` above
mechanical: `Edit`, `Write`, and `NotebookEdit` on product code are refused until the
selected path's artefact exists and is marked approved. Enable it with
`bash scripts/install.sh --hard-gate`.

On Antigravity, Gemini CLI, and Codex there is no hook API, so the gate is the text above and
nothing more. It is a strong instruction, not an enforced one. Know which you are running.

**Where artefacts live, and what unblocks the gate:**

| Path | Artefact | Location |
| :--- | :--- | :--- |
| Spike | Approved question + probe | `docs/design/<slug>-probe.md` |
| Bounded | Approved short design | `docs/design/<slug>-design.md` |
| Architectural | Approved spec, then approved plan | `docs/design/<slug>-spec.md`, `docs/design/<slug>-plan.md` |

Each file needs a `Status: approved` line. The hook looks for it; a human writes it.

**Always allowed, gate or no gate:** reading, searching, `docs/`, `tests/`, and any `.md`.
Exploration is never blocked.

**Feeding it.** `grill` and `done` first, so the design has a target. `research` when a
decision needs facts you do not have. `doubt` when one branch of the design is load-bearing
and you want it attacked before it hardens.
