import os
from collections.abc import Callable
from dataclasses import dataclass

import pygame
from OpenGL.GL import (
    GL_BLEND,
    GL_DEPTH_TEST,
    GL_LINEAR,
    GL_MODELVIEW,
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

from gui.level_picker import MAX_VISIBLE_ROWS, LevelPicker
from gui.passcode_prompt import PasscodePrompt

# Màu chữ của pygame: số nguyên 0..255
RGB = tuple[int, int, int]
# Màu tô của OpenGL: số thực 0..1
Color3 = tuple[float, float, float]
# Tọa độ hoặc kích thước tính bằng pixel
Pixel = tuple[int, int]

FONT_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "fonts",
    "DejaVuSans.ttf",
)
FONT_SIZE: int = 22
SMALL_FONT_SIZE: int = 17
BIG_FONT_SIZE: int = 44

PANEL_WIDTH: int = 340
PANEL_PADDING: int = 16
TITLE_Y: int = 16
INFO_TOP: int = 52
INFO_STEP: int = 28
INFO_COUNT: int = 6
BUTTON_TOP: int = 232
BUTTON_STEP: int = 44
BUTTON_WIDTH: int = 180
BUTTON_HEIGHT: int = 36
MESSAGE_TOP: int = 372
MAX_MESSAGE_LINES: int = 3
PANEL_BG: Color3 = (0.11, 0.11, 0.17)

BANNER_HEIGHT: int = 230
BANNER_MARGIN: int = 40

TEXT_COLOR: RGB = (255, 255, 255)
MESSAGE_COLOR: RGB = (255, 140, 140)
HELP_COLOR: RGB = (150, 150, 175)
WIN_COLOR: RGB = (120, 230, 140)
LOSE_COLOR: RGB = (255, 110, 110)
DISABLED_TEXT_COLOR: RGB = (110, 110, 120)
BUTTON_COLOR: Color3 = (0.25, 0.25, 0.35)
BUTTON_DISABLED_COLOR: Color3 = (0.15, 0.15, 0.18)
PICKER_BOX_COLOR: Color3 = (0.14, 0.14, 0.22)
PICKER_SELECTED_COLOR: Color3 = (0.28, 0.28, 0.45)
PROMPT_FOOTER: str = "Enter: xác nhận  -  Backspace: xóa  -  Esc: quay lại"
PROMPT_BOX_SIZE: tuple[int, int] = (520, 220)
PICKER_FOOTER: str = "Lên/Xuống: chọn  -  Enter: vào  -  Esc: đóng"

HELP_LINES: list[str] = [
    "Mũi tên / WASD: lăn khối",
    "Phím cách: đổi khối khi đang tách",
    "R: chơi lại",
    "N: chọn màn",
    "C: đặt lại camera",
    "Chuột phải kéo: xoay camera",
    "Chuột giữa kéo: dịch camera",
    "Con lăn: phóng to, thu nhỏ",
]


@dataclass
class HudData:
    """Những gì bảng thông tin hiển thị; do Window quyết định để khớp với hoạt cảnh."""

    level_name: str
    moves: int
    orientation: str
    status: str
    elapsed: float
    passcode: str = ""


@dataclass
class Banner:
    title: str
    subtitle: str
    hint: str
    color: RGB


def format_elapsed(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes:02d}:{seconds - minutes * 60:04.1f}"


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


def _quad(rect: pygame.Rect, window_height: int) -> None:
    bottom = window_height - rect.bottom
    top = window_height - rect.top
    glBegin(GL_QUADS)
    glVertex2f(rect.left, bottom)
    glVertex2f(rect.right, bottom)
    glVertex2f(rect.right, top)
    glVertex2f(rect.left, top)
    glEnd()


def _fill_rect(rect: pygame.Rect, color: Color3, window_height: int) -> None:
    """Tô một hình chữ nhật. rect dùng tọa độ pixel gốc trên-trái."""
    glColor3f(*color)
    _quad(rect, window_height)


def _fill_rect_alpha(rect: pygame.Rect, color: Color3, alpha: float, window_height: int) -> None:
    glColor4f(color[0], color[1], color[2], alpha)
    _quad(rect, window_height)


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Ngắt chữ thành nhiều dòng, mỗi dòng không rộng quá max_width điểm ảnh."""
    lines: list[str] = []
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
    """Một dòng chữ. Chỉ tải lại texture khi nội dung hoặc màu thay đổi."""

    def __init__(self, font: pygame.font.Font, color: RGB = TEXT_COLOR) -> None:
        self.font: pygame.font.Font = font
        self.color: RGB = color
        self.text: str | None = None
        self.texture: int | None = None
        self.size: Pixel = (0, 0)

    def set_color(self, color: RGB) -> None:
        if color != self.color:
            self.color = color
            self.text = None

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
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.size[0],
            self.size[1],
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            data,
        )

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
        glTexCoord2f(0, 0)
        glVertex2f(x, bottom)
        glTexCoord2f(1, 0)
        glVertex2f(x + w, bottom)
        glTexCoord2f(1, 1)
        glVertex2f(x + w, bottom + h)
        glTexCoord2f(0, 1)
        glVertex2f(x, bottom + h)
        glEnd()
        glDisable(GL_TEXTURE_2D)

    def draw_centered(self, center_x: int, y: int, window_height: int) -> None:
        self.draw(center_x - self.size[0] // 2, y, window_height)


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        action: str | None,
        font: pygame.font.Font,
        enabled: bool,
    ) -> None:
        self.rect: pygame.Rect = rect
        self.action: str | None = action
        self.enabled: bool = enabled
        color = TEXT_COLOR if enabled else DISABLED_TEXT_COLOR
        self.label: TextLabel = TextLabel(font, color)
        self.label.set_text(text)


class ControlPanel:
    def __init__(self, width: int, height: int, font_size: int = FONT_SIZE) -> None:
        self.width: int = width
        self.height: int = height
        font = pygame.font.Font(FONT_PATH, font_size)
        small = pygame.font.Font(FONT_PATH, SMALL_FONT_SIZE)
        big = pygame.font.Font(FONT_PATH, BIG_FONT_SIZE)
        self.font: pygame.font.Font = font
        self.small_font: pygame.font.Font = small

        self.title: TextLabel = TextLabel(font)
        self.title.set_text("Bloxorz")
        self.info_lines: list[TextLabel] = [TextLabel(font) for _ in range(INFO_COUNT)]
        self.message_lines: list[TextLabel] = [TextLabel(font, MESSAGE_COLOR) for _ in range(MAX_MESSAGE_LINES)]
        self._message: str = ""
        self._wrapped: list[str] = []

        self.buttons: list[Button] = [
            Button(
                pygame.Rect(
                    PANEL_PADDING,
                    BUTTON_TOP + i * BUTTON_STEP,
                    BUTTON_WIDTH,
                    BUTTON_HEIGHT,
                ),
                text,
                action,
                font,
                enabled,
            )
            for i, (text, action, enabled) in enumerate(
                [
                    ("Restart", "restart", True),
                    ("New Game", "new_game", True),
                    ("Run Solver", None, False),
                ]
            )
        ]

        help_width = PANEL_WIDTH - 2 * PANEL_PADDING
        self.help_labels: list[TextLabel] = []
        for line in HELP_LINES:
            for part in wrap_text(small, line, help_width):
                label = TextLabel(small, HELP_COLOR)
                label.set_text(part)
                self.help_labels.append(label)

        self.banner_title: TextLabel = TextLabel(big)
        self.banner_lines: list[TextLabel] = [TextLabel(font) for _ in range(3)]
        self.banner_hints: list[TextLabel] = [TextLabel(small, HELP_COLOR) for _ in range(2)]

        self.picker_title: TextLabel = TextLabel(font)
        self.picker_title.set_text("Chọn màn")
        self.picker_rows: list[TextLabel] = [TextLabel(font) for _ in range(MAX_VISIBLE_ROWS)]
        self.picker_footer: TextLabel = TextLabel(small, HELP_COLOR)

        self.prompt_title: TextLabel = TextLabel(font)
        self.prompt_digits: TextLabel = TextLabel(big)
        self.prompt_error: TextLabel = TextLabel(font, LOSE_COLOR)
        self.prompt_footer: TextLabel = TextLabel(small, HELP_COLOR)

    def handle_click(self, pos: Pixel) -> str | None:
        """Trả về tên hành động của nút được bấm, hoặc None."""
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                return button.action
        return None

    def draw(self, hud: HudData, message: str) -> None:
        _begin_overlay(self.width, self.height)
        _fill_rect(pygame.Rect(0, 0, PANEL_WIDTH, self.height), PANEL_BG, self.height)

        lines = [
            f"Màn: {hud.level_name}",
            f"Số bước: {hud.moves}",
            f"Orientation: {hud.orientation}",
            f"Trạng thái: {hud.status}",
            f"Thời gian: {format_elapsed(hud.elapsed)}",
            f"Mật khẩu: {hud.passcode or '-'}",
        ]
        for label, text in zip(self.info_lines, lines):
            label.set_text(text)

        self.title.draw(PANEL_PADDING, TITLE_Y, self.height)
        for i, label in enumerate(self.info_lines):
            label.draw(PANEL_PADDING, INFO_TOP + i * INFO_STEP, self.height)

        for button in self.buttons:
            color = BUTTON_COLOR if button.enabled else BUTTON_DISABLED_COLOR
            _fill_rect(button.rect, color, self.height)
            x = button.rect.x + (button.rect.w - button.label.size[0]) // 2
            y = button.rect.y + (button.rect.h - button.label.size[1]) // 2
            button.label.draw(x, y, self.height)

        if message != self._message:
            self._message = message
            self._wrapped = wrap_text(self.font, message, PANEL_WIDTH - 2 * PANEL_PADDING)[:MAX_MESSAGE_LINES]
        for i, label in enumerate(self.message_lines):
            label.set_text(self._wrapped[i] if i < len(self._wrapped) else "")
            label.draw(PANEL_PADDING, MESSAGE_TOP + i * self.font.get_linesize(), self.height)

        line_h = self.small_font.get_linesize()
        top = self.height - PANEL_PADDING - len(self.help_labels) * line_h
        for i, label in enumerate(self.help_labels):
            label.draw(PANEL_PADDING, top + i * line_h, self.height)

        _end_overlay()

    def draw_banner(self, banner: Banner) -> None:
        """Băng thông báo thắng hoặc thua, nằm giữa vùng 3D (bên phải cột bảng)."""
        view_w = self.width - PANEL_WIDTH
        center_x = PANEL_WIDTH + view_w // 2
        top = (self.height - BANNER_HEIGHT) // 2
        _begin_overlay(self.width, self.height)
        _fill_rect_alpha(
            pygame.Rect(PANEL_WIDTH, top, view_w, BANNER_HEIGHT),
            (0.0, 0.0, 0.0),
            0.62,
            self.height,
        )

        self.banner_title.set_color(banner.color)
        self.banner_title.set_text(banner.title)
        self.banner_title.draw_centered(center_x, top + 22, self.height)

        text_width = view_w - 2 * BANNER_MARGIN
        subtitle = wrap_text(self.font, banner.subtitle, text_width)[:3]
        for i, label in enumerate(self.banner_lines):
            label.set_text(subtitle[i] if i < len(subtitle) else "")
            label.draw_centered(center_x, top + 92 + i * self.font.get_linesize(), self.height)

        hints = wrap_text(self.small_font, banner.hint, text_width)[:2]
        for i, label in enumerate(self.banner_hints):
            label.set_text(hints[i] if i < len(hints) else "")
            label.draw_centered(
                center_x,
                top + BANNER_HEIGHT - 52 + i * self.small_font.get_linesize(),
                self.height,
            )
        _end_overlay()

    def draw_picker(
        self,
        picker: LevelPicker,
        current_index: int,
        is_unlocked: Callable[[int], bool] | None = None,
    ) -> None:
        box, rows = picker.layout(self.width, self.height)
        _begin_overlay(self.width, self.height)
        _fill_rect_alpha(
            pygame.Rect(0, 0, self.width, self.height),
            (0.0, 0.0, 0.0),
            0.55,
            self.height,
        )
        _fill_rect(box, PICKER_BOX_COLOR, self.height)

        start, end = picker.visible_range()
        for i, label in enumerate(self.picker_rows):
            index = start + i
            if i >= end - start:
                continue
            if index == picker.selected:
                _fill_rect(rows[i], PICKER_SELECTED_COLOR, self.height)
            name = picker.names[index]
            if index == current_index:
                name += "  (đang chơi)"
            elif is_unlocked is not None and not is_unlocked(index):
                name += "  (khóa)"
            label.set_text(name)
            label.draw(rows[i].x + 8, rows[i].y + (rows[i].h - label.size[1]) // 2, self.height)

        self.picker_title.set_text(f"Chọn màn  ({picker.selected + 1}/{len(picker.names)})")
        self.picker_title.draw(box.x + 16, box.y + 10, self.height)
        self.picker_footer.set_text(PICKER_FOOTER)
        self.picker_footer.draw(box.x + 16, box.bottom - 28, self.height)
        _end_overlay()

    def draw_prompt(self, prompt: PasscodePrompt) -> None:
        """Hộp nhập mật khẩu của một màn bị khóa, nằm giữa cửa sổ."""
        box = pygame.Rect(0, 0, *PROMPT_BOX_SIZE)
        box.center = (self.width // 2, self.height // 2)
        _begin_overlay(self.width, self.height)
        _fill_rect_alpha(
            pygame.Rect(0, 0, self.width, self.height),
            (0.0, 0.0, 0.0),
            0.55,
            self.height,
        )
        _fill_rect(box, PICKER_BOX_COLOR, self.height)

        self.prompt_title.set_text(f"Nhập mật khẩu của {prompt.title}")
        self.prompt_title.draw_centered(box.centerx, box.y + 18, self.height)

        slots = list(prompt.text) + ["_"] * (prompt.max_length - len(prompt.text))
        self.prompt_digits.set_text(" ".join(slots))
        self.prompt_digits.draw_centered(box.centerx, box.y + 68, self.height)

        self.prompt_error.set_text(prompt.error)
        self.prompt_error.draw_centered(box.centerx, box.y + 134, self.height)

        self.prompt_footer.set_text(PROMPT_FOOTER)
        self.prompt_footer.draw_centered(box.centerx, box.bottom - 34, self.height)
        _end_overlay()
