"""Bảng màu và kích thước của giao diện kiểu Minecraft."""

from dataclasses import dataclass

from gui import palette
from gui.palette import RGB


@dataclass(frozen=True)
class Theme:
    """Mọi màu sắc của giao diện; đổi giao diện chỉ cần tạo một `Theme` khác."""

    # nền cột bên trái: gạch đá lát tối màu
    panel_texture: str = "floor"
    panel_tile: int = 64
    panel_tint: RGB = (72, 72, 72)
    panel_edge: RGB = (0, 0, 0)
    panel_edge_light: RGB = (96, 96, 96)

    # nút
    border: RGB = (0, 0, 0)
    button_face: RGB = (111, 111, 111)
    button_light: RGB = (165, 165, 165)
    button_dark: RGB = (63, 63, 63)
    hover_face: RGB = (125, 134, 192)
    hover_light: RGB = (172, 180, 232)
    hover_dark: RGB = (62, 66, 112)
    disabled_face: RGB = (69, 69, 69)
    disabled_light: RGB = (88, 88, 88)
    disabled_dark: RGB = (45, 45, 45)
    text: RGB = palette.WHITE
    text_hover: RGB = (255, 255, 160)
    text_disabled: RGB = (160, 160, 160)
    hint: RGB = (205, 205, 205)
    hint_padding: int = 4

    # chữ trên nền tối
    label: RGB = palette.GRAY
    message: RGB = palette.GOLD
    help: RGB = (195, 195, 205)

    # hộp thoại kiểu túi đồ
    dim_alpha: float = 0.6
    dialog_face: RGB = (198, 198, 198)
    dialog_light: RGB = (255, 255, 255)
    dialog_dark: RGB = (85, 85, 85)
    dialog_text: RGB = (64, 64, 64)
    dialog_ok: RGB = (0, 120, 0)
    dialog_error: RGB = (170, 0, 0)
    slot_face: RGB = (139, 139, 139)
    row_face: RGB = (55, 55, 55)
    row_hover: RGB = (78, 78, 78)
    row_selected: RGB = (96, 96, 96)
    outline: RGB = palette.WHITE
    field_face: RGB = (0, 0, 0)
    field_idle_border: RGB = (139, 139, 139)

    # băng thắng, thua
    banner_alpha: float = 0.62

    def button_colors(self, enabled: bool, hovered: bool) -> tuple[RGB, RGB, RGB, RGB]:
        """(nền, mép sáng, mép tối, màu chữ) của nút theo trạng thái."""
        if not enabled:
            return (
                self.disabled_face,
                self.disabled_light,
                self.disabled_dark,
                self.text_disabled,
            )
        if hovered:
            return self.hover_face, self.hover_light, self.hover_dark, self.text_hover
        return self.button_face, self.button_light, self.button_dark, self.text


MINECRAFT: Theme = Theme()
