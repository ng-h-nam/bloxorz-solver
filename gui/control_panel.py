import os
from typing import List, Optional, Tuple

import pygame
from OpenGL.GL import (
    glBegin, glEnd, glColor3f, glVertex2f, glTexCoord2f, GL_QUADS,
    glGenTextures, glBindTexture, glTexImage2D, glTexParameteri,
    glEnable, glDisable, glBlendFunc, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_LINEAR, GL_DEPTH_TEST,
    glMatrixMode, glPushMatrix, glPopMatrix, glLoadIdentity, glOrtho,
    GL_PROJECTION, GL_MODELVIEW,
)

from core.game import Game

# Màu chữ của pygame: số nguyên 0..255
RGB = Tuple[int, int, int]
# Màu tô của OpenGL: số thực 0..1
Color3 = Tuple[float, float, float]
# Tọa độ hoặc kích thước tính bằng pixel
Pixel = Tuple[int, int]

FONT_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts", "DejaVuSans.ttf")
FONT_SIZE: int = 22
PANEL_WIDTH: int = 340
PANEL_PADDING: int = 16
MESSAGE_TOP: int = 340
MAX_MESSAGE_LINES: int = 6
PANEL_BG: Color3 = (0.11, 0.11, 0.17)

TEXT_COLOR: RGB = (255, 255, 255)
MESSAGE_COLOR: RGB = (255, 140, 140)
DISABLED_TEXT_COLOR: RGB = (110, 110, 120)
BUTTON_COLOR: Color3 = (0.25, 0.25, 0.35)
BUTTON_DISABLED_COLOR: Color3 = (0.15, 0.15, 0.18)


def _begin_overlay(width: int, height: int) -> None:
    """Chuyển sang chiếu trực giao theo pixel, gốc ở góc dưới-trái, để vẽ 2D lên 3D."""
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


def _end_overlay() -> None:
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)


def _fill_rect(rect: pygame.Rect, color: Color3, window_height: int) -> None:
    """Tô một hình chữ nhật. rect dùng tọa độ pixel gốc trên-trái."""
    glColor3f(*color)
    bottom = window_height - rect.bottom
    top = window_height - rect.top
    glBegin(GL_QUADS)
    glVertex2f(rect.left, bottom)
    glVertex2f(rect.right, bottom)
    glVertex2f(rect.right, top)
    glVertex2f(rect.left, top)
    glEnd()


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> List[str]:
    """Ngắt chữ thành nhiều dòng, mỗi dòng không rộng quá max_width điểm ảnh."""
    lines: List[str] = []
    line = ""
    for word in text.split():
        trial = word if not line else line + " " + word
        if font.size(trial)[0] <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


class TextLabel:
    """Một dòng chữ. Chỉ tải lại texture khi nội dung thay đổi."""

    def __init__(self, font: pygame.font.Font, color: RGB = TEXT_COLOR) -> None:
        self.font: pygame.font.Font = font
        self.color: RGB = color
        self.text: Optional[str] = None
        self.texture: Optional[int] = None
        self.size: Pixel = (0, 0)

    def set_text(self, text: str) -> None:
        if text == self.text:
            return
        self.text = text
        surface = self.font.render(text or " ", True, self.color)
        self.size = surface.get_size()
        data = pygame.image.tobytes(surface, "RGBA", True)

        if self.texture is None:
            self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.size[0], self.size[1],
                     0, GL_RGBA, GL_UNSIGNED_BYTE, data)

    def draw(self, x: int, y: int, window_height: int) -> None:
        """x, y là pixel gốc trên-trái của chữ."""
        if self.texture is None:
            return
        w, h = self.size
        bottom = window_height - y - h
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, bottom)
        glTexCoord2f(1, 0); glVertex2f(x + w, bottom)
        glTexCoord2f(1, 1); glVertex2f(x + w, bottom + h)
        glTexCoord2f(0, 1); glVertex2f(x, bottom + h)
        glEnd()
        glDisable(GL_TEXTURE_2D)


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        action: Optional[str],
        font: pygame.font.Font,
        enabled: bool,
    ) -> None:
        self.rect: pygame.Rect = rect
        self.action: Optional[str] = action
        self.enabled: bool = enabled
        color = TEXT_COLOR if enabled else DISABLED_TEXT_COLOR
        self.label: TextLabel = TextLabel(font, color)
        self.label.set_text(text)


class ControlPanel:
    def __init__(self, width: int, height: int, font_size: int = FONT_SIZE) -> None:
        self.width: int = width
        self.height: int = height
        font = pygame.font.Font(FONT_PATH, font_size)
        self.font: pygame.font.Font = font

        self.title: TextLabel = TextLabel(font)
        self.title.set_text("Bloxorz")
        self.info_lines: List[TextLabel] = [TextLabel(font) for _ in range(4)]
        self.message_lines: List[TextLabel] = [TextLabel(font, MESSAGE_COLOR) for _ in range(MAX_MESSAGE_LINES)]
        self._message: str = ""
        self._wrapped: List[str] = []

        # Week 1 chỉ bật Restart. New Game và Run Solver để sẵn, bật ở mốc 2
        self.buttons: List[Button] = [
            Button(pygame.Rect(16, 190, 150, 36), "Restart", "restart", font, True),
            Button(pygame.Rect(16, 234, 150, 36), "New Game", None, font, False),
            Button(pygame.Rect(16, 278, 150, 36), "Run Solver", None, font, False),
        ]

    def handle_click(self, pos: Pixel) -> Optional[str]:
        """Trả về tên hành động của nút được bấm, hoặc None."""
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                return button.action
        return None

    def draw(self, game: Game, level_name: str, message: str) -> None:
        _begin_overlay(self.width, self.height)
        _fill_rect(pygame.Rect(0, 0, PANEL_WIDTH, self.height), PANEL_BG, self.height)

        lines = [
            f"Màn: {level_name}",
            f"Số bước: {game.moves}",
            f"Orientation: {game.state.orientation.name}",
            f"Trạng thái: {game.status.name}",
        ]
        for label, text in zip(self.info_lines, lines):
            label.set_text(text)
        if message != self._message:
            self._message = message
            self._wrapped = wrap_text(self.font, message, PANEL_WIDTH - 2 * PANEL_PADDING)[:MAX_MESSAGE_LINES]

        self.title.draw(16, 16, self.height)
        for i, label in enumerate(self.info_lines):
            label.draw(16, 56 + i * 30, self.height)

        for button in self.buttons:
            color = BUTTON_COLOR if button.enabled else BUTTON_DISABLED_COLOR
            _fill_rect(button.rect, color, self.height)
            x = button.rect.x + (button.rect.w - button.label.size[0]) // 2
            y = button.rect.y + (button.rect.h - button.label.size[1]) // 2
            button.label.draw(x, y, self.height)

        for i, label in enumerate(self.message_lines):
            label.set_text(self._wrapped[i] if i < len(self._wrapped) else "")
            label.draw(PANEL_PADDING, MESSAGE_TOP + i * self.font.get_linesize(), self.height)

        _end_overlay()