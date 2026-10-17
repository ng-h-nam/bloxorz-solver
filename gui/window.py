import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_UP, K_DOWN, K_LEFT, K_RIGHT
from OpenGL.GL import glEnable, glMatrixMode, glLoadIdentity, GL_DEPTH_TEST, GL_PROJECTION, GL_MODELVIEW
from OpenGL.GLU import gluPerspective

from core.block import Direction
from core.transition import get_next_state
from gui.renderer import Renderer

KEY_TO_DIRECTION = {
    K_UP: Direction.UP,
    K_DOWN: Direction.DOWN,
    K_LEFT: Direction.LEFT,
    K_RIGHT: Direction.RIGHT,
}


class Window:
    def __init__(self, board, state, width=1024, height=768):
        self.board = board
        self.state = state

        pygame.init()
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Bloxorz")

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, width / height, 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

        self.renderer = Renderer(board)
        self.clock = pygame.time.Clock()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    self.handle_key(event.key)

            self.renderer.draw(self.state)
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def handle_key(self, key):
        direction = KEY_TO_DIRECTION.get(key)
        if direction is None:
            return
        next_state = get_next_state(self.board, self.state, direction)
        if next_state is not None:
            self.state = next_state
        # Nếu next_state là None, khối rơi: sẽ xử lý game over ở bước sau