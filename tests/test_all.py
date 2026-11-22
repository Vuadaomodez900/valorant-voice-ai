"""
Automated Comprehensive Test Suite for Valorant Voice AI Companion.
Tests all core systems, data flow, permission gate, audio routing math,
screen buffer logic, wake word detector, and web endpoints.
"""

import sys
import os
import unittest
import time
import numpy as np
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import AppConfig, DEFAULT_CONFIG, get_resource_path
from core.in_game_chat import PermissionGatedChatManager, ChatDraft
from core.audio_router import AudioRouter
from core.screen_stream import ScreenStreamManager
from core.wake_word import WakeWordDetector
from core.translator import VoiceChatTranslator
from core.cable_installer import is_vbcable_installed, get_installer_executable_path
from core.process_watcher import ProcessWatcher


class TestConfig(unittest.TestCase):
    """Verifies configuration loader and path resolution."""

    def test_default_config_structure(self):
        cfg = AppConfig("config.yaml")
        self.assertIn("audio", cfg.data)
        self.assertIn("screen", cfg.data)
        self.assertIn("wake_word", cfg.data)
        self.assertIn("gemini", cfg.data)
        self.assertIn("overlay", cfg.data)
        self.assertIn("web", cfg.data)
        self.assertTrue(cfg.data["audio"]["teammate_voice_trigger"])

    def test_resource_path_resolution(self):
        path = get_resource_path("config.yaml")
        self.assertTrue(os.path.exists(path))


class TestPermissionGatedChat(unittest.TestCase):
    """Verifies that AI can NEVER send messages without user authorization."""

    def setUp(self):
        self.manager = PermissionGatedChatManager()

    def test_draft_starts_strictly_pending(self):
        draft = self.manager.propose_chat("Enemy Sova low HP at B site", target_channel="team")
        self.assertEqual(draft.status, "PENDING")
        self.assertEqual(self.manager.current_active_draft.draft_id, draft.draft_id)

    def test_user_approval_flow(self):
        draft = self.manager.propose_chat("Planting Spike at A", target_channel="team")
        success = self.manager.approve_and_send(draft.draft_id)
        self.assertTrue(success)
        self.assertIn(draft.status, ["SENT", "APPROVED"])
        self.assertIsNone(self.manager.current_active_draft)

    def test_user_rejection_flow(self):
        draft = self.manager.propose_chat("Rush Mid", target_channel="team")
        self.manager.reject(draft.draft_id)
        self.assertEqual(draft.status, "REJECTED")
        self.assertIsNone(self.manager.current_active_draft)


class TestAudioRouter(unittest.TestCase):
    """Verifies dual audio routing, volume scaling, clipping math, and mute toggles."""

    def setUp(self):
        self.router = AudioRouter(sample_rate=16000)

    def test_volume_clamping(self):
        self.router.set_headphone_volume(2.5)  # Out of range max
        self.assertEqual(self.router.volume_headphone, 2.0)
        self.router.set_headphone_volume(-0.5) # Out of range min
        self.assertEqual(self.router.volume_headphone, 0.0)

        self.router.set_game_mic_volume(1.5)
        self.assertEqual(self.router.volume_game_mic, 1.5)

    def test_mute_toggle(self):
        self.assertFalse(self.router.mute_game_mic)
        muted = self.router.toggle_game_mic_mute()
        self.assertTrue(muted)
        self.assertTrue(self.router.mute_game_mic)
        unmuted = self.router.toggle_game_mic_mute()
        self.assertFalse(unmuted)

    def test_audio_pcm_feeding_and_resampling(self):
        dummy_pcm_24k = (np.ones(240, dtype=np.int16) * 1000).tobytes()
        self.router.feed_ai_audio_pcm(dummy_pcm_24k, original_sample_rate=24000)
        self.assertFalse(self.router.ai_audio_queue.empty())
        resampled_chunk = self.router.ai_audio_queue.get_nowait()
        self.assertGreater(len(resampled_chunk), 0)


class TestScreenStreamManager(unittest.TestCase):
    """Verifies DXGI screen frame processing, rolling buffer, and replay extraction."""

    def setUp(self):
        self.mgr = ScreenStreamManager(
            monitor_index=0,
            fps_live=2,
            fps_buffer=10,
            buffer_seconds=5,
            resolution=(320, 240)
        )

    def test_jpeg_frame_compression(self):
        dummy_frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        jpeg_bytes = self.mgr._process_frame_to_jpeg(dummy_frame, (320, 240), quality=70)
        self.assertIsInstance(jpeg_bytes, bytes)
        self.assertTrue(jpeg_bytes.startswith(b"\xff\xd8")) # Standard JPEG SOF marker

    def test_rolling_buffer_capacity_and_replay_sampling(self):
        now = time.time()
        dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        jpeg_bytes = self.mgr._process_frame_to_jpeg(dummy_frame, (320, 240), quality=50)

        # Fill buffer with 10 simulated frames over last 4 seconds
        for i in range(10):
            ts = now - (9 - i) * 0.4
            self.mgr.rolling_buffer.append((ts, jpeg_bytes))

        # Request last 3 seconds at 2 fps
        replays = self.mgr.get_recent_replay_frames(seconds=3.0, sample_fps=2)
        self.assertGreater(len(replays), 0)
        for ts, data in replays:
            self.assertGreaterEqual(ts, now - 3.5)


class TestWakeWordDetector(unittest.TestCase):
    """Verifies offline wake word detection, cooldown, and manual trigger."""

    def test_wake_word_manual_trigger(self):
        detector = WakeWordDetector(threshold=0.5)
        triggered_words = []

        def on_triggered(word, score):
            triggered_words.append((word, score))

        detector.register_callback(on_triggered)
        detector.trigger_manual("test_trigger")

        self.assertEqual(len(triggered_words), 1)
        self.assertEqual(triggered_words[0][0], "test_trigger")

    def test_cooldown_rejection(self):
        detector = WakeWordDetector(threshold=0.5)
        detector._last_trigger_time = time.time() # Just triggered
        silence_chunk = np.zeros(1280, dtype=np.int16)
        detected = detector.process_pcm_chunk(silence_chunk)
        self.assertFalse(detected)


class TestVoiceChatTranslator(unittest.TestCase):
    """Verifies VAD energy detection and translation callback mechanism."""

    def test_translator_pipeline_dispatch(self):
        translator = VoiceChatTranslator(target_lang="vi", vad_threshold=100.0)
        received_subtitles = []

        def on_sub(data):
            received_subtitles.append(data)

        translator.register_subtitle_subscriber(on_sub)
        
        # Test direct processing of speech segment
        dummy_speech = np.random.randint(-1500, 1500, 3200, dtype=np.int16)
        translator._process_utterance(dummy_speech)

        self.assertEqual(len(received_subtitles), 1)
        self.assertIn("translated", received_subtitles[0])
        self.assertIn("original", received_subtitles[0])


class TestCableInstaller(unittest.TestCase):
    """Verifies bundled driver path resolution and detection logic."""

    def test_bundled_installer_exists(self):
        installer_path = get_installer_executable_path()
        # Should resolve to drivers/vbcable/VBCABLE_Setup_x64.exe or VBCABLE_Setup.exe
        self.assertTrue(installer_path.name.startswith("VBCABLE_Setup"))


try:
    import fastapi
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@unittest.skipUnless(HAS_FASTAPI, "FastAPI or TestClient not installed in current test environment")
class TestFastAPIWebServer(unittest.TestCase):
    """Verifies FastAPI LAN dashboard endpoints, schemas, and QR generator."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from web_control.server import app, bind_engine_components
        self.client = TestClient(app)
        
        # Mock engine components
        self.router = AudioRouter()
        self.screen = ScreenStreamManager()
        bind_engine_components(self.router, self.screen, None)

    def test_html_index_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VALORANT", response.text)

    def test_status_endpoint(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("headphone_volume", data)
        self.assertIn("game_mic_volume", data)
        self.assertIn("screen_fps", data)
        self.assertIn("teammate_voice_trigger", data)

    def test_volume_update_endpoint(self):
        payload = {"headphone": 1.25, "game_mic": 0.85, "mute_game_mic": False}
        response = self.client.post("/api/volume", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(self.router.volume_headphone, 1.25, places=2)
        self.assertAlmostEqual(self.router.volume_game_mic, 0.85, places=2)

    def test_screen_fps_update_endpoint(self):
        payload = {"fps": 3}
        response = self.client.post("/api/screen", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.screen.fps_live, 3)

    def test_qr_code_generation(self):
        response = self.client.get("/api/qr")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_chat_action_endpoint(self):
        from core.in_game_chat import chat_manager
        draft = chat_manager.propose_chat("Test tactical callout", target_channel="team")
        
        # Test approval
        response = self.client.post("/api/chat/action", json={"draft_id": draft.draft_id, "action": "approve"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], ["sent", "failed"])

    def test_callout_endpoint(self):
        response = self.client.post("/api/callout", json={"text": "Enemy A site", "channel": "team"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["content"], "Enemy A site")
        self.assertIn("draft_id", data)


class TestRemoteTunnel(unittest.TestCase):
    """Verifies automated internet tunneling mechanisms."""

    def test_tunnel_manager_init(self):
        from core.remote_tunnel import RemoteTunnelManager
        mgr = RemoteTunnelManager(local_port=8000)
        self.assertEqual(mgr.local_port, 8000)
        self.assertFalse(mgr.is_active)
        self.assertIsNone(mgr.public_url)
        mgr.stop_tunnel()
        self.assertFalse(mgr.is_active)

    def test_find_ssh(self):
        from core.remote_tunnel import RemoteTunnelManager
        mgr = RemoteTunnelManager()
        ssh_bin = mgr.find_ssh()
        if sys.platform != "win32":
            self.assertIsNotNone(ssh_bin)


class TestMCPUrlResolution(unittest.TestCase):
    """Verifies MCP server and client smart URL resolution for WAN/LAN."""

    def test_get_base_url_variants(self):
        from tools.mcp_valorant_server import get_base_url
        self.assertEqual(get_base_url("192.168.1.5"), "http://192.168.1.5:8000")
        self.assertEqual(get_base_url("100.85.12.34"), "http://100.85.12.34:8000")
        self.assertEqual(get_base_url("100.85.12.34:8080"), "http://100.85.12.34:8080")
        self.assertEqual(get_base_url("https://abc.trycloudflare.com"), "https://abc.trycloudflare.com")
        self.assertEqual(get_base_url("https://abc.trycloudflare.com/"), "https://abc.trycloudflare.com")
        self.assertEqual(get_base_url("http://custom.ngrok.app"), "http://custom.ngrok.app")


class TestOverlayNotificationConfig(unittest.TestCase):
    """Verifies overlay configuration for notification toast mode."""

    def test_overlay_mode_and_timing(self):
        cfg = AppConfig("config.yaml")
        overlay_cfg = cfg.data.get("overlay", {})
        self.assertEqual(overlay_cfg.get("mode"), "notification")
        self.assertEqual(overlay_cfg.get("notification_duration"), 6.0)
        self.assertEqual(overlay_cfg.get("position"), "top-center")


if __name__ == "__main__":
    unittest.main()
