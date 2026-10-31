"""Trợ lý AI: giải từ vị trí đang chơi, giới hạn số lượt dùng AI của mỗi màn.

Quy tắc:
- Mỗi màn chỉ được dùng AI tối đa `MAX_AI_USES_PER_LEVEL` lượt (tính khi lời giải được dùng để phát lại).
- Lời giải của AI không tính kỷ lục và **không mở khóa màn kế tiếp**; người chơi vẫn chơi lại màn đó bình thường.
- Kết quả giải đã cũ (đổi màn hoặc đổi vị trí sau khi bắt đầu giải) bị bỏ và không tốn lượt.
"""

from core.game import Game, GameStatus
from gui.engine.presenter import ScenePresenter
from gui.engine.replay import ReplayMode
from gui.engine.replay_controller import ReplayController
from gui.engine.solver_service import SolverOutcome, SolverService
from gui.model.player_data import MAX_AI_USES_PER_LEVEL
from gui.model.session import GameSession

MSG_AI_EXHAUSTED: str = f"Màn này đã dùng hết {MAX_AI_USES_PER_LEVEL} lượt AI. Hãy tự chơi hoặc xem Replay lưu (V)."
MSG_AI_CANCELLED: str = "Đã hủy phiên giải AI."
MSG_AI_ALREADY_WON: str = "Ván này đã hoàn thành. Nhấn R để chơi lại."
MSG_AI_STALE: str = "Kết quả giải đã cũ (màn hoặc vị trí đã đổi) nên bị bỏ; không tốn lượt AI."


class AiAssistant:
    """Điều phối việc nhờ AI giải: kiểm tra hạn mức, chạy nền, nhận kết quả rồi phát lại."""

    def __init__(
        self,
        session: GameSession,
        presenter: ScenePresenter,
        replays: ReplayController,
        solver: SolverService,
    ) -> None:
        """Gắn trợ lý với phiên chơi, phần hiển thị, bộ phát lại và dịch vụ giải."""
        self.session: GameSession = session
        self.presenter: ScenePresenter = presenter
        self.replays: ReplayController = replays
        self.solver: SolverService = solver

    @property
    def running(self) -> bool:
        """Đang có một lượt giải chạy nền."""
        return self.solver.is_running

    @property
    def solver_name(self) -> str:
        """Tên thuật toán đang chọn."""
        return self.solver.selected_name

    @property
    def uses_left(self) -> int:
        """Số lượt dùng AI còn lại ở màn hiện tại."""
        return self.session.players.ai_uses_left(self.session.level_name)

    def cycle(self) -> None:
        """Đổi sang thuật toán kế tiếp (không đổi khi đang giải)."""
        if self.running:
            return
        self.session.say(f"Đã chọn thuật toán: {self.solver.cycle()}")

    def cancel(self) -> None:
        """Hủy lượt giải đang chạy (nếu có), không báo gì."""
        self.solver.cancel()

    def toggle(self) -> None:
        """Bấm lần đầu: bắt đầu giải từ vị trí hiện tại; bấm khi đang giải: hủy."""
        if self.running:
            self.cancel()
            self.session.say(MSG_AI_CANCELLED)
            return
        game: Game = self.session.game
        if self.uses_left <= 0:
            self.session.say(MSG_AI_EXHAUSTED)
            return
        if game.status == GameStatus.WON:
            self.session.say(MSG_AI_ALREADY_WON)
            return
        self.replays.stop(restore=True)  # đang phát lại thì trả ván về như cũ rồi mới giải
        self.session.revive()  # vừa rơi thì giải từ vị trí ngay trước lúc rơi
        self.presenter.snap(game)
        if self.solver.start(game, self.session.level_name):
            self.session.say(
                f"Đang giải bằng {self.solver_name} từ vị trí hiện tại... (còn {self.uses_left} lượt AI ở màn này)"
            )
        else:
            self.session.say(f"Không bắt đầu được: {self.solver.last_error or 'lỗi không rõ'}")

    def poll(self) -> None:
        """Gọi mỗi khung hình: nhận kết quả của lượt giải, rồi phát lại và trừ một lượt nếu dùng được."""
        outcome: SolverOutcome | None = self.solver.poll()
        if outcome is None:
            return
        context = outcome.context
        result = outcome.result
        if outcome.errors:
            error = outcome.errors[-1]
            self.session.say(f"Lỗi {context.algorithm} ({error.error_type}): {error.error_message}")
            return
        if result is None or not outcome.solved:
            status: str = result.status if result else "NO_RESULT"
            nodes: int = result.expanded_nodes if result else 0
            self.session.say(f"{context.algorithm} thất bại ({status}) sau {nodes} nodes.")
            return
        if context.level_id != self.session.level_name or self.session.game.state != context.start_state:
            self.session.say(MSG_AI_STALE)
            return
        if not self.replays.start(result.actions, ReplayMode.FROM_CURRENT, context.algorithm):
            return
        players = self.session.players
        players.record_solver_run(
            context.level_id,
            context.algorithm,
            outcome.full_actions,
            True,
            result.elapsed_time,
            result.expanded_nodes,
        )
        left: int = players.consume_ai_use(context.level_id)
        self.session.say(
            f"{context.algorithm}: {len(result.actions)} bước từ vị trí hiện tại | {result.expanded_nodes} nodes | "
            f"{result.elapsed_time * 1000:.1f}ms | {result.memory_peak_kb:.1f}KB | còn {left} lượt AI"
        )
