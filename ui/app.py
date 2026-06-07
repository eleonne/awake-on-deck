"""Main application class for Awake on Deck."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import pygame

from config import Config, load_config, save_config
from poller import PollTimeoutError, poll_until_online
from trigger import TriggerError, send_unlock
from ui.screens.home import HomeScreen
from ui.screens.settings import SettingsScreen
from ui.screens.status import (
    STATE_DONE,
    STATE_ERROR,
    STATE_POLLING,
    STATE_UNLOCKING,
    STATE_WAKING,
    StatusScreen,
)
from wol import WoLError, send_wol

logger = logging.getLogger(__name__)

WIDTH = 1280
HEIGHT = 800
FPS = 30
BG = (26, 26, 46)


class Screen(Enum):
    HOME = auto()
    STATUS = auto()
    SETTINGS = auto()


@dataclass
class StateMessage:
    state: str
    message: str = ""
    error: str = ""


@dataclass
class AppState:
    config: Config
    current_screen: Screen = Screen.HOME
    ui_queue: queue.Queue = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)


class App:
    def __init__(self) -> None:
        self._state = AppState(config=load_config())
        self._joystick: Optional[pygame.joystick.JoystickType] = None
        self._previous_screen: Screen = Screen.HOME

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption("Awake on Deck")
        self._screen = pygame.display.set_mode(
            (WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED
        )
        self._clock = pygame.time.Clock()

        if pygame.joystick.get_count() > 0:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            logger.info("Joystick initialized: %s", self._joystick.get_name())

        font_large = pygame.font.SysFont(None, 64)
        font_medium = pygame.font.SysFont(None, 36)
        font_small = pygame.font.SysFont(None, 28)

        self._home_screen = HomeScreen(
            on_wake_connect=self._start_wake_connect,
            on_settings=self._open_settings,
            on_close=self._quit,
        )
        self._home_screen.setup(WIDTH, HEIGHT, font_large, font_medium, font_small)

        self._status_screen = StatusScreen(
            on_cancel=self._cancel,
            on_retry=self._retry,
            on_settings=self._open_settings,
        )
        self._status_screen.setup(WIDTH, HEIGHT, font_large, font_medium, font_small)

        self._settings_screen = SettingsScreen(
            config=self._state.config,
            on_save=self._save_settings,
            on_back=self._go_home,
        )
        self._settings_screen.setup(WIDTH, HEIGHT, font_large, font_medium, font_small)

        self._font_large = font_large
        self._font_medium = font_medium
        self._font_small = font_small

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

                # Joystick Select button (index 4) opens settings from non-settings screens
                if event.type == pygame.JOYBUTTONDOWN and event.button == 4:
                    if self._state.current_screen != Screen.SETTINGS:
                        self._open_settings()
                        continue

                self._dispatch_input(event)

            # Drain UI queue
            while True:
                try:
                    msg = self._state.ui_queue.get_nowait()
                    self._handle_state_message(msg)
                except queue.Empty:
                    break

            self._draw()
            pygame.display.flip()
            self._clock.tick(FPS)

        pygame.quit()
        logger.info("App exited")

    def _dispatch_input(self, event: pygame.event.Event) -> None:
        screen = self._state.current_screen
        if screen == Screen.HOME:
            self._home_screen.handle_input(event)
        elif screen == Screen.STATUS:
            self._status_screen.handle_input(event)
        elif screen == Screen.SETTINGS:
            self._settings_screen.handle_input(event)

    def _draw(self) -> None:
        screen = self._state.current_screen
        if screen == Screen.HOME:
            self._home_screen.draw(self._screen)
        elif screen == Screen.STATUS:
            self._status_screen.draw(self._screen)
        elif screen == Screen.SETTINGS:
            self._settings_screen.draw(self._screen)

    def _start_wake_connect(self) -> None:
        """Begin the wake-and-connect flow."""
        logger.info("Starting wake & connect flow")
        self._state.cancel_event.clear()
        self._state.current_screen = Screen.STATUS
        self._status_screen.update_state(STATE_WAKING)
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

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

            q.put(StateMessage(STATE_UNLOCKING, message="Sending unlock signal..."))
            send_unlock(cfg, cancel)
            if cancel.is_set():
                return

            q.put(StateMessage(STATE_DONE))

        except WoLError as exc:
            logger.error("WoL error: %s", exc)
            q.put(StateMessage(STATE_ERROR, error=str(exc)))
        except PollTimeoutError as exc:
            logger.error("Poll timeout: %s", exc)
            q.put(StateMessage(STATE_ERROR, error=str(exc)))
        except TriggerError as exc:
            logger.error("Trigger error: %s", exc)
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
        self._settings_screen.setup(
            WIDTH, HEIGHT, self._font_large, self._font_medium, self._font_small
        )
        self._state.current_screen = Screen.SETTINGS

    def _save_settings(self, config: Config) -> None:
        """Save settings and return home."""
        self._state.config = config
        save_config(config)
        logger.info("Settings saved")
        self._go_home()

    def _quit(self) -> None:
        """Post a QUIT event to cleanly exit the main loop."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _go_home(self) -> None:
        """Switch to home screen."""
        self._state.current_screen = Screen.HOME
