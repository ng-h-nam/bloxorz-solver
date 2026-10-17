import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, FrozenSet, Tuple, Union, Any
from state import Coordinates

class TileType(Enum):
    VOID = " "         
    FLOOR = "F"       
    GOAL = "T"         
    FRAGILE = "W"     
    BRIDGE = "="     
    SOFT_SWITCH = "O" 
    HEAVY_SWITCH = "X"
    SPLIT_SWITCH = "U"

class BridgeMode(Enum):
    TOGGLE = "onoff"    # Đảo trạng thái đóng <-> mở
    OPEN = "on"         # Luôn mở cầu
    CLOSE = "off"       # Luôn đóng cầu


@dataclass(frozen=True)
class BridgeAction:
    """Mô tả tác động của một công tắc lên 1 ô cầu cụ thể."""
    target_pos: Coordinates   
    mode: BridgeMode  

TXT_CHAR_TO_TILE: Dict[str, TileType] = {
    ".": TileType.VOID,
    "0": TileType.VOID,
    "F": TileType.FLOOR,     
    "#": TileType.FLOOR,
    "1": TileType.FLOOR,
    "S": TileType.FLOOR,     
    "T": TileType.GOAL,      
    "G": TileType.GOAL,
    "W": TileType.FRAGILE,   
    "=": TileType.BRIDGE,
    "B": TileType.BRIDGE,
    "O": TileType.SOFT_SWITCH,
    "X": TileType.HEAVY_SWITCH,
    "U": TileType.SPLIT_SWITCH,

}

# 2. Bảng ánh xạ riêng cho file levels.json (33 màn Coolmath Games)
JSON_CHAR_TO_TILE: Dict[str, TileType] = {
    " ": TileType.VOID,
    "b": TileType.FLOOR,
    "e": TileType.GOAL,
    "f": TileType.FRAGILE,
    "s": TileType.SOFT_SWITCH,
    "h": TileType.HEAVY_SWITCH,
    "v": TileType.SPLIT_SWITCH,
    "l": TileType.BRIDGE,
    "r": TileType.BRIDGE,
    "k": TileType.BRIDGE,
    "q": TileType.BRIDGE,
}

INITIAL_OPEN_BRIDGE_CHARS = {"k", "q"}


class Board:
    """
    Lưu trữ cấu trúc của màn chơi, bao gồm: layout, điểm xuất phát, điểm đích, vị trí cầu.
    """
    def __init__(
        self, 
        grid: List[List[TileType]],
        start_pos: Coordinates,
        end_pos: Coordinates,
        initial_active_bridges: Optional[FrozenSet[Coordinates]] = None, 
        switches: Optional[Dict[Coordinates, List[BridgeAction]]] = None,
        splits: Optional[Dict[Coordinates, Tuple[Coordinates, Coordinates]]] = None,
        level_id: str = "level0"

    ):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.initial_active_bridges: FrozenSet[Coordinates] = (
            initial_active_bridges or FrozenSet()
        )

        self.switches: Dict[Coordinates, List[BridgeAction]] = switches or {}
        self.splits: Dict[Coordinates, Tuple[Coordinates, Coordinates]] = splits or {}
        self.level_id = level_id


    def in_board(self, r: int, c: int) -> bool:
        """Kiểm tra tọa độ (r, c) có nằm trong phạm vi lưới hay không."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_tile(self, r: int, c: int) -> TileType:
        """Trả về loại ô tại vị trí (r, c). Nếu không trong cuộc chơi, đã tính là rơi xuống the void."""
        if not self.in_board(r, c):
            return TileType.VOID
        return self.grid[r][c]

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

    @classmethod
    def from_str_grid(cls, lines: List[str], level_id: str = "txt_map") -> "Board":
        """
        Khởi tạo Board từ danh sách chuỗi theo chuẩn level0.txt:
          '.' : VOID
          'F' : FLOOR
          'S' : Start (FLOOR)
          'T' : Target / GOAL
        """
        grid: List[List[TileType]] = []
        start_pos: Optional[Coordinates] = None
        goal_pos: Optional[Coordinates] = None

        # Lọc bỏ các dòng trống ở cuối file txt (nếu có)
        clean_lines = [line.strip() for line in lines if line.strip()]

        for r, line in enumerate(clean_lines):
            row_tiles: List[TileType] = []
            for c, ch in enumerate(line):
                if ch == "S":
                    start_pos = (r, c)
                elif ch in ("T", "G"):
                    goal_pos = (r, c)
                tile = TXT_CHAR_TO_TILE.get(ch, TileType.VOID)
                row_tiles.append(tile)
            grid.append(row_tiles)

        if start_pos is None or goal_pos is None:
            raise ValueError("File map TXT phải có vị trí xuất phát 'S' và đích 'T' (hoặc 'G').")

        return cls(grid=grid, start_pos=start_pos, goal_pos=goal_pos, level_id=level_id)

    @classmethod
    def from_txt(cls, filepath: str) -> "Board":
        """Đọc trực tiếp file .txt (ví dụ: level0.txt)."""
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return cls.from_string_grid(lines, level_id=filepath)

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

    

