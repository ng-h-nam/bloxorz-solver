import unittest
from pathlib import Path
from core.block import Direction
from core.board import TileType
from core.map_loader import load_level, parse_level
from core.state import Orientation, State, get_occupied_cells
from core.transition import (
    check_occupied_cells,
    get_next_state,
    is_goal_state,
    is_valid_state,
)

# Tự động tìm file level0.txt trong project
PROJECT_ROOT = Path(__file__).resolve().parent.parent
POSSIBLE_PATHS = [
    PROJECT_ROOT / "level0.txt",
    PROJECT_ROOT / "maps" / "level0.txt",
    Path("level0.txt"),
]


class TestIntegrationWithMapLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Sử dụng trực tiếp load_level / parse_level từ core/map_loader.py của Thuật."""
        txt_path = next((p for p in POSSIBLE_PATHS if p.exists()), None)
        if txt_path is not None:
            cls.board = load_level(str(txt_path))
        else:
            cls.board = parse_level([
                ".....",
                ".SFF.",
                ".FFF.",
                ".FTF.",
                ".FFF.",
                ".....",
            ])

    def test_map_loader_compatibility(self):
        """Kiểm tra Board nhận đúng grid, symbols, start_pos, goal_pos từ map_loader.py."""
        self.assertEqual((self.board.rows, self.board.cols), (6, 5))
        self.assertEqual(self.board.start_pos, (1, 1))
        self.assertEqual(self.board.goal_pos, (3, 2))
        self.assertEqual(self.board.get_symbol(1, 1), "S")
        self.assertEqual(self.board.get_symbol(3, 2), "T")
        self.assertEqual(self.board.get_tile(1, 1), TileType.FLOOR)
        self.assertEqual(self.board.get_tile(3, 2), TileType.GOAL)
        self.assertEqual(self.board.get_tile(0, 0), TileType.VOID)

    def test_round_trip_no_coordinate_drift(self):
        """Kiểm tra lăn đi rồi lăn ngược lại không bị lệch tọa độ khi đổi hướng."""
        opposite = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        for orient in Orientation:
            s = State(r=2, c=2, orientation=orient)
            for d in Direction:
                moved = get_next_state(s, d)
                returned = get_next_state(moved, opposite[d])
                self.assertEqual(s, returned)

    def test_level0_boundary_cases(self):
        """Kiểm tra biên tại S(1, 1) và trạng thái nửa trong nửa ngoài trên level0.txt."""
        start_state = State(*self.board.start_pos, Orientation.STANDING)
        # Lăn UP hoặc LEFT từ (1, 1) sẽ rơi vào viền '.' (VOID)
        self.assertIsNone(get_next_state(start_state, Direction.UP, self.board))
        self.assertIsNone(get_next_state(start_state, Direction.LEFT, self.board))

        # Trạng thái nằm ngang tại (1, 3) chiếm (1, 3)='F' và (1, 4)='.' -> Không hợp lệ
        half_hanging = State(1, 3, Orientation.HORIZONTAL)
        self.assertFalse(is_valid_state(self.board, half_hanging))

    def test_falling_orange_tile_with_map_loader(self):
        """Kiểm tra ô gạch mỏng 'O' (TileType.FALLING) theo quy ước trong map_loader.py."""
        board_with_falling = parse_level([
            ".....",
            ".SOF.",
            ".FFT.",
            ".....",
        ])
        # Nằm ngang đè lên (1, 2)='O' và (1, 3)='F' -> Hợp lệ
        s_lying = State(1, 2, Orientation.HORIZONTAL)
        self.assertTrue(is_valid_state(board_with_falling, s_lying))

        # Đứng thẳng tại (1, 2)='O' -> Bị sập (Không hợp lệ)
        s_standing = State(1, 2, Orientation.STANDING)
        valid, msg = check_occupied_cells(board_with_falling, s_standing)
        self.assertFalse(valid)
        self.assertIn("FALLING", msg)

    def test_solve_level0_in_7_moves(self):
        """Kiểm tra 7 bước di chuyển thắng màn level0.txt."""
        state = State(*self.board.start_pos, Orientation.STANDING)
        moves = ["RIGHT", "DOWN", "DOWN", "LEFT", "UP", "RIGHT", "DOWN"]
        for move in moves:
            state = get_next_state(state, move, self.board)
            self.assertIsNotNone(state)
        self.assertTrue(is_goal_state(self.board, state))


if __name__ == "__main__":
    unittest.main()
