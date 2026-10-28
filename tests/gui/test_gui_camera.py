import itertools
import math

import pytest

from gui.scene.camera import (
    DEFAULT_ELEVATION,
    MAX_ELEVATION,
    MIN_DISTANCE,
    MIN_ELEVATION,
    OrbitCamera,
)


def dist(cam):
    return math.dist(cam.eye, cam.target)


def test_default_eye_matches_the_old_fixed_camera_formula():
    cam = OrbitCamera(8.5, 5.0, 20.0)
    assert cam.eye == pytest.approx(
        (8.5, 20 * math.sin(DEFAULT_ELEVATION), 5.0 + 20 * math.cos(DEFAULT_ELEVATION))
    )


def test_orbit_keeps_distance_and_clamps_elevation():
    cam = OrbitCamera(0, 0, 20.0)
    for dx, dy in [(50, 0), (-300, 40), (10, 2000), (0, -5000)]:
        cam.orbit(dx, dy)
        assert dist(cam) == pytest.approx(20.0)
        assert MIN_ELEVATION - 1e-9 <= cam.elevation <= MAX_ELEVATION + 1e-9
        assert -math.pi <= cam.yaw <= math.pi


def test_full_turn_returns_to_same_eye():
    cam = OrbitCamera(0, 0, 20.0)
    before = cam.eye
    cam.orbit(2 * math.pi / 0.008, 0)
    assert cam.eye == pytest.approx(before, abs=1e-6)


def test_zoom_changes_distance_and_clamps():
    cam = OrbitCamera(0, 0, 20.0)
    cam.zoom(1)
    assert cam.distance < 20.0
    cam.zoom(-1)
    assert cam.distance == pytest.approx(20.0)
    cam.zoom(1000)
    assert cam.distance == pytest.approx(max(MIN_DISTANCE, 20.0 * 0.35))
    cam.zoom(-1000)
    assert cam.distance == pytest.approx(20.0 * 2.5)


def test_ground_vectors_are_orthonormal_for_any_yaw():
    cam = OrbitCamera(0, 0, 20.0)
    for yaw in (0, 0.7, 1.9, -2.4, math.pi):
        cam.yaw = yaw
        f, r = cam.forward_ground(), cam.right_ground()
        assert math.hypot(*f) == pytest.approx(1) and math.hypot(*r) == pytest.approx(1)
        assert f[0] * r[0] + f[1] * r[1] == pytest.approx(0, abs=1e-9)


def test_pan_follows_the_cursor_and_respects_limits():
    cam = OrbitCamera(10, 10, 20.0, limits=(5, 15, 5, 15))
    cam.pan(100, 0)  # kéo sang phải: cảnh đi theo, điểm nhìn đi sang trái
    assert cam.center_x < 10 and cam.center_z == pytest.approx(10)
    cam.pan(0, 100)  # kéo xuống: điểm nhìn đi ra xa (z giảm khi yaw = 0)
    assert cam.center_z < 10
    cam.pan(-100000, 100000)
    assert 5 <= cam.center_x <= 15 and 5 <= cam.center_z <= 15


def test_reset_restores_the_defaults():
    cam = OrbitCamera(7, 3, 15.0)
    cam.orbit(80, 30)
    cam.zoom(3)
    cam.pan(40, 40)
    cam.reset()
    assert (cam.center_x, cam.center_z, cam.distance, cam.yaw, cam.elevation) == (
        7,
        3,
        15.0,
        0.0,
        DEFAULT_ELEVATION,
    )


def moved_camera():
    cam = OrbitCamera(7, 3, 15.0)
    cam.orbit(300, 60)
    cam.zoom(4)
    cam.pan(120, -80)
    return cam


def test_smooth_reset_reaches_the_defaults_exactly_and_stops():
    cam = moved_camera()
    cam.start_reset(0.35)
    assert cam.is_resetting
    cam.update(0.1)
    assert cam.is_resetting and cam.yaw != 0
    cam.update(1.0)
    assert not cam.is_resetting
    assert (cam.center_x, cam.center_z, cam.distance, cam.yaw, cam.elevation) == (
        7,
        3,
        15.0,
        0.0,
        DEFAULT_ELEVATION,
    )


def test_smooth_reset_moves_monotonically_toward_the_defaults():
    cam = moved_camera()
    cam.start_reset(0.4)
    distances, yaws = [], []
    for _ in range(20):
        cam.update(0.02)
        distances.append(abs(cam.distance - 15.0))
        yaws.append(abs(cam.yaw))
    assert all(b <= a + 1e-9 for a, b in itertools.pairwise(distances))
    assert all(b <= a + 1e-9 for a, b in itertools.pairwise(yaws))


def test_reset_turns_the_short_way_round():
    cam = OrbitCamera(0, 0, 20.0)
    cam.yaw = 3.0  # gần nửa vòng: về 0 theo chiều giảm, không vòng qua -pi
    cam.start_reset(0.4)
    seen = []
    for _ in range(20):
        cam.update(0.02)
        seen.append(cam.yaw)
    assert all(0 <= y <= 3.0 + 1e-9 for y in seen)


def test_any_user_input_cancels_a_running_reset():
    for action in (lambda c: c.orbit(5, 5), lambda c: c.zoom(1), lambda c: c.pan(5, 5)):
        cam = moved_camera()
        cam.start_reset(0.5)
        cam.update(0.1)
        action(cam)
        assert not cam.is_resetting
        before = (cam.yaw, cam.distance, cam.center_x)
        cam.update(1.0)
        assert (cam.yaw, cam.distance, cam.center_x) == before


def test_zero_seconds_resets_immediately():
    cam = moved_camera()
    cam.start_reset(0)
    assert not cam.is_resetting and cam.yaw == 0.0 and cam.distance == 15.0
