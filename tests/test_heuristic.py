"""
Bộ kiểm thử tính chấp nhận được (Admissibility) của hàm Heuristic và thuật toán A*.

Khớp 100% với Báo cáo kỹ thuật:
- Kiểm tra h(s) <= h*(s) ở mọi trạng thái của các map chuẩn (stage_01..stage_04).
- Khối đứng tại ô đích có h(s) = 0.
- Kiểm tra các quy tắc phạt tư thế:
  + d_min == 0 & nằm: phạt +2
  + d_min == 1 & đứng: phạt +1
  + d_min == 1 & nằm: phạt 0 (tránh vi phạm cận h* = 1)
- Kiểm tra công thức SPLIT: h_split = max(d_merge, d_goal).
- Thuật toán A* giải ra độ dài đường đi tối ưu trùng khớp 100% với BFS trên toàn bộ các bản đồ.
"""

from pathlib import Path
import unittest

from algorithms.astar import AStarSolver
from algorithms.bfs import BFSSolver
from algorithms.heuristic import (
    bloxorz_advanced_heuristic,
    compute_orientation_penalty,
    get_representative_point,
    manhattan_heuristic,
    split_state_heuristic,
    uniform_cost,
    verify_heuristic_admissibility,
    weighted_switch_cost,
)
from core.map_loader import load_level
from core.state import Orientation, State

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_LEGACY_MAP_ALIASES = {
    "level0.txt": "stage_01.txt",
    "level1.txt": "stage_02.txt",
    "level2.txt": "stage_03.txt",
    "level3.txt": "stage_04.txt",
}


def _resolve_map_path(map_filename: str) -> Path:
    direct = PROJECT_ROOT / "data" / "maps" / map_filename
    if direct.exists():
        return direct
    alias = _LEGACY_MAP_ALIASES.get(map_filename)
    if alias:
        return PROJECT_ROOT / "data" / "maps" / alias
    return direct


class TestHeuristicAdmissibilitySmallMaps(unittest.TestCase):
    """
    Kiểm tra cốt lõi: h(s) <= h*(s) trên toàn bộ không gian trạng thái của các map chuẩn.
    """

    def _assert_admissibility_for_map(self, map_filename: str, map_name: str) -> None:
        map_path = _resolve_map_path(map_filename)
        self.assertTrue(map_path.exists(), f"Không tìm thấy file map: {map_path}")

        board = load_level(str(map_path))
        report_h2 = verify_heuristic_admissibility(board, heuristic_fn=bloxorz_advanced_heuristic, map_name=map_name)
        report_h1 = verify_heuristic_admissibility(board, heuristic_fn=manhattan_heuristic, map_name=map_name)

        # 1. Bắt buộc 0 vi phạm (h(s) <= h*(s) với mọi s)
        self.assertEqual(
            report_h2["violations_count"],
            0,
            f"Phát hiện {report_h2['violations_count']} trạng thái vi phạm h(s) > h*(s) tại {map_name}: "
            f"{report_h2['violations'][:3]}",
        )
        self.assertEqual(report_h1["violations_count"], 0, f"H1 vi phạm trên {map_name}")
        self.assertTrue(report_h2["is_admissible"], f"{map_name} không đạt tính chấp nhận được!")

        # 2. Kiểm tra số lượng trạng thái giải được > 0
        self.assertGreater(report_h2["solvable_states"], 0)

        # 3. Kiểm tra riêng trạng thái đích: h(goal) == 0
        goal_state = State(
            r=board.goal_pos[0],
            c=board.goal_pos[1],
            orientation=Orientation.STANDING,
            active_bridges=board.initial_active_bridges,
        )
        self.assertEqual(bloxorz_advanced_heuristic(goal_state, board.goal_pos), 0)
        self.assertEqual(manhattan_heuristic(goal_state, board.goal_pos), 0)

    def test_admissibility_level0(self):
        """Kiểm tra tính chấp nhận được trên Stage 01."""
        self._assert_admissibility_for_map("stage_01.txt", "Stage 01")

    def test_admissibility_level1(self):
        """Kiểm tra tính chấp nhận được trên Stage 02."""
        self._assert_admissibility_for_map("stage_02.txt", "Stage 02")

    def test_admissibility_level2(self):
        """Kiểm tra tính chấp nhận được trên Stage 03."""
        self._assert_admissibility_for_map("stage_03.txt", "Stage 03")

    def test_admissibility_level3(self):
        """Kiểm tra tính chấp nhận được trên Stage 04."""
        self._assert_admissibility_for_map("stage_04.txt", "Stage 04")


class TestHeuristicComponents(unittest.TestCase):
    """
    Kiểm tra chi tiết từng thành phần cấu thành hàm heuristic theo đúng Báo cáo mục 3.
    """

    def test_representative_point_calculation(self):
        """Kiểm tra tọa độ trọng tâm hình học (điểm rút gọn) của từng tư thế khối."""
        s_stand = State(r=2, c=3, orientation=Orientation.STANDING)
        self.assertEqual(get_representative_point(s_stand), (2.0, 3.0))

        s_horiz = State(r=2, c=3, orientation=Orientation.HORIZONTAL)
        self.assertEqual(get_representative_point(s_horiz), (2.0, 3.5))

        s_vert = State(r=2, c=3, orientation=Orientation.VERTICAL)
        self.assertEqual(get_representative_point(s_vert), (2.5, 3.0))

        s_split = State(r=2, c=3, orientation=Orientation.SPLIT, split_pos=(4, 7))
        self.assertEqual(get_representative_point(s_split), (3.0, 5.0))

    def test_orientation_penalty_properties(self):
        """
        Kiểm tra các quy tắc phạt tư thế theo Báo cáo mục 3.2.B:
        1. Tại đích và STANDING: phạt 0
        2. d_min == 0 & nằm (đè lên đích): phạt +2
        3. d_min == 1 & đứng (cạnh đích): phạt +1
        4. d_min == 1 & nằm (hướng đích): phạt 0 (quy tắc chặn cận trên critical bound)
        """
        goal = (3, 2)

        # 1. Tại đích và STANDING: h = 0
        s_goal = State(r=3, c=2, orientation=Orientation.STANDING)
        self.assertEqual(bloxorz_advanced_heuristic(s_goal, goal), 0)

        # 2. d_min == 0 và nằm (ví dụ: HORIZONTAL tại (3, 2) đè lên (3, 2) và (3, 3)):
        s_on_goal_lying = State(r=3, c=2, orientation=Orientation.HORIZONTAL)
        pen_lying = compute_orientation_penalty(s_on_goal_lying, goal, base_dist=0.0)
        self.assertEqual(pen_lying, 2.0)
        # h(s) = base_h (0) + 2 = 2
        self.assertEqual(bloxorz_advanced_heuristic(s_on_goal_lying, goal), 2)

        # 3. d_min == 1 và đứng (ví dụ: STANDING tại (2, 2) kề cạnh đích (3, 2)):
        s_adj_stand = State(r=2, c=2, orientation=Orientation.STANDING)
        pen_stand = compute_orientation_penalty(s_adj_stand, goal, base_dist=1.0)
        self.assertEqual(pen_stand, 1.0)
        # h(s) = ceil(1/2) + 1 = 1 + 1 = 2
        self.assertEqual(bloxorz_advanced_heuristic(s_adj_stand, goal), 2)

        # 4. d_min == 1 và nằm hướng đích (ví dụ: VERTICAL tại (1, 2) chiếm (1, 2) và (2, 2)):
        # Chỉ cần đúng 1 bước lật DOWN là thắng -> h*(s) = 1 -> phạt 0 để h(s) = ceil(1/2) = 1 <= 1!
        s_direct_vert = State(r=1, c=2, orientation=Orientation.VERTICAL)
        pen_direct = compute_orientation_penalty(s_direct_vert, goal, base_dist=1.0)
        self.assertEqual(pen_direct, 0.0)
        self.assertEqual(bloxorz_advanced_heuristic(s_direct_vert, goal), 1)

    def test_split_state_heuristic(self):
        """Kiểm tra heuristic trạng thái tách khối: h_split = max(d_merge, d_goal)."""
        goal = (5, 5)

        s_split = State(r=0, c=0, orientation=Orientation.SPLIT, split_pos=(10, 10))
        self.assertEqual(split_state_heuristic(s_split, goal), 19)

    def test_cost_functions(self):
        """Kiểm tra cost function chuẩn (uniform) và mở rộng (weighted)."""
        s1 = State(r=1, c=1, orientation=Orientation.STANDING, active_bridges=frozenset())
        s2 = State(r=1, c=2, orientation=Orientation.HORIZONTAL, active_bridges=frozenset())
        s3 = State(r=1, c=2, orientation=Orientation.HORIZONTAL, active_bridges=frozenset([(2, 2)]))

        self.assertEqual(uniform_cost(s1, "RIGHT", s2), 1.0)
        self.assertEqual(uniform_cost(s1, "RIGHT", s3), 1.0)

        self.assertEqual(weighted_switch_cost(s1, "RIGHT", s2), 1.0)
        self.assertEqual(weighted_switch_cost(s1, "RIGHT", s3), 2.0)


class TestAStarSolverWithHeuristic(unittest.TestCase):
    """
    Kiểm tra thuật toán A* đối chứng với BFS trên các map chuẩn:
    - Tìm được nghiệm hợp lệ.
    - Phát lại (replay) trên core thành công.
    - Độ dài đường đi tối ưu trùng khớp hoàn toàn với BFS.
    """

    def _test_astar_and_bfs_match(self, map_filename: str) -> None:
        map_path = _resolve_map_path(map_filename)
        board = load_level(str(map_path))

        # Giải bằng BFS
        bfs_solver = BFSSolver(board)
        bfs_res = bfs_solver.solve()
        self.assertTrue(bfs_res.is_solved, f"BFS không giải được {map_filename}")

        # Giải bằng A* với H2
        astar_solver = AStarSolver(board, heuristic_fn=bloxorz_advanced_heuristic)
        astar_res = astar_solver.solve()
        self.assertTrue(astar_res.is_solved, f"A* không giải được {map_filename}")

        # So sánh độ dài nghiệm
        self.assertEqual(
            astar_res.cost,
            bfs_res.cost,
            f"A* ({astar_res.cost} bước) không đạt độ dài tối ưu như BFS ({bfs_res.cost} bước) trên {map_filename}",
        )

        # Phát lại chuỗi hành động trên core
        valid, _, msg = astar_solver.replay(astar_res.actions)
        self.assertTrue(valid, f"Phát lại lời giải A* thất bại trên {map_filename}: {msg}")

    def test_astar_level0(self):
        """A* giải tối ưu Stage 01 (7 bước)."""
        self._test_astar_and_bfs_match("stage_01.txt")

    def test_astar_level1(self):
        """A* giải tối ưu Stage 02 (17 bước)."""
        self._test_astar_and_bfs_match("stage_02.txt")

    def test_astar_level2(self):
        """A* giải tối ưu Stage 03 (19 bước)."""
        self._test_astar_and_bfs_match("stage_03.txt")

    def test_astar_level3(self):
        """A* giải tối ưu Stage 04 (28 bước)."""
        self._test_astar_and_bfs_match("stage_04.txt")


if __name__ == "__main__":
    unittest.main()
