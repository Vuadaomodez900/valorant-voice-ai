#!/usr/bin/env python3
"""
AGY CLI Interactive Shell for Valorant Voice AI Companion.
Runs directly in the terminal (Windows, Linux, Termux).
Connects to the local or remote PC and provides an interactive AI command prompt.
"""

import sys
import os
import json
import socket
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_FILE = Path.home() / ".gemini" / "config" / "valorant_pc.json"
DEFAULT_PORT = 8000

# ANSI Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[38;5;196m"
C_CYAN = "\033[38;5;51m"
C_GREEN = "\033[38;5;48m"
C_YELLOW = "\033[38;5;220m"
C_GRAY = "\033[38;5;244m"
C_WHITE = "\033[38;5;255m"


def get_configured_host() -> str:
    env_ip = os.environ.get("VALORANT_PC_IP")
    if env_ip:
        return env_ip.strip()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("host", "127.0.0.1")
        except Exception:
            pass
    return "127.0.0.1"


def save_configured_host(host: str) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"host": host.strip(), "port": DEFAULT_PORT}, f, indent=2)


class AGYInteractiveShell:
    def __init__(self, host: str = ""):
        self.host = host.strip() if host else get_configured_host()
        self.port = DEFAULT_PORT
        self.running = True

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def api_get(self, endpoint: str) -> dict:
        try:
            url = f"{self.base_url}{endpoint}"
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"error": f"Không thể kết nối đến {self.host}:{self.port} ({e.reason})"}
        except Exception as e:
            return {"error": str(e)}

    def api_post(self, endpoint: str, payload: dict) -> dict:
        try:
            url = f"{self.base_url}{endpoint}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"error": f"Không thể gửi lệnh đến {self.host}:{self.port} ({e.reason})"}
        except Exception as e:
            return {"error": str(e)}

    def print_banner(self):
        print(f"{C_RED}{C_BOLD}╔══════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"{C_RED}{C_BOLD}║          VALORANT VOICE AI - AGY CLI INTERACTIVE SHELL        ║{C_RESET}")
        print(f"{C_RED}{C_BOLD}╚══════════════════════════════════════════════════════════════╝{C_RESET}")
        print(f" {C_WHITE}Target PC: {C_CYAN}{self.host}:{self.port}{C_RESET}  |  Gõ {C_YELLOW}'help'{C_RESET} để xem lệnh, {C_YELLOW}'exit'{C_RESET} để thoát.")
        print(f"{C_GRAY}────────────────────────────────────────────────────────────────{C_RESET}")

    def cmd_status(self):
        data = self.api_get("/api/status")
        if "error" in data:
            print(f"{C_RED}❌ {data['error']}{C_RESET}")
            print(f"{C_GRAY}Mẹo: Gõ 'scan' để tự động quét tìm IP máy tính trên mạng Wi-Fi.{C_RESET}")
            return

        hp = int(data.get("headphone_volume", 1.0) * 100)
        mic = int(data.get("game_mic_volume", 1.0) * 100)
        is_muted = data.get("mute_game_mic", False)
        muted_str = f"{C_RED}🔇 MUTED{C_RESET}" if is_muted else f"{C_GREEN}🔊 BẬT{C_RESET}"
        cable = f"{C_GREEN}ĐÃ CÀI ĐẶT{C_RESET}" if data.get("has_virtual_cable") else f"{C_RED}CHƯA CÀI{C_RESET}"
        gemini = f"{C_GREEN}CONNECTED{C_RESET}" if data.get("gemini_connected") else f"{C_YELLOW}OFFLINE/MOCK{C_RESET}"
        tm = f"{C_GREEN}BẬT{C_RESET}" if data.get("teammate_voice_trigger") else f"{C_GRAY}TẮT{C_RESET}"

        print(f"\n{C_BOLD}🎮 THÔNG TIN HỆ THỐNG TRỰC TIẾP:{C_RESET}")
        print(f"  • Âm lượng Tai nghe:     {C_CYAN}{hp}%{C_RESET}")
        print(f"  • Âm lượng Mic Game:     {C_YELLOW}{mic}%{C_RESET} ({muted_str})")
        print(f"  • Live Stream FPS:       {C_CYAN}{data.get('screen_fps', 2)} FPS{C_RESET}")
        print(f"  • Kích hoạt Voice Đồng đội: {tm}")
        print(f"  • Virtual Audio Cable:   {cable}")
        print(f"  • Gemini Multimodal Live: {gemini}")

        draft = data.get("pending_chat")
        if draft:
            print(f"\n{C_YELLOW}⚠️ BẢN NHÁP CHAT CHỜ DUYỆT:{C_RESET}")
            print(f"  ID: {C_CYAN}{draft.get('draft_id')}{C_RESET} | Kênh: {draft.get('channel')}")
            print(f"  Nội dung: {C_BOLD}\"{draft.get('content')}\"{C_RESET}")
            print(f"  👉 Gõ {C_GREEN}'approve'{C_RESET} để gửi vào trận, hoặc {C_RED}'reject'{C_RESET} để hủy.")

    def cmd_mute(self, state: bool):
        res = self.api_post("/api/volume", {"mute_game_mic": state})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            if state:
                print(f"{C_RED}🔇 ĐÃ MUTE GIỌNG AI VÀO GAME MIC (Yên tâm clutch!){C_RESET}")
            else:
                print(f"{C_GREEN}🔊 ĐÃ UNMUTE GIỌNG AI VÀO GAME MIC!{C_RESET}")

    def cmd_volume(self, target: str, val_str: str):
        try:
            val_str = val_str.replace("%", "").strip()
            val = float(val_str)
            if val > 2.0:
                val = val / 100.0 # Convert percentage (e.g. 150 -> 1.5)
            val = max(0.0, min(2.0, val))
        except ValueError:
            print(f"{C_RED}❌ Giá trị âm lượng không hợp lệ. Ví dụ: 'vol 1.2' hoặc 'vol 120%'{C_RESET}")
            return

        payload = {"headphone": val} if target == "hp" else {"game_mic": val}
        res = self.api_post("/api/volume", payload)
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            name = "Tai nghe" if target == "hp" else "Mic Game"
            print(f"{C_GREEN}✅ Đã đặt âm lượng {name} sang: {int(val * 100)}%{C_RESET}")

    def cmd_approve_draft(self):
        data = self.api_get("/api/status")
        draft = data.get("pending_chat") if isinstance(data, dict) else None
        if not draft:
            print(f"{C_GRAY}ℹ️ Hiện không có bản nháp tin nhắn nào đang chờ duyệt.{C_RESET}")
            return
        draft_id = draft.get("draft_id")
        res = self.api_post("/api/chat/action", {"draft_id": draft_id, "action": "approve"})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            print(f"{C_GREEN}✅ ĐÃ DUYỆT VÀ GỬI TIN NHẮN [{draft_id}] VÀO VALORANT!{C_RESET}")

    def cmd_reject_draft(self):
        data = self.api_get("/api/status")
        draft = data.get("pending_chat") if isinstance(data, dict) else None
        if not draft:
            print(f"{C_GRAY}ℹ️ Hiện không có bản nháp tin nhắn nào.{C_RESET}")
            return
        draft_id = draft.get("draft_id")
        res = self.api_post("/api/chat/action", {"draft_id": draft_id, "action": "reject"})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            print(f"{C_YELLOW}🗑️ Đã từ chối bản nháp [{draft_id}].{C_RESET}")

    def cmd_teammate_toggle(self, enabled: bool):
        res = self.api_post("/api/teammate-trigger", {"enabled": enabled})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            state = f"{C_GREEN}BẬT{C_RESET}" if enabled else f"{C_GRAY}TẮT{C_RESET}"
            print(f"✅ Quyền cho đồng đội gọi 'Hey Gemini': {state}")

    def cmd_fps(self, fps_str: str):
        try:
            fps = int(fps_str)
            if not (1 <= fps <= 10):
                raise ValueError()
        except ValueError:
            print(f"{C_RED}❌ FPS phải là số nguyên từ 1 đến 10. Ví dụ: 'fps 3'{C_RESET}")
            return

        res = self.api_post("/api/screen", {"fps": fps})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            print(f"{C_GREEN}✅ Đã đổi Live Screen Stream sang: {fps} FPS{C_RESET}")

    def cmd_callout(self, text: str):
        if not text.strip():
            print(f"{C_RED}❌ Thiếu nội dung callout. Ví dụ: 'callout Địch đặt Spike ở A'{C_RESET}")
            return
        res = self.api_post("/api/callout", {"text": text, "channel": "team"})
        if "error" in res:
            print(f"{C_RED}❌ {res['error']}{C_RESET}")
        else:
            print(f"{C_GREEN}📢 Đã phát chỉ thị chiến thuật: \"{text}\" (Bản nháp ID: {res.get('draft_id')}){C_RESET}")

    def cmd_scan(self, manual_ip: str = ""):
        if manual_ip:
            self.host = manual_ip.strip()
            save_configured_host(self.host)
            print(f"{C_GREEN}✅ Đã đổi Target PC sang: {self.host}:{self.port}{C_RESET}")
            self.cmd_status()
            return

        print(f"{C_CYAN}🔍 Đang quét mạng Wi-Fi cục bộ để tìm máy tính Windows...{C_RESET}")
        from tools.mcp_valorant_server import scan_local_subnet
        found = scan_local_subnet()
        if found:
            self.host = found[0]
            save_configured_host(self.host)
            print(f"{C_GREEN}✅ ĐÃ TÌM THẤY PC TẠI ĐỊA CHỈ: {self.host}{C_RESET}")
            print(f"📁 Đã lưu cấu hình làm mặc định!")
            self.cmd_status()
        else:
            print(f"{C_YELLOW}⚠️ Không tìm thấy PC tự động trong mạng hiện tại.{C_RESET}")
            print(f"Mẹo: Bạn có thể nhập trực tiếp: 'scan <IP_HIỂN_THỊ_TRÊN_APP_PC>'")

    def print_help(self):
        print(f"""
{C_BOLD}DANH SÁCH LỆNH AGY CLI:{C_RESET}
  {C_CYAN}status{C_RESET}                 : Kiểm tra toàn bộ trạng thái app, âm lượng, FPS, Valorant
  {C_CYAN}mute / unmute{C_RESET}          : Tắt / Mở nhanh tiếng AI vào mic game
  {C_CYAN}vol <0-200%>{C_RESET}           : Đặt âm lượng tai nghe (VD: 'vol 140' hoặc 'vol 1.4')
  {C_CYAN}mic <0-200%>{C_RESET}           : Đặt âm lượng mic game cho đồng đội (VD: 'mic 100')
  {C_CYAN}approve / a{C_RESET}            : Phê duyệt gửi tin nhắn do AI đề xuất vào chat trận đấu
  {C_CYAN}reject / r{C_RESET}             : Từ chối / hủy bỏ bản nháp chat của AI
  {C_CYAN}teammate on / off{C_RESET}      : Bật / Tắt cho phép đồng đội gọi 'Hey Gemini'
  {C_CYAN}fps <1-10>{C_RESET}             : Chỉnh tốc độ khung hình luồng quay màn hình (1-10 FPS)
  {C_CYAN}callout <nội dung>{C_RESET}     : Phát chỉ thị chiến thuật vào trận đấu
  {C_CYAN}scan [ip]{C_RESET}              : Tự động quét tìm PC trên Wi-Fi hoặc nhập IP thủ công
  {C_CYAN}clear{C_RESET}                  : Xóa màn hình
  {C_CYAN}help / ?{C_RESET}               : Hiển thị hướng dẫn này
  {C_CYAN}exit / quit{C_RESET}            : Thoát shell
""")

    def run_loop(self):
        self.print_banner()
        self.cmd_status()

        while self.running:
            try:
                prompt_text = f"\n{C_RED}{C_BOLD}AGY-Valorant{C_RESET} [{C_CYAN}{self.host}{C_RESET}]> "
                cmd_line = input(prompt_text).strip()
                if not cmd_line:
                    continue

                parts = cmd_line.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if cmd in ["exit", "quit", "q"]:
                    self.running = False
                    print(f"{C_YELLOW}Tạm biệt! Đã đóng AGY CLI Shell.{C_RESET}")
                    break
                elif cmd in ["help", "?"]:
                    self.print_help()
                elif cmd == "status":
                    self.cmd_status()
                elif cmd == "mute":
                    self.cmd_mute(True)
                elif cmd == "unmute":
                    self.cmd_mute(False)
                elif cmd in ["vol", "volume", "hp"]:
                    self.cmd_volume("hp", arg)
                elif cmd == "mic":
                    self.cmd_volume("mic", arg)
                elif cmd in ["approve", "a"]:
                    self.cmd_approve_draft()
                elif cmd in ["reject", "r"]:
                    self.cmd_reject_draft()
                elif cmd == "teammate":
                    if arg.lower() in ["on", "1", "true", "bat"]:
                        self.cmd_teammate_toggle(True)
                    elif arg.lower() in ["off", "0", "false", "tat"]:
                        self.cmd_teammate_toggle(False)
                    else:
                        print("Cách dùng: teammate on  HOẶC  teammate off")
                elif cmd == "fps":
                    self.cmd_fps(arg)
                elif cmd == "callout":
                    self.cmd_callout(arg)
                elif cmd == "scan":
                    self.cmd_scan(arg)
                elif cmd == "clear":
                    os.system("clear" if os.name != "nt" else "cls")
                    self.print_banner()
                else:
                    # Treat unknown commands as tactical callouts or queries
                    print(f"{C_YELLOW}ℹ️ Coi đây là chỉ thị chiến thuật: \"{cmd_line}\"{C_RESET}")
                    self.cmd_callout(cmd_line)

            except (KeyboardInterrupt, EOFError):
                print(f"\n{C_YELLOW}Đã thoát AGY CLI Shell.{C_RESET}")
                break


def main():
    host_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ""
    shell = AGYInteractiveShell(host=host_arg)
    shell.run_loop()


if __name__ == "__main__":
    main()
