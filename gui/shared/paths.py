"""Vị trí gốc của dự án, tính một lần cho mọi module (di chuyển file không làm vỡ đường dẫn tài nguyên)."""

from pathlib import Path

PROJECT_ROOT: str = str(Path(__file__).resolve().parents[2])  # gui/shared/paths.py -> thư mục gốc repo
