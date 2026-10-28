"""Điều khiển việc phát lại: nối `Replayer` với `GameSession` và `ScenePresenter`."""

from collections.abc import Sequence

from core.transition import ActionInput
from gui.engine.presenter import ScenePresenter
from gui.engine.replay import Replayer, ReplayFrame, ReplayMode
from gui.model.session import GameSession

# (nhãn, giây giữa hai bước)
SPEED_PRESETS: list[tuple[str, float]] = [
    ("0.5x", 0.30),
    ("1x", 0.12),
    ("2x", 0.05),
    ("4x", 0.01),
]
DEFAULT_SPEED_INDEX: int = 1
MSG_NO_SAVED_REPLAY: str = "Chưa có Replay lưu cho màn này. Hãy tự thắng màn hoặc dùng AI (F)!"


class ReplayController:
    """Bắt đầu, tạm dừng, tua và kết thúc một lượt phát lại."""

    def __init__(
        self,
        session: GameSession,
        presenter: ScenePresenter,
        speeds: Sequence[tuple[str, float]] = tuple(SPEED_PRESETS),
    ) -> None:
        """Gắn bộ điều khiển với phiên chơi, phần hiển thị và các mức tốc độ (nhãn, giây giữa hai bước)."""
        self.session: GameSession = session
        self.presenter: ScenePresenter = presenter
        self.speeds: list[tuple[str, float]] = list(speeds)
        self.speed_index: int = min(DEFAULT_SPEED_INDEX, len(self.speeds) - 1)
        self.replayer: Replayer | None = None
        self.source: str = "AI"

    # ------------------------------------------------------------------ truy vấn

    @property
    def active(self) -> bool:
        """Đang có một lượt phát lại (kể cả khi tạm dừng)."""
        return self.replayer is not None

    @property
    def playing(self) -> bool:
        """Đang tự động phát."""
        return self.replayer is not None and self.replayer.is_playing

    @property
    def step(self) -> int:
        """Bước hiện tại của lượt phát lại (0 nếu không có)."""
        return self.replayer.current_index if self.replayer else 0

    @property
    def total(self) -> int:
        """Tổng số bước của lượt phát lại (0 nếu không có)."""
        return self.replayer.total_steps if self.replayer else 0

    @property
    def speed_label(self) -> str:
        """Nhãn của mức tốc độ hiện tại, ví dụ '1x'."""
        return self.speeds[self.speed_index][0]

    # ------------------------------------------------------------------ vòng đời

    def start(self, actions: Sequence[ActionInput], mode: ReplayMode, source: str = "AI") -> bool:
        """Bắt đầu phát `actions`. Trả về False (kèm thông báo) nếu đường đi không hợp lệ."""
        if self.replayer is not None:
            self.stop(restore=True)  # trả ván về như cũ trước khi bắt đầu lượt mới
        game = self.session.game
        replayer = Replayer(
            game,
            actions,
            mode=mode,
            step_interval=self.speeds[self.speed_index][1],
            on_step=self._on_step,
            on_finish=self._on_finish,
        )
        if not replayer.is_valid_path:
            self.session.say(replayer.error_message)
            return False
        self.replayer = replayer
        self.source = source
        self.presenter.snap(game)
        replayer.play()
        return True

    def play_saved(self) -> bool:
        """Phát đường đi tốt nhất đã lưu của màn hiện tại, từ ô xuất phát."""
        best = self.session.players.get_best_replay(self.session.level_name)
        if best is None:
            self.session.say(MSG_NO_SAVED_REPLAY)
            return False
        actions, source = best
        if not self.start(actions, ReplayMode.FROM_START, source):
            return False
        self.session.say(f"Đang phát Replay lưu ({source}): {len(actions)} bước từ ô xuất phát.")
        return True

    def stop(self, restore: bool = True) -> None:
        """Thoát phát lại. Mặc định khôi phục đúng tiến trình người chơi có trước đó."""
        if self.replayer is None:
            return
        self.replayer.stop(restore=restore)
        self.replayer = None
        self.presenter.snap(self.session.game)
        self.session.say("Đã thoát chế độ Replay. Bạn có thể điều khiển tiếp.")

    def takeover(self) -> None:
        """Người chơi tự đi tiếp từ vị trí phát lại: giữ nguyên vị trí và đánh dấu đã nhờ trợ giúp."""
        if self.replayer is None:
            return
        self.replayer.release()
        self.replayer = None
        self.session.assisted = True
        self.session.say("Đã thoát Replay; bạn điều khiển tiếp từ vị trí này (không tính kỷ lục).")

    def discard(self) -> None:
        """Bỏ phát lại mà không đụng tới ván (khi ván đã bị thay hoặc chơi lại)."""
        self.replayer = None

    # ------------------------------------------------------------------ điều khiển

    def update(self, dt: float) -> None:
        """Tiến thời gian của lượt phát lại; chỉ đi bước mới khi hoạt cảnh trước đã xong."""
        if self.replayer is not None and self.replayer.is_playing:
            self.replayer.update(dt, busy=self.presenter.busy)

    def toggle_pause(self) -> None:
        """Tạm dừng nếu đang phát, tiếp tục (hoặc phát lại từ đầu nếu đã xong) nếu đang dừng."""
        replayer = self.replayer
        if replayer is None:
            return
        if replayer.is_playing:
            replayer.pause()
            self.session.say(f"Đã tạm dừng Replay ở bước {replayer.current_index}/{replayer.total_steps}.")
        else:
            replayer.play(restart_if_finished=True)
            self.session.say("Tiếp tục phát Replay.")

    def step_forward(self) -> None:
        """Tạm dừng rồi tiến đúng một bước."""
        if self.replayer is None:
            return
        self.replayer.pause()
        frame = self.replayer.step_forward()
        self.session.say(
            f"Replay tiến: bước {frame.step_index}/{self.replayer.total_steps} ({frame.action or 'START'})"
        )

    def step_backward(self) -> None:
        """Tạm dừng rồi lùi đúng một bước."""
        if self.replayer is None:
            return
        self.replayer.pause()
        frame = self.replayer.step_backward()
        self.session.say(f"Replay lùi: bước {frame.step_index}/{self.replayer.total_steps}")

    def cycle_speed(self) -> None:
        """Chuyển sang mức tốc độ kế tiếp (áp dụng ngay cho lượt đang phát)."""
        self.speed_index = (self.speed_index + 1) % len(self.speeds)
        label, interval = self.speeds[self.speed_index]
        if self.replayer is not None:
            self.replayer.set_speed(interval)
        self.session.say(f"Tốc độ phát Replay: {label}")

    # ------------------------------------------------------------------ gọi lại từ Replayer

    def _on_step(self, frame: ReplayFrame, animate: bool) -> None:
        """Replayer vừa đổi bước: nhờ phần hiển thị dựng hoạt cảnh hoặc nhảy thẳng tới vị trí."""
        self.presenter.show_replay_step(self.session.game, frame, animate, self.source)

    def _on_finish(self, frame: ReplayFrame) -> None:
        """Replayer đã phát tới cuối: báo cho người chơi."""
        total: int = self.replayer.total_steps if self.replayer else frame.step_index
        self.session.say(f"Replay xong ({total} bước). Nhấn Z để lùi, R để chơi lại.")
