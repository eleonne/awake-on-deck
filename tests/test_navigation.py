"""Tests for ui/navigation.py."""

from ui.navigation import (
    DirectionRepeater,
    find_neighbor,
    hat_direction,
    hit_test,
    stick_direction,
)

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)

# Two-column grid of fields with Save / Back buttons below, like the settings screen
GRID = [
    (0, 0, 100, 40), (120, 0, 100, 40),
    (0, 60, 100, 40), (120, 60, 100, 40),
    (0, 120, 100, 40),
    (40, 200, 60, 30), (120, 200, 60, 30),  # Save, Back
]


class TestStickDirection:
    def test_inside_deadzone_is_none(self):
        assert stick_direction(0.2, -0.3) is None

    def test_dominant_axis_wins(self):
        assert stick_direction(0.9, 0.6) == RIGHT
        assert stick_direction(-0.4, -0.8) == UP

    def test_positive_y_is_down(self):
        assert stick_direction(0.0, 1.0) == DOWN


class TestHatDirection:
    def test_centered_is_none(self):
        assert hat_direction(0, 0) is None

    def test_hat_up_maps_to_screen_up(self):
        assert hat_direction(0, 1) == UP
        assert hat_direction(0, -1) == DOWN

    def test_horizontal(self):
        assert hat_direction(-1, 0) == LEFT
        assert hat_direction(1, 0) == RIGHT


class TestDirectionRepeater:
    def test_first_press_steps_immediately(self):
        r = DirectionRepeater(delay_ms=400, interval_ms=150)
        assert r.update(DOWN, 0) == DOWN

    def test_holding_waits_for_delay_then_repeats(self):
        r = DirectionRepeater(delay_ms=400, interval_ms=150)
        r.update(DOWN, 0)
        assert r.update(DOWN, 399) is None
        assert r.update(DOWN, 400) == DOWN
        assert r.update(DOWN, 549) is None
        assert r.update(DOWN, 550) == DOWN

    def test_release_resets(self):
        r = DirectionRepeater(delay_ms=400, interval_ms=150)
        r.update(DOWN, 0)
        assert r.update(None, 10) is None
        assert r.update(DOWN, 20) == DOWN

    def test_changing_direction_steps_immediately(self):
        r = DirectionRepeater(delay_ms=400, interval_ms=150)
        r.update(DOWN, 0)
        assert r.update(RIGHT, 50) == RIGHT


class TestFindNeighbor:
    def test_moves_within_grid(self):
        assert find_neighbor(GRID, 0, RIGHT) == 1
        assert find_neighbor(GRID, 0, DOWN) == 2
        assert find_neighbor(GRID, 3, LEFT) == 2
        assert find_neighbor(GRID, 3, UP) == 1

    def test_stays_put_at_edge(self):
        assert find_neighbor(GRID, 0, UP) == 0
        assert find_neighbor(GRID, 0, LEFT) == 0
        assert find_neighbor(GRID, 6, RIGHT) == 6

    def test_down_from_last_field_reaches_buttons(self):
        assert find_neighbor(GRID, 4, DOWN) == 5

    def test_between_buttons(self):
        assert find_neighbor(GRID, 5, RIGHT) == 6
        assert find_neighbor(GRID, 6, LEFT) == 5

    def test_vertical_list(self):
        column = [(0, 0, 100, 40), (0, 80, 100, 40), (0, 160, 100, 40)]
        assert find_neighbor(column, 0, DOWN) == 1
        assert find_neighbor(column, 2, UP) == 1
        assert find_neighbor(column, 1, RIGHT) == 1

    def test_empty_or_invalid_index(self):
        assert find_neighbor([], 0, DOWN) == 0
        assert find_neighbor(GRID, 99, DOWN) == 99


class TestHitTest:
    def test_hits_box(self):
        assert hit_test(GRID, (130, 70)) == 3

    def test_miss(self):
        assert hit_test(GRID, (110, 50)) is None

    def test_right_and_bottom_edges_are_exclusive(self):
        assert hit_test([(0, 0, 10, 10)], (10, 5)) is None
        assert hit_test([(0, 0, 10, 10)], (9, 9)) == 0
