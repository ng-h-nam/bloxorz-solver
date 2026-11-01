"""
Script đọc kết quả thực nghiệm từ CSV và tự động xuất ra:
- Thư mục lưu mặc định: docs/Resources/
  1. Các file biểu đồ (PDF & PNG) thang log cho báo cáo.
  2. Các file bảng mã nguồn LaTeX (.tex).
"""

import argparse
import csv
import math
import os
import json
import sys
from pathlib import Path

import matplotlib

# Chuyển Matplotlib sang chế độ không cần GUI
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Cấu hình phông chữ và định dạng xuất PDF
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

COLORS = {
    "bfs": "#4C78A8",
    "dfs": "#E45756",
    "ids": "#F58518",
    "ucs": "#54A24B",
    "astar": "#B279A2",
    "A*": "#B279A2",
    "AStar": "#B279A2",
}

GROUP_ORDER = ("basic", "fragile", "switch", "combined")
GROUP_NAMES = {
    "basic": "Cơ bản",
    "fragile": "Ô giòn",
    "switch": "Công tắc",
    "combined": "Kết hợp",
}


def tex_escape(value):
    s = str(value)
    for a, b in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        s = s.replace(a, b)
    return s


def solver_label(name):
    n = str(name).lower()
    if "astar" in n or "a*" in n:
        return "A*"
    if "bfs" in n:
        return "BFS"
    if "dfs" in n:
        return "DFS"
    if "ids" in n:
        return "IDS"
    if "ucs" in n:
        return "UCS"
    return str(name).upper()


def solver_tex(name):
    label = solver_label(name)
    return r"A$^*$" if label == "A*" else tex_escape(label)


def group_label(group_key):
    for k, v in GROUP_NAMES.items():
        if k in str(group_key).lower():
            return v
    return str(group_key)


def categorize_group(map_name):
    name = str(map_name).lower()
    if "basic" in name or "06_" in name or "07_" in name or "08_" in name:
        return "basic"
    if "fragile" in name or "glass" in name or any(f"{i:02d}_" in name for i in range(9, 14)):
        return "fragile"
    if "split" in name or "switch" in name or "bridge" in name or any(f"{i:02d}_" in name for i in range(14, 22)):
        return "switch"
    if "combined" in name or any(f"{i:02d}_" in name for i in range(22, 28)):
        return "combined"
    return "basic"


def parse_bool(raw):
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes", "success", "ok"):
        return True
    if s in ("false", "0", "no", "failed", "error"):
        return False
    return None


def load_coolmath_metadata(json_path):
    """Đọc thông tin chi tiết từng màn từ file coolmath.json"""
    metadata = {}
    if not os.path.exists(json_path):
        return metadata

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    for idx, stage in enumerate(data):
        stage_name = stage.get("name", f"Stage {idx+1:02d}")
        grid = stage.get("grid", [])
        rows = len(grid)
        cols = max(len(r) for r in grid) if grid else 0
        
        # Đếm số ô fragile (ký tự '-' hoặc 'B')
        fragile_count = sum(r.count("-") + r.count("B") for r in grid)
        
        # Đếm số lượng bridges và switches
        bridges_count = sum(len(v) for v in stage.get("bridges", [])) if isinstance(stage.get("bridges"), list) else 0
        switches_count = len(stage.get("switches", []))

        metadata[stage_name] = {
            "rows": rows,
            "cols": cols,
            "size": f"{rows}x{cols}",
            "fragile": fragile_count,
            "bridge": bridges_count,
            "switch": switches_count,
            "optimal_moves": stage.get("optimal_moves", math.nan)
        }
    return metadata


def read_results(csv_path):
    if not os.path.exists(csv_path):
        print(f"⚠️ Không tìm thấy file CSV tại {csv_path}")
        return []

    # Load metadata từ coolmath.json
    base_dir = Path(__file__).resolve().parent.parent
    json_path = base_dir / "data" / "maps" / "coolmath.json"
    meta = load_coolmath_metadata(json_path)

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r["level"] = r.get("map_name") or r.get("level") or "unknown"
        r["solver"] = r.get("algorithm") or r.get("solver") or "unknown"
        r["found"] = parse_bool(r.get("success")) if "success" in r else parse_bool(r.get("found"))
        r["group"] = r.get("group") or categorize_group(r["level"])

        # Lấy chỉ số số học
        r["expanded"] = float(r.get("expanded_nodes") or r.get("expanded") or math.nan)
        
        raw_time = float(r.get("execution_time") or r.get("time_s") or math.nan)
        if "time_ms" in r:
            raw_time = float(r["time_ms"]) / 1000.0
        r["time_s"] = raw_time

        raw_mem = float(r.get("peak_memory") or r.get("peak_mem_kb") or math.nan)
        if "peak_memory" in r and raw_mem < 100:
            raw_mem = raw_mem * 1024.0
        r["peak_mem_kb"] = raw_mem

        r["length"] = float(r.get("solution_length") or r.get("length") or math.nan)
        r["cost"] = float(r.get("cost") or r["length"])

        # Nếu không có optimal_moves trong CSV, bổ sung từ BFS solution length hoặc json metadata
        opt = r.get("optimal_moves")
        if opt is None or str(opt).strip() in ("", "nan"):
            if r["solver"].upper() == "BFS" and r["found"]:
                opt = r["length"]
            elif r["level"] in meta:
                opt = meta[r["level"]]["optimal_moves"]
            else:
                opt = math.nan
        r["optimal_moves"] = float(opt)

        # Bổ sung thông tin chi tiết cho bảng testset
        if r["level"] in meta:
            r["size"] = meta[r["level"]]["size"]
            r["fragile_cells"] = meta[r["level"]]["fragile"]
            r["bridge_cells"] = meta[r["level"]]["bridge"]
            r["switches_count"] = meta[r["level"]]["switch"]
        else:
            r["size"] = "---"
            r["fragile_cells"] = 0
            r["bridge_cells"] = 0
            r["switches_count"] = 0

    return rows


def is_solved(row):
    return row is not None and row.get("found") is True


def mean_on_solved(rows, group, solver, key, scale=1.0):
    vals = []
    solved_count = 0
    total_maps = len(set(r["level"] for r in rows if categorize_group(r["level"]) == group))

    for r in rows:
        if categorize_group(r["level"]) == group and solver_label(r["solver"]) == solver_label(solver):
            if is_solved(r):
                solved_count += 1
                v = r.get(key, math.nan)
                if isinstance(v, (int, float)) and not math.isnan(v):
                    vals.append(v * scale)

    mean_val = sum(vals) / len(vals) if vals else math.nan
    return mean_val, solved_count, max(total_maps, 1)


# ==============================================================================
# HÀM XUẤT LATEX (.TEX) VÀO DOCS/RESOURCES
# ==============================================================================

def write_testset_tex(rows, path):
    lines = [
        "% Sinh tự động bởi plot_results.py",
        r"\begin{tabular}{llrrrlr}",
        r"\hline",
        r"Màn & Nhóm & Cỡ & Fragile & Bridge & Switch & Tối ưu \\",
        r"\hline",
    ]
    seen = set()
    for r in rows:
        lv = r["level"]
        if lv in seen:
            continue
        seen.add(lv)

        grp = group_label(categorize_group(lv))
        size = r.get("size", "---")
        fragile = r.get("fragile_cells", 0)
        bridge = r.get("bridge_cells", 0)
        switch = r.get("switches_count", 0)
        opt = f"{int(r['optimal_moves'])}" if not math.isnan(r["optimal_moves"]) else "---"

        lines.append(
            f"{tex_escape(lv)} & {tex_escape(grp)} & {size} & {fragile} & {bridge} & {switch} & {opt} \\\\"
        )

    lines += [r"\hline", r"\end{tabular}", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_tier_tex(rows, solvers, groups, path):
    lines = [
        "% Sinh tự động bởi plot_results.py",
        r"\begin{tabular}{llrlllll}",
        r"\hline",
        r"Nhóm & Solver & Giải & Node & Thời gian (ms) & Bộ nhớ (KB) & Độ dài & Cost \\",
        r"\hline",
    ]
    for gi, g in enumerate(groups):
        if gi > 0:
            lines.append(r"\hline")
        for s in solvers:
            m_exp, solved, total = mean_on_solved(rows, g, s, "expanded")
            m_time, _, _ = mean_on_solved(rows, g, s, "time_s", scale=1000.0)
            m_mem, _, _ = mean_on_solved(rows, g, s, "peak_mem_kb")
            m_len, _, _ = mean_on_solved(rows, g, s, "length")
            m_cost, _, _ = mean_on_solved(rows, g, s, "cost")

            f_exp = f"{m_exp:.1f}" if not math.isnan(m_exp) else "---"
            f_time = f"{m_time:.2f}" if not math.isnan(m_time) else "---"
            f_mem = f"{m_mem:.1f}" if not math.isnan(m_mem) else "---"
            f_len = f"{m_len:.2f}" if not math.isnan(m_len) else "---"
            f_cost = f"{m_cost:.2f}" if not math.isnan(m_cost) else "---"

            lines.append(
                f"{tex_escape(group_label(g))} & {solver_tex(s)} & {solved}/{total} & "
                f"{f_exp} & {f_time} & {f_mem} & {f_len} & {f_cost} \\\\"
            )

    lines += [r"\hline", r"\end{tabular}", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_detail_tex(rows, solvers, levels, path):
    chunks = [
        "% Sinh tự động bởi plot_results.py",
    ]
    
    # Chuẩn hóa danh sách các thuật toán xuất hiện thực tế (BFS, DFS, UCS, A*)
    active_solvers = []
    for s in ["BFS", "DFS", "UCS", "A*"]:
        if any(solver_label(r["solver"]) == s for r in rows):
            active_solvers.append(s)
    if not active_solvers:
        active_solvers = list(dict.fromkeys(solver_label(r["solver"]) for r in rows))

    header = " & ".join(["Màn", "Nhóm"] + [solver_tex(s) for s in active_solvers]) + r" \\"
    colspec = "ll" + "c" * len(active_solvers)

    metrics_list = [
        ("Số node mở rộng", "expanded", 1.0, 0),
        ("Thời gian tìm kiếm (ms)", "time_s", 1000.0, 2),
        ("Bộ nhớ đỉnh (KB)", "peak_mem_kb", 1.0, 1),
        ("Độ dài lời giải (số nước)", "length", 1.0, 0),
        ("Cost", "cost", 1.0, 2),
    ]

    for title, key, scale, nd in metrics_list:
        chunks += [
            r"\Needspace*{6\baselineskip}",  # Lệnh đúng chuẩn của package needspace
            r"\begin{table}[H]",
            r"\centering",
            r"\small",
            r"{\bfseries " + tex_escape(title) + r"}\\[0.5em]",
            r"\begin{tabular}{" + colspec + "}",
            r"\hline",
            header,
            r"\hline",
        ]
        for lv in levels:
            grp = group_label(categorize_group(lv))
            cells = []
            for s in active_solvers:
                matched = [
                    r for r in rows 
                    if r["level"] == lv and solver_label(r["solver"]) == s
                ]
                if matched and is_solved(matched[0]):
                    val = matched[0].get(key, math.nan) * scale
                    cells.append(f"{val:.{nd}f}" if not math.isnan(val) else "---")
                else:
                    cells.append("---")
            chunks.append(f"{tex_escape(lv)} & {tex_escape(grp)} & " + " & ".join(cells) + r" \\")
        chunks += [
            r"\hline",
            r"\end{tabular}",
            r"\end{table}",
            r"\vspace{1em}",
            ""
        ]

    Path(path).write_text("\n".join(chunks), encoding="utf-8")


# ==============================================================================
# HÀM VẼ VÀ TỰ ĐỘNG XUẤT HÌNH ẢNH (PDF & PNG)
# ==============================================================================

def draw_group_bars(out_dir, base_filename, rows, solvers, groups, key, scale, ylabel, use_log):
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    width = 0.8 / max(len(solvers), 1)

    for i, s in enumerate(solvers):
        vals = []
        for g in groups:
            mean_val, _, _ = mean_on_solved(rows, g, s, key, scale)
            if math.isnan(mean_val) or (use_log and mean_val <= 0):
                vals.append(math.nan)
            else:
                vals.append(mean_val)

        xs = [j + (i - (len(solvers) - 1) / 2) * width for j in range(len(groups))]
        ax.bar(xs, vals, width, label=solver_label(s), color=COLORS.get(solver_label(s).lower(), "#777777"))

    ax.set_ylabel(ylabel)
    ax.grid(axis="y", which="both", alpha=0.3)
    ax.set_axisbelow(True)

    if use_log:
        ax.set_yscale("log")

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([group_label(g) for g in groups])
    ax.set_xlabel("Nhóm màn")
    ax.legend(
        ncol=min(len(solvers), 5),
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        frameon=False,
    )
    fig.tight_layout()

    # Lưu định dạng PDF cho LaTeX và PNG để xem nhanh
    fig.savefig(out_dir / f"{base_filename}.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{base_filename}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def draw_scaling(out_dir, base_filename, rows, solvers, levels):
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    
    # Khai báo màu để phân biệt rõ 4 thuật toán
    colors = {
        "bfs": "#4C72B0", 
        "dfs": "#DD8452", 
        "ucs": "#55A868", 
        "a*": "#C44E52", 
        "astar": "#C44E52"
    }

    for s in solvers:
        xs, ys = [], []
        for lv in levels:
            # Lọc kết quả của từng thuật toán trên màn chơi lv
            matched = [r for r in rows if r.get("level") == lv and r.get("solver") == s]
            
            if matched:
                r = matched[0]
                # Lấy số nước đi (trục X) và số node mở rộng (trục Y)
                length = r.get("length") 
                exp = r.get("expanded")
                
                # Bỏ qua nếu dữ liệu rỗng hoặc thuật toán không giải được
                if length is not None and exp is not None and not math.isnan(length) and not math.isnan(exp):
                    xs.append(length)
                    ys.append(exp)

        # Chỉ vẽ khi có dữ liệu
        if xs:
            lbl = "A*" if s.upper() in ["ASTAR", "A*"] else s.upper()
            c_key = lbl.lower()
            
            ax.scatter(
                xs,
                ys,
                s=35,           # Kích thước chấm tròn
                label=lbl,      # Tên hiển thị trong chú thích
                color=colors.get(c_key, "#777777"),
                alpha=0.85,
                zorder=3,
            )

    ax.set_xlabel("Độ dài lời giải (số nước)")
    ax.set_ylabel("Số node mở rộng")
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.set_axisbelow(True)
    
    # Thêm chú thích cho cả 4 thuật toán ở dưới cùng
    ax.legend(
        ncol=len(solvers),
        fontsize=9,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        frameon=False,
    )
    fig.tight_layout()

    # Xuất file
    out_path = Path(out_dir)
    fig.savefig(out_path / f"{base_filename}.pdf", bbox_inches="tight")
    fig.savefig(out_path / f"{base_filename}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    # Tự động xác định đường dẫn thư mục docs/Resources trong dự án
    base_project_dir = Path(__file__).resolve().parent.parent
    default_resources_dir = base_project_dir / "docs" / "Resources"
    default_csv_file = base_project_dir / "data" / "logs" / "results.csv"

    parser = argparse.ArgumentParser(description="Tự động vẽ biểu đồ và bảng xuất vào docs/Resources.")
    parser.add_argument("--csv", default=str(default_csv_file), help="Đường dẫn file CSV log kết quả")
    parser.add_argument("--out", default=str(default_resources_dir), help="Thư mục lưu ảnh và bảng (.tex)")
    args = parser.parse_args()

    rows = read_results(args.csv)
    if not rows:
        print(f"❌ Không tìm thấy hoặc dữ liệu rỗng tại: {args.csv}")
        sys.exit(1)

    target_dir = Path(args.out)
    target_dir.mkdir(parents=True, exist_ok=True)

    levels = list(dict.fromkeys(r["level"] for r in rows))
    solvers = list(dict.fromkeys(r["solver"] for r in rows))
    groups = [g for g in GROUP_ORDER if any(categorize_group(r["level"]) == g for r in rows)]

    print("=" * 70)
    print("🚀 ĐANG TỰ ĐỘNG XUẤT KẾT QUẢ VÀO THƯ MỤC docs/Resources...")
    print(f"📂 Thư mục đích: {target_dir}")
    print("=" * 70)

    # 1. Xuất 3 file bảng LaTeX (.tex)
    write_testset_tex(rows, target_dir / "testset.tex")
    write_tier_tex(rows, solvers, groups, target_dir / "results_by_tier.tex")
    write_detail_tex(rows, solvers, levels, target_dir / "results_detail.tex")
    print("✅ Đã tạo các file bảng LaTeX: testset.tex, results_by_tier.tex, results_detail.tex")

    # 2. Xuất 5 biểu đồ (PDF & PNG)
    draw_group_bars(target_dir, "fig_expanded", rows, solvers, groups, "expanded", 1.0, "Số node mở rộng", True)
    draw_group_bars(target_dir, "fig_time", rows, solvers, groups, "time_s", 1000.0, "Thời gian tìm kiếm (ms)", True)
    draw_group_bars(target_dir, "fig_memory", rows, solvers, groups, "peak_mem_kb", 1.0, "Bộ nhớ đỉnh (KB)", True)
    draw_group_bars(target_dir, "fig_length", rows, solvers, groups, "length", 1.0, "Độ dài lời giải (số nước)", False)
    draw_scaling(target_dir, "fig_scaling", rows, solvers, levels)
    print("✅ Đã xuất các file biểu đồ: fig_expanded, fig_time, fig_memory, fig_length, fig_scaling (PDF & PNG)")

    print("\n" + "=" * 70)
    print(f"🎉 TẤT CẢ TÀI NGUYÊN ĐÃ ĐƯỢC TỰ ĐỘNG LƯU VÀO: {target_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()