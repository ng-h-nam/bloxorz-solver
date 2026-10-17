# test_transition.py
import unittest
from core.block import Block, Direction
from core.board import Board
from core.state import Orientation, State
from core.transition import (
    TRANSITION_TABLE,
    get_next_state,
    get_successors,
    is_goal_state,
    is_valid_state,
)

S, H, V = Orientation.STANDING, Orientation.HORIZONTAL, Orientation.VERTICAL


def make_open_board(rows: int = 7, cols: int = 7) -> Board:
    """Bản đồ toàn sàn, S ở góc trên-trái, G ở góc dưới-phải."""
    lines = ["#" * cols for _ in range(rows)]
    lines[0] = "S" + lines[0][1:]
    lines[-1] = lines[-1][:-1] + "G"
    return Board.from_str_grid(lines)


class TestRolling(unittest.TestCase):
    """Kiểm tra công thức lăn trên bản đồ toàn sàn (không bị rơi)."""

    def setUp(self):
        self.board = make_open_board()

    def assertRoll(self, start: State, direction: Direction, expected: State):
        self.assertEqual(get_next_state(self.board, start, direction), expected)

    def test_transition_table_complete(self):
        self.assertEqual(len(TRANSITION_TABLE), 12)
        for o in Orientation:
            for d in Direction:
                self.assertIn((o, d), TRANSITION_TABLE)

    def test_standing(self):
        s = State(3, 3, S)
        self.assertRoll(s, Direction.UP,    State(1, 3, V))
        self.assertRoll(s, Direction.DOWN,  State(4, 3, V))
        self.assertRoll(s, Direction.LEFT,  State(3, 1, H))
        self.assertRoll(s, Direction.RIGHT, State(3, 4, H))

    def test_horizontal(self):  # chiếm (3,3), (3,4)
        s = State(3, 3, H)
        self.assertRoll(s, Direction.UP,    State(2, 3, H))
        self.assertRoll(s, Direction.DOWN,  State(4, 3, H))
        self.assertRoll(s, Direction.LEFT,  State(3, 2, S))
        self.assertRoll(s, Direction.RIGHT, State(3, 5, S))

    def test_vertical(self):  # chiếm (3,3), (4,3)
        s = State(3, 3, V)
        self.assertRoll(s, Direction.UP,    State(2, 3, S))
        self.assertRoll(s, Direction.DOWN,  State(5, 3, S))
        self.assertRoll(s, Direction.LEFT,  State(3, 2, V))
        self.assertRoll(s, Direction.RIGHT, State(3, 4, V))

    def test_roll_back_returns_original(self):
        """Lăn đi rồi lăn ngược lại phải về đúng trạng thái cũ."""
        opposite = {Direction.UP: Direction.DOWN, Direction.DOWN: Direction.UP,
                    Direction.LEFT: Direction.RIGHT, Direction.RIGHT: Direction.LEFT}
        for o in Orientation:
            for d in Direction:
                start = State(3, 3, o)
                nxt = get_next_state(self.board, start, d)
                self.assertEqual(get_next_state(self.board, nxt, opposite[d]), start)


class TestBoardRules(unittest.TestCase):
    def setUp(self):
        layout = [
            "######",
            "#S###.",
            "#####G",
            "####F#",
            "......",
        ]
        self.board = Board.from_str_grid(layout)
        self.initial_state = Block(*self.board.start_pos, S).to_state()

    def test_out_of_bounds_returns_none(self):
        self.assertIsNone(get_next_state(self.board, self.initial_state, Direction.UP))
        self.assertIsNone(get_next_state(self.board, self.initial_state, Direction.LEFT))

    def test_void_tile_invalid(self):
        self.assertFalse(is_valid_state(self.board, State(1, 4, H)))  # đè lên (1,5) là '.'
        self.assertFalse(is_valid_state(self.board, State(3, 0, V)))  # đè lên (4,0) là '.'

    def test_fragile_tile(self):
        self.assertFalse(is_valid_state(self.board, State(3, 4, S)))  # đứng trên F -> vỡ
        self.assertTrue(is_valid_state(self.board, State(3, 3, H)))   # nằm trên F -> OK

    def test_successors(self):
        succ = dict(get_successors(self.board, self.initial_state))
        self.assertEqual(set(succ), {Direction.RIGHT, Direction.DOWN})
        self.assertEqual(succ[Direction.RIGHT], State(1, 2, H))
        self.assertEqual(succ[Direction.DOWN], State(2, 1, V))

    def test_goal_detection(self):
        self.assertTrue(is_goal_state(self.board, State(2, 5, S)))
        self.assertFalse(is_goal_state(self.board, State(2, 4, H)))  # nằm đè lên G
        self.assertFalse(is_goal_state(self.board, self.initial_state))


class TestBridge(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_str_grid(["S=#G"])  # cầu ở (0,1)

    def test_bridge_closed_vs_open(self):
        self.assertFalse(is_valid_state(self.board, State(0, 1, S)))
        self.assertTrue(is_valid_state(self.board, State(0, 1, S, frozenset({(0, 1)}))))

    def test_active_bridges_preserved(self):
        bridges = frozenset({(0, 1)})
        nxt = get_next_state(self.board, State(0, 0, S, bridges), Direction.RIGHT)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.active_bridges, bridges)


class TestStateHashing(unittest.TestCase):
    def test_state_in_visited_set(self):
        visited = {State(1, 1, S)}
        self.assertIn(State(1, 1, S), visited)
        self.assertNotIn(State(1, 1, H), visited)


if __name__ == "__main__":
    unittest.main()
