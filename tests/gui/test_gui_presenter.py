"""Test cho gui.presenter: băng thông báo và ScenePresenter."""

from pathlib import Path

import pytest

from algorithms.bfs import BFSSolver
from core.block import Direction
from core.game import Game, GameStatus
from gui.actions import action_names
from gui.level_catalog import LevelCatalog
from gui.player_data import PlayerDataManager
from gui.presenter import (
    HINT_LOST,
    HINT_WON,
    HINT_WON_NEXT,
    SUBTITLE_FALL,
    ScenePresenter,
    replay_banner,
    win_banner,
)
from gui.replay import build_timeline
from gui.session import GameSession, MoveKind, MoveReport, WinReport


@pytest.fixture
def session(tmp_path: Path) -> GameSession:
    catalog = LevelCatalog.from_json()
    return GameSession(
        Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json")
    )


@pytest.fixture
def presenter(session: GameSession) -> ScenePresenter:
    result = ScenePresenter()
    result.reset(session.game)
    return result


def first_move(session: GameSession) -> str:
    return action_names(BFSSolver(session.game.board).solve().actions)[0]


# ---------------------------------------------------------------- băng thông báo


def test_win_banner_shows_score_record_and_next_level() -> None:
    banner = win_banner(WinReport(7, 7, "Stage 02", False))
    assert (
        banner.title == "HOÀN THÀNH!"
        and "Điểm: 7" in banner.subtitle
        and "Stage 02" in banner.subtitle
    )
    assert banner.hint == HINT_WON_NEXT


def test_win_banner_on_the_last_level_has_no_next_hint() -> None:
    banner = win_banner(WinReport(7, 5, None, True))
    assert "tất cả các màn" in banner.subtitle and banner.hint == HINT_WON


def test_assisted_win_banner_says_nothing_was_unlocked() -> None:
    banner = win_banner(WinReport(7, 7, None, False, assisted=True))
    assert "AI" in banner.subtitle and "chưa mở" in banner.subtitle


def test_replay_banner_names_the_source_and_moves() -> None:
    banner = replay_banner("BFS", 7)
    assert (
        "BFS" in banner.subtitle
        and "7 bước" in banner.subtitle
        and "chưa mở" in banner.subtitle
    )


# ---------------------------------------------------------------- ScenePresenter


def test_a_roll_animates_then_shows_the_new_step_count(
    session: GameSession, presenter: ScenePresenter
) -> None:
    report = session.move(Direction(first_move(session)))
    assert report is not None
    presenter.show_move(session.game, report)
    assert (
        presenter.busy and presenter.shown_moves == 0
    )  # số bước chỉ hiện khi hoạt cảnh xong
    assert presenter.update(0.01, session.game) is False
    assert presenter.update(5.0, session.game) is True
    assert (
        presenter.shown_moves == 1 and presenter.banner is None and not presenter.busy
    )


def test_a_fall_shows_the_lose_banner_after_the_animation(
    session: GameSession, presenter: ScenePresenter
) -> None:
    valid = {a for a, _ in session.game.get_valid_moves() if isinstance(a, Direction)}
    report = session.move(next(d for d in Direction if d not in valid))
    assert report is not None
    presenter.show_move(session.game, report)
    assert presenter.banner is None
    presenter.update(5.0, session.game)
    assert (
        presenter.banner is not None
        and presenter.banner.title == "THUA!"
        and presenter.banner.hint == HINT_LOST
    )
    assert not presenter.block_visible and presenter.shown_status == GameStatus.LOST


def test_a_fall_without_a_message_uses_the_default_subtitle(
    session: GameSession, presenter: ScenePresenter
) -> None:
    state = session.game.state
    presenter.show_move(
        session.game, MoveReport(MoveKind.FALL, Direction.UP, state, state, "")
    )
    presenter.update(5.0, session.game)
    assert presenter.banner is not None and presenter.banner.subtitle == SUBTITLE_FALL


def test_a_broken_tile_disappears_when_the_block_starts_falling(
    session: GameSession, presenter: ScenePresenter
) -> None:
    state = session.game.state
    report = MoveReport(MoveKind.FALL, Direction.RIGHT, state, state, "vỡ", (1, 1))
    presenter.show_move(session.game, report)
    assert presenter.broken_tiles == frozenset()
    presenter.update(0.3, session.game)  # qua pha lăn, vào pha rơi
    assert presenter.broken_tiles == frozenset({(1, 1)})
    presenter.update(5.0, session.game)
    assert presenter.broken_tiles == frozenset({(1, 1)})


def test_a_win_shows_the_win_banner_when_finished(
    session: GameSession, presenter: ScenePresenter
) -> None:
    names = action_names(BFSSolver(session.game.board).solve().actions)
    last = None
    for name in names:
        last = session.move(Direction(name))
    assert last is not None and last.kind == MoveKind.WIN
    presenter.show_move(session.game, last)
    presenter.update(5.0, session.game)
    assert presenter.banner is not None and presenter.banner.title == "HOÀN THÀNH!"


def test_snap_cancels_animation_and_syncs_with_the_game(
    session: GameSession, presenter: ScenePresenter
) -> None:
    report = session.move(Direction(first_move(session)))
    assert report is not None
    presenter.show_move(session.game, report)
    presenter.snap(session.game)
    assert not presenter.busy and presenter.shown_moves == 1 and presenter.block_visible


def test_display_uses_the_game_when_idle_and_the_animation_when_busy(
    session: GameSession, presenter: ScenePresenter
) -> None:
    state, pose = presenter.display(session.game)
    assert state == session.game.state and pose is None
    report = session.move(Direction(first_move(session)))
    assert report is not None
    presenter.show_move(session.game, report)
    state, pose = presenter.display(session.game)
    assert (
        state == report.old_state and pose is not None
    )  # đang lăn: vẽ vị trí cũ cộng tư thế


def test_replay_steps_animate_forward_and_jump_otherwise(
    session: GameSession, presenter: ScenePresenter
) -> None:
    names = action_names(BFSSolver(session.game.board).solve().actions)
    frames, _, _ = build_timeline(session.game.board, session.game.state, names)
    presenter.show_replay_step(session.game, frames[1], animate=True)
    assert presenter.busy
    presenter.show_replay_step(session.game, frames[1], animate=False)
    assert not presenter.busy and presenter.banner is None


def test_replay_reaching_the_goal_shows_the_replay_banner(
    session: GameSession, presenter: ScenePresenter
) -> None:
    names = action_names(BFSSolver(session.game.board).solve().actions)
    frames, _, _ = build_timeline(session.game.board, session.game.state, names)
    presenter.show_replay_step(session.game, frames[-1], animate=False, source="BFS")
    assert (
        presenter.banner is not None
        and presenter.banner.title == "GIẢI XONG!"
        and not presenter.block_visible
    )
    presenter.show_replay_step(session.game, frames[-1], animate=True, source="BFS")
    assert presenter.banner is None  # banner chờ hoạt cảnh xong
    presenter.update(5.0, session.game)
    assert presenter.banner is not None
