# Valorant Voice AI Companion v1.1.0 (Windows 10/11 x64)

Bản cập nhật lớn bổ sung **AGY CLI trực tiếp ngay trên máy tính** và **hệ sinh thái điều khiển từ xa cho AGY CLI trên điện thoại Android (Termux)**.

---

### 🌟 Điểm Mới Trong Phiên Bản v1.1.0:

1. **💻 Tích hợp AGY CLI Console Ngay Trên Windows**:
   - Thêm nút bấm **`[ 💻 MỞ AGY CLI TERMINAL ]`** ngay trên giao diện ứng dụng PC.
   - Hỗ trợ cờ khởi chạy dòng lệnh: `ValorantVoiceAI.exe --cli` để tương tác trực tiếp với động cơ AI và game Valorant bằng bàn phím.

2. **📱 Hệ Sinh Thái AGY CLI Cho Điện Thoại (Termux / Android)**:
   - **MCP Server Stdio (`valorant-voice-ops`)**: Cho phép AGY CLI tự động nhận diện và gọi các tool: `get_valorant_status`, `set_audio_volume`, `handle_chat_draft`, `set_screen_fps`, `toggle_teammate_trigger`, `send_tactical_callout`, `scan_and_connect_pc`.
   - **Lệnh toàn cục Termux**: Gõ `agy-valorant` để vào shell điều khiển tương tác, gõ `agy-dashboard` để xem bảng hiển thị phụ đề và âm lượng.
   - **Bộ kịch bản nhanh**: `quick_action.sh` (mute/unmute, volume, approve/reject chat, fps, callout) và `scan_pc.py` tự dò IP máy tính trên Wi-Fi.

3. **📢 API Chỉ Thị Chiến Thuật Mới (`POST /api/callout`)**:
   - Cho phép người dùng hoặc AGY CLI từ điện thoại gửi trực tiếp các callout chiến thuật vào trận đấu.

4. **⚡ Nâng Cấp Bộ Kiểm Thử Tự Động (21 / 21 Tests PASS)**:
   - Bổ sung kiểm thử đơn vị và tích hợp cho toàn bộ các endpoint mới, đảm bảo 100% không lỗi hồi quy.

---

### 🛡️ Tuân Thủ Riot Vanguard (100% Safe):
- Giám sát thụ động qua **Windows DXGI Desktop Duplication API** & **WASAPI Loopback**.
- Tuyệt đối không hook DLL, không đọc/ghi RAM game, không chỉnh sửa file Valorant.
- Tự động nhận diện tiến trình chỉ-đọc với `psutil`.

---

### 📦 Hướng Dẫn Nhanh:
1. Tải file **`ValorantVoiceAI.exe`** hoặc **`ValorantVoiceAI-Windows-x64.zip`** đính kèm bên dưới.
2. Mở file **`ValorantVoiceAI.exe`** trên máy tính Windows 10/11.
3. Bấm **"Cài đặt VB-Cable"** (đã nhúng sẵn trong app) nếu máy tính chưa có driver.
4. Cấu hình Mic và Tai nghe, vào Valorant chọn Input Device là `CABLE Output (VB-Audio Virtual Cable)`.
5. Trải nghiệm tương tác rảnh tay bằng giọng nói hoặc qua AGY CLI!
