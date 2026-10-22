# Bloxorz Solver - Index & Classifications Map Dataset (33 Stages)

File quản lý danh mục toàn bộ 33 bản đồ chính thức của game Bloxorz sử dụng định dạng văn bản `.txt`. Toàn bộ bản đồ trong hệ thống đã được kiểm thử và xác minh bằng thuật toán **BFS (Breadth-First Search)** đảm bảo có lời giải hợp lệ, không rơi vào trạng thái bế tắc (deadlock).

---

## 🔑 Chú thích Ký hiệu Bản đồ (Map Character Legend)

Hệ thống quy ước các ký tự ô (`tiles`) trong các tệp bản đồ `.txt`:

| Ký tự | Tên gọi / Ý nghĩa | Mô tả chi tiết |
| :---: | :--- | :--- |
| **` `** (Space) hoặc số dấu **`-`** | **Void / Khoảng trống** | Hố sâu. Khối gạch rơi xuống đây sẽ bị thua (Game Over). |
| **`.`** hoặc ký tự sàn | **Floor / Ô Sàn thường** | Ô đất bình thường mà khối gạch có thể di chuyển, nằm đè hoặc đứng lên. |
| **`S`** | **Start / Điểm xuất phát** | Vị trí ban đầu của khối gạch khi bắt đầu màn chơi. |
| **`T`** (hoặc **`X`**) | **Goal / Ô Đích** | Vị trí mục tiêu. Khối gạch phải **đứng thẳng (Standing)** chính xác lên ô này để chiến thắng. |
| **`O`** | **Soft Switch / Ô tròn** | Công kích hoạt khi gạch đè lên, dùng để bật/tắt hoặc đổi trạng thái cầu. |
| **`H`** | **Heavy/Hard Switch / Ô chữ X hoặc H** | Công tắc cứng, chỉ kích hoạt khi khối gạch **đứng thẳng** trên đó. |
| **`b`**, **`B`** | **Bridges / Cầu nối** | Các đoạn cầu đóng/mở (Toggle, Open/Off) liên kết với các công tắc trong phần metadata. |
| **`T`** (đứng độc lập) | **Teleport / Cổng dịch chuyển** | Ô dịch chuyển dịch khối gạch sang vị trí tương ứng trên bản đồ. |

---

## 📊 Phân loại Nhóm Bản đồ (Categories)

- **Nhóm 1 (Stage 01 – Stage 10): Cơ bản & Giới thiệu cơ chế**
  - Các màn chơi đầu tiên giúp làm quen với không gian lật gạch, các đường đi hẹp và bắt đầu tiếp cận cơ chế cầu nối đơn giản (`stage_01.txt` đến `stage_10.txt`).
- **Nhóm 2 (Stage 11 – Stage 22): Trung cấp & Phối hợp đa cơ chế**
  - Tăng độ phức tạp với hệ thống nhiều công tắc, cầu nối liên hoàn, cổng dịch chuyển (Teleport) đòi hỏi tư duy logic bước đi (`stage_11.txt` đến `stage_22.txt`).
- **Nhóm 3 (Stage 23 – Stage 33): Nâng cao & Phức hợp (Advanced / Complex)**
  - Các màn chơi có không gian rẽ nhánh lớn, kết hợp đồng thời công tắc đa chiều, ô dịch chuyển và điều kiện cầu phức tạp, thử thách tối ưu hóa thuật toán (`stage_23.txt` đến `stage_33.txt`).

---

## 🗺️ Danh sách Chi tiết 33 Bản đồ .txt

| Tên File | Nhóm Phân loại | Tình trạng BFS Solvable | Ghi chú / Đặc điểm cấu trúc |
| :--- | :---: | :---: | :--- |
| `stage_01.txt` | **Nhóm 1** | **TRUE** | Màn hướng dẫn cơ bản với không gian nhỏ. |
| `stage_02.txt` | **Nhóm 1** | **TRUE** | Bắt đầu giới thiệu cơ chế cầu nối đơn giản (`a`, `b`). |
| `stage_03.txt` | **Nhóm 1** | **TRUE** | Làm quen với các hướng chuyển động và đường đi gấp khúc. |
| `stage_04.txt` | **Nhóm 1** | **TRUE** | Đường đi hẹp, thử thách kiểm soát diện tích tiếp xúc. |
| `stage_05.txt` | **Nhóm 1** | **TRUE** | Tích hợp nhiều cầu nối và công tắc điều khiển trạng thái. |
| `stage_06.txt` | **Nhóm 1** | **TRUE** | Không gian rẽ nhánh trung bình, kiểm tra độ chính xác lật gạch. |
| `stage_07.txt` | **Nhóm 1** | **TRUE** | Kết hợp công tắc chuyển đổi cầu nối linh hoạt. |
| `stage_08.txt` | **Nhóm 1** | **TRUE** | Giới thiệu cơ chế cổng dịch chuyển (Teleport). |
| `stage_09.txt` | **Nhóm 1** | **TRUE** | Thử thách tối ưu hóa đường đi qua không gian cách ly. |
| `stage_10.txt` | **Nhóm 1** | **TRUE** | Tổng hợp công tắc, cầu nối và teleport ở mức cơ bản. |
| `stage_11.txt` | **Nhóm 2** | **TRUE** | Mở rộng quy mô lưới và cấu trúc cầu nối dọc. |
| `stage_12.txt` | **Nhóm 2** | **TRUE** | Màn chơi phối hợp công tắc cứng (`H`) và cầu ẩn. |
| `stage_13.txt` | **Nhóm 2** | **TRUE** | Đường đi zích-zắc qua các ô trống hẹp. |
| `stage_14.txt` | **Nhóm 2** | **TRUE** | Xử lý chuỗi hành động bật/tắt cầu liên tục. |
| `stage_15.txt` | **Nhóm 2** | **TRUE** | Phức hợp nhiều công tắc mềm và cổng dịch chuyển. |
| `stage_16.txt` | **Nhóm 2** | **TRUE** | Mật độ cổng dịch chuyển cao, yêu cầu tính toán hướng đi. |
| `stage_17.txt` | **Nhóm 2** | **TRUE** | Hệ thống cầu nối rải rác đòi hỏi thứ tự kích hoạt chuẩn xác. |
| `stage_18.txt` | **Nhóm 2** | **TRUE** | Cấu trúc đối xứng với nhiều công tắc điều hướng. |
| `stage_19.txt` | **Nhóm 2** | **TRUE** | Thử thách định vị khối gạch trên các tuyến đường dài. |
| `stage_20.txt` | **Nhóm 2** | **TRUE** | Kết hợp teleport và switch đa mục tiêu. |
| `stage_21.txt` | **Nhóm 2** | **TRUE** | Màn chơi chiến lược với các đoạn cầu nối ẩn. |
| `stage_22.txt` | **Nhóm 2** | **TRUE** | Cấu trúc phức hợp kiểm tra khả năng qua màn trung cấp. |
| `stage_23.txt` | **Nhóm 3** | **TRUE** | Bắt đầu phân khúc nâng cao với logic công tắc chéo. |
| `stage_24.txt` | **Nhóm 3** | **TRUE** | Tích hợp teleport ngược chiều và cầu nối điều kiện. |
| `stage_25.txt` | **Nhóm 3** | **TRUE** | Không gian hẹp kết hợp chuyển đổi trạng thái liên tục. |
| `stage_26.txt` | **Nhóm 3** | **TRUE** | Thử thách tư duy không gian với các bẫy hố sâu. |
| `stage_27.txt` | **Nhóm 3** | **TRUE** | Màn chơi quy mô lớn đòi hỏi lập kế hoạch đường đi dài. |
| `stage_28.txt` | **Nhóm 3** | **TRUE** | Phối hợp nhịp nhàng giữa công tắc, cầu và cổng dịch chuyển. |
| `stage_29.txt` | **Nhóm 3** | **TRUE** | Độ khó cao với nhiều tầng logic công tắc phụ thuộc. |
| `stage_30.txt` | **Nhóm 3** | **TRUE** | Đường đi uốn khúc qua hệ thống vực thẳm rộng lớn. |
| `stage_31.txt` | **Nhóm 3** | **TRUE** | Cấu trúc phức tạp kiểm thử hiệu suất duyệt không gian trạng thái. |
| `stage_32.txt` | **Nhóm 3** | **TRUE** | Áp lực thời gian và bước đi với các cơ chế cầu ẩn dày đặc. |
| `stage_33.txt` | **Nhóm 3** | **TRUE** | **Boss Stage:** Màn chơi đỉnh cao tổng hợp toàn bộ cơ chế phức tạp nhất của game. |