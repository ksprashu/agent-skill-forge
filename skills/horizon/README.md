# Horizon Sentinel Skill (`/horizon`, `/radar`, `/tech-horizon`)

Zero-dependency Python 3.12 stdlib engine that converts 6-12 month technical and AI forecasts into a central machine-wide ledger (`~/.gemini/horizons/`), executes mechanical upstream/anchor probes into `evidence.json` (`S9`), validates sweep verdicts (`verdict.json`), enforces SHA-256 pre-edit backups and PR URL provenance, and renders deterministic `INDEX.md` summaries.

---

## Module Layout

- `scripts/horizon_probes.py`: `S8` capture-time secret redactor (`JSON`-preserving), SSRF-hardened `http_digest` & `github_release` fetchers, allowlisted `cli_help` & `gh_pr_status` runners (`shell=False`), confined `file_anchor` inspector, and `V5`-honest `agent_query` metadata recorder.
- `scripts/horizon.py`: Atomic `0o700`/`0o600` ledger CLI (`record`, `list`, `collect-evidence`, `validate-verdict`, `backup-target`, `record-action`, `render-index`, `--doctor`).
- `references/ledger_and_probes.md`: Ledger directory resolution, `ledger.jsonl` schema, all six probe contracts, and `verdict.json` validation rules.
- `references/remediation_and_automation.md`: Fail-closed L3 gates (`backup-target`, `record-action`, `--reconcile-prs`) and optional `/schedule` sweep workflows.
- `fixtures/known_good/` & `fixtures/known_bad/`: Verifier calibration fixtures (`V1`, `V2`).

---

## Quickstart

```bash
# 1. Check environment readiness
python3 skills/horizon/scripts/horizon.py --doctor

# 2. Record a forecast item
python3 skills/horizon/scripts/horizon.py record --input skills/horizon/fixtures/known_good/valid_record_item.json

# 3. Collect mechanical evidence & reconcile merged PRs
python3 skills/horizon/scripts/horizon.py collect-evidence --repo-root . --out evidence.json --reconcile-prs

# 4. Validate LLM/MCP sweep verdict against ledger & evidence
python3 skills/horizon/scripts/horizon.py validate-verdict --verdict verdict.json --evidence evidence.json

# 5. Verify INDEX.md freshness
python3 skills/horizon/scripts/horizon.py render-index --check
```

See [`SKILL.md`](./SKILL.md) for agent workflow instructions and [`DESIGN.md`](./DESIGN.md) for architectural rationale.
