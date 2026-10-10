"""Directional navigation helpers shared by all screens.

Pure logic with no pygame dependency so it can be unit tested headlessly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

Direction = Tuple[int, int]
Point = Tuple[float, float]
Box = Tuple[float, float, float, float]  # left, top, width, height

STICK_DEADZONE = 0.5
REPEAT_DELAY_MS = 400
REPEAT_INTERVAL_MS = 150

# How much sideways offset counts against a candidate relative to distance
# along the direction of travel. Higher values prefer aligned elements.
_ALIGNMENT_WEIGHT = 2.0


def stick_direction(x: float, y: float, deadzone: float = STICK_DEADZONE) -> Optional[Direction]:
    """Convert analog stick axes to a 4-way direction, or None inside the deadzone.

    Only the dominant axis is used so diagonals never move focus twice.
    SDL reports positive y as down.
    """
    if max(abs(x), abs(y)) < deadzone:
        return None
    if abs(x) >= abs(y):
        return (1 if x > 0 else -1, 0)
    return (0, 1 if y > 0 else -1)


def hat_direction(hat_x: int, hat_y: int) -> Optional[Direction]:
    """Convert a D-pad hat value to a screen direction (down = +1), or None."""
    if hat_y:
        return (0, -hat_y)  # SDL hats report up as +1
    if hat_x:
        return (hat_x, 0)
    return None


@dataclass
class DirectionRepeater:
    """Turns a held direction into discrete steps with key-repeat timing.

    Call `update` once per frame with the currently held direction; it returns
    a direction on the frame a step should happen, otherwise None.
    """

    delay_ms: int = REPEAT_DELAY_MS
    interval_ms: int = REPEAT_INTERVAL_MS
    _held: Optional[Direction] = None
    _next_ms: int = 0

    def update(self, direction: Optional[Direction], now_ms: int) -> Optional[Direction]:
        if direction is None:
            self._held = None
            return None
        if direction != self._held:
            self._held = direction
            self._next_ms = now_ms + self.delay_ms
            return direction
        if now_ms >= self._next_ms:
            self._next_ms = now_ms + self.interval_ms
            return direction
        return None


def find_neighbor(boxes: Sequence[Box], current: int, direction: Direction) -> int:
    """Return the index of the nearest box in `direction` from boxes[current].

    Returns `current` when nothing lies in that direction.
    """
    if not boxes or not 0 <= current < len(boxes):
        return current

    dx, dy = direction
    cx, cy = _center(boxes[current])
    best = current
    best_score = float("inf")

    for i, box in enumerate(boxes):
        if i == current:
            continue
        bx, by = _center(box)
        vx, vy = bx - cx, by - cy
        along = vx * dx + vy * dy
        across = abs(vx * dy - vy * dx)
        # Only consider elements within a 45° cone of the direction of travel
        if along <= 0 or across > along:
            continue
        score = along + across * _ALIGNMENT_WEIGHT
        if score < best_score:
            best, best_score = i, score

    return best


def hit_test(boxes: Sequence[Box], pos: Point) -> Optional[int]:
    """Return the index of the box containing `pos`, or None."""
    px, py = pos
    for i, (left, top, width, height) in enumerate(boxes):
        if left <= px < left + width and top <= py < top + height:
            return i
    return None


def _center(box: Box) -> Point:
    left, top, width, height = box
    return (left + width / 2, top + height / 2)
