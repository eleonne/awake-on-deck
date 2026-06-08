"""Settings screen for Awake on Deck."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from config import Config
from ui.components.button import Button

logger = logging.getLogger(__name__)

BG_COLOR = (26, 26, 46)
WHITE = (255, 255, 255)
ACCENT = (233, 69, 96)
SUBTITLE_COLOR = (180, 180, 200)
FIELD_BG = (40, 40, 70)
FIELD_BG_FOCUSED = (55, 55, 90)
FIELD_BG_EDITING = (30, 50, 80)
FIELD_BORDER = (80, 80, 120)
FOCUS_BORDER = 3

INT_FIELDS = {"wol_port", "poll_timeout_seconds", "poll_interval_seconds", "poll_tcp_port"}


@dataclass
class SettingsField:
    label: str
    key: str
    value: str
    rect: pygame.Rect
    focused: bool = False
    editing: bool = False
    edit_buffer: str = ""
    font: Optional[pygame.font.Font] = field(default=None, compare=False)
    label_font: Optional[pygame.font.Font] = field(default=None, compare=False)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the field label and value."""
        if self.editing:
            bg = FIELD_BG_EDITING
        elif self.focused:
            bg = FIELD_BG_FOCUSED
        else:
            bg = FIELD_BG

        pygame.draw.rect(surface, bg, self.rect, border_radius=6)

        border_color = ACCENT if self.focused else FIELD_BORDER
        pygame.draw.rect(surface, border_color, self.rect, width=FOCUS_BORDER if self.focused else 1, border_radius=6)

        pad = 8
        if self.label_font is not None:
            lbl_surf = self.label_font.render(self.label, True, SUBTITLE_COLOR)
            lbl_rect = lbl_surf.get_rect(left=self.rect.left + pad, top=self.rect.top + pad)
            surface.blit(lbl_surf, lbl_rect)

        if self.font is not None:
            display_val = self.edit_buffer if self.editing else self.value
            if self.editing:
                display_val = display_val + "|"  # cursor
            val_surf = self.font.render(display_val, True, WHITE)
            val_rect = val_surf.get_rect(
                left=self.rect.left + pad,
                bottom=self.rect.bottom - pad,
            )
            surface.blit(val_surf, val_rect)


@dataclass
class SettingsScreen:
    config: Config
    on_save: Callable[[Config], None]
    on_back: Callable[[], None]
    font_large: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_medium: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_small: Optional[pygame.font.Font] = field(default=None, compare=False)
    fields: List[SettingsField] = field(default_factory=list, compare=False)
    buttons: List[Button] = field(default_factory=list, compare=False)
    all_focusable: list = field(default_factory=list, compare=False)
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
        """Initialize settings screen with current config values."""
        self.width = width
        self.height = height
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.focus_index = 0

        field_defs = [
            ("PC IP Address", "pc_ip"),
            ("PC MAC Address", "pc_mac"),
            ("WoL Broadcast", "wol_broadcast"),
            ("WoL Port", "wol_port"),
            ("Poll Timeout (s)", "poll_timeout_seconds"),
            ("Poll Interval (s)", "poll_interval_seconds"),
            ("Poll TCP Port", "poll_tcp_port"),
        ]

        margin = 60
        top = 120
        col_width = (width - margin * 2 - 20) // 2
        field_height = 72
        row_gap = 84

        self.fields = []
        for idx, (label, key) in enumerate(field_defs):
            col = idx % 2
            row = idx // 2
            x = margin + col * (col_width + 20)
            y = top + row * row_gap
            rect = pygame.Rect(x, y, col_width, field_height)
            val = str(getattr(self.config, key, ""))
            self.fields.append(
                SettingsField(
                    label=label,
                    key=key,
                    value=val,
                    rect=rect,
                    font=font_medium,
                    label_font=font_small,
                )
            )

        btn_width = 180
        btn_height = 55
        btn_y = height - 100
        center_x = width // 2

        save_btn = Button(
            text="Save",
            rect=pygame.Rect(center_x - btn_width - 15, btn_y, btn_width, btn_height),
            on_activate=self._save,
            font=font_medium,
        )
        back_btn = Button(
            text="Back",
            rect=pygame.Rect(center_x + 15, btn_y, btn_width, btn_height),
            on_activate=self.on_back,
            font=font_medium,
        )
        self.buttons = [save_btn, back_btn]

        self.all_focusable = self.fields + self.buttons  # type: ignore[assignment]
        self._update_focus()

    def _update_focus(self) -> None:
        for i, item in enumerate(self.all_focusable):
            item.focused = i == self.focus_index

    def _current_item(self):
        if self.all_focusable:
            return self.all_focusable[self.focus_index]
        return None

    def draw(self, surface: pygame.Surface) -> None:
        """Draw settings screen."""
        surface.fill(BG_COLOR)

        if self.font_large is not None:
            title_surf = self.font_large.render("Settings", True, WHITE)
            title_rect = title_surf.get_rect(centerx=self.width // 2, top=30)
            surface.blit(title_surf, title_rect)

        for f in self.fields:
            f.draw(surface)

        for btn in self.buttons:
            btn.draw(surface)

    def handle_input(self, event: pygame.event.Event) -> None:
        """Handle keyboard and gamepad input."""
        current = self._current_item()
        is_field = isinstance(current, SettingsField)

        if event.type == pygame.KEYDOWN:
            if is_field and current.editing:
                self._handle_edit_keydown(event, current)
                return

            if event.key in (pygame.K_UP, pygame.K_w):
                self.focus_index = (self.focus_index - 1) % len(self.all_focusable)
                self._update_focus()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.focus_index = (self.focus_index + 1) % len(self.all_focusable)
                self._update_focus()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if is_field:
                    current.editing = True
                    current.edit_buffer = current.value
                elif isinstance(current, Button):
                    current.activate()
            elif event.key == pygame.K_ESCAPE:
                self.on_back()

        elif event.type == pygame.TEXTINPUT:
            current = self._current_item()
            if isinstance(current, SettingsField) and current.editing:
                current.edit_buffer += event.text

        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            if hat_y == 1:
                self.focus_index = (self.focus_index - 1) % len(self.all_focusable)
                self._update_focus()
            elif hat_y == -1:
                self.focus_index = (self.focus_index + 1) % len(self.all_focusable)
                self._update_focus()

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A
                if is_field and not current.editing:
                    current.editing = True
                    current.edit_buffer = current.value
                elif isinstance(current, Button):
                    current.activate()
            elif event.button == 1:  # B
                if is_field and current.editing:
                    current.editing = False
                    current.edit_buffer = ""
                else:
                    self.on_back()

    def _handle_edit_keydown(self, event: pygame.event.Event, f: SettingsField) -> None:
        """Handle key events while a field is being edited."""
        if event.key == pygame.K_RETURN:
            f.value = f.edit_buffer
            f.editing = False
            f.edit_buffer = ""
        elif event.key == pygame.K_ESCAPE:
            f.editing = False
            f.edit_buffer = ""
        elif event.key == pygame.K_BACKSPACE:
            f.edit_buffer = f.edit_buffer[:-1]
        # Other text input is handled via TEXTINPUT event

    def _save(self) -> None:
        """Apply field values to config and call on_save."""
        for f in self.fields:
            if f.key in INT_FIELDS:
                try:
                    setattr(self.config, f.key, int(f.value))
                except ValueError:
                    logger.warning("Invalid int value for %s: %r", f.key, f.value)
            else:
                setattr(self.config, f.key, f.value)
        logger.info("Saving settings")
        self.on_save(self.config)
