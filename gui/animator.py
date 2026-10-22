from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from core.block import Direction
from core.state import State
from gui.geometry import ROLL_AXIS, Bounds, Cell, Vec3, active_piece, block_pieces

ROLL_SECONDS: float = 0.25
FALL_SECONDS: float = 0.6
SINK_SECONDS: float = 0.6

FALL_DROP: float = 8.0          # độ sâu rơi (đơn vị ô) khi hết pha rơi
FALL_EXTRA_ANGLE: float = 60.0  # góc xoay thêm khi khối rơi ra khỏi mép
SINK_DEPTH: float = 2.4         # khối chìm sâu hơn chiều cao của nó nên bị ô đích che hẳn
TILE_TILT: float = 35.0         # ô giòn vỡ nghiêng thêm ngần này độ khi rơi
TILE_LEAD: float = 0.2          # ô giòn rơi trước: khối còn đứng yên trong 20% đầu của pha rơi


class Phase(Enum):
    IDLE = "IDLE"
    ROLL = "ROLL"
    FALL = "FALL"
    SINK = "SINK"


@dataclass(frozen=True)
class TilePose:
    """Cách vẽ một ô đang rơi cùng khối (ô giòn bị vỡ)."""
    cell: Cell
    drop: float                  # dời theo trục y (không dương)
    axis: Vec3                   # trục nghiêng, quanh tâm ô
    degrees: float


@dataclass(frozen=True)
class Pose:
    """Cách vẽ mảnh khối đang chuyển động."""
    piece: int                   # chỉ số mảnh trong block_pieces(display_state)
    bounds: Bounds               # hộp bao của mảnh trước khi chuyển động
    direction: Optional[Direction]
    angle: float                 # độ xoay quanh cạnh đáy theo hướng lăn
    drop: float                  # dời theo trục y (không dương)
    tile: Optional[TilePose] = None


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Animator:
    """Không chứa luật chơi: chỉ biến một nước đi đã xảy ra thành chuyển động theo thời gian."""

    def __init__(
        self,
        roll_seconds: float = ROLL_SECONDS,
        fall_seconds: float = FALL_SECONDS,
        sink_seconds: float = SINK_SECONDS,
    ) -> None:
        self.roll_seconds: float = roll_seconds
        self.fall_seconds: float = fall_seconds
        self.sink_seconds: float = sink_seconds
        self._phases: List[Phase] = []
        self._elapsed: float = 0.0
        self._direction: Optional[Direction] = None
        self._old_state: Optional[State] = None
        self._new_state: Optional[State] = None
        self._broken_tile: Optional[Cell] = None

    @property
    def active(self) -> bool:
        return bool(self._phases)

    @property
    def phase(self) -> Phase:
        return self._phases[0] if self._phases else Phase.IDLE

    @property
    def broken_tile(self) -> Optional[Cell]:
        """Ô giòn sẽ vỡ ở pha rơi của hoạt cảnh đang chạy (None nếu không có)."""
        return self._broken_tile if self.active else None

    def start_roll(self, old_state: State, direction: Direction, new_state: State) -> None:
        self._start([Phase.ROLL], old_state, direction, new_state, None)

    def start_fall(self, old_state: State, direction: Direction, broken_tile: Optional[Cell] = None) -> None:
        """Lăn rồi rơi. Nếu `broken_tile` có giá trị: khối đứng trên ô giòn, ô vỡ và rơi cùng khối."""
        self._start([Phase.ROLL, Phase.FALL], old_state, direction, old_state, broken_tile)

    def start_win(self, old_state: State, direction: Direction, new_state: State) -> None:
        self._start([Phase.ROLL, Phase.SINK], old_state, direction, new_state, None)

    def cancel(self) -> None:
        self._phases = []
        self._elapsed = 0.0
        self._broken_tile = None

    def _start(
        self,
        phases: List[Phase],
        old_state: State,
        direction: Direction,
        new_state: State,
        broken_tile: Optional[Cell],
    ) -> None:
        self._phases = list(phases)
        self._elapsed = 0.0
        self._direction = direction
        self._old_state = old_state
        self._new_state = new_state
        self._broken_tile = broken_tile

    def _duration(self, phase: Phase) -> float:
        return {Phase.ROLL: self.roll_seconds, Phase.FALL: self.fall_seconds, Phase.SINK: self.sink_seconds}[phase]

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
    def display_state(self) -> Optional[State]:
        """Trạng thái dùng để vẽ nền, cầu và mảnh khối đứng yên trong lúc chuyển động."""
        if not self.active:
            return None
        return self._new_state if self.phase == Phase.SINK else self._old_state

    @property
    def pose(self) -> Optional[Pose]:
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
        if phase == Phase.ROLL:
            return Pose(piece, bounds, self._direction, 90.0 * ease_in_out(progress), 0.0)

        u = min(1.0, progress)
        if self._broken_tile is not None and self._direction is not None:
            # Ô giòn vỡ trước và rơi, nghiêng dần; khối đứng trên chỗ trống một nhịp rồi rơi thẳng theo
            axis, sign = ROLL_AXIS[self._direction]
            block_u = max(0.0, (u - TILE_LEAD) / (1.0 - TILE_LEAD))
            tile = TilePose(self._broken_tile, -FALL_DROP * u * u, axis, sign * TILE_TILT * u)
            return Pose(piece, bounds, self._direction, 90.0, -FALL_DROP * block_u * block_u, tile)
        return Pose(piece, bounds, self._direction, 90.0 + FALL_EXTRA_ANGLE * u, -FALL_DROP * u * u)