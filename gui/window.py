import pygame
from core.block import Direction
from core.game import Game, GameStatus
from core.transition import MoveResult
from OpenGL.GL import (
    GL_DEPTH_TEST,
    GL_MODELVIEW,
    GL_PROJECTION,
    glEnable,
    glLoadIdentity,
    glMatrixMode,
    glViewport,
)
from OpenGL.GLU import gluPerspective
from pygame.locals import (
    DOUBLEBUF,
    K_BACKSPACE,
    K_DOWN,
    K_ESCAPE,
    K_KP_ENTER,
    K_LEFT,
    K_PAGEDOWN,
    K_PAGEUP,
    K_RETURN,
    K_RIGHT,
    K_SPACE,
    K_UP,
    KEYDOWN,
    KMOD_SHIFT,
    MOUSEBUTTONDOWN,
    MOUSEBUTTONUP,
    MOUSEMOTION,
    MOUSEWHEEL,
    OPENGL,
    QUIT,
    K_a,
    K_c,
    K_d,
    K_n,
    K_r,
    K_s,
    K_w,
)

from gui.animator import Animator, Phase
from gui.control_panel import (
    LOSE_COLOR,
    PANEL_WIDTH,
    WIN_COLOR,
    Banner,
    ControlPanel,
    HudData,
)
from gui.geometry import Cell, broken_fragile_cell
from gui.level_catalog import LevelCatalog
from gui.level_picker import LevelPicker
from gui.passcode_prompt import PasscodePrompt, digit_from_key
from gui.renderer import FOV_DEGREES, Renderer, load_textures

KEY_TO_DIRECTION: dict[int, Direction] = {
    K_UP: Direction.UP,
    K_w: Direction.UP,
    K_DOWN: Direction.DOWN,
    K_s: Direction.DOWN,
    K_LEFT: Direction.LEFT,
    K_a: Direction.LEFT,
    K_RIGHT: Direction.RIGHT,
    K_d: Direction.RIGHT,
}

MSG_ENDED: str = "Ván đã kết thúc. Nhấn R để chơi lại."
SUBTITLE_FALL: str = "Khối đã rơi."
SUBTITLE_WON: str = "Bạn đã đưa khối vào ô đích."
HINT_LOST: str = "Nhấn R hoặc bấm Restart để chơi lại. Nhấn N để chọn màn khác."
HINT_WON: str = "Nhấn N để chọn màn khác, hoặc R để chơi lại."
HINT_WON_NEXT: str = "Enter: sang màn kế tiếp  -  N: chọn màn  -  R: chơi lại"
SUBTITLE_ALL_DONE: str = "Bạn đã hoàn thành tất cả các màn."
MSG_WRONG_PASSCODE: str = "Sai mật khẩu."
MAX_FRAME_SECONDS: float = 0.1


class Window:
    def __init__(
        self,
        game: Game,
        level_name: str = "",
        width: int = 1280,
        height: int = 768,
        catalog: LevelCatalog | None = None,
    ) -> None:
        self.game: Game = game
        self.level_name: str = getattr(game.board, "name", "") or level_name
        self.width: int = width
        self.height: int = height
        self.running: bool = True

        pygame.init()
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Bloxorz")
        pygame.key.stop_text_input()  # game không nhập chữ: tránh để bộ gõ (Unikey, Bamboo...) chặn phím chữ

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.aspect: float = (width - PANEL_WIDTH) / height  # chỉ vùng bên phải cột bảng dùng cho cảnh 3D
        gluPerspective(FOV_DEGREES, self.aspect, 0.1, 1000)
        glMatrixMode(GL_MODELVIEW)

        # Tạo sau set_mode vì cần ngữ cảnh OpenGL
        self.textures: dict[str, int] = load_textures()
        self.renderer: Renderer = Renderer(game.board, self.aspect, self.textures)
        self.panel: ControlPanel = ControlPanel(width, height)
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.animator: Animator = Animator()

        if catalog is None:
            try:
                catalog = LevelCatalog.from_json()
            except FileNotFoundError:
                catalog = LevelCatalog([])
        self.catalog: LevelCatalog = catalog
        self.level_index: int = catalog.index_of(self.level_name)
        catalog.unlock(self.level_index)  # màn đang chơi luôn được mở
        self.picker: LevelPicker = LevelPicker(catalog.names)
        self.prompt: PasscodePrompt = PasscodePrompt(catalog.passcode_length)
        self._next_index: int | None = None

        self._drag: str | None = None
        self._mouse: tuple[int, int] = (0, 0)

        self.elapsed: float = 0.0
        self.message: str = ""
        self.banner: Banner | None = None
        self.block_visible: bool = True
        self.shown_moves: int = 0
        self.shown_status: GameStatus = game.status
        self._pending: Banner | None = None
        self.broken_tiles: frozenset[Cell] = frozenset()
        self._pending_broken: Cell | None = None
        self._reset_view_state()

    # ------------------------------------------------------------------ vòng lặp

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, MAX_FRAME_SECONDS)
            for event in pygame.event.get():
                self.process_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == QUIT:
            self.running = False
        elif event.type == KEYDOWN:
            self.handle_key(event.key, getattr(event, "unicode", ""))
        elif event.type == MOUSEBUTTONDOWN:
            self.handle_mouse_down(event.button, event.pos)
        elif event.type == MOUSEBUTTONUP:
            self.handle_mouse_up(event.button)
        elif event.type == MOUSEMOTION:
            self.handle_mouse_motion(event.pos, event.rel)
        elif event.type == MOUSEWHEEL:
            self.handle_wheel(event.y)

    def update(self, dt: float) -> None:
        # Đồng hồ chạy từ lúc tải màn; dừng khi ván kết thúc hoặc đang mở hộp chọn màn
        if not self.picker.is_open and self.game.status == GameStatus.PLAYING:
            self.elapsed += dt
        self.renderer.camera.update(dt)
        if self.animator.update(dt):
            self._finish_animation()
        elif self.animator.active and self.animator.phase == Phase.FALL and self._pending_broken is not None:
            self.broken_tiles = frozenset({self._pending_broken})  # ô giòn vỡ đúng lúc khối bắt đầu rơi

    def draw(self) -> None:
        glViewport(PANEL_WIDTH, 0, self.width - PANEL_WIDTH, self.height)
        if self.animator.active:
            state, pose = self.animator.display_state, self.animator.pose
        else:
            state, pose = self.game.state, None
        self.renderer.draw(state, pose, self.block_visible, self.broken_tiles)

        glViewport(0, 0, self.width, self.height)
        hud = HudData(
            self.level_name,
            self.shown_moves,
            state.orientation.name,
            self.shown_status.name,
            self.elapsed,
            getattr(self.game.board, "passcode", ""),
        )
        self.panel.draw(hud, self.message)
        if self.banner is not None:
            self.panel.draw_banner(self.banner)
        if self.picker.is_open:
            self.panel.draw_picker(self.picker, self.level_index, self.catalog.is_unlocked)
        if self.prompt.is_open:
            self.panel.draw_prompt(self.prompt)

    # ------------------------------------------------------------------ bàn phím

    def handle_key(self, key: int, text: str = "") -> None:
        if self.prompt.is_open:
            self._handle_prompt_key(key, text)
            return
        if self.picker.is_open:
            self._handle_picker_key(key)
            return
        if key == K_r:
            self.restart()
            return
        if key == K_c:
            self.renderer.camera.start_reset()
            return
        if key == K_n:
            self.open_picker()
            return
        if key in (K_RETURN, K_KP_ENTER) and self.banner is not None and self._next_index is not None:
            self.load_stage(self._next_index)  # thắng rồi thì sang màn kế tiếp, không cần mật khẩu
            return
        if self.animator.active:  # bỏ qua phím di chuyển khi đang hoạt cảnh
            return

        direction = KEY_TO_DIRECTION.get(key)
        if direction is not None:
            self._move(direction)
        elif key == K_SPACE:
            self._switch()

    def _handle_picker_key(self, key: int) -> None:
        if key in (K_ESCAPE, K_n):
            self.picker.close()
        elif key in (K_UP, K_w):
            self.picker.move(-1)
        elif key in (K_DOWN, K_s):
            self.picker.move(1)
        elif key == K_PAGEUP:
            self.picker.page(-1)
        elif key == K_PAGEDOWN:
            self.picker.page(1)
        elif key in (K_RETURN, K_KP_ENTER):
            self.select_stage(self.picker.selected)

    def _handle_prompt_key(self, key: int, text: str) -> None:
        if key == K_ESCAPE:
            self.prompt.close()
            self.open_picker()
        elif key == K_BACKSPACE:
            self.prompt.backspace()
        elif key in (K_RETURN, K_KP_ENTER):
            self._submit_passcode()
        else:
            digit = digit_from_key(key, text)
            if digit is not None:
                self.prompt.type_digit(digit)

    def _submit_passcode(self) -> None:
        if len(self.prompt.text) < self.prompt.max_length:
            self.prompt.fail(f"Mật khẩu gồm {self.prompt.max_length} chữ số.")
        elif self.catalog.unlock_with_passcode(self.prompt.target, self.prompt.text):
            self.load_stage(self.prompt.target)
        else:
            self.prompt.fail(MSG_WRONG_PASSCODE)

    def _move(self, direction: Direction) -> None:
        if self.game.is_over():
            self.message = MSG_ENDED
            return
        old_state = self.game.state
        outcome = self.game.move(direction)
        if outcome is None:
            self.message = MSG_ENDED
            return

        self.message = ""
        self._pending_broken = None
        if outcome.result == MoveResult.FALL:
            # Khối đứng thẳng trên ô giòn: ô vỡ và rơi cùng khối
            self._pending_broken = broken_fragile_cell(self.game.board, outcome.state)
            self.animator.start_fall(old_state, direction, self._pending_broken)
            self._pending = Banner("THUA!", outcome.message or SUBTITLE_FALL, HINT_LOST, LOSE_COLOR)
        elif self.game.is_won():
            self.animator.start_win(old_state, direction, self.game.state)
            self._pending = self._won_banner()
        else:
            self.animator.start_roll(old_state, direction, self.game.state)
            self._pending = None

    def _won_banner(self) -> Banner:
        """Mở khóa màn kế tiếp và cho biết mật khẩu của nó (như game gốc)."""
        self._next_index = self.catalog.next_index(self.level_index) if self.level_index >= 0 else None
        if self._next_index is None:
            return Banner(
                "HOÀN THÀNH!",
                f"{SUBTITLE_WON} {SUBTITLE_ALL_DONE}",
                HINT_WON,
                WIN_COLOR,
            )
        self.catalog.unlock(self._next_index)
        entry = self.catalog.entries[self._next_index]
        subtitle = (
            # f"{SUBTITLE_WON} Màn kế tiếp: {entry.name}, mật khẩu {entry.passcode}."
            f"{SUBTITLE_WON} Màn kế tiếp: {entry.name}."
        )
        return Banner("HOÀN THÀNH!", subtitle, HINT_WON_NEXT, WIN_COLOR)

    def _switch(self) -> None:
        """Đổi khối đang điều khiển khi đang tách; không có hoạt cảnh."""
        if self.game.move("SWITCH") is not None:
            self.message = ""

    def _finish_animation(self) -> None:
        self.shown_moves = self.game.moves
        self.shown_status = self.game.status
        if self._pending_broken is not None:
            self.broken_tiles = frozenset({self._pending_broken})
            self._pending_broken = None
        if self._pending is not None:
            self.banner = self._pending
            self._pending = None
            self.block_visible = False

    # ------------------------------------------------------------------ chuột và camera

    def handle_mouse_down(self, button: int, pos: tuple[int, int]) -> None:
        if self.prompt.is_open:
            return
        if self.picker.is_open:
            if button == 1:
                row = self.picker.row_at(pos, self.width, self.height)
                if row is not None:
                    self.select_stage(row)
                elif not self.picker.box_contains(pos, self.width, self.height):
                    self.picker.close()
            return
        if button == 1:
            action = self.panel.handle_click(pos)
            if action == "restart":
                self.restart()
            elif action == "new_game":
                self.open_picker()
        elif button in (2, 3) and pos[0] >= PANEL_WIDTH:
            shift = pygame.key.get_mods() & KMOD_SHIFT
            self._drag = "pan" if (button == 2 or shift) else "orbit"

    def handle_mouse_up(self, button: int) -> None:
        if button in (2, 3):
            self._drag = None

    def handle_mouse_motion(self, pos: tuple[int, int], rel: tuple[int, int]) -> None:
        self._mouse = pos
        if self._drag == "orbit":
            self.renderer.camera.orbit(rel[0], rel[1])
        elif self._drag == "pan":
            self.renderer.camera.pan(rel[0], rel[1])

    def handle_wheel(self, steps: int) -> None:
        if self.picker.is_open:
            self.picker.scroll_by(-steps)
        elif self._mouse[0] >= PANEL_WIDTH:
            self.renderer.camera.zoom(steps)

    # ------------------------------------------------------------------ ván chơi và màn

    def open_picker(self) -> None:
        if len(self.catalog) == 0:
            self.message = "Không tìm thấy dữ liệu màn chơi (coolmath.json)."
            return
        self.picker.open(max(self.level_index, 0))

    def restart(self) -> None:
        self.game.restart()
        self._reset_view_state()

    def select_stage(self, index: int) -> None:
        """Chọn một màn trong danh sách: màn đã mở thì vào ngay, màn khóa thì phải nhập mật khẩu."""
        if not 0 <= index < len(self.catalog):
            return
        if index == self.level_index:
            self.picker.close()
        elif self.catalog.is_unlocked(index):
            self.load_stage(index)
        else:
            self.picker.close()
            self.prompt.open(index, self.catalog.entries[index].name)

    def load_stage(self, index: int) -> None:
        if not 0 <= index < len(self.catalog):
            return
        entry = self.catalog.entries[index]
        try:
            game = Game(self.catalog.board(index))
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            OSError,
        ) as error:  # màn hỏng thì giữ màn hiện tại
            self.picker.close()
            self.prompt.close()
            self.message = f"Không nạp được {entry.name}: {error}"
            return
        self.renderer.dispose()
        self.game = game
        self.renderer = Renderer(game.board, self.aspect, self.textures)
        self.level_name = entry.name
        self.level_index = index
        self.catalog.unlock(index)
        self.picker.close()
        self.prompt.close()
        self._reset_view_state()

    def _reset_view_state(self) -> None:
        self.animator.cancel()
        self.elapsed = 0.0
        self.banner = None
        self._pending = None
        self._next_index = None
        self.block_visible = True
        self.broken_tiles = frozenset()
        self._pending_broken = None
        self.message = ""
        self.shown_moves = self.game.moves
        self.shown_status = self.game.status
