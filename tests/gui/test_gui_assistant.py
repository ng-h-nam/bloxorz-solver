"""Test cho gui.engine.assistant.AiAssistant: hạn mức 2 lượt AI mỗi màn, AI không mở khóa màn kế, kết quả cũ."""

import time
from pathlib import Path
from typing import Any

import pytest

from algorithms.bfs import BFSSolver
from core.block import Direction
from core.board import Board
from core.game import Game, GameStatus
from core.state import State
from gui.engine.assistant import (
    MSG_AI_ALREADY_WON,
    MSG_AI_CANCELLED,
    MSG_AI_EXHAUSTED,
    MSG_AI_STALE,
    AiAssistant,
)
from gui.engine.presenter import ScenePresenter
from gui.engine.replay_controller import ReplayController
from gui.engine.solver_service import (
    SolverService,
    SolverSpec,
    discover_available_solvers,
)
from gui.model.level_catalog import LevelCatalog
from gui.model.player_data import MAX_AI_USES_PER_LEVEL, PlayerDataManager
from gui.model.session import GameSession
from gui.shared.actions import action_names


class FakeResult:
    def __init__(self, actions: list[str], solved: bool, status: str) -> None:
        self.actions, self.is_solved, self.status = actions, solved, status
        self.nodes_explored, self.execution_time, self.peak_memory = 3, 0.001, 1024


class ScriptedSolver:
    """Solver giả có kịch bản: chờ, thất bại, hoặc ném lỗi."""

    mode = "unsolved"
    delay = 0.0

    def __init__(self, board: Board, initial_state: State | None = None, **kwargs: Any) -> None:
        pass

    def get_state_key(self, state: State) -> State:
        return state

    def solve(self) -> FakeResult:
        time.sleep(ScriptedSolver.delay)
        if ScriptedSolver.mode == "error":
            raise RuntimeError("giả lập lỗi")
        return FakeResult([], False, "NODE_LIMIT_EXCEEDED")


@pytest.fixture(autouse=True)
def reset_scripted_solver() -> None:
    ScriptedSolver.mode, ScriptedSolver.delay = "unsolved", 0.0


def build(
    tmp_path: Path, specs: list[SolverSpec] | None = None
) -> tuple[AiAssistant, GameSession, ScenePresenter, ReplayController]:
    catalog = LevelCatalog.from_json()
    session = GameSession(Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json"))
    presenter = ScenePresenter()
    presenter.reset(session.game)
    replays = ReplayController(session, presenter)
    chosen = specs if specs is not None else [s for s in discover_available_solvers() if s.name == "BFS"]
    return (
        AiAssistant(session, presenter, replays, SolverService(specs=chosen)),
        session,
        presenter,
        replays,
    )


def wait_until_done(assistant: AiAssistant, timeout: float = 15.0) -> None:
    """Gọi poll tới khi lượt giải kết thúc và đã được xử lý."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        assistant.poll()
        if not assistant.running and assistant.solver.context is None:
            return
        time.sleep(0.01)
    raise AssertionError("lượt giải không kết thúc")


def finish_replay(replays: ReplayController, presenter: ScenePresenter, session: GameSession) -> None:
    for _ in range(200):
        replays.update(1.0)
        presenter.update(5.0, session.game)
        if not replays.playing:
            break


def best_moves(session: GameSession) -> list[str]:
    return action_names(BFSSolver(session.game.board).solve().actions)


# ---------------------------------------------------------------- dùng AI thành công


def test_toggle_solves_from_the_current_position_and_replays(tmp_path: Path) -> None:
    assistant, session, _, replays = build(tmp_path)
    for name in best_moves(session)[:3]:
        session.game.move(name)
    assistant.toggle()
    assert "BFS" in session.message and "còn 2 lượt" in session.message  # BFS có thể xong trước khi kiểm tra running
    wait_until_done(assistant)
    assert replays.active and replays.total == 4  # chỉ 4 bước còn lại, không phải 7
    assert assistant.uses_left == MAX_AI_USES_PER_LEVEL - 1 and "còn 1 lượt AI" in session.message


def test_the_ai_solution_is_stored_separately_from_the_players_records(
    tmp_path: Path,
) -> None:
    assistant, session, _, _ = build(tmp_path)
    assistant.toggle()
    wait_until_done(assistant)
    profile = session.players.get_current_profile() or session.players.players["guest"]
    assert profile.ai_solutions["Stage 01"]["BFS"]["cost"] == 7  # đường đi đầy đủ từ ô xuất phát
    assert session.players.get_level_score_info("Stage 01") is None


def test_an_ai_win_does_not_unlock_the_next_level(tmp_path: Path) -> None:
    assistant, session, presenter, replays = build(tmp_path)
    assistant.toggle()
    wait_until_done(assistant)
    finish_replay(replays, presenter, session)
    assert session.game.status == GameStatus.WON
    assert not session.catalog.is_unlocked(1) and session.next_index is None
    assert presenter.banner is not None and "chưa mở" in presenter.banner.subtitle


def test_the_level_can_be_replayed_and_won_manually_after_ai(tmp_path: Path) -> None:
    assistant, session, presenter, replays = build(tmp_path)
    assistant.toggle()
    wait_until_done(assistant)
    finish_replay(replays, presenter, session)
    replays.discard()
    session.restart()
    presenter.reset(session.game)
    for name in best_moves(session):
        session.move(Direction(name))
    assert session.catalog.is_unlocked(1)  # tự thắng thì mở màn kế
    assert session.players.get_level_score_info("Stage 01") is not None


# ---------------------------------------------------------------- hạn mức


def test_each_level_allows_at_most_two_ai_uses(tmp_path: Path) -> None:
    assistant, session, _, replays = build(tmp_path)
    for expected_left in (1, 0):
        assistant.toggle()
        wait_until_done(assistant)
        assert assistant.uses_left == expected_left
        replays.stop(restore=True)
    assistant.toggle()
    assert session.message == MSG_AI_EXHAUSTED and not assistant.running


def test_another_level_has_its_own_allowance(tmp_path: Path) -> None:
    assistant, session, _, replays = build(tmp_path)
    for _ in range(MAX_AI_USES_PER_LEVEL):
        assistant.toggle()
        wait_until_done(assistant)
        replays.stop(restore=True)
    session.load_stage(1)
    assert assistant.uses_left == MAX_AI_USES_PER_LEVEL


def test_failed_and_stale_runs_do_not_cost_a_use(tmp_path: Path) -> None:
    assistant, session, _, _ = build(tmp_path, [SolverSpec("S", ScriptedSolver)])  # type: ignore[arg-type]
    assistant.toggle()
    wait_until_done(assistant)
    assert "thất bại" in session.message and assistant.uses_left == MAX_AI_USES_PER_LEVEL
    ScriptedSolver.mode = "error"
    assistant.toggle()
    wait_until_done(assistant)
    assert "Lỗi S (RuntimeError)" in session.message and assistant.uses_left == MAX_AI_USES_PER_LEVEL


def test_a_result_that_arrives_after_the_player_moved_is_discarded(
    tmp_path: Path,
) -> None:
    assistant, session, _, replays = build(tmp_path)
    assistant.toggle()
    session.game.move(best_moves(session)[0])  # người chơi đi tiếp trong lúc AI đang giải
    wait_until_done(assistant)
    assert session.message == MSG_AI_STALE and not replays.active
    assert assistant.uses_left == MAX_AI_USES_PER_LEVEL


# ---------------------------------------------------------------- điều khiển


def test_pressing_toggle_while_solving_cancels(tmp_path: Path) -> None:
    ScriptedSolver.delay = 0.4
    assistant, session, _, _ = build(tmp_path, [SolverSpec("S", ScriptedSolver)])  # type: ignore[arg-type]
    assistant.toggle()
    assert assistant.running
    assistant.toggle()
    assert session.message == MSG_AI_CANCELLED and not assistant.running


def test_a_finished_game_is_not_solved_again(tmp_path: Path) -> None:
    assistant, session, _, _ = build(tmp_path)
    for name in best_moves(session):
        session.game.move(name)
    assistant.toggle()
    assert session.message == MSG_AI_ALREADY_WON and not assistant.running


def test_a_fallen_game_is_revived_and_solved_from_before_the_fall(
    tmp_path: Path,
) -> None:
    assistant, session, _, _ = build(tmp_path)
    valid = {a for a, _ in session.game.get_valid_moves() if isinstance(a, Direction)}
    session.move(next(d for d in Direction if d not in valid))
    assert session.game.status == GameStatus.LOST
    assistant.toggle()
    assert session.game.status == GameStatus.PLAYING  # đã khôi phục về vị trí trước lúc rơi
    wait_until_done(assistant)
    assert assistant.uses_left == MAX_AI_USES_PER_LEVEL - 1


def test_cycle_changes_the_algorithm_but_not_while_solving(tmp_path: Path) -> None:
    assistant, session, _, _ = build(tmp_path, discover_available_solvers())
    assert assistant.solver_name == "BFS"
    assistant.cycle()
    assert assistant.solver_name == "DFS" and "DFS" in session.message
    ScriptedSolver.delay = 0.3
    slow, _, _, _ = build(
        tmp_path / "x",
        [SolverSpec("A", ScriptedSolver), SolverSpec("B", ScriptedSolver)],
    )  # type: ignore[arg-type]
    slow.toggle()
    slow.cycle()
    assert slow.solver_name == "A"
    slow.cancel()


def test_starting_a_new_solve_exits_an_active_replay_first(tmp_path: Path) -> None:
    assistant, session, _, replays = build(tmp_path)
    assistant.toggle()
    wait_until_done(assistant)
    replays.replayer.seek(3)  # type: ignore[union-attr]
    assistant.toggle()
    assert not replays.active and session.game.moves == 0  # đã khôi phục về vị trí ban đầu
    assistant.cancel()
