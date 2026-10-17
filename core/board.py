import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, FrozenSet, Tuple, Union, Any, Iterable
from core.state import Coordinates

class TileType(Enum):
    VOID = " "         
    FLOOR = "b"       
    GOAL = "e"         
    FRAGILE = "f"     
    BRIDGE = "="     
    SOFT_SWITCH = "s" 
    HEAVY_SWITCH = "h"
    SPLIT_SWITCH = "v"

class BridgeMode(Enum):
    TOGGLE = "onoff"    # Đảo trạng thái đóng <-> mở
    OPEN = "on"         # Luôn mở cầu
    CLOSE = "off"       # Luôn đóng cầu


@dataclass(frozen=True)
class BridgeAction:
    """Mô tả tác động của một công tắc lên 1 ô cầu cụ thể."""
    target_pos: Coordinates   # Tọa độ (r, c) của ô cầu
    mode: BridgeMode    # Chế độ: onoff (toggle), on (mở), off (đóng)

    # nếu còn yếu tố in_game nào khác thì ae feedback nhé, t chơi gà quá ms tới màn 10 à :(

JSON_CHAR_TO_TILE: Dict[str, TileType] = {
    " ": TileType.VOID,
    "b": TileType.FLOOR,
    "e": TileType.GOAL,
    "G": TileType.GOAL,
    "f": TileType.FRAGILE,
    "s": TileType.SOFT_SWITCH,
    "h": TileType.HEAVY_SWITCH,
    "v": TileType.SPLIT_SWITCH,
    # 4 ký hiệu cầu trong levels.json đều quy về TileType.BRIDGE:
    "l": TileType.BRIDGE,    # Cầu đóng (trái)
    "r": TileType.BRIDGE,    # Cầu đóng (phải)
    "k": TileType.BRIDGE,    # Cầu MỞ   (trái)
    "q": TileType.BRIDGE,    # Cầu MỞ   (phải)
}

# Các ký tự đại diện cho cầu ĐANG MỞ SẴN khi bắt đầu màn chơi
INITIAL_OPEN_BRIDGE_CHARS = {"k", "q"}


class Board:
    """
    Lưu trữ cấu trúc của màn chơi, bao gồm: layout, điểm xuất phát, điểm đích, vị trí cầu.
    """
    def __init__(
        self,
        grid: List[List[TileType]],
        symbols: List[List[str]],
        start_pos: Coordinates,
        goal_pos: Coordinates,
        initial_active_bridges: Optional[Iterable[Coordinates]] = None,
    ):
        self.grid = grid
        self.symbols = symbols
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0
        self.start_pos = start_pos
        self.goal_pos = goal_pos
        self.initial_active_bridges: FrozenSet[Coordinates] = frozenset(
            initial_active_bridges or ()
        )

    def in_board(self, r: int, c: int) -> bool:
        """Kiểm tra tọa độ (r, c) có nằm trong lưới hay không."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_tile(self, r: int, c: int) -> TileType:
        """Trả về loại ô tại (r, c). Ngoài lưới được coi là VOID."""
        if not self.in_board(r, c):
            return TileType.VOID
        return self.grid[r][c]

    def get_symbol(self, r: int, c: int) -> str:
        """Trả về ký hiệu gốc trong file map, ví dụ 'A' hoặc 'c'."""
        return self.symbols[r][c]

    def apply_switch(
        self, switch_pos: Coordinates, current_bridges: FrozenSet[Coordinates]
    ) -> FrozenSet[Coordinates]:
        """
        Cập nhật tập hợp các cầu đang mở khi công tắc tại switch_pos được kích hoạt.
        Trả về một frozenset mới.
        """
        if switch_pos not in self.switches:
            return current_bridges

        active_set = set(current_bridges)
        for action in self.switches[switch_pos]:
            bridge_coord = action.target_pos
            if action.mode == BridgeMode.OPEN:
                active_set.add(bridge_coord)
            elif action.mode == BridgeMode.CLOSE:
                active_set.discard(bridge_coord)
            elif action.mode == BridgeMode.TOGGLE:
                if bridge_coord in active_set:
                    active_set.remove(bridge_coord)
                else:
                    active_set.add(bridge_coord)

        return frozenset(active_set)

    @staticmethod
    def _decode_packed_coord(key_str: str) -> Coordinates:
        """
        Tọa độ của file được tính từ công thức: key = x * 10 + y.
        """
        packed = int(key_str)
        c = packed // 10  # x (cột)
        r = packed % 10   # y (dòng)
        return (r, c)

    @classmethod
    def from_level_dict(cls, data: Dict[str, Any]) -> "Board":
        """Khởi tạo đối tượng Board từ 1 dictionary màn chơi trong levels.json."""
        raw_tiles: List[str] = data["tiles"]
        grid: List[List[TileType]] = []
        end_pos: Optional[Coordinates] = None
        open_bridges = set()


        for r, line in enumerate(raw_tiles):
            row_tiles: List[TileType] = []
            for c, char in enumerate(line):
                if char == "e":
                    end_pos = (r, c)
                elif char in INITIAL_OPEN_BRIDGE_CHARS:
                    open_bridges.add((r, c))
                tile = JSON_CHAR_TO_TILE.get(char, TileType.VOID)
                row_tiles.append(tile)
            grid.append(row_tiles)

        spawn_x, spawn_y = data["spawn"]
        start_pos: Coordinates = (spawn_y, spawn_x)

        if end_pos is None:
            raise ValueError(f"Level '{data.get('id')}' không có ô đích 'e'.")

        switches: Dict[Coordinates, List[BridgeAction]] = {}
        for key_str, action_list in data.get("switches", {}).items():
            switch_pos = cls._decode_packed_coord(key_str)
            actions: List[BridgeAction] = []
            for bx, by, mode_str in action_list:
                actions.append(
                    BridgeAction(target_pos=(by, bx), mode=BridgeMode(mode_str))
                )
            switches[switch_pos] = actions

        splits: Dict[Coordinates, Tuple[Coordinates, Coordinates]] = {}
        for key_str, coords in data.get("splits", {}).items():
            split_pos = cls._decode_packed_coord(key_str)
            x1, y1, x2, y2 = coords
            splits[split_pos] = ((y1, x1), (y2, x2))

        return cls(
            grid=grid,
            start_pos=start_pos,
            end_pos=end_pos,
            initial_active_bridges=frozenset(open_bridges),
            switches=switches,
            splits=splits,
            level_id=data.get("id", "unknown"),
            passcode=data.get("code", 0),
            raw_tiles=raw_tiles,
        )

    @classmethod
    def from_levels_json(
        cls, filepath: str, selector: Union[int, str] = 0
    ) -> "Board":
        """Nạp bản đồ từ file JSON theo chuẩn."""
        with open(filepath, "r", encoding="utf-8") as f:
            all_data = json.load(f)

        levels = all_data["levels"]

        if isinstance(selector, str):
            for lvl in levels:
                if lvl.get("id") == selector:
                    return cls.from_level_dict(lvl)
            raise ValueError(f"Không tìm thấy màn chơi có id='{selector}'.")

        # Tìm theo chỉ số index (0..32) hoặc theo passcode (ví dụ: 780464)
        if 0 <= selector < len(levels):
            return cls.from_level_dict(levels[selector])

        for lvl in levels:
            if lvl.get("code") == selector:
                return cls.from_level_dict(lvl)

        raise ValueError(f"Không tìm thấy màn chơi ứng với selector={selector}.")

    def __str__(self) -> str:
        """In bản đồ ra màn hình console bằng chính các dấu trong TileType."""
        return "\n".join(
            "".join(tile.value for tile in row) for row in self.grid
        )

    

