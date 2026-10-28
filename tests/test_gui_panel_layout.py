"""Bố cục của cột bên trái: không chồng lấn, mọi chữ nằm trong khung, ở mọi chiều cao cửa sổ hợp lý."""

import os
from collections.abc import Mapping

import pygame
import pytest

from gui import control_panel as cp
from gui.painter import RecordingPainter
from gui.pixel_font import MONOCRAFT_PATH, ROLE_SCALES, MinecraftTypeface, Typeface
from gui.viewmodels import HudData

pygame.font.init()
HEIGHTS = [640, 720, 768, 900, 1080]


class FixedTypeface(Typeface):
    """Bộ chữ giả: mỗi ký tự rộng 6 x scale, cao 9 x scale (đúng với chữ Latinh của Monocraft)."""

    def __init__(self, scale: int = 1) -> None:
        self.scale = scale
        self.top_padding = 4 * scale

    def measure(self, text: str) -> tuple[int, int]:
        return len(text) * 6 * self.scale, 9 * self.scale

    def render(
        self, text: str, color: tuple[int, int, int], shadow: bool = True
    ) -> pygame.Surface:
        return pygame.Surface(
            (max(1, len(text) * 6 * self.scale), 15 * self.scale), pygame.SRCALPHA
        )


def build_faces(kind: str) -> Mapping[str, Typeface]:
    if kind == "real":
        if not os.path.exists(MONOCRAFT_PATH):
            pytest.skip("thiếu assets/fonts/Monocraft.ttf")
        return {
            role: MinecraftTypeface(MONOCRAFT_PATH, scale)
            for role, (scale, _) in ROLE_SCALES.items()
        }
    return {role: FixedTypeface(scale) for role, (scale, _) in ROLE_SCALES.items()}


@pytest.fixture(params=["fixed", "real"])
def faces(request: pytest.FixtureRequest) -> Mapping[str, Typeface]:
    return build_faces(request.param)


def make_panel(
    faces: Mapping[str, Typeface], height: int = 768
) -> tuple[cp.ControlPanel, RecordingPainter]:
    painter = RecordingPainter()
    return cp.ControlPanel(1280, height, painter, faces), painter


def busy_hud() -> HudData:
    return HudData(
        "Stage 33",
        123,
        "HORIZONTAL",
        "PLAYING",
        3599.9,
        "123456",
        "nguoi_choi_ten_dai",
        "123 bước (3599.9s)",
        "BFS",
        False,
        True,
        True,
        100,
        120,
        "0.5x",
        2,
    )


def test_constants_describe_a_consistent_column() -> None:
    assert (
        cp.PANEL_WIDTH == 340
        and cp.PANEL_PADDING * 2 + 2 * cp.BUTTON_WIDTH + cp.BUTTON_COL_GAP
        == cp.PANEL_WIDTH
    )
    assert len(cp.BUTTON_SPECS) == cp.BUTTON_ROWS * 2
    assert len({spec[1] for spec in cp.BUTTON_SPECS}) == len(
        cp.BUTTON_SPECS
    )  # mã hành động không trùng


@pytest.mark.parametrize("height", HEIGHTS)
def test_sections_stack_without_overlap(
    faces: Mapping[str, Typeface], height: int
) -> None:
    panel, _ = make_panel(faces, height)
    body_h = faces["body"].measure("A")[1]
    title_h = faces["title"].measure("A")[1]
    assert cp.TITLE_Y + title_h <= cp.INFO_TOP
    assert cp.INFO_STEP >= body_h
    assert cp.INFO_TOP + (cp.INFO_COUNT - 1) * cp.INFO_STEP + body_h <= cp.BUTTON_TOP
    assert (
        cp.BUTTON_TOP + (cp.BUTTON_ROWS - 1) * cp.BUTTON_STEP + cp.BUTTON_HEIGHT
        <= cp.MESSAGE_TOP
    )
    assert cp.MESSAGE_STEP >= body_h
    assert panel.message_capacity >= 1
    assert cp.MESSAGE_TOP + panel.message_capacity * cp.MESSAGE_STEP <= panel.help_top
    assert (
        panel.help_top >= 0
        and panel.help_top + len(panel.help_lines) * cp.HELP_STEP <= height
    )


def test_buttons_are_laid_out_in_two_columns_inside_the_panel(
    faces: Mapping[str, Typeface],
) -> None:
    panel, _ = make_panel(faces)
    for index, button in enumerate(panel.buttons):
        assert (
            button.rect.left >= cp.PANEL_PADDING
            and button.rect.right <= cp.PANEL_WIDTH - cp.PANEL_PADDING
        )
        assert button.rect.bottom <= cp.MESSAGE_TOP
        assert button.rect.x == cp.PANEL_PADDING + (index % 2) * (
            cp.BUTTON_WIDTH + cp.BUTTON_COL_GAP
        )
    assert not any(
        a.rect.colliderect(b.rect)
        for i, a in enumerate(panel.buttons)
        for b in panel.buttons[i + 1 :]
    )


def test_every_button_label_fits_inside_its_button(
    faces: Mapping[str, Typeface],
) -> None:
    labels = [spec[0] for spec in cp.BUTTON_SPECS]
    labels += [f"AI: {name}" for name in ("BFS", "DFS", "UCS", "A*")]
    labels += ["Hủy giải", "Giải AI", "Tạm dừng", "Tiếp tục"] + [
        f"Tốc độ {speed}" for speed in ("0.5x", "1x", "2x", "4x")
    ]
    for label in labels:
        assert faces["body"].measure(label)[0] <= cp.BUTTON_WIDTH - 8, (
            label
        )  # chừa chỗ cho viền và mép nổi


def test_help_lines_fit_the_column(faces: Mapping[str, Typeface]) -> None:
    panel, _ = make_panel(faces)
    assert all(
        faces["small"].measure(line)[0] <= panel.content_width
        for line in panel.help_lines
    )
    assert "".join(panel.help_lines).replace(" ", "") == "".join(cp.HELP_LINES).replace(
        " ", ""
    )  # chia dòng không làm mất chữ


@pytest.mark.parametrize("height", [640, 768])
def test_nothing_drawn_in_the_column_leaves_it(
    faces: Mapping[str, Typeface], height: int
) -> None:
    panel, painter = make_panel(faces, height)
    panel.draw(busy_hud(), "một thông báo khá dài " * 12)
    for command in painter.text_commands():
        assert command.rect.right <= cp.PANEL_WIDTH - cp.PANEL_PADDING + 1, command.text
        assert command.rect.bottom <= height, command.text


def test_info_rows_do_not_overlap_the_next_section(
    faces: Mapping[str, Typeface],
) -> None:
    panel, painter = make_panel(faces)
    panel.draw(busy_hud(), "")
    info = [
        c
        for c in painter.text_commands()
        if cp.INFO_TOP <= c.pos[1] < cp.BUTTON_TOP - 4
    ]
    assert info and all(c.rect.bottom <= cp.BUTTON_TOP for c in info)
