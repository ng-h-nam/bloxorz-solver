"""Phiên chơi: ván đang chơi, màn nào đã mở, hoàn tác, đồng hồ và ghi kỷ lục.

Lớp này không biết gì về pygame hay OpenGL nên kiểm thử được hoàn toàn bằng `pytest`.
`Window` chỉ chuyển sự kiện vào đây và hiển thị kết quả.
"""

from dataclasses import dataclass
from enum import Enum

from core.block import Direction
from core.game import Game, GameStatus
from core.state import State
from core.transition import MoveOutcome, MoveResult
from gui.geometry import Cell, broken_fragile_cell
from gui.level_catalog import LevelCatalog
from gui.player_data import MANUAL, PlayerDataManager, calculate_level_score

MSG_ENDED: str = "Ván đã kết thúc. Nhấn R để chơi lại hoặc Z để hoàn tác."
MSG_SWITCHED: str = "Đã chuyển khối điều khiển."
NO_RECORD_TEXT: str = "Chưa có"


class StageSelection(Enum):
    """Kết quả của việc chọn một màn trong danh sách."""

    CURRENT = "CURRENT"  # đang ở màn đó rồi
    LOADED = "LOADED"  # màn đã mở và đã nạp
    NEEDS_PASSCODE = "NEEDS_PASSCODE"  # màn khóa: cần nhập mật khẩu
    INVALID = "INVALID"  # chỉ số không có trong danh mục hoặc màn bị hỏng


class MoveKind(Enum):
    """Loại kết quả của một nước đi."""

    ROLL = "ROLL"
    FALL = "FALL"
    WIN = "WIN"


class UndoResult(Enum):
    """Kết quả của một lần hoàn tác."""

    NOTHING = "NOTHING"
    STEPPED_BACK = "STEPPED_BACK"
    REVIVED = "REVIVED"  # vừa rơi: khôi phục ván, giữ nguyên vị trí
    RESTARTED = "RESTARTED"  # rơi ngay từ đầu: chơi lại


@dataclass(frozen=True)
class WinReport:
    """Điểm số khi thắng một màn."""

    score: int
    best_score: int
    next_name: (
        str | None
    )  # màn kế tiếp vừa mở khóa (None nếu hết màn hoặc không được mở)
    all_done: bool
    assisted: bool = False  # đã nhờ thuật toán: không tính kỷ lục và không mở khóa


@dataclass(frozen=True)
class MoveReport:
    """Những gì giao diện cần biết về một nước đi vừa thực hiện."""

    kind: MoveKind
    direction: Direction
    old_state: State
    state: State
    message: str = ""
    broken_tile: Cell | None = None
    win: WinReport | None = None


class GameSession:
    """Ván chơi hiện tại cùng tiến trình qua các màn của một người chơi."""

    def __init__(
        self,
        game: Game,
        catalog: LevelCatalog,
        players: PlayerDataManager,
        level_name: str = "",
    ) -> None:
        """Bắt đầu phiên với ván `game`; tên màn lấy từ board, nếu không có thì dùng `level_name`."""
        self.game: Game = game
        self.catalog: LevelCatalog = catalog
        self.players: PlayerDataManager = players
        self.level_name: str = getattr(game.board, "name", "") or level_name
        self.level_index: int = catalog.index_of(self.level_name)
        catalog.unlock(self.level_index)  # màn đang chơi luôn được mở
        self.elapsed: float = 0.0
        self.message: str = ""
        self.assisted: bool = False  # đã nhờ thuật toán trong ván này
        self.next_index: int | None = None
        self.revision: int = (
            0  # tăng mỗi lần đổi màn để giao diện biết cần dựng lại cảnh
        )

    # ------------------------------------------------------------------ thông tin

    @property
    def passcode(self) -> str:
        """Mật khẩu của màn đang chơi (rỗng nếu không biết)."""
        if 0 <= self.level_index < len(self.catalog):
            return self.catalog.entries[self.level_index].passcode
        return str(getattr(self.game.board, "passcode", ""))

    def say(self, text: str) -> None:
        """Đặt thông báo hiển thị cho người chơi."""
        self.message = text

    def best_record_text(self) -> str:
        """Kỷ lục tự chơi của màn này dưới dạng chữ, ví dụ '12 bước (3.4s)'."""
        info = self.players.get_level_score_info(self.level_name)
        if info is None:
            return NO_RECORD_TEXT
        return f"{info['score']} bước ({info['elapsed_time']:.1f}s)"

    def tick(self, dt: float, paused: bool = False) -> None:
        """Đồng hồ chạy từ lúc tải màn; dừng khi tạm dừng hoặc ván đã kết thúc."""
        if not paused and self.game.status == GameStatus.PLAYING:
            self.elapsed += dt

    # ------------------------------------------------------------------ màn chơi

    def _reset(self) -> None:
        """Đặt lại đồng hồ, thông báo và cờ trợ giúp cho một ván mới."""
        self.elapsed = 0.0
        self.message = ""
        self.assisted = False
        self.next_index = None

    def restart(self) -> None:
        """Chơi lại màn hiện tại từ ô xuất phát."""
        self.game.restart()
        self._reset()

    def load_stage(self, index: int) -> bool:
        """Nạp màn `index`. Màn hỏng thì giữ màn hiện tại, báo lỗi và trả về False."""
        if not 0 <= index < len(self.catalog):
            return False
        entry = self.catalog.entries[index]
        try:
            game: Game = Game(self.catalog.board(index))
        except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
            self.message = f"Không nạp được {entry.name}: {error}"
            return False
        self.game = game
        self.level_name = entry.name
        self.level_index = index
        self.catalog.unlock(index)
        self._reset()
        self.revision += 1
        return True

    def select_stage(self, index: int) -> StageSelection:
        """Chọn màn trong danh sách: màn đã mở thì vào ngay, màn khóa thì cần mật khẩu."""
        if not 0 <= index < len(self.catalog):
            return StageSelection.INVALID
        if index == self.level_index:
            return StageSelection.CURRENT
        if self.catalog.is_unlocked(index):
            return (
                StageSelection.LOADED
                if self.load_stage(index)
                else StageSelection.INVALID
            )
        return StageSelection.NEEDS_PASSCODE

    def submit_passcode(self, index: int, code: str) -> bool:
        """Mở khóa và vào màn `index` nếu mật khẩu đúng (so khớp chính xác)."""
        return self.catalog.unlock_with_passcode(index, code) and self.load_stage(index)

    # ------------------------------------------------------------------ chơi

    def move(self, direction: Direction) -> MoveReport | None:
        """Đi một nước. Trả về None nếu ván đã kết thúc (có đặt thông báo)."""
        if self.game.is_over():
            self.message = MSG_ENDED
            return None
        old_state: State = self.game.state
        outcome: MoveOutcome | None = self.game.move(direction)
        if outcome is None:
            self.message = MSG_ENDED
            return None
        self.message = ""
        if outcome.result == MoveResult.FALL:
            broken: Cell | None = broken_fragile_cell(self.game.board, outcome.state)
            return MoveReport(
                MoveKind.FALL,
                direction,
                old_state,
                outcome.state,
                outcome.message,
                broken,
            )
        if self.game.is_won():
            return MoveReport(
                MoveKind.WIN,
                direction,
                old_state,
                self.game.state,
                outcome.message,
                None,
                self._on_win(),
            )
        return MoveReport(
            MoveKind.ROLL, direction, old_state, self.game.state, outcome.message
        )

    def switch_block(self) -> bool:
        """Đổi khối đang điều khiển khi đang tách; không có hoạt cảnh."""
        if self.game.move("SWITCH") is None:
            return False
        self.message = MSG_SWITCHED
        return True

    def _on_win(self) -> WinReport:
        """Ghi kỷ lục và mở khóa màn kế tiếp, nhưng chỉ khi người chơi tự thắng (không nhờ thuật toán)."""
        score: int = calculate_level_score(self.game.moves)
        if self.assisted:
            self.next_index = None
            return WinReport(score, score, None, False, assisted=True)
        self.players.record_game_session(
            self.level_name, self.game.move_history, True, MANUAL, self.elapsed
        )
        info = self.players.get_level_score_info(self.level_name)
        best: int = int(info["score"]) if info is not None else score
        following: int | None = (
            self.catalog.next_index(self.level_index) if self.level_index >= 0 else None
        )
        self.next_index = following
        if following is None:
            return WinReport(score, best, None, True)
        self.catalog.unlock(following)
        return WinReport(score, best, self.catalog.entries[following].name, False)

    # ------------------------------------------------------------------ hoàn tác

    def revive(self) -> bool:
        """Khôi phục ván vừa rơi (trạng thái khối vẫn là trước lúc rơi).

        `Game` chưa có phương thức công khai cho việc này nên đây là chỗ duy nhất ghi `status`.
        """
        if self.game.status != GameStatus.LOST:
            return False
        self.game.status = GameStatus.PLAYING
        return True

    def undo(self) -> UndoResult:
        """Hoàn tác: rơi ngay từ đầu thì chơi lại, vừa rơi thì khôi phục, ngược lại lùi một bước."""
        if self.game.status == GameStatus.LOST and not self.game.history:
            self.restart()
            return UndoResult.RESTARTED
        if self.revive():
            self.message = "Đã hoàn tác pha rơi khối."
            return UndoResult.REVIVED
        if self.game.undo():
            self.message = "Đã hoàn tác 1 bước."
            return UndoResult.STEPPED_BACK
        self.message = "Đang ở vị trí xuất phát, không thể hoàn tác thêm."
        return UndoResult.NOTHING
