from enum import Enum
from typing import List
from core.state import Coordinates, Orientation, State


class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class Block:
    """
    Đại diện cho thực thể khối sắt rỉ 1x1x2.
    Có thể đồng bộ trực tiếp với một đối tượng State.
    """
    def __init__(self, r: int, c: int, orientation: Orientation = Orientation.STANDING):
        self.r = r
        self.c = c
        self.orientation = orientation

    @classmethod
    def from_state(cls, state: State) -> "Block":
        """Tạo đối tượng Block từ một State hiện tại."""
        return cls(r=state.r, c=state.c, orientation=state.orientation)

    def to_state(self, active_bridges=frozenset()) -> State:
        """Xuất trạng thái hiện tại của Block thành đối tượng State bất biến."""
        return State(
            r=self.r,
            c=self.c,
            orientation=self.orientation,
            active_bridges=frozenset(active_bridges),
        )

    def get_occupied_cells(self) -> List[Coordinates]:
        """Trả về các ô mà khối đang chiếm giữ (tiện cho GUI vẽ khối)."""
        return self.to_state().get_occupied_cells()
