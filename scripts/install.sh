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
WITH_MEDIA_TOOLS=0
UNINSTALL=0
PROJECT_DIR=""
HAS_SELECTION_FLAG=0
HAS_LIST_ONLY=0
HAS_SPINE=0
HAS_MEDIA_SELECTION=0
PASS_ARGS=()

_check_clusters_for_media() {
    local raw_list
    raw_list="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    local old_ifs="$IFS"
    IFS=','
    for tok in $raw_list; do
        case "$tok" in
            c3|content|core|all) HAS_MEDIA_SELECTION=1 ;;
            c5|spine)            HAS_SPINE=1 ;;
        esac
    done
    IFS="$old_ifs"
}

_check_skills_for_media() {
    local raw_list
    raw_list="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    local old_ifs="$IFS"
    IFS=','
    for tok in $raw_list; do
        case "$tok" in
            image-gen|video-gen|image-gen-expert|omni-video) HAS_MEDIA_SELECTION=1 ;;
        esac
    done
    IFS="$old_ifs"
}

ARGS=("$@")
i=0
while [ "$i" -lt "${#ARGS[@]}" ]; do
    arg="${ARGS[$i]}"
    case "$arg" in
        --uninstall)        UNINSTALL=1 ;;
        --hard-gate)        HARD_GATE=1 ;;
        --no-hard-gate)     HARD_GATE=0 ;;
        --no-fetch)         NO_FETCH=1 ;;
        --offline)          OFFLINE=1 ;;
        --with-media-tools) WITH_MEDIA_TOOLS=1 ;;
        --all|--core|--content)
            HAS_SELECTION_FLAG=1
            HAS_MEDIA_SELECTION=1
            PASS_ARGS+=("$arg")
            ;;
        --spine)
            HAS_SELECTION_FLAG=1
            HAS_SPINE=1
            PASS_ARGS+=("$arg")
            ;;
        --domain)
            HAS_SELECTION_FLAG=1
            PASS_ARGS+=("$arg")
            ;;
        --list-available|--list-clusters|--list-harnesses)
            HAS_LIST_ONLY=1
            PASS_ARGS+=("$arg")
            ;;
        --project)
            PASS_ARGS+=("$arg")
            if [ $((i + 1)) -lt "${#ARGS[@]}" ]; then
                i=$((i + 1))
                PROJECT_DIR="${ARGS[$i]}"
                PASS_ARGS+=("$PROJECT_DIR")
            fi
            ;;
        --project=*)
            PROJECT_DIR="${arg#--project=}"
            PASS_ARGS+=("$arg")
            ;;
        --clusters)
            PASS_ARGS+=("$arg")
            HAS_SELECTION_FLAG=1
            if [ $((i + 1)) -lt "${#ARGS[@]}" ]; then
                i=$((i + 1))
                _check_clusters_for_media "${ARGS[$i]}"
                PASS_ARGS+=("${ARGS[$i]}")
            fi
            ;;
        --clusters=*)
            HAS_SELECTION_FLAG=1
            _check_clusters_for_media "${arg#--clusters=}"
            PASS_ARGS+=("$arg")
            ;;
        --skills)
            PASS_ARGS+=("$arg")
            HAS_SELECTION_FLAG=1
            if [ $((i + 1)) -lt "${#ARGS[@]}" ]; then
                i=$((i + 1))
                _check_skills_for_media "${ARGS[$i]}"
                PASS_ARGS+=("${ARGS[$i]}")
            fi
            ;;
        --skills=*)
            HAS_SELECTION_FLAG=1
            _check_skills_for_media "${arg#--skills=}"
            PASS_ARGS+=("$arg")
            ;;
        *)
            PASS_ARGS+=("$arg")
            ;;
    esac
    i=$((i + 1))
done

_validate_media_url_scheme() {
    local env_name="$1"
    local url_val="$2"
    [ -z "$url_val" ] && return 0
    local lower_url
    lower_url="$(printf '%s' "$url_val" | tr '[:upper:]' '[:lower:]')"
    case "$lower_url" in
        https://*|file://*) return 0 ;;
        *)
            echo "❌ Error: $env_name must use https:// or file:// (got: $url_val)." >&2
            exit 2
            ;;
    esac
}

if [ "$WITH_MEDIA_TOOLS" -eq 1 ] && [ "$OFFLINE" -eq 1 ]; then
    echo "❌ Error: --with-media-tools cannot be combined with --offline (media tool installation requires network access)." >&2
    exit 2
fi

if [ "$WITH_MEDIA_TOOLS" -eq 1 ]; then
    # Offline test / mirror seams (unprivileged):
    #   FORGE_GEMINI_API_INSTALL_CMD - custom shell command replacing the curl installer in offline tests.
    #   FORGE_GEMINI_API_INSTALL_URL - custom installer script URL override (https:// or file:// only).
    #   FORGE_GEMINI_API_RELEASE_URL - validated here for cross-installer env parity; used by install.ps1 (https:// or file:// only).
    _validate_media_url_scheme "FORGE_GEMINI_API_INSTALL_URL" "${FORGE_GEMINI_API_INSTALL_URL:-}"
    _validate_media_url_scheme "FORGE_GEMINI_API_RELEASE_URL" "${FORGE_GEMINI_API_RELEASE_URL:-}"
fi

if [ "$UNINSTALL" -eq 1 ]; then
    # Only --uninstall goes through. Forwarding "$@" would hand
    # sync_skills.py flags it does not define (--hard-gate, --offline,
    # --with-media-tools) and argparse would exit 2 before removing anything.
    python3 "$SCRIPT_DIR/sync_skills.py" --uninstall
    python3 "$REPO_ROOT/hooks/design_gate.py" --uninstall || true
    exit 0
fi

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

# ------------------------------------------------------------------------------
# Step 5: media tools readiness & opt-in installation (--with-media-tools).
# Never escalates privileges. Default mode stays fast and side-effect-free.
# ------------------------------------------------------------------------------
resolve_local_media_bin() {
    if ! command -v gemini-api >/dev/null 2>&1 && [ -x "$HOME/.local/bin/gemini-api" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    fi
}

if [ "$WITH_MEDIA_TOOLS" -eq 1 ]; then
    echo ""
    echo "🎬 Checking & installing user-space media CLI tools (--with-media-tools, unprivileged)..."
    resolve_local_media_bin

    if ! command -v gemini-api >/dev/null 2>&1; then
        echo "⬇️  gemini-api not found on PATH; installing user-space CLI..."
        GEMINI_API_INSTALL_URL="${FORGE_GEMINI_API_INSTALL_URL:-https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh}"
        INSTALL_OK=1
        if [ -n "${FORGE_GEMINI_API_INSTALL_CMD:-}" ]; then
            if ! bash -c "$FORGE_GEMINI_API_INSTALL_CMD"; then
                INSTALL_OK=0
            fi
        elif command -v curl >/dev/null 2>&1; then
            if ! curl -fsSL "$GEMINI_API_INSTALL_URL" | bash; then
                INSTALL_OK=0
            fi
        else
            echo "❌ Error: curl is required to install gemini-api CLI." >&2
            INSTALL_OK=0
        fi
        resolve_local_media_bin
        if [ "$INSTALL_OK" -eq 0 ] || ! command -v gemini-api >/dev/null 2>&1; then
            echo "❌ Error: failed to install gemini-api CLI into user space ($HOME/.local/bin)." >&2
            echo "   Manual install: curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash" >&2
            echo "   Docs: https://aistudio.google.com/docs/cli" >&2
            exit 1
        fi
    fi

    GEMINI_API_VER="$(gemini-api --version 2>&1 || true)"
    echo "  ✅ gemini-api: ${GEMINI_API_VER:-available}"

    WHOAMI_RC=0
    gemini-api whoami -o json >/dev/null 2>&1 || WHOAMI_RC=$?
    if [ "$WHOAMI_RC" -eq 0 ]; then
        echo "  🔐 gemini-api auth (whoami): authenticated"
    else
        echo "  ℹ️  gemini-api auth: not authenticated yet (non-fatal). Run: gemini-api auth login"
    fi

    if [ -n "${GEMINI_API_KEY:-}" ]; then
        echo "  ⚠️  Warning: GEMINI_API_KEY is set in your environment and could shadow OS keyring credentials (https://aistudio.google.com/docs/cli)."
    fi

    HAVE_FFMPEG=0
    HAVE_FFPROBE=0
    command -v ffmpeg >/dev/null 2>&1 && HAVE_FFMPEG=1
    command -v ffprobe >/dev/null 2>&1 && HAVE_FFPROBE=1

    if [ "$HAVE_FFMPEG" -eq 0 ] || [ "$HAVE_FFPROBE" -eq 0 ]; then
        OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
        if [ "$OS_NAME" = "Darwin" ]; then
            if command -v brew >/dev/null 2>&1; then
                echo "⬇️  ffmpeg/ffprobe missing; installing via Homebrew (brew install ffmpeg)..."
                if ! brew install ffmpeg; then
                    echo "  ⚠️  brew install ffmpeg failed; install manually from https://ffmpeg.org/download.html"
                fi
            else
                echo "  ⚠️  ffmpeg/ffprobe not found. Install Homebrew (https://brew.sh) and run: brew install ffmpeg"
            fi
        else
            echo "  ⚠️  ffmpeg/ffprobe not found on PATH (optional for media workflows)."
            echo "     Install via your package manager (not run automatically; zero privilege escalation):"
            echo "       Debian/Ubuntu: sudo apt install ffmpeg   |   Fedora/RHEL: sudo dnf install ffmpeg   |   Arch: sudo pacman -S ffmpeg"
        fi
    fi

    HAVE_FFMPEG=0
    HAVE_FFPROBE=0
    command -v ffmpeg >/dev/null 2>&1 && HAVE_FFMPEG=1
    command -v ffprobe >/dev/null 2>&1 && HAVE_FFPROBE=1
    if [ "$HAVE_FFMPEG" -eq 1 ] && [ "$HAVE_FFPROBE" -eq 1 ]; then
        echo "  ✅ ffmpeg & ffprobe: available"
    fi
else
    MEDIA_SYNCED=0
    if [ "$HAS_LIST_ONLY" -eq 1 ]; then
        MEDIA_SYNCED=0
    elif [ "$HAS_MEDIA_SELECTION" -eq 1 ] || [ "$HAS_SELECTION_FLAG" -eq 0 ]; then
        MEDIA_SYNCED=1
    elif [ "$HAS_SPINE" -eq 0 ]; then
        for check_path in \
            "$HOME/.agents/skills/image-gen" \
            "$HOME/.agents/skills/video-gen" \
            "$HOME/.gemini/skills/image-gen" \
            "$HOME/.gemini/skills/video-gen" \
            "${PROJECT_DIR:-.}/.gemini/skills/image-gen" \
            "${PROJECT_DIR:-.}/.gemini/skills/video-gen"; do
            if [ -e "$check_path" ] || [ -L "$check_path" ]; then
                MEDIA_SYNCED=1
                break
            fi
        done
    fi

    if [ "$MEDIA_SYNCED" -eq 1 ]; then
        resolve_local_media_bin
        GEMINI_API_STATE="missing"
        FFMPEG_STATE="missing"
        FFPROBE_STATE="missing"
        command -v gemini-api >/dev/null 2>&1 && GEMINI_API_STATE="found"
        command -v ffmpeg >/dev/null 2>&1 && FFMPEG_STATE="found"
        command -v ffprobe >/dev/null 2>&1 && FFPROBE_STATE="found"
        echo ""
        echo " 🎬 Media tools readiness: gemini-api=$GEMINI_API_STATE, ffmpeg=$FFMPEG_STATE, ffprobe=$FFPROBE_STATE"
        echo "    To install user-space media CLIs (unprivileged), re-run with: --with-media-tools"
    fi
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
echo "    Install C3 + media CLIs:        bash $SCRIPT_DIR/install.sh --content --with-media-tools"
echo "    Install Specific Clusters:      bash $SCRIPT_DIR/install.sh --clusters c3,d1"
echo "    Install Complete Forge (All):   bash $SCRIPT_DIR/install.sh --all"
echo "    Air-gapped install from cache:  bash $SCRIPT_DIR/install.sh --offline"
echo "    Skip the upstream fetch:        bash $SCRIPT_DIR/install.sh --no-fetch"
echo "    Bootstrap to Project Workspace: bash $SCRIPT_DIR/install.sh --project . --clusters c3"
echo "    Uninstall All Forge Skills:     bash $SCRIPT_DIR/install.sh --uninstall"
echo "========================================================================"
