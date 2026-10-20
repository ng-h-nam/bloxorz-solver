"""
Thuật toán DFS (Depth-First Search).
"""

import os
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from algorithms.base_solver import ActionType, BaseSolver, Node, SolveResult, replay_path
from core.block import Direction
from core.board import Board
from core.map_loader import load_level
from core.state import Orientation, State


class DFSSolver(BaseSolver):
    """Thuật toán Depth-First Search (DFS) có kiểm soát chu trình."""

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
        max_depth: Optional[int] = 1000,
        node_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> None:
        super().__init__(board, initial_state, node_limit=node_limit, time_limit=time_limit)
        self.max_depth: Optional[int] = max_depth

    def solve(self) -> SolveResult:
        """
        Giải tìm kiếm theo chiều sâu (DFS).

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
        stack: List[Node] = [root_node]
        visited: Set[State] = {self.get_state_key(self.initial_state)}

        self.nodes_explored = 0
        self.max_frontier_size = 1

        while stack:
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

            if len(stack) > self.max_frontier_size:
                self.max_frontier_size = len(stack)

            current_node: Node = stack.pop()
            self.nodes_explored += 1

            if self.is_goal(current_node.state):
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

            # Cắt tỉa nếu vượt quá giới hạn độ sâu
            if self.max_depth is not None and current_node.depth >= self.max_depth:
                continue

            # Mở rộng các trạng thái kế tiếp (Successors)
            successors = self.get_successors(current_node.state)
            for action, next_state in successors:
                state_key = self.get_state_key(next_state)

                if state_key not in visited:
                    visited.add(state_key)
                    child_node = self.create_child_node(
                        parent=current_node,
                        action=action,
                        next_state=next_state,
                    )
                    stack.append(child_node)

        # Ngăn xếp rỗng mà không tìm thấy đích
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


def run_dfs_experiments(map_paths: List[str]) -> None:
    """
    Chạy thực nghiệm DFS và IDS trên danh sách bản đồ và in báo cáo chi tiết.
    """
    print("=" * 75)
    print("            BÁO CÁO THỰC NGHIỆM THUẬT TOÁN DFS & IDS")
    print("=" * 75)

    for idx, map_path in enumerate(map_paths, start=1):
        print(f"\n[Màn {idx}]: {map_path}")
        if not os.path.exists(map_path):
            print(f"  -> Lỗi: Không tìm thấy file {map_path}")
            continue

        board = load_level(map_path)

        # 1. Chạy DFS
        dfs_solver = DFSSolver(board, max_depth=1000)
        dfs_res = dfs_solver.solve()
        if dfs_res.is_solved:
            valid, _, msg = dfs_solver.replay(dfs_res.actions)
            print("  --- DFS (Depth-First Search) ---")
            print("  -> Trạng thái          : THÀNH CÔNG (Solved)")
            print(f"  -> Số bước tìm được    : {dfs_res.cost} bước")
            print(f"  -> Phát lại            : {msg}")
            print(f"  -> Nút mở rộng (nodes) : {dfs_res.nodes_explored}")
            print(f"  -> Max frontier        : {dfs_res.max_frontier_size}")
            print(f"  -> Thời gian chạy      : {dfs_res.execution_time * 1000:.3f} ms")
            print(f"  -> Bộ nhớ đỉnh         : {dfs_res.memory_kb:.2f} KB ({dfs_res.memory_bytes} bytes)")
        else:
            print(f"  --- DFS: Thất bại ({dfs_res.status}) ---")

    print("\n" + "=" * 75)


if __name__ == "__main__":
    test_maps = [
        os.path.join(PROJECT_ROOT, "data", "maps", f"level{i}.txt") for i in range(4)
    ]
    run_dfs_experiments(test_maps)
