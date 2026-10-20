"""
Package algorithms chứa các thuật toán tìm kiếm và giải bài toán Bloxorz.
"""

from algorithms.base_solver import (
    ActionType,
    BaseSolver,
    Node,
    Solution,
    SolveResult,
    replay_path,
)
from algorithms.bfs import BFS
from algorithms.dfs import DFS

__all__ = [
    "ActionType",
    "BaseSolver",
    "Node",
    "SolveResult",
    "Solution",
    "replay_path",
    "BFS",
    "DFS",
]
