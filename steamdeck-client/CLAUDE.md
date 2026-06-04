# steamdeck-client

## Project purpose

Python GUI app that runs on a Steam Deck in **Game Mode**. It wakes a Windows PC via Wake-on-LAN, waits for it to come online, sends a UDP unlock trigger to the Windows login agent, then hands off to Steam Remote Play. The app runs as a Steam shortcut under Gamescope and must be fully navigable with the Deck's gamepad — there is no keyboard or mouse in Game Mode.

## Architecture

```
steamdeck-client/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── requirements.txt          # pinned deps, installed into lib/
├── launch.sh                 # Steam shortcut target — sets env vars, patches sys.path, exec python3 main.py
├── main.py                   # Entry point: patches sys.path, inits pygame, runs app loop
├── config.py                 # Config dataclass, load/save to ~/.config/steamdeck-client/config.json
├── wol.py                    # Wake-on-LAN: sends magic packet via UDP broadcast
├── poller.py                 # Host readiness: TCP probe loop until PC responds or timeout
├── trigger.py                # Unlock trigger: sends HMAC-signed UDP packet to windows-client agent
├── lib/                      # Vendored dependencies (pygame-ce, wakeonlan) — committed to repo
└── ui/
    ├── __init__.py
    ├── app.py                # Main pygame window, event loop, state machine driver
    ├── screens/
    │   ├── home.py           # Main screen: "Wake & Connect" button
    │   ├── status.py         # Progress screen: step indicator + current state label
    │   └── settings.py       # Settings screen: PC IP, MAC, ports, timeout, secret
    └── components/
        ├── button.py         # Focusable button, gamepad-navigable
        └── status_bar.py     # Step indicator (IDLE / WAKING / POLLING / UNLOCKING / LAUNCHING)
```

## Tech stack

- **Python 3.11+** — pre-installed on SteamOS; use `/usr/bin/python3` (absolute path always)
- **pygame-ce** (`pygame-ce>=2.4`) — GUI, gamepad input, SDL2 backend; Gamescope-compatible
- **wakeonlan** (`wakeonlan>=3.0`) — magic packet broadcast
- **stdlib only** for poller and trigger (`socket`, `subprocess`, `threading`, `hmac`, `hashlib`)

No other third-party dependencies. Keep it that way unless there is a strong reason.

## Dependency management

SteamOS system updates can wipe `--user` site-packages without warning. Dependencies are therefore installed into `lib/` inside the project directory and committed to the repo:

```bash
pip install --target=lib pygame-ce wakeonlan
```

`main.py` patches the path before any other import:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
```

Never use `pip install --user` for runtime deps. `pytest` and `pytest-mock` are dev-only and can remain in user site-packages.

## Environment

- **OS**: SteamOS (Arch Linux base), read-only root filesystem
- **Compositor**: Gamescope (Wayland) — Game Mode always runs under Gamescope
- **Python path**: `/usr/bin/python3` — always use the absolute path
- **Config dir**: `~/.config/steamdeck-client/` (writable)
- **Log dir**: `~/.local/share/steamdeck-client/` (writable)
- **Input**: Steam Input presents Deck controls as a virtual gamepad (SDL joystick index 0); keyboard/mouse are not available in Game Mode and must not be required

## Steam shortcut setup

The Steam shortcut must point to the wrapper script, not directly to Python:

- **Target**: `/home/deck/steamdeck-client/launch.sh`
- **Start in**: `/home/deck/steamdeck-client`
- **Launch options**: *(empty)*

`launch.sh` contents:

```bash
#!/bin/bash
export SDL_VIDEODRIVER=wayland
export SDL_AUDIODRIVER=pipewire
export PYTHONPATH="/home/deck/steamdeck-client/lib:$PYTHONPATH"
cd /home/deck/steamdeck-client
exec /usr/bin/python3 main.py "$@"
```

`SDL_VIDEODRIVER=wayland` is required for correct rendering under Gamescope. `xcb` may be tried as fallback if `wayland` fails, but do not default to it.

## Display

- pygame must be initialised in **fullscreen mode** — windowed mode composited under Gamescope looks broken
- Target resolution: **1280×800** (native Deck); request this explicitly on `pygame.display.set_mode`
- Use `pygame.FULLSCREEN | pygame.SCALED` flags so the app scales cleanly if Gamescope overrides the resolution

```python
screen = pygame.display.set_mode((1280, 800), pygame.FULLSCREEN | pygame.SCALED)
```

- Color scheme: dark background `#1a1a2e`, accent `#e94560`, text `#ffffff`
- Font size minimum **28px** — readable on the Deck's 7" screen from couch distance
- All layout coordinates are logical pixels at 1280×800; do not hardcode pixel values outside `ui/`

## Audio

Game Mode routes audio through PipeWire. Initialise the mixer with a small buffer to avoid latency:

```python
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
```

If the app plays no sounds, still call `pre_init` before `pygame.init()` — omitting it causes a noticeable delay on first sound event.

## Running

```bash
# Install deps into lib/ (first time or after pulling changes)
pip install --target=lib pygame-ce wakeonlan

# Run from desktop mode for development
SDL_VIDEODRIVER=wayland /usr/bin/python3 main.py

# Run with debug logging
LOG_LEVEL=DEBUG /usr/bin/python3 main.py
```

In Game Mode, the app is launched exclusively via `launch.sh` through the Steam shortcut.

## Configuration

Config is stored at `~/.config/steamdeck-client/config.json`. Created with defaults on first run.

```json
{
  "pc_mac": "10-FF-E0-CE-E8-F3",
  "pc_ip": "192.168.1.228",
  "wol_broadcast": "192.168.1.255",
  "wol_port": 9,
  "agent_port": 9876,
  "agent_secret": "",
  "poll_timeout_seconds": 90,
  "poll_interval_seconds": 3,
  "poll_tcp_port": 445
}
```

`config.py` owns all load/save logic. Never read config values directly from JSON elsewhere — always go through the `Config` dataclass.

## Flow

The app follows a strict linear state machine:

```
IDLE → WAKING → POLLING → UNLOCKING → LAUNCHING → DONE / ERROR
```

- **IDLE**: home screen, waiting for user to press "Wake & Connect"
- **WAKING**: sends WoL magic packet, transitions immediately to POLLING
- **POLLING**: TCP probe on `config.poll_tcp_port` (445) every `poll_interval_seconds` until response or timeout
- **UNLOCKING**: sends UDP payload `unlock:<hmac-sha256>` to `pc_ip:agent_port`; waits 5 s
- **LAUNCHING**: calls `subprocess.Popen(["steam", "steam://connect/..."])` to hand off to Steam Remote Play
- **ERROR**: displays error with retry and settings buttons — never exits to terminal

State transitions happen on a background thread. The UI thread only reads state and redraws — it never blocks.

## UI / gamepad conventions

- **D-pad / left stick**: navigate between focusable elements
- **A button (SDL index 0)**: confirm / activate focused element
- **B button (SDL index 1)**: back / cancel
- **Select button (SDL index 4)**: open settings from any screen
- Do **not** use the Start/Menu button for in-app navigation — it collides with the Steam overlay in Game Mode
- Focus is always visible: focused element draws a 3px `#e94560` border
- There must always be a focused element on screen; focus must never be in an invisible or off-screen state

## Code conventions

- Type hints on all function signatures
- Dataclasses for all data-carrying objects (`Config`, `AppState`, screen props)
- No global mutable state outside of the single `AppState` instance owned by `app.py`
- Background threads communicate with the UI via a `queue.Queue` — no direct attribute mutation from threads
- Log with the stdlib `logging` module; logger name matches module name (`logger = logging.getLogger(__name__)`)
- All network operations (WoL, poll, trigger) must respect a `threading.Event` cancel token so they can be interrupted when the user presses B

## Error handling

Game Mode has no terminal fallback. A crash produces a black screen and the user is dropped back to the Steam library with no explanation. This means:

- Network errors in `wol.py`, `poller.py`, `trigger.py` must raise typed exceptions (`WoLError`, `PollTimeoutError`, `TriggerError`) — never let raw `OSError` or `socket.error` propagate
- The UI catches typed exceptions and transitions to the ERROR state with a human-readable message
- `main.py` wraps the entire app loop in a `try/except BaseException` that logs the traceback to `~/.local/share/steamdeck-client/crash.log` and attempts to render an in-app error screen before exiting
- If pygame itself fails to initialise, write the error to the log file and exit with code 1 — there is nothing else to do

## Testing

```bash
pip install --user pytest pytest-mock
pytest tests/
```

- Unit tests for `wol.py`, `poller.py`, `trigger.py` using `pytest-mock` to mock sockets
- No UI tests — pygame cannot run headlessly in CI
- Tests live in `tests/` mirroring the module structure (`tests/test_wol.py`, etc.)
- Tests must not import from `lib/` — mock all external deps

## Out of scope for this client

- Streaming / video — handled entirely by Steam Remote Play after handoff
- Windows credential management — handled by `windows-client`
- Auto-discovery of PC IP/MAC — user configures these once in settings