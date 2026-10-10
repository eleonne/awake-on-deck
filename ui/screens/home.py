"""Home screen for Awake on Deck."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from ui.components.button import Button
from ui.navigation import Direction, find_neighbor, hit_test

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
    pc_online: Optional[bool] = None
    font_large: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_medium: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_small: Optional[pygame.font.Font] = field(default=None, compare=False)
    buttons: List[Button] = field(default_factory=list, compare=False)
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
        """Initialize screen dimensions and create UI elements."""
        self.width = width
        self.height = height
        self.scale = scale
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.focus_index = 0
        self.pressed_index = None

        btn_width = self._px(360)
        btn_height = self._px(60)
        btn_gap = self._px(80)
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

    def _px(self, value: float) -> int:
        return round(value * self.scale)

    def _update_focus(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.focused = i == self.focus_index

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the home screen."""
        surface.fill(BG_COLOR)

        if self.font_large is not None:
            title_surf = self.font_large.render("Awake on Deck", True, WHITE)
            title_rect = title_surf.get_rect(centerx=self.width // 2, top=self._px(80))
            surface.blit(title_surf, title_rect)

        if self.font_small is not None:
            sub_surf = self.font_small.render(
                "Wake your PC and launch Steam Remote Play", True, SUBTITLE_COLOR
            )
            sub_rect = sub_surf.get_rect(centerx=self.width // 2, top=self._px(160))
            surface.blit(sub_surf, sub_rect)

            if self.pc_online is True:
                indicator_color = (60, 200, 100)
                indicator_text = "PC Online"
            elif self.pc_online is False:
                indicator_color = (200, 80, 80)
                indicator_text = "PC Offline"
            else:
                indicator_color = (150, 150, 170)
                indicator_text = "Checking..."
            ind_surf = self.font_small.render(indicator_text, True, indicator_color)
            # The default font has no "●" glyph, so the dot is drawn
            radius = ind_surf.get_height() // 4
            gap = radius * 2
            ind_rect = ind_surf.get_rect(
                centerx=self.width // 2 + radius + gap // 2, top=self._px(220)
            )
            surface.blit(ind_surf, ind_rect)
            pygame.draw.circle(
                surface, indicator_color, (ind_rect.left - gap - radius, ind_rect.centery), radius
            )

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

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A button
                if self.buttons:
                    self.buttons[self.focus_index].activate()

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
