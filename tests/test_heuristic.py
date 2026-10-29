"""
Kiểm chứng toán học Admissible cho hàm Heuristic Bloxorz (Báo cáo kỹ thuật mục 5.1).

Kiểm tra vét cạn toàn bộ không gian trạng thái đạt được bằng thuật toán BFS trên 3 map chuẩn:
- Level 0 (29 trạng thái): 0 lỗi vi phạm admissibility.
- Level 1 (114 trạng thái): 0 lỗi vi phạm admissibility.
- Level 3 (102 trạng thái): 0 lỗi vi phạm admissibility.
"""

from pathlib import Path
import unittest

from algorithms.heuristic import (
    bloxorz_advanced_heuristic,
    compute_orientation_penalty,
    get_representative_point,
    manhattan_heuristic,
    verify_heuristic_admissibility,
)
from core.map_loader import load_level
from core.state import Orientation, State

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestHeuristicAdmissibility(unittest.TestCase):
    """
    Kiểm tra tính Admissible h(s) <= h*(s) với mọi s trên 3 map chuẩn của Báo cáo mục 5.1.
    """

    def _verify_map(self, map_filename: str, expected_solvable: int):
        map_path = PROJECT_ROOT / "data" / "maps" / map_filename
        self.assertTrue(map_path.exists(), f"Không tìm thấy file: {map_path}")

        board = load_level(str(map_path))
        report_h2 = verify_heuristic_admissibility(board, heuristic_fn=bloxorz_advanced_heuristic)
        report_h1 = verify_heuristic_admissibility(board, heuristic_fn=manhattan_heuristic)

        # Kiểm tra đúng số trạng thái có thể tới đích
        self.assertEqual(report_h2["solvable_states"], expected_solvable)

        # Kiểm tra 0 vi phạm trên cả H1 và H2
        self.assertEqual(report_h1["violations_count"], 0, f"H1 vi phạm trên {map_filename}")
        self.assertEqual(report_h2["violations_count"], 0, f"H2 vi phạm trên {map_filename}")
        self.assertTrue(report_h2["is_admissible"])

    def test_level0_admissibility(self):
        """Level 0 (29 trạng thái): 0 lỗi vi phạm admissibility."""
        self._verify_map("level0.txt", 29)

    def test_level1_admissibility(self):
        """Level 1 (114 trạng thái): 0 lỗi vi phạm admissibility."""
        self._verify_map("level1.txt", 114)

    def test_level3_admissibility(self):
        """Level 3 (102 trạng thái): 0 lỗi vi phạm admissibility."""
        self._verify_map("level3.txt", 102)


if __name__ == "__main__":
    unittest.main()

