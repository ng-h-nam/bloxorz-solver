import os

from core.game import Game
from core.map_loader import load_level
from gui.window import Window

LEVEL_FILE = os.path.join("data", "maps", "coolmath.json")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    board = load_level(os.path.join(base_dir, LEVEL_FILE))
    game = Game(board)
    Window(game, level_name=os.path.basename(LEVEL_FILE)).run()


if __name__ == "__main__":
    main()
