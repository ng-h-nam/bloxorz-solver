"""Test cho gui.ui.overlays: họ hộp thoại nổi (chọn màn, mật khẩu màn, tài khoản)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pygame
import pytest
from pygame.locals import (
    K_BACKSPACE,
    K_DOWN,
    K_ESCAPE,
    K_F2,
    K_KP_ENTER,
    K_PAGEDOWN,
    K_PAGEUP,
    K_RETURN,
    K_TAB,
    K_UP,
    K_a,
    K_n,
    K_s,
    K_w,
)

from core.game import Game
from gui.model.level_catalog import LevelCatalog
from gui.model.passcode_prompt import PasscodePrompt
from gui.model.player_data import PasswordHasher, PlayerDataManager
from gui.model.session import GameSession
from gui.ui.overlays import (
    MSG_LOGGED_OUT,
    MSG_NEED_USERNAME,
    MSG_WRONG_PASSCODE,
    AccountOverlay,
    LevelPickerOverlay,
    Overlay,
    PasscodeOverlay,
)

WINDOW = (1280, 768)


class FakePanel:
    """Bảng giả ghi lại các lệnh vẽ."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def draw_picker(
        self,
        picker: Any,
        current_index: int,
        is_unlocked: Callable[[int], bool] | None = None,
    ) -> None:
        self.calls.append(("picker", (current_index, is_unlocked(1) if is_unlocked else None)))

    def draw_prompt(self, prompt: PasscodePrompt) -> None:
        self.calls.append(("prompt", prompt.title))

    def draw_account_prompt(self, prompt: Any) -> None:
        self.calls.append(("account", prompt.active_field))


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PasswordHasher, "ITERATIONS", 1000)


@pytest.fixture
def session(tmp_path: Path) -> GameSession:
    catalog = LevelCatalog.from_json()
    return GameSession(Game(catalog.board(0)), catalog, PlayerDataManager(tmp_path / "p.json"))


def type_text(overlay: Overlay, text: str) -> Overlay | None:
    current: Overlay | None = overlay
    for ch in text:
        assert current is not None
        current = current.handle_key(getattr(pygame, f"K_{ch}"), ch)
    return current


# ---------------------------------------------------------------- lớp cha


def test_overlay_is_abstract_and_has_safe_defaults(session: GameSession) -> None:
    with pytest.raises(TypeError):
        Overlay()  # type: ignore[abstract]
    overlay = PasscodeOverlay.open(session, 1)
    assert overlay.handle_click(1, (0, 0), WINDOW) is overlay and overlay.handle_wheel(3) is None


# ---------------------------------------------------------------- LevelPickerOverlay


def test_the_picker_opens_on_the_current_level(session: GameSession) -> None:
    overlay = LevelPickerOverlay.open(session)
    assert overlay.picker.is_open and overlay.picker.selected == session.level_index


def test_picker_navigation_keys(session: GameSession) -> None:
    overlay = LevelPickerOverlay.open(session)
    assert overlay.handle_key(K_DOWN) is overlay and overlay.picker.selected == 1
    overlay.handle_key(K_s)
    assert overlay.picker.selected == 2
    overlay.handle_key(K_UP)
    overlay.handle_key(K_w)
    assert overlay.picker.selected == 0
    overlay.handle_key(K_PAGEDOWN)
    assert overlay.picker.selected > 1
    overlay.handle_key(K_PAGEUP)
    assert overlay.picker.selected == 0


@pytest.mark.parametrize("key", [K_ESCAPE, K_n])
def test_escape_or_n_closes_the_picker(session: GameSession, key: int) -> None:
    assert LevelPickerOverlay.open(session).handle_key(key) is None


def test_choosing_the_current_level_just_closes(session: GameSession) -> None:
    assert LevelPickerOverlay.open(session).handle_key(K_RETURN) is None and session.level_index == 0


def test_choosing_a_locked_level_opens_the_passcode_box(session: GameSession) -> None:
    overlay = LevelPickerOverlay.open(session)
    overlay.handle_key(K_DOWN)
    follow_up = overlay.handle_key(K_KP_ENTER)
    assert isinstance(follow_up, PasscodeOverlay) and follow_up.target == 1
    assert session.level_index == 0  # chưa vào màn


def test_choosing_an_unlocked_level_loads_it(session: GameSession) -> None:
    session.catalog.unlock(1)
    overlay = LevelPickerOverlay.open(session)
    overlay.handle_key(K_DOWN)
    assert overlay.handle_key(K_RETURN) is None and session.level_name == "Stage 02"


def test_clicking_rows_and_outside(session: GameSession) -> None:
    overlay = LevelPickerOverlay.open(session)
    box, rows = overlay.picker.layout(*WINDOW)
    follow_up = overlay.handle_click(1, rows[2].center, WINDOW)
    assert isinstance(follow_up, PasscodeOverlay) and follow_up.target == 2
    assert overlay.handle_click(1, (box.x + 2, box.y + 2), WINDOW) is overlay  # trong khung, không trúng dòng nào
    assert overlay.handle_click(1, (1, 1), WINDOW) is None  # ngoài khung: đóng
    assert overlay.handle_click(3, rows[1].center, WINDOW) is overlay  # nút phải bị bỏ qua


def test_the_wheel_scrolls_the_list(session: GameSession) -> None:
    overlay = LevelPickerOverlay.open(session)
    overlay.handle_wheel(-3)
    assert overlay.picker.scroll == 3


def test_picker_draws_with_lock_information(session: GameSession) -> None:
    panel = FakePanel()
    LevelPickerOverlay.open(session).draw(panel)
    assert panel.calls == [("picker", (0, False))]


# ---------------------------------------------------------------- PasscodeOverlay


def test_digits_are_typed_and_other_keys_ignored(session: GameSession) -> None:
    overlay = PasscodeOverlay.open(session, 1)
    type_text(overlay, "12a3")
    assert overlay.prompt.text == "123"
    overlay.handle_key(K_BACKSPACE)
    assert overlay.prompt.text == "12"


def test_an_incomplete_code_is_reported_without_loading(session: GameSession) -> None:
    overlay = PasscodeOverlay.open(session, 1)
    type_text(overlay, "12")
    assert overlay.handle_key(K_RETURN) is overlay and "6 chữ số" in overlay.prompt.error
    assert session.level_index == 0


def test_a_wrong_code_is_rejected(session: GameSession) -> None:
    overlay = PasscodeOverlay.open(session, 1)
    type_text(overlay, "000000")
    assert overlay.handle_key(K_RETURN) is overlay and overlay.prompt.error == MSG_WRONG_PASSCODE
    assert overlay.prompt.text == "" and session.level_index == 0


def test_the_stage_number_is_not_a_passcode(session: GameSession) -> None:
    overlay = PasscodeOverlay.open(session, 4)
    type_text(overlay, "5")
    overlay.handle_key(K_RETURN)
    assert session.level_index == 0


def test_the_right_code_loads_the_level_and_closes(session: GameSession) -> None:
    overlay = PasscodeOverlay.open(session, 1)
    type_text(overlay, session.catalog.entries[1].passcode)
    assert overlay.handle_key(K_RETURN) is None
    assert session.level_name == "Stage 02" and session.catalog.is_unlocked(1)


def test_escape_returns_to_the_level_list(session: GameSession) -> None:
    assert isinstance(PasscodeOverlay.open(session, 1).handle_key(K_ESCAPE), LevelPickerOverlay)


def test_passcode_box_draws_the_target_title(session: GameSession) -> None:
    panel = FakePanel()
    PasscodeOverlay.open(session, 1).draw(panel)
    assert panel.calls == [("prompt", "Stage 02")]


# ---------------------------------------------------------------- AccountOverlay


def test_typing_letters_digits_and_shifted_letters(session: GameSession) -> None:
    overlay = AccountOverlay.open(session)
    type_text(overlay, "an1")
    assert overlay.prompt.username == "an1"
    shifted = AccountOverlay(session, AccountOverlayPrompt(session), shift_held=lambda: True)
    shifted.handle_key(K_a, "")  # không có ký tự thật: dùng mã phím và Shift
    assert shifted.prompt.username == "A"


def AccountOverlayPrompt(session: GameSession) -> Any:
    overlay = AccountOverlay.open(session)
    return overlay.prompt


def test_tab_and_arrows_switch_fields(session: GameSession) -> None:
    overlay = AccountOverlay.open(session)
    overlay.handle_key(K_TAB)
    assert overlay.prompt.active_field == 1
    overlay.handle_key(K_UP)
    assert overlay.prompt.active_field == 0


def test_an_empty_username_is_refused(session: GameSession) -> None:
    overlay = AccountOverlay.open(session)
    assert overlay.handle_key(K_RETURN) is overlay and overlay.prompt.error == MSG_NEED_USERNAME


def test_new_users_are_registered_and_the_box_closes(session: GameSession) -> None:
    overlay = AccountOverlay.open(session)
    type_text(overlay, "an")
    overlay.handle_key(K_TAB)
    type_text(overlay, "abc")
    assert overlay.handle_key(K_RETURN) is None
    assert session.players.current_user == "an" and "Đăng ký" in session.message


def test_a_wrong_password_keeps_the_box_open(session: GameSession) -> None:
    session.players.register("an", "abc")
    session.players.logout()
    overlay = AccountOverlay.open(session)
    type_text(overlay, "an")
    overlay.handle_key(K_TAB)
    type_text(overlay, "sai")
    assert overlay.handle_key(K_RETURN) is overlay and "không chính xác" in overlay.prompt.error
    assert session.players.current_user is None


def test_backspace_edits_the_active_field(session: GameSession) -> None:
    overlay = AccountOverlay.open(session)
    type_text(overlay, "ab")
    overlay.handle_key(K_BACKSPACE)
    assert overlay.prompt.username == "a"


def test_f2_logs_out_and_closes(session: GameSession) -> None:
    session.players.register("an", "abc")
    assert AccountOverlay.open(session).handle_key(K_F2) is None
    assert session.players.current_user is None and session.message == MSG_LOGGED_OUT


def test_escape_closes_the_account_box(session: GameSession) -> None:
    assert AccountOverlay.open(session).handle_key(K_ESCAPE) is None


def test_account_box_prefills_the_logged_in_user_and_draws(
    session: GameSession,
) -> None:
    session.players.register("an", "abc")
    overlay = AccountOverlay.open(session)
    panel = FakePanel()
    overlay.draw(panel)
    assert overlay.prompt.username == "an" and panel.calls == [("account", 1)]
