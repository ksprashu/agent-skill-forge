# Remediation Provenance Gates & Automation Reference

Read this before modifying `repo_branch_pr` or `global_config` targets, calling `backup-target` / `record-action`, or automating periodic horizon sweeps.

---

## 1. Target Types & Fail-Closed L3 Provenance Gates

Every ledger item declares one or more entries in `targets[]`:

- `{"kind": "repo_branch_pr", "repo": "<owner>/<repo>", "path": "<repo-relpath>"}` (optional `"branch"`)
- `{"kind": "global_config", "path": "~/.gemini/..."}`

### `backup-target` (Global Config Snapshot)

```bash
python3 <skill-dir>/scripts/horizon.py backup-target \
  --target ~/.gemini/config/rules/swarm-models.md \
  --allow-root ~/.gemini
```

- Flags: `--ledger-dir <dir>`, `--target <file_path>`, `--allow-root <dir>` (repeatable).
- Confines resolved `--target` (following symlinks) to `~/.gemini` or an explicit `--allow-root`; exits `2` on traversal, symlink escape, or missing file.
- Writes `<ledger-dir>/backups/<utc_ts>_<sha12>_<basename>` (`0o600`) and `<backup_path>.sha256.json`, verifies the re-read SHA-256 digest, and prints `{backup_path, target_path, sha256, bytes}`.

### `record-action` (Status Transition Gate)

```bash
python3 <skill-dir>/scripts/horizon.py record-action \
  --id <slug> \
  --status {triggered,pr_opened,landed,superseded} \
  --pr-url https://github.com/<owner>/<repo>/pull/<n> \
  --backup-path ~/.gemini/horizons/backups/<snapshot> \
  --override-reason "<justification>" \
  --note "<summary>"
```

**Fail-closed enforcement (`exit 1`):**
1. **`repo_branch_pr` + `--status pr_opened`:** Requires a valid `--pr-url` matching `https://github.com/<owner>/<repo>/pull/<n>`.
2. **`repo_branch_pr` + `--status landed`:** Requires a valid `pr_url` (from `--pr-url` or the item's prior `pr_opened` state) unless an explicit non-empty `--override-reason` is passed.
3. **`global_config` + `--status landed`:** Requires `--backup-path` residing strictly inside `<ledger-dir>/backups/`, matching `<utc_ts>_<sha12>_<basename>` and its `.sha256.json` digest sidecar, matching the item's `global_config` target path, and confirming the target file still exists on disk.

Every accepted transition writes `<ledger-dir>/runs/<utc_ts>-action-<id>.json`, appends to `history[]` in `ledger.jsonl`, and re-renders `INDEX.md`.

---

## 2. PR Reconciliation & Remediation Workflow

1. **Automated PR reconciliation:** Run `horizon.py collect-evidence --reconcile-prs` during sweeps so `pr_opened` items whose `gh pr view` state is `MERGED` automatically transition to `landed`, while items whose PR was `CLOSED` without merging move back to `triggered` (recording `pr_closed_unmerged` in `history[]`) and update `INDEX.md`.
2. **Repository changes:** Ground in `.gemini/knowledge/` (`K5`), create a feature branch (`git checkout -b ...`), verify code and security via `skills/review/SKILL.md` and `skills/security-review/SKILL.md`, open the PR, and transition the ledger item to `pr_opened`.
3. **Global config changes:** Snapshot via `backup-target`, apply minimal targeted edits, verify any rule/JSON parsers pass, and call `record-action --status landed --backup-path <path>`.

---

## 3. Optional Periodic Automation

- **Antigravity `/schedule`:** Schedule a recurring weekly or bi-weekly sweep that runs `horizon.py collect-evidence --repo-root <repo> --out /tmp/horizon_evidence.json --reconcile-prs`, inspects `not_inspected` (`agent_query` items via `swarm{action:"models"}` or MCP docs), emits `verdict.json`, gates it with `horizon.py validate-verdict`, and surfaces triggered items to the user without auto-merging.
- **Unattended safety rule:** Unattended sweeps may run `collect-evidence` (with `--reconcile-prs`) and `validate-verdict`, and may open draft PRs on feature branches, but should never force-apply `global_config` edits without a prior `backup-target` snapshot and clear audit trail.
