"""Các hộp thoại nổi (chọn màn, nhập mật khẩu màn, tài khoản) dưới dạng một họ lớp đa hình.

`Window` chỉ giữ **một** overlay đang mở (hoặc None) và chuyển phím, chuột cho nó. Mỗi overlay tự xử lý
đầu vào và **trả về overlay kế tiếp**: chính nó (giữ nguyên), None (đóng) hoặc một overlay khác (chuyển
hộp thoại). Thêm hộp thoại mới chỉ cần thêm một lớp con, không phải sửa `Window`.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Protocol

import pygame
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
    KMOD_SHIFT,
    K_n,
    K_s,
    K_w,
)

from gui.account_prompt import AccountPrompt
from gui.level_picker import LevelPicker
from gui.passcode_prompt import PasscodePrompt, char_from_key, digit_from_key
from gui.session import GameSession, StageSelection

MSG_WRONG_PASSCODE: str = "Sai mật khẩu."
MSG_LOGGED_OUT: str = "Đã đăng xuất về tài khoản khách (guest)."
MSG_NEED_USERNAME: str = "Vui lòng nhập Username (hoặc nhấn F2 để Đăng xuất)."
ENTER_KEYS: tuple[int, int] = (K_RETURN, K_KP_ENTER)


class OverlayPanel(Protocol):
    """Những gì một overlay cần từ bảng điều khiển để vẽ chính nó."""

    def draw_picker(
        self,
        picker: LevelPicker,
        current_index: int,
        is_unlocked: Callable[[int], bool] | None = None,
    ) -> None:
        """Vẽ hộp chọn màn."""

    def draw_prompt(self, prompt: PasscodePrompt) -> None:
        """Vẽ hộp nhập mật khẩu của một màn."""

    def draw_account_prompt(self, prompt: AccountPrompt) -> None:
        """Vẽ hộp tài khoản."""


def _shift_held() -> bool:
    """Phím Shift có đang được giữ không (False nếu pygame chưa khởi tạo)."""
    try:
        return bool(pygame.key.get_mods() & KMOD_SHIFT)
    except pygame.error:
        return False


class Overlay(ABC):
    """Lớp cha của mọi hộp thoại nổi."""

    @abstractmethod
    def handle_key(self, key: int, text: str = "") -> "Overlay | None":
        """Xử lý một phím; trả về overlay kế tiếp (self: giữ, None: đóng, lớp khác: chuyển)."""

    def handle_click(
        self, button: int, pos: tuple[int, int], window_size: tuple[int, int]
    ) -> "Overlay | None":
        """Xử lý một lần bấm chuột; mặc định bỏ qua và giữ nguyên overlay."""
        return self

    def handle_wheel(self, steps: int) -> None:
        """Xử lý con lăn chuột; mặc định bỏ qua."""
        return

    @abstractmethod
    def draw(self, panel: OverlayPanel) -> None:
        """Vẽ overlay bằng bảng điều khiển `panel`."""


class LevelPickerOverlay(Overlay):
    """Hộp chọn màn: màn đã mở vào ngay, màn khóa chuyển sang hộp nhập mật khẩu."""

    def __init__(self, session: GameSession, picker: LevelPicker) -> None:
        """Gắn hộp với phiên chơi và trạng thái danh sách `picker`."""
        self.session: GameSession = session
        self.picker: LevelPicker = picker

    @classmethod
    def open(cls, session: GameSession) -> "LevelPickerOverlay":
        """Mở hộp chọn màn với dòng chọn đặt ở màn đang chơi."""
        picker: LevelPicker = LevelPicker(session.catalog.names)
        picker.open(max(session.level_index, 0))
        return cls(session, picker)

    def handle_key(self, key: int, text: str = "") -> Overlay | None:
        """Lên, xuống, chuyển trang, Enter để chọn, Esc hoặc N để đóng."""
        if key in (K_ESCAPE, K_n):
            return None
        if key in (K_UP, K_w):
            self.picker.move(-1)
        elif key in (K_DOWN, K_s):
            self.picker.move(1)
        elif key == K_PAGEUP:
            self.picker.page(-1)
        elif key == K_PAGEDOWN:
            self.picker.page(1)
        elif key in ENTER_KEYS:
            return self._select(self.picker.selected)
        return self

    def handle_click(
        self, button: int, pos: tuple[int, int], window_size: tuple[int, int]
    ) -> Overlay | None:
        """Bấm trái vào một dòng để chọn; bấm ra ngoài hộp để đóng."""
        if button != 1:
            return self
        width, height = window_size
        row: int | None = self.picker.row_at(pos, width, height)
        if row is not None:
            return self._select(row)
        if not self.picker.box_contains(pos, width, height):
            return None
        return self

    def handle_wheel(self, steps: int) -> None:
        """Cuộn danh sách."""
        self.picker.scroll_by(-steps)

    def _select(self, index: int) -> Overlay | None:
        """Chọn màn `index`: màn khóa mở hộp mật khẩu, các trường hợp khác đóng hộp."""
        if self.session.select_stage(index) == StageSelection.NEEDS_PASSCODE:
            return PasscodeOverlay.open(self.session, index)
        return None

    def draw(self, panel: OverlayPanel) -> None:
        """Vẽ danh sách màn kèm nhãn 'đang chơi' và 'khóa'."""
        panel.draw_picker(
            self.picker, self.session.level_index, self.session.catalog.is_unlocked
        )


class PasscodeOverlay(Overlay):
    """Hộp nhập mật khẩu 6 chữ số của một màn bị khóa."""

    def __init__(
        self, session: GameSession, prompt: PasscodePrompt, target: int
    ) -> None:
        """Gắn hộp với phiên chơi, trạng thái nhập `prompt` và chỉ số màn cần mở."""
        self.session: GameSession = session
        self.prompt: PasscodePrompt = prompt
        self.target: int = target

    @classmethod
    def open(cls, session: GameSession, target: int) -> "PasscodeOverlay":
        """Mở hộp nhập mật khẩu cho màn `target`."""
        prompt: PasscodePrompt = PasscodePrompt(session.catalog.passcode_length)
        prompt.open(target, session.catalog.entries[target].name)
        return cls(session, prompt, target)

    def handle_key(self, key: int, text: str = "") -> Overlay | None:
        """Gõ chữ số, Backspace xóa, Enter xác nhận, Esc quay lại danh sách."""
        if key == K_ESCAPE:
            return LevelPickerOverlay.open(self.session)
        if key == K_BACKSPACE:
            self.prompt.backspace()
        elif key in ENTER_KEYS:
            return self._submit()
        else:
            digit: str | None = digit_from_key(key, text)
            if digit is not None:
                self.prompt.type_digit(digit)
        return self

    def _submit(self) -> Overlay | None:
        """Kiểm tra mật khẩu: đủ chữ số và đúng thì vào màn (đóng hộp), ngược lại báo lỗi."""
        if len(self.prompt.text) < self.prompt.max_length:
            self.prompt.fail(f"Mật khẩu gồm {self.prompt.max_length} chữ số.")
            return self
        if self.session.submit_passcode(self.target, self.prompt.text):
            return None
        self.prompt.fail(MSG_WRONG_PASSCODE)
        return self

    def draw(self, panel: OverlayPanel) -> None:
        """Vẽ hộp nhập mật khẩu."""
        panel.draw_prompt(self.prompt)


class AccountOverlay(Overlay):
    """Hộp đăng nhập, đăng ký hoặc đăng xuất tài khoản người chơi."""

    def __init__(
        self,
        session: GameSession,
        prompt: AccountPrompt,
        shift_held: Callable[[], bool] = _shift_held,
    ) -> None:
        """Gắn hộp với phiên chơi, trạng thái nhập `prompt` và hàm cho biết Shift có đang giữ không."""
        self.session: GameSession = session
        self.prompt: AccountPrompt = prompt
        self.shift_held: Callable[[], bool] = shift_held

    @classmethod
    def open(cls, session: GameSession) -> "AccountOverlay":
        """Mở hộp tài khoản, điền sẵn tên nếu đang đăng nhập."""
        prompt: AccountPrompt = AccountPrompt()
        prompt.open(session.players.current_user)
        return cls(session, prompt)

    def handle_key(self, key: int, text: str = "") -> Overlay | None:
        """Esc đóng, Tab hoặc mũi tên đổi ô, F2 đăng xuất, Enter đăng nhập hoặc đăng ký, còn lại là gõ chữ."""
        if key == K_ESCAPE:
            return None
        if key in (K_TAB, K_UP, K_DOWN):
            self.prompt.switch_field()
        elif key == K_BACKSPACE:
            self.prompt.backspace()
        elif key == K_F2:
            self.session.players.logout()
            self.session.say(MSG_LOGGED_OUT)
            return None
        elif key in ENTER_KEYS:
            return self._submit()
        else:
            ch: str | None = char_from_key(key, text, shift=self.shift_held())
            if ch is not None:
                self.prompt.type_char(ch)
        return self

    def _submit(self) -> Overlay | None:
        """Đăng nhập (hoặc đăng ký nếu chưa có); thành công thì đóng hộp, thất bại thì báo lỗi."""
        username: str = self.prompt.username.strip()
        if not username:
            self.prompt.fail(MSG_NEED_USERNAME)
            return self
        ok, message = self.session.players.authenticate_or_register(
            username, self.prompt.password
        )
        if ok:
            self.session.say(message)
            return None
        self.prompt.fail(message)
        return self

    def draw(self, panel: OverlayPanel) -> None:
        """Vẽ hộp tài khoản."""
        panel.draw_account_prompt(self.prompt)
