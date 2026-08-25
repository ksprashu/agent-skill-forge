#!/usr/bin/env bash
# ==============================================================================
# Agent Skill Forge — 1-Liner Universal Installer
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================================================"
echo " 🔨 AGENT SKILL FORGE — Universal Skill Installer"
echo "========================================================================"
echo " Repo Source: $REPO_ROOT"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not found in PATH."
    exit 1
fi

echo "🔄 Synchronizing 15 Core Action Verbs across AI developer tools..."
python3 "$SCRIPT_DIR/sync_skills.py" --prune --fix

echo ""
echo "========================================================================"
echo " ✅ AGENT SKILL FORGE IS FULLY INSTALLED & ACTIVE"
echo "========================================================================"
echo " 🌟 15 Core Global Skills:"
echo "    /prompt, /grill, /spec, /plan, /test, /verify, /review, /unslop,"
echo "    /docs, /catalog, /sync, /google-oss, /codelab, /voice, /copy-write, /image-gen"
echo ""
echo " 🛠️  To bootstrap domain skills into any project workspace:"
echo "    python3 $SCRIPT_DIR/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization"
echo "========================================================================"
