#!/bin/bash
export SDL_VIDEODRIVER=wayland
export SDL_AUDIODRIVER=pipewire
export PYTHONPATH="/home/deck/awake-on-deck/steamdeck-client/lib:$PYTHONPATH"
cd /home/deck/awake-on-deck/steamdeck-client
exec /usr/bin/python3 main.py "$@"