from enum import Enum
from typing import List, Optional
from core.state import Coordinates, Orientation, State


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class Block:
    """
    Đại diện cho thực thể khối sắt rỉ 1x1x2.
    Có thể đồng bộ trực tiếp với một đối tượng State.
    """

    def __init__(
        self,
        r: int,
        c: int,
        orientation: Orientation = Orientation.STANDING,
        split_pos: Optional[Coordinates] = None,
        active_cube: int = 0,
    ):
        self.r = r
        self.c = c
        self.orientation = orientation
        self.split_pos = split_pos
        self.active_cube = active_cube

    @classmethod
    def from_state(cls, state: State) -> "Block":
        """Tạo đối tượng Block từ một State hiện tại."""
        return cls(
            r=state.r,
            c=state.c,
            orientation=state.orientation,
            split_pos=state.split_pos,
            active_cube=state.active_cube,
        )

    def to_state(self, active_bridges=frozenset()) -> State:
        """Xuất trạng thái hiện tại của Block thành đối tượng State bất biến."""
        return State(
            r=self.r,
            c=self.c,
            orientation=self.orientation,
            active_bridges=frozenset(active_bridges),
            split_pos=self.split_pos,
            active_cube=self.active_cube,
        )

    def get_occupied_cells(self) -> List[Coordinates]:
        """Trả về các ô mà khối đang chiếm giữ (tiện cho GUI vẽ khối)."""
        return self.to_state().get_occupied_cells()

    def __repr__(self) -> str:
        return f"Block(r={self.r}, c={self.c}, orientation={self.orientation})"
