"""Tương thích ngược: các tên từng nằm trong `gui.replayer` nay có module riêng.

- `AccountPrompt` -> `gui.model.account_prompt`
- `PlayerDataManager`, `PlayerProfile`, `LevelRecord`, `calculate_level_score` -> `gui.model.player_data`
- `Replayer`, `ReplayFrame` -> `gui.engine.replay` (API mới: phát từ trạng thái đang chơi, chỉ dùng API công khai của Game)
- `BackgroundSolverWorker`, `SolverResultEvent`, `SolverErrorEvent`, `verify_solver_state_key` -> `gui.engine.solver_worker`
"""

from gui.engine.replay import Replayer, ReplayFrame, ReplayMode
from gui.engine.solver_worker import (
    BackgroundSolverWorker,
    SolverErrorEvent,
    SolverResultEvent,
    verify_solver_state_key,
)
from gui.model.account_prompt import AccountPrompt
from gui.model.player_data import (
    LevelRecord,
    PlayerDataManager,
    PlayerProfile,
    calculate_level_score,
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
