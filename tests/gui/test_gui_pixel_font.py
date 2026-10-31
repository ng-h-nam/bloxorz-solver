"""Test cho gui.ui.pixel_font: chữ Monocraft có ghép dấu tiếng Việt và bộ chữ dự phòng."""

import os
import unicodedata

import pygame
import pytest

from gui.ui.pixel_font import (
    FALLBACK_PATH,
    GLYPH_ROWS,
    HEAD_ROWS,
    MONOCRAFT_PATH,
    ROLE_SCALES,
    MinecraftTypeface,
    TrueTypeTypeface,
    Typeface,
    build_typefaces,
)

pygame.font.init()
needs_monocraft = pytest.mark.skipif(not os.path.exists(MONOCRAFT_PATH), reason="thiếu assets/fonts/Monocraft.ttf")
needs_fallback = pytest.mark.skipif(not os.path.exists(FALLBACK_PATH), reason="thiếu assets/fonts/DejaVuSans.ttf")
WHITE = (255, 255, 255)
TONES = ["\u0300", "\u0301", "\u0309", "\u0303", "\u0323"]


def vietnamese_letters() -> list[str]:
    """Mọi chữ cái tiếng Việt có dấu (hoa và thường), kể cả đ và Đ."""
    letters: set[str] = set("đĐ")
    for base in "aăâeêioôơuưyAĂÂEÊIOÔƠUƯY":
        letters.add(base)
        for tone in TONES:
            letters.add(unicodedata.normalize("NFC", base + tone))
    return sorted(letters)


def ink_box(face: Typeface, text: str) -> pygame.Rect:
    """Hình chữ nhật bao quanh phần có mực của `text` (không bóng)."""
    mask = pygame.mask.from_surface(face.render(text, WHITE, shadow=False))
    return mask.get_bounding_rects()[0].unionall(mask.get_bounding_rects()[1:])


def pixels_of(face: Typeface, text: str) -> bytes:
    return pygame.image.tobytes(face.render(text, WHITE, shadow=False), "RGBA")


@pytest.fixture(scope="module")
def face() -> MinecraftTypeface:
    return MinecraftTypeface(MONOCRAFT_PATH, scale=1)


def test_typeface_is_abstract() -> None:
    with pytest.raises(TypeError):
        Typeface()  # type: ignore[abstract]


@needs_monocraft
def test_every_vietnamese_letter_has_its_own_shape(face: MinecraftTypeface) -> None:
    placeholder = pixels_of(face, "?")
    for letter in vietnamese_letters():
        surface = face.render(letter, WHITE, shadow=False)
        assert pygame.mask.from_surface(surface).count() > 0, letter
        assert pixels_of(face, letter) != placeholder, letter


@needs_monocraft
def test_accented_letters_differ_from_each_other(face: MinecraftTypeface) -> None:
    shapes = {pixels_of(face, letter) for letter in vietnamese_letters()}
    assert len(shapes) == len(vietnamese_letters())


@needs_monocraft
def test_a_tone_mark_adds_ink_above_the_letter(face: MinecraftTypeface) -> None:
    assert ink_box(face, "ấ").top < ink_box(face, "a").top
    assert ink_box(face, "Ế").top < ink_box(face, "E").top


@needs_monocraft
def test_a_dot_below_adds_ink_under_the_letter(face: MinecraftTypeface) -> None:
    assert ink_box(face, "ạ").bottom > ink_box(face, "a").bottom


@needs_monocraft
def test_stroked_d_and_horned_vowels_are_not_plain_letters(
    face: MinecraftTypeface,
) -> None:
    for plain, special in [("d", "đ"), ("D", "Đ"), ("o", "ơ"), ("u", "ư")]:
        assert pixels_of(face, plain) != pixels_of(face, special)


@needs_monocraft
def test_unknown_characters_fall_back_to_a_question_mark(
    face: MinecraftTypeface,
) -> None:
    assert pixels_of(face, "\u4e2d") == pixels_of(face, "?")


@needs_monocraft
def test_measure_matches_the_rendered_width_and_scales_with_the_factor() -> None:
    small, big = (
        MinecraftTypeface(MONOCRAFT_PATH, 1),
        MinecraftTypeface(MONOCRAFT_PATH, 3),
    )
    text = "Chọn màn Stage 01"
    assert small.render(text, WHITE, shadow=False).get_width() == small.measure(text)[0]
    assert big.measure(text) == (small.measure(text)[0] * 3, GLYPH_ROWS * 3)
    assert big.top_padding == HEAD_ROWS * 3


@needs_monocraft
def test_shadow_adds_one_native_pixel_each_way() -> None:
    face = MinecraftTypeface(MONOCRAFT_PATH, 2)
    plain, shadowed = (
        face.render("Abc", WHITE, shadow=False),
        face.render("Abc", WHITE, shadow=True),
    )
    assert shadowed.get_width() == plain.get_width() + 2 and shadowed.get_height() == plain.get_height() + 2


@needs_monocraft
def test_scale_is_clamped_to_at_least_one() -> None:
    assert MinecraftTypeface(MONOCRAFT_PATH, 0).scale == 1


@needs_monocraft
def test_empty_text_still_renders_a_valid_surface(face: MinecraftTypeface) -> None:
    assert face.render("", WHITE).get_width() >= 1 and face.measure("") == (
        0,
        GLYPH_ROWS,
    )


@needs_monocraft
def test_build_typefaces_uses_monocraft_for_every_role() -> None:
    faces = build_typefaces(MONOCRAFT_PATH, FALLBACK_PATH)
    assert set(faces) == set(ROLE_SCALES)
    assert all(isinstance(item, MinecraftTypeface) for item in faces.values())
    assert [faces[r].scale for r in ("banner", "title", "body", "small")] == [
        5,
        3,
        2,
        1,
    ]  # type: ignore[attr-defined]


@needs_fallback
def test_missing_monocraft_falls_back_to_truetype(
    tmp_path: pytest.TempPathFactory,
) -> None:
    faces = build_typefaces(str(tmp_path / "khong_co.ttf"), FALLBACK_PATH)  # type: ignore[operator]
    assert set(faces) == set(ROLE_SCALES) and all(isinstance(f, TrueTypeTypeface) for f in faces.values())


@needs_fallback
def test_truetype_typeface_measures_renders_and_shadows() -> None:
    face = TrueTypeTypeface(FALLBACK_PATH, 20)
    width, height = face.measure("Xin chào")
    assert width > 0 and height > 0 and face.pixelated is False
    plain, shadowed = (
        face.render("Xin chào", WHITE, shadow=False),
        face.render("Xin chào", WHITE),
    )
    assert shadowed.get_size() == (plain.get_width() + 1, plain.get_height() + 1)
    assert face.measure("")[0] > 0  # chuỗi rỗng vẫn có kích thước hợp lệ
