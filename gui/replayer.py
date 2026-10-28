"""Tương thích ngược: các tên từng nằm trong `gui.replayer` nay có module riêng.

- `AccountPrompt` -> `gui.account_prompt`
- `PlayerDataManager`, `PlayerProfile`, `LevelRecord`, `calculate_level_score` -> `gui.player_data`
- `Replayer`, `ReplayFrame` -> `gui.replay` (API mới: phát từ trạng thái đang chơi, chỉ dùng API công khai của Game)
- `BackgroundSolverWorker`, `SolverResultEvent`, `SolverErrorEvent`, `verify_solver_state_key` -> `gui.solver_worker`
"""

from gui.account_prompt import AccountPrompt
from gui.player_data import (
    LevelRecord,
    PlayerDataManager,
    PlayerProfile,
    calculate_level_score,
)
from gui.replay import Replayer, ReplayFrame, ReplayMode
from gui.solver_worker import (
    BackgroundSolverWorker,
    SolverErrorEvent,
    SolverResultEvent,
    verify_solver_state_key,
)

__all__ = [
    "AccountPrompt",
    "BackgroundSolverWorker",
    "LevelRecord",
    "PlayerDataManager",
    "PlayerProfile",
    "ReplayFrame",
    "ReplayMode",
    "Replayer",
    "SolverErrorEvent",
    "SolverResultEvent",
    "calculate_level_score",
    "verify_solver_state_key",
]