"""Tài khoản người chơi, điểm số, đường đi đã lưu và số lượt dùng AI.

Ba trách nhiệm tách riêng:
- `PasswordHasher`: băm và kiểm tra mật khẩu.
- `JsonFileStore`: đọc và ghi file JSON an toàn (ghi nguyên tử, sao lưu, cách ly file hỏng).
- `PlayerDataManager`: đăng ký, đăng nhập, ghi kết quả; chỉ lời giải do người chơi tự đi
  mới được tính là kỷ lục, lời giải của thuật toán được lưu riêng, và mỗi màn chỉ được dùng AI
  tối đa `MAX_AI_USES_PER_LEVEL` lượt.
"""

import hashlib
import hmac
import json
import os
import secrets
import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from core.transition import ActionInput
from gui.shared.actions import action_names, count_moves
from gui.shared.paths import PROJECT_ROOT

MANUAL: str = "MANUAL"
SCHEMA_VERSION: int = 2
MAX_HISTORY: int = 100
MAX_AI_USES_PER_LEVEL: int = 2
MIN_PASSWORD_LENGTH: int = 3
GUEST: str = "guest"


def calculate_level_score(move_count: int, won: bool = True) -> int:
    """Điểm của một màn: chỉ dựa trên số bước lăn khối (càng thấp càng tốt); 0 nếu chưa thắng."""
    if not won:
        return 0
    return max(0, int(move_count))


@dataclass
class LevelRecord:
    """Bản ghi kết quả chơi hoặc giải một màn chơi của người chơi."""

    level_id: str
    moves: list[str]
    move_count: int
    won: bool
    mode: str = MANUAL
    elapsed_time: float = 0.0
    score: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class PlayerProfile:
    """Thông tin tài khoản và dữ liệu của một người chơi."""

    username: str
    password_hash: str = ""
    salt: str = ""
    created_at: float = field(default_factory=time.time)
    best_scores: dict[str, int] = field(default_factory=dict)
    best_times: dict[str, float] = field(default_factory=dict)
    level_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    saved_replays: dict[str, list[str]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    ai_solutions: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    ai_uses: dict[str, int] = field(default_factory=dict)
    hash_scheme: str = ""
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Any) -> "PlayerProfile":
        """Dựng hồ sơ từ dữ liệu đọc ra, bỏ qua trường lạ và dùng mặc định cho trường thiếu."""
        if not isinstance(data, dict) or not str(data.get("username", "")).strip():
            raise ValueError("Hồ sơ người chơi thiếu tên tài khoản.")
        known: set[str] = {item.name for item in fields(cls)}
        values: dict[str, Any] = {key: value for key, value in data.items() if key in known}
        values.setdefault("schema_version", 1)  # file cũ chưa có trường này
        profile = cls(**values)
        profile._sanitize()
        if profile.schema_version < SCHEMA_VERSION:
            profile._migrate_legacy()
        return profile

    def to_dict(self) -> dict[str, Any]:
        """Chuyển hồ sơ thành từ điển để ghi ra JSON."""
        return asdict(self)

    def _sanitize(self) -> None:
        """Đưa các trường về đúng kiểu để một giá trị hỏng không làm sập cả chương trình."""
        for name in (
            "best_scores",
            "best_times",
            "level_stats",
            "saved_replays",
            "ai_solutions",
            "ai_uses",
        ):
            if not isinstance(getattr(self, name), dict):
                setattr(self, name, {})
        if not isinstance(self.history, list):
            self.history = []
        self.history = [item for item in self.history if isinstance(item, dict)]
        self.ai_uses = {
            str(key): max(0, int(value)) for key, value in self.ai_uses.items() if isinstance(value, int | float)
        }
        for text_field in ("password_hash", "salt", "hash_scheme"):
            if not isinstance(getattr(self, text_field), str):
                setattr(self, text_field, "")

    def _migrate_legacy(self) -> None:
        """Dựng lại kỷ lục từ lịch sử: chỉ lượt tự chơi được tính, lượt của AI chuyển sang ai_solutions."""
        self.best_scores, self.best_times = {}, {}
        self.level_stats, self.saved_replays = {}, {}
        for item in self.history:
            if not item.get("won"):
                continue
            moves: list[str] = list(item.get("moves", []))
            level_id: str = str(item.get("level_id", ""))
            if item.get("mode", MANUAL) == MANUAL:
                self.apply_manual_win(
                    level_id,
                    moves,
                    int(item.get("score", len(moves))),
                    int(item.get("move_count", len(moves))),
                    float(item.get("elapsed_time", 0.0)),
                )
            else:
                self.apply_ai_run(
                    level_id,
                    str(item.get("mode")),
                    moves,
                    int(item.get("move_count", len(moves))),
                    float(item.get("elapsed_time", 0.0)),
                )
        self.schema_version = SCHEMA_VERSION

    def apply_manual_win(
        self,
        level_id: str,
        moves: list[str],
        score: int,
        move_count: int,
        elapsed: float,
    ) -> None:
        """Cập nhật kỷ lục khi người chơi tự thắng một màn (ít bước hơn thì tốt hơn)."""
        previous: int | None = self.best_scores.get(level_id)
        if previous is None or score <= previous:
            self.best_scores[level_id] = score
            self.saved_replays[level_id] = list(moves)
            self.level_stats[level_id] = {
                "score": score,
                "move_count": move_count,
                "elapsed_time": elapsed,
                "mode": MANUAL,
            }
        elif level_id not in self.saved_replays:
            self.saved_replays[level_id] = list(moves)
        previous_time: float | None = self.best_times.get(level_id)
        if previous_time is None or elapsed < previous_time:
            self.best_times[level_id] = elapsed

    def apply_ai_run(
        self,
        level_id: str,
        algorithm: str,
        moves: list[str],
        cost: int,
        solver_time: float,
        expanded_nodes: int = 0,
    ) -> None:
        """Lưu lời giải ngắn nhất của từng thuật toán cho một màn; không đụng vào kỷ lục của người chơi."""
        per_level: dict[str, dict[str, Any]] = self.ai_solutions.setdefault(level_id, {})
        previous: dict[str, Any] | None = per_level.get(algorithm)
        if previous is None or cost <= int(previous.get("cost", cost)):
            per_level[algorithm] = {
                "moves": list(moves),
                "cost": cost,
                "solver_time": round(float(solver_time), 6),
                "expanded_nodes": int(expanded_nodes),
                "timestamp": time.time(),
            }

    def best_replay(self, level_id: str) -> tuple[list[str], str] | None:
        """Đường đi nên phát lại: lượt tốt nhất của người chơi, nếu chưa có thì lời giải AI ngắn nhất."""
        manual: list[str] | None = self.saved_replays.get(level_id)
        if manual:
            return list(manual), MANUAL
        candidates: dict[str, dict[str, Any]] = self.ai_solutions.get(level_id, {})
        if not candidates:
            return None
        algorithm, entry = min(candidates.items(), key=lambda pair: int(pair[1].get("cost", 10**9)))
        return list(entry.get("moves", [])), algorithm

    def add_history(self, record: LevelRecord) -> None:
        """Thêm bản ghi, bỏ qua bản ghi trùng hệt bản liền trước và giữ tối đa MAX_HISTORY bản."""
        entry: dict[str, Any] = asdict(record)
        if self.history:
            last: dict[str, Any] = self.history[-1]
            if all(last.get(key) == entry[key] for key in ("level_id", "moves", "mode", "won")):
                return
        self.history.append(entry)
        del self.history[:-MAX_HISTORY]

    def ai_uses_left(self, level_id: str) -> int:
        """Số lượt dùng AI còn lại của người chơi này ở một màn."""
        return max(0, MAX_AI_USES_PER_LEVEL - int(self.ai_uses.get(level_id, 0)))

    def consume_ai_use(self, level_id: str) -> int:
        """Trừ một lượt dùng AI ở màn này; trả về số lượt còn lại (không âm)."""
        if self.ai_uses_left(level_id) > 0:
            self.ai_uses[level_id] = int(self.ai_uses.get(level_id, 0)) + 1
        return self.ai_uses_left(level_id)


class PasswordHasher:
    """Băm mật khẩu. Tài khoản cũ dùng SHA-256 một vòng; tài khoản mới dùng PBKDF2."""

    SCHEME_LEGACY: str = "sha256"
    SCHEME_CURRENT: str = "pbkdf2"
    ITERATIONS: int = 120_000

    @staticmethod
    def new_salt() -> str:
        """Sinh một chuỗi muối ngẫu nhiên."""
        return secrets.token_hex(16)

    @classmethod
    def hash(cls, password: str, salt: str, scheme: str | None = None) -> str:
        """Băm `password` với `salt` theo `scheme` (mặc định là bản mới)."""
        chosen: str = scheme or cls.SCHEME_CURRENT
        if chosen == cls.SCHEME_LEGACY:
            return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), cls.ITERATIONS).hex()

    @classmethod
    def verify(cls, password: str, salt: str, expected: str, scheme: str = "") -> bool:
        """Kiểm tra mật khẩu bằng phép so sánh thời gian không đổi; `scheme` rỗng nghĩa là băm cũ."""
        actual: str = cls.hash(password, salt, scheme or cls.SCHEME_LEGACY)
        return hmac.compare_digest(actual, expected)


class JsonFileStore:
    """Đọc và ghi một file JSON an toàn.

    - Ghi vào file tạm rồi thay thế nguyên tử, nên mất điện giữa chừng không làm hỏng file cũ.
    - Giữ bản sao lưu `.bak` của lần ghi trước.
    - File hỏng không bị ghi đè: được đổi tên để giữ lại, rồi thử khôi phục từ bản sao lưu.
    """

    def __init__(self, path: str | Path) -> None:
        """Gắn kho với đường dẫn file JSON."""
        self.path: Path = Path(path)
        self.notice: str = ""

    @property
    def backup_path(self) -> Path:
        """Đường dẫn file sao lưu (thêm đuôi `.bak`)."""
        return self.path.with_name(self.path.name + ".bak")

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        """Đọc một file JSON; yêu cầu dữ liệu gốc là một đối tượng."""
        with open(path, encoding="utf-8") as handle:
            data: Any = json.load(handle)
        if not isinstance(data, dict):
            raise TypeError("Dữ liệu gốc của file phải là một đối tượng JSON.")
        return data

    def load(self) -> dict[str, Any] | None:
        """Trả về dữ liệu đã lưu, hoặc None nếu chưa có file (hay không khôi phục được)."""
        self.notice = ""
        if not self.path.exists():
            return None
        try:
            return self._read(self.path)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            OSError,
            ValueError,
            TypeError,
        ) as error:
            kept: str = self._quarantine()
            recovered: dict[str, Any] | None = self._try_backup()
            self.notice = f"File dữ liệu bị hỏng ({type(error).__name__}); đã giữ lại bản sao '{kept}'" + (
                " và khôi phục từ bản sao lưu." if recovered is not None else "."
            )
            return recovered

    def _quarantine(self) -> str:
        """Đổi tên file hỏng để giữ lại; trả về tên mới."""
        stamp: str = time.strftime("%Y%m%d-%H%M%S")
        target: Path = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        try:
            os.replace(self.path, target)
        except OSError:
            return self.path.name
        return target.name

    def _try_backup(self) -> dict[str, Any] | None:
        """Đọc file sao lưu nếu có và còn nguyên vẹn."""
        if not self.backup_path.exists():
            return None
        try:
            return self._read(self.backup_path)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            OSError,
            ValueError,
            TypeError,
        ):
            return None

    def save(self, payload: dict[str, Any]) -> None:
        """Ghi `payload` nguyên tử: file tạm, sao lưu bản cũ, rồi thay thế."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if self.path.exists():
                shutil.copy2(self.path, self.backup_path)
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


class PlayerDataManager:
    """Quản lý tài khoản (đăng ký, đăng nhập, đăng xuất), kết quả chơi và lượt dùng AI của từng người."""

    def __init__(self, storage_path: str | Path | None = None, store: JsonFileStore | None = None) -> None:
        """Nạp dữ liệu từ `storage_path` (mặc định `data/players.json`) hoặc từ `store` được truyền vào."""
        if store is None:
            default: Path = Path(PROJECT_ROOT) / "data" / "players.json"
            store = JsonFileStore(storage_path if storage_path is not None else default)
        self._store: JsonFileStore = store
        self.players: dict[str, PlayerProfile] = {}
        self.current_user: str | None = None
        self.load_notice: str = ""
        self.save_error: str = ""
        self._load()

    @property
    def storage_path(self) -> Path:
        """Đường dẫn file dữ liệu."""
        return self._store.path

    @staticmethod
    def calculate_score(move_count: int, won: bool = True) -> int:
        """Điểm của một màn (xem `calculate_level_score`)."""
        return calculate_level_score(move_count=move_count, won=won)

    # ------------------------------------------------------------------ lưu và nạp

    def _load(self) -> None:
        """Nạp hồ sơ từ kho; hồ sơ không đọc được bị bỏ qua và được báo trong `load_notice`."""
        raw: dict[str, Any] | None = self._store.load()
        self.load_notice = self._store.notice
        self.players, self.current_user = {}, None
        if raw is None:
            return
        skipped: int = 0
        players: Any = raw.get("players", {})
        for name, data in players.items() if isinstance(players, dict) else []:
            try:
                self.players[str(name)] = PlayerProfile.from_dict(data)
            except TypeError, ValueError:
                skipped += 1
        if skipped:
            self.load_notice = (self.load_notice + f" Bỏ qua {skipped} hồ sơ không đọc được.").strip()
        last: Any = raw.get("last_active_user")
        self.current_user = last if last in self.players else None

    def save(self) -> bool:
        """Ghi toàn bộ dữ liệu xuống file. Trả về False (không ném lỗi) nếu không ghi được."""
        payload: dict[str, Any] = {
            "last_active_user": self.current_user,
            "players": {name: profile.to_dict() for name, profile in self.players.items()},
        }
        try:
            self._store.save(payload)
        except OSError as error:
            self.save_error = str(error)
            return False
        self.save_error = ""
        return True

    # ------------------------------------------------------------------ tài khoản

    def register(self, username: str, password: str) -> tuple[bool, str]:
        """Tạo tài khoản mới và đăng nhập luôn. Trả về (thành công, thông báo)."""
        name: str = username.strip()
        if not name:
            return False, "Tên tài khoản không được để trống."
        if len(password) < MIN_PASSWORD_LENGTH:
            return False, f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự."
        if name in self.players:
            return False, f"Tài khoản '{name}' đã tồn tại."
        salt: str = PasswordHasher.new_salt()
        self.players[name] = PlayerProfile(
            username=name,
            password_hash=PasswordHasher.hash(password, salt),
            salt=salt,
            hash_scheme=PasswordHasher.SCHEME_CURRENT,
        )
        self.current_user = name
        self.save()
        return True, f"Đăng ký và đăng nhập thành công tài khoản '{name}'."

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Đăng nhập tài khoản đã có; băm cũ được nâng cấp khi đăng nhập thành công."""
        name: str = username.strip()
        profile: PlayerProfile | None = self.players.get(name)
        if profile is None:
            return False, f"Không tìm thấy tài khoản '{name}'."
        if not profile.password_hash or not PasswordHasher.verify(
            password, profile.salt, profile.password_hash, profile.hash_scheme
        ):
            return False, "Mật khẩu không chính xác."
        if profile.hash_scheme != PasswordHasher.SCHEME_CURRENT:
            profile.salt = PasswordHasher.new_salt()
            profile.password_hash = PasswordHasher.hash(password, profile.salt)
            profile.hash_scheme = PasswordHasher.SCHEME_CURRENT
        self.current_user = name
        self.save()
        return True, f"Đăng nhập thành công. Xin chào '{name}'!"

    def logout(self) -> None:
        """Đăng xuất về tài khoản khách."""
        self.current_user = None
        self.save()

    def authenticate_or_register(self, username: str, password: str) -> tuple[bool, str]:
        """Có tài khoản (có mật khẩu) thì đăng nhập, chưa có thì đăng ký mới."""
        name: str = username.strip()
        profile: PlayerProfile | None = self.players.get(name)
        if profile is not None and name != GUEST and profile.password_hash:
            return self.login(name, password)
        return self.register(name, password)

    def get_current_profile(self) -> PlayerProfile | None:
        """Hồ sơ của người đang đăng nhập, hoặc None nếu đang là khách chưa có hồ sơ."""
        return self.players.get(self.current_user) if self.current_user is not None else None

    def _profile_for(self, username: str | None) -> PlayerProfile:
        """Hồ sơ cần ghi: tài khoản chỉ định, hoặc tài khoản hiện tại, nếu không có thì khách (guest)."""
        target: str | None = username or self.current_user
        if target is None or target not in self.players:
            target = GUEST
            self.players.setdefault(GUEST, PlayerProfile(username=GUEST))
        return self.players[target]

    # ------------------------------------------------------------------ kết quả

    def record_game_session(
        self,
        level_id: str,
        moves: Sequence[ActionInput],
        won: bool,
        mode: str = MANUAL,
        elapsed_time: float = 0.0,
        username: str | None = None,
    ) -> bool:
        """Ghi kết quả một lượt. Chỉ lượt MANUAL thắng mới cập nhật kỷ lục; chế độ khác là của thuật toán."""
        if mode != MANUAL:
            return self.record_solver_run(level_id, mode, moves, won, elapsed_time, username=username)
        profile: PlayerProfile = self._profile_for(username)
        names: list[str] = action_names(moves)
        move_count: int = count_moves(names)
        seconds: float = round(max(0.0, float(elapsed_time)), 3)
        score: int = calculate_level_score(move_count, won)
        profile.add_history(LevelRecord(level_id, names, move_count, won, MANUAL, seconds, score))
        if won:
            profile.apply_manual_win(level_id, names, score, move_count, seconds)
        return self.save()

    def record_solver_run(
        self,
        level_id: str,
        algorithm: str,
        moves: Sequence[ActionInput],
        solved: bool = True,
        solver_time: float = 0.0,
        expanded_nodes: int = 0,
        username: str | None = None,
    ) -> bool:
        """Ghi lời giải của thuật toán (đường đi đầy đủ từ ô xuất phát) mà không tính vào kỷ lục."""
        profile: PlayerProfile = self._profile_for(username)
        names: list[str] = action_names(moves)
        move_count: int = count_moves(names)
        profile.add_history(
            LevelRecord(
                level_id,
                names,
                move_count,
                solved,
                algorithm,
                round(max(0.0, solver_time), 6),
                calculate_level_score(move_count, solved),
            )
        )
        if solved:
            profile.apply_ai_run(level_id, algorithm, names, move_count, solver_time, expanded_nodes)
        return self.save()

    def get_level_score_info(self, level_id: str, username: str | None = None) -> dict[str, Any] | None:
        """Kỷ lục tự chơi của người chơi ở một màn (score, move_count, elapsed_time, mode)."""
        profile: PlayerProfile | None = self.players.get(username or self.current_user or GUEST)
        return None if profile is None else profile.level_stats.get(level_id)

    def get_saved_replay(self, level_id: str, username: str | None = None) -> list[str] | None:
        """Đường đi tốt nhất do người chơi tự đi ở một màn, hoặc None."""
        profile: PlayerProfile | None = self.players.get(username or self.current_user or GUEST)
        return None if profile is None else profile.saved_replays.get(level_id)

    def get_best_replay(self, level_id: str, username: str | None = None) -> tuple[list[str], str] | None:
        """(đường đi, nguồn) nên phát lại: lượt tốt nhất của người chơi, nếu chưa có thì của thuật toán."""
        profile: PlayerProfile | None = self.players.get(username or self.current_user or GUEST)
        return None if profile is None else profile.best_replay(level_id)

    # ------------------------------------------------------------------ lượt dùng AI

    def ai_uses_left(self, level_id: str, username: str | None = None) -> int:
        """Số lượt dùng AI còn lại ở một màn (mặc định `MAX_AI_USES_PER_LEVEL` nếu chưa dùng)."""
        profile: PlayerProfile | None = self.players.get(username or self.current_user or GUEST)
        return MAX_AI_USES_PER_LEVEL if profile is None else profile.ai_uses_left(level_id)

    def consume_ai_use(self, level_id: str, username: str | None = None) -> int:
        """Trừ một lượt dùng AI ở màn này, lưu lại, và trả về số lượt còn lại."""
        profile: PlayerProfile = self._profile_for(username)
        left: int = profile.consume_ai_use(level_id)
        self.save()
        return left
