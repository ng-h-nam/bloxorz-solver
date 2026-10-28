"""Test cho gui.widgets và gui.theme: chữ vừa khung, khung nổi, ô nhập và nút có chú thích phím."""

import pygame
import pytest

from gui import palette
from gui.painter import RecordingPainter
from gui.pixel_font import Typeface
from gui.theme import MINECRAFT, Theme
from gui.widgets import (
    Button,
    draw_bevel,
    draw_dialog_box,
    draw_outline,
    draw_slot,
    draw_text_field,
    fit_text,
    text_top,
    wrap_text,
)

THEME = MINECRAFT


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


BODY, SMALL = FixedTypeface(2), FixedTypeface(1)
FACES = {
    "body": BODY,
    "small": SMALL,
    "title": FixedTypeface(3),
    "banner": FixedTypeface(5),
}


# ---------------------------------------------------------------- fit_text và wrap_text


def test_fit_text_keeps_text_that_already_fits() -> None:
    assert fit_text(BODY, "abc", 36) == "abc"


def test_fit_text_truncates_with_an_ellipsis() -> None:
    shortened = fit_text(BODY, "abcdefghij", 60)
    assert shortened == "abc.." and BODY.measure(shortened)[0] <= 60


def test_fit_text_gives_nothing_when_even_the_ellipsis_does_not_fit() -> None:
    assert fit_text(BODY, "abc", 10) == ""


def test_wrap_text_breaks_on_words() -> None:
    assert wrap_text(BODY, "một hai ba bốn", 84) == [
        "một hai",
        "ba bốn",
    ]  # 7 ký tự = 84 px mỗi dòng


def test_wrap_text_splits_a_word_longer_than_a_line() -> None:
    lines = wrap_text(BODY, "x" * 25, 60)  # 5 ký tự mỗi dòng
    assert "".join(lines) == "x" * 25 and all(
        BODY.measure(line)[0] <= 60 for line in lines
    )


def test_wrap_text_of_empty_text_is_empty() -> None:
    assert wrap_text(BODY, "", 100) == [] and wrap_text(BODY, "   ", 100) == []


def test_wrap_text_marks_truncation_when_over_the_line_limit() -> None:
    lines = wrap_text(
        BODY, "aa bb cc dd ee ff gg hh", 36, max_lines=2
    )  # 3 ký tự mỗi dòng
    assert (
        len(lines) == 2
        and lines[-1].endswith("..")
        and all(BODY.measure(line)[0] <= 36 for line in lines)
    )


def test_wrap_text_without_overflow_has_no_ellipsis() -> None:
    assert wrap_text(BODY, "aa bb", 36, max_lines=2) == ["aa", "bb"]


def test_text_top_centers_a_line_vertically() -> None:
    assert text_top(pygame.Rect(0, 100, 50, 30), BODY) == 100 + (30 - 18) // 2


# ---------------------------------------------------------------- khung


def test_bevel_draws_border_face_and_four_edges() -> None:
    painter = RecordingPainter()
    draw_bevel(
        painter,
        pygame.Rect(10, 10, 100, 40),
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
        (0, 0, 0),
    )
    rects = painter.rects()
    assert (
        len(rects) == 6
        and rects[0] == pygame.Rect(10, 10, 100, 40)
        and rects[1] == pygame.Rect(11, 11, 98, 38)
    )
    assert [c.color for c in painter.commands[2:]] == [
        (2, 2, 2),
        (2, 2, 2),
        (3, 3, 3),
        (3, 3, 3),
    ]


def test_outline_is_four_thin_bars_inside_the_rect() -> None:
    painter = RecordingPainter()
    box = pygame.Rect(5, 5, 50, 30)
    draw_outline(painter, box, (9, 9, 9), 2)
    assert len(painter.rects()) == 4 and all(box.contains(r) for r in painter.rects())


def test_dialog_box_and_slot_have_opposite_lighting() -> None:
    box_painter, slot_painter = RecordingPainter(), RecordingPainter()
    area = pygame.Rect(0, 0, 60, 60)
    draw_dialog_box(box_painter, area, THEME)
    draw_slot(slot_painter, area, THEME)
    assert box_painter.commands[2].color == THEME.dialog_light  # hộp: mép trên sáng
    assert slot_painter.commands[2].color == THEME.dialog_dark  # ô lõm: mép trên tối


@pytest.mark.parametrize(
    "active, border", [(True, THEME.outline), (False, THEME.field_idle_border)]
)
def test_text_field_border_shows_whether_it_is_active(
    active: bool, border: tuple[int, int, int]
) -> None:
    painter = RecordingPainter()
    draw_text_field(painter, pygame.Rect(0, 0, 100, 40), THEME, active)
    assert painter.commands[0].color == THEME.field_face
    assert all(c.color == border for c in painter.commands[1:])


# ---------------------------------------------------------------- Theme


def test_button_colors_differ_between_states() -> None:
    normal, hover, disabled = (
        THEME.button_colors(True, False),
        THEME.button_colors(True, True),
        THEME.button_colors(False, False),
    )
    assert len({normal, hover, disabled}) == 3
    assert (
        normal[3] == THEME.text
        and hover[3] == THEME.text_hover
        and disabled[3] == THEME.text_disabled
    )


def test_a_disabled_button_ignores_hovering_in_the_theme_lookup() -> None:
    assert THEME.button_colors(False, True)[3] == THEME.text_disabled


def test_theme_is_immutable_and_replaceable() -> None:
    with pytest.raises(AttributeError):
        THEME.text = (0, 0, 0)  # type: ignore[misc]
    assert Theme(text=(1, 2, 3)).text == (1, 2, 3)


# ---------------------------------------------------------------- Button


def make_button(
    label: str = "Restart", hint: str = "R", enabled: bool = True
) -> Button:
    return Button(pygame.Rect(16, 100, 148, 30), label, "restart", hint, enabled)


def test_contains_uses_the_rect() -> None:
    button = make_button()
    assert button.contains((20, 110)) and not button.contains((200, 110))


def test_set_state_changes_only_what_is_given() -> None:
    button = make_button()
    button.set_state(enabled=False)
    assert button.label == "Restart" and not button.enabled
    button.set_state(label="Khác")
    assert button.label == "Khác" and not button.enabled
    button.set_state("Mới", True)
    assert (button.label, button.enabled) == ("Mới", True)


def test_hint_shows_only_when_there_is_room_next_to_the_label() -> None:
    assert make_button("Restart").hint_fits(
        BODY, SMALL, THEME
    )  # nhãn 84 px: còn 32 px mỗi bên
    assert not make_button("Thoát Replay").hint_fits(
        BODY, SMALL, THEME
    )  # nhãn 144 px: gần như kín nút
    assert not make_button("Restart", hint="").hint_fits(
        BODY, SMALL, THEME
    )  # không có chú thích


def test_hint_boundary_is_exact() -> None:
    # nút rộng 148, chú thích 1 ký tự (6 px) cộng 2 lề 4 px = 14 px mỗi bên: nhãn tối đa 120 px = 10 ký tự
    assert make_button("x" * 10).hint_fits(BODY, SMALL, THEME)
    assert not make_button("x" * 11).hint_fits(BODY, SMALL, THEME)


def test_draw_centers_the_label_and_puts_the_hint_in_the_corner() -> None:
    painter, button = RecordingPainter(), make_button()
    button.draw(painter, FACES, THEME)
    label, hint = painter.text_commands("Restart")[0], painter.text_commands("R")[0]
    assert label.pos[0] == 16 + (148 - 84) // 2 and label.pos[1] == text_top(
        button.rect, BODY
    )
    assert (
        hint.rect.right <= button.rect.right
        and hint.rect.top >= button.rect.top
        and hint.rect.left > label.rect.right
    )
    assert label.color == THEME.text and label.shadow and not hint.shadow


def test_draw_without_room_omits_the_hint() -> None:
    painter = RecordingPainter()
    make_button("Thoát Replay").draw(painter, FACES, THEME)
    assert painter.texts() == ["Thoát Replay"]


def test_disabled_button_uses_disabled_colors_and_no_shadow() -> None:
    painter = RecordingPainter()
    make_button(enabled=False).draw(painter, FACES, THEME)
    label = painter.text_commands("Restart")[0]
    assert label.color == THEME.text_disabled and not label.shadow
    assert painter.commands[1].color == THEME.disabled_face


def test_text_color_follows_the_state_at_every_draw() -> None:
    """Chữ không bao giờ giữ màu cũ khi trạng thái đổi (lỗi chữ xám của bản trước)."""
    button = make_button(enabled=False)
    first, second = RecordingPainter(), RecordingPainter()
    button.draw(first, FACES, THEME)
    button.set_state(enabled=True)
    button.draw(second, FACES, THEME)
    assert first.text_commands("Restart")[0].color == THEME.text_disabled
    assert second.text_commands("Restart")[0].color == THEME.text


def test_hovered_button_is_highlighted_but_a_disabled_one_is_not() -> None:
    hovered, disabled = RecordingPainter(), RecordingPainter()
    on, off = make_button(), make_button(enabled=False)
    on.hovered = off.hovered = True
    on.draw(hovered, FACES, THEME)
    off.draw(disabled, FACES, THEME)
    assert (
        hovered.text_commands("Restart")[0].color == THEME.text_hover
        and hovered.commands[1].color == THEME.hover_face
    )
    assert disabled.text_commands("Restart")[0].color == THEME.text_disabled
    assert palette.WHITE == THEME.text
