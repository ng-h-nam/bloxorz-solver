# 🧩 Bloxorz Solver

Môn: CSC14003 - Cơ sở Trí tuệ Nhân tạo. Dự án xây dựng Game Bloxorz và bộ giải tự động ứng dụng các thuật toán tìm kiếm (BFS, DFS/IDS, UCS, A*)

## 👥 Thành viên nhóm & Phân công

- **Hoàng Trung Phong**: Lead Dev & Game Core Engine.
- **Nguyễn Như Thuật**: Advanced Tiles Engine & GUI Developer.
- **Hà Chí Tâm**: Algorithm Specialist (BFS, DFS/IDS, UCS).
- **Huỳnh Văn Phú**: AI & Heuristic Specialist (A* Solver).
- **Nguyễn Hoàng Nam**: Experiment Lead, Technical Report & Video Creator.

## 🛠️ Yêu cầu môi trường & Cài đặt

### Cài đặt và Chạy Game (Hỗ trợ Windows & Linux/macOS)

1. **Cài đặt Python (3.9+):**
   - **Trên Windows:** Tải bộ cài tại [python.org](https://www.python.org/downloads/). *(Lưu ý: Bắt buộc tích vào ô **"Add Python to PATH"** lúc cài đặt).*
   - **Trên Linux (Ubuntu/Debian):** Mở Terminal và chạy lệnh sau để cài đặt Python cùng công cụ tạo môi trường ảo:
     ```bash
     sudo apt update
     sudo apt install python3 python3-pip python3-venv -y
     ```

2. **Tải mã nguồn và di chuyển vào thư mục dự án:**
   ```bash
   git clone https://github.com/ng-h-nam/bloxorz-solver.git
   cd bloxorz-solver
   ```

3. **Tạo và kích hoạt môi trường ảo (Khuyên dùng để tránh xung đột thư viện hệ thống):**
   - **Trên Windows (CMD / PowerShell):**
     ```bash
     # Tạo môi trường ảo tên là .venv
     python -m venv .venv
     # Kích hoạt môi trường ảo
     .venv\Scripts\activate
     ```
   - **Trên Linux / macOS:**
     ```bash
     # Tạo môi trường ảo tên là .venv
     python3 -m venv .venv
     # Kích hoạt môi trường ảo (sau khi chạy, đầu dòng lệnh sẽ hiện chữ (.venv))
     source .venv/bin/activate
     ```
   *(Mẹo: Khi muốn thoát khỏi môi trường ảo trên cả 2 hệ điều hành, chỉ cần gõ lệnh `deactivate`).*

4. **Cài đặt các thư viện cần thiết:**
   ```bash
   # Cập nhật pip lên bản mới nhất và cài đặt thư viện từ file requirements.txt
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Khởi chạy Game:**
   - **Trên Windows:**
     ```bash
     python main.py
     ```
   - **Trên Linux / macOS:**
     ```bash
     # Khi đã nằm trong (.venv), bạn có thể dùng lệnh 'python' hoặc 'python3' đều được
     python3 main.py
     ```