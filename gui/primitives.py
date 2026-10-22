import os
import pygame
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE, GL_LINEAR_MIPMAP_LINEAR, GL_NEAREST, GL_RGBA, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_UNSIGNED_BYTE, 
    glBegin, glBindTexture, glColor4f, glEnd, glColor3f, glGenTextures, glGenerateMipmap, 
    glTexCoord2f, glTexImage2D, glTexParameteri, glVertex3f, GL_QUADS, glEnable, glDisable,

)
SHADE = {"top": 1.0, "front": 0.85, "back": 0.85, "left": 0.7, "right": 0.7, "bottom": 0.5}
UV = ((0, 0), (1, 0), (1, 1), (0, 1))
TEXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "textures")
NAMES = ["floor", "floor_side", "block", "bridge", "fragile", "goal", "soft_switch", "heavy_switch", "split_switch"]
ROWS, COLS = 5, 9
TILE_THICKNESS = 0.3


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