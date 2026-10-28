"""Test cho gui.model.player_data: hồ sơ, băm mật khẩu, kho JSON, quản lý tài khoản và hạn mức AI."""

import json
from pathlib import Path

import pytest

from gui.model.player_data import (
    MANUAL,
    MAX_AI_USES_PER_LEVEL,
    MAX_HISTORY,
    JsonFileStore,
    LevelRecord,
    PasswordHasher,
    PlayerDataManager,
    PlayerProfile,
    calculate_level_score,
)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giảm số vòng PBKDF2 để test chạy nhanh."""
    monkeypatch.setattr(PasswordHasher, "ITERATIONS", 1000)


def make_manager(tmp_path: Path) -> PlayerDataManager:
    return PlayerDataManager(tmp_path / "players.json")


# ---------------------------------------------------------------- điểm số


def test_score_counts_moves_only_when_won() -> None:
    assert calculate_level_score(7, True) == 7
    assert calculate_level_score(7, False) == 0
    assert calculate_level_score(-3, True) == 0


# ---------------------------------------------------------------- PlayerProfile


def test_from_dict_ignores_unknown_keys_and_fills_defaults() -> None:
    profile = PlayerProfile.from_dict({"username": "an", "avatar": "steve"})
    assert (
        profile.username == "an"
        and profile.best_scores == {}
        and profile.schema_version == 2
    )


@pytest.mark.parametrize(
    "bad", [None, [], {"username": ""}, {"username": "  "}, {"name": "x"}]
)
def test_from_dict_rejects_profiles_without_a_username(bad: object) -> None:
    with pytest.raises(ValueError):
        PlayerProfile.from_dict(bad)


def test_from_dict_repairs_wrongly_typed_fields() -> None:
    profile = PlayerProfile.from_dict(
        {
            "username": "a",
            "best_scores": 5,
            "history": "x",
            "salt": 3,
            "ai_uses": {"S1": "bad", "S2": 1.0, "S3": -4},
        }
    )
    assert profile.best_scores == {} and profile.history == [] and profile.salt == ""
    assert profile.ai_uses == {"S2": 1, "S3": 0}


def test_legacy_profile_records_are_rebuilt_from_history() -> None:
    history = [
        {
            "level_id": "S1",
            "moves": ["UP"] * 9,
            "move_count": 9,
            "won": True,
            "mode": "MANUAL",
            "score": 9,
            "elapsed_time": 5.0,
        },
        {
            "level_id": "S1",
            "moves": ["UP"] * 7,
            "move_count": 7,
            "won": True,
            "mode": "BFS",
            "score": 7,
            "elapsed_time": 0.01,
        },
        {
            "level_id": "S2",
            "moves": ["UP"],
            "move_count": 1,
            "won": False,
            "mode": "MANUAL",
        },
    ]
    legacy = {
        "username": "x",
        "best_scores": {"S1": 7},
        "level_stats": {"S1": {"mode": "BFS"}},
        "history": history,
    }
    profile = PlayerProfile.from_dict(legacy)
    assert profile.best_scores == {"S1": 9}
    assert profile.level_stats["S1"]["mode"] == MANUAL
    assert profile.ai_solutions["S1"]["BFS"]["cost"] == 7
    assert profile.schema_version == 2


def test_manual_win_keeps_the_best_score_and_its_replay() -> None:
    profile = PlayerProfile("a")
    profile.apply_manual_win("S1", ["UP"] * 9, 9, 9, 10.0)
    profile.apply_manual_win(
        "S1", ["UP"] * 12, 12, 12, 8.0
    )  # tệ hơn: kỷ lục giữ nguyên
    assert profile.best_scores["S1"] == 9 and profile.saved_replays["S1"] == ["UP"] * 9
    assert profile.best_times["S1"] == 8.0  # thời gian tốt nhất tính riêng
    profile.apply_manual_win(
        "S1", ["DOWN"] * 9, 9, 9, 9.0
    )  # bằng điểm: lượt mới thay thế
    assert profile.saved_replays["S1"] == ["DOWN"] * 9
    profile.apply_manual_win("S1", ["UP"] * 5, 5, 5, 3.0)
    assert profile.best_scores["S1"] == 5


def test_worse_win_still_saves_a_replay_when_none_exists() -> None:
    profile = PlayerProfile("a")
    profile.best_scores["S1"] = 3  # kỷ lục có sẵn nhưng chưa có đường đi lưu
    profile.apply_manual_win("S1", ["UP"] * 8, 8, 8, 1.0)
    assert profile.best_scores["S1"] == 3 and profile.saved_replays["S1"] == ["UP"] * 8


def test_ai_run_keeps_the_shortest_per_algorithm_without_touching_records() -> None:
    profile = PlayerProfile("a")
    profile.apply_ai_run("S1", "BFS", ["UP"] * 7, 7, 0.01)
    profile.apply_ai_run("S1", "BFS", ["UP"] * 9, 9, 0.02)  # dài hơn: bỏ
    profile.apply_ai_run("S1", "DFS", ["UP"] * 30, 30, 0.05)
    assert (
        profile.ai_solutions["S1"]["BFS"]["cost"] == 7
        and profile.ai_solutions["S1"]["DFS"]["cost"] == 30
    )
    assert profile.best_scores == {} and profile.level_stats == {}


def test_best_replay_prefers_the_player_then_the_shortest_ai() -> None:
    profile = PlayerProfile("a")
    assert profile.best_replay("S1") is None
    profile.apply_ai_run("S1", "DFS", ["UP"] * 30, 30, 0.0)
    profile.apply_ai_run("S1", "BFS", ["UP"] * 7, 7, 0.0)
    assert profile.best_replay("S1") == (["UP"] * 7, "BFS")
    profile.apply_manual_win("S1", ["UP"] * 12, 12, 12, 1.0)
    assert profile.best_replay("S1") == (["UP"] * 12, MANUAL)


def test_history_drops_consecutive_duplicates_and_is_capped() -> None:
    profile = PlayerProfile("a")
    record = LevelRecord("S1", ["UP"], 1, True)
    profile.add_history(record)
    profile.add_history(LevelRecord("S1", ["UP"], 1, True))
    assert len(profile.history) == 1
    for i in range(MAX_HISTORY + 20):
        profile.add_history(LevelRecord("S1", ["UP"] * (i + 2), i + 2, True))
    assert len(profile.history) == MAX_HISTORY


def test_ai_quota_on_a_profile_never_goes_below_zero() -> None:
    profile = PlayerProfile("a")
    assert profile.ai_uses_left("S1") == MAX_AI_USES_PER_LEVEL
    assert [profile.consume_ai_use("S1") for _ in range(4)] == [1, 0, 0, 0]
    assert profile.ai_uses_left("S2") == MAX_AI_USES_PER_LEVEL  # mỗi màn tính riêng


# ---------------------------------------------------------------- PasswordHasher


def test_hash_is_deterministic_and_depends_on_salt() -> None:
    assert PasswordHasher.hash("abc", "s1") == PasswordHasher.hash("abc", "s1")
    assert PasswordHasher.hash("abc", "s1") != PasswordHasher.hash("abc", "s2")


def test_verify_accepts_only_the_right_password() -> None:
    digest = PasswordHasher.hash("abc", "salt", PasswordHasher.SCHEME_CURRENT)
    assert PasswordHasher.verify("abc", "salt", digest, PasswordHasher.SCHEME_CURRENT)
    assert not PasswordHasher.verify(
        "abd", "salt", digest, PasswordHasher.SCHEME_CURRENT
    )


def test_legacy_sha256_hashes_still_verify() -> None:
    digest = PasswordHasher.hash("abc", "salt", PasswordHasher.SCHEME_LEGACY)
    assert len(digest) == 64
    assert PasswordHasher.verify("abc", "salt", digest, "")  # rỗng nghĩa là băm cũ
    assert PasswordHasher.verify("abc", "salt", digest, PasswordHasher.SCHEME_LEGACY)


def test_new_salts_are_unique_hex_strings() -> None:
    salts = {PasswordHasher.new_salt() for _ in range(20)}
    assert len(salts) == 20 and all(len(s) == 32 for s in salts)


# ---------------------------------------------------------------- JsonFileStore


def test_store_returns_none_when_the_file_is_missing(tmp_path: Path) -> None:
    assert JsonFileStore(tmp_path / "x.json").load() is None


def test_store_round_trips_unicode(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "x.json")
    store.save({"tên": "Phú"})
    assert store.load() == {"tên": "Phú"}


def test_second_save_keeps_the_previous_version_as_backup(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "x.json")
    store.save({"v": 1})
    store.save({"v": 2})
    assert json.loads(store.backup_path.read_text(encoding="utf-8")) == {"v": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_corrupt_file_is_kept_aside_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text("{ không phải json", encoding="utf-8")
    store = JsonFileStore(path)
    assert store.load() is None
    assert "hỏng" in store.notice and not path.exists()
    assert len(list(tmp_path.glob("x.json.corrupt-*"))) == 1


def test_corrupt_file_is_recovered_from_the_backup(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    store = JsonFileStore(path)
    store.save({"v": 1})
    store.save({"v": 2})
    path.write_text('{"v": ', encoding="utf-8")  # cắt dở
    assert store.load() == {"v": 1}
    assert "khôi phục" in store.notice


def test_non_object_json_counts_as_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text("[1, 2]", encoding="utf-8")
    assert JsonFileStore(path).load() is None


# ---------------------------------------------------------------- PlayerDataManager


def test_register_validates_input(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    assert not manager.register("  ", "abc")[0]
    assert not manager.register("an", "ab")[0]  # mật khẩu quá ngắn
    assert manager.register("an", "abc")[0] and manager.current_user == "an"
    assert "đã tồn tại" in manager.register("an", "abc")[1]


def test_accounts_persist_across_managers(tmp_path: Path) -> None:
    make_manager(tmp_path).register("an", "abc")
    reloaded = make_manager(tmp_path)
    assert "an" in reloaded.players and reloaded.current_user == "an"


def test_login_checks_user_and_password(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.register("an", "abc")
    manager.logout()
    assert manager.current_user is None
    assert not manager.login("binh", "abc")[0]
    assert not manager.login("an", "sai")[0]
    assert manager.login("an", "abc")[0] and manager.current_user == "an"


def test_legacy_account_logs_in_and_upgrades_its_hash(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    salt = "abcd"
    manager.players["cu"] = PlayerProfile(
        "cu", PasswordHasher.hash("matkhau", salt, "sha256"), salt, hash_scheme=""
    )
    assert manager.login("cu", "matkhau")[0]
    assert manager.players["cu"].hash_scheme == PasswordHasher.SCHEME_CURRENT
    assert manager.login("cu", "matkhau")[0]  # vẫn đăng nhập được bằng băm mới


def test_authenticate_or_register_covers_both_paths(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    assert manager.authenticate_or_register("an", "abc")[0]  # chưa có: đăng ký
    manager.logout()
    assert manager.authenticate_or_register("an", "abc")[0]  # đã có: đăng nhập
    assert not manager.authenticate_or_register("an", "sai")[0]
    manager.record_game_session(
        "S1", ["UP"], False, MANUAL, 1.0, username="guest"
    )  # tạo hồ sơ guest không mật khẩu
    assert "đã tồn tại" in manager.authenticate_or_register("guest", "abc")[1]


def test_get_current_profile_follows_the_login(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    assert manager.get_current_profile() is None
    manager.register("an", "abc")
    assert manager.get_current_profile() is manager.players["an"]


def test_manual_win_updates_records_and_history(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.register("an", "abc")
    manager.record_game_session("S1", ["UP", "SWITCH", "DOWN"], True, MANUAL, 4.5)
    info = manager.get_level_score_info("S1")
    assert (
        info is not None and info["score"] == 2 and info["mode"] == MANUAL
    )  # SWITCH không tính bước
    assert manager.get_saved_replay("S1") == ["UP", "SWITCH", "DOWN"]
    assert manager.players["an"].history[-1]["move_count"] == 2


def test_records_fall_back_to_the_guest_account(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.record_game_session("S1", ["UP"], True, MANUAL, 1.0)
    assert manager.get_level_score_info("S1") is not None and "guest" in manager.players


def test_solver_runs_never_become_player_records(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.record_solver_run("S1", "BFS", ["UP"] * 7, True, 0.01, 48)
    manager.record_game_session(
        "S1", ["UP"] * 7, True, "DFS", 0.02
    )  # chế độ khác MANUAL cũng là của thuật toán
    assert manager.get_level_score_info("S1") is None
    assert manager.get_best_replay("S1") == (["UP"] * 7, "BFS")
    manager.record_game_session("S1", ["UP"] * 9, True, MANUAL, 5.0)
    best = manager.get_best_replay("S1")
    assert best is not None and best[1] == MANUAL


def test_unsolved_solver_run_is_not_stored_as_a_solution(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.record_solver_run("S1", "BFS", [], False)
    assert manager.get_best_replay("S1") is None


def test_unknown_profile_fields_do_not_lose_accounts(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.register("an", "abc")
    data = json.loads(manager.storage_path.read_text(encoding="utf-8"))
    data["players"]["an"]["avatar"] = "steve"
    manager.storage_path.write_text(json.dumps(data), encoding="utf-8")
    assert "an" in make_manager(tmp_path).players


def test_unreadable_profiles_are_skipped_and_reported(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.register("an", "abc")
    data = json.loads(manager.storage_path.read_text(encoding="utf-8"))
    data["players"]["hong"] = {"username": ""}
    manager.storage_path.write_text(json.dumps(data), encoding="utf-8")
    reloaded = make_manager(tmp_path)
    assert (
        "an" in reloaded.players
        and "hong" not in reloaded.players
        and "Bỏ qua 1" in reloaded.load_notice
    )


def test_truncated_data_file_is_recovered_not_lost(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.register("an", "abc")
    manager.register("binh", "abc")  # lần ghi thứ hai tạo bản sao lưu
    manager.storage_path.write_text('{"players": {"an"', encoding="utf-8")
    recovered = make_manager(tmp_path)
    assert "an" in recovered.players and recovered.load_notice


def test_save_reports_failure_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = make_manager(tmp_path)

    def boom(payload: dict) -> None:
        raise OSError("đĩa đầy")

    monkeypatch.setattr(manager._store, "save", boom)
    assert manager.save() is False and "đĩa đầy" in manager.save_error


def test_ai_quota_is_per_level_per_player_and_persistent(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    assert manager.ai_uses_left("S1") == MAX_AI_USES_PER_LEVEL  # chưa có hồ sơ nào
    manager.register("an", "abc")
    assert manager.consume_ai_use("S1") == 1
    assert manager.consume_ai_use("S1") == 0
    assert manager.consume_ai_use("S1") == 0  # không âm
    assert manager.ai_uses_left("S2") == MAX_AI_USES_PER_LEVEL
    assert make_manager(tmp_path).ai_uses_left("S1") == 0  # đã lưu xuống file
    manager.register("binh", "abc")
    assert (
        manager.ai_uses_left("S1") == MAX_AI_USES_PER_LEVEL
    )  # người khác có hạn mức riêng
