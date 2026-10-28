"""Test cho độ dày gạch, gui.shared.geometry.plan_fall và hoạt cảnh rơi mới: khối đổ quanh mép rồi rơi, KHÔNG xuyên gạch."""

import itertools
import math
from collections import deque
from dataclasses import dataclass

import pytest

from core.block import Direction
from core.board import Board, TileType
from core.game import Game
from core.state import Orientation, State
from core.transition import get_next_state, roll_block
from gui.engine.animator import (
    GRAVITY,
    ROLL_SECONDS,
    TIP_SECONDS,
    TOPPLE_SECONDS,
    Animator,
    Phase,
    Pose,
    transform_point,
)
from gui.model.level_catalog import LevelCatalog
from gui.shared import geometry
from gui.shared.geometry import (
    TILE_HEIGHT,
    FallKind,
    FallPlan,
    Vec3,
    active_piece,
    block_pieces,
    broken_fragile_cell,
    composed_face_shades,
    plan_fall,
    roll_pivot,
    rotate_about,
    rotated_face_shades,
    supports_block,
    tile_bounds,
)

CATALOG = LevelCatalog.from_json()
MAX_STATES_PER_MAP = 1500


@dataclass(frozen=True)
class FallCase:
    """Một pha rơi có thật trong một màn: bản đồ, trạng thái, hướng, và kế hoạch của nó."""

    map_index: int
    board: Board
    state: State
    direction: Direction
    plan: FallPlan | None
    path: tuple[Direction, ...]  # đường đi từ ô xuất phát tới `state`


def collect_falls() -> list[FallCase]:
    """Duyệt các trạng thái chạm tới được của mọi màn và gom các pha rơi (kèm đường đi tới đó)."""
    found: list[FallCase] = []
    for index in range(len(CATALOG)):
        board = CATALOG.board(index)
        start = Game(board).initial_state
        seen = {start.to_key()}
        queue: deque[tuple[State, tuple[Direction, ...]]] = deque([(start, ())])
        while queue and len(seen) < MAX_STATES_PER_MAP:
            state, path = queue.popleft()
            for direction in Direction:
                following = get_next_state(state, direction, board=board)
                if following is None:
                    found.append(
                        FallCase(
                            index,
                            board,
                            state,
                            direction,
                            plan_fall(board, state, direction),
                            path,
                        )
                    )
                elif following.to_key() not in seen:
                    seen.add(following.to_key())
                    queue.append((following, (*path, direction)))
    return found


FALLS = collect_falls()


def pick(
    kind: FallKind | None, count: int, predicate=lambda case: True
) -> list[FallCase]:
    """Chọn đều `count` ca thuộc loại `kind` (None: ca không có kế hoạch) để test chạy nhanh mà vẫn phủ nhiều màn."""
    pool = [
        c for c in FALLS if (c.plan.kind if c.plan else None) == kind and predicate(c)
    ]
    assert pool, f"không có ca nào thuộc loại {kind}"
    step = max(1, len(pool) // count)
    return pool[::step][:count]


# ---------------------------------------------------------------- độ dày gạch


def test_tile_height_is_one_block() -> None:
    assert geometry.TILE_HEIGHT == 1.0


def test_tile_bounds_follow_the_shared_thickness() -> None:
    assert tile_bounds(2, 3) == (3.02, 3.98, -1.0, 0.0, 2.02, 2.98)
    assert tile_bounds(0, 0, height=0.25)[2] == -0.25


def test_tile_thickness_can_be_changed_in_one_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(geometry, "TILE_HEIGHT", 0.5)
    assert geometry.tile_bounds(0, 0)[2] == -0.5


def test_renderer_and_primitives_use_the_shared_definition() -> None:
    try:
        from gui.scene import primitives, renderer
    except ImportError:  # máy không có thư viện OpenGL
        pytest.skip("thiếu OpenGL")
    assert (
        renderer.tile_bounds is geometry.tile_bounds
        and renderer.TILE_HEIGHT == geometry.TILE_HEIGHT
    )
    assert not hasattr(primitives, "TILE_THICKNESS")  # hằng số trùng đã bị xóa


# ---------------------------------------------------------------- supports_block


def test_supports_block_rules() -> None:
    board = CATALOG.board(0)
    state = Game(board).initial_state
    assert supports_block(board, state, (state.r, state.c))
    assert not supports_block(board, state, (-1, 0)) and not supports_block(
        board, state, (board.rows, 0)
    )
    void = next(
        (r, c)
        for r in range(board.rows)
        for c in range(board.cols)
        if board.grid[r][c] == TileType.VOID
    )
    assert not supports_block(board, state, void)


def test_a_bridge_supports_only_while_open() -> None:
    index = next(
        i
        for i in range(len(CATALOG))
        if any(t == TileType.BRIDGE for row in CATALOG.board(i).grid for t in row)
    )
    board = CATALOG.board(index)
    cell = next(
        (r, c)
        for r in range(board.rows)
        for c in range(board.cols)
        if board.grid[r][c] == TileType.BRIDGE
    )
    closed = State(0, 0, Orientation.STANDING)
    opened = State(0, 0, Orientation.STANDING, active_bridges=frozenset([cell]))
    assert not supports_block(board, closed, cell) and supports_block(
        board, opened, cell
    )


# ---------------------------------------------------------------- plan_fall


def test_every_kind_of_fall_exists_in_the_real_levels() -> None:
    kinds = {c.plan.kind for c in FALLS if c.plan}
    assert kinds == {FallKind.UNSUPPORTED, FallKind.PARTIAL}
    assert len(FALLS) > 1000 and any(
        c.plan is None for c in FALLS
    )  # ô giòn và ca hiếm không có kế hoạch


def test_a_valid_move_has_no_fall_plan() -> None:
    board = CATALOG.board(0)
    state = Game(board).initial_state
    direction = next(
        d for d in Direction if get_next_state(state, d, board=board) is not None
    )
    assert plan_fall(board, state, direction) is None


def test_standing_on_a_fragile_tile_keeps_its_own_animation() -> None:
    fragile = [
        c
        for c in FALLS
        if broken_fragile_cell(c.board, roll_block(c.state, c.direction)) is not None
    ]
    assert fragile and all(c.plan is None for c in fragile)


@pytest.mark.parametrize(
    "case",
    pick(FallKind.UNSUPPORTED, 40),
    ids=lambda c: f"m{c.map_index + 1}-{c.state.orientation.name}-{c.direction.name}",
)
def test_rolling_off_an_edge_tips_around_the_rolling_edge(case: FallCase) -> None:
    plan = case.plan
    assert (
        plan is not None
        and plan.kind == FallKind.UNSUPPORTED
        and plan.tip_direction == case.direction
    )
    bounds = block_pieces(case.state)[active_piece(case.state)]
    px, pz, _, _ = roll_pivot(bounds, case.direction)
    assert plan.pivot == (px, 0.0, pz)
    x0, x1, y0, y1, z0, z1 = bounds
    along = (
        (x1 - x0) if case.direction in (Direction.LEFT, Direction.RIGHT) else (z1 - z0)
    )
    assert plan.critical_degrees == pytest.approx(
        math.degrees(math.atan2(along / 2, (y1 - y0) / 2))
    )


def test_critical_angles_for_each_shape_of_block() -> None:
    def first(predicate) -> FallPlan:
        return next(
            c.plan for c in pick(FallKind.UNSUPPORTED, 10**6, predicate) if c.plan
        )

    along_x = lambda c: c.direction in (Direction.LEFT, Direction.RIGHT)
    assert first(
        lambda c: c.state.orientation == Orientation.STANDING
    ).critical_degrees == pytest.approx(26.565, abs=1e-3)
    assert first(
        lambda c: c.state.orientation == Orientation.HORIZONTAL and not along_x(c)
    ).critical_degrees == pytest.approx(45.0)
    assert first(
        lambda c: c.state.orientation == Orientation.HORIZONTAL and along_x(c)
    ).critical_degrees == pytest.approx(63.435, abs=1e-3)
    assert first(lambda c: c.state.is_split()).critical_degrees == pytest.approx(45.0)


@pytest.mark.parametrize(
    "case",
    pick(FallKind.PARTIAL, 40),
    ids=lambda c: f"m{c.map_index + 1}-{c.state.orientation.name}-{c.direction.name}",
)
def test_lying_across_an_edge_seesaws_around_the_supporting_tile(
    case: FallCase,
) -> None:
    plan = case.plan
    assert (
        plan is not None
        and plan.kind == FallKind.PARTIAL
        and plan.critical_degrees == 0.0
    )
    cells = roll_block(case.state, case.direction).get_occupied_cells()
    holding = [c for c in cells if supports_block(case.board, case.state, c)]
    empty = [c for c in cells if not supports_block(case.board, case.state, c)]
    assert len(holding) == len(empty) == 1
    delta = (empty[0][0] - holding[0][0], empty[0][1] - holding[0][1])
    assert geometry.FORWARD[plan.tip_direction] == (
        float(delta[1]),
        0.0,
        float(delta[0]),
    )  # đổ từ ô đỡ về ô trống
    edge = {
        Direction.RIGHT: holding[0][1] + 1,
        Direction.LEFT: holding[0][1],
        Direction.DOWN: holding[0][0] + 1,
        Direction.UP: holding[0][0],
    }[plan.tip_direction]
    assert (
        plan.pivot[0]
        if plan.tip_direction in (Direction.LEFT, Direction.RIGHT)
        else plan.pivot[2]
    ) == edge and plan.pivot[1] == 0.0


def test_move_report_and_presenter_carry_the_plan() -> None:
    import os
    import tempfile

    from gui.engine.animator import Phase
    from gui.engine.presenter import ScenePresenter
    from gui.model.player_data import PlayerDataManager
    from gui.model.session import GameSession, MoveKind

    for kind, first_phase in (
        (FallKind.UNSUPPORTED, Phase.TIP),
        (FallKind.PARTIAL, Phase.ROLL),
    ):
        case = pick(kind, 1, lambda c: c.map_index == 0)[0]
        game = Game(case.board)
        session = GameSession(
            game, CATALOG, PlayerDataManager(os.path.join(tempfile.mkdtemp(), "p.json"))
        )
        for step in case.path:
            assert session.move(step) is not None
        session.game.status  # noqa: B018 - chắc chắn ván còn đang chơi
        report = session.move(case.direction)
        assert (
            report is not None
            and report.kind == MoveKind.FALL
            and report.fall_plan == case.plan
        )
        presenter = ScenePresenter()
        presenter.show_move(session.game, report)
        assert presenter.animator.phase == first_phase


# ---------------------------------------------------------------- phép quay và độ sáng


def test_rotate_about_keeps_the_pivot_fixed() -> None:
    pivot = (2.0, 0.0, 5.0)
    assert rotate_about(pivot, pivot, (0.0, 0.0, 1.0), 77.0) == pivot
    x, y, z = rotate_about(
        (3.0, 0.0, 5.0), pivot, (0.0, 0.0, 1.0), 90.0
    )  # (+1,0) quay +90 độ quanh z -> (0,+1)
    assert (round(x, 9), round(y, 9), round(z, 9)) == (2.0, 1.0, 5.0)


def test_composed_shades_match_the_single_rotation_helpers() -> None:
    base = geometry.DEFAULT_FACE_SHADE
    axis = (1.0, 0.0, 0.0)
    assert (
        composed_face_shades(base, []) == base
        and composed_face_shades(base, []) is not base
    )
    assert composed_face_shades(base, [(axis, 40.0)]) == rotated_face_shades(
        base, axis, 40.0
    )
    twice = composed_face_shades(base, [(axis, 90.0), (axis, 90.0)])
    flipped = composed_face_shades(base, [(axis, 180.0)])
    assert all(twice[name] == pytest.approx(flipped[name]) for name in base)


# ---------------------------------------------------------------- hoạt cảnh rơi: không xuyên gạch

FRAME = 1 / 60
MARGIN = 0.03  # bỏ qua mép chạm nhẹ giữa khối và gạch


def sample_points(
    bounds: tuple[float, float, float, float, float, float], step: float = 0.25
) -> list[Vec3]:
    """Lưới điểm nằm trong thể tích khối (đại diện cho cả khối khi kiểm tra va chạm)."""
    x0, x1, y0, y1, z0, z1 = bounds

    def axis(a: float, b: float) -> list[float]:
        n = max(1, round((b - a) / step))
        return [a + (b - a) * (k + 0.5) / n for k in range(n)]

    return [(x, y, z) for x in axis(x0, x1) for y in axis(y0, y1) for z in axis(z0, z1)]


def inside_a_tile(case: FallCase, point: Vec3, height: float) -> bool:
    """Điểm có nằm sâu trong thân một viên gạch đặc không."""
    x, y, z = point
    col, row = math.floor(x), math.floor(z)
    if not case.board.in_board(row, col):
        return False
    tile = case.board.get_tile(row, col)
    if tile == TileType.VOID or (
        tile == TileType.BRIDGE and (row, col) not in case.state.active_bridges
    ):
        return False
    return (
        col + 0.02 + MARGIN < x < col + 0.98 - MARGIN
        and row + 0.02 + MARGIN < z < row + 0.98 - MARGIN
        and -height + MARGIN < y < -MARGIN
    )


def poses(animator: Animator) -> list[Pose]:
    """Mọi tư thế (mỗi khung 1/60 giây) cho tới khi hoạt cảnh kết thúc."""
    result: list[Pose] = []
    while animator.active:
        pose = animator.pose
        if pose is not None:
            result.append(pose)
        animator.update(FRAME)
    return result


def start(case: FallCase, with_plan: bool = True) -> Animator:
    animator = Animator()
    animator.start_fall(
        case.state, case.direction, None, case.plan if with_plan else None
    )
    return animator


def penetrating_frames(case: FallCase, height: float, with_plan: bool = True) -> int:
    """Số khung mà có ít nhất một điểm của khối nằm trong thân gạch."""
    points = sample_points(block_pieces(case.state)[active_piece(case.state)])
    return sum(
        any(inside_a_tile(case, transform_point(pose, p), height) for p in points)
        for pose in poses(start(case, with_plan))
    )


# ---------------------------------------------------------------- không xuyên gạch


@pytest.mark.parametrize("kind", [FallKind.UNSUPPORTED, FallKind.PARTIAL])
@pytest.mark.parametrize("height", [TILE_HEIGHT, 0.2, 0.5])
def test_the_new_fall_never_passes_through_a_tile(
    kind: FallKind, height: float
) -> None:
    cases = pick(kind, 60)
    assert len({c.map_index for c in cases}) > 10  # mẫu trải trên nhiều màn
    assert [c for c in cases if penetrating_frames(c, height) > 0] == []


def test_the_detector_really_catches_the_old_fall_motion() -> None:
    """Đối chứng: hoạt cảnh cũ (lăn trọn rồi rơi thẳng) xuyên gạch ở mọi ca 'đỡ một nửa'."""
    cases = pick(FallKind.PARTIAL, 30)
    assert all(penetrating_frames(c, TILE_HEIGHT, with_plan=False) > 0 for c in cases)


# ---------------------------------------------------------------- nhịp và hình dạng chuyển động


def case_of(kind: FallKind) -> FallCase:
    return pick(kind, 1)[0]


def test_unsupported_fall_is_a_single_tip_phase() -> None:
    animator = start(case_of(FallKind.UNSUPPORTED))
    assert animator.phase == Phase.TIP
    total = sum(1 for _ in poses(start(case_of(FallKind.UNSUPPORTED)))) * FRAME
    assert total == pytest.approx(TIP_SECONDS, abs=2 * FRAME)
    assert animator.update(TIP_SECONDS + 0.01) is True and not animator.active


def test_partial_fall_rolls_first_then_tips() -> None:
    animator = start(case_of(FallKind.PARTIAL))
    assert animator.phase == Phase.ROLL
    animator.update(ROLL_SECONDS + 0.001)
    assert animator.phase == Phase.TIP
    assert animator.update(TIP_SECONDS) is True


def test_without_a_plan_the_old_two_phase_fall_is_kept() -> None:
    animator = start(case_of(FallKind.UNSUPPORTED), with_plan=False)
    assert animator.phase == Phase.ROLL
    animator.update(ROLL_SECONDS + 0.001)
    assert animator.phase == Phase.FALL


def test_a_fragile_tile_still_uses_the_old_animation_even_with_a_plan() -> None:
    case = case_of(FallKind.UNSUPPORTED)
    animator = Animator()
    animator.start_fall(case.state, case.direction, (0, 0), case.plan)
    animator.update(ROLL_SECONDS + 0.001)
    assert animator.phase == Phase.FALL and animator.broken_tile == (0, 0)


def test_unsupported_pose_has_no_separate_roll() -> None:
    pose = start(case_of(FallKind.UNSUPPORTED)).pose
    assert (
        pose is not None
        and pose.direction is None
        and pose.angle == 0.0
        and pose.tip is not None
    )
    assert pose.tip.degrees == 0.0 and pose.tip.shift == (0.0, 0.0, 0.0)


def test_partial_pose_keeps_the_finished_roll() -> None:
    case = case_of(FallKind.PARTIAL)
    animator = start(case)
    animator.update(ROLL_SECONDS + FRAME)
    pose = animator.pose
    assert (
        pose is not None
        and pose.direction == case.direction
        and pose.angle == 90.0
        and pose.tip is not None
    )


@pytest.mark.parametrize("kind", [FallKind.UNSUPPORTED, FallKind.PARTIAL])
def test_the_block_topples_faster_and_faster_up_to_exactly_ninety_degrees(
    kind: FallKind,
) -> None:
    tips = [p.tip for p in poses(start(case_of(kind))) if p.tip is not None]
    angles = [abs(t.degrees) for t in tips]
    assert (
        angles == sorted(angles)
        and angles[0] < 0.5
        and angles[-1] == pytest.approx(90.0)
    )  # khung đầu có thể lệch tối đa một khung
    topple_frames = round(TOPPLE_SECONDS / FRAME)
    assert angles[topple_frames - 1] < 90.0 and angles[
        topple_frames + 2
    ] == pytest.approx(90.0)
    gaps = [b - a for a, b in itertools.pairwise(angles[:topple_frames])]
    assert all(
        later >= earlier - 1e-9 for earlier, later in itertools.pairwise(gaps)
    )  # tốc độ góc tăng dần


def test_the_block_only_slides_after_its_centre_of_mass_passes_the_edge() -> None:
    case = pick(
        FallKind.UNSUPPORTED, 1, lambda c: c.state.orientation.name == "STANDING"
    )[0]
    assert case.plan is not None
    contact_end = TOPPLE_SECONDS * math.sqrt(case.plan.critical_degrees / 90.0)
    for index, pose in enumerate(poses(start(case))):
        assert pose.tip is not None
        moved = pose.tip.shift != (0.0, 0.0, 0.0)
        elapsed = index * FRAME
        if elapsed < contact_end - 1e-9:
            assert not moved  # trọng tâm còn chưa qua mép: khối chỉ lật tại chỗ
        elif elapsed > contact_end + FRAME:
            assert moved  # đã qua mép: khối trượt và rơi


def test_the_block_ends_far_below_the_tiles_and_keeps_falling() -> None:
    for kind in (FallKind.UNSUPPORTED, FallKind.PARTIAL):
        tips = [p.tip for p in poses(start(case_of(kind))) if p.tip is not None]
        heights = [t.shift[1] for t in tips]
        assert heights == sorted(heights, reverse=True) and heights[-1] < -4.0
        free_fall = (
            0.5 * GRAVITY * (TIP_SECONDS - TOPPLE_SECONDS) ** 2
        )  # sau 90 độ: rơi tự do thẳng xuống
        assert -heights[-1] > free_fall * 0.95


@pytest.mark.parametrize("kind", [FallKind.UNSUPPORTED, FallKind.PARTIAL])
def test_motion_is_continuous_between_phases(kind: FallKind) -> None:
    case = case_of(kind)
    points = sample_points(block_pieces(case.state)[active_piece(case.state)])
    sequence = poses(start(case))
    for before, after in itertools.pairwise(sequence):
        for p in points[:: max(1, len(points) // 6)]:
            a, b = transform_point(before, p), transform_point(after, p)
            assert math.dist(a, b) < 1.0, "khối nhảy vọt giữa hai khung"


def test_partial_tip_starts_exactly_where_the_roll_ended() -> None:
    case = case_of(FallKind.PARTIAL)
    animator = start(case)
    animator.update(ROLL_SECONDS - 1e-6)
    last_roll = animator.pose
    animator.update(2e-6)
    first_tip = animator.pose
    assert (
        last_roll is not None
        and first_tip is not None
        and last_roll.tip is None
        and first_tip.tip is not None
    )
    for p in sample_points(last_roll.bounds)[:8]:
        assert (
            math.dist(transform_point(last_roll, p), transform_point(first_tip, p))
            < 1e-3
        )


def test_transform_point_is_the_identity_when_nothing_moves() -> None:
    case = case_of(FallKind.UNSUPPORTED)
    pose = start(case).pose
    assert pose is not None
    p = (1.5, 0.5, 2.5)
    assert transform_point(pose, p) == pytest.approx(p)
    assert transform_point(Pose(0, pose.bounds, None, 0.0, -2.0), p) == (1.5, -1.5, 2.5)


def test_cancel_forgets_the_plan() -> None:
    animator = start(case_of(FallKind.PARTIAL))
    animator.cancel()
    assert (
        not animator.active and animator.pose is None and animator.phase == Phase.IDLE
    )
    assert len(FALLS) > 0 and isinstance(FALLS[0].state, State)


def test_only_the_sink_animation_is_clipped_below_the_ground() -> None:
    """Chỉ khi chìm xuống ô đích mới cắt phần khối nằm dưới mặt gạch (nếu không khối thò ra dưới đáy gạch dày)."""
    bounds = (0.0, 1.0, 0.0, 2.0, 0.0, 1.0)
    assert Pose(0, bounds, None, 0.0, -1.5).sinking
    assert not Pose(0, bounds, None, 0.0, 0.0).sinking  # chưa chìm
    assert not Pose(0, bounds, Direction.UP, 45.0, 0.0).sinking  # đang lăn
    assert not Pose(0, bounds, Direction.UP, 120.0, -3.0).sinking  # kiểu rơi cũ
    for kind in (FallKind.UNSUPPORTED, FallKind.PARTIAL):
        assert not any(p.sinking for p in poses(start(case_of(kind))))
