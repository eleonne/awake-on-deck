"""Status screen for Awake on Deck — shown during wake/connect flow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from ui.components.button import Button
from ui.components.status_bar import StatusBar

logger = logging.getLogger(__name__)

BG_COLOR = (26, 26, 46)
WHITE = (255, 255, 255)
ACCENT = (233, 69, 96)
ERROR_COLOR = (220, 80, 80)
SUBTITLE_COLOR = (180, 180, 200)

STEPS = ["Waking", "Online"]

STATE_WAKING = "WAKING"
STATE_POLLING = "POLLING"
STATE_DONE = "DONE"
STATE_ERROR = "ERROR"

_STATE_STEP = {
    STATE_WAKING: 0,
    STATE_POLLING: 1,
    STATE_DONE: 2,
    STATE_ERROR: 0,
}

_STATE_DESC = {
    STATE_WAKING: "Sending Wake-on-LAN magic packet...",
    STATE_POLLING: "Waiting for PC to come online...",
    STATE_DONE: "Done!",
}


@dataclass
class StatusScreen:
    on_cancel: Callable[[], None]
    on_retry: Callable[[], None]
    on_settings: Callable[[], None]
    status_message: str = ""
    error_message: str = ""
    current_state: str = STATE_WAKING
    font_large: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_medium: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_small: Optional[pygame.font.Font] = field(default=None, compare=False)
    buttons: List[Button] = field(default_factory=list, compare=False)
    status_bar: Optional[StatusBar] = field(default=None, compare=False)
    focus_index: int = 0
    width: int = 1280
    height: int = 800

    def setup(
        self,
        width: int,
        height: int,
        font_large: pygame.font.Font,
        font_medium: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        """Initialize screen dimensions and UI elements."""
        self.width = width
        self.height = height
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.focus_index = 0

        bar_margin = 60
        bar_height = 70
        bar_rect = pygame.Rect(bar_margin, 60, width - bar_margin * 2, bar_height)
        self.status_bar = StatusBar(
            steps=STEPS,
            current_index=0,
            font=font_small,
            rect=bar_rect,
        )

        btn_width = 200
        btn_height = 55
        center_x = width // 2
        btn_y = height - 140

        cancel_rect = pygame.Rect(center_x - btn_width // 2, btn_y, btn_width, btn_height)
        retry_rect = pygame.Rect(center_x - btn_width - 20, btn_y, btn_width, btn_height)
        settings_rect = pygame.Rect(center_x + 20, btn_y, btn_width, btn_height)

        self._cancel_btn = Button(
            text="Cancel",
            rect=cancel_rect,
            on_activate=self.on_cancel,
            focused=True,
            font=font_medium,
        )
        self._retry_btn = Button(
            text="Retry",
            rect=retry_rect,
            on_activate=self.on_retry,
            focused=True,
            font=font_medium,
        )
        self._settings_btn = Button(
            text="Settings",
            rect=settings_rect,
            on_activate=self.on_settings,
            focused=False,
            font=font_medium,
        )

        self.buttons = [self._cancel_btn]

    def update_state(self, state: str, message: str = "", error: str = "") -> None:
        """Update the current operation state."""
        logger.debug("StatusScreen update_state: %s message=%r error=%r", state, message, error)
        self.current_state = state
        self.status_message = message
        self.error_message = error
        self.focus_index = 0

        step_index = _STATE_STEP.get(state, 0)
        if self.status_bar is not None:
            self.status_bar.current_index = step_index

        if error:
            self.buttons = [self._retry_btn, self._settings_btn]
            self._retry_btn.focused = True
            self._settings_btn.focused = False
        else:
            self.buttons = [self._cancel_btn]
            self._cancel_btn.focused = True

    def _update_focus(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.focused = i == self.focus_index

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the status screen."""
        surface.fill(BG_COLOR)

        if self.status_bar is not None:
            self.status_bar.draw(surface)

        center_x = self.width // 2
        mid_y = self.height // 2 - 40

        if self.error_message:
            if self.font_medium is not None:
                err_surf = self.font_medium.render("Error", True, ERROR_COLOR)
                err_rect = err_surf.get_rect(centerx=center_x, top=mid_y - 50)
                surface.blit(err_surf, err_rect)
            if self.font_small is not None:
                msg_surf = self.font_small.render(self.error_message, True, ERROR_COLOR)
                msg_rect = msg_surf.get_rect(centerx=center_x, top=mid_y + 10)
                surface.blit(msg_surf, msg_rect)
        else:
            desc = self.status_message or _STATE_DESC.get(self.current_state, "")
            if self.font_medium is not None and desc:
                desc_surf = self.font_medium.render(desc, True, WHITE)
                desc_rect = desc_surf.get_rect(centerx=center_x, top=mid_y)
                surface.blit(desc_surf, desc_rect)

        for btn in self.buttons:
            btn.draw(surface)

    def handle_input(self, event: pygame.event.Event) -> None:
        """Handle keyboard and gamepad input."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                if len(self.buttons) > 1:
                    self.focus_index = (self.focus_index - 1) % len(self.buttons)
                    self._update_focus()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if len(self.buttons) > 1:
                    self.focus_index = (self.focus_index + 1) % len(self.buttons)
                    self._update_focus()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.buttons:
                    self.buttons[self.focus_index].activate()
            elif event.key == pygame.K_ESCAPE:
                self.on_cancel()

        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            if hat_x == -1 and len(self.buttons) > 1:
                self.focus_index = (self.focus_index - 1) % len(self.buttons)
                self._update_focus()
            elif hat_x == 1 and len(self.buttons) > 1:
                self.focus_index = (self.focus_index + 1) % len(self.buttons)
                self._update_focus()

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A button — activate
                if self.buttons:
                    self.buttons[self.focus_index].activate()
            elif event.button == 1:  # B button — cancel
                self.on_cancel()
