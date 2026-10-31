"""Dữ liệu thuần mà giao diện hiển thị (không phụ thuộc OpenGL)."""

from dataclasses import dataclass

from gui.shared.palette import RGB


@dataclass
class HudData:
    """Những gì bảng thông tin hiển thị; do Window quyết định để khớp với hoạt cảnh."""

    level_name: str
    moves: int
    orientation: str
    status: str
    elapsed: float
    passcode: str = ""
    username: str = "guest"
    best_record: str = "Chưa có"
    solver_name: str = "BFS"
    solver_running: bool = False
    replay_active: bool = False
    replay_playing: bool = False
    replay_step: int = 0
    replay_total: int = 0
    replay_speed_label: str = "1x"
    ai_uses_left: int = 2


@dataclass
class Banner:
    """Băng thông báo thắng hoặc thua: tiêu đề, phụ đề, gợi ý phím và màu tiêu đề."""

    title: str
    subtitle: str
    hint: str
    color: RGB
