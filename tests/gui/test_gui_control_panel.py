"""Test cho gui.ui.control_panel.ControlPanel: nút, thông tin, thông báo, băng thắng và các hộp thoại."""

import os
from collections.abc import Mapping

import pygame
import pytest

from gui.model.account_prompt import AccountPrompt
from gui.model.level_picker import LevelPicker
from gui.model.passcode_prompt import PasscodePrompt
from gui.shared import palette
from gui.shared.viewmodels import Banner, HudData
from gui.ui import control_panel as cp
from gui.ui.painter import RecordingPainter
from gui.ui.pixel_font import MONOCRAFT_PATH, ROLE_SCALES, MinecraftTypeface, Typeface
from gui.ui.theme import MINECRAFT

pygame.font.init()
THEME = MINECRAFT


class FixedTypeface(Typeface):
    """Bộ chữ giả: mỗi ký tự rộng 6 x scale, cao 9 x scale."""

    def __init__(self, scale: int = 1) -> None:
        self.scale = scale
        self.top_padding = 4 * scale

    def measure(self, text: str) -> tuple[int, int]:
        return len(text) * 6 * self.scale, 9 * self.scale

    def render(
        self, text: str, color: tuple[int, int, int], shadow: bool = True
    ) -> pygame.Surface:
        return pygame.Surface(
            (max(1, len(text) * 6 * self.scale), 15 * self.scale), pygame.SRCALPHA
        )


@pytest.fixture(params=["fixed", "real"])
def faces(request: pytest.FixtureRequest) -> Mapping[str, Typeface]:
    if request.param == "real":
        if not os.path.exists(MONOCRAFT_PATH):
            pytest.skip("thiếu assets/fonts/Monocraft.ttf")
        return {
            role: MinecraftTypeface(MONOCRAFT_PATH, scale)
            for role, (scale, _) in ROLE_SCALES.items()
        }
    return {role: FixedTypeface(scale) for role, (scale, _) in ROLE_SCALES.items()}


@pytest.fixture
def parts(faces: Mapping[str, Typeface]) -> tuple[cp.ControlPanel, RecordingPainter]:
    painter = RecordingPainter()
    return cp.ControlPanel(1280, 768, painter, faces), painter


def hud(**changes: object) -> HudData:
    base = HudData(
        "Stage 01", 3, "STANDING", "PLAYING", 3.14, "780464", "guest", "Chưa có", "BFS"
    )
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def button(panel: cp.ControlPanel, action: str) -> cp.Button:
    return next(b for b in panel.buttons if b.action == action)


def message_lines(panel: cp.ControlPanel, painter: RecordingPainter) -> list:
    """Các dòng thông báo (lọc theo vị trí vì tiêu đề cũng màu vàng)."""
    return [
        c
        for c in painter.text_commands()
        if c.color == THEME.message and cp.MESSAGE_TOP <= c.pos[1] < panel.help_top
    ]


def inside(
    painter: RecordingPainter, area: pygame.Rect, color: tuple[int, int, int]
) -> int:
    """Số hình chữ nhật màu `color` nằm trọn trong `area`."""
    return len([r for r in painter.rects(color) if area.contains(r)])


def color_of(painter: RecordingPainter, text: str) -> tuple[int, int, int]:
    return painter.text_commands(text)[0].color  # type: ignore[return-value]


# ---------------------------------------------------------------- nút


def test_format_elapsed() -> None:
    assert cp.format_elapsed(0) == "00:00.0" and cp.format_elapsed(75.3) == "01:15.3"


def test_replay_buttons_start_disabled_and_do_not_react_to_clicks(parts) -> None:
    panel, _ = parts
    assert panel.handle_click(button(panel, "step_back").rect.center) is None
    assert panel.handle_click(button(panel, "restart").rect.center) == "restart"
    assert panel.handle_click((cp.PANEL_WIDTH + 50, 300)) is None


def test_every_enabled_button_returns_its_own_action(parts) -> None:
    panel, _ = parts
    panel.draw(hud(replay_active=True), "")
    for each in panel.buttons:
        assert panel.handle_click(each.rect.center) == each.action


def test_replay_state_enables_and_labels_the_replay_buttons(parts) -> None:
    panel, _ = parts
    panel.draw(
        hud(replay_active=True, replay_playing=True, replay_speed_label="2x"), ""
    )
    assert (
        button(panel, "replay_toggle").label == "Tạm dừng"
        and button(panel, "cycle_speed").label == "Tốc độ 2x"
    )
    assert all(
        button(panel, a).enabled
        for a in ("replay_toggle", "step_back", "step_fwd", "stop_replay")
    )
    panel.draw(hud(replay_active=True, replay_playing=False), "")
    assert button(panel, "replay_toggle").label == "Tiếp tục"
    panel.draw(hud(), "")
    assert not any(
        button(panel, a).enabled
        for a in ("replay_toggle", "step_back", "step_fwd", "stop_replay")
    )


def test_solving_state_locks_the_algorithm_and_saved_replay_buttons(parts) -> None:
    panel, _ = parts
    panel.draw(hud(solver_running=True, solver_name="A*"), "")
    assert (
        button(panel, "run_solver").label == "Hủy giải"
        and button(panel, "run_solver").enabled
    )
    assert (
        button(panel, "cycle_algo").label == "AI: A*"
        and not button(panel, "cycle_algo").enabled
    )
    assert not button(panel, "replay_saved").enabled
    panel.draw(hud(), "")
    assert (
        button(panel, "run_solver").label == "Giải AI"
        and button(panel, "cycle_algo").enabled
    )


def test_button_text_color_follows_replay_state_every_frame(parts) -> None:
    """Sửa lỗi cũ: nút bật lên nhưng chữ vẫn xám."""
    panel, painter = parts
    panel.draw(hud(), "")
    assert color_of(painter, "<< Bước") == THEME.text_disabled
    painter.clear()
    panel.draw(hud(replay_active=True), "")
    assert color_of(painter, "<< Bước") == THEME.text
    painter.clear()
    panel.draw(hud(), "")
    assert color_of(painter, "<< Bước") == THEME.text_disabled


def test_hovering_highlights_enabled_buttons_only(parts) -> None:
    panel, painter = parts
    panel.set_mouse(button(panel, "restart").rect.center)
    panel.draw(hud(), "")
    assert (
        color_of(painter, "Restart") == THEME.text_hover
        and color_of(painter, "Undo") == THEME.text
    )
    painter.clear()
    panel.set_mouse(button(panel, "step_back").rect.center)  # nút đang tắt
    panel.draw(hud(), "")
    assert color_of(painter, "<< Bước") == THEME.text_disabled
    panel.set_mouse((-1, -1))
    painter.clear()
    panel.draw(hud(), "")
    assert color_of(painter, "Restart") == THEME.text


def test_key_hints_appear_on_buttons_with_room(parts) -> None:
    panel, painter = parts
    panel.draw(hud(), "")
    hints = {c.text for c in painter.text_commands() if len(c.text) == 1}
    assert {"R", "N", "Z", "L", "M", "F"} <= hints


# ---------------------------------------------------------------- thông tin và thông báo


def test_info_rows_show_the_game_state_with_colors(parts) -> None:
    panel, painter = parts
    panel.draw(hud(status="WON", best_record="7 bước (6.2s)", ai_uses_left=0), "")
    texts = painter.texts()
    assert {
        "Stage 01",
        "00:03.1",
        "780464",
        "guest",
        "0/2",
        "WON",
        "7 bước (6.2s)",
    } <= set(texts)
    assert (
        color_of(painter, "WON") == palette.GOLD
        and color_of(painter, "0/2") == palette.RED
    )
    assert (
        color_of(painter, "7 bước (6.2s)") == palette.GOLD
        and color_of(painter, "780464") == palette.YELLOW
    )


def test_info_color_for_playing_and_available_ai_uses(parts) -> None:
    panel, painter = parts
    panel.draw(hud(ai_uses_left=2), "")
    assert (
        color_of(painter, "PLAYING") == palette.GREEN
        and color_of(painter, "2/2") == palette.GREEN
    )
    assert color_of(painter, "Chưa có") == palette.WHITE


def test_replay_progress_is_shown_next_to_the_move_count(parts) -> None:
    panel, painter = parts
    panel.draw(hud(moves=5, replay_active=True, replay_step=2, replay_total=4), "")
    assert "5 (Replay 2/4)" in painter.texts()


def test_an_overlong_value_is_truncated_not_overflowing(parts) -> None:
    panel, painter = parts
    panel.draw(hud(level_name="X" * 120), "")
    shown = next(c for c in painter.text_commands() if c.text.startswith("XX"))
    assert (
        shown.text.endswith("..")
        and shown.rect.right <= cp.PANEL_WIDTH - cp.PANEL_PADDING
    )


def test_message_is_wrapped_within_the_available_lines(parts) -> None:
    panel, painter = parts
    panel.draw(hud(), "một thông báo rất dài " * 30)
    lines = message_lines(panel, painter)
    assert 1 <= len(lines) <= panel.message_capacity and lines[-1].text.endswith("..")
    assert all(c.rect.right <= cp.PANEL_WIDTH - cp.PANEL_PADDING for c in lines)
    assert [c.pos[1] for c in lines] == [
        cp.MESSAGE_TOP + i * cp.MESSAGE_STEP for i in range(len(lines))
    ]


def test_short_message_fits_on_one_line_and_no_message_draws_nothing(parts) -> None:
    panel, painter = parts
    panel.draw(hud(), "Xin chào")
    assert [c.text for c in message_lines(panel, painter)] == ["Xin chào"]
    painter.clear()
    panel.draw(hud(), "")
    assert not message_lines(panel, painter)


def test_help_block_is_drawn_at_the_bottom(parts) -> None:
    panel, painter = parts
    panel.draw(hud(), "")
    help_lines = [c for c in painter.text_commands() if c.color == THEME.help]
    assert [c.text for c in help_lines] == panel.help_lines
    assert help_lines[0].pos[1] == panel.help_top and all(
        not c.shadow for c in help_lines
    )


def test_each_draw_call_is_wrapped_in_begin_and_end(parts) -> None:
    panel, painter = parts
    picker = LevelPicker(["Stage 01", "Stage 02"])
    picker.open(0)
    calls = [
        lambda: panel.draw(hud(), "x"),
        lambda: panel.draw_banner(Banner("a", "b", "c", palette.GREEN)),
        lambda: panel.draw_picker(picker, 0, None),
        lambda: panel.draw_prompt(_prompt("")),
        lambda: panel.draw_account_prompt(AccountPrompt()),
    ]
    for call in calls:
        painter.clear()
        call()
        kinds = [c.kind for c in painter.commands]
        assert (
            kinds[0] == "begin"
            and kinds[-1] == "end"
            and kinds.count("begin") == kinds.count("end") == 1
        )
        assert painter.commands[0].size == (1280, 768)


def test_the_column_is_tiled_with_the_stone_texture(parts) -> None:
    panel, painter = parts
    panel.draw(hud(), "")
    tiles = [c for c in painter.commands if c.kind == "tiles"]
    assert (
        len(tiles) == 1
        and tiles[0].texture == THEME.panel_texture
        and tiles[0].rect == pygame.Rect(0, 0, 340, 768)
    )


def test_a_missing_banner_face_falls_back_to_the_title_face() -> None:
    faces = {
        "title": FixedTypeface(3),
        "body": FixedTypeface(2),
        "small": FixedTypeface(1),
    }
    panel = cp.ControlPanel(1280, 768, RecordingPainter(), faces)
    assert panel.faces["banner"] is faces["title"]


# ---------------------------------------------------------------- băng thắng, thua


def test_banner_is_centered_in_the_3d_area_with_a_translucent_band(parts) -> None:
    panel, painter = parts
    view_w = 1280 - cp.PANEL_WIDTH
    panel.draw_banner(
        Banner(
            "HOÀN THÀNH!",
            "Bạn đã thắng " * 30,
            "Enter: sang màn kế " * 20,
            palette.GREEN,
        )
    )
    band = next(c for c in painter.commands if c.kind == "rect")
    assert band.rect == pygame.Rect(
        cp.PANEL_WIDTH, (768 - cp.BANNER_HEIGHT) // 2, view_w, cp.BANNER_HEIGHT
    )
    assert band.alpha == THEME.banner_alpha and band.color == (0, 0, 0)
    title = painter.text_commands("HOÀN THÀNH!")[0]
    assert title.color == palette.GREEN and title.typeface is panel.faces["banner"]
    assert abs(title.rect.centerx - (cp.PANEL_WIDTH + view_w // 2)) <= 2
    texts = [c for c in painter.text_commands() if c is not title]
    assert (
        len([c for c in texts if c.color == palette.WHITE]) <= 3
        and len([c for c in texts if c.color == palette.GRAY]) <= 2
    )
    assert all(band.rect.contains(c.rect) for c in painter.text_commands())


# ---------------------------------------------------------------- hộp chọn màn


def make_picker(count: int = 33, selected: int = 0) -> LevelPicker:
    picker = LevelPicker([f"Stage {i + 1:02d}" for i in range(count)])
    picker.open(selected)
    return picker


def test_picker_tags_the_current_level_and_locked_levels(parts) -> None:
    panel, painter = parts
    picker = make_picker()
    panel.draw_picker(picker, 0, lambda index: index < 2)
    texts = painter.texts()
    assert (
        texts.count("(đang chơi)") == 1
        and texts.count("(khóa)") == picker.visible_rows - 2
    )
    assert "Chọn màn  (1/33)" in texts
    assert (
        color_of(painter, "Stage 02") == palette.WHITE
        and color_of(painter, "Stage 03") == palette.GRAY
    )
    assert (
        color_of(painter, "(đang chơi)") == palette.GREEN
        and color_of(painter, "(khóa)") == palette.RED
    )


def test_picker_without_lock_information_shows_no_lock_tags(parts) -> None:
    panel, painter = parts
    panel.draw_picker(make_picker(), 3, None)
    assert "(khóa)" not in painter.texts() and painter.texts().count("(đang chơi)") == 1


def test_picker_highlights_the_selected_row_and_dims_the_window(parts) -> None:
    panel, painter = parts
    picker = make_picker(selected=4)
    panel.draw_picker(picker, 0, None)
    dim = next(c for c in painter.commands if c.kind == "rect")
    assert dim.rect == pygame.Rect(0, 0, 1280, 768) and dim.alpha == THEME.dim_alpha
    _, rows = picker.layout(1280, 768)
    assert (
        inside(painter, rows[4], THEME.outline) == 4
    )  # viền trắng quanh dòng đang chọn
    assert all(inside(painter, rows[i], THEME.outline) == 0 for i in (0, 1, 2, 3, 5))
    assert len(painter.rects(THEME.row_selected)) == 1


def test_picker_rows_sit_where_the_picker_layout_says(parts) -> None:
    panel, painter = parts
    picker = make_picker()
    panel.draw_picker(picker, 0, None)
    box, rows = picker.layout(1280, 768)
    name = painter.text_commands("Stage 05")[0]
    assert rows[4].contains(name.rect) and box.contains(name.rect)


def test_picker_row_under_the_mouse_is_lit(parts) -> None:
    panel, painter = parts
    picker = make_picker()
    _, rows = picker.layout(1280, 768)
    panel.set_mouse(rows[3].center)
    panel.draw_picker(picker, 0, None)
    assert len(painter.rects(THEME.row_hover)) == 1


def test_picker_shows_the_footer_hint(parts) -> None:
    panel, painter = parts
    panel.draw_picker(make_picker(), 0, None)
    assert cp.PICKER_FOOTER in painter.texts()


# ---------------------------------------------------------------- hộp mật khẩu


def _prompt(text: str, error: str = "") -> PasscodePrompt:
    prompt = PasscodePrompt(6)
    prompt.open(2, "Stage 03")
    for digit in text:
        prompt.type_digit(digit)
    if error:
        prompt.fail(error)
    return prompt


def test_prompt_draws_six_slots_and_the_typed_digits(parts) -> None:
    panel, painter = parts
    panel.draw_prompt(_prompt("12"))
    assert len(painter.rects(THEME.slot_face)) == 6
    digits = painter.text_commands("1") + painter.text_commands("2")
    assert len(digits) == 2 and all(
        c.color == palette.WHITE and c.typeface is panel.faces["title"] for c in digits
    )
    assert "Nhập mật khẩu của Stage 03" in painter.texts()
    slots = [
        inner.inflate(2, 2) for inner in painter.rects(THEME.slot_face)
    ]  # rect trả về là phần ruột; lấy ô ngoài
    # mỗi ô có sẵn 2 mép sáng của khung lõm; ô đang chờ nhập có thêm viền trắng 4 cạnh
    assert (
        inside(painter, slots[2], THEME.outline)
        - inside(painter, slots[3], THEME.outline)
        == 4
    )


def test_prompt_digits_sit_inside_their_slots(parts) -> None:
    panel, painter = parts
    panel.draw_prompt(_prompt("123456"))
    slots = [inner.inflate(2, 2) for inner in painter.rects(THEME.slot_face)]
    digits = [painter.text_commands(d)[0] for d in "123456"]
    assert all(slot.contains(digit.rect) for slot, digit in zip(slots, digits))
    assert all(
        inside(painter, slot, THEME.outline) == 2 for slot in slots
    )  # đủ chữ số: không ô nào đang chờ


def test_prompt_shows_the_error_in_red(parts) -> None:
    panel, painter = parts
    panel.draw_prompt(_prompt("", error="Sai mật khẩu."))
    assert color_of(painter, "Sai mật khẩu.") == THEME.dialog_error
    painter.clear()
    panel.draw_prompt(_prompt(""))
    assert all(c.color != THEME.dialog_error for c in painter.text_commands())


def test_prompt_box_is_centered(parts) -> None:
    panel, painter = parts
    panel.draw_prompt(_prompt(""))
    box = next(
        c.rect
        for c in painter.commands
        if c.kind == "rect" and c.rect.size == cp.PROMPT_BOX_SIZE
    )
    assert box.center == (640, 384)


# ---------------------------------------------------------------- hộp tài khoản


def test_account_dialog_masks_the_password_and_marks_the_active_field(parts) -> None:
    panel, painter = parts
    prompt = AccountPrompt()
    prompt.open("an")
    for ch in "abc":
        prompt.type_char(ch)
    panel.draw_account_prompt(prompt)  # đang ở ô mật khẩu (open với tên người dùng)
    texts = painter.texts()
    assert "Username: an" in texts and "Password: ***|" in texts
    user, password = [r for r in painter.rects(THEME.field_face) if r.size == (504, 40)]
    assert (
        inside(painter, password, THEME.outline) == 4
        and inside(painter, user, THEME.outline) == 0
    )
    assert (
        inside(painter, user, THEME.field_idle_border) == 4
    )  # ô không chọn có viền xám


def test_account_dialog_cursor_follows_the_active_field(parts) -> None:
    panel, painter = parts
    prompt = AccountPrompt()
    prompt.open(None)
    prompt.type_char("a")
    panel.draw_account_prompt(prompt)
    assert "Username: a|" in painter.texts() and "Password: " in painter.texts()


def test_account_dialog_shows_info_and_error_with_their_colors(parts) -> None:
    panel, painter = parts
    prompt = AccountPrompt()
    prompt.open("an")
    prompt.fail("Mật khẩu không chính xác.")
    panel.draw_account_prompt(prompt)
    assert color_of(painter, "Mật khẩu không chính xác.") == THEME.dialog_error
    assert color_of(painter, prompt.info) == THEME.dialog_ok
    assert cp.ACCOUNT_FOOTER in painter.texts()


def test_account_dialog_long_text_never_leaves_its_box(parts) -> None:
    panel, painter = parts
    prompt = AccountPrompt(max_length=60)
    prompt.open(None)
    for ch in "x" * 60:
        prompt.type_char(ch)
    prompt.fail("lỗi " * 40)
    panel.draw_account_prompt(prompt)
    box = next(
        c.rect
        for c in painter.commands
        if c.kind == "rect" and c.rect.size == cp.ACCOUNT_BOX_SIZE
    )
    assert all(box.contains(c.rect) for c in painter.text_commands())
