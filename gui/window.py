import pygame
from algorithms.base_solver import BaseSolver
from algorithms.bfs import BFSSolver
from algorithms.dfs import DFSSolver
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
    K_F2,
    K_KP_ENTER,
    K_LEFT,
    K_LEFTBRACKET,
    K_PAGEDOWN,
    K_PAGEUP,
    K_RETURN,
    K_RIGHT,
    K_RIGHTBRACKET,
    K_SPACE,
    K_TAB,
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
from gui.passcode_prompt import PasscodePrompt, char_from_key, digit_from_key
from gui.renderer import FOV_DEGREES, Renderer, load_textures
from gui.replayer import (
    AccountPrompt,
    BackgroundSolverWorker,
    PlayerDataManager,
    Replayer,
    ReplayFrame,
    calculate_level_score,
)

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

SPEED_PRESETS: list[tuple[str, float]] = [
    ("0.5x", 0.30),
    ("1x", 0.12),
    ("2x", 0.05),
    ("4x", 0.01),
]

MSG_ENDED: str = "Ván đã kết thúc. Nhấn R để chơi lại hoặc Z để hoàn tác."
SUBTITLE_FALL: str = "Khối đã rơi."
SUBTITLE_WON: str = "Bạn đã đưa khối vào ô đích."
HINT_LOST: str = "Nhấn Z để hoàn tác, R để chơi lại, hoặc N để chọn màn khác."
HINT_WON: str = "Nhấn N để chọn màn khác, V để xem lại Replay, hoặc R để chơi lại."
HINT_WON_NEXT: str = "Enter: sang màn kế tiếp  -  V: xem Replay  -  N: chọn màn  -  R: chơi lại"
SUBTITLE_ALL_DONE: str = "Bạn đã hoàn thành tất cả các màn."
MSG_WRONG_PASSCODE: str = "Sai mật khẩu."
MAX_FRAME_SECONDS: float = 0.1


def discover_available_solvers() -> list[tuple[str, type[BaseSolver]]]:
    """Tự động phát hiện các thuật toán Solver đã cài đặt trong gói algorithms."""
    solvers: list[tuple[str, type[BaseSolver]]] = [
        ("BFS", BFSSolver),
        ("DFS", DFSSolver),
    ]
    try:
        from algorithms.ucs import UCSSolver  # type: ignore

        solvers.append(("UCS", UCSSolver))
    except ImportError:
        pass
    try:
        from algorithms.astar import AStarSolver  # type: ignore

        solvers.append(("A*", AStarSolver))
    except ImportError:
        pass
    return solvers


class Window:
    def __init__(
        self,
        game: Game,
        level_name: str = "",
        width: int = 1280,
        height: int = 768,
        catalog: LevelCatalog | None = None,
        player_manager: PlayerDataManager | None = None,
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
        self.account_prompt: AccountPrompt = AccountPrompt()
        self._next_index: int | None = None

        self.player_manager: PlayerDataManager = player_manager if player_manager is not None else PlayerDataManager()
        self.solver_worker: BackgroundSolverWorker = BackgroundSolverWorker(check_state_key_before_run=True)
        self.available_solvers: list[tuple[str, type[BaseSolver]]] = discover_available_solvers()
        self.solver_index: int = 0
        self.replayer: Replayer | None = None
        self.speed_index: int = 1

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
        self.solver_worker.cancel()
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
        self._poll_solver_events()

        is_modal_open = self.picker.is_open or self.prompt.is_open or self.account_prompt.is_open
        if (
            not is_modal_open
            and self.replayer is None
            and not self.solver_worker.is_running
            and self.game.status == GameStatus.PLAYING
        ):
            self.elapsed += dt

        self.renderer.camera.update(dt)

        if self.replayer is not None and self.replayer.is_playing:
            self.replayer.update(dt)

        if self.animator.update(dt):
            self._finish_animation()
        elif self.animator.active and self.animator.phase == Phase.FALL and self._pending_broken is not None:
            self.broken_tiles = frozenset({self._pending_broken})  # ô giòn vỡ đúng lúc khối bắt đầu rơi

    def _build_hud_data(self, state_orientation: str) -> HudData:
        user = self.player_manager.current_user or "guest"
        score_info = self.player_manager.get_level_score_info(self.level_name)
        if score_info is not None:
            best_text = f"{score_info['score']} bước ({score_info['elapsed_time']:.1f}s)"
        else:
            best_text = "Chưa có"

        solver_name = self.available_solvers[self.solver_index][0]
        speed_label = SPEED_PRESETS[self.speed_index][0]
        return HudData(
            level_name=self.level_name,
            moves=self.shown_moves,
            orientation=state_orientation,
            status=self.shown_status.name,
            elapsed=self.elapsed,
            passcode=getattr(self.game.board, "passcode", ""),
            username=user,
            best_record=best_text,
            solver_name=solver_name,
            solver_running=self.solver_worker.is_running,
            replay_active=self.replayer is not None,
            replay_playing=bool(self.replayer and self.replayer.is_playing),
            replay_step=self.replayer.current_index if self.replayer else 0,
            replay_total=self.replayer.total_steps if self.replayer else 0,
            replay_speed_label=speed_label,
        )

    def draw(self) -> None:
        glViewport(PANEL_WIDTH, 0, self.width - PANEL_WIDTH, self.height)
        if self.animator.active and self.animator.display_state is not None:
            state, pose = self.animator.display_state, self.animator.pose
        else:
            state, pose = self.game.state, None
        self.renderer.draw(state, pose, self.block_visible, self.broken_tiles)

        glViewport(0, 0, self.width, self.height)
        hud = self._build_hud_data(state.orientation.name)
        self.panel.draw(hud, self.message)
        if self.banner is not None:
            self.panel.draw_banner(self.banner)
        if self.picker.is_open:
            self.panel.draw_picker(self.picker, self.level_index, self.catalog.is_unlocked)
        if self.prompt.is_open:
            self.panel.draw_prompt(self.prompt)
        if self.account_prompt.is_open:
            self.panel.draw_account_prompt(self.account_prompt)

    # ------------------------------------------------------------------ bàn phím

    def handle_key(self, key: int, text: str = "") -> None:
        if self.account_prompt.is_open:
            self._handle_account_key(key, text)
            return
        if self.prompt.is_open:
            self._handle_prompt_key(key, text)
            return
        if self.picker.is_open:
            self._handle_picker_key(key)
            return
        if key in (K_RETURN, K_KP_ENTER) and self.banner is not None and self._next_index is not None:
            self.load_stage(self._next_index)  # thắng rồi thì sang màn kế tiếp, không cần mật khẩu
            return
        if self._handle_shortcut_key(key):
            return
        if self.animator.active or self.solver_worker.is_running:
            return
        self._handle_gameplay_key(key)

    def _handle_shortcut_key(self, key: int) -> bool:
        shortcuts = {
            K_r: self.restart,
            K_c: self.renderer.camera.start_reset,
            K_n: self.open_picker,
            K_z: self.undo,
            K_u: self.undo,
            K_BACKSPACE: self.undo,
            K_l: self.open_account_prompt,
            K_m: self.cycle_solver,
            K_f: self.run_solver,
            K_v: self.replay_saved,
            K_p: self.toggle_replay_pause,
            K_t: self.cycle_replay_speed,
            K_LEFTBRACKET: self.replay_step_backward,
            K_RIGHTBRACKET: self.replay_step_forward,
        }
        handler = shortcuts.get(key)
        if handler is not None:
            handler()
            return True
        return False

    def _handle_gameplay_key(self, key: int) -> None:
        if self.replayer is not None:
            if self.replayer.is_playing:
                return
            self.stop_replay()
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

    def _handle_account_key(self, key: int, text: str) -> None:
        if key == K_ESCAPE:
            self.account_prompt.close()
        elif key in (K_TAB, K_UP, K_DOWN):
            self.account_prompt.switch_field()
        elif key == K_BACKSPACE:
            self.account_prompt.backspace()
        elif key == K_F2:
            self.player_manager.logout()
            self.account_prompt.close()
            self.message = "Đã đăng xuất về tài khoản khách (guest)."
        elif key in (K_RETURN, K_KP_ENTER):
            self._submit_account()
        else:
            shift = bool(pygame.key.get_mods() & KMOD_SHIFT)
            ch = char_from_key(key, text, shift=shift)
            if ch is not None:
                self.account_prompt.type_char(ch)

    def _submit_account(self) -> None:
        uname = self.account_prompt.username.strip()
        pw = self.account_prompt.password
        if not uname:
            self.account_prompt.fail("Vui lòng nhập Username (hoặc nhấn F2 để Đăng xuất).")
            return
        ok, msg = self.player_manager.authenticate_or_register(uname, pw)
        if ok:
            self.account_prompt.close()
            self.message = msg
        else:
            self.account_prompt.fail(msg)

    # ------------------------------------------------------------------ di chuyển & hoàn tác

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
            self.player_manager.record_game_session(
                level_id=self.level_name,
                moves=self.game.move_history,
                won=True,
                mode="MANUAL",
                elapsed_time=self.elapsed,
            )
            self.animator.start_win(old_state, direction, self.game.state)
            self._pending = self._won_banner()
        else:
            self.animator.start_roll(old_state, direction, self.game.state)
            self._pending = None

    def _won_banner(self) -> Banner:
        """Mở khóa màn kế tiếp và hiển thị điểm số (số bước) cùng kỷ lục của người chơi."""
        score = calculate_level_score(self.game.moves, won=True)
        info = self.player_manager.get_level_score_info(self.level_name)
        best_score = info["score"] if info is not None else score
        score_text = f"Điểm: {score} bước (Kỷ lục: {best_score} bước)."

        self._next_index = self.catalog.next_index(self.level_index) if self.level_index >= 0 else None
        if self._next_index is None:
            return Banner(
                "HOÀN THÀNH!",
                f"{SUBTITLE_WON} {score_text} {SUBTITLE_ALL_DONE}",
                HINT_WON,
                WIN_COLOR,
            )
        self.catalog.unlock(self._next_index)
        entry = self.catalog.entries[self._next_index]
        subtitle = f"{SUBTITLE_WON} {score_text} Màn kế tiếp: {entry.name}."
        return Banner("HOÀN THÀNH!", subtitle, HINT_WON_NEXT, WIN_COLOR)

    def _switch(self) -> None:
        """Đổi khối đang điều khiển khi đang tách; không có hoạt cảnh."""
        if self.game.move("SWITCH") is not None:
            self.message = "Đã chuyển khối điều khiển."

    def undo(self) -> None:
        """Hoàn tác 1 bước đi (hoặc lùi 1 bước nếu đang mở Replayer)."""
        if self.replayer is not None:
            self.replay_step_backward()
            return
        if self.game.status == GameStatus.LOST and not self.game.history:
            self.restart()
            return
        if self.game.status == GameStatus.LOST:
            # Nếu vừa bị rơi (state chưa đổi nhưng status=LOST), khôi phục PLAYING
            self.game.status = GameStatus.PLAYING
            self.animator.cancel()
            self.banner = None
            self._pending = None
            self.block_visible = True
            self.broken_tiles = frozenset()
            self._pending_broken = None
            self.shown_moves = self.game.moves
            self.shown_status = self.game.status
            self.message = "Đã hoàn tác pha rơi khối."
            return
        if self.game.undo():
            self.animator.cancel()
            self.banner = None
            self._pending = None
            self.block_visible = True
            self.broken_tiles = frozenset()
            self._pending_broken = None
            self.shown_moves = self.game.moves
            self.shown_status = self.game.status
            self.message = "Đã hoàn tác 1 bước."
        else:
            self.message = "Đang ở vị trí xuất phát, không thể hoàn tác thêm."

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

    # ------------------------------------------------------------------ Solver nền & Replayer

    def cycle_solver(self) -> None:
        if self.solver_worker.is_running:
            return
        self.solver_index = (self.solver_index + 1) % len(self.available_solvers)
        algo_name = self.available_solvers[self.solver_index][0]
        self.message = f"Đã chọn thuật toán: {algo_name}"

    def run_solver(self) -> None:
        if self.solver_worker.is_running:
            self.solver_worker.cancel()
            self.message = "Đã hủy phiên giải AI."
            return
        self.stop_replay()
        self.game.restart()
        self._reset_view_state()
        algo_name, solver_cls = self.available_solvers[self.solver_index]
        solver = solver_cls(
            self.game.board,
            initial_state=self.game.initial_state,
            node_limit=200000,
            time_limit=15.0,
        )
        started = self.solver_worker.start_solver(solver, algorithm_name=algo_name)
        if started:
            self.message = f"Đang giải bằng {algo_name} trên luồng nền..."

    def _poll_solver_events(self) -> None:
        res_event, err_events = self.solver_worker.poll_events()
        if err_events:
            err = err_events[-1]
            self.message = f"Lỗi {err.algorithm_name} ({err.error_type}): {err.error_message}"
        if res_event is None:
            return
        if res_event.is_solved and res_event.actions:
            self.player_manager.record_game_session(
                level_id=self.level_name,
                moves=res_event.actions,
                won=True,
                mode=res_event.algorithm_name,
                elapsed_time=res_event.elapsed_time,
            )
            self._start_replay(res_event.actions)
            move_cnt = self.replayer.timeline[-1].move_count if self.replayer else len(res_event.actions)
            self.message = (
                f"{res_event.algorithm_name}: {move_cnt} bước | "
                f"{res_event.expanded_nodes} nodes | "
                f"{res_event.elapsed_time * 1000:.1f}ms | "
                f"{res_event.memory_peak_kb:.1f}KB"
            )
        else:
            self.message = (
                f"{res_event.algorithm_name} thất bại ({res_event.status}) sau {res_event.expanded_nodes} nodes."
            )

    def _start_replay(self, actions: list[str]) -> None:
        self.animator.cancel()
        self.banner = None
        self._pending = None
        self.block_visible = True
        self.broken_tiles = frozenset()
        self._pending_broken = None
        _, interval = SPEED_PRESETS[self.speed_index]
        self.replayer = Replayer(
            self.game,
            actions,
            step_interval=interval,
            on_step_callback=self._on_replay_step,
            on_finish_callback=self._on_replay_finish,
            animator=self.animator,
        )
        if not self.replayer.is_valid_path:
            self.message = self.replayer.error_message
            return
        self.shown_moves = 0
        self.shown_status = self.game.status
        self.replayer.play()

    def _on_replay_step(self, frame: ReplayFrame) -> None:
        if frame.status == GameStatus.WON:
            banner = self._won_banner()
            if self.animator.active:
                self._pending = banner
            else:
                self.shown_moves = frame.move_count
                self.shown_status = frame.status
                self.banner = banner
                self.block_visible = False
        elif frame.status == GameStatus.LOST:
            banner = Banner("THUA!", SUBTITLE_FALL, HINT_LOST, LOSE_COLOR)
            if self.animator.active:
                self._pending = banner
            else:
                self.shown_moves = frame.move_count
                self.shown_status = frame.status
                self.banner = banner
                self.block_visible = False
        else:
            self.banner = None
            self._pending = None
            self.block_visible = True
            if not self.animator.active:
                self.shown_moves = frame.move_count
                self.shown_status = frame.status

    def _on_replay_finish(self, frame: ReplayFrame) -> None:
        if not self.animator.active:
            self.shown_moves = frame.move_count
            self.shown_status = frame.status

    def replay_saved(self) -> None:
        if self.solver_worker.is_running:
            return
        saved = self.player_manager.get_saved_replay(self.level_name)
        if not saved:
            self.message = "Chưa có Replay lưu cho màn này. Hãy thắng màn hoặc bấm Giải AI (F)!"
            return
        self._start_replay(saved)
        info = self.player_manager.get_level_score_info(self.level_name)
        mode_str = info["mode"] if info else "SAVED"
        move_cnt = self.replayer.timeline[-1].move_count if self.replayer else len(saved)
        self.message = f"Đang phát Replay lưu ({mode_str}): {move_cnt} bước."

    def toggle_replay_pause(self) -> None:
        if self.replayer is None:
            self.replay_saved()
            return
        if self.replayer.is_playing:
            self.replayer.pause()
            self.message = f"Đã tạm dừng Replay ở bước {self.replayer.current_index}/{self.replayer.total_steps}."
        else:
            if self.replayer.is_finished:
                self.banner = None
                self._pending = None
                self.block_visible = True
            self.replayer.play(restart_if_finished=True)
            self.message = "Tiếp tục phát Replay."

    def replay_step_backward(self) -> None:
        if self.replayer is None:
            return
        self.replayer.pause()
        frame = self.replayer.step_backward()
        self.message = f"Replay lùi: bước {frame.step_index}/{self.replayer.total_steps}"

    def replay_step_forward(self) -> None:
        if self.replayer is None:
            return
        self.replayer.pause()
        frame = self.replayer.step_forward()
        act = frame.action or "START"
        self.message = f"Replay tiến: bước {frame.step_index}/{self.replayer.total_steps} ({act})"

    def cycle_replay_speed(self) -> None:
        self.speed_index = (self.speed_index + 1) % len(SPEED_PRESETS)
        label, interval = SPEED_PRESETS[self.speed_index]
        if self.replayer is not None:
            self.replayer.set_speed(interval)
        self.message = f"Tốc độ phát Replay: {label}"

    def stop_replay(self) -> None:
        if self.replayer is not None:
            self.replayer.pause()
            self.replayer = None
            self.message = "Đã thoát chế độ Replay. Bạn có thể điều khiển tiếp."

    def open_account_prompt(self) -> None:
        self.picker.close()
        self.prompt.close()
        self.account_prompt.open(self.player_manager.current_user)

    # ------------------------------------------------------------------ chuột và camera

    def handle_mouse_down(self, button: int, pos: tuple[int, int]) -> None:
        if self.account_prompt.is_open or self.prompt.is_open:
            return
        if self.picker.is_open:
            self._handle_picker_click(button, pos)
            return
        if button == 1:
            action = self.panel.handle_click(pos)
            self._dispatch_panel_action(action)
        elif button in (2, 3) and pos[0] >= PANEL_WIDTH:
            shift = pygame.key.get_mods() & KMOD_SHIFT
            self._drag = "pan" if (button == 2 or shift) else "orbit"

    def _handle_picker_click(self, button: int, pos: tuple[int, int]) -> None:
        if button != 1:
            return
        row = self.picker.row_at(pos, self.width, self.height)
        if row is not None:
            self.select_stage(row)
        elif not self.picker.box_contains(pos, self.width, self.height):
            self.picker.close()

    def _dispatch_panel_action(self, action: str | None) -> None:
        if action is None:
            return
        actions = {
            "restart": self.restart,
            "new_game": self.open_picker,
            "undo": self.undo,
            "account": self.open_account_prompt,
            "cycle_algo": self.cycle_solver,
            "run_solver": self.run_solver,
            "replay_saved": self.replay_saved,
            "replay_toggle": self.toggle_replay_pause,
            "step_back": self.replay_step_backward,
            "step_fwd": self.replay_step_forward,
            "cycle_speed": self.cycle_replay_speed,
            "stop_replay": self.stop_replay,
        }
        handler = actions.get(action)
        if handler is not None:
            handler()

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
        self.solver_worker.cancel()
        self.solver_worker.clear_queues()
        self.replayer = None
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
        self.solver_worker.cancel()
        self.solver_worker.clear_queues()
        self.replayer = None
        self.renderer.dispose()
        self.game = game
        self.renderer = Renderer(game.board, self.aspect, self.textures)
        self.level_name = entry.name
        self.level_index = index
        self.catalog.unlock(index)
        self.picker.close()
        self.prompt.close()
        self.account_prompt.close()
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
