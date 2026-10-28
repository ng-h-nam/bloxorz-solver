"""Test cho gui.engine.solver_service: danh sách thuật toán, bản đồ có goal_pos và dịch vụ giải từ vị trí hiện tại."""

import time
from typing import Any, ClassVar

import pytest

from algorithms.bfs import BFSSolver
from core.board import Board
from core.game import Game
from core.state import State
from gui.engine.solver_service import (
    GoalAwareBoard,
    SolverOutcome,
    SolverService,
    SolverSpec,
    discover_available_solvers,
    with_goal_pos,
)
from gui.model.level_catalog import LevelCatalog
from gui.shared.actions import action_names


class FakeResult:
    def __init__(self, actions: list[str], solved: bool = True) -> None:
        self.actions, self.is_solved, self.status = (
            actions,
            solved,
            "SOLVED" if solved else "NO_SOLUTION",
        )
        self.nodes_explored, self.execution_time, self.peak_memory = 1, 0.0, 0


class RecordingSolver:
    """Ghi lại tham số khởi tạo; có thể giả lập lỗi hoặc chạy chậm."""

    last_kwargs: ClassVar[dict[str, Any]] = {}
    fail_init = False
    delay = 0.0

    def __init__(
        self, board: Board, initial_state: State | None = None, **kwargs: Any
    ) -> None:
        if RecordingSolver.fail_init:
            raise ValueError("trạng thái xuất phát không hợp lệ")
        RecordingSolver.last_kwargs = {"initial_state": initial_state, **kwargs}

    def get_state_key(self, state: State) -> State:
        return state

    def solve(self) -> FakeResult:
        time.sleep(RecordingSolver.delay)
        return FakeResult(["UP"])


@pytest.fixture(autouse=True)
def reset_recording_solver() -> None:
    RecordingSolver.fail_init, RecordingSolver.delay, RecordingSolver.last_kwargs = (
        False,
        0.0,
        {},
    )


@pytest.fixture
def game() -> Game:
    return Game(LevelCatalog.from_json().board(0))


def wait_outcome(service: SolverService, timeout: float = 10.0) -> SolverOutcome:
    deadline = time.time() + timeout
    while time.time() < deadline:
        outcome = service.poll()
        if outcome is not None:
            return outcome
        time.sleep(0.01)
    raise AssertionError("hết thời gian chờ kết quả giải")


# ---------------------------------------------------------------- danh sách thuật toán và goal_pos


def test_discovered_solvers_include_bfs_dfs_and_astar() -> None:
    specs = {spec.name: spec for spec in discover_available_solvers()}
    assert {"BFS", "DFS", "A*"} <= set(specs)
    assert specs["DFS"].options == {"max_depth": None}  # không cắt độ sâu
    assert specs["A*"].needs_goal_pos and not specs["BFS"].needs_goal_pos


def test_with_goal_pos_returns_a_copy_without_touching_the_original(game: Game) -> None:
    board = game.board
    adapted = with_goal_pos(board)
    assert isinstance(adapted, Board) and isinstance(adapted, GoalAwareBoard)
    assert adapted.goal_pos == board.end_pos and adapted is not board
    assert not hasattr(board, "goal_pos")  # bản gốc không bị sửa


def test_with_goal_pos_is_a_no_op_when_the_board_already_has_it(game: Game) -> None:
    adapted = with_goal_pos(game.board)
    assert with_goal_pos(adapted) is adapted


def test_service_needs_at_least_one_solver() -> None:
    with pytest.raises(ValueError):
        SolverService(specs=[])


# ---------------------------------------------------------------- SolverService


def test_cycle_wraps_around_but_not_while_running() -> None:
    service = SolverService(
        specs=[SolverSpec("A", RecordingSolver), SolverSpec("B", RecordingSolver)]
    )  # type: ignore[arg-type]
    assert (
        service.selected_name == "A"
        and service.cycle() == "B"
        and service.cycle() == "A"
    )
    assert service.names == ["A", "B"]


def test_options_and_limits_reach_the_solver(game: Game) -> None:
    spec = SolverSpec("R", RecordingSolver, {"max_depth": None})  # type: ignore[arg-type]
    service = SolverService(specs=[spec], node_limit=123, time_limit=4.5)
    assert service.start(game, "Stage 01")
    wait_outcome(service)
    assert RecordingSolver.last_kwargs["max_depth"] is None
    assert (
        RecordingSolver.last_kwargs["node_limit"] == 123
        and RecordingSolver.last_kwargs["time_limit"] == 4.5
    )
    assert RecordingSolver.last_kwargs["initial_state"] == game.state


def test_solving_starts_from_the_current_state(game: Game) -> None:
    full = action_names(BFSSolver(game.board).solve().actions)
    for name in full[:3]:
        game.move(name)
    service = SolverService(
        specs=[spec for spec in discover_available_solvers() if spec.name == "BFS"]
    )
    assert service.start(game, "Stage 01")
    outcome = wait_outcome(service)
    assert outcome.solved and outcome.context.start_state == game.state
    assert list(outcome.context.prefix) == full[:3]
    assert len(outcome.result.actions) == len(full) - 3  # type: ignore[union-attr]
    assert outcome.full_actions == full  # tiền tố cộng lời giải là đường đi đầy đủ


def test_astar_runs_from_the_current_state_and_is_optimal(game: Game) -> None:
    game.move("RIGHT")
    expected = BFSSolver(game.board, initial_state=game.state).solve().cost
    spec = next(spec for spec in discover_available_solvers() if spec.name == "A*")
    service = SolverService(specs=[spec])
    assert service.start(game, "Stage 01")
    outcome = wait_outcome(service)
    assert (
        outcome.errors == []
        and outcome.solved
        and len(outcome.result.actions) == expected
    )  # type: ignore[union-attr]


def test_a_failing_constructor_returns_false_with_a_reason(game: Game) -> None:
    RecordingSolver.fail_init = True
    service = SolverService(specs=[SolverSpec("R", RecordingSolver)])  # type: ignore[arg-type]
    assert not service.start(game, "Stage 01") and "không hợp lệ" in service.last_error


def test_starting_twice_is_refused_while_running(game: Game) -> None:
    RecordingSolver.delay = 0.3
    service = SolverService(specs=[SolverSpec("R", RecordingSolver)])  # type: ignore[arg-type]
    assert service.start(game, "Stage 01") and service.is_running
    assert not service.start(game, "Stage 01") and service.last_error
    service.cancel()


def test_cancel_forgets_the_run_and_delivers_nothing(game: Game) -> None:
    RecordingSolver.delay = 0.2
    service = SolverService(specs=[SolverSpec("R", RecordingSolver)])  # type: ignore[arg-type]
    service.start(game, "Stage 01")
    service.cancel()
    time.sleep(0.4)
    assert service.poll() is None and not service.is_running


def test_an_outcome_is_delivered_only_once(game: Game) -> None:
    service = SolverService(specs=[SolverSpec("R", RecordingSolver)])  # type: ignore[arg-type]
    service.start(game, "Stage 01")
    wait_outcome(service)
    assert service.poll() is None


def test_outcome_solved_requires_a_non_empty_solution() -> None:
    from gui.engine.solver_service import SolverContext
    from gui.engine.solver_worker import SolverResultEvent

    context = SolverContext(1, "BFS", "Stage 01", State(0, 0), ())
    assert not SolverOutcome(context).solved
    assert not SolverOutcome(
        context, SolverResultEvent("BFS", [], is_solved=True)
    ).solved
    assert SolverOutcome(context, SolverResultEvent("BFS", ["UP"])).solved
    assert SolverOutcome(context, SolverResultEvent("BFS", ["UP"])).full_actions == [
        "UP"
    ]
