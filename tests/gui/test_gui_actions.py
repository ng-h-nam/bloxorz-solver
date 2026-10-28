"""Test cho gui.actions: chuẩn hóa tên hành động."""

import pytest

from core.block import Direction
from gui.actions import action_name, action_names, count_moves


def test_direction_enum_maps_to_its_value() -> None:
    assert action_name(Direction.UP) == "UP"


def test_strings_ignore_case_and_spaces() -> None:
    assert action_name("  right ") == "RIGHT"


def test_wasd_aliases_are_accepted() -> None:
    assert action_name("w") == "UP"
    assert action_name("D") == "RIGHT"


@pytest.mark.parametrize("alias", ["SWITCH", "space", "Tab"])
def test_switch_aliases_map_to_switch(alias: str) -> None:
    assert action_name(alias) == "SWITCH"


def test_invalid_action_raises_value_error() -> None:
    with pytest.raises(ValueError):
        action_name("JUMP")


def test_action_names_normalizes_a_whole_sequence() -> None:
    assert action_names([Direction.LEFT, "down", "space"]) == ["LEFT", "DOWN", "SWITCH"]


def test_count_moves_ignores_switch() -> None:
    assert count_moves(["UP", "SWITCH", Direction.DOWN, "tab"]) == 2


def test_count_moves_of_nothing_is_zero() -> None:
    assert count_moves([]) == 0
