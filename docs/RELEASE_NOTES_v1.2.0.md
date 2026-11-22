# Valorant Voice AI Companion v1.2.0 (Windows 10/11 x64)

Bản cập nhật lớn bổ sung **Overlay Dạng Thông Báo (Toast Notification HUD)** và **Khả năng kết nối từ xa qua Internet / 4G / 5G mà không cần chung mạng Wi-Fi**.

---

### 🌟 Điểm Mới Trong Phiên Bản v1.2.0:

1. **🔔 Overlay Dạng Thông Báo eSports (Toast Notification HUD)**:
   - **Tự ẩn hoàn toàn khi rảnh tay**: Không còn bảng cố định che khuất radar, minimap, thanh máu hay tâm ngắm.
   - **Tự động hiện lên khi đồng đội nói**: Popup thông báo phong cách cyberpunk nổi bật ở giữa trên màn hình (`top-center`), hiển thị tiếng Anh gốc và tiếng Việt dịch chuẩn.
   - **Tự động ẩn sau 6 giây**: Đảm bảo người chơi kịp nắm bắt thông tin chiến thuật và lập tức tập trung vào pha đấu súng.
   - **Hỗ trợ Click-Through**: Chuột vẫn xuyên qua cửa sổ, bắn súng và di chuột mượt mà không bị ngắt quãng.

2. **🌐 Kết Nối Internet Không Cần Chung Wi-Fi (WAN / 4G / 5G / Tailscale / Cloudflare Tunnel)**:
   - **Nút 1-Click trên GUI**: Bấm **`[ 🌐 TẠO LINK INTERNET (KHÔNG CẦN WI-FI) ]`** trên ứng dụng để tự động mở đường link HTTPS bảo mật và cập nhật mã QR.
   - **Script 1-Click `bat_ket_noi_internet.bat`**: Chạy ngay bằng cách click đúp chuột trên Windows 10/11 (dùng OpenSSH có sẵn trong Windows, không cần cài thêm gì).
   - **Hỗ trợ mạng riêng ảo Tailscale**: Cấp IP cố định dạng `100.x.y.z`, kết nối mọi lúc mọi nơi kể cả khi dùng dữ liệu di động 4G/5G.

3. **📱 Nâng Cấp Hệ Sinh Thái AGY CLI (Termux / Phone)**:
   - MCP Server `valorant-voice-ops`, `quick_action.sh`, `scan_pc.py` và `agy_phone_client.py` tự động nhận diện và kết nối đến bất kỳ định dạng IP, Tailscale, hoặc URL Tunnel HTTPS.

4. **⚡ Mở Rộng Bộ Kiểm Thử (25 / 25 Tests PASS - 100%)**:
   - Thêm unit test cho `RemoteTunnelManager`, `get_base_url` WAN resolution, và `OverlayNotificationConfig`.

---

### 🛡️ Riot Vanguard Safe (100% Tuân Thủ):
- Passive Screen Stream qua **Windows DXGI Desktop Duplication API**.
- Audio Loopback qua **WASAPI**.
- Overlay DWM ẩn hoàn toàn khỏi capture bằng `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`.
- Không can thiệp RAM, không hook DLL, không chỉnh sửa file game.
