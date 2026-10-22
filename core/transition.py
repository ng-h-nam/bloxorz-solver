from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
from core.block import Direction
from core.board import Board, TileType
from core.state import Coordinates, Orientation, State, get_occupied_cells

ActionInput = Union[Direction, str]


class MoveResult(Enum):
    """Kết quả của một bước di chuyển."""

    OK = "OK"
    FALL = "FALL"


@dataclass(frozen=True)
class MoveOutcome:
    """
    Kết quả trả về sau khi thực hiện một nước đi trong Game:
    - result: MoveResult.OK nếu nước đi hợp lệ, MoveResult.FALL nếu khối bị rơi.
    - state: Trạng thái mới sau nước đi (nếu FALL thì là trạng thái rơi tạm thời để GUI vẽ hoạt cảnh).
    - message: Thông báo mô tả chi tiết kết quả nước đi.
    """

    result: MoveResult
    state: State
    message: str = ""


_CURRENT_BOARD: Optional[Board] = None


def set_active_board(board: Board) -> None:
    """Đăng ký board hiện hành để có thể gọi trực tiếp is_valid_move(state)."""
    global _CURRENT_BOARD
    _CURRENT_BOARD = board


def _resolve_board_and_state(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> Tuple[Board, State]:
    """Hỗ trợ linh hoạt func(state), func(state, board) và func(board, state)."""
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
    (Orientation.STANDING, Direction.UP): (-2, 0, Orientation.VERTICAL),
    (Orientation.STANDING, Direction.DOWN): (1, 0, Orientation.VERTICAL),
    (Orientation.STANDING, Direction.LEFT): (0, -2, Orientation.HORIZONTAL),
    (Orientation.STANDING, Direction.RIGHT): (0, 1, Orientation.HORIZONTAL),
    # 2. HORIZONTAL
    (Orientation.HORIZONTAL, Direction.UP): (-1, 0, Orientation.HORIZONTAL),
    (Orientation.HORIZONTAL, Direction.DOWN): (1, 0, Orientation.HORIZONTAL),
    (Orientation.HORIZONTAL, Direction.LEFT): (0, -1, Orientation.STANDING),
    (Orientation.HORIZONTAL, Direction.RIGHT): (0, 2, Orientation.STANDING),
    # 3. VERTICAL
    (Orientation.VERTICAL, Direction.UP): (-1, 0, Orientation.STANDING),
    (Orientation.VERTICAL, Direction.DOWN): (2, 0, Orientation.STANDING),
    (Orientation.VERTICAL, Direction.LEFT): (0, -1, Orientation.VERTICAL),
    (Orientation.VERTICAL, Direction.RIGHT): (0, 1, Orientation.VERTICAL),
}

SINGLE_CUBE_DELTA: Dict[Direction, Tuple[int, int]] = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


def normalize_action(action: ActionInput) -> Direction:
    """Chuẩn hóa action truyền từ GUI hoặc Solver về kiểu Direction."""
    if isinstance(action, Direction):
        return action
    if isinstance(action, str):
        key = action.strip().upper()
        if key in ACTION_ALIAS_MAP:
            return ACTION_ALIAS_MAP[key]
    raise ValueError(f"Action không hợp lệ: {action}")


def roll_block(state: State, action: ActionInput) -> State:
    """
    Tính tọa độ và tư thế mới của khối sau khi lăn theo `action`
    (chỉ tính toán hình học thuần túy, không kiểm tra biên hay hiệu ứng ô trên bàn cờ).
    """
    if isinstance(action, str) and action.strip().upper() in ("SPACE", "SWITCH", "TAB"):
        return state.switch_active_cube()

    direction = normalize_action(action)

    if state.orientation == Orientation.SPLIT:
        dr, dc = SINGLE_CUBE_DELTA[direction]
        if state.split_pos is None:
            return State(
                r=state.r + dr,
                c=state.c + dc,
                orientation=Orientation.SPLIT,
                active_bridges=state.active_bridges,
                split_pos=None,
                active_cube=state.active_cube,
            )
        r1, c1 = state.r, state.c
        r2, c2 = state.split_pos
        if state.active_cube == 0:
            new_r, new_c = r1 + dr, c1 + dc
            new_split_pos = (r2, c2)
        else:
            new_r, new_c = r1, c1
            new_split_pos = (r2 + dr, c2 + dc)
        return State(
            r=new_r,
            c=new_c,
            orientation=Orientation.SPLIT,
            active_bridges=state.active_bridges,
            split_pos=new_split_pos,
            active_cube=state.active_cube,
        ).normalize_or_merge()

    dr, dc, new_orientation = TRANSITION_TABLE[(state.orientation, direction)]
    return State(
        r=state.r + dr,
        c=state.c + dc,
        orientation=new_orientation,
        active_bridges=state.active_bridges,
    )


def check_occupied_cells(board: Board, state: State) -> Tuple[bool, str]:
    """Kiểm tra chi tiết từng ô mà block chiếm giữ trên bàn cờ."""
    occupied: List[Coordinates] = get_occupied_cells(state)

    for r, c in occupied:
        if not board.in_board(r, c):
            return False, f"Khối lăn ra ngoài biên bản đồ tại tọa độ ({r}, {c})."

        tile = board.get_tile(r, c)
        if tile == TileType.VOID:
            return False, f"Khối rơi xuống vực (VOID) tại ô ({r}, {c})."

        if tile == TileType.BRIDGE and (r, c) not in state.active_bridges:
            return False, f"Cầu tại ô ({r}, {c}) đang đóng."

    if state.orientation == Orientation.STANDING:
        r, c = occupied[0]
        if board.get_tile(r, c) == TileType.FRAGILE:
            return False, f"Ô gạch mỏng (FRAGILE / FALLING) tại ({r}, {c}) bị vỡ khi khối đứng thẳng."

    return True, "Nước đi hợp lệ."


def is_out_of_bounds(arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None) -> bool:
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_out_of_bounds(state)


def is_on_void(arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None) -> bool:
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_on_void(state)


def is_valid_move(arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None) -> bool:
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_valid_move(state)


is_valid_state = is_valid_move


def is_goal_state(arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None) -> bool:
    board, state = _resolve_board_and_state(arg1, arg2)
    return board.is_goal_state(state)


def get_next_state(
    state: State,
    action: ActionInput,
    board: Optional[Board] = None,
) -> Optional[State]:
    """
    Hàm duy nhất tính trạng thái kế tiếp (đã xóa mọi bản khai báo trùng):
      - Chữ ký chuẩn: get_next_state(state, action, board=None)
    """
    if board is None and _CURRENT_BOARD is not None:
        board = _CURRENT_BOARD

    if isinstance(action, str) and action.strip().upper() in ("SPACE", "SWITCH", "TAB"):
        if not state.is_split():
            return None
        return state.switch_active_cube()

    direction = normalize_action(action)

    # 1. Xử lý khi khối đang ở trạng thái SPLIT (điều khiển tuần tự từng khối đơn)
    if state.orientation == Orientation.SPLIT:
        if state.split_pos is None:
            if board is not None:
                return None
            dr, dc = SINGLE_CUBE_DELTA[direction]
            return State(
                r=state.r + dr,
                c=state.c + dc,
                orientation=Orientation.SPLIT,
                active_bridges=state.active_bridges,
                split_pos=None,
                active_cube=state.active_cube,
            )
        dr, dc = SINGLE_CUBE_DELTA[direction]
        r1, c1 = state.r, state.c
        r2, c2 = state.split_pos

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
        candidate_state = candidate_split.normalize_or_merge()

        if board is None:
            return candidate_state
        if not board.is_valid_move(candidate_state):
            return None

        new_bridges = state.active_bridges
        if board.get_tile(*moved_cell) == TileType.SOFT_SWITCH:
            new_bridges = board.apply_switch(moved_cell, new_bridges)

        final_state = State(
            r=candidate_state.r,
            c=candidate_state.c,
            orientation=candidate_state.orientation,
            active_bridges=new_bridges,
            split_pos=candidate_state.split_pos,
            active_cube=candidate_state.active_cube,
        )
        if not board.is_valid_move(final_state):
            return None
        return final_state

    # 2. Xử lý khi khối nguyên 1x1x2 (STANDING, HORIZONTAL, VERTICAL)
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

    new_bridges = state.active_bridges
    for cell_r, cell_c in candidate_state.get_occupied_cells():
        tile = board.get_tile(cell_r, cell_c)
        if tile == TileType.SOFT_SWITCH:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)
        elif tile == TileType.HEAVY_SWITCH and new_orientation == Orientation.STANDING:
            new_bridges = board.apply_switch((cell_r, cell_c), new_bridges)
        elif tile == TileType.SPLIT_SWITCH and new_orientation == Orientation.STANDING:
            if (cell_r, cell_c) in board.splits:
                pos1, pos2 = board.splits[(cell_r, cell_c)]
            else:
                pos1, pos2 = (cell_r, cell_c - 1), (cell_r, cell_c + 1)

            split_initial = State(
                r=pos1[0],
                c=pos1[1],
                orientation=Orientation.SPLIT,
                active_bridges=new_bridges,
                split_pos=pos2,
                active_cube=0,
            ).normalize_or_merge()

            if not board.is_valid_move(split_initial):
                return None

            for sp_r, sp_c in (pos1, pos2):
                if board.get_tile(sp_r, sp_c) == TileType.SOFT_SWITCH:
                    new_bridges = board.apply_switch((sp_r, sp_c), new_bridges)

            split_state = State(
                r=split_initial.r,
                c=split_initial.c,
                orientation=split_initial.orientation,
                active_bridges=new_bridges,
                split_pos=split_initial.split_pos,
                active_cube=split_initial.active_cube,
            )
            if not board.is_valid_move(split_state):
                return None
            return split_state

    final_state = State(
        r=candidate_state.r,
        c=candidate_state.c,
        orientation=new_orientation,
        active_bridges=new_bridges,
    )
    if not board.is_valid_move(final_state):
        return None
    return final_state


def get_successors(
    arg1: Union[Board, State], arg2: Optional[Union[Board, State]] = None
) -> List[Tuple[Union[Direction, str], State]]:
    """
    Sinh danh sách các nước đi hợp lệ (action, next_state).
    """
    board, state = _resolve_board_and_state(arg1, arg2)
    successors: List[Tuple[Union[Direction, str], State]] = []

    for direction in Direction:
        next_state = get_next_state(state, direction, board=board)
        if next_state is not None:
            successors.append((direction, next_state))

    # Nếu đang ở trạng thái SPLIT, cho phép thêm hành động đổi khối điều khiển ("SWITCH")
    if state.is_split():
        switched = get_next_state(state, "SWITCH", board=board)
        if switched is not None and switched != state:
            successors.append(("SWITCH", switched))

    return successors
