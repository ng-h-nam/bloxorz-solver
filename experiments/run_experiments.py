import csv
import os
import sys
import time
import tracemalloc
from datetime import datetime

"""
Script tự động chạy thực nghiệm (Batch Testing) cho dự án Bloxorz Solver.
Tự động duyệt qua tất cả các file bản đồ trong thư mục data/maps/,
chạy 4 thuật toán tìm kiếm (BFS, DFS, UCS, A*), đo lường chỉ số và ghi log vào CSV.
"""

# Import giả định các Solvers từ gói algorithms nếu chạy trong dự án


def run_single_experiment(solver, board_map, map_name, log_file_path):
    """
    Chạy 1 thuật toán trên 1 bản đồ cụ thể, đo lường chỉ số và ghi log.
    """
    tracemalloc.start()
    start_time = time.perf_counter()

    try:
        # Gọi hàm solve của thuật toán (trả về path, expanded_nodes, success)
        path, expanded_nodes, success = solver.solve(board_map)
    except Exception as e:
        path = None
        expanded_nodes = 0
        success = False
        print(f"  ❌ Lỗi khi chạy {solver.name} trên {map_name}: {e}")

    execution_time = time.perf_counter() - start_time
    _, peak_mem_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_memory_mb = peak_mem_bytes / (1024 * 1024)
    solution_length = len(path) if (path and success) else 0
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
                getattr(solver, "name", solver.__class__.__name__),
                success,
                f"{execution_time:.6f}",
                f"{peak_memory_mb:.4f}",
                expanded_nodes,
                solution_length,
            ]
        )

    status_str = "✅ Success" if success else "❌ Failed"
    print(
        f"  ├─ [{getattr(solver, 'name', solver.__class__.__name__):<4}] {status_str} | Time: {execution_time:.4f}s | Mem: {peak_memory_mb:.2f}MB | Nodes: {expanded_nodes} | Steps: {solution_length}"
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

    # Thử import các Solvers từ package algorithms
    try:
        from algorithms.bfs import BFSSolver
        from algorithms.dfs import DFSSolver

        # from algorithms.ucs import UCSSolver
        # from algorithms.astar import AStarSolver
        from core.map_loader import load_map

        solvers_cls = [BFSSolver, DFSSolver, UCSSolver, AStarSolver]
    except ImportError:
        print("💡 Chú ý: Chưa tìm thấy đầy đủ các class Solver thực tế trong package algorithms.")
        print("   Script được cấu trúc sẵn để chạy khi TV1-TV4 hoàn thiện mã nguồn.")
        return

    for map_file in map_files:
        map_path = os.path.join(maps_dir, map_file)
        print(f"\n🎮 Thử nghiệm trên Map: {map_file}")

        try:
            board_map = load_map(map_path)
        except Exception as e:
            print(f"  ❌ Không thể nạp bản đồ {map_file}: {e}")
            continue

        for SolverClass in solvers_cls:
            solver = SolverClass()
            run_single_experiment(solver, board_map, map_file, log_file)

    print("\n" + "=" * 70)
    print(f"🎉 THỰC NGHIỆM HOÀN TẤT! Kết quả đã được lưu vào {log_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
