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

# Flags this script handles itself, rather than passing to sync_skills.py
HARD_GATE=0
NO_FETCH=0
OFFLINE=0
PASS_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall)
            # Only --uninstall goes through. Forwarding "$@" would hand
            # sync_skills.py flags it does not define (--hard-gate, --offline)
            # and argparse would exit 2 before removing anything.
            python3 "$SCRIPT_DIR/sync_skills.py" --uninstall
            python3 "$REPO_ROOT/hooks/design_gate.py" --uninstall || true
            exit 0
            ;;
        --hard-gate)    HARD_GATE=1 ;;
        --no-hard-gate) HARD_GATE=0 ;;
        --no-fetch)     NO_FETCH=1 ;;
        --offline)      OFFLINE=1 ;;
        --persona=*)
            AGENT_PERSONA_REPO="${1#--persona=}"
            if [ -z "$AGENT_PERSONA_REPO" ]; then
                echo "❌ Error: --persona requires a non-empty <owner/repo>, URL, or path." >&2
                exit 2
            fi
            export AGENT_PERSONA_REPO
            ;;
        --persona)
            if [ $# -lt 2 ] || [ -z "${2:-}" ]; then
                echo "❌ Error: --persona requires a <owner/repo>, URL, or path argument." >&2
                exit 2
            fi
            AGENT_PERSONA_REPO="$2"
            export AGENT_PERSONA_REPO
            shift
            ;;
        *)              PASS_ARGS+=("$1") ;;
    esac
    shift
done

# ------------------------------------------------------------------------------
# Step 1: resolve reference-only upstream skills at their pinned commits.
# Nothing is vendored in this repo, so this must run before the symlink pass.
# ------------------------------------------------------------------------------
if [ "$NO_FETCH" -eq 0 ]; then
    echo "🔗 Resolving reference-only upstream skills (pinned commits)..."
    FETCH_ARGS=()
    [ "$OFFLINE" -eq 1 ] && FETCH_ARGS+=(--offline)
    [ -t 0 ] || FETCH_ARGS+=(--non-interactive)

    if ! python3 "$SCRIPT_DIR/fetch_upstream.py" ${FETCH_ARGS[@]+"${FETCH_ARGS[@]}"}; then
        echo ""
        echo "⚠️  Some upstream skills could not be resolved (see above)."
        echo "    The forge's own skills will still install. Re-run this installer"
        echo "    once you have network access to complete the spine."
        echo ""
    fi
    echo ""
fi

# ------------------------------------------------------------------------------
# Step 2: link skills into each harness, minus what that harness already ships.
# ------------------------------------------------------------------------------
if [ ${#PASS_ARGS[@]} -gt 0 ]; then
    python3 "$SCRIPT_DIR/sync_skills.py" --fix "${PASS_ARGS[@]}"
elif [ -t 0 ]; then
    python3 "$SCRIPT_DIR/sync_skills.py" --interactive --fix
else
    # Additive. This is the curl-pipe-bash and CI path, where nobody is
    # watching and nobody consented to a removal: defaulting to --prune meant
    # the documented one-liner deleted skills these directories already held.
    # Pruning is available, but it has to be asked for.
    echo "🔄 Synchronizing skills across AI developer tools..."
    python3 "$SCRIPT_DIR/sync_skills.py" --fix
fi

# ------------------------------------------------------------------------------
# Step 3: fetch the user's private voice profile, if they configured one.
# Unset means a neutral install: nothing is fetched. A failure here never fails
# the install; voice-register falls back to neutral prose and says why.
# ------------------------------------------------------------------------------
if [ -n "${AGENT_PERSONA_REPO:-}" ] && [ "$OFFLINE" -eq 1 ]; then
    echo ""
    echo "🎙️  Offline install: skipping the voice profile fetch. Run persona.py pull later."
elif [ -n "${AGENT_PERSONA_REPO:-}" ] && [ -f "$REPO_ROOT/skills/voice-register/scripts/persona.py" ]; then
    echo ""
    echo "🎙️  Fetching your voice profile from $AGENT_PERSONA_REPO..."
    # Exit 1 only means no profile resolved yet; 2 means the fetch failed.
    PERSONA_RC=0
    python3 "$REPO_ROOT/skills/voice-register/scripts/persona.py" pull --force || PERSONA_RC=$?
    if [ "$PERSONA_RC" -eq 2 ]; then
        echo "⚠️  Could not fetch it. voice-register will stay neutral until it can."
    fi
fi

# ------------------------------------------------------------------------------
# Step 4: optionally make the brainstorm hard gate mechanical.
# Only Claude Code has a hook API; elsewhere the gate stays advisory.
# ------------------------------------------------------------------------------
if [ "$HARD_GATE" -eq 1 ]; then
    echo ""
    echo "🚧 Enabling the design gate (blocks product-code edits without an approved design)..."
    python3 "$REPO_ROOT/hooks/design_gate.py" --install
    echo "    Antigravity, Gemini CLI, and Codex have no hook API. There the gate is"
    echo "    the instruction text in the brainstorm skill and nothing more."
fi

echo ""
echo "========================================================================"
echo " ✅ AGENT SKILL FORGE IS FULLY CONFIGURED & ACTIVE"
echo "========================================================================"
echo " 🧭 The four-gate spine:"
echo "    understand   /echo  /grill  /done"
echo "    think        /brainstorm  /research  /doubt"
echo "    verify       /prove  /bar  /scope"
echo "    human        /profile  /land  /nudge"
echo ""
echo " Each harness only gets what it lacks. See what was skipped where:"
echo "    python3 $SCRIPT_DIR/sync_skills.py --list-harnesses"
echo ""
echo " 🛠️  Installer Usage Examples:"
echo "    Interactive Wizard:             bash $SCRIPT_DIR/install.sh"
echo "    Install the spine only:         bash $SCRIPT_DIR/install.sh --spine"
echo "    Spine + enforced design gate:   bash $SCRIPT_DIR/install.sh --spine --hard-gate"
echo "    Install Content & Creative:     bash $SCRIPT_DIR/install.sh --content --prune"
echo "    Install Specific Clusters:      bash $SCRIPT_DIR/install.sh --clusters c3,d1"
echo "    Install Complete Forge (All):   bash $SCRIPT_DIR/install.sh --all"
echo "    Air-gapped install from cache:  bash $SCRIPT_DIR/install.sh --offline"
echo "    Skip the upstream fetch:        bash $SCRIPT_DIR/install.sh --no-fetch"
echo "    Bootstrap to Project Workspace: bash $SCRIPT_DIR/install.sh --project . --clusters c3"
echo "    Uninstall All Forge Skills:     bash $SCRIPT_DIR/install.sh --uninstall"
echo "========================================================================"
