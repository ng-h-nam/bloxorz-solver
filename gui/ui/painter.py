"""Giao diện vẽ 2D trừu tượng cho các thành phần giao diện.

`UiPainter` là phần duy nhất mà `ControlPanel`, các widget và nền cảnh dùng để vẽ. Bản OpenGL nằm ở
`gui.ui.gl_painter`; bản `RecordingPainter` ở đây chỉ ghi lại các lệnh vẽ nên kiểm thử được mà không cần
cửa sổ hay OpenGL.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pygame

from gui.shared.palette import RGB
from gui.ui.pixel_font import Typeface


class UiPainter(ABC):
    """Các thao tác vẽ 2D cơ bản, tọa độ pixel gốc ở góc trên-trái."""

    @abstractmethod
    def begin(self, width: int, height: int) -> None:
        """Bắt đầu một đợt vẽ 2D trên cửa sổ rộng `width`, cao `height`."""

    @abstractmethod
    def end(self) -> None:
        """Kết thúc đợt vẽ 2D, khôi phục trạng thái vẽ trước đó."""

    @abstractmethod
    def fill_rect(self, rect: pygame.Rect, color: RGB, alpha: float = 1.0) -> None:
        """Tô hình chữ nhật `rect` bằng `color` với độ đục `alpha` (0 đến 1)."""

    @abstractmethod
    def draw_text(
        self,
        typeface: Typeface,
        text: str,
        x: int,
        y: int,
        color: RGB,
        shadow: bool = True,
    ) -> None:
        """Vẽ `text` bằng `typeface`; (x, y) là góc trên-trái của hàng chữ đầu tiên (không tính chỗ chừa cho dấu)."""

    @abstractmethod
    def tile_texture(self, rect: pygame.Rect, texture: str, tile_size: int, tint: RGB) -> None:
        """Lát texture tên `texture` kín `rect` theo ô vuông `tile_size` pixel, nhân với màu `tint`."""


@dataclass
class PaintCommand:
    """Một lệnh vẽ đã được ghi lại."""

    kind: str  # "begin", "end", "rect", "text" hoặc "tiles"
    rect: pygame.Rect | None = None
    color: RGB | None = None
    alpha: float = 1.0
    text: str = ""
    pos: tuple[int, int] = (0, 0)
    shadow: bool = False
    typeface: Typeface | None = None
    texture: str = ""
    size: tuple[int, int] = (0, 0)


@dataclass
class RecordingPainter(UiPainter):
    """Bộ vẽ giả chỉ ghi lại các lệnh vẽ, dùng cho kiểm thử."""

    commands: list[PaintCommand] = field(default_factory=list)

    def begin(self, width: int, height: int) -> None:
        """Ghi lệnh bắt đầu (kèm kích thước cửa sổ)."""
        self.commands.append(PaintCommand("begin", size=(width, height)))

    def end(self) -> None:
        """Ghi lệnh kết thúc."""
        self.commands.append(PaintCommand("end"))

    def fill_rect(self, rect: pygame.Rect, color: RGB, alpha: float = 1.0) -> None:
        """Ghi một lệnh tô hình chữ nhật."""
        self.commands.append(PaintCommand("rect", rect=pygame.Rect(rect), color=color, alpha=alpha))

    def draw_text(
        self,
        typeface: Typeface,
        text: str,
        x: int,
        y: int,
        color: RGB,
        shadow: bool = True,
    ) -> None:
        """Ghi một lệnh vẽ chữ, kèm chiều rộng thật của chữ theo `typeface.measure`."""
        width, height = typeface.measure(text)
        self.commands.append(
            PaintCommand(
                "text",
                rect=pygame.Rect(x, y, width, height),
                color=color,
                text=text,
                pos=(x, y),
                shadow=shadow,
                typeface=typeface,
            )
        )

    def tile_texture(self, rect: pygame.Rect, texture: str, tile_size: int, tint: RGB) -> None:
        """Ghi một lệnh lát texture."""
        self.commands.append(
            PaintCommand(
                "tiles",
                rect=pygame.Rect(rect),
                color=tint,
                texture=texture,
                size=(tile_size, tile_size),
            )
        )

    # ------------------------------------------------------------------ truy vấn cho test

    def clear(self) -> None:
        """Xóa các lệnh đã ghi."""
        self.commands.clear()

    def texts(self) -> list[str]:
        """Nội dung mọi chuỗi chữ đã vẽ theo thứ tự vẽ."""
        return [cmd.text for cmd in self.commands if cmd.kind == "text"]

    def text_commands(self, text: str | None = None) -> list[PaintCommand]:
        """Các lệnh vẽ chữ, hoặc chỉ những lệnh vẽ đúng chuỗi `text` nếu có chỉ định."""
        return [cmd for cmd in self.commands if cmd.kind == "text" and (text is None or cmd.text == text)]

    def rects(self, color: RGB | None = None) -> list[pygame.Rect]:
        """Các hình chữ nhật đã tô, hoặc chỉ những hình có màu `color` nếu có chỉ định."""
        return [
            cmd.rect
            for cmd in self.commands
            if cmd.kind == "rect" and cmd.rect is not None and (color is None or cmd.color == color)
        ]
