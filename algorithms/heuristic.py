"""
Module heuristic.py: Định nghĩa các hàm chi phí (Cost Function) và Heuristic cho bài toán Bloxorz.

Khớp 100% với Báo cáo kỹ thuật:
1. Cost Function g(n):
   - uniform_cost: c(s, a, s') = 1.0 cho mọi hành động hợp lệ (thống nhất cùng TV3 - Hà Chí Tâm).
   - weighted_switch_cost: hỗ trợ gán trọng số khi kích hoạt công tắc đổi trạng thái cầu.
2. Hàm 1 - Baseline Heuristic (h1):
   - manhattan_heuristic: d_min = min Manhattan giữa các ô khối chiếm giữ và ô đích.
   - h1(s) = ceil(d_min / 2).
3. Hàm 2 - Advanced Heuristic (h2):
   - bloxorz_advanced_heuristic: Kết hợp điểm rút gọn d_min, cận dưới ceil(d_min / 2),
     phạt tư thế (Orientation Penalty) có điều kiện nghiêm ngặt:
       + d_min == 0 và nằm: phạt +2 bước (khối phải lăn ra rồi dựng lại vào đích).
       + d_min == 1 và đứng: phạt +1 bước (khối đứng kề đích không thể lật vào đích ngay).
       + Các trường hợp khác: phạt 0 bước (đặc biệt d_min == 1 và nằm hướng đích chỉ tốn đúng 1 bước).
     và công thức trạng thái tách khối (SPLIT):
       + d_merge = max(0, |r1 - r2| + |c1 - c2| - 1)
       + d_goal = ceil(min(||C1 - T||1, ||C2 - T||1) / 2)
       + h_split = max(d_merge, d_goal)
"""

from collections import deque
import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.board import Board
from core.state import Coordinates, Orientation, State
from core.transition import get_successors, is_goal_state

# Định nghĩa kiểu dữ liệu
CostFunction = Callable[[State, Any, State], float]
HeuristicFunction = Callable[[State, Coordinates], float]


# ============================================================================
# 1. COST FUNCTION (HÀM CHI PHÍ BƯỚC ĐI - g(n))
# ============================================================================


def uniform_cost(state: State, action: Any, next_state: State) -> float:
    """
    Cost Function chuẩn: mỗi bước đi (UP, DOWN, LEFT, RIGHT, SWITCH) tốn chi phí 1.0.
    Thống nhất cùng TV3 (Hà Chí Tâm) để tìm lời giải có số bước di chuyển tối thiểu.
    """
    return 1.0


def weighted_switch_cost(
    state: State,
    action: Any,
    next_state: State,
    switch_extra_cost: float = 1.0,
) -> float:
    """
    Hàm chi phí không đồng nhất (mở rộng cho UCS):
    - Bước đi thông thường: chi phí 1.0.
    - Bước đi kích hoạt công tắc làm đổi trạng thái cầu: chi phí 1.0 + switch_extra_cost.
    """
    base = 1.0
    if state.active_bridges != next_state.active_bridges:
        return base + switch_extra_cost
    return base


# ============================================================================
# 2. ĐIỂM RÚT GỌN (REPRESENTATIVE POINT)
# ============================================================================


def get_representative_point(state: State) -> Tuple[float, float]:
    """
    Xác định điểm rút gọn (trọng tâm hình học / centroid) của khối trên lưới 2D.

    - STANDING tại (r, c): (r, c)
    - HORIZONTAL tại (r, c): đè lên (r, c) và (r, c+1) -> trọng tâm (r, c + 0.5)
    - VERTICAL tại (r, c): đè lên (r, c) và (r+1, c) -> trọng tâm (r + 0.5, c)
    - SPLIT tại (r, c) và split_pos=(r2, c2): trung bình ((r + r2)/2, (c + c2)/2)
    """
    if state.orientation == Orientation.STANDING:
        return float(state.r), float(state.c)
    elif state.orientation == Orientation.HORIZONTAL:
        return float(state.r), float(state.c) + 0.5
    elif state.orientation == Orientation.VERTICAL:
        return float(state.r) + 0.5, float(state.c)
    elif state.orientation == Orientation.SPLIT:
        if state.split_pos is not None:
            r2, c2 = state.split_pos
            return (state.r + r2) / 2.0, (state.c + c2) / 2.0
        return float(state.r), float(state.c)
    return float(state.r), float(state.c)


def manhattan_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Khoảng cách Manhattan giữa 2 điểm tọa độ 2D (hỗ trợ số thực)."""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


# ============================================================================
# 3. HÀM 1: MANHATTAN HEURISTIC (H1 - BASELINE)
# ============================================================================


def manhattan_heuristic(state: State, goal_pos: Coordinates) -> int:
    """
    Hàm Heuristic cơ sở H1 (Baseline):
    - Xác định khoảng cách Manhattan ngắn nhất từ các ô bị khối chiếm giữ tới ô đích T:
      d_min = min_{(r, c) in cells(s)} (|r - r_T| + |c - c_T|)
    - Chia cho 2 vì tốc độ dịch chuyển tối đa của khối là 2 ô/bước:
      h1(s) = ceil(d_min / 2)
    """
    if state.is_standing_at(goal_pos):
        return 0

    cells = state.get_occupied_cells()
    gr, gc = goal_pos
    d_min = min(abs(r - gr) + abs(c - gc) for r, c in cells)
    return int(math.ceil(d_min / 2.0))


def manhattan_div2_heuristic(state: State, goal_pos: Coordinates) -> float:
    """Alias tương thích ngược cho manhattan_heuristic."""
    return float(manhattan_heuristic(state, goal_pos))


# ============================================================================
# 4. HÀM 2: BLOXORZ ADVANCED HEURISTIC (H2 - ADVANCED)
# ============================================================================


def split_state_heuristic(state: State, goal_pos: Coordinates) -> int:
    """
    Công thức Heuristic cho trạng thái tách khối (SPLIT) theo Báo cáo kỹ thuật mục 3.2.C:
    1. d_merge = max(0, |r1 - r2| + |c1 - c2| - 1)  (chi phí áp sát nhau để gộp)
    2. d_goal = ceil(min(||C1 - T||1, ||C2 - T||1) / 2)  (chi phí tiếp cận đích)
    3. h_split(s) = max(d_merge, d_goal)
    """
    if state.split_pos is None:
        cr, cc = float(state.r), float(state.c)
        return int(math.ceil(max(2.0, (abs(cr - goal_pos[0]) + abs(cc - goal_pos[1])) / 2.0)))

    r1, c1 = state.r, state.c
    r2, c2 = state.split_pos
    gr, gc = goal_pos

    d_merge = max(0, abs(r1 - r2) + abs(c1 - c2) - 1)
    d1 = abs(r1 - gr) + abs(c1 - gc)
    d2 = abs(r2 - gr) + abs(c2 - gc)
    d_goal = int(math.ceil(min(d1, d2) / 2.0))

    return max(d_merge, d_goal)


def bloxorz_advanced_heuristic(state: State, goal_pos: Coordinates) -> int:
    """
    Hàm Heuristic nâng cao H2 theo đúng đặc tả Báo cáo kỹ thuật mục 3.2:

    1. Kiểm tra đích:
       Nếu đã đứng thẳng tại T -> h = 0.

    2. Trạng thái SPLIT:
       Áp dụng split_state_heuristic -> h_split = max(d_merge, d_goal).

    3. Khoảng cách điểm rút gọn (Representative Distance):
       d_min = min_{(r, c) in occupied} (|r - r_T| + |c - c_T|)
       base_h = ceil(d_min / 2)

    4. Phạt tư thế (Orientation Penalty) có điều kiện nghiêm ngặt:
       - d_min == 0 và theta != STANDING (nằm đè lên đích):
         Khối buộc phải lăn ra rồi mới dựng lại vào đích (cần ít nhất >= 2 bước) -> phạt +2 bước.
       - d_min == 1 và theta == STANDING (đứng cạnh đích):
         Khối đứng kề đích chỉ có thể lật sang thế nằm, không thể thắng ngay (cần ít nhất >= 2 bước) -> phạt +1 bước.
       - Các trường hợp khác:
         Phạt 0 bước (đặc biệt khi d_min == 1 và đang nằm hướng vào đích, chỉ cần đúng 1 bước lật là thắng).

    5. Tổng hợp:
       h(s) = base_h + penalty
    """
    # 1. Kiểm tra đích
    if state.is_standing_at(goal_pos):
        return 0

    # 2. Trạng thái SPLIT
    if state.orientation == Orientation.SPLIT:
        return split_state_heuristic(state, goal_pos)

    # 3. Khoảng cách điểm rút gọn
    cells = state.get_occupied_cells()
    gr, gc = goal_pos
    d_min = min(abs(r - gr) + abs(c - gc) for r, c in cells)
    base_h = int(math.ceil(d_min / 2.0))

    # 4. Phạt tư thế
    if d_min == 0 and state.orientation != Orientation.STANDING:
        penalty = 2
    elif d_min == 1 and state.orientation == Orientation.STANDING:
        penalty = 1
    else:
        penalty = 0

    return base_h + penalty


# Alias chính cho solver
bloxorz_heuristic = bloxorz_advanced_heuristic


def compute_orientation_penalty(
    state: State,
    goal_pos: Coordinates,
    base_dist: float,
) -> float:
    """
    Hàm phụ trợ tính penalty theo định dạng float tương thích ngược cho test.
    """
    if state.is_standing_at(goal_pos):
        return 0.0

    cells = state.get_occupied_cells()
    gr, gc = goal_pos
    d_min = min(abs(r - gr) + abs(c - gc) for r, c in cells)

    if d_min == 0 and state.orientation != Orientation.STANDING:
        return 2.0
    elif d_min == 1 and state.orientation == Orientation.STANDING:
        return 1.0
    return 0.0


def is_direct_goal_predecessor(state: State, goal_pos: Coordinates) -> bool:
    """
    Kiểm tra trạng thái nằm có phải 1 trong 4 trạng thái trực tiếp lật 1 bước đứng vào đích.
    """
    gr, gc = goal_pos
    if state.orientation == Orientation.HORIZONTAL:
        return state.r == gr and (state.c == gc - 2 or state.c == gc + 1)
    elif state.orientation == Orientation.VERTICAL:
        return state.c == gc and (state.r == gr - 2 or state.r == gr + 1)
    return False


def make_heuristic(
    board: Board,
    advanced: bool = True,
) -> Callable[[State], float]:
    """
    Factory tạo hàm heuristic nhận 1 tham số duy nhất là State, gắn liền với Board.
    """
    goal = board.goal_pos
    if advanced:
        return lambda s: float(bloxorz_advanced_heuristic(s, goal))
    return lambda s: float(manhattan_heuristic(s, goal))


# ============================================================================
# 5. SCRIPT KIỂM TRA TÍNH CHẤP NHẬN ĐƯỢC (ADMISSIBILITY CHECKER BẰNG BFS)
# ============================================================================


def compute_all_true_distances_bfs(board: Board) -> Tuple[Dict[State, int], Set[State]]:
    """
    Chạy BFS từ trạng thái xuất phát để xác định:
    1. Toàn bộ các trạng thái đạt được (reachable states).
    2. Chi phí tối ưu thực tế h*(s) từ mọi trạng thái s tới đích.
    """
    init_state = State(
        r=board.start_pos[0],
        c=board.start_pos[1],
        orientation=Orientation.STANDING,
        active_bridges=board.initial_active_bridges,
    )

    q_reach: deque[State] = deque([init_state])
    reachable: Set[State] = {init_state}

    while q_reach:
        curr = q_reach.popleft()
        for _, nxt in get_successors(board, curr):
            if nxt not in reachable:
                reachable.add(nxt)
                q_reach.append(nxt)

    true_costs: Dict[State, int] = {}
    for s in reachable:
        q_dist: deque[Tuple[State, int]] = deque([(s, 0)])
        visited: Set[State] = {s}
        found_dist: Optional[int] = None

        while q_dist:
            curr, dist = q_dist.popleft()
            if is_goal_state(board, curr):
                found_dist = dist
                break

            for _, nxt in get_successors(board, curr):
                if nxt not in visited:
                    visited.add(nxt)
                    q_dist.append((nxt, dist + 1))

        if found_dist is not None:
            true_costs[s] = found_dist

    return true_costs, reachable


def verify_heuristic_admissibility(
    board: Board,
    heuristic_fn: Optional[HeuristicFunction] = None,
    map_name: str = "Map",
) -> Dict[str, Any]:
    """
    Kiểm tra điều kiện h(s) <= h*(s) trên toàn bộ trạng thái có thể tới đích của bản đồ.
    """
    if heuristic_fn is None:
        heuristic_fn = bloxorz_advanced_heuristic

    true_costs, reachable = compute_all_true_distances_bfs(board)
    violations: List[Dict[str, Any]] = []
    differences: List[float] = []

    for s, h_star in true_costs.items():
        h_val = heuristic_fn(s, board.goal_pos)
        diff = h_star - h_val
        differences.append(diff)

        if h_val > h_star:
            violations.append(
                {
                    "state": s,
                    "h_val": h_val,
                    "h_star": h_star,
                    "overestimate": h_val - h_star,
                }
            )

    is_admissible = len(violations) == 0
    avg_error = sum(differences) / len(differences) if differences else 0.0

    return {
        "map_name": map_name,
        "is_admissible": is_admissible,
        "total_reachable": len(reachable),
        "solvable_states": len(true_costs),
        "violations_count": len(violations),
        "violations": violations,
        "avg_underestimate": avg_error,
        "min_slack": min(differences) if differences else 0.0,
        "max_slack": max(differences) if differences else 0.0,
    }


def run_admissibility_verification_on_small_maps() -> bool:
    """
    Script kiểm tra tự động trên 3 map chuẩn theo Báo cáo kỹ thuật mục 5.1:
    Level 0 (29 trạng thái), Level 1 (114 trạng thái), Level 3 (102 trạng thái).
    """
    from core.map_loader import load_level

    maps_to_test = [
        ("Stage 01 (Level 0)", os.path.join(PROJECT_ROOT, "data", "maps", "stage_01.txt")),
        ("Stage 02 (Level 1)", os.path.join(PROJECT_ROOT, "data", "maps", "stage_02.txt")),
        ("Stage 04 (Level 3)", os.path.join(PROJECT_ROOT, "data", "maps", "stage_04.txt")),
    ]

    print("=" * 80)
    print("      KIỂM TRA TÍNH CHẤP NHẬN ĐƯỢC (ADMISSIBILITY) CỦA HEURISTIC BẰNG BFS")
    print("=" * 80)

    all_passed = True

    for label, path in maps_to_test:
        if not os.path.exists(path):
            print(f"[-] Bỏ qua {label}: không tìm thấy file {path}")
            continue

        board = load_level(path)
        report = verify_heuristic_admissibility(board, heuristic_fn=bloxorz_advanced_heuristic, map_name=label)

        status_str = "THÀNH CÔNG (ADMISSIBLE)" if report["is_admissible"] else "THẤT BẠI (VIOLATION)"
        print(f"\n[+] {label}:")
        print(f"    - Số trạng thái duyệt được : {report['total_reachable']}")
        print(f"    - Số trạng thái tới đích   : {report['solvable_states']}")
        print(f"    - Số vi phạm (h > h*)      : {report['violations_count']}")
        print(f"    - Độ lệch trung bình (h*-h): {report['avg_underestimate']:.2f}")
        print(f"    - Kết quả                  : {status_str}")

        if not report["is_admissible"]:
            all_passed = False
            print("    [!] Chi tiết vi phạm đầu tiên:")
            v = report["violations"][0]
            print(f"        State : {v['state']}")
            print(f"        h(s)  : {v['h_val']} > h*(s): {v['h_star']}")

    print("\n" + "=" * 80)
    if all_passed:
        print("[V] TOÀN BỘ CÁC MAP ĐỀU THỎA MÃN: h(s) <= h*(s) Ở MỌI TRẠNG THÁI!")
    else:
        print("[X] CÓ TRẠNG THÁI BỊ ĐÁNH GIÁ CAO HƠN THỰC TẾ (OVERESTIMATION)!")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_admissibility_verification_on_small_maps()
    sys.exit(0 if success else 1)
