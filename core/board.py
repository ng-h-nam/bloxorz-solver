from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, FrozenSet, Tuple, Any
from core.state import Coordinates, Orientation, State


class TileType(Enum):
    VOID = "."
    FLOOR = "F"
    GOAL = "T"
    FRAGILE = "O"
    BRIDGE = "a"
    SOFT_SWITCH = "A"
    HEAVY_SWITCH = "0"
    SPLIT_SWITCH = "U"


class BridgeMode(Enum):
    TOGGLE = "onoff"  # Đảo trạng thái đóng <-> mở
    OPEN = "on"  # Luôn mở cầu
    CLOSE = "off"  # Luôn đóng cầu

    @classmethod
    def from_str(cls, text: str) -> "BridgeMode":
        t = text.strip().lower()
        if t in ("onoff", "toggle", "switch", "swap"):
            return cls.TOGGLE
        if t in ("on", "open", "enable", "permanent", "permanent_open"):
            return cls.OPEN
        if t in ("off", "close", "disable", "permanent_close"):
            return cls.CLOSE
        raise ValueError(f"Chế độ cầu không hợp lệ: '{text}'")


@dataclass(frozen=True)
class BridgeAction:
    """Mô tả tác động của một công tắc lên 1 ô cầu cụ thể."""

    target_pos: Coordinates
    mode: BridgeMode = BridgeMode.TOGGLE
    bridge_id: str = ""


@dataclass(frozen=True)
class BridgeMetadata:
    """Metadata chi tiết cho từng cây cầu (đặc biệt quan trọng với các màn chơi có hơn 2 cây cầu).
    - bridge_id: Ký hiệu định danh cây cầu (ví dụ: "a", "b", "c").
    - cells: Danh sách các tọa độ thuộc cây cầu đó.
    - priority (quan trọng): Độ ưu tiên giải quyết cây cầu đó trước trong thuật toán. (1 -> 2 -> ...)
    - initial_open: Trạng thái ban đầu (True = mở sẵn, False = đóng sẵn.)
    - controlled_by: Danh sách tọa độ (r, c) của các công tác điều khiển cây cầu này.
    - requires: Danh sách bridge_id của các cây cầu bắt buộc phải mở trước cái cầu này.
    """

    bridge_id: str
    cells: tuple[Coordinates, ...]
    priority: int = 1
    initial_open: bool = False
    controlled_by: tuple[Coordinates, ...] = field(default_factory=tuple)
    requires: tuple[str, ...] = field(default_factory=tuple)



@dataclass(frozen=True)
class SwitchMetadata:
    """Metadata chi tiết của một công tắc trên bản đồ."""

    switch_id: str
    pos: Coordinates
    switch_type: TileType
    actions: tuple[BridgeAction, ...] = field(default_factory=tuple)


class Board:
    """
    Lưu trữ cấu trúc của màn chơi, bao gồm: layout, điểm xuất phát, điểm đích, vị trí cầu.
    """

    def __init__(
        self,
        grid: list[list[TileType]],
        symbols: list[list[str]] | None = None,
        start_pos: Coordinates = (0, 0),
        end_pos: Coordinates = (0, 0),
        initial_active_bridges: Optional[FrozenSet[Coordinates]] = None,
        switches: Optional[Dict[Coordinates, List[BridgeAction]]] = None,
        splits: Optional[Dict[Coordinates, Tuple[Coordinates, Coordinates]]] = None,
        bridge_metadata: Optional[Dict[str, BridgeMetadata]] = None,
        switch_metadata: Optional[Dict[Coordinates, SwitchMetadata]] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.grid = grid
        self.symbols = symbols
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0
        self.height = self.rows
        self.width = self.cols
        self.start_pos = start_pos
        self.end_pos = end_pos

        if symbols is not None:
            self.symbols = symbols
        else:
            self.symbols = [[tile.value for tile in row] for row in grid]

        self.splits: dict[Coordinates, tuple[Coordinates, Coordinates]] = splits or {}
        self.raw_metadata: dict[str, Any] = raw_metadata or {}
        self.bridge_groups: dict[str, list[Coordinates]] = self._collect_bridge_groups()

        if switches is not None:
            self.switches: dict[Coordinates, list[BridgeAction]] = switches
        else:
            self.switches = self._auto_bind_switches_from_symbols()

        if bridge_metadata is not None:
            self.bridge_metadata = bridge_metadata
        else:
            self.bridge_metadata = self._build_default_bridge_metadata(initial_active_bridges)

        if switch_metadata is not None:
            self.switch_metadata = switch_metadata
        else:
            self.switch_metadata = self._build_switch_metadata()

        open_cells = set(initial_active_bridges or frozenset())
        for b_meta in self.bridge_metadata.values():
            if b_meta.initial_open:
                open_cells.update(b_meta.cells)
        self.initial_active_bridges: frozenset[Coordinates] = frozenset(open_cells)

    def _collect_bridge_groups(self) -> Dict[str, List[Coordinates]]:
        """Gom các tọa độ ô cầu có cùng ký tự định danh ('a'..'z') thành từng cụm cầu."""
        groups: dict[str, list[Coordinates]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == TileType.BRIDGE:
                    char = self.symbols[r][c]
                    groups.setdefault(char, []).append((r, c))
        return groups

    def _auto_bind_switches_from_symbols(self) -> Dict[Coordinates, List[BridgeAction]]:
        """
        Tự động liên kết:
        - Công tắc chữ hoa ('A'-'Z') với nhóm cầu chữ thường ('a'-'z') tương ứng.
        - Công tắc số ('0'-'9') với nhóm cầu thứ d ('0' -> 'a', '1' -> 'b', ...).
        """
        bridges_by_char: dict[str, list[Coordinates]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == TileType.BRIDGE:
                    ch = self.symbols[r][c].lower()
                    bridges_by_char.setdefault(ch, []).append((r, c))

        sorted_bridge_ids = sorted(bridges_by_char.keys())
        auto_switches: dict[Coordinates, list[BridgeAction]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                tile = self.grid[r][c]
                if tile in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH):
                    ch = self.symbols[r][c]
                    target_char: str | None = None
                    if ch.isalpha() and ch.lower() in bridges_by_char:
                        target_char = ch.lower()
                    elif ch.isdigit():
                        mapped_char = chr(ord("a") + int(ch))
                        if mapped_char in bridges_by_char:
                            target_char = mapped_char
                        elif int(ch) < len(sorted_bridge_ids):
                            target_char = sorted_bridge_ids[int(ch)]

                    if target_char is not None:
                        auto_switches[(r, c)] = [
                            BridgeAction(
                                target_pos=pos,
                                mode=BridgeMode.TOGGLE,
                                bridge_id=target_char,
                            )
                            for pos in bridges_by_char[target_char]
                        ]
        return auto_switches

    def _build_default_bridge_metadata(
        self, initial_open_set: frozenset[Coordinates] | None = None
    ) -> dict[str, BridgeMetadata]:
        """
        Tự động sinh BridgeMetadata và dự đoán thứ tự ưu tiên
        dựa trên khoảng cách Manhattan?? từ điểm xuất phát tới công tắc điều khiển cầu đó.
        """
        open_set = initial_open_set or frozenset()
        switch_map: dict[str, list[Coordinates]] = {b_id: [] for b_id in self.bridge_groups}

        for sw_pos, actions in self.switches.items():
            for act in actions:
                for b_id, cells in self.bridge_groups.items():
                    if act.target_pos in cells and sw_pos not in switch_map[b_id]:
                        switch_map[b_id].append(sw_pos)

        # thứ tự ưu tiên mặc định: cầu nào có công tắc gần điểm xuất phát S hơn sẽ được ưu tiên trước.
        def estimate_distance(b_id: str) -> tuple[int, str]:
            controllers = switch_map.get(b_id, [])
            if controllers:
                min_dist = min(abs(sr - self.start_pos[0]) + abs(sc - self.start_pos[1]) for sr, sc in controllers)
                return (min_dist, b_id)
            cells = self.bridge_groups[b_id]
            min_dist = min(abs(br - self.start_pos[0]) + abs(bc - self.start_pos[1]) for br, bc in cells)
            return (min_dist, b_id)

        ordered_ids = sorted(self.bridge_groups.keys(), key=estimate_distance)
        metadata_dict: dict[str, BridgeMetadata] = {}

        for rank, b_id in enumerate(ordered_ids, start=1):
            cells = tuple(self.bridge_groups[b_id])
            is_open = all(cell in open_set for cell in cells) if cells else False
            metadata_dict[b_id] = BridgeMetadata(
                bridge_id=b_id,
                cells=cells,
                priority=rank,
                initial_open=is_open,
                controlled_by=tuple(switch_map.get(b_id, [])),
                requires=(),
            )
        return metadata_dict

    def _build_switch_metadata(self) -> dict[Coordinates, SwitchMetadata]:
        sw_meta: dict[Coordinates, SwitchMetadata] = {}
        for sw_pos, actions in self.switches.items():
            r, c = sw_pos
            sw_meta[sw_pos] = SwitchMetadata(
                switch_id=self.get_symbol(r, c),
                pos=sw_pos,
                switch_type=self.get_tile(r, c),
                actions=tuple(actions),
            )
        return sw_meta

    # --- CÁC HÀM TRUY VẤN METADATA CẦU DÀNH CHO SOLVER (BFS / DFS / UCS / A*) ---

    def has_multiple_bridges(self) -> bool:
        """Kiểm tra màn chơi có từ 2 cây cầu trở lên hay không."""
        return len(self.bridge_metadata) >= 2

    def get_bridges_by_priority(self) -> List[BridgeMetadata]:
        """
        Trả về danh sách các cây cầu theo đúng thứ tự ưu tiên cần giải quyết
        (priority = 1 -> 2 -> 3...).
        """
        return sorted(
            self.bridge_metadata.values(),
            key=lambda b: (b.priority, b.bridge_id),
        )

    def is_bridge_open(self, bridge_id: str, state: State) -> bool:
        """Kiểm tra toàn bộ các ô của cây cầu `bridge_id` đã được mở trong `state` hay chưa."""
        if bridge_id not in self.bridge_metadata:
            return False
        cells = self.bridge_metadata[bridge_id].cells
        return all(cell in state.active_bridges for cell in cells)

    def get_next_priority_bridge(self, state: State) -> Optional[BridgeMetadata]:
        """
        Trả về cây cầu có độ ưu tiên cao nhất hiện đang ĐÓNG,
        mà các cầu điều kiện tiên quyết (requires) của nó đều đã mở. (Quan trọng).
        """
        for b_meta in self.get_bridges_by_priority():
            if not self.is_bridge_open(b_meta.bridge_id, state):
                # Kiểm tra các cầu điều kiện đã mở hết chưa
                if all(self.is_bridge_open(req_id, state) for req_id in b_meta.requires):
                    return b_meta
        return None

    # --- CÁC HÀM KIỂM TRA BÀN CỜ & LUẬT CHƠI CƠ BẢN ---

    def in_board(self, r: int, c: int) -> bool:
        """Kiểm tra tọa độ (r, c) có nằm trong lưới hay không."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_symbol(self, r: int, c: int) -> str:
        """Trả về ký tự gốc trong file map tại (r, c)."""
        if not self.in_board(r, c):
            return "."
        return self.symbols[r][c]

    def get_tile(self, r: int, c: int) -> TileType:
        """Trả về loại ô tại (r, c). Ngoài lưới được coi là VOID."""
        if not self.in_board(r, c):
            return TileType.VOID
        return self.grid[r][c]

    def get_symbol(self, r: int, c: int) -> str:
        """Trả về ký hiệu gốc trong file map, ví dụ 'A' hoặc 'c'."""
        return self.symbols[r][c]

    def apply_switch(self, switch_pos: Coordinates, current_bridges: FrozenSet[Coordinates]) -> FrozenSet[Coordinates]:
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

    def is_out_of_bounds(self, state) -> bool:
        """
        Kiểm tra xem block có nằm ngoài map hay không?
        Trả về True nếu có, còn False nếu ngược lại."""

        for r, c in state.get_occupied_cells():
            if not self.in_board(r, c):
                return True
        return False

    def is_on_void(self, state) -> bool:
        """
        Kiểm tra xem block có nằm trên ô void hay không?
        (Trong màn chơi sẽ có 2 thứ cần chú ý: biên của game và VOID.)
        """
        # Để dễ giải thích, ta xét map chơi là 1 hình chữ nhật với kích thước r * c.
        # Trong đó, ngoài các ô floor, start, end,.. ra thì có các ô void nữa.
        # Nên ta cần kiểm tra sự tồn tại của cả 2 cái.

        for r, c in state.get_occupied_cells():
            if self.in_board(r, c) and self.grid[r][c] == TileType.VOID:
                return True
        return False

    def is_on_valid_tiles(self, state: State) -> bool:
        """
        Kiểm tra xem block có nằm trên các tile hợp lệ hay không:
        1. Không vượt ra ngoài biên bản đồ và không đè lên ô VOID.
        2. Nếu đi qua Bridge thì cầu phải đang mở.
        3. Nếu đang STANDING thì không được đứng trên ô gạch mỏng (FRAGILE).
        """
        occupied = state.get_occupied_cells()

        for r, c in occupied:
            if not self.in_board(r, c):
                return False
            tile = self.grid[r][c]
            if tile == TileType.VOID:
                return False
            if tile == TileType.BRIDGE and (r, c) not in state.active_bridges:
                return False

        if state.orientation == Orientation.STANDING:
            r, c = occupied[0]
            if self.grid[r][c] == TileType.FRAGILE:
                return False
        return True

    def is_valid_move(self, state: State) -> bool:
        """Kiểm tra tất thảy các điều kiện đó luôn."""
        return self.is_on_valid_tiles(state)

    def is_goal_state(self, state: State) -> bool:
        return state.is_standing_at(self.end_pos)

    def __str__(self) -> str:
        """In bản đồ ra màn hình console bằng chính các dấu trong TileType."""
        return "\n".join("".join(tile.value for tile in row) for row in self.grid)
