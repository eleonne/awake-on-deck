"""Home screen for Awake on Deck."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from ui.components.button import Button

logger = logging.getLogger(__name__)

BG_COLOR = (26, 26, 46)
WHITE = (255, 255, 255)
ACCENT = (233, 69, 96)
SUBTITLE_COLOR = (180, 180, 200)


@dataclass
class HomeScreen:
    on_wake_connect: Callable[[], None]
    on_settings: Callable[[], None]
    on_close: Callable[[], None] = field(default=lambda: None)
    font_large: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_medium: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_small: Optional[pygame.font.Font] = field(default=None, compare=False)
    buttons: List[Button] = field(default_factory=list, compare=False)
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
        """Initialize screen dimensions and create UI elements."""
        self.width = width
        self.height = height
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.focus_index = 0

        btn_width = 360
        btn_height = 60
        btn_gap = 80
        center_x = width // 2
        top = height // 2 - btn_height - btn_gap // 2

        self.buttons = [
            Button(
                text="Wake & Connect",
                rect=pygame.Rect(center_x - btn_width // 2, top, btn_width, btn_height),
                on_activate=self.on_wake_connect,
                focused=True,
                font=font_medium,
            ),
            Button(
                text="Settings",
                rect=pygame.Rect(center_x - btn_width // 2, top + btn_gap, btn_width, btn_height),
                on_activate=self.on_settings,
                focused=False,
                font=font_medium,
            ),
            Button(
                text="Close",
                rect=pygame.Rect(center_x - btn_width // 2, top + btn_gap * 2, btn_width, btn_height),
                on_activate=self.on_close,
                focused=False,
                font=font_medium,
            ),
        ]

    def _update_focus(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.focused = i == self.focus_index

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the home screen."""
        surface.fill(BG_COLOR)

        if self.font_large is not None:
            title_surf = self.font_large.render("Awake on Deck", True, WHITE)
            title_rect = title_surf.get_rect(centerx=self.width // 2, top=80)
            surface.blit(title_surf, title_rect)

        if self.font_small is not None:
            sub_surf = self.font_small.render(
                "Wake your PC and launch Steam Remote Play", True, SUBTITLE_COLOR
            )
            sub_rect = sub_surf.get_rect(centerx=self.width // 2, top=160)
            surface.blit(sub_surf, sub_rect)

        for btn in self.buttons:
            btn.draw(surface)

    def handle_input(self, event: pygame.event.Event) -> None:
        """Handle keyboard and gamepad input."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.focus_index = (self.focus_index - 1) % len(self.buttons)
                self._update_focus()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.focus_index = (self.focus_index + 1) % len(self.buttons)
                self._update_focus()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.buttons:
                    self.buttons[self.focus_index].activate()

        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            if hat_y == 1:  # D-pad up
                self.focus_index = (self.focus_index - 1) % len(self.buttons)
                self._update_focus()
            elif hat_y == -1:  # D-pad down
                self.focus_index = (self.focus_index + 1) % len(self.buttons)
                self._update_focus()

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A button
                if self.buttons:
                    self.buttons[self.focus_index].activate()
