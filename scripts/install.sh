#!/usr/bin/env bash
# Copyright 2026 Agent Skill Forge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

if [ $# -gt 0 ]; then
    python3 "$SCRIPT_DIR/sync_skills.py" --fix "$@"
elif [ -t 0 ]; then
    python3 "$SCRIPT_DIR/sync_skills.py" --interactive --fix
else
    echo "🔄 Synchronizing 15 Core Action Verbs across AI developer tools..."
    python3 "$SCRIPT_DIR/sync_skills.py" --prune --fix
fi

echo ""
echo "========================================================================"
echo " ✅ AGENT SKILL FORGE IS FULLY CONFIGURED & ACTIVE"
echo "========================================================================"
echo " 🌟 15 Core Global Skills:"
echo "    /prompt, /grill, /spec, /plan, /test, /verify, /review, /unslop,"
echo "    /docs, /catalog, /sync, /google-oss, /codelab, /voice, /copy-write, /image-gen"
echo ""
echo " 🛠️  Installer Usage Examples:"
echo "    Interactive Wizard:             bash $SCRIPT_DIR/install.sh"
echo "    Install Content & Creative:     bash $SCRIPT_DIR/install.sh --content --prune"
echo "    Install Specific Clusters:      bash $SCRIPT_DIR/install.sh --clusters c3,d1"
echo "    Install All Core Skills:        bash $SCRIPT_DIR/install.sh --core"
echo "    Install All Domain Skills:      bash $SCRIPT_DIR/install.sh --domain"
echo "    Install Complete Forge (All):   bash $SCRIPT_DIR/install.sh --all"
echo "    Bootstrap to Project Workspace: bash $SCRIPT_DIR/install.sh --project . --clusters c3"
echo "    List All Clusters & Skills:     bash $SCRIPT_DIR/install.sh --list-clusters"
echo "========================================================================"
