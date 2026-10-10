"""Status screen for Awake on Deck — shown during wake/connect flow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from ui.components.button import Button
from ui.components.status_bar import StatusBar
from ui.navigation import Direction, find_neighbor, hit_test

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
    pressed_index: Optional[int] = None
    width: int = 1280
    height: int = 800
    scale: float = 1.0

    def setup(
        self,
        width: int,
        height: int,
        font_large: pygame.font.Font,
        font_medium: pygame.font.Font,
        font_small: pygame.font.Font,
        scale: float = 1.0,
    ) -> None:
        """Initialize screen dimensions and UI elements."""
        self.width = width
        self.height = height
        self.scale = scale
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.focus_index = 0

        px = self._px
        bar_margin = px(60)
        bar_height = px(70)
        bar_rect = pygame.Rect(bar_margin, px(60), width - bar_margin * 2, bar_height)
        self.status_bar = StatusBar(
            steps=STEPS,
            current_index=0,
            font=font_small,
            rect=bar_rect,
            scale=scale,
        )

        btn_width = px(200)
        btn_height = px(55)
        center_x = width // 2
        btn_y = height - px(140)

        cancel_rect = pygame.Rect(center_x - btn_width // 2, btn_y, btn_width, btn_height)
        retry_rect = pygame.Rect(center_x - btn_width - px(20), btn_y, btn_width, btn_height)
        settings_rect = pygame.Rect(center_x + px(20), btn_y, btn_width, btn_height)

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
        self.pressed_index = None

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

    def _px(self, value: float) -> int:
        return round(value * self.scale)

    def _update_focus(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.focused = i == self.focus_index

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the status screen."""
        surface.fill(BG_COLOR)

        if self.status_bar is not None:
            self.status_bar.draw(surface)

        center_x = self.width // 2
        mid_y = self.height // 2 - self._px(40)

        if self.error_message:
            if self.font_medium is not None:
                err_surf = self.font_medium.render("Error", True, ERROR_COLOR)
                err_rect = err_surf.get_rect(centerx=center_x, top=mid_y - self._px(50))
                surface.blit(err_surf, err_rect)
            if self.font_small is not None:
                msg_surf = self.font_small.render(self.error_message, True, ERROR_COLOR)
                msg_rect = msg_surf.get_rect(centerx=center_x, top=mid_y + self._px(10))
                surface.blit(msg_surf, msg_rect)
        else:
            desc = self.status_message or _STATE_DESC.get(self.current_state, "")
            if self.font_medium is not None and desc:
                desc_surf = self.font_medium.render(desc, True, WHITE)
                desc_rect = desc_surf.get_rect(centerx=center_x, top=mid_y)
                surface.blit(desc_surf, desc_rect)

        for btn in self.buttons:
            btn.draw(surface)

    def navigate(self, direction: Direction) -> None:
        """Move focus to the nearest button in the given direction."""
        boxes = [btn.rect for btn in self.buttons]
        self.focus_index = find_neighbor(boxes, self.focus_index, direction)
        self._update_focus()

    def handle_input(self, event: pygame.event.Event) -> None:
        """Handle keyboard, gamepad and touch input."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.buttons:
                    self.buttons[self.focus_index].activate()
            elif event.key == pygame.K_ESCAPE:
                self.on_cancel()

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A button — activate
                if self.buttons:
                    self.buttons[self.focus_index].activate()
            elif event.button == 1:  # B button — cancel
                self.on_cancel()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Touch taps arrive as synthesized left-clicks in logical coordinates
            self.pressed_index = hit_test([btn.rect for btn in self.buttons], event.pos)
            if self.pressed_index is not None:
                self.focus_index = self.pressed_index
                self._update_focus()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            released = hit_test([btn.rect for btn in self.buttons], event.pos)
            pressed, self.pressed_index = self.pressed_index, None
            if released is not None and released == pressed:
                self.buttons[released].activate()
