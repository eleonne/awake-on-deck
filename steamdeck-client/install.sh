#!/bin/bash
# install.sh — Awake on Deck installer
# Run this from Desktop Mode on your Steam Deck.
# It clones the repo, installs dependencies, and adds the app to Steam.

set -e

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/eleonne/awake-on-deck.git"
REPO_DIR="/home/deck/awake-on-deck"
APP_DIR="$REPO_DIR/steamdeck-client"
APP_NAME="Awake on Deck"
PYTHON="/usr/bin/python3"

# ── Helpers ───────────────────────────────────────────────────────────────────
info()    { echo -e "\033[1;34m[awake]\033[0m $*"; }
success() { echo -e "\033[1;32m[awake]\033[0m $*"; }
warn()    { echo -e "\033[1;33m[awake]\033[0m $*"; }
die()     { echo -e "\033[1;31m[awake] ERROR:\033[0m $*" >&2; exit 1; }

# ── 1. Clone or update repo ───────────────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
    info "Updating existing installation at $REPO_DIR ..."
    git -C "$REPO_DIR" pull --ff-only || die "git pull failed. Resolve conflicts manually."
else
    info "Cloning $REPO_URL → $REPO_DIR ..."
    git clone "$REPO_URL" "$REPO_DIR" || die "git clone failed. Check your internet connection."
fi

[ -d "$APP_DIR" ] || die "Expected steamdeck-client/ folder not found inside repo. Check the repo structure."

cd "$APP_DIR"

# ── 2. Ensure pip is available ────────────────────────────────────────────────
info "Checking for pip ..."
if ! $PYTHON -m pip --version > /dev/null 2>&1; then
    warn "pip not found. Bootstrapping via ensurepip ..."
    if ! $PYTHON -m ensurepip --upgrade 2>/dev/null; then
        warn "ensurepip failed. Fetching get-pip.py ..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
            || die "Could not download get-pip.py. Check your internet connection."
        # --break-system-packages required on SteamOS (PEP 668 externally-managed-environment)
        $PYTHON /tmp/get-pip.py --break-system-packages \
            || die "Could not install pip."
    fi
    info "pip installed."
fi

# ── 3. Vendor dependencies into lib/ ─────────────────────────────────────────
info "Installing Python dependencies into $APP_DIR/lib/ ..."
mkdir -p lib
# --target keeps everything inside lib/, never touching the system Python
# --break-system-packages bypasses PEP 668 restriction on SteamOS
$PYTHON -m pip install \
    --target=lib \
    --upgrade \
    --break-system-packages \
    "pygame-ce>=2.4" \
    "wakeonlan>=3.0" \
    "vdf>=3.4" \
    || die "pip install failed."

success "Dependencies installed."

# ── 4. Make scripts executable ────────────────────────────────────────────────
chmod +x "$APP_DIR/launch.sh"
chmod +x "$APP_DIR/install.sh"

# ── 5. Add to Steam as a non-Steam shortcut ───────────────────────────────────
info "Adding '$APP_NAME' to Steam shortcuts ..."

# Steam must be closed while we edit shortcuts.vdf — it overwrites on exit
if pgrep -x steam > /dev/null; then
    warn "Steam is running. Closing it now to update shortcuts safely ..."
    steam -shutdown 2>/dev/null || true
    for i in $(seq 1 15); do
        pgrep -x steam > /dev/null || break
        sleep 1
    done
    pgrep -x steam > /dev/null && die "Steam did not close in time. Please close Steam manually and re-run install.sh."
    info "Steam closed."
fi

# Find the Steam userdata directory
STEAM_USERDATA="$HOME/.steam/steam/userdata"
[ -d "$STEAM_USERDATA" ] || STEAM_USERDATA="$HOME/.local/share/Steam/userdata"
[ -d "$STEAM_USERDATA" ] || die "Cannot find Steam userdata directory. Is Steam installed?"

USERID=$(ls "$STEAM_USERDATA" | grep -E '^[0-9]+$' | head -1)
[ -n "$USERID" ] || die "No Steam user ID found under $STEAM_USERDATA. Launch Steam at least once first."

SHORTCUTS_DIR="$STEAM_USERDATA/$USERID/config"
SHORTCUTS_FILE="$SHORTCUTS_DIR/shortcuts.vdf"

info "Steam user ID: $USERID"
info "Shortcuts file: $SHORTCUTS_FILE"

mkdir -p "$SHORTCUTS_DIR"

$PYTHON - <<PYEOF
import sys, os
sys.path.insert(0, "$APP_DIR/lib")

import vdf, time

shortcuts_file = "$SHORTCUTS_FILE"
launch_sh      = "$APP_DIR/launch.sh"
app_name       = "$APP_NAME"
app_dir        = "$APP_DIR"

if os.path.exists(shortcuts_file):
    with open(shortcuts_file, "rb") as f:
        data = vdf.binary_load(f)
else:
    data = {"shortcuts": {}}

shortcuts = data.get("shortcuts", {})

# Remove any existing entry with the same AppName to avoid duplicates
to_remove = [k for k, v in shortcuts.items() if v.get("AppName") == app_name or v.get("appname") == app_name]
for k in to_remove:
    del shortcuts[k]

next_key = str(max((int(k) for k in shortcuts.keys()), default=-1) + 1)

shortcuts[next_key] = {
    "AppName":             app_name,
    "Exe":                 f'"{launch_sh}"',
    "StartDir":            f'"{app_dir}"',
    "icon":                "",
    "ShortcutPath":        "",
    "LaunchOptions":       "",
    "IsHidden":            0,
    "AllowDesktopConfig":  1,
    "AllowOverlay":        1,
    "OpenVR":              0,
    "Devkit":              0,
    "DevkitGameID":        "",
    "DevkitOverrideAppID": 0,
    "LastPlayTime":        int(time.time()),
    "tags":                {},
}

data["shortcuts"] = shortcuts

with open(shortcuts_file, "wb") as f:
    vdf.binary_dump(data, f)

print(f"  Shortcut written (index {next_key}).")
PYEOF

success "'$APP_NAME' added to Steam shortcuts."

# ── 6. Relaunch Steam ─────────────────────────────────────────────────────────
info "Relaunching Steam ..."
nohup steam > /dev/null 2>&1 &
disown

success "Done! '$APP_NAME' will appear in your Steam library under Non-Steam games."
echo ""
echo "  To launch in Game Mode, find '$APP_NAME' in your library."
echo "  To update later, re-run:  bash $APP_DIR/install.sh"
echo ""