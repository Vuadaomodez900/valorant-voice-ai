"""
Safe Read-Only Process Watcher for Valorant.
Compliance guarantee:
- Uses ONLY psutil process enumeration.
- Strictly read-only: checks process name and pid.
- NEVER calls ReadProcessMemory, OpenProcess with write permissions, or DLL hooks.
- 100% compliant with Riot Vanguard policies.
"""

import threading
import time
from typing import Callable, List, Optional
import psutil


class ProcessWatcher:
    """Monitors if Valorant process is running in a strictly non-intrusive way."""

    def __init__(self, target_process_name: str = "VALORANT-Win64-Shipping.exe", interval: float = 2.0):
        self.target_name = target_process_name.lower()
        self.interval = max(0.5, interval)
        self.is_running = False
        self.current_pid: Optional[int] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_game_start_callbacks: List[Callable[[int], None]] = []
        self.on_game_stop_callbacks: List[Callable[[], None]] = []

    def register_start_callback(self, cb: Callable[[int], None]) -> None:
        self.on_game_start_callbacks.append(cb)

    def register_stop_callback(self, cb: Callable[[], None]) -> None:
        self.on_game_stop_callbacks.append(cb)

    def check_process_status(self) -> bool:
        """Passive scan across running process names."""
        found = False
        pid_found = None
        try:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    name = proc.info["name"]
                    if name and name.lower() == self.target_name:
                        found = True
                        pid_found = proc.info["pid"]
                        break
                    # Fallback check for bootstrap process
                    if name and name.lower() == "valorant.exe":
                        found = True
                        pid_found = proc.info["pid"]
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass

        if found and not self.is_running:
            self.is_running = True
            self.current_pid = pid_found
            print(f"[ProcessWatcher] Valorant detected (PID: {pid_found}) - Activating Game Profile")
            for cb in self.on_game_start_callbacks:
                try:
                    cb(pid_found or 0)
                except Exception as e:
                    print(f"[ProcessWatcher] Callback error on start: {e}")

        elif not found and self.is_running:
            self.is_running = False
            self.current_pid = None
            print("[ProcessWatcher] Valorant closed - Restoring idle profile")
            for cb in self.on_game_stop_callbacks:
                try:
                    cb()
                except Exception as e:
                    print(f"[ProcessWatcher] Callback error on stop: {e}")

        return self.is_running

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            self.check_process_status()
            self._stop_event.wait(self.interval)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ValorantProcessWatcher")
        self._thread.start()
        print(f"[ProcessWatcher] Started watching for '{self.target_name}' (passive loop)")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        print("[ProcessWatcher] Stopped")
