import hashlib
import json
import os
import queue
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from core.block import Direction
from core.board import Board
from core.game import Game, GameStatus
from core.state import Orientation, State, state_key
from core.transition import (
    SWITCH_ACTION,
    ActionInput,
    get_next_state,
    is_goal_state,
    normalize_action,
)


def _normalize_replay_action_str(action: ActionInput) -> str:
    """Chuẩn hóa hành động đầu vào thành chuỗi chuẩn ('UP', 'DOWN', 'LEFT', 'RIGHT', 'SWITCH')."""
    if isinstance(action, Direction):
        return action.value
    if hasattr(action, "value"):
        return str(getattr(action, "value")).strip().upper()
    text = str(action).strip().upper()
    if text in ("SPACE", "SWITCH", "TAB"):
        return SWITCH_ACTION
    return normalize_action(text).value


# =============================================================================
# 1. KIỂM TRA KHÓA TRẠNG THÁI CỦA SOLVER (CẦU & TÁCH KHỐI)
# =============================================================================
def verify_solver_state_key(
    key_fn: Callable[[State], Any] = state_key,
) -> Tuple[bool, List[str]]:
    """
    Rà soát xem hàm khóa trạng thái (state_key / get_state_key) của Solver có phân biệt đầy đủ:
      1. Tọa độ và hướng cơ bản (r, c, orientation).
      2. Trạng thái đóng/mở của các cây cầu (active_bridges) và bất biến thứ tự frozenset.
      3. Trạng thái tách khối (Orientation.SPLIT, tọa độ khối phụ split_pos).
      4. Khối đơn đang được điều khiển tuần tự (active_cube = 0 hoặc 1).
    Trả về: (Đạt_yêu_cầu: bool, Danh_sách_lỗi_nếu_có: List[str]).
    """
    issues: List[str] = []

    # 1. Kiểm tra phân biệt tọa độ và tư thế cơ bản (r, c, orientation)
    s_base = State(2, 2, Orientation.STANDING)
    s_diff_pos = State(2, 3, Orientation.STANDING)
    s_diff_orient = State(2, 2, Orientation.HORIZONTAL)
    if key_fn(s_base) == key_fn(s_diff_pos):
        issues.append("Lỗi khóa trạng thái: Không phân biệt được tọa độ (r, c) của khối.")
    if key_fn(s_base) == key_fn(s_diff_orient):
        issues.append("Lỗi khóa trạng thái: Không phân biệt được tư thế (orientation) của khối.")

    # 2. Kiểm tra phân biệt cấu hình cầu (active_bridges)
    s_no_bridge = State(2, 2, Orientation.STANDING, active_bridges=frozenset())
    s_with_bridge = State(2, 2, Orientation.STANDING, active_bridges=frozenset([(3, 2), (3, 3)]))
    if key_fn(s_no_bridge) == key_fn(s_with_bridge):
        issues.append("Lỗi khóa trạng thái: Không phân biệt được trạng thái đóng/mở của cầu (active_bridges).")

    # 3. Kiểm tra thứ tự cầu trong frozenset không làm lệch khóa (và băm được trong set/dict)
    s_bridge_order_1 = State(2, 2, Orientation.STANDING, active_bridges=frozenset([(3, 2), (3, 3)]))
    s_bridge_order_2 = State(2, 2, Orientation.STANDING, active_bridges=frozenset([(3, 3), (3, 2)]))
    if key_fn(s_bridge_order_1) != key_fn(s_bridge_order_2):
        issues.append("Lỗi khóa trạng thái: Cùng tập cầu mở nhưng khác thứ tự lại sinh ra 2 khóa khác nhau.")
    try:
        visited = {key_fn(s_bridge_order_1)}
        if key_fn(s_bridge_order_2) not in visited:
            issues.append("Lỗi khóa trạng thái: Khóa trạng thái không hoạt động đúng trong tập visited.")
    except TypeError:
        issues.append("Lỗi khóa trạng thái: Giá trị trả về của key_fn không thể băm (unhashable).")

    # 4. Kiểm tra phân biệt tọa độ khối phụ khi tách khối (split_pos)
    s_split_1 = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=0)
    s_split_2 = State(1, 1, Orientation.SPLIT, split_pos=(3, 2), active_cube=0)
    if key_fn(s_split_1) == key_fn(s_split_2):
        issues.append("Lỗi khóa trạng thái: Không phân biệt được tọa độ khối thứ hai (split_pos) khi tách khối.")

    # 5. Kiểm tra phân biệt quyền điều khiển khối đơn (active_cube 0 vs 1)
    s_cube_0 = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=0)
    s_cube_1 = State(1, 1, Orientation.SPLIT, split_pos=(3, 1), active_cube=1)
    if key_fn(s_cube_0) == key_fn(s_cube_1):
        issues.append("Lỗi khóa trạng thái: Không phân biệt được khối đơn đang điều khiển (active_cube 0 vs 1).")

    return (len(issues) == 0, issues)


# =============================================================================
# 2. QUẢN LÝ TÀI KHOẢN, TÍNH ĐIỂM & LƯU DỮ LIỆU NGƯỜI CHƠI
# =============================================================================
def calculate_level_score(move_count: int, won: bool = True) -> int:
    """
    Tính điểm của người chơi khi vượt qua màn chơi:
      - Điểm chỉ dựa duy nhất trên SỐ BƯỚC ĐI của người chơi (`base_level_score = move_count`).
      - Số điểm càng thấp (càng ít bước đi) nghĩa là thành tích của người chơi càng cao.
      - Nếu chưa vượt qua màn chơi (`won == False`), trả về 0.
    """
    if not won:
        return 0
    base_level_score = max(0, int(move_count))
    return base_level_score


@dataclass
class LevelRecord:
    """Bản ghi kết quả chơi hoặc giải một màn chơi của người chơi."""

    level_id: str
    moves: List[str]
    move_count: int
    won: bool
    mode: str = "MANUAL"  # "MANUAL", "BFS", "DFS", "UCS", "A*"
    elapsed_time: float = 0.0  # Yếu tố phụ lưu lại thời gian hoàn thành màn chơi (giây)
    score: int = 0  # Điểm màn chơi (= move_count; càng thấp càng tốt)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PlayerProfile:
    """Thông tin tài khoản và dữ liệu của một người chơi."""

    username: str
    password_hash: str
    salt: str
    created_at: float = field(default_factory=time.time)
    best_scores: Dict[str, int] = field(default_factory=dict)  # Điểm tốt nhất = số bước ít nhất
    best_times: Dict[str, float] = field(default_factory=dict)  # Thời gian hoàn thành (yếu tố phụ)
    level_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    saved_replays: Dict[str, List[str]] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


class AccountPrompt:
    """Hộp thoại Đăng nhập / Đăng ký / Đăng xuất tài khoản người chơi trên GUI."""

    def __init__(self, max_length: int = 18) -> None:
        self.max_length: int = max_length
        self.is_open: bool = False
        self.username: str = ""
        self.password: str = ""
        self.active_field: int = 0  # 0: username, 1: password
        self.error: str = ""
        self.info: str = ""

    def open(self, current_user: Optional[str] = None) -> None:
        self.is_open = True
        active_name = current_user or "guest"
        self.username = "" if active_name == "guest" else active_name
        self.password = ""
        self.active_field = 0 if not self.username else 1
        self.error = ""
        self.info = f"Đang dùng: {active_name} (Nhấn F2 để Đăng xuất)"

    def close(self) -> None:
        self.is_open = False
        self.password = ""
        self.error = ""

    def switch_field(self) -> None:
        self.active_field = 1 - self.active_field
        self.error = ""

    def type_char(self, ch: str) -> None:
        if len(ch) != 1 or not (ch.isalnum() or ch in ("_", "-")):
            return
        if self.active_field == 0 and len(self.username) < self.max_length:
            self.username += ch
            self.error = ""
        elif self.active_field == 1 and len(self.password) < self.max_length:
            self.password += ch
            self.error = ""

    def backspace(self) -> None:
        if self.active_field == 0:
            self.username = self.username[:-1]
        else:
            self.password = self.password[:-1]
        self.error = ""

    def fail(self, message: str) -> None:
        self.error = message


class PlayerDataManager:
    """
    Hệ thống quản lý tài khoản người chơi (Đăng ký, Đăng nhập, Đăng xuất),
    tính điểm màn chơi (dựa trên số bước đi: càng ít bước điểm càng cao)
    và lưu trữ thời gian chơi (yếu tố phụ) cùng đường đi Replay vào file JSON.
    """

    def __init__(self, storage_path: Union[str, Path, None] = None):
        if storage_path is None:
            self.storage_path = Path(__file__).resolve().parent.parent / "data" / "players.json"
        else:
            self.storage_path = Path(storage_path)
        self.players: Dict[str, PlayerProfile] = {}
        self.current_user: Optional[str] = None
        self._load()

    @staticmethod
    def calculate_score(move_count: int, won: bool = True) -> int:
        """Tính điểm màn chơi dựa duy nhất trên số bước đi (`base_level_score = move_count`)."""
        return calculate_level_score(move_count=move_count, won=won)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Băm mật khẩu an toàn bằng SHA-256 kết hợp chuỗi salt."""
        combined = f"{salt}:{password}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def _load(self) -> None:
        """Đọc dữ liệu người chơi từ file JSON nếu tồn tại."""
        if not self.storage_path.exists():
            self.players = {}
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.players = {uname: PlayerProfile(**pdata) for uname, pdata in raw.get("players", {}).items()}
            self.current_user = raw.get("last_active_user")
            if self.current_user not in self.players:
                self.current_user = None
        except json.JSONDecodeError, OSError, TypeError:
            self.players = {}
            self.current_user = None

    def save(self) -> None:
        """Lưu toàn bộ dữ liệu tài khoản và lịch sử người chơi xuống file JSON."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_active_user": self.current_user,
            "players": {uname: asdict(profile) for uname, profile in self.players.items()},
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def register(self, username: str, password: str) -> Tuple[bool, str]:
        """Tạo tài khoản mới cho người chơi."""
        uname = username.strip()
        if not uname:
            return False, "Tên tài khoản không được để trống."
        if len(password) < 3:
            return False, "Mật khẩu phải có ít nhất 3 ký tự."
        if uname in self.players:
            return False, f"Tài khoản '{uname}' đã tồn tại."

        salt = os.urandom(8).hex()
        pw_hash = self._hash_password(password, salt)
        self.players[uname] = PlayerProfile(
            username=uname,
            password_hash=pw_hash,
            salt=salt,
        )
        self.current_user = uname
        self.save()
        return True, f"Đăng ký và đăng nhập thành công tài khoản '{uname}'."

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """Đăng nhập vào tài khoản đã có."""
        uname = username.strip()
        if uname not in self.players:
            return False, f"Không tìm thấy tài khoản '{uname}'."

        profile = self.players[uname]
        expected_hash = self._hash_password(password, profile.salt)
        if expected_hash != profile.password_hash:
            return False, "Mật khẩu không chính xác."

        self.current_user = uname
        self.save()
        return True, f"Đăng nhập thành công. Xin chào '{uname}'!"

    def logout(self) -> None:
        """Đăng xuất tài khoản hiện tại."""
        self.current_user = None
        self.save()

    def authenticate_or_register(self, username: str, password: str) -> Tuple[bool, str]:
        """Nếu tài khoản đã tồn tại thì đăng nhập, nếu chưa tồn tại thì đăng ký mới."""
        uname = username.strip()
        if uname in self.players and uname != "guest" and self.players[uname].password_hash:
            return self.login(uname, password)
        return self.register(uname, password)

    def get_current_profile(self) -> Optional[PlayerProfile]:
        """Lấy hồ sơ của người chơi đang đăng nhập."""
        if self.current_user is None:
            return None
        return self.players.get(self.current_user)

    def record_game_session(
        self,
        level_id: str,
        moves: Sequence[ActionInput],
        won: bool,
        mode: str = "MANUAL",
        elapsed_time: float = 0.0,
        username: Optional[str] = None,
    ) -> bool:
        """
        Lưu kết quả lượt chơi và đường đi (Replay) của người chơi.
        - Điểm (`score`) = số bước di chuyển (`move_count`); điểm càng thấp thành tích càng cao.
        - Thời gian chơi (`elapsed_time`) được lưu kèm như yếu tố phụ.
        """
        target_user = username or self.current_user
        if target_user is None or target_user not in self.players:
            # Nếu chưa đăng nhập, tự động lưu vào tài khoản khách "guest"
            target_user = "guest"
            if target_user not in self.players:
                self.players[target_user] = PlayerProfile(username="guest", password_hash="", salt="")

        profile = self.players[target_user]
        move_list = [
            m.value if isinstance(m, Direction) or hasattr(m, "value") else str(m).strip().upper() for m in moves
        ]
        move_count = sum(1 for m in move_list if m not in ("SWITCH", "SPACE", "TAB"))
        safe_time = round(max(0.0, float(elapsed_time)), 3)
        score = self.calculate_score(move_count=move_count, won=won)

        record = LevelRecord(
            level_id=level_id,
            moves=move_list,
            move_count=move_count,
            won=won,
            mode=mode,
            elapsed_time=safe_time,
            score=score,
        )
        profile.history.append(asdict(record))

        if won:
            prev_best = profile.best_scores.get(level_id)
            # Số điểm (số bước) càng thấp nghĩa là thành tích càng cao
            if prev_best is None or score <= prev_best:
                profile.best_scores[level_id] = score
                profile.saved_replays[level_id] = move_list
                profile.level_stats[level_id] = {
                    "score": score,
                    "move_count": move_count,
                    "elapsed_time": safe_time,
                    "mode": mode,
                }
            elif level_id not in profile.saved_replays:
                profile.saved_replays[level_id] = move_list

            prev_time = profile.best_times.get(level_id)
            if prev_time is None or safe_time < prev_time:
                profile.best_times[level_id] = safe_time

        self.save()
        return True

    def get_level_score_info(self, level_id: str, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin kỷ lục của người chơi tại một màn chơi, bao gồm:
        `score` (= `move_count`, càng thấp càng tốt) và thông tin phụ `elapsed_time`.
        """
        target_user = username or self.current_user or "guest"
        profile = self.players.get(target_user)
        if profile is None:
            return None
        return profile.level_stats.get(level_id)

    def get_saved_replay(self, level_id: str, username: Optional[str] = None) -> Optional[List[str]]:
        """Lấy chuỗi hành động Replay đã lưu của một màn chơi."""
        target_user = username or self.current_user or "guest"
        profile = self.players.get(target_user)
        if profile is None:
            return None
        return profile.saved_replays.get(level_id)


# =============================================================================
# 3. BỘ PHÁT LẠI ĐƯỜNG ĐI (REPLAYER) CHO GUI & KIỂM THỬ
# =============================================================================
@dataclass(frozen=True)
class ReplayFrame:
    """Một khung hình (bước) trong tiến trình Replay."""

    step_index: int
    action: Optional[str]
    state: State
    status: GameStatus
    is_valid: bool
    prev_state: Optional[State] = None
    direction: Optional[Direction] = None
    move_count: int = 0


class Replayer:
    """
    Bộ phát lại đường đi (Solution / Player Replay) cho trò chơi Bloxorz.
    Hỗ trợ:
      - Tiền tính toán và xác thực toàn bộ quỹ đạo trạng thái (timeline) từ đầu đến cuối.
      - Tương thích hoàn toàn với `core.game.Game` và `gui.animator.Animator` (OpenGL 3D).
      - Phát tự động theo thời gian thực `update(dt)` cho vòng lặp GUI.
      - Điều khiển tua từng bước: `step_forward()`, `step_backward()`, `seek(index)`,
        `play()`, `pause()`, `resume()`, `restart()`.
    """

    def __init__(
        self,
        game_or_board: Union[Game, Board],
        actions: Sequence[ActionInput] = (),
        step_interval: float = 0.35,
        on_step_callback: Optional[Callable[[ReplayFrame], None]] = None,
        on_finish_callback: Optional[Callable[[ReplayFrame], None]] = None,
        animator: Optional[Any] = None,
    ):
        if isinstance(game_or_board, Game):
            self.game = game_or_board
            self.board = game_or_board.board
        elif isinstance(game_or_board, Board):
            self.board = game_or_board
            self.game = Game(board=game_or_board)
        else:
            raise TypeError("Replayer cần nhận vào đối tượng Game hoặc Board.")

        self.step_interval: float = max(0.01, float(step_interval))
        self.on_step_callback = on_step_callback
        self.on_finish_callback = on_finish_callback
        self.animator = animator

        self.actions: List[str] = []
        self.timeline: List[ReplayFrame] = []
        self.current_index: int = 0
        self.is_playing: bool = False
        self.is_valid_path: bool = True
        self.error_message: str = ""
        self._accumulator: float = 0.0

        self.load_actions(actions)

    def _parse_frame_step(
        self,
        idx: int,
        act_str: str,
        curr_state: State,
        roll_moves: int,
    ) -> Tuple[ReplayFrame, Optional[State], int]:
        """Tính toán một bước chuyển trạng thái cho timeline Replay."""
        direction: Optional[Direction] = None
        if act_str != SWITCH_ACTION:
            try:
                direction = normalize_action(act_str)
            except ValueError:
                direction = None

        try:
            next_state = get_next_state(curr_state, act_str, board=self.board)
        except ValueError:
            next_state = None

        if next_state is None:
            frame = ReplayFrame(
                step_index=idx,
                action=act_str,
                state=curr_state,
                status=GameStatus.LOST,
                is_valid=False,
                prev_state=curr_state,
                direction=direction,
                move_count=roll_moves,
            )
            return frame, None, roll_moves

        if act_str != SWITCH_ACTION:
            roll_moves += 1

        step_status = GameStatus.WON if is_goal_state(self.board, next_state) else GameStatus.PLAYING
        frame = ReplayFrame(
            step_index=idx,
            action=act_str,
            state=next_state,
            status=step_status,
            is_valid=True,
            prev_state=curr_state,
            direction=direction,
            move_count=roll_moves,
        )
        return frame, next_state, roll_moves

    def load_actions(self, actions: Sequence[ActionInput]) -> bool:
        """
        Nạp danh sách các bước đi và dựng sẵn toàn bộ timeline trạng thái từ bước 0 đến bước N.
        Trả về True nếu toàn bộ đường đi hợp lệ trên bàn cờ, False nếu có bước đi bị rơi/lỗi.
        """
        normalized_actions: List[str] = []
        for raw_act in actions:
            try:
                normalized_actions.append(_normalize_replay_action_str(raw_act))
            except ValueError:
                normalized_actions.append(str(raw_act).strip().upper())

        self.actions = normalized_actions
        self.timeline.clear()
        self.current_index = 0
        self.is_playing = False
        self.is_valid_path = True
        self.error_message = ""
        self._accumulator = 0.0

        # Bước 0: Trạng thái khởi đầu
        self.game.restart()
        initial_state = self.game.initial_state
        initial_status = GameStatus.WON if is_goal_state(self.board, initial_state) else GameStatus.PLAYING
        self.timeline.append(
            ReplayFrame(
                step_index=0,
                action=None,
                state=initial_state,
                status=initial_status,
                is_valid=True,
                prev_state=None,
                direction=None,
                move_count=0,
            )
        )

        curr_state = initial_state
        roll_moves = 0
        for idx, act_str in enumerate(self.actions, start=1):
            frame, next_state, roll_moves = self._parse_frame_step(idx, act_str, curr_state, roll_moves)
            self.timeline.append(frame)
            if next_state is None:
                self.is_valid_path = False
                self.error_message = f"Bước replay thứ {idx} ('{act_str}') từ trạng thái {curr_state} không hợp lệ!"
                break
            curr_state = next_state

        self._sync_to_game()
        return self.is_valid_path

    def _sync_to_game(self) -> None:
        """Đồng bộ trạng thái tại bước `current_index` của Replayer sang đối tượng `Game`."""
        frame = self.current_frame
        self.game.state = frame.state
        self.game.status = frame.status
        self.game.moves = frame.move_count
        self.game.move_count = frame.step_index
        self.game.action_history = self.actions[: frame.step_index]
        self.game.history = [f.state for f in self.timeline[: self.current_index]]

        move_hist: List[Union[Direction, str]] = []
        for f in self.timeline[1 : self.current_index + 1]:
            if f.direction is not None:
                move_hist.append(f.direction)
            elif f.action is not None:
                move_hist.append(f.action)
        self.game.move_history = move_hist

    def _trigger_animator(self, frame: ReplayFrame) -> None:
        """Kích hoạt hoạt cảnh 3D trên `gui.animator.Animator` (nếu được gắn kèm)."""
        if self.animator is None or frame.prev_state is None or frame.direction is None:
            return
        if frame.status == GameStatus.WON and hasattr(self.animator, "start_win"):
            self.animator.start_win(frame.prev_state, frame.direction, frame.state)
        elif frame.status == GameStatus.LOST and hasattr(self.animator, "start_fall"):
            self.animator.start_fall(frame.prev_state, frame.direction)
        elif hasattr(self.animator, "start_roll"):
            self.animator.start_roll(frame.prev_state, frame.direction, frame.state)

    @property
    def total_steps(self) -> int:
        """Tổng số bước di chuyển trong chuỗi Replay."""
        return max(0, len(self.timeline) - 1)

    @property
    def current_frame(self) -> ReplayFrame:
        """Khung hình Replay tại bước hiện tại."""
        return self.timeline[self.current_index]

    @property
    def current_state(self) -> State:
        """Trạng thái `State` tại bước hiện tại."""
        return self.current_frame.state

    @property
    def is_finished(self) -> bool:
        """Kiểm tra Replayer đã chạy đến bước cuối cùng của đường đi hay chưa."""
        return self.current_index >= len(self.timeline) - 1

    @property
    def reaches_goal(self) -> bool:
        """Kiểm tra đường đi Replay có hợp lệ và kết thúc ở trạng thái chiến thắng (WON) hay không."""
        return self.is_valid_path and len(self.timeline) > 0 and self.timeline[-1].status == GameStatus.WON

    def play(self, restart_if_finished: bool = True) -> None:
        """Bắt đầu hoặc tiếp tục phát tự động."""
        if self.is_finished and restart_if_finished:
            self.seek(0)
        self.is_playing = True
        self._accumulator = 0.0

    def pause(self) -> None:
        """Tạm dừng phát tự động."""
        self.is_playing = False

    def resume(self) -> None:
        """Tiếp tục phát tự động từ vị trí hiện tại."""
        if not self.is_finished:
            self.is_playing = True

    def stop(self) -> None:
        """Dừng phát và đưa về bước 0 ban đầu."""
        self.is_playing = False
        self._accumulator = 0.0
        self.seek(0)

    def restart(self) -> ReplayFrame:
        """Khởi động lại Replay từ bước 0."""
        self.stop()
        return self.current_frame

    def set_speed(self, step_interval: float) -> None:
        """Điều chỉnh thời gian nghỉ (giây) giữa 2 bước lăn khối."""
        self.step_interval = max(0.01, float(step_interval))

    def seek(self, step_index: int, animate: bool = False) -> ReplayFrame:
        """Nhảy trực tiếp tới bước `step_index` bất kỳ (0 <= step_index <= N)."""
        clamped = max(0, min(int(step_index), len(self.timeline) - 1))
        self.current_index = clamped
        self._sync_to_game()
        frame = self.current_frame
        if animate:
            self._trigger_animator(frame)
        elif self.animator is not None and hasattr(self.animator, "cancel"):
            self.animator.cancel()
        if self.on_step_callback is not None:
            self.on_step_callback(frame)
        return frame

    def step_forward(self) -> ReplayFrame:
        """Tiến lên 1 bước trong chuỗi Replay."""
        if not self.is_finished:
            self.seek(self.current_index + 1, animate=True)
            if self.is_finished:
                self.is_playing = False
                if self.on_finish_callback is not None:
                    self.on_finish_callback(self.current_frame)
        else:
            self.is_playing = False
        return self.current_frame

    def step_backward(self) -> ReplayFrame:
        """Lùi lại 1 bước trong chuỗi Replay."""
        if self.current_index > 0:
            self.seek(self.current_index - 1, animate=False)
        return self.current_frame

    def update(self, dt: float) -> bool:
        """
        Hàm cập nhật theo thời gian thực `dt` (giây) dành cho vòng lặp GUI của Thuật.
        Trả về True nếu trong nhịp này có bước chuyển trạng thái mới.
        """
        if not self.is_playing:
            return False

        if self.is_finished:
            self.is_playing = False
            return False

        if self.animator is not None and getattr(self.animator, "active", False):
            return False

        self._accumulator += max(0.0, float(dt))
        advanced = False
        while self._accumulator >= self.step_interval and self.is_playing:
            self._accumulator -= self.step_interval
            self.step_forward()
            advanced = True
            if self.is_finished:
                self.is_playing = False
                break
            if self.animator is not None and getattr(self.animator, "active", False):
                break
        return advanced

    def replay_all_to_end(self) -> ReplayFrame:
        """Chạy ngay lập tức đến bước cuối cùng và trả về khung hình kết thúc."""
        self.is_playing = False
        frame = self.seek(len(self.timeline) - 1, animate=False)
        if self.on_finish_callback is not None:
            self.on_finish_callback(frame)
        return frame


# =============================================================================
# 4. CHẠY SOLVER NỀN (BACKGROUND THREAD) & XỬ LÝ HÀNG ĐỢI LỖI (ERROR QUEUE)
# =============================================================================
@dataclass
class SolverResultEvent:
    """Gói tin kết quả khi Solver chạy nền hoàn thành."""

    algorithm_name: str
    actions: List[str]
    expanded_nodes: int = 0
    elapsed_time: float = 0.0
    memory_peak_kb: float = 0.0
    is_solved: bool = True
    status: str = "SOLVED"
    raw_output: Any = None


@dataclass
class SolverErrorEvent:
    """Gói tin báo lỗi trong hàng đợi lỗi (error_queue) khi Solver gặp sự cố."""

    algorithm_name: str
    error_type: str
    error_message: str
    traceback_str: str
    timestamp: float = field(default_factory=time.time)


def _extract_object_metrics(output: Any) -> Tuple[List[str], int, float]:
    """Bóc tách (actions, expanded_nodes, memory_kb) từ đối tượng SolveResult hoặc tương đương."""
    raw_seq = (
        getattr(output, "actions", None) or getattr(output, "solution", None) or getattr(output, "path", None) or []
    )
    actions = [a.value if hasattr(a, "value") else str(a) for a in raw_seq if not isinstance(a, State)]
    expanded = int(
        getattr(
            output,
            "nodes_explored",
            getattr(output, "expanded_nodes", getattr(output, "nodes_expanded", 0)),
        )
    )
    if hasattr(output, "memory_kb"):
        mem_kb = float(getattr(output, "memory_kb"))
    elif hasattr(output, "memory_peak_kb"):
        mem_kb = float(getattr(output, "memory_peak_kb"))
    elif hasattr(output, "memory_usage"):
        mem_kb = float(getattr(output, "memory_usage"))
    elif hasattr(output, "peak_memory"):
        mem_kb = float(getattr(output, "peak_memory")) / 1024.0
    else:
        mem_kb = 0.0
    return actions, expanded, mem_kb


def _extract_dict_metrics(output: Dict[str, Any]) -> Tuple[List[str], int, float]:
    """Bóc tách (actions, expanded_nodes, memory_kb) từ dictionary kết quả."""
    raw_seq = output.get("actions") or output.get("solution") or output.get("path") or []
    actions = [a.value if hasattr(a, "value") else str(a) for a in raw_seq if not isinstance(a, State)]
    expanded = int(
        output.get(
            "nodes_explored",
            output.get("expanded_nodes", output.get("nodes_expanded", 0)),
        )
    )
    if "memory_kb" in output:
        mem_kb = float(output["memory_kb"])
    elif "memory_peak_kb" in output:
        mem_kb = float(output["memory_peak_kb"])
    elif "memory_usage" in output:
        mem_kb = float(output["memory_usage"])
    elif "peak_memory" in output:
        mem_kb = float(output["peak_memory"]) / 1024.0
    else:
        mem_kb = 0.0
    return actions, expanded, mem_kb


class BackgroundSolverWorker:
    """
    Bộ điều phối chạy các thuật toán tìm kiếm (BFS, DFS/IDS, UCS, A*) trên luồng nền (Thread)
    để giao diện GUI của Thuật không bị đơ (Not Responding).
    Tích hợp hai hàng đợi an toàn luồng (Thread-safe Queues):
      - `result_queue`: Chứa kết quả đường đi khi thuật toán tìm xong.
      - `error_queue`: Chứa thông tin lỗi chi tiết (`SolverErrorEvent`) nếu thuật toán ném ngoại lệ.
    """

    def __init__(self, check_state_key_before_run: bool = True):
        self.result_queue: "queue.Queue[SolverResultEvent]" = queue.Queue()
        self.error_queue: "queue.Queue[SolverErrorEvent]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self.is_running: bool = False
        self.check_state_key_before_run: bool = check_state_key_before_run

    def clear_queues(self) -> None:
        """Làm sạch hàng đợi kết quả và hàng đợi lỗi trước phiên chạy mới."""
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break
        while not self.error_queue.empty():
            try:
                self.error_queue.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _extract_actions_from_output(output: Any) -> Tuple[List[str], int, float]:
        """
        Tự động bóc tách danh sách hành động (actions), số node mở rộng và bộ nhớ (KB)
        từ nhiều định dạng trả về khác nhau của các Solver trong nhóm.
        """
        if output is None:
            return [], 0, 0.0

        if hasattr(output, "actions") or hasattr(output, "solution") or hasattr(output, "path"):
            return _extract_object_metrics(output)

        if isinstance(output, dict):
            return _extract_dict_metrics(output)

        if isinstance(output, tuple) and len(output) > 0 and isinstance(output[0], (list, tuple)):
            raw_seq = output[0]
            actions = [a.value if hasattr(a, "value") else str(a) for a in raw_seq if not isinstance(a, State)]
            expanded = int(output[1]) if len(output) > 1 and isinstance(output[1], (int, float)) else 0
            mem_kb = float(output[2]) if len(output) > 2 and isinstance(output[2], (int, float)) else 0.0
            return actions, expanded, mem_kb

        if isinstance(output, (list, tuple)):
            actions = [a.value if hasattr(a, "value") else str(a) for a in output if not isinstance(a, State)]
            return actions, 0, 0.0

        raise ValueError(f"Định dạng kết quả trả về từ Solver không hợp lệ: {type(output)}")

    @staticmethod
    def _invoke_solver_target(
        solver_or_callable: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[Any, Optional[Callable[[State], Any]]]:
        """
        Hỗ trợ linh hoạt cả 3 cách truyền Solver:
          1. Truyền đối tượng BaseSolver (ví dụ: `BFSSolver(board)`) -> gọi `.solve(*args, **kwargs)`.
          2. Truyền lớp BaseSolver (ví dụ: `BFSSolver, board`) -> khởi tạo rồi gọi `.solve()`.
          3. Truyền hàm / phương thức callable (ví dụ: `solver.solve` hoặc hàm `bfs_solve`).
        """
        solver_key_fn: Optional[Callable[[State], Any]] = None
        if hasattr(solver_or_callable, "get_state_key") and callable(getattr(solver_or_callable, "get_state_key")):
            solver_key_fn = getattr(solver_or_callable, "get_state_key")

        # Trường hợp 1: Đối tượng Solver có phương thức .solve() nhưng bản thân không phải hàm/class
        if not callable(solver_or_callable) and hasattr(solver_or_callable, "solve"):
            return solver_or_callable.solve(*args, **kwargs), solver_key_fn

        # Trường hợp 2 & 3: Callable (hàm, method, hoặc class Solver)
        result = solver_or_callable(*args, **kwargs)
        if hasattr(result, "solve") and callable(getattr(result, "solve")):
            if hasattr(result, "get_state_key") and callable(getattr(result, "get_state_key")):
                solver_key_fn = getattr(result, "get_state_key")
            return result.solve(), solver_key_fn

        return result, solver_key_fn

    def _audit_keys(
        self,
        key_fn_to_audit: Callable[[State], Any],
        solver_key_fn: Optional[Callable[[State], Any]] = None,
    ) -> None:
        """Kiểm tra hàm khóa trạng thái trước/sau khi khởi tạo Solver."""
        ok, issues = verify_solver_state_key(key_fn_to_audit)
        if not ok:
            raise RuntimeError(" | ".join(issues))
        if solver_key_fn is not None and solver_key_fn is not key_fn_to_audit:
            ok_solver, solver_issues = verify_solver_state_key(solver_key_fn)
            if not ok_solver:
                raise RuntimeError(" | ".join(solver_issues))

    def start_solver(
        self,
        solver_callable: Any,
        *args: Any,
        algorithm_name: str = "SOLVER",
        key_fn_to_audit: Callable[[State], Any] = state_key,
        **kwargs: Any,
    ) -> bool:
        """
        Khởi chạy `solver_callable(*args, **kwargs)` trong một luồng nền (Background Thread).
        Mọi ngoại lệ phát sinh trong luồng nền đều được bắt và đẩy vào `self.error_queue`.
        """
        if self.is_running and self._thread is not None and self._thread.is_alive():
            self.error_queue.put(
                SolverErrorEvent(
                    algorithm_name=algorithm_name,
                    error_type="SolverBusyError",
                    error_message="Đang có một thuật toán khác chạy nền, vui lòng đợi hoặc hủy.",
                    traceback_str="",
                )
            )
            return False

        self.clear_queues()
        self._cancel_event.clear()
        self.is_running = True

        def _worker_target() -> None:
            start_ts = time.perf_counter()
            try:
                if self.check_state_key_before_run:
                    self._audit_keys(key_fn_to_audit)

                raw_output, solver_key_fn = self._invoke_solver_target(solver_callable, *args, **kwargs)
                if self.check_state_key_before_run and solver_key_fn is not None:
                    self._audit_keys(key_fn_to_audit, solver_key_fn)

                elapsed = time.perf_counter() - start_ts
                if hasattr(raw_output, "execution_time") and getattr(raw_output, "execution_time"):
                    elapsed = float(getattr(raw_output, "execution_time"))

                if self._cancel_event.is_set():
                    return

                actions, expanded, mem_kb = self._extract_actions_from_output(raw_output)
                is_solved = bool(getattr(raw_output, "is_solved", bool(actions)))
                status = str(getattr(raw_output, "status", "SOLVED" if is_solved else "NO_SOLUTION"))

                self.result_queue.put(
                    SolverResultEvent(
                        algorithm_name=algorithm_name,
                        actions=actions,
                        expanded_nodes=expanded,
                        elapsed_time=elapsed,
                        memory_peak_kb=mem_kb,
                        is_solved=is_solved,
                        status=status,
                        raw_output=raw_output,
                    )
                )
            except Exception as exc:
                self.error_queue.put(
                    SolverErrorEvent(
                        algorithm_name=algorithm_name,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        traceback_str=traceback.format_exc(),
                    )
                )
            finally:
                self.is_running = False

        self._thread = threading.Thread(
            target=_worker_target,
            name=f"BloxorzSolver-{algorithm_name}",
            daemon=True,
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        """Gửi tín hiệu yêu cầu dừng phiên chạy nền hiện tại."""
        self._cancel_event.set()
        self.is_running = False

    def join(self, timeout: Optional[float] = None) -> None:
        """Đợi luồng nền hoàn tất (hữu ích trong Unit Test hoặc CLI)."""
        if self._thread is not None and self._thread.is_alive():
            self.self_join_thread(timeout)

    def self_join_thread(self, timeout: Optional[float] = None) -> None:
        """Hàm nội bộ hỗ trợ join thread an toàn."""
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def poll_events(
        self,
    ) -> Tuple[Optional[SolverResultEvent], List[SolverErrorEvent]]:
        """
        Hàm không chặn (non-blocking) để GUI của Thuật gọi ở mỗi khung hình:
        Lấy ra kết quả giải (nếu đã xong) và toàn bộ các lỗi trong `error_queue`.
        """
        result_event: Optional[SolverResultEvent] = None
        errors: List[SolverErrorEvent] = []

        try:
            result_event = self.result_queue.get_nowait()
        except queue.Empty:
            pass

        while not self.error_queue.empty():
            try:
                errors.append(self.error_queue.get_nowait())
            except queue.Empty:
                break

        return result_event, errors
