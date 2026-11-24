"""
Safe Read-Only Multi-Game Process Watcher for Valorant, Minecraft, Roblox, and Desktop.
Compliance guarantee:
- Uses ONLY psutil process enumeration.
- Strictly read-only: checks process name and pid.
- NEVER calls ReadProcessMemory, OpenProcess with write permissions, or DLL hooks.
- 100% compliant with anti-cheat and security policies.
"""

import threading
import time
from typing import Callable, List, Optional, Dict

try:
    import psutil
except ImportError:
    psutil = None

from core.game_profiles import game_profile_manager, GameProfile


class ProcessWatcher:
    """Monitors running games passively and switches GameProfiles automatically."""

    def __init__(self, target_process_name: str = "VALORANT-Win64-Shipping.exe", interval: float = 2.0):
        self.interval = max(0.5, interval)
        self.is_running = False
        self.current_pid: Optional[int] = None
        self.current_active_profile: str = "desktop"
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_game_start_callbacks: List[Callable[[int], None]] = []
        self.on_game_stop_callbacks: List[Callable[[], None]] = []
        self.on_profile_change_callbacks: List[Callable[[str], None]] = []

    def register_start_callback(self, cb: Callable[[int], None]) -> None:
        self.on_game_start_callbacks.append(cb)

    def register_stop_callback(self, cb: Callable[[], None]) -> None:
        self.on_game_stop_callbacks.append(cb)

    def register_profile_callback(self, cb: Callable[[str], None]) -> None:
        self.on_profile_change_callbacks.append(cb)

    def check_process_status(self) -> bool:
        """Passive scan across running process names to identify active game."""
        if psutil is None:
            return False

        detected_profile_id: Optional[str] = None
        detected_pid: Optional[int] = None
        detected_proc_name: Optional[str] = None

        process_map = game_profile_manager.get_all_target_processes()

        try:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    name = proc.info["name"]
                    if not name:
                        continue
                    name_lower = name.lower()
                    if name_lower in process_map:
                        detected_profile_id = process_map[name_lower]
                        detected_pid = proc.info["pid"]
                        detected_proc_name = name
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass

        # Handle Profile Switching
        if detected_profile_id is not None:
            if not self.is_running or self.current_active_profile != detected_profile_id:
                self.is_running = True
                self.current_pid = detected_pid
                old_profile = self.current_active_profile
                self.current_active_profile = detected_profile_id
                game_profile_manager.set_active_profile(detected_profile_id)
                print(f"[ProcessWatcher] Game detected: '{detected_proc_name}' (PID: {detected_pid}) -> Switched profile to '{detected_profile_id}'")

                # Valorant / general game start callbacks
                for cb in self.on_game_start_callbacks:
                    try:
                        cb(detected_pid or 0)
                    except Exception as e:
                        print(f"[ProcessWatcher] Start callback error: {e}")

                # Profile change callbacks
                for cb in self.on_profile_change_callbacks:
                    try:
                        cb(detected_profile_id)
                    except Exception as e:
                        print(f"[ProcessWatcher] Profile callback error: {e}")

        else:
            # No game detected
            if self.is_running:
                self.is_running = False
                self.current_pid = None
                self.current_active_profile = "desktop"
                game_profile_manager.set_active_profile("desktop")
                print("[ProcessWatcher] Game closed -> Reverting to Desktop Companion profile")

                for cb in self.on_game_stop_callbacks:
                    try:
                        cb()
                    except Exception as e:
                        print(f"[ProcessWatcher] Stop callback error: {e}")

                for cb in self.on_profile_change_callbacks:
                    try:
                        cb("desktop")
                    except Exception as e:
                        print(f"[ProcessWatcher] Profile callback error: {e}")

        return self.is_running

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            self.check_process_status()
            self._stop_event.wait(self.interval)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="MultiGameProcessWatcher")
        self._thread.start()
        print("[ProcessWatcher] Started multi-game passive process monitor")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        print("[ProcessWatcher] Stopped")


# Global process watcher singleton
process_watcher = ProcessWatcher()
