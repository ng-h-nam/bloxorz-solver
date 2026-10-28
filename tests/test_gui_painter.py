"""Test cho gui.painter: giao diện vẽ trừu tượng và bộ vẽ ghi lệnh."""

import pygame
import pytest

from gui.painter import PaintCommand, RecordingPainter, UiPainter
from gui.pixel_font import Typeface


class FixedTypeface(Typeface):
    """Bộ chữ giả: mỗi ký tự rộng 6 x scale, cao 9 x scale."""

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


def test_ui_painter_is_abstract() -> None:
    with pytest.raises(TypeError):
        UiPainter()  # type: ignore[abstract]


def test_every_call_is_recorded_in_order() -> None:
    painter = RecordingPainter()
    painter.begin(800, 600)
    painter.fill_rect(pygame.Rect(1, 2, 3, 4), (1, 2, 3), 0.5)
    painter.draw_text(FixedTypeface(2), "abc", 10, 20, (9, 9, 9), shadow=False)
    painter.tile_texture(pygame.Rect(0, 0, 64, 64), "floor", 32, (70, 70, 70))
    painter.end()
    assert [c.kind for c in painter.commands] == [
        "begin",
        "rect",
        "text",
        "tiles",
        "end",
    ]
    assert painter.commands[0].size == (800, 600)


def test_rect_commands_keep_color_and_alpha_and_copy_the_rect() -> None:
    painter = RecordingPainter()
    source = pygame.Rect(1, 2, 3, 4)
    painter.fill_rect(source, (1, 2, 3), 0.25)
    source.x = 99  # sửa rect gốc không được làm đổi lệnh đã ghi
    command = painter.commands[0]
    assert (
        command.rect == pygame.Rect(1, 2, 3, 4)
        and command.color == (1, 2, 3)
        and command.alpha == 0.25
    )


def test_text_commands_record_the_measured_box() -> None:
    painter = RecordingPainter()
    painter.draw_text(FixedTypeface(2), "abcd", 5, 7, (255, 0, 0), shadow=True)
    command = painter.commands[0]
    assert (
        command.rect == pygame.Rect(5, 7, 48, 18)
        and command.pos == (5, 7)
        and command.shadow
    )


def test_tiles_record_texture_name_and_tile_size() -> None:
    painter = RecordingPainter()
    painter.tile_texture(pygame.Rect(0, 0, 10, 10), "floor", 64, (1, 1, 1))
    command: PaintCommand = painter.commands[0]
    assert (
        command.texture == "floor"
        and command.size == (64, 64)
        and command.color == (1, 1, 1)
    )


def test_query_helpers_filter_the_commands() -> None:
    painter = RecordingPainter()
    face = FixedTypeface()
    painter.draw_text(face, "một", 0, 0, (1, 1, 1))
    painter.draw_text(face, "hai", 0, 0, (2, 2, 2))
    painter.fill_rect(pygame.Rect(0, 0, 1, 1), (5, 5, 5))
    painter.fill_rect(pygame.Rect(0, 0, 2, 2), (6, 6, 6))
    assert painter.texts() == ["một", "hai"]
    assert [c.color for c in painter.text_commands("hai")] == [(2, 2, 2)]
    assert painter.rects() == [pygame.Rect(0, 0, 1, 1), pygame.Rect(0, 0, 2, 2)]
    assert painter.rects((6, 6, 6)) == [pygame.Rect(0, 0, 2, 2)]


def test_clear_forgets_everything() -> None:
    painter = RecordingPainter()
    painter.begin(1, 1)
    painter.clear()
    assert painter.commands == []
