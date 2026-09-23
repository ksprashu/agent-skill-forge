# Harness Capabilities

What each harness already gives you, what the forge adds on top, and how to
drive both together without doing the same job twice.

The machine-readable source for all of this is
[`config/harnesses.json`](../config/harnesses.json). To see the live state of
your own machine:

```bash
python3 scripts/sync_skills.py --list-harnesses
```

If this document and that command ever disagree, the command is right and this
document is stale. Please fix it.

---

## 1. The idea in one paragraph

A skill in this repo does not claim a *name*. It claims a **capability** — one
sentence describing a job to be done, like `task-decomposition` or
`completion-evidence`. Each harness declares which capabilities it already
covers, and how completely. At install time the forge subtracts whatever is
already fully covered, so you end up with one set of skills, a different subset
per harness, and no two things answering to the same job.

```
   forge skill      capability            harness covers it?        installed
   ───────────      ──────────            ──────────────────        ─────────
   plan             task-decomposition    partially (plan mode) ──►   yes
   review           code-review           partially (/review)   ──►   yes
   brainstorm       design-gate           no                    ──►   yes
   <any>            <any>                 fully                 ──►   skipped
   <any>            <any>                 you wrote /<any>      ──►   skipped
```

Today no harness in the matrix claims `full` coverage of anything, so a clean
install gets the complete selection everywhere. The machinery exists because
that will change, and because the alternative — hand-maintaining a different
skill list per harness — rots the moment a harness ships a new command.

---

## 2. Coverage levels

Every native entry carries a coverage level. This is the only lever that
decides whether a skill is skipped.

| Level | Meaning | Default behaviour |
| :--- | :--- | :--- |
| `full` | The native does the whole job. The forge skill would be noise. | **Skipped** |
| `partial` | The native does part of the job. The forge skill goes further. | **Installed** |
| `local` | *You* defined a command with that name. Not a harness capability. | **Skipped** |

Two flags override the defaults:

| Flag | Effect | Use when |
| :--- | :--- | :--- |
| `--strict-native` | Skip `partial` too. Install only what has no native at all. | You want the smallest possible footprint and trust the native. |
| `--ignore-native` | Skip nothing. Install every selected skill everywhere. | You are comparing forge and native behaviour side by side. |

A wrong `full` is the one entry that can do real damage: it silently removes a
capability from a harness and nobody notices until the work is worse. When you
are unsure, write `partial`. The cost of `partial` is one redundant skill. The
cost of a wrong `full` is a missing gate.

### `native` is about the harness, `local` is about you

`config/harnesses.json` describes what a harness ships **to everybody**. It must
never describe one person's setup. If you keep a `~/.claude/commands/plan.md`,
that is your config, not a Claude Code feature, and writing it into the matrix
would delete the `plan` skill from every other user's install too.

So personal commands are detected at runtime instead. Before linking, the
installer scans each harness's `commands_dirs` for a `<skill-name>.md`. A match
subtracts that one skill, on that one machine, and says so:

```
  [YOURS LOCAL ] plan                   covered by your own /plan
                 Your own command at ~/.claude/commands/plan.md.
                 Delete it to use the forge skill instead.
```

Only Claude Code declares `commands_dirs` today, because it is the only harness
in the matrix with a user-level slash-command directory. The detection is by
exact name, so `~/.claude/commands/code-simplify.md` does not suppress `unslop`
— different names, no collision, both stay.

---

## 3. Per-harness reference

### Claude Code

| | |
| :--- | :--- |
| User skills | `~/.claude/skills` |
| Project skills | `.claude/skills` |
| Hook support | `settings-json` (`~/.claude/settings.json`) |
| User commands | `~/.claude/commands` (scanned for local collisions) |
| Design gate | **Mechanically enforced** — see §5 |
| Reserved names | none |

Claude Code is the only harness in the matrix with a real hook API, so it is
the only place the design gate can actually block an edit. Everywhere else the
gate is instruction text.

**Natively covered:**

| Capability | Native | Coverage | Result |
| :--- | :--- | :--- | :--- |
| `task-decomposition` | plan mode (shift+tab) | partial | `plan` still installs |
| `code-review` | `/review` | partial | `review` still installs |

Both are `partial`, so by default Claude Code gets the full forge selection and
nothing is subtracted. The overlap is real but incomplete:

- **Plan mode** produces an approved plan for the current turn. It does not
  persist an ordered task graph with per-task checkpoints, which is what the
  `plan` skill writes to disk and what `/work` later executes against.
- **`/review`** reviews a GitHub pull request. The `review` skill runs a
  five-axis audit over an arbitrary working diff, with no PR required.

If you would rather lean on the built-ins, `--strict-native` drops both.

> **A correction worth recording.** An earlier version of this matrix listed
> `/plan`, `/spec`, `/test`, and `/code-review` as `full` Claude Code natives.
> They are not built-ins — they were command files in one contributor's
> `~/.claude/commands/`. The effect was that every Claude Code user silently
> lost four spine skills and got nothing in their place. This is precisely the
> "wrong `full`" failure described in §2, and it is why personal commands are
> now detected at runtime rather than declared in the matrix.

### Antigravity IDE

| | |
| :--- | :--- |
| User skills | `~/.gemini/config/skills` |
| Project skills | `.gemini/skills` |
| Hook support | none |
| Design gate | Advisory |
| Reserved names | 31 |
| Natively covered | none recorded — the forge installs its full selection |

Antigravity ships a large set of built-in commands. They are **reserved**, not
**native**. The difference matters:

- **Reserved** means the forge will never create a skill with that name,
  because doing so would shadow a built-in and break it.
- **Native** means the forge will never install a skill for that *capability*,
  because the built-in already does the job.

Antigravity's built-ins are mostly session and environment control — `resume`,
`rewind`, `fork`, `permissions`, `statusline`, `keybindings`, `add-dir`,
`diff`, `config`, `settings`, `clear`, `undo`, `title`, `credits`, `help`. Those
are harness plumbing. They do not overlap with any forge capability, which is
why the native list is empty even though the reserved list is long.

Three reserved names are worth calling out because they *look* like overlaps
and are not:

| Reserved built-in | Looks like | Actually |
| :--- | :--- | :--- |
| `grill-me` | forge `grill` | Different job. The forge skill keeps its own name, so both coexist. |
| `voice` | forge voice work | This is why the forge skill is called `human-voice`. |
| `browser`, `codesearch` | research tooling | Tools, not a research method. `research` still installs. |

Full reserved list:

```
goal          schedule      browser        grill-me       teamwork-preview
learn         boost         agents         config         settings
clear         resume        rewind         undo           fork
add-dir       keybindings   codesearch     credits        diff
permissions   statusline    title          voice          help
agy-customizations           antigravity_guide            antigravity-guide
generative_ui migrate-workflows            permissioned-github
```

### Antigravity CLI

Same reserved list and same empty native list as the IDE. The only difference
is the install path.

| | |
| :--- | :--- |
| User skills | `~/.gemini/antigravity-cli/skills` |
| Project skills | `.gemini/skills` |
| Hook support | none |
| Design gate | Advisory |

### Gemini CLI

| | |
| :--- | :--- |
| User skills | `~/.gemini/skills` |
| Project skills | `.gemini/skills` |
| Hook support | none |
| Design gate | Advisory |
| Reserved names | none |
| Natively covered | none recorded |

Gets the full forge selection.

### OpenAI Codex

| | |
| :--- | :--- |
| User skills | `~/.codex/skills` |
| Project skills | `.codex/skills` |
| Hook support | none |
| Design gate | Advisory |
| Reserved names | none |
| Natively covered | none recorded |

Gets the full forge selection. Codex is the harness the forge adds the most
to, because it arrives with the least.

### Universal Agent Hub

| | |
| :--- | :--- |
| User skills | `~/.agents/skills` |
| Project skills | `.agents/skills` |
| Hook support | none |
| Design gate | Advisory |
| Reserved names | none |
| Natively covered | none recorded |

The vendor-neutral `AGENTS.md` convention. Gets the full selection.

---

## 4. Using the native defaults canonically

The forge is designed to sit *around* whatever your harness already does well,
not on top of it. Here is the canonical order, with the two Claude Code
built-ins marked where they slot in.

```
  ┌─ UNDERSTAND ────────────────────────────────────────────────┐
  │  /echo      dump the ramble, get it read back               │
  │  /grill     get interrogated until the ask is unambiguous   │
  │  /done      write observable done criteria                  │
  │             → docs/understand/<slug>.md                     │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌─ THINK ───────────────────▼─────────────────────────────────┐
  │  /brainstorm  three real alternatives, one recommendation   │
  │  /research    first-party sources, every claim cited        │
  │  /doubt       cross-examine the choice from a fresh context │
  │  ── then write it down ──                                   │
  │  /spec        structured spec                               │
  │  /plan        ordered task graph   (cf. plan mode, partial) │
  │             → docs/design/<slug>.md  status: approved       │
  └──────────────────────────┬──────────────────────────────────┘
                             │  ◄── the design gate sits HERE
  ┌─ BUILD ───────────────────▼─────────────────────────────────┐
  │  /test        failing test first                            │
  │  …implementation…                                           │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌─ VERIFY ──────────────────▼─────────────────────────────────┐
  │  /review      five-axis diff audit  (cf. /review, partial)  │
  │  /verify      static checks + blinded rubrics               │
  │  /scope       what grew beyond the stated intent            │
  │  /bar         did we hold the project's thresholds          │
  │  /prove       paste the fresh output or do not claim done   │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌─ HUMAN ───────────────────▼─────────────────────────────────┐
  │  /profile     how does *this* human read                    │
  │  /unslop      strip the filler                              │
  │  /land        simulate the reader, find where they drop off │
  │  /nudge       hand back the questions worth asking          │
  └─────────────────────────────────────────────────────────────┘
```

Read the four gates as the contract, and any given command as one
implementation of a step in it.

The sequence is identical on every harness. That is the point of the capability
matrix: the workflow you learn on Codex is the workflow you use on Claude Code.
Only the provider of an individual step can differ.

**Where the Claude Code built-ins fit.** Use plan mode for the fast interactive
loop — you are deciding something now, in this turn, and want approval before
the model moves. Use `/plan` when the plan has to outlive the session: it
writes an ordered task graph to disk with per-task checkpoints, which is what
the design gate reads and what `/work` executes against. Same for review: use
the built-in `/review` on a pull request, and the `review` skill on an
uncommitted working diff. They are not competing; they cover different moments.

**If you already have your own commands** for these steps, the installer skips
the matching forge skills automatically. Nothing to configure — see §2.

### Three things to get right

**Run the gates in order.** `/grill` before `/brainstorm` before `/spec`. Each
gate consumes the artefact the previous one wrote. Running `/plan` on an
un-grilled ask produces a confident plan for the wrong problem, which is worse
than no plan.

**Do not run two things for one step.** Where a native fully covers a
capability the forge skill is not installed, so this is handled for you. Where
coverage is `partial` you have both and you have to pick using the guidance
above. If you used `--ignore-native`, you have everything and the choice is
entirely yours.

**Approving a spec is not approving a plan.** The design gate treats those as
separate stamps. See §5.

---

## 5. Where the design gate is real

This is the honest bit.

| Harness | Hook API | Design gate |
| :--- | :--- | :--- |
| Claude Code | `PreToolUse` via `settings.json` | **Enforced.** Edits are blocked. |
| Antigravity IDE | none | Advisory |
| Antigravity CLI | none | Advisory |
| Gemini CLI | none | Advisory |
| Codex | none | Advisory |
| Agent Hub | none | Advisory |

**Enforced** means `hooks/design_gate.py` runs before every `Edit`, `Write`,
`MultiEdit`, and `NotebookEdit`, and exits 2 — which blocks the call — when a
product-code path is touched without an approved design artefact. The model is
told why. It cannot proceed by trying again.

**Advisory** means the gate is the instruction text in the `brainstorm` skill
and nothing more. It is a strong instruction. It is not an enforced one. A
determined or careless model can walk straight past it. If you need the gate to
actually hold on those harnesses, the honest answer today is a pre-commit hook
or CI check, not a skill.

Enable the enforced gate:

```bash
bash scripts/install.sh --spine --hard-gate
python3 hooks/design_gate.py --status     # is it open, and why
python3 hooks/design_gate.py --self-test  # 15 assertions
FORGE_GATE=off claude                     # bypass for one session
```

### What the gate never blocks

Exploration must stay free, or the gate becomes the friction it was built to
prevent. These are always allowed with no artefact:

- Reading anything. The gate only sees write tools.
- `docs/`, `tests/`, `spec/`, `.forge/`, `.upstream/`, `.github/`
- Any `*.md`, `*.txt`, `*.rst`
- Any test file — `*.test.*`, `*.spec.*`, `test_*.py`, `*_test.py`
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONSTRAINTS.md`, `ACCEPTANCE.md`

You can always write the design, and you can always write the test. You cannot
write the implementation until the design is stamped.

### The three approval paths

| Artefact | Path | Unlocks |
| :--- | :--- | :--- |
| `docs/design/<slug>-probe.md` | spike | Throwaway exploration |
| `docs/design/<slug>-design.md` | bounded | A scoped change |
| `docs/design/<slug>-spec.md` **and** `-plan.md` | architectural | Structural work |

The separator is a hyphen, not a dot. The gate splits on the last `-` in the
stem, so `payment-retry-design.md` is a bounded design for `payment-retry`.
A file named `payment-retry.design.md` is not recognised at all.

An approved spec on its own does **not** open the gate. It returns
`architectural-plan-missing`. A spec says what to build; a plan says in what
order and how you will know each step worked. The gate wants both, because the
failure mode it exists to prevent is a good spec followed by improvised
execution.

```bash
python3 hooks/design_gate.py --approve docs/design/my-feature-design.md
```

---

## 6. Adding a harness or a native entry

Edit `config/harnesses.json`. Nothing else needs to change — the installer,
`--list-harnesses`, and the subtraction all read from it.

To add a harness:

```json
"my-harness": {
  "label": "My Harness",
  "skills_dirs": ["~/.myharness/skills"],
  "project_skills_dirs": [".myharness/skills"],
  "commands_dirs": ["~/.myharness/commands"],
  "hook_support": "none",
  "native": {},
  "reserved": []
}
```

`commands_dirs` is optional. Set it if the harness has a directory where users
drop their own `<name>.md` slash commands, and the installer will detect local
collisions there.

To record that it covers a capability natively:

```json
"native": {
  "task-decomposition": { "provider": "/breakdown", "coverage": "full" }
}
```

Use the capability id from the `capabilities` block, not the skill name. A
capability the forge has no skill for is fine to record — it documents the
harness. A skill with no capability entry installs everywhere, always.

Before you write `"coverage": "full"`, check that the command is something the
harness actually ships to every user. If it only exists on your machine, it
does not belong in this file at all — the runtime detection already handles it.

Then check your work:

```bash
python3 scripts/sync_skills.py --list-harnesses
python3 scripts/validate_skills.py
```
