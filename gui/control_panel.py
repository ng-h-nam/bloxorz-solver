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

TEXT_COLOR = (255, 255, 255)
MESSAGE_COLOR = (255, 140, 140)
DISABLED_TEXT_COLOR = (110, 110, 120)
BUTTON_COLOR = (0.25, 0.25, 0.35)
BUTTON_DISABLED_COLOR = (0.15, 0.15, 0.18)


def _begin_overlay(width, height):
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


def _end_overlay():
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)


def _fill_rect(rect, color, window_height):
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


class TextLabel:
    """Một dòng chữ. Chỉ tải lại texture khi nội dung thay đổi."""

    def __init__(self, font, color=TEXT_COLOR):
        self.font = font
        self.color = color
        self.text = None
        self.texture = None
        self.size = (0, 0)

    def set_text(self, text):
        if text == self.text:
            return
        self.text = text
        surface = self.font.render(text or " ", True, self.color)
        self.size = surface.get_size()
        data = pygame.image.tostring(surface, "RGBA", True)

        if self.texture is None:
            self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.size[0], self.size[1],
                     0, GL_RGBA, GL_UNSIGNED_BYTE, data)

    def draw(self, x, y, window_height):
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
    def __init__(self, rect, text, action, font, enabled):
        self.rect = rect
        self.action = action
        self.enabled = enabled
        color = TEXT_COLOR if enabled else DISABLED_TEXT_COLOR
        self.label = TextLabel(font, color)
        self.label.set_text(text)


class ControlPanel:
    def __init__(self, width, height, font_size=30):
        self.width = width
        self.height = height
        font = pygame.font.Font(None, font_size)

        self.title = TextLabel(font)
        self.title.set_text("Bloxorz")
        self.info_lines = [TextLabel(font) for _ in range(4)]
        self.message = TextLabel(font, MESSAGE_COLOR)

        # Week 1 chỉ bật Restart. New Game và Run Solver để sẵn, bật ở mốc 2
        self.buttons = [
            Button(pygame.Rect(16, 190, 150, 36), "Restart", "restart", font, True),
            Button(pygame.Rect(16, 234, 150, 36), "New Game", None, font, False),
            Button(pygame.Rect(16, 278, 150, 36), "Run Solver", None, font, False),
        ]

    def handle_click(self, pos):
        """Trả về tên hành động của nút được bấm, hoặc None."""
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                return button.action
        return None

    def draw(self, game, level_name, message):
        _begin_overlay(self.width, self.height)

        lines = [
            f"Màn: {level_name}",
            f"Số bước: {game.moves}",
            f"Orientation: {game.state.orientation.name}",
            f"Trạng thái: {game.status.name}",
        ]
        for label, text in zip(self.info_lines, lines):
            label.set_text(text)
        self.message.set_text(message)

        self.title.draw(16, 16, self.height)
        for i, label in enumerate(self.info_lines):
            label.draw(16, 56 + i * 30, self.height)

        for button in self.buttons:
            color = BUTTON_COLOR if button.enabled else BUTTON_DISABLED_COLOR
            _fill_rect(button.rect, color, self.height)
            x = button.rect.x + (button.rect.w - button.label.size[0]) // 2
            y = button.rect.y + (button.rect.h - button.label.size[1]) // 2
            button.label.draw(x, y, self.height)

        self.message.draw(16, self.height - 40, self.height)

        _end_overlay()