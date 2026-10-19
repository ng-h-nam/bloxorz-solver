from typing import Dict, List, Optional, Tuple, Union
from core.block import Direction
from core.board import Board, TileType
from core.state import Coordinates, Orientation, State

ActionInput = Union[Direction, str]
_CURRENT_BOARD: Optional[Board] = None
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
SINGLE_CUBE_DELTA: Dict[Direction, Tuple[int, int]] = {
    Direction.UP:    (-1,  0),
    Direction.DOWN:  ( 1,  0),
    Direction.LEFT:  ( 0, -1),
    Direction.RIGHT: ( 0,  1),
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

def set_active_board(board: Board) -> None:
    global _CURRENT_BOARD
    _CURRENT_BOARD = board

def _resolve_board_and_state(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> Tuple[Board, State]:
    """
    Hỗ trợ linh hoạt cả 3 cách gọi từ các thành viên trong nhóm:
      1. func(state)          -> dùng _CURRENT_BOARD đã đăng ký
      2. func(state, board)   -> truyền state trước, board sau
      3. func(board, state)   -> truyền board trước, state sau
    """
    if isinstance(arg1, State) and isinstance(arg2, Board):
        return arg2, arg1
    if isinstance(arg1, Board) and isinstance(arg2, State):
        return arg1, arg2
    if isinstance(arg1, State) and arg2 is None:
        if _CURRENT_BOARD is None:
            raise ValueError(
                "Cần truyền `board` hoặc gọi `set_active_board(board)` trước khi gọi với 1 tham số `state`."
            )
        return _CURRENT_BOARD, arg1
    raise TypeError(f"Tham số không hợp lệ: ({type(arg1)}, {type(arg2)})")

def is_out_of_bounds(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> bool:
    """Kiểm tra block có nằm ngoài phạm vi board hay không."""
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_out_of_bounds(state)

def is_on_void(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> bool:
    """Kiểm tra block có đè lên ô trống (VOID) hay không."""
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_on_void(state)


def is_valid_move(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> bool:
    """
    Output chuẩn ngày 18/10: Kiểm tra trạng thái/nước đi của block có hợp lệ không
    (không ra ngoài board, không nằm trên void, nằm trên các tile hợp lệ).
    """
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_valid_move(state)


# Giữ tên is_valid_state tương đương với is_valid_move để tương thích ngược với code ngày 16-17/10
is_valid_state = is_valid_move


def is_goal_state(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> bool:
    """
    Output chuẩn ngày 18/10: Kiểm tra điều kiện thắng
    (block phải đứng thẳng STANDING tại đúng ô đích).
    """
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_goal_state(state)

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


def is_validstate(board: Board, state: State) -> bool:
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

    if not is_validstate(board, temp_state):
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

def get_next_state(
    state: State,
    action: ActionInput,
    board: Optional[Board] = None,
) -> Optional[State]:
    """
    Tính trạng thái kế tiếp sau hành động `action`:
      - Hỗ trợ đổi khối đơn đang điều khiển khi truyền action="SPACE".
      - Hỗ trợ di chuyển tuần tự từng khối đơn khi đang ở trạng thái SPLIT và tự động gộp khối khi kề nhau.
      - Hỗ trợ tự động chia đôi khối khi STANDING trên ô SPLIT_SWITCH ('U').
    """
    if board is None and _CURRENT_BOARD is not None:
        board = _CURRENT_BOARD

    # 1. Xử lý hành động chuyển đổi quyền điều khiển giữa 2 khối đơn (Spacebar / Switch Cube)
    if isinstance(action, str) and action.strip().upper() in ("SPACE", "SWITCH", "TAB"):
        if not state.is_split():
            return None
        return state.switch_active_cube()

    direction = standardize_action(action)

    # 2. Trường hợp khối đang bị chia đôi (Orientation.SPLIT): điều khiển khối đơn active_cube
    if state.is_split():
        dr, dc = SINGLE_CUBE_DELTA[direction]
        r1, c1 = state.r, state.c
        r2, c2 = state.split_pos  # type: ignore

        if state.active_cube == 0:
            moved_cell = (r1 + dr, c1 + dc)
            new_r, new_c = moved_cell
            new_split_pos = (r2, c2)
        else:
            moved_cell = (r2 + dr, c2 + dc)
            new_r, new_c = r1, c1
            new_split_pos = moved_cell

        candidate_split = State(
            r=new_r,
            c=new_c,
            orientation=Orientation.SPLIT,
            active_bridges=state.active_bridges,
            split_pos=new_split_pos,
            active_cube=state.active_cube,
        )

        # Kiểm tra nếu 2 khối đơn tiến lại sát cạnh nhau thì tự động gộp thành khối 1x1x2
        candidate_state = candidate_split.normalize_or_merge()

        if board is None:
            return candidate_state

        if not board.is_valid_move(candidate_state):
            return None

        # Khối đơn 1x1x1 chỉ kích hoạt được Soft Switch thôi.
        new_bridges = state.active_bridges
        if board.get_tile(*moved_cell) == TileType.SOFT_SWITCH:
            new_bridges = board.apply_switch(moved_cell, new_bridges)

        return State(
            r=candidate_state.r,
            c=candidate_state.c,
            orientation=candidate_state.orientation,
            active_bridges=new_bridges,
            split_pos=candidate_state.split_pos,
            active_cube=candidate_state.active_cube,
        )

    # 3. Trường hợp khối nguyên 1x1x2.
    dr, dc, new_orientation = TRANSITION_TABLE[(state.orientation, direction)]
    candidate_state = State(
        r=state.r + dr,
        c=state.c + dc,
        orientation=new_orientation,
        active_bridges=state.active_bridges,
    )

    if board is None:
        return candidate_state

    if not board.is_valid_move(candidate_state):
        return None

    # Kiểm tra khả năng kích hoạt công tắc
    new_bridges = state.active_bridges
    for cell_r, cell_c in candidate_state.get_occupied_cells():
        tile = board.get_tile(cell_r, cell_c)
        if tile == TileType.SOFT_SWITCH:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)
        elif tile == TileType.HEAVY_SWITCH and new_orientation == Orientation.STANDING:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)
        elif tile == TileType.SPLIT_SWITCH and new_orientation == Orientation.STANDING:
            # Khi đứng thẳng trên SPLIT_SWITCH -> Tự động tách thành 2 khối đơn 1x1x1!
            if (cell_r, cell_c) in board.splits:
                pos1, pos2 = board.splits[(cell_r, cell_c)]
            else:
                # Fallback nếu map không khai báo tọa độ đáp: tách sang 2 ô bên cạnh
                pos1, pos2 = (cell_r, cell_c - 1), (cell_r, cell_c + 1)

            split_state = State(
                r=pos1[0],
                c=pos1[1],
                orientation=Orientation.SPLIT,
                active_bridges=new_bridges,
                split_pos=pos2,
                active_cube=0,
            ).normalize_or_merge()

            if not board.is_valid_move(split_state):
                return None
            return split_state

    return State(
        r=candidate_state.r,
        c=candidate_state.c,
        orientation=new_orientation,
        active_bridges=new_bridges,
    )


