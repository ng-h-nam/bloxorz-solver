"""
Bộ kiểm thử toàn diện cho các thuật toán giải bài toán Bloxorz:
- BFS (Breadth-First Search)
- DFS (Depth-First Search)
- UCS (Uniform-Cost Search)
- Cơ chế Replay và xác thực đường đi
- Giới hạn tìm kiếm (node_limit, time_limit)
- Tối ưu hóa băm trạng thái (State Hashing Optimization)
"""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.base_solver import replay_path
from algorithms.bfs import BFSSolver
from algorithms.dfs import DFSSolver
from algorithms.heuristic import weighted_switch_cost
from algorithms.ucs import UCSSolver
from core.board import Board, TileType
from core.map_loader import load_level
from core.state import Orientation, State


def _build_unsolvable_board() -> Board:
    """Tạo một bản đồ nhân tạo không có đường tới đích để test trường hợp vô nghiệm."""
    grid = [
        [TileType.FLOOR, TileType.FLOOR, TileType.VOID, TileType.GOAL],
        [TileType.FLOOR, TileType.FLOOR, TileType.VOID, TileType.VOID],
    ]
    return Board(grid=grid, start_pos=(0, 0), end_pos=(0, 3))


class TestBFSSolver(unittest.TestCase):
    """Kiểm thử thuật toán Breadth-First Search (BFS)."""

    def setUp(self) -> None:
        self.map_path = PROJECT_ROOT / "data" / "maps" / "stage_01.txt"
        self.board = load_level(str(self.map_path))

    def test_bfs_solves_stage_01(self) -> None:
        """BFS giải thành công Stage 01 với 7 bước đi tối ưu."""
        solver = BFSSolver(self.board)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.status, "SOLVED")
        self.assertEqual(result.cost, 7)
        self.assertGreater(result.nodes_explored, 0)
        self.assertGreater(result.max_frontier_size, 0)

        # Phát lại lời giải trên core
        valid, _, msg = solver.replay(result.actions)
        self.assertTrue(valid, f"Phát lại thất bại: {msg}")

    def test_bfs_already_at_goal(self) -> None:
        """BFS xuất phát ngay tại ô đích."""
        goal_state = State(
            r=self.board.end_pos[0],
            c=self.board.end_pos[1],
            orientation=Orientation.STANDING,
            active_bridges=self.board.initial_active_bridges,
        )
        solver = BFSSolver(self.board, initial_state=goal_state)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.cost, 0)
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.nodes_explored, 0)
        self.assertEqual(result.status, "SOLVED")

    def test_bfs_node_limit(self) -> None:
        """BFS dừng khi chạm node_limit và ghi nhận trạng thái NODE_LIMIT_EXCEEDED."""
        solver = BFSSolver(self.board, node_limit=3)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NODE_LIMIT_EXCEEDED")
        self.assertGreaterEqual(result.nodes_explored, 3)

    def test_bfs_time_limit(self) -> None:
        """BFS dừng khi chạm time_limit và ghi nhận trạng thái TIME_LIMIT_EXCEEDED."""
        solver = BFSSolver(self.board, time_limit=1e-7)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertIn(result.status, ("TIME_LIMIT_EXCEEDED", "NODE_LIMIT_EXCEEDED"))

    def test_bfs_unsolvable_map(self) -> None:
        """BFS trả về NO_SOLUTION khi bàn cờ không có đường tới đích."""
        board = _build_unsolvable_board()
        solver = BFSSolver(board)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NO_SOLUTION")


class TestDFSSolver(unittest.TestCase):
    """Kiểm thử thuật toán Depth-First Search (DFS)."""

    def setUp(self) -> None:
        self.map_path = PROJECT_ROOT / "data" / "maps" / "stage_01.txt"
        self.board = load_level(str(self.map_path))

    def test_dfs_solves_stage_01(self) -> None:
        """DFS tìm được nghiệm hợp lệ trên Stage 01."""
        solver = DFSSolver(self.board, max_depth=100)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.status, "SOLVED")
        self.assertGreater(result.cost, 0)

        # Phát lại lời giải để đảm bảo tính đúng đắn của đường đi
        valid, _, msg = solver.replay(result.actions)
        self.assertTrue(valid, f"Phát lại DFS thất bại: {msg}")

    def test_dfs_already_at_goal(self) -> None:
        """DFS xuất phát ngay tại ô đích."""
        goal_state = State(
            r=self.board.end_pos[0],
            c=self.board.end_pos[1],
            orientation=Orientation.STANDING,
            active_bridges=self.board.initial_active_bridges,
        )
        solver = DFSSolver(self.board, initial_state=goal_state)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.cost, 0)
        self.assertEqual(len(result.actions), 0)

    def test_dfs_max_depth_cutoff(self) -> None:
        """DFS cắt tỉa khi vượt quá max_depth."""
        # Stage 01 cần ít nhất 7 bước, nếu max_depth = 3 sẽ không thể tìm thấy nghiệm
        solver = DFSSolver(self.board, max_depth=3)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NO_SOLUTION")

    def test_dfs_node_limit(self) -> None:
        """DFS dừng khi chạm node_limit."""
        solver = DFSSolver(self.board, node_limit=5)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NODE_LIMIT_EXCEEDED")


class TestUCSSolver(unittest.TestCase):
    """Kiểm thử thuật toán Uniform-Cost Search (UCS)."""

    def setUp(self) -> None:
        self.map_path = PROJECT_ROOT / "data" / "maps" / "stage_01.txt"
        self.board = load_level(str(self.map_path))

    def test_ucs_solves_stage_01_optimally(self) -> None:
        """UCS giải tối ưu Stage 01 với 7 bước đi."""
        solver = UCSSolver(self.board)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.status, "SOLVED")
        self.assertEqual(result.cost, 7)
        self.assertEqual(len(result.actions), 7)

        valid, _, msg = solver.replay(result.actions)
        self.assertTrue(valid, f"Phát lại UCS thất bại: {msg}")

    def test_ucs_matches_bfs_optimality(self) -> None:
        """UCS với uniform_cost luôn tìm được chi phí tối ưu trùng khớp 100% với BFS."""
        for stage_idx in (1, 2, 3):
            path = PROJECT_ROOT / "data" / "maps" / f"stage_{stage_idx:02d}.txt"
            board = load_level(str(path))

            bfs_res = BFSSolver(board).solve()
            ucs_res = UCSSolver(board).solve()

            self.assertTrue(bfs_res.is_solved)
            self.assertTrue(ucs_res.is_solved)
            self.assertEqual(
                bfs_res.cost,
                ucs_res.cost,
                f"Lệch chi phí tại Stage {stage_idx}: BFS={bfs_res.cost}, UCS={ucs_res.cost}",
            )

    def test_ucs_already_at_goal(self) -> None:
        """UCS xuất phát ngay tại ô đích."""
        goal_state = State(
            r=self.board.end_pos[0],
            c=self.board.end_pos[1],
            orientation=Orientation.STANDING,
            active_bridges=self.board.initial_active_bridges,
        )
        solver = UCSSolver(self.board, initial_state=goal_state)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.cost, 0)
        self.assertEqual(len(result.actions), 0)

    def test_ucs_node_limit(self) -> None:
        """UCS dừng khi chạm node_limit."""
        solver = UCSSolver(self.board, node_limit=4)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NODE_LIMIT_EXCEEDED")

    def test_ucs_time_limit(self) -> None:
        """UCS dừng khi chạm time_limit."""
        solver = UCSSolver(self.board, time_limit=1e-7)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertIn(result.status, ("TIME_LIMIT_EXCEEDED", "NODE_LIMIT_EXCEEDED"))

    def test_ucs_unsolvable_map(self) -> None:
        """UCS trả về NO_SOLUTION khi bàn cờ không có đường tới đích."""
        board = _build_unsolvable_board()
        solver = UCSSolver(board)
        result = solver.solve()

        self.assertFalse(result.is_solved)
        self.assertEqual(result.status, "NO_SOLUTION")

    def test_ucs_weighted_cost_function(self) -> None:
        """UCS hỗ trợ hàm chi phí tùy biến (weighted_switch_cost)."""
        solver = UCSSolver(self.board, cost_fn=weighted_switch_cost)
        result = solver.solve()

        self.assertTrue(result.is_solved)
        self.assertEqual(result.status, "SOLVED")
        self.assertGreaterEqual(result.cost, 7)


class TestSolveResultAndReplay(unittest.TestCase):
    """Kiểm thử các thuộc tính của SolveResult và hàm replay_path."""

    def test_solve_result_properties(self) -> None:
        board = load_level(str(PROJECT_ROOT / "data" / "maps" / "stage_01.txt"))
        solver = BFSSolver(board)
        res = solver.solve()

        self.assertTrue(res.found)
        self.assertEqual(res.nodes_expanded, res.nodes_explored)
        self.assertGreater(res.memory_kb, 0)
        self.assertGreater(res.memory_mb, 0)
        self.assertGreaterEqual(res.time_taken, 0)
        self.assertIn("SOLVED", res.summary())
        self.assertIn("RIGHT", res.get_action_sequence_str())

    def test_replay_path_invalid_move(self) -> None:
        """Replay thất bại khi khối lăn ra khỏi bản đồ."""
        board = load_level(str(PROJECT_ROOT / "data" / "maps" / "stage_01.txt"))
        # Từ (1, 1) lật LEFT sẽ rơi ra ngoài vực
        success, states, msg = replay_path(board, ["LEFT"])
        self.assertFalse(success)
        self.assertIn("thất bại", msg)


class TestStateHashingOptimization(unittest.TestCase):
    """Kiểm thử tính đúng đắn của tối ưu hóa băm trạng thái State."""

    def test_state_hash_and_equality(self) -> None:
        s1 = State(1, 2, Orientation.STANDING, frozenset([(3, 4)]))
        s2 = State(1, 2, Orientation.STANDING, frozenset([(3, 4)]))
        s3 = State(1, 2, Orientation.HORIZONTAL, frozenset([(3, 4)]))

        self.assertEqual(s1, s2)
        self.assertNotEqual(s1, s3)
        self.assertEqual(hash(s1), hash(s2))
        self.assertEqual(s1.to_key(), s2.to_key())

        state_set = {s1}
        self.assertIn(s2, state_set)
        self.assertNotIn(s3, state_set)

    def test_state_split_hashing(self) -> None:
        s_split1 = State(
            r=2,
            c=3,
            orientation=Orientation.SPLIT,
            split_pos=(5, 6),
            active_cube=0,
        )
        s_split2 = State(
            r=2,
            c=3,
            orientation=Orientation.SPLIT,
            split_pos=(5, 6),
            active_cube=0,
        )
        s_split_other_cube = State(
            r=2,
            c=3,
            orientation=Orientation.SPLIT,
            split_pos=(5, 6),
            active_cube=1,
        )

        self.assertEqual(s_split1, s_split2)
        self.assertNotEqual(s_split1, s_split_other_cube)
        self.assertEqual(hash(s_split1), hash(s_split2))


if __name__ == "__main__":
    unittest.main()
