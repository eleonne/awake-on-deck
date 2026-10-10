"""Main application class for Awake on Deck."""

from __future__ import annotations

import logging
import queue
import socket
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

import pygame

from config import Config, load_config, save_config
from discovery import DiscoveredPC, DiscoveryError, broadcast_address, discover
from poller import PollTimeoutError, poll_until_online
from ui.display import DisplayMode, display_mode
from ui.navigation import Direction, DirectionRepeater, hat_direction, stick_direction
from ui.screens.discovery import DiscoveryScreen
from ui.screens.home import HomeScreen
from ui.screens.settings import SettingsScreen
from ui.screens.status import (
    STATE_DONE,
    STATE_ERROR,
    STATE_POLLING,
    STATE_WAKING,
    StatusScreen,
)
from wol import WoLError, send_wol

logger = logging.getLogger(__name__)

FPS = 30
BG = (26, 26, 46)

_ARROW_KEYS: dict[int, Direction] = {
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
}


class Screen(Enum):
    HOME = auto()
    STATUS = auto()
    SETTINGS = auto()
    DISCOVERY = auto()


@dataclass
class StateMessage:
    state: str
    message: str = ""
    error: str = ""


@dataclass
class PcStatusMessage:
    online: bool


@dataclass
class DiscoveryMessage:
    scan_id: int
    pcs: Optional[List[DiscoveredPC]] = None
    done: bool = False
    error: str = ""


@dataclass
class AppState:
    config: Config
    current_screen: Screen = Screen.HOME
    pc_online: Optional[bool] = None
    ui_queue: queue.Queue = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    discovery_cancel: threading.Event = field(default_factory=threading.Event)
    discovery_scan_id: int = 0


class App:
    def __init__(self) -> None:
        self._state = AppState(config=load_config())
        self._joystick: Optional[pygame.joystick.JoystickType] = None
        self._previous_screen: Screen = Screen.HOME
        self._checker_stop = threading.Event()
        self._repeater = DirectionRepeater()

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption("Awake on Deck")
        self._clock = pygame.time.Clock()

        if pygame.joystick.get_count() > 0:
            self._init_joystick(0)

        threading.Thread(target=self._pc_status_worker, daemon=True).start()

        self._home_screen = HomeScreen(
            on_wake_connect=self._start_wake_connect,
            on_settings=self._open_settings,
            on_close=self._quit,
        )

        self._status_screen = StatusScreen(
            on_cancel=self._cancel,
            on_retry=self._retry,
            on_settings=self._open_settings,
        )

        self._settings_screen = SettingsScreen(
            config=self._state.config,
            on_save=self._save_settings,
            on_back=self._go_home,
            on_discover=self._open_discovery,
        )

        self._discovery_screen = DiscoveryScreen(
            on_select=self._select_discovered,
            on_rescan=self._start_discovery,
            on_back=self._close_discovery,
        )

        self._mode: Optional[DisplayMode] = None
        self._apply_display_mode(display_mode(self._state.config.resolution))

    def run(self) -> None:
        """Run the main event loop."""
        logger.info("App starting")
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break

                # ESC on home exits; ESC on other screens handled by screen
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self._state.current_screen == Screen.HOME:
                        running = False
                        break

                if event.type == pygame.JOYDEVICEADDED and self._joystick is None:
                    self._init_joystick(event.device_index)
                    continue
                if event.type == pygame.JOYDEVICEREMOVED and self._joystick is not None:
                    if event.instance_id == self._joystick.get_instance_id():
                        logger.info("Joystick disconnected")
                        self._joystick = None
                    continue

                if event.type == pygame.KEYDOWN and event.key in _ARROW_KEYS:
                    self._navigate(_ARROW_KEYS[event.key])
                    continue

                # Joystick Select button (index 4) opens settings from non-settings screens
                if event.type == pygame.JOYBUTTONDOWN and event.button == 4:
                    if self._state.current_screen not in (Screen.SETTINGS, Screen.DISCOVERY):
                        self._open_settings()
                        continue

                self._dispatch_input(event)

            step = self._repeater.update(self._held_direction(), pygame.time.get_ticks())
            if step is not None:
                self._navigate(step)

            # Drain UI queue
            while True:
                try:
                    msg = self._state.ui_queue.get_nowait()
                    if isinstance(msg, PcStatusMessage):
                        self._state.pc_online = msg.online
                        self._home_screen.pc_online = msg.online
                    elif isinstance(msg, DiscoveryMessage):
                        self._handle_discovery_message(msg)
                    else:
                        self._handle_state_message(msg)
                except queue.Empty:
                    break

            self._draw()
            pygame.display.flip()
            self._clock.tick(FPS)

        self._checker_stop.set()
        self._state.discovery_cancel.set()
        pygame.quit()
        logger.info("App exited")

    def _init_joystick(self, device_index: int) -> None:
        self._joystick = pygame.joystick.Joystick(device_index)
        self._joystick.init()
        logger.info("Joystick initialized: %s", self._joystick.get_name())

    def _held_direction(self) -> Optional[Direction]:
        """Direction currently held on the D-pad or left stick (D-pad wins)."""
        js = self._joystick
        if js is None:
            return None
        if js.get_numhats() > 0:
            direction = hat_direction(*js.get_hat(0))
            if direction is not None:
                return direction
        if js.get_numaxes() >= 2:
            return stick_direction(js.get_axis(0), js.get_axis(1))
        return None

    def _navigate(self, direction: Direction) -> None:
        screen = self._state.current_screen
        if screen == Screen.HOME:
            self._home_screen.navigate(direction)
        elif screen == Screen.STATUS:
            self._status_screen.navigate(direction)
        elif screen == Screen.SETTINGS:
            self._settings_screen.navigate(direction)
        elif screen == Screen.DISCOVERY:
            self._discovery_screen.navigate(direction)

    def _dispatch_input(self, event: pygame.event.Event) -> None:
        screen = self._state.current_screen
        if screen == Screen.HOME:
            self._home_screen.handle_input(event)
        elif screen == Screen.STATUS:
            self._status_screen.handle_input(event)
        elif screen == Screen.SETTINGS:
            self._settings_screen.handle_input(event)
        elif screen == Screen.DISCOVERY:
            self._discovery_screen.handle_input(event)

    def _draw(self) -> None:
        screen = self._state.current_screen
        if screen == Screen.HOME:
            self._home_screen.draw(self._screen)
        elif screen == Screen.STATUS:
            self._status_screen.draw(self._screen)
        elif screen == Screen.SETTINGS:
            self._settings_screen.draw(self._screen)
        elif screen == Screen.DISCOVERY:
            self._discovery_screen.draw(self._screen)

    def _start_wake_connect(self) -> None:
        """Begin the wake-and-connect flow."""
        logger.info("Starting wake & connect flow")
        self._state.cancel_event.clear()
        self._state.current_screen = Screen.STATUS
        self._status_screen.update_state(STATE_WAKING)
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _pc_status_worker(self) -> None:
        """Probe the PC periodically and push online/offline status to the UI queue."""
        while not self._checker_stop.is_set():
            cfg = self._state.config
            try:
                with socket.create_connection((cfg.pc_ip, cfg.poll_tcp_port), timeout=2):
                    self._state.ui_queue.put(PcStatusMessage(online=True))
            except OSError:
                self._state.ui_queue.put(PcStatusMessage(online=False))
            self._checker_stop.wait(10)

    def _worker(self) -> None:
        """Background thread: WoL → poll → unlock → done."""
        cfg = self._state.config
        cancel = self._state.cancel_event
        q = self._state.ui_queue

        try:
            q.put(StateMessage(STATE_WAKING, message="Sending Wake-on-LAN magic packet..."))
            send_wol(cfg, cancel)
            if cancel.is_set():
                return

            q.put(StateMessage(STATE_POLLING, message="Waiting for PC to come online..."))
            poll_until_online(cfg, cancel)
            if cancel.is_set():
                return

            q.put(StateMessage(STATE_DONE))

        except WoLError as exc:
            logger.error("WoL error: %s", exc)
            q.put(StateMessage(STATE_ERROR, error=str(exc)))
        except PollTimeoutError as exc:
            logger.error("Poll timeout: %s", exc)
            q.put(StateMessage(STATE_ERROR, error=str(exc)))
        except Exception as exc:
            logger.exception("Unexpected error in worker")
            q.put(StateMessage(STATE_ERROR, error=f"Unexpected error: {exc}"))

    def _handle_state_message(self, msg: StateMessage) -> None:
        """Update status screen from UI queue message."""
        self._status_screen.update_state(msg.state, message=msg.message, error=msg.error)
        if msg.state == STATE_DONE:
            self._go_home()

    def _cancel(self) -> None:
        """Cancel the current operation and return home."""
        logger.info("Cancelling operation")
        self._state.cancel_event.set()
        self._go_home()

    def _retry(self) -> None:
        """Retry the wake-and-connect flow."""
        logger.info("Retrying wake & connect flow")
        self._start_wake_connect()

    def _open_settings(self) -> None:
        """Switch to settings screen, refreshing it with current config."""
        logger.info("Opening settings")
        self._previous_screen = self._state.current_screen
        self._settings_screen.config = self._state.config
        self._settings_screen.setup(*self._setup_args())
        self._state.current_screen = Screen.SETTINGS

    def _save_settings(self, config: Config) -> None:
        """Save settings and return home."""
        self._state.config = config
        save_config(config)
        logger.info("Settings saved")
        mode = display_mode(config.resolution)
        if mode != self._mode:
            self._apply_display_mode(mode)
        self._go_home()

    def _apply_display_mode(self, mode: DisplayMode) -> None:
        """Open the window at `mode`'s resolution and lay out every screen for it."""
        logger.info("Display mode %dx%d", mode.width, mode.height)
        size = (mode.width, mode.height)
        flags = pygame.FULLSCREEN | pygame.SCALED
        try:
            self._screen = pygame.display.set_mode(size, flags)
        except pygame.error:
            # Some backends can't resize a SCALED window in place; recreate it
            logger.warning("Resizing the window failed, reinitialising the display", exc_info=True)
            pygame.display.quit()
            pygame.display.init()
            pygame.display.set_caption("Awake on Deck")
            self._screen = pygame.display.set_mode(size, flags)

        self._mode = mode
        self._font_large = pygame.font.SysFont(None, mode.font_large)
        self._font_medium = pygame.font.SysFont(None, mode.font_medium)
        self._font_small = pygame.font.SysFont(None, mode.font_small)

        args = self._setup_args()
        self._home_screen.setup(*args)
        self._status_screen.setup(*args)
        self._settings_screen.setup(*args)
        self._discovery_screen.setup(*args)

    def _setup_args(self) -> tuple:
        assert self._mode is not None
        return (
            self._mode.width,
            self._mode.height,
            self._font_large,
            self._font_medium,
            self._font_small,
            self._mode.scale,
        )

    def _open_discovery(self) -> None:
        """Switch to the discovery screen and start scanning."""
        logger.info("Opening discovery")
        self._discovery_screen.poll_port = self._state.config.poll_tcp_port
        self._state.current_screen = Screen.DISCOVERY
        self._start_discovery()

    def _start_discovery(self) -> None:
        """Cancel any running scan and start a new one."""
        self._state.discovery_cancel.set()
        self._state.discovery_cancel = threading.Event()
        self._state.discovery_scan_id += 1
        self._discovery_screen.start_scan()
        threading.Thread(
            target=self._discovery_worker,
            args=(
                self._state.discovery_scan_id,
                self._state.discovery_cancel,
                self._state.config.poll_tcp_port,
            ),
            daemon=True,
        ).start()

    def _discovery_worker(self, scan_id: int, cancel: threading.Event, port: int) -> None:
        """Background thread: run discovery and report results via the UI queue."""
        q = self._state.ui_queue
        try:
            discover(port, cancel, on_update=lambda pcs: q.put(DiscoveryMessage(scan_id, pcs=pcs)))
            q.put(DiscoveryMessage(scan_id, done=True))
        except DiscoveryError as exc:
            logger.error("Discovery error: %s", exc)
            q.put(DiscoveryMessage(scan_id, done=True, error=str(exc)))
        except Exception as exc:
            logger.exception("Unexpected error in discovery")
            q.put(DiscoveryMessage(scan_id, done=True, error=f"Unexpected error: {exc}"))

    def _handle_discovery_message(self, msg: DiscoveryMessage) -> None:
        if msg.scan_id != self._state.discovery_scan_id:
            return  # result of a scan that was cancelled or replaced
        if msg.pcs is not None:
            self._discovery_screen.update_results(msg.pcs)
        if msg.done:
            self._discovery_screen.finish_scan(msg.error)

    def _close_discovery(self) -> None:
        """Stop scanning and return to settings, keeping unsaved edits."""
        self._state.discovery_cancel.set()
        self._state.current_screen = Screen.SETTINGS

    def _select_discovered(self, pc: DiscoveredPC) -> None:
        """Fill settings with the chosen PC; the user still has to save."""
        self._state.discovery_cancel.set()
        self._settings_screen.apply_discovered(pc.ip, pc.mac, broadcast_address(pc.ip))
        self._state.current_screen = Screen.SETTINGS

    def _quit(self) -> None:
        """Post a QUIT event to cleanly exit the main loop."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _go_home(self) -> None:
        """Switch to home screen."""
        self._state.current_screen = Screen.HOME
