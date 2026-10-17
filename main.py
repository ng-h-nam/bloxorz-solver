import os

from core.map_loader import load_level
from core.state import State, Orientation
from gui.window import Window

LEVELS_FILE = os.path.join("data", "maps", "levels.json")
DEFAULT_LEVEL_ID = "ez"  # màn không có công tắc, dùng để kiểm tra


def main(level_id: str = DEFAULT_LEVEL_ID):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, LEVELS_FILE)

    board = load_level(path, level_id)
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