from typing import List

from core.board import Board, TileType


def classify(ch: str) -> TileType:
    """Chuyển một ký hiệu trong file map thành loại tile."""
    if ch in ".-":
        return TileType.VOID
    if ch in "FS":
        return TileType.FLOOR
    if ch == "T":
        return TileType.GOAL
    if ch == "O":
        return TileType.FALLING
    if "A" <= ch <= "Z":
        return TileType.SOFT_SWITCH
    if "0" <= ch <= "9":
        return TileType.HEAVY_SWITCH
    if "a" <= ch <= "z":
        return TileType.BRIDGE
    raise ValueError(f"Ký tự lạ '{ch}' trong file map")


def parse_level(lines: List[str]) -> Board:
    """Chuyển danh sách dòng chữ thành Board. Báo lỗi nếu map sai định dạng."""
    rows = [line.strip() for line in lines if line.strip()]
    if not rows:
        raise ValueError("Map rỗng")

    width = len(rows[0])
    grid = []
    symbols = []
    start_pos = None
    goal_pos = None

    for r, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"Hàng {r} có độ dài {len(row)}, cần {width}")

        tile_row = []
        symbol_row = []
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

    return Board(grid=grid, symbols=symbols, start_pos=start_pos, goal_pos=goal_pos)


def load_level(filepath: str) -> Board:
    """Đọc một file map dạng text và trả về Board."""
    with open(filepath, "r", encoding="utf-8") as f:
        return parse_level(f.readlines())