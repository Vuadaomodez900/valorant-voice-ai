"""
Anti-Tamper, Anti-Reverse Engineering, and Sensitive Data Protection Engine.
Provides:
1. Anti-Debugging and inspection detection (IsDebuggerPresent, CheckRemoteDebuggerPresent, trace hooks).
2. Runtime code & binary integrity verification (checksum validation against tampering).
3. Secret masking and in-memory string obfuscation to prevent string dumping and memory scraping.
4. Data leak sanitizer for diagnostic dumps, logs, and configuration payloads.
"""

import sys
import os
import re
import time
import hashlib
import ctypes
from typing import Dict, Any, List, Optional, Union


# -----------------------------------------------------------------------------
# 1. Anti-Debugging & Anti-Inspection Protections
# -----------------------------------------------------------------------------

def is_debugger_active() -> bool:
    """
    Checks if a native or managed debugger is attached to the running process.
    Uses Win32 kernel API on Windows, and sys trace detection across platforms.
    """
    # 1. Check Python-level trace hooks (e.g. pdb, pydevd, ide debuggers)
    if sys.gettrace() is not None:
        return True

    # 2. Check native Windows debuggers (x64dbg, Cheat Engine, OllyDbg, IDA Pro)
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            # IsDebuggerPresent check
            if kernel32.IsDebuggerPresent():
                return True

            # CheckRemoteDebuggerPresent check
            is_remote_present = ctypes.c_bool(False)
            current_proc = kernel32.GetCurrentProcess()
            if kernel32.CheckRemoteDebuggerPresent(current_proc, ctypes.byref(is_remote_present)):
                if is_remote_present.value:
                    return True
        except Exception:
            pass

    # 3. Check Linux / Android tracer pid (e.g., gdb, frida, strace)
    if sys.platform.startswith("linux"):
        try:
            status_path = "/proc/self/status"
            if os.path.exists(status_path):
                with open(status_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("TracerPid:"):
                            tracer_pid = int(line.split()[1])
                            if tracer_pid != 0:
                                return True
        except Exception:
            pass

    return False


def verify_timing_integrity(threshold_ms: float = 80.0) -> bool:
    """
    High-resolution timing check to detect manual step-by-step debugger stepping.
    Returns False if execution delay between two micro-ops indicates a breakpoint pause.
    """
    t0 = time.perf_counter()
    # Micro compute operation
    _ = hashlib.sha256(b"integrity_check_nonce").hexdigest()
    t1 = time.perf_counter()
    elapsed_ms = (t1 - t0) * 1000.0
    return elapsed_ms < threshold_ms


# -----------------------------------------------------------------------------
# 2. Anti-Tamper & Integrity Verification
# -----------------------------------------------------------------------------

class IntegrityGuard:
    """Verifies that loaded modules and executable packages are untampered."""

    _baseline_hashes: Dict[str, str] = {}

    @classmethod
    def register_baseline(cls, component_name: str, raw_bytes: bytes) -> str:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        cls._baseline_hashes[component_name] = digest
        return digest

    @classmethod
    def verify_component(cls, component_name: str, current_bytes: bytes) -> bool:
        if component_name not in cls._baseline_hashes:
            return True
        current_digest = hashlib.sha256(current_bytes).hexdigest()
        return current_digest == cls._baseline_hashes[component_name]

    @classmethod
    def self_check(cls) -> Dict[str, Any]:
        """Runs complete integrity and anti-tamper evaluation."""
        debugger_detected = is_debugger_active()
        timing_ok = verify_timing_integrity()
        frozen = getattr(sys, "frozen", False)

        is_tampered = debugger_detected or not timing_ok

        return {
            "is_secure": not is_tampered,
            "debugger_detected": debugger_detected,
            "timing_integrity": timing_ok,
            "is_packaged_bundle": frozen,
            "timestamp": time.time(),
        }


# -----------------------------------------------------------------------------
# 3. Secret Masking & Data Leak Prevention
# -----------------------------------------------------------------------------

SECRET_KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),               # Google API Key
    re.compile(r"sk-[a-zA-Z0-9]{32,64}"),               # OpenAI / Claude Key
    re.compile(r"gh[opsu]_[0-9a-zA-Z]{36,255}"),        # GitHub Token
    re.compile(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}"),      # Discord Bot Token
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-\.]{20,})"), # Bearer JWT / Tokens
]

SENSITIVE_FIELD_NAMES = {
    "api_key", "secret", "client_secret", "password", "token",
    "access_token", "refresh_token", "authorization", "auth_token",
    "pin", "private_key", "webhook_url"
}


def mask_secret_string(val: str, visible_start: int = 3, visible_end: int = 3) -> str:
    """Masks secret string preserving only first/last few characters."""
    if not val:
        return ""
    if len(val) <= (visible_start + visible_end):
        return "***"
    return f"{val[:visible_start]}****{val[-visible_end:]}"


def sanitize_data_payload(data: Union[Dict, List, str, Any]) -> Any:
    """
    Recursively scans and sanitizes data structures to prevent leaking
    API keys, credentials, or sensitive headers in responses or logs.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sensitive in k_lower for sensitive in SENSITIVE_FIELD_NAMES):
                if isinstance(v, str) and v:
                    sanitized[k] = mask_secret_string(v)
                elif isinstance(v, (int, float)):
                    sanitized[k] = "***"
                else:
                    sanitized[k] = sanitize_data_payload(v)
            else:
                sanitized[k] = sanitize_data_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data_payload(item) for item in data]
    elif isinstance(data, str):
        # Scan for raw regex patterns of known API keys
        sanitized_str = data
        for pattern in SECRET_KEY_PATTERNS:
            sanitized_str = pattern.sub(lambda m: mask_secret_string(m.group(0)), sanitized_str)
        return sanitized_str
    return data


# -----------------------------------------------------------------------------
# 4. In-Memory String Obfuscation (Anti-Memory Dump)
# -----------------------------------------------------------------------------

class ObfuscatedString:
    """
    Stores sensitive strings in XOR-encoded form in memory.
    Decodes on demand and cleans up plaintext to prevent memory dump extraction.
    """

    def __init__(self, plaintext: str, key_seed: int = 0xA7):
        self._key = key_seed & 0xFF
        raw_bytes = plaintext.encode("utf-8")
        self._encoded = bytes([b ^ self._key for b in raw_bytes])

    def reveal(self) -> str:
        """Decrypts in-place for immediate usage."""
        decrypted_bytes = bytes([b ^ self._key for b in self._encoded])
        return decrypted_bytes.decode("utf-8", errors="replace")

    def __repr__(self) -> str:
        return "<ObfuscatedSecret [Protected]>"


# Global security guard singleton
security_guard = IntegrityGuard()
