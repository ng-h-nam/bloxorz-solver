from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, List, Tuple, Optional

Coordinates = Tuple[int, int]

class Orientation(Enum):
    STANDING = "STANDING"
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"
    SPLIT = "SPLIT"

@dataclass(frozen=True)
class State:
    """
    Trạng thái của trò chơi Bloxorz:
    - (r, c): tọa độ neo? (sẽ fix tại khúc này ch hiểu, ban đầu để orientation bên block dễ deploy hơn.)
    - orientation: khối đang đứng ntn? (đứng, nằm ngang hay nằm dọc)
    - active_bridges: tập hợp các ô cầu đang mở.
    - split_pos: Tọa độ (r2, c2) của khối đơn 1x1x1 khi trạng thái của khối sắt orientation = Orientation.SPLIT
    - active_cube: chỉ trị số của khối đơn (0 hoặc 1) đang điều khiển. Mặc định khi mới SPLIT là 0.
    """

    r: int
    c: int
    orientation: Orientation = Orientation.STANDING
    active_bridges: FrozenSet[Coordinates] = field(default_factory=frozenset)
    split_pos: Optional[Coordinates] = None
    active_cube: int = 0

   
    def is_split(self) -> bool:
        """Trả về trạng thái hiện tại xem có đang bị chia đôi hay không?"""
        return self.orientation == Orientation.SPLIT and self.split_pos is not None
    
    def get_occupied_cells(self) -> List[Coordinates]:
        """Trả về danh sách các ô (r, c) mà khối đang đè lên ở trạng thái này."""
        if self.orientation == Orientation.STANDING:
            return [(self.r, self.c)]
        elif self.orientation == Orientation.HORIZONTAL:
            return [(self.r, self.c), (self.r, self.c + 1)]
        elif self.orientation == Orientation.VERTICAL:
            return [(self.r, self.c), (self.r + 1, self.c)]
        elif self.orientation == Orientation.SPLIT:
            if self.split_pos is None:
                raise ValueError("Trạng thái split không hợp lệ.")
            return [(self.r, self.c), self.split_pos]
        raise ValueError(f"Cách đứng không hợp lệ: {self.orientation}")

    def get_active_cube_pos(self) -> Coordinates:
        """Trả về tọa độ của khối đơn ta đang điều khiển."""
        if self.is_split() and self.active_cube == 1 and self.split_pos is not None:
            return self.split_pos
        return (self.r, self.c)

    def get_inactive_cube_pos(self) -> Optional[Coordinates]:
        """Trả về tọa độ của khối đơn ta đang không điều khiển (ngược lại với cái trên)."""
        if not self.is_split() or self.split_pos is None:
            return None
        return (self.r, self.c) if self.active_cube == 1 else self.split_pos

    def switch_active_cube(self) -> "State":
        """Chuyển sự điều khiển của người chơi sang cho khối kia (qua lại giữa 2 khối 0 và 1).
           Trong game, ta sử dụng phím cách (SpaceBar) để chuyển đổi việc điều khiển 2 khối này."""

        if not self.is_split():
            return self
        return State(
            r=self.r,
            c=self.c,
            orientation=Orientation.SPLIT,
            active_bridges=self.active_bridges,
            split_pos=self.split_pos,
            active_cube=1 - self.active_cube,
        )

    def normalize_or_merge(self) -> "State":
        """Kiểm tra nếu đang ở trạng thái SPLIT mà 2 khối đơn 1x1x1 nằm ở 2 ô kề cạnh nhau.
        Điều kiện là: (|r1-r2| + |c1-c2| == 1), tự động gộp chúng lại thành khối 1x1x2 chuẩn."""

        if not self.is_split() or self.split_pos is None:
            return self
        r1, c1 = self.r, self.c
        r2, c2 = self.split_pos

        if r1 == r2 and abs(c1 - c2) == 1:
            return State(
                r=r1,
                c=min(c1, c2),
                orientation=Orientation.HORIZONTAL,
                active_bridges=self.active_bridges,
                split_pos=None,
                active_cube=0,
            )

        if abs(r1 - r2) == 1 and c1 == c2:
            return State(
                r=min(r1, r2),
                c=c1,
                orientation=Orientation.VERTICAL,
                active_bridges=self.active_bridges,
                split_pos=None,
                active_cube=0,
            )

        return self


    def is_standing_at(self, pos: Coordinates) -> bool:
        """Kiểm tra khối có đang đứng thẳng tại đúng tọa độ pos hay không."""
        return self.orientation == Orientation.STANDING and (self.r, self.c) == pos

    def to_key(self) -> Tuple[int, int, str, FrozenSet[Coordinates]]:
        """Đại diện duy nhất của state. Có thể hỗ trợ cho hàm state_key."""
        split_coord = self.split_pos if self.split_pos is not None else (-1, -1)
        bridge_tuple = tuple(sorted(self.active_bridges))

        return (
            self.r,
            self.c,
            self.orientation.value,
            split_coord,
            self.active_cube,
            bridge_tuple,
        )

    def __lt__(self, other: "State") -> bool:
        """So sánh thứ tự an toàn cho heapq trong UCS và A* (kể cả khi split_pos là None.)"""

        if not isinstance(other, State):
            return NotImplemented
        return self.to_key() < other.to_key()
# nhớ import state thì gọi hàm cho chuẩn nha mấy bạn



# đây là hàm phụ trợ, khi import state không cần gọi thêm self. gì gì đó, chỉ cần from state import... là dùng dc luôn nha
# assisted by antigravity

def get_occupied_cells(state: State) -> List[Coordinates]:
    return state.get_occupied_cells()

def state_key(state: State) -> Tuple:
    return state.to_key()
    
