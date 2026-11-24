"""
PyQt6 Non-Intrusive Desktop Overlay for Valorant.
Design Specifications:
- Borderless, translucent, frameless toast notification / HUD running on Windows DWM.
- Click-through capable via WS_EX_TRANSPARENT.
- Excluded from all screen capture and OBS via SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE = 0x11).
- 2 Operation Modes:
  1. "notification" (Default): Clean, auto-hiding toast popup when teammates talk / translate.
     Never clutters or blocks crosshair, radar, or health bars. Auto-dismisses after 6s.
  2. "card": Persistent corner HUD dashboard with status, live cards, and chat drafts.
"""

import sys
import os
import json
import time
import ctypes
from ctypes import wintypes
import threading
from typing import Optional, Dict

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame
    )
    from PyQt6.QtGui import QFont, QColor
except ImportError:
    QApplication = None

from core.config import config
from core.lipsync import lipsync_analyzer

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
    viseme_received = pyqtSignal(dict)
    profile_changed = pyqtSignal(dict)
    neuro_commentary_received = pyqtSignal(dict)


class ValorantOverlayWindow(QMainWindow):
    """Modern translucent HUD overlay with toast notification, card, and tamagotchi desktop pet modes."""

    def __init__(self, click_through: bool = True, opacity: float = 0.92):
        super().__init__()
        cfg_overlay = config.data.get("overlay", {})
        self.is_click_through = cfg_overlay.get("click_through", click_through)
        self.window_opacity = cfg_overlay.get("opacity", opacity)
        self.mode = cfg_overlay.get("mode", "notification")  # "notification", "tamagotchi", or "card"
        self.duration = float(cfg_overlay.get("notification_duration", 6.0))
        self.position = cfg_overlay.get("position", "top-center")

        self.signals = OverlaySignals()
        self.signals.subtitle_received.connect(self.add_subtitle)
        self.signals.gemini_response_received.connect(self.display_gemini_response)
        self.signals.chat_draft_received.connect(self.display_chat_draft)
        self.signals.status_updated.connect(self.update_status_bar)
        self.signals.viseme_received.connect(self.update_avatar_viseme)
        self.signals.profile_changed.connect(self.update_game_profile)
        self.signals.neuro_commentary_received.connect(self.display_neuro_commentary)

        # Connect lipsync subscriber
        lipsync_analyzer.register_subscriber(lambda s: self.signals.viseme_received.emit(s))

        self.current_draft_id: Optional[str] = None
        self._drag_pos = None

        # Auto-dismiss timer for notification mode
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.hide_notification)

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

        if self.mode == "notification":
            self._init_notification_ui()
        elif self.mode == "tamagotchi":
            self._init_tamagotchi_ui()
        else:
            self._init_card_ui()

    def _init_notification_ui(self) -> None:
        """Initializes compact toast notification HUD (auto-hiding)."""
        self.resize(520, 130)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        # Floating Toast Box
        self.toast_frame = QFrame()
        self.toast_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(13, 17, 23, 235);
                border: 1px solid rgba(0, 245, 212, 170);
                border-radius: 10px;
            }
        """)
        toast_layout = QVBoxLayout(self.toast_frame)
        toast_layout.setContentsMargins(14, 8, 14, 10)
        toast_layout.setSpacing(4)

        # Header bar
        header_layout = QHBoxLayout()
        self.toast_badge = QLabel("🎙️ DỊCH VOICE CHAT ĐỒNG ĐỘI")
        self.toast_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.toast_badge.setStyleSheet("color: #00F5D4; border: none; background: transparent;")
        header_layout.addWidget(self.toast_badge)

        header_layout.addStretch()

        self.toast_status = QLabel("🟢 LIVE")
        self.toast_status.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.toast_status.setStyleSheet("""
            color: #00FF88;
            background-color: rgba(0, 255, 136, 25);
            border: 1px solid rgba(0, 255, 136, 90);
            border-radius: 4px;
            padding: 1px 6px;
        """)
        header_layout.addWidget(self.toast_status)
        toast_layout.addLayout(header_layout)

        # Original speech label
        self.toast_original_label = QLabel("")
        self.toast_original_label.setWordWrap(True)
        self.toast_original_label.setFont(QFont("Segoe UI", 9))
        self.toast_original_label.setStyleSheet("color: #94A3B8; font-style: italic; border: none; background: transparent;")
        toast_layout.addWidget(self.toast_original_label)

        # Translated speech label (High visual prominence)
        self.toast_translated_label = QLabel("Đang lắng nghe voice chat đồng đội...")
        self.toast_translated_label.setWordWrap(True)
        self.toast_translated_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.toast_translated_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        toast_layout.addWidget(self.toast_translated_label)

        # Draft action row (shown only on pending draft)
        self.draft_actions_frame = QFrame()
        self.draft_actions_frame.setStyleSheet("background: transparent; border: none;")
        btn_layout = QHBoxLayout(self.draft_actions_frame)
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(8)

        self.btn_send = QPushButton("✔ GỬI VÀO TEAM")
        self.btn_send.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                border-radius: 4px;
                padding: 4px 12px;
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
                padding: 4px 12px;
                border: none;
            }
            QPushButton:hover { background-color: #F85149; }
        """)
        self.btn_cancel.clicked.connect(self.reject_current_draft)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()

        toast_layout.addWidget(self.draft_actions_frame)
        self.draft_actions_frame.hide()

        main_layout.addWidget(self.toast_frame)

        # Reposition according to preference
        self.reposition()

    def _init_tamagotchi_ui(self) -> None:
        """Initializes interactive transparent Desktop Pet (Tamagotchi) window with Lip-Sync."""
        self.resize(300, 360)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Floating Speech / Thought Bubble (above avatar)
        self.pet_bubble = QFrame()
        self.pet_bubble.setStyleSheet("""
            QFrame {
                background-color: rgba(23, 18, 33, 235);
                border: 2px solid #FF8FAB;
                border-radius: 12px;
            }
        """)
        bubble_layout = QVBoxLayout(self.pet_bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(2)

        self.pet_name_badge = QLabel("🌸 SAKURA AI • DESKTOP PET")
        self.pet_name_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.pet_name_badge.setStyleSheet("color: #FF8FAB; border: none; background: transparent;")
        bubble_layout.addWidget(self.pet_name_badge)

        self.pet_speech_label = QLabel("Chào bạn! Mình là Sakura, trợ lý ảo đồng hành cùng bạn.")
        self.pet_speech_label.setWordWrap(True)
        self.pet_speech_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.pet_speech_label.setStyleSheet("color: #ECE7F5; border: none; background: transparent;")
        bubble_layout.addWidget(self.pet_speech_label)
        main_layout.addWidget(self.pet_bubble)

        # Interactive Avatar Frame
        self.avatar_frame = QFrame()
        self.avatar_frame.setStyleSheet("""
            QFrame {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                    stop:0 rgba(255, 143, 171, 0.25), stop:1 rgba(23, 18, 33, 0));
                border: none;
            }
        """)
        avatar_layout = QVBoxLayout(self.avatar_frame)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Visual avatar illustration / emoji representation with lip-sync states
        self.avatar_visual_label = QLabel("🌸( ◕ ‿ ◕ )🌸")
        self.avatar_visual_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.avatar_visual_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_visual_label.setStyleSheet("color: #FF8FAB; border: none; background: transparent;")
        avatar_layout.addWidget(self.avatar_visual_label)

        # Avatar state badge
        self.avatar_state_badge = QLabel("🌸 IDLE • SẴN SÀNG")
        self.avatar_state_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.avatar_state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_state_badge.setStyleSheet("""
            color: #9ECE6A;
            background-color: rgba(158, 206, 106, 30);
            border: 1px solid rgba(158, 206, 106, 120);
            border-radius: 9px;
            padding: 2px 8px;
        """)
        avatar_layout.addWidget(self.avatar_state_badge)
        main_layout.addWidget(self.avatar_frame)

        self.reposition()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        """Double clicking pet triggers instant voice interaction or quick callout."""
        if self.mode == "tamagotchi":
            from core.fast_ai_router import ai_router
            ai_router.query_fast("Báo cáo tình hình chiến thuật")
            event.accept()

    def update_avatar_viseme(self, data: dict):
        """Updates avatar face, eyes, and mouth shapes based on real-time audio visemes."""
        if self.mode != "tamagotchi" or not hasattr(self, "avatar_visual_label"):
            return
        mouth_open = data.get("mouth_open", 0.0)
        blink = data.get("blink", False)
        emotion = data.get("emotion", "neutral")

        # Select eyes
        eyes = "-  -" if blink else "◕  ◕"

        # Select mouth based on viseme
        if mouth_open > 0.4:
            mouth = "▽"
        elif mouth_open > 0.15:
            mouth = "‿"
        else:
            mouth = "·"

        self.avatar_visual_label.setText(f"🌸( {eyes[0:2]} {mouth} {eyes[3:]} )🌸")

        if emotion == "alert":
            self.avatar_state_badge.setText("🚨 BÁO ĐỘNG IN-GAME")
            self.avatar_state_badge.setStyleSheet("color: #FF4655; background: rgba(255, 70, 85, 40); border: 1px solid #FF4655; border-radius: 9px; padding: 2px 8px;")
        elif emotion == "speaking":
            self.avatar_state_badge.setText("💬 ĐANG TRẢ LỜI")
            self.avatar_state_badge.setStyleSheet("color: #FF8FAB; background: rgba(255, 143, 171, 40); border: 1px solid #FF8FAB; border-radius: 9px; padding: 2px 8px;")
        elif emotion == "listening":
            self.avatar_state_badge.setText("👂 ĐANG LẮNG NGHE")
            self.avatar_state_badge.setStyleSheet("color: #7AA2F7; background: rgba(122, 162, 247, 40); border: 1px solid #7AA2F7; border-radius: 9px; padding: 2px 8px;")
        else:
            self.avatar_state_badge.setText("🌸 IDLE • SẴN SÀNG")
            self.avatar_state_badge.setStyleSheet("color: #9ECE6A; background: rgba(158, 206, 106, 30); border: 1px solid rgba(158, 206, 106, 120); border-radius: 9px; padding: 2px 8px;")

    def update_game_profile(self, data: dict) -> None:
        """Dynamically adapts desktop companion HUD to current game profile."""
        profile_id = data.get("id", "desktop").lower()
        name = data.get("name", "Desktop Companion")
        icon = data.get("icon", "🌸")

        if hasattr(self, "pet_name_badge"):
            if profile_id == "minecraft":
                self.pet_name_badge.setText(f"{icon} NEURO-SAMA • MINECRAFT")
                self.pet_name_badge.setStyleSheet("color: #38BDF8; border: none; background: transparent;")
            elif profile_id == "valorant":
                self.pet_name_badge.setText(f"{icon} SAKURA AI • VALORANT")
                self.pet_name_badge.setStyleSheet("color: #FF4655; border: none; background: transparent;")
            elif profile_id == "roblox":
                self.pet_name_badge.setText(f"{icon} ROBLOX BUDDY")
                self.pet_name_badge.setStyleSheet("color: #FBBF24; border: none; background: transparent;")
            else:
                self.pet_name_badge.setText(f"{icon} SAKURA AI • DESKTOP")
                self.pet_name_badge.setStyleSheet("color: #FF8FAB; border: none; background: transparent;")

        if hasattr(self, "toast_badge"):
            self.toast_badge.setText(f"{icon} {name.upper()}")

    def display_neuro_commentary(self, data: dict) -> None:
        """Displays Neuro-sama voice reaction and speech bubble on desktop."""
        text = data.get("text", "")
        emotion = data.get("emotion", "happy")

        if hasattr(self, "pet_speech_label"):
            self.pet_speech_label.setText(text)
        elif hasattr(self, "toast_translated_label"):
            self.toast_translated_label.setText(text)
            self.show_notification()

        if hasattr(self, "avatar_state_badge"):
            if emotion in ["panic", "alert", "danger"]:
                self.avatar_state_badge.setText("🚨 NGUY CƠ IN-GAME")
                self.avatar_state_badge.setStyleSheet("color: #EF4444; background: rgba(239, 68, 68, 30); border: 1px solid #EF4444; border-radius: 9px; padding: 2px 8px;")
            elif emotion == "excited":
                self.avatar_state_badge.setText("✨ PHẤN KHÍCH")
                self.avatar_state_badge.setStyleSheet("color: #F59E0B; background: rgba(245, 158, 11, 30); border: 1px solid #F59E0B; border-radius: 9px; padding: 2px 8px;")
            else:
                self.avatar_state_badge.setText("💬 NEURO BÌNH LUẬN")
                self.avatar_state_badge.setStyleSheet("color: #38BDF8; background: rgba(56, 189, 248, 30); border: 1px solid #38BDF8; border-radius: 9px; padding: 2px 8px;")

        if not self.isVisible():
            self.show()

    def _init_card_ui(self) -> None:
        """Initializes classic fixed card HUD (pinned at top-right)."""
        self.resize(380, 520)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

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

        # Header
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

        # Subtitles
        sub_title = QLabel("VOICE CHAT DỊCH TIẾNG VIỆT")
        sub_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sub_title.setStyleSheet("color: #8B949E; border: none; background: transparent;")
        card_layout.addWidget(sub_title)

        self.subtitle_label = QLabel("Đang lắng nghe voice chat đồng đội...")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setFont(QFont("Segoe UI", 9))
        self.subtitle_label.setStyleSheet("color: #E6EDF3; border: none; background: transparent;")
        card_layout.addWidget(self.subtitle_label)

        # AI Tactical
        ai_title = QLabel("GEMINI TACTICAL ASSIST")
        ai_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ai_title.setStyleSheet("color: #8B949E; border: none; background: transparent;")
        card_layout.addWidget(ai_title)

        self.ai_response_label = QLabel("Gọi 'Hey Gemini' để hỏi chiến thuật hoặc phân tích pha vừa qua.")
        self.ai_response_label.setWordWrap(True)
        self.ai_response_label.setFont(QFont("Segoe UI", 9))
        self.ai_response_label.setStyleSheet("color: #58A6FF; border: none; background: transparent;")
        card_layout.addWidget(self.ai_response_label)

        # Draft Card
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
        self.draft_frame.hide()

        main_layout.addWidget(self.card)
        self.reposition()

    def reposition(self) -> None:
        """Dynamically calculates window coordinates based on chosen position."""
        if not QApplication or not QApplication.primaryScreen():
            return
        screen = QApplication.primaryScreen().geometry()
        w = self.width()
        h = self.height()

        if self.position == "top-center":
            x = (screen.width() - w) // 2
            y = 35
        elif self.position == "bottom-center":
            x = (screen.width() - w) // 2
            y = screen.height() - h - 110
        else:  # "top-right"
            x = screen.width() - w - 40
            y = 40
        self.move(x, y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        hwnd = int(self.winId())
        apply_capture_exclusion(hwnd)
        if self.is_click_through:
            set_click_through(hwnd, True)

    def add_subtitle(self, data: dict) -> None:
        """Triggered when real-time translation is received."""
        original = data.get("original", "").strip()
        translated = data.get("translated", "").strip()

        if not original and not translated:
            return

        if self.mode == "notification":
            self.toast_badge.setText("🎙️ DỊCH VOICE CHAT ĐỒNG ĐỘI")
            self.toast_badge.setStyleSheet("color: #00F5D4; border: none; background: transparent;")
            self.toast_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(13, 17, 23, 235);
                    border: 1px solid rgba(0, 245, 212, 180);
                    border-radius: 10px;
                }
            """)
            self.toast_original_label.setText(f'"{original}"')
            self.toast_translated_label.setText(f'👉 "{translated}"')
            self.toast_translated_label.setStyleSheet("color: #00FF88; font-size: 11pt; font-weight: bold; border: none; background: transparent;")
            self.draft_actions_frame.hide()

            self.reposition()
            self.show()
            self.toast_timer.start(int(self.duration * 1000))
        elif self.mode == "tamagotchi":
            if hasattr(self, "pet_speech_label"):
                self.pet_speech_label.setText(f"🗣️ {original}\n👉 {translated}")
                self.show()
        else:
            self.subtitle_label.setText(f"<b>{original}</b><br><span style='color: #00FF88;'>👉 {translated}</span>")

    def display_gemini_response(self, text: str) -> None:
        """Triggered when Gemini provides a tactical voice or callout response."""
        if not text:
            return
        if self.mode == "notification":
            self.toast_badge.setText("🤖 TRỢ LÝ CHIẾN THUẬT GEMINI")
            self.toast_badge.setStyleSheet("color: #38BDF8; border: none; background: transparent;")
            self.toast_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(13, 17, 23, 235);
                    border: 1px solid rgba(56, 189, 248, 180);
                    border-radius: 10px;
                }
            """)
            self.toast_original_label.setText("")
            self.toast_translated_label.setText(f'💬 "{text}"')
            self.toast_translated_label.setStyleSheet("color: #E2E8F0; font-size: 10pt; font-weight: bold; border: none; background: transparent;")
            self.draft_actions_frame.hide()

            self.reposition()
            self.show()
            self.toast_timer.start(int(self.duration * 1000))
        elif self.mode == "tamagotchi":
            if hasattr(self, "pet_speech_label"):
                self.pet_speech_label.setText(f"💬 {text}")
                self.show()
        else:
            self.ai_response_label.setText(text)

    def display_chat_draft(self, draft: dict) -> None:
        """Triggered when AI proposes an in-game chat message for approval."""
        self.current_draft_id = draft.get("draft_id")
        content = draft.get("content", "")

        if self.mode == "notification":
            self.toast_badge.setText("⚡ BẢN NHÁP CHAT GAME (CHỜ DUYỆT)")
            self.toast_badge.setStyleSheet("color: #F59E0B; border: none; background: transparent;")
            self.toast_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(24, 20, 14, 245);
                    border: 1px solid rgba(245, 158, 11, 200);
                    border-radius: 10px;
                }
            """)
            self.toast_original_label.setText("Tin nhắn AI đề xuất gửi vào kênh Team Valorant:")
            self.toast_translated_label.setText(f'"{content}"')
            self.toast_translated_label.setStyleSheet("color: #FDE047; font-size: 11pt; font-weight: bold; border: none; background: transparent;")
            self.draft_actions_frame.show()

            # Temporarily disable click-through so user can click Approve / Reject
            hwnd = int(self.winId())
            set_click_through(hwnd, False)

            self.reposition()
            self.show()
            # Stays visible until user acts (or max 15 seconds)
            self.toast_timer.start(15000)
        else:
            self.draft_content_label.setText(f'"{content}"')
            self.draft_frame.show()

    def approve_current_draft(self) -> None:
        if self.current_draft_id:
            from core.in_game_chat import chat_manager
            chat_manager.approve_and_send(self.current_draft_id)
            self.current_draft_id = None
        self.hide_notification()

    def reject_current_draft(self) -> None:
        if self.current_draft_id:
            from core.in_game_chat import chat_manager
            chat_manager.reject(self.current_draft_id)
            self.current_draft_id = None
        self.hide_notification()

    def hide_notification(self) -> None:
        """Hides notification toast and restores click-through."""
        if self.mode == "notification":
            hwnd = int(self.winId())
            if self.is_click_through:
                set_click_through(hwnd, True)
            self.hide()
        else:
            if hasattr(self, "draft_frame"):
                self.draft_frame.hide()

    def update_status_bar(self, status: str) -> None:
        if hasattr(self, "status_pill"):
            self.status_pill.setText(status)
        if hasattr(self, "toast_status"):
            self.toast_status.setText(status)


def start_websocket_listener(signals: OverlaySignals, port: int = 8000) -> None:
    """Connects to FastAPI WebSocket /ws and dispatches events to PyQt signals."""
    import asyncio
    import websockets

    async def _client_loop():
        uri = f"ws://127.0.0.1:{port}/ws"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    signals.status_updated.emit("🟢 LIVE")
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        m_type = data.get("type")
                        if m_type == "subtitle":
                            signals.subtitle_received.emit(data)
                        elif m_type == "chat_draft":
                            signals.chat_draft_received.emit(data)
                        elif m_type == "wake_word_triggered":
                            signals.gemini_response_received.emit(data.get("message", ""))
                        elif m_type == "profile_changed":
                            signals.profile_changed.emit(data)
                        elif m_type == "neuro_commentary":
                            signals.neuro_commentary_received.emit(data)
                        elif m_type == "game_status":
                            if data.get("running"):
                                signals.status_updated.emit("🟢 IN-GAME")
                            else:
                                signals.status_updated.emit("⚪ WAITING")
            except Exception:
                signals.status_updated.emit("🔴 WAITING")
                await asyncio.sleep(2.0)

    def _thread_target():
        asyncio.run(_client_loop())

    t = threading.Thread(target=_thread_target, daemon=True, name="OverlayWebSocketListener")
    t.start()


def run_overlay_standalone() -> None:
    """Launches overlay as independent application or child process."""
    if QApplication is None:
        print("[Overlay] PyQt6 not installed. Overlay cannot start.")
        return

    port = config.data.get("web", {}).get("port", 8000)
    app = QApplication(sys.argv)
    window = ValorantOverlayWindow()

    # Start live WebSocket event listener
    start_websocket_listener(window.signals, port=port)

    # In tamagotchi (desktop pet) or card mode: window shows immediately on desktop screen!
    # In notification mode: window starts hidden and pops up on incoming speech.
    if window.mode in ["card", "tamagotchi"]:
        window.show()
    else:
        # Window remains hidden until a translation or alert arrives
        pass

    sys.exit(app.exec())
        # Window remains hidden until a translation or alert arrives
        pass

    sys.exit(app.exec())


if __name__ == "__main__":
    run_overlay_standalone()
