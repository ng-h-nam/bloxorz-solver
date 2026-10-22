"""Demo màn chơi 3D dùng hình của nhóm: mỗi loại ô một texture ở mặt trên.

Chạy từ thư mục Source/:  python gui/demo_level_textures_opengl.py
Hình lấy từ assets/textures/ (tạo bằng tools/prepare_textures.py).
"""

import argparse
import os

import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE
from OpenGL.GL import (
    glBegin, glEnd, glVertex3f, glColor3f, glColor4f, glTexCoord2f, GL_QUADS,
    glClearColor, glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glEnable, glDisable, GL_DEPTH_TEST,
    glMatrixMode, glLoadIdentity, GL_PROJECTION, GL_MODELVIEW, glDepthMask, GL_TRUE, GL_FALSE,
    glGenTextures, glBindTexture, glTexImage2D, glTexParameteri, glGenerateMipmap, glDeleteTextures,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_LINEAR, GL_NEAREST, GL_LINEAR_MIPMAP_LINEAR, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
    GL_BLEND, glBlendFunc, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    glGenLists, glNewList, glEndList, glCallList, GL_COMPILE,
    glReadPixels, GL_RGB,
)
from OpenGL.GLU import gluPerspective, gluLookAt

SHADE = {"top": 1.0, "front": 0.85, "back": 0.85, "left": 0.7, "right": 0.7, "bottom": 0.5}
UV = ((0, 0), (1, 0), (1, 1), (0, 1))
TEXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "textures")
NAMES = ["floor", "floor_side", "block", "bridge", "fragile", "goal", "soft_switch", "heavy_switch", "split_switch"]
ROWS, COLS = 5, 9
TILE_THICKNESS = 0.3

# loại ô -> hình dùng cho mặt trên
TOP = {"floor": "floor", "fragile": "fragile", "bridge": "bridge", "goal": "goal",
       "soft": "soft_switch", "heavy": "heavy_switch", "split": "split_switch"}

LEVEL = {(2, 1): "fragile", (2, 2): "bridge", (2, 4): "goal", (2, 5): "soft", (2, 6): "heavy", (2, 7): "split"}
CLOSED_BRIDGES = [(2, 3)]


def cuboid_faces(x0, x1, y0, y1, z0, z1):
    return {
        "top":    ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)),
        "bottom": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
        "front":  ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
        "back":   ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)),
        "left":   ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
        "right":  ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)),
    }


def load_texture(path):
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
    return texture


def draw_textured_box(bounds, top, side, alpha=1.0):
    glEnable(GL_TEXTURE_2D)
    for name, quad in cuboid_faces(*bounds).items():
        glBindTexture(GL_TEXTURE_2D, top if name == "top" else side)
        shade = SHADE[name]
        glColor4f(shade, shade, shade, alpha)
        glBegin(GL_QUADS)
        for (u, v), vertex in zip(UV, quad):
            glTexCoord2f(u, v)
            glVertex3f(*vertex)
        glEnd()
    glDisable(GL_TEXTURE_2D)


def tile_bounds(row, col):
    return (col + 0.02, col + 0.98, -TILE_THICKNESS, 0.0, row + 0.02, row + 0.98)


def build_static_list(tex):
    """Nền tĩnh vẽ một lần vào display list."""
    handle = glGenLists(1)
    glNewList(handle, GL_COMPILE)
    for r in range(ROWS):
        for c in range(COLS):
            if (r, c) in CLOSED_BRIDGES:
                continue
            kind = LEVEL.get((r, c), "floor")
            draw_textured_box(tile_bounds(r, c), tex[TOP[kind]], tex["floor_side"])
    glEndList()
    return handle


def draw_closed_bridges(tex):
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDepthMask(GL_FALSE)
    for r, c in CLOSED_BRIDGES:
        draw_textured_box(tile_bounds(r, c), tex["bridge"], tex["bridge"], alpha=0.28)
    glDepthMask(GL_TRUE)
    glDisable(GL_BLEND)


def draw_scene(tex, static_list):
    glClearColor(0.08, 0.08, 0.12, 1)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    gluLookAt(COLS / 2, 8.5, ROWS / 2 + 6.5, COLS / 2, 0, ROWS / 2, 0, 1, 0)
    glCallList(static_list)
    draw_textured_box((1.0, 2.0, 0.0, 2.0, 0.0, 1.0), tex["block"], tex["block"])
    draw_textured_box((5.0, 7.0, 0.0, 1.0, 0.0, 1.0), tex["block"], tex["block"])
    draw_closed_bridges(tex)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", help="vẽ một khung hình rồi lưu ra file PNG")
    args = parser.parse_args()
    width, height = 900, 560
    pygame.init()
    pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, width / height, 0.1, 100)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    tex = {name: load_texture(os.path.join(TEXTURE_DIR, name + ".png")) for name in NAMES}
    static_list = build_static_list(tex)

    if args.shot:
        draw_scene(tex, static_list)
        data = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
        data = data.tobytes() if hasattr(data, "tobytes") else data
        pygame.image.save(pygame.image.frombytes(data, (width, height), "RGB", True), args.shot)
    else:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    running = False
            draw_scene(tex, static_list)
            pygame.display.flip()
    glDeleteTextures(list(tex.values()))
    pygame.quit()


if __name__ == "__main__":
    main()
