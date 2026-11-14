# Horizon Sentinel Specification (`skills/horizon`)

Status: approved
Slug: horizon-sentinel
Path: architectural
Date: 2026-11-14

---

## 1. Problem Statement & Objectives

Engineering sessions routinely produce high-signal 6-12 month technical and AI forecasts (model pricing drops, preview-to-GA identifier promotions, upstream CLI flag stabilization, deprecation timelines), yet those predictions dissipate inside session transcripts. Conversely, naive automation loops either hallucinate trigger confirmations without factual evidence or mutate global `~/.gemini` rules and repositories without backups or pull-request provenance.

This specification defines **`skills/horizon`** (Cluster `C4`, aliases `radar` and `tech-horizon`), a 100% Python 3.12 stdlib engine implementing:
1. A central machine-wide ledger (`~/.gemini/horizons/` by default, overridable via `--ledger-dir` and `$FORGE_HORIZONS_DIR`) with `0o700`/`0o600` atomic writes, `revision` tracking, and deterministic `INDEX.md` rendering (`T1`, `T3`, `T6`).
2. Six pure-factual mechanical probe collectors in `horizon_probes.py` (`cli_help`, `github_release`, `http_digest`, `file_anchor`, `gh_pr_status`, `agent_query`) emitting `evidence.json` (`S9`, `V5`) with `S8` capture-time secret redaction.
3. Fail-closed L3 verification (`validate-verdict`) enforcing schema, known unique IDs, evidence citations, two-way `triggered_count` parity, secret-leak checks, and `not_inspected` honesty (`V1-V6`).
4. Fail-closed remediation provenance gates (`backup-target` + `record-action`) requiring SHA-256 backups confined to `~/.gemini` / `--allow-root` for `global_config` targets and canonical GitHub PR URLs (or `--override-reason`) for `repo_branch_pr` targets, plus `--reconcile-prs`.

### Explicit Non-Goals
- **No third-party Python dependencies (`S1`):** Uses only Python 3.12 stdlib (`urllib.request`, `subprocess`, `hashlib`, `json`, `re`, `pathlib`, `ipaddress`).
- **No mechanical scoring or drop conclusions (`S9`):** `horizon_probes.py` never scores or emits verdicts; models judge from `evidence.json` and pass `validate-verdict`.
- **No silent or unbacked mutations:** External plain `http://` and `file://` URLs are rejected in `http_digest`; `global_config` `landed` transitions fail closed without a verified backup inside `<ledger-dir>/backups/`.

---

## 2. Architecture & Security Contracts (`S1-S9`, `V1-V6`)

| Component | Path | Key Invariants |
| :--- | :--- | :--- |
| **Probe Collectors** | `skills/horizon/scripts/horizon_probes.py` | `S4` `shell=False` + `timeout` + CWE-88 `--`/token guards; `S8` JSON-preserving `SECRET_PATTERNS` redaction at capture; SSRF redirect handler + `2 MiB` HTTP read cap; `FORGE_HORIZON_GITHUB_API_BASE` scheme fence (`https://`, loopback `http://`, `file://`); `V5` `not_inspected` reporting. |
| **Ledger & L3 Gates** | `skills/horizon/scripts/horizon.py` | Atomic `0o700`/`0o600` ledger writes; strict `record` validation (`exit 2`); deterministic `render-index --check` (`T6`); `validate-verdict` (`exit 1` on violations); `backup-target` symlink/traversal confinement (`exit 2`); `record-action` fail-closed PR & backup gates (`exit 1`); `--doctor`. |
| **Calibration Fixtures** | `skills/horizon/fixtures/{known_good,known_bad}/` | `V1`/`V2` fixtures covering corrupt JSONL, missing evidence citations, duplicate IDs, contradictory counts, insecure HTTP probes, and empty probes. |
| **K8 Registration** | `sync_skills.py`, `harnesses.json`, `autowire.py`, `check_stdlib_only.py`, `README.md`, `docs/catalog_reference.md` | Registers `horizon` in Cluster `C4` with `radar`/`tech-horizon` aliases, `horizon-watch` capability, specific `autowire.py` triggers with negative tests, and stdlib root enforcement. |
