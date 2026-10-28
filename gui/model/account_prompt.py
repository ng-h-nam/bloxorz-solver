"""Trạng thái hộp thoại đăng nhập, đăng ký và đăng xuất (chỉ giữ dữ liệu, không vẽ)."""


class AccountPrompt:
    """Hộp nhập tên tài khoản và mật khẩu; Window xử lý phím, ControlPanel lo việc vẽ."""

    def __init__(self, max_length: int = 18) -> None:
        """Tạo hộp đóng; `max_length` là số ký tự tối đa của mỗi ô nhập."""
        self.max_length: int = max_length
        self.is_open: bool = False
        self.username: str = ""
        self.password: str = ""
        self.active_field: int = 0  # 0: tên tài khoản, 1: mật khẩu
        self.error: str = ""
        self.info: str = ""

    def open(self, current_user: str | None = None) -> None:
        """Mở hộp; nếu đang đăng nhập thì điền sẵn tên và chuyển con trỏ sang ô mật khẩu."""
        self.is_open = True
        active_name: str = current_user or "guest"
        self.username = "" if active_name == "guest" else active_name
        self.password = ""
        self.active_field = 0 if not self.username else 1
        self.error = ""
        self.info = f"Đang dùng: {active_name} (Nhấn F2 để Đăng xuất)"

    def close(self) -> None:
        """Đóng hộp và xóa mật khẩu đã gõ."""
        self.is_open = False
        self.password = ""
        self.error = ""

    def switch_field(self) -> None:
        """Đổi con trỏ giữa ô tên tài khoản và ô mật khẩu."""
        self.active_field = 1 - self.active_field
        self.error = ""

    def type_char(self, ch: str) -> None:
        """Gõ thêm một ký tự (chữ, số, '_' hoặc '-') vào ô đang chọn nếu còn chỗ."""
        if len(ch) != 1 or not (ch.isalnum() or ch in ("_", "-")):
            return
        if self.active_field == 0 and len(self.username) < self.max_length:
            self.username += ch
            self.error = ""
        elif self.active_field == 1 and len(self.password) < self.max_length:
            self.password += ch
            self.error = ""

    def backspace(self) -> None:
        """Xóa ký tự cuối của ô đang chọn."""
        if self.active_field == 0:
            self.username = self.username[:-1]
        else:
            self.password = self.password[:-1]
        self.error = ""

    def fail(self, message: str) -> None:
        """Hiện thông báo lỗi (ví dụ sai mật khẩu)."""
        self.error = message
