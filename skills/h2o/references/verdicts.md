# H2O verdicts and gate commands

Read this before routing any reviewer verdict.

## Verdict block (every reviewer ends with this)

```
@coordinator [done] VERDICT: GOOD | NOT GOOD | NOT GOOD (DESIGN)
Evidence:
$ <command run>
<its output, trimmed to what matters>
<file:line references for anything cited>
Findings:
1. <severity>: <problem> -> <fix expected>
2. ...
```

- Exactly one `VERDICT:` line.
- `Evidence:` must contain a code span, a `$ command` line, or a `file:line`
  reference. "None", "n/a" or prose opinion is not evidence.
- `NOT GOOD` needs at least one numbered finding.
- `NOT GOOD (DESIGN)` means the plan, not the code, is wrong.

## Routing a verdict

Save the reviewer's post to a file (or pipe it) and run, from the repo root:

```bash
python3 <skill-dir>/scripts/h2o_gate.py verdict --file <post.md>
```

| Exit | `verdict` | Coordinator action |
| :--- | :--- | :--- |
| 0 | `GOOD` | `record --verdict GOOD` |
| 1 | `NOT_GOOD` | `record --verdict NOT_GOOD` |
| 1 | `DESIGN` | `record --verdict DESIGN` |
| 1 | `MALFORMED` | Send it back to the same reviewer with the `reasons`; do not record it |
| 2 | - | Invocation error; fix the command |

Then record it:

```bash
python3 <skill-dir>/scripts/h2o_gate.py record --state-dir .agents/h2o \
  --gate <intent_review|plan_review|functional_review|code_review|security_review> \
  --verdict <GOOD|NOT_GOOD|DESIGN>
```

`record` prints `next_stage` (read from `swarm.config.json`) and
`escalate_implementer_to` when the implementer should move up a tier.

| Exit | Meaning | Coordinator action |
| :--- | :--- | :--- |
| 0 | Continue | Hand work to `next_stage`, citing the verdict `#seq` |
| 3 | Cap reached | Ask the user: stop, or continue |
| 2 | Invocation error | Unknown gate, DESIGN on the plan gate, or no `freeze` yet |

If the user says continue:

```bash
python3 <skill-dir>/scripts/h2o_gate.py grant --state-dir .agents/h2o --gate <gate>
```

## Other commands

| Command | When | Fails (exit 1) when |
| :--- | :--- | :--- |
| `freeze --state-dir .agents/h2o --file <f> ...` | Once, right after the user approves the criteria | State already frozen (preserves pre-freeze `intent_review` counts; use `--force` only to reset everything) |
| `check-frozen --state-dir .agents/h2o` | Implementer before posting; code reviewer always | Nothing frozen yet, or any frozen file changed or is missing |
| `diff-guard --base <ref>` (or `--diff-file <f>`) | Implementer before posting; code reviewer always | Deleted test files, added skips or suppressions, net assertion removal in tests |
| `status --state-dir .agents/h2o` | Summary stage, or any time | Never (exit 2 if no state) |

All commands print JSON to stdout. Exit codes: 0 pass, 1 fail, 2 invocation
error, 3 loop cap reached.
