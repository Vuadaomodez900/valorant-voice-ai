"""
PyQt6 Non-Intrusive Desktop Overlay for Valorant.
Design Specifications:
- Borderless, translucent, frameless window running on Windows DWM.
- Click-through capable via WS_EX_TRANSPARENT.
- Excluded from all screen capture and OBS via SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE = 0x11).
- 2 Main Functions:
  1. Real-time translation of teammates' in-game voice chat to Vietnamese (auto-scrolling, fading).
  2. Gemini Activity & QA card + Permission-Gated Chat Draft approval box.
"""

import sys
import ctypes
from ctypes import wintypes
import time
from typing import Optional, Dict

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QScrollArea
    )
    from PyQt6.QtGui import QFont, QColor
except ImportError:
    QApplication = None

# Windows Win32 API Constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00000080
GWL_EXSTYLE = -20


def apply_capture_exclusion(hwnd: int) -> bool:
    """Excludes this window from DXGI Desktop Duplication & OBS capture."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        success = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if success:
            print("[Overlay] SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) applied successfully.")
            return True
        else:
            print(f"[Overlay] SetWindowDisplayAffinity error code: {ctypes.get_last_error()}")
    except Exception as e:
        print(f"[Overlay] Failed to apply capture exclusion: {e}")
    return False


def set_click_through(hwnd: int, enable: bool) -> None:
    """Toggles WS_EX_TRANSPARENT flag to let mouse clicks pass through directly to Valorant."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long

        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        else:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
    except Exception as e:
        print(f"[Overlay] Error setting click-through: {e}")


class OverlaySignals(QObject):
    subtitle_received = pyqtSignal(dict)
    gemini_response_received = pyqtSignal(str)
    chat_draft_received = pyqtSignal(dict)
    status_updated = pyqtSignal(str)


class ValorantOverlayWindow(QMainWindow):
    """Modern translucent HUD overlay."""

    def __init__(self, click_through: bool = False, opacity: float = 0.90):
        super().__init__()
        self.is_click_through = click_through
        self.window_opacity = opacity

        self.signals = OverlaySignals()
        self.signals.subtitle_received.connect(self.add_subtitle)
        self.signals.gemini_response_received.connect(self.display_gemini_response)
        self.signals.chat_draft_received.connect(self.display_chat_draft)
        self.signals.status_updated.connect(self.update_status_bar)

        self.current_draft_id: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Valorant AI Companion Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(self.window_opacity)

        # Overlay geometry: positioned neatly at top-right
        self.resize(380, 520)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 400, 40)

        # Central container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Main dark card container
        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(18, 22, 28, 230);
                border: 1px solid rgba(255, 70, 85, 120);
                border-radius: 10px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        # 1. Header / Status Bar
        header_layout = QHBoxLayout()
        title_label = QLabel("VALORANT VOICE AI")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FF4655; border: none; background: transparent;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_pill = QLabel("🟢 LIVE")
        self.status_pill.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.status_pill.setStyleSheet("""
            color: #00FF88;
            background-color: rgba(0, 255, 136, 30);
            border: 1px solid rgba(0, 255, 136, 100);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header_layout.addWidget(self.status_pill)
        card_layout.addLayout(header_layout)

        # Subtitle separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: rgba(255, 255, 255, 20); border: none; max-height: 1px;")
        card_layout.addWidget(sep1)

        # 2. Section 1: Real-Time Vietnamese Subtitles (In-game Voice Chat)
        sub_title = QLabel("VOICE CHAT DỊCH TIẾNG VIỆT")
        sub_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sub_title.setStyleSheet("color: #8B949E; border: none; background: transparent;")
        card_layout.addWidget(sub_title)

        self.subtitles_container = QVBoxLayout()
        self.subtitles_container.setSpacing(4)
        card_layout.addLayout(self.subtitles_container)

        # Default placeholder subtitle
        self.subtitle_label = QLabel("Đang lắng nghe voice chat đồng đội...")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setFont(QFont("Segoe UI", 9))
        self.subtitle_label.setStyleSheet("color: #E6EDF3; border: none; background: transparent;")
        self.subtitles_container.addWidget(self.subtitle_label)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: rgba(255, 255, 255, 20); border: none; max-height: 1px;")
        card_layout.addWidget(sep2)

        # 3. Section 2: Gemini Tactical Response Card
        ai_title = QLabel("GEMINI TACTICAL ASSIST")
        ai_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ai_title.setStyleSheet("color: #8B949E; border: none; background: transparent;")
        card_layout.addWidget(ai_title)

        self.ai_response_label = QLabel("Gọi 'Hey Gemini' để hỏi chiến thuật hoặc phân tích pha vừa qua.")
        self.ai_response_label.setWordWrap(True)
        self.ai_response_label.setFont(QFont("Segoe UI", 9))
        self.ai_response_label.setStyleSheet("color: #58A6FF; border: none; background: transparent;")
        card_layout.addWidget(self.ai_response_label)

        # 4. Section 3: Permission-Gated Chat Draft Card
        self.draft_frame = QFrame()
        self.draft_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 38, 48, 200);
                border: 1px solid #E3B341;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        draft_layout = QVBoxLayout(self.draft_frame)
        draft_layout.setContentsMargins(6, 6, 6, 6)
        draft_layout.setSpacing(6)

        draft_header = QLabel("⚡ BẢN NHÁP CHAT GAME (CHỜ DUYỆT)")
        draft_header.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        draft_header.setStyleSheet("color: #F0883E; border: none; background: transparent;")
        draft_layout.addWidget(draft_header)

        self.draft_content_label = QLabel("Chưa có tin nhắn nháp nào.")
        self.draft_content_label.setWordWrap(True)
        self.draft_content_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.draft_content_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        draft_layout.addWidget(self.draft_content_label)

        btn_layout = QHBoxLayout()
        self.btn_send = QPushButton("✔ GỬI VÀO TEAM")
        self.btn_send.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                border-radius: 4px;
                padding: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #2EA043; }
        """)
        self.btn_send.clicked.connect(self.approve_current_draft)
        btn_layout.addWidget(self.btn_send)

        self.btn_cancel = QPushButton("✖ HỦY")
        self.btn_cancel.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #DA3633;
                color: white;
                border-radius: 4px;
                padding: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #F85149; }
        """)
        self.btn_cancel.clicked.connect(self.reject_current_draft)
        btn_layout.addWidget(self.btn_cancel)
        draft_layout.addLayout(btn_layout)

        card_layout.addWidget(self.draft_frame)
        self.draft_frame.hide()  # Hidden until a draft is requested

        main_layout.addWidget(self.card)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Apply Windows 10/11 Display Affinity to exclude from screen capture
        hwnd = int(self.winId())
        apply_capture_exclusion(hwnd)
        if self.is_click_through:
            set_click_through(hwnd, True)

    def add_subtitle(self, data: dict) -> None:
        """Updates voice chat translation subtitle."""
        original = data.get("original", "")
        translated = data.get("translated", "")
        self.subtitle_label.setText(f"<b>{original}</b><br><span style='color: #00FF88;'>👉 {translated}</span>")

    def display_gemini_response(self, text: str) -> None:
        self.ai_response_label.setText(text)

    def display_chat_draft(self, draft: dict) -> None:
        self.current_draft_id = draft.get("draft_id")
        content = draft.get("content", "")
        self.draft_content_label.setText(f'"{content}"')
        self.draft_frame.show()

    def approve_current_draft(self) -> None:
        if self.current_draft_id:
            from core.in_game_chat import chat_manager
            chat_manager.approve_and_send(self.current_draft_id)
            self.draft_frame.hide()
            self.current_draft_id = None

    def reject_current_draft(self) -> None:
        if self.current_draft_id:
            from core.in_game_chat import chat_manager
            chat_manager.reject(self.current_draft_id)
            self.draft_frame.hide()
            self.current_draft_id = None

    def update_status_bar(self, status: str) -> None:
        self.status_pill.setText(status)


def run_overlay_standalone() -> None:
    """Launches overlay as independent application or child process."""
    if QApplication is None:
        print("[Overlay] PyQt6 not installed. Overlay cannot start.")
        return
    app = QApplication(sys.argv)
    window = ValorantOverlayWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_overlay_standalone()
