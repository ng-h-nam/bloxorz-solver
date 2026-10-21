import os
from core.map_loader import load_level

def test_load_all_txt_maps():
    # Sửa từ "." thành đường dẫn thực tế chứa các file level*.txt
    maps_dir = os.path.join("data", "maps")
    assert os.path.exists(maps_dir), f"Thư mục bản đồ không tồn tại tại: {maps_dir}"
    
    txt_files = [f for f in os.listdir(maps_dir) if f.startswith("level") and f.endswith(".txt")]
    assert len(txt_files) > 0, "Không tìm thấy file map .txt nào!"
    
    for file_name in txt_files:
        file_path = os.path.join(maps_dir, file_name)
        board_obj = load_level(file_path)
        assert board_obj is not None