"""
Integrated Virtual Audio Cable Installer for Windows.
Eliminates manual downloads by embedding the official driver installer
and providing 1-click silent/elevated installation directly from the app.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Tuple

from core.config import get_resource_path


def is_vbcable_installed() -> bool:
    """Checks whether VB-Audio Virtual Cable is recognized by the OS audio subsystem."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        for dev in devices:
            name = dev.get("name", "").lower()
            if "cable" in name or "vb-audio" in name:
                return True
    except Exception:
        pass

    # Secondary check on Windows via registry or system files
    if sys.platform == "win32":
        try:
            import winreg
            # Check uninstall registry keys
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\VB:Audio Cable") as key:
                        return True
                except OSError:
                    pass
        except Exception:
            pass

    return False


def get_installer_executable_path() -> Path:
    """Locates the bundled setup executable within PyInstaller bundle or local source."""
    is_64bit = sys.maxsize > 2**32 or "64" in sys.platform or "64" in os.environ.get("PROCESSOR_ARCHITECTURE", "")
    exe_name = "VBCABLE_Setup_x64.exe" if is_64bit else "VBCABLE_Setup.exe"

    # Search in resource path
    bundled_path = Path(get_resource_path(f"drivers/vbcable/{exe_name}"))
    if bundled_path.exists():
        return bundled_path

    # Fallback search relative to this script
    local_path = Path(__file__).resolve().parent.parent / "drivers" / "vbcable" / exe_name
    return local_path


def install_vbcable_integrated() -> Tuple[bool, str]:
    """
    Installs the embedded VB-Audio Virtual Cable driver using Windows elevation.
    Uses '-i -h' for silent installation.
    """
    if sys.platform != "win32":
        return False, "Driver installation is only supported on Windows 10/11."

    installer_path = get_installer_executable_path()
    if not installer_path.exists():
        return False, f"Driver installer file not found at: {installer_path}"

    try:
        import ctypes
        from ctypes import wintypes

        # Run with Administrator elevation via ShellExecuteEx (verb: 'runas')
        # Switches: -i (install), -h (silent/hide GUI)
        parameters = "-i -h"
        working_dir = str(installer_path.parent)

        print(f"[CableInstaller] Launching elevated installation: {installer_path} {parameters}")

        # Execute elevated process
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            str(installer_path),
            parameters,
            working_dir,
            1  # SW_SHOWNORMAL
        )

        # HINSTANCE > 32 indicates success
        if int(result) <= 32:
            return False, f"User denied UAC administrator prompt (Error code {result})."

        # Wait up to 10 seconds for driver registration
        for _ in range(20):
            time.sleep(0.5)
            if is_vbcable_installed():
                print("[CableInstaller] VB-Audio Cable detected and registered successfully!")
                return True, "Cài đặt Virtual Cable thành công! Thiết bị đã sẵn sàng."

        return True, "Lệnh cài đặt đã được gửi. Bạn có thể cần khởi động lại máy để hoàn tất đăng ký thiết bị."

    except Exception as e:
        return False, f"Lỗi trong quá trình cài đặt driver: {e}"
