# 🎮 Valorant Voice AI Companion (Windows 10/11)

> **Trợ lý AI giọng nói & phân tích chiến thuật thời gian thực cho Valorant**, tích hợp **Gemini Multimodal Live API**, định tuyến âm thanh hai chiều (**Dual Audio Routing**), dịch Voice Chat đồng đội sang **Tiếng Việt** trên màn hình, điều khiển từ xa qua điện thoại (**LAN Web Dashboard**), và **TÍCH HỢP SẴN 100% DRIVER VIRTUAL AUDIO CABLE LÀM MỘT KHỐI THỐNG NHẤT** (không cần tải thêm bất kỳ driver nào bên ngoài!).
> 
> 🛡️ **Tuyệt đối an toàn với Riot Vanguard (100% Vanguard Compliant)**: Chỉ quay màn hình thụ động bằng **Windows DXGI Desktop Duplication API**, thu âm thanh qua **WASAPI Loopback**, và kiểm tra trạng thái tiến trình chỉ-đọc bằng `psutil`. Không inject DLL, không đọc/ghi RAM, không chỉnh sửa file game.

---

## 🌟 ĐẶC ĐIỂM TÍCH HỢP MỚI: CABLE TÍCH HỢP LÀM 1 (ALL-IN-ONE)

- 🔌 **Tích hợp sẵn Driver Virtual Audio Cable bên trong file `.exe`**: Toàn bộ bộ cài driver 64-bit/32-bit đã được nhúng trực tiếp vào ứng dụng.
- ⚡ **Cài đặt 1-chạm (1-Click Auto Install)**: Mở `.exe` lên, nếu máy tính của bạn chưa có Virtual Cable, app sẽ hiện ngay nút bấm **`[ ⚡ CÀI ĐẶT VIRTUAL CABLE 1-CHẠM (TÍCH HỢP SẴN) ]`**. Chỉ cần bấm 1 click là driver tự động cài đặt ngầm và tự động nhận diện thiết bị ngay lập tức!
- 🌐 **Hỗ trợ cài từ xa qua điện thoại**: Có thể kích hoạt cài đặt driver ngay trên Web Dashboard điện thoại qua mạng LAN.

---

## 🌟 TÍNH NĂNG CỐT LÕI

1. **Quay màn hình thụ động & Bộ nhớ đệm tua lại (Continuous Screen Stream + Rolling Buffer)**:
   - Truyền luồng hình ảnh 1–5 FPS trực tiếp sang Gemini Multimodal Live API.
   - Duy trì bộ nhớ đệm 15–30 giây gần nhất (15–30 FPS). Khi hỏi *"Pha vừa rồi tôi sai ở đâu?"*, AI sẽ phân tích chính xác tình huống vừa diễn ra.
2. **Định tuyến âm thanh hai chiều (Dual Audio Routing)**:
   - Khi AI nói, **CẢ bạn (qua tai nghe) LẪN đồng đội trong game (qua mic Valorant)** đều nghe thấy đồng thời với độ trễ siêu thấp.
   - Trộn âm thanh Mic vật lý của bạn + Giọng AI vào **Virtual Cable tích hợp**.
   - Tự động kích hoạt phím Push-to-Talk (PTT) hoặc Open Mic khi AI giao tiếp.
3. **Kích hoạt bằng giọng nói ngoại tuyến (Wake Word)**:
   - Nhận diện tức thì cụm từ **"Hey Gemini"** hoặc **"Hey Google"**, hỗ trợ ngắt lời (barge-in) mượt mà.
4. **Dịch Voice Chat đồng đội sang Tiếng Việt (Non-Intrusive Overlay)**:
   - Overlay trong suốt chạy ở tầng Windows DWM bằng **PyQt6**, tương thích hoàn hảo với chế độ **Borderless Windowed** của Valorant.
   - Đặt cờ `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` để overlay **hoàn toàn vô hình** trong luồng quay màn hình của AI và OBS/Discord Stream.
   - Tự động nhận diện voice chat đồng đội và hiển thị phụ đề Tiếng Việt mượt mà.
5. **Duyệt gửi Chat In-Game có kiểm soát (Permission-Gated Chat)**:
   - AI tuyệt đối không tự ý spam chat. Khi có thông tin chiến thuật (vd: *"Sova 40 HP A Main"*), bản nháp sẽ hiện lên Overlay/Web để bạn bấm **Duyệt (Gửi)** hoặc ra lệnh bằng giọng nói.
6. **Bảng điều khiển từ xa qua mạng nội bộ (LAN Web Dashboard & QR Code)**:
   - Truy cập giao diện điều khiển bằng trình duyệt PC hoặc camera điện thoại quét mã QR.
   - Kéo thanh trượt âm lượng AI trong tai nghe (0–200%) và âm lượng AI vào game (0–200%).
   - Nút Mute nhanh giọng AI vào game, đổi giọng đọc Gemini (Puck, Charon, Aoede,...).
7. **Tích hợp AGY CLI Trực Tiếp Ngay Trên Máy (Embedded AGY Shell & Remote Tools)**:
   - **Trên Windows**: Bấm nút **`[ 💻 MỞ AGY CLI TERMINAL ]`** trên giao diện hoặc chạy `ValorantVoiceAI.exe --cli` để mở console tương tác trực tiếp bằng bàn phím.
   - **Trên Điện Thoại (Termux)**: Cung cấp lệnh toàn cục `agy-valorant` (Interactive Shell), `agy-dashboard` (TUI Live Screen), bộ lệnh nhanh `quick_action.sh`, và MCP Server `valorant-voice-ops` để chat điều khiển tự nhiên với AGY.
8. **Chạy ngầm khay hệ thống (System Tray)**:
   - Đóng cửa sổ chính sẽ tự động thu gọn xuống System Tray cạnh đồng hồ Windows để tiết kiệm diện tích.

---

## 🛠️ HƯỚNG DẪN SỬ DỤNG SIÊU ĐƠN GIẢN (CHỈ CẦN FILE `.EXE`)

### Bước 1: Mở File `.exe`
1. Tải gói `ValorantVoiceAI-Windows-x64.zip` từ mục **GitHub Actions Artifacts** (hoặc mục Releases).
2. Giải nén và mở **`ValorantVoiceAI.exe`**.
3. Nếu máy bạn chưa có Virtual Cable, bấm nút:  
   👉 **`[ ⚡ CÀI ĐẶT VIRTUAL CABLE 1-CHẠM (TÍCH HỢP SẴN) ]`** ngay trên đầu ứng dụng.  
   *(App sẽ tự động cài đặt driver ngầm trong vài giây mà bạn không cần tải file nào từ web).*

### Bước 2: Thiết lập trong game Valorant
1. Mở Valorant, vào **Settings (Cài đặt) -> Audio (Âm thanh) -> Voice Chat (Chat thoại)**:
   - **Input Device (Thiết bị đầu vào)**: Chọn `CABLE Output (VB-Audio Virtual Cable)`.
   - **Output Device (Thiết bị đầu ra)**: Chọn Tai nghe của bạn (ví dụ: `Headphones / Realtek Audio`).
   - **Voice Chat Mode**: Chọn `Push to Talk` (mặc định phím `V`) hoặc `Open Mic`.
2. Vào **Settings -> Video -> General**:
   - **Display Mode**: Chọn `Borderless Windowed` (Cửa sổ không viền) để Overlay hiển thị đè lên game mượt mà nhất.

### Bước 3: Bắt đầu chơi
- Trên app chọn Micro của bạn, Virtual Cable (`CABLE Input`), và dán Gemini API Key.
- Bấm **LƯU CẤU HÌNH** và bấm **THU GỌN VÀO TRAY** để bắt đầu trải nghiệm trận đấu!
