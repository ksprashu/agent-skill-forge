#!/usr/bin/env bash
# Lightweight CVE / dependency check helper for agents.
# Usage: ./check-vulns.sh [lockfile or "recent"]
# Falls back gracefully; agent should interpret results.

set -euo pipefail

echo "=== Agent Security Posture Check ==="

# Recent critical CVEs (last ~7 days window example; adjust dates)
if command -v curl >/dev/null 2>&1; then
  echo "--- Recent Critical CVEs (NVD) ---"
  # Note: replace dates as needed; rate-limit aware
  curl -sS "https://services.nvd.nist.gov/rest/json/cves/2.0?cvssV3Severity=CRITICAL&resultsPerPage=5" \
    | head -c 2000 || echo "(NVD query failed or rate-limited)"
  echo
fi

# Example OSV query for a common package (agent should customize)
echo "--- Example OSV query ---"
curl -sS -X POST https://api.osv.dev/v1/query \
  -H "Content-Type: application/json" \
  -d '{"package":{"name":"requests","ecosystem":"PyPI"},"version":"2.31.0"}' \
  | head -c 1500 || echo "(OSV query failed)"

echo
echo "=== End check. Review output, triage by severity/reachability, fix critical items. ==="
