"""
Self-Healing, Auto-Configuration, and Autonomous Diagnostics Engine for Valorant Voice AI.
Features:
- Zero-touch auto-configuration on application startup ("Mở lên là dùng được luôn").
- Automatic detection and background installation of missing components & drivers.
- Complete system health diagnostics.
- Autonomous self-repair (Auto-Fix) for audio devices, screen capture, tunnels, and network.
- Dynamic runtime reconfiguration API for AI agents (AGY CLI / Remote Controller).
"""

import os
import sys
import time
import threading
from typing import Dict, Any, List, Optional, Tuple

from core.config import config
from core.cable_installer import is_vbcable_installed, install_vbcable_integrated
from core.remote_tunnel import tunnel_manager


class SystemSelfHealer:
    """Monitors, self-repairs, auto-configures, and exposes mutation API to AI agents."""

    def __init__(self):
        self.orchestrator = None
        self._lock = threading.Lock()
        self.last_fix_log: List[str] = []
        self.last_fix_time: float = 0.0

    def bind_orchestrator(self, orchestrator) -> None:
        """Binds running orchestrator to allow self-repair actions on live components."""
        self.orchestrator = orchestrator

    def auto_heal_on_startup(self) -> List[str]:
        """
        Executes zero-touch auto-configuration when the application launches:
        1. Auto-loads GEMINI_API_KEY from environment if not present in config.
        2. Auto-detects and auto-installs VB-Audio Virtual Cable if missing.
        3. Auto-configures optimal default audio devices if not explicitly chosen.
        4. Auto-starts Internet Tunnel in the background so mobile AI can connect immediately.
        """
        logs = []
        print("[SelfHealer] Running zero-touch startup auto-configuration...")

        # 1. Environment API Key auto-load
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        cfg_key = config.data.get("gemini", {}).get("api_key", "").strip()
        if not cfg_key and env_key:
            config.data["gemini"]["api_key"] = env_key
            config.save()
            logs.append("Đã tự động nạp GEMINI_API_KEY từ biến môi trường.")
            print("[SelfHealer] Auto-loaded GEMINI_API_KEY from environment.")

        # 2. Check and auto-install Virtual Cable driver if missing (on Windows)
        if sys.platform == "win32":
            if not is_vbcable_installed():
                print("[SelfHealer] Virtual Audio Cable not detected. Auto-installing in background...")
                logs.append("Chưa có Virtual Cable: Đang tự động kích hoạt bộ cài driver tích hợp...")
                def _bg_install():
                    success, msg = install_vbcable_integrated()
                    if success:
                        print(f"[SelfHealer] Auto-installation of Virtual Cable successful: {msg}")
                        if self.orchestrator and hasattr(self.orchestrator, "router"):
                            self.orchestrator.router.start(virtual_cable_name="CABLE Input")
                    else:
                        print(f"[SelfHealer] Auto-installation note: {msg}")

                threading.Thread(target=_bg_install, daemon=True, name="AutoCableInstaller").start()
            else:
                logs.append("Virtual Audio Cable: Đã sẵn sàng.")

        # 3. Auto-start Remote Internet Tunnel (Zero-configuration WAN connection)
        def _on_tunnel_ready(url: str):
            print(f"[SelfHealer] Internet Tunnel auto-started: {url}")

        tunnel_manager.start_tunnel(on_url_ready=_on_tunnel_ready)
        logs.append("Đã tự động khởi động đường truyền Internet Tunnel cho điện thoại.")

        self.last_fix_log = logs
        self.last_fix_time = time.time()
        return logs

    def diagnose_system(self) -> Dict[str, Any]:
        """Provides a comprehensive health check across all sub-systems."""
        issues: List[str] = []
        warnings: List[str] = []

        # 1. Driver status
        cable_ok = is_vbcable_installed()
        if not cable_ok:
            if sys.platform == "win32":
                issues.append("Chưa cài đặt Virtual Audio Cable (đồng đội in-game chưa thể nghe giọng AI).")
            else:
                warnings.append("Môi trường không phải Windows: Chế độ giả lập âm thanh đang chạy.")

        # 2. Audio Router status
        audio_running = False
        mic_bound = False
        cable_bound = False
        hp_bound = False
        if self.orchestrator and hasattr(self.orchestrator, "router"):
            router = self.orchestrator.router
            audio_running = router.is_running
            mic_bound = router.physical_mic_id is not None or sys.platform != "win32"
            cable_bound = router.virtual_cable_out_id is not None or sys.platform != "win32"
            hp_bound = router.headphone_out_id is not None or sys.platform != "win32"

        if not audio_running:
            issues.append("Động cơ Audio Router chưa chạy.")

        # 3. Screen Capture status
        screen_running = False
        screen_fps = 2
        if self.orchestrator and hasattr(self.orchestrator, "screen_manager"):
            screen_mgr = self.orchestrator.screen_manager
            screen_running = screen_mgr.is_running
            screen_fps = screen_mgr.fps_live
        if not screen_running:
            issues.append("Động cơ chụp màn hình DXGI chưa chạy.")

        # 4. Gemini Live API status
        has_api_key = bool(config.data.get("gemini", {}).get("api_key") or os.environ.get("GEMINI_API_KEY"))
        bridge_connected = False
        if self.orchestrator and hasattr(self.orchestrator, "bridge"):
            bridge_connected = self.orchestrator.bridge.is_connected
        if not has_api_key:
            warnings.append("Chưa cấu hình GEMINI_API_KEY (AI trợ lý thoại đang ở chế độ chờ).")

        # 5. Game process status
        is_game_running = False
        game_pid = None
        if self.orchestrator and hasattr(self.orchestrator, "process_watcher"):
            is_game_running = self.orchestrator.process_watcher.is_process_running()
            game_pid = self.orchestrator.process_watcher.current_pid

        # 6. Internet Tunnel status
        tunnel_active = tunnel_manager.is_active
        tunnel_url = tunnel_manager.public_url

        # Health score calculation (0 - 100)
        score = 100
        score -= len(issues) * 25
        score -= len(warnings) * 10
        score = max(0, min(100, score))

        return {
            "health_score": score,
            "status": "HEALTHY" if score >= 80 else ("DEGRADED" if score >= 50 else "CRITICAL"),
            "issues": issues,
            "warnings": warnings,
            "subsystems": {
                "driver": {
                    "vbcable_installed": cable_ok,
                },
                "audio": {
                    "running": audio_running,
                    "mic_connected": mic_bound,
                    "virtual_cable_connected": cable_bound,
                    "headphones_connected": hp_bound,
                },
                "screen": {
                    "running": screen_running,
                    "fps": screen_fps,
                },
                "gemini": {
                    "has_key": has_api_key,
                    "connected": bridge_connected,
                    "model": config.data.get("gemini", {}).get("model", "gemini-2.0-flash-exp"),
                },
                "tunnel": {
                    "active": tunnel_active,
                    "url": tunnel_url,
                },
                "game": {
                    "valorant_running": is_game_running,
                    "pid": game_pid,
                }
            },
            "last_fix_log": self.last_fix_log,
            "timestamp": time.time()
        }

    def auto_fix_system(self) -> Dict[str, Any]:
        """
        Autonomous Self-Healing routine:
        Diagnoses issues and actively executes repairs.
        Can be triggered by the user or remotely by AI agents.
        """
        with self._lock:
            fix_actions: List[str] = []
            print("[SelfHealer] Initiating autonomous self-repair routine...")

            # 1. Driver auto-fix
            if sys.platform == "win32" and not is_vbcable_installed():
                success, msg = install_vbcable_integrated()
                if success:
                    fix_actions.append("Đã tự động cài đặt driver VB-Audio Virtual Cable tích hợp.")
                else:
                    fix_actions.append(f"Cài đặt driver: {msg}")

            # 2. Audio Router re-bind and re-start
            if self.orchestrator and hasattr(self.orchestrator, "router"):
                try:
                    router = self.orchestrator.router
                    cfg_audio = config.data["audio"]
                    router.stop()
                    time.sleep(0.2)
                    success = router.start(
                        physical_mic_name=cfg_audio.get("physical_mic", ""),
                        virtual_cable_name=cfg_audio.get("virtual_mic_out", "CABLE Input"),
                        headphone_name=cfg_audio.get("headphone_out", "")
                    )
                    if success:
                        fix_actions.append("Đã khởi động lại và kết nối lại các luồng âm thanh.")
                except Exception as e:
                    fix_actions.append(f"Khởi động lại audio thất bại: {e}")

            # 3. Screen Capture re-start
            if self.orchestrator and hasattr(self.orchestrator, "screen_manager"):
                try:
                    sm = self.orchestrator.screen_manager
                    if not sm.is_running:
                        sm.start()
                        fix_actions.append("Đã khởi động lại bộ quay màn hình DXGI Desktop Duplication.")
                except Exception as e:
                    fix_actions.append(f"Khởi động lại màn hình: {e}")

            # 4. Internet Tunnel re-spawn if dead
            if not tunnel_manager.is_active or not tunnel_manager.public_url:
                try:
                    tunnel_manager.stop_tunnel()
                    tunnel_manager.start_tunnel()
                    fix_actions.append("Đã tái tạo đường truyền Internet Tunnel mới.")
                except Exception as e:
                    fix_actions.append(f"Tạo lại tunnel: {e}")

            # 5. Gemini Bridge re-sync
            env_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not config.data.get("gemini", {}).get("api_key") and env_key:
                config.data["gemini"]["api_key"] = env_key
                config.save()
                fix_actions.append("Đã tự động cập nhật GEMINI_API_KEY từ biến môi trường.")

            self.last_fix_log = fix_actions
            self.last_fix_time = time.time()

            new_diag = self.diagnose_system()
            return {
                "success": True,
                "actions_taken": fix_actions,
                "health_after_fix": new_diag["health_score"],
                "status": new_diag["status"],
                "diagnostics": new_diag
            }

    def update_runtime_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allows AI agents or mobile client to dynamically reconfigure ANY setting
        and immediately hot-reload the running engines without app restart.
        """
        with self._lock:
            applied_keys: List[str] = []

            for key, val in updates.items():
                parts = key.split(".")
                if len(parts) == 1:
                    config.data[parts[0]] = val
                    applied_keys.append(parts[0])
                elif len(parts) == 2:
                    sec, field = parts
                    if sec not in config.data:
                        config.data[sec] = {}
                    config.data[sec][field] = val
                    applied_keys.append(key)
                elif len(parts) == 3:
                    sec, sub, field = parts
                    if sec not in config.data:
                        config.data[sec] = {}
                    if sub not in config.data[sec]:
                        config.data[sec][sub] = {}
                    config.data[sec][sub][field] = val
                    applied_keys.append(key)

            config.save()

            # Hot-apply to running engines
            if self.orchestrator:
                # 1. Audio changes
                if hasattr(self.orchestrator, "router"):
                    r = self.orchestrator.router
                    cfg_audio = config.data.get("audio", {})
                    if "audio.volume_headphone" in applied_keys or "volume_headphone" in applied_keys:
                        r.set_headphone_volume(cfg_audio.get("volume_headphone", 1.0))
                    if "audio.volume_game_mic" in applied_keys or "volume_game_mic" in applied_keys:
                        r.set_game_mic_volume(cfg_audio.get("volume_game_mic", 1.0))
                    if "audio.mute_game_mic" in applied_keys:
                        r.mute_game_mic = cfg_audio.get("mute_game_mic", False)
                    if "audio.auto_mic_trigger" in applied_keys:
                        r.auto_mic_trigger = cfg_audio.get("auto_mic_trigger", True)
                    if "audio.ptt_key" in applied_keys:
                        r.ptt_key = cfg_audio.get("ptt_key", "v")

                # 2. Teammate Trigger
                if "audio.teammate_voice_trigger" in applied_keys:
                    self.orchestrator.set_teammate_voice_trigger(config.data["audio"].get("teammate_voice_trigger", True))

                # 3. Screen FPS
                if hasattr(self.orchestrator, "screen_manager"):
                    if "screen.fps_live_stream" in applied_keys or "fps_live_stream" in applied_keys:
                        self.orchestrator.screen_manager.set_live_fps(config.data["screen"].get("fps_live_stream", 2))

                # 4. Gemini Bridge updates
                if hasattr(self.orchestrator, "bridge"):
                    b = self.orchestrator.bridge
                    cfg_gemini = config.data.get("gemini", {})
                    if "gemini.api_key" in applied_keys and cfg_gemini.get("api_key"):
                        b.api_key = cfg_gemini["api_key"]
                    if "gemini.voice_name" in applied_keys:
                        b.voice_name = cfg_gemini.get("voice_name", "Puck")
                    if "gemini.model" in applied_keys:
                        b.model_name = cfg_gemini.get("model", "gemini-2.0-flash-exp")

            return {
                "status": "ok",
                "applied_keys": applied_keys,
                "message": f"Đã cập nhật và áp dụng nóng {len(applied_keys)} cài đặt thành công."
            }


# Singleton instance
self_healer = SystemSelfHealer()
