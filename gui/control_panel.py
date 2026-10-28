"""Bảng điều khiển bên trái và các hộp thoại, kiểu giao diện Minecraft.

`ControlPanel` chỉ biết *vẽ gì ở đâu* và *nút nào ở đâu*; việc vẽ thật nằm ở `UiPainter` (OpenGL khi chạy
game, `RecordingPainter` khi kiểm thử). Chữ lấy từ các `Typeface` theo vai trò: banner, title, body, small.
"""

from collections.abc import Callable, Mapping

import pygame

from gui import palette
from gui.account_prompt import AccountPrompt
from gui.level_picker import LevelPicker
from gui.painter import UiPainter
from gui.palette import RGB
from gui.passcode_prompt import PasscodePrompt
from gui.pixel_font import Typeface, build_typefaces
from gui.player_data import MAX_AI_USES_PER_LEVEL
from gui.theme import MINECRAFT, Theme
from gui.viewmodels import Banner, HudData
from gui.widgets import (
    Button,
    Faces,
    Pixel,
    draw_dialog_box,
    draw_outline,
    draw_slot,
    draw_text_field,
    fit_text,
    text_top,
    wrap_text,
)

PANEL_WIDTH: int = 340
PANEL_PADDING: int = 16
TITLE_Y: int = 12
INFO_TOP: int = 50
INFO_STEP: int = 22
INFO_COUNT: int = 9
BUTTON_TOP: int = INFO_TOP + INFO_COUNT * INFO_STEP + 8
BUTTON_STEP: int = 36
BUTTON_WIDTH: int = 148
BUTTON_HEIGHT: int = 30
BUTTON_COL_GAP: int = 12
BUTTON_ROWS: int = 6
MESSAGE_TOP: int = BUTTON_TOP + (BUTTON_ROWS - 1) * BUTTON_STEP + BUTTON_HEIGHT + 12
MESSAGE_STEP: int = 20
HELP_STEP: int = 12
MAX_MESSAGE_LINES: int = 5
BANNER_HEIGHT: int = 230
BANNER_MARGIN: int = 40
PROMPT_BOX_SIZE: tuple[int, int] = (520, 220)
ACCOUNT_BOX_SIZE: tuple[int, int] = (560, 290)
PROMPT_FOOTER: str = "Enter: xác nhận  -  Backspace: xóa  -  Esc: quay lại"
ACCOUNT_FOOTER: str = (
    "Tab: đổi ô  -  Enter: Đăng nhập/Đăng ký  -  F2: Đăng xuất  -  Esc: đóng"
)
PICKER_FOOTER: str = "Lên/Xuống: chọn  -  Enter: vào  -  Esc: đóng"
HELP_LINES: list[str] = [
    "Mũi tên / WASD: lăn khối  |  Space: đổi khối",
    "Z: hoàn tác (Undo)  |  R: chơi lại  |  N: chọn màn",
    "F: giải AI  |  M: đổi thuật toán  |  L: tài khoản",
    "V: phát Replay lưu  |  P: tạm dừng/tiếp tục",
    "[ / ]: lùi/tiến 1 bước  |  T: đổi tốc độ Replay",
    "C: đặt lại camera  |  Chuột phải/giữa/lăn: camera",
]

# (nhãn, mã hành động, phím tắt hiện ở góc nút nếu còn chỗ, bật ngay từ đầu)
BUTTON_SPECS: tuple[tuple[str, str, str, bool], ...] = (
    ("Restart", "restart", "R", True),
    ("Chọn màn", "new_game", "N", True),
    ("Undo", "undo", "Z", True),
    ("Tài khoản", "account", "L", True),
    ("AI: BFS", "cycle_algo", "M", True),
    ("Giải AI", "run_solver", "F", True),
    ("Replay lưu", "replay_saved", "V", True),
    ("Tạm dừng", "replay_toggle", "P", False),
    ("<< Bước", "step_back", "[", False),
    ("Bước >>", "step_fwd", "]", False),
    ("Tốc độ 1x", "cycle_speed", "T", True),
    ("Đóng Replay", "stop_replay", "", False),
)
STATUS_COLORS: dict[str, RGB] = {
    "PLAYING": palette.GREEN,
    "WON": palette.GOLD,
    "LOST": palette.RED,
}
NO_RECORD: str = "Chưa có"


def format_elapsed(seconds: float) -> str:
    """Đổi số giây thành 'mm:ss.s', ví dụ 75.3 -> '01:15.3'."""
    minutes: int = int(seconds // 60)
    return f"{minutes:02d}:{seconds - minutes * 60:04.1f}"


class ControlPanel:
    """Cột bảng điều khiển bên trái, băng thắng/thua và các hộp thoại (chọn màn, mật khẩu, tài khoản)."""

    def __init__(
        self,
        width: int,
        height: int,
        painter: UiPainter | None = None,
        faces: Mapping[str, Typeface] | None = None,
        theme: Theme = MINECRAFT,
    ) -> None:
        """Dựng bảng cho cửa sổ `width` x `height`.

        `painter` mặc định là bản OpenGL (cần ngữ cảnh OpenGL đang mở); `faces` mặc định lấy từ `build_typefaces()`.
        """
        if painter is None:
            from gui.gl_painter import (
                GLPainter,  # nạp muộn để module này không cần OpenGL khi kiểm thử
            )

            painter = GLPainter()
        self.width: int = width
        self.height: int = height
        self.painter: UiPainter = painter
        self.theme: Theme = theme
        chosen: dict[str, Typeface] = dict(
            faces if faces is not None else build_typefaces()
        )
        chosen.setdefault("banner", chosen["title"])
        self.faces: Faces = chosen
        self._mouse: Pixel = (-1, -1)

        self.buttons: list[Button] = []
        self._button_map: dict[str, Button] = {}
        for index, (label, action, hint, enabled) in enumerate(BUTTON_SPECS):
            rect = pygame.Rect(
                PANEL_PADDING + (index % 2) * (BUTTON_WIDTH + BUTTON_COL_GAP),
                BUTTON_TOP + (index // 2) * BUTTON_STEP,
                BUTTON_WIDTH,
                BUTTON_HEIGHT,
            )
            button = Button(rect, label, action, hint, enabled)
            self.buttons.append(button)
            self._button_map[action] = button

        self.help_lines: list[str] = [
            part
            for line in HELP_LINES
            for part in wrap_text(chosen["small"], line, self.content_width)
        ]

    # ------------------------------------------------------------------ bố cục

    @property
    def content_width(self) -> int:
        """Bề rộng vùng nội dung của cột bên trái (trừ lề hai bên)."""
        return PANEL_WIDTH - 2 * PANEL_PADDING

    @property
    def help_top(self) -> int:
        """Tọa độ y dòng đầu của bảng phím (bảng phím neo ở đáy cột)."""
        return self.height - PANEL_PADDING - len(self.help_lines) * HELP_STEP

    @property
    def message_capacity(self) -> int:
        """Số dòng thông báo tối đa còn chỗ giữa các nút và bảng phím (ít nhất 1, nhiều nhất MAX_MESSAGE_LINES)."""
        room: int = (self.help_top - 6 - MESSAGE_TOP) // MESSAGE_STEP
        return max(1, min(MAX_MESSAGE_LINES, room))

    # ------------------------------------------------------------------ chuột

    def set_mouse(self, pos: Pixel) -> None:
        """Ghi nhận vị trí con trỏ để tô sáng nút hoặc dòng đang rê chuột."""
        self._mouse = pos

    def handle_click(self, pos: Pixel) -> str | None:
        """Mã hành động của nút (đang bật) được bấm, hoặc None."""
        for button in self.buttons:
            if button.enabled and button.contains(pos):
                return button.action
        return None

    def _sync_buttons(self, hud: HudData) -> None:
        """Đồng bộ nhãn và trạng thái bật/tắt của các nút theo trạng thái hiện hành."""
        buttons: dict[str, Button] = self._button_map
        buttons["cycle_algo"].set_state(
            f"AI: {hud.solver_name}", enabled=not hud.solver_running
        )
        buttons["run_solver"].set_state(
            "Hủy giải" if hud.solver_running else "Giải AI", enabled=True
        )
        buttons["replay_saved"].set_state(enabled=not hud.solver_running)
        playing: bool = hud.replay_active and hud.replay_playing
        buttons["replay_toggle"].set_state(
            "Tạm dừng" if playing else "Tiếp tục", enabled=hud.replay_active
        )
        buttons["step_back"].set_state(enabled=hud.replay_active)
        buttons["step_fwd"].set_state(enabled=hud.replay_active)
        buttons["cycle_speed"].set_state(
            f"Tốc độ {hud.replay_speed_label}", enabled=True
        )
        buttons["stop_replay"].set_state(enabled=hud.replay_active)
        for button in self.buttons:
            button.hovered = button.enabled and button.contains(self._mouse)

    # ------------------------------------------------------------------ vẽ tiện ích

    def _text(
        self, role: str, text: str, x: int, y: int, color: RGB, shadow: bool = True
    ) -> None:
        """Vẽ `text` bằng bộ chữ của vai trò `role` với góc trên-trái ở (x, y)."""
        self.painter.draw_text(self.faces[role], text, x, y, color, shadow)

    def _text_centered(
        self,
        role: str,
        text: str,
        center_x: int,
        y: int,
        color: RGB,
        shadow: bool = True,
    ) -> None:
        """Vẽ `text` căn giữa theo `center_x`."""
        width: int = self.faces[role].measure(text)[0]
        self._text(role, text, center_x - width // 2, y, color, shadow)

    def _dim_window(self) -> None:
        """Làm tối toàn cửa sổ phía sau một hộp thoại."""
        self.painter.fill_rect(
            pygame.Rect(0, 0, self.width, self.height), (0, 0, 0), self.theme.dim_alpha
        )

    def _dialog_rect(self, size: tuple[int, int]) -> pygame.Rect:
        """Hình chữ nhật cỡ `size` đặt giữa cửa sổ."""
        box = pygame.Rect(0, 0, *size)
        box.center = (self.width // 2, self.height // 2)
        return box

    # ------------------------------------------------------------------ cột bên trái

    def _info_rows(self, hud: HudData) -> list[tuple[str, str, RGB]]:
        """Các dòng thông tin (nhãn, giá trị, màu giá trị)."""
        moves: str = (
            f"{hud.moves} (Replay {hud.replay_step}/{hud.replay_total})"
            if hud.replay_active
            else str(hud.moves)
        )
        record_color: RGB = (
            palette.WHITE if hud.best_record == NO_RECORD else palette.GOLD
        )
        uses_color: RGB = palette.GREEN if hud.ai_uses_left > 0 else palette.RED
        return [
            ("Màn", hud.level_name, palette.WHITE),
            ("Số bước", moves, palette.WHITE),
            ("Orientation", hud.orientation, palette.WHITE),
            ("Trạng thái", hud.status, STATUS_COLORS.get(hud.status, palette.WHITE)),
            ("Thời gian", format_elapsed(hud.elapsed), palette.WHITE),
            ("Mật khẩu", hud.passcode or "-", palette.YELLOW),
            ("Tài khoản", hud.username, palette.WHITE),
            ("Kỷ lục", hud.best_record, record_color),
            ("Lượt AI", f"{hud.ai_uses_left}/{MAX_AI_USES_PER_LEVEL}", uses_color),
        ]

    def draw(self, hud: HudData, message: str) -> None:
        """Vẽ cả cột bên trái: tiêu đề, thông tin, nút, thông báo và bảng phím."""
        self._sync_buttons(hud)
        painter, theme, body = self.painter, self.theme, self.faces["body"]
        painter.begin(self.width, self.height)
        painter.tile_texture(
            pygame.Rect(0, 0, PANEL_WIDTH, self.height),
            theme.panel_texture,
            theme.panel_tile,
            theme.panel_tint,
        )
        painter.fill_rect(
            pygame.Rect(PANEL_WIDTH - 4, 0, 2, self.height), theme.panel_edge_light
        )
        painter.fill_rect(
            pygame.Rect(PANEL_WIDTH - 2, 0, 2, self.height), theme.panel_edge
        )

        self._text("title", "BLOXORZ", PANEL_PADDING, TITLE_Y, palette.GOLD)
        for index, (label, value, color) in enumerate(self._info_rows(hud)):
            y: int = INFO_TOP + index * INFO_STEP
            prefix: str = f"{label}: "
            x: int = PANEL_PADDING + body.measure(prefix)[0]
            self._text("body", prefix, PANEL_PADDING, y, theme.label)
            self._text(
                "body",
                fit_text(body, value, PANEL_WIDTH - PANEL_PADDING - x),
                x,
                y,
                color,
            )

        for button in self.buttons:
            button.draw(painter, self.faces, theme)

        if message:
            for index, line in enumerate(
                wrap_text(body, message, self.content_width, self.message_capacity)
            ):
                self._text(
                    "body",
                    line,
                    PANEL_PADDING,
                    MESSAGE_TOP + index * MESSAGE_STEP,
                    theme.message,
                )
        for index, line in enumerate(self.help_lines):
            self._text(
                "small",
                line,
                PANEL_PADDING,
                self.help_top + index * HELP_STEP,
                theme.help,
                shadow=False,
            )
        painter.end()

    # ------------------------------------------------------------------ băng thắng, thua

    def draw_banner(self, banner: Banner) -> None:
        """Băng thông báo thắng hoặc thua, nằm giữa vùng 3D (bên phải cột bảng)."""
        view_w: int = self.width - PANEL_WIDTH
        center_x: int = PANEL_WIDTH + view_w // 2
        top: int = (self.height - BANNER_HEIGHT) // 2
        body: Typeface = self.faces["body"]
        text_width: int = view_w - 2 * BANNER_MARGIN
        self.painter.begin(self.width, self.height)
        self.painter.fill_rect(
            pygame.Rect(PANEL_WIDTH, top, view_w, BANNER_HEIGHT),
            (0, 0, 0),
            self.theme.banner_alpha,
        )
        self._text_centered("banner", banner.title, center_x, top + 20, banner.color)
        for index, line in enumerate(wrap_text(body, banner.subtitle, text_width, 3)):
            self._text_centered(
                "body", line, center_x, top + 82 + index * 22, palette.WHITE
            )
        for index, line in enumerate(wrap_text(body, banner.hint, text_width, 2)):
            self._text_centered(
                "body",
                line,
                center_x,
                top + BANNER_HEIGHT - 64 + index * 22,
                palette.GRAY,
            )
        self.painter.end()

    # ------------------------------------------------------------------ hộp thoại

    def draw_picker(
        self,
        picker: LevelPicker,
        current_index: int,
        is_unlocked: Callable[[int], bool] | None = None,
    ) -> None:
        """Hộp chọn màn: mỗi dòng là một màn, kèm nhãn '(đang chơi)' hoặc '(khóa)'."""
        theme, body, small = self.theme, self.faces["body"], self.faces["small"]
        box, rows = picker.layout(self.width, self.height)
        self.painter.begin(self.width, self.height)
        self._dim_window()
        draw_dialog_box(self.painter, box, theme)
        title: str = fit_text(
            body, f"Chọn màn  ({picker.selected + 1}/{len(picker.names)})", box.w - 32
        )
        self._text(
            "body", title, box.x + 16, box.y + 16, theme.dialog_text, shadow=False
        )

        start, end = picker.visible_range()
        for slot, row in enumerate(rows):
            index: int = start + slot
            selected: bool = index == picker.selected
            hovered: bool = row.collidepoint(self._mouse)
            face: RGB = (
                theme.row_selected
                if selected
                else theme.row_hover
                if hovered
                else theme.row_face
            )
            self.painter.fill_rect(row.inflate(-4, -2), face)
            if selected:
                draw_outline(self.painter, row.inflate(-4, -2), theme.outline)
            locked: bool = is_unlocked is not None and not is_unlocked(index)
            tag, tag_color = "", palette.WHITE
            if index == current_index:
                tag, tag_color = "(đang chơi)", palette.GREEN
            elif locked:
                tag, tag_color = "(khóa)", palette.RED
            tag_width: int = body.measure(tag)[0] if tag else 0
            name: str = fit_text(
                body, picker.names[index], row.w - 24 - tag_width - (12 if tag else 0)
            )
            y: int = text_top(row, body)
            self._text(
                "body", name, row.x + 10, y, palette.GRAY if locked else palette.WHITE
            )
            if tag:
                self._text("body", tag, row.right - 10 - tag_width, y, tag_color)
        self._text_centered(
            "small",
            PICKER_FOOTER,
            box.centerx,
            box.bottom - 26,
            theme.dialog_text,
            shadow=False,
        )
        del small, end
        self.painter.end()

    def draw_prompt(self, prompt: PasscodePrompt) -> None:
        """Hộp nhập mật khẩu của một màn bị khóa: mỗi chữ số một ô lõm."""
        theme, body, title_face = self.theme, self.faces["body"], self.faces["title"]
        box: pygame.Rect = self._dialog_rect(PROMPT_BOX_SIZE)
        self.painter.begin(self.width, self.height)
        self._dim_window()
        draw_dialog_box(self.painter, box, theme)
        heading: str = fit_text(body, f"Nhập mật khẩu của {prompt.title}", box.w - 32)
        self._text_centered(
            "body", heading, box.centerx, box.y + 18, theme.dialog_text, shadow=False
        )

        slot_w, slot_h, gap = 46, 54, 10
        total: int = prompt.max_length * slot_w + (prompt.max_length - 1) * gap
        left: int = box.centerx - total // 2
        for index in range(prompt.max_length):
            slot = pygame.Rect(
                left + index * (slot_w + gap), box.y + 66, slot_w, slot_h
            )
            draw_slot(self.painter, slot, theme)
            if index == len(prompt.text) and index < prompt.max_length:
                draw_outline(self.painter, slot, theme.outline)
            if index < len(prompt.text):
                digit: str = prompt.text[index]
                self._text(
                    "title",
                    digit,
                    slot.centerx - title_face.measure(digit)[0] // 2,
                    text_top(slot, title_face),
                    palette.WHITE,
                )
        if prompt.error:
            self._text_centered(
                "body",
                fit_text(body, prompt.error, box.w - 32),
                box.centerx,
                box.y + 136,
                theme.dialog_error,
                shadow=False,
            )
        self._text_centered(
            "small",
            PROMPT_FOOTER,
            box.centerx,
            box.bottom - 30,
            theme.dialog_text,
            shadow=False,
        )
        self.painter.end()

    def draw_account_prompt(self, prompt: AccountPrompt) -> None:
        """Hộp Đăng nhập / Đăng ký / Đăng xuất tài khoản người chơi."""
        theme, body = self.theme, self.faces["body"]
        box: pygame.Rect = self._dialog_rect(ACCOUNT_BOX_SIZE)
        self.painter.begin(self.width, self.height)
        self._dim_window()
        draw_dialog_box(self.painter, box, theme)
        heading: str = fit_text(
            body, "Tài khoản người chơi (Đăng nhập / Đăng ký)", box.w - 32
        )
        self._text_centered(
            "body", heading, box.centerx, box.y + 16, theme.dialog_text, shadow=False
        )
        self._text_centered(
            "body",
            fit_text(body, prompt.info, box.w - 32),
            box.centerx,
            box.y + 50,
            theme.dialog_ok,
            shadow=False,
        )

        fields: list[tuple[pygame.Rect, str, bool]] = [
            (
                pygame.Rect(box.x + 28, box.y + 84, box.w - 56, 40),
                f"Username: {prompt.username}",
                prompt.active_field == 0,
            ),
            (
                pygame.Rect(box.x + 28, box.y + 138, box.w - 56, 40),
                f"Password: {'*' * len(prompt.password)}",
                prompt.active_field == 1,
            ),
        ]
        for rect, text, active in fields:
            draw_text_field(self.painter, rect, theme, active)
            shown: str = fit_text(body, text + ("|" if active else ""), rect.w - 24)
            self._text("body", shown, rect.x + 12, text_top(rect, body), palette.WHITE)
        if prompt.error:
            self._text_centered(
                "body",
                fit_text(body, prompt.error, box.w - 32),
                box.centerx,
                box.y + 196,
                theme.dialog_error,
                shadow=False,
            )
        self._text_centered(
            "small",
            ACCOUNT_FOOTER,
            box.centerx,
            box.bottom - 30,
            theme.dialog_text,
            shadow=False,
        )
        self.painter.end()