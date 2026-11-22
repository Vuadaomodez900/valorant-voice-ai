"""
Valorant Voice AI - Main Application Entry Point.
Orchestrates:
- Dual Audio Router (Physical Mic + Virtual Cable + Headphone Output)
- High-Performance Passive Screen Stream (DXGI Desktop Duplication)
- Offline Wake Word Detector ("Hey Gemini" / "Hey Google")
- Real-time In-Game Voice Chat Translator to Vietnamese
- Gemini Multimodal Live API Bridge (google-genai SDK)
- Safe Read-Only Process Watcher (psutil)
- LAN Web Dashboard (FastAPI + WebSocket + QR Code)
- PyQt6 Non-Intrusive Overlay (Excluded from Screen Capture)
- CustomTkinter Configuration GUI & System Tray
"""

import sys
import os
import time
import signal
import threading
import subprocess
import uvicorn

from core.config import config
from core.audio_router import AudioRouter
from core.screen_stream import ScreenStreamManager
from core.wake_word import WakeWordDetector
from core.translator import VoiceChatTranslator
from core.agy_bridge import GeminiLiveBridge
from core.process_watcher import ProcessWatcher
from core.in_game_chat import chat_manager
from core.self_healer import self_healer
from web_control.server import app as fastapi_app, bind_engine_components, ws_manager
from gui.tray import SystemTrayManager


class ValorantVoiceAIOrchestrator:
    """Central engine coordinating all threads, streams, and UI modules."""

    def __init__(self):
        self.is_running = False
        self._overlay_process = None

        # 1. Initialize Components
        cfg = config.data
        self.router = AudioRouter(sample_rate=cfg["audio"]["sample_rate"])
        self.router.set_headphone_volume(cfg["audio"]["volume_headphone"])
        self.router.set_game_mic_volume(cfg["audio"]["volume_game_mic"])
        self.router.mute_game_mic = cfg["audio"]["mute_game_mic"]
        self.router.auto_mic_trigger = cfg["audio"]["auto_mic_trigger"]
        self.router.ptt_key = cfg["audio"]["ptt_key"]

        self.screen_manager = ScreenStreamManager(
            monitor_index=cfg["screen"]["monitor_index"],
            fps_live=cfg["screen"]["fps_live_stream"],
            fps_buffer=cfg["screen"]["fps_buffer"],
            buffer_seconds=cfg["screen"]["buffer_seconds"],
            resolution=tuple(cfg["screen"]["capture_resolution"])
        )

        self.wake_detector = WakeWordDetector(
            model_name=cfg["wake_word"]["model_name"],
            threshold=cfg["wake_word"]["threshold"]
        )

        # Dedicated detector for teammates' voice chat via WASAPI loopback
        self.teammate_wake_detector = WakeWordDetector(
            model_name=cfg["wake_word"]["model_name"],
            threshold=cfg["wake_word"]["threshold"]
        )
        self.teammate_voice_trigger_enabled = cfg["audio"].get("teammate_voice_trigger", True)
        self._teammate_listening_until = 0.0

        self.translator = VoiceChatTranslator(
            target_lang=cfg["overlay"]["translation_target_lang"]
        )

        self.bridge = GeminiLiveBridge(
            api_key=cfg["gemini"]["api_key"],
            model_name=cfg["gemini"]["model"],
            voice_name=cfg["gemini"]["voice_name"],
            system_prompt=cfg["gemini"]["system_prompt"]
        )

        self.process_watcher = ProcessWatcher(
            target_process_name=cfg["process_watcher"]["target_process"],
            interval=cfg["process_watcher"]["check_interval"]
        )

        # Wire Web Server & Self-Healer to Engine
        bind_engine_components(self.router, self.screen_manager, self.bridge, self)
        self_healer.bind_orchestrator(self)

        # 2. Inter-component Pipeline Wiring
        self._wire_pipelines()

    def set_teammate_voice_trigger(self, enabled: bool) -> bool:
        self.teammate_voice_trigger_enabled = enabled
        config.data["audio"]["teammate_voice_trigger"] = enabled
        config.save()
        print(f"[Orchestrator] Teammate Voice Chat Trigger is now: {self.teammate_voice_trigger_enabled}")
        return self.teammate_voice_trigger_enabled

    def _wire_pipelines(self) -> None:
        """Connects data streams between mic, AI, screen, and translation."""

        # A. User Physical Mic Chunks -> Wake Word Detector & Gemini Live Session
        def on_user_mic_chunk(chunk):
            self.wake_detector.process_pcm_chunk(chunk)
            if self.bridge.is_connected:
                self.bridge.send_user_audio_chunk(chunk)

        self.router.subscribe_mic(on_user_mic_chunk)

        # B. In-Game WASAPI Loopback (Teammates' Voice) -> Voice Chat Translator & Wake Word
        def on_loopback_chunk(chunk):
            self.translator.feed_loopback_chunk(chunk)

            # Check if teammate in-game voice chat trigger is active
            if self.teammate_voice_trigger_enabled:
                self.teammate_wake_detector.process_pcm_chunk(chunk)

                # Forward teammate question to Gemini if within active query window
                now = time.time()
                if now < self._teammate_listening_until:
                    if self.bridge.is_connected:
                        self.bridge.send_user_audio_chunk(chunk)

        self.router.subscribe_loopback(on_loopback_chunk)

        # Wire Subtitle Translation stream to WebSocket clients / Mobile Dashboard
        def on_sub_received(sub_data):
            self._broadcast_event({
                "type": "subtitle",
                "original": sub_data.get("original", ""),
                "translated": sub_data.get("translated", "")
            })
        self.translator.register_subtitle_subscriber(on_sub_received)

        # Wire Permission-Gated Chat drafts to WebSocket clients / Mobile Dashboard
        def on_draft_created(draft):
            self._broadcast_event({
                "type": "chat_draft",
                "draft_id": draft.draft_id,
                "content": draft.content,
                "channel": draft.target_channel
            })
        chat_manager.register_draft_created(on_draft_created)

        # C. Live Screen Frames (1-5 FPS) -> Gemini Live Session
        def on_live_frame(jpeg_bytes):
            if self.bridge.is_connected:
                self.bridge.send_screen_frame_jpeg(jpeg_bytes)

        self.screen_manager.register_live_subscriber(on_live_frame)

        # D. Gemini Speech Output (24kHz PCM) -> Audio Router
        # (Plays simultaneously into user headphones AND into Virtual Cable for game teammates!)
        def on_ai_audio_received(pcm_bytes):
            self.router.feed_ai_audio_pcm(pcm_bytes, original_sample_rate=24000)

        self.bridge.register_audio_output(on_ai_audio_received)

        # E. Wake Word Trigger Events (User & Teammate)
        def on_user_wake_word_detected(word, score):
            print(f"[Orchestrator] User Wake Word '{word}' triggered! Activating Gemini Live Uplink...")
            if not self.bridge.is_connected:
                self.bridge.start()
            self._broadcast_event({
                "type": "wake_word_triggered",
                "speaker": "user",
                "message": f"Bạn vừa gọi '{word}'"
            })

        self.wake_detector.register_callback(on_user_wake_word_detected)

        def on_teammate_wake_word_detected(word, score):
            if not self.teammate_voice_trigger_enabled:
                return
            print(f"[Orchestrator] 🔥 TEAMMATE in-game voice chat triggered '{word}'! Listening for question (6s)...")
            self._teammate_listening_until = time.time() + 6.0
            if not self.bridge.is_connected:
                self.bridge.start()
            self._broadcast_event({
                "type": "wake_word_triggered",
                "speaker": "teammate",
                "message": f"🎙️ Đồng đội vừa gọi '{word}' qua Voice Chat game! AI đang lắng nghe và sẽ trả lời qua mic..."
            })

        self.teammate_wake_detector.register_callback(on_teammate_wake_word_detected)

        # F. Process Watcher Callbacks
        def on_game_started(pid):
            print(f"[Orchestrator] Valorant active (PID: {pid}). Activating Overlay & Game Profile.")
            self._broadcast_event({"type": "game_status", "running": True, "pid": pid})

        def on_game_stopped():
            print("[Orchestrator] Valorant closed. Audio and screen capture idle.")
            self._broadcast_event({"type": "game_status", "running": False})

        self.process_watcher.register_start_callback(on_game_started)
        self.process_watcher.register_stop_callback(on_game_stopped)

    def _broadcast_event(self, event_data: dict) -> None:
        """Broadcasts event to WebSocket clients and overlay."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_data), loop)
        except Exception:
            pass

    def start_web_server(self) -> None:
        """Starts FastAPI Web Dashboard in a daemon thread."""
        host = config.data["web"]["host"]
        port = config.data["web"]["port"]

        def run_uvicorn():
            uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")

        web_thread = threading.Thread(target=run_uvicorn, daemon=True, name="FastAPIWebServerThread")
        web_thread.start()
        print(f"[Orchestrator] LAN Web Dashboard live at: http://localhost:{port}")

    def start_overlay_process(self) -> None:
        """Launches PyQt6 Overlay in a child process to prevent Tkinter/Qt event loop conflicts."""
        if not config.data["overlay"]["enabled"]:
            return
        try:
            cmd = [sys.executable, sys.argv[0], "--overlay-worker"]
            self._overlay_process = subprocess.Popen(cmd)
            print("[Orchestrator] PyQt6 Overlay process spawned successfully.")
        except Exception as e:
            print(f"[Orchestrator] Could not spawn overlay process: {e}")

    def start_all(self) -> None:
        """Starts all background services."""
        if self.is_running:
            return
        print("=" * 60)
        print("  VALORANT VOICE AI COMPANION - STARTING ENGINES")
        print("=" * 60)

        # 0. Zero-Touch Startup Auto-Configuration & Self-Healing
        self_healer.auto_heal_on_startup()

        # 1. Start Audio Router
        cfg_audio = config.data["audio"]
        self.router.start(
            physical_mic_name=cfg_audio["physical_mic"],
            virtual_cable_name=cfg_audio["virtual_mic_out"],
            headphone_name=cfg_audio["headphone_out"]
        )

        # 2. Start Screen Capture
        self.screen_manager.start()

        # 3. Start Translator
        self.translator.start()

        # 4. Start Gemini Bridge
        self.bridge.start()

        # 5. Start Process Watcher
        self.process_watcher.start()

        # 6. Start LAN Web Server
        self.start_web_server()

        # 7. Start Overlay Process
        self.start_overlay_process()

        self.is_running = True
        print("[Orchestrator] All engines operational.")

    def shutdown(self) -> None:
        """Gracefully stops all services and cleans up audio and processes."""
        if not self.is_running:
            return
        print("\n[Orchestrator] Initiating graceful shutdown...")
        self.process_watcher.stop()
        self.bridge.stop()
        self.translator.stop()
        self.screen_manager.stop()
        self.router.stop()

        if self._overlay_process:
            try:
                self._overlay_process.terminate()
            except Exception:
                pass
            self._overlay_process = None

        self.is_running = False
        print("[Orchestrator] Clean shutdown complete.")


def main():
    # Check if invoked as child overlay worker
    if "--overlay-worker" in sys.argv:
        from overlay.app import run_overlay_standalone
        run_overlay_standalone()
        return

    # Normal application startup
    orchestrator = ValorantVoiceAIOrchestrator()
    orchestrator.start_all()

    # System Tray Manager
    def on_show_window():
        if gui_app:
            gui_app.show_from_tray()

    def on_toggle_mute():
        return orchestrator.router.toggle_game_mic_mute()

    def on_exit_app():
        orchestrator.shutdown()
        if gui_app and gui_app.root:
            gui_app.root.quit()
        sys.exit(0)

    tray = SystemTrayManager(
        on_show_window=on_show_window,
        on_toggle_mute=on_toggle_mute,
        on_exit_app=on_exit_app
    )
    tray.start()

    # GUI or CLI Mode
    gui_app = None
    if "--cli" in sys.argv:
        # Launch AGY CLI interactive shell directly in the console on the machine
        from scripts.agy_cli import AGYInteractiveShell
        shell = AGYInteractiveShell(host="127.0.0.1")
        try:
            shell.run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            on_exit_app()
    elif "--headless" not in sys.argv:
        from gui.app import QuickConfigApp
        gui_app = QuickConfigApp(
            router=orchestrator.router,
            on_tray_minimize=lambda: print("[App] Minimized to System Tray. Running in background."),
            on_shutdown=on_exit_app
        )
        gui_app.create_ui()
        try:
            gui_app.run()
        except KeyboardInterrupt:
            pass
        finally:
            on_exit_app()
    else:
        # Keep alive in headless mode
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            on_exit_app()


if __name__ == "__main__":
    main()
