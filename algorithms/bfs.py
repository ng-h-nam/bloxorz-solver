"""Thuật toán BFS (Breadth-First Search)."""

from collections import deque
import os
import sys
import time
from typing import List, Optional, Set

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from algorithms.base_solver import ActionType, BaseSolver, Node, SolveResult, replay_path
from core.block import Direction
from core.board import Board
from core.map_loader import load_level
from core.state import Orientation, State


class BFS(BaseSolver):
    """
    Thuật toán Breadth-First Search (BFS) tìm số bước đi ít nhất trên đồ thị có trọng số đồng nhất.
    """

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
        node_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> None:
        super().__init__(board, initial_state, node_limit=node_limit, time_limit=time_limit)

    def solve(self) -> SolveResult:
        """
        Giải tìm kiếm theo chiều rộng (BFS).

        Returns:
            SolveResult chứa chuỗi hành động, danh sách trạng thái, thời gian chạy,
            bộ nhớ đỉnh tracemalloc và số nút mở rộng.
        """
        start_time = self._start_profiling()

        # Kiểm tra nếu trạng thái bắt đầu đã là đích
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
        queue: deque[Node] = deque([root_node])
        visited: Set[State] = {self.get_state_key(self.initial_state)}

        self.nodes_explored = 0
        self.max_frontier_size = 1

        while queue:
            # Kiểm tra time_limit, node_limit
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

            if len(queue) > self.max_frontier_size:
                self.max_frontier_size = len(queue)

            current_node: Node = queue.popleft()
            self.nodes_explored += 1

            for action, next_state in self.get_successors(current_node.state):
                state_key = self.get_state_key(next_state)

                if state_key not in visited:
                    visited.add(state_key)

                    child_node = self.create_child_node(
                        parent=current_node,
                        action=action,
                        next_state=next_state,
                    )

                    # Early Goal Test: Kiểm tra đích ngay khi đưa nút con vào hàng đợi (tối ưu BFS)
                    if self.is_goal(next_state):
                        exec_time, peak_mem = self._finish_profiling(start_time)
                        path_nodes = child_node.reconstruct_path()
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

                    queue.append(child_node)

        # Hàng đợi rỗng mà không tìm thấy đích -> Vô nghiệm
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


def run_bfs_experiments(map_paths: List[str]) -> None:
    """
    Chạy thực nghiệm BFS trên danh sách bản đồ và in báo cáo chi tiết.
    """
    print("=" * 75)
    print("           BÁO CÁO THỰC NGHIỆM THUẬT TOÁN BFS (BREADTH-FIRST SEARCH)")
    print("=" * 75)

    for idx, map_path in enumerate(map_paths, start=1):
        print(f"\n[Màn {idx}]: {map_path}")
        if not os.path.exists(map_path):
            print(f"  -> Lỗi: Không tìm thấy file {map_path}")
            continue

        board = load_level(map_path)
        solver = BFS(board)
        result = solver.solve()

        if result.is_solved:
            # Phát lại lời giải để kiểm tra tính đúng đắn trên core
            valid, _, msg = solver.replay(result.actions)
            print("  -> Trạng thái          : THÀNH CÔNG")
            print(f"  -> Số bước tối ưu      : {result.cost} bước")
            print(f"  -> Phát lại            : {msg}")
            print(f"  -> Chuỗi di chuyển     : {result.get_action_sequence_str()}")
            print(f"  -> Nút mở rộng (nodes) : {result.nodes_explored}")
            print(f"  -> Max frontier        : {result.max_frontier_size}")
            print(f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms ({result.execution_time:.6f} s)")
            print(f"  -> Bộ nhớ đỉnh         : {result.memory_kb:.2f} KB ({result.memory_bytes} bytes)")
        else:
            print(f"  -> Trạng thái          : THẤT BẠI ({result.status})")
            print(f"  -> Nút mở rộng         : {result.nodes_explored}")
            print(f"  -> Thời gian chạy      : {result.execution_time * 1000:.3f} ms")

    print("\n" + "=" * 75)


if __name__ == "__main__":
    test_maps = [
        os.path.join(PROJECT_ROOT, "data", "maps", f"level{i}.txt") for i in range(4)
    ]
    run_bfs_experiments(test_maps)
