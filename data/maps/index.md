# Bloxorz Solver - Index & Classifications Map Dataset

File quản lý danh mục bản đồ game Bloxorz sử dụng định dạng `.txt`. Toàn bộ bản đồ trong hệ thống đã được xác minh bằng thuật toán **BFS (Breadth-First Search)** đảm bảo có lời giải hợp lệ.

---

## 🔑 Chú thích Ký hiệu Bản đồ (Map Character Legend)

Để hiểu rõ cấu trúc các file bản đồ `.txt`, hệ thống quy ước các ký tự ô (tiles) như sau:

| Ký tự | Tên gọi / Ý nghĩa | Mô tả chi tiết |
| :---: | :--- | :--- |
| **` `** (Space) hoặc **`-`** | **Void / Khoảng trống** | Hố sâu. Khối gạch rơi xuống đây sẽ bị thua (Game Over). |
| **`F`** hoặc số/chữ khác | **Floor / Ô Sàn thường** | Ô đất bình thường mà khối gạch có thể di chuyển, nằm đè hoặc đứng lên. |
| **`S`** | **Start / Điểm xuất phát** | Vị trí ban đầu của khối gạch khi bắt đầu màn chơi. |
| **`G`** (hoặc đích tùy map) | **Goal / Ô Đích** | Vị trí mục tiêu. Khối gạch phải **đứng thẳng (Standing)** chính xác lên ô này để chiến thắng. |
| **`1`, `0`** | **Switches / Công tắc** | Các loại công tắc (Soft/Heavy switches) giúp kích hoạt hoặc thay đổi trạng thái cầu. |
| **`A`, `B`, `C` / `a`, `b`, `c`** | **Bridges / Cầu nối** | Các khối cầu đóng/mở (Toggle hoặc Permanent bridge) liên kết với công tắc tương ứng. |

---

## 📊 Phân loại Nhóm Bản đồ (Categories)

- **Nhóm E (Basic / Introductory):** Các màn chơi cơ bản (`level0.txt`, `level1.txt`, `level2.txt`) giúp làm quen với không gian trạng thái, góc lật khối và các lối đi hẹp.
- **Nhóm B (Fragile / Special Tiles):** Các màn chơi (`level3.txt`, `level4.txt`) có các đặc điểm cấu trúc thử thách khả năng kiểm soát diện tích tiếp xúc của khối.
- **Nhóm D (Switches & Bridges):** Các màn chơi (`level5.txt`, `level6.txt`, `level7.txt`) có chứa các cơ chế công tắc và cầu nối điều khiển đường đi.
- **Nhóm C & Advanced / Complex:** Các màn chơi nâng cao (`level8.txt`, `level9.txt`,... đến `level12.txt`, `zfortest.txt`, `zlevel120.txt`) với độ phức tạp cao, không gian rẽ nhánh lớn phục vụ cho kiểm thử hiệu năng toàn diện của các thuật toán (BFS, DFS, UCS, A*).

---

## 🗺️ Danh sách Chi tiết Bản đồ .txt

| Tên File | Nhóm Phân loại | Tình trạng BFS Solvable | Ghi chú / Đặc điểm cấu trúc |
| :--- | :---: | :---: | :--- |
| `level0.txt`[cite: 14] | **E** | **TRUE** | Màn hướng dẫn cơ bản với không gian nhỏ. |
| `level1.txt`[cite: 15] | **E** | **TRUE** | Làm quen với các hướng chuyển động và độ rộng đường đi. |
| `level2.txt`[cite: 16] | **E** | **TRUE** | Kết hợp các đoạn đường gấp khúc và ranh giới hố sâu. |
| `level3.txt`[cite: 17] | **B** | **TRUE** | Bắt đầu xuất hiện các cấu trúc thử thách diện tích bề mặt. |
| `level4.txt`[cite: 18] | **B** | **TRUE** | Màn chơi phức hợp có chứa các khu vực bẫy và công tắc cục bộ (`1`, `a`, `b`). |
| `level5.txt`[cite: 19] | **D** | **TRUE** | Tích hợp cơ chế công tắc (`0`) và điều hướng cầu nối. |
| `level6.txt`[cite: 20] | **D** | **TRUE** | Sử dụng hệ thống công tắc đa dạng (`A`, `B`, `C`, `a`, `b`, `c`) mở cầu phức tạp. |
| `level7.txt`[cite: 21] | **D** | **TRUE** | Màn chơi tổng hợp nhiều công tắc và tuyến đường rẽ nhánh sâu. |
| `level8.txt`[cite: 22] | **C / Advanced** | **TRUE** | Mức độ khó cao, đòi hỏi thuật toán tìm kiếm duyệt qua nhiều không gian trạng thái. |
| `level9.txt`[cite: 23] | **C / Advanced** | **TRUE** | Thử thách tối ưu hóa đường đi với các khu vực cách ly. |
| `level10.txt` - `level12.txt` | **C / Advanced** | **TRUE** | Bộ map nâng cao dùng cho đánh giá thực nghiệm hiệu suất Solver. |
| `zfortest.txt` / `zlevel120.txt` | **Stress Test** | **TRUE** | Các map đặc biệt dùng để kiểm tra giới hạn bộ nhớ và thời gian (Stress testing). |