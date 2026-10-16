from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

Coordinates = Tuple[int, int]

class Orientation(Enum):
    STANDING = "STANDING"
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

@dataclass(frozen=True, order=True)
class Block: 
    """
    Block ở đây chính là biểu diễn khối dài 1x1x2 trên map.
    
    """

    r: int # row: hàng
    c: int # col: cột
    orientation: Orientation = Orientation.STANDING

    def get_occupied_cells(self) -> List[Coordinates]:
        """Trả về danh sách các tọa độ (r, c) mà khối đang chiếm giữ."""
        if self.orientation == Orientation.STANDING:
            return [(self.r, self.c)]
        elif self.orientation == Orientation.HORIZONTAL:
            return [(self.r, self.c), (self.r, self.c + 1)]
        elif self.orientation == Orientation.VERTICAL:
            return [(self.r, self.c), (self.r + 1, self.c)]
        raise ValueError(f"Cách đứng không hợp lệ: {self.orientation}")


