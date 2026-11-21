# Valorant Voice AI Companion v1.0.0 (Windows 10/11 x64)

Ứng dụng trợ lý AI giọng nói độc lập chạy trực tiếp trên Windows 10/11 dạng **`.exe` mở lên là chạy ngay**, tích hợp Gemini Multimodal Live API, giao tiếp rảnh tay, dịch phụ đề thời gian thực và định tuyến âm thanh 2 chiều cho game Valorant.

---

### 🛡️ Ràng buộc bảo mật & Tuân thủ Riot Vanguard (100% PASS)
- **100% Thụ động tầng hệ điều hành**: Chỉ truy cập màn hình qua **DXGI Desktop Duplication API / Windows Graphics Capture** và âm thanh qua **WASAPI Loopback**.
- **Tuyệt đối an toàn**: Không đọc/ghi bộ nhớ RAM (`ReadProcessMemory`), không DLL injection, không hook DirectX/Vulkan vào `VALORANT-Win64-Shipping.exe`.
- **Không can thiệp file game**: Không sửa đổi hoặc can thiệp file cài đặt hay file `.pak` của Valorant.
- **Giám sát chỉ-đọc**: Chỉ dùng `psutil` để phát hiện trạng thái game nhằm bật/tắt HUD và giải phóng tài nguyên sạch sẽ.

---

### 🌟 Tính Năng Cốt Lõi:
1. **Tích hợp Driver VB-Audio Cable 1-Chạm**:
   - Nhúng sẵn bộ cài `VBCABLE_Setup_x64.exe` trực tiếp vào trong file `.exe`.
   - Tự động nhận diện và cung cấp nút cài đặt im lặng bằng quyền Quản trị viên (Admin) ngay trên giao diện mà không cần người dùng tìm tải ngoài thủ công.

2. **Định tuyến âm thanh 2 chiều (Dual Audio Routing)**:
   - Trộn giọng micro thật của bạn + giọng phản hồi của AI vào Mic ảo (`CABLE Input`).
   - Khi AI nói: **CẢ bạn (qua tai nghe) LẪN đồng đội (qua mic game)** đều nghe thấy đồng thời!
   - Tự động giả lập giữ phím đàm thoại (Auto PTT) khi AI phản hồi.

3. **Đồng đội trong game gọi AI được phản hồi**:
   - Khi đồng đội trong Voice Chat Valorant gọi *"Hey Gemini"*, hệ thống nhận diện qua WASAPI Loopback và AI trả lời trực tiếp qua mic game để cả đội cùng nghe.

4. **HUD Màn hình trong suốt (PyQt6 Overlay)**:
   - Hiển thị phụ đề dịch voice chat đồng đội sang Tiếng Việt theo thời gian thực.
   - Hỗ trợ click-through (`WS_EX_TRANSPARENT`), không chiếm focus chuột khi bắn súng.
   - Đặt cờ `WDA_EXCLUDEFROMCAPTURE`: Tàng hình trên OBS / Discord Stream và không bị AI tự chụp lại.

5. **Phê duyệt Chat an toàn (Permission-Gated Chat)**:
   - AI không tự ý gõ phím vào khung chat game.
   - Chỉ gửi tin nhắn sau khi người dùng xác nhận bằng giọng nói hoặc bấm nút Duyệt `[F8]`.

6. **Web Dashboard điều khiển qua mạng LAN**:
   - Web server FastAPI + WebSocket tích hợp sẵn.
   - Quét mã QR từ điện thoại để kéo thanh trượt chỉnh âm lượng (0-200%), nút Mute nhanh và chỉnh FPS luồng màn hình.

---

### 📦 Hướng Dẫn Cài Đặt & Sử Dụng:
1. Tải file **`ValorantVoiceAI-Windows-x64.zip`** hoặc trực tiếp file **`ValorantVoiceAI.exe`** đính kèm bên dưới.
2. Giải nén và mở **`ValorantVoiceAI.exe`** trên máy tính Windows 10 hoặc 11 (x64).
3. Nếu máy chưa có Virtual Cable, bấm nút **"Cài đặt VB-Cable"** trên giao diện ứng dụng để hệ thống tự cài driver.
4. Chọn Micro và Tai nghe thực tế của bạn, rồi vào Cài đặt Âm thanh của Valorant chọn **Thiết bị Đầu vào (Input Device): CABLE Output (VB-Audio Virtual Cable)**.
5. Vào trận đấu và trải nghiệm tương tác giọng nói trực tiếp cùng đồng đội và AI!
