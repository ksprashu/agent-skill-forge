## In the forge

`prove` is the last gate before you are allowed to say a thing is done.

**Forge verification commands.** For work inside this repository the fresh-evidence commands
are:

```bash
python3 scripts/validate_skills.py          # frontmatter lint + PII scan
python3 scripts/fetch_upstream.py --verify  # upstream trees match their manifests
python3 scripts/sync_skills.py              # audit installed links (read-only)
```

**Against acceptance criteria.** If `done` produced an acceptance file, walk it line by line
and attach the command output that satisfies each AC. A passing test suite is not evidence
that AC-004 was met; only AC-004's own check is.

**The failure this prevents** is not dishonesty. It is the model reading its own earlier
output as if it were a fresh test run. Fresh means run in this message.
