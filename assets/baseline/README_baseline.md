# Baseline dự án Bloxorz: hướng dẫn đọc và ý tưởng kỹ thuật

Tài liệu này giải thích cách đọc các sơ đồ baseline, những quyết định thiết kế đã chốt, và các ý tưởng kỹ thuật cả nhóm cần nắm trước khi viết code.

## 1. Các sơ đồ trong baseline

Có năm sơ đồ Mermaid. Dán từng khối vào https://mermaid.live để xem.

| Sơ đồ | Trả lời câu hỏi |
|---|---|
| Sơ đồ lớp | Có những class nào, thuộc nhóm nào, quan hệ với nhau ra sao |
| Logic công tắc | Một nước đi được xử lý thế nào khi có công tắc và cầu |
| Luồng chạy | Khi người chơi bấm phím hoặc bấm Run Solver thì chuyện gì xảy ra |
| Thực nghiệm | Từ map đến biểu đồ so sánh các thuật toán |
| Lộ trình | Làm theo thứ tự nào, ai đang chờ ai |

## 2. Cách đọc ký hiệu

**Namespace** là nhóm phụ trách. Các class nằm trong `TV1_Core` do TV1 làm, `TV2_GUI` do TV2, `TV34_Algorithms` do TV3 và TV4, `TV5_Experiments` do TV5. File nào thuộc nhóm nào thì class của file đó nằm trong namespace tương ứng.

**Nhãn trạng thái** nằm trong `note`:

- `[ĐÃ CÓ]`: đã viết và đúng, không cần đổi.
- `[CHỈNH SỬA]`: đã có nhưng cần sửa theo thiết kế mới.
- `[MỚI]`: thêm mới.
- `[CHƯA VIẾT]`: cần viết, chưa có gì.

**Ký hiệu quan hệ giữa các class:**

| Ký hiệu | Nghĩa | Ví dụ |
|---|---|---|
| `*--` | Sở hữu, sống cùng vòng đời | `Board` sở hữu `grid` |
| `o--` | Tham chiếu, không sở hữu | `Window` giữ `Animator` |
| `-->` | Tham chiếu lâu dài | `Window` biết `Game` |
| `..>` | Phụ thuộc: dùng, nhận tham số, trả về | `Game` dùng `apply_move` |
| `<\|--` | Kế thừa | `FallingView` kế thừa `TileView` |

**Stereotype:**

- `<<enumeration>>`: tập giá trị cố định.
- `<<module>>`: file chỉ chứa hàm, không tạo object.
- `<<abstract>>`: lớp cha, không tạo trực tiếp.

## 3. Cấu trúc thư mục (đã cập nhật)

```
bloxorz-solver/
└── Source/
    ├── main.py                     [CHỈNH SỬA] nạp map txt, tạo Game, mở Window
    ├── requirements.txt            [CHỈNH SỬA] pygame, PyOpenGL, PyOpenGL_accelerate, matplotlib
    ├── README.md
    ├── core/                       TV1
    │   ├── __init__.py
    │   ├── board.py                [CHỈNH SỬA] thêm symbols, goal_pos, switch_group, bridge_cells, bridge_groups
    │   ├── state.py                [CHỈNH SỬA] Orientation là IntEnum, bỏ order=True
    │   ├── block.py                [THU GỌN] chỉ còn Direction, bỏ class Block
    │   ├── transition.py           [CHỈNH SỬA] thêm pressed_switches, apply_move; bỏ get_next_state; switch_group đã chuyển sang board.py
    │   ├── game.py                 [MỚI] trạng thái ván: state, moves, status, history
    │   └── map_loader.py           [CHỈNH SỬA] đọc map txt, phân loại ký hiệu, kiểm tra liên kết công tắc và cầu
    ├── gui/                        TV2
    │   ├── __init__.py
    │   ├── window.py               [CHỈNH SỬA] vòng lặp sự kiện, gọi Game, không chứa luật
    │   ├── renderer.py             [CHỈNH SỬA] vẽ map (display list), khối, cầu
    │   ├── primitives.py           [MỚI] draw_box, shade (tách khỏi renderer)
    │   ├── camera.py               [MỚI] OrbitCamera: xoay, pan, kẹp giới hạn
    │   ├── animator.py             [MỚI] nội suy lăn và rơi
    │   ├── replayer.py             [MỚI] phát lại lời giải trên một Game riêng
    │   ├── hud.py                  [MỚI] số bước, thời gian, tên màn
    │   ├── control_panel.py        [CHƯA VIẾT] New Game, Restart, Run Solver
    │   └── tiles/
    │       ├── __init__.py
    │       ├── base_tile.py        [MỚI] lớp cha TileView
    │       ├── falling.py          [ĐỔI TÊN từ fragile.py] ô O
    │       ├── switch.py           [CHỈNH SỬA] công tắc soft và heavy
    │       └── bridge.py           [CHỈNH SỬA] cầu đóng và mở
    ├── algorithms/                 TV3, TV4
    │   ├── __init__.py
    │   ├── base_solver.py          [CHƯA VIẾT] SolveResult, BaseSolver
    │   ├── bfs.py                  [CHƯA VIẾT] TV3
    │   ├── dfs.py                  [CHƯA VIẾT] TV3, DFS và IDS
    │   ├── ucs.py                  [CHƯA VIẾT] TV3, chi phí không đồng nhất
    │   ├── astar.py                [CHƯA VIẾT] TV4
    │   └── heuristic.py            [CHƯA VIẾT] TV4
    ├── data/                       TV5
    │   ├── maps/                   [ĐỔI] *.txt, bỏ JSON
    │   │   ├── level0.txt          [ĐÃ CÓ]
    │   │   └── level1.txt ...      [CHƯA VIẾT]
    │   └── logs/                   [CHƯA VIẾT] CSV kết quả
    ├── experiments/                TV5
    │   ├── __init__.py
    │   ├── run_experiments.py      [CHƯA VIẾT]
    │   └── plot_results.py         [CHƯA VIẾT]
    ├── tests/
    │   ├── test_map_loader.py      [MỚI] TV1
    │   ├── test_transition.py      [CHỈNH SỬA] TV1, thêm test công tắc
    │   ├── test_game.py            [MỚI] TV1
    │   └── test_solvers.py         [CHƯA VIẾT] TV3, TV4
    ├── Report.pdf                  TV5 chủ trì
    └── README.md                   TV5 và TV1
```

## 4. Quyết định thiết kế đã chốt

Các điểm dưới đây đã được giải quyết trong baseline. Nếu nhóm muốn đổi, hãy sửa README này trước rồi mới sửa code.

| Vấn đề | Quyết định | Lý do |
|---|---|---|
| Công tắc điều khiển cầu nào | Công tắc chữ hoa `X` điều khiển nhóm cầu chữ thường `x`. Công tắc số `d` điều khiển nhóm cầu chữ thứ `d` (`0` là `a`, ..., `9` là `j`) | ĐÃ CHỐT. Quy tắc đơn giản, nhìn map là biết. Đã kiểm chứng trên 8 map có công tắc, tất cả đều khớp. Loader kiểm tra hai chiều, không cần file metadata riêng |
| Khi nào công tắc kích hoạt | Khi khối vừa chạm vào ô công tắc, không phải khi khối đang đứng yên trên đó. Soft kích hoạt ở mọi tư thế. Heavy chỉ kích hoạt khi khối đứng thẳng | Không cần lưu trạng thái công tắc trong `State`, nên trạng thái vẫn so sánh và băm được cho solver |
| Mỗi lần kích hoạt thì làm gì | Lật (toggle) trạng thái mọi cầu trong nhóm | Khớp với cách chơi gốc |
| Cầu lúc bắt đầu | Tất cả cầu đều đóng | Map txt chưa có chỗ khai báo cầu mở. Cần xác nhận, xem mục 9 |
| Khối rơi khi nào | Ra ngoài lưới, đứng thẳng trên ô `O`, hoặc nằm trên cầu đang đóng sau khi cầu được lật | Chỉ có một hàm `is_valid_state` quyết định, không rải luật ở nơi khác |
| Split switch | ĐÃ CHỐT: làm ở mốc 5 như tùy chọn, chỉ sau khi mốc 1 đến 4 ổn định | Phải đổi `State` từ một khối thành nhiều khối, ảnh hưởng toàn bộ code. Bảng ký hiệu cũng chưa có ký hiệu cho nó |
| Class `Block` | Xóa. `Direction` giữ trong `block.py` | `Block` trùng với `State`, làm có hai nguồn sự thật |
| `Orientation` | Dùng `IntEnum` và bỏ `order=True` khỏi `State` | Enum thường không so sánh được, dẫn đến lỗi khi UCS và A* dùng `heapq` |
| Kết quả nước đi | `MoveResult` chỉ có `OK` và `FALL`. Thắng được suy ra từ `is_goal_state` sau nước `OK` | Ít trạng thái, không trùng lặp |
| Trạng thái ván | Lớp `Game` trong `core` giữ `state`, `moves`, `status`, `history` | Luật chơi không nằm trong GUI |
| Thời gian | Do GUI đo. Không thuộc `core` | Solver không cần thời gian ván chơi |
| Đo bộ nhớ | `tracemalloc` của thư viện chuẩn, không dùng `psutil` | Đo đúng bộ nhớ Python, ổn định giữa các lần chạy |
| Giới hạn tìm kiếm | `node_limit` trong `BaseSolver` | Tránh chạy vô hạn trên map khó |
| Định dạng map | `.txt`, bỏ JSON | Khớp với file `level0.txt` đã có |
| Liên kết công tắc và cầu | Đọc theo quy tắc: chữ hoa `X` điều khiển `x`, số `d` điều khiển chữ thứ `d`. Không dùng file metadata riêng. Loader kiểm tra hai chiều và báo lỗi khi lệch | Lỗi được phát hiện ngay khi nạp map, không đợi đến lúc chạy |
| Số lượng map | 25 map: 13 map riêng và 12 map tách từ `zlevel120.txt` (đang chờ tách file) | Đủ cho thực nghiệm, có cả map đơn giản và map có nhiều công tắc |
| `requirements.txt` | Bỏ `customtkinter` | Không dùng |

## 5. Ý tưởng kỹ thuật cần nắm

### 5.1. Ba tầng và hàm thuần

Dự án chia làm ba tầng: `core` (luật chơi), `gui` (hiển thị và nhập liệu), `algorithms` (tìm lời giải). Tầng `core` không import pygame hay OpenGL. Các hàm trong `transition.py` là hàm thuần: cùng đầu vào thì luôn cho cùng đầu ra, không thay đổi gì bên ngoài. Nhờ vậy cùng một hàm `apply_move` được dùng cho game, cho solver và cho test, không cần viết lại luật ở ba nơi.

### 5.2. `State` bất biến

`State` là `dataclass(frozen=True)`. Khi cần trạng thái mới, tạo object mới, không sửa object cũ. Điều này có ba lợi ích:

- Solver có thể đưa `State` vào `set` để kiểm tra đã thăm chưa, vì object băm được.
- Có thể lưu lịch sử để undo mà không sợ bị sửa ngầm.
- Animator giữ được trạng thái cũ để vẽ chuyển động, trong khi `Game` đã có trạng thái mới.

Lưu ý: `active_bridges` phải là `frozenset`, không phải `set`, để băm được.

### 5.3. Logic công tắc

Ý tưởng cốt lõi: công tắc không lưu trạng thái. Thay vào đó, so sánh tập công tắc đang bị nhấn trước và sau nước đi. Công tắc nào mới bị nhấn thì lật nhóm cầu tương ứng. Cách này gọi là kích hoạt theo cạnh, và có ba ưu điểm: `State` gọn, không có trạng thái công tắc để đồng bộ, và solver không phải theo dõi thêm gì.

Ví dụ: khối đang đứng ở ô `(2, 3)` không có công tắc. Sau khi lăn sang phải, khối phủ lên ô `A` ở `(2, 4)`. Tập công tắc mới là `{(2, 4)}`, tập cũ là rỗng, nên công tắc `A` vừa được nhấn. Nhóm của `A` là `a`, nên mọi ô `a` trên map bị lật. Nếu một ô `a` đang đóng thì mở ra, và ngược lại.

Mã tham khảo cho TV1:

```python
# core/transition.py

# switch_group nằm trong core/board.py, xem phần ghi chú dưới đây


def pressed_switches(board, state) -> frozenset:
    """Tập ô công tắc đang bị khối nhấn. Heavy chỉ tính khi khối đứng thẳng."""
    pressed = set()
    for r, c in state.get_occupied_cells():
        tile = board.get_tile(r, c)
        if tile == TileType.SOFT_SWITCH:
            pressed.add((r, c))
        elif tile == TileType.HEAVY_SWITCH and state.orientation == Orientation.STANDING:
            pressed.add((r, c))
    return frozenset(pressed)


def apply_move(board, state, direction) -> MoveOutcome:
    candidate = raw_next_state(state, direction)

    # Chỉ công tắc mới bị nhấn trong nước này mới lật cầu
    newly = pressed_switches(board, candidate) - pressed_switches(board, state)
    bridges = set(state.active_bridges)
    for r, c in newly:
        group = switch_group(board.get_symbol(r, c))
        for cell in board.bridge_cells(group):
            bridges ^= {cell}  # lật trạng thái của ô cầu

    final = State(candidate.r, candidate.c, candidate.orientation, frozenset(bridges))
    if is_valid_state(board, final):
        return MoveOutcome(MoveResult.OK, final)
    return MoveOutcome(MoveResult.FALL, final)  # final vẫn dùng để vẽ hoạt cảnh rơi
```

Lưu ý: `switch_group` không nằm trong `transition.py` mà nằm trong `board.py`, vì `map_loader` cũng cần dùng để kiểm tra liên kết công tắc và cầu. `transition.py` chỉ import từ đó.

Lưu ý: `is_valid_state` nhận `final` đã có cầu mới. Vì vậy nếu nước đi làm một cầu đóng ngay dưới khối, khối sẽ rơi. Đây là hành vi đúng của game.

Trường hợp hai công tắc cùng điều khiển một nhóm cầu (level 8 và level 11) vẫn chưa được nhóm xác nhận. Nếu có, nhấn cả hai sẽ lật cầu hai lần, và cầu trở về trạng thái cũ. Xem mục 9.

### 5.4. Trạng thái ván và animation

`Game` cập nhật trạng thái ngay khi nhận nước đi. `Animator` chỉ là lớp hiển thị: nó nhận trạng thái cũ, hướng lăn, và tự nội suy trong vài trăm mili-giây. Khi `Animator` đang chạy, `Renderer` vẽ khối từ `animator.old_state` đã biến đổi, còn không thì vẽ từ `game.state`.

Trong lúc animation đang chạy, `Window` bỏ qua phím mũi tên. Đây là cách đơn giản nhất để người chơi không thể bấm lúc khối đang lăn. Nếu kết quả là `FALL`, `Game` giữ nguyên `state` cũ, đặt `status = LOST`, và `Animator` chạy hoạt cảnh rơi dựa trên `outcome.state`. Khi animation xong, `Window` mới hiện màn thua.

Khi `Game` đã WON hoặc LOST, nước đi mới bị bỏ qua.

### 5.5. Lăn khối và rơi

Khối lăn quanh một cạnh đáy ở phía trước theo hướng di chuyển. Với mỗi hướng có một điểm xoay và một trục:

| Hướng | Điểm xoay | Trục | Góc cuối |
|---|---|---|---|
| RIGHT | cạnh `x1` | Z | -90° |
| LEFT | cạnh `x0` | Z | +90° |
| DOWN | cạnh `z1` | X | +90° |
| UP | cạnh `z0` | X | -90° |

Ta dùng `glRotatef` quanh điểm xoay, nghĩa là dịch điểm xoay về gốc, xoay, rồi dịch ngược lại. Góc được nội suy bằng hàm `ease_in_out(t) = t² (3 - 2t)` để chuyển động có đà.

Khi rơi, sau khi lật xong thì khối tịnh tiến xuống theo hàm bình phương của thời gian, để trông như đang rơi thật.

### 5.6. Camera

Camera có bốn kỹ thuật, lấy cảm hứng từ `main.c` của repo tham khảo nhưng viết lại theo cách của nhóm:

1. **Tự căn theo map.** Khoảng cách camera tỷ lệ với `max(rows, cols)`, có mức tối thiểu để map nhỏ không bị phóng quá to.
2. **Xoay bằng tọa độ cầu.** Lưu bán kính `radius`, góc ngang `angle_xz`, góc đứng `angle_y`. Chuột thay đổi hai góc, rồi đổi lại thành tọa độ `x, y, z`. Góc đứng bị kẹp trong khoảng ±1.4 rad để camera không lật qua đỉnh. Bán kính bị kẹp trong khoảng hợp lý quanh kích thước map.
3. **Pan theo hướng nhìn.** Vector "trước" là hướng từ camera đến điểm nhìn, chiếu xuống mặt phẳng XZ. Vector "phải" vuông góc với nó. Phím di chuyển cộng hoặc trừ vector này vào cả vị trí và điểm nhìn. Điểm nhìn bị kẹp trong biên map cộng với một khoảng đệm.
4. **Tốc độ theo thời gian thực.** Tốc độ pan và xoay nhân với `dt` (thời gian của khung hình), không phải số cố định mỗi khung. Nếu không, máy FPS cao sẽ di chuyển nhanh hơn máy FPS thấp.

### 5.7. Vẽ ô rõ nét

- **Shading theo mặt.** Mỗi mặt của hộp có một hệ số độ sáng: mặt trên sáng nhất, mặt bên tối hơn, mặt đáy tối nhất. Đây là cách đơn giản nhất để khối có chiều sâu mà không cần ánh sáng thật.
- **Khe giữa các ô.** Vẽ mỗi ô nhỏ hơn ô lưới một chút. Phần trống giữa các ô lộ nền tối và tạo cảm giác tách biệt.
- **Viền.** Vẽ thêm `GL_LINE_LOOP` cho từng mặt. Để viền không bị lẫn với mặt, dùng `glPolygonOffset` đẩy mặt ra sau một chút.
- **Display list cho bản đồ.** Bản đồ không đổi trong màn chơi, nên vẽ một lần vào display list, rồi mỗi khung chỉ gọi `glCallList`. Khối và cầu vẫn vẽ trực tiếp vì chúng thay đổi.
- **Khử răng cưa.** Bật multisample trước khi tạo cửa sổ.

### 5.8. Đo lường solver

Mỗi solver đo cùng bốn chỉ số, theo cùng một cách, để so sánh công bằng:

- **Thời gian:** `time.perf_counter()` trước và sau khi chạy.
- **Bộ nhớ đỉnh:** `tracemalloc.start()` trước khi chạy, và `tracemalloc.get_traced_memory()[1]` sau khi chạy.
- **Số nút đã mở rộng:** đếm số lần lấy một trạng thái ra khỏi frontier và sinh các trạng thái con. Cần định nghĩa đúng một lần trong `BaseSolver` và dùng chung.
- **Độ dài lời giải:** số nước trong `path`, hoặc `None` nếu không tìm thấy.

Mọi solver nhận `node_limit`. Nếu vượt quá, dừng và trả về `found = False`, để thí nghiệm không bị treo.

### 5.9. Heuristic phải chấp nhận được

Một heuristic chấp nhận được (admissible) không bao giờ đánh giá cao hơn chi phí thật để đến đích. Nếu không, A* có thể bỏ qua lời giải tối ưu.

Cách kiểm tra đơn giản nhất: trên một map nhỏ, chạy BFS từ trạng thái đầu để có khoảng cách thật `dist(s)` cho mọi trạng thái đạt được. Sau đó với mọi `s`, kiểm tra `h(s) <= dist(s)`. Kiểm tra này nên nằm trong `test_solvers.py`.

Manhattan chia cho 2 chỉ là một đề xuất, TV4 phải chứng minh hoặc kiểm tra bằng test như trên.

## 6. Phân công và điều kiện hoàn thành từng mốc

| Mốc | Nội dung | Người phụ trách | Hoàn thành khi |
|---|---|---|---|
| 0 | Chốt thiết kế | Cả nhóm | Không còn câu hỏi nào trong mục 4 và 9 chưa có người quyết |
| 1 | Core: map loader, transition, game | TV1 | `test_map_loader`, `test_transition`, `test_game` pass. Nạp được mọi map txt, liên kết công tắc và cầu hợp lệ trên 25 map |
| 2 | GUI cơ bản: renderer, camera, primitives | TV2 | Vẽ được map, khối, di chuyển bằng phím. Chạy ổn định ở 60 FPS trên map cỡ 15 x 10 |
| 3 | Solver: BFS, DFS, UCS, A*, heuristic | TV3 và TV4 | Giải được `level0` và ít nhất ba map khác, trong đó có ít nhất một map có công tắc. UCS dùng chi phí do TV3 quyết định, xem mục 9. `test_solvers` pass, kiểm tra admissible pass |
| 4 | Animation, replayer, HUD, control panel | TV2 | Lăn, rơi, thắng, thua đều có màn hình. Replay lời giải của solver chạy đúng |
| 5 | Thực nghiệm trên 25 map. Split switch là tùy chọn | TV5, và TV1 nếu làm split | Có CSV và bốn biểu đồ cho 25 map. Split chỉ làm khi mốc 1 đến 4 đã ổn định, và không làm hỏng kết quả của các map cũ |
| 6 | Hoàn thiện | Cả nhóm | Report, video demo, README chạy được trên máy sạch |

Mốc 3 có thể bắt đầu song song với mốc 2, vì solver chỉ cần `core`.

## 7. Kiểm thử tối thiểu

- `test_map_loader.py`: ký tự lạ báo lỗi, thiếu S hoặc T báo lỗi, dòng lệch độ dài báo lỗi, map hợp lệ thì parse đúng. Công tắc không có cầu hoặc cầu không có công tắc báo lỗi. Công tắc chữ và công tắc số khớp đúng nhóm cầu.
- `test_transition.py`: lăn đúng ở mọi hướng, rơi khi ra ngoài lưới, rơi khi đứng thẳng trên `O`, heavy chỉ kích hoạt khi đứng thẳng, soft kích hoạt ở mọi tư thế, lật cầu đúng nhóm, rơi khi cầu đóng dưới khối.
- `test_game.py`: nước `OK` tăng `moves`, nước `FALL` không tăng `moves` và đặt `LOST`, đến đích thì `WON`, sau `WON` hoặc `LOST` thì nước đi bị bỏ qua, `restart` đưa về trạng thái đầu.
- `test_solvers.py`: lời giải của mỗi solver khi áp dụng lên map thì đến đích. Heuristic chấp nhận được.

## 8. Cách cập nhật baseline

Khi đổi một quyết định:

1. Sửa mục 4 của README này trước, ghi rõ lý do.
2. Sửa sơ đồ lớp nếu có class hoặc quan hệ thay đổi.
3. Sửa sơ đồ luồng nếu thứ tự xử lý thay đổi.
4. Báo cả nhóm trước khi merge.

Không sửa code của người khác mà không báo. Nếu cần đổi `core`, báo TV1, vì mọi nhóm đều phụ thuộc vào đó.