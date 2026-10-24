import glob
import os
import re
from typing import List, Optional, Union

PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MAP_DIR: str = os.path.join(PROJECT_ROOT, "data", "maps")


def natural_key(path: str) -> List[Union[int, str]]:
    """Khóa sắp xếp tự nhiên: level2 đứng trước level10."""
    name = os.path.basename(path).lower()
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def discover_levels(map_dir: Optional[str] = None) -> List[str]:
    folder = map_dir or DEFAULT_MAP_DIR
    return sorted(glob.glob(os.path.join(folder, "*.txt")), key=natural_key)


def level_label(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]
