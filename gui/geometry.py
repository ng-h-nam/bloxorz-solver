import math
from typing import Dict, List, Optional, Tuple

from core.block import Direction
from core.board import Board, TileType
from core.state import Orientation, State

# Hộp bao (x0, x1, y0, y1, z0, z1): x = cột, y = chiều cao, z = hàng
Bounds = Tuple[float, float, float, float, float, float]
Vec3 = Tuple[float, float, float]
Cell = Tuple[int, int]

# Pháp tuyến của sáu mặt hộp, trong hệ tọa độ của chính hộp
FACE_NORMALS: Dict[str, Vec3] = {
    "top": (0.0, 1.0, 0.0),
    "bottom": (0.0, -1.0, 0.0),
    "front": (0.0, 0.0, 1.0),
    "back": (0.0, 0.0, -1.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}

# Độ sáng của mặt khi hộp đứng yên (mặt hướng lên sáng nhất, hướng xuống tối nhất)
DEFAULT_FACE_SHADE: Dict[str, float] = {
    "top": 1.0, "front": 0.85, "back": 0.85, "left": 0.7, "right": 0.7, "bottom": 0.5,
}

# Trục quay và dấu của góc khi lăn theo từng hướng (glRotatef quay ngược chiều kim đồng hồ)
ROLL_AXIS: Dict[Direction, Tuple[Vec3, int]] = {
    Direction.RIGHT: ((0.0, 0.0, 1.0), -1),
    Direction.LEFT: ((0.0, 0.0, 1.0), 1),
    Direction.DOWN: ((1.0, 0.0, 0.0), 1),
    Direction.UP: ((1.0, 0.0, 0.0), -1),
}


def block_bounds(state: State) -> Bounds:
    """Hộp bao của khối nguyên, suy ra từ các ô mà core báo là khối đang chiếm."""
    cells = state.get_occupied_cells()
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    height = 2 if state.orientation == Orientation.STANDING else 1
    return (min(cs), max(cs) + 1, 0, height, min(rs), max(rs) + 1)


def cube_bounds(row: int, col: int) -> Bounds:
    return (col, col + 1, 0, 1, row, row + 1)


def block_pieces(state: State) -> List[Bounds]:
    """Các mảnh cần vẽ: một khối nguyên, hoặc hai khối đơn khi đang tách."""
    if state.is_split() and state.split_pos is not None:
        return [cube_bounds(state.r, state.c), cube_bounds(*state.split_pos)]
    return [block_bounds(state)]


def active_piece(state: State) -> int:
    """Chỉ số mảnh đang được điều khiển trong block_pieces(state)."""
    return state.active_cube if state.is_split() else 0


def roll_pivot(bounds: Bounds, direction: Direction) -> Tuple[float, float, Vec3, int]:
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
    cross = (axis[1] * z - axis[2] * y, axis[2] * x - axis[0] * z, axis[0] * y - axis[1] * x)
    return (
        x * c + cross[0] * s + axis[0] * dot * (1 - c),
        y * c + cross[1] * s + axis[1] * dot * (1 - c),
        z * c + cross[2] * s + axis[2] * dot * (1 - c),
    )


def shade_for_normal(normal: Vec3, base: Dict[str, float]) -> float:
    """Độ sáng theo hướng pháp tuyến, liên tục theo hướng.

    Tại sáu hướng trục, kết quả đúng bằng bảng `base`; ở giữa thì nội suy theo bình phương
    thành phần, nên khối xoay thì độ sáng đổi từ từ, không nhảy.
    """
    nx, ny, nz = normal
    weight_x = base["right"] if nx >= 0 else base["left"]
    weight_y = base["top"] if ny >= 0 else base["bottom"]
    weight_z = base["front"] if nz >= 0 else base["back"]
    return weight_x * nx * nx + weight_y * ny * ny + weight_z * nz * nz


def rotated_face_shades(base: Dict[str, float], axis: Vec3, degrees: float) -> Dict[str, float]:
    """Độ sáng của từng mặt khi hộp đã xoay `degrees` độ quanh `axis`."""
    if degrees == 0:
        return dict(base)
    return {
        name: shade_for_normal(rotate_vector(normal, axis, degrees), base)
        for name, normal in FACE_NORMALS.items()
    }


def roll_face_shades(base: Dict[str, float], direction: Direction, angle: float) -> Dict[str, float]:
    """Độ sáng các mặt của khối đang lăn theo `direction`, đã xoay `angle` độ (0 đến 90 hoặc hơn)."""
    axis, sign = ROLL_AXIS[direction]
    return rotated_face_shades(base, axis, sign * angle)


def broken_fragile_cell(board: Board, state: State) -> Optional[Cell]:
    """Ô giòn bị vỡ nếu `state` (trạng thái khối vừa rơi) là khối đứng thẳng trên ô giòn."""
    if state.orientation != Orientation.STANDING:
        return None
    if board.in_board(state.r, state.c) and board.get_tile(state.r, state.c) == TileType.FRAGILE:
        return (state.r, state.c)
    return None