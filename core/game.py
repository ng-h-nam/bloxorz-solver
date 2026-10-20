from enum import Enum
from typing import List, Optional, Sequence, Tuple, Union

from core.block import Block, Direction
from core.board import Board, TileType
from core.map_loader import load_level, parse_level
from core.state import Orientation, State
from core.transition import (
    ActionInput,
    MoveOutcome,
    MoveResult,
    check_occupied_cells,
    get_next_state,
    get_successors,
    is_goal_state,
    is_valid_state,
    normalize_action,
    roll_block,
    set_active_board,
)


class GameStatus(Enum):
    """Trạng thái hiện tại của ván chơi Bloxorz."""
    PLAYING = "PLAYING"
    WON = "WON"
    LOST = "LOST"


class Game:
    """
    Quản lý vòng đời và trạng thái của một ván chơi Bloxorz:
    - board: Bản đồ màn chơi hiện tại.
    - state: Trạng thái hiện tại của khối trên bàn cờ.
    - moves: Số bước di chuyển hợp lệ đã thực hiện.
    - status: Trạng thái ván chơi (PLAYING, WON, LOST).
    - history: Lịch sử các State trước đó (hỗ trợ hoàn tác undo).
    """

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
    ) -> None:
        self.board: Board = board
        set_active_board(board)

        if initial_state is not None:
            self.initial_state: State = initial_state
        else:
            start_r, start_c = board.start_pos
            self.initial_state = State(
                r=start_r,
                c=start_c,
                orientation=Orientation.STANDING,
                active_bridges=board.initial_active_bridges,
            )

        self.state: State = self.initial_state
        self.moves: int = 0
        self.status: GameStatus = GameStatus.PLAYING
        self.history: List[State] = []
        self.move_history: List[Union[Direction, str]] = []

        self._update_initial_status()

    @classmethod
    def from_file(cls, filepath: str) -> "Game":
        """Khởi tạo ván chơi trực tiếp từ đường dẫn file map (.txt)."""
        board = load_level(filepath)
        return cls(board)

    @classmethod
    def from_lines(cls, lines: List[str]) -> "Game":
        """Khởi tạo ván chơi từ danh sách các dòng văn bản mô tả map."""
        board = parse_level(lines)
        return cls(board)

    def _update_initial_status(self) -> None:
        """Cập nhật trạng thái ván chơi dựa trên state khởi đầu."""
        if not is_valid_state(self.board, self.state):
            self.status = GameStatus.LOST
        elif is_goal_state(self.board, self.state):
            self.status = GameStatus.WON
        else:
            self.status = GameStatus.PLAYING

    @property
    def block(self) -> Block:
        """Trả về đối tượng Block đồng bộ với trạng thái hiện tại."""
        return Block.from_state(self.state)

    def is_playing(self) -> bool:
        """Kiểm tra ván chơi có đang diễn ra hay không."""
        return self.status == GameStatus.PLAYING

    def is_won(self) -> bool:
        """Kiểm tra người chơi đã thắng màn chơi hay chưa."""
        return self.status == GameStatus.WON

    def is_lost(self) -> bool:
        """Kiểm tra người chơi đã thua (rơi khối) hay chưa."""
        return self.status == GameStatus.LOST

    def is_over(self) -> bool:
        """Kiểm tra ván chơi đã kết thúc (WON hoặc LOST) hay chưa."""
        return self.status in (GameStatus.WON, GameStatus.LOST)

    def _compute_fallen_state(self, direction: Direction) -> Tuple[State, str]:
        """
        Tính trạng thái tọa độ khi khối vừa lăn vào ô không hợp lệ (rơi)
        để phục vụ Animator vẽ hoạt cảnh rơi, kèm thông báo nguyên nhân.
        """
        candidate = roll_block(self.state, direction)

        valid, reason = check_occupied_cells(self.board, candidate)
        if not valid:
            return candidate, reason

        # Trường hợp khối chạm công tắc làm đóng cầu ngay dưới chân khối
        new_bridges = candidate.active_bridges
        for cell_r, cell_c in candidate.get_occupied_cells():
            tile = self.board.get_tile(cell_r, cell_c)
            if tile == TileType.SOFT_SWITCH:
                new_bridges = self.board.apply_switch((cell_r, cell_c), new_bridges)
            elif tile == TileType.HEAVY_SWITCH and candidate.orientation == Orientation.STANDING:
                new_bridges = self.board.apply_switch((cell_r, cell_c), new_bridges)

        fallen = State(
            r=candidate.r,
            c=candidate.c,
            orientation=candidate.orientation,
            active_bridges=new_bridges,
            split_pos=candidate.split_pos,
            active_cube=candidate.active_cube,
        )
        _, reason = check_occupied_cells(self.board, fallen)
        return fallen, reason

    def move(self, action: ActionInput) -> Optional[MoveOutcome]:
        """
        Thực hiện một bước di chuyển theo `action` (Direction hoặc chuỗi hướng / 'SPACE').
        - Nếu ván chơi đã kết thúc (WON hoặc LOST), bỏ qua nước đi và trả về None.
        - Nếu nước đi hợp lệ (OK): cập nhật `state`, tăng `moves`, lưu `history`,
          và chuyển `status` sang WON nếu khối đứng thẳng tại ô đích.
        - Nếu khối bị rơi (FALL): giữ nguyên `state` cũ, không tăng `moves`,
          đặt `status = GameStatus.LOST` và trả về MoveOutcome chứa trạng thái rơi.
        """
        if self.status != GameStatus.PLAYING:
            return None

        # Xử lý đổi khối điều khiển khi đang ở trạng thái tách đôi (SPLIT)
        if isinstance(action, str) and action.strip().upper() in ("SPACE", "SWITCH", "TAB"):
            if not self.state.is_split():
                return None
            next_state = get_next_state(self.state, "SWITCH", board=self.board)
            if next_state is None:
                return None
            self.history.append(self.state)
            self.move_history.append("SWITCH")
            self.state = next_state
            return MoveOutcome(
                result=MoveResult.OK,
                state=self.state,
                message="Đã chuyển quyền điều khiển sang khối đơn còn lại.",
            )

        direction = normalize_action(action)
        next_state = get_next_state(self.state, direction, board=self.board)

        if next_state is None:
            fallen_state, reason = self._compute_fallen_state(direction)
            self.status = GameStatus.LOST
            return MoveOutcome(
                result=MoveResult.FALL,
                state=fallen_state,
                message=reason,
            )

        self.history.append(self.state)
        self.move_history.append(direction)
        self.state = next_state
        self.moves += 1

        if is_goal_state(self.board, self.state):
            self.status = GameStatus.WON
            return MoveOutcome(
                result=MoveResult.OK,
                state=self.state,
                message="Hoàn thành màn chơi!",
            )

        return MoveOutcome(
            result=MoveResult.OK,
            state=self.state,
            message="Nước đi hợp lệ.",
        )

    def switch_cube(self) -> Optional[MoveOutcome]:
        """Chuyển quyền điều khiển giữa 2 khối đơn khi đang ở trạng thái SPLIT."""
        return self.move("SWITCH")

    def undo(self) -> bool:
        """
        Hoàn tác bước di chuyển hợp lệ gần nhất trong `history`
        và đưa trạng thái ván chơi về PLAYING.
        """
        if not self.history:
            return False

        last_state = self.history.pop()
        last_action = self.move_history.pop() if self.move_history else None
        self.state = last_state
        if last_action != "SWITCH":
            self.moves = max(0, self.moves - 1)
        self.status = GameStatus.PLAYING
        return True

    def restart(self) -> State:
        """Đưa ván chơi về lại trạng thái xuất phát ban đầu."""
        set_active_board(self.board)
        self.state = self.initial_state
        self.moves = 0
        self.history.clear()
        self.move_history.clear()
        self._update_initial_status()
        return self.state

    def get_valid_moves(self) -> List[Tuple[str, State]]:
        """Trả về danh sách các nước đi hợp lệ (action_name, next_state) từ trạng thái hiện tại."""
        if self.status != GameStatus.PLAYING:
            return []
        return get_successors(self.board, self.state)

    def apply_solution(self, actions: Sequence[ActionInput]) -> List[MoveOutcome]:
        """
        Thực thi tuần tự một danh sách các hành động (ví dụ: đường đi từ Solver).
        Dừng lại sớm nếu ván chơi kết thúc (WON hoặc LOST).
        """
        outcomes: List[MoveOutcome] = []
        for action in actions:
            outcome = self.move(action)
            if outcome is None:
                break
            outcomes.append(outcome)
            if self.status != GameStatus.PLAYING:
                break
        return outcomes

    def __repr__(self) -> str:
        return (
            f"Game(state={self.state}, moves={self.moves}, "
            f"status={self.status.value})"
        )
