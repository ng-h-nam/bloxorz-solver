"""Cửa sổ game Bloxorz: vòng lặp pygame và OpenGL, chuyển sự kiện, và vẽ.

`Window` chỉ là lớp mỏng nối các thành phần; luật chơi nằm ở `GameSession`, hiển thị theo hoạt cảnh ở
`ScenePresenter`, phát lại ở `ReplayController`, nhờ AI ở `AiAssistant`, hộp thoại ở họ `Overlay`.
"""

from collections.abc import Callable

import pygame
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
    K_KP_ENTER,
    K_LEFT,
    K_LEFTBRACKET,
    K_RETURN,
    K_RIGHT,
    K_RIGHTBRACKET,
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
    K_f,
    K_l,
    K_m,
    K_n,
    K_p,
    K_r,
    K_s,
    K_t,
    K_u,
    K_v,
    K_w,
    K_z,
)

from core.block import Direction
from core.game import Game
from core.state import State
from gui.assistant import AiAssistant
from gui.control_panel import PANEL_WIDTH, ControlPanel
from gui.level_catalog import LevelCatalog
from gui.overlays import AccountOverlay, LevelPickerOverlay, Overlay
from gui.player_data import PlayerDataManager
from gui.presenter import ScenePresenter
from gui.renderer import FOV_DEGREES, Renderer, load_textures
from gui.replay_controller import ReplayController
from gui.session import GameSession, UndoResult
from gui.solver_service import SolverService
from gui.viewmodels import HudData

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
MAX_FRAME_SECONDS: float = 0.1
MSG_NO_LEVELS: str = "Không tìm thấy dữ liệu màn chơi (coolmath.json)."


class Window:
    """Cửa sổ game: nhận sự kiện, điều phối các thành phần và vẽ mỗi khung hình."""

    def __init__(
        self,
        game: Game,
        level_name: str = "",
        width: int = 1280,
        height: int = 768,
        catalog: LevelCatalog | None = None,
        player_manager: PlayerDataManager | None = None,
        solver_service: SolverService | None = None,
    ) -> None:
        """Tạo cửa sổ OpenGL cho ván `game`; các thành phần không truyền vào sẽ được tự tạo."""
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
        self.aspect: float = (
            width - PANEL_WIDTH
        ) / height  # chỉ vùng bên phải cột bảng dùng cho cảnh 3D
        gluPerspective(FOV_DEGREES, self.aspect, 0.1, 1000)
        glMatrixMode(GL_MODELVIEW)

        if catalog is None:
            try:
                catalog = LevelCatalog.from_json()
            except FileNotFoundError:
                catalog = LevelCatalog([])
        players: PlayerDataManager = (
            player_manager if player_manager is not None else PlayerDataManager()
        )

        # Tạo sau set_mode vì cần ngữ cảnh OpenGL
        self.textures: dict[str, int] = load_textures()
        self.session: GameSession = GameSession(game, catalog, players, level_name)
        self.presenter: ScenePresenter = ScenePresenter()
        self.presenter.reset(game)
        self.replays: ReplayController = ReplayController(self.session, self.presenter)
        self.solver: SolverService = (
            solver_service if solver_service is not None else SolverService()
        )
        self.assistant: AiAssistant = AiAssistant(
            self.session, self.presenter, self.replays, self.solver
        )
        self.renderer: Renderer = Renderer(game.board, self.aspect, self.textures)
        self.panel: ControlPanel = ControlPanel(width, height)
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.overlay: Overlay | None = None

        self._drag: str | None = None
        self._mouse: tuple[int, int] = (0, 0)
        self._seen_revision: int = self.session.revision
        self._commands: dict[int, Callable[[], None]] = {
            K_r: self.restart,
            K_c: self._reset_camera,
            K_n: self.open_picker,
            K_z: self.undo,
            K_u: self.undo,
            K_BACKSPACE: self.undo,
            K_l: self.open_account,
            K_m: self.assistant.cycle,
            K_f: self.assistant.toggle,
            K_v: self.replays.play_saved,
            K_p: self.replays.toggle_pause,
            K_t: self.replays.cycle_speed,
            K_LEFTBRACKET: self.replays.step_backward,
            K_RIGHTBRACKET: self.replays.step_forward,
        }
        self._panel_actions: dict[str, Callable[[], None]] = {
            "restart": self.restart,
            "new_game": self.open_picker,
            "undo": self.undo,
            "account": self.open_account,
            "cycle_algo": self.assistant.cycle,
            "run_solver": self.assistant.toggle,
            "replay_saved": self.replays.play_saved,
            "replay_toggle": self.replays.toggle_pause,
            "step_back": self.replays.step_backward,
            "step_fwd": self.replays.step_forward,
            "cycle_speed": self.replays.cycle_speed,
            "stop_replay": self.replays.stop,
        }
        if players.load_notice:
            self.session.say(players.load_notice)

    # ------------------------------------------------------------------ vòng lặp

    def run(self) -> None:
        """Chạy vòng lặp chính: nhận sự kiện, cập nhật, vẽ, cho tới khi đóng cửa sổ."""
        while self.running:
            dt: float = min(self.clock.tick(60) / 1000.0, MAX_FRAME_SECONDS)
            for event in pygame.event.get():
                self.process_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        self.assistant.cancel()
        pygame.quit()

    def process_event(self, event: pygame.event.Event) -> None:
        """Chuyển một sự kiện pygame tới hàm xử lý tương ứng."""
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
        """Cập nhật một khung hình: đổi màn nếu cần, nhận kết quả AI, đồng hồ, camera, phát lại, hoạt cảnh."""
        self._sync_stage()
        self.assistant.poll()
        paused: bool = (
            self.overlay is not None or self.replays.active or self.assistant.running
        )
        self.session.tick(dt, paused)
        self.renderer.camera.update(dt)
        self.replays.update(dt)
        self.presenter.update(dt, self.session.game)

    def draw(self) -> None:
        """Vẽ vùng 3D bên phải, rồi bảng bên trái, băng thông báo và overlay đang mở."""
        self._sync_stage()
        game: Game = self.session.game
        glViewport(PANEL_WIDTH, 0, self.width - PANEL_WIDTH, self.height)
        state, pose = self.presenter.display(game)
        self.renderer.draw(
            state, pose, self.presenter.block_visible, self.presenter.broken_tiles
        )

        glViewport(0, 0, self.width, self.height)
        self.panel.draw(self._build_hud(state), self.session.message)
        if self.presenter.banner is not None:
            self.panel.draw_banner(self.presenter.banner)
        if self.overlay is not None:
            self.overlay.draw(self.panel)

    def _build_hud(self, state: State) -> HudData:
        """Gom thông tin cho bảng bên trái từ các thành phần."""
        session: GameSession = self.session
        return HudData(
            level_name=session.level_name,
            moves=self.presenter.shown_moves,
            orientation=state.orientation.name,
            status=self.presenter.shown_status.name,
            elapsed=session.elapsed,
            passcode=session.passcode,
            username=session.players.current_user or "guest",
            best_record=session.best_record_text(),
            solver_name=self.assistant.solver_name,
            solver_running=self.assistant.running,
            replay_active=self.replays.active,
            replay_playing=self.replays.playing,
            replay_step=self.replays.step,
            replay_total=self.replays.total,
            replay_speed_label=self.replays.speed_label,
            ai_uses_left=self.assistant.uses_left,
        )

    def _sync_stage(self) -> None:
        """Nếu phiên chơi vừa đổi màn thì dựng lại cảnh 3D và đặt lại các thành phần phụ thuộc màn."""
        if self.session.revision == self._seen_revision:
            return
        self.assistant.cancel()
        self.replays.discard()
        self.renderer.dispose()
        self.renderer = Renderer(self.session.game.board, self.aspect, self.textures)
        self.presenter.reset(self.session.game)
        self._seen_revision = self.session.revision

    # ------------------------------------------------------------------ bàn phím

    def handle_key(self, key: int, text: str = "") -> None:
        """Overlay đang mở nhận phím trước; sau đó tới Enter sang màn kế, phím tắt, rồi phím di chuyển."""
        if self.overlay is not None:
            self.overlay = self.overlay.handle_key(key, text)
            return
        if key in (K_RETURN, K_KP_ENTER) and self._advance_to_next():
            return
        command: Callable[[], None] | None = self._commands.get(key)
        if command is not None:
            command()
            return
        if self.presenter.busy or self.assistant.running:
            return  # bỏ qua phím di chuyển khi đang hoạt cảnh hoặc đang giải
        self._gameplay_key(key)

    def _advance_to_next(self) -> bool:
        """Vừa thắng: Enter sang màn kế tiếp (không cần mật khẩu). Trả về True nếu đã xử lý."""
        if self.presenter.banner is None or self.session.next_index is None:
            return False
        self.session.load_stage(self.session.next_index)
        return True

    def _gameplay_key(self, key: int) -> None:
        """Phím di chuyển hoặc đổi khối; đang xem Replay mà bấm thì tiếp quản (nếu Replay đã dừng)."""
        direction: Direction | None = KEY_TO_DIRECTION.get(key)
        if direction is None and key != K_SPACE:
            return
        if self.replays.active:
            if self.replays.playing:
                return
            self.replays.takeover()
        if direction is not None:
            self._move(direction)
        else:
            self.session.switch_block()

    def _move(self, direction: Direction) -> None:
        """Đi một nước và bắt đầu hoạt cảnh tương ứng."""
        report = self.session.move(direction)
        if report is not None:
            self.presenter.show_move(self.session.game, report)

    # ------------------------------------------------------------------ chuột và camera

    def handle_mouse_down(self, button: int, pos: tuple[int, int]) -> None:
        """Overlay nhận chuột trước; nếu không thì bấm nút bên trái hoặc bắt đầu kéo camera."""
        if self.overlay is not None:
            self.overlay = self.overlay.handle_click(
                button, pos, (self.width, self.height)
            )
            return
        if button == 1:
            self._dispatch(self.panel.handle_click(pos))
        elif button in (2, 3) and pos[0] >= PANEL_WIDTH:
            shift: int = pygame.key.get_mods() & KMOD_SHIFT
            self._drag = "pan" if (button == 2 or shift) else "orbit"

    def _dispatch(self, action: str | None) -> None:
        """Chạy hành động của nút vừa bấm."""
        handler: Callable[[], None] | None = (
            self._panel_actions.get(action) if action is not None else None
        )
        if handler is not None:
            handler()

    def handle_mouse_up(self, button: int) -> None:
        """Kết thúc việc kéo camera."""
        if button in (2, 3):
            self._drag = None

    def handle_mouse_motion(self, pos: tuple[int, int], rel: tuple[int, int]) -> None:
        """Xoay hoặc dịch camera theo chuột đang kéo."""
        self._mouse = pos
        if self._drag == "orbit":
            self.renderer.camera.orbit(rel[0], rel[1])
        elif self._drag == "pan":
            self.renderer.camera.pan(rel[0], rel[1])

    def handle_wheel(self, steps: int) -> None:
        """Cuộn danh sách trong overlay, hoặc phóng to, thu nhỏ khi con trỏ ở vùng 3D."""
        if self.overlay is not None:
            self.overlay.handle_wheel(steps)
        elif self._mouse[0] >= PANEL_WIDTH:
            self.renderer.camera.zoom(steps)

    def _reset_camera(self) -> None:
        """Đưa camera về vị trí mặc định (mượt)."""
        self.renderer.camera.start_reset()

    # ------------------------------------------------------------------ lệnh của người chơi

    def restart(self) -> None:
        """Chơi lại màn hiện tại: hủy giải, bỏ phát lại, đặt lại ván."""
        self.assistant.cancel()
        self.replays.discard()
        self.session.restart()
        self.presenter.reset(self.session.game)

    def undo(self) -> None:
        """Hoàn tác một bước (hoặc lùi một bước nếu đang xem Replay)."""
        if self.replays.active:
            self.replays.step_backward()
            return
        if self.session.undo() != UndoResult.NOTHING:
            self.presenter.snap(self.session.game)

    def open_picker(self) -> None:
        """Mở hộp chọn màn."""
        if len(self.session.catalog) == 0:
            self.session.say(MSG_NO_LEVELS)
            return
        self.overlay = LevelPickerOverlay.open(self.session)

    def open_account(self) -> None:
        """Mở hộp đăng nhập, đăng ký, đăng xuất."""
        self.overlay = AccountOverlay.open(self.session)