"""Test cho gui.replay: dựng timeline và phát lại từ trạng thái đang chơi hoặc từ đầu."""

import pytest

from algorithms.bfs import BFSSolver
from core.block import Direction
from core.board import Board
from core.game import Game, GameStatus
from gui.actions import action_names
from gui.level_catalog import LevelCatalog
from gui.replay import (
    MSG_EXTRA_STEPS,
    MSG_GAME_OVER,
    Replayer,
    ReplayFrame,
    ReplayMode,
    build_timeline,
)


@pytest.fixture
def board() -> Board:
    return LevelCatalog.from_json().board(0)


@pytest.fixture
def full(board: Board) -> list[str]:
    """Lời giải tối ưu (7 bước) của Stage 01 từ ô xuất phát."""
    return action_names(BFSSolver(board).solve().actions)


def play_manually(game: Game, steps: list[str]) -> None:
    for name in steps:
        assert game.move(name) is not None


# ---------------------------------------------------------------- build_timeline


def test_timeline_of_a_valid_solution(board: Board, full: list[str]) -> None:
    game = Game(board)
    frames, valid, error = build_timeline(board, game.state, full)
    assert valid and error == "" and len(frames) == len(full) + 1
    assert frames[0].action is None and frames[-1].status == GameStatus.WON
    assert frames[-1].move_count == len(full)
    assert all(f.is_valid for f in frames)


def test_timeline_stops_at_the_first_invalid_step(board: Board) -> None:
    game = Game(board)
    frames, valid, error = build_timeline(board, game.state, ["UP"])
    assert not valid and "không hợp lệ" in error and not frames[-1].is_valid


def test_timeline_rejects_steps_after_reaching_the_goal(
    board: Board, full: list[str]
) -> None:
    frames, valid, error = build_timeline(board, Game(board).state, [*full, "UP"])
    assert not valid and error == MSG_EXTRA_STEPS and len(frames) == len(full) + 1


def test_timeline_counts_only_rolls_not_switches(board: Board) -> None:
    game = Game(board)
    frames, _, _ = build_timeline(board, game.state, ["RIGHT"])
    assert frames[1].move_count == 1 and frames[1].direction == Direction.RIGHT


# ---------------------------------------------------------------- Replayer: từ trạng thái đang chơi


def test_replay_starts_from_the_current_state(board: Board, full: list[str]) -> None:
    game = Game(board)
    play_manually(game, full[:3])
    replayer = Replayer(game, full[3:], mode=ReplayMode.FROM_CURRENT)
    assert replayer.is_valid_path and replayer.timeline[0].state == game.state
    assert replayer.total_steps == len(full) - 3
    assert game.moves == 3  # tạo Replayer chưa đụng tới ván


def test_playing_to_the_end_accumulates_moves_and_wins(
    board: Board, full: list[str]
) -> None:
    game = Game(board)
    play_manually(game, full[:3])
    replayer = Replayer(game, full[3:])
    replayer.play()
    guard = 0
    while replayer.is_playing and guard < 100:
        replayer.update(1.0)
        guard += 1
    assert replayer.is_finished and replayer.reaches_goal
    assert game.is_won() and game.moves == len(full)


def test_every_frame_matches_the_game_after_seeking(
    board: Board, full: list[str]
) -> None:
    game = Game(board)
    replayer = Replayer(game, full)
    for index in [*range(len(full) + 1), 3, 0, len(full)]:
        replayer.seek(index)
        assert (
            game.state == replayer.timeline[index].state
            and replayer.current_index == index
        )


def test_step_backward_undoes_and_stops_at_zero(board: Board, full: list[str]) -> None:
    game = Game(board)
    replayer = Replayer(game, full)
    replayer.step_forward()
    replayer.step_forward()
    replayer.step_backward()
    assert replayer.current_index == 1 and game.moves == 1
    replayer.step_backward()
    replayer.step_backward()
    assert replayer.current_index == 0 and game.moves == 0


def test_stop_restores_the_players_progress(board: Board, full: list[str]) -> None:
    game = Game(board)
    play_manually(game, full[:3])
    before = (game.state, game.moves, list(game.move_history))
    replayer = Replayer(game, full[3:])
    replayer.replay_all_to_end()
    assert game.is_won()
    replayer.stop()
    assert (
        game.state,
        game.moves,
        list(game.move_history),
    ) == before and game.status == GameStatus.PLAYING


def test_release_keeps_the_position_and_makes_stop_a_no_op(
    board: Board, full: list[str]
) -> None:
    game = Game(board)
    replayer = Replayer(game, full)
    replayer.seek(4)
    replayer.release()
    assert replayer.released and game.moves == 4
    replayer.stop()  # không khôi phục vì đã giao lại cho người chơi
    assert game.moves == 4


# ---------------------------------------------------------------- Replayer: từ ô xuất phát


def test_from_start_restarts_then_restores_the_manual_progress(
    board: Board, full: list[str]
) -> None:
    game = Game(board)
    play_manually(game, full[:3])
    snapshot = list(game.move_history)
    replayer = Replayer(game, full, mode=ReplayMode.FROM_START)
    assert (
        game.moves == 0 and game.state == game.initial_state
    )  # đã quay về ô xuất phát
    replayer.seek(5)
    replayer.stop()
    assert list(game.move_history) == snapshot and game.moves == 3


# ---------------------------------------------------------------- Replayer: đường đi không hợp lệ


def test_invalid_path_is_rejected_without_touching_the_game(board: Board) -> None:
    game = Game(board)
    before = game.state
    replayer = Replayer(game, ["UP", "UP"])
    assert (
        not replayer.is_valid_path and replayer.error_message and game.state == before
    )


def test_unknown_action_name_is_reported(board: Board) -> None:
    replayer = Replayer(Game(board), ["NHẢY"])
    assert not replayer.is_valid_path and replayer.error_message


def test_finished_game_cannot_be_replayed_from_current(
    board: Board, full: list[str]
) -> None:
    game = Game(board)
    play_manually(game, full)  # đã thắng
    replayer = Replayer(game, [], mode=ReplayMode.FROM_CURRENT)
    assert not replayer.is_valid_path and replayer.error_message == MSG_GAME_OVER


def test_invalid_replayer_never_moves_the_game(board: Board) -> None:
    game = Game(board)
    replayer = Replayer(game, ["UP"])
    replayer.seek(1)
    assert replayer.current_index == 0 and game.moves == 0


# ---------------------------------------------------------------- phát tự động


def test_update_waits_for_the_interval_and_for_animations(
    board: Board, full: list[str]
) -> None:
    replayer = Replayer(Game(board), full, step_interval=0.5)
    replayer.play()
    assert replayer.update(0.2) is False and replayer.current_index == 0
    assert replayer.update(0.4, busy=True) is False  # hoạt cảnh đang chạy: chưa đi
    assert (
        replayer.update(0.4) is True and replayer.current_index == 1
    )  # đã tới hạn khi hoạt cảnh xong


def test_update_does_nothing_while_paused(board: Board, full: list[str]) -> None:
    replayer = Replayer(Game(board), full, step_interval=0.01)
    assert replayer.update(1.0) is False
    replayer.play()
    replayer.pause()
    assert replayer.update(1.0) is False
    replayer.resume()
    assert replayer.update(1.0) is True


def test_play_after_finishing_starts_over(board: Board, full: list[str]) -> None:
    replayer = Replayer(Game(board), full)
    replayer.replay_all_to_end()
    replayer.play()
    assert replayer.current_index == 0 and replayer.is_playing


def test_speed_has_a_lower_bound(board: Board, full: list[str]) -> None:
    replayer = Replayer(Game(board), full)
    replayer.set_speed(0.0)
    assert replayer.step_interval == 0.01


def test_callbacks_report_steps_and_the_finish(board: Board, full: list[str]) -> None:
    steps: list[tuple[int, bool]] = []
    finished: list[ReplayFrame] = []
    replayer = Replayer(
        Game(board),
        full,
        on_step=lambda frame, animate: steps.append((frame.step_index, animate)),
        on_finish=finished.append,
    )
    replayer.seek(2)  # nhảy: không hoạt cảnh
    replayer.step_forward()  # tiến một bước: có hoạt cảnh
    replayer.replay_all_to_end()
    assert steps[0] == (2, False) and steps[1] == (3, True)
    assert len(finished) == 1 and finished[0].step_index == len(full)


def test_resume_is_ignored_when_already_finished(board: Board, full: list[str]) -> None:
    replayer = Replayer(Game(board), full)
    replayer.replay_all_to_end()
    replayer.resume()
    assert not replayer.is_playing
    assert replayer.current_state == replayer.timeline[-1].state
