"""Bản vẽ OpenGL của `UiPainter` (chiếu trực giao theo pixel, chữ được lưu đệm thành texture)."""

from collections import OrderedDict
from collections.abc import Mapping

import pygame
from OpenGL.GL import (
    GL_BLEND,
    GL_DEPTH_TEST,
    GL_LINEAR,
    GL_MODELVIEW,
    GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glColor3f,
    glColor4f,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex2f,
)

from gui.painter import UiPainter
from gui.palette import RGB
from gui.pixel_font import Typeface

# (typeface, chữ, màu, có bóng)
TextKey = tuple[Typeface, str, RGB, bool]
# (mã texture OpenGL, rộng, cao)
TextEntry = tuple[int, int, int]


class GLPainter(UiPainter):
    """Vẽ giao diện 2D lên cảnh OpenGL đang có; chữ được dựng một lần rồi giữ trong bộ nhớ đệm LRU."""

    def __init__(
        self, textures: Mapping[str, int] | None = None, max_cached_texts: int = 400
    ) -> None:
        """`textures` là bảng tên texture -> mã OpenGL (dùng cho nền lát); `max_cached_texts` là số chuỗi chữ giữ lại."""
        self._textures: Mapping[str, int] = textures or {}
        self._max_cached: int = max_cached_texts
        self._cache: OrderedDict[TextKey, TextEntry] = OrderedDict()
        self._height: int = 0

    # ------------------------------------------------------------------ vòng đời

    def begin(self, width: int, height: int) -> None:
        """Chuyển sang chiếu trực giao theo pixel, gốc dưới-trái, để vẽ 2D lên 3D."""
        self._height = height
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

    def end(self) -> None:
        """Khôi phục ma trận và trạng thái vẽ 3D."""
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def dispose(self) -> None:
        """Giải phóng mọi texture chữ đã dựng."""
        for texture, _, _ in self._cache.values():
            glDeleteTextures([texture])
        self._cache.clear()

    # ------------------------------------------------------------------ vẽ

    def _quad(self, rect: pygame.Rect) -> None:
        """Vẽ một hình chữ nhật (tọa độ trên-trái) bằng màu hiện tại."""
        bottom: int = self._height - rect.bottom
        top: int = self._height - rect.top
        glBegin(GL_QUADS)
        glVertex2f(rect.left, bottom)
        glVertex2f(rect.right, bottom)
        glVertex2f(rect.right, top)
        glVertex2f(rect.left, top)
        glEnd()

    def fill_rect(self, rect: pygame.Rect, color: RGB, alpha: float = 1.0) -> None:
        """Tô hình chữ nhật bằng `color` với độ đục `alpha`."""
        glColor4f(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, alpha)
        self._quad(rect)

    def _upload(self, surface: pygame.Surface, pixelated: bool) -> TextEntry:
        """Đưa một ảnh chữ lên GPU; chữ pixel dùng lọc gần nhất để giữ nét vuông."""
        width, height = surface.get_size()
        data: bytes = pygame.image.tobytes(surface, "RGBA", True)
        texture: int = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, texture)
        mode: int = GL_NEAREST if pixelated else GL_LINEAR
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, mode)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, mode)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data
        )
        return texture, width, height

    def draw_text(
        self,
        typeface: Typeface,
        text: str,
        x: int,
        y: int,
        color: RGB,
        shadow: bool = True,
    ) -> None:
        """Vẽ `text` tại (x, y); chuỗi đã dựng được lấy lại từ bộ nhớ đệm, chuỗi quá cũ bị loại bớt."""
        if not text:
            return
        key: TextKey = (typeface, text, color, shadow)
        entry: TextEntry | None = self._cache.get(key)
        if entry is None:
            entry = self._upload(
                typeface.render(text, color, shadow), typeface.pixelated
            )
            self._cache[key] = entry
            while len(self._cache) > self._max_cached:
                _, (old, _, _) = self._cache.popitem(last=False)
                glDeleteTextures([old])
        else:
            self._cache.move_to_end(key)
        texture, width, height = entry
        bottom: int = self._height - (y - typeface.top_padding) - height
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D, texture)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0)
        glVertex2f(x, bottom)
        glTexCoord2f(1, 0)
        glVertex2f(x + width, bottom)
        glTexCoord2f(1, 1)
        glVertex2f(x + width, bottom + height)
        glTexCoord2f(0, 1)
        glVertex2f(x, bottom + height)
        glEnd()
        glDisable(GL_TEXTURE_2D)

    def tile_texture(
        self, rect: pygame.Rect, texture: str, tile_size: int, tint: RGB
    ) -> None:
        """Lát texture kín `rect`; thiếu texture thì tô màu đặc theo `tint`."""
        handle: int | None = self._textures.get(texture)
        if handle is None:
            self.fill_rect(rect, tint)
            return
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, handle)
        glColor3f(tint[0] / 255.0, tint[1] / 255.0, tint[2] / 255.0)
        for top in range(rect.top, rect.bottom, tile_size):
            for left in range(rect.left, rect.right, tile_size):
                width: int = min(tile_size, rect.right - left)
                height: int = min(tile_size, rect.bottom - top)
                u: float = width / tile_size
                v: float = height / tile_size
                bottom: int = self._height - top - height
                glBegin(GL_QUADS)
                glTexCoord2f(0, 1 - v)
                glVertex2f(left, bottom)
                glTexCoord2f(u, 1 - v)
                glVertex2f(left + width, bottom)
                glTexCoord2f(u, 1)
                glVertex2f(left + width, bottom + height)
                glTexCoord2f(0, 1)
                glVertex2f(left, bottom + height)
                glEnd()
        glDisable(GL_TEXTURE_2D)
