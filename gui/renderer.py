import math
import os
from typing import Dict, List, Tuple

from OpenGL.GL import (
    glClearColor, glClear, glLoadIdentity,
    glGenLists, glNewList, glEndList, glCallList, GL_COMPILE,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
)
from OpenGL.GLU import gluLookAt

from core.board import Board, TileType
from core.state import Orientation, State
from gui.primitives import draw_textured_box, load_texture

# Hộp bao (x0, x1, y0, y1, z0, z1): x = cột, y = chiều cao, z = hàng
Bounds = Tuple[float, float, float, float, float, float]

TILE_HEIGHT: float = 0.2

FOV_DEGREES: float = 45.0
CAMERA_ELEVATION: float = math.atan2(12, 8)   # góc nhìn chéo từ trên xuống, giữ như bản cũ
MIN_CAMERA_DISTANCE: float = 10.0
MAX_CAMERA_DISTANCE: float = 120.0
CAMERA_MARGIN: float = 0.95                   # chừa 5% mép khung
BLOCK_HEIGHT: float = 2.0

TEXTURE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "textures")
TEXTURE_NAMES: List[str] = [
    "floor", "floor_side", "block", "bridge", "fragile",
    "goal", "soft_switch", "heavy_switch", "split_switch",
]

# Loại ô -> hình dùng cho mặt trên
TOP_TEXTURE: Dict[TileType, str] = {
    TileType.FLOOR: "floor",
    TileType.FRAGILE: "fragile",
    TileType.GOAL: "goal",
    TileType.SOFT_SWITCH: "soft_switch",
    TileType.HEAVY_SWITCH: "heavy_switch",
    TileType.SPLIT_SWITCH: "split_switch",
}

# VOID là khoảng trống; BRIDGE vẽ riêng mỗi khung hình vì phụ thuộc state.active_bridges
SKIPPED_TILES: Tuple[TileType, ...] = (TileType.VOID, TileType.BRIDGE)


Vec = Tuple[float, float, float]


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalize(a: Vec) -> Vec:
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def content_bounds(board: Board) -> Tuple[float, float, float, float]:
    """(cột đầu, cột cuối + 1, hàng đầu, hàng cuối + 1) của vùng có ô thật, bỏ qua viền ô trống."""
    cells = [(r, c) for r in range(board.rows) for c in range(board.cols) if board.grid[r][c] != TileType.VOID]
    if not cells:
        return (0.0, float(board.cols), 0.0, float(board.rows))
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return (float(min(cols)), float(max(cols) + 1), float(min(rows)), float(max(rows) + 1))


def camera_eye(center_x: float, center_z: float, distance: float) -> Vec:
    return (center_x, distance * math.sin(CAMERA_ELEVATION), center_z + distance * math.cos(CAMERA_ELEVATION))


def fit_camera_distance(bounds: Tuple[float, float, float, float], aspect: float) -> float:
    """Khoảng cách camera nhỏ nhất để vùng có ô (kể cả khối cao 2) nằm trong khung nhìn."""
    c0, c1, r0, r1 = bounds
    center_x, center_z = (c0 + c1) / 2, (r0 + r1) / 2
    target: Vec = (center_x, 0.0, center_z)
    tan_half = math.tan(math.radians(FOV_DEGREES) / 2)
    corners = [(x, y, z) for x in (c0, c1) for z in (r0, r1) for y in (-TILE_HEIGHT, BLOCK_HEIGHT)]
    distance = MIN_CAMERA_DISTANCE
    while distance < MAX_CAMERA_DISTANCE:
        eye = camera_eye(center_x, center_z, distance)
        forward = _normalize((target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]))
        right = _normalize(_cross(forward, (0.0, 1.0, 0.0)))
        up = _cross(right, forward)
        fits = True
        for corner in corners:
            v = (corner[0] - eye[0], corner[1] - eye[1], corner[2] - eye[2])
            depth = _dot(v, forward)
            if abs(_dot(v, right) / depth / (tan_half * aspect)) > CAMERA_MARGIN or abs(_dot(v, up) / depth / tan_half) > CAMERA_MARGIN:
                fits = False
                break
        if fits:
            return distance
        distance += 0.25
    return MAX_CAMERA_DISTANCE


def tile_bounds(row: int, col: int) -> Bounds:
    return (col + 0.02, col + 0.98, -TILE_HEIGHT, 0.0, row + 0.02, row + 0.98)


def block_bounds(state: State) -> Bounds:
    """Hộp bao của khối, suy ra từ các ô mà core báo là khối đang chiếm."""
    cells = state.get_occupied_cells()
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    height = 2 if state.orientation == Orientation.STANDING else 1
    return (min(cs), max(cs) + 1, 0, height, min(rs), max(rs) + 1)


class Renderer:
    def __init__(self, board: Board, aspect: float = 4 / 3) -> None:
        self.board: Board = board
        bounds = content_bounds(board)
        self.camera_center: Tuple[float, float] = ((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2)
        self.camera_distance: float = fit_camera_distance(bounds, aspect)

        # Cần có cửa sổ OpenGL trước khi tải hình và tạo display list
        self.tex: Dict[str, int] = {
            name: load_texture(os.path.join(TEXTURE_DIR, name + ".png")) for name in TEXTURE_NAMES
        }
        self.bridge_cells: List[Tuple[int, int]] = [
            (r, c) for r in range(board.rows) for c in range(board.cols)
            if board.grid[r][c] == TileType.BRIDGE
        ]
        self.map_list: int = self._build_map_list()

    def _build_map_list(self) -> int:
        """Biên dịch nền bản đồ thành một display list, chỉ chạy một lần."""
        map_list = glGenLists(1)
        glNewList(map_list, GL_COMPILE)
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                tile = self.board.grid[r][c]
                if tile in SKIPPED_TILES:
                    continue
                top = self.tex[TOP_TEXTURE.get(tile, "floor")]
                draw_textured_box(tile_bounds(r, c), top, self.tex["floor_side"])
        glEndList()
        return map_list

    def _setup_camera(self) -> None:
        cx, cz = self.camera_center
        eye = camera_eye(cx, cz, self.camera_distance)
        glLoadIdentity()
        gluLookAt(
            *eye,            # camera nhìn chéo từ trên xuống, xa vừa đủ để thấy cả bản đồ
            cx, 0, cz,       # điểm nhìn: giữa bản đồ
            0, 1, 0,         # hướng "lên" là trục Y
        )

    def draw(self, state: State) -> None:
        glClearColor(0.08, 0.08, 0.12, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self._setup_camera()

        glCallList(self.map_list)

        self._draw_open_bridges(state)
        draw_textured_box(block_bounds(state), self.tex["block"], self.tex["block"])

    def _draw_open_bridges(self, state: State) -> None:
        for r, c in self.bridge_cells:
            if (r, c) in state.active_bridges:
                draw_textured_box(tile_bounds(r, c), self.tex["bridge"], self.tex["floor_side"])