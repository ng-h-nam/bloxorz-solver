import pytest

from core.block import Direction
from core.state import Orientation, State
from gui.engine.animator import (
    FALL_SECONDS,
    ROLL_SECONDS,
    SINK_SECONDS,
    Animator,
    Phase,
)

OLD = State(3, 3, Orientation.STANDING)
NEW = State(3, 4, Orientation.HORIZONTAL)


def test_idle_by_default():
    a = Animator()
    assert not a.active and a.phase == Phase.IDLE and a.pose is None and a.display_state is None
    assert a.update(1.0) is False


def test_roll_runs_exactly_roll_seconds():
    a = Animator()
    a.start_roll(OLD, Direction.RIGHT, NEW)
    assert a.update(ROLL_SECONDS / 2) is False
    assert a.phase == Phase.ROLL and 0 < a.pose.angle < 90 and a.pose.drop == 0
    assert a.display_state == OLD
    assert a.update(ROLL_SECONDS / 2) is True
    assert not a.active


def test_update_reports_finish_only_once():
    a = Animator()
    a.start_roll(OLD, Direction.RIGHT, NEW)
    assert a.update(10.0) is True
    assert a.update(10.0) is False


def test_fall_is_roll_then_fall_with_continuous_angle():
    a = Animator()
    a.start_fall(OLD, Direction.RIGHT)
    assert a.update(ROLL_SECONDS - 1e-9) is False
    assert a.phase == Phase.ROLL and a.pose.angle == pytest.approx(90, abs=1e-3)
    assert a.update(1e-9 + FALL_SECONDS / 2) is False
    assert a.phase == Phase.FALL and a.pose.angle > 90 and a.pose.drop < 0
    assert a.update(FALL_SECONDS / 2) is True


def test_win_is_roll_then_sink_and_switches_display_state():
    a = Animator()
    a.start_win(OLD, Direction.RIGHT, NEW)
    assert a.display_state == OLD
    a.update(ROLL_SECONDS + SINK_SECONDS / 2)
    assert a.phase == Phase.SINK and a.display_state == NEW
    pose = a.pose
    assert pose.direction is None and pose.angle == 0 and pose.drop < 0
    assert a.update(SINK_SECONDS) is True


def test_big_step_spanning_all_phases_finishes():
    a = Animator()
    a.start_fall(OLD, Direction.LEFT)
    assert a.update(ROLL_SECONDS + FALL_SECONDS + 5) is True and not a.active


def test_cancel_stops_everything():
    a = Animator()
    a.start_roll(OLD, Direction.UP, NEW)
    a.cancel()
    assert not a.active and a.pose is None


def test_pose_of_split_cube_uses_the_active_cube():
    split = State(2, 2, Orientation.SPLIT, frozenset(), (2, 6), 1)
    a = Animator()
    a.start_roll(split, Direction.RIGHT, State(2, 2, Orientation.SPLIT, frozenset(), (2, 7), 1))
    a.update(0.05)
    assert a.pose.piece == 1 and a.pose.bounds == (6, 7, 0, 1, 2, 3)


def test_fall_without_broken_tile_rotates_off_the_edge():
    a = Animator()
    a.start_fall(OLD, Direction.RIGHT)
    a.update(ROLL_SECONDS + FALL_SECONDS / 2)
    assert a.pose.tile is None and a.pose.angle > 90 and a.pose.drop < 0 and a.broken_tile is None


def test_fall_with_broken_tile_tile_goes_first_then_block_follows_straight_down():
    a = Animator()
    a.start_fall(OLD, Direction.RIGHT, (3, 4))
    a.update(ROLL_SECONDS / 2)
    assert a.pose.tile is None  # còn đang lăn: ô chưa vỡ
    a.update(ROLL_SECONDS / 2 + FALL_SECONDS * 0.1)  # 10% đầu pha rơi: ô đã rơi, khối chưa
    early = a.pose
    assert a.phase == Phase.FALL and a.broken_tile == (3, 4)
    assert early.tile is not None and early.tile.cell == (3, 4)
    assert early.tile.drop < 0 and early.drop == 0
    assert early.angle == pytest.approx(90.0)  # khối đã đứng trên ô, không xoay thêm
    a.update(FALL_SECONDS * 0.4)  # giữa pha rơi: cả hai đang rơi, ô nhanh hơn
    mid = a.pose
    assert mid.drop < 0 and mid.tile.drop < mid.drop
    assert mid.tile.degrees != 0  # ô nghiêng
    a.update(FALL_SECONDS * 0.49)  # gần hết pha rơi: cả hai gần như cùng độ sâu
    late = a.pose
    assert abs(late.tile.drop - late.drop) < 0.2
    assert a.update(FALL_SECONDS) is True


def test_broken_tile_is_forgotten_after_cancel_or_finish():
    a = Animator()
    a.start_fall(OLD, Direction.UP, (1, 1))
    a.cancel()
    assert a.broken_tile is None
    a.start_fall(OLD, Direction.UP, (1, 1))
    a.update(10.0)
    assert a.broken_tile is None and a.pose is None
