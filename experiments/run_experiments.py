import csv
from datetime import datetime
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# python -m experiments.run_experiments

"""
Script tự động chạy thực nghiệm (Batch Testing) cho dự án Bloxorz Solver.
Tự động duyệt qua tất cả các file bản đồ trong thư mục data/maps/,
chạy các thuật toán tìm kiếm sẵn có (BFS, DFS, UCS), đo lường chỉ số và ghi log vào CSV.
Kiểm soát giới hạn mở rộng nút (node_limit) và giới hạn thời gian (time_limit)
để đảm bảo không treo hệ thống khi duyệt các không gian trạng thái lớn.
"""

DEFAULT_NODE_LIMIT: int = 25000
DEFAULT_TIME_LIMIT: float = 5.0


def run_single_experiment(
    solver_cls,
    board_map,
    map_name: str,
    log_file_path: str,
    node_limit: int = DEFAULT_NODE_LIMIT,
    time_limit: float = DEFAULT_TIME_LIMIT,
) -> None:
    """
    Chạy 1 thuật toán trên 1 bản đồ cụ thể, đo lường chỉ số và ghi log.
    """
    solver_name = solver_cls.__name__  # Lấy tên của class Solver chính xác
    try:
        # Khởi tạo instance của solver với node_limit và time_limit
        solver_instance = solver_cls(
            board_map,
            node_limit=node_limit,
            time_limit=time_limit,
        )

        # Gọi hàm solve() để nhận về đối tượng SolveResult
        result = solver_instance.solve()

        success = result.is_solved
        expanded_nodes = result.nodes_explored
        execution_time = result.execution_time
        peak_memory_mb = (
            result.peak_memory / (1024 * 1024)
            if hasattr(result, "peak_memory")
            else 0.0
        )
        solution_length = result.cost if success else 0
        status = result.status

    except Exception as e:
        expanded_nodes = 0
        success = False
        execution_time = 0.0
        peak_memory_mb = 0.0
        solution_length = 0
        status = f"ERROR: {e}"
        print(f"  ❌ Lỗi khi chạy {solver_name} trên {map_name}: {e}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ghi nối kết quả vào CSV
    file_exists = os.path.isfile(log_file_path)
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    with open(log_file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                [
                    "timestamp",
                    "map_name",
                    "algorithm",
                    "success",
                    "execution_time",
                    "peak_memory",
                    "expanded_nodes",
                    "solution_length",
                    "status",
                ]
            )
        writer.writerow(
            [
                timestamp,
                map_name,
                solver_name,
                success,
                f"{execution_time:.6f}",
                f"{peak_memory_mb:.4f}",
                expanded_nodes,
                solution_length,
                status,
            ]
        )

    status_str = "✅ Success" if success else f"❌ {status}"
    print(
        f"  ├─ [{solver_name:<10}] {status_str:<26} | Time: {execution_time:.4f}s | "
        f"Mem: {peak_memory_mb:.2f}MB | Nodes: {expanded_nodes:5d} | Steps: {solution_length:3d}"
    )


def main() -> None:
    # Xác định đường dẫn tương đối từ thư mục root của Source
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    maps_dir = os.path.join(base_dir, "data", "maps")
    log_file = os.path.join(base_dir, "data", "logs", "results.csv")

    print("=" * 80)
    print("🚀 BẮT ĐẦU CHẠY THỰC NGHIỆM TỰ ĐỘNG (BLOXORZ SOLVER BATCH TEST)")
    print(f"📂 Thư mục Maps: {maps_dir}")
    print(f"📊 File Log đầu ra: {log_file}")
    print(f"⚙️ Giới hạn: node_limit={DEFAULT_NODE_LIMIT}, time_limit={DEFAULT_TIME_LIMIT}s")
    print("=" * 80)

    if not os.path.exists(maps_dir):
        print(f"⚠️ Chưa tìm thấy thư mục {maps_dir}. Hãy tạo các file map trước khi chạy!")
        sys.exit(1)

    # Ưu tiên lấy 33 stage files chuẩn stage_01.txt -> stage_33.txt
    stage_files = sorted(
        [f for f in os.listdir(maps_dir) if f.startswith("stage_") and f.endswith(".txt")]
    )
    if stage_files:
        map_files = stage_files
    else:
        map_files = sorted([f for f in os.listdir(maps_dir) if f.endswith((".json", ".txt"))])

    if not map_files:
        print("⚠️ Không tìm thấy file map (.json / .txt) nào trong thư mục data/maps/!")
        sys.exit(0)

    # Nạp danh sách solver muốn test (BFS, DFS, UCS)
    solvers_cls = []

    try:
        from algorithms.bfs import BFSSolver

        solvers_cls.append(BFSSolver)
    except ImportError:
        print("💡 Chú ý: Không tìm thấy module BFSSolver trong package algorithms.")

    try:
        from algorithms.dfs import DFSSolver

        solvers_cls.append(DFSSolver)
    except ImportError:
        print("💡 Chú ý: Không tìm thấy module DFSSolver trong package algorithms.")

    try:
        from algorithms.ucs import UCSSolver

        solvers_cls.append(UCSSolver)
    except ImportError:
        print("💡 Chú ý: Không tìm thấy module UCSSolver trong package algorithms.")

    try:
        from core.map_loader import load_level
    except ImportError as e:
        print(f"❌ Không thể import load_level từ core.map_loader: {e}")
        return

    if not solvers_cls:
        print("❌ Không có thuật toán nào được nạp thành công để chạy thực nghiệm.")
        return

    for map_file in map_files:
        map_path = os.path.join(maps_dir, map_file)
        print(f"\n🎮 Thử nghiệm trên Map: {map_file}")

        try:
            if map_file == "coolmath.json":
                from core.map_loader import load_coolmath_levels

                board_maps = load_coolmath_levels(map_path)
            else:
                board_map = load_level(map_path)
                board_maps = [board_map]
        except Exception as e:
            print(f"  ❌ Không thể nạp bản đồ {map_file}: {e}")
            continue

        items_to_run = board_maps if isinstance(board_maps, list) else list(board_maps)

        for idx, board_map in enumerate(items_to_run):
            current_map_name = (
                f"{map_file}_stage_{idx + 1}" if map_file == "coolmath.json" else map_file
            )
            for SolverClass in solvers_cls:
                try:
                    run_single_experiment(
                        SolverClass,
                        board_map,
                        current_map_name,
                        log_file,
                        node_limit=DEFAULT_NODE_LIMIT,
                        time_limit=DEFAULT_TIME_LIMIT,
                    )
                except Exception as e:
                    print(f"  ❌ Lỗi khi chạy thực nghiệm: {e}")

    print("\n" + "=" * 80)
    print(f"THỰC NGHIỆM HOÀN TẤT! Kết quả đã được lưu vào {log_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
