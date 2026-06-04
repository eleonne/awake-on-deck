"""StatusBar UI component showing progress steps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pygame

logger = logging.getLogger(__name__)

COLOR_DONE = (80, 200, 120)
COLOR_CURRENT_DOT = (233, 69, 96)
COLOR_CURRENT_TEXT = (255, 255, 255)
COLOR_FUTURE = (120, 120, 140)
COLOR_LINE = (80, 80, 100)

DOT_RADIUS = 8
LINE_HEIGHT = 2


@dataclass
class StatusBar:
    steps: List[str]
    current_index: int = 0
    font: Optional[pygame.font.Font] = field(default=None, compare=False)
    rect: Optional[pygame.Rect] = field(default=None, compare=False)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw step dots and labels onto the surface."""
        if not self.steps or self.rect is None:
            return

        n = len(self.steps)
        bar_x = self.rect.left
        bar_y = self.rect.top + self.rect.height // 2
        bar_width = self.rect.width

        # Evenly space dots across the bar width
        if n == 1:
            dot_positions = [bar_x + bar_width // 2]
        else:
            spacing = bar_width // (n - 1)
            dot_positions = [bar_x + i * spacing for i in range(n)]

        # Draw connecting lines between dots
        for i in range(n - 1):
            x_start = dot_positions[i]
            x_end = dot_positions[i + 1]
            line_color = COLOR_DONE if i < self.current_index else COLOR_LINE
            pygame.draw.line(
                surface,
                line_color,
                (x_start + DOT_RADIUS, bar_y),
                (x_end - DOT_RADIUS, bar_y),
                LINE_HEIGHT,
            )

        # Draw dots and labels
        for i, step in enumerate(self.steps):
            x = dot_positions[i]

            if i < self.current_index:
                dot_color = COLOR_DONE
                text_color = COLOR_DONE
            elif i == self.current_index:
                dot_color = COLOR_CURRENT_DOT
                text_color = COLOR_CURRENT_TEXT
            else:
                dot_color = COLOR_FUTURE
                text_color = COLOR_FUTURE

            pygame.draw.circle(surface, dot_color, (x, bar_y), DOT_RADIUS)

            if self.font is not None:
                label_surf = self.font.render(step, True, text_color)
                label_rect = label_surf.get_rect(
                    centerx=x, top=bar_y + DOT_RADIUS + 4
                )
                surface.blit(label_surf, label_rect)
