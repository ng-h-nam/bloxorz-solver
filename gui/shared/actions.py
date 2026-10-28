"""Tên hành động chuẩn hóa dùng chung cho phát lại, bộ giải và lưu dữ liệu."""

from collections.abc import Iterable

from core.block import Direction
from core.transition import SWITCH_ACTION, SWITCH_ALIASES, ActionInput, normalize_action


def action_name(action: ActionInput) -> str:
    """Chuẩn hóa một hành động về 'UP', 'DOWN', 'LEFT', 'RIGHT' hoặc 'SWITCH'.

    Ném ValueError nếu hành động không hợp lệ.
    """
    if isinstance(action, Direction):
        return action.value
    text: str = str(getattr(action, "value", action)).strip().upper()
    if text in SWITCH_ALIASES:
        return SWITCH_ACTION
    return normalize_action(text).value


def action_names(actions: Iterable[ActionInput]) -> list[str]:
    """Chuẩn hóa cả một chuỗi hành động (xem `action_name`)."""
    return [action_name(action) for action in actions]


def count_moves(actions: Iterable[ActionInput]) -> int:
    """Số bước lăn khối trong chuỗi hành động (không tính lệnh đổi khối SWITCH)."""
    return sum(1 for action in actions if action_name(action) != SWITCH_ACTION)
