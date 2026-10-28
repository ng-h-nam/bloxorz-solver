"""Vẽ cảnh 3D: nền bản đồ, các ô đặc biệt, khối đứng yên hoặc đang chuyển động (lăn, đổ quanh mép, chìm)."""

import math
import os
from collections.abc import Set as AbstractSet

from OpenGL.GL import (
    GL_CLIP_PLANE0,
    GL_COLOR_BUFFER_BIT,
    GL_COMPILE,
    GL_DEPTH_BUFFER_BIT,
    GL_LINE_LOOP,
    GL_QUADS,
    GL_TEXTURE_2D,
    glBegin,
    glBindTexture,
    glCallList,
    glClear,
    glClearColor,
    glClipPlane,
    glColor3f,
    glColor4f,
    glDeleteLists,
    glDisable,
    glEnable,
    glEnd,
    glEndList,
    glGenLists,
    glLineWidth,
    glLoadIdentity,
    glNewList,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTexCoord2f,
    glTranslatef,
    glVertex3f,
)
from OpenGL.GLU import gluLookAt

from core.block import Direction
from core.board import Board, TileType
from core.state import State
from gui.engine.animator import Pose, TilePose
from gui.scene import primitives
from gui.scene.camera import OrbitCamera
from gui.scene.primitives import cuboid_faces, draw_textured_box, load_texture
from gui.shared.geometry import (
    DEFAULT_FACE_SHADE,
    TILE_HEIGHT,
    Bounds,
    Cell,
    Vec3,
    active_piece,
    block_pieces,
    composed_face_shades,
    roll_pivot,
    rotated_face_shades,
    tile_bounds,
)
from gui.shared.paths import PROJECT_ROOT

FOV_DEGREES: float = 45.0
MIN_CAMERA_DISTANCE: float = 10.0
MAX_CAMERA_DISTANCE: float = 120.0
CAMERA_MARGIN: float = 0.95  # chừa 5% mép khung
BLOCK_HEIGHT: float = 2.0
PAN_MARGIN: float = 4.0  # được dịch điểm nhìn ra ngoài vùng bản đồ tối đa bằng ngần này ô

TEXTURE_DIR: str = os.path.join(PROJECT_ROOT, "assets", "textures")
TEXTURE_NAMES: list[str] = [
    "floor",
    "floor_side",
    "block",
    "bridge",
    "fragile",
    "goal",
    "soft_switch",
    "heavy_switch",
    "split_switch",
]

# Loại ô -> hình dùng cho mặt trên
TOP_TEXTURE: dict[TileType, str] = {
    TileType.FLOOR: "floor",
    TileType.FRAGILE: "fragile",
    TileType.GOAL: "goal",
    TileType.SOFT_SWITCH: "soft_switch",
    TileType.HEAVY_SWITCH: "heavy_switch",
    TileType.SPLIT_SWITCH: "split_switch",
}

# VOID là khoảng trống; BRIDGE vẽ riêng mỗi khung hình vì phụ thuộc state.active_bridges
SKIPPED_TILES: tuple[TileType, ...] = (TileType.VOID, TileType.BRIDGE)

OUTLINE_COLOR: tuple[float, float, float] = (1.0, 0.9, 0.2)

# Độ sáng các mặt khi đứng yên: dùng cùng bảng với primitives để khối và ô khớp nhau
BASE_SHADE: dict[str, float] = {
    **DEFAULT_FACE_SHADE,
    **getattr(primitives, "SHADE", {}),
}
_UV: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (1, 1), (0, 1))


def _dot(a: Vec3, b: Vec3) -> float:
    """Tích vô hướng của hai vector."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    """Tích có hướng của hai vector."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(a: Vec3) -> Vec3:
    """Vector đơn vị cùng hướng với `a`."""
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def content_bounds(board: Board) -> tuple[float, float, float, float]:
    """(cột đầu, cột cuối + 1, hàng đầu, hàng cuối + 1) của vùng có ô thật, bỏ qua viền ô trống."""
    cells = [(r, c) for r in range(board.rows) for c in range(board.cols) if board.grid[r][c] != TileType.VOID]
    if not cells:
        return (0.0, float(board.cols), 0.0, float(board.rows))
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return (
        float(min(cols)),
        float(max(cols) + 1),
        float(min(rows)),
        float(max(rows) + 1),
    )


def fit_camera_distance(bounds: tuple[float, float, float, float], aspect: float) -> float:
    """Khoảng cách camera nhỏ nhất để vùng có ô (kể cả khối cao 2) nằm trong khung nhìn."""
    c0, c1, r0, r1 = bounds
    center_x, center_z = (c0 + c1) / 2, (r0 + r1) / 2
    target: Vec3 = (center_x, 0.0, center_z)
    tan_half = math.tan(math.radians(FOV_DEGREES) / 2)
    corners = [(x, y, z) for x in (c0, c1) for z in (r0, r1) for y in (-TILE_HEIGHT, BLOCK_HEIGHT)]
    distance = MIN_CAMERA_DISTANCE
    while distance < MAX_CAMERA_DISTANCE:
        eye = OrbitCamera(center_x, center_z, distance).eye
        forward = _normalize((target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]))
        right = _normalize(_cross(forward, (0.0, 1.0, 0.0)))
        up = _cross(right, forward)
        fits = True
        for corner in corners:
            v = (corner[0] - eye[0], corner[1] - eye[1], corner[2] - eye[2])
            depth = _dot(v, forward)
            if (
                abs(_dot(v, right) / depth / (tan_half * aspect)) > CAMERA_MARGIN
                or abs(_dot(v, up) / depth / tan_half) > CAMERA_MARGIN
            ):
                fits = False
                break
        if fits:
            return distance
        distance += 0.25
    return MAX_CAMERA_DISTANCE


def load_textures() -> dict[str, int]:
    """Nạp hình một lần (cần có cửa sổ OpenGL). Dùng chung cho mọi Renderer."""
    return {name: load_texture(os.path.join(TEXTURE_DIR, name + ".png")) for name in TEXTURE_NAMES}


def apply_roll(bounds: Bounds, direction: Direction, angle: float) -> None:
    """Xoay quanh cạnh đáy phía hướng lăn: dời điểm xoay về gốc, xoay, rồi dời ngược lại."""
    px, pz, axis, sign = roll_pivot(bounds, direction)
    glTranslatef(px, 0.0, pz)
    glRotatef(sign * angle, *axis)
    glTranslatef(-px, 0.0, -pz)


def draw_shaded_box(bounds: Bounds, top_texture: int, side_texture: int, shades: dict[str, float]) -> None:
    """Hộp có texture, độ sáng từng mặt lấy từ `shades` (tính theo hướng thật của mặt)."""
    glEnable(GL_TEXTURE_2D)
    for name, quad in cuboid_faces(*bounds).items():
        glBindTexture(GL_TEXTURE_2D, top_texture if name == "top" else side_texture)
        shade = shades[name]
        glColor4f(shade, shade, shade, 1.0)
        glBegin(GL_QUADS)
        for (u, v), vertex in zip(_UV, quad, strict=True):
            glTexCoord2f(u, v)
            glVertex3f(*vertex)
        glEnd()
    glDisable(GL_TEXTURE_2D)


class Renderer:
    """Vẽ một bản đồ cùng khối của nó; giữ camera và display list của nền."""

    def __init__(
        self,
        board: Board,
        aspect: float = 4 / 3,
        textures: dict[str, int] | None = None,
    ) -> None:
        """Dựng cảnh cho `board` (cần ngữ cảnh OpenGL đang mở); camera được đặt vừa khít bản đồ."""
        self.board: Board = board

        # Cần có cửa sổ OpenGL trước khi tải hình và tạo display list
        self.tex: dict[str, int] = textures if textures is not None else load_textures()
        self.bridge_cells: list[Cell] = [
            (r, c) for r in range(board.rows) for c in range(board.cols) if board.grid[r][c] == TileType.BRIDGE
        ]

        c0, c1, r0, r1 = content_bounds(board)
        self.camera: OrbitCamera = OrbitCamera(
            (c0 + c1) / 2,
            (r0 + r1) / 2,
            fit_camera_distance((c0, c1, r0, r1), aspect),
            limits=(c0 - PAN_MARGIN, c1 + PAN_MARGIN, r0 - PAN_MARGIN, r1 + PAN_MARGIN),
        )
        self._hidden: frozenset[Cell] = frozenset()
        self.map_list: int = self._build_map_list()

    def dispose(self) -> None:
        """Giải phóng display list khi đổi sang màn khác. Texture dùng chung nên không xóa ở đây."""
        glDeleteLists(self.map_list, 1)

    def _build_map_list(self) -> int:
        """Biên dịch nền bản đồ thành một display list. Ô trong `_hidden` (đã vỡ) thì bỏ qua."""
        map_list = glGenLists(1)
        glNewList(map_list, GL_COMPILE)
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                tile = self.board.grid[r][c]
                if tile in SKIPPED_TILES or (r, c) in self._hidden:
                    continue
                top = self.tex[TOP_TEXTURE.get(tile, "floor")]
                draw_textured_box(tile_bounds(r, c), top, self.tex["floor_side"])
        glEndList()
        return map_list

    def _set_hidden(self, hidden: AbstractSet[Cell]) -> None:
        """Dựng lại display list khi tập ô đã vỡ thay đổi (hiếm: chỉ khi một ô giòn vỡ hoặc chơi lại)."""
        self._hidden = frozenset(hidden)
        glDeleteLists(self.map_list, 1)
        self.map_list = self._build_map_list()

    def _setup_camera(self) -> None:
        """Đặt ma trận nhìn theo camera hiện tại."""
        glLoadIdentity()
        gluLookAt(*self.camera.eye, *self.camera.target, 0.0, 1.0, 0.0)

    def draw(
        self,
        state: State,
        pose: Pose | None = None,
        show_block: bool = True,
        hidden_tiles: AbstractSet[Cell] = frozenset(),
        clear_color: bool = True,
    ) -> None:
        """Vẽ cả cảnh 3D. `clear_color=False` chỉ xóa độ sâu để giữ nền đã vẽ sẵn phía sau (bầu trời)."""
        if frozenset(hidden_tiles) != self._hidden:
            self._set_hidden(hidden_tiles)

        if clear_color:
            glClearColor(0.08, 0.08, 0.12, 1)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        else:
            glClear(GL_DEPTH_BUFFER_BIT)
        self._setup_camera()

        glCallList(self.map_list)

        self._draw_open_bridges(state)
        if show_block:
            self._draw_pieces(state, pose)
        if pose is not None and pose.tile is not None:
            self._draw_falling_tile(pose.tile)

    def _draw_open_bridges(self, state: State) -> None:
        """Vẽ các cầu đang mở theo trạng thái công tắc."""
        for r, c in self.bridge_cells:
            if (r, c) in state.active_bridges:
                draw_textured_box(tile_bounds(r, c), self.tex["bridge"], self.tex["floor_side"])

    def _apply_pose(self, pose: Pose) -> dict[str, float]:
        """Áp ma trận của `pose` (dời y, đổ quanh mép, lăn) và trả về độ sáng các mặt tương ứng.

        Thứ tự ma trận khớp với `animator.transform_point`: điểm của khối được lăn trước, rồi đổ quanh mép, rồi dời.
        """
        glTranslatef(0.0, pose.drop, 0.0)
        rotations: list[tuple[Vec3, float]] = []
        if pose.tip is not None:
            tip = pose.tip
            glTranslatef(*tip.shift)
            glTranslatef(*tip.pivot)
            glRotatef(tip.degrees, *tip.axis)
            glTranslatef(-tip.pivot[0], -tip.pivot[1], -tip.pivot[2])
        if pose.direction is not None:
            apply_roll(pose.bounds, pose.direction, pose.angle)
            axis, sign = roll_pivot(pose.bounds, pose.direction)[2:]
            rotations.append((axis, sign * pose.angle))
        if pose.tip is not None:
            rotations.append((pose.tip.axis, pose.tip.degrees))
        return composed_face_shades(BASE_SHADE, rotations)

    def _draw_pieces(self, state: State, pose: Pose | None) -> None:
        """Vẽ các mảnh khối; mảnh đang chuyển động được vẽ theo `pose`."""
        split = state.is_split()
        active = active_piece(state)
        for index, bounds in enumerate(block_pieces(state)):
            outline = split and index == active
            if pose is not None and pose.piece == index:
                if pose.sinking:
                    # Khối chìm vào ô đích: cắt bỏ phần nằm dưới mặt gạch để nó không thò ra dưới đáy gạch dày
                    glClipPlane(GL_CLIP_PLANE0, (0.0, 1.0, 0.0, 0.0))
                    glEnable(GL_CLIP_PLANE0)
                glPushMatrix()
                shades = self._apply_pose(pose)
                self._draw_piece(pose.bounds, shades, outline)
                glPopMatrix()
                if pose.sinking:
                    glDisable(GL_CLIP_PLANE0)
            else:
                self._draw_piece(bounds, BASE_SHADE, outline)

    def _draw_piece(self, bounds: Bounds, shades: dict[str, float], outline: bool) -> None:
        """Vẽ một mảnh khối, kèm viền vàng nếu đó là khối đơn đang được điều khiển."""
        draw_shaded_box(bounds, self.tex["block"], self.tex["block"], shades)
        if outline:
            self._draw_outline(bounds)

    def _draw_falling_tile(self, pose: TilePose) -> None:
        """Ô giòn vỡ: dời xuống và nghiêng quanh tâm ô, độ sáng các mặt theo góc nghiêng."""
        row, col = pose.cell
        cx, cy, cz = col + 0.5, -TILE_HEIGHT / 2, row + 0.5
        glPushMatrix()
        glTranslatef(0.0, pose.drop, 0.0)
        glTranslatef(cx, cy, cz)
        glRotatef(pose.degrees, *pose.axis)
        glTranslatef(-cx, -cy, -cz)
        draw_shaded_box(
            tile_bounds(row, col),
            self.tex["fragile"],
            self.tex["floor_side"],
            rotated_face_shades(BASE_SHADE, pose.axis, pose.degrees),
        )
        glPopMatrix()

    def _draw_outline(self, bounds: Bounds) -> None:
        """Viền vàng quanh hộp (nhô ra 0.01 để không bị z-fighting)."""
        x0, x1, y0, y1, z0, z1 = bounds
        e = 0.01
        glLineWidth(3.0)
        glColor3f(*OUTLINE_COLOR)
        for quad in cuboid_faces(x0 - e, x1 + e, y0 - e, y1 + e, z0 - e, z1 + e).values():
            glBegin(GL_LINE_LOOP)
            for vertex in quad:
                glVertex3f(*vertex)
            glEnd()
