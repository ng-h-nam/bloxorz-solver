from typing import List, Any, Dict, Optional, Tuple
import json
from core.board import (
    Board,
    TileType,
    BridgeAction,
    BridgeMetadata,
    BridgeMode,
)
from core.state import Coordinates


def classify(ch: str) -> TileType:
    """Chuyển một ký hiệu trong file map thành loại tile."""
    if ch in ".-":
        return TileType.VOID
    if ch in "FS":
        return TileType.FLOOR
    if ch == "T":
        return TileType.GOAL
    if ch == "O":
        return TileType.FRAGILE
    if ch == "U":
        return TileType.SPLIT_SWITCH
    if "A" <= ch <= "Z":
        return TileType.SOFT_SWITCH
    if "0" <= ch <= "9":
        return TileType.HEAVY_SWITCH
    if "a" <= ch <= "z":
        return TileType.BRIDGE
    raise ValueError(f"Ký tự lạ '{ch}' trong file map")


def _parse_coord_str(text: str) -> Coordinates:
    """Chuyển chuỗi "r, c" thành tuple."""
    parts = text.strip().split(",")
    if len(parts) != 2:
        raise ValueError(f"Tọa độ '{text}' không đúng định dạng 'r,c'")
    return (int(parts[0].strip()), int(parts[1].strip()))


def _parse_kv_tokens(tokens: List[str]) -> Dict[str, str]:
    """Chuyển danh sách ['id=a', 'priority=1'] thành dict {'id': 'a', 'priority': '1'}."""
    result: Dict[str, str] = {}
    for token in tokens:
        if "=" in token:
            k, v = token.split("=", 1)
            result[k.strip().lower()] = v.strip()
    return result


def _parse_metadata_section(
    meta_lines: List[str],
    grid: List[List[TileType]],
    symbols: List[List[str]],
    start_pos: Coordinates,
) -> Tuple[
    Dict[Coordinates, List[BridgeAction]],
    Dict[Coordinates, Tuple[Coordinates, Coordinates]],
    Dict[str, BridgeMetadata],
    Dict[str, Any],
]:
    """
    Giải mã phần Metadata
    để xử lý màn chơi có nhiều cầu (priority, initial state, dependencies, switches, splits).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    bridge_groups: Dict[str, List[Coordinates]] = {}
    switch_positions: Dict[str, List[Coordinates]] = {}
    split_positions: List[Coordinates] = []

    for r in range(rows):
        for c in range(cols):
            tile = grid[r][c]
            ch = symbols[r][c]
            if tile == TileType.BRIDGE:
                bridge_groups.setdefault(ch, []).append((r, c))
            elif tile in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH):
                switch_positions.setdefault(ch, []).append((r, c))
            elif tile == TileType.SPLIT_SWITCH:
                split_positions.append((r, c))
                switch_positions.setdefault(ch, []).append((r, c))

    # Nếu phần metadata được viết dưới dạng khối JSON
    joined_meta = "\n".join(meta_lines).strip()
    raw_meta: Dict[str, Any] = {}
    if joined_meta.startswith("{") and joined_meta.endswith("}"):
        raw_meta = json.loads(joined_meta)

    bridge_cfg: Dict[str, Dict[str, Any]] = {}
    switches: Dict[Coordinates, List[BridgeAction]] = {}
    splits: Dict[Coordinates, Tuple[Coordinates, Coordinates]] = {}

    # Nếu phần metadata được viết dưới dạng txt
    if not raw_meta:
        for line in meta_lines:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            parts = clean.split()
            directive = parts[0].upper()
            kv = _parse_kv_tokens(parts[1:])

            if directive == "BRIDGE":
                b_id = kv.get("id", "")
                if not b_id:
                    raise ValueError(f"Thiếu 'id=' trong dòng metadata: {line}")
                cells = (
                    [_parse_coord_str(x) for x in kv["cells"].split(";")]
                    if "cells" in kv
                    else bridge_groups.get(b_id, [])
                )
                priority = int(kv.get("priority", 1))
                initial_str = kv.get("initial", "closed").lower()
                initial_open = initial_str in ("open", "on", "true", "1")
                requires = tuple(x.strip() for x in kv.get("requires", "").split(",") if x.strip())
                bridge_cfg[b_id] = {
                    "cells": tuple(cells),
                    "priority": priority,
                    "initial_open": initial_open,
                    "requires": requires,
                }

            elif directive == "SWITCH":
                # Có thể xác định switch bằng pos=r,c hoặc id=A
                sw_coords: List[Coordinates] = []
                if "pos" in kv:
                    sw_coords = [_parse_coord_str(kv["pos"])]
                elif "id" in kv and kv["id"] in switch_positions:
                    sw_coords = switch_positions[kv["id"]]

                targets_str = kv.get("targets", "")
                actions: List[BridgeAction] = []
                for item in targets_str.split(","):
                    if not item.strip():
                        continue
                    if ":" in item:
                        target_spec, mode_str = item.split(":", 1)
                        mode = BridgeMode.from_str(mode_str)
                    else:
                        target_spec = item.strip()
                        mode = BridgeMode.TOGGLE

                    target_spec = target_spec.strip()
                    if target_spec in bridge_groups:
                        for cell in bridge_groups[target_spec]:
                            actions.append(BridgeAction(target_pos=cell, mode=mode, bridge_id=target_spec))
                    elif ";" in target_spec or target_spec[0].isdigit():
                        cell = _parse_coord_str(target_spec.replace(";", ","))
                        actions.append(BridgeAction(target_pos=cell, mode=mode))

                for sc in sw_coords:
                    switches[sc] = actions

            elif directive == "SPLIT":
                if "pos" in kv:
                    sp_coords = [_parse_coord_str(kv["pos"])]
                elif "id" in kv and kv["id"] in switch_positions:
                    sp_coords = switch_positions[kv["id"]]
                else:
                    sp_coords = split_positions

                t1 = _parse_coord_str(kv["target1"] if "target1" in kv else kv["pos1"])
                t2 = _parse_coord_str(kv["target2"] if "target2" in kv else kv["pos2"])
                for sc in sp_coords:
                    splits[sc] = (t1, t2)
    else:
        # Hỗ trợ khi khối sau '---' là JSON metadata
        for b_id, b_info in raw_meta.get("bridges", {}).items():
            cells = [tuple(c) for c in b_info["cells"]] if "cells" in b_info else bridge_groups.get(b_id, [])
            bridge_cfg[b_id] = {
                "cells": tuple(cells),
                "priority": int(b_info.get("priority", 1)),
                "initial_open": bool(b_info.get("initial_open", False)),
                "requires": tuple(b_info.get("requires", [])),
            }
        for sw_key, sw_info in raw_meta.get("switches", {}).items():
            sc = _parse_coord_str(sw_key) if "," in sw_key else switch_positions.get(sw_key, [(0, 0)])[0]
            actions = []
            for t in sw_info.get("targets", []):
                b_id = t["bridge"]
                mode = BridgeMode.from_str(t.get("mode", "toggle"))
                for cell in bridge_groups.get(b_id, []):
                    actions.append(BridgeAction(target_pos=cell, mode=mode, bridge_id=b_id))
            switches[sc] = actions
        for sp_key, sp_info in raw_meta.get("splits", {}).items():
            sc = _parse_coord_str(sp_key) if "," in sp_key else split_positions[0]
            splits[sc] = (tuple(sp_info[0]), tuple(sp_info[1]))

    # 3. Nếu một số công tắc trên bản đồ chưa được khai báo tường minh trong metadata,
    # tự động bổ sung liên kết mặc định ('A' -> 'a', '0' -> cầu thứ 0)
    sorted_bridge_ids = sorted(bridge_groups.keys())
    for ch, coords in switch_positions.items():
        for sc in coords:
            if sc in switches or grid[sc[0]][sc[1]] == TileType.SPLIT_SWITCH:
                continue
            target_id = None
            if ch.isalpha() and ch.lower() in bridge_groups:
                target_id = ch.lower()
            elif ch.isdigit():
                mapped_char = chr(ord("a") + int(ch))
                if mapped_char in bridge_groups:
                    target_id = mapped_char
                elif int(ch) < len(sorted_bridge_ids):
                    target_id = sorted_bridge_ids[int(ch)]
            if target_id:
                switches[sc] = [
                    BridgeAction(target_pos=pos, mode=BridgeMode.TOGGLE, bridge_id=target_id)
                    for pos in bridge_groups[target_id]
                ]

    controlled_by_map: Dict[str, List[Coordinates]] = {b_id: [] for b_id in bridge_groups}
    for sw_pos, act_list in switches.items():
        for act in act_list:
            for b_id, b_cells in bridge_groups.items():
                if act.target_pos in b_cells and sw_pos not in controlled_by_map[b_id]:
                    controlled_by_map[b_id].append(sw_pos)

    final_bridge_meta: Dict[str, BridgeMetadata] = {}
    for rank, b_id in enumerate(sorted_bridge_ids, start=1):
        cfg = bridge_cfg.get(b_id, {})
        cells = cfg.get("cells", tuple(bridge_groups[b_id]))
        priority = cfg.get("priority", rank)
        initial_open = cfg.get("initial_open", False)
        requires = cfg.get("requires", ())
        final_bridge_meta[b_id] = BridgeMetadata(
            bridge_id=b_id,
            cells=cells,
            priority=priority,
            initial_open=initial_open,
            controlled_by=tuple(controlled_by_map.get(b_id, [])),
            requires=requires,
        )

    raw_meta["bridge_count"] = len(final_bridge_meta)
    return switches, splits, final_bridge_meta, raw_meta


def parse_level(lines: List[str]) -> Board:
    """Chuyển danh sách dòng chữ thành Board (hỗ trợ cả phần metadata sau '---'). Báo lỗi nếu map sai định dạng."""
    map_lines: List[str] = []
    meta_lines: List[str] = []
    in_metadata = False

    for line in lines:
        stripped = line.strip()
        if not in_metadata and stripped == "---":
            in_metadata = True
            continue
        if in_metadata:
            meta_lines.append(line)
        elif stripped and not stripped.startswith("#"):
            map_lines.append(stripped)

    if not map_lines:
        raise ValueError("Map rỗng")

    width = len(map_lines[0])
    grid: List[List[TileType]] = []
    symbols: List[List[str]] = []
    start_pos: Optional[Coordinates] = None
    goal_pos: Optional[Coordinates] = None

    for r, row in enumerate(map_lines):
        if len(row) != width:
            raise ValueError(f"Hàng {r} có độ dài {len(row)}, cần {width}")

        tile_row: List[TileType] = []
        symbol_row: List[str] = []
        for c, ch in enumerate(row):
            tile_row.append(classify(ch))
            symbol_row.append(ch)

            if ch == "S":
                if start_pos is not None:
                    raise ValueError("Map có nhiều hơn một điểm S")
                start_pos = (r, c)
            elif ch == "T":
                if goal_pos is not None:
                    raise ValueError("Map có nhiều hơn một điểm T")
                goal_pos = (r, c)

        grid.append(tile_row)
        symbols.append(symbol_row)

    if start_pos is None:
        raise ValueError("Map thiếu điểm bắt đầu S")
    if goal_pos is None:
        raise ValueError("Map thiếu điểm đích T")

    has_meta = any(line.strip() and not line.strip().startswith("#") for line in meta_lines)
    if has_meta:
        switches, splits, bridge_metadata, raw_metadata = _parse_metadata_section(
            meta_lines=meta_lines,
            grid=grid,
            symbols=symbols,
            start_pos=start_pos,
        )
        return Board(
            grid=grid,
            symbols=symbols,
            start_pos=start_pos,
            goal_pos=goal_pos,
            switches=switches,
            splits=splits,
            bridge_metadata=bridge_metadata,
            raw_metadata=raw_metadata,
        )

    return Board(grid=grid, symbols=symbols, start_pos=start_pos, goal_pos=goal_pos)


def load_level(filepath: str) -> Board:
    """Đọc một file map dạng text và trả về Board."""
    with open(filepath, "r", encoding="utf-8") as f:
        return parse_level(f.readlines())
