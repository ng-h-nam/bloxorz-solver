"""
Thuật toán tìm kiếm theo chi phí đồng nhất (Uniform-Cost Search - UCS) cho bài toán Bloxorz.

Đặc điểm kỹ thuật:
- Mở rộng nút có chi phí đường đi g(n) nhỏ nhất trước.
- Tương đương thuật toán Dijkstra trên không gian trạng thái ẩn (implicit state space graph).
- Đảm bảo tính tối ưu toàn cục (Optimality) với mọi hàm chi phí không âm c(s, a, s') >= eps > 0.
- Pop-time Goal Test: Bắt buộc kiểm tra đích tại thời điểm lấy nút ra khỏi Frontier (heap pop)
  để đảm bảo không trả về một đường đi chưa tối ưu tới đích.
- Quản lý tập đóng và cập nhật đường đi ngắn hơn thông qua bảng best_g[state_key].
- Hàng đợi ưu tiên (Priority Queue) sử dụng min-heap (heapq).
- Tiêu chí Tie-breaking:
  1. Chi phí g(n) nhỏ hơn được ưu tiên trước.
  2. Nếu g(n) bằng nhau, ưu tiên theo thứ tự đưa vào hàng đợi (tie_counter) để ổn định FIFO.
- Hỗ trợ hàm chi phí linh hoạt (CostFunction):
  + uniform_cost: c = 1.0 cho mọi bước đi (tìm đường đi ít bước nhất, tương đương BFS).
  + weighted_switch_cost: phạt chi phí cao hơn khi kích hoạt công tắc chuyển đổi cầu.
  + Các hàm chi phí tùy biến khác.
- Đo lường đầy đủ: thời gian thực thi (time.perf_counter), bộ nhớ đỉnh (tracemalloc),
  số nút mở rộng, kích thước frontier lớn nhất.
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
from algorithms.heuristic import CostFunction, uniform_cost
from core.board import Board
from core.map_loader import load_level
from core.state import State


class UCSSolver(BaseSolver):
    """
    Thuật toán tìm kiếm theo chi phí đồng nhất (Uniform-Cost Search).
    """

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
        cost_fn: Optional[CostFunction] = None,
        node_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> None:
        """
        Khởi tạo UCS Solver.

        Args:
            board: Bản đồ trò chơi chứa kích thước, vị trí Start, Goal, cầu, công tắc.
            initial_state: Trạng thái bắt đầu. Mặc định khởi tạo từ board.start_pos.
            cost_fn: Hàm chi phí bước đi c(state, action, next_state). Mặc định là uniform_cost (= 1.0).
            node_limit: Giới hạn số nút mở rộng tối đa (tránh tràn RAM hoặc treo máy).
            time_limit: Giới hạn thời gian chạy tối đa (giây).
        """
        super().__init__(
            board=board,
            initial_state=initial_state,
            node_limit=node_limit,
            time_limit=time_limit,
        )
        self.cost_fn: CostFunction = cost_fn if cost_fn is not None else uniform_cost

    def solve(self) -> SolveResult:
        """
        Thực thi thuật toán tìm kiếm Uniform-Cost Search.

        Returns:
            SolveResult chứa chuỗi hành động, danh sách trạng thái, chi phí tối ưu,
            thời gian thực thi, bộ nhớ đỉnh và số nút đã mở rộng.
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

        # Min-heap priority queue: (priority_cost, tie_counter, node)
        tie_counter: int = 0
        frontier: List[Tuple[float, int, Node]] = [(0.0, tie_counter, root_node)]

        # Bảng ghi nhận chi phí tốt nhất đến mỗi trạng thái: best_g[state_key] = g
        best_g: Dict[State, float] = {root_key: 0.0}

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

            # Lấy nút có chi phí g(n) nhỏ nhất ra khỏi Frontier
            curr_cost, _, current_node = heapq.heappop(frontier)
            curr_state = current_node.state
            curr_key = self.get_state_key(curr_state)

            # Bỏ qua nếu đã tìm được đường đi khác tới curr_state với chi phí nhỏ hơn (Lazy Deletion)
            if curr_cost > best_g.get(curr_key, float("inf")):
                continue

            self.nodes_explored += 1

            # 2. Pop-time Goal Test: Đảm bảo tính tối ưu toàn cục của UCS
            if self.is_goal(curr_state):
                exec_time, peak_mem = self._finish_profiling(start_time)
                path_nodes = current_node.reconstruct_path()
                actions = [n.action for n in path_nodes if n.action is not None]
                states = [n.state for n in path_nodes]
                cost_val = (
                    int(current_node.cost)
                    if isinstance(current_node.cost, float) and current_node.cost.is_integer()
                    else current_node.cost
                )

                return SolveResult(
                    actions=actions,
                    states=states,
                    cost=cost_val,
                    nodes_explored=self.nodes_explored,
                    max_frontier_size=self.max_frontier_size,
                    execution_time=exec_time,
                    peak_memory=peak_mem,
                    is_solved=True,
                    status="SOLVED",
                )

            # 3. Mở rộng các trạng thái con kế tiếp
            for action, next_state in self.get_successors(curr_state):
                step_c = float(self.cost_fn(curr_state, action, next_state))
                tentative_g = curr_cost + step_c
                nxt_key = self.get_state_key(next_state)

                # Chỉ xét nút con nếu tìm ra đường đi có chi phí nhỏ hơn tới nxt_key
                if tentative_g < best_g.get(nxt_key, float("inf")):
                    best_g[nxt_key] = tentative_g

                    cost_val = (
                        int(tentative_g)
                        if isinstance(tentative_g, float) and tentative_g.is_integer()
                        else tentative_g
                    )
                    child_node = self.create_child_node(
                        parent=current_node,
                        action=action,
                        next_state=next_state,
                        cost=cost_val,
                    )

                    tie_counter += 1
                    heapq.heappush(
                        frontier,
                        (tentative_g, tie_counter, child_node),
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


def run_ucs_experiments(
    map_paths: List[str], cost_fn: Optional[CostFunction] = None
) -> None:
    """
    Chạy thử nghiệm thuật toán UCS trên danh sách bản đồ và in báo cáo chi tiết.
    """
    print("=" * 80)
    print("      BÁO CÁO THỰC NGHIỆM THUẬT TOÁN TÌM KIẾM THEO CHI PHÍ ĐỒNG NHẤT (UCS)")
    print("=" * 80)

    for idx, map_path in enumerate(map_paths, start=1):
        print(f"\n[Màn {idx}]: {map_path}")
        if not os.path.exists(map_path):
            print(f"  -> Lỗi: Không tìm thấy file {map_path}")
            continue

        board = load_level(map_path)
        solver = UCSSolver(board, cost_fn=cost_fn)
        result = solver.solve()

        if result.is_solved:
            valid, _, msg = solver.replay(result.actions)
            print("  -> Trạng thái          : THÀNH CÔNG (SOLVED)")
            print(f"  -> Chi phí tối ưu      : {result.cost}")
            print(f"  -> Số bước di chuyển   : {len(result.actions)} bước")
            print(f"  -> Phát lại (replay)   : {msg}")
            print(f"  -> Chuỗi di chuyển     : {result.get_action_sequence_str()}")
            print(f"  -> Nút mở rộng (nodes) : {result.nodes_explored}")
            print(f"  -> Max frontier        : {result.max_frontier_size}")
            print(
                f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms ({result.execution_time:.6f} s)"
            )
            print(f"  -> Bộ nhớ đỉnh         : {result.memory_kb:.2f} KB ({result.memory_bytes} bytes)")
        else:
            print(f"  -> Trạng thái          : THẤT BẠI ({result.status})")
            print(f"  -> Nút mở rộng         : {result.nodes_explored}")
            print(f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_maps = [
        os.path.join(PROJECT_ROOT, "data", "maps", f"stage_{i:02d}.txt") for i in range(1, 34)
    ]
    run_ucs_experiments(test_maps)

