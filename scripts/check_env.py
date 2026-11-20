"""
Environment Diagnostic & Self-Check Tool for Valorant Voice AI.
Run this script to verify your Windows system setup, audio devices, and prerequisites.
"""

import sys
import platform
import os

# Ensure safe UTF-8 output even on legacy Windows cp1252 console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def check_os():
    print("[1] KIEM TRA HE DIEU HANH:")
    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    arch = platform.architecture()[0]

    print(f"    - He dieu hanh: {os_name} {os_release} ({arch})")
    print(f"    - Phien ban build: {os_version}")

    if os_name != "Windows":
        print("    [!] CANH BAO: Ung dung duoc toi uu hoa cho Windows 10/11.")
    else:
        print("    [OK] He dieu hanh Windows tuong thich.")


def check_python():
    print("\n[2] KIEM TRA PYTHON RUNTIME:")
    py_ver = sys.version.split()[0]
    print(f"    - Phien ban Python: {py_ver}")
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        print("    [OK] Phien ban Python dat chuan (>= 3.10).")
    else:
        print("    [!] CANH BAO: Khuyen nghi Python 3.10 - 3.12.")


def check_audio():
    print("\n[3] KIEM TRA THIET BI AM THANH & VB-AUDIO CABLE:")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"    - Tim thay tong cong {len(devices)} thiet bi am thanh.")

        has_mic = False
        has_cable = False
        has_output = False

        for idx, dev in enumerate(devices):
            name = dev.get("name", "")
            in_ch = dev.get("max_input_channels", 0)
            out_ch = dev.get("max_output_channels", 0)

            if "cable" in name.lower():
                has_cable = True
                print(f"    * Da tim thay VB-Audio Cable: [{idx}] {name}")
            elif in_ch > 0 and not has_mic:
                has_mic = True
                print(f"    * Micro mac dinh: [{idx}] {name}")
            elif out_ch > 0 and not has_output:
                has_output = True
                print(f"    * Loa/Tai nghe dau ra: [{idx}] {name}")

        if not has_cable:
            print("    [!] CHU Y: Chua tim thay 'VB-Audio Virtual Cable'.")
            print("       Tai mien phi tai: https://vb-audio.com/Cable/")
        else:
            print("    [OK] Virtual Audio Cable da san sang!")

    except ImportError:
        print("    [X] sounddevice chua duoc cai dat.")
    except Exception as e:
        print(f"    [!] Loi khi quet thiet bi am thanh: {e}")


def check_screen_capture():
    print("\n[4] KIEM TRA DXGI DESKTOP DUPLICATION (SCREEN CAPTURE):")
    if sys.platform != "win32":
        print("    [INFO] Bo qua kiem tra DXGI tren OS khong phai Windows.")
        return

    try:
        import dxcam
        cam = dxcam.create(output_color="RGB")
        frame = cam.grab()
        if frame is not None:
            print(f"    [OK] DXGI Desktop Duplication hoat dong hoan hao! (Shape: {frame.shape})")
        else:
            print("    [INFO] DXGI da khoi tao thanh cong.")
    except ImportError:
        print("    [!] dxcam chua duoc cai dat. Se dung fallback capture.")
    except Exception as e:
        print(f"    [INFO] DXGI khong kha dung tren runner ({e}). Se dung fallback.")


def check_api_key():
    print("\n[5] KIEM TRA GEMINI API KEY:")
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        print(f"    [OK] Da tim thay GEMINI_API_KEY ({masked})")
    else:
        print("    [INFO] Chua dat bien moi truong GEMINI_API_KEY (Co the nhap tren GUI).")


def main():
    print_header("VALORANT VOICE AI - DIAGNOSTIC CHECK")
    check_os()
    check_python()
    check_audio()
    check_screen_capture()
    check_api_key()
    print("\n" + "=" * 65)
    print("  HOAN THANH KIEM TRA!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
