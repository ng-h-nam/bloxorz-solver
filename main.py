import os

from core.map_loader import load_level
from core.state import State, Orientation
from gui.window import Window

LEVEL_FILE = os.path.join("data", "maps", "level0.txt")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    board = load_level(os.path.join(base_dir, LEVEL_FILE))

    r, c = board.start_pos
    state = State(
        r=r,
        c=c,
        orientation=Orientation.STANDING,
        active_bridges=board.initial_active_bridges,
    )

    Window(board, state).run()


if __name__ == "__main__":
    main()