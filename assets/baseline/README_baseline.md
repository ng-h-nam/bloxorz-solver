# Baseline dự án Bloxorz: hướng dẫn đọc và ý tưởng kỹ thuật

Tài liệu này giải thích cách đọc các sơ đồ baseline, những quyết định thiết kế đã chốt, và các ý tưởng kỹ thuật cả nhóm cần nắm. Baseline phản ánh **code core đã gửi ngày 20/10** và **đề bài (file PDF CSC14003 Project 1), bắt buộc tuân thủ**.

## 1. Các sơ đồ trong baseline

Có năm sơ đồ Mermaid trong thư mục `baseline_mermaid/`, và lịch ở `timeline_v2.mmd`. Dán nội dung từng file vào https://mermaid.live để xem. Cả sáu file đều đã được kiểm tra cú pháp bằng trình phân tích của Mermaid.

| File | Trả lời câu hỏi |
|---|---|
| `1_class_diagram.mmd` | Có những class nào, thuộc nhóm nào, quan hệ với nhau ra sao |
| `2_switch_logic.mmd` | Một nước đi được xử lý thế nào khi có công tắc và cầu |
| `3_runtime_flow.mmd` | Khi người chơi bấm phím hoặc bấm Run Solver thì chuyện gì xảy ra |
| `4_experiments.mmd` | Từ map đến biểu đồ so sánh các thuật toán |
| `5_roadmap.mmd` | Các giai đoạn và cổng kiểm soát |
| `timeline_v2.mmd` | Sơ đồ Gantt theo thành viên (bản có tô màu theo trạng thái là `Bloxorz_Gantt_Tracker.xlsx`) |

## 2. Cách đọc ký hiệu

**Namespace** là nhóm phụ trách. Các class nằm trong `TV1_Core` do TV1 làm, `TV2_GUI` do TV2, `TV34_Algorithms` do TV3 và TV4, `TV5_Experiments` do TV5.

**Nhãn trạng thái** nằm trong `note` của sơ đồ lớp và trong cây thư mục:

- `[ĐÃ CÓ]`: đã có trong code đã gửi.
- `[CHƯA CÓ]`: chưa có trong code, hoặc file hiện còn rỗng.

Class không có nhãn là class đã có trong code.

**Ký hiệu quan hệ giữa các class:**

| Ký hiệu | Nghĩa | Ví dụ |
|---|---|---|
| `*--` | Sở hữu, sống cùng vòng đời | `Game` sở hữu `State` |
| `o--` | Tham chiếu, không sở hữu | `Window` giữ `Animator` |
| `-->` | Tham chiếu lâu dài | `Window` biết `Game` |
| `..>` | Phụ thuộc: dùng, nhận tham số, trả về | `Game` dùng `get_next_state` |
| `<\|--` | Kế thừa | `FragileView` kế thừa `TileView` |

**Stereotype:** `<<enumeration>>` là tập giá trị cố định; `<<dataclass>>` là lớp dữ liệu; `<<module>>` là file chỉ chứa hàm, không tạo object; `<<abstract>>` là lớp cha, không tạo trực tiếp.

## 3. Cấu trúc thư mục

```text
MSSV1_MSSV2_.../
├── Report.pdf                      TV5 chủ trì; có link video; nằm cạnh Source/ (đề bài mục 4)
└── Source/
    ├── main.py                     [ĐÃ CÓ] nạp map, tạo Game, mở Window
    ├── requirements.txt            pygame, PyOpenGL, PyOpenGL_accelerate, matplotlib
    ├── README.md                   TV5 và TV1: cách cài và chạy
    ├── core/                       TV1
    │   ├── __init__.py
    │   ├── state.py                [ĐÃ CÓ] State (có SPLIT), Orientation, Coordinates
    │   ├── block.py                [ĐÃ CÓ] Direction, Block (adapter đồng bộ với State)
    │   ├── board.py                [ĐÃ CÓ] TileType, Board, BridgeMode, BridgeAction, BridgeMetadata, SwitchMetadata
    │   ├── transition.py           [ĐÃ CÓ] TRANSITION_TABLE, get_next_state, get_successors
    │   ├── map_loader.py           [ĐÃ CÓ] classify, parse_level, load_level, đọc metadata
    │   └── game.py                 [CHƯA CÓ] Game, GameStatus, MoveOutcome
    ├── gui/                        TV2
    │   ├── __init__.py
    │   ├── window.py               [ĐÃ CÓ] Window
    │   ├── renderer.py             [ĐÃ CÓ] Renderer, draw_box, block_bounds
    │   ├── control_panel.py        [ĐÃ CÓ] ControlPanel, Button, TextLabel (mới có nút Restart)
    │   ├── animator.py             [CHƯA CÓ] nội suy lăn và rơi
    │   ├── replayer.py             [CHƯA CÓ] phát lại lời giải trên một Game riêng
    │   ├── hud.py                  [CHƯA CÓ] số bước, thời gian, tên màn
    │   ├── camera.py               [CHƯA CÓ] OrbitCamera (tùy chọn)
    │   └── tiles/
    │       ├── __init__.py
    │       ├── base_tile.py        [CHƯA CÓ] lớp cha TileView
    │       ├── fragile.py          [CHƯA CÓ] hiện là file rỗng; FragileView vẽ ô O
    │       ├── switch.py           [CHƯA CÓ] hiện là file rỗng; SwitchView cho soft, heavy, split
    │       └── bridge.py           [CHƯA CÓ] hiện là file rỗng; BridgeView
    ├── algorithms/                 TV3, TV4
    │   ├── __init__.py
    │   ├── base_solver.py          [CHƯA CÓ] SolveResult, BaseSolver
    │   ├── bfs.py                  [CHƯA CÓ] TV3
    │   ├── dfs.py                  [CHƯA CÓ] TV3, DFS hoặc IDS
    │   ├── ucs.py                  [CHƯA CÓ] TV3, chi phí không đồng nhất
    │   ├── astar.py                [CHƯA CÓ] TV4
    │   └── heuristic.py            [CHƯA CÓ] TV4
    ├── data/
    │   ├── maps/                   TV5: *.txt, 13 map hiện có (level0 đến level12)
    │   └── logs/                   [CHƯA CÓ] CSV kết quả
    ├── experiments/                TV5
    │   ├── run_experiments.py      [CHƯA CÓ]
    │   └── plot_results.py         [CHƯA CÓ]
    ├── docs/
    │   ├── README_MAP.md           [ĐÃ CÓ] yêu cầu của đề bài về map và cách đọc map
    │   ├── BAO_CAO_KIEM_THU.md     [ĐÃ CÓ] kết quả kiểm thử core và 13 map
    │   ├── decisions.md            [CHƯA CÓ] biên bản họp chốt quyết định
    │   ├── api_contract.md         [CHƯA CÓ] hợp đồng API của core
    │   └── ai_usage_log.md         [CHƯA CÓ] nhật ký dùng AI (đề bài yêu cầu trong phụ lục)
    └── tests/
        ├── test_maps.py            [ĐÃ CÓ] bản nháp trong tests_kiem_thu/: nạp map, BFS, bất biến
        ├── test_rules.py           [ĐÃ CÓ] bản nháp trong tests_kiem_thu/: luật nâng cao theo đề bài
        ├── test_meta.py            [ĐÃ CÓ] bản nháp trong tests_kiem_thu/: đọc metadata
        ├── test_transition.py      [CHƯA CÓ] TV4 viết theo đề bài (xem ROADMAP_v2.md)
        ├── test_game.py            [CHƯA CÓ] TV1
        └── test_solvers.py         [CHƯA CÓ] TV3, TV4
```

`level0.txt` và `level0_1.txt` có nội dung giống hệt nhau; chỉ giữ một file.

## 4. Quyết định thiết kế đã chốt

Nếu nhóm muốn đổi một quyết định, sửa README này trước rồi mới sửa code. Các yêu cầu của đề bài là bắt buộc và không nằm trong danh sách "có thể đổi".

| Vấn đề | Quyết định | Lý do |
|---|---|---|
| Liên kết công tắc và cầu | Chữ hoa `X` điều khiển nhóm cầu `x`. Chữ số `d` điều khiển nhóm cầu là chữ cái thứ `d` (`0` là `a`, ..., `9` là `j`). Mọi ô cầu cùng chữ thuộc cùng một nhóm | Đã chốt. Nhìn map là biết; khớp cả 13 map hiện có |
| Hai công tắc cùng điều khiển một nhóm cầu | Giữ nguyên (level8: `A` và `0`; level11: `B` và `1`). Hiệu ứng toggle chồng lên nhau | Đề bài không cấm; cả hai map đều giải được |
| Khi nào công tắc kích hoạt | Khi khối chạm vào ô công tắc. Soft: mọi tư thế. Heavy: chỉ khi khối đứng thẳng. Khối đơn chỉ kích hoạt được soft | Đề bài mục 2.5 |
| Chế độ tác động lên cầu | Mặc định toggle. Permanent (`OPEN`, `CLOSE`) khai báo trong metadata sau dòng `---`, ví dụ `SWITCH id=A targets=a:on` | Đề bài mục 2.5 yêu cầu cả hai chế độ. Dùng cú pháp có sẵn trong code |
| Cầu lúc bắt đầu | Tất cả cầu đều đóng | Map txt không khai báo cầu mở |
| Khi nào khối rơi | Ra ngoài lưới, trên ô trống, đứng thẳng trên ô `O`, hoặc nằm trên cầu đóng. Kể cả khi cầu vừa bị công tắc đóng ngay dưới chân khối: kiểm tra hợp lệ lại sau khi công tắc đổi cầu | Đề bài mục 2.3: khối luôn phải được sàn đỡ hoàn toàn |
| Ô `O` | Tên `FRAGILE` theo đề bài. Khối nguyên: đứng thẳng thì rơi, nằm thì an toàn. Khối đơn 1×1×1 đứng trên `O` không rơi | Đề bài mục 2.5. Đề bài không nêu trường hợp khối đơn; ghi vào báo cáo |
| Công tắc tách khối | Bắt buộc. Ký hiệu `U`. Đứng thẳng trên `U` thì tách thành hai khối đơn tại vị trí khai báo bằng `SPLIT` trong metadata. Điều khiển lần lượt từng khối (hành động `SWITCH`, phím cách), gộp lại khi hai khối ở hai ô kề nhau. Khối đơn không thắng | Đề bài mục 2.5 |
| Class `Block` | Giữ như code: adapter đồng bộ với `State` (`from_state`, `to_state`). `State` là nguồn dữ liệu chính; `transition` chưa dùng `Block` | Đã chốt |
| `State` | Dataclass bất biến, gồm cả `split_pos` và `active_cube`. `to_key()` là khóa so sánh và băm cho solver | Dùng được với `set` và `heapq` |
| Kết quả nước đi | Hiện `get_next_state` trả `State` hoặc `None` (`None` là không hợp lệ hoặc rơi). Lớp `Game` (chưa có) bọc thành `MoveOutcome` với `MoveResult` là `OK` hoặc `FALL` để GUI có dữ liệu diễn hoạt cảnh rơi. Thắng suy ra từ `is_goal_state` | Ít trạng thái, không trùng lặp |
| Hành động | `Direction` hoặc chuỗi (`UP`, `DOWN`, `LEFT`, `RIGHT`, `SWITCH`). `get_successors` trả danh sách (chuỗi, `State`). Đường đi của solver là danh sách chuỗi | Khớp code |
| Trạng thái ván | Lớp `Game` trong `core` giữ `state`, `moves`, `status`, `history` (chưa có) | Luật chơi không nằm trong GUI |
| Định dạng map | `.txt`. Hàng ngắn hơn hàng dài nhất được đệm ô trống `.` bên phải. Phần sau dòng `---` là metadata | Đề bài mục 3.1 yêu cầu định dạng văn bản hoặc JSON đơn giản |
| Bộ map | 13 map riêng, chia nhóm A đến E (xem `README_MAP.md` mục 4). Cần tạo thêm map nhóm E, map cầu permanent, và 1 map mỗi nhóm B, D | Nhóm đã xác nhận 13 map; hiện thiếu split và permanent |
| Thời gian | Do GUI đo. Không thuộc `core` | Solver không cần thời gian ván chơi |
| Đo bộ nhớ | `tracemalloc` của thư viện chuẩn, không dùng `psutil` | Đo đúng bộ nhớ Python, ổn định giữa các lần chạy |
| Giới hạn tìm kiếm | `node_limit` trong `BaseSolver` | Tránh chạy vô hạn trên map khó |
| Thư viện | pygame và PyOpenGL cho GUI; `requirements.txt` bỏ `customtkinter` | Đề bài mục 3 cho phép dùng thư viện hỗ trợ (ví dụ cho GUI); các thuật toán tìm kiếm phải tự cài đặt |

## 5. Ý tưởng kỹ thuật cần nắm

### 5.1. Ba tầng và hàm thuần

Dự án chia làm ba tầng: `core` (luật chơi), `gui` (hiển thị và nhập liệu), `algorithms` (tìm lời giải). Tầng `core` không import pygame hay OpenGL. Các hàm trong `transition.py` nên là hàm thuần: khi được truyền đủ `state`, `action`, `board` thì cùng đầu vào luôn cho cùng đầu ra, không thay đổi gì bên ngoài. Nhờ vậy cùng một hàm `get_next_state` được dùng cho game, cho solver và cho test, không cần viết lại luật ở ba nơi.

### 5.2. `State` bất biến

`State` là `dataclass(frozen=True)`. Khi cần trạng thái mới, tạo object mới, không sửa object cũ. Điều này có ba lợi ích:

- Solver có thể đưa `State` vào `set` để kiểm tra đã thăm chưa, vì object băm được.
- Có thể lưu lịch sử để undo mà không sợ bị sửa ngầm.
- Animator giữ được trạng thái cũ để vẽ chuyển động, trong khi `Game` đã có trạng thái mới.

Lưu ý: `active_bridges` phải là `frozenset`, không phải `set`, để băm được.

`State` còn có hai trường cho trạng thái tách khối là `split_pos` và `active_cube`, và `to_key()` gồm cả hai, nên hai trạng thái khác nhau không bị gộp nhầm khi đưa vào tập đã thăm.

### 5.3. Logic công tắc và cầu

Công tắc không lưu trạng thái. Trạng thái đóng hoặc mở của cầu nằm trong `State.active_bridges`. Luật nằm trong `get_next_state` (file `transition.py`) và `Board.apply_switch` (file `board.py`). Sơ đồ chi tiết ở `2_switch_logic.mmd`.

Một nước đi của khối nguyên:

1. Tính trạng thái ứng viên từ `TRANSITION_TABLE`.
2. Kiểm tra hợp lệ với tập cầu hiện tại (`Board.is_valid_move`). Sai thì trả về `None`.
3. Với mỗi ô mà khối chiếm: ô soft thì kích hoạt; ô heavy và khối đứng thẳng thì kích hoạt; ô `U` và khối đứng thẳng thì tách khối (mục 5.4).
4. `Board.apply_switch` áp dụng danh sách `BridgeAction` của công tắc lên tập cầu: `TOGGLE` đảo trạng thái, `OPEN` thêm vào tập mở, `CLOSE` bỏ ra. Kết quả là một `frozenset` mới.
5. Kiểm tra hợp lệ lại với tập cầu mới. Sai (cầu vừa đóng ngay dưới chân khối) thì trả về `None`.

Ví dụ: khối đứng ở `(2, 3)` lăn sang phải, nằm ngang phủ hai ô `(2, 4)` và `(2, 5)`. Nếu `(2, 4)` là công tắc soft `A` thì nhóm cầu `a` đổi trạng thái: ô `a` đang đóng thì mở, đang mở thì đóng. Khi đó bước 5 kiểm tra khối không đang nằm trên một ô `a` vừa đóng.

Cách công tắc nối với cầu: theo quy tắc ở mục 4 (chữ hoa `X` điều khiển `x`, số `d` điều khiển chữ thứ `d`), hoặc khai báo tường minh trong metadata của map. Metadata còn dùng để đặt chế độ permanent. Cú pháp và ví dụ nằm ở `README_MAP.md` mục 1.5.

### 5.4. Tách và gộp khối

- **Tách.** Khối đứng thẳng trên ô `U` thì chuyển sang `orientation = SPLIT`. `(r, c)` là khối số 0, `split_pos` là khối số 1, `active_cube = 0`. Vị trí hai khối lấy từ `board.splits[(r, c)]`, khai báo bằng `SPLIT pos=r,c target1=r,c target2=r,c`. Nếu map chưa khai báo thì code dùng ô bên trái và bên phải của `U`; map chính thức nên khai báo để đúng yêu cầu "vị trí định sẵn" của đề bài.
- **Điều khiển.** Mũi tên di chuyển khối đang điều khiển đúng một ô (`SINGLE_CUBE_DELTA`). Hành động `SWITCH` (phím cách) đổi `active_cube`.
- **Gộp.** Khi hai khối ở hai ô kề nhau, `normalize_or_merge` gộp lại thành khối 1×1×2 nằm ngang hoặc nằm dọc, `split_pos = None`.
- **Quy tắc của khối đơn.** Kích hoạt được công tắc soft; không kích hoạt được heavy; không thắng khi đứng trên ô đích; rơi nếu ra ngoài, trên ô trống hoặc trên cầu đóng; không rơi khi đứng trên ô `O`.
- **Với solver.** Ở trạng thái `SPLIT`, `get_successors` có thêm hành động `SWITCH`. Heuristic và hàm chi phí cũng phải xử lý trạng thái `SPLIT`.

### 5.5. Trạng thái ván và animation

Phần này mô tả thiết kế dự kiến; `Game`, `MoveOutcome` và `Animator` chưa có trong code.

`Game` cập nhật trạng thái ngay khi nhận nước đi. `Animator` chỉ là lớp hiển thị: nó nhận trạng thái cũ, hướng lăn, và tự nội suy trong vài trăm mili-giây. Khi `Animator` đang chạy, `Renderer` vẽ khối từ `animator.old_state` đã biến đổi, còn không thì vẽ từ `game.state`.

Trong lúc animation đang chạy, `Window` bỏ qua phím mũi tên. Đây là cách đơn giản nhất để người chơi không thể bấm lúc khối đang lăn. Nếu kết quả là `FALL`, `Game` giữ nguyên `state` cũ, đặt `status = LOST`, và `Animator` chạy hoạt cảnh rơi dựa trên `outcome.state`. Khi animation xong, `Window` mới hiện màn thua.

Khi `Game` đã WON hoặc LOST, nước đi mới bị bỏ qua.

### 5.6. Lăn khối và rơi

Khối lăn quanh một cạnh đáy ở phía trước theo hướng di chuyển. Với mỗi hướng có một điểm xoay và một trục:

| Hướng | Điểm xoay | Trục | Góc cuối |
|---|---|---|---|
| RIGHT | cạnh `x1` | Z | -90° |
| LEFT | cạnh `x0` | Z | +90° |
| DOWN | cạnh `z1` | X | +90° |
| UP | cạnh `z0` | X | -90° |

Ta dùng `glRotatef` quanh điểm xoay, nghĩa là dịch điểm xoay về gốc, xoay, rồi dịch ngược lại. Góc được nội suy bằng hàm `ease_in_out(t) = t² (3 - 2t)` để chuyển động có đà.

Khi rơi, sau khi lật xong thì khối tịnh tiến xuống theo hàm bình phương của thời gian, để trông như đang rơi thật.

### 5.7. Camera

Camera có bốn kỹ thuật, lấy cảm hứng từ `main.c` của repo tham khảo nhưng viết lại theo cách của nhóm:

1. **Tự căn theo map.** Khoảng cách camera tỷ lệ với `max(rows, cols)`, có mức tối thiểu để map nhỏ không bị phóng quá to.
2. **Xoay bằng tọa độ cầu.** Lưu bán kính `radius`, góc ngang `angle_xz`, góc đứng `angle_y`. Chuột thay đổi hai góc, rồi đổi lại thành tọa độ `x, y, z`. Góc đứng bị kẹp trong khoảng ±1.4 rad để camera không lật qua đỉnh. Bán kính bị kẹp trong khoảng hợp lý quanh kích thước map.
3. **Pan theo hướng nhìn.** Vector "trước" là hướng từ camera đến điểm nhìn, chiếu xuống mặt phẳng XZ. Vector "phải" vuông góc với nó. Phím di chuyển cộng hoặc trừ vector này vào cả vị trí và điểm nhìn. Điểm nhìn bị kẹp trong biên map cộng với một khoảng đệm.
4. **Tốc độ theo thời gian thực.** Tốc độ pan và xoay nhân với `dt` (thời gian của khung hình), không phải số cố định mỗi khung. Nếu không, máy FPS cao sẽ di chuyển nhanh hơn máy FPS thấp.

### 5.8. Vẽ ô rõ nét

- **Shading theo mặt.** Mỗi mặt của hộp có một hệ số độ sáng: mặt trên sáng nhất, mặt bên tối hơn, mặt đáy tối nhất. Đây là cách đơn giản nhất để khối có chiều sâu mà không cần ánh sáng thật.
- **Khe giữa các ô.** Vẽ mỗi ô nhỏ hơn ô lưới một chút. Phần trống giữa các ô lộ nền tối và tạo cảm giác tách biệt.
- **Viền.** Vẽ thêm `GL_LINE_LOOP` cho từng mặt. Để viền không bị lẫn với mặt, dùng `glPolygonOffset` đẩy mặt ra sau một chút.
- **Display list cho bản đồ.** Bản đồ không đổi trong màn chơi, nên vẽ một lần vào display list, rồi mỗi khung chỉ gọi `glCallList`. Khối và cầu vẫn vẽ trực tiếp vì chúng thay đổi.
- **Khử răng cưa.** Bật multisample trước khi tạo cửa sổ.

### 5.9. Đo lường solver

Mỗi solver đo cùng bốn chỉ số, theo cùng một cách, để so sánh công bằng:

- **Thời gian:** `time.perf_counter()` trước và sau khi chạy.
- **Bộ nhớ đỉnh:** `tracemalloc.start()` trước khi chạy, và `tracemalloc.get_traced_memory()[1]` sau khi chạy.
- **Số nút đã mở rộng:** đếm số lần lấy một trạng thái ra khỏi frontier và sinh các trạng thái con. Cần định nghĩa đúng một lần trong `BaseSolver` và dùng chung.
- **Độ dài lời giải:** số nước trong `path`, hoặc `None` nếu không tìm thấy.

Mọi solver nhận `node_limit`. Nếu vượt quá, dừng và trả về `found = False`, để thí nghiệm không bị treo.

### 5.10. Heuristic phải chấp nhận được

Một heuristic chấp nhận được (admissible) không bao giờ đánh giá cao hơn chi phí thật để đến đích. Nếu không, A* có thể bỏ qua lời giải tối ưu.

Cách kiểm tra đơn giản nhất: trên một map nhỏ, chạy BFS từ trạng thái đầu để có khoảng cách thật `dist(s)` cho mọi trạng thái đạt được. Sau đó với mọi `s`, kiểm tra `h(s) <= dist(s)`. Kiểm tra này nên nằm trong `test_solvers.py`.

Manhattan chia cho 2 chỉ là một đề xuất, TV4 phải chứng minh hoặc kiểm tra bằng test như trên.

## 6. Các giai đoạn và cổng kiểm soát

Lịch chi tiết ở `ROADMAP_v2.md`. Tóm tắt:

| Giai đoạn | Thời gian | Mục tiêu | Cổng cuối giai đoạn |
|---|---|---|---|
| 0. Ổn định nền | 19/10-20/10 | Core import được và có test. GUI và BFS chạy trên level0. Mọi quyết định thiết kế được ghi lại. | G0 (20/10): Core nạp được cả 13 map; pytest chạy và test transition pass; python main.py mở level0; BFS giải level0; quyết định mục 4 đã ghi lại |
| 1. Core đầy đủ và solver cơ bản | 21/10-22/10 | Core có đủ cơ chế nâng cao (fragile, cầu, ba loại công tắc, tách và gộp khối). BFS, DFS chạy được. GUI vẽ đủ loại ô. | G1 (22/10): Test tách, gộp, permanent, đổi khối pass; BFS và DFS giải được ít nhất 8 map bằng dòng lệnh; GUI hiện đủ loại ô |
| 2. Đủ tính năng và chạy từ đầu đến cuối | 23/10-25/10 | Bốn solver chạy được trên bộ map. GUI chọn màn, bấm Solve, xem phát lại. Script thực nghiệm chạy một lệnh. | G2 (25/10): Từ GUI: chọn màn, bấm Solve cho từng solver, xem phát lại; script thực nghiệm chạy hết bộ map; chưa có lỗi nghiêm trọng đang mở |
| 3. Tích hợp, thực nghiệm chính thức, đóng băng | 26/10-27/10 | Gộp mọi nhánh, chạy thực nghiệm chính thức, đóng băng tính năng vào tối 27/10. Bản nháp báo cáo xong. | G3 (27/10): Thẻ v1.0-rc; results.csv chính thức; biểu đồ; bản nháp báo cáo đủ 80% các mục |
| 4. Báo cáo, video, đóng gói | 28/10-29/10 | Report.pdf hoàn chỉnh có link video. File nộp được kiểm tra trên máy sạch. Đã tập phỏng vấn. | G4 (29/10): Report.pdf có link video; zip kiểm tra trên máy sạch; đã tập phỏng vấn |
| 5. Nộp bài | 30/10-31/10 | Nộp ngày 30/10. Ngày 31/10 chỉ để dự phòng. | - |

Solver chỉ cần `core` nên có thể bắt đầu song song với GUI.

## 7. Kiểm thử

- `test_maps.py`: nạp từng map, chạy BFS toàn bộ không gian trạng thái, kiểm tra mọi công tắc có cầu và ngược lại, kiểm tra mọi trạng thái đạt tới đều hợp lệ.
- `test_rules.py`: 32 kiểm tra luật theo đề bài mục 2.5 trên map tổng hợp nhỏ (tách, gộp, đổi khối, khối đơn với công tắc, fragile, cầu toggle và permanent).
- `test_meta.py`: đọc metadata `SWITCH` và `SPLIT`.
- `test_transition.py`: 12 phép lăn, rơi ra ngoài lưới và trên ô trống, chỉ thắng khi đứng thẳng trên đích, heavy chỉ kích hoạt khi đứng thẳng, soft kích hoạt ở mọi tư thế, cầu đóng dưới khối.
- `test_game.py`: nước hợp lệ tăng `moves`, nước rơi đặt `LOST`, đến đích thì `WON`, sau `WON` hoặc `LOST` thì nước đi bị bỏ qua, `restart` về trạng thái đầu.
- `test_solvers.py`: đường đi của mỗi solver, khi áp dụng lên map, đến được đích; số nước của BFS khớp bảng tham chiếu dưới đây; heuristic chấp nhận được.

**Bảng đáp án tham chiếu** (BFS, mỗi nước đi có chi phí 1; tính trên 13 map hiện có). BFS, UCS với chi phí 1 và A* đều phải ra đúng số nước tối ưu này (tham khảo và cần kiểm tra lại)

| Map | Cỡ | Nhóm | Số nước tối ưu | Số trạng thái đạt tới |
|---|---|---|---|---|
| level0 | 6x5 | A | 7 | 29 |
| level1 | 6x17 | A | 21 | 114 |
| level2 | 10x15 | A | 35 | 116 |
| level3 | 9x17 | B | 33 | 102 |
| level4 | 6x17 | C | 18 | 380 |
| level5 | 9x17 | C | 45 | 190 |
| level6 | 10x17 | C | 75 | 529 |
| level7 | 11x17 | B | 46 | 177 |
| level8 | 10x13 | C | 19 | 490 |
| level9 | 10x17 | C | 72 | 422 |
| level10 | 10x17 | D | 59 | 276 |
| level11 | 10x17 | D | 37 | 436 |
| level12 | 10x17 | C | 91 | 6016 |

Các số này phụ thuộc vào luật đã chốt ở mục 4. Nếu đổi luật thì tính lại bằng `test_maps.py`.

## 8. Cách cập nhật baseline

Khi đổi một quyết định:

1. Sửa mục 4 của README này trước, ghi rõ lý do.
2. Sửa sơ đồ lớp nếu có class hoặc quan hệ thay đổi.
3. Sửa sơ đồ luồng nếu thứ tự xử lý thay đổi.
4. Báo cả nhóm trước khi merge.

Không sửa code của người khác mà không báo. Nếu cần đổi `core`, báo TV1, vì mọi nhóm đều phụ thuộc vào đó.

## 9. Các câu hỏi và trạng thái

| # | Câu hỏi | Trạng thái |
|---|---|---|
| 1 | Quy ước số cho công tắc | Đã chốt, xem mục 4 |
| 2 | Cầu lúc bắt đầu | Đã chốt: tất cả đóng |
| 3 | Công tắc tách khối | Đã chốt: bắt buộc theo đề bài |
| 4 | Chi phí cho UCS | **Chưa chốt.** TV3 quyết định khi viết `ucs.py`. Nếu mọi nước đi có chi phí như nhau thì UCS giống BFS (đề bài mục 3.4 nêu rõ), nên chi phí cần phân biệt các nước đi |
| 5 | Số lượng map | Đã chốt: 13 map; cần thêm map mới, xem mục 4 |
| 6 | Thư viện pygame và PyOpenGL | Đã chốt: đề bài cho phép thư viện hỗ trợ GUI |
| 7 | Hai công tắc cùng nhóm cầu | Đã chốt: giữ nguyên |
| 8 | Cầu đóng ngay dưới chân khối | Đã chốt: coi là rơi |
| 9 | Map có hàng ngắn | Đã chốt: đệm ô trống bên phải |

## 10. Tuân thủ đề bài

Bảng đối chiếu từng yêu cầu của đề bài về map và luật chơi nằm ở `README_MAP.md` mục 5. Các yêu cầu còn lại (báo cáo, video, cách nộp) nằm ở `ROADMAP_v2.md` mục 2 và mục 9.

