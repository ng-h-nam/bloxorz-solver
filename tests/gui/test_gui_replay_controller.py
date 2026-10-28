"""Test cho gui.engine.replay_controller.ReplayController."""

from pathlib import Path

import pytest

from algorithms.bfs import BFSSolver
from core.game import Game
from gui.engine.presenter import ScenePresenter
from gui.engine.replay import ReplayMode
from gui.engine.replay_controller import (
    MSG_NO_SAVED_REPLAY,
    SPEED_PRESETS,
    ReplayController,
)
from gui.model.level_catalog import LevelCatalog
from gui.model.player_data import MANUAL, PlayerDataManager
from gui.model.session import GameSession
from gui.shared.actions import action_names


@pytest.fixture
def parts(
    tmp_path: Path,
) -> tuple[GameSession, ScenePresenter, ReplayController, list[str]]:
    catalog = LevelCatalog.from_json()
    session = GameSession(
        Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json")
    )
    presenter = ScenePresenter()
    presenter.reset(session.game)
    full = action_names(BFSSolver(session.game.board).solve().actions)
    return session, presenter, ReplayController(session, presenter), full


def test_start_from_current_begins_playing(parts) -> None:
    _, _, controller, full = parts
    assert controller.start(full, ReplayMode.FROM_CURRENT, "BFS")
    assert (
        controller.active
        and controller.playing
        and controller.total == len(full)
        and controller.step == 0
    )


def test_invalid_path_reports_and_stays_inactive(parts) -> None:
    session, _, controller, _ = parts
    assert not controller.start(["UP"], ReplayMode.FROM_CURRENT)
    assert not controller.active and session.message


def test_a_new_replay_first_restores_the_previous_one(parts) -> None:
    session, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.replayer.seek(4)  # type: ignore[union-attr]
    controller.start(full, ReplayMode.FROM_CURRENT)
    assert session.game.moves == 0  # lượt cũ đã được trả về như ban đầu


def test_steps_wait_for_the_animation_to_finish(parts) -> None:
    session, presenter, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.update(0.5)
    assert controller.step == 1 and presenter.busy  # bước đầu có hoạt cảnh
    controller.update(0.5)
    assert controller.step == 1  # hoạt cảnh chưa xong nên chưa đi tiếp
    presenter.update(5.0, session.game)
    controller.update(0.5)
    assert controller.step == 2


def test_toggle_pause_and_resume(parts) -> None:
    session, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.toggle_pause()
    assert not controller.playing and "tạm dừng" in session.message
    controller.toggle_pause()
    assert controller.playing and "Tiếp tục" in session.message


def test_manual_stepping_pauses_and_reports(parts) -> None:
    session, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.step_forward()
    assert (
        not controller.playing and controller.step == 1 and "bước 1" in session.message
    )
    controller.step_backward()
    assert controller.step == 0 and "lùi" in session.message


def test_controls_do_nothing_without_a_replay(parts) -> None:
    session, _, controller, _ = parts
    for action in (
        controller.toggle_pause,
        controller.step_forward,
        controller.step_backward,
        controller.stop,
    ):
        action()
    assert not controller.active and session.message == ""


def test_cycle_speed_wraps_around_and_updates_the_replayer(parts) -> None:
    _, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    labels = []
    for _ in range(len(SPEED_PRESETS)):
        controller.cycle_speed()
        labels.append(controller.speed_label)
    assert labels[-1] == controller.speeds[controller.speed_index][0] == "1x"
    assert controller.replayer.step_interval == dict(SPEED_PRESETS)["1x"]  # type: ignore[union-attr]


def test_stop_restores_the_players_position(parts) -> None:
    session, _, controller, full = parts
    for name in full[:3]:
        session.game.move(name)
    here = session.game.state
    controller.start(full[3:], ReplayMode.FROM_CURRENT)
    controller.replayer.replay_all_to_end()  # type: ignore[union-attr]
    controller.stop()
    assert (
        session.game.state == here and session.game.moves == 3 and not controller.active
    )
    assert not session.assisted


def test_takeover_keeps_the_position_and_marks_assistance(parts) -> None:
    session, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.replayer.seek(3)  # type: ignore[union-attr]
    controller.takeover()
    assert not controller.active and session.assisted and session.game.moves == 3


def test_discard_drops_the_replay_without_touching_the_game(parts) -> None:
    session, _, controller, full = parts
    controller.start(full, ReplayMode.FROM_CURRENT)
    controller.replayer.seek(2)  # type: ignore[union-attr]
    controller.discard()
    assert not controller.active and session.game.moves == 2


def test_play_saved_without_a_record_explains_itself(parts) -> None:
    session, _, controller, _ = parts
    assert not controller.play_saved()
    assert session.message == MSG_NO_SAVED_REPLAY


def test_play_saved_replays_from_the_start_and_restores_progress(parts) -> None:
    session, _, controller, full = parts
    session.players.record_game_session(session.level_name, full, True, MANUAL, 3.0)
    session.game.move(full[0])
    assert controller.play_saved()
    assert (
        session.game.moves == 0 and "từ ô xuất phát" in session.message
    )  # đã về ô xuất phát
    controller.stop()
    assert session.game.moves == 1  # tiến trình của người chơi được trả lại
