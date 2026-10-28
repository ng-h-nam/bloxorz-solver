from typing import Any, Dict, List, Optional, Tuple, Union
import json
import os

from core.board import (
    Board,
    BridgeAction,
    BridgeMetadata,
    BridgeMode,
    SwitchMetadata,
    TileType,
)
from core.state import Coordinates


# Danh sách ký hiệu chữ in hoa hợp lệ cho SOFT_SWITCH trong hệ thống ký hiệu nội bộ của Board
# (tránh trùng với các ký hiệu đặc biệt: F=FLOOR, S=START, T=GOAL, O=FRAGILE, U=SPLIT_SWITCH)
_SOFT_SWITCH_SYMBOLS: Tuple[str, ...] = tuple(
    ch for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if ch not in {"F", "S", "T", "O", "U"}
)
_HEAVY_SWITCH_SYMBOLS: Tuple[str, ...] = tuple("0123456789")


def classify(ch: str) -> TileType:
    """
    Chuyển một ký hiệu trong lưới 'grid' của coolmath.json (game gốc Bloxorz) thành TileType:
      - ' ' : Ô trống / vực thẳm (VOID)
      - '.' : Ô gạch sàn thường (FLOOR)
      - 'S' : Điểm xuất phát (FLOOR + start_pos)
      - 'H' : Ô đích / lỗ vuông (GOAL + end_pos)
      - '-' : Ô gạch cam mỏng, đứng thẳng sẽ vỡ (FRAGILE)
      - 'O' : Công tắc tròn (Round / Soft Switch - chạm bất kỳ tư thế nào cũng kích hoạt)
      - 'X' : Công tắc chữ X (Heavy Switch - chỉ kích hoạt khi khối 1x1x2 đứng thẳng)
      - 'T' : Công tắc phân tách / dịch chuyển (Teleport / Split Switch)
      - 'b' : Cầu lúc bắt đầu đang ĐÓNG (BRIDGE, initial_open=False)
      - 'B' : Cầu lúc bắt đầu đang MỞ (BRIDGE, initial_open=True)
    """
    if ch == " ":
        return TileType.VOID
    if ch in ".S":
        return TileType.FLOOR
    if ch == "H":
        return TileType.GOAL
    if ch == "-":
        return TileType.FRAGILE
    if ch == "O":
        return TileType.SOFT_SWITCH
    if ch == "X":
        return TileType.HEAVY_SWITCH
    if ch == "T":
        return TileType.SPLIT_SWITCH
    if ch in ("b", "B"):
        return TileType.BRIDGE
    raise ValueError(f"Ký tự lạ '{ch}' trong dữ liệu coolmath.json")


classify_coolmath = classify


def _parse_bridge_mode(text: str) -> BridgeMode:
    """Chuyển chuỗi chế độ công tắc ('swap', 'on', 'off') trong coolmath.json thành BridgeMode."""
    t = text.strip().lower()
    if t in ("swap", "onoff", "toggle", "switch"):
        return BridgeMode.TOGGLE
    if t in ("on", "open", "enable", "permanent", "permanent_open"):
        return BridgeMode.OPEN
    if t in ("off", "close", "disable", "permanent_close"):
        return BridgeMode.CLOSE
    return BridgeMode.from_str(text)


def _bridge_index_to_id(index: int) -> str:
    """Ánh xạ chỉ số cầu 0, 1, 2... trong coolmath.json thành định danh 'a', 'b', 'c'..."""
    if 0 <= index < 26:
        return chr(ord("a") + index)
    return f"b{index}"


def parse_coolmath_stage(stage_data: Dict[str, Any]) -> Board:
    """
    Chuyển đổi dữ liệu của một màn chơi (Stage) từ coolmath.json thành đối tượng Board
    chuẩn xác theo luật của tựa game Bloxorz gốc:
      - Xử lý lưới 'grid' (' ': VOID, '.': FLOOR, 'S': START, 'H': GOAL, '-': FRAGILE,
        'O': SOFT_SWITCH, 'X': HEAVY_SWITCH, 'T': SPLIT_SWITCH, 'b': cầu đóng, 'B': cầu mở sẵn).
      - Xử lý 'bridges': gom từng cụm cầu theo chỉ số 0, 1, 2... -> 'a', 'b', 'c'...
        và tự động kích hoạt các ô cầu 'B' trong initial_active_bridges.
      - Xử lý 'switches': liên kết tọa độ công tắc [r, c, [[bridge_idx, mode], ...]]
        với đầy đủ 3 chế độ 'swap' (TOGGLE), 'on' (OPEN), 'off' (CLOSE).
      - Xử lý 'teleports': [tr, tc, r1, c1, r2, c2, active_flag] -> ánh xạ chính xác
        vị trí 2 khối đơn 1x1x1 và khối đơn được điều khiển đầu tiên (active_flag = 0 hoặc 1).
    """
    if not isinstance(stage_data, dict) or "grid" not in stage_data:
        raise ValueError("Dữ liệu màn chơi coolmath.json không hợp lệ (thiếu trường 'grid').")

    raw_grid_lines: List[str] = [str(row).rstrip("\r\n") for row in stage_data["grid"]]
    if not raw_grid_lines:
        raise ValueError("Lưới bản đồ 'grid' trong coolmath.json bị rỗng.")

    max_width = max(len(row) for row in raw_grid_lines)
    padded_grid_lines = [row.ljust(max_width, " ") for row in raw_grid_lines]

    grid: List[List[TileType]] = []
    symbols: List[List[str]] = []
    start_pos: Optional[Coordinates] = None
    end_pos: Optional[Coordinates] = None

    soft_sw_counter = 0
    heavy_sw_counter = 0
    initial_open_cells: set[Coordinates] = set()

    for r, row_str in enumerate(padded_grid_lines):
        tile_row: List[TileType] = []
        symbol_row: List[str] = []

        for c, ch in enumerate(row_str):
            tile = classify(ch)
            tile_row.append(tile)

            if ch == " ":
                symbol_row.append(".")
            elif ch == ".":
                symbol_row.append("F")
            elif ch == "S":
                if start_pos is not None:
                    raise ValueError(f"Map có nhiều hơn một điểm xuất phát S tại ({r}, {c})")
                start_pos = (r, c)
                symbol_row.append("S")
            elif ch == "H":
                if end_pos is not None:
                    raise ValueError(f"Map có nhiều hơn một điểm đích H tại ({r}, {c})")
                end_pos = (r, c)
                symbol_row.append("T")
            elif ch == "-":
                symbol_row.append("O")
            elif ch == "O":
                sym = _SOFT_SWITCH_SYMBOLS[soft_sw_counter % len(_SOFT_SWITCH_SYMBOLS)]
                soft_sw_counter += 1
                symbol_row.append(sym)
            elif ch == "X":
                sym = _HEAVY_SWITCH_SYMBOLS[heavy_sw_counter % len(_HEAVY_SWITCH_SYMBOLS)]
                heavy_sw_counter += 1
                symbol_row.append(sym)
            elif ch == "T":
                symbol_row.append("U")
            elif ch in ("b", "B"):
                if ch == "B":
                    initial_open_cells.add((r, c))
                symbol_row.append("a")

        grid.append(tile_row)
        symbols.append(symbol_row)

    if start_pos is None:
        raise ValueError("Map trong coolmath.json thiếu điểm bắt đầu 'S'")
    if end_pos is None:
        raise ValueError("Map trong coolmath.json thiếu điểm đích 'H'")

    # 1. Giải mã danh sách các cây cầu ("bridges")
    raw_bridges = stage_data.get("bridges", [])
    bridge_cells_by_id: Dict[str, Tuple[Coordinates, ...]] = {}
    bridge_initial_open_by_id: Dict[str, bool] = {}

    for b_idx, cell_list in enumerate(raw_bridges):
        b_id = _bridge_index_to_id(b_idx)
        coords: List[Coordinates] = []
        for coord_pair in cell_list:
            br, bc = int(coord_pair[0]), int(coord_pair[1])
            coords.append((br, bc))
            if 0 <= br < len(symbols) and 0 <= bc < len(symbols[br]):
                symbols[br][bc] = b_id
                if grid[br][bc] != TileType.BRIDGE:
                    grid[br][bc] = TileType.BRIDGE

        coords_tuple = tuple(coords)
        bridge_cells_by_id[b_id] = coords_tuple
        # Trong coolmath.json, cầu ký hiệu bằng 'B' (in hoa) là mở sẵn khi bắt đầu màn chơi
        is_open = bool(coords_tuple) and all(padded_grid_lines[br][bc] == "B" for br, bc in coords_tuple)
        bridge_initial_open_by_id[b_id] = is_open
        if is_open:
            initial_open_cells.update(coords_tuple)

    # 2. Giải mã danh sách công tắc ("switches")
    # Mỗi phần tử có dạng: [r, c, [[bridge_idx, mode_str], ...]]
    raw_switches = stage_data.get("switches", [])
    switches: Dict[Coordinates, List[BridgeAction]] = {}
    controlled_by_map: Dict[str, List[Coordinates]] = {b_id: [] for b_id in bridge_cells_by_id}

    for sw_entry in raw_switches:
        if len(sw_entry) < 3:
            raise ValueError(f"Định dạng switch trong coolmath.json không hợp lệ: {sw_entry}")
        sr, sc = int(sw_entry[0]), int(sw_entry[1])
        sw_pos: Coordinates = (sr, sc)
        action_specs = sw_entry[2]

        actions: List[BridgeAction] = list(switches.get(sw_pos, []))
        for spec in action_specs:
            if len(spec) < 2:
                raise ValueError(f"Định dạng tác động cầu không hợp lệ: {spec}")
            b_ref = spec[0]
            b_id = (
                str(b_ref).strip().lower()
                if isinstance(b_ref, str) and str(b_ref).strip().isalpha()
                else _bridge_index_to_id(int(b_ref))
            )
            mode = _parse_bridge_mode(str(spec[1]))

            target_cells = bridge_cells_by_id.get(b_id, ())
            for cell in target_cells:
                actions.append(BridgeAction(target_pos=cell, mode=mode, bridge_id=b_id))
            if b_id in controlled_by_map and sw_pos not in controlled_by_map[b_id]:
                controlled_by_map[b_id].append(sw_pos)

        switches[sw_pos] = actions

    # 3. Giải mã danh sách cổng phân tách / dịch chuyển ("teleports")
    # Mỗi phần tử có dạng: [tr, tc, r1, c1, r2, c2, active_flag]
    # Trong core/transition.py: khối đứng thẳng tại (tr, tc) sẽ tách thành State(r=pos1[0], c=pos1[1], split_pos=pos2, active_cube=0)
    # trong đó khối active_cube=0 nằm tại pos1. Do đó nếu active_flag == 1 trong coolmath.json,
    # ta đặt pos1 = (r2, c2) và pos2 = (r1, c1) để khối điều khiển đầu tiên khớp 100% với game gốc.
    raw_teleports = stage_data.get("teleports", [])
    splits: Dict[Coordinates, Tuple[Coordinates, Coordinates]] = {}
    for tp_entry in raw_teleports:
        if len(tp_entry) < 6:
            raise ValueError(f"Định dạng teleport trong coolmath.json không hợp lệ: {tp_entry}")
        tr, tc = int(tp_entry[0]), int(tp_entry[1])
        r1, c1 = int(tp_entry[2]), int(tp_entry[3])
        r2, c2 = int(tp_entry[4]), int(tp_entry[5])
        active_flag = int(tp_entry[6]) if len(tp_entry) >= 7 else 0

        pos_a: Coordinates = (r1, c1)
        pos_b: Coordinates = (r2, c2)
        if active_flag == 1:
            splits[(tr, tc)] = (pos_b, pos_a)
        else:
            splits[(tr, tc)] = (pos_a, pos_b)

    # 4. Xây dựng BridgeMetadata (tính độ ưu tiên dựa trên khoảng cách Manhattan từ điểm xuất phát)
    def _estimate_bridge_distance(b_id: str) -> Tuple[int, str]:
        controllers = controlled_by_map.get(b_id, [])
        if controllers:
            min_dist = min(abs(sr - start_pos[0]) + abs(sc - start_pos[1]) for sr, sc in controllers)
            return (min_dist, b_id)
        cells = bridge_cells_by_id.get(b_id, ())
        if cells:
            min_dist = min(abs(br - start_pos[0]) + abs(bc - start_pos[1]) for br, bc in cells)
            return (min_dist, b_id)
        return (0, b_id)

    ordered_bridge_ids = sorted(bridge_cells_by_id.keys(), key=_estimate_bridge_distance)
    bridge_metadata: Dict[str, BridgeMetadata] = {}
    for rank, b_id in enumerate(ordered_bridge_ids, start=1):
        bridge_metadata[b_id] = BridgeMetadata(
            bridge_id=b_id,
            cells=bridge_cells_by_id[b_id],
            priority=rank,
            initial_open=bridge_initial_open_by_id.get(b_id, False),
            controlled_by=tuple(controlled_by_map.get(b_id, [])),
            requires=(),
        )

    # 5. Xây dựng SwitchMetadata
    switch_metadata: Dict[Coordinates, SwitchMetadata] = {}
    for sw_pos, act_list in switches.items():
        sr, sc = sw_pos
        switch_metadata[sw_pos] = SwitchMetadata(
            switch_id=symbols[sr][sc],
            pos=sw_pos,
            switch_type=grid[sr][sc],
            actions=tuple(act_list),
        )

    stage_name = str(stage_data.get("name", ""))
    passcode = str(stage_data.get("passcode", ""))
    raw_metadata: Dict[str, Any] = {
        "name": stage_name,
        "passcode": passcode,
        "source_format": "coolmath_json",
        "bridge_count": len(bridge_metadata),
        "bridges": raw_bridges,
        "switches": raw_switches,
        "teleports": raw_teleports,
    }

    return Board(
        grid=grid,
        symbols=symbols,
        start_pos=start_pos,
        end_pos=end_pos,
        initial_active_bridges=frozenset(initial_open_cells),
        switches=switches,
        splits=splits,
        bridge_metadata=bridge_metadata,
        switch_metadata=switch_metadata,
        raw_metadata=raw_metadata,
        name=stage_name,
        passcode=passcode,
    )


def resolve_coolmath_path(filepath: Optional[str] = None) -> str:
    """
    Tìm đường dẫn thực tế của file coolmath.json.
    Ưu tiên đường dẫn truyền vào, sau đó tìm trong data/maps/coolmath.json,
    data/coolmath.json, thư mục gốc dự án hoặc thư mục Downloads của người dùng.
    """
    if filepath and os.path.isfile(filepath):
        return filepath

    core_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(core_dir, ".."))
    home_dir = os.path.expanduser("~")

    candidates: List[str] = []
    if filepath:
        candidates.extend(
            [
                filepath,
                os.path.join(project_root, filepath),
                os.path.join(project_root, "data", "maps", os.path.basename(filepath)),
                os.path.join(project_root, "data", os.path.basename(filepath)),
                os.path.join(home_dir, "Downloads", os.path.basename(filepath)),
            ]
        )

    candidates.extend(
        [
            os.path.join(project_root, "data", "maps", "coolmath.json"),
            os.path.join(project_root, "data", "coolmath.json"),
            os.path.join(project_root, "coolmath.json"),
            os.path.join("data", "maps", "coolmath.json"),
            os.path.join("data", "coolmath.json"),
            "coolmath.json",
            os.path.join(home_dir, "Downloads", "coolmath.json"),
        ]
    )

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Không tìm thấy file coolmath.json (đã thử tìm tại: {filepath or 'data/maps/coolmath.json'})."
    )


def _select_stage_from_list(
    stages_list: List[Dict[str, Any]],
    stage: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """
    Chọn 1 stage từ danh sách 33 màn trong coolmath.json dựa trên:
      - Số thứ tự màn (1..33, kiểu int hoặc chuỗi số '1', '01', ...)
      - Tên màn ('Stage 01', 'stage 1', ...)
      - Mã passcode ('780464', ...)
    Nếu stage=None, mặc định trả về màn đầu tiên (Stage 01).
    """
    if not stages_list:
        raise ValueError("Danh sách màn chơi trong file coolmath.json bị rỗng.")

    if stage is None:
        return stages_list[0]

    if isinstance(stage, int):
        if 1 <= stage <= len(stages_list):
            return stages_list[stage - 1]
        raise ValueError(f"Số thứ tự màn chơi {stage} nằm ngoài phạm vi (1..{len(stages_list)}).")

    query = str(stage).strip()
    if not query:
        return stages_list[0]

    # 1. Khớp theo tên chính xác hoặc passcode
    query_lower = query.lower()
    for item in stages_list:
        name = str(item.get("name", "")).strip()
        passcode = str(item.get("passcode", "")).strip()
        if name.lower() == query_lower or (passcode and passcode == query):
            return item

    # 2. Khớp theo số thứ tự màn (ví dụ: "1", "01", "Stage 1", "stage_05")
    base_query = os.path.basename(query)
    digits = "".join(ch for ch in base_query if ch.isdigit())
    if digits:
        stage_num = max(1, int(digits))
        if 1 <= stage_num <= len(stages_list):
            return stages_list[stage_num - 1]

    raise ValueError(f"Không tìm thấy màn chơi '{stage}' trong dữ liệu coolmath.json.")


def load_coolmath_levels(filepath: Optional[str] = None) -> List[Board]:
    """
    Đọc toàn bộ 33 màn chơi từ file coolmath.json và trả về danh sách các đối tượng Board.
    """
    resolved_path = resolve_coolmath_path(filepath)
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return [parse_coolmath_stage(data)]
    if isinstance(data, list):
        return [parse_coolmath_stage(stage_item) for stage_item in data]
    raise ValueError("Cấu trúc file coolmath.json không hợp lệ (cần list hoặc dict).")


def load_coolmath_dict(filepath: Optional[str] = None) -> Dict[str, Board]:
    """
    Đọc toàn bộ màn chơi từ coolmath.json và trả về dict {tên_màn: Board}
    (ví dụ: {'Stage 01': Board, ..., 'Stage 33': Board}).
    """
    boards = load_coolmath_levels(filepath)
    result: Dict[str, Board] = {}
    for idx, board in enumerate(boards, start=1):
        name = board.raw_metadata.get("name") or f"Stage {idx:02d}"
        result[str(name)] = board
    return result


def load_coolmath_stage(
    stage: Union[int, str] = 1,
    filepath: Optional[str] = None,
) -> Board:
    """
    Đọc một màn chơi cụ thể từ file coolmath.json theo:
      - Số thứ tự màn (1..33), ví dụ: load_coolmath_stage(1) hoặc load_coolmath_stage(8)
      - Tên màn, ví dụ: load_coolmath_stage("Stage 08")
      - Passcode màn chơi gốc, ví dụ: load_coolmath_stage("499707")
    """
    resolved_path = resolve_coolmath_path(filepath)
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return parse_coolmath_stage(data)
    if isinstance(data, list):
        selected = _select_stage_from_list(data, stage=stage)
        return parse_coolmath_stage(selected)
    raise ValueError("Cấu trúc file coolmath.json không hợp lệ.")


def parse_level(
    data: Union[Dict[str, Any], List[str], str],
    stage: Optional[Union[int, str]] = None,
) -> Board:
    """
    Chuyển dữ liệu JSON hoặc dictionary/grid của coolmath.json thành đối tượng Board.
    """
    if isinstance(data, dict):
        return parse_coolmath_stage(data)

    if isinstance(data, list):
        joined = "\n".join(str(x) for x in data).strip()
        if joined.startswith("{") or joined.startswith("["):
            parsed = json.loads(joined)
            if isinstance(parsed, dict):
                return parse_coolmath_stage(parsed)
            if isinstance(parsed, list):
                return parse_coolmath_stage(_select_stage_from_list(parsed, stage=stage))
        return parse_coolmath_stage({"grid": [str(x) for x in data]})

    if isinstance(data, str):
        parsed = json.loads(data)
        if isinstance(parsed, dict):
            return parse_coolmath_stage(parsed)
        if isinstance(parsed, list):
            return parse_coolmath_stage(_select_stage_from_list(parsed, stage=stage))

    raise ValueError("Dữ liệu đầu vào của parse_level không hợp lệ cho định dạng coolmath.json.")


def _split_filepath_and_stage(
    filepath: str,
    stage: Optional[Union[int, str]] = None,
) -> Tuple[Optional[str], Optional[Union[int, str]]]:
    """
    Phân tách đường dẫn file coolmath.json và chỉ số/tên màn chơi:
      - 'coolmath.json#Stage 05' hoặc 'coolmath.json#5'
      - 'coolmath.json:5'
      - Hoặc truyền trực tiếp tên màn / passcode như 'Stage 05', '780464'
    """
    if stage is not None:
        return filepath, stage

    if "#" in filepath:
        path_part, stage_part = filepath.rsplit("#", 1)
        if stage_part.strip():
            return path_part.strip(), stage_part.strip()

    if ".json:" in filepath.lower():
        idx = filepath.lower().rfind(".json:") + 5
        path_part = filepath[:idx]
        stage_part = filepath[idx + 1 :].strip()
        if stage_part:
            return path_part, stage_part

    if not filepath.lower().endswith(".json"):
        return None, filepath

    return filepath, None


def load_level(
    stage_or_filepath: Union[int, str] = 1,
    stage: Optional[Union[int, str]] = None,
) -> Board:
    """
    Hàm chính nạp màn chơi từ nguồn duy nhất coolmath.json:
      - load_level(1) hoặc load_level("Stage 05") hoặc load_level("780464")
      - load_level("data/maps/coolmath.json", stage=5)
      - load_level("coolmath.json:5") hoặc load_level("coolmath.json#Stage 05")
    """
    if isinstance(stage_or_filepath, int):
        return load_coolmath_stage(stage=stage_or_filepath)

    clean_path, parsed_stage = _split_filepath_and_stage(stage_or_filepath, stage)
    return load_coolmath_stage(
        stage=1 if parsed_stage is None else parsed_stage,
        filepath=clean_path,
    )


load_map = load_level
