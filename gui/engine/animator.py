"""Hoạt cảnh của khối: lăn, rơi, chìm xuống ô đích. Không chứa luật chơi, chỉ biến nước đi thành chuyển động."""

import math
from dataclasses import dataclass
from enum import Enum

from core.block import Direction
from core.state import State
from gui.shared.geometry import (
    FORWARD,
    ROLL_AXIS,
    Bounds,
    Cell,
    FallKind,
    FallPlan,
    Vec3,
    active_piece,
    block_pieces,
    roll_pivot,
    rotate_about,
)

ROLL_SECONDS: float = 0.25
FALL_SECONDS: float = 0.6
SINK_SECONDS: float = 0.6
TIP_SECONDS: float = 0.85  # tổng thời gian của chuyển động đổ rồi rơi
TOPPLE_SECONDS: float = 0.35  # thời gian để khối lật đủ 90 độ quanh mép (nhanh dần như vật đang đổ)
GRAVITY: float = 28.0  # gia tốc rơi, tính bằng ô trên giây bình phương

FALL_DROP: float = 8.0  # độ sâu rơi (đơn vị ô) khi hết pha rơi của ô giòn
FALL_EXTRA_ANGLE: float = 60.0  # góc xoay thêm khi khối rơi ra khỏi mép (kiểu rơi cũ)
SINK_DEPTH: float = 2.4  # khối chìm sâu hơn chiều cao của nó nên bị ô đích che hẳn
TILE_TILT: float = 35.0  # ô giòn vỡ nghiêng thêm ngần này độ khi rơi
TILE_LEAD: float = 0.2  # ô giòn rơi trước: khối còn đứng yên trong 20% đầu của pha rơi


class Phase(Enum):
    """Giai đoạn của hoạt cảnh."""

    IDLE = "IDLE"
    ROLL = "ROLL"
    FALL = "FALL"
    SINK = "SINK"
    TIP = "TIP"  # đổ quanh mép rồi rơi (khối không còn được đỡ đầy đủ)


@dataclass(frozen=True)
class TilePose:
    """Cách vẽ một ô đang rơi cùng khối (ô giòn bị vỡ)."""

    cell: Cell
    drop: float  # dời theo trục y (không dương)
    axis: Vec3  # trục nghiêng, quanh tâm ô
    degrees: float


@dataclass(frozen=True)
class Tip:
    """Phép đổ quanh mép: quay `degrees` quanh đường mép qua `pivot`, rồi dời `shift` (trượt dọc mặt đáy và rơi)."""

    pivot: Vec3
    axis: Vec3
    degrees: float  # đã kèm dấu
    shift: Vec3


@dataclass(frozen=True)
class Pose:
    """Cách vẽ mảnh khối đang chuyển động: lăn (nếu có), đổ quanh mép (nếu có), rồi dời theo trục y."""

    piece: int  # chỉ số mảnh trong block_pieces(display_state)
    bounds: Bounds  # hộp bao của mảnh trước khi chuyển động
    direction: Direction | None
    angle: float  # độ xoay quanh cạnh đáy theo hướng lăn
    drop: float  # dời theo trục y (không dương)
    tile: TilePose | None = None
    tip: Tip | None = None

    @property
    def sinking(self) -> bool:
        """Đang chìm xuống ô đích (không lăn, không đổ, chỉ dời xuống): phần khối dưới mặt gạch phải bị cắt bỏ."""
        return self.direction is None and self.tip is None and self.tile is None and self.drop < 0


def ease_in_out(t: float) -> float:
    """Làm mượt tiến độ t (0 đến 1): chậm ở hai đầu, nhanh ở giữa."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def transform_point(pose: Pose, point: Vec3) -> Vec3:
    """Vị trí của một điểm thuộc khối (tọa độ lúc đứng yên) sau khi áp dụng `pose`.

    Thứ tự y hệt lúc vẽ: lăn, rồi đổ quanh mép, rồi dời theo trục y; dùng cho kiểm thử va chạm.
    """
    moved = point
    if pose.direction is not None and pose.angle != 0.0:
        px, pz, axis, sign = roll_pivot(pose.bounds, pose.direction)
        moved = rotate_about(moved, (px, 0.0, pz), axis, sign * pose.angle)
    if pose.tip is not None:
        moved = rotate_about(moved, pose.tip.pivot, pose.tip.axis, pose.tip.degrees)
        moved = (
            moved[0] + pose.tip.shift[0],
            moved[1] + pose.tip.shift[1],
            moved[2] + pose.tip.shift[2],
        )
    return (moved[0], moved[1] + pose.drop, moved[2])


class Animator:
    """Không chứa luật chơi: chỉ biến một nước đi đã xảy ra thành chuyển động theo thời gian."""

    def __init__(
        self,
        roll_seconds: float = ROLL_SECONDS,
        fall_seconds: float = FALL_SECONDS,
        sink_seconds: float = SINK_SECONDS,
        tip_seconds: float = TIP_SECONDS,
    ) -> None:
        """Đặt thời lượng (giây) của từng giai đoạn."""
        self.roll_seconds: float = roll_seconds
        self.fall_seconds: float = fall_seconds
        self.sink_seconds: float = sink_seconds
        self.tip_seconds: float = tip_seconds
        self._phases: list[Phase] = []
        self._elapsed: float = 0.0
        self._direction: Direction | None = None
        self._old_state: State | None = None
        self._new_state: State | None = None
        self._broken_tile: Cell | None = None
        self._plan: FallPlan | None = None

    @property
    def active(self) -> bool:
        """Còn hoạt cảnh đang chạy không."""
        return bool(self._phases)

    @property
    def phase(self) -> Phase:
        """Giai đoạn hiện tại (IDLE nếu không có hoạt cảnh)."""
        return self._phases[0] if self._phases else Phase.IDLE

    @property
    def broken_tile(self) -> Cell | None:
        """Ô giòn sẽ vỡ ở pha rơi của hoạt cảnh đang chạy (None nếu không có)."""
        return self._broken_tile if self.active else None

    def start_roll(self, old_state: State, direction: Direction, new_state: State) -> None:
        """Bắt đầu hoạt cảnh lăn từ `old_state` sang `new_state`."""
        self._start([Phase.ROLL], old_state, direction, new_state, None)

    def start_fall(
        self,
        old_state: State,
        direction: Direction,
        broken_tile: Cell | None = None,
        plan: FallPlan | None = None,
    ) -> None:
        """Bắt đầu hoạt cảnh rơi.

        - `broken_tile`: khối đứng trên ô giòn; ô vỡ và rơi cùng khối.
        - `plan` (từ `plan_fall`): khối đổ quanh mép rồi rơi, không xuyên qua gạch đỡ nó.
        - Không có cả hai: kiểu cũ, lăn trọn rồi rơi thẳng.
        """
        if broken_tile is None and plan is not None:
            phases = [Phase.ROLL, Phase.TIP] if plan.kind == FallKind.PARTIAL else [Phase.TIP]
            self._start(phases, old_state, direction, old_state, None, plan)
        else:
            self._start([Phase.ROLL, Phase.FALL], old_state, direction, old_state, broken_tile)

    def start_win(self, old_state: State, direction: Direction, new_state: State) -> None:
        """Bắt đầu hoạt cảnh lăn rồi chìm xuống ô đích."""
        self._start([Phase.ROLL, Phase.SINK], old_state, direction, new_state, None)

    def cancel(self) -> None:
        """Dừng hoạt cảnh ngay lập tức."""
        self._phases = []
        self._elapsed = 0.0
        self._broken_tile = None
        self._plan = None

    def _start(
        self,
        phases: list[Phase],
        old_state: State,
        direction: Direction,
        new_state: State,
        broken_tile: Cell | None,
        plan: FallPlan | None = None,
    ) -> None:
        """Đặt lại bộ đếm và ghi nhớ mọi thứ cần cho hoạt cảnh mới."""
        self._phases = list(phases)
        self._elapsed = 0.0
        self._direction = direction
        self._old_state = old_state
        self._new_state = new_state
        self._broken_tile = broken_tile
        self._plan = plan

    def _duration(self, phase: Phase) -> float:
        """Thời lượng (giây) của một giai đoạn."""
        return {
            Phase.ROLL: self.roll_seconds,
            Phase.FALL: self.fall_seconds,
            Phase.SINK: self.sink_seconds,
            Phase.TIP: self.tip_seconds,
        }[phase]

    def update(self, dt: float) -> bool:
        """Tiến thời gian. Trả về True đúng ở lần gọi làm hoạt cảnh kết thúc."""
        if not self._phases or dt <= 0:
            return False
        remaining = dt
        while self._phases and remaining > 0:
            need = self._duration(self._phases[0]) - self._elapsed
            if remaining >= need:
                remaining -= need
                self._phases.pop(0)
                self._elapsed = 0.0
            else:
                self._elapsed += remaining
                remaining = 0.0
        return not self._phases

    @property
    def display_state(self) -> State | None:
        """Trạng thái dùng để vẽ nền, cầu và mảnh khối đứng yên trong lúc chuyển động."""
        if not self.active:
            return None
        return self._new_state if self.phase == Phase.SINK else self._old_state

    def _tip_pose(self, piece: int, bounds: Bounds) -> Pose:
        """Tư thế khi đổ quanh mép: lật 0 đến 90 độ, trượt dọc mặt đáy cũ từ lúc trọng tâm qua mép, rồi rơi thẳng.

        Mặt đáy cũ đi qua cạnh xoay nên gạch phía sau cạnh luôn nằm dưới mặt phẳng đó còn khối nằm trên nó:
        khối không thể xuyên qua gạch đỡ nó. Sau 90 độ mặt phẳng thẳng đứng nên trượt thành rơi thẳng.
        """
        plan = self._plan
        if plan is None:
            raise RuntimeError("Giai đoạn TIP cần có FallPlan.")
        t = self._elapsed
        degrees = 90.0 * min(1.0, (t / TOPPLE_SECONDS) ** 2)
        contact_end = TOPPLE_SECONDS * math.sqrt(plan.critical_degrees / 90.0)
        slide = 0.5 * GRAVITY * max(0.0, t - contact_end) ** 2
        radians = math.radians(degrees)
        forward = FORWARD[plan.tip_direction]
        shift: Vec3 = (
            forward[0] * math.cos(radians) * slide,
            -math.sin(radians) * slide,
            forward[2] * math.cos(radians) * slide,
        )
        axis, sign = ROLL_AXIS[plan.tip_direction]
        tip = Tip(plan.pivot, axis, sign * degrees, shift)
        if plan.kind == FallKind.PARTIAL:
            return Pose(piece, bounds, self._direction, 90.0, 0.0, tip=tip)  # đã lăn trọn 90 độ rồi mới bập bênh
        return Pose(piece, bounds, None, 0.0, 0.0, tip=tip)

    @property
    def pose(self) -> Pose | None:
        """Tư thế của mảnh khối đang chuyển động (None nếu không có hoạt cảnh)."""
        if not self.active or self._old_state is None or self._new_state is None:
            return None
        phase = self.phase
        progress = self._elapsed / self._duration(phase)
        if phase == Phase.SINK:
            piece = active_piece(self._new_state)
            bounds = block_pieces(self._new_state)[piece]
            return Pose(piece, bounds, None, 0.0, -SINK_DEPTH * ease_in_out(progress))
        piece = active_piece(self._old_state)
        bounds = block_pieces(self._old_state)[piece]
        if phase == Phase.TIP:
            return self._tip_pose(piece, bounds)
        if phase == Phase.ROLL:
            return Pose(piece, bounds, self._direction, 90.0 * ease_in_out(progress), 0.0)

        u = min(1.0, progress)
        if self._broken_tile is not None and self._direction is not None:
            # Ô giòn vỡ trước và rơi, nghiêng dần; khối đứng trên chỗ trống một nhịp rồi rơi thẳng theo
            axis, sign = ROLL_AXIS[self._direction]
            block_u = max(0.0, (u - TILE_LEAD) / (1.0 - TILE_LEAD))
            tile = TilePose(self._broken_tile, -FALL_DROP * u * u, axis, sign * TILE_TILT * u)
            return Pose(
                piece,
                bounds,
                self._direction,
                90.0,
                -FALL_DROP * block_u * block_u,
                tile,
            )
        return Pose(
            piece,
            bounds,
            self._direction,
            90.0 + FALL_EXTRA_ANGLE * u,
            -FALL_DROP * u * u,
        )
