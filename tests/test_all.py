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


class TestSelfHealer(unittest.TestCase):
    """Verifies autonomous diagnostics, self-repair, and dynamic mutation API."""

    def test_diagnose_system(self):
        from core.self_healer import self_healer
        diag = self_healer.diagnose_system()
        self.assertIn("health_score", diag)
        self.assertIn("status", diag)
        self.assertIn("subsystems", diag)
        self.assertIsInstance(diag["health_score"], int)
        self.assertGreaterEqual(diag["health_score"], 0)
        self.assertLessEqual(diag["health_score"], 100)

    def test_auto_fix_system(self):
        from core.self_healer import self_healer
        res = self_healer.auto_fix_system()
        self.assertTrue(res["success"])
        self.assertIn("actions_taken", res)
        self.assertIn("health_after_fix", res)

    def test_update_runtime_config(self):
        from core.self_healer import self_healer
        updates = {"audio.volume_headphone": 1.25, "overlay.mode": "notification"}
        res = self_healer.update_runtime_config(updates)
        self.assertEqual(res["status"], "ok")
        self.assertIn("audio.volume_headphone", res["applied_keys"])

    def test_auto_heal_on_startup(self):
        from core.self_healer import self_healer
        logs = self_healer.auto_heal_on_startup()
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)


class TestLipSyncAndFastAI(unittest.TestCase):
    """Verifies Lip-Sync viseme analyzer, fast tactical cache, and AI router."""

    def test_lipsync_audio_feeding_and_viseme(self):
        from core.lipsync import LipSyncAnalyzer
        analyzer = LipSyncAnalyzer()
        # Feed silent chunk
        silent_chunk = np.zeros(320, dtype=np.int16)
        state_silent = analyzer.feed_audio_chunk(silent_chunk)
        self.assertIn("mouth_open", state_silent)
        self.assertIn("viseme", state_silent)
        self.assertIn("blink", state_silent)
        self.assertEqual(state_silent["viseme"], "closed")

        # Feed loud speech chunk (10000 amplitude)
        loud_chunk = (np.sin(np.linspace(0, 100, 480)) * 12000).astype(np.int16)
        state_loud = analyzer.feed_audio_chunk(loud_chunk, is_ai_speaking=True)
        self.assertGreater(state_loud["mouth_open"], 0.0)
        self.assertEqual(state_loud["emotion"], "speaking")
        analyzer.stop()

    def test_fast_tactical_cache_matching(self):
        from core.fast_ai_router import FastTacticalCache
        cache = FastTacticalCache()

        t0 = time.time()
        spike_ans = cache.match("Spike đặt ở đâu rồi?")
        duration_ms = (time.time() - t0) * 1000.0

        self.assertIsNotNone(spike_ans)
        self.assertIn("Spike", spike_ans)
        self.assertLess(duration_ms, 15.0) # Guaranteed <15ms

        eco_ans = cache.match("vòng này có nên eco hay buy không?")
        self.assertIsNotNone(eco_ans)
        self.assertIn("Eco", eco_ans)

    def test_ai_router_provider_switching(self):
        from core.fast_ai_router import ai_router
        ai_router.set_provider("antigravity_cli", model="gemini-2.0-flash")
        self.assertEqual(ai_router.current_provider, "antigravity_cli")
        ai_router.set_provider("claude_code")
        self.assertEqual(ai_router.current_provider, "claude_code")


class TestMultiGameAndMinecraft(unittest.TestCase):
    """Verifies GameProfileManager, MinecraftAgent (Neuro-sama), and Multi-Game detection."""

    def test_game_profile_manager(self):
        from core.game_profiles import GameProfileManager, game_profile_manager
        mgr = GameProfileManager()
        profiles = mgr.list_profiles()
        p_ids = [p["id"] for p in profiles]
        self.assertIn("desktop", p_ids)
        self.assertIn("valorant", p_ids)
        self.assertIn("minecraft", p_ids)
        self.assertIn("roblox", p_ids)

        # Switch profile
        success = mgr.set_active_profile("minecraft")
        self.assertTrue(success)
        active = mgr.get_active_profile()
        self.assertEqual(active.profile_id, "minecraft")
        self.assertIn("Neuro-sama", active.name)
        self.assertIn("Neuro-sama", active.system_prompt)

        # Process detection mapping
        self.assertEqual(mgr.detect_profile_by_process_name("javaw.exe"), "minecraft")
        self.assertEqual(mgr.detect_profile_by_process_name("VALORANT.exe"), "valorant")
        self.assertEqual(mgr.detect_profile_by_process_name("RobloxPlayerBeta.exe"), "roblox")
        self.assertIsNone(mgr.detect_profile_by_process_name("notepad.exe"))

    def test_minecraft_agent_neuro_voice_and_triggers(self):
        from core.minecraft_agent import MinecraftAgent
        agent = MinecraftAgent(host="127.0.0.1", port=28888)

        # Check default autonomy
        self.assertTrue(agent.autonomous_enabled)
        self.assertTrue(agent.auto_shield_enabled)
        self.assertTrue(agent.auto_eat_enabled)

        # Reactive voice test
        commentary_received = []
        agent.register_commentary_listener(lambda txt, emo: commentary_received.append((txt, emo)))

        voice_line = agent.trigger_neuro_voice("creeper_alert", emotion="panic")
        self.assertGreater(len(voice_line), 0)
        self.assertGreater(len(commentary_received), 0)
        self.assertEqual(commentary_received[-1][1], "panic")

        # Autonomous trigger test: Creeper ambush
        agent.in_game = True
        mock_danger_state = {
            "player": {"health": 18.0, "food_level": 20, "x": 100.0, "y": 64.0, "z": 200.0},
            "danger": {"level": "CRITICAL", "reasons": ["Creeper within 4.5m"]},
            "radar": {"hostile_count": 1, "hostiles": [{"name": "Creeper", "distance": 4.2}]},
            "environment": {"dimension": "minecraft:overworld", "biome": "plains"},
            "target": {"type": "NONE"}
        }
        agent._evaluate_autonomous_triggers(mock_danger_state)
        self.assertIn("creeper", agent._last_reaction_time)

        # Autonomous trigger test: Low Health
        mock_low_hp_state = {
            "player": {"health": 4.0, "food_level": 10, "x": 100.0, "y": 64.0, "z": 200.0},
            "danger": {"level": "CRITICAL", "reasons": ["Low HP"]},
            "radar": {"hostile_count": 0, "hostiles": []},
            "environment": {"dimension": "minecraft:overworld", "biome": "plains"},
            "target": {"type": "NONE"}
        }
        agent._evaluate_autonomous_triggers(mock_low_hp_state)
        self.assertIn("low_hp", agent._last_reaction_time)
        self.assertIn("eat", agent._last_reaction_time)

    def test_process_watcher_multigame_support(self):
        from core.process_watcher import ProcessWatcher
        watcher = ProcessWatcher()
        self.assertEqual(watcher.current_active_profile, "desktop")
        # Ensure watcher has profile change callbacks list
        profile_events = []
        watcher.register_profile_callback(lambda p: profile_events.append(p))
        self.assertEqual(len(watcher.on_profile_change_callbacks), 1)


class TestSecurityAndOAuth(unittest.TestCase):
    """Verifies Anti-Tamper engine, Data Leak Sanitizer, and OAuth2 session signing."""

    def test_data_leak_sanitization(self):
        from core.security import sanitize_data_payload, mask_secret_string

        # Test secret string masking
        masked = mask_secret_string("sk-1234567890abcdef1234567890abcdef")
        self.assertTrue(masked.startswith("sk-"))
        self.assertTrue(masked.endswith("def"))
        self.assertIn("****", masked)

        # Test dictionary sanitization
        sensitive_payload = {
            "api_key": "AIzaSyD-1234567890abcdef1234567890",
            "client_secret": "super_secret_discord_oauth_secret",
            "normal_data": "public_username",
            "nested": {
                "password": "my_secure_password_123",
                "logs": "Raw key sk-99999999999999999999999999999999 detected"
            }
        }
        sanitized = sanitize_data_payload(sensitive_payload)
        self.assertNotIn("AIzaSyD-1234567890abcdef1234567890", str(sanitized))
        self.assertNotIn("super_secret_discord_oauth_secret", str(sanitized))
        self.assertNotIn("my_secure_password_123", str(sanitized))
        self.assertEqual(sanitized["normal_data"], "public_username")

    def test_in_memory_obfuscated_string(self):
        from core.security import ObfuscatedString
        secret_text = "VanguardSafeSecretToken_2026"
        obf = ObfuscatedString(secret_text, key_seed=0x42)
        # Representation should be masked
        self.assertIn("[Protected]", repr(obf))
        # Plaintext should not be in the internal raw bytes directly
        self.assertNotIn(b"VanguardSafeSecretToken_2026", obf._encoded)
        # Reveal decrypts accurately
        self.assertEqual(obf.reveal(), secret_text)

    def test_integrity_guard_and_timing(self):
        from core.security import security_guard, verify_timing_integrity
        self.assertTrue(verify_timing_integrity())
        check = security_guard.self_check()
        self.assertIn("is_secure", check)
        self.assertIn("debugger_detected", check)
        self.assertIn("timing_integrity", check)

    def test_oauth_authorization_urls(self):
        from core.auth import auth_manager
        redirect_uri = "http://127.0.0.1:8000/api/auth/callback/discord"
        url = auth_manager.generate_authorization_url("discord", redirect_uri)
        self.assertTrue("discord" in url or "mock-login" in url)

    def test_session_token_cryptographic_signing_and_tampering(self):
        from core.auth import auth_manager, UserSession
        user = UserSession(
            user_id="user_test_99",
            username="TestPlayer",
            display_name="Test Commander",
            email="test@game.local",
            avatar_url="",
            provider="github",
            role="admin"
        )
        token = auth_manager.issue_session_token(user)
        self.assertIn(".", token)

        # Verify valid token
        verified = auth_manager.verify_session_token(token)
        self.assertIsNotNone(verified)
        self.assertEqual(verified.username, "TestPlayer")
        self.assertEqual(verified.provider, "github")

        # Test Tampering detection (altering signature or payload)
        tampered_token = token[:-4] + "ffff"
        self.assertIsNone(auth_manager.verify_session_token(tampered_token))


if __name__ == "__main__":
    unittest.main()
