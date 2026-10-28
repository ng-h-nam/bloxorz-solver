"""Trạng thái hiển thị đi theo hoạt cảnh.

`GameSession` cập nhật luật chơi ngay lập tức; `ScenePresenter` giữ lại phần "chờ hoạt cảnh xong mới hiện"
(số bước, băng thắng thua, ô giòn vỡ, khối bị ẩn) để màn hình khớp với chuyển động đang diễn ra.
"""

from core.game import Game, GameStatus
from core.state import State
from gui.animator import Animator, Phase, Pose
from gui.geometry import Cell
from gui.palette import LOSE_COLOR, WIN_COLOR
from gui.replay import ReplayFrame
from gui.session import MoveKind, MoveReport, WinReport
from gui.viewmodels import Banner

SUBTITLE_FALL: str = "Khối đã rơi."
SUBTITLE_WON: str = "Bạn đã đưa khối vào ô đích."
SUBTITLE_ALL_DONE: str = "Bạn đã hoàn thành tất cả các màn."
SUBTITLE_ASSISTED: str = (
    "Bạn đã đưa khối vào ô đích (có nhờ AI nên không tính kỷ lục, màn kế chưa mở)."
)
HINT_LOST: str = "Nhấn Z để hoàn tác, R để chơi lại, hoặc N để chọn màn khác."
HINT_WON: str = "Nhấn N để chọn màn khác, V để xem lại Replay, hoặc R để chơi lại."
HINT_WON_NEXT: str = (
    "Enter: sang màn kế tiếp  -  V: xem Replay  -  N: chọn màn  -  R: chơi lại"
)
HINT_REPLAY_DONE: str = (
    "Nhấn Z để lùi từng bước, R để chơi lại màn này, hoặc N để chọn màn khác."
)


def win_banner(report: WinReport) -> Banner:
    """Băng báo thắng khi người chơi tự thắng một màn."""
    if report.assisted:
        return Banner("HOÀN THÀNH!", SUBTITLE_ASSISTED, HINT_WON, WIN_COLOR)
    score_text: str = f"Điểm: {report.score} bước (Kỷ lục: {report.best_score} bước)."
    if report.all_done:
        return Banner(
            "HOÀN THÀNH!",
            f"{SUBTITLE_WON} {score_text} {SUBTITLE_ALL_DONE}",
            HINT_WON,
            WIN_COLOR,
        )
    subtitle: str = f"{SUBTITLE_WON} {score_text} Màn kế tiếp: {report.next_name}."
    return Banner("HOÀN THÀNH!", subtitle, HINT_WON_NEXT, WIN_COLOR)


def replay_banner(source: str, moves: int) -> Banner:
    """Băng báo khi một đường đi được phát lại tới đích (không tính kỷ lục, không mở màn kế)."""
    subtitle: str = f"{source} đã đưa khối vào ô đích sau {moves} bước (không tính kỷ lục, màn kế chưa mở)."
    return Banner("GIẢI XONG!", subtitle, HINT_REPLAY_DONE, WIN_COLOR)


class ScenePresenter:
    """Giữ và cập nhật những gì hiển thị cùng hoạt cảnh."""

    def __init__(self, animator: Animator | None = None) -> None:
        """Dùng `animator` được truyền vào, hoặc tự tạo một bộ mới."""
        self.animator: Animator = animator if animator is not None else Animator()
        self.banner: Banner | None = None
        self.block_visible: bool = True
        self.broken_tiles: frozenset[Cell] = frozenset()
        self.shown_moves: int = 0
        self.shown_status: GameStatus = GameStatus.PLAYING
        self._pending: Banner | None = None
        self._pending_broken: Cell | None = None

    @property
    def busy(self) -> bool:
        """Hoạt cảnh đang chạy: chưa nên nhận nước đi mới."""
        return self.animator.active

    def reset(self, game: Game) -> None:
        """Về trạng thái hiển thị ban đầu của một ván."""
        self.snap(game)

    def snap(self, game: Game) -> None:
        """Dừng hoạt cảnh và đưa phần hiển thị khớp ngay với `game`."""
        self.animator.cancel()
        self.banner = None
        self.block_visible = True
        self.broken_tiles = frozenset()
        self._pending = None
        self._pending_broken = None
        self.shown_moves = game.moves
        self.shown_status = game.status

    def display(self, game: Game) -> tuple[State, Pose | None]:
        """Trạng thái và tư thế dùng để vẽ ở khung hình này."""
        if self.animator.active and self.animator.display_state is not None:
            return self.animator.display_state, self.animator.pose
        return game.state, None

    # ------------------------------------------------------------------ sự kiện

    def show_move(self, game: Game, report: MoveReport) -> None:
        """Bắt đầu hoạt cảnh cho một nước đi của người chơi."""
        self._pending_broken = None
        self._pending = None
        if report.kind == MoveKind.FALL:
            self._pending_broken = report.broken_tile
            self.animator.start_fall(
                report.old_state, report.direction, report.broken_tile
            )
            self._pending = Banner(
                "THUA!", report.message or SUBTITLE_FALL, HINT_LOST, LOSE_COLOR
            )
        elif report.kind == MoveKind.WIN and report.win is not None:
            self.animator.start_win(report.old_state, report.direction, report.state)
            self._pending = win_banner(report.win)
        else:
            self.animator.start_roll(report.old_state, report.direction, report.state)

    def show_replay_step(
        self, game: Game, frame: ReplayFrame, animate: bool, source: str = "AI"
    ) -> None:
        """Hiển thị một bước của phát lại: có hoạt cảnh khi tiến một bước, ngược lại nhảy thẳng tới vị trí."""
        won: bool = frame.status == GameStatus.WON
        if animate and frame.prev_state is not None and frame.direction is not None:
            self.snap(game)
            if won:
                self.animator.start_win(frame.prev_state, frame.direction, frame.state)
                self._pending = replay_banner(source, game.moves)
            else:
                self.animator.start_roll(frame.prev_state, frame.direction, frame.state)
            return
        self.snap(game)
        if won:
            self.banner = replay_banner(source, game.moves)
            self.block_visible = False

    def update(self, dt: float, game: Game) -> bool:
        """Tiến hoạt cảnh. Trả về True đúng ở lần gọi làm hoạt cảnh kết thúc."""
        if self.animator.update(dt):
            self._finish(game)
            return True
        if (
            self.animator.active
            and self.animator.phase == Phase.FALL
            and self._pending_broken is not None
        ):
            self.broken_tiles = frozenset(
                {self._pending_broken}
            )  # ô giòn vỡ đúng lúc khối bắt đầu rơi
        return False

    def _finish(self, game: Game) -> None:
        """Hoạt cảnh vừa xong: hiện số bước, ô vỡ và băng thông báo đang chờ."""
        self.shown_moves = game.moves
        self.shown_status = game.status
        if self._pending_broken is not None:
            self.broken_tiles = frozenset({self._pending_broken})
            self._pending_broken = None
        if self._pending is not None:
            self.banner = self._pending
            self._pending = None
            self.block_visible = False
