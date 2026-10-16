from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, List, Tuple

Coordinates = Tuple[int, int]

class Orientation(Enum):
    STANDING = "STANDING"
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"

@dataclass(frozen=True, order=True)
class State:
    """
    Trạng thái của trò chơi Bloxorz:
    - (r, c): tọa độ neo? (sẽ fix tại khúc này ch hiểu, ban đầu để orientation bên block dễ deploy hơn.)
    - orientation: khối đang đứng ntn? (đứng, nằm ngang hay nằm dọc)
    - active_bridges: tập hợp các ô cầu đang mở.
    """

    r: int # hàng
    c: int # cột
    orientation: Orientation = Orientation.STANDING
    active_bridges: FrozenSet[Coordinates] = field(default_factory=frozenset)

    def get_occupied_cells(self) -> List[Coordinates]:
        """Trả về danh sách các ô (r, c) mà khối đang đè lên ở trạng thái này."""
        if self.orientation == Orientation.STANDING:
            return [(self.r, self.c)]
        elif self.orientation == Orientation.HORIZONTAL:
            return [(self.r, self.c), (self.r, self.c + 1)]
        elif self.orientation == Orientation.VERTICAL:
            return [(self.r, self.c), (self.r + 1, self.c)]
        raise ValueError(f"Cách đứng không hợp lệ: {self.orientation}")

    def is_standing_at(self, pos: Coordinates) -> bool:
        """Kiểm tra khối có đang đứng thẳng tại đúng tọa độ pos hay không."""
        return self.orientation == Orientation.STANDING and (self.r, self.c) == pos
    
