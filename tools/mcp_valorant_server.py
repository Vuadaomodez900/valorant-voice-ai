#!/usr/bin/env python3
"""
Valorant Voice Ops MCP Server (Model Context Protocol - Stdio Transport).
Enables AGY CLI on Android Phone (Termux) to connect, inspect, and control
the Valorant Voice AI Companion running on a Windows PC over local Wi-Fi / LAN.
"""

import sys
import os
import json
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

CONFIG_FILE = Path("/data/data/com.termux/files/home/.gemini/config/valorant_pc.json")
DEFAULT_PORT = 8000


def get_configured_pc_host() -> str:
    """Reads saved PC IP address from config file or env var, fallback to 127.0.0.1."""
    env_ip = os.environ.get("VALORANT_PC_IP")
    if env_ip:
        return env_ip.strip()

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("host", "127.0.0.1")
        except Exception:
            pass
    return "127.0.0.1"


def save_configured_pc_host(host: str, port: int = DEFAULT_PORT) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"host": host.strip(), "port": port}, f, indent=2)


def get_base_url(host: str = "") -> str:
    """Resolves base URL supporting IPs, Tailscale (100.x.y.z), custom ports, or tunnels (https://)."""
    target = host.strip() if host else get_configured_pc_host()
    if not target:
        target = "127.0.0.1"
    if target.startswith("http://") or target.startswith("https://"):
        return target.rstrip("/")
    if ":" in target:
        return f"http://{target}"
    return f"http://{target}:{DEFAULT_PORT}"


def make_http_request(endpoint: str, method: str = "GET", payload: Optional[Dict] = None, host: str = "", timeout: float = 3.0) -> Dict[str, Any]:
    base_url = get_base_url(host)
    url = f"{base_url}{endpoint}"

    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if resp.headers.get_content_type() == "application/json":
                return json.loads(body)
            return {"status": "ok", "body": body}
    except urllib.error.URLError as e:
        return {"error": f"Không thể kết nối đến PC ({url}): {e.reason}"}
    except Exception as e:
        return {"error": f"Lỗi yêu cầu ({url}): {str(e)}"}


def probe_single_ip(ip: str, port: int = DEFAULT_PORT, timeout: float = 0.3) -> Optional[str]:
    """Quick socket probe to check if PC app is responding on port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.close()
        # Verify it's actually Valorant Voice AI
        res = make_http_request("/api/status", host=ip, timeout=1.0)
        if "headphone_volume" in res:
            return ip
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    return None


def scan_local_subnet() -> List[str]:
    """Scans local /24 subnet for PCs running Valorant Voice AI."""
    # Find local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
    except Exception:
        my_ip = "192.168.1.100"
    finally:
        s.close()

    parts = my_ip.split(".")
    if len(parts) != 4:
        return []
    subnet_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."

    found_hosts = []
    ips_to_scan = [f"{subnet_prefix}{i}" for i in range(1, 255)]

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(probe_single_ip, ip): ip for ip in ips_to_scan}
        for future in as_completed(futures):
            res = future.result()
            if res:
                found_hosts.append(res)
    return found_hosts


# ------------------ MCP Protocol Handlers ------------------

def send_response(response: Dict[str, Any]):
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_initialize(req_id: Any) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "valorant-voice-ops",
                "version": "1.0.0"
            }
        }
    }


def handle_tools_list(req_id: Any) -> Dict[str, Any]:
    tools = [
        {
            "name": "get_valorant_status",
            "description": "Lấy trạng thái vận hành của Valorant Voice AI trên Windows PC (Âm lượng tai nghe/mic, Mute, FPS màn hình, Trạng thái Gemini, Đang chạy Valorant hay không, và Bản nháp chat chờ duyệt).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "IP của PC (tùy chọn, mặc định lấy IP đã cấu hình)"}
                }
            }
        },
        {
            "name": "set_audio_volume",
            "description": "Điều chỉnh âm lượng tai nghe (0.0-2.0), âm lượng mic game (0.0-2.0), hoặc bật/tắt Mute giọng AI vào game.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "headphone": {"type": "number", "description": "Âm lượng tai nghe người dùng (0.0 đến 2.0, ví dụ 1.2 là 120%)"},
                    "game_mic": {"type": "number", "description": "Âm lượng mic game cho đồng đội (0.0 đến 2.0)"},
                    "mute_game_mic": {"type": "boolean", "description": "True để Mute giọng AI vào game, False để Unmute"},
                    "host": {"type": "string", "description": "IP PC (tùy chọn)"}
                }
            }
        },
        {
            "name": "handle_chat_draft",
            "description": "Duyệt hoặc từ chối gửi tin nhắn chat do AI đề xuất vào Valorant (Permission-gated chat).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "ID bản nháp tin nhắn (lấy từ get_valorant_status)"},
                    "action": {"type": "string", "enum": ["approve", "reject"], "description": "'approve' để cho phép gửi, 'reject' để hủy bỏ"},
                    "host": {"type": "string", "description": "IP PC (tùy chọn)"}
                },
                "required": ["draft_id", "action"]
            }
        },
        {
            "name": "set_screen_fps",
            "description": "Điều chỉnh tốc độ khung hình (FPS) của luồng quay màn hình gửi lên Gemini Live API (1 đến 10 FPS).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "fps": {"type": "integer", "description": "FPS (1-10, khuyến nghị 2 hoặc 3 để mượt và tiết kiệm token)"},
                    "host": {"type": "string", "description": "IP PC (tùy chọn)"}
                },
                "required": ["fps"]
            }
        },
        {
            "name": "toggle_teammate_trigger",
            "description": "Bật hoặc tắt tính năng cho phép đồng đội trong Voice Chat Valorant gọi 'Hey Gemini' để AI trả lời qua mic game.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "True để bật, False để tắt"},
                    "host": {"type": "string", "description": "IP PC (tùy chọn)"}
                },
                "required": ["enabled"]
            }
        },
        {
            "name": "send_tactical_callout",
            "description": "Gửi một chỉ thị chiến thuật hoặc nội dung callout từ AGY CLI trên điện thoại sang máy tính Windows.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Nội dung callout (ví dụ: 'Địch đang đặt Spike tại site A, 2 người thủ')"},
                    "channel": {"type": "string", "enum": ["team", "all"], "description": "Kênh chat game ('team' hoặc 'all')"},
                    "host": {"type": "string", "description": "IP PC (tùy chọn)"}
                },
                "required": ["text"]
            }
        },
        {
            "name": "scan_and_connect_pc",
            "description": "Quét mạng Wi-Fi cục bộ để tự động tìm IP máy tính Windows đang chạy Valorant Voice AI và lưu lại cấu hình.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pc_ip": {"type": "string", "description": "IP cụ thể của PC nếu bạn đã biết (để kiểm tra và lưu)"}
                }
            }
        },
        {
            "name": "auto_fix_valorant_app",
            "description": "Tự động kích hoạt cơ chế Self-Healing trên PC: tự cài driver Virtual Cable còn thiếu, tự kết nối lại thiết bị âm thanh, tự khôi phục tunnel Internet và sửa lỗi hệ thống tức thì.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "IP hoặc URL của PC (tùy chọn)"}
                }
            }
        },
        {
            "name": "get_app_diagnostics",
            "description": "Lấy báo cáo chẩn đoán chi tiết tình trạng sức khỏe của từng thành phần trên PC (Driver, Audio Router, Screen DXGI, Gemini Live API, Game process, Internet tunnel) kèm điểm sức khỏe và danh sách vấn đề phát hiện.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "IP hoặc URL của PC (tùy chọn)"}
                }
            }
        },
        {
            "name": "update_app_config",
            "description": "Cho phép AI trực tiếp thay đổi và nạp nóng bất kỳ cấu hình nào của ứng dụng trên PC ngay lập tức mà không cần khởi động lại (ví dụ: 'gemini.api_key', 'audio.volume_headphone', 'screen.fps_live_stream', 'overlay.mode').",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "updates": {"type": "object", "description": "Từ điển key-value chứa các cài đặt cần cập nhật (ví dụ: {'overlay.mode': 'notification', 'audio.volume_headphone': 1.2})"},
                    "host": {"type": "string", "description": "IP hoặc URL của PC (tùy chọn)"}
                },
                "required": ["updates"]
            }
        }
    ]
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": tools
        }
    }


def handle_tools_call(req_id: Any, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    text_result = ""
    host = args.get("host", "")

    if name == "get_valorant_status":
        res = make_http_request("/api/status", host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}\n💡 Mẹo: Chạy 'scan_and_connect_pc' để tự động tìm IP PC trên mạng Wi-Fi."
        else:
            pc = host or get_configured_pc_host()
            hp_pct = int(res.get("headphone_volume", 1.0) * 100)
            mic_pct = int(res.get("game_mic_volume", 1.0) * 100)
            muted_str = "🔇 ĐANG MUTE" if res.get("mute_game_mic") else "🔊 ĐANG BẬT"
            tm_str = "BẬT (Đồng đội gọi 'Hey Gemini' AI sẽ nói vào mic game)" if res.get("teammate_voice_trigger") else "TẮT"
            gemini_str = "ĐÃ KẾT NỐI" if res.get("gemini_connected") else "CHỜ KẾT NỐI (Offline Mode)"
            cable_str = "ĐÃ CÀI ĐẶT" if res.get("has_virtual_cable") else "CHƯA CÀI ĐẶT"
            draft = res.get("pending_chat")

            text_result = (
                f"🎮 TRẠNG THÁI VALORANT VOICE AI (PC: {pc}:{DEFAULT_PORT}):\n"
                f"- Âm lượng Tai nghe: {hp_pct}%\n"
                f"- Âm lượng Mic Game: {mic_pct}%\n"
                f"- Trạng thái Mic Game: {muted_str}\n"
                f"- Live Screen FPS: {res.get('screen_fps', 2)} FPS\n"
                f"- Kích hoạt Voice đồng đội: {tm_str}\n"
                f"- Kết nối Gemini Live API: {gemini_str}\n"
                f"- Driver Virtual Cable: {cable_str}\n"
            )
            if draft:
                text_result += (
                    f"\n⚠️ CÓ BẢN NHÁP CHAT CHỜ BẠN DUYỆT:\n"
                    f"- ID: {draft.get('draft_id')}\n"
                    f"- Nội dung: \"{draft.get('content')}\"\n"
                    f"- Kênh: {draft.get('channel')}\n"
                    f"👉 Ra lệnh duyệt: 'handle_chat_draft' với draft_id='{draft.get('draft_id')}', action='approve'"
                )

    elif name == "set_audio_volume":
        payload = {}
        if "headphone" in args:
            payload["headphone"] = float(args["headphone"])
        if "game_mic" in args:
            payload["game_mic"] = float(args["game_mic"])
        if "mute_game_mic" in args:
            payload["mute_game_mic"] = bool(args["mute_game_mic"])

        res = make_http_request("/api/volume", method="POST", payload=payload, host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            text_result = f"✅ Đã cập nhật âm thanh trên PC: {payload}"

    elif name == "handle_chat_draft":
        draft_id = args.get("draft_id", "")
        action = args.get("action", "approve")
        payload = {"draft_id": draft_id, "action": action}
        res = make_http_request("/api/chat/action", method="POST", payload=payload, host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            status = res.get("status", "")
            if status == "sent":
                text_result = f"✅ ĐÃ DUYỆT VÀ GỬI TIN NHẮN [{draft_id}] VÀO CHAT TRẬN ĐẤU VALORANT!"
            elif status == "rejected":
                text_result = f"🗑️ ĐÃ TỪ CHỐI / HỦY BỎ bản nháp [{draft_id}]."
            else:
                text_result = f"ℹ️ Trạng thái xử lý: {res}"

    elif name == "set_screen_fps":
        fps = int(args.get("fps", 2))
        res = make_http_request("/api/screen", method="POST", payload={"fps": fps}, host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            text_result = f"✅ Đã điều chỉnh tốc độ Live Screen Stream trên PC sang: {fps} FPS"

    elif name == "toggle_teammate_trigger":
        enabled = bool(args.get("enabled", True))
        res = make_http_request("/api/teammate-trigger", method="POST", payload={"enabled": enabled}, host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            text_result = f"✅ Kích hoạt voice chat đồng đội ('Hey Gemini'): {'BẬT' if enabled else 'TẮT'}"

    elif name == "send_tactical_callout":
        text = args.get("text", "")
        channel = args.get("channel", "team")
        res = make_http_request("/api/callout", method="POST", payload={"text": text, "channel": channel}, host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            text_result = f"✅ Đã gửi chỉ thị chiến thuật: \"{text}\" (Bản nháp ID: {res.get('draft_id')})"

    elif name == "scan_and_connect_pc":
        direct_ip = args.get("pc_ip", "").strip()
        if direct_ip:
            res = make_http_request("/api/status", host=direct_ip, timeout=3.0)
            target_display = get_base_url(direct_ip)
            if "headphone_volume" in res:
                save_configured_pc_host(direct_ip)
                text_result = f"✅ Kết nối thành công đến PC tại {target_display} và đã lưu cấu hình làm mặc định!"
            else:
                err_msg = res.get("error", "Không phản hồi")
                text_result = f"❌ Không thể xác nhận Valorant Voice AI tại {target_display} ({err_msg}). Kiểm tra app đã mở chưa."
        else:
            text_result = "🔍 Đang quét dải mạng Wi-Fi cục bộ để tìm PC..."
            found = scan_local_subnet()
            if found:
                best_ip = found[0]
                save_configured_pc_host(best_ip)
                text_result = (
                    f"✅ ĐÃ TÌM THẤY PC ĐANG CHẠY VALORANT VOICE AI TẠI IP: {best_ip}\n"
                    f"📁 Đã lưu cấu hình làm mặc định. Bây giờ bạn có thể điều khiển trực tiếp bằng giọng nói hoặc chat trong AGY CLI!"
                )
            else:
                curr = get_configured_pc_host()
                curr_display = get_base_url(curr)
                text_result = (
                    f"⚠️ Không tìm thấy PC tự động trong mạng LAN hiện tại.\n"
                    f"Địa chỉ hiện đang lưu: {curr_display}\n"
                    f"👉 Nếu không chung Wi-Fi (dùng 4G/5G hoặc mạng khác):\n"
                    f"   1. Dùng Tailscale (khuyên dùng): Nhập IP Tailscale dạng 100.x.y.z (ví dụ: scan_and_connect_pc với pc_ip='100.85.12.34').\n"
                    f"   2. Dùng Cloudflare Tunnel / ngrok: Nhập URL public (ví dụ: pc_ip='https://xxx.trycloudflare.com')."
                )
    elif name == "auto_fix_valorant_app":
        res = make_http_request("/api/auto-fix", method="POST", host=host, timeout=12.0)
        if "error" in res:
            text_result = f"❌ Lỗi khi tự sửa ứng dụng: {res['error']}"
        else:
            actions = res.get("actions_taken", [])
            health = res.get("health_after_fix", 100)
            status = res.get("status", "HEALTHY")
            act_str = "\n".join([f"  + {a}" for a in actions]) if actions else "  + Mọi thành phần đều hoạt động bình thường, không cần sửa đổi."
            text_result = (
                f"🔧 KẾT QUẢ TỰ ĐỘNG SỬA LỖI & PHỤC HỒI (SELF-HEALING):\n"
                f"- Điểm sức khỏe sau khi fix: {health}/100 ({status})\n"
                f"- Các hành động đã thực hiện:\n{act_str}"
            )

    elif name == "get_app_diagnostics":
        res = make_http_request("/api/diagnostics", method="GET", host=host)
        if "error" in res:
            text_result = f"❌ {res['error']}"
        else:
            score = res.get("health_score", 100)
            status = res.get("status", "HEALTHY")
            sub = res.get("subsystems", {})
            issues = res.get("issues", [])
            warnings = res.get("warnings", [])

            sub_driver = "✅ ĐÃ CÀI ĐẶT" if sub.get("driver", {}).get("vbcable_installed") else "❌ CHƯA CÓ"
            sub_audio = "✅ HOẠT ĐỘNG" if sub.get("audio", {}).get("running") else "❌ DỪNG"
            sub_screen = f"✅ {sub.get('screen', {}).get('fps', 2)} FPS" if sub.get("screen", {}).get("running") else "❌ DỪNG"
            sub_gemini = "✅ KẾT NỐI" if sub.get("gemini", {}).get("connected") else ("⚠️ CÓ KEY NHƯNG CHƯA KẾT NỐI" if sub.get("gemini", {}).get("has_key") else "⚠️ CHƯA CÓ KEY")
            sub_tunnel = f"🌐 {sub.get('tunnel', {}).get('url')}" if sub.get("tunnel", {}).get("active") and sub.get("tunnel", {}).get("url") else "⚪ CHƯA BẬT"
            sub_game = f"🎮 ĐANG CHƠI (PID: {sub.get('game', {}).get('pid')})" if sub.get("game", {}).get("valorant_running") else "⚪ CHƯA MỞ VALORANT"

            issue_str = "\n".join([f"  - ❌ {i}" for i in issues]) if issues else "  - Không có lỗi nghiêm trọng."
            warn_str = "\n".join([f"  - ⚠️ {w}" for w in warnings]) if warnings else ""

            text_result = (
                f"📊 BÁO CÁO CHẨN ĐOÁN HỆ THỐNG VALORANT VOICE AI:\n"
                f"- Điểm sức khỏe: {score}/100 [{status}]\n"
                f"- Virtual Cable Driver: {sub_driver}\n"
                f"- Audio Router Streams: {sub_audio}\n"
                f"- Screen Capture DXGI:  {sub_screen}\n"
                f"- Gemini Live API:      {sub_gemini}\n"
                f"- Internet Tunnel:      {sub_tunnel}\n"
                f"- Tiến trình Valorant:  {sub_game}\n\n"
                f"🚨 Vấn đề phát hiện:\n{issue_str}\n"
            )
            if warn_str:
                text_result += f"\n💡 Cảnh báo:\n{warn_str}\n"
            if issues:
                text_result += "\n👉 Gợi ý: Hãy ra lệnh 'auto_fix_valorant_app' để hệ thống tự động sửa chữa ngay lập tức!"

    elif name == "update_app_config":
        updates = args.get("updates", {})
        res = make_http_request("/api/config", method="POST", payload={"updates": updates}, host=host)
        if "error" in res:
            text_result = f"❌ Lỗi cập nhật cấu hình: {res['error']}"
        else:
            text_result = f"✅ AI đã áp dụng nóng cấu hình mới thành công:\n{json.dumps(updates, indent=2, ensure_ascii=False)}"

    else:
        text_result = f"Lỗi: Không tìm thấy tool '{name}'"

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text_result
                }
            ]
        }
    }


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            send_response(handle_initialize(req_id))
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send_response(handle_tools_list(req_id))
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            send_response(handle_tools_call(req_id, name, args))
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        else:
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found"
                    }
                })


if __name__ == "__main__":
    main()
