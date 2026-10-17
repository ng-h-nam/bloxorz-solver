from typing import Dict, List, Optional, Tuple, Union
from block import Direction
from board import Board, TileType
from state import Coordinates, Orientation, State

ActionInput = Union[Direction, str]

# Lưu ý, nếu muốn chỉ sử dụng các phím mũi tên để di chuyển giống game gốc thì xóa mấy khúc WASD đi.
ACTION_ALIAS_MAP: Dict[str, Direction] = {
    "UP": Direction.UP,
    "W": Direction.UP,
    "ARROW_UP": Direction.UP,
    "DOWN": Direction.DOWN,
    "S": Direction.DOWN,
    "ARROW_DOWN": Direction.DOWN,
    "LEFT": Direction.LEFT,
    "A": Direction.LEFT,
    "ARROW_LEFT": Direction.LEFT,
    "RIGHT": Direction.RIGHT,
    "D": Direction.RIGHT,
    "ARROW_RIGHT": Direction.RIGHT,
}

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

def standardize_action(action: ActionInput) -> Direction:
    """
    Chuẩn hóa hành động của người chơi về đúng kiểu Direction trong game.
    """
    if isinstance(action, Direction):
        return action
    if isinstance(action, str):
        key = action.strip().upper()
        if key in ACTION_ALIAS_MAP:
            return ACTION_ALIAS_MAP[key]
    raise ValueError(f"Hành động không hợp lệ: {action}")

def check_occupied_cells(board: Board, state: State) -> Tuple[bool, str]:
    """
    Kiểm tra chi tiết từng ô mà block chiếm giữ trên bàn cờ.
    Trả về: (Hợp_lệ: bool, Lý_do: str).
    """
    occupied: List[Coordinates] = state.get_occupied_cells()

    for r, c in occupied:
        if not board.in_board(r, c):
            return False
        tile = board.get_tile(r, c)

        if tile == TileType.VOID:
            return False

        if tile == TileType.BRIDGE and (r, c) not in state.active_bridges:
            return False

    if state.orientation == Orientation.STANDING:
        r, c = occupied[0]
        if board.get_tile(r, c) == TileType.FALLING:
            return False, f"Ô gạch mỏng tại ({r}, {c}) quá yếu để khối đứng thẳng."

    return True, "Nước đi hợp lệ."


def is_valid_state(board: Board, state: State) -> bool:
    """Kiểm tra trạng thái có hợp lệ trên bàn cờ hay không."""
    valid, _ = check_occupied_cells(board, state)
    return valid

def is_goal_state(board: Board, state: State) -> bool:
    """Kiểm tra khối đã đứng thẳng vào đúng ô đích G hay chưa."""
    return state.is_standing_at(board.end_pos)


def get_next_state(state: State, direction: Direction, board=None) -> Optional[State]:
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


