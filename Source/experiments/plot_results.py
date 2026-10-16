from datetime import datetime
import os
import matplotlib

# Headless backend cho phép lưu file ảnh mà không cần mở giao diện UI
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_experiment_results(log_csv_path=None, output_dir=None):
  """Đọc file log CSV kết quả thực nghiệm và vẽ 4 biểu đồ so sánh hiệu năng

  giữa các thuật toán (BFS, DFS, UCS, A*) trên từng bản đồ.
  """
  # Tự động định vị đường dẫn chuẩn dựa vào vị trí file script hiện tại
  current_dir = os.path.dirname(os.path.abspath(__file__))

  if log_csv_path is None:
    # Trỏ về Source/data/logs/results.csv
    log_csv_path = os.path.normpath(
        os.path.join(current_dir, "..", "data", "logs", "results.csv")
    )

  if output_dir is None:
    # Trỏ về Source/data/logs/plots
    output_dir = os.path.normpath(
        os.path.join(current_dir, "..", "data", "logs", "plots")
    )

  if not os.path.exists(log_csv_path):
    print(f"❌ File log không tồn tại tại: {log_csv_path}")
    print(
        "Vui lòng chạy script thực nghiệm trước để tạo dữ liệu log trong"
        " Source/data/logs/results.csv."
    )
    return

  # Đọc dữ liệu CSV
  try:
    df = pd.read_csv(log_csv_path)
  except Exception as e:
    print(f"❌ Lỗi khi đọc file CSV: {e}")
    return

  if df.empty:
    print("⚠️ File CSV chưa có dữ liệu thực nghiệm!")
    return

  # Tạo thư mục xuất biểu đồ nếu chưa có
  os.makedirs(output_dir, exist_ok=True)

  # Đặt phong cách giao diện biểu đồ
  sns.set_theme(style="whitegrid", palette="muted")
  fig, axes = plt.subplots(2, 2, figsize=(14, 10))
  fig.suptitle(
      "SO SÁNH HIỆU NĂNG CÁC THUẬT TOÁN TÌM KIẾM (BLOXORZ SOLVER)",
      fontsize=16,
      fontweight="bold",
      y=0.98,
  )

  # Danh sách thuật toán chuẩn để cố định thứ tự màu sắc
  algo_order = ["BFS", "DFS", "UCS", "A*"]
  palette = {
      "BFS": "#3498db",
      "DFS": "#e74c3c",
      "UCS": "#f39c12",
      "A*": "#2ecc71",
  }

  # 1. Biểu đồ Thời gian thực thi (Execution Time)
  sns.barplot(
      data=df,
      x="map_name",
      y="execution_time",
      hue="algorithm",
      hue_order=[a for a in algo_order if a in df["algorithm"].unique()],
      palette=palette,
      ax=axes[0, 0],
  )
  axes[0, 0].set_title(
      "1. Thời gian thực thi (Giây - Thấp hơn là tốt hơn)", fontweight="bold"
  )
  axes[0, 0].set_xlabel("Bản đồ (Map)")
  axes[0, 0].set_ylabel("Execution Time (s)")
  axes[0, 0].tick_params(axis="x", rotation=15)

  # 2. Biểu đồ Bộ nhớ đỉnh (Peak Memory)
  sns.barplot(
      data=df,
      x="map_name",
      y="peak_memory",
      hue="algorithm",
      hue_order=[a for a in algo_order if a in df["algorithm"].unique()],
      palette=palette,
      ax=axes[0, 1],
  )
  axes[0, 1].set_title(
      "2. Dung lượng bộ nhớ đỉnh (MB - Thấp hơn là tốt hơn)", fontweight="bold"
  )
  axes[0, 1].set_xlabel("Bản đồ (Map)")
  axes[0, 1].set_ylabel("Peak Memory (MB)")
  axes[0, 1].tick_params(axis="x", rotation=15)

  # 3. Biểu đồ Số nút đã mở rộng (Expanded Nodes)
  sns.barplot(
      data=df,
      x="map_name",
      y="expanded_nodes",
      hue="algorithm",
      hue_order=[a for a in algo_order if a in df["algorithm"].unique()],
      palette=palette,
      ax=axes[1, 0],
  )
  axes[1, 0].set_title(
      "3. Số lượng trạng thái đã mở rộng (Nút - Thấp hơn là tốt hơn)",
      fontweight="bold",
  )
  axes[1, 0].set_xlabel("Bản đồ (Map)")
  axes[1, 0].set_ylabel("Expanded Nodes Count")
  axes[1, 0].tick_params(axis="x", rotation=15)

  # 4. Biểu đồ Độ dài lời giải (Solution Length)
  sns.barplot(
      data=df,
      x="map_name",
      y="solution_length",
      hue="algorithm",
      hue_order=[a for a in algo_order if a in df["algorithm"].unique()],
      palette=palette,
      ax=axes[1, 1],
  )
  axes[1, 1].set_title(
      "4. Độ dài chuỗi bước đi lời giải (Số nước đi - Ngắn hơn là tối ưu)",
      fontweight="bold",
  )
  axes[1, 1].set_xlabel("Bản đồ (Map)")
  axes[1, 1].set_ylabel("Steps Count")
  axes[1, 1].tick_params(axis="x", rotation=15)

  plt.tight_layout(rect=[0, 0, 1, 0.96])

  # Lưu biểu đồ tổng hợp vào đúng thư mục data/logs/plots
  output_chart_path = os.path.join(output_dir, "algorithm_comparison.png")
  plt.savefig(output_chart_path, dpi=300, bbox_inches="tight")
  plt.close()

  print(f"✅ Đã tạo biểu đồ so sánh thành công tại: {output_chart_path}")


if __name__ == "__main__":
  plot_experiment_results()