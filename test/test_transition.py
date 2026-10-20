# tests/test_transition.py
import unittest
from core.block import Direction
from core.board import TileType
from core.game import Game, GameStatus, MoveResult
from core.map_loader import parse_level
from core.state import Orientation, State, state_key
from core.transition import (
    get_next_state,
    is_goal_state,
    is_on_void,
    is_out_of_bounds,
    is_valid_move,
    roll_block,
    set_active_board,
)


class TestBloxorzTransition(unittest.TestCase):
    """
    Bộ kiểm thử toàn diện theo yêu cầu bảng phân công (tests/test_transition.py):
      1. 12 phép lăn (3 tư thế STANDING, HORIZONTAL, VERTICAL x 4 hướng UP, DOWN, LEFT, RIGHT).
      2. Rơi ra ngoài biên (out of board) và rơi vào ô trống (VOID).
      3. Chỉ thắng khi đứng thẳng (STANDING) trên ô đích (T / end_pos).
      4. Ô gạch mỏng 'O' (FRAGILE): đứng thẳng thì rơi (vỡ gạch), nằm ngang/dọc thì an toàn.
      5. Công tắc Soft Switch ('A'..'Z') và Heavy Switch ('0'..'9').
      6. Cầu (Bridge 'a'..'z') khi đang đóng và khi đã mở (kể cả trường hợp cầu sập dưới khối).
    """

    def setUp(self):
        """
        Khởi tạo 2 bản đồ phục vụ kiểm thử:
          - open_board (7x7 toàn gạch 'F'): dùng để kiểm thử trọn vẹn 12 phép lăn tại tâm (2, 2).
          - board (5x8): tích hợp VOID ('.'), FRAGILE ('O'), Soft Switch ('A'),
            Heavy Switch ('0'), Cầu ('a', 'b') và Đích ('T').
        """
        self.open_board = parse_level([
            "FFFFFFF",
            "FSFFFFF",
            "FFFFFFF",
            "FFFFFFF",
            "FFFFFFF",
            "FFFFFTF",
            "FFFFFFF",
        ])

        self.board = parse_level([
            "........",
            ".SFOFAF.",
            ".FFFFF0.",
            ".FaabbT.",
            "........",
            "---",
            "BRIDGE id=a priority=1 initial=closed",
            "BRIDGE id=b priority=2 initial=closed",
            "SWITCH id=A targets=a:toggle",
            "SWITCH id=0 targets=b:toggle",
        ])
        set_active_board(self.board)

    # =========================================================================
    # 1. KIỂM THỬ 12 PHÉP LĂN CƠ BẢN (3 ORIENTATIONS x 4 DIRECTIONS)
    # =========================================================================
    def test_01_standing_4_transitions(self):
        """Kiểm tra 4 phép lăn (UP, DOWN, LEFT, RIGHT) khi khối đang STANDING tại (2, 2)."""
        s = State(2, 2, Orientation.STANDING)

        # Lăn UP: ngả dọc lên trên, chiếm (0, 2) và (1, 2) -> neo tại (0, 2)
        self.assertEqual(
            get_next_state(s, Direction.UP, self.open_board),
            State(0, 2, Orientation.VERTICAL),
        )
        # Lăn DOWN: ngả dọc xuống dưới, chiếm (3, 2) và (4, 2) -> neo tại (3, 2)
        self.assertEqual(
            get_next_state(s, Direction.DOWN, self.open_board),
            State(3, 2, Orientation.VERTICAL),
        )
        # Lăn LEFT: ngả ngang sang trái, chiếm (2, 0) và (2, 1) -> neo tại (2, 0)
        self.assertEqual(
            get_next_state(s, Direction.LEFT, self.open_board),
            State(2, 0, Orientation.HORIZONTAL),
        )
        # Lăn RIGHT: ngả ngang sang phải, chiếm (2, 3) và (2, 4) -> neo tại (2, 3)
        self.assertEqual(
            get_next_state(s, Direction.RIGHT, self.open_board),
            State(2, 3, Orientation.HORIZONTAL),
        )

    def test_02_horizontal_4_transitions(self):
        """Kiểm tra 4 phép lăn khi khối đang HORIZONTAL tại (2, 2) [chiếm (2, 2) và (2, 3)]."""
        s = State(2, 2, Orientation.HORIZONTAL)

        # Lăn UP: lăn ngang lên 1 hàng -> HORIZONTAL tại (1, 2)
        self.assertEqual(
            get_next_state(s, Direction.UP, self.open_board),
            State(1, 2, Orientation.HORIZONTAL),
        )
        # Lăn DOWN: lăn ngang xuống 1 hàng -> HORIZONTAL tại (3, 2)
        self.assertEqual(
            get_next_state(s, Direction.DOWN, self.open_board),
            State(3, 2, Orientation.HORIZONTAL),
        )
        # Lăn LEFT: dựng đứng dậy ở ô bên trái -> STANDING tại (2, 1)
        self.assertEqual(
            get_next_state(s, Direction.LEFT, self.open_board),
            State(2, 1, Orientation.STANDING),
        )
        # Lăn RIGHT: dựng đứng dậy ở ô bên phải -> STANDING tại (2, 4)
        self.assertEqual(
            get_next_state(s, Direction.RIGHT, self.open_board),
            State(2, 4, Orientation.STANDING),
        )

    def test_03_vertical_4_transitions(self):
        """Kiểm tra 4 phép lăn khi khối đang VERTICAL tại (2, 2) [chiếm (2, 2) và (3, 2)]."""
        s = State(2, 2, Orientation.VERTICAL)

        # Lăn UP: dựng đứng dậy ở ô phía trên -> STANDING tại (1, 2)
        self.assertEqual(
            get_next_state(s, Direction.UP, self.open_board),
            State(1, 2, Orientation.STANDING),
        )
        # Lăn DOWN: dựng đứng dậy ở ô phía dưới -> STANDING tại (4, 2)
        self.assertEqual(
            get_next_state(s, Direction.DOWN, self.open_board),
            State(4, 2, Orientation.STANDING),
        )
        # Lăn LEFT: lăn dọc sang trái 1 cột -> VERTICAL tại (2, 1)
        self.assertEqual(
            get_next_state(s, Direction.LEFT, self.open_board),
            State(2, 1, Orientation.VERTICAL),
        )
        # Lăn RIGHT: lăn dọc sang phải 1 cột -> VERTICAL tại (2, 3)
        self.assertEqual(
            get_next_state(s, Direction.RIGHT, self.open_board),
            State(2, 3, Orientation.VERTICAL),
        )

    # =========================================================================
    # 2. KIỂM THỬ RƠI RA NGOÀI BÀN CỜ (OUT OF BOARD) VÀ RƠI VÀO VOID
    # =========================================================================
    def test_04_fall_out_of_board_bounds(self):
        """Kiểm tra khối lăn vượt ra ngoài kích thước ma trận bàn cờ (5x8)."""
        start_state = State(1, 1, Orientation.STANDING)

        # Đứng tại (1, 1) lăn UP -> đòi chiếm (-1, 1) và (0, 1) -> (-1, 1) vượt biên trên
        raw_up = roll_block(start_state, Direction.UP)
        self.assertTrue(is_out_of_bounds(self.board, raw_up))
        self.assertFalse(is_valid_move(self.board, raw_up))
        self.assertIsNone(get_next_state(start_state, Direction.UP, board=self.board))

        # Đứng tại (1, 1) lăn LEFT -> đòi chiếm (1, -1) và (1, 0) -> (1, -1) vượt biên trái
        raw_left = roll_block(start_state, Direction.LEFT)
        self.assertTrue(is_out_of_bounds(self.board, raw_left))
        self.assertIsNone(get_next_state(start_state, Direction.LEFT, board=self.board))

    def test_05_fall_into_void_full_and_partial(self):
        """Kiểm tra khối rơi hoàn toàn vào VOID hoặc nửa trên gạch - nửa trên VOID."""
        # 1. Rơi hoàn toàn vào VOID: Đang VERTICAL tại (1, 1) [chiếm (1,1) và (2,1)],
        # lăn LEFT sẽ sang (1, 0) và (2, 0) đều là ô '.' (VOID) nằm trong biên ma trận
        s_vert = State(1, 1, Orientation.VERTICAL)
        raw_void = roll_block(s_vert, Direction.LEFT)
        self.assertFalse(is_out_of_bounds(self.board, raw_void))
        self.assertTrue(is_on_void(self.board, raw_void))
        self.assertFalse(is_valid_move(self.board, raw_void))
        self.assertIsNone(get_next_state(s_vert, Direction.LEFT, board=self.board))

        # 2. Nửa trong nửa ngoài (Partial void): HORIZONTAL tại (1, 6) chiếm (1, 6)='F' và (1, 7)='.'
        half_void = State(1, 6, Orientation.HORIZONTAL)
        self.assertTrue(is_on_void(self.board, half_void))
        self.assertFalse(is_valid_move(self.board, half_void))

    # =========================================================================
    # 3. KIỂM THỬ ĐIỀU KIỆN THẮNG: CHỈ THẮNG KHI ĐỨNG THẲNG TRÊN ĐÍCH (T)
    # =========================================================================
    def test_06_win_only_when_standing_on_goal(self):
        """Chỉ thắng khi STANDING tại đích T(3, 6). Nằm ngang/dọc đè lên T chưa thắng."""
        goal_r, goal_c = self.board.end_pos
        self.assertEqual((goal_r, goal_c), (3, 6))

        # Đứng thẳng trên đích -> Thắng (True)
        win_state = State(goal_r, goal_c, Orientation.STANDING)
        self.assertTrue(is_goal_state(self.board, win_state))

        # Nằm ngang hoặc nằm dọc đè qua ô (3, 6) -> Chưa thắng (False)
        lying_states = [
            State(3, 5, Orientation.HORIZONTAL),  # Chiếm (3, 5) và (3, 6)
            State(3, 6, Orientation.HORIZONTAL),  # Chiếm (3, 6) và (3, 7)
            State(2, 6, Orientation.VERTICAL),    # Chiếm (2, 6) và (3, 6)
            State(3, 6, Orientation.VERTICAL),    # Chiếm (3, 6) và (4, 6)
        ]
        for st in lying_states:
            self.assertIn((goal_r, goal_c), st.get_occupied_cells())
            self.assertFalse(is_goal_state(self.board, st))

    # =========================================================================
    # 4. KIỂM THỬ Ô GẠCH MỎNG 'O' (FRAGILE): ĐỨNG THÌ RƠI, NẰM THÌ AN TOÀN
    # =========================================================================
    def test_07_fragile_tile_standing_breaks_lying_safe(self):
        """
        Ô 'O' (TileType.FRAGILE) tại tọa độ (1, 3):
          - Đứng thẳng (STANDING) tại (1, 3) -> Gạch vỡ, nước đi không hợp lệ (None).
          - Nằm ngang (HORIZONTAL) tại (1, 2)-(1, 3) hoặc nằm dọc (VERTICAL) tại (1, 3)-(2, 3) -> An toàn.
        """
        self.assertEqual(self.board.get_tile(1, 3), TileType.FRAGILE)

        # Từ (1, 1) HORIZONTAL [chiếm (1,1) và (1,2)], nếu lăn RIGHT sẽ STANDING tại (1, 3)='O' -> Bị chặn (None)
        horiz_before_o = State(1, 1, Orientation.HORIZONTAL)
        self.assertIsNone(get_next_state(horiz_before_o, Direction.RIGHT, board=self.board))
        self.assertFalse(is_valid_move(self.board, State(1, 3, Orientation.STANDING)))

        # Từ (2, 2) HORIZONTAL [chiếm (2,2) và (2,3)], lăn UP sẽ HORIZONTAL tại (1, 2)-(1, 3) -> An toàn!
        horiz_below = State(2, 2, Orientation.HORIZONTAL)
        safe_horiz = get_next_state(horiz_below, Direction.UP, board=self.board)
        self.assertIsNotNone(safe_horiz)
        self.assertEqual(safe_horiz, State(1, 2, Orientation.HORIZONTAL))
        self.assertTrue(is_valid_move(self.board, safe_horiz))

        # Nằm dọc đè lên (1, 3) và (2, 3) -> An toàn!
        safe_vert = State(1, 3, Orientation.VERTICAL)
        self.assertTrue(is_valid_move(self.board, safe_vert))

    # =========================================================================
    # 5. KIỂM THỬ CÔNG TẮC SOFT SWITCH ('A') VÀ HEAVY SWITCH ('0')
    # =========================================================================
    def test_08_soft_switch_triggers_both_standing_and_lying(self):
        """
        Soft Switch 'A' tại (1, 5) điều khiển cầu 'a' [(3, 2), (3, 3)]:
          - Kích hoạt ngay cả khi khối NẰM đè lên (1, 5).
          - Kích hoạt khi khối ĐỨNG THẲNG tại (1, 5).
        """
        bridge_a_cells = frozenset([(3, 2), (3, 3)])

        # 1. Nằm dọc tại (1, 4)-(2, 4) lăn RIGHT sang VERTICAL tại (1, 5)-(2, 5) -> Chạm 'A' ở tư thế nằm -> Cầu 'a' MỞ!
        s_vert = State(1, 4, Orientation.VERTICAL)
        after_lying_on_a = get_next_state(s_vert, Direction.RIGHT, board=self.board)
        self.assertIsNotNone(after_lying_on_a)
        self.assertEqual(after_lying_on_a.active_bridges, bridge_a_cells)

        # 2. Đứng thẳng vào 'A' tại (1, 5): từ HORIZONTAL tại (1, 3)-(1, 4) lăn RIGHT -> STANDING tại (1, 5)
        # Vì cầu 'a' đang mở (từ bước trên), kích hoạt toggle lần nữa sẽ ĐÓNG cầu 'a'
        s_horiz_with_open_a = State(1, 3, Orientation.HORIZONTAL, active_bridges=bridge_a_cells)
        after_standing_on_a = get_next_state(s_horiz_with_open_a, Direction.RIGHT, board=self.board)
        self.assertIsNotNone(after_standing_on_a)
        self.assertEqual(after_standing_on_a.orientation, Orientation.STANDING)
        self.assertEqual(after_standing_on_a.active_bridges, frozenset())

    def test_09_heavy_switch_triggers_only_when_standing(self):
        """
        Heavy Switch '0' tại (2, 6) điều khiển cầu 'b' [(3, 4), (3, 5)]:
          - Nằm ngang/dọc đè lên (2, 6) -> KHÔNG kích hoạt.
          - Đứng thẳng (STANDING) tại (2, 6) -> Kích hoạt mở/đóng cầu 'b'.
        """
        bridge_b_cells = frozenset([(3, 4), (3, 5)])

        # 1. Nằm ngang tại (1, 5)-(1, 6) lăn DOWN sang HORIZONTAL tại (2, 5)-(2, 6)
        # Dù một nửa khối đè lên (2, 6)='0' nhưng đang HORIZONTAL nên cầu 'b' vẫn ĐÓNG
        s_horiz = State(1, 5, Orientation.HORIZONTAL)
        after_lying_on_0 = get_next_state(s_horiz, Direction.DOWN, board=self.board)
        self.assertIsNotNone(after_lying_on_0)
        self.assertEqual(after_lying_on_0.orientation, Orientation.HORIZONTAL)
        self.assertEqual(after_lying_on_0.active_bridges, frozenset())

        # 2. Đứng thẳng vào (2, 6)='0': từ HORIZONTAL tại (2, 4)-(2, 5) lăn RIGHT -> STANDING tại (2, 6)
        # Đủ trọng lượng kích hoạt Heavy Switch '0' -> Cầu 'b' MỞ!
        s_before_0 = State(2, 4, Orientation.HORIZONTAL)
        after_standing_on_0 = get_next_state(s_before_0, Direction.RIGHT, board=self.board)
        self.assertIsNotNone(after_standing_on_0)
        self.assertEqual(after_standing_on_0.orientation, Orientation.STANDING)
        self.assertEqual((after_standing_on_0.r, after_standing_on_0.c), (2, 6))
        self.assertEqual(after_standing_on_0.active_bridges, bridge_b_cells)

    # =========================================================================
    # 6. KIỂM THỬ CẦU ĐÓNG VÀ CẦU MỞ (BRIDGE CLOSED & OPEN)
    # =========================================================================
    def test_10_bridge_closed_blocks_and_open_allows(self):
        """
        Kiểm tra di chuyển qua cầu 'a' [(3, 2), (3, 3)] và cầu 'b' [(3, 4), (3, 5)]:
          - Khi cầu đóng: khối lăn lên cầu sẽ bị rơi (trả về None).
          - Khi cầu mở: khối lăn lên cầu hợp lệ.
          - Khi công tắc đóng sập cầu ngay dưới chân khối: khối bị rơi (trả về None).
        """
        bridge_a_cells = frozenset([(3, 2), (3, 3)])
        bridge_b_cells = frozenset([(3, 4), (3, 5)])
        all_bridges = bridge_a_cells | bridge_b_cells

        # 1. Cầu 'a' đang đóng: từ HORIZONTAL tại (2, 2)-(2, 3) lăn DOWN xuống (3, 2)-(3, 3) -> Rơi (None)
        s_above_bridge_closed = State(2, 2, Orientation.HORIZONTAL, active_bridges=frozenset())
        self.assertIsNone(get_next_state(s_above_bridge_closed, Direction.DOWN, board=self.board))
        self.assertFalse(is_valid_move(self.board, State(3, 2, Orientation.HORIZONTAL)))

        # 2. Cầu 'a' đang mở: từ HORIZONTAL tại (2, 2)-(2, 3) lăn DOWN xuống (3, 2)-(3, 3) -> Thành công!
        s_above_bridge_open = State(2, 2, Orientation.HORIZONTAL, active_bridges=bridge_a_cells)
        on_bridge_a = get_next_state(s_above_bridge_open, Direction.DOWN, board=self.board)
        self.assertIsNotNone(on_bridge_a)
        self.assertEqual(
            on_bridge_a,
            State(3, 2, Orientation.HORIZONTAL, active_bridges=bridge_a_cells),
        )

        # 3. Cầu 'a' mở nhưng cầu 'b' còn đóng: từ (3, 2)-(3, 3) lăn RIGHT sang STANDING tại (3, 4) -> Rơi (None)
        self.assertIsNone(get_next_state(on_bridge_a, Direction.RIGHT, board=self.board))

        # 4. Cả cầu 'a' và 'b' đều mở: từ (3, 3)-(3, 4) HORIZONTAL lăn RIGHT -> STANDING tại đích T(3, 6) sau 2 bước
        s_all_open = State(3, 2, Orientation.HORIZONTAL, active_bridges=all_bridges)
        step1 = get_next_state(s_all_open, Direction.RIGHT, board=self.board)  # STANDING tại (3, 4)
        self.assertIsNotNone(step1)
        self.assertEqual((step1.r, step1.c, step1.orientation), (3, 4, Orientation.STANDING))

        # 5. Trường hợp công tắc đóng cầu ngay dưới chân khối:
        # Bản đồ có công tắc mềm 'A' tại (1, 2) cạnh cầu 'a' tại (1, 3) đang mở.
        # Khi khối nằm ngang đè lên cả 'A'(1, 2) và 'a'(1, 3), công tắc 'A' đóng cầu 'a' làm khối rơi!
        trap_board = parse_level([
            "......",
            ".SAaT.",
            ".FFFF.",
            "......",
        ])
        s_before_trap = State(2, 2, Orientation.HORIZONTAL, active_bridges=frozenset([(1, 3)]))
        self.assertIsNone(get_next_state(s_before_trap, Direction.UP, board=trap_board))

    # =========================================================================
    # 7. KIỂM THỬ BỔ SUNG: Ô TÁCH KHỐI ('U') & VÒNG ĐỜI GAME
    # =========================================================================
    def test_11_split_switch_and_game_lifecycle(self):
        """Kiểm tra tách khối trên ô 'U' (SPLIT_SWITCH), đổi khối (SWITCH), gộp khối và class Game."""
        split_board = parse_level([
            "........",
            ".SFFUFT.",
            ".FFFFFF.",
            "........",
        ])
        game = Game(split_board)
        self.assertEqual(game.status, GameStatus.PLAYING)

        # Lăn RIGHT 2 lần từ (1, 1) để đứng thẳng trên ô 'U' tại (1, 4) -> Tách thành 2 khối đơn tại (1, 3) và (1, 5)
        game.move(Direction.RIGHT)
        outcome = game.move(Direction.RIGHT)
        self.assertEqual(outcome.result, MoveResult.OK)
        self.assertTrue(game.state.is_split())
        self.assertEqual(set(game.state.get_occupied_cells()), {(1, 3), (1, 5)})

        # Đổi quyền điều khiển sang khối đơn thứ 2 và di chuyển lại gần để tự động gộp thành khối 1x1x2
        game.switch_cube()
        self.assertEqual(game.state.active_cube, 1)
        game.move(Direction.LEFT)  # Khối (1, 5) sang (1, 4), kề với (1, 3) -> Tự động gộp thành HORIZONTAL (1, 3)-(1, 4)
        self.assertFalse(game.state.is_split())
        self.assertEqual(game.state.orientation, Orientation.HORIZONTAL)
        self.assertEqual(state_key(game.state)[:3], (1, 3, "HORIZONTAL"))


if __name__ == "__main__":
    unittest.main()