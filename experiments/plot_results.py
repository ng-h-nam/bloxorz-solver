import os
import matplotlib.pyplot as plt
import pandas as pd

"""
Script đọc file kết quả thực nghiệm từ data/logs/results.csv
và vẽ biểu đồ so sánh hiệu năng giữa các thuật toán tìm kiếm, sau đó lưu vào data/logs/plots.
"""


def main():
    # Xác định đường dẫn tới file log kết quả và thư mục lưu biểu đồ
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_file = os.path.join(base_dir, "data", "logs", "results.csv")

    if not os.path.exists(log_file):
        print(f"⚠️ Chưa tìm thấy file log kết quả tại {log_file}. Hãy chạy run_experiments.py trước!")
        return

    # Đọc dữ liệu CSV bằng Pandas
    df = pd.read_csv(log_file)

    # Lọc chỉ lấy các lần chạy thành công (success == True)
    df_success = df[df["success"] == True]

    if df_success.empty:
        print("⚠️ Không có dữ liệu thành công nào trong file log để vẽ biểu đồ!")
        return

    # Cấu hình giao diện biểu đồ
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("So sánh hiệu năng các thuật toán giải Bloxorz", fontsize=16, fontweight="bold")

    # 1. Biểu đồ so sánh Thời gian thực thi (Execution Time)
    ax1 = axes[0, 0]
    df_success.groupby("algorithm")["execution_time"].mean().plot(
        kind="bar", ax=ax1, color="skyblue", edgecolor="black"
    )
    ax1.set_title("Thời gian chạy trung bình (giây)")
    ax1.set_xlabel("Thuật toán")
    ax1.set_ylabel("Thời gian (s)")
    ax1.tick_params(axis="x", rotation=0)

    # 2. Biểu đồ so sánh Bộ nhớ đỉnh (Peak Memory)
    ax2 = axes[0, 1]
    df_success.groupby("algorithm")["peak_memory"].mean().plot(kind="bar", ax=ax2, color="salmon", edgecolor="black")
    ax2.set_title("Bộ nhớ đỉnh trung bình (MB)")
    ax2.set_xlabel("Thuật toán")
    ax2.set_ylabel("Memory (MB)")
    ax2.tick_params(axis="x", rotation=0)

    # 3. Biểu đồ so sánh Số nút mở rộng (Expanded Nodes)
    ax3 = axes[1, 0]
    df_success.groupby("algorithm")["expanded_nodes"].mean().plot(
        kind="bar", ax=ax3, color="lightgreen", edgecolor="black"
    )
    ax3.set_title("Số nút mở rộng trung bình (Nodes)")
    ax3.set_xlabel("Thuật toán")
    ax3.set_ylabel("Số nút")
    ax3.tick_params(axis="x", rotation=0)

    # 4. Biểu đồ so sánh Độ dài đường đi (Solution Length / Steps)
    ax4 = axes[1, 1]
    df_success.groupby("algorithm")["solution_length"].mean().plot(
        kind="bar", ax=ax4, color="orange", edgecolor="black"
    )
    ax4.set_title("Độ dài đường đi trung bình (Steps)")
    ax4.set_xlabel("Thuật toán")
    ax4.set_ylabel("Số bước")
    ax4.tick_params(axis="x", rotation=0)

    # Tự động căn chỉnh khoảng cách các biểu đồ
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    # Lưu file biểu đồ vào thư mục data/logs/plots
    output_img_dir = os.path.join(base_dir, "data", "logs", "plots")
    os.makedirs(output_img_dir, exist_ok=True)
    output_img_path = os.path.join(output_img_dir, "algorithm_comparison.png")

    plt.savefig(output_img_path, dpi=300)
    print(f"🎉 Đã vẽ biểu đồ thành công! File lưu tại: {output_img_path}")

    # Hiển thị biểu đồ
    plt.show()


if __name__ == "__main__":
    main()
