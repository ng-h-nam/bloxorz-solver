import json

import pytest

from gui.model.level_catalog import LevelCatalog

STAGES = [
    {
        "name": "Stage 01",
        "passcode": "111111",
        "grid": ["S.H"],
        "bridges": [],
        "switches": [],
        "teleports": [],
    },
    {
        "name": "Stage 02",
        "passcode": "222222",
        "grid": ["S..H"],
        "bridges": [],
        "switches": [],
        "teleports": [],
    },
    {
        "name": "Stage 03",
        "passcode": "333333",
        "grid": ["S...H"],
        "bridges": [],
        "switches": [],
        "teleports": [],
    },
]


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "coolmath.json"
    path.write_text(json.dumps(STAGES), encoding="utf-8")
    return LevelCatalog.from_json(str(path))


def test_reads_names_and_passcodes(catalog):
    assert len(catalog) == 3
    assert catalog.names == ["Stage 01", "Stage 02", "Stage 03"]
    assert [e.passcode for e in catalog.entries] == ["111111", "222222", "333333"]
    assert catalog.passcode_length == 6


def test_only_the_first_stage_is_unlocked_at_start(catalog):
    assert [catalog.is_unlocked(i) for i in range(3)] == [True, False, False]


def test_index_of_matches_exact_name_only(catalog):
    assert catalog.index_of("Stage 02") == 1
    assert catalog.index_of("stage 02") == -1
    assert catalog.index_of("") == -1


def test_board_loads_the_requested_stage(catalog):
    assert catalog.board(2).name == "Stage 03"
    assert catalog.board(0).passcode == "111111"


def test_next_index_stops_at_the_last_stage(catalog):
    assert catalog.next_index(0) == 1
    assert catalog.next_index(2) is None
    assert catalog.next_index(-5) is None


def test_unlock_ignores_invalid_indexes(catalog):
    catalog.unlock(None)
    catalog.unlock(99)
    catalog.unlock(-1)
    assert [catalog.is_unlocked(i) for i in range(3)] == [True, False, False]
    catalog.unlock(1)
    assert catalog.is_unlocked(1)


def test_passcode_must_match_exactly(catalog):
    assert catalog.check_passcode(1, "222222")
    assert catalog.check_passcode(1, " 222222 ")
    assert not catalog.check_passcode(1, "111111")
    assert not catalog.check_passcode(1, "22222")
    assert not catalog.check_passcode(1, "")


def test_stage_numbers_and_names_are_not_passcodes(catalog):
    """Khác load_level(): chuỗi chứa chữ số, số thứ tự hay tên màn không được coi là mật khẩu."""
    for guess in ["2", "02", "Stage 2", "Stage 02", "abc2", "x222222", "222222x"]:
        assert not catalog.check_passcode(1, guess), guess


def test_unlock_with_passcode_only_unlocks_on_success(catalog):
    assert not catalog.unlock_with_passcode(2, "999999")
    assert not catalog.is_unlocked(2)
    assert catalog.unlock_with_passcode(2, "333333")
    assert catalog.is_unlocked(2)


def test_check_passcode_with_out_of_range_index_is_false(catalog):
    assert not catalog.check_passcode(7, "333333")
    assert not catalog.check_passcode(-1, "111111")


def test_stage_without_passcode_cannot_be_unlocked_by_an_empty_code(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([STAGES[0], {**STAGES[1], "passcode": ""}]), encoding="utf-8")
    catalog = LevelCatalog.from_json(str(path))
    assert not catalog.check_passcode(1, "")


def test_empty_catalog_is_safe():
    catalog = LevelCatalog([])
    assert len(catalog) == 0 and catalog.names == [] and not catalog.is_unlocked(0)
    assert catalog.next_index(0) is None and catalog.passcode_length == 6


def test_real_coolmath_file_if_present():
    try:
        catalog = LevelCatalog.from_json()
    except FileNotFoundError:
        pytest.skip("không có data/maps/coolmath.json")
    codes = [e.passcode for e in catalog.entries]
    assert len(set(codes)) == len(codes) and all(c.isdigit() for c in codes)
