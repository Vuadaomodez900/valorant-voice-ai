# 🎮 Valorant Voice AI Companion (Windows 10/11)

> **Trợ lý AI giọng nói & phân tích chiến thuật thời gian thực cho Valorant**, tích hợp **Gemini Multimodal Live API**, định tuyến âm thanh hai chiều (**Dual Audio Routing**), dịch Voice Chat đồng đội sang **Tiếng Việt** trên màn hình, và điều khiển từ xa qua điện thoại (**LAN Web Dashboard**).
> 
> 🛡️ **Tuyệt đối an toàn với Riot Vanguard (100% Vanguard Compliant)**: Chỉ quay màn hình thụ động bằng **Windows DXGI Desktop Duplication API**, thu âm thanh qua **WASAPI Loopback**, và kiểm tra trạng thái tiến trình chỉ-đọc bằng `psutil`. Không inject DLL, không đọc/ghi RAM, không chỉnh sửa file game.

---

## 🌟 TÍNH NĂNG NỔI BẬT

1. **Quay màn hình thụ động & Bộ nhớ đệm tua lại (Continuous Screen Stream + Rolling Buffer)**:
   - Truyền luồng hình ảnh 1–5 FPS trực tiếp sang Gemini Multimodal Live API.
   - Duy trì bộ nhớ đệm 15–30 giây gần nhất (15–30 FPS). Khi hỏi *"Pha vừa rồi tôi sai ở đâu?"*, AI sẽ phân tích chính xác tình huống vừa diễn ra.
2. **Định tuyến âm thanh hai chiều (Dual Audio Routing)**:
   - Khi AI nói, **CẢ bạn (qua tai nghe) LẪN đồng đội trong game (qua mic Valorant)** đều nghe thấy đồng thời với độ trễ siêu thấp.
   - Trộn âm thanh Mic vật lý của bạn + Giọng AI vào **VB-Audio Virtual Cable**.
   - Tự động kích hoạt phím Push-to-Talk (PTT) hoặc Open Mic khi AI giao tiếp.
3. **Kích hoạt bằng giọng nói ngoại tuyến (Wake Word)**:
   - Nhận diện tức thì cụm từ **"Hey Gemini"** hoặc **"Hey Google"**, hỗ trợ ngắt lời (barge-in) mượt mà.
4. **Dịch Voice Chat đồng đội sang Tiếng Việt (Non-Intrusive Overlay)**:
   - Overlay trong suốt chạy ở tầng Windows DWM bằng **PyQt6**, tương thích hoàn hảo với chế độ **Borderless Windowed** của Valorant.
   - Đặt cờ `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` để overlay **hoàn toàn vô hình** với AI screen stream và các phần mềm quay màn hình/OBS.
   - Tự động nhận diện voice chat đồng đội và hiển thị phụ đề Tiếng Việt mượt mà.
5. **Duyệt gửi Chat In-Game có kiểm soát (Permission-Gated Chat)**:
   - AI tuyệt đối không tự ý spam chat. Khi có thông tin chiến thuật (vd: *"Sova 40 HP A Main"*), bản nháp sẽ hiện lên Overlay/Web để bạn bấm **Duyệt (Gửi)** hoặc ra lệnh bằng giọng nói.
6. **Bảng điều khiển từ xa qua mạng nội bộ (LAN Web Dashboard & QR Code)**:
   - Truy cập giao diện điều khiển bằng trình duyệt PC hoặc camera điện thoại quét mã QR.
   - Kéo thanh trượt âm lượng AI trong tai nghe (0–200%) và âm lượng AI vào game (0–200%).
   - Nút Mute nhanh giọng AI vào game, đổi giọng đọc Gemini (Puck, Charon, Aoede,...).
7. **Chạy ngầm khay hệ thống (System Tray)**:
   - Đóng cửa sổ chính sẽ tự động thu gọn xuống System Tray cạnh đồng hồ Windows để tiết kiệm diện tích.

---

## 🛠️ HƯỚNG DẪN CÀI ĐẶT NHANH (3 BƯỚC)

### Bước 1: Cài đặt VB-Audio Virtual Cable (Miễn phí)
1. Tải **VB-CABLE Driver** tại: [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/)
2. Giải nén file `.zip`, click chuột phải vào `VBCABLE_Setup_x64.exe` chọn **Run as administrator**.
3. Bấm **Install Driver** và khởi động lại máy tính nếu được yêu cầu.

### Bước 2: Thiết lập cài đặt trong game Valorant
1. Mở Valorant, vào **Settings (Cài đặt) -> Audio (Âm thanh) -> Voice Chat (Chat thoại)**:
   - **Input Device (Thiết bị đầu vào)**: Chọn `CABLE Output (VB-Audio Virtual Cable)`.
   - **Output Device (Thiết bị đầu ra)**: Chọn Tai nghe của bạn (ví dụ: `Headphones / Realtek Audio`).
   - **Voice Chat Mode**: Chọn `Push to Talk` (mặc định phím `V`) hoặc `Open Mic`.
2. Vào **Settings -> Video -> General**:
   - **Display Mode**: Chọn `Borderless Windowed` (Cửa sổ không viền) để Overlay hiển thị đè lên game mượt mà nhất.

### Bước 3: Tải và Chạy File `.exe`
1. Tải gói `ValorantVoiceAI-Windows-x64.zip` từ mục **GitHub Actions Artifacts** (hoặc mục Releases).
2. Giải nén vào một thư mục bất kỳ trên máy tính Windows.
3. Double-click file `ValorantVoiceAI.exe` để mở ứng dụng.
4. Trên giao diện xuất hiện:
   - Chọn **Micro vật lý** của bạn.
   - Chọn **CABLE Input** cho Virtual Mic.
   - Chọn **Tai nghe** làm thiết bị phát.
   - Dán **Gemini API Key** (lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/)).
   - Bấm **LƯU CẤU HÌNH** và bấm **THU GỌN VÀO TRAY** để bắt đầu chơi!

---

## 📱 ĐIỀU KHIỂN TỪ ĐIỆN THOẠI (LAN WEB DASHBOARD)
- Khi app chạy, giao diện chính và log sẽ hiển thị một **mã QR**.
- Dùng điện thoại kết nối chung mạng Wi-Fi với máy tính, mở camera quét mã QR (hoặc truy cập địa chỉ `http://<IP_MÁY_TÍNH>:8765`).
- Bạn có thể vừa bắn Valorant vừa dùng điện thoại để:
  - Tăng giảm âm lượng giọng AI phát vào tai bạn hoặc vào game.
  - Bấm Mute nhanh khi cần tập trung nghe tiếng chân địch.
  - Duyệt nhanh tin nhắn chat in-game.

---

## 🔒 CAM KẾT BẢO MẬT & CHỐNG GIAN LẬN RIOT VANGUARD
Ứng dụng tuân thủ nghiêm ngặt điều khoản dịch vụ của Riot Games:
- ❌ **KHÔNG** can thiệp vào bộ nhớ RAM (`ReadProcessMemory` / `WriteProcessMemory`).
- ❌ **KHÔNG** hook DirectX / Vulkan hay inject bất kỳ file DLL nào vào tiến trình `VALORANT-Win64-Shipping.exe`.
- ❌ **KHÔNG** chỉnh sửa file `.pak` hay cấu hình hệ thống game.
- ❌ **KHÔNG** can thiệp tự động điều khiển tâm chuột/aimbot hay di chuyển nhân vật.
- 💡 **AI chỉ phản hồi khi được người dùng chủ động hỏi** (qua wake word hoặc overlay), không tự động spam âm thanh.

---

## 📦 TỰ BUILD FILE `.EXE` TỪ MÃ NGUỒN (TUỲ CHỌN)
Nếu bạn muốn tự đóng gói file `.exe` trên máy tính Windows cá nhân:
```powershell
# Clone mã nguồn
git clone https://github.com/Vuadaomodez900/valorant-voice-ai.git
cd valorant-voice-ai

# Cài đặt môi trường ảo Python 3.11
python -m venv venv
.\venv\Scripts\activate

# Cài đặt thư viện
pip install -r requirements.txt

# Kiểm tra môi trường hệ thống
python scripts/check_env.py

# Đóng gói file .exe bằng PyInstaller
pyinstaller build.spec --clean --noconfirm
```
File thực thi độc lập sẽ nằm trong thư mục `dist/ValorantVoiceAI.exe`.
