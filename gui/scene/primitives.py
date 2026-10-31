"""Hình nguyên thủy của cảnh 3D: hộp có texture và việc nạp texture từ file."""

import os

import pygame
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_LINEAR_MIPMAP_LINEAR,
    GL_NEAREST,
    GL_QUADS,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glGenerateMipmap,
    glGenTextures,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex3f,
)

from gui.shared.geometry import Bounds, Vec3
from gui.shared.paths import PROJECT_ROOT

Quad = tuple[Vec3, Vec3, Vec3, Vec3]

SHADE: dict[str, float] = {
    "top": 1.0,
    "front": 0.85,
    "back": 0.85,
    "left": 0.7,
    "right": 0.7,
    "bottom": 0.5,
}
UV: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (1, 1), (0, 1))
TEXTURE_DIR: str = os.path.join(PROJECT_ROOT, "assets", "textures")
NAMES: list[str] = [
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


def cuboid_faces(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> dict[str, Quad]:
    """Bốn đỉnh của từng mặt trong sáu mặt của hộp (theo thứ tự khớp với UV)."""
    return {
        "top": ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)),
        "bottom": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
        "front": ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
        "back": ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)),
        "left": ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
        "right": ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)),
    }


def load_texture(path: str) -> int:
    """Nạp một file ảnh thành texture OpenGL (có mipmap) và trả về mã texture."""
    surface = pygame.image.load(path).convert_alpha()
    width, height = surface.get_size()
    data = pygame.image.tobytes(surface, "RGBA", True)
    texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glGenerateMipmap(GL_TEXTURE_2D)
    return int(texture)


def draw_textured_box(bounds: Bounds, top: int, side: int, alpha: float = 1.0) -> None:
    """Vẽ hộp `bounds`: mặt trên dùng texture `top`, năm mặt còn lại dùng `side`, độ sáng theo SHADE."""
    glEnable(GL_TEXTURE_2D)
    for name, quad in cuboid_faces(*bounds).items():
        glBindTexture(GL_TEXTURE_2D, top if name == "top" else side)
        shade = SHADE[name]
        glColor4f(shade, shade, shade, alpha)
        glBegin(GL_QUADS)
        for (u, v), vertex in zip(UV, quad, strict=True):
            glTexCoord2f(u, v)
            glVertex3f(*vertex)
        glEnd()
    glDisable(GL_TEXTURE_2D)
