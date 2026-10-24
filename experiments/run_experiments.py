import os
import sys
import csv
from datetime import datetime

# python -m experiments.run_experiments

"""
Script tự động chạy thực nghiệm (Batch Testing) cho dự án Bloxorz Solver.
Tự động duyệt qua tất cả các file bản đồ trong thư mục data/maps/,
chạy các thuật toán tìm kiếm sẵn có (BFS, DFS), đo lường chỉ số và ghi log vào CSV.
"""


def run_single_experiment(solver_cls, board_map, map_name, log_file_path):
    """
    Chạy 1 thuật toán trên 1 bản đồ cụ thể, đo lường chỉ số và ghi log.
    """
    solver_name = solver_cls.__name__  # Lấy tên của class Solver chính xác
    try:
        # Khởi tạo instance của solver bằng cách truyền board_map vào
        solver_instance = solver_cls(board_map)

        # Gọi hàm solve() không tham số để nhận về đối tượng SolveResult
        result = solver_instance.solve()

        success = result.is_solved
        expanded_nodes = result.nodes_explored
        execution_time = result.execution_time
        peak_memory_mb = result.peak_memory / (1024 * 1024) if hasattr(result, "peak_memory") else 0.0
        solution_length = result.cost if success else 0

    except Exception as e:
        expanded_nodes = 0
        success = False
        execution_time = 0.0
        peak_memory_mb = 0.0
        solution_length = 0
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
            ]
        )

    status_str = "✅ Success" if success else "❌ Failed"
    print(
        f"  ├─ [{solver_name:<10}] {status_str} | Time: {execution_time:.4f}s | Mem: {peak_memory_mb:.2f}MB | Nodes: {expanded_nodes} | Steps: {solution_length}"
    )


def main():
    # Xác định đường dẫn tương đối từ thư mục root của Source
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    maps_dir = os.path.join(base_dir, "data", "maps")
    log_file = os.path.join(base_dir, "data", "logs", "results.csv")

    print("=" * 70)
    print("🚀 BẮT ĐẦU CHẠY THỰC NGHIỆM TỰ ĐỘNG (BLOXORZ SOLVER BATCH TEST)")
    print(f"📂 Thư mục Maps: {maps_dir}")
    print(f"📊 File Log đầu ra: {log_file}")
    print("=" * 70)

    if not os.path.exists(maps_dir):
        print(f"⚠️ Chưa tìm thấy thư mục {maps_dir}. Hãy tạo các file map trước khi chạy!")
        sys.exit(1)

    # Lấy danh sách file map trong thư mục data/maps/
    map_files = sorted([f for f in os.listdir(maps_dir) if f.endswith((".json", ".txt"))])

    if not map_files:
        print("⚠️ Không tìm thấy file map (.json / .txt) nào trong thư mục data/maps/!")
        sys.exit(0)

    # Chỉ định rõ ràng danh sách class solver muốn test (chỉ BFS và DFS)
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
            # Nếu file map là coolmath.json tổng hợp nhiều màn, có thể load theo danh sách hoặc từng stage
            if map_file == "coolmath.json":
                from core.map_loader import load_coolmath_levels

                boards_dict = load_coolmath_levels(map_path)
                board_maps = boards_dict
            else:
                board_map = load_level(map_path)
                board_maps = [board_map]
        except Exception as e:
            print(f"  ❌ Không thể nạp bản đồ {map_file}: {e}")
            continue

        # Xử lý trường hợp nạp danh sách màn chơi từ coolmath.json
        items_to_run = board_maps if isinstance(board_maps, list) else list(board_maps)

        for idx, board_map in enumerate(items_to_run):
            current_map_name = f"{map_file}_stage_{idx + 1}" if map_file == "coolmath.json" else map_file
            for SolverClass in solvers_cls:
                try:
                    # Truyền trực tiếp SolverClass vào hàm thực nghiệm
                    run_single_experiment(SolverClass, board_map, current_map_name, log_file)
                except Exception as e:
                    print(f"  ❌ Lỗi khi chạy thực nghiệm: {e}")

    print("\n" + "=" * 70)
    print(f"THỰC NGHIỆM HOÀN TẤT! Kết quả đã được lưu vào {log_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
