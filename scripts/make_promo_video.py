"""
Automated Promo Video Generator for Valorant Voice AI.
Renders a 9:16 vertical video (1080x1920) formatted for TikTok, Reels & Shorts.
Uses Pillow for high-contrast gaming typography and pipes directly into ffmpeg.
"""

import sys
import os
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
FPS = 30
TOTAL_SECONDS = 30
TOTAL_FRAMES = FPS * TOTAL_SECONDS

FONT_PATH = "/system/fonts/Roboto-Regular.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = None


def get_font(size: int):
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()


# Scenes definition: (start_sec, end_sec, tag, title, points, color_accent)
SCENES = [
    (
        0, 5,
        "AI GAMING REVOLUTION",
        "TRỢ LÝ AI CHƠI VALORANT\nNÓI CHUYỆN THỜI GIAN THỰC!",
        [
            "🔥 Tích hợp trực tiếp Gemini Multimodal Live API",
            "🎙️ Tương tác giọng nói rảnh tay: Gọi 'Hey Gemini'",
            "🧠 Vừa quan sát màn hình vừa phân tích bối cảnh trận đấu"
        ],
        "#FF4655"  # Valorant Red
    ),
    (
        5, 10,
        "ANTI-CHEAT COMPLIANCE",
        "100% TUÂN THỦ RIOT VANGUARD\nAN TOÀN TUYỆT ĐỐI!",
        [
            "🛡️ Quay màn hình thụ động tầng OS (DXGI Duplication)",
            "❌ KHÔNG Hook DirectX, KHÔNG Inject DLL",
            "❌ KHÔNG đọc/ghi RAM game, KHÔNG sửa file",
            "💡 Chỉ trả lời khi bạn chủ động hỏi, không spam callout"
        ],
        "#00E676"  # Emerald Green
    ),
    (
        10, 15,
        "DUAL AUDIO ROUTING",
        "ĐỊNH TUYẾN ÂM THANH 2 CHIỀU\nTÍCH HỢP DRIVER 1-CHẠM!",
        [
            "🎧 Bạn nghe thấy AI qua tai nghe",
            "🎙️ Đồng đội TRONG TRẬN cũng nghe thấy qua Mic game",
            "🔌 TÍCH HỢP SẴN Virtual Cable trong file .exe!",
            "⚡ Bấm 1 click là tự cài driver, không cần tải ngoài"
        ],
        "#00F5D4"  # Cyan Neon
    ),
    (
        15, 20,
        "REAL-TIME TRANSLATOR",
        "DỊCH VOICE CHAT ĐỒNG ĐỘI\nSANG TIẾNG VIỆT NGAY TRÊN MÀN",
        [
            "🗣️ Đồng đội call tiếng Anh -> Hiện phụ đề Tiếng Việt",
            "🖥️ Overlay trong suốt chạy trên nền Borderless Windowed",
            "👻 Tàng hình trên OBS & Discord (WDA_EXCLUDEFROMCAPTURE)",
            "⚡ Hộp duyệt tin nhắn chat in-game an toàn có kiểm soát"
        ],
        "#FFD166"  # Amber Gold
    ),
    (
        20, 25,
        "LAN MOBILE DASHBOARD",
        "ĐIỀU KHIỂN TỪ ĐIỆN THOẠI\nQUÉT MÃ QR CỰC TIỆN!",
        [
            "📱 Dùng camera điện thoại quét mã QR cùng Wi-Fi",
            "🎚️ Thanh trượt âm lượng AI tai nghe & Mic game (0-200%)",
            "🔇 Nút Mute nhanh giọng AI khi cần clutch tập trung",
            "🎭 Đổi giọng đọc Gemini: Puck, Charon, Aoede..."
        ],
        "#A78BFA"  # Neon Violet
    ),
    (
        25, 30,
        "OPEN & PLAY STANDALONE .EXE",
        "TẢI FILE .EXE CHẠY NGAY\nĐÃ ĐÓNG GÓI HOÀN TẤT!",
        [
            "📦 Mở lên là dùng ngay trên Windows 10/11",
            "⭐ Đã build sẵn trên GitHub Actions Artifacts",
            "🔗 Repo: github.com/Vuadaomodez900/valorant-voice-ai",
            "🚀 Trải nghiệm trợ lý AI Valorant thế hệ mới ngay hôm nay!"
        ],
        "#FF4655"  # Valorant Red
    )
]


def render_frame(frame_idx: int) -> Image.Image:
    t = frame_idx / FPS
    # Find current scene
    cur_scene = SCENES[-1]
    for s in SCENES:
        if s[0] <= t < s[1]:
            cur_scene = s
            break

    _, _, tag, title, points, accent_hex = cur_scene

    # Base Canvas
    img = Image.new("RGB", (WIDTH, HEIGHT), "#0B0E14")
    draw = ImageDraw.Draw(img)

    # 1. Subtle Background Grid & Pulsing Accent Header
    for y in range(0, HEIGHT, 80):
        draw.line([(0, y), (WIDTH, y)], fill="#141923", width=1)
    for x in range(0, WIDTH, 80):
        draw.line([(x, 0), (x, HEIGHT)], fill="#141923", width=1)

    # Glowing Top Bar
    draw.rectangle([0, 0, WIDTH, 160], fill="#12161F")
    draw.line([(0, 160), (WIDTH, 160)], fill=accent_hex, width=3)

    # App Header Label
    font_header = get_font(34)
    draw.text((60, 45), "VALORANT VOICE AI COMPANION", fill="#FFFFFF", font=font_header)

    font_subhead = get_font(24)
    draw.text((60, 95), "Powered by Gemini Multimodal Live API • Windows 10/11", fill="#94A3B8", font=font_subhead)

    # Pulsing Live Indicator
    pulse = int(128 + 127 * math.sin(t * 5))
    rec_color = (255, 70, 85, pulse)
    draw.ellipse([WIDTH - 120, 60, WIDTH - 80, 100], fill="#FF4655")
    font_rec = get_font(22)
    draw.text((WIDTH - 200, 68), "LIVE", fill="#FF4655", font=font_rec)

    # 2. Main Center Card
    card_margin = 60
    card_top = 220
    card_bottom = HEIGHT - 240
    draw.rounded_rectangle(
        [card_margin, card_top, WIDTH - card_margin, card_bottom],
        radius=24,
        fill="#161C26",
        outline=accent_hex,
        width=3
    )

    # Tag Badge inside card
    font_tag = get_font(24)
    draw.rounded_rectangle([card_margin + 40, card_top + 40, card_margin + 440, card_top + 90], radius=8, fill=accent_hex)
    draw.text((card_margin + 60, card_top + 52), tag, fill="#0B0E14", font=font_tag)

    # Big Title
    font_title = get_font(52)
    title_lines = title.split("\n")
    y_text = card_top + 130
    for line in title_lines:
        draw.text((card_margin + 40, y_text), line, fill="#FFFFFF", font=font_title)
        y_text += 70

    # Separator
    draw.line([(card_margin + 40, y_text + 20), (WIDTH - card_margin - 40, y_text + 20)], fill="#252F40", width=2)
    y_text += 60

    # Feature Bullet Points
    font_bullet = get_font(34)
    for p in points:
        # Box background for each bullet
        draw.rounded_rectangle(
            [card_margin + 30, y_text, WIDTH - card_margin - 30, y_text + 110],
            radius=12,
            fill="#1E2634"
        )
        draw.text((card_margin + 50, y_text + 35), p, fill="#F1F5F9", font=font_bullet)
        y_text += 140

    # 3. Bottom Progress Bar & Branding
    progress_width = int((t / TOTAL_SECONDS) * WIDTH)
    draw.rectangle([0, HEIGHT - 14, progress_width, HEIGHT], fill=accent_hex)

    font_footer = get_font(26)
    footer_text = "100% Riot Vanguard Safe • Zero DLL Injection • Passive DXGI Desktop Stream"
    draw.text((card_margin, HEIGHT - 180), footer_text, fill="#64748B", font=font_footer)

    font_cta = get_font(38)
    draw.text((card_margin, HEIGHT - 120), "👉 github.com/Vuadaomodez900/valorant-voice-ai", fill="#00F5D4", font=font_cta)

    return img


def generate_video(output_mp4: str = "docs/valorant_voice_ai_demo.mp4"):
    os.makedirs(os.path.dirname(output_mp4), exist_ok=True)
    print(f"[VideoGen] Starting video render: {WIDTH}x{HEIGHT} @ {FPS} FPS ({TOTAL_SECONDS}s)...")

    # Start ffmpeg process reading raw RGB from stdin
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-crf", "22",
        output_mp4
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    for i in range(TOTAL_FRAMES):
        frame = render_frame(i)
        proc.stdin.write(frame.tobytes())
        if (i + 1) % 150 == 0:
            print(f"[VideoGen] Rendered {i + 1}/{TOTAL_FRAMES} frames ({int((i+1)/FPS)}s / {TOTAL_SECONDS}s)...")

    proc.stdin.close()
    proc.wait()
    print(f"[VideoGen] Video created successfully at: {output_mp4}")


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "docs/valorant_voice_ai_demo.mp4"
    generate_video(out_file)
