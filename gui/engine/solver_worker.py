"""Chạy thuật toán giải màn trên luồng nền để giao diện không bị đơ.

Khác với bản cũ:
- Mỗi lượt chạy có `run_id` riêng; kết quả của lượt đã hủy hoặc đã bị thay thế không bao giờ được giao.
- Hủy dừng được cả luồng nền (qua `_check_limits` của BaseSolver), không chỉ bỏ kết quả.
- `is_running` suy ra từ trạng thái của lượt chạy hiện tại, không dùng cờ dùng chung giữa các luồng.
"""

import queue
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.state import Orientation, State, state_key
from gui.shared.actions import action_names

CANCELLED: str = "CANCELLED"


def verify_solver_state_key(
    key_fn: Callable[[State], Any] = state_key,
) -> tuple[bool, list[str]]:
    """Kiểm tra hàm khóa trạng thái phân biệt đủ: tọa độ, tư thế, cầu, khối phụ và khối đang điều khiển."""
    issues: list[str] = []

    base = State(2, 2, Orientation.STANDING)
    if key_fn(base) == key_fn(State(2, 3, Orientation.STANDING)):
        issues.append(
            "Lỗi khóa trạng thái: Không phân biệt được tọa độ (r, c) của khối."
        )
    if key_fn(base) == key_fn(State(2, 2, Orientation.HORIZONTAL)):
        issues.append(
            "Lỗi khóa trạng thái: Không phân biệt được tư thế (orientation) của khối."
        )

    bridges: frozenset[tuple[int, int]] = frozenset([(3, 2), (3, 3)])
    if key_fn(State(2, 2, Orientation.STANDING)) == key_fn(
        State(2, 2, Orientation.STANDING, active_bridges=bridges)
    ):
        issues.append(
            "Lỗi khóa trạng thái: Không phân biệt được trạng thái đóng/mở của cầu (active_bridges)."
        )

    first = State(
        2, 2, Orientation.STANDING, active_bridges=frozenset([(3, 2), (3, 3)])
    )
    second = State(
        2, 2, Orientation.STANDING, active_bridges=frozenset([(3, 3), (3, 2)])
    )
    if key_fn(first) != key_fn(second):
        issues.append(
            "Lỗi khóa trạng thái: Cùng tập cầu mở nhưng khác thứ tự lại sinh ra 2 khóa khác nhau."
        )
    try:
        if key_fn(second) not in {key_fn(first)}:
            issues.append(
                "Lỗi khóa trạng thái: Khóa trạng thái không hoạt động đúng trong tập visited."
            )
    except TypeError:
        issues.append(
            "Lỗi khóa trạng thái: Giá trị trả về của key_fn không thể băm (unhashable)."
        )

    split_a = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=0)
    if key_fn(split_a) == key_fn(
        State(1, 1, Orientation.SPLIT, split_pos=(3, 2), active_cube=0)
    ):
        issues.append(
            "Lỗi khóa trạng thái: Không phân biệt được tọa độ khối thứ hai (split_pos) khi tách khối."
        )
    if key_fn(split_a) == key_fn(
        State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=1)
    ):
        issues.append(
            "Lỗi khóa trạng thái: Không phân biệt được khối đơn đang điều khiển (active_cube 0 vs 1)."
        )

    return (not issues, issues)


@dataclass
class SolverResultEvent:
    """Kết quả khi thuật toán chạy nền hoàn thành."""

    algorithm_name: str
    actions: list[str]
    run_id: int = 0
    expanded_nodes: int = 0
    elapsed_time: float = 0.0
    memory_peak_kb: float = 0.0
    is_solved: bool = True
    status: str = "SOLVED"
    raw_output: Any = None


@dataclass
class SolverErrorEvent:
    """Thông tin lỗi khi thuật toán ném ngoại lệ trong luồng nền."""

    algorithm_name: str
    error_type: str
    error_message: str
    traceback_str: str = ""
    run_id: int = 0
    timestamp: float = field(default_factory=time.time)


class _Run:
    """Một lượt chạy: tín hiệu hủy và tín hiệu xong là của riêng lượt đó."""

    def __init__(self, run_id: int, algorithm_name: str) -> None:
        """Tạo lượt chạy mang mã `run_id` cho thuật toán `algorithm_name`."""
        self.run_id: int = run_id
        self.algorithm_name: str = algorithm_name
        self.cancel: threading.Event = threading.Event()
        self.done: threading.Event = threading.Event()
        self.thread: threading.Thread | None = None


class BackgroundSolverWorker:
    """Chạy `solver.solve()` trên luồng nền; kết quả và lỗi được lấy ra bằng `poll_events()`."""

    def __init__(self, audit_state_keys: bool = True) -> None:
        """`audit_state_keys`: kiểm tra hàm khóa trạng thái của solver trước mỗi lượt chạy."""
        self.audit_state_keys: bool = audit_state_keys
        self._results: queue.Queue[SolverResultEvent] = queue.Queue()
        self._errors: queue.Queue[SolverErrorEvent] = queue.Queue()
        self._lock: threading.Lock = threading.Lock()
        self._counter: int = 0
        self._active: _Run | None = None
        self._cancelled: set[int] = set()

    @property
    def is_running(self) -> bool:
        """Lượt chạy hiện tại còn đang chạy và chưa bị hủy."""
        run: _Run | None = self._active
        return run is not None and not run.cancel.is_set() and not run.done.is_set()

    @property
    def current_run_id(self) -> int:
        """Mã của lượt chạy gần nhất (0 nếu chưa chạy lần nào)."""
        return self._counter

    @staticmethod
    def _install_cancel_hook(solver: Any, cancel: threading.Event) -> None:
        """Mọi BaseSolver gọi `_check_limits` ở mỗi vòng lặp; chèn vào đó để việc hủy dừng được luồng."""
        original: Any = getattr(solver, "_check_limits", None)
        if not callable(original):
            return

        def check(start_time: float) -> str | None:
            """Trả về CANCELLED nếu đã bị hủy, ngược lại dùng kiểm tra giới hạn gốc."""
            return CANCELLED if cancel.is_set() else original(start_time)

        solver._check_limits = check

    def start(self, solver: Any, algorithm_name: str = "SOLVER") -> int | None:
        """Bắt đầu một lượt chạy. Trả về `run_id`, hoặc None nếu đang có lượt khác chạy."""
        with self._lock:
            if self.is_running:
                self._errors.put(
                    SolverErrorEvent(
                        algorithm_name,
                        "SolverBusyError",
                        "Đang có một thuật toán khác chạy nền, vui lòng đợi hoặc hủy.",
                        run_id=self._counter,
                    )
                )
                return None
            self._counter += 1
            run = _Run(self._counter, algorithm_name)
            self._active = run
        self._install_cancel_hook(solver, run.cancel)
        run.thread = threading.Thread(
            target=self._work,
            args=(solver, run),
            name=f"BloxorzSolver-{algorithm_name}",
            daemon=True,
        )
        run.thread.start()
        return run.run_id

    def _work(self, solver: Any, run: _Run) -> None:
        """Thân luồng nền: kiểm tra khóa, giải, rồi đẩy kết quả hoặc lỗi vào hàng đợi."""
        try:
            if self.audit_state_keys:
                ok, issues = verify_solver_state_key(
                    getattr(solver, "get_state_key", state_key)
                )
                if not ok:
                    raise RuntimeError(" | ".join(issues))
            output: Any = solver.solve()
            if run.cancel.is_set():
                return
            self._results.put(self._to_event(output, run))
        except Exception as error:  # noqa: BLE001 - ranh giới luồng: mọi lỗi phải được báo lại cho giao diện
            if not run.cancel.is_set():
                self._errors.put(
                    SolverErrorEvent(
                        run.algorithm_name,
                        type(error).__name__,
                        str(error),
                        traceback.format_exc(),
                        run.run_id,
                    )
                )
        finally:
            run.done.set()

    @staticmethod
    def _to_event(output: Any, run: _Run) -> SolverResultEvent:
        """Đổi kết quả của solver (kiểu SolveResult) thành `SolverResultEvent`."""
        actions: list[str] = action_names(getattr(output, "actions", None) or [])
        solved: bool = bool(getattr(output, "is_solved", bool(actions)))
        return SolverResultEvent(
            algorithm_name=run.algorithm_name,
            actions=actions,
            run_id=run.run_id,
            expanded_nodes=int(getattr(output, "nodes_explored", 0)),
            elapsed_time=float(getattr(output, "execution_time", 0.0)),
            memory_peak_kb=float(getattr(output, "peak_memory", 0)) / 1024.0,
            is_solved=solved,
            status=str(
                getattr(output, "status", "SOLVED" if solved else "NO_SOLUTION")
            ),
            raw_output=output,
        )

    def cancel(self) -> None:
        """Hủy lượt đang chạy: luồng dừng ở lần kiểm tra giới hạn kế tiếp và kết quả (nếu có) bị bỏ."""
        with self._lock:
            if self._active is not None:
                self._active.cancel.set()
                self._cancelled.add(self._active.run_id)

    def join(self, timeout: float | None = None) -> None:
        """Đợi luồng của lượt hiện tại kết thúc (dùng trong test hoặc khi thoát)."""
        run: _Run | None = self._active
        if run is not None and run.thread is not None and run.thread.is_alive():
            run.thread.join(timeout=timeout)

    def poll_events(self) -> tuple[SolverResultEvent | None, list[SolverErrorEvent]]:
        """Lấy (kết quả, lỗi) của lượt hiện tại mà không chặn; sự kiện của các lượt cũ bị bỏ."""
        current: int = self._counter
        result: SolverResultEvent | None = None
        errors: list[SolverErrorEvent] = []
        while True:
            try:
                event: SolverResultEvent = self._results.get_nowait()
            except queue.Empty:
                break
            if event.run_id == current and event.run_id not in self._cancelled:
                result = event
        while True:
            try:
                error: SolverErrorEvent = self._errors.get_nowait()
            except queue.Empty:
                break
            if error.run_id == current and error.run_id not in self._cancelled:
                errors.append(error)
        return result, errors
