"""Test cho gui.engine.solver_worker: kiểm tra khóa trạng thái và bộ chạy giải nền."""

import time
from typing import Any

from core.block import Direction
from core.state import State
from gui.engine.solver_worker import (
    CANCELLED,
    BackgroundSolverWorker,
    SolverErrorEvent,
    SolverResultEvent,
    verify_solver_state_key,
)


class FakeResult:
    """Kết quả giả có các thuộc tính của SolveResult."""

    def __init__(
        self,
        actions: list[Any] | None = None,
        solved: bool = True,
        status: str = "SOLVED",
    ) -> None:
        self.actions = ["UP"] if actions is None else actions
        self.is_solved = solved
        self.status = status
        self.nodes_explored = 5
        self.execution_time = 0.25
        self.peak_memory = 2048


class FakeSolver:
    """Solver giả: chờ `delay` giây rồi trả kết quả hoặc ném lỗi."""

    def __init__(
        self,
        delay: float = 0.0,
        actions: list[Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.delay, self.actions, self.error = delay, actions, error

    def get_state_key(self, state: State) -> State:
        return state

    def solve(self) -> FakeResult:
        time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return FakeResult(self.actions)


class LoopingSolver:
    """Solver chạy vô hạn, chỉ dừng khi `_check_limits` báo (như BaseSolver)."""

    def __init__(self) -> None:
        self.reason: str | None = None

    def _check_limits(self, start_time: float) -> str | None:
        return None

    def get_state_key(self, state: State) -> State:
        return state

    def solve(self) -> FakeResult:
        start = time.perf_counter()
        while True:
            self.reason = self._check_limits(start)
            if self.reason:
                return FakeResult([], False, self.reason)
            time.sleep(0.002)


def wait_for(
    worker: BackgroundSolverWorker, timeout: float = 5.0
) -> tuple[SolverResultEvent | None, list[SolverErrorEvent]]:
    """Chờ tới khi có kết quả hoặc lỗi."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result, errors = worker.poll_events()
        if result is not None or errors:
            return result, errors
        time.sleep(0.01)
    return None, []


# ---------------------------------------------------------------- verify_solver_state_key


def test_a_state_key_that_distinguishes_everything_passes() -> None:
    ok, issues = verify_solver_state_key(lambda state: state)
    assert ok and issues == []


def test_a_key_that_ignores_orientation_and_bridges_is_flagged() -> None:
    ok, issues = verify_solver_state_key(lambda state: (state.r, state.c))
    assert (
        not ok
        and any("tư thế" in item for item in issues)
        and any("cầu" in item for item in issues)
    )


def test_an_unhashable_key_is_flagged() -> None:
    ok, issues = verify_solver_state_key(
        lambda state: [
            state.r,
            state.c,
            state.orientation.value,
            str(state.active_bridges),
        ]
    )
    assert not ok and any("băm" in item for item in issues)


def test_a_key_that_ignores_the_split_cube_is_flagged() -> None:
    ok, issues = verify_solver_state_key(
        lambda state: (state.r, state.c, state.orientation.value, state.active_bridges)
    )
    assert not ok and any(
        "split_pos" in item or "active_cube" in item for item in issues
    )


# ---------------------------------------------------------------- BackgroundSolverWorker


def test_a_run_delivers_a_normalized_result_with_its_run_id() -> None:
    worker = BackgroundSolverWorker()
    run_id = worker.start(FakeSolver(actions=[Direction.UP, "space"]), "BFS")
    result, errors = wait_for(worker)
    assert run_id == 1 == worker.current_run_id and errors == []
    assert (
        result is not None and result.actions == ["UP", "SWITCH"] and result.run_id == 1
    )
    assert (
        result.expanded_nodes == 5
        and result.elapsed_time == 0.25
        and result.memory_peak_kb == 2.0
    )
    assert result.algorithm_name == "BFS" and result.is_solved


def test_is_running_follows_the_lifecycle() -> None:
    worker = BackgroundSolverWorker()
    assert not worker.is_running
    worker.start(FakeSolver(delay=0.2))
    assert worker.is_running
    wait_for(worker)
    worker.join(2.0)
    assert not worker.is_running


def test_starting_while_busy_is_refused_and_reported() -> None:
    worker = BackgroundSolverWorker()
    worker.start(FakeSolver(delay=0.3))
    assert worker.start(FakeSolver()) is None
    _, errors = worker.poll_events()
    assert errors and errors[0].error_type == "SolverBusyError"
    worker.cancel()


def test_exceptions_become_error_events() -> None:
    worker = BackgroundSolverWorker()
    worker.start(FakeSolver(error=RuntimeError("hỏng")), "X")
    result, errors = wait_for(worker)
    assert (
        result is None
        and errors[0].error_type == "RuntimeError"
        and errors[0].error_message == "hỏng"
    )
    assert "Traceback" in errors[0].traceback_str


def test_a_cancelled_run_never_leaks_into_the_next_one() -> None:
    worker = BackgroundSolverWorker()
    worker.start(FakeSolver(delay=0.4, actions=["DOWN"]), "A")
    worker.cancel()
    worker.start(FakeSolver(delay=0.02, actions=["UP"]), "B")
    seen: list[str] = []
    deadline = time.time() + 1.2
    while time.time() < deadline:
        result, _ = worker.poll_events()
        if result is not None:
            seen.append(result.algorithm_name)
        time.sleep(0.02)
    assert seen == ["B"]


def test_cancel_really_stops_the_solver_thread() -> None:
    worker = BackgroundSolverWorker()
    solver = LoopingSolver()
    worker.start(solver, "LOOP")
    time.sleep(0.05)
    worker.cancel()
    worker.join(3.0)
    assert solver.reason == CANCELLED and not worker.is_running
    assert worker.poll_events() == (None, [])


def test_a_solver_with_a_bad_state_key_is_rejected_before_running() -> None:
    class BadKey(FakeSolver):
        def get_state_key(self, state: State) -> tuple[int, int]:  # type: ignore[override]
            return (state.r, state.c)

    worker = BackgroundSolverWorker()
    worker.start(BadKey())
    result, errors = wait_for(worker)
    assert result is None and errors[0].error_type == "RuntimeError"


def test_auditing_can_be_switched_off() -> None:
    class BadKey(FakeSolver):
        def get_state_key(self, state: State) -> tuple[int, int]:  # type: ignore[override]
            return (state.r, state.c)

    worker = BackgroundSolverWorker(audit_state_keys=False)
    worker.start(BadKey())
    result, _ = wait_for(worker)
    assert result is not None and result.is_solved


def test_unsolved_results_are_reported_as_such() -> None:
    class Unsolved(FakeSolver):
        def solve(self) -> FakeResult:
            return FakeResult([], False, "NODE_LIMIT_EXCEEDED")

    worker = BackgroundSolverWorker()
    worker.start(Unsolved())
    result, _ = wait_for(worker)
    assert (
        result is not None
        and not result.is_solved
        and result.status == "NODE_LIMIT_EXCEEDED"
    )


def test_join_without_a_run_is_harmless() -> None:
    BackgroundSolverWorker().join(0.1)
