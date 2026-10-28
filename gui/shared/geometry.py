"""Hình học dùng chung cho cảnh 3D: hộp bao, trục lăn, độ sáng các mặt và kế hoạch rơi khỏi gạch.

Quy ước tọa độ: x = cột, y = chiều cao, z = hàng; mặt trên của gạch ở y = 0 còn gạch kéo xuống tới -TILE_HEIGHT.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from core.block import Direction
from core.board import Board, TileType
from core.state import Orientation, State
from core.transition import roll_block

# Hộp bao (x0, x1, y0, y1, z0, z1): x = cột, y = chiều cao, z = hàng
Bounds = tuple[float, float, float, float, float, float]
Vec3 = tuple[float, float, float]
Cell = tuple[int, int]

TILE_HEIGHT: float = (
    1.0  # độ dày của gạch (nguồn duy nhất: mọi nơi khác đọc hằng số này)
)
TILE_INSET: float = 0.02  # gạch nhỏ hơn ô một chút mỗi bên để lộ khe giữa các gạch

# Pháp tuyến của sáu mặt hộp, trong hệ tọa độ của chính hộp
FACE_NORMALS: dict[str, Vec3] = {
    "top": (0.0, 1.0, 0.0),
    "bottom": (0.0, -1.0, 0.0),
    "front": (0.0, 0.0, 1.0),
    "back": (0.0, 0.0, -1.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}

# Độ sáng của mặt khi hộp đứng yên (mặt hướng lên sáng nhất, hướng xuống tối nhất)
DEFAULT_FACE_SHADE: dict[str, float] = {
    "top": 1.0,
    "front": 0.85,
    "back": 0.85,
    "left": 0.7,
    "right": 0.7,
    "bottom": 0.5,
}

# Trục quay và dấu của góc khi lăn theo từng hướng (glRotatef quay ngược chiều kim đồng hồ)
ROLL_AXIS: dict[Direction, tuple[Vec3, int]] = {
    Direction.RIGHT: ((0.0, 0.0, 1.0), -1),
    Direction.LEFT: ((0.0, 0.0, 1.0), 1),
    Direction.DOWN: ((1.0, 0.0, 0.0), 1),
    Direction.UP: ((1.0, 0.0, 0.0), -1),
}

# Vector đơn vị nằm ngang theo hướng di chuyển
FORWARD: dict[Direction, Vec3] = {
    Direction.RIGHT: (1.0, 0.0, 0.0),
    Direction.LEFT: (-1.0, 0.0, 0.0),
    Direction.DOWN: (0.0, 0.0, 1.0),
    Direction.UP: (0.0, 0.0, -1.0),
}


def block_bounds(state: State) -> Bounds:
    """Hộp bao của khối nguyên, suy ra từ các ô mà core báo là khối đang chiếm."""
    cells = state.get_occupied_cells()
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    height = 2 if state.orientation == Orientation.STANDING else 1
    return (min(cs), max(cs) + 1, 0, height, min(rs), max(rs) + 1)


def cube_bounds(row: int, col: int) -> Bounds:
    """Hộp bao của một khối đơn (cạnh 1) ở ô (row, col)."""
    return (col, col + 1, 0, 1, row, row + 1)


def tile_bounds(row: int, col: int, height: float | None = None) -> Bounds:
    """Hộp bao của gạch ở ô (row, col): mặt trên ở y = 0, dày `height` (mặc định TILE_HEIGHT)."""
    thickness = TILE_HEIGHT if height is None else height
    return (
        col + TILE_INSET,
        col + 1 - TILE_INSET,
        -thickness,
        0.0,
        row + TILE_INSET,
        row + 1 - TILE_INSET,
    )


def block_pieces(state: State) -> list[Bounds]:
    """Các mảnh cần vẽ: một khối nguyên, hoặc hai khối đơn khi đang tách."""
    if state.is_split() and state.split_pos is not None:
        return [cube_bounds(state.r, state.c), cube_bounds(*state.split_pos)]
    return [block_bounds(state)]


def active_piece(state: State) -> int:
    """Chỉ số mảnh đang được điều khiển trong block_pieces(state)."""
    return state.active_cube if state.is_split() else 0


def roll_pivot(bounds: Bounds, direction: Direction) -> tuple[float, float, Vec3, int]:
    """(x, z của điểm xoay, trục quay, dấu của góc) khi lăn theo `direction`.

    Xoay 90 độ quanh cạnh đáy phía hướng lăn thì khối trùng đúng vị trí mới.
    """
    x0, x1, _, _, z0, z1 = bounds
    axis, sign = ROLL_AXIS[direction]
    px, pz = {
        Direction.RIGHT: (x1, 0.0),
        Direction.LEFT: (x0, 0.0),
        Direction.DOWN: (0.0, z1),
        Direction.UP: (0.0, z0),
    }[direction]
    return (px, pz, axis, sign)


def rotate_vector(vector: Vec3, axis: Vec3, degrees: float) -> Vec3:
    """Quay `vector` quanh trục đơn vị `axis` theo quy tắc bàn tay phải (giống glRotatef)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    x, y, z = vector
    dot = axis[0] * x + axis[1] * y + axis[2] * z
    cross = (
        axis[1] * z - axis[2] * y,
        axis[2] * x - axis[0] * z,
        axis[0] * y - axis[1] * x,
    )
    return (
        x * c + cross[0] * s + axis[0] * dot * (1 - c),
        y * c + cross[1] * s + axis[1] * dot * (1 - c),
        z * c + cross[2] * s + axis[2] * dot * (1 - c),
    )


def rotate_about(point: Vec3, pivot: Vec3, axis: Vec3, degrees: float) -> Vec3:
    """Quay `point` quanh đường thẳng đi qua `pivot` theo hướng `axis` (đơn vị) một góc `degrees`."""
    offset = (point[0] - pivot[0], point[1] - pivot[1], point[2] - pivot[2])
    rx, ry, rz = rotate_vector(offset, axis, degrees)
    return (pivot[0] + rx, pivot[1] + ry, pivot[2] + rz)


def shade_for_normal(normal: Vec3, base: dict[str, float]) -> float:
    """Độ sáng theo hướng pháp tuyến, liên tục theo hướng.

    Tại sáu hướng trục, kết quả đúng bằng bảng `base`; ở giữa thì nội suy theo bình phương
    thành phần, nên khối xoay thì độ sáng đổi từ từ, không nhảy.
    """
    nx, ny, nz = normal
    weight_x = base["right"] if nx >= 0 else base["left"]
    weight_y = base["top"] if ny >= 0 else base["bottom"]
    weight_z = base["front"] if nz >= 0 else base["back"]
    return weight_x * nx * nx + weight_y * ny * ny + weight_z * nz * nz


def composed_face_shades(
    base: dict[str, float], rotations: Sequence[tuple[Vec3, float]]
) -> dict[str, float]:
    """Độ sáng các mặt của hộp sau một chuỗi phép quay (trục, độ) áp dụng lần lượt theo thứ tự."""
    if not rotations:
        return dict(base)
    shades: dict[str, float] = {}
    for name, normal in FACE_NORMALS.items():
        current = normal
        for axis, degrees in rotations:
            current = rotate_vector(current, axis, degrees)
        shades[name] = shade_for_normal(current, base)
    return shades


def rotated_face_shades(
    base: dict[str, float], axis: Vec3, degrees: float
) -> dict[str, float]:
    """Độ sáng của từng mặt khi hộp đã xoay `degrees` độ quanh `axis`."""
    if degrees == 0:
        return dict(base)
    return composed_face_shades(base, [(axis, degrees)])


def roll_face_shades(
    base: dict[str, float], direction: Direction, angle: float
) -> dict[str, float]:
    """Độ sáng các mặt của khối đang lăn theo `direction`, đã xoay `angle` độ (0 đến 90 hoặc hơn)."""
    axis, sign = ROLL_AXIS[direction]
    return rotated_face_shades(base, axis, sign * angle)


def broken_fragile_cell(board: Board, state: State) -> Cell | None:
    """Ô giòn bị vỡ nếu `state` (trạng thái khối vừa rơi) là khối đứng thẳng trên ô giòn."""
    if state.orientation != Orientation.STANDING:
        return None
    if (
        board.in_board(state.r, state.c)
        and board.get_tile(state.r, state.c) == TileType.FRAGILE
    ):
        return (state.r, state.c)
    return None


# ---------------------------------------------------------------------- kế hoạch rơi


class FallKind(Enum):
    """Cách khối rơi khỏi gạch."""

    UNSUPPORTED = "UNSUPPORTED"  # lăn ra khỏi mép: không còn ô nào đỡ, khối đổ quanh chính cạnh đang lăn
    PARTIAL = (
        "PARTIAL"  # lăn xong nhưng chỉ nằm trên một ô: khối bập bênh quanh mép ô đỡ nó
    )


@dataclass(frozen=True)
class FallPlan:
    """Cách dựng hoạt cảnh rơi (tính từ bản đồ, không phụ thuộc thời gian)."""

    kind: FallKind
    tip_direction: Direction  # hướng khối đổ
    pivot: Vec3  # một điểm trên đường mép làm trục xoay (y = 0)
    critical_degrees: float  # góc lật mà từ đó trọng tâm đã qua mép và khối bắt đầu rơi


def supports_block(board: Board, state: State, cell: Cell) -> bool:
    """Ô `cell` có gạch đỡ được khối không (ngoài bản đồ, ô trống và cầu đang đóng thì không)."""
    row, col = cell
    if not board.in_board(row, col):
        return False
    tile = board.get_tile(row, col)
    if tile == TileType.VOID:
        return False
    if tile == TileType.BRIDGE:
        return cell in state.active_bridges
    return True


def _edge_pivot(supported: Cell, direction: Direction) -> Vec3:
    """Điểm trên mép của ô `supported` về phía `direction` (đường mép nằm ở y = 0)."""
    row, col = supported
    return {
        Direction.RIGHT: (col + 1.0, 0.0, 0.0),
        Direction.LEFT: (float(col), 0.0, 0.0),
        Direction.DOWN: (0.0, 0.0, row + 1.0),
        Direction.UP: (0.0, 0.0, float(row)),
    }[direction]


def plan_fall(board: Board, state: State, direction: Direction) -> FallPlan | None:
    """Phân loại cú rơi khi khối ở `state` lăn theo `direction`; None nếu không phải kiểu rơi cần dựng riêng.

    - Khối chỉ chiếm ô giòn: None (ô giòn vỡ và rơi cùng khối, đã có hoạt cảnh riêng).
    - Không ô nào đỡ: UNSUPPORTED, trục xoay là cạnh đang lăn.
    - Hai ô mà chỉ một ô đỡ: PARTIAL, trục xoay là mép giữa ô đỡ và ô trống.
    """
    rolled = roll_block(state, direction)
    cells = (
        [rolled.get_active_cube_pos()]
        if state.is_split()
        else rolled.get_occupied_cells()
    )
    supported = [supports_block(board, state, cell) for cell in cells]
    if (
        not state.is_split()
        and rolled.orientation == Orientation.STANDING
        and supported[0]
        and board.get_tile(*cells[0]) == TileType.FRAGILE
    ):
        return None
    count = sum(supported)
    if count == 0:
        x0, x1, y0, y1, z0, z1 = block_pieces(state)[active_piece(state)]
        extent = (
            (x1 - x0) if direction in (Direction.LEFT, Direction.RIGHT) else (z1 - z0)
        )
        critical = math.degrees(
            math.atan2(extent / 2, (y1 - y0) / 2)
        )  # trọng tâm qua mép khi tan = (nửa bề ngang)/(độ cao trọng tâm)
        px, pz, _, _ = roll_pivot(block_pieces(state)[active_piece(state)], direction)
        return FallPlan(FallKind.UNSUPPORTED, direction, (px, 0.0, pz), critical)
    if count == 1 and len(cells) == 2 and not state.is_split():
        holding = cells[supported.index(True)]
        empty = cells[supported.index(False)]
        tip = {
            (0, 1): Direction.RIGHT,
            (0, -1): Direction.LEFT,
            (1, 0): Direction.DOWN,
            (-1, 0): Direction.UP,
        }[(empty[0] - holding[0], empty[1] - holding[1])]
        return FallPlan(
            FallKind.PARTIAL, tip, _edge_pivot(holding, tip), 0.0
        )  # nằm vắt qua mép: trọng tâm ngay trên mép
    return None
