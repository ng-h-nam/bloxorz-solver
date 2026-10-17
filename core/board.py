import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, FrozenSet, Tuple, Union, Any
from state import Coordinates

class TileType(Enum):
    VOID = "."         
    FLOOR = "F"       
    GOAL = "T"         
    FRAGILE = "O"     
    FALLING = "O"
    BRIDGE = "a"     
    SOFT_SWITCH = "A" 
    HEAVY_SWITCH = "0"
    SPLIT_SWITCH = "U"

class BridgeMode(Enum):
    TOGGLE = "onoff"    # Đảo trạng thái đóng <-> mở
    OPEN = "on"         # Luôn mở cầu
    CLOSE = "off"       # Luôn đóng cầu


@dataclass(frozen=True)
class BridgeAction:
    """Mô tả tác động của một công tắc lên 1 ô cầu cụ thể."""
    target_pos: Coordinates   
    mode: BridgeMode = BridgeMode.TOGGLE

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
        symbols: Optional[List[List[str]]] = None,
        start_pos: Coordinates = (0, 0),
        end_pos: Coordinates = (0, 0),
        initial_active_bridges: Optional[FrozenSet[Coordinates]] = None, 
        switches: Optional[Dict[Coordinates, List[BridgeAction]]] = None,
        splits: Optional[Dict[Coordinates, Tuple[Coordinates, Coordinates]]] = None,

    ):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.symbols = symbols
        self.initial_active_bridges: FrozenSet[Coordinates] = (
            initial_active_bridges or FrozenSet()
        )

        self.switches: Dict[Coordinates, List[BridgeAction]] = switches or {}
        self.splits: Dict[Coordinates, Tuple[Coordinates, Coordinates]] = splits or {}
        
    def _auto_bind_switches_from_symbols(self) -> Dict[Coordinates, List[BridgeAction]]:
        """
        Tự động liên kết công tắc ('A'-'Z') với các ô cầu ('a'-'z') có cùng chữ cái
        dựa trên ma trận symbols do map_loader.py cung cấp.
        """
        bridges_by_char: Dict[str, List[Coordinates]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == TileType.BRIDGE:
                    ch = self.symbols[r][c].lower()
                    bridges_by_char.setdefault(ch, []).append((r, c))

        auto_switches: Dict[Coordinates, List[BridgeAction]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                tile = self.grid[r][c]
                if tile in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH):
                    ch = self.symbols[r][c]
                    target_char = ch.lower()
                    if target_char in bridges_by_char:
                        auto_switches[(r, c)] = [
                            BridgeAction(target_pos=pos, mode=BridgeMode.TOGGLE)
                            for pos in bridges_by_char[target_char]
                        ]
        return auto_switches
    def in_board(self, r: int, c: int) -> bool:
        """Kiểm tra tọa độ (r, c) có nằm trong phạm vi lưới hay không."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_symbol(self, r: int, c: int) -> str:
        """Trả về ký tự gốc trong file map tại (r, c)."""
        if not self.in_bounds(r, c):
            return "."
        return self.symbols[r][c]
    
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

    def __str__(self) -> str:
        """In bản đồ ra màn hình console bằng chính các dấu trong TileType."""
        return "\n".join(
            "".join(tile.value for tile in row) for row in self.grid
        )

    

