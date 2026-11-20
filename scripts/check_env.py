"""
Environment Diagnostic & Self-Check Tool for Valorant Voice AI.
Run this script to verify your Windows system setup, audio devices, and prerequisites.
"""

import sys
import platform
import os


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def check_os():
    print("[1] KIỂM TRA HỆ ĐIỀU HÀNH:")
    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    arch = platform.architecture()[0]

    print(f"    - Hệ điều hành: {os_name} {os_release} ({arch})")
    print(f"    - Phiên bản build: {os_version}")

    if os_name != "Windows":
        print("    ⚠️ CẢNH BÁO: Ứng dụng được thiết kế tối ưu hóa cho Windows 10/11.")
        print("                 (Đang chạy trên môi trường không phải Windows - chỉ phù hợp để test code)")
    else:
        print("    ✅ Hệ điều hành Windows tương thích.")


def check_python():
    print("\n[2] KIỂM TRA PYTHON RUNTIME:")
    py_ver = sys.version.split()[0]
    print(f"    - Phiên bản Python: {py_ver}")
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        print("    ✅ Phiên bản Python đạt chuẩn (>= 3.10).")
    else:
        print("    ⚠️ CẢNH BÁO: Khuyến nghị Python 3.10 - 3.12 để đảm bảo tương thích các thư viện AI.")


def check_audio():
    print("\n[3] KIỂM TRA THIẾT BỊ ÂM THANH & VB-AUDIO CABLE:")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"    - Tìm thấy tổng cộng {len(devices)} thiết bị âm thanh.")

        has_mic = False
        has_cable = False
        has_output = False

        for idx, dev in enumerate(devices):
            name = dev.get("name", "")
            in_ch = dev.get("max_input_channels", 0)
            out_ch = dev.get("max_output_channels", 0)

            if "cable" in name.lower():
                has_cable = True
                print(f"    ⭐ Đã tìm thấy VB-Audio Cable: [{idx}] {name}")
            elif in_ch > 0 and not has_mic:
                has_mic = True
                print(f"    🎤 Micro đầu vào mặc định: [{idx}] {name}")
            elif out_ch > 0 and not has_output:
                has_output = True
                print(f"    🎧 Loa/Tai nghe đầu ra: [{idx}] {name}")

        if not has_cable:
            print("    ⚠️ CHÚ Ý: Chưa tìm thấy 'VB-Audio Virtual Cable'.")
            print("       Để đưa giọng AI vào mic game Valorant cho đồng đội nghe, bạn cần cài đặt:")
            print("       👉 Tải miễn phí tại: https://vb-audio.com/Cable/")
        else:
            print("    ✅ Virtual Audio Cable đã sẵn sàng!")

    except ImportError:
        print("    ❌ sounddevice chưa được cài đặt. Chạy: pip install sounddevice")
    except Exception as e:
        print(f"    ⚠️ Lỗi khi quét thiết bị âm thanh: {e}")


def check_screen_capture():
    print("\n[4] KIỂM TRA DXGI DESKTOP DUPLICATION (SCREEN CAPTURE):")
    if sys.platform != "win32":
        print("    ℹ️ Bỏ qua kiểm tra DXGI trên hệ điều hành không phải Windows.")
        return

    try:
        import dxcam
        cam = dxcam.create(output_color="RGB")
        frame = cam.grab()
        if frame is not None:
            print(f"    ✅ DXGI Desktop Duplication hoạt động hoàn hảo! (Frame shape: {frame.shape})")
        else:
            print("    ⚠️ DXGI khởi tạo được nhưng frame tạm thời None (màn hình có thể đang tắt/khóa).")
    except ImportError:
        print("    ⚠️ dxcam chưa được cài đặt. Sẽ sử dụng fallback capture.")
    except Exception as e:
        print(f"    ⚠️ DXGI không khả dụng ({e}). Sẽ sử dụng fallback capture.")


def check_api_key():
    print("\n[5] KIỂM TRA GEMINI API KEY:")
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        print(f"    ✅ Đã tìm thấy biến môi trường GEMINI_API_KEY ({masked})")
    else:
        print("    ℹ️ Chưa đặt biến môi trường GEMINI_API_KEY.")
        print("       (Bạn có thể nhập trực tiếp trên giao diện GUI hoặc Web Dashboard khi mở ứng dụng)")


def main():
    print_header("VALORANT VOICE AI - CÔNG CỤ TỰ KIỂM TRA MÔI TRƯỜNG")
    check_os()
    check_python()
    check_audio()
    check_screen_capture()
    check_api_key()
    print("\n" + "=" * 65)
    print("  HOÀN THÀNH KIỂM TRA!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
