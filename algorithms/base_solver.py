"""
Base Solver: Bộ khung chuẩn cho các thuật toán giải bài toán Bloxorz.

Bao gồm:
1. Node: Biểu diễn một nút trong không gian tìm kiếm, hỗ trợ truy ngược đường đi và so sánh độ ưu tiên.
2. SolveResult (Solution): Chứa toàn diện kết quả tìm kiếm gồm chuỗi hành động, trạng thái,
   thời gian thực thi (time.perf_counter), bộ nhớ đỉnh (tracemalloc), số nút đã mở rộng, kích thước frontier lớn nhất.
3. replay_path: Hàm phát lại chuỗi hành động trên core để kiểm tra tính hợp lệ và xác nhận khối đến đích.
4. BaseSolver: Abstract Base Class quản lý cấu hình giới hạn (node_limit, time_limit), đo lường hiệu năng và các thao tác cốt lõi.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
import tracemalloc
from typing import List, Optional, Sequence, Tuple, Union

from core.block import Direction
from core.board import Board
from core.state import Orientation, State
from core.transition import get_next_state, get_successors, is_goal_state, is_valid_state


ActionType = Union[Direction, str]

# 1. BIỂU DIỄN NÚT TÌM KIẾM (SEARCH TREE NODE)


class Node:
    """
    Biểu diễn một nút trong cây tìm kiếm (Search Tree Node).

    Thuộc tính:
        state: Trạng thái Bloxorz tại nút này (tọa độ, tư thế đứng/nằm, các cầu đang mở, split).
        parent: Nút cha dẫn đến nút này (hỗ trợ truy ngược nghiệm).
        action: Hành động (UP, DOWN, LEFT, RIGHT, SWITCH) thực hiện từ parent để tới state này.
        cost: Chi phí đường đi g(n) từ nút gốc đến nút hiện tại.
        depth: Độ sâu của nút trong cây tìm kiếm (Root = 0).
    """

    def __init__(
        self,
        state: State,
        parent: Optional["Node"] = None,
        action: Optional[ActionType] = None,
        cost: int = 0,
        depth: int = 0,
    ) -> None:
        self.state: State = state
        self.parent: Optional["Node"] = parent
        self.action: Optional[ActionType] = action
        self.cost: int = cost
        self.depth: int = depth

    def reconstruct_path(self) -> List["Node"]:
        """
        Truy ngược từ nút hiện tại về nút gốc (Root).

        Returns:
            List[Node]: Danh sách các nút theo thứ tự từ Root -> Goal.
        """
        path: List[Node] = []
        current: Optional[Node] = self
        while current is not None:
            path.append(current)
            current = current.parent
        path.reverse()
        return path

    def reconstruct_actions(self) -> List[ActionType]:
        """Trả về chuỗi hành động từ Root đến Goal."""
        return [n.action for n in self.reconstruct_path() if n.action is not None]

    def reconstruct_states(self) -> List[State]:
        """Trả về chuỗi trạng thái tương ứng từ Root đến Goal."""
        return [n.state for n in self.reconstruct_path()]

    def __lt__(self, other: "Node") -> bool:
        """Hỗ trợ so sánh trong hàng đợi ưu tiên (heapq) cho UCS, Greedy, A*."""
        if self.cost != other.cost:
            return self.cost < other.cost
        return self.depth < other.depth

    def __repr__(self) -> str:
        act = self.action.value if isinstance(self.action, Direction) else str(self.action)
        return (
            f"Node(pos=({self.state.r}, {self.state.c}), "
            f"orient={self.state.orientation.value}, action={act}, depth={self.depth}, cost={self.cost})"
        )


# 2. KẾT QUẢ TÌM KIẾM (SOLUTION)


@dataclass
class SolveResult:
    """
    Chứa toàn bộ thông tin kết quả giải của thuật toán tìm kiếm.

    Thuộc tính:
        actions: Danh sách hành động để giải màn chơi.
        states: Danh sách trạng thái tương ứng qua từng bước (dành cho GUI animation/replay).
        cost: Số bước di chuyển (= len(actions)).
        nodes_explored: Tổng số nút đã lấy ra khỏi Frontier và duyệt mở rộng.
        max_frontier_size: Kích thước lớn nhất của Frontier/Queue trong suốt quá trình tìm kiếm.
        execution_time: Thời gian tìm kiếm (tính bằng giây, đo bằng time.perf_counter).
        peak_memory: Bộ nhớ đỉnh tiêu thụ (bytes, đo bằng tracemalloc).
        is_solved: True nếu tìm ra nghiệm hợp lệ tới đích, False nếu thất bại hoặc vượt giới hạn.
        status: Chuỗi thông báo trạng thái ("SOLVED", "NO_SOLUTION", "NODE_LIMIT_EXCEEDED", "TIME_LIMIT_EXCEEDED").
    """

    actions: List[ActionType] = field(default_factory=list)
    states: List[State] = field(default_factory=list)
    cost: int = 0
    nodes_explored: int = 0
    max_frontier_size: int = 0
    execution_time: float = 0.0
    peak_memory: int = 0
    is_solved: bool = False
    status: str = "NOT_STARTED"

    @property
    def found(self) -> bool:
        return self.is_solved

    @property
    def nodes_expanded(self) -> int:
        return self.nodes_explored

    @property
    def memory_bytes(self) -> int:
        return self.peak_memory

    @property
    def memory_kb(self) -> float:
        return self.peak_memory / 1024.0

    @property
    def memory_mb(self) -> float:
        return self.peak_memory / (1024.0 * 1024.0)

    @property
    def time_taken(self) -> float:
        return self.execution_time

    def get_action_names(self) -> List[str]:
        """Trả về danh sách tên chuỗi tên các hành động (ví dụ: ['RIGHT', 'DOWN', 'SWITCH'])."""
        res: List[str] = []
        for act in self.actions:
            if isinstance(act, Direction):
                res.append(act.value)
            else:
                res.append(str(act).upper())
        return res

    def get_action_sequence_str(self, separator: str = " -> ") -> str:
        """Trả về chuỗi string biểu diễn trực quan các bước di chuyển."""
        if not self.actions:
            return "Empty solution"
        return separator.join(self.get_action_names())

    def summary(self) -> str:
        """Trả về chuỗi tóm tắt các chỉ số thực nghiệm."""
        return (
            f"Trạng thái: {self.status} | Thắng: {self.is_solved} | Số bước: {self.cost} | "
            f"Số nút mở rộng: {self.nodes_explored} | Kích thước frontier max: {self.max_frontier_size} | "
            f"Thời gian: {self.execution_time * 1000:.3f} ms | Bộ nhớ đỉnh: {self.memory_kb:.2f} KB ({self.memory_mb:.4f} MB)"
        )


Solution = SolveResult


# 3. HÀM PHÁT LẠI ĐƯỜNG ĐI TRÊN CORE ĐỂ KIỂM TRA (REPLAY PATH)


def replay_path(
    board: Board,
    actions: Sequence[ActionType],
    initial_state: Optional[State] = None,
) -> Tuple[bool, List[State], str]:
    """
    Phát lại (replay) chuỗi hành động trên tầng core để kiểm tra tính hợp lệ và xác nhận về đích.

    Quy trình kiểm tra:
    1. Bắt đầu từ trạng thái initial_state (nếu None thì lấy mặc định từ board).
    2. Duyệt qua từng action trong actions, gọi get_next_state(current_state, action, board).
    3. Nếu bước đi trả về None (rơi khỏi map, đứng trên ô O vỡ, cầu đóng), kiểm tra thất bại ngay lập tức.
    4. Sau khi hoàn thành toàn bộ hành động, kiểm tra is_goal_state.

    Args:
        board: Đối tượng Board của màn chơi.
        actions: Danh sách hành động (Direction hoặc chuỗi như 'UP', 'DOWN', 'LEFT', 'RIGHT', 'SWITCH').
        initial_state: Trạng thái bắt đầu. Mặc định là trạng thái khởi tạo từ board.

    Returns:
        (success, states, message):
            - success: True nếu toàn bộ nước đi hợp lệ và điểm cuối cùng đạt đích.
            - states: Danh sách trạng thái từ vị trí ban đầu đến cuối cùng.
            - message: Mô tả kết quả phát lại chi tiết.
    """
    if initial_state is None:
        initial_state = State(
            r=board.start_pos[0],
            c=board.start_pos[1],
            orientation=Orientation.STANDING,
            active_bridges=board.initial_active_bridges,
        )

    if not is_valid_state(board, initial_state):
        return False, [initial_state], f"Trạng thái ban đầu không hợp lệ: {initial_state}"

    states: List[State] = [initial_state]
    current_state = initial_state

    # Trường hợp đặc biệt: xuất phát ngay tại đích và không có hành động
    if not actions:
        if is_goal_state(board, current_state):
            return True, states, "Xuất phát ngay tại ô đích thành công."
        return False, states, "Chuỗi hành động rỗng nhưng trạng thái hiện tại chưa phải đích."

    for idx, act in enumerate(actions, start=1):
        next_state = get_next_state(current_state, act, board=board)
        if next_state is None:
            act_name = act.value if isinstance(act, Direction) else str(act)
            return (
                False,
                states,
                f"Bước {idx} ({act_name}) thất bại: Khối lăn vào vị trí không hợp lệ hoặc bị rơi từ {current_state}.",
            )
        states.append(next_state)
        current_state = next_state

    if is_goal_state(board, current_state):
        return (
            True,
            states,
            f"Phát lại thành công {len(actions)} bước di chuyển: Khối đứng thẳng tại ô đích T{board.end_pos}.",
        )

    return (
        False,
        states,
        f"Thực hiện xong {len(actions)} bước nhưng khối chưa đứng thẳng tại ô đích (vị trí hiện tại: {current_state}).",
    )


# 4. ABSTRACT BASE SOLVER CHO TẤT CẢ CÁC THUẬT TOÁN


class BaseSolver(ABC):
    """
    Abstract Base Class định nghĩa bộ khung chuẩn cho mọi thuật toán giải Bloxorz (BFS, DFS, IDS, UCS, A*).

    Trách nhiệm:
    - Quản lý trạng thái bắt đầu và bàn cờ.
    - Đo lường thời gian (time.perf_counter) và bộ nhớ đỉnh (tracemalloc).
    - Quản lý các giới hạn dừng sớm (node_limit, time_limit).
    - Cung cấp phương thức sinh trạng thái con (get_successors), kiểm tra đích (is_goal), kiểm tra hợp lệ (is_valid).
    - Tích hợp kiểm thử đường đi phát lại (replay).
    """

    def __init__(
        self,
        board: Board,
        initial_state: Optional[State] = None,
        node_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> None:
        """
        Khởi tạo BaseSolver.

        Args:
            board: Đối tượng Board chứa bản đồ, vị trí Start, Goal, Switches, Bridges.
            initial_state: Trạng thái bắt đầu. Nếu None, tự động tạo từ board.start_pos.
            node_limit: Giới hạn số nút mở rộng tối đa (tránh tràn RAM hoặc treo máy).
            time_limit: Giới hạn thời gian chạy tối đa tính bằng giây.
        """
        self.board: Board = board
        if initial_state is not None:
            self.initial_state: State = initial_state
        else:
            self.initial_state = State(
                r=board.start_pos[0],
                c=board.start_pos[1],
                orientation=Orientation.STANDING,
                active_bridges=board.initial_active_bridges,
            )

        if not self.is_valid(self.initial_state):
            raise ValueError(f"Trạng thái xuất phát không hợp lệ trên bản đồ: {self.initial_state}")

        self.node_limit: Optional[int] = node_limit
        self.time_limit: Optional[float] = time_limit

        self.nodes_explored: int = 0
        self.max_frontier_size: int = 0
        self.execution_time: float = 0.0
        self.peak_memory: int = 0
        self._started_tracemalloc_locally: bool = False

    @abstractmethod
    def solve(self) -> SolveResult:
        """
        Abstract Method thuật toán tìm kiếm.

        Returns:
            SolveResult chứa thông tin chi tiết về lời giải và các chỉ số thực nghiệm.
        """
        pass

    # Quản lý Profiling

    def _start_profiling(self) -> float:
        """
        Khởi động đo thời gian và bộ nhớ đỉnh bằng tracemalloc.
        Trả về thời điểm bắt đầu theo time.perf_counter().
        """
        self.nodes_explored = 0
        self.max_frontier_size = 0
        self.execution_time = 0.0
        self.peak_memory = 0

        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_tracemalloc_locally = True
        else:
            self._started_tracemalloc_locally = False
            tracemalloc.reset_peak()

        return time.perf_counter()

    def _finish_profiling(self, start_time: float) -> Tuple[float, int]:
        """
        Dừng hoặc lấy kết quả đo thời gian và bộ nhớ đỉnh.

        Returns:
            (execution_time, peak_memory_bytes)
        """
        execution_time = time.perf_counter() - start_time
        _, peak = tracemalloc.get_traced_memory()

        if self._started_tracemalloc_locally:
            tracemalloc.stop()
            self._started_tracemalloc_locally = False

        self.execution_time = execution_time
        self.peak_memory = peak
        return execution_time, peak

    def _check_limits(self, start_time: float) -> Optional[str]:
        """
        Kiểm tra xem quá trình tìm kiếm đã vượt qua time_limit hoặc node_limit hay chưa.

        Returns:
            Chuỗi lý do ("TIME_LIMIT_EXCEEDED" hoặc "NODE_LIMIT_EXCEEDED") nếu vượt giới hạn, ngược lại None.
        """
        if self.time_limit is not None:
            if (time.perf_counter() - start_time) >= self.time_limit:
                return "TIME_LIMIT_EXCEEDED"

        if self.node_limit is not None:
            if self.nodes_explored >= self.node_limit:
                return "NODE_LIMIT_EXCEEDED"

        return None

    # Các hàm bổ trợ Search

    def get_state_key(self, state: State) -> State:
        """Trả về khóa băm đại diện cho trạng thái trò chơi (hỗ trợ visited set)."""
        return state

    def create_root_node(self) -> Node:
        """Tạo nút gốc (Root Node) từ trạng thái xuất phát ban đầu."""
        return Node(
            state=self.initial_state,
            parent=None,
            action=None,
            cost=0,
            depth=0,
        )

    def create_child_node(
        self,
        parent: Node,
        action: ActionType,
        next_state: State,
    ) -> Node:
        """
        Tạo một nút con kế tiếp từ nút cha sau khi thực hiện hành động.
        """
        return Node(
            state=next_state,
            parent=parent,
            action=action,
            cost=parent.cost + 1,
            depth=parent.depth + 1,
        )

    def get_successors(self, state: State) -> List[Tuple[ActionType, State]]:
        """Lấy danh sách các cặp (hành động, trạng thái kế tiếp) hợp lệ từ state hiện tại."""
        return get_successors(self.board, state)

    def is_goal(self, state: State) -> bool:
        """Kiểm tra xem trạng thái state đã đạt đích hay chưa (khối đứng thẳng tại ô Goal)."""
        return is_goal_state(self.board, state)

    def is_valid(self, state: State) -> bool:
        """Kiểm tra trạng thái state có hợp lệ trên bàn cờ hay không."""
        return is_valid_state(self.board, state)

    def replay(self, actions: Sequence[ActionType]) -> Tuple[bool, List[State], str]:
        """Phát lại lời giải trên bàn cờ của solver này."""
        return replay_path(self.board, actions, self.initial_state)
