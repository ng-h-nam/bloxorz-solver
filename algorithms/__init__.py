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
from algorithms.bfs import BFSSolver
from algorithms.dfs import DFSSolver

__all__ = [
    "ActionType",
    "BFSSolver",
    "BaseSolver",
    "DFSSolver",
    "Node",
    "Solution",
    "SolveResult",
    "replay_path",
]
