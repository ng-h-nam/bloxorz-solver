import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.block import Direction
from core.game import Game, GameStatus
from core.map_loader import load_coolmath_stage, parse_level
from core.state import Orientation, State
from core.transition import (
    MoveResult,
    SWITCH_ACTION,
    get_next_state,
    get_successors,
    is_goal_state,
    set_active_board,
)


class TestBloxorzAdvancedGameMechanics(unittest.TestCase):
    """
    Bộ kiểm thử nghiệm thu nhiệm vụ nâng cao (tests/test_game.py):
      1. Ô tách khối 'T' (SPLIT_SWITCH): chỉ tách khi đứng thẳng, dịch chuyển tới 2 vị trí định sẵn.
      2. Hành động đổi khối (SWITCH / SPACE) và get_successors có hành động đổi khối.
      3. Gộp khối (Merge): 2 khối đơn tiến lại kề nhau tự động gộp thành HORIZONTAL hoặc VERTICAL.
      4. Cầu toggle ('swap') và permanent ('on' / 'off' / 'permanent') với công tắc soft ('O') và heavy ('X').
      5. Khối đơn KHÔNG thắng khi đi vào ô đích 'H' (end_pos).
      6. Khối đơn KHÔNG kích hoạt được Heavy Switch ('X'), nhưng kích hoạt được Soft Switch ('O').
      7. Tích hợp đầy đủ trong class Game và dữ liệu coolmath.json.
    """

    def setUp(self):
        self.stage_data = {
            "name": "Test Advanced Mechanics",
            "grid": [
                "         ",
                " S.T.O.. ",
                " .....X. ",
                " .bbbbH. ",
                "         ",
            ],
            "bridges": [
                [[3, 2], [3, 3]],
                [[3, 4], [3, 5]],
            ],
            "switches": [
                [1, 5, [[0, "swap"]]],
                [2, 6, [[1, "permanent"]]],
            ],
            "teleports": [
                [1, 3, 1, 1, 3, 1, 0],
            ],
        }
        self.board = parse_level(self.stage_data)
        set_active_board(self.board)

    def test_01_split_switch_teleports_to_predefined_positions(self):
        """
        - Nằm đè lên ô 'T' tại (1, 3) -> KHÔNG tách khối.
        - Đứng thẳng (STANDING) trên ô 'T' tại (1, 3) -> Tách thành 2 khối đơn tại (1, 1) và (3, 1).
        """
        lying_below = State(2, 2, Orientation.HORIZONTAL)
        lying_on_t = get_next_state(lying_below, Direction.UP, self.board)
        self.assertIsNotNone(lying_on_t)
        self.assertEqual(lying_on_t.orientation, Orientation.HORIZONTAL)
        self.assertFalse(lying_on_t.is_split())

        horiz_start = State(1, 1, Orientation.HORIZONTAL)
        split_state = get_next_state(horiz_start, Direction.RIGHT, self.board)
        self.assertIsNotNone(split_state)
        self.assertTrue(split_state.is_split())
        self.assertEqual(split_state.orientation, Orientation.SPLIT)
        self.assertEqual(split_state.get_occupied_cells(), [(1, 1), (3, 1)])
        self.assertEqual(split_state.active_cube, 0)

    def test_02_switch_cube_action_and_get_successors(self):
        """
        - Khi chưa tách khối: get_successors KHÔNG có 'SWITCH'.
        - Khi đã tách khối (SPLIT): get_successors CÓ hành động 'SWITCH', và gọi đổi khối
          sẽ chuyển quyền điều khiển từ khối 0 sang khối 1.
        """
        normal_state = State(1, 1, Orientation.STANDING)
        normal_actions = [act for act, _ in get_successors(self.board, normal_state)]
        self.assertNotIn(SWITCH_ACTION, normal_actions)
        self.assertIsNone(get_next_state(normal_state, SWITCH_ACTION, self.board))

        split_state = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=0)
        split_actions = dict(get_successors(self.board, split_state))
        self.assertIn(SWITCH_ACTION, split_actions)

        switched = split_actions[SWITCH_ACTION]
        self.assertEqual(switched.active_cube, 1)
        self.assertEqual(switched.get_active_cube_pos(), (3, 1))

        split_custom = State(1, 1, Orientation.SPLIT, split_pos=(2, 4), active_cube=1)
        moved_cube1 = get_next_state(split_custom, Direction.RIGHT, self.board)
        self.assertIsNotNone(moved_cube1)
        self.assertEqual(moved_cube1.get_occupied_cells(), [(1, 1), (2, 5)])

    def test_03_merge_cubes_vertical_and_horizontal(self):
        """
        Khi 2 khối đơn di chuyển tới 2 ô kề cạnh nhau:
          - Cùng cột (kề dọc) -> Tự động gộp thành Orientation.VERTICAL.
          - Cùng hàng (kề ngang) -> Tự động gộp thành Orientation.HORIZONTAL.
        """
        split_v = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=0)
        merged_v = get_next_state(split_v, Direction.DOWN, self.board)
        self.assertIsNotNone(merged_v)
        self.assertFalse(merged_v.is_split())
        self.assertEqual(merged_v.orientation, Orientation.VERTICAL)
        self.assertEqual(merged_v.get_occupied_cells(), [(2, 1), (3, 1)])

        split_h = State(2, 2, Orientation.SPLIT, split_pos=(2, 4), active_cube=0)
        merged_h = get_next_state(split_h, Direction.RIGHT, self.board)
        self.assertIsNotNone(merged_h)
        self.assertFalse(merged_h.is_split())
        self.assertEqual(merged_h.orientation, Orientation.HORIZONTAL)
        self.assertEqual(merged_h.get_occupied_cells(), [(2, 3), (2, 4)])

    def test_04_toggle_vs_permanent_bridges(self):
        """
        - Cầu 'a' (toggle / swap, điều khiển bởi Soft Switch 'O' tại (1, 5)):
          Bấm lần 1 -> Mở; Bấm lần 2 -> Đóng lại.
        - Cầu 'b' (permanent / on, điều khiển bởi Heavy Switch 'X' tại (2, 6)):
          Đứng thẳng lần 1 -> Mở; Đứng thẳng lần 2 -> VẪN MỞ (không bị đóng lại).
        """
        bridge_a = frozenset([(3, 2), (3, 3)])
        bridge_b = frozenset([(3, 4), (3, 5)])

        s_before_a = State(1, 4, Orientation.VERTICAL)
        s_press_a1 = get_next_state(s_before_a, Direction.RIGHT, self.board)
        self.assertEqual(s_press_a1.active_bridges, bridge_a)
        s_away_a = get_next_state(s_press_a1, Direction.LEFT, self.board)
        s_press_a2 = get_next_state(s_away_a, Direction.RIGHT, self.board)
        self.assertEqual(s_press_a2.active_bridges, frozenset())

        s_before_heavy = State(2, 4, Orientation.HORIZONTAL)
        s_press_h1 = get_next_state(s_before_heavy, Direction.RIGHT, self.board)
        self.assertEqual((s_press_h1.r, s_press_h1.c), (2, 6))
        self.assertEqual(s_press_h1.orientation, Orientation.STANDING)
        self.assertEqual(s_press_h1.active_bridges, bridge_b)

        s_away_h = get_next_state(s_press_h1, Direction.LEFT, self.board)
        s_press_h2 = get_next_state(s_away_h, Direction.RIGHT, self.board)
        self.assertEqual(s_press_h2.active_bridges, bridge_b)

    def test_05_single_cube_cannot_win_and_cannot_trigger_heavy_switch(self):
        """
        Đảm bảo luật của khối đơn (1x1x1) khi ở trạng thái SPLIT:
          1. Khối đơn đi vào ô đích H(3, 6) KHÔNG thắng màn chơi.
          2. Khối đơn đi vào Heavy Switch 'X'(2, 6) KHÔNG kích hoạt được cầu 'b'.
          3. Khối đơn đi vào Soft Switch 'O'(1, 5) KÍCH HOẠT được cầu 'a'.
        """
        split_near_goal = State(2, 6, Orientation.SPLIT, split_pos=(1, 1), active_cube=0)
        on_goal_split = get_next_state(split_near_goal, Direction.DOWN, self.board)
        self.assertIsNotNone(on_goal_split)
        self.assertEqual(on_goal_split.get_active_cube_pos(), self.board.end_pos)
        self.assertFalse(is_goal_state(self.board, on_goal_split))

        split_near_heavy = State(2, 5, Orientation.SPLIT, split_pos=(1, 1), active_cube=0)
        on_heavy_split = get_next_state(split_near_heavy, Direction.RIGHT, self.board)
        self.assertIsNotNone(on_heavy_split)
        self.assertEqual(on_heavy_split.get_active_cube_pos(), (2, 6))
        self.assertEqual(on_heavy_split.active_bridges, frozenset())

        split_near_soft = State(1, 4, Orientation.SPLIT, split_pos=(2, 1), active_cube=0)
        on_soft_split = get_next_state(split_near_soft, Direction.RIGHT, self.board)
        self.assertIsNotNone(on_soft_split)
        self.assertEqual(on_soft_split.active_bridges, frozenset([(3, 2), (3, 3)]))

    def test_06_full_game_session_split_switch_merge_and_win(self):
        """
        Kiểm tra luồng chơi hoàn chỉnh thông qua class Game:
        Tách khối tại T -> Khối đơn đè lên đích nhưng chưa thắng -> Đổi khối (SWITCH)
        -> Gộp 2 khối đơn lại thành 1x1x2 -> Lăn dựng đứng vào đích H -> Thắng (GameStatus.WON).
        """
        board = parse_level(
            {
                "grid": [
                    "       ",
                    " S.T.H ",
                    " ..... ",
                    " ..... ",
                    "       ",
                ],
                "teleports": [
                    [1, 3, 2, 4, 2, 2, 0],
                ],
            }
        )
        game = Game(board)
        self.assertEqual(game.status, GameStatus.PLAYING)

        for act in ["DOWN", "RIGHT", "RIGHT", "UP"]:
            outcome = game.move(act)
            self.assertIsNotNone(outcome)
            self.assertEqual(outcome.result, MoveResult.OK)

        self.assertTrue(game.state.is_split())
        self.assertEqual(game.state.get_occupied_cells(), [(2, 4), (2, 2)])

        self.assertEqual(game.move("RIGHT").result, MoveResult.OK)
        self.assertEqual(game.move("UP").result, MoveResult.OK)
        self.assertEqual(game.state.get_active_cube_pos(), (1, 5))
        self.assertFalse(game.is_won())
        self.assertEqual(game.status, GameStatus.PLAYING)

        self.assertEqual(game.move("DOWN").result, MoveResult.OK)
        self.assertEqual(game.move("LEFT").result, MoveResult.OK)

        self.assertEqual(game.move("SWITCH").result, MoveResult.OK)
        self.assertEqual(game.state.active_cube, 1)

        self.assertEqual(game.move("RIGHT").result, MoveResult.OK)
        self.assertFalse(game.state.is_split())
        self.assertEqual(game.state.orientation, Orientation.HORIZONTAL)
        self.assertEqual(game.state.get_occupied_cells(), [(2, 3), (2, 4)])

        self.assertTrue(game.undo())
        self.assertTrue(game.state.is_split())

        for act in ["DOWN", "RIGHT", "RIGHT", "RIGHT"]:
            self.assertEqual(game.move(act).result, MoveResult.OK)

        self.assertFalse(game.state.is_split())
        self.assertEqual(game.state.orientation, Orientation.VERTICAL)
        self.assertEqual(game.state.get_occupied_cells(), [(2, 5), (3, 5)])

        self.assertEqual(game.move("UP").result, MoveResult.OK)
        self.assertTrue(game.is_won())
        self.assertEqual(game.status, GameStatus.WON)

    def test_07_coolmath_stage_08_teleport_and_win(self):
        """Kiểm tra giải trực tiếp màn Stage 08 (cổng tách khối T) từ coolmath.json."""
        stage_08 = load_coolmath_stage(8)
        game = Game(stage_08)
        solution = [
            "RIGHT",
            "RIGHT",
            "DOWN",
            "DOWN",
            "DOWN",
            "RIGHT",
            "RIGHT",
            "SWITCH",
            "UP",
            "UP",
            "UP",
            "RIGHT",
            "RIGHT",
        ]
        game.apply_solution(solution)
        self.assertTrue(game.is_won())
        self.assertEqual(game.status, GameStatus.WON)


if __name__ == "__main__":
    unittest.main()
