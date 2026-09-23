# Where the rendered files go

`render.py` writes files into a directory you choose. It does not decide
*which* directory — placement is the part that differs per tool, and getting
it wrong means a profile that silently never loads.

---

## Targets

| `-t` | Writes | Put it in | Scope |
|---|---|---|---|
| `claude` | `CLAUDE.md` | repo root, or `~/.claude/` | project / global |
| `antigravity` | `GEMINI.md` | repo root, or `~/.gemini/` | project / global |
| `gemini-cli` | `GEMINI.md` | repo root, or `~/.gemini/` | project / global |
| `agents` | `AGENTS.md` | repo root | project |
| `codex` | `AGENTS.md` | repo root | project |
| `cursor` | `.cursorrules` | repo root | project |
| `windsurf` | `.windsurfrules` | repo root | project |
| `system` | `system_prompt.md` | wherever you assemble prompts | manual |

Default with no `-t` is every target. Harnesses that share a filename share a
template, so `agents` and `codex` cannot disagree about `AGENTS.md`.

---

## Global or per-project

A communication profile describes a person, not a codebase, so **global is
usually right**:

```bash
python3 scripts/render.py profile.json -t claude -o ~/.claude
python3 scripts/render.py profile.json -t antigravity -o ~/.gemini
```

Render per-project when the repo has other contributors — a file describing
how *you* like to read does not belong in shared source control unless the
team agrees.

---

## Merging with existing files

`render.py` **overwrites the whole file**. If you already have a `CLAUDE.md`
holding build commands and architecture notes, do not point `-o` at it.

Instead render to a scratch directory and paste the body in under a heading:

```bash
python3 scripts/render.py profile.json -t claude -o /tmp/profile
# then copy the body into your existing CLAUDE.md
```

Keep the provenance footer when you paste. It is the part that tells you how
much of the profile was actually earned.

---

## Keeping configs current

After any `profile_tool.py amend`, re-render. To catch drift in CI:

```bash
python3 scripts/render.py profile.json --check -o .
```

Exit code `1` with a diff means the committed files no longer match the
profile.

---

## Precedence traps

- **Claude Code** merges `~/.claude/CLAUDE.md` with the project file; the
  project file wins on conflict. Rendering to both means the global one is
  mostly ignored — pick one.
- **Cursor** is migrating from `.cursorrules` to `.cursor/rules/*.mdc`. If your
  version supports the directory form, copy the rendered file to
  `.cursor/rules/communication.mdc` and add the frontmatter your version wants.
- **Antigravity** reserves some skill and command names. The rendered files are
  plain instruction files and do not collide, but do not rename this skill to
  anything in that reserved set.
