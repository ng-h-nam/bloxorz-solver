"""Test cho gui.ui.backdrop: nền trời chuyển sắc và mây trôi."""

from itertools import pairwise

import pygame
import pytest

from gui.ui.backdrop import Backdrop, SkyBackdrop
from gui.ui.painter import RecordingPainter

AREA = pygame.Rect(340, 0, 940, 768)


def test_backdrop_is_abstract() -> None:
    with pytest.raises(TypeError):
        Backdrop()  # type: ignore[abstract]


def test_gradient_bands_tile_the_area_exactly() -> None:
    bands = SkyBackdrop().gradient_bands(AREA)
    assert len(bands) == SkyBackdrop.BANDS
    assert bands[0][0].top == AREA.top and bands[-1][0].bottom == AREA.bottom
    for (upper, _), (lower, _) in pairwise(bands):
        assert upper.bottom == lower.top  # không hở, không chồng
    assert all(rect.x == AREA.x and rect.w == AREA.w for rect, _ in bands)


def test_gradient_goes_from_the_top_color_to_the_horizon_color() -> None:
    colors = [color for _, color in SkyBackdrop().gradient_bands(AREA)]
    assert (
        colors[0] == SkyBackdrop.TOP_COLOR and colors[-1] == SkyBackdrop.HORIZON_COLOR
    )
    assert colors == sorted(colors)  # sáng dần xuống phía chân trời


def test_clouds_never_leave_the_area_even_after_a_long_time() -> None:
    sky = SkyBackdrop()
    for seconds in (0, 3, 61, 1000, 123456):
        sky.offset = seconds * SkyBackdrop.SPEED
        pieces = sky.cloud_rects(AREA)
        assert pieces and all(AREA.contains(piece) for piece in pieces)


def test_clouds_drift_to_the_right_over_time() -> None:
    wide = pygame.Rect(0, 0, 2000, 800)
    sky = SkyBackdrop()
    before = sky.cloud_rects(wide)
    sky.update(1.0)
    after = sky.cloud_rects(wide)
    assert len(before) == len(after)
    moved = [
        a.x - b.x for a, b in zip(after, before) if b.x > 0 and a.right < wide.right
    ]  # bỏ mảnh bị cắt ở mép
    assert moved and all(shift > 0 for shift in moved)


def test_update_ignores_negative_time() -> None:
    sky = SkyBackdrop()
    sky.update(-5.0)
    assert sky.offset == 0.0


def test_draw_paints_the_sky_then_translucent_clouds() -> None:
    painter, sky = RecordingPainter(), SkyBackdrop()
    sky.draw(painter, AREA)
    rects = [c for c in painter.commands if c.kind == "rect"]
    cloud_count = len(sky.cloud_rects(AREA))
    assert len(rects) == SkyBackdrop.BANDS + cloud_count
    assert all(c.alpha == 1.0 for c in rects[: SkyBackdrop.BANDS])
    assert all(
        c.color == SkyBackdrop.CLOUD_COLOR and c.alpha == SkyBackdrop.CLOUD_ALPHA
        for c in rects[SkyBackdrop.BANDS :]
    )
