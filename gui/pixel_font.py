"""Bộ chữ cho giao diện kiểu Minecraft.

`MinecraftTypeface` vẽ chữ bằng font Monocraft ở cỡ gốc 8 (mỗi điểm ảnh của chữ là một điểm ảnh thật),
rồi phóng to theo số nguyên để giữ nét vuông. Monocraft thiếu phần lớn chữ tiếng Việt có dấu, nên
những chữ đó được **ghép** từ chữ gốc cộng dấu vẽ tay theo kiểu điểm ảnh (giống cách Minecraft dùng
font dự phòng cho ký tự không có trong bảng chính, nhưng ở đây nét chữ không bị lệch).
"""

import os
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Mapping

import pygame

from gui.palette import RGB

FONT_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts"
)
MONOCRAFT_PATH: str = os.path.join(FONT_DIR, "Monocraft.ttf")
FALLBACK_PATH: str = os.path.join(FONT_DIR, "DejaVuSans.ttf")

NATIVE_SIZE: int = 8  # cỡ mà Monocraft vẽ đúng một điểm ảnh gốc
GLYPH_ROWS: int = 9  # số hàng của một chữ Monocraft (hàng 7 là đường cơ sở)
HEAD_ROWS: int = 4  # chỗ trống phía trên cho dấu chồng (ví dụ ấ trên chữ hoa)
TAIL_ROWS: int = 4  # chỗ trống phía dưới cho dấu nặng
CELL_ROWS: int = HEAD_ROWS + GLYPH_ROWS + TAIL_ROWS
ADVANCE: int = 6  # chiều rộng một chữ (5 điểm ảnh cộng 1 điểm cách)
BASE_CENTER: int = 2  # cột giữa của chữ rộng 5 điểm ảnh

Pixels = frozenset[tuple[int, int]]

GRAVE: str = "\u0300"
ACUTE: str = "\u0301"
TILDE: str = "\u0303"
HOOK: str = "\u0309"
DOT_BELOW: str = "\u0323"
CIRCUMFLEX: str = "\u0302"
BREVE: str = "\u0306"
HORN: str = "\u031b"

# Hình các dấu, tính từ góc trên trái của một chữ rộng 5 điểm ảnh
MARKS: dict[str, tuple[tuple[int, int], ...]] = {
    GRAVE: ((1, 0), (2, 1)),
    ACUTE: ((3, 0), (2, 1)),
    TILDE: ((2, 0), (4, 0), (1, 1), (3, 1)),
    HOOK: ((2, 0), (3, 0), (3, 1), (2, 2)),
    CIRCUMFLEX: ((2, 0), (1, 1), (3, 1)),
    BREVE: ((1, 0), (4, 0), (2, 1), (3, 1)),
}
TONES: tuple[str, ...] = (GRAVE, ACUTE, TILDE, HOOK)
MODIFIERS: tuple[str, ...] = (CIRCUMFLEX, BREVE, HORN)


class Typeface(ABC):
    """Một bộ chữ ở một cỡ nhất định."""

    top_padding: int = (
        0  # số điểm ảnh trống phía trên hàng đầu của chữ trong ảnh trả về
    )
    pixelated: bool = True  # True: phóng ảnh theo kiểu gần nhất (giữ nét vuông)

    @abstractmethod
    def render(self, text: str, color: RGB, shadow: bool = True) -> pygame.Surface:
        """Ảnh RGBA của `text` (có bóng đổ nếu `shadow`)."""

    @abstractmethod
    def measure(self, text: str) -> tuple[int, int]:
        """(rộng, cao) của `text` tính bằng điểm ảnh thật, không tính phần chừa cho dấu."""


class MinecraftTypeface(Typeface):
    """Chữ Monocraft có tự ghép dấu tiếng Việt, phóng to theo số nguyên `scale`."""

    def __init__(self, path: str = MONOCRAFT_PATH, scale: int = 2) -> None:
        """Mở font Monocraft ở `path` và phóng chữ lên `scale` lần (số nguyên, tối thiểu 1)."""
        self.scale: int = max(1, int(scale))
        self.top_padding = HEAD_ROWS * self.scale
        self._font: pygame.font.Font = pygame.font.Font(path, NATIVE_SIZE)
        self._ink_cache: dict[str, Pixels] = {}
        self._glyph_cache: dict[str, tuple[Pixels, int]] = {}
        self._missing: Pixels = self._ink("\uffff")  # hình "thiếu glyph" của font

    # ------------------------------------------------------------------ chữ gốc

    def _ink(self, ch: str) -> Pixels:
        """Các điểm ảnh sáng của một ký tự theo đúng lưới gốc (x, y), y tính từ đỉnh ô chữ."""
        cached = self._ink_cache.get(ch)
        if cached is not None:
            return cached
        surface = self._font.render(ch, False, (255, 255, 255), (0, 0, 0))
        width, height = surface.get_size()
        pixels = frozenset(
            (x, y)
            for y in range(height)
            for x in range(width)
            if surface.get_at((x, y))[0] > 127
        )
        self._ink_cache[ch] = pixels
        return pixels

    def _supported(self, ch: str) -> bool:
        """Font có chữ này thật (không phải hình ô vuông thay thế)."""
        return len(ch) == 1 and self._ink(ch) != self._missing

    # ------------------------------------------------------------------ ghép chữ

    def _mark_above(
        self, pixels: set[tuple[int, int]], mark: str, gap: int
    ) -> set[tuple[int, int]]:
        """Thêm dấu `mark` phía trên chữ, giữa chữ, cách `gap` hàng."""
        shape = MARKS[mark]
        height = max(y for _, y in shape) + 1
        top = min((y for _, y in pixels), default=3)
        center = (
            min((x for x, _ in pixels), default=0)
            + max((x for x, _ in pixels), default=4)
        ) // 2
        origin_x, origin_y = center - BASE_CENTER, top - gap - height
        return {(origin_x + dx, origin_y + dy) for dx, dy in shape}

    def _compose(self, ch: str) -> Pixels:
        """Ghép một chữ có dấu từ chữ gốc cộng dấu vẽ tay (chữ không ghép được thì dùng dấu '?')."""
        if ch in "đĐ":
            return self._stroked_d(ch)
        parts = unicodedata.normalize("NFD", ch)
        base, marks = parts[0], parts[1:]
        if len(parts) < 2 or not self._supported(base):
            return self._ink("?")
        modifier = next((m for m in marks if m in MODIFIERS), None)
        tone = next((m for m in marks if m in TONES or m == DOT_BELOW), None)

        pixels = set(self._ink(base))
        accented = False
        if modifier == HORN:
            right = max(x for x, _ in pixels)
            top = min(y for _, y in pixels)
            pixels |= {(right + 1, top), (right + 1, top + 1)}
        elif modifier is not None:
            combined = unicodedata.normalize("NFC", base + modifier)
            if self._supported(combined):
                pixels = set(self._ink(combined))
            else:
                pixels |= self._mark_above(pixels, modifier, gap=1)
            accented = True
        if tone == DOT_BELOW:
            center = (min(x for x, _ in pixels) + max(x for x, _ in pixels)) // 2
            pixels.add(
                (center, max(y for _, y in pixels) + 2)
            )  # cách đáy thật của chữ 1 hàng (chữ hoa có dấu thấp hơn)
        elif tone is not None:
            pixels |= self._mark_above(pixels, tone, gap=0 if accented else 1)
        return frozenset(pixels)

    def _stroked_d(self, ch: str) -> Pixels:
        """Chữ đ và Đ: chữ d, D có thêm nét ngang."""
        if ch == "đ":
            return frozenset(set(self._ink("d")) | {(2, 2), (3, 2)})
        shifted = {
            (x + 1, y) for x, y in self._ink("D")
        }  # dời sang phải để nhường chỗ cho nét ngang
        return frozenset(shifted | {(0, 4)})

    def _glyph(self, ch: str) -> tuple[Pixels, int]:
        """(các điểm ảnh sáng, độ rộng tiến) của một chữ, lấy từ font hoặc ghép nếu font thiếu."""
        cached = self._glyph_cache.get(ch)
        if cached is not None:
            return cached
        pixels = self._ink(ch) if self._supported(ch) else self._compose(ch)
        right = max((x for x, _ in pixels), default=ADVANCE - 2)
        result = (pixels, max(ADVANCE, right + 2))
        self._glyph_cache[ch] = result
        return result

    # ------------------------------------------------------------------ Typeface

    def measure(self, text: str) -> tuple[int, int]:
        """(rộng, cao) của `text` đã nhân với `scale`."""
        width = sum(self._glyph(ch)[1] for ch in text)
        return width * self.scale, GLYPH_ROWS * self.scale

    def render(self, text: str, color: RGB, shadow: bool = True) -> pygame.Surface:
        """Vẽ `text` ra ảnh RGBA: dựng ở cỡ gốc rồi phóng nguyên số lần, bóng đổ lệch 1 điểm ảnh gốc."""
        glyphs = [self._glyph(ch) for ch in text]
        width = max(1, sum(advance for _, advance in glyphs) + (1 if shadow else 0))
        height = CELL_ROWS + (1 if shadow else 0)
        native = pygame.Surface((width, height), pygame.SRCALPHA)
        passes: list[tuple[RGB, int]] = []
        if shadow:
            passes.append(((color[0] // 4, color[1] // 4, color[2] // 4), 1))
        passes.append((color, 0))
        for tint, offset in passes:
            x = 0
            for pixels, advance in glyphs:
                for px, py in pixels:
                    target = (x + px + offset, py + HEAD_ROWS + offset)
                    if 0 <= target[0] < width and 0 <= target[1] < height:
                        native.set_at(target, (*tint, 255))
                x += advance
        if self.scale == 1:
            return native
        return pygame.transform.scale(native, (width * self.scale, height * self.scale))


class TrueTypeTypeface(Typeface):
    """Bộ chữ TrueType thường (dự phòng khi thiếu Monocraft)."""

    pixelated = False

    def __init__(self, path: str = FALLBACK_PATH, size: int = 20) -> None:
        """Mở font TrueType ở `path` với cỡ `size` điểm."""
        self._font: pygame.font.Font = pygame.font.Font(path, size)

    def measure(self, text: str) -> tuple[int, int]:
        """(rộng, cao dòng) của `text`."""
        width, _ = self._font.size(text or " ")
        return width, self._font.get_linesize()

    def render(self, text: str, color: RGB, shadow: bool = True) -> pygame.Surface:
        """Vẽ `text` ra ảnh RGBA, có bóng đổ lệch 1 điểm ảnh nếu `shadow`."""
        body = self._font.render(text or " ", True, color)
        if not shadow:
            return body
        dark = (color[0] // 4, color[1] // 4, color[2] // 4)
        back = self._font.render(text or " ", True, dark)
        out = pygame.Surface(
            (body.get_width() + 1, body.get_height() + 1), pygame.SRCALPHA
        )
        out.blit(back, (1, 1))
        out.blit(body, (0, 0))
        return out


# Vai trò của chữ -> cỡ phóng của Minecraft (cỡ TrueType dự phòng đi kèm)
ROLE_SCALES: dict[str, tuple[int, int]] = {
    "banner": (5, 56),
    "title": (3, 28),
    "body": (2, 20),
    "small": (1, 14),
}


def build_typefaces(
    monocraft: str = MONOCRAFT_PATH, fallback: str = FALLBACK_PATH
) -> Mapping[str, Typeface]:
    """Bộ chữ cho từng vai trò (banner, title, body, small); dùng Monocraft nếu có, ngược lại dùng TrueType."""
    faces: dict[str, Typeface] = {}
    for role, (scale, size) in ROLE_SCALES.items():
        if os.path.exists(monocraft):
            faces[role] = MinecraftTypeface(monocraft, scale)
        else:
            faces[role] = TrueTypeTypeface(fallback, size)
    return faces
