---
name: horizon
description: Track 6-12 month technical and AI forecasts in a central machine-wide ledger (`~/.gemini/horizons/`), collect mechanical upstream/anchor evidence into `evidence.json`, validate sweep verdicts (`verdict.json`), and gate remediations with SHA-256 backups and PR URL provenance. Trigger via /horizon, /radar, /tech-horizon, or when tracking predictive horizons and forecast watchlists.
---

# Horizon Sentinel (`/horizon`, `/radar`, `/tech-horizon`)

Manage 6-12 month technical and AI forecasts as verifiable ledger entries via `<skill-dir>/scripts/horizon.py` (100% Python 3.12 stdlib).

**Central ledger resolution:** `--ledger-dir` -> `$FORGE_HORIZONS_DIR` -> `~/.gemini/horizons` (created `0o700`, files `0o600`).

---

## Step-by-Step Workflow

### Step 1: Preflight & Inspect Active Watchlist
Verify environment readiness and inspect current forecasts before recording or sweeping:

```bash
python3 <skill-dir>/scripts/horizon.py --doctor
python3 <skill-dir>/scripts/horizon.py list --status all --format table
```

- Filter with `--status {all,watching,triggered,pr_opened,landed,superseded}` and `--format {json,table}`.

### Step 2: Record or Update a Forecast (`record`)
Read `references/ledger_and_probes.md` for the complete `ledger.jsonl` schema and all six probe contracts (`cli_help`, `github_release`, `http_digest`, `file_anchor`, `gh_pr_status`, `agent_query`).

Record via `--input <json>` (or `-` stdin) and/or ergonomic CLI flags:

```bash
python3 <skill-dir>/scripts/horizon.py record \
  --id gemini-cli-store-flag \
  --title "Watch gemini-api --store stabilization" \
  --category cli-tool \
  --window "2026-Q4..2027-Q2" \
  --baseline "gemini-api requires explicit --store=false" \
  --forecast "gemini-api adds --stateless default within 6-12 months." \
  --playbook "Open a PR updating skills/image-gen/scripts/image_gen.py." \
  --source architecture-review \
  --probe '{"kind":"cli_help","binary":"gemini-api","subcommand":"generate","expect_tokens":["--store"]}' \
  --target '{"kind":"repo_branch_pr","repo":"ksprashu/agent-skill-forge","path":"skills/image-gen/scripts/image_gen.py"}'
```

- Upserts deduplicate on `--id` (`^[a-z0-9][a-z0-9-]{2,63}$`), increment `revision`, preserve `created_at` and `history[]`, and regenerate `INDEX.md`.

### Step 3: Collect Mechanical Evidence (`collect-evidence`, S9)
Run deterministic probes across `watching` and `pr_opened` items before making any judgement:

```bash
python3 <skill-dir>/scripts/horizon.py collect-evidence \
  --repo-root . \
  --out evidence.json \
  --reconcile-prs
```

- Optional filters & overrides: `--id <slug>`, `--allow-root <dir>`, `--timeout <s>`.
- `horizon_probes.py` emits purely factual observations (`output_sha256`, `tag_name`, `content_sha256`, `anchor_found`, `state`) and logs unavailable tools or `agent_query` items under `not_inspected` (`V5`).
- `--reconcile-prs` automatically transitions `pr_opened` items to `landed` when `gh_pr_status` reports `MERGED`, or back to `triggered` (`pr_closed_unmerged`) when `CLOSED` without merge, and updates `INDEX.md`.

### Step 4: Author Sweep Judgement & Run L3 Verdict Gate (`validate-verdict`)
Evaluate `evidence.json` (plus any MCP/model-catalogue `agent_query` items), write `verdict.json`, and validate it before acting:

```bash
python3 <skill-dir>/scripts/horizon.py validate-verdict \
  --verdict verdict.json \
  --evidence evidence.json
```

- Enforces `schema_version == "1"`, unique known `item_id`s, `decision` in `{"no_change","drop_confirmed","target_drifted","supersede"}`, non-empty `evidence_citations` + `summary` on triggered decisions, two-way `triggered_count` parity, zero secret leaks, and `not_inspected` honesty (`exit 1` on violation).

### Step 5: Execute Remediation Behind Provenance Gates (`backup-target`, `record-action`)
Read `references/remediation_and_automation.md` before modifying targets or scheduling recurring sweeps.

- **Repository targets (`repo_branch_pr`)**: Read `.gemini/knowledge/` first (`K5`), implement on a new branch, run `skills/review/SKILL.md` and `skills/security-review/SKILL.md`, open a PR, and record:
  ```bash
  python3 <skill-dir>/scripts/horizon.py record-action \
    --id <slug> --status pr_opened --pr-url https://github.com/<owner>/<repo>/pull/<n> --note "Opened PR"
  ```
- **Global config targets (`global_config`)**: Create a verified SHA-256 backup **before** editing, then record `landed`:
  ```bash
  python3 <skill-dir>/scripts/horizon.py backup-target --target ~/.gemini/config/rules/swarm-models.md
  python3 <skill-dir>/scripts/horizon.py record-action \
    --id <slug> --status landed --backup-path ~/.gemini/horizons/backups/<snapshot>
  ```
- Re-render or verify `INDEX.md` freshness (`T6`): `python3 <skill-dir>/scripts/horizon.py render-index --check`.

---

## Hard Constraints

- **NEVER** accept an LLM/MCP sweep verdict without running `collect-evidence` and passing `validate-verdict` (`S9`).
- **NEVER** use plain external `http://` or `file://` URLs in `http_digest` probes (`record` and `collect-evidence` reject them).
- **NEVER** edit a `global_config` target without running `backup-target` first; `record-action --status landed` fails closed without a verified backup inside `<ledger-dir>/backups/`.
- **NEVER** mark a `repo_branch_pr` item `pr_opened` without a canonical `https://github.com/<owner>/<repo>/pull/<n>` `--pr-url`, or `landed` without `--pr-url` or explicit `--override-reason`.
- **NEVER** hand-edit `<ledger-dir>/INDEX.md`; regenerate it via `record`, `record-action`, or `render-index`.
