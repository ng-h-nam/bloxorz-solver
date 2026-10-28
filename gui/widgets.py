"""Các thành phần giao diện kiểu Minecraft: chữ vừa khung, nút có chú thích phím, khung và ô nhập."""

from collections.abc import Mapping

import pygame

from gui.painter import UiPainter
from gui.palette import RGB
from gui.pixel_font import Typeface
from gui.theme import Theme

Faces = Mapping[str, Typeface]
Pixel = tuple[int, int]
ELLIPSIS: str = ".."


def fit_text(
    typeface: Typeface, text: str, max_width: int, ellipsis: str = ELLIPSIS
) -> str:
    """Cắt `text` cho vừa `max_width` điểm ảnh, thêm `ellipsis` vào cuối nếu phải cắt."""
    if typeface.measure(text)[0] <= max_width:
        return text
    if typeface.measure(ellipsis)[0] > max_width:
        return ""
    while text and typeface.measure(text + ellipsis)[0] > max_width:
        text = text[:-1]
    return text + ellipsis


def wrap_text(
    typeface: Typeface, text: str, max_width: int, max_lines: int | None = None
) -> list[str]:
    """Ngắt `text` thành các dòng không rộng quá `max_width`; chữ dài quá một dòng bị chẻ theo ký tự.

    Quá `max_lines` dòng thì dòng cuối bị rút gọn và thêm '..' để người đọc biết còn nữa.
    """
    lines: list[str] = []
    line: str = ""
    for word in text.split():
        while (
            typeface.measure(word)[0] > max_width and len(word) > 1
        ):  # chữ đơn dài hơn cả một dòng
            cut: int = len(word) - 1
            while cut > 1 and typeface.measure(word[:cut])[0] > max_width:
                cut -= 1
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:cut])
            word = word[cut:]
        trial: str = word if not line else f"{line} {word}"
        if typeface.measure(trial)[0] <= max_width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(typeface, lines[-1] + ELLIPSIS, max_width)
    return lines


def text_top(rect: pygame.Rect, typeface: Typeface) -> int:
    """Tọa độ y để chữ nằm giữa theo chiều dọc của `rect`."""
    return rect.y + (rect.h - typeface.measure("A")[1]) // 2


def draw_bevel(
    painter: UiPainter, rect: pygame.Rect, face: RGB, light: RGB, dark: RGB, border: RGB
) -> None:
    """Khung nổi: viền đen, mép sáng trên-trái, mép tối dưới-phải (đổi `light` và `dark` để thành khung lõm)."""
    painter.fill_rect(rect, border)
    inner: pygame.Rect = rect.inflate(-2, -2)
    painter.fill_rect(inner, face)
    painter.fill_rect(pygame.Rect(inner.x, inner.y, inner.w, 2), light)
    painter.fill_rect(pygame.Rect(inner.x, inner.y, 2, inner.h), light)
    painter.fill_rect(pygame.Rect(inner.x, inner.bottom - 2, inner.w, 2), dark)
    painter.fill_rect(pygame.Rect(inner.right - 2, inner.y, 2, inner.h), dark)


def draw_outline(
    painter: UiPainter, rect: pygame.Rect, color: RGB, thickness: int = 2
) -> None:
    """Viền rỗng quanh `rect` (nằm trong rect)."""
    painter.fill_rect(pygame.Rect(rect.x, rect.y, rect.w, thickness), color)
    painter.fill_rect(
        pygame.Rect(rect.x, rect.bottom - thickness, rect.w, thickness), color
    )
    painter.fill_rect(pygame.Rect(rect.x, rect.y, thickness, rect.h), color)
    painter.fill_rect(
        pygame.Rect(rect.right - thickness, rect.y, thickness, rect.h), color
    )


def draw_dialog_box(painter: UiPainter, rect: pygame.Rect, theme: Theme) -> None:
    """Khung hộp thoại xám kiểu túi đồ của Minecraft."""
    draw_bevel(
        painter,
        rect,
        theme.dialog_face,
        theme.dialog_light,
        theme.dialog_dark,
        theme.border,
    )


def draw_slot(painter: UiPainter, rect: pygame.Rect, theme: Theme) -> None:
    """Ô lõm (như ô vật phẩm) dùng cho từng chữ số của mật khẩu."""
    draw_bevel(
        painter,
        rect,
        theme.slot_face,
        theme.dialog_dark,
        theme.dialog_light,
        theme.border,
    )


def draw_text_field(
    painter: UiPainter, rect: pygame.Rect, theme: Theme, active: bool
) -> None:
    """Ô nhập chữ: nền đen, viền trắng khi đang chọn, viền xám khi không chọn."""
    painter.fill_rect(rect, theme.field_face)
    draw_outline(painter, rect, theme.outline if active else theme.field_idle_border)


class Button:
    """Nút bấm kiểu Minecraft với chú thích phím tùy chọn.

    Chú thích phím (chữ nhỏ ở góc phải) chỉ hiện khi nhãn còn chừa đủ chỗ cho nó.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        action: str,
        hint: str = "",
        enabled: bool = True,
    ) -> None:
        """Tạo nút ở `rect` với nhãn `label`, mã hành động `action` và chú thích phím `hint`."""
        self.rect: pygame.Rect = rect
        self.label: str = label
        self.action: str = action
        self.hint: str = hint
        self.enabled: bool = enabled
        self.hovered: bool = False

    def set_state(self, label: str | None = None, enabled: bool | None = None) -> None:
        """Cập nhật nhãn và trạng thái bật/tắt. Màu chữ được tính lại ở mỗi lần vẽ nên không bao giờ bị cũ."""
        if label is not None:
            self.label = label
        if enabled is not None:
            self.enabled = enabled

    def contains(self, pos: Pixel) -> bool:
        """Điểm `pos` có nằm trong nút không."""
        return self.rect.collidepoint(pos)

    def hint_fits(self, body: Typeface, small: Typeface, theme: Theme) -> bool:
        """Còn đủ chỗ ở bên phải nhãn để hiện chú thích phím mà không chạm vào nhãn không."""
        if not self.hint:
            return False
        margin: int = (self.rect.w - body.measure(self.label)[0]) // 2
        return margin >= small.measure(self.hint)[0] + 2 * theme.hint_padding

    def draw(self, painter: UiPainter, faces: Faces, theme: Theme) -> None:
        """Vẽ nút: khung nổi, nhãn ở giữa và (nếu còn chỗ) chú thích phím ở góc phải."""
        face, light, dark, text_color = theme.button_colors(
            self.enabled, self.hovered and self.enabled
        )
        draw_bevel(painter, self.rect, face, light, dark, theme.border)
        body: Typeface = faces["body"]
        small: Typeface = faces["small"]
        label_width: int = body.measure(self.label)[0]
        painter.draw_text(
            body,
            self.label,
            self.rect.x + (self.rect.w - label_width) // 2,
            text_top(self.rect, body),
            text_color,
            shadow=self.enabled,
        )
        if self.hint_fits(body, small, theme):
            hint_width: int = small.measure(self.hint)[0]
            hint_color: RGB = (
                text_color if self.hovered and self.enabled else theme.hint
            )
            painter.draw_text(
                small,
                self.hint,
                self.rect.right - theme.hint_padding - 2 - hint_width,
                self.rect.y + theme.hint_padding + 2,
                hint_color if self.enabled else theme.text_disabled,
                shadow=False,
            )
