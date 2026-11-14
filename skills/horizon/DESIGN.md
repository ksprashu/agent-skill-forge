# Design Notes (`skills/horizon`)

Why `horizon` separates mechanical probing (`horizon_probes.py`), central ledger state and L3 gating (`horizon.py`), and LLM/MCP sweep judgement (`verdict.json`). Read `SKILL.md` for operational usage.

---

## 1. Failure Modes This Design Prevents

| Failure Mode | How Naive Watchlists Fail | Structural Defence in `skills/horizon` |
| :--- | :--- | :--- |
| **Forecast Rot Across Ephemeral Chats** | 6-12 month predictions stay buried in single-conversation prose and are forgotten within days. | `horizon.py record` upserts every forecast into a central `0o700`/`0o600` ledger (`~/.gemini/horizons/ledger.jsonl`), preserving `revision` and `history[]` across repositories. |
| **Decorative Horizon Sweeps (`S9`)** | An agent asserts `"nothing changed"` or `"drop confirmed"` without running tools or citing probe output, hiding missed checks. | `collect-evidence` records strictly factual digests, exit codes, HTTP statuses, and `not_inspected` gaps into `evidence.json`; `validate-verdict` rejects missing citations, duplicate IDs, contradictory `triggered_count`, or omitted `not_inspected` entries (`exit 1`). |
| **Unbacked Global Config Edits** | An agent edits `~/.gemini/config/rules/*.md` or `~/.claude/` directly and corrupts user-wide rules with no rollback artifact. | `backup-target` snapshots files confined to `~/.gemini` (or explicit `--allow-root`) into `<ledger-dir>/backups/` with SHA-256 verification; `record-action --status landed` fails closed (`exit 1`) unless backup location, digest, sidecar, and target existence verify. |
| **Unprovenanced Repo Mutations** | Remediation items are marked `landed` from unmerged local edits or invalid URLs. | `record-action` refuses `pr_opened` without `https://github.com/<owner>/<repo>/pull/<n>` and refuses `landed` on `repo_branch_pr` items without `--pr-url` or `--override-reason`; `collect-evidence --reconcile-prs` auto-reconciles merged PRs via `gh pr view`. |
| **SSRF, Command Injection & Path Escape** | Allowing `file:///etc/passwd` or external `http://` in web probes, `shell=True` CLI probes, or `../` in file/backup paths leaks local secrets. | `http_digest` restricts URLs and redirects to `https://` or loopback test hosts with a `2 MiB` read cap; `cli_help` allows only 6 binaries and `^[A-Za-z0-9_.-]+$` tokens (`shell=False`); `file_anchor` and `backup-target` confine resolved paths via `is_relative_to`. |
| **Secret Leaks & Host Paths (`S5`, `S8`, `K7`)** | Captured CLI/HTTP error traces echo API keys or `/Users/<name>` paths into `evidence.json` and `ledger.jsonl`. | `horizon_probes.py` runs `redact_secrets` at capture (preserving JSON `null`/`true`/`false`/numbers), `find_secret_leaks` rejects raw secrets in `verdict.json`, and `contract_home` stores `~/...`. |

---

## 2. Evidence vs. Judgement Split (`S9`)

```text
horizon_probes.py (facts) -> evidence.json -\
                                             +-> validate-verdict (L3 gate) -> record-action -> INDEX.md
LLM / MCP sweep (judgement)-> verdict.json  -/
```

1. **Mechanical Facts (`horizon_probes.py`)**: Executes `cli_help`, `github_release`, `http_digest`, `file_anchor`, `gh_pr_status`, and records `agent_query` metadata under `not_inspected` (`V5`). Never emits scores, bands, or drop verdicts.
2. **Judgement Boundary (`verdict.json`)**: The agent interprets `evidence.json` and executes any `agent_query` MCP/catalogue checks, writing structured `decisions[]` with explicit `evidence_citations`.
3. **Fail-Closed Provenance (`horizon.py`)**: `validate-verdict` checks structural, citation, anti-contradiction, and `not_inspected` honesty invariants (`V1-V6`), while `record-action` enforces SHA-256 backups and PR URLs before updating `ledger.jsonl` and `INDEX.md`.

---

## 3. Rejected Alternatives

- **Third-party HTTP/YAML clients (`requests`, `httpx`, `pyyaml`)**: Rejected per `S1` so `horizon` runs on bare Python 3.12 across every harness without virtualenv setup.
- **Per-repository `.horizons/` files as primary store**: Rejected because global rule/CLI/model forecasts affect all projects on the machine; a central `~/.gemini/horizons/` store (overridable via `--ledger-dir` and `$FORGE_HORIZONS_DIR`) keeps one authoritative watchlist while tagging targets as `repo_branch_pr` or `global_config`.
- **Mandatory background OS cron/launchd daemon**: Rejected to preserve cross-platform portability and opt-in control; automation integrates optionally via `/schedule` or user-configured timers (`references/remediation_and_automation.md`).
