from typing import Dict, Tuple

from OpenGL.GL import (
    glBegin, glEnd, glColor3f, glVertex3f, GL_QUADS,
    glClearColor, glClear, glLoadIdentity,
    glGenLists, glNewList, glEndList, glCallList, GL_COMPILE,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
)
from OpenGL.GLU import gluLookAt

from core.board import Board, TileType
from core.state import Orientation, State

# Màu RGB, mỗi kênh trong [0, 1]
Color = Tuple[float, float, float]
# Hộp bao (x0, x1, y0, y1, z0, z1): x = cột, y = chiều cao, z = hàng
Bounds = Tuple[int, int, int, int, int, int]

TILE_HEIGHT: float = 0.2

TILE_COLORS: Dict[TileType, Color] = {
    TileType.FLOOR: (0.85, 0.85, 0.75),
    TileType.GOAL: (0.3, 0.9, 0.4),
    TileType.FRAGILE: (0.9, 0.6, 0.4),
    TileType.SOFT_SWITCH: (0.6, 0.6, 0.9),
    TileType.HEAVY_SWITCH: (0.9, 0.4, 0.8),
}
BRIDGE_COLOR: Color = (0.5, 0.5, 0.95)
BLOCK_COLOR: Color = (0.95, 0.55, 0.1)

# VOID là khoảng trống; BRIDGE chỉ vẽ khi đang mở (lấy từ state.active_bridges)
SKIPPED_TILES: Tuple[TileType, ...] = (TileType.VOID, TileType.BRIDGE)


def draw_box(
    x0: float, x1: float,
    y0: float, y1: float,
    z0: float, z1: float,
    color: Color,
) -> None:
    """Vẽ một hộp chữ nhật với 6 mặt, mỗi mặt là một quad."""
    glColor3f(*color)
    glBegin(GL_QUADS)
    faces = [
        ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)),  # trên
        ((x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)),  # dưới
        ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)),  # trước
        ((x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1)),  # sau
        ((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)),  # trái
        ((x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)),  # phải
    ]
    for face in faces:
        for x, y, z in face:
            glVertex3f(x, y, z)
    glEnd()


def block_bounds(state: State) -> Bounds:
    """Hộp bao của khối, suy ra từ các ô mà core báo là khối đang chiếm."""
    cells = state.get_occupied_cells()
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    height = 2 if state.orientation == Orientation.STANDING else 1
    return (min(cs), max(cs) + 1, 0, height, min(rs), max(rs) + 1)


class Renderer:
    def __init__(self, board: Board) -> None:
        self.board: Board = board
        # Gọi sau khi đã tạo cửa sổ OpenGL, vì display list cần context
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
                color = TILE_COLORS.get(tile, (0.7, 0.7, 0.7))
                draw_box(c, c + 1, -TILE_HEIGHT, 0, r, r + 1, color)
        glEndList()
        return map_list

    def _setup_camera(self) -> None:
        cx = self.board.cols / 2
        cz = self.board.rows / 2
        glLoadIdentity()
        gluLookAt(
            cx, 12, cz + 8,  # camera nhìn chéo từ trên xuống
            cx, 0, cz,       # điểm nhìn: giữa bản đồ
            0, 1, 0,         # hướng "lên" là trục Y
        )

    def draw(self, state: State) -> None:
        glClearColor(0.08, 0.08, 0.12, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self._setup_camera()

        glCallList(self.map_list)

        for r, c in state.active_bridges:
            draw_box(c, c + 1, -TILE_HEIGHT, 0, r, r + 1, BRIDGE_COLOR)

        draw_box(*block_bounds(state), BLOCK_COLOR)