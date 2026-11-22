"""
Automated Internet Tunnel Manager for Valorant Voice AI.
Enables remote mobile connection from anywhere (4G/5G/WAN) without Wi-Fi,
without router port forwarding, and without requiring external account signups.
Supports:
1. Windows built-in OpenSSH (Pinggy / Localhost.run) - 0 downloads required.
2. Cloudflare Quick Tunnels (trycloudflare.com).
"""

import sys
import os
import re
import time
import shutil
import subprocess
import threading
from typing import Optional, Callable


class RemoteTunnelManager:
    """Manages secure outbound reverse tunnel to expose port 8000 to the internet."""

    def __init__(self, local_port: int = 8000):
        self.local_port = local_port
        self.tunnel_process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.is_active = False
        self._lock = threading.Lock()

    def find_ssh(self) -> Optional[str]:
        """Locates SSH executable (native to Windows 10/11 & Linux/macOS)."""
        ssh_path = shutil.which("ssh")
        if ssh_path:
            return ssh_path
        if sys.platform == "win32":
            win_ssh = r"C:\Windows\System32\OpenSSH\ssh.exe"
            if os.path.exists(win_ssh):
                return win_ssh
        return None

    def find_cloudflared(self) -> Optional[str]:
        """Finds cloudflared binary if installed."""
        return shutil.which("cloudflared")

    def start_tunnel(self, on_url_ready: Optional[Callable[[str], None]] = None) -> None:
        """Starts tunnel in a background daemon thread."""
        with self._lock:
            if self.is_active and self.public_url:
                if on_url_ready:
                    on_url_ready(self.public_url)
                return

        def _worker():
            url = self._spawn_tunnel_process()
            with self._lock:
                self.public_url = url
                self.is_active = bool(url)
            if url and on_url_ready:
                on_url_ready(url)

        threading.Thread(target=_worker, daemon=True, name="RemoteTunnelWorkerThread").start()

    def _spawn_tunnel_process(self) -> Optional[str]:
        # Strategy 1: Check for cloudflared
        cf_bin = self.find_cloudflared()
        if cf_bin:
            try:
                cmd = [cf_bin, "tunnel", "--url", f"http://localhost:{self.local_port}"]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.tunnel_process = proc
                # Look for trycloudflare.com
                for _ in range(60):
                    line = proc.stdout.readline()
                    if not line:
                        break
                    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                    if match:
                        url = match.group(0)
                        print(f"[RemoteTunnel] Cloudflare Tunnel Live: {url}")
                        return url
            except Exception as e:
                print(f"[RemoteTunnel] Cloudflare tunnel failed: {e}")

        # Strategy 2: Windows Built-in OpenSSH with Pinggy (0 install, instant)
        ssh_bin = self.find_ssh()
        if ssh_bin:
            try:
                # pinggy.io free tunnel over port 443 with TLS
                cmd = [
                    ssh_bin,
                    "-p", "443",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ServerAliveInterval=30",
                    "-R0:localhost:" + str(self.local_port),
                    "a.pinggy.io"
                ]
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.tunnel_process = proc
                for _ in range(50):
                    line = proc.stdout.readline()
                    if not line:
                        break
                    # Pinggy URL pattern: https://xxxx.a.pinggy.link or free.pinggy.link
                    match = re.search(r"https://[a-zA-Z0-9-]+\.(?:a|free)\.pinggy\.link", line)
                    if match:
                        url = match.group(0)
                        print(f"[RemoteTunnel] Pinggy SSH Tunnel Live: {url}")
                        return url
                    # Localhost.run fallback pattern
                    match_lhr = re.search(r"https://[a-zA-Z0-9-]+\.lhr\.life", line)
                    if match_lhr:
                        url = match_lhr.group(0)
                        print(f"[RemoteTunnel] Localhost.run Tunnel Live: {url}")
                        return url
            except Exception as e:
                print(f"[RemoteTunnel] SSH Pinggy tunnel failed: {e}")

            # Strategy 3: Localhost.run via OpenSSH
            try:
                cmd_lhr = [
                    ssh_bin,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ServerAliveInterval=30",
                    "-R", f"80:localhost:{self.local_port}",
                    "nokey@localhost.run"
                ]
                proc_lhr = subprocess.Popen(
                    cmd_lhr,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.tunnel_process = proc_lhr
                for _ in range(50):
                    line = proc_lhr.stdout.readline()
                    if not line:
                        break
                    match = re.search(r"https://[a-zA-Z0-9-]+\.lhr\.life", line)
                    if match:
                        url = match.group(0)
                        print(f"[RemoteTunnel] Localhost.run Tunnel Live: {url}")
                        return url
            except Exception as e:
                print(f"[RemoteTunnel] Localhost.run failed: {e}")

        return None

    def stop_tunnel(self) -> None:
        """Kills the active tunnel subprocess."""
        with self._lock:
            if self.tunnel_process:
                try:
                    self.tunnel_process.terminate()
                    self.tunnel_process.wait(timeout=2)
                except Exception:
                    try:
                        self.tunnel_process.kill()
                    except Exception:
                        pass
                self.tunnel_process = None
            self.public_url = None
            self.is_active = False


tunnel_manager = RemoteTunnelManager(local_port=8000)
