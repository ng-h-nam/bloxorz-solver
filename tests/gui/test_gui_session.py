"""Test cho gui.model.session.GameSession: luật chơi, tiến trình màn, mật khẩu, hoàn tác và đồng hồ."""

import json
from pathlib import Path

import pytest

from algorithms.bfs import BFSSolver
from core.block import Direction
from core.game import Game, GameStatus
from gui.model.level_catalog import LevelCatalog
from gui.model.player_data import PlayerDataManager
from gui.model.session import (
    MSG_ENDED,
    NO_RECORD_TEXT,
    GameSession,
    MoveKind,
    StageSelection,
    UndoResult,
)
from gui.shared.actions import action_names


@pytest.fixture
def session(tmp_path: Path) -> GameSession:
    catalog = LevelCatalog.from_json()
    return GameSession(Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json"))


def solution(session: GameSession) -> list[str]:
    return action_names(BFSSolver(session.game.board).solve().actions)


def invalid_direction(game: Game) -> Direction:
    """Một hướng chắc chắn làm khối rơi từ trạng thái hiện tại."""
    valid = {action for action, _ in game.get_valid_moves() if isinstance(action, Direction)}
    return next(direction for direction in Direction if direction not in valid)


# ---------------------------------------------------------------- khởi tạo và thông tin


def test_the_starting_level_is_unlocked_and_named(session: GameSession) -> None:
    assert session.level_name == "Stage 01" and session.level_index == 0
    assert session.catalog.is_unlocked(0) and not session.catalog.is_unlocked(1)


def test_passcode_comes_from_the_catalog(session: GameSession) -> None:
    assert session.passcode == session.catalog.entries[0].passcode != ""


def test_say_sets_the_message(session: GameSession) -> None:
    session.say("xin chào")
    assert session.message == "xin chào"


def test_best_record_text_before_and_after_winning(session: GameSession) -> None:
    assert session.best_record_text() == NO_RECORD_TEXT
    for name in solution(session):
        session.move(Direction(name))
    assert session.best_record_text().startswith("7 bước")


# ---------------------------------------------------------------- nước đi


def test_a_valid_move_reports_a_roll(session: GameSession) -> None:
    report = session.move(Direction(solution(session)[0]))
    assert report is not None and report.kind == MoveKind.ROLL
    assert report.old_state != report.state and report.win is None and session.game.moves == 1


def test_stepping_off_the_board_reports_a_fall(session: GameSession) -> None:
    report = session.move(invalid_direction(session.game))
    assert report is not None and report.kind == MoveKind.FALL and report.broken_tile is None
    assert session.game.status == GameStatus.LOST and report.message


def test_moves_after_the_game_ends_explain_why(session: GameSession) -> None:
    session.move(invalid_direction(session.game))
    assert session.move(Direction.UP) is None and session.message == MSG_ENDED


def test_winning_records_the_score_and_unlocks_the_next_level(
    session: GameSession,
) -> None:
    reports = [session.move(Direction(name)) for name in solution(session)]
    final = reports[-1]
    assert final is not None and final.kind == MoveKind.WIN and final.win is not None
    assert final.win.score == 7 and final.win.next_name == "Stage 02" and not final.win.all_done
    assert session.catalog.is_unlocked(1) and session.next_index == 1
    info = session.players.get_level_score_info("Stage 01")
    assert info is not None and info["score"] == 7


def test_an_assisted_win_neither_records_nor_unlocks(session: GameSession) -> None:
    session.assisted = True
    final = [session.move(Direction(name)) for name in solution(session)][-1]
    assert final is not None and final.win is not None and final.win.assisted
    assert not session.catalog.is_unlocked(1) and session.next_index is None
    assert session.players.get_level_score_info("Stage 01") is None


def test_the_last_level_has_no_next(session: GameSession) -> None:
    session.load_stage(len(session.catalog) - 1)
    final = [session.move(Direction(name)) for name in solution(session)][-1]
    assert final is not None and final.win is not None and final.win.all_done and final.win.next_name is None


def test_switch_block_only_works_when_split(session: GameSession) -> None:
    assert session.switch_block() is False


# ---------------------------------------------------------------- hoàn tác


def test_undo_after_a_first_move_fall_restarts(session: GameSession) -> None:
    session.move(invalid_direction(session.game))
    assert session.undo() == UndoResult.RESTARTED and session.game.status == GameStatus.PLAYING


def test_undo_after_a_fall_revives_then_steps_back(session: GameSession) -> None:
    session.move(Direction(solution(session)[0]))
    position = session.game.state
    session.move(invalid_direction(session.game))
    assert session.undo() == UndoResult.REVIVED
    assert session.game.status == GameStatus.PLAYING and session.game.state == position
    assert session.undo() == UndoResult.STEPPED_BACK and session.game.moves == 0
    assert session.undo() == UndoResult.NOTHING and "xuất phát" in session.message


def test_revive_only_acts_on_a_lost_game(session: GameSession) -> None:
    assert session.revive() is False
    session.move(invalid_direction(session.game))
    assert session.revive() is True and session.game.status == GameStatus.PLAYING


def test_restart_resets_the_game_and_flags(session: GameSession) -> None:
    session.move(Direction(solution(session)[0]))
    session.assisted, session.elapsed = True, 5.0
    session.restart()
    assert session.game.moves == 0 and not session.assisted and session.elapsed == 0.0


# ---------------------------------------------------------------- chọn màn và mật khẩu


def test_select_stage_outcomes(session: GameSession) -> None:
    assert session.select_stage(0) == StageSelection.CURRENT
    assert session.select_stage(1) == StageSelection.NEEDS_PASSCODE
    assert session.select_stage(-1) == StageSelection.INVALID and session.select_stage(999) == StageSelection.INVALID
    session.catalog.unlock(1)
    assert session.select_stage(1) == StageSelection.LOADED
    assert session.level_name == "Stage 02" and session.revision == 1


def test_passcode_must_match_the_chosen_level_exactly(session: GameSession) -> None:
    assert not session.submit_passcode(2, "000000")
    assert not session.submit_passcode(2, session.catalog.entries[1].passcode)  # mật khẩu của màn khác
    assert not session.submit_passcode(2, "3")  # số thứ tự màn không phải mật khẩu
    assert session.submit_passcode(2, session.catalog.entries[2].passcode)
    assert session.level_name == "Stage 03"


def test_loading_a_stage_resets_the_session_state(session: GameSession) -> None:
    session.assisted, session.elapsed = True, 9.0
    assert session.load_stage(3)
    assert not session.assisted and session.elapsed == 0.0 and session.level_index == 3
    assert not session.load_stage(-1) and not session.load_stage(10_000)


def test_a_broken_stage_keeps_the_current_level_and_reports(tmp_path: Path) -> None:
    stages = [
        {
            "name": "Stage 01",
            "passcode": "111111",
            "grid": ["S.H"],
            "bridges": [],
            "switches": [],
            "teleports": [],
        },
        {
            "name": "Stage 02",
            "passcode": "222222",
            "grid": ["XXX"],
            "bridges": [],
            "switches": [],
            "teleports": [],
        },
    ]
    path = tmp_path / "coolmath.json"
    path.write_text(json.dumps(stages), encoding="utf-8")
    catalog = LevelCatalog.from_json(str(path))
    broken = GameSession(Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json"))
    broken.catalog.unlock(1)
    assert broken.load_stage(1) is False
    assert broken.level_name == "Stage 01" and "Không nạp được Stage 02" in broken.message


# ---------------------------------------------------------------- đồng hồ


def test_tick_runs_only_while_playing_and_not_paused(session: GameSession) -> None:
    session.tick(1.0)
    session.tick(1.0, paused=True)
    assert session.elapsed == 1.0
    session.move(invalid_direction(session.game))  # thua: đồng hồ dừng
    session.tick(1.0)
    assert session.elapsed == 1.0
