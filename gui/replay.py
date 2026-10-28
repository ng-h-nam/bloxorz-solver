"""Phát lại một đường đi trên `Game`.

Khác với bản cũ:
- Có thể bắt đầu từ **trạng thái đang chơi** (`ReplayMode.FROM_CURRENT`), không cần quay về ô xuất phát.
- Chỉ dùng API công khai của `Game` (`move`, `undo`, `restart`, `apply_solution`); không ghi đè
  `state`, `status`, `history` hay gắn thêm thuộc tính vào `Game`.
- Không phụ thuộc `Animator`: bên ngoài nhận thông báo qua `on_step` và tự quyết định hoạt cảnh.
- Thoát phát lại có thể khôi phục đúng tiến trình mà người chơi đang có.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from core.block import Direction
from core.board import Board
from core.game import Game, GameStatus
from core.state import State
from core.transition import (
    SWITCH_ACTION,
    ActionInput,
    MoveResult,
    get_next_state,
    is_goal_state,
    normalize_action,
)
from gui.actions import action_name

MSG_GAME_OVER: str = "Ván đã kết thúc; hãy hoàn tác hoặc chơi lại trước khi phát lại."
MSG_EXTRA_STEPS: str = "Đường đi đã tới đích nhưng còn bước thừa phía sau."


class ReplayMode(Enum):
    """Điểm bắt đầu của một lượt phát lại."""

    FROM_CURRENT = "FROM_CURRENT"  # bắt đầu từ trạng thái đang chơi
    FROM_START = "FROM_START"  # bắt đầu từ ô xuất phát của màn


@dataclass(frozen=True)
class ReplayFrame:
    """Một khung hình (bước) trong tiến trình phát lại."""

    step_index: int
    action: str | None
    state: State
    status: GameStatus
    is_valid: bool
    prev_state: State | None = None
    direction: Direction | None = None
    move_count: int = 0  # số bước lăn khối đã phát từ khung 0


def build_timeline(
    board: Board, start: State, actions: Sequence[str]
) -> tuple[list[ReplayFrame], bool, str]:
    """Dựng và kiểm tra toàn bộ quỹ đạo từ `start`. Trả về (các khung, hợp lệ, thông báo lỗi)."""
    initial_status: GameStatus = (
        GameStatus.WON if is_goal_state(board, start) else GameStatus.PLAYING
    )
    frames: list[ReplayFrame] = [ReplayFrame(0, None, start, initial_status, True)]
    current: State = start
    rolls: int = 0
    for index, name in enumerate(actions, start=1):
        if frames[-1].status == GameStatus.WON:
            return frames, False, MSG_EXTRA_STEPS
        direction: Direction | None = (
            None if name == SWITCH_ACTION else normalize_action(name)
        )
        following: State | None = get_next_state(current, name, board=board)
        if following is None:
            frames.append(
                ReplayFrame(
                    index,
                    name,
                    current,
                    GameStatus.LOST,
                    False,
                    current,
                    direction,
                    rolls,
                )
            )
            return (
                frames,
                False,
                f"Bước replay thứ {index} ('{name}') từ trạng thái {current} không hợp lệ!",
            )
        if name != SWITCH_ACTION:
            rolls += 1
        status: GameStatus = (
            GameStatus.WON if is_goal_state(board, following) else GameStatus.PLAYING
        )
        frames.append(
            ReplayFrame(index, name, following, status, True, current, direction, rolls)
        )
        current = following
    return frames, True, ""


class Replayer:
    """Bộ phát lại đường đi (lời giải của thuật toán hoặc lượt chơi đã lưu)."""

    def __init__(
        self,
        game: Game,
        actions: Sequence[ActionInput],
        *,
        mode: ReplayMode = ReplayMode.FROM_CURRENT,
        step_interval: float = 0.35,
        on_step: Callable[[ReplayFrame, bool], None] | None = None,
        on_finish: Callable[[ReplayFrame], None] | None = None,
    ) -> None:
        """Dựng timeline từ trạng thái bắt đầu của `mode` và kiểm tra hợp lệ trước khi chạm vào `game`.

        `on_step(khung, có_hoạt_cảnh)` được gọi sau mỗi lần đổi bước; `on_finish(khung)` khi phát tới cuối.
        """
        self.game: Game = game
        self.board: Board = game.board
        self.mode: ReplayMode = mode
        self.step_interval: float = max(0.01, float(step_interval))
        self.on_step: Callable[[ReplayFrame, bool], None] | None = on_step
        self.on_finish: Callable[[ReplayFrame], None] | None = on_finish
        self.is_playing: bool = False
        self.released: bool = False
        self.current_index: int = 0
        self._applied: int = 0
        self._accumulator: float = 0.0
        self._snapshot: list[Direction | str] = list(game.move_history)

        start: State = (
            game.state if mode == ReplayMode.FROM_CURRENT else game.initial_state
        )
        self.actions: list[str] = []
        self.timeline: list[ReplayFrame] = [
            ReplayFrame(0, None, start, game.status, True)
        ]
        self.is_valid_path: bool = False
        self.error_message: str = ""
        try:
            self.actions = [action_name(item) for item in actions]
        except ValueError as error:
            self.error_message = str(error)
            return
        self.timeline, self.is_valid_path, self.error_message = build_timeline(
            self.board, start, self.actions
        )
        if (
            self.is_valid_path
            and mode == ReplayMode.FROM_CURRENT
            and game.status != GameStatus.PLAYING
        ):
            self.is_valid_path, self.error_message = False, MSG_GAME_OVER
        if self.is_valid_path and mode == ReplayMode.FROM_START:
            game.restart()

    # ------------------------------------------------------------------ truy vấn

    @property
    def total_steps(self) -> int:
        """Tổng số bước của đường đi (không tính khung 0)."""
        return max(0, len(self.timeline) - 1)

    @property
    def current_frame(self) -> ReplayFrame:
        """Khung hình tại bước hiện tại."""
        return self.timeline[self.current_index]

    @property
    def current_state(self) -> State:
        """Trạng thái của khối tại bước hiện tại."""
        return self.current_frame.state

    @property
    def is_finished(self) -> bool:
        """Đã tới bước cuối cùng của đường đi."""
        return self.current_index >= self.total_steps

    @property
    def reaches_goal(self) -> bool:
        """Đường đi hợp lệ và kết thúc ở trạng thái thắng."""
        return self.is_valid_path and self.timeline[-1].status == GameStatus.WON

    # ------------------------------------------------------------------ áp dụng lên Game

    def _goto(self, target: int) -> None:
        """Đưa `Game` tới bước `target` bằng `move` (tiến) hoặc `undo` (lùi)."""
        limit: int = self.total_steps if self.is_valid_path else 0
        target = max(0, min(int(target), limit))
        while self._applied < target:
            outcome = self.game.move(self.actions[self._applied])
            if outcome is None or outcome.result == MoveResult.FALL:
                break
            self._applied += 1
        while self._applied > target:
            if not self.game.undo():
                break
            self._applied -= 1
        self.current_index = self._applied

    def seek(self, step_index: int, animate: bool = False) -> ReplayFrame:
        """Nhảy tới bước bất kỳ (0 là trạng thái bắt đầu) rồi báo qua `on_step`."""
        self._goto(step_index)
        frame: ReplayFrame = self.current_frame
        if self.on_step is not None:
            self.on_step(frame, animate)
        return frame

    def step_forward(self) -> ReplayFrame:
        """Tiến một bước (có hoạt cảnh); tới cuối thì dừng phát và gọi `on_finish`."""
        if self.is_finished:
            self.is_playing = False
            return self.current_frame
        frame: ReplayFrame = self.seek(self.current_index + 1, animate=True)
        if self.is_finished:
            self.is_playing = False
            if self.on_finish is not None:
                self.on_finish(frame)
        return frame

    def step_backward(self) -> ReplayFrame:
        """Lùi một bước (không hoạt cảnh)."""
        if self.current_index > 0:
            self.seek(self.current_index - 1, animate=False)
        return self.current_frame

    def replay_all_to_end(self) -> ReplayFrame:
        """Chạy ngay tới bước cuối cùng và gọi `on_finish`."""
        self.is_playing = False
        frame: ReplayFrame = self.seek(self.total_steps)
        if self.on_finish is not None:
            self.on_finish(frame)
        return frame

    # ------------------------------------------------------------------ phát tự động

    def play(self, restart_if_finished: bool = True) -> None:
        """Bắt đầu phát tự động; nếu đã tới cuối thì quay về đầu trước."""
        if self.is_finished and restart_if_finished:
            self.seek(0)
        self.is_playing = True
        self._accumulator = 0.0

    def pause(self) -> None:
        """Tạm dừng phát tự động."""
        self.is_playing = False

    def resume(self) -> None:
        """Tiếp tục phát tự động nếu chưa tới cuối."""
        if not self.is_finished:
            self.is_playing = True

    def set_speed(self, step_interval: float) -> None:
        """Đặt số giây giữa hai bước (tối thiểu 0,01)."""
        self.step_interval = max(0.01, float(step_interval))

    def update(self, dt: float, busy: bool = False) -> bool:
        """Tiến thời gian; mỗi lần gọi đi tối đa một bước. `busy` là hoạt cảnh đang chạy (chưa đi tiếp).

        Trả về True nếu trong nhịp này vừa có bước mới.
        """
        if not self.is_playing:
            return False
        if self.is_finished:
            self.is_playing = False
            return False
        if busy:
            return False
        self._accumulator += max(0.0, float(dt))
        if self._accumulator < self.step_interval:
            return False
        self._accumulator -= self.step_interval
        self.step_forward()
        return True

    # ------------------------------------------------------------------ kết thúc

    def restore(self) -> None:
        """Đưa `Game` về đúng tiến trình người chơi có trước khi phát lại."""
        if self.mode == ReplayMode.FROM_CURRENT:
            self._goto(0)
            return
        self.game.restart()
        self.game.apply_solution(self._snapshot)
        self._applied = self.current_index = 0

    def stop(self, restore: bool = True) -> None:
        """Dừng phát lại. Mặc định khôi phục tiến trình trước đó; `restore=False` để giữ vị trí hiện tại."""
        self.is_playing = False
        self._accumulator = 0.0
        if restore and not self.released:
            self.restore()
        self.released = True

    def release(self) -> None:
        """Giao lại quyền điều khiển cho người chơi tại vị trí hiện tại (không khôi phục)."""
        self.stop(restore=False)
