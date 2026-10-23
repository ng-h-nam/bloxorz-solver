import json
from dataclasses import dataclass

from core.board import Board
from core.map_loader import load_coolmath_stage, resolve_coolmath_path


@dataclass(frozen=True)
class LevelEntry:
    index: int
    name: str
    passcode: str


class LevelCatalog:
    """Danh mục các màn trong coolmath.json và trạng thái khóa hoặc mở của từng màn.

    Chỉ đọc tên và mật khẩu; lưới của một màn chỉ được phân tích khi gọi `board()`.
    """

    def __init__(self, entries: list[LevelEntry], path: str = "") -> None:
        self.entries: list[LevelEntry] = list(entries)
        self.path: str = path
        self._unlocked: set[int] = {0} if self.entries else set()

    @classmethod
    def from_json(cls, path: str | None = None) -> "LevelCatalog":
        resolved = resolve_coolmath_path(path)
        with open(resolved, encoding="utf-8") as handle:
            data = json.load(handle)
        stages = [data] if isinstance(data, dict) else data
        entries = [
            LevelEntry(
                index=i,
                name=str(stage.get("name") or f"Stage {i + 1:02d}"),
                passcode=str(stage.get("passcode", "")).strip(),
            )
            for i, stage in enumerate(stages)
        ]
        return cls(entries, resolved)

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def names(self) -> list[str]:
        return [entry.name for entry in self.entries]

    @property
    def passcode_length(self) -> int:
        return max((len(entry.passcode) for entry in self.entries), default=6)

    def index_of(self, name: str) -> int:
        """Chỉ số của màn có đúng tên `name`, hoặc -1."""
        for entry in self.entries:
            if entry.name == name:
                return entry.index
        return -1

    def board(self, index: int) -> Board:
        """Phân tích và trả về Board của màn thứ `index` (đếm từ 0)."""
        return load_coolmath_stage(index + 1, self.path)

    def next_index(self, index: int) -> int | None:
        return index + 1 if 0 <= index + 1 < len(self.entries) else None

    def is_unlocked(self, index: int) -> bool:
        return index in self._unlocked

    def unlock(self, index: int | None) -> None:
        if index is not None and 0 <= index < len(self.entries):
            self._unlocked.add(index)

    def check_passcode(self, index: int, code: str) -> bool:
        """So khớp chính xác với mật khẩu của màn `index`; không suy ra màn từ các chữ số."""
        if not 0 <= index < len(self.entries):
            return False
        expected = self.entries[index].passcode
        return bool(expected) and code.strip() == expected

    def unlock_with_passcode(self, index: int, code: str) -> bool:
        if self.check_passcode(index, code):
            self.unlock(index)
            return True
        return False
