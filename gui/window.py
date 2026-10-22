from typing import Dict, Tuple

import pygame
from pygame.locals import (
    DOUBLEBUF, OPENGL, QUIT, KEYDOWN, MOUSEBUTTONDOWN,
    K_UP, K_DOWN, K_LEFT, K_RIGHT, K_w, K_a, K_s, K_d, K_r,
)
from OpenGL.GL import glEnable, glMatrixMode, glLoadIdentity, glViewport, GL_DEPTH_TEST, GL_PROJECTION, GL_MODELVIEW
from OpenGL.GLU import gluPerspective

from core.block import Direction
from core.game import Game, GameStatus
from core.transition import MoveResult
from gui.control_panel import PANEL_WIDTH, ControlPanel
from gui.renderer import FOV_DEGREES, Renderer

KEY_TO_DIRECTION: Dict[int, Direction] = {
    K_UP: Direction.UP, K_w: Direction.UP,
    K_DOWN: Direction.DOWN, K_s: Direction.DOWN,
    K_LEFT: Direction.LEFT, K_a: Direction.LEFT,
    K_RIGHT: Direction.RIGHT, K_d: Direction.RIGHT,
}

MSG_FALL: str = "Nước đi không hợp lệ: khối đã rơi. Nhấn R hoặc Restart để chơi lại."
MSG_WIN: str = "Hoàn thành màn chơi!"
MSG_ENDED: str = "Ván đã kết thúc. Nhấn R để chơi lại."


class Window:
    def __init__(
        self,
        game: Game,
        level_name: str = "",
        width: int = 1280,
        height: int = 768,
    ) -> None:
        self.game: Game = game
        self.level_name: str = level_name
        self.message: str = ""
        self.width: int = width
        self.height: int = height

        pygame.init()
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Bloxorz")

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = (width - PANEL_WIDTH) / height      # chỉ vùng bên phải cột bảng dùng cho cảnh 3D
        gluPerspective(FOV_DEGREES, aspect, 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

        # Tạo sau set_mode vì cần ngữ cảnh OpenGL
        self.renderer: Renderer = Renderer(game.board, aspect)
        self.panel: ControlPanel = ControlPanel(width, height)
        self.clock: pygame.time.Clock = pygame.time.Clock()

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    self.handle_key(event.key)
                elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)

            self.draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def draw(self) -> None:
        glViewport(PANEL_WIDTH, 0, self.width - PANEL_WIDTH, self.height)
        self.renderer.draw(self.game.state)
        glViewport(0, 0, self.width, self.height)
        self.panel.draw(self.game, self.level_name, self.message)

    def handle_key(self, key: int) -> None:
        if key == K_r:
            self.restart()
            return

        direction = KEY_TO_DIRECTION.get(key)
        if direction is None:
            return

        outcome = self.game.move(direction)
        if outcome is None:
            self.message = MSG_ENDED
        elif outcome.result == MoveResult.FALL:
            self.message = MSG_FALL
        elif self.game.status == GameStatus.WON:
            self.message = MSG_WIN
        else:
            self.message = ""

    def handle_click(self, pos: Tuple[int, int]) -> None:
        if self.panel.handle_click(pos) == "restart":
            self.restart()

    def restart(self) -> None:
        self.game.restart()
        self.message = ""