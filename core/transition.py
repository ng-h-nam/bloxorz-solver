from typing import Dict, List, Optional, Tuple
from block import Direction
from board import Board, TileType
from state import Orientation, State

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
        if board.get_tile(r, c) == TileType.FRAGILE:
            return False

    return True

def is_goal_state(board: Board, state: State) -> bool:
    """Kiểm tra khối đã đứng thẳng vào đúng ô đích G hay chưa."""
    return state.is_standing_at(board.end_pos)


def get_next_state(board: Board, state: State, direction: Direction) -> Optional[State]:
    """Tính trạng thái kế tiếp khi lăn theo hướng direction. Trả về None nếu rơi."""
    dr, dc, new_orientation = TRANSITION_TABLE[(state.orientation, direction)]
    candidate_state = State(
        r=state.r + dr,
        c=state.c + dc,
        orientation=new_orientation,
        active_bridges=state.active_bridges,
    )

    if not is_valid_state(board, candidate_state):
        return None

    return candidate_state


def get_successors(board: Board, state: State) -> List[Tuple[Direction, State]]:
    """Sinh tất cả các cặp (Direction, State kế tiếp) hợp lệ."""
    successors: List[Tuple[Direction, State]] = []
    for direction in Direction:
        next_state = get_next_state(board, state, direction)
        if next_state is not None:
            successors.append((direction, next_state))
    return successors


