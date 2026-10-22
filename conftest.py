"""
File cấu hình Pytest.
File này được pytest tự động tải ở thư mục gốc để cấu hình các plugin test, fixture,
và phân giải đường dẫn python cho dự án Bloxorz Solver.
"""

import os
import sys

# Thêm thư mục gốc của project vào sys.path để pytest có thể nhận diện các module core, algorithms, gui,...
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)