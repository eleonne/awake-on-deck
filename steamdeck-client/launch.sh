#!/bin/bash

# In Game Mode, Gamescope provides Wayland. In Desktop Mode, use x11.
if [ "$SteamGamepadUI" = "1" ]; then
    export SDL_VIDEODRIVER=wayland
    export SDL_AUDIODRIVER=pipewire
else
    export SDL_VIDEODRIVER=x11
fi

export PYTHONPATH="/home/deck/awake-on-deck/steamdeck-client/lib:$PYTHONPATH"
cd /home/deck/awake-on-deck/steamdeck-client
exec /usr/bin/python3 main.py "$@"