import json
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from block import Coordinates

class TileType(Enum):
    VOID = "."         
    FLOOR = "#"       
    GOAL = "G"         
    FRAGILE = "F"     
    BRIDGE = "="     
    SOFT_SWITCH = "O" 
    HEAVY_SWITCH = "X"
    SPLIT_SWITCH = "U"

    # nếu còn yếu tố in_game nào khác thì ae feedback nhé, t chơi gà quá ms tới màn 10 à :(


class Board:
    """
    Lưu trữ cấu trúc của màn chơi, bao gồm: layout, điểm xuất phát, điểm đích, vị trí cầu.
    """
    def __init__(
        self, 
        grid: List[List[TileType]],
        start_pos: Coordinates,
        end_pos: Coordinates,
        initial_active_bridges: Optional[Set[Coordinates]] = None, 

    ):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.initial_active_bridges = frozenset(initial_active_bridges or set())


    def in_board(self, r: int, c: int) -> bool:
        """Kiểm tra tọa độ (r, c) có nằm trong phạm vi lưới hay không."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_tile(self, r: int, c: int) -> TileType:
        """Trả về loại ô tại vị trí (r, c). Nếu không trong cuộc chơi, đã tính là rơi xuống the void."""
        if not self.in_board(r, c):
            return TileType.VOID
        return self.grid[r][c]

    @classmethod # khúc này t phải nhờ AI giúp r chứ tự code khê quá
    def from_str_grid(cls, lines: List[str]) -> "Board":
        """
        Khởi tạo Board nhanh từ danh sách chuỗi.
        Quy ước:
          '.' hoặc '0': VOID
          '#' hoặc '1': FLOOR
          'S': Start (FLOOR)
          'G': Goal
          'F': Fragile
          có thể chỉnh sửa phụ thuộc vào mấy file .json map sau.
        """

        grid: List[List[TileType]] = []
        start_pos = Optional[Coordinates] = None
        end_pos = Optional[Coordinates] = None

        for r, line in enumerate(lines):
            row_tiles: List[TileType] = []
            for c, char in enumerate(line.strip()):
                if char == "S":
                    start_pos = (r, c)
                    row_tiles.append(TileType.FLOOR)
                else:
                    if char == "G":
                        end_pos = (r, c)
                    try:
                        tile = TileType(char)
                    except ValueError:
                        tile = TileType.VOID
                    row_tiles.append(tile)
            grid.append(row_tiles)

        if start_pos is None or end_pos is None:
            raise ValueError("Bản đồ lỗi, phải tồn tại cả điểm bắt đầu và đích.")

        return cls(grid=grid, start_pos=start_pos, end_pos=end_pos)

    @classmethod
    def from_json(cls, filepath: str) -> "Board":
        """Nạp bản đồ từ file JSON theo chuẩn."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        board = cls.from_string_grid(data["layout"])
        if "initial_bridges" in data:
            board.initial_active_bridges = frozenset(
                tuple(coordinates) for coordinates in data["initial_bridges"]
            )
        return board

    def __str__(self) -> str:
        """In bản đồ ra màn hình console bằng chính các dấu trong TileType."""
        return "\n".join(
            "".join(tile.value for tile in row) for row in self.grid
        )

    

