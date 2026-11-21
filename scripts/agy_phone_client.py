#!/usr/bin/env python3
"""
Interactive Phone TUI Client for Valorant Voice AI.
Runs directly in Termux terminal on Android phone.
Provides real-time telemetry, live translated subtitle streaming,
and 1-key quick controls (Mute, Volume, Chat Approval, FPS).
"""

import sys
import os
import time
import json
import socket
import select
import termios
import tty
import threading
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_FILE = Path.home() / ".gemini" / "config" / "valorant_pc.json"
DEFAULT_PORT = 8000

# ANSI color codes for cyberpunk Valorant theme in Termux
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[38;5;196m"
C_CYAN = "\033[38;5;51m"
C_GREEN = "\033[38;5;48m"
C_YELLOW = "\033[38;5;220m"
C_GRAY = "\033[38;5;244m"
C_WHITE = "\033[38;5;255m"
C_BG_DARK = "\033[48;5;234m"


def get_default_pc_host() -> str:
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return sys.argv[1].strip()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("host", "127.0.0.1")
        except Exception:
            pass
    return "127.0.0.1"


class PhoneTUIClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{self.host}:{self.port}"
        self.running = True
        self.status_data = {}
        self.subtitles = []
        self.last_event_msg = ""
        self.lock = threading.Lock()

    def api_get(self, endpoint: str):
        try:
            url = f"{self.base_url}{endpoint}"
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def api_post(self, endpoint: str, payload: dict):
        try:
            url = f"{self.base_url}{endpoint}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def poll_status_loop(self):
        """Polls server every 1 second to update status."""
        while self.running:
            data = self.api_get("/api/status")
            with self.lock:
                if data:
                    self.status_data = data
                else:
                    self.status_data = {"error": "DISCONNECTED"}
            time.sleep(1.0)

    def draw_screen(self):
        with self.lock:
            data = dict(self.status_data)
            subs = list(self.subtitles[-4:])
            event_msg = self.last_event_msg

        # Clear screen
        sys.stdout.write("\033[2J\033[H")

        # Header
        sys.stdout.write(f"{C_RED}{C_BOLD}╔══════════════════════════════════════════════════════════════╗{C_RESET}\n")
        sys.stdout.write(f"{C_RED}{C_BOLD}║  VALORANT VOICE AI - MOBILE CONTROL DASHBOARD (AGY CLI)      ║{C_RESET}\n")
        sys.stdout.write(f"{C_RED}{C_BOLD}╚══════════════════════════════════════════════════════════════╝{C_RESET}\n")

        pc_info = f"PC Target: {self.host}:{self.port}"
        if "error" in data:
            status_badge = f"{C_RED}[DISCONNECTED / CHECK PC & WI-FI]{C_RESET}"
        else:
            status_badge = f"{C_GREEN}[ONLINE / CONNECTED]{C_RESET}"
        sys.stdout.write(f" {C_WHITE}{pc_info}  |  Status: {status_badge}\n")
        sys.stdout.write(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}\n")

        if "error" not in data and data:
            hp = data.get("headphone_volume", 1.0)
            mic = data.get("game_mic_volume", 1.0)
            is_muted = data.get("mute_game_mic", False)
            fps = data.get("screen_fps", 2)
            tm_trig = data.get("teammate_voice_trigger", True)
            gemini = data.get("gemini_connected", False)

            # Volume bars (10 blocks = 100%, up to 20 blocks = 200%)
            hp_blocks = int(hp * 10)
            hp_bar = f"{C_CYAN}{'█' * min(20, hp_blocks)}{C_GRAY}{'░' * max(0, 20 - hp_blocks)}{C_RESET}"
            
            mic_blocks = int(mic * 10)
            mic_bar = f"{C_YELLOW}{'█' * min(20, mic_blocks)}{C_GRAY}{'░' * max(0, 20 - mic_blocks)}{C_RESET}"

            mute_str = f"{C_RED}{C_BOLD}[MUTED]{C_RESET}" if is_muted else f"{C_GREEN}[UNMUTED]{C_RESET}"
            tm_str = f"{C_GREEN}BẬT{C_RESET}" if tm_trig else f"{C_GRAY}TẮT{C_RESET}"
            gemini_str = f"{C_GREEN}CONNECTED{C_RESET}" if gemini else f"{C_YELLOW}OFFLINE/MOCK{C_RESET}"

            sys.stdout.write(f"  {C_BOLD}🎧 Tai nghe bạn:{C_RESET}    [{hp_bar}] {int(hp*100):3d}%\n")
            sys.stdout.write(f"  {C_BOLD}🎙️ Mic game (Team):{C_RESET} [{mic_bar}] {int(mic*100):3d}%  {mute_str}\n")
            sys.stdout.write(f"  {C_BOLD}🖥️ Live Stream FPS:{C_RESET} {C_CYAN}{fps} FPS{C_RESET}  |  Đồng đội gọi AI: {tm_str}  |  Gemini: {gemini_str}\n")
            sys.stdout.write(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}\n")

            # Pending Chat Draft section
            draft = data.get("pending_chat")
            if draft:
                sys.stdout.write(f"  {C_YELLOW}{C_BOLD}⚠️ BẢN NHÁP CHAT IN-GAME ĐANG CHỜ PHÊ DUYỆT:{C_RESET}\n")
                sys.stdout.write(f"     ID: {C_CYAN}{draft.get('draft_id')}{C_RESET}  Kênh: {draft.get('channel')}\n")
                sys.stdout.write(f"     Nội dung: {C_BOLD}\"{draft.get('content')}\"{C_RESET}\n")
                sys.stdout.write(f"     👉 Bấm {C_GREEN}[A] Cho phép{C_RESET} hoặc {C_RED}[R] Từ chối{C_RESET}\n")
                sys.stdout.write(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}\n")

        # Subtitles Feed
        sys.stdout.write(f"  {C_BOLD}💬 PHỤ ĐỀ VOICE CHAT ĐỒNG ĐỘI (DỊCH TIẾNG VIỆT THỜI GIAN THỰC):{C_RESET}\n")
        if not subs:
            sys.stdout.write(f"     {C_GRAY}(Đang lắng nghe Voice Chat in-game qua WASAPI Loopback...){C_RESET}\n")
        else:
            for s in subs:
                orig = s.get("original", "")
                trans = s.get("translated", "")
                sys.stdout.write(f"     {C_GRAY}Team: \"{orig}\"{C_RESET}\n")
                sys.stdout.write(f"     {C_GREEN}  -> \"{trans}\"{C_RESET}\n")
        sys.stdout.write(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}\n")

        # Status event banner
        if event_msg:
            sys.stdout.write(f"  {C_YELLOW}🔔 {event_msg}{C_RESET}\n")
            sys.stdout.write(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}\n")

        # Control Hotkeys Legend
        sys.stdout.write(f"{C_BOLD}PHÍM ĐIỀU KHIỂN NHANH TRÊN ĐIỆN THOẠI:{C_RESET}\n")
        sys.stdout.write(f"  [{C_CYAN}M{C_RESET}] Mute/Unmute Mic AI     [{C_GREEN}A{C_RESET}] Duyệt Chat      [{C_RED}R{C_RESET}] Hủy Chat\n")
        sys.stdout.write(f"  [{C_CYAN}+{C_RESET}] Tăng Vol Tai nghe      [{C_CYAN}-{C_RESET}] Giảm Vol Tai nghe\n")
        sys.stdout.write(f"  [{C_CYAN}T{C_RESET}] Bật/Tắt Voice Đồng đội [{C_CYAN}F{C_RESET}] Đổi FPS         [{C_RED}Q{C_RESET}] Thoát\n")
        sys.stdout.flush()

    def run(self):
        # Start background polling thread
        t_poll = threading.Thread(target=self.poll_status_loop, daemon=True)
        t_poll.start()

        # Save old terminal settings for single-key input
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)
            last_draw = 0
            while self.running:
                now = time.time()
                if now - last_draw >= 0.5:
                    self.draw_screen()
                    last_draw = now

                # Check if user pressed key without blocking
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    ch = sys.stdin.read(1).lower()
                    if ch == 'q':
                        self.running = False
                        break
                    elif ch == 'm':
                        with self.lock:
                            curr_muted = self.status_data.get("mute_game_mic", False)
                        self.api_post("/api/volume", {"mute_game_mic": not curr_muted})
                        self.last_event_msg = f"Đã {'MUTE' if not curr_muted else 'UNMUTE'} giọng AI vào game!"
                    elif ch in ['+', '=']:
                        with self.lock:
                            curr_hp = self.status_data.get("headphone_volume", 1.0)
                        new_hp = min(2.0, curr_hp + 0.2)
                        self.api_post("/api/volume", {"headphone": new_hp})
                        self.last_event_msg = f"Tăng âm lượng tai nghe: {int(new_hp*100)}%"
                    elif ch in ['-', '_']:
                        with self.lock:
                            curr_hp = self.status_data.get("headphone_volume", 1.0)
                        new_hp = max(0.0, curr_hp - 0.2)
                        self.api_post("/api/volume", {"headphone": new_hp})
                        self.last_event_msg = f"Giảm âm lượng tai nghe: {int(new_hp*100)}%"
                    elif ch == 'a':
                        with self.lock:
                            draft = self.status_data.get("pending_chat")
                        if draft:
                            self.api_post("/api/chat/action", {"draft_id": draft["draft_id"], "action": "approve"})
                            self.last_event_msg = f"ĐÃ DUYỆT GỬI TIN NHẮN [{draft['draft_id']}] VÀO TRẬN ĐẤU!"
                        else:
                            self.last_event_msg = "Không có tin nhắn nào đang chờ duyệt."
                    elif ch == 'r':
                        with self.lock:
                            draft = self.status_data.get("pending_chat")
                        if draft:
                            self.api_post("/api/chat/action", {"draft_id": draft["draft_id"], "action": "reject"})
                            self.last_event_msg = f"ĐÃ TỪ CHỐI BẢN NHÁP [{draft['draft_id']}]."
                    elif ch == 't':
                        with self.lock:
                            curr_tm = self.status_data.get("teammate_voice_trigger", True)
                        self.api_post("/api/teammate-trigger", {"enabled": not curr_tm})
                        self.last_event_msg = f"Kích hoạt voice đồng đội: {'BẬT' if not curr_tm else 'TẮT'}"
                    elif ch == 'f':
                        with self.lock:
                            curr_fps = self.status_data.get("screen_fps", 2)
                        next_fps = 3 if curr_fps == 1 else (5 if curr_fps == 3 else 1)
                        self.api_post("/api/screen", {"fps": next_fps})
                        self.last_event_msg = f"Đã chuyển FPS sang: {next_fps}"

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("\nĐã đóng Mobile Dashboard.")


def main():
    host = get_default_pc_host()
    client = PhoneTUIClient(host=host)
    client.run()


if __name__ == "__main__":
    main()
