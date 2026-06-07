"""Reusable Button UI component."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import pygame

logger = logging.getLogger(__name__)

ACCENT = (233, 69, 96)
WHITE = (255, 255, 255)
BUTTON_BG = (40, 40, 70)
BUTTON_BG_FOCUSED = (60, 60, 100)
FOCUS_BORDER = 3


@dataclass
class Button:
    text: str
    rect: pygame.Rect
    on_activate: Callable[[], None]
    focused: bool = False
    enabled: bool = True
    font: Optional[pygame.font.Font] = field(default=None, compare=False)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the button onto the given surface."""
        bg_color = BUTTON_BG_FOCUSED if self.focused else BUTTON_BG
        if not self.enabled:
            bg_color = tuple(max(0, c - 30) for c in bg_color)  # type: ignore[assignment]

        pygame.draw.rect(surface, bg_color, self.rect, border_radius=8)

        if self.focused:
            pygame.draw.rect(surface, ACCENT, self.rect, width=FOCUS_BORDER, border_radius=8)

        if self.font is not None:
            text_color = WHITE if self.enabled else (150, 150, 160)
            text_surf = self.font.render(self.text, True, text_color)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)

    def activate(self) -> None:
        """Call on_activate if the button is enabled."""
        if self.enabled:
            logger.debug("Button '%s' activated", self.text)
            self.on_activate()
