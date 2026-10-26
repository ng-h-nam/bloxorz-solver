"""
Package algorithms chứa các thuật toán tìm kiếm và giải bài toán Bloxorz.
"""

from algorithms.astar import AStarSolver
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
from algorithms.ucs import UCSSolver
from algorithms.heuristic import (
    CostFunction,
    HeuristicFunction,
    bloxorz_advanced_heuristic,
    bloxorz_heuristic,
    get_representative_point,
    manhattan_div2_heuristic,
    manhattan_heuristic,
    split_state_heuristic,
    uniform_cost,
    weighted_switch_cost,
)

__all__ = [
    "ActionType",
    "BaseSolver",
    "Node",
    "SolveResult",
    "Solution",
    "replay_path",
    "BFSSolver",
    "DFSSolver",
    "UCSSolver",
    "AStarSolver",
    "CostFunction",
    "HeuristicFunction",
    "bloxorz_heuristic",
    "bloxorz_advanced_heuristic",
    "manhattan_heuristic",
    "get_representative_point",
    "manhattan_div2_heuristic",
    "split_state_heuristic",
    "uniform_cost",
    "weighted_switch_cost",
]
