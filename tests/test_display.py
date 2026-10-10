"""Tests for ui/display.py."""

from config import Config
from ui.display import DEFAULT_RESOLUTION, DISPLAY_MODES, display_mode


def test_default_is_1080p():
    assert DEFAULT_RESOLUTION == "1920x1080"
    assert Config().resolution == DEFAULT_RESOLUTION


def test_supported_modes():
    assert (display_mode("1920x1080").width, display_mode("1920x1080").height) == (1920, 1080)
    assert (display_mode("1280x720").width, display_mode("1280x720").height) == (1280, 720)


def test_unknown_falls_back_to_default():
    assert display_mode("800x600") == DISPLAY_MODES[DEFAULT_RESOLUTION]
    assert display_mode("") == DISPLAY_MODES[DEFAULT_RESOLUTION]


def test_fonts_meet_minimum_size():
    for mode in DISPLAY_MODES.values():
        assert mode.font_small >= 28
