"""
Fast Config GUI (CustomTkinter) for Valorant Voice AI.
Features:
- Instant device selection: Physical Mic, Virtual Cable, Playback Device.
- Gemini API Key / AGY status input and persistence.
- Live Screen Stream FPS & Wake Word toggles.
- QR Code display for instant mobile connection.
- Seamless minimization to System Tray.
"""

import sys
import threading
import io
from pathlib import Path
from typing import Optional, Callable
from PIL import Image

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

import qrcode
from core.config import config
from core.audio_router import AudioRouter


class QuickConfigApp:
    """Modern dark-themed setup and control dashboard."""

    def __init__(self,
                 router: AudioRouter,
                 on_tray_minimize: Callable[[], None],
                 on_shutdown: Callable[[], None]):
        self.router = router
        self.on_tray_minimize = on_tray_minimize
        self.on_shutdown = on_shutdown

        self.root = None
        self._is_visible = True

    def create_ui(self) -> None:
        if ctk is None:
            print("[GUI] customtkinter not installed. GUI will run in headless CLI mode.")
            return

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Valorant Voice AI - Windows Companion")
        self.root.geometry("780x640")
        self.root.minsize(700, 580)

        # Handle window close event -> minimize to tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Main Layout: 2 Columns (Left: Config & Devices, Right: QR Code & Status)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(0, weight=1)

        # Left Column Frame
        left_frame = ctk.CTkScrollableFrame(self.root, corner_radius=10)
        left_frame.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        title_label = ctk.CTkLabel(
            left_frame,
            text="VALORANT VOICE AI",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FF4655"
        )
        title_label.pack(anchor="w", pady=(0, 4))

        subtitle_label = ctk.CTkLabel(
            left_frame,
            text="Thiết lập âm thanh hai chiều, Gemini Live & Màn hình thụ động",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        subtitle_label.pack(anchor="w", pady=(0, 16))

        # 1. Device Selection Section
        dev_section = ctk.CTkLabel(left_frame, text="1. THIẾT BỊ ÂM THANH (AUDIO ROUTING)", font=ctk.CTkFont(size=14, weight="bold"))
        dev_section.pack(anchor="w", pady=(8, 4))

        devices = AudioRouter.get_audio_devices()
        input_names = [d["name"] for d in devices["inputs"]] or ["Default Microphone"]
        output_names = [d["name"] for d in devices["outputs"]] or ["Default Headphones"]

        # Physical Mic
        ctk.CTkLabel(left_frame, text="Micro Vật Lý Của Bạn:").pack(anchor="w", pady=(4, 2))
        self.mic_combo = ctk.CTkComboBox(left_frame, values=input_names, width=400)
        self.mic_combo.pack(anchor="w", pady=(0, 8))

        # Virtual Cable Output (for Valorant in-game voice)
        ctk.CTkLabel(left_frame, text="Virtual Cable (Mic Game Đồng Đội):").pack(anchor="w", pady=(4, 2))
        self.cable_combo = ctk.CTkComboBox(left_frame, values=output_names, width=400)
        # Try to select CABLE Input if present
        for name in output_names:
            if "cable" in name.lower():
                self.cable_combo.set(name)
                break
        self.cable_combo.pack(anchor="w", pady=(0, 8))

        # Headphone Output
        ctk.CTkLabel(left_frame, text="Tai Nghe Của Bạn (Phát Giọng AI):").pack(anchor="w", pady=(4, 2))
        self.hp_combo = ctk.CTkComboBox(left_frame, values=output_names, width=400)
        self.hp_combo.pack(anchor="w", pady=(0, 16))

        # 2. Gemini Live API Key
        api_section = ctk.CTkLabel(left_frame, text="2. CẤU HÌNH GEMINI LIVE API", font=ctk.CTkFont(size=14, weight="bold"))
        api_section.pack(anchor="w", pady=(8, 4))

        self.api_entry = ctk.CTkEntry(left_frame, placeholder_text="Nhập GEMINI_API_KEY (hoặc để trống nếu dùng AGY CLI)", width=400, show="•")
        current_key = config.data["gemini"].get("api_key", "")
        if current_key:
            self.api_entry.insert(0, current_key)
        self.api_entry.pack(anchor="w", pady=(0, 8))

        # 3. Quick Toggles
        toggle_section = ctk.CTkLabel(left_frame, text="3. TÍNH NĂNG CHÍNH", font=ctk.CTkFont(size=14, weight="bold"))
        toggle_section.pack(anchor="w", pady=(8, 4))

        self.wake_switch = ctk.CTkSwitch(left_frame, text="Nhận diện 'Hey Gemini' ngoại tuyến")
        self.wake_switch.select() if config.data["wake_word"]["enabled"] else self.wake_switch.deselect()
        self.wake_switch.pack(anchor="w", pady=4)

        self.overlay_switch = ctk.CTkSwitch(left_frame, text="Bật Desktop Overlay (Dịch Tiếng Việt + HUD)")
        self.overlay_switch.select() if config.data["overlay"]["enabled"] else self.overlay_switch.deselect()
        self.overlay_switch.pack(anchor="w", pady=4)

        self.ptt_switch = ctk.CTkSwitch(left_frame, text="Tự động mở mic game khi AI nói (Auto PTT)")
        self.ptt_switch.select() if config.data["audio"]["auto_mic_trigger"] else self.ptt_switch.deselect()
        self.ptt_switch.pack(anchor="w", pady=4)

        # Save Button
        save_btn = ctk.CTkButton(left_frame, text="LƯU CẤU HÌNH", fg_color="#FF4655", hover_color="#E03E4C", command=self.save_settings)
        save_btn.pack(anchor="w", pady=(16, 8))

        # Right Column Frame (QR Code, Status & System Tray Button)
        right_frame = ctk.CTkFrame(self.root, corner_radius=10)
        right_frame.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")

        qr_title = ctk.CTkLabel(right_frame, text="KẾT NỐI ĐIỆN THOẠI", font=ctk.CTkFont(size=14, weight="bold"))
        qr_title.pack(pady=(16, 4))

        # Generate QR code for mobile connection
        from web_control.server import get_local_ip
        local_ip = get_local_ip()
        port = config.data["web"]["port"]
        web_url = f"http://{local_ip}:{port}"

        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(web_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#FF4655", back_color="#1E293B").convert("RGB")

        ctk_qr = ctk.CTkImage(light_image=qr_img, dark_image=qr_img, size=(160, 160))
        qr_display = ctk.CTkLabel(right_frame, text="", image=ctk_qr)
        qr_display.pack(pady=8)

        url_label = ctk.CTkLabel(right_frame, text=web_url, font=ctk.CTkFont(size=11), text_color="#00F5D4")
        url_label.pack(pady=(0, 16))

        # Tray Minimize Button
        tray_btn = ctk.CTkButton(
            right_frame,
            text="THU GỌN VÀO TRAY\n(Chạy ngầm khi chơi game)",
            fg_color="#334155",
            hover_color="#475569",
            command=self.hide_to_tray
        )
        tray_btn.pack(fill="x", padx=16, pady=(16, 8))

        # Full Exit Button
        exit_btn = ctk.CTkButton(
            right_frame,
            text="THOÁT HOÀN TOÀN",
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self.on_shutdown
        )
        exit_btn.pack(fill="x", padx=16, pady=8)

    def save_settings(self) -> None:
        if self.api_entry:
            config.data["gemini"]["api_key"] = self.api_entry.get().strip()
        if self.wake_switch:
            config.data["wake_word"]["enabled"] = bool(self.wake_switch.get())
        if self.overlay_switch:
            config.data["overlay"]["enabled"] = bool(self.overlay_switch.get())
        if self.ptt_switch:
            config.data["audio"]["auto_mic_trigger"] = bool(self.ptt_switch.get())

        config.save()
        print("[GUI] Settings saved to configuration.")

    def hide_to_tray(self) -> None:
        """Hides GUI window to let it run smoothly in the background."""
        if self.root:
            self.root.withdraw()
            self._is_visible = False
            self.on_tray_minimize()

    def show_from_tray(self) -> None:
        """Restores window from system tray."""
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self._is_visible = True

    def run(self) -> None:
        if self.root:
            self.root.mainloop()
