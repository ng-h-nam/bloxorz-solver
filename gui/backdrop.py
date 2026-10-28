"""Nền phía sau cảnh 3D: bầu trời chuyển sắc và mây vuông trôi chậm kiểu Minecraft."""

from abc import ABC, abstractmethod

import pygame

from gui.painter import UiPainter
from gui.palette import RGB

# Mỗi đám mây là một nhóm hình chữ nhật xếp theo ô (dx, dy, rộng, cao) tính bằng ô mây
CloudShape = tuple[tuple[int, int, int, int], ...]


class Backdrop(ABC):
    """Lớp cha của mọi nền cảnh."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Tiến thời gian `dt` giây (cho nền có chuyển động)."""

    @abstractmethod
    def draw(self, painter: UiPainter, rect: pygame.Rect) -> None:
        """Vẽ nền kín `rect` (tọa độ cửa sổ)."""


class SkyBackdrop(Backdrop):
    """Bầu trời xanh chuyển sắc từ đỉnh xuống chân trời, có mây vuông trắng trôi sang phải."""

    TOP_COLOR: RGB = (92, 148, 232)
    HORIZON_COLOR: RGB = (196, 228, 255)
    CLOUD_COLOR: RGB = (255, 255, 255)
    CLOUD_ALPHA: float = 0.85
    BANDS: int = 24
    CELL: int = 30  # cạnh một ô mây, tính bằng pixel
    SPEED: float = 14.0  # pixel mỗi giây
    # (vị trí ngang 0..1, vị trí dọc 0..1, hình dạng, hệ số tốc độ)
    CLOUDS: tuple[tuple[float, float, CloudShape, float], ...] = (
        (0.05, 0.10, ((0, 1, 5, 1), (1, 0, 3, 1), (1, 2, 3, 1)), 1.0),
        (0.55, 0.20, ((0, 1, 4, 1), (1, 0, 2, 1)), 0.7),
        (0.30, 0.34, ((0, 0, 6, 1), (1, 1, 4, 1)), 1.3),
        (0.80, 0.08, ((0, 1, 3, 1), (1, 0, 1, 1)), 0.6),
        (0.15, 0.48, ((0, 1, 4, 1), (1, 0, 3, 1), (2, 2, 2, 1)), 0.9),
    )

    def __init__(self) -> None:
        """Bắt đầu với các đám mây ở vị trí ban đầu."""
        self.offset: float = 0.0

    def update(self, dt: float) -> None:
        """Cho mây trôi thêm `dt` giây."""
        self.offset += max(0.0, dt) * self.SPEED

    def gradient_bands(self, rect: pygame.Rect) -> list[tuple[pygame.Rect, RGB]]:
        """Các dải màu ngang (hình chữ nhật, màu) từ đỉnh xuống chân trời, phủ kín `rect`."""
        bands: list[tuple[pygame.Rect, RGB]] = []
        for index in range(self.BANDS):
            top: int = rect.y + rect.h * index // self.BANDS
            bottom: int = rect.y + rect.h * (index + 1) // self.BANDS
            mix: float = index / max(1, self.BANDS - 1)
            color: RGB = (
                round(
                    self.TOP_COLOR[0]
                    + (self.HORIZON_COLOR[0] - self.TOP_COLOR[0]) * mix
                ),
                round(
                    self.TOP_COLOR[1]
                    + (self.HORIZON_COLOR[1] - self.TOP_COLOR[1]) * mix
                ),
                round(
                    self.TOP_COLOR[2]
                    + (self.HORIZON_COLOR[2] - self.TOP_COLOR[2]) * mix
                ),
            )
            bands.append((pygame.Rect(rect.x, top, rect.w, bottom - top), color))
        return bands

    def cloud_rects(self, rect: pygame.Rect) -> list[pygame.Rect]:
        """Các hình chữ nhật tạo nên mây ở thời điểm hiện tại, đã cắt gọn trong `rect`."""
        pieces: list[pygame.Rect] = []
        for x_fraction, y_fraction, shape, speed in self.CLOUDS:
            width: int = max(dx + w for dx, _, w, _ in shape) * self.CELL
            span: int = rect.w + width
            x0: float = (x_fraction * rect.w + self.offset * speed) % span - width
            y0: int = rect.y + round(y_fraction * rect.h)
            for dx, dy, w, h in shape:
                piece = pygame.Rect(
                    round(rect.x + x0 + dx * self.CELL),
                    y0 + dy * self.CELL,
                    w * self.CELL,
                    h * self.CELL,
                )
                clipped: pygame.Rect = piece.clip(rect)
                if clipped.w > 0 and clipped.h > 0:
                    pieces.append(clipped)
        return pieces

    def draw(self, painter: UiPainter, rect: pygame.Rect) -> None:
        """Vẽ bầu trời rồi các đám mây."""
        for band, color in self.gradient_bands(rect):
            painter.fill_rect(band, color)
        for piece in self.cloud_rects(rect):
            painter.fill_rect(piece, self.CLOUD_COLOR, self.CLOUD_ALPHA)
