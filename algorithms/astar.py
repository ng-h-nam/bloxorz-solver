"""
Thuật toán A* Search cho bài toán Bloxorz.

Đặc điểm kỹ thuật:
- Hàm đánh giá f(n) = g(n) + h(n), trong đó:
  + g(n): Chi phí thực tế tích lũy từ nút gốc đến nút hiện tại (đo bằng cost_fn).
  + h(n): Ước lượng chi phí từ trạng thái hiện tại tới đích (đo bằng bloxorz_heuristic).
- Hàng đợi ưu tiên (Priority Queue) sử dụng min-heap (heapq).
- Tiêu chí Tie-breaking:
  1. f(n) nhỏ nhất được ưu tiên trước.
  2. Nếu f(n) bằng nhau, nút có h(n) nhỏ hơn (gần đích hơn) được ưu tiên trước.
  3. Nếu cả f và h bằng nhau, so sánh theo thứ tự chèn (counter).
- Pop-time Goal Test: Kiểm tra đích khi lấy nút ra khỏi Frontier để đảm bảo tính tối ưu toàn cục
  theo định lý tìm kiếm đồ thị A*.
- Quản lý tập đóng và cập nhật đường đi ngắn hơn thông qua bảng best_g[state_key].
- Đo lường đầy đủ: thời gian (time.perf_counter), bộ nhớ đỉnh (tracemalloc), số nút đã duyệt,
  kích thước frontier lớn nhất.
"""

import heapq
import os
import sys
from typing import Dict, List, Optional, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from algorithms.base_solver import BaseSolver, Node, SolveResult
from algorithms.heuristic import (
    CostFunction,
    HeuristicFunction,
    bloxorz_heuristic,
    uniform_cost,
)
from core.board import Board
from core.map_loader import load_level
from core.state import State


class AStarSolver(BaseSolver):
    """
    Thuật toán tìm kiếm A* (A-Star Search) tìm đường đi tối ưu đến đích
    dựa trên hàm đánh giá f(n) = g(n) + h(n).
    """

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
        heuristic_fn: Optional[HeuristicFunction] = None,
        cost_fn: Optional[CostFunction] = None,
        node_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> None:
        """
        Khởi tạo A* Solver.

        Args:
            board: Bản đồ trò chơi chứa kích thước, vị trí Start, Goal, cầu, công tắc.
            initial_state: Trạng thái bắt đầu. Mặc định khởi tạo từ board.start_pos.
            heuristic_fn: Hàm ước lượng h(state, goal_pos). Mặc định là bloxorz_heuristic.
            cost_fn: Hàm chi phí bước đi c(state, action, next_state). Mặc định là uniform_cost (= 1.0).
            node_limit: Giới hạn số nút duyệt tối đa.
            time_limit: Giới hạn thời gian chạy tối đa (giây).
        """
        super().__init__(
            board=board,
            initial_state=initial_state,
            node_limit=node_limit,
            time_limit=time_limit,
        )
        self.heuristic_fn: HeuristicFunction = heuristic_fn if heuristic_fn is not None else bloxorz_heuristic
        self.cost_fn: CostFunction = cost_fn if cost_fn is not None else uniform_cost

    def solve(self) -> SolveResult:
        """
        Thực thi thuật toán tìm kiếm A*.

        Returns:
            SolveResult chứa chuỗi hành động, danh sách trạng thái, chi phí,
            thời gian chạy, bộ nhớ đỉnh và số nút đã mở rộng.
        """
        start_time = self._start_profiling()

        # Kiểm tra nếu xuất phát đã là đích
        if self.is_goal(self.initial_state):
            exec_time, peak_mem = self._finish_profiling(start_time)
            return SolveResult(
                actions=[],
                states=[self.initial_state],
                cost=0,
                nodes_explored=0,
                max_frontier_size=1,
                execution_time=exec_time,
                peak_memory=peak_mem,
                is_solved=True,
                status="SOLVED",
            )

        root_node = self.create_root_node()
        root_key = self.get_state_key(self.initial_state)

        # Tính h(start) và f(start)
        h_root = float(self.heuristic_fn(self.initial_state, self.board.goal_pos))
        f_root = root_node.cost + h_root

        # Min-heap priority queue: (f_score, h_score, tie_breaker_counter, node)
        tie_counter: int = 0
        frontier: List[Tuple[float, float, int, Node]] = [(f_root, h_root, tie_counter, root_node)]

        # Bảng ghi nhận chi phí tốt nhất đến mỗi trạng thái: best_g[state_key] = g
        best_g: Dict[State, float] = {root_key: float(root_node.cost)}

        self.nodes_explored = 0
        self.max_frontier_size = 1

        while frontier:
            # 1. Kiểm tra các giới hạn thời gian và số nút
            limit_reason = self._check_limits(start_time)
            if limit_reason:
                exec_time, peak_mem = self._finish_profiling(start_time)
                return SolveResult(
                    actions=[],
                    states=[],
                    cost=0,
                    nodes_explored=self.nodes_explored,
                    max_frontier_size=self.max_frontier_size,
                    execution_time=exec_time,
                    peak_memory=peak_mem,
                    is_solved=False,
                    status=limit_reason,
                )

            # Cập nhật kích thước frontier lớn nhất
            if len(frontier) > self.max_frontier_size:
                self.max_frontier_size = len(frontier)

            # Lấy nút có f(n) nhỏ nhất ra khỏi Frontier
            f_score, h_score, _, current_node = heapq.heappop(frontier)
            curr_state = current_node.state
            curr_key = self.get_state_key(curr_state)

            # Bỏ qua nếu đã tìm được đường đi khác tới curr_state với chi phí g nhỏ hơn
            if current_node.cost > best_g.get(curr_key, float("inf")):
                continue

            self.nodes_explored += 1

            # 2. Pop-time Goal Test: Đảm bảo tính tối ưu của A*
            if self.is_goal(curr_state):
                exec_time, peak_mem = self._finish_profiling(start_time)
                path_nodes = current_node.reconstruct_path()
                actions = [n.action for n in path_nodes if n.action is not None]
                states = [n.state for n in path_nodes]

                return SolveResult(
                    actions=actions,
                    states=states,
                    cost=len(actions),
                    nodes_explored=self.nodes_explored,
                    max_frontier_size=self.max_frontier_size,
                    execution_time=exec_time,
                    peak_memory=peak_mem,
                    is_solved=True,
                    status="SOLVED",
                )

            # 3. Mở rộng các trạng thái con hợp lệ
            for action, next_state in self.get_successors(curr_state):
                step_c = self.cost_fn(curr_state, action, next_state)
                tentative_g = current_node.cost + step_c
                nxt_key = self.get_state_key(next_state)

                # Chỉ xét nút con nếu tìm ra đường đi ngắn hơn tới nxt_key
                if tentative_g < best_g.get(nxt_key, float("inf")):
                    best_g[nxt_key] = tentative_g

                    child_node = self.create_child_node(
                        parent=current_node,
                        action=action,
                        next_state=next_state,
                    )
                    # Gán chính xác chi phí g(n) từ cost_fn
                    child_node.cost = int(tentative_g) if tentative_g.is_integer() else tentative_g

                    # Tính h(n) và f(n) = g(n) + h(n)
                    h_val = float(self.heuristic_fn(next_state, self.board.goal_pos))
                    f_val = tentative_g + h_val

                    tie_counter += 1
                    heapq.heappush(
                        frontier,
                        (f_val, h_val, tie_counter, child_node),
                    )

        # Frontier rỗng -> Không tìm thấy đường đi tới đích
        exec_time, peak_mem = self._finish_profiling(start_time)
        return SolveResult(
            actions=[],
            states=[],
            cost=0,
            nodes_explored=self.nodes_explored,
            max_frontier_size=self.max_frontier_size,
            execution_time=exec_time,
            peak_memory=peak_mem,
            is_solved=False,
            status="NO_SOLUTION",
        )


def run_astar_experiments(map_paths: List[str]) -> None:
    """
    Chạy thử nghiệm thuật toán A* trên danh sách bản đồ và in báo cáo chi tiết.
    """
    print("=" * 80)
    print("           BÁO CÁO THỰC NGHIỆM THUẬT TOÁN TÌM KIẾM A* (A-STAR SEARCH)")
    print("=" * 80)

    for idx, map_path in enumerate(map_paths, start=1):
        print(f"\n[Màn {idx}]: {map_path}")
        if not os.path.exists(map_path):
            print(f"  -> Lỗi: Không tìm thấy file {map_path}")
            continue

        board = load_level(map_path)
        solver = AStarSolver(board)
        result = solver.solve()

        if result.is_solved:
            valid, _, msg = solver.replay(result.actions)
            print("  -> Trạng thái          : THÀNH CÔNG (SOLVED)")
            print(f"  -> Số bước tối ưu      : {result.cost} bước")
            print(f"  -> Phát lại (replay)   : {msg}")
            print(f"  -> Chuỗi di chuyển     : {result.get_action_sequence_str()}")
            print(f"  -> Nút mở rộng (nodes) : {result.nodes_explored}")
            print(f"  -> Max frontier        : {result.max_frontier_size}")
            print(f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms ({result.execution_time:.6f} s)")
            print(f"  -> Bộ nhớ đỉnh         : {result.memory_kb:.2f} KB ({result.memory_bytes} bytes)")
        else:
            print(f"  -> Trạng thái          : THẤT BẠI ({result.status})")
            print(f"  -> Nút mở rộng         : {result.nodes_explored}")
            print(f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_maps = [os.path.join(PROJECT_ROOT, "data", "maps", f"level{i}.txt") for i in range(4)]
    run_astar_experiments(test_maps)
