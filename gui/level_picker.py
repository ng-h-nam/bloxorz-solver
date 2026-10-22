from typing import List, Optional, Tuple

import pygame

MAX_VISIBLE_ROWS: int = 12
ROW_HEIGHT: int = 30
BOX_WIDTH: int = 420
BOX_PADDING: int = 16
TITLE_HEIGHT: int = 48
FOOTER_HEIGHT: int = 40


class LevelPicker:
    """Hộp chọn màn bật lên. Chỉ giữ trạng thái và bố cục; việc vẽ nằm ở ControlPanel."""

    def __init__(self, names: List[str]) -> None:
        self.names: List[str] = list(names)
        self.is_open: bool = False
        self.selected: int = 0
        self.scroll: int = 0

    @property
    def visible_rows(self) -> int:
        return min(MAX_VISIBLE_ROWS, len(self.names))

    def open(self, current: int = 0) -> None:
        self.is_open = True
        self.selected = max(0, min(len(self.names) - 1, current)) if self.names else 0
        self.scroll = 0
        self._ensure_visible()

    def close(self) -> None:
        self.is_open = False

    def move(self, delta: int) -> None:
        if not self.names:
            return
        self.selected = max(0, min(len(self.names) - 1, self.selected + delta))
        self._ensure_visible()

    def page(self, direction: int) -> None:
        self.move(direction * max(1, self.visible_rows - 1))

    def scroll_by(self, steps: int) -> None:
        limit = max(0, len(self.names) - self.visible_rows)
        self.scroll = max(0, min(limit, self.scroll + steps))

    def _ensure_visible(self) -> None:
        if self.selected < self.scroll:
            self.scroll = self.selected
        elif self.selected >= self.scroll + self.visible_rows:
            self.scroll = self.selected - self.visible_rows + 1
        self.scroll_by(0)

    def visible_range(self) -> Tuple[int, int]:
        return (self.scroll, min(len(self.names), self.scroll + self.visible_rows))

    def layout(self, window_w: int, window_h: int) -> Tuple[pygame.Rect, List[pygame.Rect]]:
        """(khung ngoài, danh sách hình chữ nhật của các dòng đang hiện), tọa độ gốc trên-trái."""
        height = TITLE_HEIGHT + self.visible_rows * ROW_HEIGHT + FOOTER_HEIGHT
        box = pygame.Rect(0, 0, BOX_WIDTH, height)
        box.center = (window_w // 2, window_h // 2)
        start, end = self.visible_range()
        rows = [
            pygame.Rect(
                box.x + BOX_PADDING, box.y + TITLE_HEIGHT + i * ROW_HEIGHT, BOX_WIDTH - 2 * BOX_PADDING, ROW_HEIGHT
            )
            for i in range(end - start)
        ]
        return box, rows

    def row_at(self, pos: Tuple[int, int], window_w: int, window_h: int) -> Optional[int]:
        """Chỉ số (trong toàn danh sách) của dòng dưới con trỏ, hoặc None."""
        _, rows = self.layout(window_w, window_h)
        for i, rect in enumerate(rows):
            if rect.collidepoint(pos):
                return self.scroll + i
        return None

    def box_contains(self, pos: Tuple[int, int], window_w: int, window_h: int) -> bool:
        box, _ = self.layout(window_w, window_h)
        return box.collidepoint(pos)
