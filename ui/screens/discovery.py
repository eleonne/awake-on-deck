"""Discovery screen: lists PCs found on the network and lets the user pick one."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame

from discovery import DiscoveredPC
from ui.components.button import Button
from ui.navigation import Direction, find_neighbor, hit_test

logger = logging.getLogger(__name__)

BG_COLOR = (26, 26, 46)
WHITE = (255, 255, 255)
ACCENT = (233, 69, 96)
SUBTITLE_COLOR = (180, 180, 200)
WARNING_COLOR = (230, 180, 90)
ERROR_COLOR = (220, 80, 80)
ROW_BG = (40, 40, 70)
ROW_BG_FOCUSED = (55, 55, 90)
ROW_BORDER = (80, 80, 120)
FOCUS_BORDER = 3
DRAG_THRESHOLD = 14


@dataclass
class DiscoveryScreen:
    on_select: Callable[[DiscoveredPC], None]
    on_rescan: Callable[[], None]
    on_back: Callable[[], None]
    poll_port: int = 445
    pcs: List[DiscoveredPC] = field(default_factory=list)
    scanning: bool = False
    error_message: str = ""
    font_large: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_medium: Optional[pygame.font.Font] = field(default=None, compare=False)
    font_small: Optional[pygame.font.Font] = field(default=None, compare=False)
    buttons: List[Button] = field(default_factory=list, compare=False)
    # Focus: 0..len(pcs)-1 are list rows, len(pcs)+i is buttons[i]
    focus_index: int = 0
    scroll: int = 0
    user_moved: bool = False
    pressed_index: Optional[int] = None
    drag_start: Optional[tuple] = None  # (y, scroll) at touch down
    dragging: bool = False
    width: int = 1280
    height: int = 800
    scale: float = 1.0
    row_height: int = 100
    row_pitch: int = 115
    list_top: int = 200
    visible_rows: int = 1

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

        px = self._px
        pad = px(11)
        self.row_height = font_medium.get_height() + font_small.get_height() + pad * 3
        self.row_pitch = self.row_height + px(10)
        self.list_top = px(40) + font_large.get_height() + font_small.get_height() + px(20)

        btn_width = px(150)
        btn_height = px(40)
        btn_y = height - px(67)
        center_x = width // 2
        list_bottom = btn_y - px(20)
        self.visible_rows = max(1, (list_bottom - self.list_top) // self.row_pitch)

        self.buttons = [
            Button(
                text="Rescan",
                rect=pygame.Rect(center_x - btn_width - px(10), btn_y, btn_width, btn_height),
                on_activate=self.on_rescan,
                font=font_medium,
            ),
            Button(
                text="Back",
                rect=pygame.Rect(center_x + px(10), btn_y, btn_width, btn_height),
                on_activate=self.on_back,
                font=font_medium,
            ),
        ]
        self._clamp_focus()

    # ── State updates from the app ────────────────────────────────────────────

    def start_scan(self) -> None:
        """Reset to an empty, scanning list with focus on Back."""
        self.pcs = []
        self.scanning = True
        self.error_message = ""
        self.scroll = 0
        self.user_moved = False
        self.pressed_index = None
        self.drag_start = None
        self.focus_index = 1  # Back
        self._update_focus()

    def update_results(self, pcs: List[DiscoveredPC]) -> None:
        """Replace the list, keeping focus on the same PC or button."""
        focused_ip = self._focused_pc().ip if self._focused_pc() else None
        button_offset = self.focus_index - len(self.pcs)

        self.pcs = list(pcs)
        if focused_ip is not None:
            ips = [pc.ip for pc in self.pcs]
            self.focus_index = ips.index(focused_ip) if focused_ip in ips else 0
        elif self.pcs and not self.user_moved:
            self.focus_index = 0  # jump to the first result until the user takes over
        else:
            self.focus_index = len(self.pcs) + button_offset
        self._clamp_focus()

    def finish_scan(self, error: str = "") -> None:
        self.scanning = False
        self.error_message = error
        if not self.pcs and not self.user_moved:
            self.focus_index = 0  # Rescan
        self._clamp_focus()

    # ── Focus helpers ─────────────────────────────────────────────────────────

    def _focused_pc(self) -> Optional[DiscoveredPC]:
        if 0 <= self.focus_index < len(self.pcs):
            return self.pcs[self.focus_index]
        return None

    def _clamp_focus(self) -> None:
        total = len(self.pcs) + len(self.buttons)
        if total:
            self.focus_index = max(0, min(self.focus_index, total - 1))
        self._ensure_visible()
        self._update_focus()

    def _px(self, value: float) -> int:
        return round(value * self.scale)

    def _update_focus(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.focused = self.focus_index == len(self.pcs) + i

    def _ensure_visible(self) -> None:
        max_scroll = max(0, len(self.pcs) - self.visible_rows)
        if self.focus_index < len(self.pcs):
            if self.focus_index < self.scroll:
                self.scroll = self.focus_index
            elif self.focus_index >= self.scroll + self.visible_rows:
                self.scroll = self.focus_index - self.visible_rows + 1
        self.scroll = max(0, min(self.scroll, max_scroll))

    def _row_rect(self, index: int) -> pygame.Rect:
        y = self.list_top + (index - self.scroll) * self.row_pitch
        margin = self._px(40)
        return pygame.Rect(margin, y, self.width - margin * 2, self.row_height)

    def _visible_indices(self) -> range:
        return range(self.scroll, min(len(self.pcs), self.scroll + self.visible_rows))

    def _focusable_boxes(self) -> List[Optional[pygame.Rect]]:
        """Rects for every focus index; None for rows scrolled out of view."""
        visible = self._visible_indices()
        rows = [self._row_rect(i) if i in visible else None for i in range(len(self.pcs))]
        return rows + [btn.rect for btn in self.buttons]

    # ── Input ─────────────────────────────────────────────────────────────────

    def navigate(self, direction: Direction) -> None:
        """Move through the list (scrolling as needed) and the buttons."""
        self.user_moved = True
        dx, dy = direction
        n = len(self.pcs)
        in_list = self.focus_index < n

        if in_list:
            if dy < 0 and self.focus_index > 0:
                self.focus_index -= 1
            elif dy > 0:
                self.focus_index = self.focus_index + 1 if self.focus_index < n - 1 else n
        else:
            if dy < 0 and n:
                # Back up into the last visible row
                self.focus_index = self._visible_indices()[-1]
            elif dx:
                boxes = [btn.rect for btn in self.buttons]
                current = self.focus_index - n
                self.focus_index = n + find_neighbor(boxes, current, direction)

        self._clamp_focus()

    def _activate(self, index: int) -> None:
        if index < len(self.pcs):
            logger.info("Selected %s", self.pcs[index])
            self.on_select(self.pcs[index])
        elif index - len(self.pcs) < len(self.buttons):
            self.buttons[index - len(self.pcs)].activate()

    def handle_input(self, event: pygame.event.Event) -> None:
        """Handle keyboard, gamepad and touch input."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(self.focus_index)
            elif event.key == pygame.K_ESCAPE:
                self.on_back()

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A
                self._activate(self.focus_index)
            elif event.button == 1:  # B
                self.on_back()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Touch taps arrive as synthesized left-clicks in logical coordinates
            self.pressed_index = self._hit(event.pos)
            self.drag_start = (event.pos[1], self.scroll)
            self.dragging = False
            if self.pressed_index is not None:
                self.user_moved = True
                self.focus_index = self.pressed_index
                self._update_focus()

        elif event.type == pygame.MOUSEMOTION and self.drag_start is not None:
            start_y, start_scroll = self.drag_start
            delta = event.pos[1] - start_y
            if abs(delta) > self._px(DRAG_THRESHOLD):
                self.dragging = True
            if self.dragging:
                max_scroll = max(0, len(self.pcs) - self.visible_rows)
                self.scroll = max(0, min(start_scroll - delta // self.row_pitch, max_scroll))

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            released = self._hit(event.pos)
            pressed, self.pressed_index = self.pressed_index, None
            dragged, self.dragging = self.dragging, False
            self.drag_start = None
            if dragged:
                # Keep focus on screen after scrolling by touch
                visible = self._visible_indices()
                if self.focus_index < len(self.pcs) and self.focus_index not in visible:
                    self.focus_index = visible[0]
                self._update_focus()
            elif released is not None and released == pressed:
                self._activate(released)

        elif event.type == pygame.MOUSEWHEEL:
            max_scroll = max(0, len(self.pcs) - self.visible_rows)
            self.scroll = max(0, min(self.scroll - event.y, max_scroll))
            visible = self._visible_indices()
            if self.focus_index < len(self.pcs) and self.focus_index not in visible:
                self.focus_index = visible[0]
            self._update_focus()

    def _hit(self, pos: tuple) -> Optional[int]:
        boxes = self._focusable_boxes()
        live = [(i, box) for i, box in enumerate(boxes) if box is not None]
        hit = hit_test([box for _, box in live], pos)
        return live[hit][0] if hit is not None else None

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _status_text(self) -> tuple:
        if self.error_message:
            return self.error_message, ERROR_COLOR
        if self.scanning:
            found = f" Found {len(self.pcs)} so far." if self.pcs else ""
            return f"Searching your network...{found}", SUBTITLE_COLOR
        if not self.pcs:
            return "No PCs found. Make sure your PC is turned on, then rescan.", SUBTITLE_COLOR
        noun = "PC" if len(self.pcs) == 1 else "PCs"
        return f"Found {len(self.pcs)} {noun}. Choose yours.", SUBTITLE_COLOR

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the discovery screen."""
        surface.fill(BG_COLOR)
        center_x = self.width // 2

        if self.font_large is not None:
            title = self.font_large.render("Find PCs", True, WHITE)
            surface.blit(title, title.get_rect(centerx=center_x, top=self._px(20)))

        if self.font_small is not None:
            text, color = self._status_text()
            status = self.font_small.render(text, True, color)
            top = self._px(20) + (self.font_large.get_height() if self.font_large else 0) + self._px(10)
            surface.blit(status, status.get_rect(centerx=center_x, top=top))

        for i in self._visible_indices():
            self._draw_row(surface, i)

        arrow = self._px(9)
        if self.scroll > 0:
            y = self.list_top - self._px(12)
            pygame.draw.polygon(
                surface, SUBTITLE_COLOR,
                [(center_x - arrow, y + arrow // 2), (center_x + arrow, y + arrow // 2), (center_x, y - arrow // 2)],
            )
        if self.scroll + self.visible_rows < len(self.pcs):
            y = self.list_top + self.visible_rows * self.row_pitch
            pygame.draw.polygon(
                surface, SUBTITLE_COLOR,
                [(center_x - arrow, y - arrow // 2), (center_x + arrow, y - arrow // 2), (center_x, y + arrow // 2)],
            )

        for btn in self.buttons:
            btn.draw(surface)

    def _draw_row(self, surface: pygame.Surface, index: int) -> None:
        pc = self.pcs[index]
        rect = self._row_rect(index)
        focused = index == self.focus_index

        pygame.draw.rect(surface, ROW_BG_FOCUSED if focused else ROW_BG, rect, border_radius=8)
        pygame.draw.rect(
            surface,
            ACCENT if focused else ROW_BORDER,
            rect,
            width=FOCUS_BORDER if focused else 1,
            border_radius=8,
        )

        pad = self._px(11)
        if self.font_medium is not None:
            name = self.font_medium.render(pc.name or "Unknown device", True, WHITE)
            surface.blit(name, (rect.left + pad, rect.top + pad))

        if self.font_small is not None:
            details = f"{pc.ip}    {pc.mac or 'MAC unknown'}"
            detail_surf = self.font_small.render(details, True, SUBTITLE_COLOR)
            detail_rect = detail_surf.get_rect(left=rect.left + pad, bottom=rect.bottom - pad)
            surface.blit(detail_surf, detail_rect)

            if not pc.port_open and not self.scanning:
                warn = self.font_small.render(f"Port {self.poll_port} closed", True, WARNING_COLOR)
                surface.blit(warn, warn.get_rect(right=rect.right - pad, centery=rect.centery))
