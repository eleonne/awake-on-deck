"""Supported display resolutions and their layout scale / font sizes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayMode:
    width: int
    height: int
    # Layout constants in the screens are designed for 1280-wide (scale 1.0)
    scale: float
    font_large: int
    font_medium: int
    font_small: int  # never below 28px, readable from couch distance


DEFAULT_RESOLUTION = "1920x1080"

DISPLAY_MODES: Dict[str, DisplayMode] = {
    "1920x1080": DisplayMode(1920, 1080, scale=1.5, font_large=86, font_medium=48, font_small=38),
    "1280x720": DisplayMode(1280, 720, scale=1.0, font_large=64, font_medium=36, font_small=28),
}


def display_mode(resolution: str) -> DisplayMode:
    """Look up a resolution, falling back to the default for unknown values."""
    mode = DISPLAY_MODES.get(resolution)
    if mode is None:
        logger.warning("Unsupported resolution %r, using %s", resolution, DEFAULT_RESOLUTION)
        mode = DISPLAY_MODES[DEFAULT_RESOLUTION]
    return mode
