from core.game import Game, GameStatus
from core.map_loader import (
    load_coolmath_dict,
    load_coolmath_levels,
    load_coolmath_stage,
    load_level,
)


def test_load_all_coolmath_stages():
    boards = load_coolmath_levels()
    assert len(boards) == 33, f"Cần đủ 33 màn chơi gốc Bloxorz, nhận được {len(boards)}"

    for idx, board in enumerate(boards, start=1):
        assert board.raw_metadata["name"] == f"Stage {idx:02d}"
        game = Game(board)
        assert game.status == GameStatus.PLAYING
        assert len(game.get_valid_moves()) > 0


def test_coolmath_stage_selection_and_mechanics():
    # Chọn theo số thứ tự, tên màn, passcode, và cú pháp filepath:stage
    s1 = load_coolmath_stage(1)
    s5 = load_coolmath_stage("Stage 05")
    s8_by_passcode = load_coolmath_stage("499707")
    s8_by_path = load_level("coolmath.json:8")
    stage_dict = load_coolmath_dict()

    assert s1.raw_metadata["passcode"] == "780464"
    assert len(s5.initial_active_bridges) == 6  # Stage 05 có 3 cây cầu 'BB' mở sẵn (6 ô)
    assert s8_by_passcode.splits == {(4, 4): ((1, 10), (7, 10))}
    assert s8_by_path.start_pos == s8_by_passcode.start_pos
    assert len(stage_dict) == 33
