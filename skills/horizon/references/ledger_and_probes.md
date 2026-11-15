# Ledger Schema, Probes, and Verdict Verification Reference

This reference documents every flag, schema field, and mechanical probe contract implemented in `scripts/horizon.py` and `scripts/horizon_probes.py` (`S6`, `S9`).

---

## 1. Ledger Directory & File Permissions

`horizon.py` resolves the central ledger directory in strict precedence order:

1. `--ledger-dir <dir>` (supported before or after the subcommand)
2. `$FORGE_HORIZONS_DIR`
3. `~/.gemini/horizons` (`Path.home() / ".gemini" / "horizons"`)

Directories are created with `0o700` permissions; `ledger.jsonl`, `INDEX.md`, `runs/*.json`, and `backups/*` are written atomically via temp file + `os.fsync` + `0o600` + `os.replace`.

---

## 2. Forecast Item Schema (`ledger.jsonl`) & `record` Flags

Each line in `ledger.jsonl` is one JSON object (`schema_version: "1"`). `horizon.py record` accepts `--input <json_file>` (or `-` for stdin) and/or CLI flags:

| Field | CLI Flag | Requirement |
| :--- | :--- | :--- |
| `id` | `--id` | Unique slug matching `^[a-z0-9][a-z0-9-]{2,63}$` |
| `title` | `--title` | Non-empty string |
| `category` | `--category` | Non-empty string (defaults to `"general"`) |
| `window` | `--window` | Non-empty forecast horizon string (e.g., `"2026-Q4..2027-Q2"`) |
| `baseline_measurement` | `--baseline` | Non-empty current measurement observed today |
| `forecast` | `--forecast` | Non-empty explicit 6-12 month forecast |
| `playbook` | `--playbook` | Non-empty remediation instructions when triggered |
| `source` | `--source` | Non-empty origin label (defaults to `"manual"`) |
| `probes` | `--probe` *(repeatable JSON)* | Non-empty list (`len >= 1`) of validated probe objects |
| `targets` | `--target` *(repeatable JSON)* | Non-empty list (`len >= 1`) of `repo_branch_pr` or `global_config` target objects |

Upserts on an existing `id` increment `revision`, preserve `created_at` and `history[]`, retain current lifecycle `status`, and regenerate `INDEX.md`.

### `list` & `render-index` Flags

- `list`: `--ledger-dir <dir>`, `--status {all,watching,triggered,pr_opened,landed,superseded}`, `--format {json,table}`
- `render-index`: `--ledger-dir <dir>`, `--check` (exits `1` if `INDEX.md` is missing or stale)
- Top-level `--doctor`: emits JSON readiness check (`python_version`, `stdlib_only`, `ledger_dir`, `ledger_valid`, `item_count`, `tools`).

---

## 3. Mechanical Probe Contracts (`horizon_probes.py`)

`collect-evidence` accepts `--ledger-dir <dir>`, `--out <evidence.json>`, `--repo-root <dir>`, `--allow-root <dir>` (repeatable), `--id <slug>`, `--reconcile-prs`, and `--timeout <s>`.

| Probe `kind` | Required / Optional Input Fields | Factual Output Fields (`S9`) | `not_inspected` & Security Rules |
| :--- | :--- | :--- | :--- |
| `cli_help` | `binary` (`gemini-api`, `gh`, `ffmpeg`, `ffprobe`, `python3`, `git`), optional `subcommand` or `args`, optional `expect_tokens`, `baseline_output_sha256` | `available`, `returncode`, `output_sha256`, `matched_tokens`, `missing_tokens`, `changed_vs_baseline` | Tokens must match `^[A-Za-z0-9_.-]+$`; option flags restricted to `--help`, `-h`, `--version`; missing binary logged in `not_inspected`. |
| `github_release` | `repo` (`owner/repo`), optional `baseline_tag` | `available`, `http_status`, `tag_name`, `published_at`, `asset_names`, `tag_changed_vs_baseline` | Queries `https://api.github.com/repos/<owner>/<repo>/releases/latest`; `FORGE_HORIZON_GITHUB_API_BASE` allows only `https://`, loopback `http://`, or `file://` (rejects external `http://` with `ValueError`). |
| `http_digest` | `url`, optional `expect_tokens`, `baseline_sha256` | `available`, `http_status`, `content_sha256`, `bytes_read`, `truncated`, `changed_vs_baseline`, `matched_tokens`, `missing_tokens` | Allows `https://` or loopback `http://127.0.0.1` / `localhost` / `[::1]` only; rejects `file://`, metadata hosts, and external `http://` (including redirects); caps read at `2 * 1024 * 1024` bytes. |
| `file_anchor` | `path` (or `relpath`), `anchor_literal`, optional `scope` (`repo` or `global_config`), `baseline_sha256` | `exists`, `file_sha256`, `anchor_found`, `changed_vs_baseline` | `repo` confined via `.resolve().is_relative_to(repo_root.resolve())`; `global_config` confined to `~/.gemini` or `--allow-root`. |
| `gh_pr_status` | `pr_url` (`https://github.com/<owner>/<repo>/pull/<n>`) | `available`, `state`, `merged_at`, `url` | Runs `gh pr view --json state,mergedAt,url -- <pr_url>`; `available: false` logged in `not_inspected`. |
| `agent_query` | `source`, `query` | `kind: "agent_query"`, `source`, `query`, `status: "requires_agent_eval"`, `available: false` | Always appended to `not_inspected` during mechanical collection (`V5`). |

---

## 4. Verdict Verification Contract (`validate-verdict`)

`horizon.py validate-verdict --verdict <verdict.json> [--evidence <evidence.json>] [--ledger-dir <dir>]` enforces:

1. `schema_version == "1"`, non-empty `evaluated_at` and `summary`, non-negative integer `triggered_count` (never `bool`), list `not_inspected`, and list `decisions`.
2. Every `decisions[].item_id` exists in `ledger.jsonl` and is unique (no duplicates).
3. Each `decision` is in `{"no_change", "drop_confirmed", "target_drifted", "supersede"}`.
4. Whenever `decision` is in `{"drop_confirmed", "target_drifted", "supersede"}`, both `evidence_citations` (non-empty list of non-empty strings) and `summary` (non-empty string) are required.
5. **Two-way `triggered_count` consistency:** `triggered_count` must equal the exact count of `decisions` in `{"drop_confirmed", "target_drifted", "supersede"}`.
6. **`not_inspected` honesty:** When `--evidence` is supplied, every item in `evidence.items` must appear in `decisions` and every entry in `evidence.not_inspected` must be preserved in `verdict.not_inspected`.
7. Zero unredacted secrets (`SECRET_PATTERNS`) anywhere inside `verdict.json`.
