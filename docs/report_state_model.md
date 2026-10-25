# Mô Hình Hóa Bài Toán Giải Game Bloxorz (Problem Formulation & State Space Model)

Tài liệu này trình bày chi tiết mục **Mô hình hóa bài toán (Problem Formulation)** cho báo cáo đồ án Trí tuệ Nhân tạo giải bài toán **Bloxorz**, đối chiếu trực tiếp với cài đặt trong các mô-đun [`core/state.py`](../core/state.py), [`core/board.py`](../core/board.py), [`core/transition.py`](../core/transition.py), [`algorithms/base_solver.py`](../algorithms/base_solver.py) và [`gui/replayer.py`](../gui/replayer.py).

---

## 1. Tổng Quan Bài Toán

**Bloxorz** là trò chơi giải đố logic trên lưới hai chiều kích thước $R \times C$. Người chơi điều khiển một khối hộp chữ nhật kích thước $1 \times 1 \times 2$ (hoặc hai khối lập phương đơn $1 \times 1 \times 1$ khi bị phân tách) lăn qua các ô gạch trên bản đồ để đưa khối về **đứng thẳng** ($1 \times 1 \times 2$) ngay tại **ô đích** (`end_pos`) mà không bị rơi khỏi bản đồ hoặc làm vỡ gạch mỏng.

Vì môi trường của Bloxorz hoàn toàn xác định (deterministic), quan sát được đầy đủ (fully observable), rời rạc (discrete) và tĩnh (static), bài toán được mô hình hóa chuẩn xác dưới dạng **Bài toán tìm kiếm trong không gian trạng thái (State-Space Search Problem)**:

$$\mathcal{P} = \langle \mathcal{S}, s_0, \mathcal{A}, \mathcal{T}, \mathcal{G}, c \rangle$$

---

## 2. Biểu Diễn Trạng Thái ($\mathcal{S}$) và Khóa Trạng Thái (`state_key`)

### 2.1. Cấu trúc bộ trạng thái `State`
Trong Bloxorz có sự xuất hiện của các **công tắc đóng/mở cầu** (làm thay đổi địa hình bản đồ theo hành trình) và **cổng phân tách khối** (chia khối $1 \times 1 \times 2$ thành hai khối đơn $1 \times 1 \times 1$ điều khiển độc lập). Do đó, nếu chỉ lưu tọa độ $(r, c)$ và tư thế của khối thì không gian trạng thái sẽ không thỏa mãn tính chất Markov.

Mỗi trạng thái $s \in \mathcal{S}$ trong [`core/state.py`](../core/state.py) được biểu diễn bởi một bộ 6 thành phần bất biến (`@dataclass(frozen=True)`):

$$s = (r, c, \text{orientation}, \text{active\_bridges}, \text{split\_pos}, \text{active\_cube})$$

Trong đó:
1. **`r`, `c`** ($\mathbb{Z} \times \mathbb{Z}$): Tọa độ dòng và cột neo (anchor cell) của khối chính:
   - Khi `orientation = STANDING`: khối đứng thẳng chiếm duy nhất 1 ô $(r, c)$.
   - Khi `orientation = HORIZONTAL`: khối nằm ngang chiếm 2 ô $(r, c)$ và $(r, c + 1)$.
   - Khi `orientation = VERTICAL`: khối nằm dọc chiếm 2 ô $(r, c)$ và $(r + 1, c)$.
   - Khi `orientation = SPLIT`: khối đơn thứ nhất (cube 0) chiếm ô $(r, c)$.
2. **`orientation`** ($\{\text{STANDING}, \text{HORIZONTAL}, \text{VERTICAL}, \text{SPLIT}\}$): Tư thế hiện tại của khối trên mặt phẳng.
3. **`active_bridges`** ($\text{FrozenSet}[(r_b, c_b)]$): Tập hợp bất biến chứa tọa độ các ô cầu (`TileType.BRIDGE`) **đang mở** tại thời điểm hiện tại.
4. **`split_pos`** ($\text{Optional}[(r_2, c_2)]$):
   - Bằng `None` khi khối ở trạng thái nguyên vẹn (`STANDING`, `HORIZONTAL`, `VERTICAL`).
   - Bằng $(r_2, c_2)$ khi `orientation = SPLIT`, biểu diễn tọa độ của khối đơn thứ hai (cube 1).
5. **`active_cube`** ($\{0, 1\}$): Chỉ số khối đơn đang nhận lệnh di chuyển khi ở trạng thái `SPLIT` ($0$ tương ứng khối tại $(r, c)$; $1$ tương ứng khối tại $\text{split\_pos}$). Khi không ở trạng thái `SPLIT`, chuẩn hóa `active_cube = 0`.

### 2.2. Khóa trạng thái (`state_key`) cho tập `visited` của Solver
Để tránh lặp vô hạn và nhận diện chính xác các trạng thái trùng lặp trong BFS, DFS, UCS và A*, khóa trạng thái được định nghĩa tại [`state_key(state)`](../core/state.py) và kiểm tra tự động qua [`verify_solver_state_key()`](../gui/replayer.py):

$$\text{key}(s) = \big(r, c, \text{orientation}, \text{tuple}(\text{sorted}(\text{active\_bridges})), \text{split\_pos}, \text{active\_cube}\big)$$

- Việc dùng `frozenset` trên `State` và `tuple(sorted(active_bridges))` trong `state_key` đảm bảo **tính bất biến theo thứ tự mở cầu**: dù các cầu được kích hoạt theo thứ tự nào, cùng một tập ô cầu đang mở sẽ luôn sinh ra cùng một mã băm (`hash`).
- Phân biệt đầy đủ trạng thái cầu đóng/mở, tọa độ hai khối phân tách và quyền điều khiển khối đơn (`active_cube`).

---

## 3. Trạng Thái Khởi Đầu ($s_0$) và Kiểm Tra Đích ($\mathcal{G}$)

### 3.1. Trạng thái khởi đầu ($s_0$)
Từ bản đồ `Board` nạp qua [`core/map_loader.py`](../core/map_loader.py) (dữ liệu chuẩn `coolmath.json`), khối bắt đầu ở tư thế đứng thẳng tại ô xuất phát `board.start_pos` $(r_S, c_S)$ cùng tập các ô cầu mở sẵn ban đầu `board.initial_active_bridges`:

$$s_0 = \big(r_S, c_S, \text{STANDING}, \text{initial\_active\_bridges}, \text{None}, 0\big)$$

### 3.2. Điều kiện đích ($\mathcal{G}$ — `is_goal_state`)
Một trạng thái $s$ là trạng thái đích ($\mathcal{G}(s) = \text{True}$) khi và chỉ khi khối đã **hợp nhất nguyên vẹn**, ở tư thế **đứng thẳng** (`STANDING`) chính xác trên ô đích `board.end_pos` $(r_T, c_T)$:

$$\mathcal{G}(s) \iff (s.\text{orientation} = \text{STANDING}) \land (s.r = r_T) \land (s.c = c_T)$$

> **Lưu ý luật gốc Bloxorz**: Một khối đơn lẻ ($1 \times 1 \times 1$) ở trạng thái `SPLIT` đi qua ô đích **không** được tính là thắng; hai khối đơn bắt buộc phải gộp lại thành khối $1 \times 1 \times 2$ rồi mới dựng đứng vào lỗ đích.

---

## 4. Tập Hành Động ($\mathcal{A}$) và Hàm Chuyển Trạng Thái ($\mathcal{T}$)

### 4.1. Tập hành động ($\mathcal{A}(s)$)
- Khi khối nguyên vẹn ($s.\text{orientation} \neq \text{SPLIT}$):
  $$\mathcal{A}(s) = \{\text{UP}, \text{DOWN}, \text{LEFT}, \text{RIGHT}\}$$
- Khi khối đang tách đôi ($s.\text{orientation} = \text{SPLIT}$):
  $$\mathcal{A}(s) = \{\text{UP}, \text{DOWN}, \text{LEFT}, \text{RIGHT}, \text{SWITCH}\}$$
  Trong đó hành động `SWITCH` (phím `Space` khi người chơi điều khiển) đổi quyền điều khiển giữa hai khối đơn: $\text{active\_cube} \leftarrow 1 - \text{active\_cube}$ mà không làm thay đổi vị trí hai khối.

### 4.2. Luật lăn khối hình học (`roll_block`)
1. **Từ tư thế đứng (`STANDING`) tại $(r, c)$**:
   - `UP`: $(r - 2, c, \text{VERTICAL})$
   - `DOWN`: $(r + 1, c, \text{VERTICAL})$
   - `LEFT`: $(r, c - 2, \text{HORIZONTAL})$
   - `RIGHT`: $(r, c + 1, \text{HORIZONTAL})$
2. **Từ tư thế nằm ngang (`HORIZONTAL`) tại $(r, c), (r, c+1)$**:
   - `UP`: $(r - 1, c, \text{HORIZONTAL})$
   - `DOWN`: $(r + 1, c, \text{HORIZONTAL})$
   - `LEFT`: $(r, c - 1, \text{STANDING})$
   - `RIGHT`: $(r, c + 2, \text{STANDING})$
3. **Từ tư thế nằm dọc (`VERTICAL`) tại $(r, c), (r+1, c)$**:
   - `UP`: $(r - 1, c, \text{STANDING})$
   - `DOWN`: $(r + 2, c, \text{STANDING})$
   - `LEFT`: $(r, c - 1, \text{VERTICAL})$
   - `RIGHT`: $(r, c + 1, \text{VERTICAL})$
4. **Từ tư thế tách khối (`SPLIT`)**:
   - Chỉ khối đơn đang được chọn (`active_cube`) dịch chuyển 1 ô theo hướng $(\Delta r, \Delta c) \in \{(-1, 0), (1, 0), (0, -1), (0, 1)\}$; khối đơn còn lại giữ nguyên tọa độ.

### 4.3. Điều kiện hợp lệ của địa hình (`check_occupied_cells`)
Gọi $\text{Occ}(s)$ là tập các ô bản đồ mà khối đang đè lên ($1$ ô nếu `STANDING`, $2$ ô nếu `HORIZONTAL` / `VERTICAL` / `SPLIT`). Trạng thái $s'$ sau khi lăn là hợp lệ nếu thỏa mãn đồng thời:
1. **Trong biên và không rơi xuống vực (`VOID`)**: $\forall (r_i, c_i) \in \text{Occ}(s'), \text{tile}(r_i, c_i) \neq \text{VOID}$.
2. **Cầu phải đang mở (`BRIDGE`)**: $\forall (r_i, c_i) \in \text{Occ}(s')$, nếu $\text{tile}(r_i, c_i) = \text{BRIDGE}$ thì $(r_i, c_i) \in s'.\text{active\_bridges}$.
3. **Gạch mỏng cam (`FRAGILE`)**: Nếu $s'.\text{orientation} = \text{STANDING}$ tại $(r, c)$ thì $\text{tile}(r, c) \neq \text{FRAGILE}$ (đứng thẳng dồn toàn bộ trọng lượng lên 1 ô gạch mỏng sẽ làm vỡ gạch và rơi xuống vực).

### 4.4. Cơ chế công tắc, cầu, tách khối và gộp khối trong `get_next_state`
Khi khối di chuyển hợp lệ sang vị trí mới, hệ thống áp dụng tuần tự các hiệu ứng môi trường:
1. **Kích hoạt công tắc cầu (`SOFT_SWITCH` & `HEAVY_SWITCH`)**:
   - **Công tắc tròn (`SOFT_SWITCH` — ký hiệu `'O'` trong `coolmath.json`)**: Kích hoạt ngay khi bất kỳ phần nào của khối (đứng, nằm ngang/dọc, hoặc khối đơn `SPLIT` vừa di chuyển tới) chạm vào ô công tắc.
   - **Công tắc chữ X (`HEAVY_SWITCH` — ký hiệu `'X'` trong `coolmath.json`)**: Đòi hỏi trọng lượng lớn, **chỉ kích hoạt khi khối đứng thẳng (`STANDING`)** ngay trên ô công tắc. Khối nằm hoặc khối đơn `SPLIT` đi qua không kích hoạt được `HEAVY_SWITCH`.
   - **Ba chế độ cầu (`BridgeMode`)**: Mỗi công tắc có thể điều khiển một hoặc nhiều cụm cầu theo chế độ:
     - `TOGGLE` (`swap`): Đảo trạng thái đóng $\leftrightarrow$ mở.
     - `OPEN` (`on`): Mở cầu vĩnh viễn (permanent open).
     - `CLOSE` (`off`): Đóng cầu vĩnh viễn (permanent close).
   - *Kiểm tra lại sau khi bật/tắt cầu*: Nếu việc chạm công tắc làm đóng ngay cây cầu dưới chân khối hiện tại, nước đi đó bị tính là rơi (`None`).
2. **Cổng phân tách / dịch chuyển (`SPLIT_SWITCH` — ký hiệu `'T'` trong `coolmath.json`)**:
   - Khi khối đứng thẳng (`STANDING`) tại ô phân tách $(r_U, c_U)$, khối lập tức tách thành 2 khối lập phương đơn $1 \times 1 \times 1$ tại hai tọa độ cố định $(p_1, p_2)$ do bản đồ quy định (`board.splits[(r_U, c_U)]`) và chuyển sang tư thế `Orientation.SPLIT`.
3. **Tự động gộp khối (`SPLIT` $\to$ `HORIZONTAL` / `VERTICAL`)**:
   - Khi đang ở trạng thái `SPLIT`, nếu sau bước di chuyển hai khối đơn nằm trên **hai ô kề cạnh nhau** ($|r_1 - r_2| + |c_1 - c_2| = 1$), chúng tự động gắn kết lại thành khối $1 \times 1 \times 2$:
     - Thành `HORIZONTAL` tại $(r_1, \min(c_1, c_2))$ nếu cùng hàng ($r_1 = r_2$).
     - Thành `VERTICAL` tại $(\min(r_1, r_2), c_1)$ nếu cùng cột ($c_1 = c_2$).

---

## 5. Hàm Chi Phí Đường Đi ($c$) và Tính Tối Ưu

- Trong bài toán tìm đường đi ngắn nhất theo số bước lăn (BFS, UCS, A*):
  - Mỗi hành động sinh trạng thái kế tiếp trong cây tìm kiếm có chi phí bước dương để đảm bảo các thuật toán tìm kiếm không rơi vào chu trình chi phí 0.
  - Khi thống kê số bước di chuyển (`moves`) trong ván chơi (`core.game.Game` và `gui.replayer.Replayer`), các bước lăn khối vật lý (`UP`, `DOWN`, `LEFT`, `RIGHT`) tăng bộ đếm `moves` thêm $1$, trong khi thao tác chuyển đổi khối điều khiển (`SWITCH` / `SPACE`) chỉ đổi quyền điều khiển giữa hai khối đơn mà không tốn lượt lăn vật lý.

---

## 6. Cơ Chế Kiểm Chứng Lời Giải (Replayer & Background Solver)

Để đảm bảo mọi lời giải do người chơi thực hiện hoặc do các thuật toán (`BFS`, `DFS`, `UCS`, `A*`) tìm ra đều hợp lệ từ đầu đến cuối:
1. **Rà soát khóa trạng thái tự động (`verify_solver_state_key`)**: Trước khi chạy thuật toán trên luồng nền (`BackgroundSolverWorker`), hệ thống kiểm tra hàm khóa trạng thái có phân biệt đầy đủ tọa độ, hướng, trạng thái cầu (`active_bridges`), tọa độ khối tách (`split_pos`) và khối đơn đang điều khiển (`active_cube`).
2. **Thực thi luồng nền và Hàng đợi lỗi (`BackgroundSolverWorker` & `error_queue`)**: Thuật toán tìm kiếm chạy trên daemon thread riêng biệt, trả kết quả qua `result_queue` (`SolverResultEvent`) và bắt toàn bộ ngoại lệ (nếu có) vào `error_queue` (`SolverErrorEvent`) để giao diện 3D OpenGL không bao giờ bị treo.
3. **Bộ phát lại quỹ đạo (`Replayer`)**: Tiền tính toán và xác thực từng bước trong chuỗi hành động từ $s_0$ qua `get_next_state`, đồng bộ trực tiếp với `core.game.Game` và `gui.animator.Animator` để phát lại chính xác từng bước lăn, tách/gộp khối và đóng/mở cầu.

