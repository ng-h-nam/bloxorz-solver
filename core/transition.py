from typing import Dict, List, Optional, Tuple
from core.block import Direction
from core.board import Board, TileType
from core.state import Orientation, State

TRANSITION_TABLE: Dict[Tuple[Orientation, Direction], Tuple[int, int, Orientation]] = {
    # 1. STANDING
    (Orientation.STANDING, Direction.UP):    (-2,  0, Orientation.VERTICAL),
    (Orientation.STANDING, Direction.DOWN):  ( 1,  0, Orientation.VERTICAL),
    (Orientation.STANDING, Direction.LEFT):  ( 0, -2, Orientation.HORIZONTAL),
    (Orientation.STANDING, Direction.RIGHT): ( 0,  1, Orientation.HORIZONTAL),

    # 2. HORIZONTAL
    (Orientation.HORIZONTAL, Direction.UP):    (-1,  0, Orientation.HORIZONTAL),
    (Orientation.HORIZONTAL, Direction.DOWN):  ( 1,  0, Orientation.HORIZONTAL),
    (Orientation.HORIZONTAL, Direction.LEFT):  ( 0, -1, Orientation.STANDING),
    (Orientation.HORIZONTAL, Direction.RIGHT): ( 0,  2, Orientation.STANDING),

    # 3. VERTICAL
    (Orientation.VERTICAL, Direction.UP):    (-1,  0, Orientation.STANDING),
    (Orientation.VERTICAL, Direction.DOWN):  ( 2,  0, Orientation.STANDING),
    (Orientation.VERTICAL, Direction.LEFT):  ( 0, -1, Orientation.VERTICAL),
    (Orientation.VERTICAL, Direction.RIGHT): ( 0,  1, Orientation.VERTICAL),
}

def is_valid_state(board: Board, state: State) -> bool:
    """Kiểm tra trạng thái có hợp lệ trên bàn cờ hay không."""
    occupied = state.get_occupied_cells()

    for r, c in occupied:
        tile = board.get_tile(r, c)
        if tile == TileType.VOID:
            return False
        if tile == TileType.BRIDGE and (r, c) not in state.active_bridges:
            return False

    if state.orientation == Orientation.STANDING:
        r, c = occupied[0]
        if board.get_tile(r, c) == TileType.FALLING:
            return False

    return True

def is_goal_state(board: Board, state: State) -> bool:
    """Kiểm tra khối đã đứng thẳng vào đúng ô đích G hay chưa."""
    return state.is_standing_at(board.end_pos)


def get_next_state(board: Board, state: State, direction: Direction) -> Optional[State]:
    """Tính trạng thái kế tiếp khi lăn theo hướng direction và kích hoạt công tắc nếu có."""
    dr, dc, new_orientation = TRANSITION_TABLE[(state.orientation, direction)]
    next_r = state.r + dr
    next_c = state.c + dc

    temp_state = State(
        r=next_r,
        c=next_c,
        orientation=new_orientation,
        active_bridges=state.active_bridges,
    )

    if not is_valid_state(board, temp_state):
        return None

    new_bridges = state.active_bridges
    for cell_r, cell_c in temp_state.get_occupied_cells():
        tile = board.get_tile(cell_r, cell_c)
        if tile == TileType.SOFT_SWITCH:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)
        elif tile == TileType.HEAVY_SWITCH and new_orientation == Orientation.STANDING:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)

    return State(
        r=next_r,
        c=next_c,
        orientation=new_orientation,
        active_bridges=new_bridges,
    )


def get_successors(board: Board, state: State) -> List[Tuple[Direction, State]]:
    """Sinh tất cả các cặp (Direction, State kế tiếp) hợp lệ."""
    successors: List[Tuple[Direction, State]] = []
    for direction in Direction:
        next_state = get_next_state(board, state, direction)
        if next_state is not None:
            successors.append((direction, next_state))
    return successors


