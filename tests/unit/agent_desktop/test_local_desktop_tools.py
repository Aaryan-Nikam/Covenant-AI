from __future__ import annotations

from azmeth_agent.local_desktop_tools import scale_point


def test_scale_point_maps_capture_space_to_screen_space() -> None:
    assert scale_point(640, 360, (1280, 720), (2560, 1440)) == (1280, 720)


def test_scale_point_clamps_to_screen_bounds() -> None:
    assert scale_point(2000, -10, (1280, 720), (2560, 1440)) == (2559, 0)


def test_scale_point_uses_input_coordinates_without_capture_size() -> None:
    assert scale_point(100, 200, None, (2560, 1440)) == (100, 200)
