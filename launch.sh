#!/bin/bash

# Use Wayland only when Gamescope actually provides it (Game Mode).
# Big Picture mode also sets SteamGamepadUI=1 but runs on X11, so check
# WAYLAND_DISPLAY instead — Gamescope sets it; desktop/Big Picture does not.
if [ -n "$WAYLAND_DISPLAY" ]; then
    export SDL_VIDEODRIVER=wayland
    export SDL_AUDIODRIVER=pipewire
else
    export SDL_VIDEODRIVER=x11
fi

export PYTHONPATH="/home/deck/awake-on-deck/lib:$PYTHONPATH"
cd /home/deck/awake-on-deck
exec /usr/bin/python3 main.py "$@"