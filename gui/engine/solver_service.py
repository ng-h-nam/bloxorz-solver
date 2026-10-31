"""Chọn thuật toán và chạy nó **từ trạng thái đang chơi** trên luồng nền.

`SolverService` nhớ ngữ cảnh của mỗi lượt giải (màn nào, bắt đầu từ trạng thái nào, người chơi đã
đi những bước nào) để khi có kết quả, giao diện biết chắc kết quả còn dùng được hay đã cũ.
"""

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from algorithms.base_solver import BaseSolver
from algorithms.bfs import BFSSolver
from algorithms.dfs import DFSSolver
from core.board import Board
from core.game import Game
from core.state import State
from gui.engine.solver_worker import (
    BackgroundSolverWorker,
    SolverErrorEvent,
    SolverResultEvent,
)
from gui.shared.actions import action_names

DEFAULT_NODE_LIMIT: int = 200_000
DEFAULT_TIME_LIMIT: float = 15.0


class GoalAwareBoard(Board):
    """Board có thêm `goal_pos` (bí danh của `end_pos`) cho A*, vốn đọc `board.goal_pos`.

    Giải pháp tạm trong gui/: `Board` hiện chỉ có `end_pos`, còn `astar.py` và `heuristic.py` dùng
    `goal_pos`, nên A* lỗi AttributeError ở mọi màn. Khi core đã thêm `goal_pos`, lớp này không còn tác dụng.
    """

    @property
    def goal_pos(self) -> tuple[int, int]:
        """Tọa độ ô đích (cùng giá trị với `end_pos`)."""
        return self.end_pos


def with_goal_pos(board: Board) -> Board:
    """Bản sao nông của `board` có `goal_pos`; không sửa đối tượng gốc."""
    if hasattr(board, "goal_pos"):
        return board
    adapted: Board = copy.copy(board)
    adapted.__class__ = GoalAwareBoard
    return adapted


@dataclass(frozen=True)
class SolverSpec:
    """Mô tả một thuật toán: tên hiển thị, lớp cài đặt và tham số riêng."""

    name: str
    solver_class: type[BaseSolver]
    options: Mapping[str, Any] = field(default_factory=dict)
    needs_goal_pos: bool = False


def discover_available_solvers() -> list[SolverSpec]:
    """Các thuật toán đã cài trong gói algorithms.

    DFS chạy không cắt độ sâu (`max_depth=None`): mặc định 1000 làm DFS báo vô nghiệm sai ở các màn
    có lời giải dài hơn (Stage 23 và 26).
    """
    specs: list[SolverSpec] = [
        SolverSpec("BFS", BFSSolver),
        SolverSpec("DFS", DFSSolver, {"max_depth": None}),
    ]
    try:
        from algorithms.ucs import UCSSolver  # type: ignore[import-not-found]

        specs.append(SolverSpec("UCS", UCSSolver))
    except ImportError:
        pass
    try:
        from algorithms.astar import AStarSolver

        specs.append(SolverSpec("A*", AStarSolver, needs_goal_pos=True))
    except ImportError:
        pass
    return specs


@dataclass(frozen=True)
class SolverContext:
    """Hoàn cảnh lúc bắt đầu một lượt giải."""

    run_id: int
    algorithm: str
    level_id: str
    start_state: State
    prefix: tuple[str, ...]  # các bước người chơi đã đi trước khi giải


@dataclass
class SolverOutcome:
    """Kết quả một lượt giải kèm hoàn cảnh bắt đầu."""

    context: SolverContext
    result: SolverResultEvent | None = None
    errors: list[SolverErrorEvent] = field(default_factory=list)

    @property
    def solved(self) -> bool:
        """Có lời giải hợp lệ và không rỗng."""
        return self.result is not None and self.result.is_solved and bool(self.result.actions)

    @property
    def full_actions(self) -> list[str]:
        """Đường đi đầy đủ từ ô xuất phát: các bước đã đi cộng với lời giải."""
        return list(self.context.prefix) + (self.result.actions if self.result else [])


class SolverService:
    """Điều phối việc chọn thuật toán và chạy giải nền cho ván đang chơi."""

    def __init__(
        self,
        specs: list[SolverSpec] | None = None,
        worker: BackgroundSolverWorker | None = None,
        node_limit: int = DEFAULT_NODE_LIMIT,
        time_limit: float = DEFAULT_TIME_LIMIT,
    ) -> None:
        """Dùng danh sách thuật toán `specs` (mặc định: tự phát hiện) và giới hạn nút, thời gian cho mỗi lượt."""
        self.specs: list[SolverSpec] = specs if specs is not None else discover_available_solvers()
        if not self.specs:
            raise ValueError("Cần ít nhất một thuật toán giải.")
        self.worker: BackgroundSolverWorker = worker if worker is not None else BackgroundSolverWorker()
        self.node_limit: int = node_limit
        self.time_limit: float = time_limit
        self.selected_index: int = 0
        self.last_error: str = ""
        self._context: SolverContext | None = None

    @property
    def names(self) -> list[str]:
        """Tên các thuật toán có sẵn."""
        return [spec.name for spec in self.specs]

    @property
    def selected_name(self) -> str:
        """Tên thuật toán đang chọn."""
        return self.specs[self.selected_index].name

    @property
    def is_running(self) -> bool:
        """Đang có một lượt giải chạy nền."""
        return self.worker.is_running

    def cycle(self) -> str:
        """Chọn thuật toán kế tiếp (không đổi khi đang chạy) và trả về tên thuật toán đang chọn."""
        if not self.is_running:
            self.selected_index = (self.selected_index + 1) % len(self.specs)
        return self.selected_name

    def start(self, game: Game, level_id: str) -> bool:
        """Giải từ **trạng thái hiện tại** của `game`. Trả về False nếu không bắt đầu được."""
        spec: SolverSpec = self.specs[self.selected_index]
        board: Board = with_goal_pos(game.board) if spec.needs_goal_pos else game.board
        try:
            solver: BaseSolver = spec.solver_class(
                board,
                initial_state=game.state,
                node_limit=self.node_limit,
                time_limit=self.time_limit,
                **dict(spec.options),
            )
        except (ValueError, TypeError) as error:
            self.last_error = str(error)
            return False
        run_id: int | None = self.worker.start(solver, spec.name)
        if run_id is None:
            self.last_error = "Đang có một thuật toán khác chạy nền."
            return False
        self.last_error = ""
        self._context = SolverContext(
            run_id,
            spec.name,
            level_id,
            game.state,
            tuple(action_names(game.move_history)),
        )
        return True

    def cancel(self) -> None:
        """Hủy lượt đang chạy và quên ngữ cảnh của nó."""
        self.worker.cancel()
        self._context = None

    def poll(self) -> SolverOutcome | None:
        """Kết quả (hoặc lỗi) của lượt giải hiện tại nếu đã có, ngược lại None. Mỗi lượt chỉ giao một lần."""
        result, errors = self.worker.poll_events()
        if self._context is None or (result is None and not errors):
            return None
        context: SolverContext = self._context
        self._context = None
        return SolverOutcome(context, result, errors)
