import pygame

_DIGITS = "0123456789"

_DIGIT_KEYS: dict[int, str] = {
    **{pygame.K_0 + i: str(i) for i in range(10)},
    pygame.K_KP0: "0",
    pygame.K_KP1: "1",
    pygame.K_KP2: "2",
    pygame.K_KP3: "3",
    pygame.K_KP4: "4",
    pygame.K_KP5: "5",
    pygame.K_KP6: "6",
    pygame.K_KP7: "7",
    pygame.K_KP8: "8",
    pygame.K_KP9: "9",
}


def digit_from_key(key: int, text: str = "") -> str | None:
    """Chữ số mà một lần nhấn phím biểu diễn, hoặc None.

    Ưu tiên ký tự thật của sự kiện (đúng với mọi bố cục bàn phím), rồi mới tới mã phím
    (hàng số và bàn phím số). Không dùng chế độ nhập văn bản nên không bị bộ gõ chặn.
    """
    if len(text) == 1 and text in _DIGITS:
        return text
    return _DIGIT_KEYS.get(key)


def char_from_key(key: int, text: str = "", shift: bool = False) -> str | None:
    """Ký tự chữ, số hoặc '_', '-' cho hộp nhập tài khoản mà không cần text_input."""
    if len(text) == 1 and text.isascii() and (text.isalnum() or text in ("_", "-")):
        return text
    digit = digit_from_key(key, text)
    if digit is not None:
        return digit
    if pygame.K_a <= key <= pygame.K_z:
        letter = chr(ord("a") + (key - pygame.K_a))
        return letter.upper() if shift else letter
    if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
        return "_" if shift else "-"
    return None


class PasscodePrompt:
    """Hộp nhập mật khẩu của một màn: chỉ giữ trạng thái; Window xử lý phím và việc vẽ."""

    def __init__(self, max_length: int = 6) -> None:
        self.max_length: int = max_length
        self.is_open: bool = False
        self.target: int = -1
        self.title: str = ""
        self.text: str = ""
        self.error: str = ""

    def open(self, target: int, title: str) -> None:
        self.is_open = True
        self.target = target
        self.title = title
        self.text = ""
        self.error = ""

    def close(self) -> None:
        self.is_open = False
        self.text = ""
        self.error = ""

    def type_digit(self, digit: str) -> None:
        if len(digit) == 1 and digit in _DIGITS and len(self.text) < self.max_length:
            self.text += digit
            self.error = ""

    def backspace(self) -> None:
        self.text = self.text[:-1]
        self.error = ""

    def fail(self, message: str) -> None:
        """Báo sai mật khẩu: xóa nội dung đã gõ để nhập lại."""
        self.text = ""
        self.error = message
