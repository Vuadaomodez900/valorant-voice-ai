"""
System Tray Integration using pystray and Pillow.
Allows the application to run smoothly in the background while playing Valorant.
"""

import sys
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw


def create_tray_icon_image() -> Image.Image:
    """Generates a sleek, high-contrast Valorant-themed tray icon."""
    width, height = 64, 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw rounded background badge
    draw.rounded_rectangle([4, 4, 60, 60], radius=14, fill="#12161C", outline="#FF4655", width=3)

    # Draw iconic 'V' polygon
    v_points = [
        (18, 18), (32, 48), (46, 18),
        (38, 18), (32, 34), (26, 18)
    ]
    draw.polygon(v_points, fill="#FF4655")
    return image


class SystemTrayManager:
    """Manages the Windows notification area tray icon."""

    def __init__(self,
                 on_show_window: Callable[[], None],
                 on_toggle_mute: Callable[[], bool],
                 on_exit_app: Callable[[], None]):
        self.on_show_window = on_show_window
        self.on_toggle_mute = on_toggle_mute
        self.on_exit_app = on_exit_app

        self.icon = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        try:
            import pystray
            from pystray import MenuItem as item

            image = create_tray_icon_image()
            menu = pystray.Menu(
                item("Mở Bảng Điều Khiển (Open GUI)", lambda icon, item: self.on_show_window()),
                item("Mute/Unmute Giọng AI Game", lambda icon, item: self._handle_toggle_mute()),
                pystray.Menu.SEPARATOR,
                item("Thoát Hoàn Toàn (Exit)", lambda icon, item: self._handle_exit())
            )

            self.icon = pystray.Icon("ValorantVoiceAI", image, "Valorant Voice AI Companion", menu)
            self._thread = threading.Thread(target=self.icon.run, daemon=True, name="SystemTrayThread")
            self._thread.start()
            print("[SystemTray] System tray icon initialized.")
        except Exception as e:
            print(f"[SystemTray] Failed to start system tray: {e}")

    def _handle_toggle_mute(self) -> None:
        muted = self.on_toggle_mute()
        if self.icon:
            status_text = "AI Mic Muted to Game" if muted else "AI Mic Live to Game"
            self.icon.notify(status_text, "Valorant Voice AI")

    def _handle_exit(self) -> None:
        if self.icon:
            self.icon.stop()
        self.on_exit_app()

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
