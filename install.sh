#!/usr/bin/env bash
# =============================================================================
# PulseEngine — macOS / Linux Installer Wrapper
# =============================================================================
# This is a thin convenience wrapper around install.py.
# It ensures Python 3 is available, then delegates everything to install.py.
#
# One-line install (from a cloned repo):
#   curl -sL https://raw.githubusercontent.com/The-Pulse-Engine/\
#       Pulse-Engine_Market_Intelligence_Platform/main/install.sh | bash
#
# Or after cloning:
#   bash install.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

info()  { echo -e "  ${CYAN}→${RESET}  $*"; }
ok()    { echo -e "  ${GREEN}✔${RESET}  $*"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail()  { echo -e "  ${RED}✘  ERROR:${RESET}  $*" >&2; }
abort() { fail "$1"; [ -n "${2:-}" ] && echo -e "$2" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve repo root (works when piped via curl AND run directly)
# ---------------------------------------------------------------------------
if [ -n "${BASH_SOURCE[0]+x}" ] && [ "${BASH_SOURCE[0]}" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    # Piped via curl — assume CWD is the repo root
    SCRIPT_DIR="$(pwd)"
fi

cd "$SCRIPT_DIR"

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║  PulseEngine — macOS/Linux Installer Wrapper     ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

# ---------------------------------------------------------------------------
# 1. Locate a suitable Python interpreter (3.11–3.14)
# ---------------------------------------------------------------------------
info "Looking for a compatible Python interpreter (3.11–3.14) …"

PYTHON_CMD=""

# Try common interpreter names in preferred order
for cmd in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)

        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ] && [ "$MINOR" -le 14 ]; then
            PYTHON_CMD="$cmd"
            ok "Found $cmd ($VERSION)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    abort \
        "No compatible Python version found (need 3.11–3.14)." \
        "$(cat <<'EOF'

     Install Python 3.12 and retry:

       macOS (Homebrew):
           brew install python@3.12

       Ubuntu / Debian:
           sudo apt update && sudo apt install python3.12 python3.12-venv

       Fedora:
           sudo dnf install python3.12

       Direct download:
           https://www.python.org/downloads/

     Then re-run:
           bash install.sh
EOF
)"
fi

# ---------------------------------------------------------------------------
# 2. Confirm install.py exists
# ---------------------------------------------------------------------------
if [ ! -f "$SCRIPT_DIR/install.py" ]; then
    abort \
        "install.py not found in $SCRIPT_DIR." \
        "  Make sure you are running this script from the repo root."
fi

# ---------------------------------------------------------------------------
# 3. Delegate to install.py
# ---------------------------------------------------------------------------
echo ""
info "Handing off to install.py …"
echo ""

exec "$PYTHON_CMD" "$SCRIPT_DIR/install.py"
